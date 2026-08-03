from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data_types.hplc_lc.validate_native_peak_integration import (  # noqa: E402
    validate_native_integration,
)
from src.core.agilent_pmx import read_uniform_pmx_integration_policy  # noqa: E402
from src.core.file_utils import (  # noqa: E402
    ensure_safe_output_file_target,
    lexical_absolute_path,
    prepare_safe_output_file_targets,
)
from src.core.hplc_pmx_hybrid_integration import (  # noqa: E402
    PMX_HYBRID_INTEGRATOR_NAME,
    PMX_HYBRID_INTEGRATOR_VERSION,
    integrate_pmx_constrained_hybrid,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the production HPLC integrator with the strictly gated, "
            "PMX-constrained native-boundary hybrid candidate."
        )
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--since", type=date.fromisoformat, default=date(2026, 7, 17))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_dir = lexical_absolute_path(args.output_dir)
    _validate_paths(input_root, output_dir)
    targets = {
        "native": output_dir / "native_validation.json",
        "candidate": output_dir / "pmx_hybrid_candidate_validation.json",
        "comparison": output_dir / "comparison.json",
        "metadata": output_dir / "metadata.json",
    }
    planned_targets = tuple(
        ensure_safe_output_file_target(path, output_root=output_dir)
        for path in targets.values()
    )
    existing = [path for path in planned_targets if path.exists()]
    if existing and not args.force:
        raise FileExistsError(
            "comparison outputs already exist; pass --force to replace: "
            + ", ".join(path.name for path in existing)
        )

    policy, pmx_audit = read_uniform_pmx_integration_policy(input_root)

    def candidate_integrator(
        time: Any,
        signal: Any,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        return integrate_pmx_constrained_hybrid(
            time,
            signal,
            config,
            method_policy=policy,
        )

    native = validate_native_integration(input_root, since=args.since)
    _require_local_pmx_coverage(native, pmx_audit)
    candidate = validate_native_integration(
        input_root,
        since=args.since,
        integrator=candidate_integrator,
        integrator_descriptor={
            "name": PMX_HYBRID_INTEGRATOR_NAME,
            "version": PMX_HYBRID_INTEGRATOR_VERSION,
            "vendor_method_required": True,
            "vendor_code_executed": False,
            "validation_status": "candidate",
            "vendor_equivalent": False,
            "production_enabled": False,
            "method_source": policy["method_source"],
        },
    )
    comparison = _comparison(native, candidate, pmx_audit)

    prepare_safe_output_file_targets(
        planned_targets,
        output_root=output_dir,
        force=args.force,
        context="HPLC PMX hybrid candidate comparison",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(targets["native"], native)
    _write_json(targets["candidate"], candidate)
    _write_json(targets["comparison"], comparison)
    metadata = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "workflow": "hplc_pmx_constrained_hybrid_candidate_comparison",
        "status": comparison["validation_outcome"],
        "input_root_name": input_root.name,
        "raw_input_modified": False,
        "pmx_files_parsed": pmx_audit["pmx_file_count"],
        "candidate_promoted": comparison["candidate_promoted"],
        "production_integrator_changed": False,
        "manual_check_required": True,
        "scientific_claim": "none",
        "artifacts": {
            key: {"name": path.name, "sha256": _sha256(path)}
            for key, path in targets.items()
            if key != "metadata"
        },
    }
    _write_json(targets["metadata"], metadata)
    print(json.dumps(comparison["summary"], ensure_ascii=False, indent=2))
    print(f"comparison: {targets['comparison']}")
    return 0


def _require_local_pmx_coverage(
    native: dict[str, Any],
    pmx_audit: dict[str, Any],
) -> None:
    vendor_result_sets = set(
        native["validation_snapshot"]["vendor_validation_result_set_relatives"]
    )
    pmx_result_sets = set(pmx_audit["pmx_result_set_relatives"])
    missing = sorted(vendor_result_sets - pmx_result_sets)
    if missing:
        raise ValueError(
            "vendor-validation result sets have no local PMX method: "
            + ", ".join(missing)
        )
    pmx_audit["vendor_validation_result_set_count"] = len(vendor_result_sets)
    pmx_audit["vendor_validation_result_sets_without_local_pmx"] = []
    pmx_audit["vendor_validation_result_set_pmx_coverage_complete"] = True


def _comparison(
    native: dict[str, Any],
    candidate: dict[str, Any],
    pmx_audit: dict[str, Any],
) -> dict[str, Any]:
    native_validation = native["native_all_peak_validation"]
    candidate_validation = candidate["native_all_peak_validation"]
    native_all = native_validation["metrics"]["all"]
    candidate_all = candidate_validation["metrics"]["all"]
    native_non_target = native_validation["non_target_metrics"]["all"]
    candidate_non_target = candidate_validation["non_target_metrics"]["all"]
    target_rows_identical = (
        native["native_target_validation_rows"]
        == candidate["native_target_validation_rows"]
    )
    gates = {
        "all_pmx_files_parsed": bool(pmx_audit["all_pmx_files_parsed"]),
        "one_effective_pmx_policy": (
            int(pmx_audit["unique_integration_policy_count"]) == 1
        ),
        "vendor_result_set_pmx_coverage_complete": bool(
            pmx_audit["vendor_validation_result_set_pmx_coverage_complete"]
        ),
        "paired_input_snapshot_identical": (
            native["validation_snapshot"]["fingerprint_sha256"]
            == candidate["validation_snapshot"]["fingerprint_sha256"]
        ),
        "candidate_acceptance_passed": bool(candidate["passed"]),
        "target_rows_bit_identical": target_rows_identical,
        "detection_disagreement_count_equal": (
            candidate["summary"]["detection_disagreements"]
            == native["summary"]["detection_disagreements"]
        ),
        "matched_peak_count_equal": (
            candidate_all["matched_peak_count"] == native_all["matched_peak_count"]
        ),
        "unmatched_native_peak_count_equal": (
            candidate_validation["unmatched_native_peak_count"]
            == native_validation["unmatched_native_peak_count"]
        ),
        "unmatched_vendor_peak_count_equal": (
            candidate_validation["unmatched_vendor_peak_count"]
            == native_validation["unmatched_vendor_peak_count"]
        ),
        "non_target_area_p95_noninferior": _metric_le(
            candidate_non_target["area_ape_percent"]["p95"],
            native_non_target["area_ape_percent"]["p95"],
        ),
        "non_target_area_max_noninferior": _metric_le(
            candidate_non_target["area_ape_percent"]["max"],
            native_non_target["area_ape_percent"]["max"],
        ),
        "non_target_area_over_15_count_noninferior": (
            candidate_non_target["area_ape_over_15_percent_count"]
            <= native_non_target["area_ape_over_15_percent_count"]
        ),
        "non_target_absolute_area_p95_noninferior": _metric_le(
            candidate_non_target["area_absolute_error_mau_s"]["p95"],
            native_non_target["area_absolute_error_mau_s"]["p95"],
        ),
        "material_non_target_improvement_present": _material_improvement_present(
            native_non_target,
            candidate_non_target,
        ),
        "fresh_blind_confirmation_present": False,
    }
    historical_gates = {
        key: value
        for key, value in gates.items()
        if key != "fresh_blind_confirmation_present"
    }
    historical_nonregression_passed = all(historical_gates.values())
    promoted = historical_nonregression_passed and gates[
        "fresh_blind_confirmation_present"
    ]
    outcome = (
        "completed_historical_nonregression_passed_blind_pending"
        if historical_nonregression_passed
        else "completed_candidate_rejected"
    )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "candidate_promoted": promoted,
        "historical_nonregression_passed": historical_nonregression_passed,
        "validation_outcome": outcome,
        "production_integrator_changed": False,
        "vendor_values_used_for_runtime_decision": False,
        "promotion_gates": gates,
        "pmx_audit": pmx_audit,
        "summary": {
            "rx_processed_injection_count": native["summary"][
                "rx_processed_injection_count"
            ],
            "vendor_peak_injection_count": native["summary"][
                "vendor_peak_injection_count"
            ],
            "vendor_peak_rows": native["summary"]["vendor_peak_rows"],
            "candidate_changed_peak_count": candidate[
                "integrator_runtime_audit"
            ]["changed_peak_count"],
            "candidate_hybrid_decision_counts": candidate[
                "integrator_runtime_audit"
            ]["hybrid_decision_counts"],
            "candidate_confirmed_accumulator_block_count": candidate[
                "integrator_runtime_audit"
            ]["confirmed_accumulator_block_count"],
            "native_matched_peak_count": native_all["matched_peak_count"],
            "candidate_matched_peak_count": candidate_all["matched_peak_count"],
            "native_all_peak_area_median_ape_percent": native_all[
                "area_ape_percent"
            ]["median"],
            "candidate_all_peak_area_median_ape_percent": candidate_all[
                "area_ape_percent"
            ]["median"],
            "native_all_peak_area_p95_ape_percent": native_all[
                "area_ape_percent"
            ]["p95"],
            "candidate_all_peak_area_p95_ape_percent": candidate_all[
                "area_ape_percent"
            ]["p95"],
            "native_non_target_area_p95_ape_percent": native_non_target[
                "area_ape_percent"
            ]["p95"],
            "candidate_non_target_area_p95_ape_percent": candidate_non_target[
                "area_ape_percent"
            ]["p95"],
            "native_non_target_absolute_area_p95_mau_s": native_non_target[
                "area_absolute_error_mau_s"
            ]["p95"],
            "candidate_non_target_absolute_area_p95_mau_s": candidate_non_target[
                "area_absolute_error_mau_s"
            ]["p95"],
            "native_non_target_area_over_15_percent_count": native_non_target[
                "area_ape_over_15_percent_count"
            ],
            "candidate_non_target_area_over_15_percent_count": (
                candidate_non_target["area_ape_over_15_percent_count"]
            ),
            "target_rows_bit_identical": target_rows_identical,
            "candidate_promoted": promoted,
        },
        "decision": (
            "retain production native integrator; fresh blind confirmation required"
            if historical_nonregression_passed
            else (
                "retain production native integrator; hybrid failed strict "
                "non-regression"
            )
        ),
        "limitations": [
            (
                "Agilent does not publish the exact recognition-filter coefficients "
                "or normalization."
            ),
            (
                "The PMX PeakWidth dynamic update remains an independent "
                "compatibility interpretation."
            ),
            (
                "The historical holdout has already been inspected and cannot be "
                "a fresh blind test."
            ),
            (
                "PMX supplies declarative method settings, not the proprietary "
                "integration engine."
            ),
            (
                "Vendor rows are validation evidence only and never select a "
                "runtime branch."
            ),
        ],
    }


