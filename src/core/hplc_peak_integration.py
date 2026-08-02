from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
from pybaselines import Baseline
from scipy.signal import find_peaks, savgol_filter


NATIVE_INTEGRATOR_NAME = "project-native-hplc-target-integrator"
NATIVE_INTEGRATOR_VERSION = "1.1.0"


def integrate_chromatogram(
    time_min: np.ndarray | list[float],
    signal_mau: np.ndarray | list[float],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Detect and integrate chromatographic peaks without an OpenLab method file.

    Peak candidates are true local maxima after light Savitzky-Golay smoothing.
    The baseline is estimated independently with a morphological opening/closing
    baseline.  The closest smoothed minima delimit each peak. Isolated peaks use
    a straight line between their morphological baseline endpoints. Adjacent
    accepted peaks that share a valley use one common outer baseline and a
    vertical valley drop-line, reflecting documented ChemStation/OpenLab
    allocation semantics without reading vendor integration results.
    """
    policy = config["native_integration"]
    time = np.asarray(time_min, dtype=np.float64).reshape(-1)
    signal = np.asarray(signal_mau, dtype=np.float64).reshape(-1)
    _validate_signal(time, signal)

    point_count = len(time)
    smoothing_window = _odd_window(
        int(policy["smoothing_window_points"]),
        point_count,
        minimum=int(policy["smoothing_polyorder"]) + 2,
    )
    smoothed = savgol_filter(
        signal,
        window_length=smoothing_window,
        polyorder=int(policy["smoothing_polyorder"]),
        mode="interp",
    )
    sampling_interval_min = float(np.median(np.diff(time)))
    half_window_points = max(
        1,
        int(round(float(policy["morphology_half_window_min"]) / sampling_interval_min)),
    )
    baseline, _ = Baseline(x_data=time, check_finite=True).mor(
        signal,
        half_window=half_window_points,
    )
    baseline = np.asarray(baseline, dtype=np.float64)
    if baseline.shape != signal.shape or not np.isfinite(baseline).all():
        raise ValueError("native HPLC baseline calculation returned invalid values")

    maxima, _ = find_peaks(smoothed)
    minima, _ = find_peaks(-smoothed)
    minimum_height = float(policy["minimum_corrected_height_mau"])
    minimum_area = float(policy["minimum_area_mau_s"])
    minimum_width = float(policy["minimum_peak_width_min"])
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for apex_index in maxima:
        corrected_height = float(smoothed[apex_index] - baseline[apex_index])
        if corrected_height < minimum_height:
            continue
        left_candidates = minima[minima < apex_index]
        right_candidates = minima[minima > apex_index]
        if not len(left_candidates) or not len(right_candidates):
            rejected.append(
                _rejected_candidate(
                    time,
                    apex_index,
                    corrected_height,
                    "色谱边界内缺少左右局部极小值",
                )
            )
            continue
        begin_index = int(left_candidates[-1])
        end_index = int(right_candidates[0])
        width_min = float(time[end_index] - time[begin_index])
        if width_min < minimum_width:
            rejected.append(
                _rejected_candidate(
                    time,
                    apex_index,
                    corrected_height,
                    f"峰宽 {width_min:.6g} min 小于最小峰宽",
                )
            )
            continue
        area = _integrate_linear_baseline(
            time,
            signal,
            begin_index,
            end_index,
            float(baseline[begin_index]),
            float(baseline[end_index]),
        )
        if not math.isfinite(area) or area < minimum_area:
            rejected.append(
                _rejected_candidate(
                    time,
                    apex_index,
                    corrected_height,
                    f"峰面积 {area:.6g} mAU·s 小于最小面积",
                )
            )
            continue
        accepted.append(
            {
                "apex_index": int(apex_index),
                "begin_index": begin_index,
                "end_index": end_index,
                "retention_time_min": float(time[apex_index]),
                "begin_time_min": float(time[begin_index]),
                "end_time_min": float(time[end_index]),
                "width_base_min": width_min,
                "area": area,
                "area_unit": "mAU*s",
                "height": corrected_height,
                "height_unit": "mAU",
                "baseline_start": float(baseline[begin_index]),
                "baseline_end": float(baseline[end_index]),
                "baseline_model": "native individual morphological endpoints + linear baseline",
                "baseline_allocation": "individual_peak",
                "baseline_cluster_id": None,
                "baseline_cluster_size": 1,
                "baseline_cluster_position": 1,
                "baseline_model_uncertain": False,
                "individual_baseline_area": None,
                "baseline_code": "NATIVE",
                "peak_source": "native_dx",
                "integrator_name": NATIVE_INTEGRATOR_NAME,
                "integrator_version": NATIVE_INTEGRATOR_VERSION,
                "manual_check_required": True,
            }
        )

    accepted.sort(key=lambda peak: (peak["retention_time_min"], peak["apex_index"]))
    shared_baseline_cluster_count = _allocate_shared_cluster_baselines(
        time,
        signal,
        accepted,
        minimum_area=minimum_area,
    )
    reallocated: list[dict[str, Any]] = []
    for peak in accepted:
        area = float(peak["area"])
        if not math.isfinite(area) or area < minimum_area:
            rejected.append(
                _rejected_candidate(
                    time,
                    int(peak["apex_index"]),
                    float(peak["height"]),
                    f"共用基线分配后峰面积 {area:.6g} mAU·s 小于最小面积",
                )
            )
            continue
        reallocated.append(peak)
    accepted = reallocated
    for ordinal, peak in enumerate(accepted, start=1):
        peak["peak_ordinal"] = ordinal
    return {
        "integrator_name": NATIVE_INTEGRATOR_NAME,
        "integrator_version": NATIVE_INTEGRATOR_VERSION,
        "status": "OK",
        "sampling_interval_s": sampling_interval_min * 60.0,
        "smoothing_window_points": smoothing_window,
        "morphology_half_window_points": half_window_points,
        "shared_baseline_cluster_count": shared_baseline_cluster_count,
        "peak_count": len(accepted),
        "peaks": accepted,
        "rejected_candidates": rejected,
    }


def match_native_target_peaks(
    peaks: list[dict[str, Any]],
    targets: Mapping[str, Mapping[str, Any]],
    *,
    ambiguity_margin_min: float,
    signal_quantifiable: bool,
) -> dict[str, dict[str, Any]]:
    """Match configured targets to independently integrated peak rows."""
    matched: dict[str, dict[str, Any]] = {}
    for target_key, target in targets.items():
        nominal = float(target["nominal_rt_min"])
        tolerance = float(target["rt_tolerance_min"])
        candidates = [
            peak
            for peak in peaks
            if abs(float(peak["retention_time_min"]) - nominal) <= tolerance + 1e-12
        ]
        candidates.sort(
            key=lambda peak: (
                abs(float(peak["retention_time_min"]) - nominal),
                int(peak["peak_ordinal"]),
            )
        )
        if not candidates:
            matched[target_key] = {
                "target_key": target_key,
                "display_name": str(target["display_name"]),
                "nominal_rt_min": nominal,
                "retention_time_min": None,
                "rt_deviation_min": None,
                "area": 0.0 if signal_quantifiable else None,
                "selected_peak_ordinal": None,
                "candidate_count": 0,
                "candidate_peak_ordinals": [],
                "candidate_retention_times_min": [],
                "ambiguous": False,
                "match_status": (
                    "正常未检出" if signal_quantifiable else "数据异常导致无法定量"
                ),
                "peak_source": "native_dx",
            }
            continue
        selected = candidates[0]
        ambiguous = (
            len(candidates) > 1
            and abs(
                abs(float(candidates[1]["retention_time_min"]) - nominal)
                - abs(float(selected["retention_time_min"]) - nominal)
            )
            <= float(ambiguity_margin_min)
        )
        matched[target_key] = {
            "target_key": target_key,
            "display_name": str(target["display_name"]),
            "nominal_rt_min": nominal,
            "retention_time_min": float(selected["retention_time_min"]),
            "rt_deviation_min": float(selected["retention_time_min"]) - nominal,
            "area": float(selected["area"]),
            "selected_peak_ordinal": int(selected["peak_ordinal"]),
            "candidate_count": len(candidates),
            "candidate_peak_ordinals": [int(peak["peak_ordinal"]) for peak in candidates],
            "candidate_retention_times_min": [
                float(peak["retention_time_min"]) for peak in candidates
            ],
            "ambiguous": ambiguous,
            "match_status": (
                "目标峰匹配存在歧义"
                if ambiguous
                else "多候选峰-按最近RT"
                if len(candidates) > 1
                else "RT窗口匹配"
            ),
            "peak_source": "native_dx",
            "begin_time_min": float(selected["begin_time_min"]),
            "end_time_min": float(selected["end_time_min"]),
            "height": float(selected["height"]),
            "baseline_start": float(selected["baseline_start"]),
            "baseline_end": float(selected["baseline_end"]),
            "baseline_model": selected.get("baseline_model", ""),
            "baseline_allocation": selected.get("baseline_allocation", "individual_peak"),
            "baseline_model_uncertain": bool(selected.get("baseline_model_uncertain", False)),
            "individual_baseline_area": selected.get("individual_baseline_area"),
            "integrator_name": selected["integrator_name"],
            "integrator_version": selected["integrator_version"],
        }
    return matched


def _integrate_linear_baseline(
    time: np.ndarray,
    signal: np.ndarray,
    begin_index: int,
    end_index: int,
    baseline_start: float,
    baseline_end: float,
) -> float:
    segment_time = time[begin_index : end_index + 1]
    segment_signal = signal[begin_index : end_index + 1]
    line = np.interp(
        segment_time,
        (segment_time[0], segment_time[-1]),
        (baseline_start, baseline_end),
    )
    return float(np.trapezoid(segment_signal - line, segment_time) * 60.0)


def _allocate_shared_cluster_baselines(
    time: np.ndarray,
    signal: np.ndarray,
    peaks: list[dict[str, Any]],
    *,
    minimum_area: float,
) -> int:
    """Allocate one outer baseline across adjacent valley-separated peaks.

    Consecutive accepted peaks are first chained only when the right bound of
    one is exactly the left bound of the next. A chain is then split recursively
    wherever an internal valley lies on or below its proposed outer baseline;
    such a valley is baseline-resolved and cannot support a positive vertical
    drop-line. This introduces no fitted tolerance or vendor-derived decision
    rule. Each retained valley remains the integration boundary, while its
    baseline value is taken from the common line spanning the cluster. If that
    allocation would make any member non-finite or smaller than the configured
    minimum area, the entire proposed cluster keeps its individual baselines.
    """
    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for peak in peaks:
        if current and int(current[-1]["end_index"]) != int(peak["begin_index"]):
            clusters.append(current)
            current = []
        current.append(peak)
    if current:
        clusters.append(current)

    allocated_clusters = [
        allocated
        for cluster in clusters
        for allocated in _split_nonpositive_valley_drops(time, signal, cluster)
    ]

    shared_count = 0
    for cluster in allocated_clusters:
        if len(cluster) < 2:
            continue
        cluster_begin_index = int(cluster[0]["begin_index"])
        cluster_end_index = int(cluster[-1]["end_index"])
        cluster_begin_time = float(time[cluster_begin_index])
        cluster_end_time = float(time[cluster_end_index])
        cluster_baseline_start = float(cluster[0]["baseline_start"])
        cluster_baseline_end = float(cluster[-1]["baseline_end"])

        allocations: list[tuple[float, float, float]] = []
        for peak in cluster:
            begin_index = int(peak["begin_index"])
            end_index = int(peak["end_index"])
            baseline_start = float(
                np.interp(
                    time[begin_index],
                    (cluster_begin_time, cluster_end_time),
                    (cluster_baseline_start, cluster_baseline_end),
                )
            )
            baseline_end = float(
                np.interp(
                    time[end_index],
                    (cluster_begin_time, cluster_end_time),
                    (cluster_baseline_start, cluster_baseline_end),
                )
            )
            area = _integrate_linear_baseline(
                time,
                signal,
                begin_index,
                end_index,
                baseline_start,
                baseline_end,
            )
            allocations.append((area, baseline_start, baseline_end))
        if any(
            not math.isfinite(area) or area < minimum_area
            for area, _, _ in allocations
        ):
            continue

        shared_count += 1
        cluster_id = f"NATIVE-C{shared_count:03d}"
        for position, (peak, allocation) in enumerate(
            zip(cluster, allocations),
            start=1,
        ):
            area, baseline_start, baseline_end = allocation
            individual_baseline_area = float(peak["area"])
            peak["area"] = area
            peak["baseline_start"] = baseline_start
            peak["baseline_end"] = baseline_end
            peak["baseline_model"] = (
                "native shared morphological outer baseline + valley drop-line"
            )
            peak["baseline_allocation"] = "shared_cluster_valley_drop"
            peak["baseline_cluster_id"] = cluster_id
            peak["baseline_cluster_size"] = len(cluster)
            peak["baseline_cluster_position"] = position
            peak["baseline_cluster_begin_time_min"] = cluster_begin_time
            peak["baseline_cluster_end_time_min"] = cluster_end_time
            peak["baseline_model_uncertain"] = True
            peak["individual_baseline_area"] = individual_baseline_area
            peak["baseline_model_uncertainty_reason"] = (
                "raw geometry alone cannot uniquely distinguish a shared valley "
                "drop-line from two baseline-resolved peaks"
            )
    return shared_count


def _split_nonpositive_valley_drops(
    time: np.ndarray,
    signal: np.ndarray,
    cluster: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Split a proposed cluster until every internal valley is above its baseline."""
    if len(cluster) < 2:
        return [cluster]
    cluster_begin_index = int(cluster[0]["begin_index"])
    cluster_end_index = int(cluster[-1]["end_index"])
    outer_time = (
        float(time[cluster_begin_index]),
        float(time[cluster_end_index]),
    )
    outer_baseline = (
        float(cluster[0]["baseline_start"]),
        float(cluster[-1]["baseline_end"]),
    )
    valley_drops = []
    for peak in cluster[:-1]:
        valley_index = int(peak["end_index"])
        common_baseline = float(
            np.interp(time[valley_index], outer_time, outer_baseline)
        )
        valley_drops.append(float(signal[valley_index]) - common_baseline)
    split_index = int(np.argmin(valley_drops))
    if valley_drops[split_index] > 0.0:
        return [cluster]
    return [
        *_split_nonpositive_valley_drops(
            time,
            signal,
            cluster[: split_index + 1],
        ),
        *_split_nonpositive_valley_drops(
            time,
            signal,
            cluster[split_index + 1 :],
        ),
    ]


def _validate_signal(time: np.ndarray, signal: np.ndarray) -> None:
    if time.shape != signal.shape:
        raise ValueError("native HPLC integration requires equal one-dimensional time/signal arrays")
    if len(time) < 5:
        raise ValueError("native HPLC integration requires at least five signal points")
    if not np.isfinite(time).all() or not np.isfinite(signal).all():
        raise ValueError("native HPLC integration requires finite time/signal values")
    if not np.all(np.diff(time) > 0):
        raise ValueError("native HPLC integration requires a strictly increasing time axis")


def _odd_window(requested: int, point_count: int, *, minimum: int) -> int:
    window = max(requested, minimum)
    if window % 2 == 0:
        window += 1
    maximum = point_count if point_count % 2 == 1 else point_count - 1
    if maximum < minimum:
        raise ValueError("signal is too short for the configured Savitzky-Golay polynomial")
    return min(window, maximum)


def _rejected_candidate(
    time: np.ndarray,
    apex_index: int,
    height: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "retention_time_min": float(time[apex_index]),
        "corrected_height_mau": height,
        "reason": reason,
        "manual_check_required": True,
    }
