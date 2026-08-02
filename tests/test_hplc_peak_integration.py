from __future__ import annotations

import numpy as np
import pytest

from src.core.hplc_peak_integration import (
    NATIVE_INTEGRATOR_NAME,
    NATIVE_INTEGRATOR_VERSION,
    _allocate_shared_cluster_baselines,
    integrate_chromatogram,
    match_native_target_peaks,
)


def _config() -> dict:
    return {
        "native_integration": {
            "smoothing_window_points": 9,
            "smoothing_polyorder": 3,
            "morphology_half_window_min": 0.40,
            "minimum_corrected_height_mau": 1.70,
            "minimum_area_mau_s": 1.0,
            "minimum_peak_width_min": 0.02,
        }
    }


def _targets() -> dict:
    return {
        "sulfoxide": {
            "display_name": "茴香亚砜",
            "nominal_rt_min": 5.50,
            "rt_tolerance_min": 0.30,
        },
        "sulfone": {
            "display_name": "茴香砜",
            "nominal_rt_min": 7.34,
            "rt_tolerance_min": 0.30,
        },
        "thioanisole": {
            "display_name": "茴香硫醚",
            "nominal_rt_min": 16.52,
            "rt_tolerance_min": 0.30,
        },
    }


def _gaussian(time: np.ndarray, center: float, height: float, sigma: float) -> np.ndarray:
    return height * np.exp(-0.5 * ((time - center) / sigma) ** 2)


def test_native_integrator_detects_targets_and_preserves_numeric_peak_trace():
    time = np.arange(0.0, 20.0, 0.005)
    signal = 0.08 * np.sin(time * 1.7)
    for center, height, sigma in (
        (3.0, 2.2, 0.07),
        (5.51, 12.0, 0.09),
        (7.32, 5.0, 0.08),
        (16.50, 20.0, 0.10),
        (18.5, 2.3, 0.07),
    ):
        signal += _gaussian(time, center, height, sigma)

    result = integrate_chromatogram(time, signal, _config())
    matched = match_native_target_peaks(
        result["peaks"],
        _targets(),
        ambiguity_margin_min=0.02,
        signal_quantifiable=True,
    )

    assert result["integrator_name"] == NATIVE_INTEGRATOR_NAME
    assert result["integrator_version"] == NATIVE_INTEGRATOR_VERSION
    assert result["status"] == "OK"
    assert result["peak_count"] >= 5
    for key, expected_rt in (
        ("sulfoxide", 5.51),
        ("sulfone", 7.32),
        ("thioanisole", 16.50),
    ):
        target = matched[key]
        assert target["peak_source"] == "native_dx"
        assert target["selected_peak_ordinal"] is not None
        assert target["retention_time_min"] == pytest.approx(expected_rt, abs=0.006)
        assert target["area"] > 1.0
        assert target["begin_time_min"] < target["retention_time_min"]
        assert target["end_time_min"] > target["retention_time_min"]
        assert target["match_status"] == "RT窗口匹配"


def test_adjacent_peaks_share_outer_baseline_and_use_valley_drop_line():
    time = np.arange(0.0, 5.0, 0.005)
    signal = 0.02 * np.sin(time * 3.0)
    signal += _gaussian(time, 2.00, 10.0, 0.08)
    signal += _gaussian(time, 2.40, 9.0, 0.09)

    result = integrate_chromatogram(time, signal, _config())
    cluster = [
        peak
        for peak in result["peaks"]
        if peak["baseline_allocation"] == "shared_cluster_valley_drop"
    ]

    assert result["shared_baseline_cluster_count"] == 1
    assert len(cluster) == 2
    assert cluster[0]["end_index"] == cluster[1]["begin_index"]
    assert [peak["baseline_cluster_position"] for peak in cluster] == [1, 2]
    assert {peak["baseline_cluster_size"] for peak in cluster} == {2}
    assert len({peak["baseline_cluster_id"] for peak in cluster}) == 1
    assert all(peak["baseline_model_uncertain"] for peak in cluster)
    assert all(peak["individual_baseline_area"] is not None for peak in cluster)
    assert cluster[0]["baseline_end"] == pytest.approx(cluster[1]["baseline_start"])

    outer_time = (cluster[0]["begin_time_min"], cluster[-1]["end_time_min"])
    outer_baseline = (cluster[0]["baseline_start"], cluster[-1]["baseline_end"])
    valley_index = int(cluster[0]["end_index"])
    expected_valley_baseline = float(
        np.interp(time[valley_index], outer_time, outer_baseline)
    )
    assert cluster[0]["baseline_end"] == pytest.approx(expected_valley_baseline)
    assert signal[valley_index] > expected_valley_baseline

    for peak in cluster:
        begin = int(peak["begin_index"])
        end = int(peak["end_index"])
        segment_time = time[begin : end + 1]
        common_line = np.interp(segment_time, outer_time, outer_baseline)
        expected_area = float(
            np.trapezoid(signal[begin : end + 1] - common_line, segment_time) * 60.0
        )
        assert peak["area"] == pytest.approx(expected_area)
        assert peak["baseline_model"].endswith("valley drop-line")


