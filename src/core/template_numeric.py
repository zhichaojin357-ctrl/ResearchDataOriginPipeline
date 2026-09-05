"""Pure table and numeric helpers for both Origin template routes.

The executor re-exports these private names for existing callers.  No Origin
objects or rendering policy are involved here.
"""
from __future__ import annotations

import math


def _paired_numeric_row_bounds(
    rows: list[list[object]],
    x_index: int,
    y_index: int,
) -> tuple[int, int] | None:
    first = last = count = 0
    for row_index, row in enumerate(rows, start=1):
        if (
            x_index < len(row)
            and y_index < len(row)
            and _finite_numeric_value(row[x_index]) is not None
            and _finite_numeric_value(row[y_index]) is not None
        ):
            if not count:
                first = row_index
            last = row_index
            count += 1
    if not count or count != last - first + 1:
        return None
    return first, last


def _finite_numeric_value(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_verified_current_data(
    product_key: str,
    rows: list[list[object]],
    xy_ranges: list[dict[str, object]],
    graph_snapshot: dict[str, object],
) -> dict[str, object]:
    plots = [
        dict(plot)
        for plot in graph_snapshot.get("plots", [])
        if isinstance(plot, dict)
    ]
    reasons: list[str] = []
    if str(graph_snapshot.get("status") or "") != "ready":
        reasons.append("reopened graph data snapshot is not ready")
    if len(plots) != len(xy_ranges):
        reasons.append(
            f"reopened graph has {len(plots)} plots; expected {len(xy_ranges)}"
        )
    for index, expected in enumerate(xy_ranges):
        if index >= len(plots):
            break
        plot = plots[index]
        source_x_index = int(expected.get("source_x_index", expected["x_col"] - 1))
        source_y_index = int(expected.get("source_y_index", expected["y_col"] - 1))
        source_row_from = int(expected.get("source_row_from", expected["row_from"]))
        source_row_to = int(expected.get("source_row_to", expected["row_to"]))
        expected_x_raw = [
            _finite_numeric_value(rows[row_index - 1][source_x_index])
            for row_index in range(source_row_from, source_row_to + 1)
        ]
        expected_y_raw = [
            _finite_numeric_value(rows[row_index - 1][source_y_index])
            for row_index in range(source_row_from, source_row_to + 1)
        ]
        actual_x_raw = [
            _finite_numeric_value(value)
            for value in (plot.get("x_values") or [])
        ]
        actual_y_raw = [
            _finite_numeric_value(value)
            for value in (plot.get("y_values") or [])
        ]
        if any(value is None for value in expected_x_raw) or any(value is None for value in expected_y_raw):
            reasons.append(f"plot {index + 1} expected CSV range contains a nonfinite X/Y value")
            continue
        if any(value is None for value in actual_x_raw) or any(value is None for value in actual_y_raw):
            reasons.append(f"plot {index + 1} reopened X/Y range contains a nonfinite value")
            continue
        if actual_x_raw != expected_x_raw:
            reasons.append(f"plot {index + 1} X values differ from processed CSV")
        if actual_y_raw != expected_y_raw:
            reasons.append(f"plot {index + 1} Y values differ from processed CSV")
        if (
            int(plot.get("plot_row_from") or 0) != expected["row_from"]
            or int(plot.get("plot_row_to") or 0) != expected["row_to"]
        ):
            reasons.append(f"plot {index + 1} displayed row range differs")
        expected_x_letter = str(expected.get("expected_x_col_letter") or "")
        expected_y_letter = str(expected.get("expected_y_col_letter") or "")
        if expected_x_letter and str(plot.get("x_col_letter") or "").upper() != expected_x_letter:
            reasons.append(f"plot {index + 1} X dataset column differs")
        if expected_y_letter and str(plot.get("y_col_letter") or "").upper() != expected_y_letter:
            reasons.append(f"plot {index + 1} Y dataset column differs")
        if expected_x_letter and str(plot.get("x_mapping_source") or "") != "graph_plot_mapping":
            reasons.append(f"plot {index + 1} lacks explicit graph X mapping readback")
        if "expected_y_masked_rows" in expected:
            expected_masked_rows = [
                int(value) for value in list(expected.get("expected_y_masked_rows") or [])
            ]
            actual_masked_rows = [
                int(value) for value in list(plot.get("y_masked_rows") or [])
            ]
            if str(plot.get("mask_readback_status") or "") != "ready":
                reasons.append(f"plot {index + 1} lacks native mask-state readback")
            elif actual_masked_rows != expected_masked_rows:
                reasons.append(f"plot {index + 1} Y masked rows differ")
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            f"Reopened {product_key} graph contains the exact processed CSV X/Y values "
            "and displayed row ranges."
            if not reasons
            else "; ".join(reasons)
        ),
        "expected_plot_count": len(xy_ranges),
        "actual_plot_count": len(plots),
        "reasons": reasons,
    }


