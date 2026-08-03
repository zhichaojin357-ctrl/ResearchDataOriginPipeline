from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "data_types"
    / "hplc_lc"
    / "compare_pmx_hybrid_candidate.py"
)
SPEC = importlib.util.spec_from_file_location("hplc_pmx_hybrid_comparison", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def test_absolute_non_target_regression_rejects_relative_improvement():
    native = _report(relative_p95=30.0, absolute_p95=7.0, over15=100)
    candidate = _report(relative_p95=28.0, absolute_p95=8.0, over15=90)

    result = comparison._comparison(native, candidate, _pmx_audit())

    assert result["promotion_gates"]["material_non_target_improvement_present"]
    assert not result["promotion_gates"][
        "non_target_absolute_area_p95_noninferior"
    ]
    assert result["historical_nonregression_passed"] is False
    assert result["candidate_promoted"] is False
    assert result["validation_outcome"] == "completed_candidate_rejected"


def test_target_row_change_rejects_otherwise_noninferior_candidate():
    native = _report(relative_p95=30.0, absolute_p95=7.0, over15=100)
    candidate = _report(relative_p95=29.0, absolute_p95=6.0, over15=90)
    candidate["native_target_validation_rows"][0]["native_area"] = 99.0

    result = comparison._comparison(native, candidate, _pmx_audit())

    assert result["promotion_gates"]["target_rows_bit_identical"] is False
    assert result["historical_nonregression_passed"] is False
    assert result["candidate_promoted"] is False


def test_historical_pass_still_requires_fresh_blind_confirmation():
    native = _report(relative_p95=30.0, absolute_p95=7.0, over15=100)
    candidate = _report(relative_p95=29.0, absolute_p95=6.0, over15=90)

    result = comparison._comparison(native, candidate, _pmx_audit())

    assert result["historical_nonregression_passed"] is True
    assert result["promotion_gates"]["fresh_blind_confirmation_present"] is False
    assert result["candidate_promoted"] is False
    assert result["validation_outcome"].endswith("blind_pending")


def _report(
    *,
    relative_p95: float,
    absolute_p95: float,
    over15: int,
) -> dict:
    relative = {
        "n": 10,
        "median": relative_p95 / 2,
        "p90": relative_p95,
        "p95": relative_p95,
        "p99": relative_p95,
        "max": relative_p95 + 10,
    }
    absolute = {
        "n": 10,
        "median": absolute_p95 / 2,
        "p90": absolute_p95,
        "p95": absolute_p95,
        "p99": absolute_p95,
        "max": absolute_p95 + 10,
    }
    all_metrics = {
        "matched_peak_count": 10,
        "area_ape_percent": deepcopy(relative),
        "area_absolute_error_mau_s": deepcopy(absolute),
        "area_ape_over_15_percent_count": over15,
    }
    return {
        "passed": True,
        "summary": {
            "rx_processed_injection_count": 2,
            "vendor_peak_injection_count": 2,
            "vendor_peak_rows": 10,
            "detection_disagreements": 0,
        },
        "validation_snapshot": {"fingerprint_sha256": "SAME"},
        "integrator_runtime_audit": {
            "changed_peak_count": 1,
            "hybrid_decision_counts": {"refined_pmx_confirmed_block": 1},
            "confirmed_accumulator_block_count": 1,
        },
        "native_target_validation_rows": [
            {
                "injection_id": "I001",
                "target_key": "target",
                "native_area": 10.0,
                "native_rt_min": 5.0,
            }
        ],
        "native_all_peak_validation": {
            "unmatched_native_peak_count": 0,
            "unmatched_vendor_peak_count": 0,
            "metrics": {"all": deepcopy(all_metrics)},
            "non_target_metrics": {"all": deepcopy(all_metrics)},
        },
    }


def _pmx_audit() -> dict:
    return {
        "all_pmx_files_parsed": True,
        "unique_integration_policy_count": 1,
        "vendor_validation_result_set_pmx_coverage_complete": True,
    }
