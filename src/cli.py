from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.core.project import (
    configured_path,
    ensure_output_path_separate_from_inputs,
    ensure_output_path_within_root,
    load_project_config,
    project_config_scope,
)
from src.core.runtime_paths import resolve_output_root


DEFAULT_ORIGIN_SKILL_DIR = Path(".agents") / "skills" / "originpro-graph-export"
DEFAULT_XRD_REFERENCE_OPJU = Path("templates") / "origin_styles" / "reference_opju" / "XRD.opju"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--input")
    scan.add_argument("--config", type=Path, help="explicit project config; defaults to optional config/default.yaml")
    scan.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    process = subparsers.add_parser("process")
    process.add_argument("--input")
    process.add_argument("--source", type=Path, action="append", help="explicit file to process directly with --only-type; repeat for multiple files; no directory scan")
    process.add_argument("--config", type=Path, help="explicit project config; defaults to optional config/default.yaml")
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
        help="process only items from an explicit vetted queue; for current AUTO_PROCESS candidates prefer output/reports/auto_process_queue.json",
    )
    process.add_argument(
        "--auto-select",
        action="store_true",
        help="legacy shortcut: run triage then process AUTO_PROCESS items; for current reviewed queue work prefer auto-queue dry-run plus an explicit vetted queue",
    )
    process.add_argument("--include-ambiguous", action="store_true", help="allow MANUAL_REVIEW queue items to be processed")

    triage = subparsers.add_parser("triage")
    triage.add_argument("--input")
    triage.add_argument("--config", type=Path, help="explicit project config; defaults to optional config/default.yaml")
    triage.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")
    triage.add_argument("--only-type")
    triage.add_argument("--only-folder")
    triage.add_argument("--min-confidence", type=float, default=0.75, help="classification threshold; this CLI option is the active override (default 0.75)")
    triage.add_argument("--explain", action="store_true")
    triage.add_argument("--force-refresh", action="store_true", help="compatibility option; triage already refreshes all selected inputs on each run")
    triage.add_argument("--dry-run", action="store_true")

    origin_test = subparsers.add_parser("origin-test")
    origin_test.add_argument(
        "--force",
        action="store_true",
        help="replace fixed-name smoke-test artifacts after all safety preflights",
    )

    template_format = subparsers.add_parser(
        "template-format-products",
        help=(
            "generate OPJU/TIF/PNG products using project-local Origin runtime assets "
            "without changing established legacy OTH behavior"
        ),
    )
    template_format.add_argument("--pairing", type=Path, required=True, help="OPJU/data pairing plan JSON")
    template_format.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    template_format.add_argument("--with-origin", action="store_true", help="launch isolated Origin COM and export OPJU/TIF/PNG")
    template_format.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    template_format.add_argument("--f-drive-template-root", type=Path, help="F-drive OPJU/OPJ template root to scan for non-XPS types")
    template_format.add_argument("--xps-reference-template-root", type=Path, help="XPS OPJU/OPJ reference root")
    template_format.add_argument("--xps-non-in-situ-template-root", type=Path, help="optional non-in-situ stacked XPS OPJU template root")
    template_format.add_argument("--user-style", type=Path, help="optional local user plot-style override YAML")
    template_source = template_format.add_mutually_exclusive_group()
    template_source.add_argument(
        "--asset-only",
        action="store_true",
        help=(
            "use only project-local runtime style assets (legacy accepted OTH assets or "
            "independently validated replacements); skip external template discovery and preview export"
        ),
    )
    template_source.add_argument(
        "--exemplar-driven",
        action="store_true",
        help=(
            "explicit baseline/diagnostic mode: replace data in an isolated copy of the reviewed "
            "pairing-plan OPJU; this remains runtime-OPJU-dependent"
        ),
    )
    template_format.add_argument("--compact-output", action="store_true", help="write deliverables under products/<type> with minimal top-level output folders")
    template_format.add_argument("--only-type", help="run template-format generation for one product type first, for example XRD")
    template_format.add_argument(
        "--origin-style-mode",
        choices=("auto", "otpu", "oth-json"),
        default="auto",
        help=(
            "Origin style execution route: auto selects exact verified OTPU for a fixed "
            "binding and accepted OTH+JSON only for adaptive series cardinality; explicit "
            "modes never silently fall back"
        ),
    )
    template_format.add_argument(
        "--style-replay-report",
        type=Path,
        help=(
            "independent theme-application replay summary used by the strict "
            "saved-style acceptance gate"
        ),
    )

    origin_style_assets = subparsers.add_parser(
        "export-origin-style-assets",
        help="harvest quarantined Origin style candidates for independent replay validation",
    )
    origin_style_assets.add_argument("--run-root", type=Path, help="accepted template-format run root to harvest")
    origin_style_assets.add_argument("--template-plan", type=Path, help="JSON plan with multiple template OPJU items to harvest")
    origin_style_assets.add_argument("--template-opju", type=Path, help="single OPJU/OPJ template to harvest directly")
    origin_style_assets.add_argument("--product-key", help="product key for --template-opju, for example XRD")
    origin_style_assets.add_argument("--data-type", help="data type label for --template-opju; defaults to --product-key")
    origin_style_assets.add_argument("--graph-page", help="graph page to save from --template-opju, for example Graph4")
    origin_style_assets.add_argument("--asset-root", type=Path, help="style asset root; defaults to templates/origin_styles")
    origin_style_assets.add_argument(
        "--with-origin",
        action="store_true",
        help="launch isolated Origin and create candidate assets; this does not validate them for runtime use",
    )

    origin_style_replay = subparsers.add_parser(
        "origin-style-asset-replay",
        help=(
            "diagnostic style replay; supports explicit fresh-project same-data OTPU validation "
            "but never promotes an asset or substitutes for manual preview"
        ),
    )
    origin_style_replay.add_argument("--template-plan", type=Path, required=True, help="JSON plan with template OPJU items")
    origin_style_replay.add_argument("--output-dir", type=Path, required=True, help="single output folder for replay products")
    origin_style_replay.add_argument("--with-origin", action="store_true", help="launch isolated Origin and export comparison products")

    origin_batch = subparsers.add_parser(
        "origin-batch",
        help="plan Origin exports from a package manifest; dry-run by default and never launches Origin unless explicitly executed",
    )
    origin_batch.add_argument("--manifest", type=Path, required=True, help="package index.csv or compatible manifest")
    origin_batch.add_argument("--dry-run", action="store_true", help="plan only; this is also the default")
    origin_batch.add_argument("--execute", action="store_true", help="request real execution; requires --with-origin")
    origin_batch.add_argument("--with-origin", action="store_true", help="required for future real execution; dry-run never launches Origin")
    origin_batch.add_argument("--only-type", help="include only one data_type from the manifest")
    origin_batch.add_argument("--only-missing", action="store_true", help="plan only entries missing Origin outputs")
    origin_batch.add_argument("--report-json", type=Path, help="optional JSON report path under the configured output root")
    origin_batch.add_argument("--report-md", type=Path, help="optional Markdown report path under the configured output root")
    origin_batch.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    manifest_normalize = subparsers.add_parser(
        "manifest-normalize",
        help="normalize a material collection index into an origin-batch-compatible manifest without processing data",
    )
    manifest_normalize.add_argument("--manifest", type=Path, required=True, help="material collection index.csv")
    manifest_normalize.add_argument("--output-csv", type=Path)
    manifest_normalize.add_argument("--output-json", type=Path)
    manifest_normalize.add_argument("--output-md", type=Path)
    manifest_normalize.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    reviewed_queue = subparsers.add_parser(
        "reviewed-queue",
        help="build a dry-run queue plan from user-reviewed result package audit proposal decisions; never launches Origin or process",
    )
    reviewed_queue.add_argument("--proposals", type=Path, required=True, help="result package audit review-only proposal JSON")
    reviewed_queue.add_argument("--decisions", type=Path, help="reviewed queue user decision CSV")
    reviewed_queue.add_argument("--write-template", action="store_true", help="write a blank user decision CSV template")
    reviewed_queue.add_argument("--dry-run", action="store_true", help="plan only; this is the only supported mode")
    reviewed_queue.add_argument("--template-out", type=Path, help="optional template CSV path under the configured output root")
    reviewed_queue.add_argument("--report-json", type=Path, help="optional JSON report path under the configured output root")
    reviewed_queue.add_argument("--report-md", type=Path, help="optional Markdown report path under the configured output root")
    reviewed_queue.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")

    auto_queue = subparsers.add_parser(
        "auto-queue",
        help="dry-run a no-Origin candidate queue from current AUTO_PROCESS items, excluding locked result package processed hashes",
    )
    auto_queue.add_argument("--queue", type=Path)
    auto_queue.add_argument("--workspace-root", type=Path, help="workspace data root; defaults to config/env/autodetected project path")
    auto_queue.add_argument("--processed-index", type=Path, help="locked result package index.csv or package directory; defaults to config/env/latest package")
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
    xps_stacked.add_argument("--output-dir", type=Path)
    xps_origin = xps_stacked.add_mutually_exclusive_group()
    xps_origin.add_argument("--dry-run", action="store_true", help="parse data, write tables/reports, but do not launch Origin")
    xps_origin.add_argument("--with-origin", action="store_true", help="explicitly launch Origin COM and export OPJU/TIF")
    xps_stacked.add_argument("--no-bc-candidate", action="store_true", help="do not use the detected BC candidate Excel outside the official BC folder")
    xps_stacked.add_argument(
        "--force",
        action="store_true",
        help="explicitly overwrite every preflighted output owned by this XPS run",
    )

    xrd_overlay = subparsers.add_parser(
        "xrd-overlay",
        help="build a user-reviewed XRD overlay with BiCu-10, BiOBr0.5Cl0.5, CuWO4, and CuWO4 reference-card sticks",
    )
    xrd_overlay.add_argument("--bicu-source", type=Path, required=True, help="RAW4/TXT source for BiCu-10")
    xrd_overlay.add_argument("--bobc-source", type=Path, required=True, help="RAW4/TXT source for BiOBr0.5Cl0.5")
    xrd_overlay.add_argument("--cwo-source", type=Path, required=True, help="RAW4/TXT source for CuWO4")
    xrd_overlay.add_argument("--cwo-card", type=Path, required=True, help="CuWO4 PDF/JCPDS text card")
    xrd_overlay.add_argument(
        "--reference-opju",
        type=Path,
        default=DEFAULT_XRD_REFERENCE_OPJU,
        help="optional XRD reference retained for audit compatibility only; the fresh product uses the verified project-local OTPU",
    )
    xrd_overlay.add_argument("--output-root", type=Path, help="optional output root; defaults to configured output root")
    xrd_origin = xrd_overlay.add_mutually_exclusive_group()
    xrd_origin.add_argument("--dry-run", action="store_true", help="write processed table, metadata, and report without launching Origin")
    xrd_origin.add_argument("--with-origin", action="store_true", help="explicitly launch Origin COM and export OPJU/TIF/PNG")
    xrd_overlay.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    xrd_overlay.add_argument(
        "--force",
        action="store_true",
        help="explicitly overwrite every preflighted output owned by this timestamped XRD run",
    )

    xrd_analysis = subparsers.add_parser(
        "xrd-analyze",
        help="process one exported XRD dataset and generate Jade/ICSD phase-match candidates without Origin or plotting",
    )
    xrd_analysis.add_argument("--source", type=Path, required=True, help="one exported XRD TXT/CSV/DAT/XY/XLSX file")
    xrd_analysis.add_argument("--database-dir", type=Path, required=True, help="directory containing one Jade XID/SID/RID group")
    xrd_analysis.add_argument("--database-stem", default="ICSD-ALL")
    xrd_analysis.add_argument("--card-id", action="append", default=[], help="card ID to compare; repeat as needed")
    xrd_analysis.add_argument("--card-query", action="append", default=[], help="formula or phase-name query; repeat as needed")
    xrd_analysis.add_argument("--full-library-screen", action="store_true", help="composition-blind exploratory screen of the selected database group")
    xrd_analysis.add_argument("--query-limit", type=int, default=20)
    xrd_analysis.add_argument("--result-limit", type=int, default=20)
    xrd_analysis.add_argument("--wavelength", type=float, default=1.5406, help="X-ray wavelength in angstrom")
    xrd_analysis.add_argument("--prominence", type=float, default=0.05, help="normalized candidate-peak prominence")
    xrd_analysis.add_argument("--distance-deg", type=float, default=0.10, help="minimum candidate-peak distance in degrees")
    xrd_analysis.add_argument("--card-tolerance", type=float, default=0.20, help="2theta card-match tolerance in degrees")
    xrd_analysis.add_argument("--min-card-intensity", type=float, default=10.0, help="minimum reference relative intensity")
    xrd_analysis.add_argument("--output-root", type=Path, help="external output root; defaults to configured output root")
    xrd_analysis.add_argument("--force", action="store_true", help="replace this command's preflighted output files")

    xrd_no_card = subparsers.add_parser(
        "xrd-no-card-overlay",
        help="build a user-reviewed no-card XRD overlay from one directory or explicit XRD text sources",
    )
    xrd_no_card.add_argument("--input-dir", type=Path, help="directory containing XRD TXT/CSV/DAT/XY sources")
    xrd_no_card.add_argument("--source", type=Path, action="append", default=[], help="explicit XRD source file; repeat for multiple curves")
    xrd_no_card.add_argument("--labels", nargs="*", help="direct labels for sources; defaults to source stems")
    xrd_no_card.add_argument("--output-root", type=Path, help="optional output root; defaults to configured output root")
    xrd_no_card.add_argument("--output-stem", default="XRD_BOBXC1_X_no_card_overlay")
    xrd_no_card.add_argument(
        "--reference-opju",
        type=Path,
        help="optional audit-only reference path; it is never loaded for product generation",
    )
    xrd_no_card.add_argument(
        "--reference-graph",
        default="Graph4",
        help="audit-only compatibility value",
    )
    xrd_no_card_origin = xrd_no_card.add_mutually_exclusive_group()
    xrd_no_card_origin.add_argument("--dry-run", action="store_true", help="write processed table, metadata, and report without launching Origin")
    xrd_no_card_origin.add_argument("--with-origin", action="store_true", help="explicitly launch Origin COM and export OPJU/TIF/PNG")
    xrd_no_card.add_argument("--timestamp", help="optional run timestamp for reproducible output paths")
    xrd_no_card.add_argument("--force", action="store_true", help="overwrite an existing run with the same timestamp/output stem")

    jeol_epr = subparsers.add_parser(
        "jeol-epr-decode",
        help="decode verified JEOL JES-FA/JES-X3 cAcqu cwESR files to data-only .xlsx tables",
    )
    jeol_epr.add_argument("--out", required=True, type=Path, help="output root for data-only .xlsx files")
    jeol_epr.add_argument("--reference-dir", type=Path, help="optional directory of known decoded .xlsx files")
    jeol_epr.add_argument("--report-xlsx", type=Path, help="optional comparison report path")
    jeol_epr.add_argument(
        "--force",
        action="store_true",
        help="explicitly overwrite preflighted JEOL XLSX, metadata, and comparison-report targets",
    )
    jeol_epr.add_argument("roots", nargs="+", type=Path, help="raw JEOL EPR folders to scan recursively")

    hplc_openlab = subparsers.add_parser(
        "hplc-openlab-export",
        help="decode Agilent OpenLab .rslt/.dx/.rx raw LC data into one data-only Excel workbook",
    )
    hplc_openlab.add_argument("--input", type=Path, required=True, help="root containing OpenLab .rslt result sets")
    hplc_openlab.add_argument(
        "--since",
        type=date.fromisoformat,
        required=True,
        help="inclusive acquisition-date cutoff in YYYY-MM-DD format",
    )
    hplc_openlab.add_argument("--output-root", type=Path, required=True, help="external output root")
    hplc_openlab.add_argument("--output-name", help="one .xlsx filename; defaults from --since")
    hplc_openlab.add_argument("--node-exe", type=Path, required=True, help="Node.js executable used by the workbook builder")
    hplc_openlab.add_argument(
        "--builder-workdir",
        type=Path,
        required=True,
        help="work directory under --output-root containing the artifact-tool node_modules link",
    )
    hplc_openlab.add_argument("--force", action="store_true", help="overwrite a same-name workbook")
    hplc_openlab.add_argument(
        "--vendor-reprocess",
        action="store_true",
        help="reprocess staged result-set copies with the Agilent Processing Server and a complete PMX method",
    )
    hplc_openlab.add_argument(
        "--vendor-runtime-bin",
        type=Path,
        help="optional complete-runtime override; defaults to the checked-in hash-verified Agilent bundle",
    )
    hplc_openlab.add_argument(
        "--vendor-bridge-exe",
        type=Path,
        help="optional bridge override inside --vendor-runtime-bin; supply all three vendor overrides together",
    )
    hplc_openlab.add_argument(
        "--vendor-processing-method",
        type=Path,
        help="optional complete-PMX override; defaults to the checked-in normalization-percent method",
    )
    hplc_openlab.add_argument(
        "--vendor-timeout-seconds",
        type=int,
        default=600,
        help="per-result-set Agilent Processing Server timeout (default: 600)",
    )

    epr_overlay = subparsers.add_parser(
        "epr-overlay",
        help="build JEOL EPR condition-group overlay tables and optional Origin figures from verified Excel exports",
    )
    epr_overlay.add_argument("--reference-dir", type=Path, help="directory of verified JEOL EPR Excel exports")
    epr_overlay.add_argument("--config", type=Path, help="explicit project config; defaults to optional config/default.yaml")
    epr_overlay.add_argument("--output-root", type=Path, help="optional output root; defaults to local/env/default config")
    epr_overlay.add_argument("--group", choices=["all", "OH", "O3"], default="all")
    epr_overlay.add_argument("--with-origin", action="store_true", help="explicitly export OPJU/TIF/PNG through Origin")
    epr_overlay.add_argument("--normalize", action="store_true", help="max-abs normalize each trace before offsetting; off by default")
    epr_overlay.add_argument("--smooth-window", type=int, default=0, help="optional odd moving-average smoothing window; default 0 preserves raw shape")
    epr_overlay.add_argument("--background", choices=["none", "matched_dark"], default="none", help="optional explicit dark/background subtraction mode")
    epr_overlay.add_argument("--force", action="store_true", help="overwrite existing EPR overlay outputs")
    epr_overlay.add_argument("--report-json", type=Path)
    epr_overlay.add_argument("--report-md", type=Path)

    subparsers.add_parser("deps-audit")
    validation = subparsers.add_parser("validate")
    validation.add_argument("--scope", choices=("full", "runtime"), default="full", help="full includes historical outputs; runtime checks software/config/assets only")
    readiness = subparsers.add_parser("readiness", help="check current project artifacts and dry-run safety state")
    readiness.add_argument("--scope", choices=("full", "runtime"), default="full", help="full includes historical jobs; runtime checks the matching runtime validation report")
    readiness.add_argument("--expected-locked-result-count", type=int, default=167)
    readiness.add_argument("--workspace-root", type=Path, help="workspace data root; defaults to config/env/autodetected project path")
    readiness.add_argument("--f-drive-backup", type=Path, help="optional stable raw backup path; defaults to config/env or detected F-drive path")
    readiness.add_argument("--locked-result-package", type=Path, help="locked result package directory or index.csv; defaults to config/env/latest package")
    readiness.add_argument(
        "--skip-legacy-project-path-check",
        action="store_true",
        help="skip the post-rename check for a lingering GroupMeetingAutoPPT directory",
    )
    readiness.add_argument(
        "--desktop-review-xlsx",
        type=Path,
        default=None,
        help="optional external Excel copy that should match the project report workbook; disabled by default",
    )
    readiness.add_argument(
        "--no-desktop-review-xlsx",
        action="store_true",
        help="skip the machine-local desktop workbook copy check; project report workbook is still checked",
    )
    readiness.add_argument(
        "--strict-artifacts",
        action="store_true",
        help="treat generated packages, queues, dashboards, and review workbooks as required artifacts",
    )
    readiness.add_argument("--report-json", type=Path)
    readiness.add_argument("--report-md", type=Path)

    origin_governance = subparsers.add_parser(
        "origin-governance",
        help="generate Origin plotting governance reports without processing data",
    )
    origin_governance.add_argument("--skill-dir", type=Path, default=DEFAULT_ORIGIN_SKILL_DIR)
    origin_governance.add_argument("--package-dir", type=Path)
    return parser