def _mott_schottky_candidate_guides(
    headers: list[str],
    rows: list[list[object]],
    *,
    series_count: int,
) -> dict[str, object]:
    if series_count < 1 or len(headers) < series_count + 1:
        return {}
    numeric: list[tuple[float, list[float]]] = []
    for row in rows:
        if len(row) < series_count + 1:
            continue
        x_value = _finite_float(row[0])
        y_values = [_finite_float(value) for value in row[1 : series_count + 1]]
        if x_value is None or any(value is None for value in y_values):
            continue
        numeric.append((x_value, [float(value) for value in y_values if value is not None]))
    numeric.sort(key=lambda item: item[0])
    if len(numeric) < 5 or any(numeric[index][0] >= numeric[index + 1][0] for index in range(len(numeric) - 1)):
        return {}

    x_values = [item[0] for item in numeric]
    series = [[item[1][series_index] for item in numeric] for series_index in range(series_count)]
    rising_end = min(max(range(len(values)), key=values.__getitem__) for values in series)
    window_size = 3
    if rising_end + 1 < window_size:
        return {}

    best: tuple[tuple[float, float], int, list[dict[str, float]]] | None = None
    for start in range(0, rising_end - window_size + 2):
        stop = start + window_size
        x_window = x_values[start:stop]
        fits = [_linear_fit(x_window, values[start:stop]) for values in series]
        if any(not fit or float(fit["slope"]) <= 0 for fit in fits):
            continue
        minimum_r_squared = min(float(fit["r_squared"]) for fit in fits)
        mean_r_squared = sum(float(fit["r_squared"]) for fit in fits) / len(fits)
        candidate = ((minimum_r_squared, mean_r_squared), start, fits)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return {}
    _score, start, independent_fits = best
    stop = start + window_size
    x_window = x_values[start:stop]
    y_windows = [values[start:stop] for values in series]
    shared = _shared_x_intercept_fit(x_window, y_windows, full_x_span=x_values[-1] - x_values[0])
    if not shared or min(float(value) for value in shared.get("r_squared", [])) < 0.98:
        return {}

    next_index = stop if stop <= rising_end else stop - 1
    guide_x_end = x_values[next_index]
    return {
        "series_headers": headers[1 : series_count + 1],
        "linear_interval_candidate": [x_window[0], x_window[-1]],
        "linear_fit_point_count": window_size,
        "independent_linear_fits": independent_fits,
        "shared_x_intercept_candidate": shared["x_intercept"],
        "constrained_slopes": shared["slopes"],
        "constrained_r_squared": shared["r_squared"],
        "guide_x_end": guide_x_end,
        "data_x_span": x_values[-1] - x_values[0],
        "visible_y_max": max(max(values) for values in series),
    }


