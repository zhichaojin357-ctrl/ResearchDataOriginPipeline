from __future__ import annotations

import csv
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.core.table_reader import read_table_with_metadata


@dataclass(frozen=True)
class EisPoint:
    source_index: int
    frequency_hz: float | None
    z_real_ohm: float
    minus_z_imag_ohm: float
    impedance_magnitude_ohm: float | None = None
    phase_deg: float | None = None

    def to_row(self) -> dict[str, float | int | None]:
        return {
            "source_index": self.source_index,
            "frequency_hz": self.frequency_hz,
            "z_real_ohm": self.z_real_ohm,
            "minus_z_imag_ohm": self.minus_z_imag_ohm,
        }


@dataclass(frozen=True)
class EisMeasurementResult:
    points: list[EisPoint]
    selected_columns: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    column_transforms: dict[str, dict[str, object]] = field(default_factory=dict)
    source_format: str | None = None
    format_metadata: dict[str, object] = field(default_factory=dict)
    source_rows: list[dict[str, str]] = field(default_factory=list, repr=False, compare=False)

    def to_metadata(self) -> dict[str, object]:
        magnitude_transform = self.column_transforms.get("impedance_magnitude_ohm", {})
        phase_transform = self.column_transforms.get("phase_deg", {})
        payload = {
            "measured_point_count": len(self.points),
            "selected_columns": dict(self.selected_columns),
            "column_transforms": {
                key: dict(value)
                for key, value in self.column_transforms.items()
            },
            "point_selection_policy": (
                "all parsed measured points retained; no automatic outlier removal "
                "or semicircle-main-branch selection"
            ),
            "magnitude_source": (
                "source_column"
                if magnitude_transform.get("status") == "converted"
                else "derived_from_measured_impedance_components"
            ),
            "phase_source": (
                "source_column"
                if phase_transform.get("status") == "converted"
                else "derived_from_measured_impedance_components"
            ),
            "warnings": list(self.warnings),
        }
        if self.source_format:
            payload["source_format"] = self.source_format
            payload["format_provenance"] = dict(self.format_metadata)
            payload["manual_check_required"] = True
            payload["manual_check_items"] = [
                "Confirm Scribner ZPlotW impedance-unit and imaginary-sign conventions against the instrument export."
            ]
        return payload


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