@project_config_scope()
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path.cwd()

    if args.command == "scan":
        from src.scanner.scanner import scan_raw_data

        config = _load_cli_project_config(project_root, args.config)
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        _validate_input_directory(input_path)
        output_root = _resolve_cli_output_root(project_root, args)
        ensure_output_path_separate_from_inputs(project_root, output_root, [input_path])
        scan_raw_data(project_root, input_path, output_root=output_root)
        return 0
    if args.command == "process":
        from src.core.process import ProcessOptions, run_process

        config = _load_cli_project_config(project_root, args.config)
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        if args.source:
            if args.input:
                raise ValueError("--source cannot be combined with --input; list the intended files explicitly.")
            for source in args.source:
                if not source.is_file():
                    raise ValueError(f"Explicit source is not an existing file: {source}")
        else:
            _validate_input_directory(input_path)
        output_root = _resolve_cli_output_root(project_root, args)
        ensure_output_path_separate_from_inputs(project_root, output_root, args.source or [input_path])
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
                output_root=output_root,
                sources=tuple(args.source or ()),
            ),
        )
    if args.command == "triage":
        from src.core.triage import TriageOptions, run_triage

        config = _load_cli_project_config(project_root, args.config)
        input_path = Path(args.input) if args.input else configured_path(project_root, config, "paths", "raw_data", "input/raw_data")
        _validate_input_directory(input_path)
        output_root = _resolve_cli_output_root(project_root, args)
        ensure_output_path_separate_from_inputs(project_root, output_root, [input_path])
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
                output_root=output_root,
            ),
        )
        return 0
    if args.command == "origin-test":
        from src.origin.adapter import origin_smoke_test

        result = origin_smoke_test(project_root, force=bool(args.force))
        return 0 if result.ok else 1
    if args.command == "template-format-products":
        from src.core.template_format_executor import (
            TemplateFormatExecutorOptions,
            run_template_format_executor,
        )

        result = run_template_format_executor(
            project_root,
            TemplateFormatExecutorOptions(
                pairing_path=args.pairing,
                output_root=args.output_root,
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                f_drive_template_root=args.f_drive_template_root,
                xps_reference_template_root=args.xps_reference_template_root,
                xps_non_in_situ_template_root=args.xps_non_in_situ_template_root,
                user_style_path=args.user_style,
                asset_only=bool(args.asset_only),
                exemplar_driven=bool(args.exemplar_driven),
                compact_output=bool(args.compact_output),
                only_type=args.only_type,
                style_replay_report=args.style_replay_report,
                origin_style_mode=args.origin_style_mode,
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"product_count={result['summary']['product_count']}")
        print(f"success_count={result['summary'].get('success_count', result['summary'].get('accepted_count', 0))}")
        print(f"blocked_count={result['summary']['blocked_count']}")
        print(f"failed_count={result['summary']['failed_count']}")
        summary = result["summary"]
        accepted_count = int(summary.get("accepted_count", summary.get("success_count", 0)) or 0)
        required_count = int(summary.get("required_product_count", 11) or 11)
        return 0 if summary["product_count"] == required_count and accepted_count == required_count and summary["blocked_count"] == 0 and summary["failed_count"] == 0 else 1
    if args.command == "export-origin-style-assets":
        from src.core.origin_style_assets import export_origin_style_assets

        result = export_origin_style_assets(
            project_root,
            args.run_root,
            asset_root=args.asset_root,
            with_origin=bool(args.with_origin),
            template_plan=args.template_plan,
            template_opju=args.template_opju,
            product_key=args.product_key,
            data_type=args.data_type,
            graph_page=args.graph_page,
        )
        print(f"asset_root={result['asset_root']}")
        print(f"manifest={result['manifest']}")
        print(f"planned_count={result['planned_count']}")
        print(f"exported_count={result['exported_count']}")
        print(f"failure_count={result['failure_count']}")
        return 0 if result["planned_count"] > 0 and result["planned_count"] == result["exported_count"] and result["failure_count"] == 0 else 1
    if args.command == "origin-style-asset-replay":
        from src.core.origin_style_assets import run_origin_style_asset_replay

        configured_output_root = _resolve_cli_output_root(project_root, args)
        output_dir = ensure_output_path_within_root(project_root, args.output_dir, configured_output_root)
        ensure_output_path_separate_from_inputs(project_root, output_dir, ())
        result = run_origin_style_asset_replay(
            project_root,
            args.template_plan if args.template_plan.is_absolute() else project_root / args.template_plan,
            output_dir,
            with_origin=bool(args.with_origin),
        )
        print(f"output_dir={result['output_dir']}")
        print(f"planned_count={result['planned_count']}")
        print(f"compared_count={result['compared_count']}")
        print(f"self_replay_count={result.get('self_replay_count', 0)}")
        print(f"failure_count={result['failure_count']}")
        return 0 if result["planned_count"] > 0 and result["planned_count"] == result["compared_count"] and result["failure_count"] == 0 else 1
    if args.command == "origin-batch":
        from src.core.origin_batch import OriginBatchOptions, run_origin_batch

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
        from src.core.manifest_normalizer import normalize_material_collection_manifest

        output_root = _resolve_cli_output_root(project_root, args)
        reports = output_root / "reports"
        normalize_material_collection_manifest(
            args.manifest if args.manifest.is_absolute() else project_root / args.manifest,
            project_root,
            output_dir=reports,
            output_root=output_root,
            output_csv=args.output_csv,
            output_json=args.output_json,
            output_md=args.output_md,
        )
        return 0
    if args.command == "reviewed-queue":
        from src.core.reviewed_queue import ReviewedQueueOptions, run_reviewed_queue

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
        from src.core.auto_queue import AutoQueueOptions, run_auto_queue

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
        from src.core.xps_heterojunction import (
            XpsHeterojunctionOptions,
            discover_default_xps_sample_files,
            run_xps_heterojunction_stacked,
        )

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
        if args.output_dir is None:
            output_dir = _resolve_cli_output_root(project_root, args) / "xps_heterojunction_stacked"
        else:
            output_dir = _resolve_cli_output_directory_arg(project_root, args.output_dir)
        xps_inputs = [path for paths in sample_files.values() for path in paths]
        ensure_output_path_separate_from_inputs(project_root, output_dir, xps_inputs)
        result = run_xps_heterojunction_stacked(
            project_root,
            sample_files,
            XpsHeterojunctionOptions(
                output_dir=output_dir,
                with_origin=bool(args.with_origin),
                force=bool(args.force),
            ),
            pre_manual_review=notes,
        )
        figures = result.get("figures", [])
        if not figures:
            return 1
        if args.with_origin and any(figure.get("status") != "success" for figure in figures):
            return 1
        return 0
    if args.command == "xrd-overlay":
        from src.core.xrd_overlay import XrdOverlayOptions, run_xrd_overlay

        result = run_xrd_overlay(
            project_root,
            XrdOverlayOptions(
                bicu_source=args.bicu_source,
                bobc_source=args.bobc_source,
                cwo_source=args.cwo_source,
                cwo_card=args.cwo_card,
                reference_opju=args.reference_opju,
                output_root=_resolve_cli_output_root(project_root, args),
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                force=bool(args.force),
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"processed_data={result['processed_data']}")
        print(f"metadata={result['metadata']}")
        print(f"origin_file={result['origin_file']}")
        print(f"figure_tif={result['figure_tif']}")
        print(f"preview_png={result['preview_png']}")
        return 0 if (not args.with_origin or bool(result["origin_status"].get("ok"))) else 1
    if args.command == "xrd-analyze":
        from src.core.xrd_analysis import XrdAnalysisOptions, run_xrd_analysis

        result = run_xrd_analysis(
            project_root,
            XrdAnalysisOptions(
                source=args.source,
                database_dir=args.database_dir,
                database_stem=args.database_stem,
                card_ids=tuple(args.card_id),
                card_queries=tuple(args.card_query),
                full_library_screen=bool(args.full_library_screen),
                query_limit=args.query_limit,
                result_limit=args.result_limit,
                wavelength_angstrom=args.wavelength,
                peak_prominence_normalized=args.prominence,
                minimum_peak_distance_deg=args.distance_deg,
                card_tolerance_deg=args.card_tolerance,
                minimum_card_relative_intensity=args.min_card_intensity,
                output_root=_resolve_cli_output_root(project_root, args),
                force=bool(args.force),
            ),
        )
        print(f"processed_data={result['processed_data']}")
        print(f"metadata={result['metadata']}")
        print(f"card_match_candidates={result['card_match_candidates']}")
        return 0 if result["ok"] else 1
    if args.command == "xrd-no-card-overlay":
        from src.core.xrd_no_card_overlay import (
            XrdNoCardOverlayOptions,
            discover_xrd_text_sources,
            run_xrd_no_card_overlay,
        )

        sources = list(args.source or [])
        if args.input_dir is not None:
            sources.extend(discover_xrd_text_sources(args.input_dir))
        if not sources:
            raise ValueError("xrd-no-card-overlay requires --input-dir or at least one --source")
        result = run_xrd_no_card_overlay(
            project_root,
            XrdNoCardOverlayOptions(
                sources=tuple(sources),
                labels=tuple(args.labels or ()),
                output_root=_resolve_cli_output_root(project_root, args),
                with_origin=bool(args.with_origin),
                timestamp=args.timestamp,
                output_stem=args.output_stem,
                reference_opju=args.reference_opju,
                reference_graph=args.reference_graph,
                force=bool(args.force),
            ),
        )
        print(f"run_root={result['run_root']}")
        print(f"processed_data={result['processed_data']}")
        print(f"metadata={result['metadata']}")
        print(f"origin_file={result['origin_file']}")
        print(f"figure_tif={result['figure_tif']}")
        print(f"preview_png={result['preview_png']}")
        return 0 if (not args.with_origin or bool(result["origin_status"].get("ok"))) else 1
    if args.command == "hplc-openlab-export":
        from src.core.hplc_openlab import (
            HplcOpenLabExportOptions,
            run_hplc_openlab_export,
        )

        _validate_input_directory(args.input)
        output_root = _resolve_cli_output_root(project_root, args)
        builder_workdir = ensure_output_path_within_root(project_root, args.builder_workdir, output_root)
        ensure_output_path_separate_from_inputs(project_root, output_root, [args.input])
        result = run_hplc_openlab_export(
            project_root,
            HplcOpenLabExportOptions(
                input_root=args.input,
                since=args.since,
                output_root=output_root,
                node_exe=args.node_exe,
                builder_workdir=builder_workdir,
                output_name=args.output_name,
                force=bool(args.force),
                vendor_reprocess=bool(args.vendor_reprocess),
                vendor_runtime_bin=args.vendor_runtime_bin,
                vendor_bridge_exe=args.vendor_bridge_exe,
                vendor_processing_method=args.vendor_processing_method,
                vendor_timeout_seconds=args.vendor_timeout_seconds,
            ),
        )
        print(f"workbook={result['workbook']}")
        print(f"workbook_count={len(result['workbooks'])}")
        print(f"injections={result['summary']['selected_injection_count']}")
        print(f"result_sets={result['summary']['result_set_count']}")
        print(f"raw_signal_points={result['summary']['signal_point_count']}")
        return 0
    if args.command == "jeol-epr-decode":
        from src.core.epr_jeol import export_jeol_cwesr_to_xlsx

        output_root = _resolve_cli_output_directory_arg(project_root, args.out)
        reference_dir = args.reference_dir if args.reference_dir is None or args.reference_dir.is_absolute() else project_root / args.reference_dir
        protected_inputs = [*args.roots]
        if reference_dir is not None:
            protected_inputs.append(reference_dir)
        ensure_output_path_separate_from_inputs(project_root, output_root, protected_inputs)
        report_xlsx = _resolve_cli_output_file(project_root, args.report_xlsx, output_root) if args.report_xlsx is not None else None
        result = export_jeol_cwesr_to_xlsx(
            args.roots,
            output_root,
            reference_dir=reference_dir,
            report_xlsx=report_xlsx,
            force=bool(args.force),
        )
        print(f"exported_xlsx={result['exported_xlsx']}")
        return 0 if int(result.get("exported_xlsx", 0) or 0) > 0 else 1
    if args.command == "epr-overlay":
        from src.core.epr_overlay import EprOverlayOptions, run_epr_overlay

        reference_dir = args.reference_dir if args.reference_dir is None or args.reference_dir.is_absolute() else project_root / args.reference_dir
        return run_epr_overlay(
            project_root,
            EprOverlayOptions(
                reference_dir=reference_dir,
                output_root=_resolve_cli_output_root(project_root, args),
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
        from src.core.deps import dependency_audit

        code, _ = dependency_audit(project_root)
        return code
    if args.command == "validate":
        from src.core.validate import validate

        return validate(project_root, scope=args.scope)
    if args.command == "readiness":
        from src.core.readiness import ReadinessOptions, run_readiness

        return run_readiness(
            project_root,
            ReadinessOptions(
                scope=args.scope,
                expected_locked_result_count=args.expected_locked_result_count,
                workspace_root=args.workspace_root,
                f_drive_backup=args.f_drive_backup,
                locked_result_package=args.locked_result_package,
                strict_artifacts=args.strict_artifacts,
                check_legacy_project_path=not args.skip_legacy_project_path_check,
                desktop_review_xlsx=None if args.no_desktop_review_xlsx else args.desktop_review_xlsx,
                report_json=args.report_json,
                report_md=args.report_md,
            ),
        )
    if args.command == "origin-governance":
        from src.core.origin_governance import run_origin_governance

        run_origin_governance(project_root, skill_dir=args.skill_dir, package_dir=args.package_dir)
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


def _load_cli_project_config(project_root: Path, explicit_config: Path | None) -> dict:
    if explicit_config is not None:
        config_path = explicit_config if explicit_config.is_absolute() else project_root / explicit_config
        if not config_path.exists():
            raise FileNotFoundError(f"explicit config file does not exist: {explicit_config}")
        if not config_path.is_file():
            raise ValueError(f"explicit config path is not a file: {explicit_config}")
        return load_project_config(project_root, explicit_config)
    return load_project_config(project_root, Path("config/default.yaml"))


def _resolve_cli_output_root(project_root: Path, args: argparse.Namespace) -> Path:
    config_path = getattr(args, "config", None) or Path("config/default.yaml")
    return resolve_output_root(project_root, explicit=getattr(args, "output_root", None), config_path=config_path)


def _resolve_cli_output_file(project_root: Path, path: Path, output_root: Path) -> Path:
    from src.core.project import ensure_write_path_allowed

    target = path if path.is_absolute() else output_root / path
    ensure_write_path_allowed(project_root, target, output_root=output_root)
    return target


def _resolve_cli_output_directory_arg(project_root: Path, path: Path) -> Path:
    from src.core.project import ensure_write_path_allowed

    configured_root = resolve_output_root(project_root)
    target = path if path.is_absolute() else configured_root / path
    ensure_write_path_allowed(project_root, target, output_root=target)
    return target