def _linear_fit(x_values: list[float], y_values: list[float]) -> dict[str, float]:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return {}
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    denominator = sum((value - mean_x) ** 2 for value in x_values)
    if denominator <= 0:
        return {}
    slope = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(x_values, y_values)) / denominator
    intercept = mean_y - slope * mean_x
    total = sum((value - mean_y) ** 2 for value in y_values)
    residual = sum((y_value - (slope * x_value + intercept)) ** 2 for x_value, y_value in zip(x_values, y_values))
    r_squared = 1.0 if total <= 0 else 1.0 - residual / total
    return {"slope": slope, "intercept": intercept, "r_squared": r_squared}


def _shared_x_intercept_fit(
    x_values: list[float],
    y_series: list[list[float]],
    *,
    full_x_span: float,
) -> dict[str, object]:
    if len(x_values) < 3 or full_x_span <= 0 or any(len(values) != len(x_values) for values in y_series):
        return {}
    upper = x_values[0] - max(full_x_span * 1e-6, abs(x_values[-1] - x_values[0]) * 0.01)
    lower = x_values[0] - 5.0 * full_x_span
    grid_count = 4000
    step = (upper - lower) / grid_count

    # These totals depend only on the selected data window, not its candidate intercept.
    means = [sum(values) / len(values) for values in y_series]
    totals = [
        sum((y_value - mean_y) ** 2 for y_value in values)
        for values, mean_y in zip(y_series, means)
    ]

    def evaluate(x_intercept: float) -> tuple[float, list[float], list[float]]:
        offsets = [x_value - x_intercept for x_value in x_values]
        denominator = sum(value * value for value in offsets)
        if denominator <= 0:
            return math.inf, [], []
        slopes: list[float] = []
        r_squared_values: list[float] = []
        objective = 0.0
        for values, total in zip(y_series, totals):
            slope = sum(offset * y_value for offset, y_value in zip(offsets, values)) / denominator
            if slope <= 0:
                return math.inf, [], []
            residual = sum((y_value - slope * offset) ** 2 for offset, y_value in zip(offsets, values))
            if total <= 0:
                return math.inf, [], []
            objective += residual / total
            slopes.append(slope)
            r_squared_values.append(1.0 - residual / total)
        return objective, slopes, r_squared_values

    best_index = -1
    best: tuple[float, list[float], list[float]] = (math.inf, [], [])
    for index in range(grid_count + 1):
        candidate = evaluate(lower + index * step)
        if candidate[0] < best[0]:
            best = candidate
            best_index = index
    if best_index <= 0 or best_index >= grid_count:
        return {}

    left = lower + (best_index - 1) * step
    right = lower + (best_index + 1) * step
    for _ in range(50):
        first = left + (right - left) / 3.0
        second = right - (right - left) / 3.0
        if evaluate(first)[0] <= evaluate(second)[0]:
            right = second
        else:
            left = first
    x_intercept = (left + right) / 2.0
    objective, slopes, r_squared_values = evaluate(x_intercept)
    if not math.isfinite(objective) or not slopes:
        return {}
    return {
        "x_intercept": x_intercept,
        "slopes": slopes,
        "r_squared": r_squared_values,
        "normalized_residual_objective": objective,
    }


def _padded_axis_bounds(min_value: float, max_value: float, *, zero_floor: bool = False) -> tuple[float, float]:
    if max_value <= min_value:
        span = max(abs(max_value), abs(min_value), 1.0)
    else:
        span = max_value - min_value
    pad = max(span * 0.08, 1e-9)
    lower = min_value - pad
    upper = max_value + pad
    if zero_floor and min_value >= 0:
        lower = 0.0
    return lower, upper


