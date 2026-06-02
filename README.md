# ResearchDataOriginPipeline

Current checkpoint: Phase 1.9 package integration, algorithm hardening, and journal-ready plotting governance.

Latest locked Origin package: `output/phase1_6_origin_results_20260531_041538`

Phase 1.6 produced 167 real Origin result sets. Phase 1.7 added preview review, manifest dry-run, Origin isolation proof, and triage-recognition reports. Phase 1.8 added a user-reviewed queue gate and a filtered manual-review workbook. Phase 1.9 adds origin-plotting skill governance, package import/smoke reports, algorithm provenance, safer EIS/Mott-Schottky/XPS handling, and a journal-ready index without processing new real data or launching Origin.

## Phase 1.9 Outputs

- Origin plotting skill snapshot: `docs/agent_reports/phase1_9_origin_plotting_skill_snapshot.md`
- Journal-ready index: `output/reports/phase1_9_journal_ready_index.csv`
- Journal figure QC: `output/reports/phase1_9_journal_figure_qc.md`
- Package integration report: `docs/agent_reports/phase1_9_package_integration_report.md`
- Data type coverage matrix: `output/reports/phase1_9_data_type_coverage_matrix.md`
- Final manual-review workbook: `output/reports/phase1_9_manual_review_required_final.xlsx`
- Bugfix report: `docs/agent_reports/phase1_9_bugfix_report.md`

Phase 1.9 uses `D:\CodexData\.codex\skills\origin-plotting\SKILL.md` as the only style authority for Origin/Graph4 canvas geometry, axis lengths, fonts, line widths, y-axis tick policy, color consistency, OPJU/TIF/PNG outputs, and QC expectations.

## Phase 1.9 Package Policy

Installed or verified optional packages include `nmrglue`, `pyteomics`, `pygaps`, `ixdat`, `rainbow-api`, `mocca2`, `cwepr`, `lmfitxps`, and `vgd-reader`; pre-existing usable packages include `pybaselines`, `scipy`, `pymzml`, `tifffile`, `Pillow`, and `scikit-image`. They are recorded in `phase1_9_package_integration_report.md`.

Only low-risk candidate calculations enter the automatic flow. GPL or expert-system packages remain reference-only. XPS valence, EPR radical, XRD phase/plane, MS product, heterojunction mechanism, and SEM/TEM morphology/lattice conclusions remain blocked.

## Current Scope

- Phase 1.6 Origin exports completed: EIS 22, photocurrent 3, Raman 30, Mott-Schottky 90, EPR 13, XPS 9.
- Origin visual QC: 167/167 `QC_PASS`.
- XPS outputs are raw spectrum plots only; no automatic valence assignment.
- SEM, TEM, NMR, and MS remain scan-only/deferred.
- Kinetics/reference folders remain `reference_literature`.
- PPT generation and kinetics processors remain forbidden.

## Phase 1.8 Reviewed Queue Workflow

Generate a decision template from the Phase 1.7 review-only proposals:

```powershell
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --write-template
```

Edit:

```text
output\reports\phase1_8_review_decisions_template.csv
```

CSV rules:

- The CSV header must exactly match the generated template. Missing, duplicate, blank, or unknown columns are rejected.
- Every non-empty decision row must keep a non-empty `proposal_id`; malformed CSV is rejected before planning.
- Do not edit traceability columns such as `proposal_id`, `relative_path`, `source_hash`, `proposed_data_type`, `proposed_processor`, `risk_level`, and `reason`.
- Empty `user_decision` means skip; it will not enter a queue.
- The only approval value is `approve_for_no_origin_queue`.
- Approved rows must include `approved_by` and `approval_date`.
- High-risk rows must include `high_risk_ack=true`.
- Folder/header conflict rows must include `folder_header_conflict_ack=true`.
- Use UTF-8 when saving the CSV; do not let spreadsheet software rename columns or damage paths.

Run the dry-run planner:

```powershell
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --decisions output\reports\phase1_8_review_decisions_template.csv --dry-run
```

Outputs:

- `output/reports/phase1_8_review_decisions_template.csv`
- `output/reports/phase1_8_reviewed_queue_plan.json`
- `output/reports/phase1_8_reviewed_queue_plan.md`
- `docs/agent_reports/phase1_8_reviewed_queue_report.md`

The planner validates CSV schema, path safety, current source hash, current triage state, Phase 1.6 duplicate/processed status, required approvals, and high-risk acknowledgement. It records the proposals CSV/JSON and decision CSV SHA256 values in the dry-run plan so `readiness` can detect stale plans even when file modification times are unreliable. It never launches Origin and never calls `process`.

## New AUTO_PROCESS Queue Planner

After the latest triage improvements, the raw `output/reports/processing_queue.json` contains both new candidates and items already represented in the Phase 1.6 Origin package. Use the dry-run planner before any future no-Origin run:

```powershell
D:\Python\python.exe run.py auto-queue
```

Outputs:

- Plan: `output/reports/phase1_8_new_auto_process_plan.md`
- Candidate queue: `output/reports/phase1_8_new_auto_process_queue.json`

Current dry-run result:

- Source AUTO_PROCESS items: 188
- Skipped because already represented in Phase 1.6: 83
- New no-Origin candidates: 105
- Candidate types: EPR 44, Mott-Schottky 32, EIS 24, photocurrent 5
- Will run process: false
- Will launch Origin: false

Do not run the raw `processing_queue.json` directly for the next batch. Review `phase1_8_new_auto_process_plan.md` first, then use the generated candidate queue only for an explicit no-Origin run. The `process --from-queue output/reports/processing_queue.json` path now refuses to run when the raw queue still contains hashes already represented in the Phase 1.6 package. Queue processing also rejects unknown `data_type` values, scan-only data types, and `selected_processor` values that do not match the processor registry. `--include-ambiguous` is restricted to MANUAL_REVIEW queue items with explicit promotion/user-approval provenance. `--auto-select` cannot be combined with `--with-origin` or an explicit `--from-queue`; build and review a queue first.

Queue-driven output filenames use a stable hash of the full queue id so reviewed-queue items with the same source filename cannot collapse into the same `sample_phase1_8` output path.

## Latest Manual Review Workbook

After the latest rule optimization, triage refresh, and same-data filtering, unresolved files are listed here:

- Excel: `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- CSV: `output/reports/phase1_8_manual_review_required_filtered.csv`
- Report: `output/reports/phase1_8_manual_review_required_filtered_report.md`
- Desktop copy: `C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx`

Current counts:

- Latest triage has 618 `MANUAL_REVIEW` items.
- 125 same-data items are excluded from the main manual-review workbook because a successful Phase 1.6 result or an AUTO_PROCESS/DUPLICATE_SUPPRESSED representative exists.
- 493 files remain in the current manual-review workbook.
- The older `phase1_8_manual_review_required_after_ai.csv` is historical and should not be used as the current user-facing list.

## BET Status

`D:\Codex Project\科研数据处理\数据\26.5.29\BET` already contains legacy BET OPJU/PNG/TSV/CSV outputs, including Graph4-style PNG previews. Those files are preserved as existing work. BET has not yet been incorporated into the locked Phase 1.6 standardized result package, and current triage keeps BET in manual review/proposal mode until adsorption/desorption columns and source format handling are reviewed.

## Phase 1.7 Review Outputs

- Preview review checklist: `output/reports/phase1_7_origin_preview_review_checklist.csv`
- Preview gallery: `output/review_dashboard/phase1_7_preview_gallery.md`
- Gallery by type: `output/review_dashboard/phase1_7_preview_gallery_by_type.md`
- High-priority manual review: `output/reports/phase1_7_high_priority_manual_review.md`
- Manual override decision table: `output/reports/phase1_7_manual_override_decision_table.csv`

The preview checklist is for visual acceptance of the 167 completed Phase 1.6 figures. It is not approval to process new files.

## Separate XPS Figure Outputs

The Phase 1.8 queue gate did not process new real datasets or launch Origin. Separate XPS figure-output workflows may still exist outside that queue gate:

- Guardrails: `docs/xps_origin_plotting_guardrails.md`
- Stacked heterojunction summary: `output/xps_heterojunction_stacked/reports/xps_heterojunction_stacked_summary.md`
- In-situ XPS mapping: `outputs/xps_in_situ_20260506/xps_data_mapping_report.md`

Treat those outputs as dedicated XPS figure products, not as Phase 1.8 queue-processing results.

## Manifest Runner

Dry-run is the default:

```powershell
D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run
D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run --only-type XPS
```

The runner reads the package manifest, verifies paths and hashes, skips completed outputs, writes a run plan, and does not launch Origin.

## Phase 1.10 Manifest Stabilization

Phase 1.10 keeps `output/phase1_6_origin_results_20260531_041538` as the canonical standard result package and writes a locked pointer manifest under `output/final_locked_results/freeze_*`.

The latest material collection, `output/material_collections/cwo_bobc_bicu_with_xps_unprocessed_20260531_133711`, is a mixed material-selection package. It contains workspace copies, selected formats, historical Phase 1.6 artifacts, and unprocessed XPS files. Do not pass its raw `index.csv` directly to `origin-batch`.

Use this normalization command for a controlled dry-run manifest:

```powershell
D:\Python\python.exe run.py manifest-normalize --manifest output\material_collections\cwo_bobc_bicu_with_xps_unprocessed_20260531_133711\index.csv
D:\Python\python.exe run.py origin-batch --manifest output\reports\phase1_10_material_collection_normalized_manifest.csv --dry-run
```

The normalized material manifest is allowed to contain zero safe export items. In that case `origin-batch` exits cleanly, skips all rows, and launches no Origin instances.

## Output Directory Governance

`output/` is the primary project output root for canonical result packages, reports, manifests, dashboards, dry-run plans, and `final_locked_results`. `outputs/` is reserved for specialized or historical run outputs and is not raw data. Material collections are not standard result packages unless a normalizer report and dry-run prove compatibility.

## Why Remaining MANUAL_REVIEW Is Not Processed In Bulk

The latest triage has 618 `MANUAL_REVIEW` items after parser and recognition improvements. The user-facing filtered workbook keeps 493 rows after excluding same-data items already represented by successful or processable formats. Many remaining items involve parser failures, proprietary/binary formats, duplicate ambiguity, folder/header conflicts, or scientific context. Do not use global `--include-ambiguous`.

## Recommended Validation Commands

```powershell
D:\Python\python.exe -m pytest
D:\Python\python.exe run.py deps-audit
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py readiness
D:\Python\python.exe run.py readiness --no-desktop-review-xlsx
D:\Python\python.exe run.py scan --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml
D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh
```

`readiness` writes `output/reports/readiness_report.json` and `.md`. It checks the locked Phase 1.6 package count plus `result_summary.json`/`index.csv` consistency, current filtered manual-review workbook CSV/XLSX/report row consistency, the desktop review workbook copy, auto-queue dry-run safety flags, auto-queue plan/queue identity consistency, auto-queue dry-run provenance, reviewed-queue proposal/template/plan consistency including stored input SHA256 values and zero blocked approval rows, current `validate` report safety markers, validation-report freshness against validation-related source/config files, required active entry documents, current Phase 1.8 summaries, the review dashboard's current links, workspace copy, F-drive backup, project-rename path hygiene, and PPT forbidden paths without processing data or launching Origin.

`--no-desktop-review-xlsx` is for portable or CI-style checks where the project workbook exists but the user-facing desktop copy is not expected. The default remains the stricter local workflow. If PowerShell displays Chinese paths as mojibake, inspect the UTF-8 Markdown/JSON files directly; the stored files are UTF-8.

## Data Safety

- Workspace copy: `workspace_data/LL_detection_copy_20260530`
- Stable backup reference: `F:\课题\LL\检测`
- Do not write into workspace source folders or the F-drive backup.
- Do not batch-process all `MANUAL_REVIEW`.
- Do not auto-apply override proposals.

## Phase 1.11 Release Freeze And Project Layout

- Current canonical package: `output/phase1_6_origin_results_20260531_041538`
- Current locked results: `output/final_locked_results/freeze_20260602_011419`
- Locked results contain 167 items and are the current release baseline.
- Material collection normalized manifest: `output/reports/phase1_10_material_collection_normalized_manifest.csv`; it has 1340 rows, 0 direct origin-batch rows, and 1340 safe-skip rows.
- Phase 1.11 handoff: `docs/agent_reports/PHASE1_11_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`
- Report indexes: `docs/indexes/agent_reports_index.md`, `docs/indexes/output_reports_index.md`, `docs/indexes/scripts_index.md`, `docs/indexes/outputs_index.md`

Project layout rules:

- `src/`: source code and CLI-backed implementation.
- `config/`: configuration; do not move config files without tests.
- `scripts/maintenance/`: reusable maintenance helpers.
- `scripts/one_off/`: one-time audit or migration helpers kept for traceability.
- `scripts/archive/`: historical scripts after references are checked.
- `docs/agent_reports/`: phase reports; keep for audit history.
- `docs/indexes/`: generated indexes for reports, scripts, and outputs.
- `output/`: primary output repository and canonical result packages.
- `outputs/`: specialized or historical result outputs, not raw data.
- `workspace_data/`: real copied data source; treat as read-only.

Do not delete or move Phase 1.5/1.6 packages, locked results, OPJU/TIF/PNG previews, processed CSV, metadata, or report artifacts without an explicit user instruction.

## Phase 1.12 Release Commit Preparation

Phase 1.12 is commit-preparation only. `ALLOW_GIT_COMMIT=false`, so no `git add`, `git commit`, or `git tag` was executed.

- Pre-commit validation: `docs/agent_reports/phase1_12_pre_commit_validation.md`
- Git workspace audit: `docs/agent_reports/phase1_12_git_workspace_audit.md`
- Staging strategy: `docs/agent_reports/phase1_12_staging_strategy.md`
- Commit commands: `docs/agent_reports/phase1_12_commit_commands.md`
- Final handoff: `docs/agent_reports/PHASE1_12_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`

Recommended default commit route is Scheme A: source/schema fixes, regression tests, governance docs, `.gitignore`, `docs/indexes`, and scripts directory README files. Do not stage raw data, workspace data, Phase result packages, OPJU/TIF/PNG artifacts, tmp files, pycache, or large binary outputs.
