from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import heapq
import math
import mmap
from pathlib import Path
import re
import statistics
import struct
from typing import Sequence

from src.adapters import peak_detection_adapter


DEFAULT_DATABASE_STEM = "ICSD-ALL"
DEFAULT_PEAK_PROMINENCE_NORMALIZED = 0.05
DEFAULT_MINIMUM_PEAK_DISTANCE_DEG = 0.10
_J7_XID_HEADER_SIZE = 12
# J7 XID carries its count through byte 11, while the companion SID/RID
# streams observed by the existing reader start their records at byte 7.
_J7_SID_RID_HEADER_SIZE = 7
_J7_RID_RECORD_SIZE = 9


@dataclass(frozen=True)
class XidRecord:
    pdf_number: int
    sid_offset: int
    rid_offset: int
    database_number: int


@dataclass(frozen=True)
class ObservedPeak:
    index: int
    two_theta_deg: float
    intensity: float
    normalized_intensity: float


@dataclass(frozen=True)
class XrdPhaseMatchOptions:
    database_dir: Path
    database_stem: str = DEFAULT_DATABASE_STEM
    card_ids: tuple[str, ...] = ()
    card_queries: tuple[str, ...] = ()
    full_library_screen: bool = False
    query_limit: int = 20
    result_limit: int = 20
    wavelength_angstrom: float = 1.5406
    peak_prominence_normalized: float = DEFAULT_PEAK_PROMINENCE_NORMALIZED
    minimum_peak_distance_deg: float = DEFAULT_MINIMUM_PEAK_DISTANCE_DEG
    card_tolerance_deg: float = 0.20
    minimum_card_relative_intensity: float = 10.0

    def validate(self) -> None:
        _validate_database_stem(self.database_stem)
        if self.full_library_screen and (self.card_ids or self.card_queries):
            raise ValueError("Full-library XRD screening cannot be combined with explicit card IDs or queries")
        if not self.full_library_screen and not (self.card_ids or self.card_queries):
            raise ValueError("XRD phase matching requires a card ID, card query, or full-library screen")
        if self.query_limit <= 0 or self.result_limit <= 0:
            raise ValueError("XRD query and result limits must be positive")
        if self.wavelength_angstrom <= 0:
            raise ValueError("XRD wavelength must be positive")
        if not 0 <= self.peak_prominence_normalized <= 1:
            raise ValueError("XRD peak prominence must be between 0 and 1")
        if self.minimum_peak_distance_deg <= 0 or self.card_tolerance_deg <= 0:
            raise ValueError("XRD peak distance and card tolerance must be positive")
        if not 0 <= self.minimum_card_relative_intensity <= 100:
            raise ValueError("XRD minimum card intensity must be between 0 and 100")


