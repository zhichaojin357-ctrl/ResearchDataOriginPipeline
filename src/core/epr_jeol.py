from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook, load_workbook

from src.core.output_sanitizer import render_output_path
from src.core.project import ensure_write_path_allowed


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
    return [
        {"magnetic field": f"{round(x_value, 4)}", "intensity": f"{round(y_value, 3)}"}
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


def write_data_xlsx(path: Path, x_values: list[float], y_values: list[float]) -> None:
    """Write the skill-compatible data-only workbook: two columns and no header row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet()
    for x_value, y_value in zip(x_values, y_values):
        worksheet.append([round(x_value, 4), round(y_value, 3)])
    workbook.save(path)


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
    if raw_source is None or not export_y:
        return JeolEprExportSeries(export_x, export_y, "", "excel_export", None)

    try:
        decoded = read_jeol_cacqu(raw_source)
        decoded_x, decoded_y = to_export_series(decoded, points=len(export_y))
    except (OSError, ValueError, struct.error):
        return JeolEprExportSeries(export_x, export_y, "", "excel_export", None)

    decoded_x = [round(value, 4) for value in decoded_x]
    decoded_y = [round(value, 3) for value in decoded_y]
    if len(decoded_y) != len(export_y) or max_abs_delta(decoded_y, export_y) > 5e-4:
        return JeolEprExportSeries(export_x, export_y, "", "excel_export", None)
    return JeolEprExportSeries(
        decoded_x,
        export_y,
        decoded.header.x_unit.strip(),
        "verified_jeol_raw_header",
        raw_source,
    )


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


def export_data(roots: list[Path], output_root: Path) -> dict[str, tuple[Path, list[float], list[float]]]:
    """Export verified JEOL cAcqu files to data-only Excel tables."""
    exported: dict[str, tuple[Path, list[float], list[float]]] = {}
    for source_root, source in collect_raw_files(roots):
        x_values, y_values = decode_jeol_cacqu_series(source)
        destination = destination_for(source, source_root, output_root)
        write_data_xlsx(destination, x_values, y_values)
        exported[source.name] = (destination, x_values, y_values)
    return exported


def write_compare_report(
    reference_dir: Path,
    exported: dict[str, tuple[Path, list[float], list[float]]],
    report_xlsx: Path,
) -> None:
    """Write an optional comparison workbook against known JEOL Excel exports."""
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
        same = exported.get(reference.stem)
        if same:
            destination, export_x, export_y = same
            same_max_x = max_abs_delta(ref_x, export_x)
            same_max_y = max_abs_delta(ref_y, export_y)
            same_rms_y = rms_delta(ref_y, export_y)
            result = "PASS" if len(ref_x) == len(export_x) and same_max_x == 0 and same_max_y == 0 else "DIFF"
            same_sheet.append([reference.name, destination.name, len(ref_x), len(export_x), same_max_x, same_max_y, same_rms_y, result])
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

    report_xlsx.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(report_xlsx)


def export_jeol_cwesr_to_xlsx(
    roots: list[Path],
    output_root: Path,
    *,
    reference_dir: Path | None = None,
    report_xlsx: Path | None = None,
) -> dict[str, object]:
    ensure_write_path_allowed(Path.cwd(), output_root, output_root=output_root)
    exported = export_data(roots, output_root)
    if reference_dir is not None and report_xlsx is not None:
        ensure_write_path_allowed(Path.cwd(), report_xlsx, output_root=output_root)
        write_compare_report(reference_dir, exported, report_xlsx)
    return {
        "exported_xlsx": len(exported),
        "output_root": ".",
        "reference_dir": render_output_path(reference_dir, output_root=output_root) if reference_dir else None,
        "report_xlsx": render_output_path(report_xlsx, output_root=output_root) if report_xlsx else None,
        "files": [render_output_path(item[0], output_root=output_root) for item in exported.values()],
    }


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
