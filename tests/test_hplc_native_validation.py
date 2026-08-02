from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "data_types"
    / "hplc_lc"
    / "validate_native_peak_integration.py"
)
SPEC = importlib.util.spec_from_file_location("hplc_native_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_result_set_split_rejects_cross_boundary_leakage():
    injections = [
        {
            "injection_id": "one",
            "result_set_id": "shared-result",
            "acquisition_date": "2026-07-21",
        },
        {
            "injection_id": "two",
            "result_set_id": "shared-result",
            "acquisition_date": "2026-07-23",
        },
    ]

    with pytest.raises(ValueError, match="cross validation split boundaries"):
        validator._result_set_splits(
            injections,
            train_end=date(2026, 7, 21),
            holdout_start=date(2026, 7, 23),
        )


def test_empty_validation_metrics_cannot_pass_a_gate():
    metrics = validator._error_metrics([])

    assert metrics["n"] == 0
    assert metrics["p95"] is None
    assert validator._safe_ratio(0, 0) is None
    assert validator._metric_at_most(metrics, "p95", 0.1) is False
    assert validator._at_least(None, 0.99) is False


def test_all_peak_matching_is_one_to_one_and_rt_limited():
    native = [
        {"peak_ordinal": 1, "retention_time_min": 1.01, "area": 11.0},
        {"peak_ordinal": 2, "retention_time_min": 2.20, "area": 20.0},
    ]
    vendor = [
        {"peak_ordinal": 4, "retention_time_min": 1.00, "area": 10.0},
        {"peak_ordinal": 5, "retention_time_min": 2.00, "area": 20.0},
    ]

    matches, unmatched_native, unmatched_vendor = validator._match_all_peaks(
        native,
        vendor,
        maximum_rt_error_min=0.03,
    )

    assert len(matches) == 1
    assert matches[0]["native_peak_ordinal"] == 1
    assert matches[0]["vendor_peak_ordinal"] == 4
    assert matches[0]["area_ape_percent"] == pytest.approx(10.0)
    assert unmatched_native == 1
    assert unmatched_vendor == 1
