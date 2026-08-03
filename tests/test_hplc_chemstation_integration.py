from __future__ import annotations

import numpy as np
import pytest

from src.core.hplc_chemstation_integration import (
    _advanced_baseline,
    _derivative_outputs,
    _downslope_increment,
    _recognition_filter,
    _stable_baseline_window_surrogate,
    _upslope_increment,
    integrate_chemstation_compatible,
)


def _policy() -> dict[str, object]:
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
        "timed_events": [],
        "signal_specific_events": [],
        "method_source": {"kind": "synthetic_pmx"},
    }


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        (7, (1, 0)),
        (8, (2, 0)),
        (11, (2, 0)),
        (12, (3, 0)),
        (24, (3, 0)),
        (25, (3, 1)),
        (48, (3, 1)),
        (49, (3, 2)),
        (96, (3, 2)),
        (97, (3, 3)),
        (192, (3, 3)),
        (193, (3, 4)),
    ],
)
def test_documented_filter_mapping_has_fixed_overlap_resolution(points, expected):
    assert _recognition_filter(points) == expected


def test_response_difference_filter_preserves_linear_slope_and_zero_curvature():
    time = np.arange(12, dtype=np.float64)
    signal = 3.0 * time + 2.0

    slope, curvature = _derivative_outputs(
        time,
        signal,
        8,
        filter_number=1,
        bunching_power=0,
        expected_peak_width_min=1.0,
        scaling="response_difference",
    )

    assert slope == pytest.approx(3.0)
    assert curvature == pytest.approx(0.0)


def test_accumulator_tables_use_published_weights():
    assert _upslope_increment(2.0, 0.0, 1.0, 1) == 8
    assert _upslope_increment(0.0, 0.0, 1.0, 3) == -1
    assert _downslope_increment(-2.0, 0.0, 1.0, 2) == 5
    assert _downslope_increment(2.0, 0.0, 1.0, 2) == -7


def test_advanced_baseline_removes_signal_penetration():
    time = np.arange(5, dtype=np.float64)
    signal = np.asarray([0.0, 0.2, -1.0, 0.2, 0.0])

    baseline, pegs = _advanced_baseline(time, signal, 0.0, 0.0)

    assert np.all(baseline <= signal + 1e-10)
    assert 2 in pegs


def test_stable_window_must_be_flat_and_return_to_tracked_baseline():
    flat_at_peak_top = np.asarray([0.0, 10.0, 10.0, 10.0, 10.0])
    returned = np.asarray([10.0, 4.0, 0.2, 0.1, 0.0])

    assert not _stable_baseline_window_surrogate(
        flat_at_peak_top, 4, 3, 1.0, 0.0
    )
    assert _stable_baseline_window_surrogate(returned, 4, 3, 1.0, 0.0)


def test_candidate_integrates_raw_gaussian_and_stays_explicitly_non_vendor():
    time = np.linspace(0.0, 3.0, 3001)
    signal = 0.1 * time + 100.0 * np.exp(-0.5 * ((time - 1.5) / 0.05) ** 2)

    result = integrate_chemstation_compatible(
        time,
        signal,
        {},
        method_policy=_policy(),
    )

    assert result["status"] == "OK"
    assert result["validation_status"] == "candidate"
    assert result["vendor_equivalent"] is False
    assert result["method_source"]["kind"] == "synthetic_pmx"
    assert result["peak_count"] == 1
    assert result["peaks"][0]["retention_time_min"] == pytest.approx(1.5, abs=0.002)
    assert result["peaks"][0]["area_unit"] == "mAU*s"


def test_candidate_fails_explicitly_for_pmx_feature_it_cannot_reproduce():
    time = np.linspace(0.0, 1.0, 101)
    signal = np.zeros_like(time)
    policy = _policy()
    policy["shoulders_mode"] = "ON"

    with pytest.raises(NotImplementedError, match="shoulders"):
        integrate_chemstation_compatible(
            time,
            signal,
            {},
            method_policy=policy,
        )


def test_candidate_rejects_invalid_numeric_and_baseline_policy():
    time = np.linspace(0.0, 1.0, 101)
    signal = np.zeros_like(time)
    policy = _policy()
    policy["initial_peak_width_min"] = float("nan")
    with pytest.raises(ValueError, match="initial_peak_width_min"):
        integrate_chemstation_compatible(time, signal, {}, method_policy=policy)

    policy = _policy()
    policy["baseline_correction"] = "Standard"
    with pytest.raises(NotImplementedError, match="baseline correction"):
        integrate_chemstation_compatible(time, signal, {}, method_policy=policy)
