from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import tempfile
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl import Workbook, load_workbook

from src.core.file_utils import (
    apply_safe_owned_directory_removal,
    ensure_safe_output_file_target,
    file_sha256,
    lexical_absolute_path,
    plan_safe_owned_directory_removal,
)
from src.core.output_sanitizer import render_output_path
from src.core.project import (
    ensure_output_path_separate_from_inputs,
    ensure_write_path_allowed,
)
from src.processors.calculations import normalize_epr_magnetic_field_unit


DATA_OFFSET_CACQU = 9500
DEFAULT_EXPORT_POINTS = 4096  # Verified JEOL cAcqu export default.
JEOL_PROCESS_TYPES = {"cAcqu", "spin", "endor", "pAcqu", "cidep", "sod", "iso", "ani"}


@dataclass(frozen=True)
class JeolEprHeader:
    process_type: str
    filename: str
    aux_num: int
    data_set: int
    data_length: int
    data_kind: str
    x_offset: float
    x_range: float
    x_unit: str
    x_start: float
    x_stop: float


@dataclass(frozen=True)
class JeolEprDecodeResult:
    header: JeolEprHeader
    ch1: list[float]
    ch2: list[float] | None


@dataclass(frozen=True)
class JeolEprExportSeries:
    x_values: list[float]
    y_values: list[float]
    x_unit: str
    axis_source: str
    raw_source: Path | None


@dataclass(frozen=True)
class _JeolEprExportPlan:
    source_root: Path
    source: Path
    source_key: str
    destination: Path
    metadata_path: Path


@dataclass(frozen=True)
class _PreparedJeolEprExport:
    plan: _JeolEprExportPlan
    decoded: JeolEprDecodeResult
    x_values: list[float]
    y_values: list[float]
    source_sha256_before: str
    source_sha256_after: str


class _JeolEprRollbackError(RuntimeError):
    """Raised when a failed JEOL package commit cannot be fully rolled back."""


def looks_like_jeol_cwesr_file(path: Path) -> bool:
    """Return true for JEOL JES-FA/JES-X3-like binary EPR files."""
    if not path.is_file() or path.suffix.lower() in {".xlsx", ".xls", ".csv", ".txt"}:
        return False
    if path.stat().st_size < DATA_OFFSET_CACQU + 4:
        return False
    try:
        with path.open("rb") as handle:
            process_type = _read_c_string(handle, 16)
    except OSError:
        return False
    return process_type in JEOL_PROCESS_TYPES


def read_jeol_cacqu(path: Path) -> JeolEprDecodeResult:
    """Read a JEOL JES-FA/JES-X3 cAcqu file into CH1/CH2 float arrays."""
    with path.open("rb") as handle:
        process_type = _read_c_string(handle, 16)
        filename = _read_c_string(handle, 64)
        handle.read(4)
        aux_num = _read_i32(handle)
        data_set = _read_i32(handle)
        data_length = _read_i32(handle)
        data_kind = _read_c_string(handle, 15)
        handle.read(1)
        x_offset = _read_f32(handle)
        x_range = _read_f32(handle)
        x_unit = _read_c_string(handle, 16)
        handle.read(8)
        _read_c_string(handle, 16)
        handle.read(4)
        _read_c_string(handle, 16)
        x_start = _read_f32(handle)
        x_stop = _read_f32(handle)

        header = JeolEprHeader(
            process_type=process_type,
            filename=filename,
            aux_num=aux_num,
            data_set=data_set,
            data_length=data_length,
            data_kind=data_kind,
            x_offset=x_offset,
            x_range=x_range,
            x_unit=x_unit,
            x_start=x_start,
            x_stop=x_stop,
        )

        if process_type != "cAcqu":
            raise ValueError(f"unsupported JEOL EPR processType {process_type!r}; only cAcqu is enabled")
        if aux_num != 0 or data_set != 1:
            raise ValueError(f"unsupported JEOL EPR aux/dataSet combination aux={aux_num}, dataSet={data_set}")
        if data_kind not in {"real", "complex"}:
            raise ValueError(f"unsupported JEOL EPR dataKind {data_kind!r}")
        if data_length <= 0:
            raise ValueError(f"invalid JEOL EPR dataLength {data_length}")

        handle.seek(DATA_OFFSET_CACQU)
        raw = handle.read(4 * data_length)
        if len(raw) != 4 * data_length:
            raise ValueError("truncated JEOL EPR CH1 data")
        ch1 = list(struct.unpack(f"<{data_length}f", raw))

        ch2 = None
        if data_kind == "complex":
            raw = handle.read(4 * data_length)
            if len(raw) != 4 * data_length:
                raise ValueError("truncated JEOL EPR CH2 data")
            ch2 = list(struct.unpack(f"<{data_length}f", raw))

    return JeolEprDecodeResult(header=header, ch1=ch1, ch2=ch2)