class JadeIndex:
    """Read one unpacked Jade J7 XID/SID/RID database group.

    XID is small enough to parse eagerly. SID and RID are memory-mapped so a
    full ICSD library does not require copying both large files into Python
    heap memory. The class owns its file handles and should be used as a
    context manager.
    """

    def __init__(self, database_dir: Path, stem: str = DEFAULT_DATABASE_STEM) -> None:
        self.database_dir = database_dir.expanduser().resolve(strict=False)
        self.stem = _validate_database_stem(stem)
        self.xid_path = self._database_file(".xid")
        self.sid_path = self._database_file(".sid")
        self.rid_path = self._database_file(".rid")
        missing = [path.name for path in (self.xid_path, self.sid_path, self.rid_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Jade index is incomplete; missing: {', '.join(missing)}")

        xid = self.xid_path.read_bytes()
        if len(xid) < 12 or xid[:2] != b"J7":
            raise ValueError(f"Unsupported or corrupt Jade XID header: {self.xid_path.name}")
        count = struct.unpack_from("<I", xid, 8)[0]
        required = _J7_XID_HEADER_SIZE + count * 16
        if count <= 0 or required > len(xid):
            raise ValueError(f"Invalid Jade XID record count: {count}")
        self.records = tuple(
            XidRecord(*struct.unpack_from("<IIII", xid, _J7_XID_HEADER_SIZE + index * 16))
            for index in range(count)
        )
        pdf_numbers = [record.pdf_number for record in self.records]
        if len(set(pdf_numbers)) != len(pdf_numbers):
            raise ValueError(f"Jade XID contains duplicate card IDs: {self.xid_path.name}")
        self._validate_record_offsets()
        self._record_by_pdf = {record.pdf_number: index for index, record in enumerate(self.records)}

        self._sid_handle = self.sid_path.open("rb")
        self._rid_handle = self.rid_path.open("rb")
        self._sid: mmap.mmap | None = None
        self._rid: mmap.mmap | None = None
        try:
            self._sid = mmap.mmap(self._sid_handle.fileno(), 0, access=mmap.ACCESS_READ)
            self._rid = mmap.mmap(self._rid_handle.fileno(), 0, access=mmap.ACCESS_READ)
        except Exception:
            if self._sid is not None:
                self._sid.close()
            if self._rid is not None:
                self._rid.close()
            self._sid_handle.close()
            self._rid_handle.close()
            raise
        self._closed = False

    def _database_file(self, suffix: str) -> Path:
        """Resolve one required database member without permitting path escape."""
        path = (self.database_dir / f"{self.stem}{suffix}").resolve(strict=False)
        try:
            path.relative_to(self.database_dir)
        except ValueError as exc:
            raise ValueError("Jade database member resolves outside database_dir") from exc
        return path

    def _validate_record_offsets(self) -> None:
        """Check table boundaries before mmap so malformed indices cannot slice arbitrarily."""
        sid_size = self.sid_path.stat().st_size
        rid_size = self.rid_path.stat().st_size
        if sid_size <= _J7_SID_RID_HEADER_SIZE or rid_size <= _J7_SID_RID_HEADER_SIZE:
            raise ValueError("Jade SID/RID files are missing their payload records")
        with self.sid_path.open("rb") as handle:
            sid_magic = handle.read(2)
        with self.rid_path.open("rb") as handle:
            rid_magic = handle.read(2)
        if sid_magic != b"J7" or rid_magic != b"J7":
            raise ValueError("Unsupported or corrupt Jade SID/RID header")

        previous_sid = _J7_SID_RID_HEADER_SIZE - 1
        previous_rid = _J7_SID_RID_HEADER_SIZE - 1
        for index, record in enumerate(self.records):
            if not (_J7_SID_RID_HEADER_SIZE <= record.sid_offset < sid_size):
                raise ValueError(f"Jade SID offset is outside file bounds at index {index}")
            if not (_J7_SID_RID_HEADER_SIZE <= record.rid_offset < rid_size):
                raise ValueError(f"Jade RID offset is outside file bounds at index {index}")
            if record.sid_offset <= previous_sid:
                raise ValueError(f"Jade SID offsets must be strictly increasing (index {index})")
            if record.rid_offset <= previous_rid:
                raise ValueError(f"Jade RID offsets must be strictly increasing (index {index})")
            previous_sid = record.sid_offset
            previous_rid = record.rid_offset

        rid_offsets = [record.rid_offset for record in self.records] + [rid_size]
        for index, (start, end) in enumerate(zip(rid_offsets, rid_offsets[1:])):
            record_size = end - start
            if record_size <= 0 or record_size % _J7_RID_RECORD_SIZE:
                raise ValueError(
                    f"Jade RID record length must be a positive multiple of {_J7_RID_RECORD_SIZE} bytes "
                    f"(index {index})"
                )

    def __enter__(self) -> JadeIndex:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        assert self._sid is not None and self._rid is not None
        self._sid.close()
        self._rid.close()
        self._sid_handle.close()
        self._rid_handle.close()
        self._closed = True

    @property
    def record_count(self) -> int:
        return len(self.records)

    def info(self) -> dict[str, object]:
        return {
            "format": "Jade unpacked PDF/ICSD J7 index",
            "stem": self.stem,
            "record_count": self.record_count,
            "required_files": [
                {"file_name": path.name, "size_bytes": path.stat().st_size}
                for path in (self.xid_path, self.sid_path, self.rid_path)
            ],
            "decoder_scope": "XID/SID metadata and RID peak-position candidate screening",
            "relative_intensity_status": "candidate; validate against a trusted card export",
        }

    def index_for_pdf(self, identifier: str | int) -> int:
        pdf_number = parse_pdf_number(identifier)
        try:
            return self._record_by_pdf[pdf_number]
        except KeyError as exc:
            raise KeyError(f"Card is not present in {self.stem}: {format_card_id(pdf_number)}") from exc

    def metadata(self, index: int) -> dict[str, object]:
        assert self._sid is not None
        record = self.records[index]
        end = self.records[index + 1].sid_offset if index + 1 < self.record_count else len(self._sid)
        raw = self._sid[record.sid_offset:end]
        if not raw:
            raise ValueError(f"Jade SID record is truncated at index {index}")
        # Real J7 SID records begin with one record-marker byte (observed 1/2).
        parts = raw[1:].split(b"\x01")
        formula = _decode_index_text(parts[0]).strip("\x00 ") if parts else ""
        database_name = _decode_index_text(parts[1].split(b"\x00", 1)[0]).strip() if len(parts) > 1 else ""
        printable = re.sub(rb"[\x00-\x1f\x7f-\xff]+", b" ", raw).decode("latin-1", errors="ignore")
        traditional: list[str] = []
        for pattern in (r"PDF#\s*([0-9]{1,2}-[0-9]{2,4})", r"data\):\s*(0[1-9]-[0-9]{3}-[0-9]{4})"):
            for value in re.findall(pattern, printable):
                if value not in traditional:
                    traditional.append(value)
        return {
            "pdf_number": record.pdf_number,
            "card_id": format_card_id(record.pdf_number),
            "database_number": record.database_number,
            "formula": formula,
            "database_name": database_name,
            "traditional_pdf_ids": traditional,
        }

    def peaks(
        self,
        index: int,
        *,
        wavelength_angstrom: float,
        x_min: float,
        x_max: float,
    ) -> list[dict[str, float | int]]:
        assert self._rid is not None
        record = self.records[index]
        end = self.records[index + 1].rid_offset if index + 1 < self.record_count else len(self._rid)
        raw = self._rid[record.rid_offset:end]
        decoded_peaks: list[dict[str, float | int]] = []
        for offset in range(0, len(raw), _J7_RID_RECORD_SIZE):
            d_spacing = struct.unpack_from("<f", raw, offset + 3)[0]
            intensity_raw = int(raw[offset + 7])
            if not (0 < d_spacing < 100 and intensity_raw > 0):
                continue
            ratio = wavelength_angstrom / (2 * d_spacing)
            if not 0 < ratio <= 1:
                continue
            two_theta = 2 * math.degrees(math.asin(ratio))
            decoded_peaks.append(
                {
                    "two_theta_deg": two_theta,
                    "d_spacing_angstrom": d_spacing,
                    "intensity_raw": intensity_raw,
                }
            )
        if not decoded_peaks:
            return []
        # A PDF/Jade relative intensity is defined against the strongest line in
        # the complete card, not merely the selected scan window.  Filtering
        # before normalization silently changes the rank/threshold of lines.
        maximum = max(int(peak["intensity_raw"]) for peak in decoded_peaks)
        peaks: list[dict[str, float | int]] = []
        for peak in decoded_peaks:
            if x_min <= float(peak["two_theta_deg"]) <= x_max:
                peaks.append({**peak, "relative_intensity": 100 * int(peak["intensity_raw"]) / maximum})
        return sorted(peaks, key=lambda peak: float(peak["two_theta_deg"]))

    def search(self, query: str, *, limit: int) -> list[dict[str, object]]:
        return self.search_many((query,), limit=limit)[0]

    def search_many(self, queries: Sequence[str], *, limit: int) -> list[list[dict[str, object]]]:
        """Resolve several formula/name queries in one metadata pass."""
        if limit <= 0:
            raise ValueError("Card search limit must be positive")
        cleaned = [query.strip() for query in queries]
        if any(not query for query in cleaned):
            raise ValueError("Card search query must not be empty")
        results: list[list[dict[str, object]]] = [[] for _ in cleaned]
        pending: dict[int, str] = {}
        for query_index, query in enumerate(cleaned):
            try:
                direct_index = self.index_for_pdf(query)
            except (KeyError, ValueError):
                direct_index = None
            if direct_index is not None:
                results[query_index] = [self.metadata(direct_index)]
            else:
                pending[query_index] = normalize_search_text(query)

        for index in range(self.record_count):
            if not pending:
                break
            metadata = self.metadata(index)
            searchable = " ".join(
                (
                    str(metadata["formula"]),
                    str(metadata["database_name"]),
                    str(metadata["card_id"]),
                    " ".join(str(value) for value in metadata["traditional_pdf_ids"]),
                )
            )
            normalized_searchable = normalize_search_text(searchable)
            completed: list[int] = []
            for query_index, normalized_query in pending.items():
                if normalized_query in normalized_searchable:
                    results[query_index].append(metadata)
                    if len(results[query_index]) >= limit:
                        completed.append(query_index)
            for query_index in completed:
                pending.pop(query_index)
        return results


def parse_pdf_number(identifier: str | int) -> int:
    if isinstance(identifier, int):
        if identifier <= 0:
            raise ValueError("Card number must be positive")
        return identifier
    digits = re.sub(r"\D", "", str(identifier))
    if not digits:
        raise ValueError(f"Invalid PDF/ICSD card identifier: {identifier!r}")
    return int(digits)


def format_card_id(pdf_number: int) -> str:
    digits = f"{pdf_number:09d}"
    return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"


def normalize_search_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def detect_observed_peaks(
    numeric: Sequence[tuple[float, float]],
    *,
    prominence: float,
    distance_deg: float,
) -> tuple[list[ObservedPeak], dict[str, object]]:
    if len(numeric) < 3:
        return [], {
            "method": "not_run_insufficient_points",
            "candidate_count": 0,
            "parameters": {"prominence": prominence, "distance_deg": distance_deg},
        }
    y_values = [float(y) for _, y in numeric]
    y_min = min(y_values)
    y_max = max(y_values)
    signal_span = y_max - y_min
    if signal_span == 0:
        return [], {
            "method": "not_run_constant_signal",
            "candidate_count": 0,
            "parameters": {"prominence": prominence, "distance_deg": distance_deg},
        }
    x_values = [float(x) for x, _ in numeric]
    normalized = [(value - y_min) / signal_span for value in y_values]
    deltas = [x_values[index + 1] - x_values[index] for index in range(len(x_values) - 1) if x_values[index + 1] > x_values[index]]
    median_step = statistics.median(deltas) if deltas else distance_deg
    distance_points = max(1, round(distance_deg / median_step)) if median_step > 0 else 1
    adapter_result = peak_detection_adapter.process_or_analyze(
        x_values,
        normalized,
        prominence=prominence,
        distance=distance_points,
    )
    peaks = [
        ObservedPeak(
            index=int(item["index"]),
            two_theta_deg=float(item["x"]),
            intensity=float(numeric[int(item["index"])][1]),
            normalized_intensity=float(item["y"]),
        )
        for item in adapter_result.get("candidate_peaks", [])
    ]
    provenance = dict(adapter_result.get("metadata_provenance", {}))
    return peaks, {
        "method": provenance.get("method", "unknown"),
        "candidate_count": len(peaks),
        "parameters": {
            "prominence": prominence,
            "distance_deg": distance_deg,
            "distance_points": distance_points,
            "median_step_deg": median_step,
            "normalization": "min_max",
            "signal_min": y_min,
            "signal_max": y_max,
        },
        "fallback_reason": adapter_result.get("fallback_reason"),
        "provenance": provenance,
    }


def score_card_peaks(
    observed: Sequence[ObservedPeak],
    card_peaks: Sequence[dict[str, float | int]],
    *,
    tolerance_deg: float,
    minimum_card_relative_intensity: float,
    detailed: bool,
    observed_thetas: Sequence[float] | None = None,
) -> dict[str, object]:
    eligible = [
        peak
        for peak in card_peaks
        if float(peak["relative_intensity"]) >= minimum_card_relative_intensity
    ]
    theta_values = list(observed_thetas) if observed_thetas is not None else [peak.two_theta_deg for peak in observed]
    matches: list[dict[str, object]] = []
    used_observed: set[int] = set()
    for card_peak in sorted(eligible, key=lambda peak: float(peak["relative_intensity"]), reverse=True):
        card_theta = float(card_peak["two_theta_deg"])
        left = bisect_left(theta_values, card_theta - tolerance_deg)
        right = bisect_right(theta_values, card_theta + tolerance_deg)
        candidates = [
            (abs(observed[index].two_theta_deg - card_theta), index, observed[index])
            for index in range(left, right)
            if index not in used_observed
        ]
        if not candidates:
            continue
        _delta, observed_index, observed_peak = min(candidates, key=lambda item: item[0])
        used_observed.add(observed_index)
        if detailed:
            matches.append(
                {
                    "card_two_theta_deg": card_theta,
                    "observed_two_theta_deg": observed_peak.two_theta_deg,
                    "delta_deg": observed_peak.two_theta_deg - card_theta,
                    "card_relative_intensity": card_peak["relative_intensity"],
                    "observed_normalized_intensity": observed_peak.normalized_intensity,
                }
            )
        else:
            matches.append({"card_relative_intensity": card_peak["relative_intensity"]})

    total_weight = sum(float(peak["relative_intensity"]) for peak in eligible)
    matched_weight = sum(float(match["card_relative_intensity"]) for match in matches)
    weighted_coverage = matched_weight / total_weight if total_weight else 0.0
    observed_fraction = len(used_observed) / len(observed) if observed else 0.0
    score = 0.8 * weighted_coverage + 0.2 * min(1.0, observed_fraction * 2)
    if len(matches) >= 5 and score >= 0.75:
        tier = "screening_high_candidate"
    elif len(matches) >= 3 and score >= 0.45:
        tier = "screening_medium_candidate"
    else:
        tier = "screening_low_candidate"
    result: dict[str, object] = {
        "eligible_card_peak_count": len(eligible),
        "matched_peak_count": len(matches),
        "weighted_card_peak_coverage": weighted_coverage,
        "observed_peak_match_fraction": observed_fraction,
        "match_score_candidate": score,
        "confidence_candidate": tier,
        "manual_check_required": True,
    }
    if detailed:
        matched_card_thetas = {float(match["card_two_theta_deg"]) for match in matches}
        result["matched_peaks"] = matches
        result["unmatched_card_peaks"] = [
            peak for peak in eligible if float(peak["two_theta_deg"]) not in matched_card_thetas
        ]
    return result


def match_xrd_phases(
    numeric: Sequence[tuple[float, float]],
    options: XrdPhaseMatchOptions,
) -> dict[str, object]:
    options.validate()
    ordered = sorted((float(x), float(y)) for x, y in numeric)
    observed, peak_detection = detect_observed_peaks(
        ordered,
        prominence=options.peak_prominence_normalized,
        distance_deg=options.minimum_peak_distance_deg,
    )
    warnings = [
        "Jade RID relative-intensity decoding is a screening candidate and requires trusted-card validation.",
        "No independently verified real Jade XID/SID/RID card fixture is bundled; database decoding remains candidate-only until validated against a trusted card export.",
        "Candidate card rankings are not confirmed phase identities and require manual review with independent evidence.",
    ]
    if options.full_library_screen:
        warnings.append(
            "Composition-blind full-library screening can over-rank dense patterns through coincidental peak overlap."
        )

    with JadeIndex(options.database_dir, options.database_stem) as database:
        database_info = database.info()
        selection_notes: list[dict[str, object]] = []
        if options.full_library_screen:
            matches = _full_library_screen(
                observed,
                database,
                options=options,
                x_min=ordered[0][0],
                x_max=ordered[-1][0],
            )
            status = "full_library_screened_candidates_manual_review_required"
        else:
            indices: list[int] = []
            for card_id in options.card_ids:
                index = database.index_for_pdf(card_id)
                if index not in indices:
                    indices.append(index)
            query_batches = database.search_many(options.card_queries, limit=options.query_limit)
            for query, query_results in zip(options.card_queries, query_batches, strict=True):
                selection_notes.append({"query": query, "result_count": len(query_results)})
                for result in query_results:
                    index = database.index_for_pdf(int(result["pdf_number"]))
                    if index not in indices:
                        indices.append(index)
            matches = _screen_indices(
                observed,
                database,
                indices,
                options=options,
                x_min=ordered[0][0],
                x_max=ordered[-1][0],
            )[: options.result_limit]
            status = "selected_cards_screened_candidates_manual_review_required"

    return {
        "status": status,
        "database": database_info,
        "candidate_count": len(matches),
        "selection_notes": selection_notes,
        "peak_detection": peak_detection,
        "parameters": {
            "wavelength_angstrom": options.wavelength_angstrom,
            "card_tolerance_deg": options.card_tolerance_deg,
            "minimum_card_relative_intensity": options.minimum_card_relative_intensity,
            "full_library_screen": options.full_library_screen,
        },
        "matches": matches,
        "warnings": warnings,
        "manual_check_required": True,
        "manual_check_items": [
            "Confirm radiation wavelength, scan range, instrumental zero shift, background, and candidate peaks.",
            "Confirm card provenance, competing phases, tolerance, and every proposed peak match.",
            "Apply independent elemental/composition constraints before interpreting full-library rankings.",
        ],
        "forbidden_claims": [
            "no automatic confirmation of a phase identity from a candidate card ranking",
            "no automatic hkl or crystal-plane assignment",
            "no automatic phase-purity or impurity-free claim",
            "no quantitative phase fraction, crystallinity, crystallite-size, strain, or mechanism conclusion",
        ],
    }


def _screen_indices(
    observed: Sequence[ObservedPeak],
    database: JadeIndex,
    indices: Sequence[int],
    *,
    options: XrdPhaseMatchOptions,
    x_min: float,
    x_max: float,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for index in indices:
        reference_peaks = database.peaks(
            index,
            wavelength_angstrom=options.wavelength_angstrom,
            x_min=x_min,
            x_max=x_max,
        )
        score = score_card_peaks(
            observed,
            reference_peaks,
            tolerance_deg=options.card_tolerance_deg,
            minimum_card_relative_intensity=options.minimum_card_relative_intensity,
            detailed=True,
        )
        results.append({**database.metadata(index), **score})
    return sorted(results, key=lambda item: float(item["match_score_candidate"]), reverse=True)


def _full_library_screen(
    observed: Sequence[ObservedPeak],
    database: JadeIndex,
    *,
    options: XrdPhaseMatchOptions,
    x_min: float,
    x_max: float,
) -> list[dict[str, object]]:
    heap: list[tuple[float, int, int]] = []
    observed_thetas = [peak.two_theta_deg for peak in observed]
    for index in range(database.record_count):
        reference_peaks = database.peaks(
            index,
            wavelength_angstrom=options.wavelength_angstrom,
            x_min=x_min,
            x_max=x_max,
        )
        if not reference_peaks:
            continue
        score = score_card_peaks(
            observed,
            reference_peaks,
            tolerance_deg=options.card_tolerance_deg,
            minimum_card_relative_intensity=options.minimum_card_relative_intensity,
            detailed=False,
            observed_thetas=observed_thetas,
        )
        matched = int(score["matched_peak_count"])
        if matched < 3:
            continue
        entry = (float(score["match_score_candidate"]), matched, index)
        if len(heap) < options.result_limit:
            heapq.heappush(heap, entry)
        elif entry > heap[0]:
            heapq.heapreplace(heap, entry)
    selected = [entry[2] for entry in sorted(heap, reverse=True)]
    return _screen_indices(
        observed,
        database,
        selected,
        options=options,
        x_min=x_min,
        x_max=x_max,
    )


def _decode_index_text(payload: bytes) -> str:
    return payload.decode("latin-1", errors="replace")


def _validate_database_stem(stem: str) -> str:
    """Accept a single Jade file stem, never a path or suffixed filename."""
    invalid_characters = '<>:"|?*'
    if (
        not isinstance(stem, str)
        or not stem.strip()
        or stem in {".", ".."}
        or "/" in stem
        or "\\" in stem
        or stem.endswith((" ", "."))
        or stem.casefold().endswith((".xid", ".sid", ".rid"))
        or any(character in invalid_characters or ord(character) < 32 for character in stem)
    ):
        raise ValueError(
            "XRD Jade database stem must be one non-empty filename stem "
            "(without path separators, Jade filename suffixes, Windows-invalid characters, or trailing dot/space)"
        )
    return stem
