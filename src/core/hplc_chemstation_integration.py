from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

from src.core.hplc_peak_integration import _validate_signal


CHEMSTATION_COMPATIBLE_INTEGRATOR_NAME = (
    "chemstation-compatible-hplc-integrator-candidate"
)
CHEMSTATION_COMPATIBLE_INTEGRATOR_VERSION = "0.4.0"


def integrate_chemstation_compatible(
    time_min: np.ndarray | list[float],
    signal_mau: np.ndarray | list[float],
    config: Mapping[str, Any],
    *,
    method_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Integrate a chromatogram using documented ChemStation state semantics.

    This is an independent, auditable implementation of the behavior published
    in Agilent's OpenLab CDS Data Analysis Reference Guide. It does not contain
    vendor code. The guide publishes derivative-filter spans and accumulator
    weights, but not the exact production filter coefficients; this candidate
    therefore uses block-mean finite differences and records that limitation.
    """
    fallback_policy = config.get("chemstation_compatible_integration", {})
    policy = {**fallback_policy, **dict(method_policy or {})}
    required_policy = (
        "initial_peak_width_min",
        "slope_sensitivity",
        "height_reject_mau",
        "area_reject_mau_s",
        "peak_to_valley_ratio",
        "baseline_correction",
        "tangent_skim_mode",
    )
    missing_policy = [key for key in required_policy if key not in policy]
    if missing_policy:
        raise ValueError(
            "ChemStation-compatible integration policy is missing: "
            + ", ".join(missing_policy)
        )
    _validate_supported_method_policy(policy)
    time = np.asarray(time_min, dtype=np.float64).reshape(-1)
    signal = np.asarray(signal_mau, dtype=np.float64).reshape(-1)
    _validate_signal(time, signal)

    sampling_interval_min = float(np.median(np.diff(time)))
    expected_peak_width_min = float(policy["initial_peak_width_min"])
    slope_sensitivity = float(policy["slope_sensitivity"])
    minimum_height = float(policy["height_reject_mau"])
    minimum_area = float(policy["area_reject_mau_s"])
    peak_to_valley_ratio = float(policy["peak_to_valley_ratio"])

    baseline_trace = np.full(signal.shape, np.nan, dtype=np.float64)
    baseline_level = float(signal[0])
    baseline_trace[0] = baseline_level
    baseline_points: list[int] = [0]
    last_baseline_index = 0
    candidate_start_index = 0
    up_accumulator = 0
    down_accumulator = 0
    cluster_start_index: int | None = None
    possible_end = False
    clusters: list[dict[str, Any]] = []
    cluster_apices: list[int] = []
    previous_slope: float | None = None
    filter_usage = {"filter_1": 0, "filter_2": 0, "filter_3": 0}
    bunching_usage: dict[int, int] = {}

    for index in range(1, len(signal)):
        expected_points = max(
            1,
            int(round(expected_peak_width_min / sampling_interval_min)),
        )
        filter_number, bunching_power = _recognition_filter(expected_points)
        filter_usage[f"filter_{filter_number}"] += 1
        bunching_usage[bunching_power] = bunching_usage.get(bunching_power, 0) + 1
        derivative = _derivative_outputs(
            time,
            signal,
            index,
            filter_number=filter_number,
            bunching_power=bunching_power,
            expected_peak_width_min=expected_peak_width_min,
            scaling=str(policy.get("recognition_scaling", "peak_width_normalized")),
        )
        if derivative is None:
            baseline_trace[index] = baseline_level
            continue
        slope, curvature = derivative

        previous_up = up_accumulator
        up_accumulator = max(
            0,
            up_accumulator
            + _upslope_increment(
                slope,
                curvature,
                slope_sensitivity,
                filter_number,
            ),
        )
        down_accumulator = max(
            0,
            down_accumulator
            + _downslope_increment(
                slope,
                curvature,
                slope_sensitivity,
                filter_number,
            ),
        )

        within_baseline_envelope = (
            abs(slope) <= slope_sensitivity
            and abs(curvature) <= slope_sensitivity
        )
        if cluster_start_index is None:
            if within_baseline_envelope:
                baseline_points.append(index)
                expected_points = max(1, expected_points)
                window_start = max(0, index - 2 * expected_points + 1)
                accepted = [
                    point for point in baseline_points if point >= window_start
                ]
                if accepted:
                    baseline_level = float(np.mean(signal[accepted]))
                last_baseline_index = index
            baseline_trace[index] = baseline_level
            if previous_up == 0 and up_accumulator > 0:
                candidate_start_index = last_baseline_index
            if up_accumulator >= 15:
                cluster_start_index = candidate_start_index
                cluster_apices = []
                previous_slope = slope
                possible_end = False
                down_accumulator = 0
        else:
            baseline_trace[index] = baseline_level
            if previous_slope is not None and previous_slope > 0.0 >= slope:
                lookback = max(expected_points, 3)
                search_start = max(cluster_start_index, index - lookback)
                apex = search_start + int(
                    np.argmax(signal[search_start : index + 1])
                )
                if not cluster_apices or apex != cluster_apices[-1]:
                    cluster_apices.append(apex)
            previous_slope = slope
            if down_accumulator >= 15:
                possible_end = True
            stable_baseline = _stable_baseline_window_surrogate(
                signal,
                index,
                expected_points,
                slope_sensitivity,
                baseline_level,
            )
            stable_after_apex = bool(
                cluster_apices
                and index - cluster_apices[-1] >= max(2, expected_points)
            )
            if (possible_end and within_baseline_envelope) or (
                stable_after_apex and stable_baseline
            ):
                end_reason = (
                    "documented_down_accumulator_and_envelope"
                    if possible_end and within_baseline_envelope
                    else "surrogate_stable_return_to_baseline"
                )
                end_index = (
                    max(cluster_apices[-1] + 1, index - expected_points + 1)
                    if stable_after_apex and stable_baseline
                    else index
                )
                if end_index > cluster_start_index:
                    clusters.append(
                        {
                            "begin": cluster_start_index,
                            "end": end_index,
                            "apices": cluster_apices,
                            "peak_width_min": expected_peak_width_min,
                            "end_reason": end_reason,
                        }
                    )
                    width = _cluster_width_estimate(
                        time,
                        signal,
                        cluster_start_index,
                        end_index,
                    )
                    if math.isfinite(width) and width > 0:
                        expected_peak_width_min = (
                            0.75 * expected_peak_width_min + 0.25 * width
                        )
                cluster_start_index = None
                possible_end = False
                up_accumulator = 0
                down_accumulator = 0
                baseline_points = [index]
                last_baseline_index = index
                candidate_start_index = index
                baseline_level = float(signal[index])
                baseline_trace[index] = baseline_level
                baseline_trace[end_index] = min(
                    float(baseline_trace[end_index]),
                    float(signal[end_index]),
                )
                previous_slope = None

    if cluster_start_index is not None and len(signal) - cluster_start_index >= 3:
        clusters.append(
            {
                "begin": cluster_start_index,
                "end": len(signal) - 1,
                "apices": cluster_apices,
                "peak_width_min": expected_peak_width_min,
                "end_reason": "end_of_signal",
            }
        )

    peaks: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    cluster_count = 0
    for cluster in _merge_overlapping_clusters(clusters):
        cluster_start = int(cluster["begin"])
        cluster_end = int(cluster["end"])
        cluster_peaks, cluster_rejected = _evaluate_cluster(
            time,
            signal,
            baseline_trace,
            cluster_start,
            cluster_end,
            initial_peak_width_min=float(cluster["peak_width_min"]),
            minimum_height=minimum_height,
            minimum_area=minimum_area,
            peak_to_valley_ratio=peak_to_valley_ratio,
            candidate_apices=list(cluster["apices"]),
        )
        if cluster_peaks:
            cluster_count += 1
            cluster_id = f"CS-C{cluster_count:03d}"
            for position, peak in enumerate(cluster_peaks, start=1):
                peak["baseline_cluster_id"] = cluster_id
                peak["baseline_cluster_size"] = len(cluster_peaks)
                peak["baseline_cluster_position"] = position
                peak["baseline_model_uncertain"] = True
                peak["manual_check_required"] = True
                peak["cluster_end_reason"] = str(cluster["end_reason"])
                peaks.append(peak)
        rejected.extend(cluster_rejected)

    peaks.sort(key=lambda peak: (peak["retention_time_min"], peak["apex_index"]))
    area_percent_reject = float(policy.get("area_percent_reject", 0.0))
    if area_percent_reject > 0.0 and peaks:
        total_area = sum(max(float(peak["area"]), 0.0) for peak in peaks)
        retained: list[dict[str, Any]] = []
        for peak in peaks:
            area_percent = (
                float(peak["area"]) / total_area * 100.0 if total_area > 0 else 0.0
            )
            if area_percent + 1e-12 < area_percent_reject:
                rejected.append(
                    {
                        "retention_time_min": peak["retention_time_min"],
                        "candidate_area_mau_s": peak["area"],
                        "candidate_area_percent": area_percent,
                        "reason": "PMX AreaPercentReject",
                        "manual_check_required": True,
                    }
                )
            else:
                retained.append(peak)
        peaks = retained
    for ordinal, peak in enumerate(peaks, start=1):
        peak["peak_ordinal"] = ordinal

    return {
        "integrator_name": CHEMSTATION_COMPATIBLE_INTEGRATOR_NAME,
        "integrator_version": CHEMSTATION_COMPATIBLE_INTEGRATOR_VERSION,
        "status": "OK",
        "validation_status": "candidate",
        "vendor_equivalent": False,
        "sampling_interval_s": sampling_interval_min * 60.0,
        "documented_method": {
            "slope_sensitivity": slope_sensitivity,
            "initial_peak_width_min": float(policy["initial_peak_width_min"]),
            "area_reject_mau_s": minimum_area,
            "height_reject_mau": minimum_height,
            "baseline_correction": str(policy["baseline_correction"]),
            "peak_to_valley_ratio": peak_to_valley_ratio,
            "tangent_skim_mode": str(policy["tangent_skim_mode"]),
            "front_skim_height_ratio": float(
                policy.get("front_skim_height_ratio", 0.0)
            ),
            "tail_skim_height_ratio": float(
                policy.get("tail_skim_height_ratio", 0.0)
            ),
            "skim_valley_ratio": float(policy.get("skim_valley_ratio", 0.0)),
            "shoulders_mode": str(policy.get("shoulders_mode", "OFF")),
            "area_percent_reject": area_percent_reject,
            "timed_events": list(policy.get("timed_events", [])),
            "signal_specific_events": list(
                policy.get("signal_specific_events", [])
            ),
        },
        "method_source": dict(policy.get("method_source", {"kind": "config_fallback"})),
        "filter_model": (
            "causal block-mean finite differences; document-driven candidate "
            f"approximation ({policy.get('recognition_scaling', 'peak_width_normalized')})"
        ),
        "recognition_scaling": str(
            policy.get("recognition_scaling", "peak_width_normalized")
        ),
        "preprocessing_policy": {
            "smoothing": dict(policy.get("smoothing", {})),
            "blank_subtraction": dict(policy.get("blank_subtraction", {})),
            "quantification_normalization": dict(
                policy.get("quantification_normalization", {})
            ),
            "shoulder_detection_applied": False,
            "tangent_skim_applied": False,
        },
        "filter_usage": filter_usage,
        "bunching_usage": bunching_usage,
        "cluster_end_reasons": {
            reason: sum(
                str(cluster["end_reason"]) == reason
                for cluster in _merge_overlapping_clusters(clusters)
            )
            for reason in sorted(
                {str(cluster["end_reason"]) for cluster in clusters}
            )
        },
        "peak_cluster_count": cluster_count,
        "peak_count": len(peaks),
        "peaks": peaks,
        "rejected_candidates": rejected,
        "manual_check_required": True,
    }


def _validate_supported_method_policy(policy: Mapping[str, Any]) -> None:
    numeric_rules = {
        "slope_sensitivity": (0.0, None, False),
        "initial_peak_width_min": (0.0, None, False),
        "area_reject_mau_s": (0.0, None, True),
        "height_reject_mau": (0.0, None, True),
        "area_percent_reject": (0.0, 100.0, True),
        "peak_to_valley_ratio": (0.0, None, False),
        "front_skim_height_ratio": (0.0, None, True),
        "tail_skim_height_ratio": (0.0, None, True),
        "skim_valley_ratio": (0.0, None, True),
    }
    for key, (minimum, maximum, inclusive_minimum) in numeric_rules.items():
        value = float(policy.get(key, 0.0))
        invalid_minimum = value < minimum if inclusive_minimum else value <= minimum
        if (
            not math.isfinite(value)
            or invalid_minimum
            or (maximum is not None and value > maximum)
        ):
            raise ValueError(f"invalid ChemStation-compatible policy value {key}={value}")
    baseline_mode = str(policy.get("baseline_correction", "")).strip().casefold()
    if baseline_mode != "advanced":
        raise NotImplementedError(
            f"unsupported PMX baseline correction in candidate: {baseline_mode}"
        )
    skim_mode = str(policy.get("tangent_skim_mode", "")).strip().casefold()
    if skim_mode != "standard":
        raise NotImplementedError(
            f"unsupported PMX tangent skim mode in candidate: {skim_mode}"
        )
    shoulders = str(policy.get("shoulders_mode", "OFF")).strip().casefold()
    if shoulders not in {"off", "false", "0"}:
        raise NotImplementedError(
            "ChemStation-compatible candidate does not implement enabled shoulders"
        )
    if (
        float(policy.get("front_skim_height_ratio", 0.0)) > 0.0
        or float(policy.get("tail_skim_height_ratio", 0.0)) > 0.0
    ):
        raise NotImplementedError(
            "ChemStation-compatible candidate does not implement enabled tangent skim"
        )
    if policy.get("timed_events"):
        raise NotImplementedError(
            "ChemStation-compatible candidate does not yet apply timed events"
        )
    if policy.get("signal_specific_events"):
        raise NotImplementedError(
            "ChemStation-compatible candidate does not yet apply signal-specific events"
        )
    smoothing = policy.get("smoothing", {})
    algorithm = str(
        smoothing.get("SmoothingAlgorithm", "None")
        if isinstance(smoothing, Mapping)
        else "None"
    ).strip().casefold()
    if algorithm not in {"", "none"}:
        raise NotImplementedError(
            f"unsupported PMX signal smoothing in candidate: {algorithm}"
        )
    blank = policy.get("blank_subtraction", {})
    blank_target = str(
        blank.get("BlankSubtractionTarget", "None")
        if isinstance(blank, Mapping)
        else "None"
    ).strip().casefold()
    if blank_target not in {"", "none"}:
        raise NotImplementedError(
            f"unsupported PMX blank subtraction in candidate: {blank_target}"
        )


def _stable_baseline_window_surrogate(
    signal: np.ndarray,
    index: int,
    expected_points: int,
    sensitivity: float,
    baseline_level: float,
) -> bool:
    """Unpublished response-amplitude surrogate for stable baseline re-entry.

    The exact ChemStation baseline-cone normalization is not disclosed.  This
    branch is therefore recorded separately from accumulator-confirmed ends.
    """
    width = max(3, int(expected_points))
    if index + 1 < width:
        return False
    window = signal[index + 1 - width : index + 1]
    center = float(np.mean(window))
    return bool(
        np.max(np.abs(window - center)) <= sensitivity
        and abs(center - baseline_level) <= sensitivity
    )


def _recognition_filter(expected_peak_width_points: int) -> tuple[int, int]:
    """Map expected peak width to the published filter/bunching table."""
    points = max(1, int(expected_peak_width_points))
    if points < 8:
        return 1, 0
    if points < 12:
        return 2, 0
    if points <= 24:
        return 3, 0
    if points <= 48:
        return 3, 1
    if points <= 96:
        return 3, 2
    if points <= 192:
        return 3, 3
    bunching_power = 3
    while math.ceil(points / (2**bunching_power)) > 24:
        bunching_power += 1
    return 3, bunching_power


def _derivative_outputs(
    time: np.ndarray,
    signal: np.ndarray,
    index: int,
    *,
    filter_number: int,
    bunching_power: int,
    expected_peak_width_min: float,
    scaling: str,
) -> tuple[float, float] | None:
    block = 2**bunching_power
    slope_blocks = {1: 1, 2: 2, 3: 4}[filter_number]
    spacing_blocks = {1: 1, 2: 2, 3: 4}[filter_number]
    required = max(
        2 * slope_blocks * block,
        (2 * spacing_blocks + 1) * block,
    )
    if index + 1 < required:
        return None

    recent_start = index + 1 - slope_blocks * block
    older_start = recent_start - slope_blocks * block
    recent = float(np.mean(signal[recent_start : index + 1]))
    older = float(np.mean(signal[older_start:recent_start]))
    recent_center = float(np.mean(time[recent_start : index + 1]))
    older_center = float(np.mean(time[older_start:recent_start]))
    response_difference = recent - older

    spacing = spacing_blocks * block
    current_slice = signal[index + 1 - block : index + 1]
    middle_end = index + 1 - spacing
    middle_slice = signal[middle_end - block : middle_end]
    older_end = index + 1 - 2 * spacing
    older_slice = signal[older_end - block : older_end]
    if not len(current_slice) or not len(middle_slice) or not len(older_slice):
        return None
    current = float(np.mean(current_slice))
    middle = float(np.mean(middle_slice))
    old = float(np.mean(older_slice))
    current_time = float(np.mean(time[index + 1 - block : index + 1]))
    middle_time = float(np.mean(time[middle_end - block : middle_end]))
    second_difference = (current - middle) - (middle - old)
    if scaling == "response_difference":
        slope = response_difference
        curvature = second_difference
    elif scaling == "peak_width_normalized":
        slope = response_difference / max(recent_center - older_center, 1e-15)
        slope *= expected_peak_width_min
        curvature = second_difference / max(
            (current_time - middle_time) ** 2,
            1e-15,
        )
        curvature *= expected_peak_width_min**2
    else:
        raise ValueError(f"unknown recognition_scaling: {scaling}")
    return slope, curvature


def _upslope_increment(
    slope: float,
    curvature: float,
    sensitivity: float,
    filter_number: int,
) -> int:
    positive = {1: 8, 2: 5, 3: 3}[filter_number]
    flat = {1: 4, 2: 2, 3: 1}[filter_number]
    curve = {1: 0, 2: 2, 3: 1}[filter_number]
    value = positive if slope > sensitivity else -positive if slope < -sensitivity else -flat
    if curvature > sensitivity:
        value += curve
    elif curvature < -sensitivity:
        value -= curve
    return value


def _downslope_increment(
    slope: float,
    curvature: float,
    sensitivity: float,
    filter_number: int,
) -> int:
    negative = {1: 8, 2: 5, 3: 3}[filter_number]
    opposing = {1: 11, 2: 7, 3: 4}[filter_number]
    flat = {1: 28, 2: 18, 3: 11}[filter_number]
    curve = {1: 0, 2: 2, 3: 1}[filter_number]
    value = negative if slope < -sensitivity else -opposing if slope > sensitivity else -flat
    if curvature < -sensitivity:
        value += curve
    elif curvature > sensitivity:
        value -= curve
    return value


def _cluster_width_estimate(
    time: np.ndarray,
    signal: np.ndarray,
    begin_index: int,
    end_index: int,
) -> float:
    segment_time = time[begin_index : end_index + 1]
    segment_signal = signal[begin_index : end_index + 1]
    if len(segment_time) < 3:
        return math.nan
    line = np.interp(
        segment_time,
        (segment_time[0], segment_time[-1]),
        (segment_signal[0], segment_signal[-1]),
    )
    corrected = np.maximum(segment_signal - line, 0.0)
    height = float(np.max(corrected))
    if height <= 0:
        return math.nan
    area_min = float(np.trapezoid(corrected, segment_time))
    area_height_width = area_min / height
    apex = int(np.argmax(corrected))
    left = apex
    right = apex
    half_height = height / 2.0
    while left > 0 and corrected[left] > half_height:
        left -= 1
    while right < len(corrected) - 1 and corrected[right] > half_height:
        right += 1
    inflection_width = float(segment_time[right] - segment_time[left])
    return 0.3 * inflection_width + 0.7 * area_height_width


def _merge_overlapping_clusters(
    clusters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for cluster in sorted(clusters, key=lambda item: (item["begin"], item["end"])):
        begin = int(cluster["begin"])
        end = int(cluster["end"])
        if merged and begin <= int(merged[-1]["end"]):
            merged[-1]["end"] = max(int(merged[-1]["end"]), end)
            merged[-1]["apices"] = sorted(
                set(merged[-1]["apices"]) | set(cluster["apices"])
            )
            merged[-1]["peak_width_min"] = max(
                float(merged[-1]["peak_width_min"]),
                float(cluster["peak_width_min"]),
            )
            merged[-1]["end_reason"] = "merged_overlapping_clusters"
        else:
            merged.append(
                {
                    "begin": begin,
                    "end": end,
                    "apices": list(cluster["apices"]),
                    "peak_width_min": float(cluster["peak_width_min"]),
                    "end_reason": str(cluster["end_reason"]),
                }
            )
    return merged


def _evaluate_cluster(
    time: np.ndarray,
    signal: np.ndarray,
    baseline_trace: np.ndarray,
    cluster_start: int,
    cluster_end: int,
    *,
    initial_peak_width_min: float,
    minimum_height: float,
    minimum_area: float,
    peak_to_valley_ratio: float,
    candidate_apices: list[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if cluster_end - cluster_start < 2:
        return [], []
    segment = signal[cluster_start : cluster_end + 1]
    maxima = [
        int(index)
        for index in candidate_apices
        if cluster_start < int(index) < cluster_end
    ]
    if not maxima:
        maxima = [cluster_start + int(np.argmax(segment))]

    baseline_start = _finite_or_raw(
        baseline_trace[cluster_start], signal[cluster_start]
    )
    baseline_end = _finite_or_raw(baseline_trace[cluster_end], signal[cluster_end])
    outer_baseline, outer_pegs = _advanced_baseline(
        time[cluster_start : cluster_end + 1],
        signal[cluster_start : cluster_end + 1],
        baseline_start,
        baseline_end,
    )
    corrected_heights = {
        apex: float(signal[apex] - outer_baseline[apex - cluster_start])
        for apex in maxima
    }
    maxima = [apex for apex in maxima if corrected_heights[apex] >= minimum_height]
    if not maxima:
        return [], []

    minimum_distance_points = max(
        1,
        int(round(initial_peak_width_min / np.median(np.diff(time)) / 2.0)),
    )
    maxima = _suppress_close_maxima(maxima, corrected_heights, minimum_distance_points)
    maxima.sort()
    valleys = [
        left
        + int(np.argmin(signal[left : right + 1]))
        for left, right in zip(maxima[:-1], maxima[1:])
    ]
    split_valleys: set[int] = set()
    for left_apex, valley, right_apex in zip(maxima[:-1], valleys, maxima[1:]):
        valley_baseline = float(
            np.interp(
                time[valley],
                (time[cluster_start], time[cluster_end]),
                (baseline_start, baseline_end),
            )
        )
        valley_baseline = float(outer_baseline[valley - cluster_start])
        valley_height = float(signal[valley] - valley_baseline)
        if valley_height <= 0:
            split_valleys.add(valley)
            continue
        ratio = min(
            corrected_heights[left_apex],
            corrected_heights[right_apex],
        ) / valley_height
        if ratio >= peak_to_valley_ratio:
            split_valleys.add(valley)

    groups: list[tuple[int, int]] = []
    group_start = cluster_start
    for valley in valleys:
        if valley in split_valleys:
            groups.append((group_start, valley))
            group_start = valley
    groups.append((group_start, cluster_end))

    peaks: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for group_start, group_end in groups:
        group_maxima = [apex for apex in maxima if group_start <= apex <= group_end]
        if not group_maxima:
            continue
        group_valleys = [
            left + int(np.argmin(signal[left : right + 1]))
            for left, right in zip(group_maxima[:-1], group_maxima[1:])
        ]
        group_boundaries = [group_start, *group_valleys, group_end]
        group_baseline = np.asarray(
            outer_baseline[
                group_start - cluster_start : group_end - cluster_start + 1
            ],
            dtype=np.float64,
        ).copy()
        if group_start in split_valleys:
            group_baseline[0] = signal[group_start]
        if group_end in split_valleys:
            group_baseline[-1] = signal[group_end]
        if len(group_baseline) > 1 and (
            group_start in split_valleys or group_end in split_valleys
        ):
            group_baseline = np.interp(
                time[group_start : group_end + 1],
                (time[group_start], time[group_end]),
                (float(group_baseline[0]), float(group_baseline[-1])),
            )
        for position, apex in enumerate(group_maxima):
            begin = group_boundaries[position]
            end = group_boundaries[position + 1]
            if end <= begin:
                continue
            peak_baseline_start = float(group_baseline[begin - group_start])
            peak_baseline_end = float(group_baseline[end - group_start])
            segment_time = time[begin : end + 1]
            line = group_baseline[
                begin - group_start : end - group_start + 1
            ]
            area = float(
                np.trapezoid(signal[begin : end + 1] - line, segment_time)
                * 60.0
            )
            height = float(signal[apex] - group_baseline[apex - group_start])
            if not math.isfinite(area) or area < minimum_area or height < minimum_height:
                rejected.append(
                    {
                        "retention_time_min": float(time[apex]),
                        "corrected_height_mau": height,
                        "candidate_area_mau_s": area,
                        "reason": "ChemStation-compatible area/height reject",
                        "manual_check_required": True,
                    }
                )
                continue
            apex_time = _parabolic_apex_time(time, signal, apex)
            peaks.append(
                {
                    "apex_index": int(apex),
                    "begin_index": int(begin),
                    "end_index": int(end),
                    "retention_time_min": apex_time,
                    "begin_time_min": float(time[begin]),
                    "end_time_min": float(time[end]),
                    "width_base_min": float(time[end] - time[begin]),
                    "area": area,
                    "area_unit": "mAU*s",
                    "height": height,
                    "height_unit": "mAU",
                    "baseline_start": peak_baseline_start,
                    "baseline_end": peak_baseline_end,
                    "baseline_model": (
                        "ChemStation-compatible moving baseline outer line + valley drop"
                    ),
                    "baseline_allocation": (
                        "individual_peak"
                        if len(group_maxima) == 1
                        else "shared_cluster_valley_drop"
                    ),
                    "individual_baseline_area": None,
                    "baseline_code": "CS-CANDIDATE",
                    "advanced_baseline_peg_indices": [
                        cluster_start + int(index) for index in outer_pegs
                    ],
                    "peak_source": "native_dx",
                    "integrator_name": CHEMSTATION_COMPATIBLE_INTEGRATOR_NAME,
                    "integrator_version": CHEMSTATION_COMPATIBLE_INTEGRATOR_VERSION,
                }
            )
    return peaks, rejected


def _advanced_baseline(
    time: np.ndarray,
    signal: np.ndarray,
    baseline_start: float,
    baseline_end: float,
) -> tuple[np.ndarray, list[int]]:
    """Create a deterministic, non-penetrating pegs-and-thread baseline.

    The published Advanced algorithm does not disclose its objective function.
    This candidate adds the deepest penetration point as a peg until the
    piecewise-linear baseline no longer crosses the raw signal.
    """
    pegs = [0, len(signal) - 1]
    values = {
        0: min(float(baseline_start), float(signal[0])),
        len(signal) - 1: min(float(baseline_end), float(signal[-1])),
    }
    tolerance = max(float(np.ptp(signal)) * 1e-12, 1e-12)
    while True:
        ordered = sorted(pegs)
        baseline = np.interp(
            time,
            time[ordered],
            [values[index] for index in ordered],
        )
        penetration = baseline - signal
        index = int(np.argmax(penetration))
        if penetration[index] <= tolerance or index in values:
            return baseline, ordered
        pegs.append(index)
        values[index] = float(signal[index])


def _suppress_close_maxima(
    maxima: list[int],
    heights: Mapping[int, float],
    minimum_distance_points: int,
) -> list[int]:
    selected: list[int] = []
    for apex in sorted(maxima, key=lambda item: (-heights[item], item)):
        if all(abs(apex - existing) >= minimum_distance_points for existing in selected):
            selected.append(apex)
    return selected


def _parabolic_apex_time(
    time: np.ndarray,
    signal: np.ndarray,
    apex_index: int,
) -> float:
    if apex_index <= 0 or apex_index >= len(signal) - 1:
        return float(time[apex_index])
    x = time[apex_index - 1 : apex_index + 2]
    y = signal[apex_index - 1 : apex_index + 2]
    coefficients = np.polyfit(x, y, 2)
    if coefficients[0] >= 0 or not np.isfinite(coefficients).all():
        return float(time[apex_index])
    vertex = float(-coefficients[1] / (2.0 * coefficients[0]))
    if vertex < float(x[0]) or vertex > float(x[-1]):
        return float(time[apex_index])
    return vertex


def _finite_or_raw(value: float, raw: float) -> float:
    return float(value) if math.isfinite(float(value)) else float(raw)