def decode_jeol_cacqu_rows(path: Path, *, points: int = DEFAULT_EXPORT_POINTS) -> list[dict[str, str]]:
    """Decode JEOL cAcqu CH1 to the project's two-column EPR table shape.

    The default point count matches the verified JEOL cAcqu Excel export size.
    """
    decoded = read_jeol_cacqu(path)
    x_values, y_values = to_export_series(decoded, points=points)
    x_unit = normalize_epr_magnetic_field_unit(decoded.header.x_unit)
    field_header = f"magnetic field {x_unit}" if x_unit is not None else "magnetic field"
    return [
        {field_header: f"{round(x_value, 4)}", "intensity": f"{round(y_value, 3)}"}
        for x_value, y_value in zip(x_values, y_values)
    ]


def decode_jeol_cacqu_series(path: Path, *, points: int = DEFAULT_EXPORT_POINTS) -> tuple[list[float], list[float]]:
    """Decode JEOL cAcqu CH1 to rounded field/intensity series used by JEOL Excel export.

    ``points`` controls the export grid size. The default mirrors the verified JEOL
    cAcqu export point count, but callers may request another grid when the raw data
    length is compatible.
    """
    decoded = read_jeol_cacqu(path)
    x_values, y_values = to_export_series(decoded, points=points)
    return [round(value, 4) for value in x_values], [round(value, 3) for value in y_values]


def write_data_xlsx(
    path: Path,
    x_values: list[float],
    y_values: list[float],
    *,
    force: bool = False,
    output_root: Path | None = None,
) -> None:
    """Write the skill-compatible data-only workbook: two columns and no header row."""
    safe_root = _standalone_jeol_output_root(path, output_root)
    safe_path = _ensure_file_target_available(
        path,
        force=force,
        output_root=safe_root,
    )
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet()
    for x_value, y_value in zip(x_values, y_values):
        worksheet.append([round(x_value, 4), round(y_value, 3)])
    _save_workbook_atomically(
        workbook,
        safe_path,
        output_root=safe_root,
        force=force,
    )