def _material_improvement_present(
    native: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    comparisons = (
        (
            candidate["area_ape_percent"]["p95"],
            native["area_ape_percent"]["p95"],
        ),
        (
            candidate["area_ape_percent"]["max"],
            native["area_ape_percent"]["max"],
        ),
        (
            candidate["area_ape_over_15_percent_count"],
            native["area_ape_over_15_percent_count"],
        ),
        (
            candidate["area_absolute_error_mau_s"]["p95"],
            native["area_absolute_error_mau_s"]["p95"],
        ),
    )
    return any(
        candidate_value is not None
        and native_value is not None
        and float(candidate_value) < float(native_value)
        for candidate_value, native_value in comparisons
    )


def _metric_le(candidate: Any, native: Any) -> bool:
    return (
        candidate is not None
        and native is not None
        and float(candidate) <= float(native)
    )


def _validate_paths(input_root: Path, output_dir: Path) -> None:
    if not input_root.is_dir():
        raise NotADirectoryError(input_root)
    if _is_within(output_dir, input_root):
        raise ValueError("comparison output must not be inside the raw input tree")
    if _is_within(output_dir, PROJECT_ROOT):
        raise ValueError("comparison output must be outside the project source tree")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


if __name__ == "__main__":
    raise SystemExit(main())