def _photocurrent_xy_series(
    rows: list[list[object]],
    pairs: list[tuple[int, int]],
) -> list[tuple[list[float], list[float]]]:
    """Return strict contiguous finite X/Y runs for each processed photocurrent pair."""
    series: list[tuple[list[float], list[float]]] = []
    for x_column, y_column in pairs:
        x_index = x_column - 1
        y_index = y_column - 1
        x_values: list[float] = []
        y_values: list[float] = []
        finite_run_ended = False
        for row in rows:
            x_value = _finite_numeric_value(row[x_index]) if x_index < len(row) else None
            y_value = _finite_numeric_value(row[y_index]) if y_index < len(row) else None
            if x_value is None and y_value is None:
                if x_values:
                    finite_run_ended = True
                continue
            if x_value is None or y_value is None or finite_run_ended:
                return []
            x_values.append(float(x_value))
            y_values.append(float(y_value))
        if not x_values or len(x_values) != len(y_values):
            return []
        series.append((x_values, y_values))
    return series


def _shared_x_contiguous_y_series(
    rows: list[list[object]],
    pairs: list[tuple[int, int]],
) -> list[tuple[list[float], list[float]]]:
    """Return contiguous shared-X series while allowing different Y run lengths."""
    series: list[tuple[list[float], list[float]]] = []
    for x_column, y_column in pairs:
        x_index = x_column - 1
        y_index = y_column - 1
        bounds = _paired_numeric_row_bounds(rows, x_index, y_index)
        if bounds is None:
            return []
        first_row, last_row = bounds
        x_values: list[float] = []
        y_values: list[float] = []
        for row_index, row in enumerate(rows, start=1):
            x_value = _finite_numeric_value(row[x_index]) if x_index < len(row) else None
            y_value = _finite_numeric_value(row[y_index]) if y_index < len(row) else None
            if y_value is not None and x_value is None:
                return []
            if first_row <= row_index <= last_row:
                if x_value is None or y_value is None:
                    return []
                x_values.append(float(x_value))
                y_values.append(float(y_value))
            elif y_value is not None:
                return []
        if not x_values or len(x_values) != len(y_values):
            return []
        series.append((x_values, y_values))
    return series


def _photocurrent_reference_xy_series(
    snapshot: dict[str, object] | None,
) -> list[tuple[list[float], list[float]]]:
    if not isinstance(snapshot, dict):
        return []
    plots = snapshot.get("plots")
    if not isinstance(plots, list) or not plots:
        return []
    series: list[tuple[list[float], list[float]]] = []
    for plot in plots:
        if not isinstance(plot, dict):
            return []
        raw_x = plot.get("x_values")
        raw_y = plot.get("y_values")
        if not isinstance(raw_x, list) or not isinstance(raw_y, list) or len(raw_x) != len(raw_y):
            return []
        x_values: list[float] = []
        y_values: list[float] = []
        finite_run_ended = False
        for raw_x_value, raw_y_value in zip(raw_x, raw_y):
            x_value = _finite_numeric_value(raw_x_value)
            y_value = _finite_numeric_value(raw_y_value)
            if x_value is None and y_value is None:
                if x_values:
                    finite_run_ended = True
                continue
            if x_value is None or y_value is None or finite_run_ended:
                return []
            x_values.append(float(x_value))
            y_values.append(float(y_value))
        if not x_values:
            return []
        series.append((x_values, y_values))
    return series


def _photocurrent_axis_series_match(
    current: list[tuple[list[float], list[float]]],
    reference: list[tuple[list[float], list[float]]],
    *,
    axis: str,
) -> bool:
    if axis not in {"x", "y"} or len(current) != len(reference):
        return False
    axis_index = 0 if axis == "x" else 1
    reference_values = [value for series in reference for value in series[axis_index]]
    if not reference_values:
        return False
    reference_span = max(reference_values) - min(reference_values)
    absolute_tolerance = max(abs(reference_span) * 1e-12, 1e-15)
    for current_series, reference_series in zip(current, reference):
        current_values = current_series[axis_index]
        expected_values = reference_series[axis_index]
        if len(current_values) != len(expected_values):
            return False
        if any(
            not math.isclose(
                actual,
                expected,
                rel_tol=1e-9,
                abs_tol=absolute_tolerance,
            )
            for actual, expected in zip(current_values, expected_values)
        ):
            return False
    return True


_finite_float = _finite_numeric_value