def read_eis_measurements(path: Path) -> EisMeasurementResult:
    table = read_table_with_metadata(path)
    if not table.rows:
        raise ValueError(f"EIS table has no rows: {path}")
    columns = list(table.rows[0].keys())
    selected = _pick_eis_columns(columns)
    scribner_contract = _scribner_zplotw_impedance_contract(table.source_format, table.format_metadata, selected)
    if scribner_contract is None:
        real_scale, real_unit = _required_impedance_conversion(selected["z_real_ohm"])
        imag_scale, imag_unit = _required_impedance_conversion(selected["minus_z_imag_ohm"])
    else:
        real_scale, real_unit = 1.0, "ohm"
        imag_scale, imag_unit = 1.0, "ohm"
    frequency_conversion = _frequency_conversion_to_hz(selected.get("frequency_hz", ""))
    magnitude_conversion = _impedance_conversion_to_ohm(selected.get("impedance_magnitude_ohm", ""))
    phase_conversion = _phase_conversion_to_deg(selected.get("phase_deg", ""))
    if scribner_contract is None:
        imag_sign, imag_sign_policy, imag_sign_evidence = _imaginary_to_minus_sign(
            selected["minus_z_imag_ohm"],
            rows=table.rows,
            z_real_column=selected["z_real_ohm"],
            phase_column=selected.get("phase_deg", ""),
            real_scale=real_scale,
            imag_scale=imag_scale,
            phase_conversion=phase_conversion,
        )
    else:
        imag_sign = -1.0
        imag_sign_policy = "scribner_zplotw_raw_zdoubleprime_negated_without_absolute_value"
        imag_sign_evidence = {
            "method": "scribner_zplotw_vendor_signature",
            "source_component": "Z''(b)",
            "source_semantics": "raw_imaginary_impedance",
            "selected_sign_multiplier": -1.0,
        }
    points: list[EisPoint] = []
    warnings: list[str] = []
    transforms: dict[str, dict[str, object]] = {
        "z_real_ohm": {
            "source_column": selected["z_real_ohm"],
            "source_unit": real_unit,
            "multiplier_to_ohm": real_scale,
            "status": "converted",
        },
        "minus_z_imag_ohm": {
            "source_column": selected["minus_z_imag_ohm"],
            "source_unit": imag_unit,
            "unit_multiplier_to_ohm": imag_scale,
            "sign_multiplier_to_minus_imaginary": imag_sign,
            "imaginary_sign_convention": imag_sign_policy,
            "sign_evidence": imag_sign_evidence,
            "status": "converted",
        },
    }
    if scribner_contract is not None:
        vendor_unit_provenance = {
            "unit_evidence": "inferred_from_scribner_zplotw_vendor_signature",
            "vendor_signature_inference": True,
            "manual_check_required": True,
        }
        transforms["z_real_ohm"].update(vendor_unit_provenance)
        transforms["minus_z_imag_ohm"].update(vendor_unit_provenance)
        warnings.append(
            "Scribner ZPlotW vendor signature supplied ohm units and raw Z'' sign semantics; confirm them against the instrument export."
        )
    _record_optional_transform(
        transforms,
        warnings,
        canonical_name="frequency_hz",
        source_column=selected.get("frequency_hz", ""),
        conversion=frequency_conversion,
        multiplier_key="multiplier_to_hz",
        unknown_message="EIS frequency column unit was not explicit; frequency values were omitted rather than labeled as Hz.",
    )
    _record_optional_transform(
        transforms,
        warnings,
        canonical_name="impedance_magnitude_ohm",
        source_column=selected.get("impedance_magnitude_ohm", ""),
        conversion=magnitude_conversion,
        multiplier_key="multiplier_to_ohm",
        unknown_message=(
            "EIS impedance-magnitude column unit was not explicit; magnitude was derived "
            "from the converted real and imaginary components."
        ),
    )
    _record_optional_transform(
        transforms,
        warnings,
        canonical_name="phase_deg",
        source_column=selected.get("phase_deg", ""),
        conversion=phase_conversion,
        multiplier_key="multiplier_to_deg",
        unknown_message=(
            "EIS phase column unit was not explicit; phase was derived from the converted "
            "real and imaginary components."
        ),
    )
    for row_index, row in enumerate(table.rows, start=1):
        z_real = _to_float(row.get(selected["z_real_ohm"], ""))
        minus_z_imag = _to_float(row.get(selected["minus_z_imag_ohm"], ""))
        if z_real is None or minus_z_imag is None:
            continue
        z_real *= real_scale
        minus_z_imag *= imag_scale * imag_sign
        frequency = _converted_optional_value(
            row,
            selected.get("frequency_hz", ""),
            frequency_conversion,
        )
        if frequency is not None and frequency <= 0:
            frequency = None
            _append_once(
                warnings,
                "Non-positive EIS frequency values were omitted from Bode-ready output.",
            )
        magnitude = (
            _converted_optional_value(
                row,
                selected.get("impedance_magnitude_ohm", ""),
                magnitude_conversion,
            )
        )
        if magnitude is None or magnitude < 0:
            if magnitude is not None and magnitude < 0:
                _append_once(
                    warnings,
                    "Negative EIS impedance-magnitude values were ignored and derived from the impedance components.",
                )
            magnitude = math.hypot(z_real, minus_z_imag)
        phase = _converted_optional_value(
            row,
            selected.get("phase_deg", ""),
            phase_conversion,
        )
        if phase is None:
            phase = math.degrees(math.atan2(-minus_z_imag, z_real))
        points.append(
            EisPoint(
                row_index,
                frequency,
                z_real,
                minus_z_imag,
                impedance_magnitude_ohm=magnitude,
                phase_deg=phase,
            )
        )
    if len(points) < 2:
        raise ValueError(f"EIS table has fewer than 2 numeric Z rows: {path}")
    return EisMeasurementResult(
        points=points,
        selected_columns=selected,
        warnings=warnings,
        column_transforms=transforms,
        source_format=table.source_format if scribner_contract is not None else None,
        format_metadata=dict(table.format_metadata or {}) if scribner_contract is not None else {},
        source_rows=table.rows,
    )