def test_shared_boundary_does_not_create_drop_line_below_the_signal_baseline():
    time = np.arange(5.0)
    signal = np.asarray([0.0, 5.0, -1.0, 4.0, 0.0])
    peaks = [
        {
            "begin_index": 0,
            "end_index": 2,
            "baseline_start": 0.0,
            "baseline_end": -1.0,
            "baseline_allocation": "individual_peak",
        },
        {
            "begin_index": 2,
            "end_index": 4,
            "baseline_start": -1.0,
            "baseline_end": 0.0,
            "baseline_allocation": "individual_peak",
        },
    ]

    count = _allocate_shared_cluster_baselines(
        time,
        signal,
        peaks,
        minimum_area=1.0,
    )

    assert count == 0
    assert [peak["baseline_allocation"] for peak in peaks] == [
        "individual_peak",
        "individual_peak",
    ]


def test_target_match_never_uses_a_window_edge_as_a_peak_fallback():
    time = np.arange(0.0, 10.0, 0.005)
    signal = _gaussian(time, 5.19, 20.0, 0.05) + 0.01 * np.sin(time)

    result = integrate_chromatogram(time, signal, _config())
    target = match_native_target_peaks(
        result["peaks"],
        {"sulfoxide": _targets()["sulfoxide"]},
        ambiguity_margin_min=0.02,
        signal_quantifiable=True,
    )["sulfoxide"]

    assert target["selected_peak_ordinal"] is None
    assert target["retention_time_min"] is None
    assert target["area"] == 0.0
    assert target["match_status"] == "正常未检出"


def test_multiple_target_candidates_are_auditable_and_can_be_ambiguous():
    peaks = [
        {
            "peak_ordinal": ordinal,
            "retention_time_min": retention_time,
            "area": area,
            "begin_time_min": retention_time - 0.1,
            "end_time_min": retention_time + 0.1,
            "height": area / 2,
            "baseline_start": 0.0,
            "baseline_end": 0.0,
            "integrator_name": NATIVE_INTEGRATOR_NAME,
            "integrator_version": NATIVE_INTEGRATOR_VERSION,
        }
        for ordinal, retention_time, area in (
            (4, 5.48, 10.0),
            (5, 5.52, 20.0),
        )
    ]

    target = match_native_target_peaks(
        peaks,
        {"sulfoxide": _targets()["sulfoxide"]},
        ambiguity_margin_min=0.02,
        signal_quantifiable=True,
    )["sulfoxide"]

    assert target["selected_peak_ordinal"] == 4
    assert target["candidate_peak_ordinals"] == [4, 5]
    assert target["candidate_retention_times_min"] == [5.48, 5.52]
    assert target["ambiguous"] is True
    assert target["match_status"] == "目标峰匹配存在歧义"


def test_missing_target_is_not_zero_when_signal_is_not_quantifiable():
    target = match_native_target_peaks(
        [],
        {"sulfone": _targets()["sulfone"]},
        ambiguity_margin_min=0.02,
        signal_quantifiable=False,
    )["sulfone"]

    assert target["area"] is None
    assert target["match_status"] == "数据异常导致无法定量"


@pytest.mark.parametrize(
    ("time", "signal", "expected"),
    [
        ([0, 1], [0], "equal one-dimensional"),
        ([0, 1, 2, 3], [0, 1, 2, 3], "at least five"),
        ([0, 1, 2, 3, 4], [0, 1, np.nan, 3, 4], "finite"),
        ([0, 1, 1, 3, 4], [0, 1, 2, 3, 4], "strictly increasing"),
    ],
)
def test_native_integrator_rejects_invalid_signal(time, signal, expected):
    with pytest.raises(ValueError, match=expected):
        integrate_chromatogram(time, signal, _config())
