from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.hplc_openlab import extract_hplc_openlab_dataset
from src.core.hplc_openlab_vendor import (
    compare_vendor_peak_datasets,
    reprocess_openlab_with_vendor_method,
    resolve_bundled_openlab_vendor_assets,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Agilent Processing Server on copied OpenLab data and write a JSON-only "
            "feasibility/equivalence report. No Excel or plot is created."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--since", required=True, type=date.fromisoformat)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--require-stored-equivalence",
        action="store_true",
        help="fail unless newly generated vendor peaks are bit-exact to stored successful RX peaks",
    )
    parser.add_argument("--vendor-runtime-bin", type=Path)
    parser.add_argument("--vendor-bridge-exe", type=Path)
    parser.add_argument("--vendor-processing-method", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_root = args.input.resolve()
    output_root = args.output_root.resolve()
    if not source_root.is_dir():
        raise NotADirectoryError(f"OpenLab input root does not exist: {source_root}")
    if output_root.exists():
        raise FileExistsError(f"Feasibility output root already exists: {output_root}")
    if source_root == output_root or source_root in output_root.parents or output_root in source_root.parents:
        raise ValueError("Feasibility output root must be separate from the OpenLab input")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be greater than zero")

    overrides = (
        args.vendor_runtime_bin,
        args.vendor_bridge_exe,
        args.vendor_processing_method,
    )
    if any(value is not None for value in overrides) and any(value is None for value in overrides):
        raise ValueError("Vendor runtime overrides must be supplied together")
    if all(value is None for value in overrides):
        assets = resolve_bundled_openlab_vendor_assets()
        runtime_bin = assets.runtime_bin
        bridge_exe = assets.bridge_exe
        processing_method = assets.processing_method
        runtime_source = "project_bundled_hash_verified_archive"
        runtime_archive_sha256 = assets.archive_sha256
    else:
        runtime_bin, bridge_exe, processing_method = (
            value.resolve() for value in overrides if value is not None
        )
        runtime_source = "explicit_complete_override"
        runtime_archive_sha256 = None

    output_root.mkdir(parents=True)
    staged_input_root = output_root / "staged_input"
    report_path = output_root / "vendor_reprocessing_feasibility.json"
    reference = extract_hplc_openlab_dataset(source_root, args.since)
    vendor_result = reprocess_openlab_with_vendor_method(
        source_root=source_root,
        staged_input_root=staged_input_root,
        dataset=reference,
        runtime_bin=runtime_bin,
        bridge_exe=bridge_exe,
        processing_method=processing_method,
        timeout_seconds=args.timeout_seconds,
    )
    candidate = extract_hplc_openlab_dataset(vendor_result.effective_input_root, args.since)
    comparison = compare_vendor_peak_datasets(reference, candidate)
    stored_peak_count = int(comparison["reference_peak_count"])
    equivalence_applicable = stored_peak_count > 0
    equivalence_passed = bool(
        equivalence_applicable and comparison["all_compared_fields_bit_exact"]
    )

    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "purpose": "Agilent original-integration feasibility; JSON only; no Excel or plot",
        "runtime_source": runtime_source,
        "runtime_archive_sha256": runtime_archive_sha256,
        "vendor_reprocessing": vendor_result.manifest,
        "stored_result_equivalence": {
            "applicable": equivalence_applicable,
            "passed": equivalence_passed,
            **comparison,
        },
        "new_vendor_peak_count": int(candidate["summary"]["peak_count"]),
        "source_input_unchanged": bool(vendor_result.manifest["source_input_unchanged"]),
        "excel_created": False,
        "plot_created": False,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"report={report_path}")
    print(f"vendor_injections={vendor_result.manifest['completed_injection_count']}")
    print(f"new_vendor_peaks={candidate['summary']['peak_count']}")
    print(f"stored_equivalence_applicable={str(equivalence_applicable).lower()}")
    print(f"stored_equivalence_passed={str(equivalence_passed).lower()}")
    if args.require_stored_equivalence and not equivalence_passed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
