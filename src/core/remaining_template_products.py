from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from src.core.template_product_common import (
    TargetPairing,
    _load_pairing_items,
    _resolve_pairing_path,
    _root_for_label,
)
from src.core.table_reader import coerce_numeric_rows, read_table_with_metadata, read_text_with_fallback
from src.processors.base import safe_name


REMAINING_TARGET_PRODUCT_KEYS = (
    "EIS",
    "Raman",
    "Mott-Schottky",
    "UV-vis DRS",
    "Tauc",
    "PL",
    "photocurrent",
    "FTIR",
)

def load_remaining_pairings(pairing_path: Path, root_map: dict[str, Path]) -> list[TargetPairing]:
    items = _load_pairing_items(pairing_path)
    selected: list[TargetPairing] = []
    seen: set[str] = set()
    for item in items:
        product_keys = _remaining_product_keys(item)
        if not product_keys:
            continue
        data_root_label = str(item.get("selected_data_root_label") or "")
        opju_root_label = str(item.get("selected_opju_root_label") or "")
        data_root = _root_for_label(root_map, data_root_label)
        opju_root = _root_for_label(root_map, opju_root_label)
        raw_data_paths = [str(value) for value in item.get("selected_data_relative_paths") or []]
        opju_relative = str(item.get("selected_opju_relative_path") or "")
        if not raw_data_paths or not opju_relative:
            continue
        for product_key in product_keys:
            if product_key in seen:
                continue
            selected.append(
                TargetPairing(
                    product_key=product_key,
                    data_type=product_key,
                    xps_subtype=str(item.get("xps_subtype") or ""),
                    data_root_label=data_root_label,
                    data_paths=[_resolve_pairing_path(data_root, value) for value in raw_data_paths],
                    opju_root_label=opju_root_label,
                    reference_opju=_resolve_pairing_path(opju_root, opju_relative),
                    raw=dict(item),
                )
            )
            seen.add(product_key)
    return selected


def _build_remaining_processed_plot_table(pairing: TargetPairing) -> tuple[list[str], list[list[float | str | None]], dict[str, str]]:
    if pairing.product_key == "EIS":
        result = read_table_with_metadata(pairing.data_paths[0])
        rows = _numeric_column_rows(result.rows, "z_real", ("z'", "z real", "zreal"), "minus_z_imag", ("-z''", "-z", "imag"))
        return ["z_real_ohm", "minus_z_imag_ohm"], rows, {
            "x_label": "Z' (ohm)",
            "y_label": "-Z'' (ohm)",
            "title": "EIS draft",
            "plot_type": "line+symbol",
            "notes": "Nyquist draft only; equivalent-circuit interpretation requires manual review.",
        }
    if pairing.product_key == "Raman":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["raman_shift_cm-1", "intensity"], rows, {
            "x_label": "Raman shift (cm-1)",
            "y_label": "Intensity (a.u.)",
            "title": "Raman draft",
            "plot_type": "line",
        }
    if pairing.product_key == "Mott-Schottky":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["potential_v", "signal"], rows, {
            "x_label": "Potential (V)",
            "y_label": "Signal (manual review)",
            "title": "Mott-Schottky draft",
            "plot_type": "line+symbol",
            "notes": "Carrier type and band positions are not inferred.",
        }
    if pairing.product_key == "PL":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["wavelength_nm", "counts"], rows, {
            "x_label": "Wavelength (nm)",
            "y_label": "Counts",
            "title": "PL draft",
            "plot_type": "line",
        }
    if pairing.product_key == "photocurrent":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["time_s", "current_a"], rows, {
            "x_label": "Time (s)",
            "y_label": "Current (A)",
            "title": "Photocurrent draft",
            "plot_type": "line",
            "notes": "Light on/off segmentation requires manual review if labels are needed.",
        }
    if pairing.product_key == "FTIR":
        return _ftir_overlay_table(pairing.data_paths)
    raise ValueError(f"Unsupported remaining product key: {pairing.product_key}")


