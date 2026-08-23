from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from math import isfinite
from pathlib import Path


@dataclass(frozen=True)
class TableReadResult:
    rows: list[dict[str, str]]
    sheet_name: str | None = None
    header_row_index: int | None = None
    sheet_scores: dict[str, dict[str, float | int | str | None]] | None = None
    # Optional parser provenance.  Keep these defaults empty so existing callers
    # that only consume tabular rows remain fully backward compatible.
    source_format: str | None = None
    format_metadata: dict[str, object] | None = None


X_COLUMN_NEEDLES = [
    "x",
    "2theta",
    "2θ",
    "two theta",
    "wavelength",
    "波长",
    "wavenumber",
    "波数",
    "raman",
    "potential",
    "电位",
    "voltage",
    "frequency",
    "freq",
    "hz",
    "频率",
    "time",
    "时间",
    "retention",
    "保留",
    "binding energy",
    "结合能",
    "magnetic field",
    "磁场",
]
Y_COLUMN_NEEDLES = [
    "y",
    "intensity",
    "强度",
    "counts",
    "计数",
    "current",
    "电流",
    "absorbance",
    "吸光度",
    "reflectance",
    "反射率",
    "transmittance",
    "透过率",
    "phase",
    "z'",
    "zreal",
    "re z",
    "re(z)",
    "real impedance",
    "area",
    "面积",
    "height",
    "高度",
    "signal",
]


def read_table(path: Path) -> list[dict[str, str]]:
    return read_table_with_metadata(path).rows


def read_table_with_metadata(path: Path, *, allow_legacy_xls_com: bool = True) -> TableReadResult:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required to read Excel files") from exc
        try:
            frames = pd.read_excel(path, sheet_name=None, header=None)
        except ImportError as exc:
            if suffix == ".xls" and "xlrd" in str(exc).lower():
                if not allow_legacy_xls_com:
                    raise RuntimeError("legacy .xls requires xlrd or explicit Excel COM processing") from exc
                return _read_legacy_xls_with_excel_com(path)
            raise
        frame, sheet_name, header_row_index, sheet_scores = _best_excel_frame(frames)
        rows = [
            {str(key): "" if value is None or pd.isna(value) else str(value) for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]
        return TableReadResult(rows, sheet_name=sheet_name, header_row_index=header_row_index, sheet_scores=sheet_scores)

    text = read_text_with_fallback(path)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t; ")
    except csv.Error:
        dialect = csv.excel

    zplotw_result = _zplotw_table_result(text)
    if zplotw_result is not None:
        return zplotw_result

    bracketed_result = _bracketed_data_table_result(text)
    if bracketed_result is not None:
        return bracketed_result

    hitachi_uvvis_result = _hitachi_u3900_wavelength_scan_table_result(text)
    if hitachi_uvvis_result is not None:
        return hitachi_uvvis_result

    numeric_rows = _headerless_numeric_rows(text)
    if numeric_rows:
        return TableReadResult(numeric_rows)

    grid = [row for row in csv.reader(text.splitlines(), dialect=dialect)]
    if grid:
        return _table_result_from_excel_grids({"text": grid}, max_header_scan=_text_header_scan_limit(text))

    return TableReadResult(_numeric_rows_from_text(text))


def coerce_numeric_rows(rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    if not rows:
        return []
    columns = list(rows[0].keys())
    x_key = _pick_column(columns, X_COLUMN_NEEDLES)
    y_key = _pick_column(columns, Y_COLUMN_NEEDLES)
    if x_key == y_key or x_key is None or y_key is None:
        numeric_columns = []
        for column in columns:
            values = [_to_float(row.get(column, "")) for row in rows]
            if any(value is not None for value in values):
                numeric_columns.append(column)
        if len(numeric_columns) < 2:
            return []
        x_key, y_key = numeric_columns[0], numeric_columns[1]

    numeric = []
    for row in rows:
        x_value = _to_float(row.get(x_key, ""))
        y_value = _to_float(row.get(y_key, ""))
        if x_value is not None and y_value is not None:
            numeric.append((x_value, y_value))
    return numeric


def _pick_column(columns: list[str], needles: list[str]) -> str | None:
    lowered = [(column, _normalize_header(column)) for column in columns]
    for needle in needles:
        normalized_needle = _normalize_header(needle)
        for original, lower in lowered:
            if _header_contains_needle(lower, normalized_needle):
                return original
    return None


def _header_contains_needle(normalized_header: str, normalized_needle: str) -> bool:
    if not normalized_needle:
        return False
    if re.fullmatch(r"[a-z0-9]", normalized_needle):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_needle)}(?![a-z0-9])"
        return re.search(pattern, normalized_header) is not None
    return normalized_needle in normalized_header


