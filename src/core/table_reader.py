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


X_COLUMN_NEEDLES = [
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
    "area",
    "面积",
    "height",
    "高度",
    "signal",
]


def read_table(path: Path) -> list[dict[str, str]]:
    return read_table_with_metadata(path).rows


def read_table_with_metadata(path: Path) -> TableReadResult:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required to read Excel files") from exc
        frame, sheet_name, header_row_index, sheet_scores = _best_excel_frame(pd.read_excel(path, sheet_name=None, header=None))
        rows = [
            {str(key): "" if value is None or pd.isna(value) else str(value) for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]
        return TableReadResult(rows, sheet_name=sheet_name, header_row_index=header_row_index, sheet_scores=sheet_scores)

    text = _read_text(path)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t; ")
    except csv.Error:
        dialect = csv.excel

    numeric_rows = _headerless_numeric_rows(text)
    if numeric_rows:
        return TableReadResult(numeric_rows)

    rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
    if rows and rows[0]:
        return TableReadResult([{str(key): "" if value is None else str(value) for key, value in row.items()} for row in rows])

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
            if normalized_needle and normalized_needle in lower:
                return original
    return None


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


def _best_header_row(frame):
    scored = []
    max_header_scan = min(10, len(frame.index))
    for header_index in range(max_header_scan):
        header_values = list(frame.iloc[header_index].values)
        headers = [_header_value(value, index) for index, value in enumerate(header_values)]
        data = frame.iloc[header_index + 1 :].copy()
        data.columns = headers
        data = data.dropna(how="all")
        numeric_rows = sum(1 for _idx, row in data.iterrows() if any(_to_float(value) is not None for value in row))
        numeric_columns = sum(1 for column in data.columns if any(_to_float(value) is not None for value in data[column].tolist()))
        header_bonus = _header_bonus(headers)
        score = numeric_rows * max(numeric_columns, 1) + header_bonus * 10
        scored.append((score, header_bonus, numeric_rows, numeric_columns, -header_index, data, header_index))
    best = max(scored, key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
    return best[5], int(best[6]), int(best[2]), int(best[3]), int(best[1])


def _header_value(value: object, index: int) -> str:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "nan":
        return f"Unnamed: {index}"
    return text


def _header_bonus(columns: list[str]) -> int:
    x_hit = _pick_column(columns, X_COLUMN_NEEDLES)
    y_hit = _pick_column(columns, Y_COLUMN_NEEDLES)
    return int(bool(x_hit)) + int(bool(y_hit))


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


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8-sig", errors="replace")


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