def _numeric_column_rows(
    rows: list[dict[str, str]],
    x_header: str,
    x_needles: tuple[str, ...],
    y_header: str,
    y_needles: tuple[str, ...],
) -> list[list[float | str | None]]:
    if not rows:
        raise ValueError("No rows were read from the selected data table.")
    columns = list(rows[0].keys())
    x_col = _pick_column(columns, x_needles)
    y_col = _pick_column(columns, y_needles)
    if x_col is None or y_col is None or x_col == y_col:
        numeric = coerce_numeric_rows(rows)
        if len(numeric) < 2:
            raise ValueError(f"Could not find numeric columns for {x_header}/{y_header}.")
        return [[x, y] for x, y in numeric]
    output = []
    for row in rows:
        x_value = _to_float(row.get(x_col, ""))
        y_value = _to_float(row.get(y_col, ""))
        if x_value is not None and y_value is not None:
            output.append([x_value, y_value])
    if len(output) < 2:
        raise ValueError(f"Fewer than 2 numeric rows for {x_col}/{y_col}.")
    return output


def _coerced_xy_rows(path: Path) -> list[list[float | str | None]]:
    result = read_table_with_metadata(path)
    numeric = coerce_numeric_rows(result.rows)
    if len(numeric) < 2:
        raise ValueError(f"Fewer than 2 numeric rows could be read from {path}")
    return [[x, y] for x, y in numeric]


def _data_points_rows(path: Path) -> list[list[float | str | None]]:
    text = read_text_with_fallback(path)
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().casefold() == "data points":
            start = index + 1
            break
    if start is None:
        return _coerced_xy_rows(path)
    output = []
    for line in lines[start + 1 :]:
        parts = [part for part in re.split(r"[,\t; ]+", line.strip()) if part]
        if len(parts) < 2:
            continue
        x_value = _to_float(parts[0])
        y_value = _to_float(parts[1])
        if x_value is not None and y_value is not None:
            output.append([x_value, y_value])
    if len(output) < 2:
        raise ValueError(f"Fewer than 2 data-point rows could be read from {path}")
    return output


def _ftir_overlay_table(paths: list[Path]) -> tuple[list[str], list[list[float | str | None]], dict[str, str]]:
    series = []
    for path in paths:
        rows = _coerced_xy_rows(path)
        series.append((safe_name(path.stem), rows))
    if not series:
        raise ValueError("No FTIR source files were selected.")
    point_count = min(len(rows) for _name, rows in series)
    headers = ["wavenumber_cm-1", *[f"{name}_transmittance" for name, _rows in series]]
    output = []
    for index in range(point_count):
        row = [series[0][1][index][0]]
        for _name, rows in series:
            row.append(rows[index][1])
        output.append(row)
    return headers, output, {
        "x_label": "Wavenumber (cm-1)",
        "y_label": "Transmittance (a.u.)",
        "title": "FTIR draft",
        "plot_type": "line",
        "x_descending": "true",
        "notes": "Wavenumber direction and peak labels require manual review.",
    }


def _remaining_product_keys(item: dict[str, Any]) -> tuple[str, ...]:
    data_type = str(item.get("data_type") or "")
    if data_type == "UV-vis DRS / Tauc":
        return ("UV-vis DRS", "Tauc")
    return (data_type,) if data_type in REMAINING_TARGET_PRODUCT_KEYS else ()


def _pick_column(columns: list[str], needles: tuple[str, ...]) -> str | None:
    normalized = [(column, _normalize(column)) for column in columns]
    for needle in needles:
        norm_needle = _normalize(needle)
        for original, column in normalized:
            if norm_needle and norm_needle in column:
                return original
    return None


def _normalize(value: object) -> str:
    text = str(value).casefold()
    text = text.replace("\u03a9".casefold(), "ohm").replace("\u60df", "ohm")
    text = re.sub(r"[\[\]\(\),;:/\\_\s]+", " ", text)
    return text.strip()


def _to_float(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
