from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.core.epr_jeol import decode_jeol_cacqu_rows, looks_like_jeol_cwesr_file
from src.core.metadata import file_hash
from src.core.project import load_json_compatible_yaml, output_dir, registry_path, report_path
from src.core.table_reader import coerce_numeric_rows, read_table_with_metadata


DECISIONS = (
    "AUTO_PROCESS",
    "MANUAL_REVIEW",
    "EXCLUDE_INVALID",
    "DUPLICATE_SUPPRESSED",
    "AUXILIARY_ONLY",
    "DEFERRED_TYPE",
    "REFERENCE_ONLY",
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".caj", ".ris", ".bib", ".enw", ".enl"}
TABLE_EXTENSIONS = {".csv", ".txt", ".tsv", ".xlsx", ".xls", ".xlsm", ".dat", ".xy", ".z", ".mpt"}
ORIGIN_PROJECT_EXTENSIONS = {".opju", ".opj", ".ogwu", ".ogw", ".otpu"}
BACKUP_PATTERNS = ("backup", "copy", "old", "temp", "tmp", "bak", "备份", "副本", "复件", "旧", "临时")
TRACEABILITY_ROLE_FOLDERS = {
    "origin_project_reference": ("origin_project", "origin project", "origin", "origin工程", "origin项目"),
    "raw_data": ("raw_data", "raw data", "raw", "原始", "原文件", "acqdata"),
    "processed_table": ("processed_tables", "processed_table", "processed data", "processed", "处理", "拟合", "pdata"),
    "exported_figure": ("exported_figures", "exported_figure", "figures", "figure", "图片", "图"),
}

ROLE_NEEDLES = {
    "x": ("2theta", "2θ", "two theta", "angle", "wavelength", "wavenumber", "raman", "potential", "frequency", "time", "retention", "binding energy", "magnetic field", "field"),
    "y": ("intensity", "counts", "current", "absorbance", "reflectance", "transmittance", "area", "height", "signal", "mau", "quantity"),
}

MIN_ROWS = {
    "XRD": 50,
    "UV-vis DRS": 30,
    "EIS": 5,
    "photocurrent": 10,
    "photocurrent_response": 10,
    "XPS": 30,
    "PL": 20,
    "FTIR": 20,
    "Raman": 20,
    "reaction_condition_screening": 2,
    "HPLC/LC exported data": 2,
    "BET": 2,
    "EPR": 2,
    "Mott-Schottky": 3,
}


@dataclass(frozen=True)
class TriageOptions:
    only_type: str | None = None
    only_folder: str | None = None
    min_confidence: float = 0.75
    explain: bool = False
    force_refresh: bool = False
    dry_run: bool = False
    output_root: Path | None = None


def run_triage(project_root: Path, input_path: Path, options: TriageOptions | None = None) -> dict:
    options = options or TriageOptions()
    input_path = input_path.absolute()
    registry = load_json_compatible_yaml(registry_path(project_root))
    entries = list(registry["entries"])
    items = []
    for path in sorted(input_path.rglob("*")) if input_path.exists() else []:
        if not path.is_file():
            continue
        item = _triage_file(project_root, input_path, path, entries, options)
        if options.only_type and _norm(item["data_type_candidate"]) != _norm(options.only_type):
            continue
        if options.only_folder and _norm_path(options.only_folder) not in _norm_path(item["relative_path"]):
            continue
        items.append(item)

    _suppress_exact_duplicates(items)
    queue = _build_queue(input_path, options.min_confidence, items)
    result = {
        "triage_version": "1.0",
        "created_at": _now(),
        "source_root": str(input_path),
        "summary": _summary(items),
        "items": items,
        "queue": queue,
    }
    if not options.dry_run:
        _write_outputs(project_root, result, output_root=options.output_root)
    return result


