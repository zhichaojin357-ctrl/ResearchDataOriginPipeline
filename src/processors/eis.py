from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.optimize import least_squares

from src.core.table_reader import read_table_with_metadata


@dataclass(frozen=True)
class EisPoint:
    source_index: int
    frequency_hz: float | None
    z_real_ohm: float
    minus_z_imag_ohm: float

    def to_row(self) -> dict[str, float | int | None]:
        return {
            "source_index": self.source_index,
            "frequency_hz": self.frequency_hz,
            "z_real_ohm": self.z_real_ohm,
            "minus_z_imag_ohm": self.minus_z_imag_ohm,
        }


@dataclass(frozen=True)
class EisIgnoredPoint:
    point: EisPoint
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {**self.point.to_row(), "reason": self.reason}


@dataclass(frozen=True)
class EisCleaningResult:
    raw_points: list[EisPoint]
    cleaned_points: list[EisPoint]
    ignored_points: list[EisIgnoredPoint]
    selected_columns: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict[str, object]:
        return {
            "raw_point_count": len(self.raw_points),
            "cleaned_point_count": len(self.cleaned_points),
            "ignored_point_count": len(self.ignored_points),
            "selected_columns": dict(self.selected_columns),
            "ignored_points": [item.to_dict() for item in self.ignored_points],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class EisFitResult:
    method: str
    points: list[tuple[float, float]]
    parameters: dict[str, float] = field(default_factory=dict)
    residual_sse: float = math.nan
    robust_cost: float = math.nan
    semicircle_classification: str = "manual_review"
    warning: str = ""
    adapter_provenance: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        payload = {
            "method": self.method,
            "model": "Model A: Rs + (Rct || CPE)",
            "point_count": len(self.points),
            "parameters": dict(self.parameters),
            "residual_sse": self.residual_sse,
            "robust_cost": self.robust_cost,
            "semicircle_classification": self.semicircle_classification,
            "warning": self.warning,
            "review_policy": "draft fit for visualization/manual review only",
            "forbidden_claims_avoided": [
                "no final equivalent-circuit conclusion",
                "no charge-transfer resistance interpretation",
                "no electrochemical mechanism conclusion",
            ],
        }
        if self.adapter_provenance:
            payload["adapter_provenance"] = dict(self.adapter_provenance)
        return payload


def clean_eis_file(path: Path) -> EisCleaningResult:
    table = read_table_with_metadata(path)
    if not table.rows:
        raise ValueError(f"EIS table has no rows: {path}")
    columns = list(table.rows[0].keys())
    selected = _pick_eis_columns(columns)
    points: list[EisPoint] = []
    warnings: list[str] = []
    for row_index, row in enumerate(table.rows, start=1):
        z_real = _to_float(row.get(selected["z_real_ohm"], ""))
        minus_z_imag = _to_float(row.get(selected["minus_z_imag_ohm"], ""))
        frequency = _to_float(row.get(selected["frequency_hz"], "")) if selected.get("frequency_hz") else None
        if z_real is None or minus_z_imag is None:
            continue
        if _looks_like_raw_imaginary_column(selected["minus_z_imag_ohm"]):
            minus_z_imag = abs(minus_z_imag)
        points.append(EisPoint(row_index, frequency, z_real, minus_z_imag))
    if len(points) < 2:
        raise ValueError(f"EIS table has fewer than 2 numeric Z rows: {path}")
    cleaned, ignored = _remove_obvious_outliers(points)
    if len(cleaned) < 2:
        warnings.append("Outlier filtering would leave fewer than two points; raw numeric points were retained.")
        return EisCleaningResult(points, points, [], selected, warnings)
    return EisCleaningResult(points, cleaned, ignored, selected, warnings)


def select_eis_semicircle_main_branch(
    cleaning: EisCleaningResult,
    *,
    ratio_threshold: float = 1.2,
    min_prefix_points: int = 4,
) -> EisCleaningResult:
    """Keep the main semicircle-like branch before the low-frequency offset tail."""
    if len(cleaning.cleaned_points) <= max(min_prefix_points, 4):
        return cleaning
    cutoff_index: int | None = None
    for index, point in enumerate(cleaning.cleaned_points):
        if index < min_prefix_points:
            continue
        denominator = max(point.z_real_ohm, 1e-9)
        if point.minus_z_imag_ohm / denominator > ratio_threshold:
            cutoff_index = index
            break
    if cutoff_index is None or cutoff_index < 4:
        return cleaning
    kept = cleaning.cleaned_points[:cutoff_index]
    tail = cleaning.cleaned_points[cutoff_index:]
    ignored = list(cleaning.ignored_points)
    ignored.extend(
        EisIgnoredPoint(point, "offset_tail_beyond_semicircle_main_branch")
        for point in tail
    )
    warnings = list(cleaning.warnings)
    warnings.append(
        "Low-frequency offset tail was excluded from the strict semicircle main-branch draft fit."
    )
    return EisCleaningResult(
        raw_points=list(cleaning.raw_points),
        cleaned_points=kept,
        ignored_points=ignored,
        selected_columns=dict(cleaning.selected_columns),
        warnings=warnings,
    )


def draft_fit_eis_randles_cpe(points: list[EisPoint], *, fit_points: int = 240) -> EisFitResult:
    fit_points_input = [point for point in points if point.frequency_hz is not None and point.frequency_hz > 0]
    adapter = _draft_fit_with_impedance_adapter(fit_points_input, fit_points=fit_points)
    if adapter is not None:
        return adapter
    if len(fit_points_input) < 4:
        ordered = sorted(points, key=lambda item: item.z_real_ohm)
        return EisFitResult(
            "diagnostic_linear_interpolation_insufficient_frequency_points",
            [(point.z_real_ohm, point.minus_z_imag_ohm) for point in ordered],
            warning="Fewer than 4 cleaned points with positive frequency; Randles-CPE fit not attempted.",
        )
    ordered = sorted(fit_points_input, key=lambda item: float(item.frequency_hz or 0.0), reverse=True)
    freq = np.array([float(point.frequency_hz or 0.0) for point in ordered], dtype=float)
    z_real = np.array([point.z_real_ohm for point in ordered], dtype=float)
    minus_z_imag = np.array([point.minus_z_imag_ohm for point in ordered], dtype=float)
    measured = z_real - 1j * minus_z_imag
    modulus = np.maximum(np.abs(measured), max(float(np.median(np.abs(measured))) * 0.05, 1e-9))
    lower = np.array([1e-12, 1e-12, 1e-12, 0.5], dtype=float)
    upper = _randles_cpe_upper_bounds(z_real, minus_z_imag)
    best = None
    for guess in _randles_cpe_initial_guesses(freq, z_real, minus_z_imag):
        guess = np.minimum(np.maximum(np.array(guess, dtype=float), lower * 1.01), upper * 0.99)
        result = least_squares(
            _randles_cpe_residual,
            guess,
            bounds=(lower, upper),
            args=(freq, measured, modulus),
            loss="soft_l1",
            f_scale=1.0,
            max_nfev=5000,
        )
        if best is None or result.cost < best.cost:
            best = result
    if best is None or not best.success:
        ordered_by_x = sorted(points, key=lambda item: item.z_real_ohm)
        return EisFitResult(
            "diagnostic_linear_interpolation_fallback",
            [(point.z_real_ohm, point.minus_z_imag_ohm) for point in ordered_by_x],
            warning="Randles-CPE least-squares did not converge; fallback curve is diagnostic only.",
        )
    rs, rct, q_value, n_value = [float(value) for value in best.x]
    smooth_min_freq = max(float(freq.min()) * 1e-6, 1e-12)
    smooth_freq = np.logspace(math.log10(float(freq.max())), math.log10(smooth_min_freq), max(fit_points, len(points)))
    fit_complex = randles_cpe_impedance(smooth_freq, rs, rct, q_value, n_value)
    fit_points_xy = [(float(value.real), float(-value.imag)) for value in fit_complex]
    predicted = randles_cpe_impedance(freq, rs, rct, q_value, n_value)
    residual = np.concatenate(((predicted.real - measured.real) / modulus, ((-predicted.imag) - minus_z_imag) / modulus))
    sse = float(np.sum(residual * residual))
    classification = "near-ideal semicircle candidate" if n_value >= 0.95 else "depressed semicircle candidate"
    warning = ""
    if rct >= float(upper[1]) * 0.98:
        warning = "Rct reached the bounded search ceiling; draft fit is under-constrained by the available cleaned branch and requires manual review."
    return EisFitResult(
        "least_squares_randles_cpe",
        fit_points_xy,
        {"Rs": rs, "Rct": rct, "Q": q_value, "n": n_value},
        residual_sse=sse,
        robust_cost=float(best.cost),
        semicircle_classification=classification,
        warning=warning,
    )


def draft_fit_eis_arc(points: list[EisPoint], *, fit_points: int = 240) -> EisFitResult:
    return draft_fit_eis_randles_cpe(points, fit_points=fit_points)


def _draft_fit_with_impedance_adapter(points: list[EisPoint], *, fit_points: int) -> EisFitResult | None:
    if len(points) < 4:
        return None
    from src.adapters import eis_impedance_adapter

    result = eis_impedance_adapter.fit_randles_cpe_candidate(
        [float(point.frequency_hz or 0.0) for point in points],
        [point.z_real_ohm for point in points],
        [point.minus_z_imag_ohm for point in points],
        fit_points=fit_points,
    )
    if not result.get("ok"):
        return None
    return EisFitResult(
        str(result.get("method") or "impedance_custom_circuit_R0_p_R1_CPE1_candidate"),
        [(float(x_value), float(y_value)) for x_value, y_value in result.get("fit_points", [])],
        {str(key): float(value) for key, value in dict(result.get("parameters", {})).items()},
        residual_sse=float(result.get("residual_sse", math.nan)),
        robust_cost=float(result.get("robust_cost", math.nan)),
        semicircle_classification=str(result.get("semicircle_classification") or "manual_review"),
        warning=str(result.get("warning") or ""),
        adapter_provenance=dict(result.get("metadata_provenance", {})),
    )


def randles_cpe_impedance(frequency_hz: np.ndarray | list[float], rs: float, rct: float, q_value: float, n_value: float) -> np.ndarray:
    omega = 2 * np.pi * np.asarray(frequency_hz, dtype=float)
    admittance = (1.0 / rct) + q_value * np.power(1j * omega, n_value)
    return rs + 1.0 / admittance


def write_eis_points_csv(path: Path, points: Iterable[EisPoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_index", "frequency_hz", "z_real_ohm", "minus_z_imag_ohm"])
        writer.writeheader()
        for point in points:
            writer.writerow(point.to_row())


def write_ignored_eis_points_csv(path: Path, points: Iterable[EisIgnoredPoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_index", "frequency_hz", "z_real_ohm", "minus_z_imag_ohm", "reason"],
        )
        writer.writeheader()
        for item in points:
            writer.writerow(item.to_dict())


def write_eis_fit_csv(path: Path, fit: EisFitResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["z_real_ohm", "draft_fit_minus_z_imag_ohm"])
        writer.writerows(fit.points)


def eis_plot_rows(cleaned: list[EisPoint], fit: EisFitResult, *, scale: float = 1.0) -> list[list[float | None]]:
    measured = sorted(cleaned, key=lambda item: (item.z_real_ohm, item.minus_z_imag_ohm))
    fit_points = sorted(fit.points)
    output: list[list[float | None]] = []
    for index in range(max(len(measured), len(fit_points))):
        measured_point = measured[index] if index < len(measured) else None
        fit_point = fit_points[index] if index < len(fit_points) else None
        output.append(
            [
                measured_point.z_real_ohm * scale if measured_point else None,
                measured_point.minus_z_imag_ohm * scale if measured_point else None,
                fit_point[0] * scale if fit_point else None,
                fit_point[1] * scale if fit_point else None,
            ]
        )
    return output


def _remove_obvious_outliers(points: list[EisPoint]) -> tuple[list[EisPoint], list[EisIgnoredPoint]]:
    ignored_by_index: dict[int, str] = {}
    y_values = [point.minus_z_imag_ohm for point in points]
    mostly_positive = sum(1 for value in y_values if value >= 0) >= max(2, int(0.8 * len(y_values)))
    hard_invalid_indexes: set[int] = set()
    for index, point in enumerate(points):
        reason = _hard_invalid_eis_reason(point, mostly_positive)
        if reason:
            _add_ignored_reason(ignored_by_index, point.source_index, reason)
            hard_invalid_indexes.add(index)
    first_tail_index = _first_low_frequency_invalid_index(points, hard_invalid_indexes)
    if first_tail_index is not None:
        for index in range(first_tail_index, len(points)):
            _add_ignored_reason(ignored_by_index, points[index].source_index, "unstable_low_frequency_tail_after_first_invalid")
    step_distances = [
        _distance(points[index - 1], points[index])
        for index in range(1, len(points))
        if math.isfinite(_distance(points[index - 1], points[index]))
    ]
    positive_steps = [value for value in step_distances if value > 0]
    median_step = statistics.median(positive_steps) if positive_steps else 0.0
    jump_threshold = max(median_step * 6.0, 1e-9)
    if jump_threshold > 0 and len(points) >= 5:
        start_index = first_tail_index if first_tail_index is not None else int(len(points) * 0.85)
        for index in range(max(1, start_index), len(points)):
            prev_distance = _distance(points[index - 1], points[index])
            next_distance = _distance(points[index], points[index + 1]) if index < len(points) - 1 else 0.0
            tail_like = first_tail_index is not None or _is_lower_frequency(points[index], points[index - 1]) or index >= int(len(points) * 0.85)
            if prev_distance > jump_threshold and (next_distance > jump_threshold or tail_like):
                _add_ignored_reason(ignored_by_index, points[index].source_index, "large_jump_unstable_low_frequency_tail")
    ignored = [
        EisIgnoredPoint(point, ignored_by_index[point.source_index])
        for point in points
        if point.source_index in ignored_by_index
    ]
    cleaned = [point for point in points if point.source_index not in ignored_by_index]
    return cleaned, ignored


def _randles_cpe_residual(params: np.ndarray, freq: np.ndarray, measured: np.ndarray, modulus: np.ndarray) -> np.ndarray:
    rs, rct, q_value, n_value = params
    predicted = randles_cpe_impedance(freq, float(rs), float(rct), float(q_value), float(n_value))
    real_residual = (predicted.real - measured.real) / modulus
    minus_imag_residual = ((-predicted.imag) - (-measured.imag)) / modulus
    return np.concatenate((real_residual, minus_imag_residual))


def _randles_cpe_upper_bounds(z_real: np.ndarray, minus_z_imag: np.ndarray) -> np.ndarray:
    max_impedance = max(float(np.nanmax(np.abs(z_real))), float(np.nanmax(np.abs(minus_z_imag))), 1.0)
    span = max(float(np.nanmax(z_real) - np.nanmin(z_real)), 1.0)
    return np.array([max_impedance * 2.0, max(span * 10.0, max_impedance * 4.0), 1e3, 1.0], dtype=float)


def _randles_cpe_initial_guesses(freq: np.ndarray, z_real: np.ndarray, minus_z_imag: np.ndarray) -> list[tuple[float, float, float, float]]:
    rs_base = max(float(np.nanmin(z_real)), 1e-6)
    rct_base = max(float(np.nanmax(z_real) - np.nanmin(z_real)), 1e-6)
    peak_index = int(np.nanargmax(minus_z_imag))
    peak_freq = max(float(freq[peak_index]), 1e-6)
    guesses: list[tuple[float, float, float, float]] = []
    for rs_factor in (0.5, 0.9, 1.1):
        for rct_factor in (0.5, 1.0, 2.0, 4.0):
            for n_value in (0.6, 0.8, 0.95, 1.0):
                q_guess = 1.0 / max((rct_base * rct_factor) * (2 * math.pi * peak_freq) ** n_value, 1e-12)
                guesses.append((rs_base * rs_factor, rct_base * rct_factor, q_guess, n_value))
    return guesses


def _is_lower_frequency(point: EisPoint, previous: EisPoint) -> bool:
    if point.frequency_hz is None or previous.frequency_hz is None:
        return False
    return point.frequency_hz < previous.frequency_hz


def _hard_invalid_eis_reason(point: EisPoint, mostly_positive: bool) -> str:
    if point.z_real_ohm < 0:
        return "invalid_negative_z_real_unstable_low_frequency_tail"
    if mostly_positive and point.minus_z_imag_ohm < 0:
        return "sign_flip_negative_minus_z_imag_unstable_low_frequency_tail"
    return ""


def _add_ignored_reason(ignored_by_index: dict[int, str], source_index: int, reason: str) -> None:
    existing = ignored_by_index.get(source_index, "")
    parts = [part for part in existing.split(";") if part]
    if reason not in parts:
        parts.append(reason)
    ignored_by_index[source_index] = ";".join(parts)


def _first_low_frequency_invalid_index(points: list[EisPoint], hard_invalid_indexes: set[int]) -> int | None:
    if not hard_invalid_indexes:
        return None
    low_frequency_floor = max(1, int(len(points) * 0.5))
    candidates = [index for index in sorted(hard_invalid_indexes) if index >= low_frequency_floor]
    return candidates[0] if candidates else None


def _pick_eis_columns(columns: list[str]) -> dict[str, str]:
    frequency = _first_matching(columns, lambda text: "freq" in text)
    z_real = _first_matching(
        columns,
        lambda text: ("z'" in text or "z real" in text or "zreal" in text)
        and "''" not in text
        and "imag" not in text
        and "phase" not in text
        and not text.strip().startswith("-"),
    )
    minus_z_imag = _first_matching(
        columns,
        lambda text: ("-z''" in text or "z''" in text or "imag" in text or "-z" in text)
        and "phase" not in text,
    )
    if z_real is None or minus_z_imag is None:
        numeric = [column for column in columns if column and "phase" not in _normalize(column)]
        if len(numeric) >= 3:
            frequency = frequency or numeric[0]
            z_real = z_real or numeric[1]
            minus_z_imag = minus_z_imag or numeric[2]
    if z_real is None or minus_z_imag is None:
        raise ValueError(f"Could not identify EIS Z columns from headers: {columns}")
    return {"frequency_hz": frequency or "", "z_real_ohm": z_real, "minus_z_imag_ohm": minus_z_imag}


def _first_matching(columns: list[str], predicate) -> str | None:
    for column in columns:
        if predicate(_normalize(column)):
            return column
    return None


def _looks_like_raw_imaginary_column(column: str) -> bool:
    normalized = _normalize(column).strip()
    return (
        not normalized.startswith("-")
        and "-z" not in normalized
        and ("imag" in normalized or normalized.startswith("im") or "z''" in normalized)
    )


def _normalize(value: object) -> str:
    return (
        str(value)
        .casefold()
        .replace("\u03a9".casefold(), "ohm")
        .replace("（", "(")
        .replace("）", ")")
        .replace("\u2032", "'")
        .replace("\u2019", "'")
        .replace("\u2033", "''")
    )


def _to_float(value: object) -> float | None:
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _distance(a: EisPoint, b: EisPoint) -> float:
    return math.hypot(a.z_real_ohm - b.z_real_ohm, a.minus_z_imag_ohm - b.minus_z_imag_ohm)