def clean_eis_file(path: Path) -> EisCleaningResult:
    measurement = read_eis_measurements(path)
    points = measurement.points
    cleaned, ignored = _remove_obvious_outliers(points)
    if len(cleaned) < 2:
        warnings = list(measurement.warnings)
        warnings.append("Outlier filtering would leave fewer than two points; raw numeric points were retained.")
        return EisCleaningResult(points, points, [], measurement.selected_columns, warnings)
    return EisCleaningResult(
        points,
        cleaned,
        ignored,
        measurement.selected_columns,
        list(measurement.warnings),
    )


def _scribner_zplotw_impedance_contract(
    source_format: str | None,
    format_metadata: dict[str, object] | None,
    selected_columns: dict[str, str],
) -> dict[str, object] | None:
    """Accept implied units only from the complete Scribner ZPlotW parser signature."""
    if source_format != "scribner_zplotw_impedance" or not format_metadata:
        return None
    if format_metadata.get("vendor") != "Scribner":
        return None
    if format_metadata.get("vendor_signature") != "ZPlotW Data File + Freq(Hz) + Z'(a) + Z''(b)":
        return None
    if list(format_metadata.get("signature_headers", [])) != ["Freq(Hz)", "Z'(a)", "Z''(b)"]:
        return None
    if (
        selected_columns.get("frequency_hz") != "Freq(Hz)"
        or selected_columns.get("z_real_ohm") != "Z'(a)"
        or selected_columns.get("minus_z_imag_ohm") != "Z''(b)"
    ):
        return None
    return {
        "unit": "ohm",
        "imaginary_component": "raw_imaginary_impedance",
    }


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
    import numpy as np
    from scipy.optimize import least_squares

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


def randles_cpe_impedance(
    frequency_hz: Iterable[float],
    rs: float,
    rct: float,
    q_value: float,
    n_value: float,
) -> Any:
    import numpy as np

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