def _triage_file(project_root: Path, root: Path, path: Path, entries: list[dict], options: TriageOptions) -> dict:
    relative_to_root = path.relative_to(root)
    relative_path = str(relative_to_root).replace("\\", "/")
    suffix = path.suffix.lower()
    size = path.stat().st_size
    traceability = _traceability_context(relative_path, suffix)
    folder_entry = _entry_from_path(relative_path, entries)
    filename_entry = _entry_from_filename(path.name, entries)
    parser = _probe_parser(path, suffix, size)
    header_entry = _entry_from_headers(parser["observed_column_headers"], entries)
    selected_entry = _select_entry(folder_entry, filename_entry, header_entry)
    data_type = selected_entry["inferred_data_type"] if selected_entry else "unknown"
    selected_processor = selected_entry["selected_processor"] if selected_entry else "none"
    supported = bool(selected_entry and selected_entry["supported_in_phase_1"])
    folder_conflict = bool(folder_entry and header_entry and folder_entry["inferred_data_type"] != header_entry["inferred_data_type"])
    conflict_level = _folder_header_conflict_level(folder_entry, filename_entry, header_entry, parser)
    confidence = _confidence_score(path, suffix, folder_entry, filename_entry, header_entry, selected_entry, parser)
    validity = _validity_score(parser, data_type, suffix)
    decision, reasons = _decision(path, suffix, size, parser, selected_entry, data_type, confidence, validity, folder_conflict, conflict_level, options)
    evidence = _evidence(folder_entry, filename_entry, header_entry, parser, suffix, size, folder_conflict, conflict_level)
    file_id = hashlib.sha256(str(relative_to_root).encode("utf-8", errors="replace")).hexdigest()[:16]
    source_hash = file_hash(path) if path.is_file() else ""
    return {
        "file_id": file_id,
        "relative_path": relative_path,
        "absolute_path": str(path),
        "absolute_path_hash": hashlib.sha256(str(path.resolve()).encode("utf-8", errors="replace")).hexdigest(),
        "source_hash": source_hash,
        "file_name": path.name,
        "extension": suffix,
        "file_size_bytes": size,
        "traceability_group_id": traceability["group_id"],
        "traceability_group_path": traceability["group_path"],
        "traceability_role": traceability["role"],
        "traceability_basis": traceability["basis"],
        "folder_type_hint": folder_entry["inferred_data_type"] if folder_entry else None,
        "filename_type_hint": filename_entry["inferred_data_type"] if filename_entry else None,
        "header_type_hint": header_entry["inferred_data_type"] if header_entry else None,
        "numeric_shape_hint": parser["numeric_shape_hint"],
        "encoding_detected": parser["encoding_detected"],
        "sheet_name": parser["sheet_name"],
        "sheet_scores": parser.get("sheet_scores", {}),
        "header_row_index": parser.get("header_row_index"),
        "parser_probe_status": parser["parser_probe_status"],
        "parser_probe_error": parser["parser_probe_error"],
        "observed_column_headers": parser["observed_column_headers"],
        "normalized_column_headers": [_norm(header) for header in parser["observed_column_headers"]],
        "column_role_candidates": parser["column_role_candidates"],
        "unit_candidates": parser.get("unit_candidates", {}),
        "data_type_candidate": data_type,
        "subtype_candidate": data_type,
        "selected_processor": selected_processor,
        "supported_in_phase_1": supported,
        "confidence_score": confidence,
        "validity_score": validity,
        "decision": decision,
        "decision_reasons": reasons,
        "evidence": evidence if options.explain else evidence[:5],
        "manual_check_required": True,
        "manual_check_items": _manual_check_items(data_type, decision),
        "duplicate_group_id": None,
        "duplicate_representative": None,
        "suppressed_by": None,
        "process_priority": _process_priority(decision, confidence, validity),
        "safe_to_process_no_origin": decision == "AUTO_PROCESS",
        "safe_to_process_with_origin": False,
        "folder_type_conflict": folder_conflict,
        "folder_header_conflict_level": conflict_level,
        "recognition_fallbacks": parser.get("recognition_fallbacks", []),
        "header_quality": parser.get("header_quality", {}),
        "manual_override_used": False,
        "manual_override_keys": [],
    }


def _probe_parser(path: Path, suffix: str, size: int) -> dict:
    result = {
        "encoding_detected": None,
        "sheet_name": None,
        "parser_probe_status": "skipped",
        "parser_probe_error": None,
        "observed_column_headers": [],
        "column_role_candidates": {},
        "unit_candidates": {},
        "numeric_shape_hint": {"rows": 0, "columns": 0, "numeric_columns": 0},
        "sheet_scores": {},
        "header_row_index": None,
        "header_quality": {},
        "recognition_fallbacks": [],
    }
    if size == 0:
        return result
    try:
        if suffix not in TABLE_EXTENSIONS and looks_like_jeol_cwesr_file(path):
            rows = decode_jeol_cacqu_rows(path)
            table = None
            fallbacks = ["jeol_cacqu_epr_binary_decode"]
        elif suffix in TABLE_EXTENSIONS:
            table = read_table_with_metadata(path, allow_legacy_xls_com=False)
            rows = table.rows
            fallbacks = []
        else:
            return result
        headers = list(rows[0].keys()) if rows else []
        numeric = coerce_numeric_rows(rows)
        numeric_columns = _numeric_column_count(rows)
        header_quality = _header_quality(headers, rows)
        if header_quality["unnamed_column_count"]:
            fallbacks.append("unnamed_columns_with_numeric_data")
        if headers == ["x", "y"] and numeric:
            fallbacks.append("headerless_numeric_table")
        result.update(
            {
                "encoding_detected": "auto",
                "sheet_name": table.sheet_name if table else None,
                "parser_probe_status": "success",
                "observed_column_headers": headers,
                "column_role_candidates": _column_roles(headers),
                "unit_candidates": _unit_candidates(headers),
                "numeric_shape_hint": {"rows": len(numeric), "columns": len(headers), "numeric_columns": numeric_columns},
                "sheet_scores": (table.sheet_scores or {}) if table else {},
                "header_row_index": table.header_row_index if table else None,
                "header_quality": header_quality,
                "recognition_fallbacks": _fallback_levels(fallbacks, header_quality, parser_rows=len(numeric), numeric_columns=numeric_columns),
            }
        )
    except Exception as exc:
        result["parser_probe_status"] = "fail"
        result["parser_probe_error"] = str(exc)
    return result


def _numeric_column_count(rows: list[dict[str, str]]) -> int:
    if not rows:
        return 0
    count = 0
    for header in rows[0]:
        values = []
        for row in rows:
            try:
                values.append(float(str(row.get(header, "")).strip()))
            except ValueError:
                continue
        if values:
            count += 1
    return count


def _column_roles(headers: list[str]) -> dict:
    roles: dict[str, list[str]] = {}
    for role, needles in ROLE_NEEDLES.items():
        matches = [header for header in headers if any(_keyword_matches(_norm(needle), _normalized_header(header)) for needle in needles)]
        if matches:
            roles[role] = matches
    return roles