def read_xy_xlsx(path: Path) -> tuple[list[float], list[float]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        x_values: list[float] = []
        y_values: list[float] = []
        for row in worksheet.iter_rows(values_only=True):
            if not row or row[0] is None:
                continue
            x_values.append(float(row[0]))
            y_values.append(float(row[1]))
        return x_values, y_values
    finally:
        workbook.close()


def read_verified_jeol_export_series(path: Path) -> JeolEprExportSeries:
    """Read a JEOL Excel export and repair its field grid from matching raw data.

    The legacy 4096-point exports contain the verified block-averaged signal but
    may retain only the first 1/16 of the raw magnetic-field span.  Replace that
    grid only when a same-name JEOL raw file is found and its decoded signal
    matches the workbook values.
    """
    export_x, export_y = read_xy_xlsx(path)
    raw_source = _matching_jeol_raw_source(path)
    if raw_source is not None and export_y:
        try:
            decoded = read_jeol_cacqu(raw_source)
            decoded_x, decoded_y = to_export_series(
                decoded,
                points=len(export_y),
            )
        except (OSError, ValueError, struct.error):
            pass
        else:
            decoded_x = [round(value, 4) for value in decoded_x]
            decoded_y = [round(value, 3) for value in decoded_y]
            if (
                len(decoded_y) == len(export_y)
                and max_abs_delta(decoded_y, export_y) <= 5e-4
            ):
                return JeolEprExportSeries(
                    decoded_x,
                    export_y,
                    decoded.header.x_unit.strip(),
                    "verified_jeol_raw_header",
                    raw_source,
                )

    metadata_unit = _verified_jeol_decoder_metadata_unit(
        path,
        exported_point_count=len(export_y),
    )
    if metadata_unit is not None:
        return JeolEprExportSeries(
            export_x,
            export_y,
            metadata_unit,
            "verified_jeol_decoder_metadata",
            None,
        )
    return JeolEprExportSeries(export_x, export_y, "", "excel_export", None)


def _verified_jeol_decoder_metadata_unit(
    export_path: Path,
    *,
    exported_point_count: int,
) -> str | None:
    """Read unit evidence only from a hash-matched official decoder package."""

    safe_export = lexical_absolute_path(export_path)
    if not safe_export.is_file() or exported_point_count <= 0:
        return None
    export_hash = file_sha256(safe_export)
    for candidate_root in safe_export.parents:
        relative = safe_export.relative_to(candidate_root)
        if len(relative.parts) < 2:
            continue
        metadata_path = (
            candidate_root
            / "metadata"
            / relative.with_suffix("")
            / "metadata.json"
        )
        if not metadata_path.is_file():
            continue
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            outputs = payload.get("outputs", {})
            decode = payload.get("decode", {})
            source = payload.get("source", {})
            header = payload.get("jeol_header", {})
            if not all(
                isinstance(item, dict)
                for item in (outputs, decode, source, header)
            ):
                continue
            if (
                payload.get("processor_name") != "jeol_cacqu_decoder"
                or payload.get("data_type") != "EPR"
                or payload.get("processing_status")
                != "processed_no_origin"
                or outputs.get("xlsx_sha256") != export_hash
                or int(decode.get("exported_point_count", 0))
                != exported_point_count
                or source.get("sha256_before")
                != source.get("sha256_after")
            ):
                continue
            unit = normalize_epr_magnetic_field_unit(header.get("x_unit"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if unit is not None:
            return unit
    return None


def _matching_jeol_raw_source(export_path: Path) -> Path | None:
    epr_root = next((parent for parent in export_path.parents if parent.name.casefold() == "epr"), None)
    if epr_root is None:
        return None
    stem = export_path.stem
    preferred = epr_root / export_path.parent.name / stem
    if looks_like_jeol_cwesr_file(preferred):
        return preferred
    matches = [
        candidate
        for candidate in epr_root.rglob(stem)
        if candidate.is_file() and looks_like_jeol_cwesr_file(candidate)
    ]
    if len(matches) == 1:
        return matches[0]
    same_group = [candidate for candidate in matches if candidate.parent.name == export_path.parent.name]
    return same_group[0] if len(same_group) == 1 else None


def collect_raw_files(roots: list[Path]) -> list[tuple[Path, Path]]:
    """Collect JEOL-like raw files after checking the processType header."""
    pairs: list[tuple[Path, Path]] = []
    for root in roots:
        if not root.exists():
            raise FileNotFoundError(f"JEOL EPR input root does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"JEOL EPR input root is not a directory: {root}")
        for path in sorted(root.rglob("*")):
            if looks_like_jeol_cwesr_file(path):
                pairs.append((root, path))
    return pairs


def destination_for(source: Path, source_root: Path, output_root: Path) -> Path:
    relative = source.relative_to(source_root)
    return output_root / source_root.name / relative.parent / f"{relative.name}.xlsx"


def metadata_destination_for(source: Path, source_root: Path, output_root: Path) -> Path:
    relative = source.relative_to(source_root)
    return output_root / "metadata" / source_root.name / relative.parent / relative.name / "metadata.json"


def export_data(
    roots: list[Path],
    output_root: Path,
    *,
    force: bool = False,
) -> dict[str, tuple[Path, list[float], list[float]]]:
    """Export verified JEOL cAcqu files to data-only Excel tables."""
    output_root = _validate_jeol_output_root(roots, output_root)
    exported, _metadata_paths = _export_data_with_metadata(
        roots,
        output_root,
        force=force,
    )
    return exported


def _export_data_with_metadata(
    roots: list[Path],
    output_root: Path,
    *,
    force: bool = False,
    reserved_output_paths: tuple[Path, ...] = (),
    comparison_reference_dir: Path | None = None,
    comparison_report_path: Path | None = None,
) -> tuple[dict[str, tuple[Path, list[float], list[float]]], list[Path]]:
    if (comparison_reference_dir is None) != (comparison_report_path is None):
        raise ValueError(
            "JEOL comparison reference_dir and report path must be provided together"
        )
    plans = _build_export_plan(
        roots,
        output_root,
        force=force,
        reserved_output_paths=reserved_output_paths,
    )
    prepared = [_prepare_jeol_export(plan) for plan in plans]
    final_targets = _prepare_jeol_export_targets(
        plans,
        output_root=output_root,
        force=force,
        reserved_output_paths=reserved_output_paths,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    ensure_safe_output_file_target(output_root, output_root=output_root)

    stage_root: Path | None = None
    preserve_stage_for_recovery = False
    try:
        stage_root = lexical_absolute_path(
            Path(
                tempfile.mkdtemp(
                    prefix=".jeol-epr-staging-",
                    dir=output_root,
                )
            )
        )
        ensure_safe_output_file_target(stage_root, output_root=output_root)
        staged_targets: list[Path] = []
        staged_exported: dict[str, tuple[Path, list[float], list[float]]] = {}
        final_exported: dict[str, tuple[Path, list[float], list[float]]] = {}
        metadata_paths: list[Path] = []

        for item in prepared:
            plan = item.plan
            staged_destination = _staged_jeol_path(
                plan.destination,
                output_root,
                stage_root,
            )
            staged_metadata = _staged_jeol_path(
                plan.metadata_path,
                output_root,
                stage_root,
            )
            write_data_xlsx(
                staged_destination,
                item.x_values,
                item.y_values,
                force=False,
                output_root=stage_root,
            )
            _write_jeol_decode_metadata(
                metadata_path=staged_metadata,
                source=plan.source,
                source_root=plan.source_root,
                source_key=plan.source_key,
                source_sha256_before=item.source_sha256_before,
                source_sha256_after=item.source_sha256_after,
                decoded=item.decoded,
                destination=staged_destination,
                output_root=stage_root,
                exported_point_count=len(item.x_values),
                force=False,
                published_destination=plan.destination,
                published_metadata_path=plan.metadata_path,
                published_output_root=output_root,
            )
            staged_exported[plan.source_key] = (
                staged_destination,
                item.x_values,
                item.y_values,
            )
            final_exported[plan.source_key] = (
                plan.destination,
                item.x_values,
                item.y_values,
            )
            metadata_paths.append(plan.metadata_path)
            staged_targets.extend((staged_destination, staged_metadata))

        if comparison_report_path is not None:
            staged_report = _staged_jeol_path(
                comparison_report_path,
                output_root,
                stage_root,
            )
            write_compare_report(
                comparison_reference_dir,
                staged_exported,
                staged_report,
                force=False,
                output_root=stage_root,
            )
            staged_targets.append(staged_report)

        _validate_staged_jeol_package(
            tuple(staged_targets),
            stage_root=stage_root,
        )
        _commit_staged_jeol_files(
            tuple(staged_targets),
            final_targets,
            output_root=output_root,
            stage_root=stage_root,
            force=force,
        )
        return final_exported, metadata_paths
    except _JeolEprRollbackError:
        preserve_stage_for_recovery = True
        raise
    finally:
        if stage_root is not None and not preserve_stage_for_recovery:
            _remove_safe_jeol_tree_best_effort(
                stage_root,
                output_root=output_root,
            )


def _build_export_plan(
    roots: list[Path],
    output_root: Path,
    *,
    force: bool,
    reserved_output_paths: tuple[Path, ...],
) -> list[_JeolEprExportPlan]:
    plans = [
        _JeolEprExportPlan(
            source_root=source_root,
            source=source,
            source_key=_jeol_export_source_key(source, source_root),
            destination=destination_for(source, source_root, output_root),
            metadata_path=metadata_destination_for(source, source_root, output_root),
        )
        for source_root, source in collect_raw_files(roots)
    ]
    plans.sort(key=lambda plan: (plan.source_key.casefold(), plan.source_key))

    source_keys: dict[str, _JeolEprExportPlan] = {}
    output_targets: dict[str, tuple[str, Path]] = {}
    for plan in plans:
        normalized_source_key = plan.source_key.casefold()
        previous = source_keys.get(normalized_source_key)
        if previous is not None:
            raise ValueError(
                "JEOL EPR export source key collision: "
                f"{plan.source_key!r} maps both {previous.source} and {plan.source}"
            )
        source_keys[normalized_source_key] = plan
        _register_export_target(
            output_targets,
            plan.destination,
            f"xlsx for {plan.source_key}",
        )
        _register_export_target(
            output_targets,
            plan.metadata_path,
            f"metadata for {plan.source_key}",
        )

    for index, reserved_path in enumerate(reserved_output_paths):
        _register_export_target(
            output_targets,
            reserved_path,
            f"reserved output {index + 1}",
        )

    targets = [path for _owner, path in output_targets.values()]
    safe_targets = [
        ensure_safe_output_file_target(path, output_root=output_root)
        for path in targets
    ]
    directory_targets = [
        path for path in safe_targets if path.exists() and path.is_dir()
    ]
    if directory_targets:
        rendered = ", ".join(
            _output_target_label(path, output_root) for path in directory_targets
        )
        raise IsADirectoryError(
            f"JEOL EPR export targets must be files, not directories: {rendered}"
        )
    if not force:
        existing = [path for path in safe_targets if path.exists()]
        if existing:
            rendered = ", ".join(
                _output_target_label(path, output_root) for path in existing
            )
            raise FileExistsError(
                "JEOL EPR export targets already exist; rerun with force=True "
                f"to overwrite explicitly: {rendered}"
            )
    return plans


def _prepare_jeol_export_targets(
    plans: list[_JeolEprExportPlan],
    *,
    output_root: Path,
    force: bool,
    reserved_output_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    targets = [
        path
        for plan in plans
        for path in (plan.destination, plan.metadata_path)
    ]
    targets.extend(reserved_output_paths)
    safe_targets = tuple(
        dict.fromkeys(
            ensure_safe_output_file_target(path, output_root=output_root)
            for path in targets
        )
    )
    existing = [
        path
        for path in safe_targets
        if os.path.lexists(os.fspath(path))
    ]
    directories = [path for path in existing if path.is_dir()]
    if directories:
        rendered = ", ".join(
            _output_target_label(path, output_root) for path in directories
        )
        raise IsADirectoryError(
            f"JEOL EPR export targets must be files, not directories: {rendered}"
        )
    if existing and not force:
        rendered = ", ".join(
            _output_target_label(path, output_root) for path in existing
        )
        raise FileExistsError(
            "JEOL EPR export targets already exist; rerun with force=True "
            f"to overwrite explicitly: {rendered}"
        )
    return safe_targets


def _prepare_jeol_export(plan: _JeolEprExportPlan) -> _PreparedJeolEprExport:
    source_hash_before = file_sha256(plan.source)
    decoded = read_jeol_cacqu(plan.source)
    x_values_raw, y_values_raw = to_export_series(
        decoded,
        points=DEFAULT_EXPORT_POINTS,
    )
    source_hash_after = file_sha256(plan.source)
    if source_hash_after != source_hash_before:
        raise RuntimeError(
            "JEOL EPR source changed during read-only decode: "
            f"{plan.source_key}"
        )
    return _PreparedJeolEprExport(
        plan=plan,
        decoded=decoded,
        x_values=[round(value, 4) for value in x_values_raw],
        y_values=[round(value, 3) for value in y_values_raw],
        source_sha256_before=source_hash_before,
        source_sha256_after=source_hash_after,
    )


def _jeol_export_source_key(source: Path, source_root: Path) -> str:
    relative = source.relative_to(source_root).as_posix()
    return f"{source_root.name}/{relative}"


def _register_export_target(
    targets: dict[str, tuple[str, Path]],
    path: Path,
    owner: str,
) -> None:
    normalized = str(lexical_absolute_path(path)).casefold()
    previous = targets.get(normalized)
    if previous is not None:
        previous_owner, previous_path = previous
        raise ValueError(
            "JEOL EPR output target collision: "
            f"{previous_owner} and {owner} both map to {previous_path}"
        )
    targets[normalized] = (owner, path)


def _output_target_label(path: Path, output_root: Path) -> str:
    try:
        return lexical_absolute_path(path).relative_to(
            lexical_absolute_path(output_root)
        ).as_posix()
    except ValueError:
        return path.name


def _ensure_file_target_available(
    path: Path,
    *,
    force: bool,
    output_root: Path,
) -> Path:
    safe_path = ensure_safe_output_file_target(path, output_root=output_root)
    exists = os.path.lexists(os.fspath(safe_path))
    if exists and safe_path.is_dir():
        raise IsADirectoryError(f"Output target is a directory: {safe_path}")
    if exists and not force:
        raise FileExistsError(
            f"Output target already exists; rerun with force=True: {safe_path}"
        )
    return safe_path


def _write_jeol_decode_metadata(
    *,
    metadata_path: Path,
    source: Path,
    source_root: Path,
    source_key: str,
    source_sha256_before: str,
    source_sha256_after: str,
    decoded: JeolEprDecodeResult,
    destination: Path,
    output_root: Path,
    exported_point_count: int,
    force: bool,
    published_destination: Path | None = None,
    published_metadata_path: Path | None = None,
    published_output_root: Path | None = None,
) -> None:
    safe_metadata_path = _ensure_file_target_available(
        metadata_path,
        force=force,
        output_root=output_root,
    )
    rendered_destination = published_destination or destination
    rendered_metadata_path = published_metadata_path or metadata_path
    rendered_output_root = published_output_root or output_root
    raw_point_count = decoded.header.data_length
    aggregation_factor = raw_point_count // exported_point_count
    source_key_digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:16]
    payload = {
        "schema_version": 1,
        "dataset_id": f"JEOL_EPR_{source.name}_{source_key_digest}",
        "data_type": "EPR",
        "processor_name": "jeol_cacqu_decoder",
        "processing_status": "processed_no_origin",
        "source_key": source_key,
        "source_hash": source_sha256_before,
        "source": {
            "root_label": source_root.name,
            "relative_path": source.relative_to(source_root).as_posix(),
            "sha256": source_sha256_before,
            "sha256_before": source_sha256_before,
            "sha256_after": source_sha256_after,
            "size_bytes": source.stat().st_size,
        },
        "jeol_header": asdict(decoded.header),
        "decode": {
            "channel": "CH1",
            "raw_point_count": raw_point_count,
            "exported_point_count": exported_point_count,
            "aggregation_factor": aggregation_factor,
            "aggregation_method": "contiguous_arithmetic_mean",
            "x_coordinate_method": "aggregation_bin_center_from_jeol_header",
            "x_round_digits": 4,
            "intensity_round_digits": 3,
        },
        "outputs": {
            "xlsx": render_output_path(
                rendered_destination,
                output_root=rendered_output_root,
            ),
            "xlsx_sha256": file_sha256(destination),
            "xlsx_size_bytes": destination.stat().st_size,
            "metadata": render_output_path(
                rendered_metadata_path,
                output_root=rendered_output_root,
            ),
        },
        "manual_check_required": True,
        "manual_check_items": [
            "Confirm the JEOL magnetic-field header unit before using field-derived candidates.",
            "Confirm the acquisition microwave frequency before calculating any g candidate.",
            "Review the decoded CH1 aggregation against an instrument export when one is available.",
        ],
        "forbidden_claims": [
            "do not assign EPR radical species automatically",
        ],
        "scientific_claims": {
            "g_candidate_generated": False,
            "radical_assignment_generated": False,
        },
        "warnings": [
            "This command decodes the JEOL cAcqu signal only; it does not identify radical species.",
        ],
    }
    _write_text_atomically(
        safe_metadata_path,
        json.dumps(payload, ensure_ascii=False, indent=2),
        output_root=output_root,
        force=force,
    )


def write_compare_report(
    reference_dir: Path,
    exported: dict[str, tuple[Path, list[float], list[float]]],
    report_xlsx: Path,
    *,
    force: bool = False,
    output_root: Path | None = None,
) -> None:
    """Write an optional comparison workbook against known JEOL Excel exports."""
    if not reference_dir.is_dir():
        raise FileNotFoundError(
            f"JEOL comparison reference directory not found: {reference_dir}"
        )
    safe_root = _standalone_jeol_output_root(report_xlsx, output_root)
    safe_report = _ensure_file_target_available(
        report_xlsx,
        force=force,
        output_root=safe_root,
    )
    workbook = Workbook()
    same_sheet = workbook.active
    same_sheet.title = "same_name_compare"
    same_sheet.append(
        [
            "reference",
            "same_name_export",
            "ref_rows",
            "export_rows",
            "same_max_x",
            "same_max_y",
            "same_rms_y",
            "same_result",
        ]
    )
    cross_sheet = workbook.create_sheet("best_crossmatch")
    cross_sheet.append(["reference", "best_export", "best_max_x", "best_max_y", "best_rms_y"])

    for reference in sorted(reference_dir.glob("*.xlsx")):
        ref_x, ref_y = read_xy_xlsx(reference)
        same_name_candidates = [
            (source_key, item)
            for source_key, item in exported.items()
            if Path(source_key).name == reference.stem
        ]
        if len(same_name_candidates) == 1:
            _source_key, same = same_name_candidates[0]
            destination, export_x, export_y = same
            same_max_x = max_abs_delta(ref_x, export_x)
            same_max_y = max_abs_delta(ref_y, export_y)
            same_rms_y = rms_delta(ref_y, export_y)
            result = "PASS" if len(ref_x) == len(export_x) and same_max_x == 0 and same_max_y == 0 else "DIFF"
            same_sheet.append([reference.name, destination.name, len(ref_x), len(export_x), same_max_x, same_max_y, same_rms_y, result])
        elif len(same_name_candidates) > 1:
            source_keys = "; ".join(
                source_key for source_key, _item in same_name_candidates
            )
            same_sheet.append(
                [
                    reference.name,
                    source_keys,
                    len(ref_x),
                    "",
                    "",
                    "",
                    "",
                    "AMBIGUOUS",
                ]
            )
        else:
            same_sheet.append([reference.name, "", len(ref_x), "", "", "", "", "MISSING"])

        best: list[tuple[float, float, float, Path]] = []
        for destination, export_x, export_y in exported.values():
            if len(ref_x) != len(export_x):
                continue
            best.append((max_abs_delta(ref_y, export_y), max_abs_delta(ref_x, export_x), rms_delta(ref_y, export_y), destination))
        if best:
            best.sort(key=lambda item: item[0])
            best_max_y, best_max_x, best_rms_y, best_destination = best[0]
            cross_sheet.append([reference.name, best_destination.name, best_max_x, best_max_y, best_rms_y])

    _save_workbook_atomically(
        workbook,
        safe_report,
        output_root=safe_root,
        force=force,
    )


def export_jeol_cwesr_to_xlsx(
    roots: list[Path],
    output_root: Path,
    *,
    reference_dir: Path | None = None,
    report_xlsx: Path | None = None,
    force: bool = False,
) -> dict[str, object]:
    output_root = _validate_jeol_output_root(roots, output_root)
    if (reference_dir is None) != (report_xlsx is None):
        raise ValueError(
            "JEOL comparison requires both reference_dir and report_xlsx"
        )
    write_comparison = reference_dir is not None and report_xlsx is not None
    protected_inputs = [
        *roots,
        *((reference_dir,) if reference_dir is not None else ()),
    ]
    ensure_output_path_separate_from_inputs(
        Path.cwd(),
        output_root,
        protected_inputs,
    )
    if write_comparison:
        if not reference_dir.is_dir():
            raise FileNotFoundError(
                f"JEOL comparison reference directory not found: {reference_dir}"
            )
        ensure_write_path_allowed(
            Path.cwd(),
            report_xlsx,
            output_root=output_root,
        )
    reserved_output_paths = (
        (
            ensure_safe_output_file_target(
                report_xlsx,
                output_root=output_root,
            ),
        )
        if write_comparison
        else ()
    )
    exported, metadata_paths = _export_data_with_metadata(
        roots,
        output_root,
        force=force,
        reserved_output_paths=reserved_output_paths,
        comparison_reference_dir=reference_dir if write_comparison else None,
        comparison_report_path=report_xlsx if write_comparison else None,
    )
    return {
        "exported_xlsx": len(exported),
        "output_root": ".",
        "reference_dir": render_output_path(reference_dir, output_root=output_root) if reference_dir else None,
        "report_xlsx": render_output_path(report_xlsx, output_root=output_root) if report_xlsx else None,
        "files": [render_output_path(item[0], output_root=output_root) for item in exported.values()],
        "metadata_files": [
            render_output_path(metadata_path, output_root=output_root)
            for metadata_path in metadata_paths
        ],
        "source_keys": list(exported),
    }


def _validate_jeol_output_root(
    roots: list[Path],
    output_root: Path,
) -> Path:
    safe_root = lexical_absolute_path(output_root)
    for project_root in dict.fromkeys(
        (Path.cwd(), Path(__file__).resolve().parents[2])
    ):
        ensure_write_path_allowed(
            project_root,
            safe_root,
            output_root=safe_root,
        )
    ensure_output_path_separate_from_inputs(
        Path.cwd(),
        safe_root,
        tuple(roots),
    )
    ensure_safe_output_file_target(safe_root, output_root=safe_root)
    return safe_root


def _standalone_jeol_output_root(
    path: Path,
    output_root: Path | None,
) -> Path:
    safe_root = lexical_absolute_path(output_root or path.parent)
    safe_path = lexical_absolute_path(path)
    lowered_parts = tuple(part.casefold() for part in safe_path.parts)
    forbidden_parts = {"src", "templates", "raw_data"}
    if forbidden_parts.intersection(lowered_parts):
        raise ValueError(
            "Refusing JEOL output under raw/src/templates; provide an explicit "
            "external output_root"
        )
    for project_root in dict.fromkeys(
        (Path.cwd(), Path(__file__).resolve().parents[2])
    ):
        ensure_write_path_allowed(
            project_root,
            safe_path,
            output_root=safe_root,
        )
    ensure_safe_output_file_target(safe_path, output_root=safe_root)
    return safe_root


def _save_workbook_atomically(
    workbook: Workbook,
    target: Path,
    *,
    output_root: Path,
    force: bool,
) -> None:
    safe_target = _ensure_file_target_available(
        target,
        force=force,
        output_root=output_root,
    )
    safe_target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{safe_target.name}.",
        suffix=".tmp.xlsx",
        dir=safe_target.parent,
    )
    os.close(descriptor)
    temporary = ensure_safe_output_file_target(
        Path(temporary_name),
        output_root=output_root,
    )
    try:
        workbook.save(temporary)
        verification = load_workbook(temporary, read_only=True, data_only=True)
        verification.close()
        ensure_safe_output_file_target(safe_target, output_root=output_root)
        if os.path.lexists(os.fspath(safe_target)) and not force:
            raise FileExistsError(
                f"Output target appeared before atomic commit: {safe_target}"
            )
        os.replace(temporary, safe_target)
    finally:
        if os.path.lexists(os.fspath(temporary)):
            temporary.unlink()


def _write_text_atomically(
    target: Path,
    content: str,
    *,
    output_root: Path,
    force: bool,
) -> None:
    safe_target = _ensure_file_target_available(
        target,
        force=force,
        output_root=output_root,
    )
    safe_target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{safe_target.name}.",
        suffix=".tmp",
        dir=safe_target.parent,
    )
    temporary = ensure_safe_output_file_target(
        Path(temporary_name),
        output_root=output_root,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        ensure_safe_output_file_target(safe_target, output_root=output_root)
        if os.path.lexists(os.fspath(safe_target)) and not force:
            raise FileExistsError(
                f"Output target appeared before atomic commit: {safe_target}"
            )
        os.replace(temporary, safe_target)
    finally:
        if os.path.lexists(os.fspath(temporary)):
            temporary.unlink()


def _staged_jeol_path(
    final_path: Path,
    output_root: Path,
    stage_root: Path,
) -> Path:
    safe_final = ensure_safe_output_file_target(
        final_path,
        output_root=output_root,
    )
    relative = safe_final.relative_to(lexical_absolute_path(output_root))
    return ensure_safe_output_file_target(
        stage_root / relative,
        output_root=stage_root,
    )


def _validate_staged_jeol_package(
    paths: tuple[Path, ...],
    *,
    stage_root: Path,
) -> None:
    for path in paths:
        safe_path = ensure_safe_output_file_target(path, output_root=stage_root)
        if not safe_path.is_file() or safe_path.stat().st_size <= 0:
            raise RuntimeError(
                f"Staged JEOL package file is missing or empty: {safe_path}"
            )
        if safe_path.suffix.casefold() == ".xlsx":
            workbook = load_workbook(safe_path, read_only=True, data_only=True)
            workbook.close()
        elif safe_path.name.casefold() == "metadata.json":
            payload = json.loads(safe_path.read_text(encoding="utf-8"))
            if payload.get("processing_status") != "processed_no_origin":
                raise RuntimeError(
                    f"Staged JEOL metadata has invalid status: {safe_path}"
                )


def _commit_staged_jeol_files(
    staged_targets: tuple[Path, ...],
    final_targets: tuple[Path, ...],
    *,
    output_root: Path,
    stage_root: Path,
    force: bool,
) -> None:
    if len(staged_targets) != len(final_targets):
        raise ValueError("Staged and final JEOL package target counts do not match")
    safe_finals = tuple(
        ensure_safe_output_file_target(path, output_root=output_root)
        for path in final_targets
    )
    existing = [
        path for path in safe_finals if os.path.lexists(os.fspath(path))
    ]
    directories = [path for path in existing if path.is_dir()]
    if directories:
        raise IsADirectoryError(
            "JEOL package file target became a directory before commit: "
            + ", ".join(str(path) for path in directories)
        )
    if existing and not force:
        raise FileExistsError(
            "JEOL package targets appeared before commit; rerun with force=True: "
            + ", ".join(str(path) for path in existing)
        )
    for path in staged_targets:
        safe_path = ensure_safe_output_file_target(path, output_root=stage_root)
        if not safe_path.is_file() or safe_path.stat().st_size <= 0:
            raise RuntimeError(f"Staged JEOL package file changed before commit: {path}")

    backup_root = ensure_safe_output_file_target(
        stage_root / "rollback",
        output_root=stage_root,
    )
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for final_path in safe_finals:
            if not os.path.lexists(os.fspath(final_path)):
                continue
            backup = ensure_safe_output_file_target(
                backup_root / final_path.relative_to(output_root),
                output_root=stage_root,
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace_jeol(final_path, backup)
            backups.append((backup, final_path))
        for staged_path, final_path in zip(
            staged_targets,
            safe_finals,
            strict=True,
        ):
            if os.path.lexists(os.fspath(final_path)):
                raise RuntimeError(
                    f"JEOL package target changed during commit: {final_path}"
                )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace_jeol(staged_path, final_path)
            installed.append(final_path)
    except Exception as exc:
        rollback_errors: list[str] = []
        for final_path in reversed(installed):
            try:
                safe_path = ensure_safe_output_file_target(
                    final_path,
                    output_root=output_root,
                )
                if not safe_path.is_file():
                    raise RuntimeError("installed target is no longer a regular file")
                safe_path.unlink()
            except Exception as rollback_exc:
                rollback_errors.append(f"remove {final_path}: {rollback_exc}")
        for backup, final_path in reversed(backups):
            try:
                if os.path.lexists(os.fspath(final_path)):
                    raise RuntimeError(
                        "unexpected target appeared before rollback restoration"
                    )
                final_path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_replace_jeol(backup, final_path)
            except Exception as rollback_exc:
                rollback_errors.append(f"restore {final_path}: {rollback_exc}")
        if rollback_errors:
            raise _JeolEprRollbackError(
                "JEOL package commit failed and rollback was incomplete; "
                f"recovery files remain under {stage_root}: "
                + "; ".join(rollback_errors)
            ) from exc
        raise RuntimeError(
            f"JEOL package commit failed; previous outputs were restored: {exc}"
        ) from exc


def _atomic_replace_jeol(source: Path, target: Path) -> None:
    os.replace(source, target)


def _remove_safe_jeol_tree(path: Path, *, output_root: Path) -> None:
    if not os.path.lexists(os.fspath(path)):
        return
    plan = plan_safe_owned_directory_removal(path, output_root=output_root)
    apply_safe_owned_directory_removal(plan, output_root=output_root)


def _remove_safe_jeol_tree_best_effort(
    path: Path,
    *,
    output_root: Path,
) -> None:
    try:
        _remove_safe_jeol_tree(path, output_root=output_root)
    except Exception as exc:
        warnings.warn(
            "JEOL EPR outputs were committed, but the task-owned staging "
            f"directory could not be removed safely: {path}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )


def max_abs_delta(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return math.inf
    return max(abs(a - b) for a, b in zip(left, right))


def rms_delta(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return math.inf
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)) / len(left))


def to_export_series(decoded: JeolEprDecodeResult, *, points: int = DEFAULT_EXPORT_POINTS) -> tuple[list[float], list[float]]:
    raw_points = decoded.header.data_length
    if points <= 0:
        raise ValueError(f"JEOL EPR export points must be positive, got {points}")
    if raw_points < 2:
        raise ValueError(f"JEOL EPR raw_points must be at least 2, got {raw_points}")
    if raw_points % points:
        raise ValueError(f"JEOL EPR raw_points {raw_points} must be divisible by export points {points}")
    repeats = raw_points // points
    y_values = [
        sum(decoded.ch1[index * repeats + offset] for offset in range(repeats)) / repeats
        for index in range(points)
    ]
    x_step = decoded.header.x_range / (raw_points - 1)
    x_values = [
        decoded.header.x_offset + x_step * (index * repeats + (repeats - 1) / 2)
        for index in range(points)
    ]
    return x_values, y_values


def _read_c_string(handle, length: int) -> str:
    raw = handle.read(length)
    return raw.split(b"\0", 1)[0].decode("latin1", "replace")


def _read_i32(handle) -> int:
    raw = handle.read(4)
    if len(raw) != 4:
        raise ValueError("truncated JEOL EPR int32 header field")
    return struct.unpack("<i", raw)[0]


def _read_f32(handle) -> float:
    raw = handle.read(4)
    if len(raw) != 4:
        raise ValueError("truncated JEOL EPR float32 header field")
    return struct.unpack("<f", raw)[0]
