from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    PROJECT_ROOT
    / "scripts"
    / "data_types"
    / "hplc_lc"
    / "compare_chemstation_candidate.py"
)
SPEC = importlib.util.spec_from_file_location("hplc_chemstation_comparison", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def test_historical_improvement_still_cannot_auto_promote_without_fresh_blind_data():
    native = _report(p95=10.0, maximum=30.0, absolute_p95=3.0, over15=1)
    candidate = _report(p95=5.0, maximum=20.0, absolute_p95=2.0, over15=0)

    result = comparison._comparison(native, candidate, _pmx_audit())

    assert result["historical_nonregression_passed"] is True
    assert result["promotion_gates"]["fresh_blind_confirmation_present"] is False
    assert result["candidate_promoted"] is False
    assert result["validation_outcome"].endswith("blind_pending")


def test_zero_match_candidate_is_rejected_without_none_metric_crash():
    native = _report(p95=10.0, maximum=30.0, absolute_p95=3.0, over15=1)
    candidate = _report(
        p95=None,
        maximum=None,
        absolute_p95=None,
        over15=0,
        matched=0,
        passed=False,
    )

    result = comparison._comparison(native, candidate, _pmx_audit())

    assert result["historical_nonregression_passed"] is False
    assert result["candidate_promoted"] is False
    assert result["validation_outcome"] == "completed_candidate_rejected"


def _report(
    *,
    p95: float | None,
    maximum: float | None,
    absolute_p95: float | None,
    over15: int,
    matched: int = 10,
    passed: bool = True,
) -> dict:
    metric = {"n": matched, "median": p95, "p90": p95, "p95": p95, "p99": p95, "max": maximum}
    absolute = {
        "n": matched,
        "median": absolute_p95,
        "p90": absolute_p95,
        "p95": absolute_p95,
        "p99": absolute_p95,
        "max": absolute_p95,
    }
    return {
        "passed": passed,
        "summary": {
            "vendor_validation_injections": 2,
            "vendor_peak_rows": 10,
            "detection_disagreements": 0,
        },
        "validation_snapshot": {"fingerprint_sha256": "SAME"},
        "native_all_peak_validation": {
            "unmatched_native_peak_count": 0,
            "unmatched_vendor_peak_count": 0,
            "metrics": {
                "all": {
                    "matched_peak_count": matched,
                    "area_ape_percent": metric,
                    "area_absolute_error_mau_s": absolute,
                    "area_ape_over_15_percent_count": over15,
                }
            },
        },
        "native_target_validation": {
            "holdout": {
                "targets": {
                    "target": {
                        "area_ape_percent": {"p95": p95},
                        "rt_abs_error_min": {"p95": 0.001},
                    }
                }
            }
        },
    }


def _pmx_audit() -> dict:
    return {
        "all_pmx_files_parsed": True,
        "unique_integration_policy_count": 1,
        "vendor_validation_result_set_pmx_coverage_complete": True,
    }