def _unit_candidates(headers: list[str]) -> dict[str, list[str]]:
    unit_patterns = {
        "wavelength_nm": (r"\bnm\b", "纳米"),
        "wavenumber_cm-1": (r"cm\s*[-^]?\s*1", "cm-1", "cm^-1"),
        "energy_ev": (r"\bev\b", "电子伏"),
        "current": (r"\bma\b", r"\bua\b", r"\bµa\b", r"\bμa\b", "电流"),
        "potential_v": (r"\bv\b", "电位", "电压"),
        "frequency_hz": (r"\bhz\b", "频率"),
        "time": (r"\bs\b", r"\bsec\b", r"\bmin\b", "时间"),
        "field": (r"\bmt\b", r"\bgauss\b", "磁场"),
        "relative_pressure": ("p/p0", "p p0"),
        "capacitance_inverse_square": ("1/c", "1 c", "1/c^2", "1 c^2"),
        "arbitrary_unit": ("a.u.", "a u", "arb", "任意"),
    }
    hits: dict[str, list[str]] = {}
    for header in headers:
        normalized = _normalized_header(header)
        raw = str(header).casefold()
        for unit, patterns in unit_patterns.items():
            for pattern in patterns:
                if pattern.startswith("\\"):
                    matched = re.search(pattern, raw) or re.search(pattern, normalized)
                else:
                    matched = pattern.casefold() in raw or pattern.casefold() in normalized
                if matched:
                    hits.setdefault(unit, []).append(header)
                    break
    return hits


def _fallback_levels(fallbacks: list[str], quality: dict, *, parser_rows: int, numeric_columns: int) -> list[str]:
    levels = list(fallbacks)
    if "headerless_numeric_table" in fallbacks:
        if parser_rows >= 20 and numeric_columns == 2:
            levels.append("headerless_numeric_table_strong_shape")
        else:
            levels.append("headerless_numeric_table_weak_shape")
    if "unnamed_columns_with_numeric_data" in fallbacks:
        if quality.get("all_headers_unnamed_or_empty") and parser_rows >= 20 and numeric_columns >= 2:
            levels.append("all_unnamed_numeric_table")
        else:
            levels.append("partial_unnamed_metadata_mixed")
    return levels


def _header_quality(headers: list[str], rows: list[dict[str, str]]) -> dict:
    unnamed = [header for header in headers if _is_unnamed_header(header)]
    empty = [header for header in headers if not str(header).strip()]
    numeric_like = sum(1 for header in headers if _to_floatish(header) is not None)
    return {
        "unnamed_column_count": len(unnamed),
        "empty_column_count": len(empty),
        "numeric_like_header_count": numeric_like,
        "all_headers_unnamed_or_empty": bool(headers) and len(unnamed) + len(empty) == len(headers),
        "row_count": len(rows),
    }


def _is_unnamed_header(header: str) -> bool:
    lowered = str(header).strip().casefold()
    return not lowered or lowered.startswith("unnamed") or lowered in {"nan", "none"}


