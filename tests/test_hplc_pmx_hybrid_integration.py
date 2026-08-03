from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from src.core.hplc_peak_integration import integrate_chromatogram
from src.core.hplc_pmx_hybrid_integration import (
    _intersecting_target_keys,
    _scan_documented_accumulator_blocks,
    integrate_pmx_constrained_hybrid,
)


def _config(targets: dict | None = None) -> dict:
    return {
        "native_integration": {
            "smoothing_window_points": 9,
            "smoothing_polyorder": 3,
            "morphology_half_window_min": 0.40,
            "minimum_corrected_height_mau": 1.70,
            "minimum_area_mau_s": 1.0,
            "minimum_peak_width_min": 0.02,
        },
        "targets": targets or {},
    }


def _policy() -> dict:
    return {
        "slope_sensitivity": 1.0,
        "initial_peak_width_min": 0.02,
        "area_reject_mau_s": 1.0,
        "height_reject_mau": 1.7,
        "area_percent_reject": 0.0,
        "shoulders_mode": "OFF",
        "baseline_correction": "Advanced",
        "tangent_skim_mode": "Standard",
        "front_skim_height_ratio": 0.0,
        "tail_skim_height_ratio": 0.0,
        "skim_valley_ratio": 20.0,
        "peak_to_valley_ratio": 500.0,
        "recognition_scaling": "peak_width_normalized",
        "timed_events": [],
        "signal_specific_events": [],
        "method_source": {"kind": "synthetic_pmx"},
    }


def _single_peak() -> tuple[np.ndarray, np.ndarray]:
    time = np.arange(0.0, 5.0, 0.005)
    signal = 0.02 * np.sin(time * 3.0)
    signal += 100.0 * np.exp(-0.5 * ((time - 2.5) / 0.08) ** 2)
    return time, signal


def test_hybrid_success_changes_only_allowed_native_measurement_fields():
    time, signal = _single_peak()
    native = integrate_chromatogram(time, signal, _config())
    result = integrate_pmx_constrained_hybrid(
        time,
        signal,
        _config(),
        method_policy=_policy(),
    )

    assert result["production_enabled"] is False
    assert result["vendor_equivalent"] is False
    assert result["changed_peak_count"] == 1
    assert result["peak_count"] == native["peak_count"] == 1
    native_peak = native["peaks"][0]
    peak = result["peaks"][0]
    for field in (
        "peak_ordinal",
        "apex_index",
        "retention_time_min",
        "height",
        "height_unit",
        "area_unit",
        "peak_source",
    ):
        assert peak[field] == native_peak[field]
    assert peak["pre_hybrid_result"] == native_peak
    assert peak["hybrid_decision"] == "refined_pmx_confirmed_block"
    assert native_peak["begin_index"] <= peak["begin_index"] < peak["apex_index"]
    assert peak["apex_index"] < peak["end_index"] <= native_peak["end_index"]


def test_target_window_freezes_peak_when_interval_intersects_but_apex_does_not():
    time, signal = _single_peak()
    native = integrate_chromatogram(time, signal, _config())
    native_peak = native["peaks"][0]
    assert native_peak["begin_time_min"] < 2.28 < native_peak["retention_time_min"]
    targets = {
        "protected": {
            "display_name": "protected",
            "nominal_rt_min": 2.28,
            "rt_tolerance_min": 0.01,
        }
    }

    result = integrate_pmx_constrained_hybrid(
        time,
        signal,
        _config(targets),
        method_policy=_policy(),
    )

    peak = result["peaks"][0]
    assert result["changed_peak_count"] == 0
    assert peak["hybrid_decision"] == "frozen_target_window_intersection"
    for field in (
        "begin_index",
        "end_index",
        "area",
        "height",
        "baseline_start",
        "baseline_end",
    ):
        assert peak[field] == native_peak[field]


def test_shared_cluster_peaks_are_frozen():
    time = np.arange(0.0, 5.0, 0.005)
    signal = 0.02 * np.sin(time * 3.0)
    signal += 10.0 * np.exp(-0.5 * ((time - 2.0) / 0.08) ** 2)
    signal += 9.0 * np.exp(-0.5 * ((time - 2.4) / 0.09) ** 2)

    result = integrate_pmx_constrained_hybrid(
        time,
        signal,
        _config(),
        method_policy=_policy(),
    )

    shared = [
        peak
        for peak in result["peaks"]
        if peak["baseline_allocation"] == "shared_cluster_valley_drop"
    ]
    assert len(shared) == 2
    assert all(peak["hybrid_decision"] == "frozen_shared_cluster" for peak in shared)


def test_accumulator_scan_is_deterministic_and_has_only_confirmed_end_reasons():
    time, signal = _single_peak()
    first = _scan_documented_accumulator_blocks(time, signal, _policy())
    second = _scan_documented_accumulator_blocks(time, signal, _policy())

    assert first == second
    assert first["blocks"]
    assert all(
        block["end_reason"] == "documented_down_accumulator_and_envelope"
        for block in first["blocks"]
    )
    assert first["audit"]["surrogate_end_conditions_allowed"] is False


def test_target_interval_intersection_uses_closed_windows():
    targets = {
        "target": {
            "nominal_rt_min": 5.0,
            "rt_tolerance_min": 0.25,
        }
    }

    assert _intersecting_target_keys(4.0, 4.75, targets) == ["target"]
    assert _intersecting_target_keys(5.25, 6.0, targets) == ["target"]
    assert _intersecting_target_keys(4.0, 4.74, targets) == []


def test_hybrid_rejects_nonzero_area_percent_policy():
    time, signal = _single_peak()
    policy = deepcopy(_policy())
    policy["area_percent_reject"] = 0.1

    with pytest.raises(NotImplementedError, match="AreaPercentReject=0"):
        integrate_pmx_constrained_hybrid(
            time,
            signal,
            _config(),
            method_policy=policy,
        )