def eis_measured_plot_rows(points: Iterable[EisPoint], *, scale: float = 1.0) -> list[list[float | None]]:
    """Return source-order measured Nyquist coordinates plus Bode-ready columns."""
    output: list[list[float | None]] = []
    for point in points:
        magnitude = point.impedance_magnitude_ohm
        if magnitude is None:
            magnitude = math.hypot(point.z_real_ohm, point.minus_z_imag_ohm)
        phase = point.phase_deg
        if phase is None:
            phase = math.degrees(math.atan2(-point.minus_z_imag_ohm, point.z_real_ohm))
        output.append(
            [
                point.z_real_ohm * scale,
                point.minus_z_imag_ohm * scale,
                point.frequency_hz,
                magnitude * scale,
                phase,
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


def _randles_cpe_residual(params: Any, freq: Any, measured: Any, modulus: Any) -> Any:
    import numpy as np

    rs, rct, q_value, n_value = params
    predicted = randles_cpe_impedance(freq, float(rs), float(rct), float(q_value), float(n_value))
    real_residual = (predicted.real - measured.real) / modulus
    minus_imag_residual = ((-predicted.imag) - (-measured.imag)) / modulus
    return np.concatenate((real_residual, minus_imag_residual))


def _randles_cpe_upper_bounds(z_real: Any, minus_z_imag: Any) -> Any:
    import numpy as np

    max_impedance = max(float(np.nanmax(np.abs(z_real))), float(np.nanmax(np.abs(minus_z_imag))), 1.0)
    span = max(float(np.nanmax(z_real) - np.nanmin(z_real)), 1.0)
    return np.array([max_impedance * 2.0, max(span * 10.0, max_impedance * 4.0), 1e3, 1.0], dtype=float)


def _randles_cpe_initial_guesses(
    freq: Any,
    z_real: Any,
    minus_z_imag: Any,
) -> list[tuple[float, float, float, float]]:
    import numpy as np

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
    frequency = _first_matching(
        columns,
        lambda text: (
            "freq" in text
            or "angular frequency" in text
            or "omega" in text
            or "ω" in text
        ),
    )
    z_real = _first_matching(
        columns,
        lambda text: (
            "z'" in text
            or "z real" in text
            or "zreal" in text
            or "re(z)" in text
            or "real(z)" in text
        )
        and "''" not in text
        and "imag" not in text
        and "phase" not in text
        and not text.strip().startswith("-"),
    )
    minus_z_imag = _first_matching(
        columns,
        lambda text: (
            "-z''" in text
            or "z''" in text
            or "imag" in text
            or "im(z)" in text
            or "zimag" in text
            or "-z" in text
        )
        and "phase" not in text,
    )
    impedance_magnitude = _first_matching(
        columns,
        lambda text: "|z|" in text or "modulus" in text or "magnitude" in text or "zmod" in text,
    )
    phase = _first_matching(columns, lambda text: "phase" in text)
    if z_real is None or minus_z_imag is None:
        raise ValueError(f"Could not identify EIS Z columns from headers: {columns}")
    return {
        "frequency_hz": frequency or "",
        "z_real_ohm": z_real,
        "minus_z_imag_ohm": minus_z_imag,
        "impedance_magnitude_ohm": impedance_magnitude or "",
        "phase_deg": phase or "",
    }


def _first_matching(columns: list[str], predicate) -> str | None:
    for column in columns:
        if predicate(_normalize(column)):
            return column
    return None


def _imaginary_to_minus_sign(
    column: str,
    *,
    rows: list[dict[str, object]],
    z_real_column: str,
    phase_column: str,
    real_scale: float,
    imag_scale: float,
    phase_conversion: tuple[float, str] | None,
) -> tuple[float, str, dict[str, object]]:
    normalized = _normalize(column).strip()
    explicitly_negative = (
        normalized.startswith("-")
        or "-im" in normalized
        or "-z''" in normalized
        or "minus" in normalized
        or "negative imag" in normalized
        or "neg imag" in normalized
    )
    if explicitly_negative:
        return (
            1.0,
            "source_is_minus_imaginary_preserve_signed_values",
            {"method": "explicit_header_prefix"},
        )
    if (
        "imag" in normalized
        or normalized.startswith("im")
        or "im(z)" in normalized
    ):
        return (
            -1.0,
            "source_is_raw_imaginary_negated_without_absolute_value",
            {"method": "explicit_raw_imaginary_header"},
        )
    if "z''" in normalized:
        sign, evidence = _resolve_ambiguous_z_double_prime_sign(
            rows,
            z_real_column=z_real_column,
            z_double_prime_column=column,
            phase_column=phase_column,
            real_scale=real_scale,
            imag_scale=imag_scale,
            phase_conversion=phase_conversion,
        )
        return (
            sign,
            "ambiguous_z_double_prime_resolved_from_phase_consistency",
            evidence,
        )
    raise ValueError(f"Could not determine EIS imaginary sign convention from header: {column!r}")


def _resolve_ambiguous_z_double_prime_sign(
    rows: list[dict[str, object]],
    *,
    z_real_column: str,
    z_double_prime_column: str,
    phase_column: str,
    real_scale: float,
    imag_scale: float,
    phase_conversion: tuple[float, str] | None,
) -> tuple[float, dict[str, object]]:
    if not phase_column or phase_conversion is None:
        raise ValueError(
            "Bare EIS Z''/Z\" headers are sign-ambiguous. Supply an explicit Im(Z) or -Z'' "
            "header, or an explicit-unit phase column for consistency resolution."
        )
    deltas: dict[float, list[float]] = {1.0: [], -1.0: []}
    for row in rows:
        z_real = _to_float(row.get(z_real_column, ""))
        z_double_prime = _to_float(row.get(z_double_prime_column, ""))
        phase = _converted_optional_value(row, phase_column, phase_conversion)
        if z_real is None or z_double_prime is None or phase is None:
            continue
        z_real *= real_scale
        z_double_prime *= imag_scale
        for sign in (1.0, -1.0):
            minus_imag = z_double_prime * sign
            predicted_phase = math.degrees(math.atan2(-minus_imag, z_real))
            deltas[sign].append(_angular_difference_deg(predicted_phase, phase))
    if min(len(values) for values in deltas.values()) < 2:
        raise ValueError(
            "Bare EIS Z''/Z\" sign could not be resolved: fewer than two rows have "
            "numeric real, imaginary, and explicit-unit phase values."
        )
    median_deltas = {
        sign: statistics.median(values)
        for sign, values in deltas.items()
    }
    ranked = sorted(median_deltas.items(), key=lambda item: item[1])
    best_sign, best_delta = ranked[0]
    second_delta = ranked[1][1]
    if best_delta > 20.0 or second_delta - best_delta < 10.0:
        raise ValueError(
            "Bare EIS Z''/Z\" sign remains ambiguous after phase-consistency checking: "
            f"median phase deltas are preserve={median_deltas[1.0]:.3f} deg and "
            f"negate={median_deltas[-1.0]:.3f} deg."
        )
    return best_sign, {
        "method": "phase_consistency",
        "rows_compared": len(deltas[best_sign]),
        "median_phase_delta_deg_if_preserved": median_deltas[1.0],
        "median_phase_delta_deg_if_negated": median_deltas[-1.0],
        "selected_sign_multiplier": best_sign,
    }


def _angular_difference_deg(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _required_impedance_conversion(column: str) -> tuple[float, str]:
    conversion = _impedance_conversion_to_ohm(column)
    if conversion is None:
        raise ValueError(
            "EIS impedance unit must be explicit in the real and imaginary column headers "
            f"(supported: ohm/Ω, kOhm/kΩ, MOhm/MΩ, mOhm/mΩ): {column!r}"
        )
    return conversion


def _impedance_conversion_to_ohm(column: str) -> tuple[float, str] | None:
    text = str(column).strip()
    if not text:
        return None
    compact = re.sub(r"[\s_\[\](){}]+", "", text)
    if re.search(r"(?:MΩ|M[Oo]hm)", compact):
        return 1_000_000.0, "MOhm"
    if re.search(r"(?:kΩ|[kK][Oo]hm)", compact):
        return 1_000.0, "kOhm"
    if re.search(r"(?:mΩ|m[Oo]hm)", compact):
        return 0.001, "mOhm"
    normalized = _normalize(text)
    if "ohm" in normalized or "Ω" in text:
        return 1.0, "ohm"
    return None


def _frequency_conversion_to_hz(column: str) -> tuple[float, str] | None:
    text = str(column).strip()
    if not text:
        return None
    compact = re.sub(r"[\s_\[\](){}]+", "", text)
    normalized = _normalize(text).replace(" ", "")
    if "rad/s" in normalized or "rads-1" in normalized or "rads^-1" in normalized:
        return 1.0 / (2.0 * math.pi), "rad/s"
    if re.search(r"(?:MHz)", compact):
        return 1_000_000.0, "MHz"
    if re.search(r"(?:kHz|KHz|KHZ)", compact):
        return 1_000.0, "kHz"
    if re.search(r"(?:mHz)", compact):
        return 0.001, "mHz"
    if re.search(r"(?:Hz|HZ|hz)", compact):
        return 1.0, "Hz"
    return None


def _phase_conversion_to_deg(column: str) -> tuple[float, str] | None:
    text = str(column).strip()
    if not text:
        return None
    normalized = _normalize(text)
    if "degree" in normalized or "deg" in normalized or "°" in text:
        return 1.0, "deg"
    if "rad" in normalized:
        return 180.0 / math.pi, "rad"
    return None


def _record_optional_transform(
    transforms: dict[str, dict[str, object]],
    warnings: list[str],
    *,
    canonical_name: str,
    source_column: str,
    conversion: tuple[float, str] | None,
    multiplier_key: str,
    unknown_message: str,
) -> None:
    if not source_column:
        transforms[canonical_name] = {
            "source_column": "",
            "status": "derived_or_unavailable",
        }
        return
    if conversion is None:
        transforms[canonical_name] = {
            "source_column": source_column,
            "status": "ignored_unknown_unit",
        }
        _append_once(warnings, unknown_message)
        return
    multiplier, source_unit = conversion
    transforms[canonical_name] = {
        "source_column": source_column,
        "source_unit": source_unit,
        multiplier_key: multiplier,
        "status": "converted",
    }


def _converted_optional_value(
    row: dict[str, object],
    source_column: str,
    conversion: tuple[float, str] | None,
) -> float | None:
    if not source_column or conversion is None:
        return None
    value = _to_float(row.get(source_column, ""))
    return value * conversion[0] if value is not None else None


def _append_once(values: list[str], message: str) -> None:
    if message not in values:
        values.append(message)


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
        .replace("\u2212", "-")
        .replace("\u207b", "-")
        .replace("\u00b7", "")
        .replace('"', "''")
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
