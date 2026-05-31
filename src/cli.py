from __future__ import annotations

import argparse
from pathlib import Path

from src.core.deps import dependency_audit
from src.core.origin_batch import OriginBatchOptions, run_origin_batch
from src.core.process import ProcessOptions, run_process
from src.core.project import configured_path, load_project_config
from src.core.reviewed_queue import ReviewedQueueOptions, run_reviewed_queue
from src.core.triage import TriageOptions, run_triage
from src.core.validate import validate
from src.origin.adapter import origin_smoke_test
from src.scanner.scanner import scan_raw_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--input")
    scan.add_argument("--config", default="config/default.yaml")

    process = subparsers.add_parser("process")
    process.add_argument("--input")
    process.add_argument("--config", default="config/default.yaml")
    origin_mode = process.add_mutually_exclusive_group()
    origin_mode.add_argument("--no-origin", action="store_true", help="process tables and metadata without launching Origin")
    origin_mode.add_argument("--with-origin", action="store_true", help="explicitly allow Origin export for this processing run")
    process.add_argument("--only-type", help="process only one inferred data type, for example XRD or EIS")
    process.add_argument("--only-folder", help="process only one raw_data folder name or relative path")
    process.add_argument("--fail-fast", action="store_true", help="stop on the first failed dataset")
    process.add_argument("--force", action="store_true", help="allow overwriting same-name output artifacts under output/")
    process.add_argument("--from-queue", type=Path, help="process only items from a processing_queue.json")
    process.add_argument("--auto-select", action="store_true", help="run triage first and process only AUTO_PROCESS items")
    process.add_argument("--include-ambiguous", action="store_true", help="allow MANUAL_REVIEW queue items to be processed")

    triage = subparsers.add_parser("triage")
    triage.add_argument("--input")
    triage.add_argument("--config", default="config/default.yaml")
    triage.add_argument("--only-type")
    triage.add_argument("--only-folder")
    triage.add_argument("--min-confidence", type=float, default=0.75)
    triage.add_argument("--explain", action="store_true")
    triage.add_argument("--force-refresh", action="store_true")
    triage.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("origin-test")

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

    subparsers.add_parser("deps-audit")
    subparsers.add_parser("validate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path.cwd()

    if args.command == "scan":
        config = load_project_config(project_root, Path(args.config))
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        scan_raw_data(project_root, input_path)
        return 0
    if args.command == "process":
        config = load_project_config(project_root, Path(args.config))
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
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
            ),
        )
    if args.command == "triage":
        config = load_project_config(project_root, Path(args.config))
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
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
            ),
        )
        return 0
    if args.command == "origin-test":
        result = origin_smoke_test(project_root)
        return 0 if result.ok else 1
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
            ),
        )
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
            ),
        )
    if args.command == "deps-audit":
        code, _ = dependency_audit(project_root)
        return code
    if args.command == "validate":
        return validate(project_root)
    raise AssertionError(f"Unhandled command: {args.command}")