def _to_floatish(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _traceability_context(relative_path: str, suffix: str) -> dict:
    raw_segments = [segment for segment in re.split(r"[/\\]+", relative_path) if segment]
    normalized_segments = [_norm_path(segment) for segment in raw_segments]
    role, role_index, role_basis = _traceability_role(raw_segments, normalized_segments, suffix)
    group_segments = _traceability_group_segments(raw_segments, normalized_segments, role_index, role)
    group_path = "/".join(group_segments) if group_segments else "."
    group_id = hashlib.sha256(group_path.encode("utf-8", errors="replace")).hexdigest()[:16]
    return {
        "group_id": group_id,
        "group_path": group_path,
        "role": role,
        "basis": role_basis,
    }


def _traceability_role(raw_segments: list[str], normalized_segments: list[str], suffix: str) -> tuple[str, int | None, list[str]]:
    role_hits: list[tuple[int, int, str, str]] = []
    for role, keywords in TRACEABILITY_ROLE_FOLDERS.items():
        for index, segment in enumerate(normalized_segments[:-1]):
            for keyword in keywords:
                normalized_keyword = _norm_path(keyword)
                if normalized_keyword and _keyword_matches(normalized_keyword, segment):
                    role_hits.append((index, len(normalized_keyword), role, raw_segments[index]))
    if role_hits:
        index, _length, role, segment = max(role_hits, key=lambda hit: (hit[0], hit[1]))
        return role, index, [f"role_folder={segment}"]
    if suffix in ORIGIN_PROJECT_EXTENSIONS:
        return "origin_project_reference", None, [f"extension={suffix}"]
    if suffix in IMAGE_EXTENSIONS:
        return "exported_figure", None, [f"extension={suffix}"]
    if suffix in DOC_EXTENSIONS:
        return "document_or_report", None, [f"extension={suffix}"]
    if suffix in TABLE_EXTENSIONS:
        return "raw_or_exported_numeric_table", None, [f"extension={suffix}"]
    if not suffix and any(segment in {"epr", "esr"} or "epr" in segment or "esr" in segment for segment in normalized_segments):
        return "raw_or_exported_numeric_table", None, ["extension=none", "folder_hint=epr_esr"]
    if any(segment.endswith(".d") for segment in normalized_segments):
        return "vendor_bundle_member", None, ["vendor_bundle=.d"]
    return "auxiliary_file", None, [f"extension={suffix or 'none'}"]


def _traceability_group_segments(raw_segments: list[str], normalized_segments: list[str], role_index: int | None, role: str) -> list[str]:
    if not raw_segments:
        return []
    if role_index is not None and role_index > 0:
        return raw_segments[:role_index]
    vendor_bundle_index = next((index for index, segment in enumerate(normalized_segments) if segment.endswith(".d")), None)
    if vendor_bundle_index is not None:
        return raw_segments[:vendor_bundle_index + 1]
    if role == "origin_project_reference" and len(raw_segments) > 1:
        return raw_segments[:-1]
    return raw_segments[:-1]


def _entry_from_path(relative_path: str, entries: list[dict]) -> dict | None:
    raw_segments = [segment for segment in re.split(r"[/\\]+", relative_path) if segment]
    segments = [_norm_path(segment) for segment in raw_segments[:-1]]
    haystack = "/".join(segments)
    matches = []
    for order, entry in enumerate(entries):
        keywords = [entry["folder_name"], *entry.get("folder_keywords", [])]
        for keyword_index, keyword in enumerate(keywords):
            normalized_keyword = _norm_path(keyword)
            if not normalized_keyword:
                continue
            strength = _folder_keyword_strength(normalized_keyword, keyword_index == 0)
            segment_hits = [
                index
                for index, segment in enumerate(segments)
                if _keyword_matches(normalized_keyword, segment)
            ]
            if segment_hits:
                matches.append((strength, max(segment_hits), len(normalized_keyword), -order, entry))
            elif _keyword_matches(normalized_keyword, haystack):
                matches.append((strength, -1, len(normalized_keyword), -order, entry))
    return max(matches, key=lambda match: (match[0], match[1], match[2], match[3]), default=(0, 0, 0, 0, None))[4]


def _select_entry(folder_entry: dict | None, filename_entry: dict | None, header_entry: dict | None) -> dict | None:
    if _is_folder_scan_only(folder_entry):
        return folder_entry
    return header_entry or folder_entry or filename_entry


def _is_folder_scan_only(entry: dict | None) -> bool:
    if not entry:
        return False
    return (
        entry.get("special_handling") == "scan_only"
        or entry.get("inferred_data_type") == "reference_literature"
        or not entry.get("supported_in_phase_1", False)
    )


def _folder_keyword_strength(normalized_keyword: str, is_folder_name: bool) -> int:
    if is_folder_name or not re.fullmatch(r"[a-z0-9]{1,4}", normalized_keyword):
        return 2
    return 1


def _entry_from_filename(name: str, entries: list[dict]) -> dict | None:
    haystack = _norm(name)
    for entry in entries:
        keywords = [entry["folder_name"], *entry.get("filename_keywords", [])]
        if any(_norm(keyword) and _keyword_matches(_norm(keyword), haystack) for keyword in keywords):
            return entry
    return None


def _entry_from_headers_legacy_unused(headers: list[str], entries: list[dict]) -> dict | None:
    text = " ".join(_norm(header) for header in headers)
    header_signatures = [
        ("XRD", ("2theta", "2θ", "two theta")),
        ("UV-vis DRS", ("wavelength", "reflectance", "absorbance")),
        ("EIS", ("re(z)", "zreal", "-im(z)", "im(z)", "phase")),
        ("photocurrent", ("time", "current")),
        ("XPS", ("binding energy", "be")),
        ("PL", ("wavelength", "pl")),
        ("FTIR", ("wavenumber", "transmittance", "absorbance")),
        ("Raman", ("raman", "shift")),
        ("HPLC/LC exported data", ("retention", "area", "mau")),
        ("BET", ("relative pressure", "p/p0", "bet surface")),
        ("EPR", ("magnetic field", "microwave")),
        ("Mott-Schottky", ("1/c", "capacitance", "potential")),
    ]
    for dtype, needles in header_signatures:
        if dtype == "photocurrent":
            matched = all(needle in text for needle in needles)
        else:
            matched = any(needle in text for needle in needles)
        if matched:
            return _entry_by_type(entries, dtype)
    return None


def _entry_from_headers_legacy_units_unused(headers: list[str], entries: list[dict]) -> dict | None:
    text = " ".join(_normalized_header(header) for header in headers)
    header_signatures = [
        ("XRD", ("2theta", "2 theta", "two theta", "2θ")),
        ("UV-vis DRS", ("wavelength", "reflectance", "absorbance", "f r", "kubelka", "波长", "反射", "吸光")),
        ("EIS", ("re z", "zreal", "z real", "z'", "im z", "zimag", "z imag", "z\"", "phase", "frequency")),
        ("photocurrent", ("time", "current")),
        ("XPS", ("binding energy", "bind energy", "be ev", "cps", "counts s", "raw intensity")),
        ("PL", ("wavelength", "photoluminescence", "emission", "excitation", "pl", "波长", "强度")),
        ("FTIR", ("wavenumber", "wave number", "transmittance", "absorbance", "cm 1")),
        ("Raman", ("raman", "shift", "wavenumber", "cm 1")),
        ("HPLC/LC exported data", ("retention", "retention time", "area", "mau", "peak height")),
        ("BET", ("relative pressure", "p p0", "bet surface", "adsorbed", "desorption")),
        ("EPR", ("magnetic field", "field", "microwave", "gauss", "intensity")),
        ("Mott-Schottky", ("1 c", "1 c2", "1 c^2", "capacitance", "potential", "ewe")),
    ]
    for dtype, needles in header_signatures:
        if dtype == "photocurrent":
            matched = "time" in text and ("current" in text or "photocurrent" in text)
        else:
            matched = any(_keyword_matches(_norm(needle), text) for needle in needles)
        if matched:
            return _entry_by_type(entries, dtype)
    return None


def _normalized_header_legacy_units_unused(header: str) -> str:
    value = _norm(str(header))
    value = value.replace("μ", "u").replace("µ", "u").replace("θ", "theta")
    value = re.sub(r"[\[\]\(\),;:/\\]+", " ", value)
    value = value.replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    aliases = {
        "2 theta": "2theta",
        "two theta": "2theta",
        "binding energy ev": "binding energy",
        "potential v": "potential",
        "voltage v": "potential",
        "current ma": "current",
        "current ua": "current",
        "wavelength nm": "wavelength",
        "wavenumber cm 1": "wavenumber",
        "raman shift cm 1": "raman shift",
        "relative pressure p p0": "relative pressure p p0",
    }
    return aliases.get(value, value)


def _entry_by_type(entries: list[dict], data_type: str) -> dict | None:
    for entry in entries:
        if entry["inferred_data_type"] == data_type:
            return entry
    return None


def _entry_from_headers(headers: list[str], entries: list[dict]) -> dict | None:
    text = " ".join(_normalized_header(header) for header in headers)
    scores = _header_type_scores(text)
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_type, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if best_score >= 2 and best_score > second_score:
        return _entry_by_type(entries, best_type)
    return None


def _header_type_scores(text: str) -> dict[str, int]:
    scores: dict[str, int] = {}

    def add(data_type: str, value: int) -> None:
        if value > 0:
            scores[data_type] = scores.get(data_type, 0) + value

    add("XRD", 2 if _has(text, "2theta", "two theta", "2 theta") and _has(text, "intensity", "强度", "counts") else 0)
    add("UV-vis DRS", int(_has(text, "wavelength", "波长")) + int(_has(text, "reflectance", "反射", "absorbance", "吸光", "kubelka", "f r")))
    add("EIS", int(_has(text, "frequency", "频率", "hz")) + int(_has(text, "re z", "zreal", "z real", "z'")) + int(_has(text, "im z", "zimag", "z imag", "z\"", "phase")))
    add("photocurrent", int(_has(text, "time", "时间")) + int(_has(text, "photocurrent", "current", "电流")))
    add("XPS", int(_has(text, "binding energy", "结合能", "be ev")) + int(_has(text, "cps", "counts", "计数", "raw intensity", "intensity", "强度")))
    add("PL", int(_has(text, "pl", "photoluminescence", "emission", "excitation")) + int(_has(text, "wavelength", "波长")) + int(_has(text, "intensity", "强度")))
    add("FTIR", int(_has(text, "wavenumber", "波数", "cm 1")) + int(_has(text, "transmittance", "透过", "absorbance", "吸光")) + int(_has(text, "ftir", "infrared")))
    add("Raman", int(_has(text, "raman", "拉曼")) + int(_has(text, "shift", "位移", "wavenumber", "波数", "cm 1")) + int(_has(text, "intensity", "强度")))
    add("HPLC/LC exported data", int(_has(text, "retention", "保留")) + int(_has(text, "area", "面积", "mau", "peak height")))
    add("BET", int(_has(text, "relative pressure", "p p0", "p/p0")) + int(_has(text, "adsorbed", "desorption", "bet surface")))
    add("EPR", int(_has(text, "magnetic field", "磁场", "gauss", "mt")) + int(_has(text, "microwave", "intensity", "强度")))
    add(
        "Mott-Schottky",
        int(_has(text, "potential", "电位", "voltage", "ewe"))
        + int(_has(text, "1 c", "1/c", "1 c2", "1/c^2", "capacitance"))
        + 2 * int(_has(text, "z'", "z real", "zreal", "z\"", "phase") and not _has(text, "frequency", "hz", "频率")),
    )
    return scores


def _has(text: str, *needles: str) -> bool:
    return any(_normalized_header(needle) in text for needle in needles)


def _normalized_header(header: str) -> str:
    value = _norm(str(header))
    value = value.replace("μ", "u").replace("µ", "u").replace("θ", "theta")
    value = re.sub(r"[\[\]\(\),;:/\\]+", " ", value)
    value = value.replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    aliases = {
        "2 theta": "2theta",
        "two theta": "2theta",
        "binding energy ev": "binding energy",
        "potential v": "potential",
        "voltage v": "potential",
        "current ma": "current",
        "current ua": "current",
        "wavelength nm": "wavelength",
        "wavenumber cm 1": "wavenumber",
        "raman shift cm 1": "raman shift",
        "relative pressure p p0": "relative pressure p p0",
        "结合能 ev": "结合能",
        "波长 nm": "波长",
        "波数 cm 1": "波数",
        "电位 v": "电位",
        "电流 ma": "电流",
        "电流 ua": "电流",
    }
    return aliases.get(value, value)


def _keyword_matches(normalized_keyword: str, normalized_value: str) -> bool:
    if not normalized_keyword:
        return False
    if re.fullmatch(r"[a-z0-9]{1,4}", normalized_keyword):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
        return re.search(pattern, normalized_value) is not None
    return normalized_keyword in normalized_value


def _confidence_score(
    path: Path,
    suffix: str,
    folder_entry: dict | None,
    filename_entry: dict | None,
    header_entry: dict | None,
    selected_entry: dict | None,
    parser: dict,
) -> float:
    score = 0.0
    if folder_entry:
        score += 0.35
    if filename_entry and selected_entry and filename_entry["inferred_data_type"] == selected_entry["inferred_data_type"]:
        score += 0.15
    if header_entry and selected_entry and header_entry["inferred_data_type"] == selected_entry["inferred_data_type"]:
        score += 0.4
    if selected_entry and suffix in {ext.lower() for ext in selected_entry.get("extensions", [])}:
        score += 0.1
    if selected_entry and parser.get("recognition_fallbacks") and "jeol_cacqu_epr_binary_decode" in parser["recognition_fallbacks"]:
        score += 0.1
    if _safe_numeric_fallback_applies(suffix, folder_entry, filename_entry, header_entry, selected_entry, parser):
        score += 0.3
    return round(min(score, 1.0), 3)


def _safe_numeric_fallback_applies(
    suffix: str,
    folder_entry: dict | None,
    filename_entry: dict | None,
    header_entry: dict | None,
    selected_entry: dict | None,
    parser: dict,
) -> bool:
    if not folder_entry or header_entry or not selected_entry:
        return False
    if folder_entry["inferred_data_type"] != selected_entry["inferred_data_type"]:
        return False
    if parser["parser_probe_status"] != "success":
        return False
    if suffix not in {ext.lower() for ext in selected_entry.get("extensions", [])}:
        return False
    rows = int(parser["numeric_shape_hint"]["rows"])
    cols = int(parser["numeric_shape_hint"]["numeric_columns"])
    if rows < MIN_ROWS.get(selected_entry["inferred_data_type"], 2) or cols < 2:
        return False
    fallbacks = set(parser.get("recognition_fallbacks", []))
    strong_shape = "headerless_numeric_table_strong_shape" in fallbacks or "all_unnamed_numeric_table" in fallbacks
    if not strong_shape:
        return False
    semantic_signal = (
        filename_entry is not None
        and filename_entry.get("inferred_data_type") == selected_entry.get("inferred_data_type")
    ) or _sheet_name_supports_type(str(parser.get("sheet_name") or ""), selected_entry.get("inferred_data_type", ""))
    return bool(semantic_signal)


def _sheet_name_supports_type(sheet_name: str, data_type: str) -> bool:
    if not sheet_name:
        return False
    text = _norm(sheet_name)
    tokens = {
        "XPS": ("xps", "binding", "survey", "scan"),
        "EIS": ("eis", "nyquist", "impedance"),
        "Raman": ("raman", "拉曼"),
        "Mott-Schottky": ("mott", "schottky", "ms"),
        "photocurrent": ("photocurrent", "it", "current"),
        "UV-vis DRS": ("uv", "uvvis", "drs", "reflectance"),
        "PL": ("pl", "emission", "excitation"),
        "EPR": ("epr", "esr"),
    }.get(data_type, ())
    return any(token in text for token in tokens)


def _validity_score(parser: dict, data_type: str, suffix: str) -> float:
    if parser["parser_probe_status"] != "success":
        return 0.0
    rows = int(parser["numeric_shape_hint"]["rows"])
    cols = int(parser["numeric_shape_hint"]["numeric_columns"])
    min_rows = MIN_ROWS.get(data_type, 2)
    score = 0.25
    if rows >= min_rows:
        score += 0.35
    elif rows >= max(2, min_rows // 3):
        score += 0.15
    if cols >= 2:
        score += 0.25
    if parser["column_role_candidates"]:
        score += 0.15
    if "jeol_cacqu_epr_binary_decode" in parser.get("recognition_fallbacks", []):
        score += 0.1
    return round(min(score, 1.0), 3)


def _decision(
    path: Path,
    suffix: str,
    size: int,
    parser: dict,
    entry: dict | None,
    data_type: str,
    confidence: float,
    validity: float,
    folder_conflict: bool,
    conflict_level: str,
    options: TriageOptions,
) -> tuple[str, list[str]]:
    reasons = []
    if entry and data_type == "reference_literature":
        return "REFERENCE_ONLY", ["reference_literature_scan_only"]
    if entry and not entry.get("supported_in_phase_1", False):
        return "DEFERRED_TYPE", ["deferred_scan_only"]
    if size == 0:
        return "EXCLUDE_INVALID", ["empty_file"]
    if suffix in ORIGIN_PROJECT_EXTENSIONS:
        return "AUXILIARY_ONLY", ["origin_project_file_grouped_with_same_folder_data"]
    if suffix in IMAGE_EXTENSIONS:
        return "AUXILIARY_ONLY", ["plot_image_not_raw_numeric_data"]
    if suffix in DOC_EXTENSIONS:
        return "AUXILIARY_ONLY", ["document_or_report_not_primary_data"]
    if _is_backup_name(path.name):
        reasons.append("backup_or_temp_name")
    if parser["parser_probe_status"] != "success":
        return ("MANUAL_REVIEW" if entry else "EXCLUDE_INVALID"), reasons + ["parser_probe_not_success"]
    rows = int(parser["numeric_shape_hint"]["rows"])
    cols = int(parser["numeric_shape_hint"]["numeric_columns"])
    if rows < 2 or cols < 2:
        return "EXCLUDE_INVALID", reasons + ["insufficient_numeric_table"]
    if folder_conflict:
        return "MANUAL_REVIEW", reasons + [f"{conflict_level}_folder_header_type_conflict"]
    if confidence >= options.min_confidence and validity >= options.min_confidence and entry and entry.get("supported_in_phase_1", False) and not reasons:
        if parser.get("recognition_fallbacks"):
            return "AUTO_PROCESS", ["high_confidence_valid_numeric_data_with_safe_numeric_fallback"]
        return "AUTO_PROCESS", ["high_confidence_valid_numeric_data"]
    if max(confidence, validity) >= 0.45 or reasons:
        return "MANUAL_REVIEW", reasons + ["below_auto_process_threshold_or_ambiguous"]
    return "EXCLUDE_INVALID", reasons + ["low_confidence_low_validity"]


def _is_backup_name(name: str) -> bool:
    lowered = _norm(name)
    return name.startswith("~$") or any(pattern in lowered for pattern in BACKUP_PATTERNS)


def _folder_header_conflict_level(folder_entry: dict | None, filename_entry: dict | None, header_entry: dict | None, parser: dict) -> str:
    if not folder_entry or not header_entry or folder_entry["inferred_data_type"] == header_entry["inferred_data_type"]:
        return "none"
    if _is_folder_scan_only(folder_entry):
        return "severe"
    if filename_entry and filename_entry["inferred_data_type"] == header_entry["inferred_data_type"]:
        return "mild"
    rows = int(parser.get("numeric_shape_hint", {}).get("rows", 0))
    cols = int(parser.get("numeric_shape_hint", {}).get("numeric_columns", 0))
    if rows >= 20 and cols >= 2 and parser.get("parser_probe_status") == "success":
        return "mild"
    return "severe"


def _evidence(
    folder_entry: dict | None,
    filename_entry: dict | None,
    header_entry: dict | None,
    parser: dict,
    suffix: str,
    size: int,
    folder_conflict: bool,
    conflict_level: str,
) -> list[str]:
    evidence = [f"extension={suffix or 'none'}", f"file_size_bytes={size}", f"parser_probe_status={parser['parser_probe_status']}"]
    if folder_entry:
        evidence.append(f"folder_type_hint={folder_entry['inferred_data_type']}")
    if filename_entry:
        evidence.append(f"filename_type_hint={filename_entry['inferred_data_type']}")
    if header_entry:
        evidence.append(f"header_type_hint={header_entry['inferred_data_type']}")
    if folder_conflict:
        evidence.append("folder_type_conflict=true")
        evidence.append(f"folder_header_conflict_level={conflict_level}")
    shape = parser["numeric_shape_hint"]
    evidence.append(f"numeric_rows={shape['rows']}")
    evidence.append(f"numeric_columns={shape['numeric_columns']}")
    for fallback in parser.get("recognition_fallbacks", []):
        evidence.append(f"recognition_fallback={fallback}")
    return evidence


def _manual_check_items(data_type: str, decision: str) -> list[str]:
    if decision in {"DEFERRED_TYPE", "REFERENCE_ONLY"}:
        return ["scan only; do not process in Phase 1.2"]
    if decision == "DUPLICATE_SUPPRESSED":
        return ["duplicate suppressed; inspect representative before processing"]
    if decision == "MANUAL_REVIEW":
        return ["manual review required before processing"]
    return [f"confirm triage decision and column mapping for {data_type}"]


def _process_priority(decision: str, confidence: float, validity: float) -> int:
    if decision != "AUTO_PROCESS":
        return 0
    return int(round((confidence + validity) * 50))


def _suppress_exact_duplicates(items: list[dict]) -> None:
    groups: dict[str, list[dict]] = {}
    for item in items:
        if item["source_hash"]:
            groups.setdefault(item["source_hash"], []).append(item)
    for source_hash, group in groups.items():
        candidates = [
            item for item in group
            if item["decision"] in {"AUTO_PROCESS", "MANUAL_REVIEW"}
            and item["supported_in_phase_1"]
            and item["parser_probe_status"] == "success"
        ]
        auto_candidates = [item for item in candidates if item["decision"] == "AUTO_PROCESS"]
        if len(candidates) < 2:
            continue
        group_id = hashlib.sha256(source_hash.encode("ascii")).hexdigest()[:12]
        representative_pool = auto_candidates or candidates
        representative = max(representative_pool, key=lambda item: (item["validity_score"], item["confidence_score"], item["process_priority"]))
        representative["duplicate_group_id"] = group_id
        representative["duplicate_representative"] = representative["relative_path"]
        for item in candidates:
            if item is representative:
                continue
            item["decision"] = "DUPLICATE_SUPPRESSED"
            item["duplicate_group_id"] = group_id
            item["duplicate_representative"] = representative["relative_path"]
            item["suppressed_by"] = representative["relative_path"]
            item["safe_to_process_no_origin"] = False
            item["safe_to_process_with_origin"] = False
            item["decision_reasons"] = ["exact_duplicate_suppressed"]
            item["manual_check_items"] = _manual_check_items(item["data_type_candidate"], "DUPLICATE_SUPPRESSED")


def _build_queue(source_root: Path, min_confidence: float, items: list[dict]) -> dict:
    queue_items = []
    for item in items:
        if item["decision"] != "AUTO_PROCESS":
            continue
        queue_items.append(
            {
                "queue_id": item["file_id"],
                "relative_path": item["relative_path"],
                "absolute_path": item["absolute_path"],
                "source_hash": item["source_hash"],
                "data_type": item["data_type_candidate"],
                "subtype": item["subtype_candidate"],
                "selected_processor": item["selected_processor"],
                "decision": item["decision"],
                "confidence_score": item["confidence_score"],
                "validity_score": item["validity_score"],
                "manual_check_required": item["manual_check_required"],
                "column_mapping": item["column_role_candidates"],
                "sheet_name": item["sheet_name"],
                "sample_id": Path(item["file_name"]).stem,
                "traceability_group_id": item["traceability_group_id"],
                "traceability_group_path": item["traceability_group_path"],
                "traceability_role": item["traceability_role"],
                "reasons": item["decision_reasons"],
                "warnings": [],
                "evidence": item["evidence"],
                "folder_type_conflict": item["folder_type_conflict"],
                "duplicate_group_id": item["duplicate_group_id"],
                "duplicate_representative": item["duplicate_representative"],
            }
        )
    return {
        "queue_version": "1.0",
        "created_at": _now(),
        "config_hash": "phase1_2_rules_v1",
        "min_confidence": min_confidence,
        "source_root": str(source_root),
        "items": queue_items,
        "excluded_counts": _decision_count(items, "EXCLUDE_INVALID"),
        "ambiguous_counts": _decision_count(items, "MANUAL_REVIEW"),
        "duplicate_counts": _decision_count(items, "DUPLICATE_SUPPRESSED"),
        "deferred_counts": _decision_count(items, "DEFERRED_TYPE"),
        "reference_counts": _decision_count(items, "REFERENCE_ONLY"),
    }


def _decision_count(items: list[dict], decision: str) -> dict:
    return {"count": sum(1 for item in items if item["decision"] == decision)}


def _summary(items: list[dict]) -> dict:
    counts = {decision: 0 for decision in DECISIONS}
    for item in items:
        counts[item["decision"]] += 1
    return {"total_files": len(items), "decision_counts": counts}


def _write_outputs(project_root: Path, result: dict, *, output_root: Path | None = None) -> None:
    reports = output_dir(project_root, "reports", output_root=output_root)
    dashboard_path = (
        reports / "triage_index.md"
        if output_root is not None
        else output_dir(project_root, "review_dashboard") / "triage_index.md"
    )
    items = result["items"]
    queue = result["queue"]
    _write_json(reports / "data_triage_manifest.json", {key: value for key, value in result.items() if key != "queue"})
    _write_json(reports / "processing_queue.json", queue)
    _write_json(reports / "ambiguous_files.json", {"items": _items_by_decision(items, "MANUAL_REVIEW")})
    _write_json(reports / "excluded_files.json", {"items": _items_by_decision(items, "EXCLUDE_INVALID") + _items_by_decision(items, "AUXILIARY_ONLY")})
    _write_json(reports / "duplicate_candidates.json", {"items": _items_by_decision(items, "DUPLICATE_SUPPRESSED")})
    _write_json(reports / "source_hash_index.json", _source_hash_index(items))
    traceability_groups = _traceability_groups(items)
    _write_json(reports / "traceability_groups.json", {"groups": traceability_groups})
    _write_triage_report(reports / "data_triage_report.md", result)
    _write_item_report(reports / "processing_queue.md", "Processing Queue", queue["items"])
    _write_item_report(reports / "ambiguous_files.md", "Ambiguous Files", _items_by_decision(items, "MANUAL_REVIEW"))
    _write_item_report(reports / "excluded_files.md", "Excluded Files", _items_by_decision(items, "EXCLUDE_INVALID") + _items_by_decision(items, "AUXILIARY_ONLY"))
    _write_item_report(reports / "duplicate_candidates.md", "Duplicate Candidates", _items_by_decision(items, "DUPLICATE_SUPPRESSED"))
    _write_traceability_group_report(reports / "traceability_groups.md", traceability_groups)
    _write_triage_dashboard(dashboard_path, result)


def _traceability_groups(items: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in items:
        group_id = item["traceability_group_id"]
        group = grouped.setdefault(
            group_id,
            {
                "traceability_group_id": group_id,
                "traceability_group_path": item["traceability_group_path"],
                "file_count": 0,
                "data_type_counts": {},
                "decision_counts": {},
                "role_counts": {},
                "queued_files": [],
                "origin_project_files": [],
                "raw_numeric_files": [],
                "representative_files": [],
            },
        )
        group["file_count"] += 1
        _increment_count(group["data_type_counts"], item["data_type_candidate"])
        _increment_count(group["decision_counts"], item["decision"])
        _increment_count(group["role_counts"], item["traceability_role"])
        if item["decision"] == "AUTO_PROCESS":
            group["queued_files"].append(item["relative_path"])
        if item["traceability_role"] == "origin_project_reference":
            group["origin_project_files"].append(item["relative_path"])
        if item["traceability_role"] == "raw_or_exported_numeric_table":
            group["raw_numeric_files"].append(item["relative_path"])
        if len(group["representative_files"]) < 5:
            group["representative_files"].append(item["relative_path"])
    return sorted(grouped.values(), key=lambda group: group["traceability_group_path"])


def _increment_count(counts: dict, key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_triage_report(path: Path, result: dict) -> None:
    lines = ["# Data Triage Report", "", f"Source root: `{result['source_root']}`", ""]
    for decision, count in result["summary"]["decision_counts"].items():
        lines.append(f"- {decision}: {count}")
    lines.extend(["", "## Files", "", "| decision | data_type | traceability_role | traceability_group | confidence | validity | relative_path | reasons |", "|---|---|---|---|---:|---:|---|---|"])
    for item in result["items"]:
        lines.append(
            f"| {item['decision']} | {item['data_type_candidate']} | {item['traceability_role']} | `{item['traceability_group_path']}` | {item['confidence_score']} | {item['validity_score']} | `{item['relative_path']}` | {'; '.join(item['decision_reasons'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_item_report(path: Path, title: str, items: list[dict]) -> None:
    lines = [f"# {title}", "", f"Count: {len(items)}", "", "| decision | data_type | traceability_role | traceability_group | relative_path | reason | suppressed_by |", "|---|---|---|---|---|---|---|"]
    for item in items[:200]:
        lines.append(
            f"| {item.get('decision')} | {item.get('data_type_candidate', item.get('data_type'))} | {item.get('traceability_role', '')} | `{item.get('traceability_group_path', '')}` | `{item.get('relative_path')}` | {'; '.join(item.get('decision_reasons', item.get('reasons', [])))} | {item.get('suppressed_by', '') or ''} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_traceability_group_report(path: Path, groups: list[dict]) -> None:
    lines = [
        "# Traceability Groups",
        "",
        f"Count: {len(groups)}",
        "",
        "| group | files | data_types | roles | queued | origin_projects | examples |",
        "|---|---:|---|---|---:|---:|---|",
    ]
    for group in groups[:300]:
        data_types = "; ".join(f"{key}:{value}" for key, value in sorted(group["data_type_counts"].items()))
        roles = "; ".join(f"{key}:{value}" for key, value in sorted(group["role_counts"].items()))
        examples = "<br>".join(f"`{item}`" for item in group["representative_files"][:3])
        lines.append(
            f"| `{group['traceability_group_path']}` | {group['file_count']} | {data_types} | {roles} | {len(group['queued_files'])} | {len(group['origin_project_files'])} | {examples} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_triage_dashboard(path: Path, result: dict) -> None:
    lines = ["# Triage Dashboard", "", f"- Total files: {result['summary']['total_files']}"]
    for decision, count in result["summary"]["decision_counts"].items():
        lines.append(f"- {decision}: {count}")
    lines.append(f"- Queue items: {len(result['queue']['items'])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _items_by_decision(items: list[dict], decision: str) -> list[dict]:
    return [item for item in items if item["decision"] == decision]


def _source_hash_index(items: list[dict]) -> dict:
    index: dict[str, list[str]] = {}
    for item in items:
        index.setdefault(item["source_hash"], []).append(item["relative_path"])
    return index


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: str | None) -> str:
    return str(value or "").casefold().strip()


def _norm_path(value: str | None) -> str:
    return _norm(value).replace("\\", "/").strip("/")