def _best_excel_frame(frames: dict[str, object]):
    scored = []
    for order, (sheet_name, frame) in enumerate(frames.items()):
        candidate_frame, header_row_index, numeric_rows, numeric_columns, header_bonus = _best_header_row(frame)
        score = numeric_rows * max(numeric_columns, 1) + header_bonus * 10
        scored.append((score, header_bonus, numeric_rows, numeric_columns, -order, sheet_name, candidate_frame, header_row_index))
    best = max(scored, key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
    sheet_scores = {
        str(item[5]): {
            "score": item[0],
            "header_bonus": item[1],
            "numeric_rows": item[2],
            "numeric_columns": item[3],
            "header_row_index": item[7],
        }
        for item in scored
    }
    return best[6], str(best[5]), int(best[7]), sheet_scores


def _read_legacy_xls_with_excel_com(path: Path) -> TableReadResult:
    """Read legacy OLE `.xls` through a private hidden Excel instance when xlrd is absent."""
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("xlrd or pywin32 Excel COM is required to read legacy .xls files") from exc

    excel = None
    workbook = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        _configure_excel_for_safe_read(excel)
        workbook = excel.Workbooks.Open(str(path.resolve()), ReadOnly=True, UpdateLinks=0)
        grids = {}
        for worksheet in workbook.Worksheets:
            used = worksheet.UsedRange
            values = used.Value
            if values is None:
                grids[str(worksheet.Name)] = []
            elif not isinstance(values, tuple):
                grids[str(worksheet.Name)] = [[values]]
            elif values and not isinstance(values[0], tuple):
                grids[str(worksheet.Name)] = [list(values)]
            else:
                grids[str(worksheet.Name)] = [list(row) for row in values]
        return _table_result_from_excel_grids(grids, max_header_scan=20)
    finally:
        if workbook is not None:
            workbook.Close(False)
        if excel is not None:
            excel.Quit()


def _configure_excel_for_safe_read(excel: object) -> None:
    _safe_set_com_attr(excel, "Visible", False)
    _safe_set_com_attr(excel, "DisplayAlerts", False)
    _safe_set_com_attr(excel, "EnableEvents", False)
    _safe_set_com_attr(excel, "AskToUpdateLinks", False)
    # Microsoft Office constant: msoAutomationSecurityForceDisable.
    _safe_set_com_attr(excel, "AutomationSecurity", 3)


def _safe_set_com_attr(obj: object, name: str, value: object) -> None:
    try:
        setattr(obj, name, value)
    except Exception:
        return


def _table_result_from_excel_grids(grids: dict[str, list[list[object]]], *, max_header_scan: int = 10) -> TableReadResult:
    scored = []
    for order, (sheet_name, grid) in enumerate(grids.items()):
        rows, header_row_index, numeric_rows, numeric_columns, header_bonus = _best_rows_from_grid(grid, max_header_scan=max_header_scan)
        score = numeric_rows * max(numeric_columns, 1) + header_bonus * 10
        scored.append((score, header_bonus, numeric_rows, numeric_columns, -order, str(sheet_name), rows, header_row_index))
    if not scored:
        return TableReadResult([])
    best = max(scored, key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
    sheet_scores = {
        item[5]: {
            "score": item[0],
            "header_bonus": item[1],
            "numeric_rows": item[2],
            "numeric_columns": item[3],
            "header_row_index": item[7],
        }
        for item in scored
    }
    return TableReadResult(best[6], sheet_name=best[5], header_row_index=int(best[7]), sheet_scores=sheet_scores)


def _best_rows_from_grid(grid: list[list[object]], *, max_header_scan: int = 10) -> tuple[list[dict[str, str]], int, int, int, int]:
    if not grid:
        return [], 0, 0, 0, 0
    scored = []
    max_header_scan = min(max_header_scan, len(grid))
    for header_index in range(max_header_scan):
        headers = _dedupe_headers([_header_value(value, index) for index, value in enumerate(grid[header_index])])
        data_rows = []
        for raw_row in grid[header_index + 1 :]:
            if not raw_row or all(value is None or str(value).strip() == "" for value in raw_row):
                continue
            row = {
                header: "" if value is None else str(value)
                for header, value in zip(headers, raw_row)
            }
            data_rows.append(row)
        numeric_rows = sum(1 for row in data_rows if any(_to_float(value) is not None for value in row.values()))
        numeric_columns = sum(
            1
            for header in headers
            if any(_to_float(row.get(header, "")) is not None for row in data_rows)
        )
        header_bonus = _header_bonus(headers)
        score = numeric_rows * max(numeric_columns, 1) + header_bonus * 10 - _header_penalty(headers) * 5
        scored.append((score, header_bonus, numeric_rows, numeric_columns, -header_index, data_rows, header_index))
    best = max(scored, key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
    return best[5], int(best[6]), int(best[2]), int(best[3]), int(best[1])


def _best_header_row(frame):
    scored = []
    max_header_scan = min(20, len(frame.index))
    if max_header_scan == 0:
        return frame.copy(), 0, 0, 0, 0
    for header_index in range(max_header_scan):
        header_values = list(frame.iloc[header_index].values)
        headers = _dedupe_headers([_header_value(value, index) for index, value in enumerate(header_values)])
        data = frame.iloc[header_index + 1 :].copy()
        data.columns = headers
        data = data.dropna(how="all")
        numeric_rows = sum(1 for _idx, row in data.iterrows() if any(_to_float(value) is not None for value in row))
        numeric_columns = sum(
            1
            for column_index in range(len(data.columns))
            if any(_to_float(value) is not None for value in data.iloc[:, column_index].tolist())
        )
        header_bonus = _header_bonus(headers)
        score = numeric_rows * max(numeric_columns, 1) + header_bonus * 10 - _header_penalty(headers) * 5
        scored.append((score, header_bonus, numeric_rows, numeric_columns, -header_index, data, header_index))
    best = max(scored, key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
    return best[5], int(best[6]), int(best[2]), int(best[3]), int(best[1])


def _dedupe_headers(headers: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    output = []
    for header in headers:
        count = counts.get(header, 0)
        counts[header] = count + 1
        output.append(header if count == 0 else f"{header}.{count}")
    return output


def _header_value(value: object, index: int) -> str:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "nan":
        return f"Unnamed: {index}"
    return text


def _header_bonus(columns: list[str]) -> int:
    x_hit = _pick_column(columns, X_COLUMN_NEEDLES)
    y_hit = _pick_column(columns, Y_COLUMN_NEEDLES)
    normalized = [_normalize_header(column) for column in columns]
    summary_hits = {
        "metric": any(value in {"metric", "parameter", "item"} for value in normalized),
        "value": any(value in {"value", "reported"} for value in normalized),
        "unit": any(value == "unit" for value in normalized),
    }
    return int(bool(x_hit)) + int(bool(y_hit)) + sum(int(hit) for hit in summary_hits.values())


def _header_penalty(columns: list[str]) -> int:
    return sum(1 for column in columns if _to_float(column) is not None)


def _normalize_header(value: object) -> str:
    text = str(value).casefold()
    text = text.replace("μ", "u").replace("µ", "u").replace("θ", "theta")
    text = re.sub(r"[\[\]\(\),;:/\\_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _to_float(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _text_header_scan_limit(text: str) -> int:
    first_lines = "\n".join(text.splitlines()[:100]).casefold()
    if "amperometric i-t curve" in first_lines or "time/sec" in first_lines:
        return 100
    metadata_markers = (
        "instrument model",
        "impedance - potential",
        "init e",
        "final e",
        "frequency (hz)",
        "amplitude",
        "quiet time",
    )
    return 80 if any(marker in first_lines for marker in metadata_markers) else 10


def _zplotw_table_result(text: str) -> TableReadResult | None:
    lines = text.splitlines()
    first_block = "\n".join(lines[:20]).casefold()
    has_zplotw_banner = any(
        re.search(r"\bzplotw\s+data\s+file\s*:", line, flags=re.IGNORECASE)
        for line in lines[:20]
    )
    if (
        "zplotw data file" not in first_block
        and "z60w data file" not in first_block
        and not any(_has_frequency_hz_header(line) for line in lines[:80])
    ):
        return None

    header_index = None
    headers: list[str] = []
    for index, line in enumerate(lines[:80]):
        cleaned = line.strip().strip('"').strip()
        lowered = cleaned.casefold()
        if _has_frequency_hz_header(lowered) and "z'" in lowered and "z''" in lowered:
            header_index = index
            normalized = re.sub(r"freq\s*\(\s*hz\s*\)", "Freq(Hz)", cleaned, flags=re.IGNORECASE)
            headers = _dedupe_headers([part for part in re.split(r"\s+", normalized) if part])
            break
    if header_index is None or len(headers) < 3:
        return None

    rows: list[dict[str, str]] = []
    for raw_line in lines[header_index + 1 :]:
        stripped = raw_line.strip().strip('"').strip()
        if not stripped:
            continue
        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) < len(headers):
            continue
        if _to_float(parts[0]) is None:
            continue
        rows.append({header: parts[idx] if idx < len(parts) else "" for idx, header in enumerate(headers)})
    if not rows:
        return None
    numeric_columns = sum(
        1
        for header in headers
        if any(_to_float(row.get(header, "")) is not None for row in rows)
    )
    source_format = None
    format_metadata = None
    if has_zplotw_banner and len(rows) >= 2 and _has_scribner_zplotw_impedance_headers(headers):
        source_format = "scribner_zplotw_impedance"
        format_metadata = {
            "vendor": "Scribner",
            "vendor_signature": "ZPlotW Data File + Freq(Hz) + Z'(a) + Z''(b)",
            "signature_headers": ["Freq(Hz)", "Z'(a)", "Z''(b)"],
        }
    return TableReadResult(
        rows,
        sheet_name="ZPlotW",
        header_row_index=header_index,
        sheet_scores={
            "ZPlotW": {
                "score": len(rows) * max(numeric_columns, 1),
                "header_bonus": _header_bonus(headers),
                "numeric_rows": len(rows),
                "numeric_columns": numeric_columns,
                "header_row_index": header_index,
            }
        },
        source_format=source_format,
        format_metadata=format_metadata,
    )


def _has_frequency_hz_header(line: str) -> bool:
    return re.search(r"\bfreq\s*\(\s*hz\s*\)", line.casefold()) is not None


def _has_scribner_zplotw_impedance_headers(headers: list[str]) -> bool:
    """Return true only for the documented ZPlotW complex-impedance columns."""
    normalized = "\n".join(str(header) for header in headers)
    return bool(
        _has_frequency_hz_header(normalized)
        and re.search(r"z'\s*\(\s*a\s*\)", normalized, flags=re.IGNORECASE)
        and re.search(r"z''\s*\(\s*b\s*\)", normalized, flags=re.IGNORECASE)
    )


def _bracketed_data_table_result(text: str) -> TableReadResult | None:
    lines = text.splitlines()
    data_index = None
    for index, line in enumerate(lines):
        if line.strip().casefold() == "[data]":
            data_index = index
            break
    if data_index is None:
        return None

    section_lines: list[str] = []
    for line in lines[data_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            break
        section_lines.append(line)
    if len(section_lines) < 2:
        return None

    try:
        dialect = csv.Sniffer().sniff("\n".join(section_lines[:10]), delimiters=",\t; ")
    except csv.Error:
        dialect = csv.excel
    grid = [row for row in csv.reader(section_lines, dialect=dialect) if any(str(value).strip() for value in row)]
    if len(grid) < 2:
        return None
    result = _table_result_from_excel_grids({"Data": grid}, max_header_scan=min(5, len(grid)))
    if not result.rows or len(coerce_numeric_rows(result.rows)) < 2:
        return None
    return TableReadResult(
        result.rows,
        sheet_name="Data",
        header_row_index=(data_index + 1 + (result.header_row_index or 0)),
        sheet_scores=result.sheet_scores,
    )


def _hitachi_u3900_wavelength_scan_table_result(text: str) -> TableReadResult | None:
    """Read only the explicit spectrum block from a Hitachi U-3900 text export."""

    lines = text.splitlines()
    signature = "\n".join(lines[:100]).casefold()
    if (
        "u-3900 spectrophotometer" not in signature
        or "measurement type:" not in signature
        or "wavelength scan" not in signature
        or "data points" not in signature
    ):
        return None

    header_index: int | None = None
    signal_header = ""
    raw_signal_header = ""
    for index, line in enumerate(lines[:200]):
        parts = [part.strip() for part in re.split(r"[\t,;]+", line.strip()) if part.strip()]
        if len(parts) < 2:
            continue
        x_header = _normalize_header(parts[0])
        y_header = _normalize_header(parts[1])
        if x_header not in {"nm", "wavelength", "wavelength nm"}:
            continue
        if y_header in {"abs", "absorbance"}:
            signal_header = "absorbance"
        elif y_header in {"r", "%r", "reflectance", "reflectance %"}:
            signal_header = "reflectance_percent" if "%" in parts[1] else "reflectance"
        elif y_header in {"t", "%t", "transmittance", "transmittance %"}:
            signal_header = "transmittance_percent" if "%" in parts[1] else "transmittance"
        else:
            continue
        header_index = index
        raw_signal_header = parts[1]
        break
    if header_index is None or not signal_header:
        return None

    rows: list[dict[str, str]] = []
    started = False
    for line in lines[header_index + 1 :]:
        parts = _split_numeric_line(line)
        if len(parts) < 2 or _to_float(parts[0]) is None or _to_float(parts[1]) is None:
            if started:
                break
            continue
        started = True
        rows.append({"wavelength_nm": parts[0], signal_header: parts[1]})
    if len(rows) < 2:
        return None
    return TableReadResult(
        rows,
        sheet_name="Hitachi U-3900 spectrum",
        header_row_index=header_index,
        sheet_scores={
            "Hitachi U-3900 spectrum": {
                "score": len(rows) * 2,
                "header_bonus": 2,
                "numeric_rows": len(rows),
                "numeric_columns": 2,
                "header_row_index": header_index,
            }
        },
        source_format="hitachi_u3900_wavelength_scan",
        format_metadata={
            "vendor": "Hitachi",
            "instrument_model": "U-3900 Spectrophotometer",
            "measurement_type": "Wavelength Scan",
            "signal_header": raw_signal_header,
            "data_section_only": True,
        },
    )


def _headerless_numeric_rows(text: str) -> list[dict[str, str]]:
    first_parts = None
    for line in text.splitlines():
        parts = _split_numeric_line(line)
        if parts:
            first_parts = parts
            break
    if not first_parts or len(first_parts) < 2:
        return []
    if any(_to_float(part) is None for part in first_parts[:2]):
        return []
    return _numeric_rows_from_text(text)


def _numeric_rows_from_text(text: str) -> list[dict[str, str]]:
    numeric_rows = []
    for line in text.splitlines():
        parts = _split_numeric_line(line)
        if len(parts) >= 2 and _to_float(parts[0]) is not None and _to_float(parts[1]) is not None:
            numeric_rows.append({"x": parts[0], "y": parts[1]})
    return numeric_rows


def _split_numeric_line(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "//")):
        return []
    return [part for part in re.split(r"[,\t; ]+", stripped) if part]
