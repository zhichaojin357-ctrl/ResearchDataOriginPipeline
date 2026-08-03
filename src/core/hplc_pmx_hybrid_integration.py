from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from typing import Any, Mapping

import numpy as np

from src.core.hplc_chemstation_integration import (
    _cluster_width_estimate,
    _derivative_outputs,
    _downslope_increment,
    _recognition_filter,
    _upslope_increment,
    _validate_supported_method_policy,
)
from src.core.hplc_peak_integration import (
    _validate_signal,
    integrate_chromatogram,
)


PMX_HYBRID_INTEGRATOR_NAME = "pmx-constrained-native-hplc-hybrid-candidate"
PMX_HYBRID_INTEGRATOR_VERSION = "0.2.0"


def integrate_pmx_constrained_hybrid(
    time_min: np.ndarray | list[float],
    signal_mau: np.ndarray | list[float],
    config: Mapping[str, Any],
    *,
    method_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply strictly confirmed PMX boundary proposals to safe native peaks.

    Detection remains entirely native.  The documented accumulator scan is run
    once over the complete raw chromatogram and is independent of configured
    target windows.  It may only refine the two bounds and area of an isolated,
    non-target native peak.  Every other native field is frozen.

    This remains an auditable compatibility experiment, not a vendor-equivalent
    implementation and not a production integrator.
    """
    policy = dict(method_policy)
    _validate_hybrid_method_policy(policy)
    time = np.asarray(time_min, dtype=np.float64).reshape(-1)
    signal = np.asarray(signal_mau, dtype=np.float64).reshape(-1)
    _validate_signal(time, signal)

    base = integrate_chromatogram(time, signal, config)
    scan = _scan_documented_accumulator_blocks(time, signal, policy)
    base_peaks = base["peaks"]
    peaks = deepcopy(base_peaks)
    decisions: Counter[str] = Counter()
    changed = 0

    for peak in peaks:
        original = deepcopy(peak)
        if _intersecting_target_keys(
            float(peak["begin_time_min"]),
            float(peak["end_time_min"]),
            config["targets"],
        ):
            decision = "frozen_target_window_intersection"
            audit = {"intersecting_target_keys": _intersecting_target_keys(
                float(peak["begin_time_min"]),
                float(peak["end_time_min"]),
                config["targets"],
            )}
        elif str(peak.get("baseline_allocation")) != "individual_peak":
            decision = "frozen_shared_cluster"
            audit = {}
        else:
            decision, audit, refinement = _propose_refinement(
                time,
                signal,
                peak,
                base_peaks,
                scan["blocks"],
                config,
                policy,
            )
            if decision == "refined_pmx_confirmed_block":
                peak.update(refinement)
                peak["pre_hybrid_result"] = original
                peak["integrator_name"] = PMX_HYBRID_INTEGRATOR_NAME
                peak["integrator_version"] = PMX_HYBRID_INTEGRATOR_VERSION
                peak["baseline_model"] = (
                    "native baseline line evaluated at strictly confirmed "
                    "PMX accumulator bounds"
                )
                peak["baseline_code"] = "PMX-HYBRID-CANDIDATE"
                peak["baseline_model_uncertain"] = True
                peak["manual_check_required"] = True
                changed += 1

        peak["hybrid_decision"] = decision
        peak["hybrid_candidate_audit"] = audit
        decisions[decision] += 1

    _assert_native_identity_fields_unchanged(base_peaks, peaks)
    return {
        **base,
        "integrator_name": PMX_HYBRID_INTEGRATOR_NAME,
        "integrator_version": PMX_HYBRID_INTEGRATOR_VERSION,
        "status": "OK",
        "validation_status": "candidate",
        "vendor_equivalent": False,
        "production_enabled": False,
        "manual_check_required": True,
        "base_integrator": {
            "name": base["integrator_name"],
            "version": base["integrator_version"],
        },
        "method_source": dict(policy.get("method_source", {})),
        "boundary_confirmation_mode": "both_accumulators_and_envelope_required",
        "target_peak_policy": (
            "freeze every native interval intersecting a target RT window"
        ),
        "scan_model": scan["model"],
        "scan_audit": scan["audit"],
        "changed_peak_count": changed,
        "hybrid_decision_counts": dict(sorted(decisions.items())),
        "peaks": peaks,
    }


def _validate_hybrid_method_policy(policy: Mapping[str, Any]) -> None:
    _validate_supported_method_policy(policy)
    if float(policy.get("area_percent_reject", 0.0)) != 0.0:
        raise NotImplementedError(
            "PMX hybrid candidate requires AreaPercentReject=0 because a "
            "total-area rejection rule could change the frozen native peak set"
        )


def _scan_documented_accumulator_blocks(
    time: np.ndarray,
    signal: np.ndarray,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Scan complete blocks using only accumulator-confirmed end semantics."""
    sampling_interval_min = float(np.median(np.diff(time)))
    expected_peak_width_min = float(policy["initial_peak_width_min"])
    sensitivity = float(policy["slope_sensitivity"])
    scaling = str(policy.get("recognition_scaling", "peak_width_normalized"))

    baseline_level = float(signal[0])
    baseline_points: list[int] = [0]
    last_baseline_index = 0
    candidate_start_index = 0
    start_confirmation_index: int | None = None
    down_confirmation_index: int | None = None
    up_accumulator = 0
    down_accumulator = 0
    block_start_index: int | None = None
    possible_end = False
    blocks: list[dict[str, Any]] = []
    filter_usage: Counter[str] = Counter()
    bunching_usage: Counter[int] = Counter()
    incomplete_block_count = 0

    for index in range(1, len(signal)):
        expected_points = max(
            1,
            int(round(expected_peak_width_min / sampling_interval_min)),
        )
        filter_number, bunching_power = _recognition_filter(expected_points)
        filter_usage[f"filter_{filter_number}"] += 1
        bunching_usage[bunching_power] += 1
        derivative = _derivative_outputs(
            time,
            signal,
            index,
            filter_number=filter_number,
            bunching_power=bunching_power,
            expected_peak_width_min=expected_peak_width_min,
            scaling=scaling,
        )
        if derivative is None:
            continue
        slope, curvature = derivative
        previous_up = up_accumulator
        up_accumulator = max(
            0,
            up_accumulator
            + _upslope_increment(
                slope,
                curvature,
                sensitivity,
                filter_number,
            ),
        )
        down_accumulator = max(
            0,
            down_accumulator
            + _downslope_increment(
                slope,
                curvature,
                sensitivity,
                filter_number,
            ),
        )
        within_envelope = (
            abs(slope) <= sensitivity and abs(curvature) <= sensitivity
        )

        if block_start_index is None:
            if within_envelope:
                baseline_points.append(index)
                window_start = max(0, index - 2 * expected_points + 1)
                accepted = [point for point in baseline_points if point >= window_start]
                if accepted:
                    baseline_level = float(np.mean(signal[accepted]))
                last_baseline_index = index
            if previous_up == 0 and up_accumulator > 0:
                candidate_start_index = last_baseline_index
            if up_accumulator >= 15:
                block_start_index = candidate_start_index
                start_confirmation_index = index
                down_confirmation_index = None
                possible_end = False
                down_accumulator = 0
            continue

        if down_accumulator >= 15 and not possible_end:
            possible_end = True
            down_confirmation_index = index
        if not (possible_end and within_envelope):
            continue

        end_index = index
        if end_index > block_start_index:
            width_before = expected_peak_width_min
            observed_width = _cluster_width_estimate(
                time,
                signal,
                block_start_index,
                end_index,
            )
            if math.isfinite(observed_width) and observed_width > 0.0:
                expected_peak_width_min = (
                    0.75 * expected_peak_width_min + 0.25 * observed_width
                )
            blocks.append(
                {
                    "begin_index": int(block_start_index),
                    "end_index": int(end_index),
                    "start_confirmation_index": int(start_confirmation_index),
                    "down_confirmation_index": int(down_confirmation_index),
                    "end_confirmation_index": int(index),
                    "expected_width_before_min": float(width_before),
                    "observed_width_min": (
                        float(observed_width)
                        if math.isfinite(observed_width)
                        else None
                    ),
                    "expected_width_after_min": float(expected_peak_width_min),
                    "end_reason": "documented_down_accumulator_and_envelope",
                }
            )

        block_start_index = None
        start_confirmation_index = None
        down_confirmation_index = None
        possible_end = False
        up_accumulator = 0
        down_accumulator = 0
        baseline_points = [index]
        last_baseline_index = index
        candidate_start_index = index
        baseline_level = float(signal[index])

    if block_start_index is not None:
        incomplete_block_count += 1
    return {
        "model": (
            "causal whole-chromatogram PMX accumulator scan using the published "
            "filter/bunching table and accumulator weights; exact vendor filter "
            "coefficients and normalization remain undisclosed"
        ),
        "blocks": blocks,
        "audit": {
            "confirmed_block_count": len(blocks),
            "incomplete_block_count": incomplete_block_count,
            "filter_usage": dict(sorted(filter_usage.items())),
            "bunching_usage": {
                str(key): value for key, value in sorted(bunching_usage.items())
            },
            "initial_peak_width_min": float(policy["initial_peak_width_min"]),
            "final_expected_peak_width_min": float(expected_peak_width_min),
            "dynamic_width_update": "0.75 previous + 0.25 observed completed block",
            "surrogate_end_conditions_allowed": False,
        },
    }


def _propose_refinement(
    time: np.ndarray,
    signal: np.ndarray,
    peak: Mapping[str, Any],
    all_peaks: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    config: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    begin = int(peak["begin_index"])
    apex = int(peak["apex_index"])
    end = int(peak["end_index"])
    matching = [
        block
        for block in blocks
        if int(block["begin_index"]) < apex < int(block["end_index"])
    ]
    audit: dict[str, Any] = {
        "native_begin_index": begin,
        "native_apex_index": apex,
        "native_end_index": end,
        "matching_confirmed_block_count": len(matching),
    }
    if len(matching) != 1:
        return "fallback_no_unique_confirmed_block", audit, {}
    block = matching[0]
    new_begin = int(block["begin_index"])
    new_end = int(block["end_index"])
    audit.update(
        {
            "candidate_begin_index": new_begin,
            "candidate_end_index": new_end,
            "block": deepcopy(block),
        }
    )
    if not (begin <= new_begin < apex < new_end <= end):
        return "fallback_not_inward", audit, {}
    if new_begin == begin and new_end == end:
        return "fallback_no_change", audit, {}
    enclosed_apices = [
        int(other["apex_index"])
        for other in all_peaks
        if new_begin < int(other["apex_index"]) < new_end
    ]
    audit["enclosed_native_apex_indices"] = enclosed_apices
    if enclosed_apices != [apex]:
        return "fallback_contains_other_apex", audit, {}

    candidate_begin_time = float(time[new_begin])
    candidate_end_time = float(time[new_end])
    intersecting_targets = _intersecting_target_keys(
        candidate_begin_time,
        candidate_end_time,
        config["targets"],
    )
    audit["candidate_intersecting_target_keys"] = intersecting_targets
    if intersecting_targets:
        return "frozen_target_window_intersection", audit, {}

    width_min = candidate_end_time - candidate_begin_time
    if width_min + 1e-15 < float(
        config["native_integration"]["minimum_peak_width_min"]
    ):
        return "fallback_native_min_width", audit, {}

    baseline_start = _baseline_value_at_index(peak, time, new_begin)
    baseline_end = _baseline_value_at_index(peak, time, new_end)
    segment_time = time[new_begin : new_end + 1]
    baseline = np.interp(
        segment_time,
        (segment_time[0], segment_time[-1]),
        (baseline_start, baseline_end),
    )
    segment_signal = signal[new_begin : new_end + 1]
    tolerance = max(float(np.ptp(segment_signal)) * 1e-12, 1e-12)
    if np.any(baseline > segment_signal + tolerance):
        return "fallback_baseline_penetration", audit, {}

    area = float(np.trapezoid(segment_signal - baseline, segment_time) * 60.0)
    candidate_height = float(signal[apex] - baseline[apex - new_begin])
    audit.update(
        {
            "candidate_area_mau_s": area,
            "candidate_height_mau": candidate_height,
            "candidate_baseline_start_mau": baseline_start,
            "candidate_baseline_end_mau": baseline_end,
        }
    )
    if not math.isfinite(area) or not math.isfinite(candidate_height):
        return "fallback_nonfinite", audit, {}
    if area < float(policy["area_reject_mau_s"]):
        return "fallback_pmx_area_reject", audit, {}
    if candidate_height < float(policy["height_reject_mau"]):
        return "fallback_pmx_height_reject", audit, {}

    return (
        "refined_pmx_confirmed_block",
        audit,
        {
            "begin_index": new_begin,
            "end_index": new_end,
            "begin_time_min": candidate_begin_time,
            "end_time_min": candidate_end_time,
            "width_base_min": width_min,
            "area": area,
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
            "boundary_refinement": (
                "inward-only, whole-chromatogram PMX accumulator-confirmed block"
            ),
        },
    )


def _intersecting_target_keys(
    begin_time_min: float,
    end_time_min: float,
    targets: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    return sorted(
        key
        for key, target in targets.items()
        if begin_time_min
        <= float(target["nominal_rt_min"]) + float(target["rt_tolerance_min"])
        + 1e-12
        and end_time_min
        >= float(target["nominal_rt_min"]) - float(target["rt_tolerance_min"])
        - 1e-12
    )


def _baseline_value_at_index(
    peak: Mapping[str, Any],
    time: np.ndarray,
    index: int,
) -> float:
    return float(
        np.interp(
            time[index],
            (
                float(peak["begin_time_min"]),
                float(peak["end_time_min"]),
            ),
            (
                float(peak["baseline_start"]),
                float(peak["baseline_end"]),
            ),
        )
    )


def _assert_native_identity_fields_unchanged(
    native_peaks: list[dict[str, Any]],
    hybrid_peaks: list[dict[str, Any]],
) -> None:
    if len(native_peaks) != len(hybrid_peaks):
        raise AssertionError("PMX hybrid changed the frozen native peak count")
    frozen_fields = (
        "peak_ordinal",
        "apex_index",
        "retention_time_min",
        "height",
        "height_unit",
        "area_unit",
        "peak_source",
    )
    for native, hybrid in zip(native_peaks, hybrid_peaks):
        for field in frozen_fields:
            if hybrid.get(field) != native.get(field):
                raise AssertionError(f"PMX hybrid changed frozen native field: {field}")
