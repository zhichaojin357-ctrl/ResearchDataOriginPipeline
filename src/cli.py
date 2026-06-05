from __future__ import annotations

import argparse
from pathlib import Path

from src.core.deps import dependency_audit
from src.core.auto_queue import AutoQueueOptions, run_auto_queue
from src.core.epr_jeol import export_jeol_cwesr_to_xlsx
from src.core.epr_overlay import EprOverlayOptions, run_epr_overlay
from src.core.manifest_normalizer import normalize_material_collection_manifest
from src.core.origin_batch import OriginBatchOptions, run_origin_batch
from src.core.opju_product_pilot import OpjuProductPilotOptions, run_opju_product_pilot
from src.core.phase1_9 import DEFAULT_ORIGIN_SKILL_DIR, DEFAULT_PHASE1_6_PACKAGE, run_phase1_9_governance
from src.core.process import ProcessOptions, run_process
from src.core.project import configured_path, load_project_config
from src.core.readiness import ReadinessOptions, run_readiness
from src.core.remaining_opju_product_drafts import RemainingOpjuProductDraftOptions, run_remaining_opju_product_drafts
from src.core.reviewed_queue import ReviewedQueueOptions, run_reviewed_queue
from src.core.runtime_paths import resolve_output_root
from src.core.triage import TriageOptions, run_triage
from src.core.validate import validate
from src.core.v2_exemplar_conformance import (
    EisRandlesCpeV2Options,
    UnifiedV2ExemplarConformanceOptions,
    V2ExemplarConformanceOptions,
    run_eis_randles_cpe_v2,
    run_unified_v2_exemplar_conformance_products,
    run_v2_exemplar_conformance_products,
)
from src.core.xps_heterojunction import XpsHeterojunctionOptions, discover_default_xps_sample_files, run_xps_heterojunction_stacked
from src.origin.adapter import origin_smoke_test
from src.scanner.scanner import scan_raw_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--input")
    scan.add_argument("--config", default="config/default.yaml")
    scan.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    process = subparsers.add_parser("process")
    process.add_argument("--input")
    process.add_argument("--config", default="config/default.yaml")
    process.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")
    origin_mode = process.add_mutually_exclusive_group()
    origin_mode.add_argument("--no-origin", action="store_true", help="process tables and metadata without launching Origin")
    origin_mode.add_argument("--with-origin", action="store_true", help="explicitly allow Origin export for this processing run")
    process.add_argument("--only-type", help="process only one inferred data type, for example XRD or EIS")
    process.add_argument("--only-folder", help="process only one raw_data folder name or relative path")
    process.add_argument("--fail-fast", action="store_true", help="stop on the first failed dataset")
    process.add_argument("--force", action="store_true", help="allow overwriting same-name output artifacts under output/")
    process.add_argument(
        "--from-queue",
        type=Path,
        help="process only items from an explicit vetted queue; for current AUTO_PROCESS candidates prefer output/reports/phase1_8_new_auto_process_queue.json",
    )
    process.add_argument(
        "--auto-select",
        action="store_true",
        help="legacy shortcut: run triage then process AUTO_PROCESS items; for current Phase 1.8 work prefer auto-queue dry-run plus an explicit vetted queue",
    )
    process.add_argument("--include-ambiguous", action="store_true", help="allow MANUAL_REVIEW queue items to be processed")

    triage = subparsers.add_parser("triage")
    triage.add_argument("--input")
    triage.add_argument("--config", default="config/default.yaml")
    triage.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")
    triage.add_argument("--only-type")
    triage.add_argument("--only-folder")
    triage.add_argument("--min-confidence", type=float, default=0.75)
    triage.add_argument("--explain", action="store_true")
    triage.add_argument("--force-refresh", action="store_true")
    triage.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("origin-test")

    opju_product_pilot = subparsers.add_parser(
        "opju-product-pilot",
        help="generate scoped OPJU/TIF/PNG pilot products from reviewed OPJU/data pairings",
    )
    opju_product_pilot.add_argument("--pairing", type=Path, required=True, help="OPJU/data pairing plan JSON from the reviewed pilot")
    opju_product_pilot.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    opju_product_pilot.add_argument("--with-origin", action="store_true", help="launch isolated Origin COM and export OPJU/TIF/PNG")
    opju_product_pilot.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")

    remaining_opju = subparsers.add_parser(
        "remaining-opju-product-drafts",
        help="generate remaining OPJU-backed draft products for manual review",
    )
    remaining_opju.add_argument("--pairing", type=Path, required=True, help="OPJU/data pairing plan JSON from the reviewed pilot")
    remaining_opju.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    remaining_opju.add_argument("--with-origin", action="store_true", help="launch isolated Origin COM and export OPJU/TIF/PNG")
    remaining_opju.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    remaining_opju.add_argument("--previous-run-root", type=Path, help="previous completed BET/XPS/XRD/EPR run root for report links")

    v2_products = subparsers.add_parser(
        "v2-exemplar-conformance-products",
        help="regenerate all completed OPJU-backed products with v2 exemplar conformance checks",
    )
    v2_products.add_argument("--pairing", type=Path, required=True, help="OPJU/data pairing plan JSON from the reviewed pilot")
    v2_products.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    v2_products.add_argument("--with-origin", action="store_true", help="launch isolated Origin COM and export OPJU/TIF/PNG")
    v2_products.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    v2_products.add_argument("--first-run-root", type=Path, help="v1 BET/XPS/XRD/EPR run root")
    v2_products.add_argument("--remaining-run-root", type=Path, help="v1 remaining-products run root")
    v2_products.add_argument("--user-style", type=Path, help="optional local user plot-style override YAML")

    eis_v2 = subparsers.add_parser(
        "eis-randles-cpe-v2",
        help="regenerate only the EIS v2 product with Randles-CPE cleaning/fitting",
    )
    eis_v2.add_argument("--pairing", type=Path, required=True, help="OPJU/data pairing plan JSON from the reviewed pilot")
    eis_v2.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    eis_v2.add_argument("--with-origin", action="store_true", help="launch isolated Origin COM and export OPJU/TIF/PNG")
    eis_v2.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    eis_v2.add_argument("--previous-eis-run-root", type=Path, help="v1 remaining-products run root containing EIS")
    eis_v2.add_argument("--user-style", type=Path, help="optional local user plot-style override YAML")

    unified_v2 = subparsers.add_parser(
        "unified-v2-exemplar-conformance-all-types",
        help="regenerate unified v2 products while importing the completed EIS Randles-CPE v2 product without refitting",
    )
    unified_v2.add_argument("--pairing", type=Path, required=True, help="OPJU/data pairing plan JSON from the reviewed pilot")
    unified_v2.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    unified_v2.add_argument("--with-origin", action="store_true", help="launch isolated Origin COM and export non-EIS OPJU/TIF/PNG")
    unified_v2.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    unified_v2.add_argument("--first-run-root", type=Path, help="v1 BET/XPS/XRD/EPR run root")
    unified_v2.add_argument("--remaining-run-root", type=Path, help="v1 remaining-products run root")
    unified_v2.add_argument("--eis-v2-run-root", type=Path, help="completed EIS Randles-CPE v2 run root to import")
    unified_v2.add_argument("--user-style", type=Path, help="optional local user plot-style override YAML")

    origin_batch = subparsers.add_parser(
        "origin-batch",
        help="plan Origin exports from a package manifest; dry-run by default and never launches Origin unless explicitly executed in a future phase",
    )
    origin_batch.add_argument("--manifest", type=Path, required=True, help="package index.csv or compatible manifest")
    origin_batch.add_argument("--dry-run", action="store_true", help="plan only; this is also the default")
    origin_batch.add_argument("--execute", action="store_true", help="request real execution; Phase 1.7 planner will block export")
    origin_batch.add_argument("--with-origin", action="store_true", help="required for future real execution; dry-run never launches Origin")
    origin_batch.add_argument("--only-type", help="include only one data_type from the manifest")
    origin_batch.add_argument("--only-missing", action="store_true", help="plan only entries missing Origin outputs")
    origin_batch.add_argument("--report-json", type=Path, help="optional JSON report path under output/ or docs/")
    origin_batch.add_argument("--report-md", type=Path, help="optional Markdown report path under output/ or docs/")
    origin_batch.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    manifest_normalize = subparsers.add_parser(
        "manifest-normalize",
        help="normalize a material collection index into an origin-batch-compatible manifest without processing data",
    )
    manifest_normalize.add_argument("--manifest", type=Path, required=True, help="material collection index.csv")
    manifest_normalize.add_argument("--output-csv", type=Path, default=Path("output/reports/phase1_10_material_collection_normalized_manifest.csv"))
    manifest_normalize.add_argument("--output-json", type=Path, default=Path("output/reports/phase1_10_material_collection_normalized_manifest.json"))
    manifest_normalize.add_argument("--output-md", type=Path, default=Path("output/reports/phase1_10_material_collection_normalized_manifest.md"))

    reviewed_queue = subparsers.add_parser(
        "reviewed-queue",
        help="build a dry-run queue plan from user-reviewed Phase 1.7 proposal decisions; never launches Origin or process",
    )
    reviewed_queue.add_argument("--proposals", type=Path, required=True, help="Phase 1.7 review-only proposal JSON")
    reviewed_queue.add_argument("--decisions", type=Path, help="Phase 1.8 user decision CSV")
    reviewed_queue.add_argument("--write-template", action="store_true", help="write a blank user decision CSV template")
    reviewed_queue.add_argument("--dry-run", action="store_true", help="plan only; this is the only supported mode")
    reviewed_queue.add_argument("--template-out", type=Path, help="optional template CSV path under output/ or docs/")
    reviewed_queue.add_argument("--report-json", type=Path, help="optional JSON report path under output/ or docs/")
    reviewed_queue.add_argument("--report-md", type=Path, help="optional Markdown report path under output/ or docs/")
    reviewed_queue.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    auto_queue = subparsers.add_parser(
        "auto-queue",
        help="dry-run a no-Origin candidate queue from current AUTO_PROCESS items, excluding Phase 1.6 processed hashes",
    )
    auto_queue.add_argument("--queue", type=Path, default=Path("output/reports/processing_queue.json"))
    auto_queue.add_argument("--workspace-root", type=Path, help="workspace data root; defaults to config/env/autodetected project path")
    auto_queue.add_argument("--processed-index", type=Path, help="Phase 1.6 index.csv or package directory; defaults to config/env/latest package")
    auto_queue.add_argument("--only-type")
    auto_queue.add_argument("--report-json", type=Path)
    auto_queue.add_argument("--report-md", type=Path)
    auto_queue.add_argument("--queue-out", type=Path)
    auto_queue.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    xps_stacked = subparsers.add_parser(
        "xps-heterojunction-stacked",
        help="build BOBC/BC and CWO/BC fitted XPS stacked comparison outputs",
    )
    xps_stacked.add_argument("--bobc", type=Path, nargs="*", help="BOBC fitted XPS Excel workbook(s)")
    xps_stacked.add_argument("--cwo", type=Path, nargs="*", help="CWO fitted XPS Excel workbook(s)")
    xps_stacked.add_argument("--bc", type=Path, nargs="*", help="BC fitted XPS Excel workbook(s)")
    xps_stacked.add_argument("--output-dir", type=Path, default=Path("output/xps_heterojunction_stacked"))
    xps_origin = xps_stacked.add_mutually_exclusive_group()
    xps_origin.add_argument("--dry-run", action="store_true", help="parse data, write tables/reports, but do not launch Origin")
    xps_origin.add_argument("--with-origin", action="store_true", help="explicitly launch Origin COM and export OPJU/TIF")
    xps_stacked.add_argument("--no-bc-candidate", action="store_true", help="do not use the detected BC candidate Excel outside the official BC folder")

    jeol_epr = subparsers.add_parser(
        "jeol-epr-decode",
        help="decode verified JEOL JES-FA/JES-X3 cAcqu cwESR files to data-only .xlsx tables",
    )
    jeol_epr.add_argument("--out", required=True, type=Path, help="output root for data-only .xlsx files")
    jeol_epr.add_argument("--reference-dir", type=Path, help="optional directory of known decoded .xlsx files")
    jeol_epr.add_argument("--report-xlsx", type=Path, help="optional comparison report path")
    jeol_epr.add_argument("roots", nargs="+", type=Path, help="raw JEOL EPR folders to scan recursively")

    epr_overlay = subparsers.add_parser(
        "epr-overlay",
        help="build JEOL EPR condition-group overlay tables and optional Origin figures from verified Excel exports",
    )
    epr_overlay.add_argument("--reference-dir", type=Path, help="directory of verified JEOL EPR Excel exports")
    epr_overlay.add_argument("--group", choices=["all", "OH", "O3"], default="all")
    epr_overlay.add_argument("--with-origin", action="store_true", help="explicitly export OPJU/TIF/PNG through Origin")
    epr_overlay.add_argument("--normalize", action="store_true", help="max-abs normalize each trace before offsetting; off by default")
    epr_overlay.add_argument("--smooth-window", type=int, default=0, help="optional odd moving-average smoothing window; default 0 preserves raw shape")
    epr_overlay.add_argument("--background", choices=["none", "matched_dark"], default="none", help="optional explicit dark/background subtraction mode")
    epr_overlay.add_argument("--force", action="store_true", help="overwrite existing EPR overlay outputs")
    epr_overlay.add_argument("--report-json", type=Path)
    epr_overlay.add_argument("--report-md", type=Path)

    subparsers.add_parser("deps-audit")
    subparsers.add_parser("validate")
    readiness = subparsers.add_parser("readiness", help="check current project artifacts and dry-run safety state")
    readiness.add_argument("--expected-phase1-6-count", type=int, default=167)
    readiness.add_argument("--workspace-root", type=Path, help="workspace data root; defaults to config/env/autodetected project path")
    readiness.add_argument("--f-drive-backup", type=Path, help="optional stable raw backup path; defaults to config/env or detected F-drive path")
    readiness.add_argument("--phase1-6-package", type=Path, help="Phase 1.6 result package; defaults to config/env/latest package")
    readiness.add_argument(
        "--skip-legacy-project-path-check",
        action="store_true",
        help="skip the post-rename check for a lingering GroupMeetingAutoPPT directory",
    )
    readiness.add_argument(
        "--desktop-review-xlsx",
        type=Path,
        default=Path.home() / "Desktop" / "phase1_8_manual_review_required_filtered.xlsx",
        help="optional user-facing Excel copy that should match the project report workbook",
    )
    readiness.add_argument(
        "--no-desktop-review-xlsx",
        action="store_true",
        help="skip the machine-local desktop workbook copy check; project report workbook is still checked",
    )
    readiness.add_argument("--report-json", type=Path)
    readiness.add_argument("--report-md", type=Path)

    phase1_9 = subparsers.add_parser(
        "phase1-9-governance",
        help="generate Phase 1.9 Origin plotting skill snapshot, journal-ready index, and structure reports without processing data",
    )
    phase1_9.add_argument("--skill-dir", type=Path, default=DEFAULT_ORIGIN_SKILL_DIR)
    phase1_9.add_argument("--package-dir", type=Path, default=DEFAULT_PHASE1_6_PACKAGE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path.cwd()

    if args.command == "scan":
        config = load_project_config(project_root, Path(args.config))
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        _validate_input_directory(input_path)
        scan_raw_data(project_root, input_path, output_root=_resolve_cli_output_root(project_root, args))
        return 0
    if args.command == "process":
        config = load_project_config(project_root, Path(args.config))
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        _validate_input_directory(input_path)
        return run_process(
            project_root,
            input_path,
            ProcessOptions(
                no_origin=args.no_origin,
                with_origin=args.with_origin,
                only_type=args.only_type,
                only_folder=args.only_folder,
                fail_fast=args.fail_fast,
                force=args.force,
                from_queue=args.from_queue,
                auto_select=args.auto_select,
                include_ambiguous=args.include_ambiguous,
                output_root=_resolve_cli_output_root(project_root, args),
            ),
        )
    if args.command == "triage":
        config = load_project_config(project_root, Path(args.config))
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        _validate_input_directory(input_path)
        run_triage(
            project_root,
            input_path,
            TriageOptions(
                only_type=args.only_type,
                only_folder=args.only_folder,
                min_confidence=args.min_confidence,
                explain=args.explain,
                force_refresh=args.force_refresh,
                dry_run=args.dry_run,
                output_root=_resolve_cli_output_root(project_root, args),
            ),
        )
        return 0
    if args.command == "origin-test":
        result = origin_smoke_test(project_root)
        return 0 if result.ok else 1
    if args.command == "opju-product-pilot":
        result = run_opju_product_pilot(
            project_root,
            OpjuProductPilotOptions(
                pairing_path=args.pairing,
                output_root=args.output_root,
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"product_count={result['summary']['product_count']}")
        return 0 if not result.get("failures") else 1
    if args.command == "remaining-opju-product-drafts":
        result = run_remaining_opju_product_drafts(
            project_root,
            RemainingOpjuProductDraftOptions(
                pairing_path=args.pairing,
                output_root=args.output_root,
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                previous_run_root=args.previous_run_root,
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"product_count={result['summary']['product_count']}")
        print(f"skipped_count={result['summary']['skipped_count']}")
        return 0 if result["summary"]["product_count"] > 0 and not result.get("failures") else 1
    if args.command == "v2-exemplar-conformance-products":
        result = run_v2_exemplar_conformance_products(
            project_root,
            V2ExemplarConformanceOptions(
                pairing_path=args.pairing,
                output_root=args.output_root,
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                first_run_root=args.first_run_root,
                remaining_run_root=args.remaining_run_root,
                user_style_path=args.user_style,
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"product_count={result['summary']['product_count']}")
        print(f"failure_count={result['summary']['failure_count']}")
        return 0 if result["summary"]["product_count"] == 11 and not result.get("failures") else 1
    if args.command == "eis-randles-cpe-v2":
        result = run_eis_randles_cpe_v2(
            project_root,
            EisRandlesCpeV2Options(
                pairing_path=args.pairing,
                output_root=args.output_root,
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                previous_eis_run_root=args.previous_eis_run_root,
                user_style_path=args.user_style,
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"product_count={result['summary']['product_count']}")
        print(f"failure_count={result['summary']['failure_count']}")
        return 0 if result["summary"]["product_count"] == 1 and not result.get("failures") else 1
    if args.command == "unified-v2-exemplar-conformance-all-types":
        result = run_unified_v2_exemplar_conformance_products(
            project_root,
            UnifiedV2ExemplarConformanceOptions(
                pairing_path=args.pairing,
                output_root=args.output_root,
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                first_run_root=args.first_run_root,
                remaining_run_root=args.remaining_run_root,
                eis_v2_run_root=args.eis_v2_run_root,
                user_style_path=args.user_style,
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"product_count={result['summary']['product_count']}")
        print(f"failure_count={result['summary']['failure_count']}")
        print(f"eis_imported={result['summary'].get('eis_imported', False)}")
        return 0 if result["summary"]["product_count"] == 11 and not result.get("failures") else 1
    if args.command == "origin-batch":
        return run_origin_batch(
            project_root,
            OriginBatchOptions(
                manifest=args.manifest,
                dry_run=args.dry_run or not args.execute,
                execute=args.execute,
                with_origin=args.with_origin,
                only_type=args.only_type,
                only_missing=args.only_missing,
                report_json=args.report_json,
                report_md=args.report_md,
                output_root=_resolve_cli_output_root(project_root, args),
            ),
        )
    if args.command == "manifest-normalize":
        normalize_material_collection_manifest(
            args.manifest if args.manifest.is_absolute() else project_root / args.manifest,
            project_root,
            output_csv=args.output_csv,
            output_json=args.output_json,
            output_md=args.output_md,
        )
        return 0
    if args.command == "reviewed-queue":
        return run_reviewed_queue(
            project_root,
            ReviewedQueueOptions(
                proposals=args.proposals,
                decisions=args.decisions,
                write_template=args.write_template,
                dry_run=True,
                template_out=args.template_out,
                report_json=args.report_json,
                report_md=args.report_md,
                output_root=_resolve_cli_output_root(project_root, args),
            ),
        )
    if args.command == "auto-queue":
        return run_auto_queue(
            project_root,
            AutoQueueOptions(
                queue=args.queue,
                workspace_root=args.workspace_root,
                processed_index=args.processed_index,
                report_json=args.report_json,
                report_md=args.report_md,
                queue_out=args.queue_out,
                only_type=args.only_type,
                output_root=_resolve_cli_output_root(project_root, args),
            ),
        )
    if args.command == "xps-heterojunction-stacked":
        if args.bobc is None and args.cwo is None and args.bc is None:
            sample_files, notes = discover_default_xps_sample_files(project_root, include_bc_candidate=not args.no_bc_candidate)
        else:
            sample_files = {
                "BOBC": list(args.bobc or []),
                "CWO": list(args.cwo or []),
                "BC": list(args.bc or []),
            }
            _validate_explicit_xps_input_files(sample_files)
            notes = []
        output_dir = args.output_dir if args.output_dir.is_absolute() else project_root / args.output_dir
        run_xps_heterojunction_stacked(
            project_root,
            sample_files,
            XpsHeterojunctionOptions(output_dir=output_dir, with_origin=bool(args.with_origin)),
            pre_manual_review=notes,
        )
        return 0
    if args.command == "jeol-epr-decode":
        output_root = args.out if args.out.is_absolute() else project_root / args.out
        reference_dir = args.reference_dir if args.reference_dir is None or args.reference_dir.is_absolute() else project_root / args.reference_dir
        report_xlsx = args.report_xlsx if args.report_xlsx is None or args.report_xlsx.is_absolute() else project_root / args.report_xlsx
        result = export_jeol_cwesr_to_xlsx(
            args.roots,
            output_root,
            reference_dir=reference_dir,
            report_xlsx=report_xlsx,
        )
        print(f"exported_xlsx={result['exported_xlsx']}")
        return 0
    if args.command == "epr-overlay":
        reference_dir = args.reference_dir if args.reference_dir is None or args.reference_dir.is_absolute() else project_root / args.reference_dir
        return run_epr_overlay(
            project_root,
            EprOverlayOptions(
                reference_dir=reference_dir,
                group=args.group,
                with_origin=bool(args.with_origin),
                force=bool(args.force),
                normalize=bool(args.normalize),
                smooth_window=int(args.smooth_window),
                background=None if args.background == "none" else args.background,
                report_json=args.report_json,
                report_md=args.report_md,
            ),
        )
    if args.command == "deps-audit":
        code, _ = dependency_audit(project_root)
        return code
    if args.command == "validate":
        return validate(project_root)
    if args.command == "readiness":
        return run_readiness(
            project_root,
            ReadinessOptions(
                expected_phase1_6_count=args.expected_phase1_6_count,
                workspace_root=args.workspace_root,
                f_drive_backup=args.f_drive_backup,
                phase1_6_package=args.phase1_6_package,
                check_legacy_project_path=not args.skip_legacy_project_path_check,
                desktop_review_xlsx=None if args.no_desktop_review_xlsx else args.desktop_review_xlsx,
                report_json=args.report_json,
                report_md=args.report_md,
            ),
        )
    if args.command == "phase1-9-governance":
        run_phase1_9_governance(project_root, skill_dir=args.skill_dir, package_dir=args.package_dir)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def _validate_explicit_xps_input_files(sample_files: dict[str, list[Path]]) -> None:
    for sample, paths in sample_files.items():
        for path in paths:
            if not path.exists():
                raise ValueError(f"explicit XPS input file does not exist for {sample}: {path}")
            if not path.is_file():
                raise ValueError(f"explicit XPS input path is not a file for {sample}: {path}")


def _validate_input_directory(input_path: Path) -> None:
    if not input_path.exists():
        raise ValueError(f"input directory does not exist: {input_path}")
    if not input_path.is_dir():
        raise ValueError(f"input path is not a directory: {input_path}")


def _resolve_cli_output_root(project_root: Path, args: argparse.Namespace) -> Path:
    config_path = Path(getattr(args, "config", "config/default.yaml"))
    return resolve_output_root(project_root, explicit=getattr(args, "output_root", None), config_path=config_path)
