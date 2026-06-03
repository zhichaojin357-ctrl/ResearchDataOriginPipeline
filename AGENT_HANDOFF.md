# Agent Handoff

## Current Status Pointer

For the current repository state, use `docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md` as the status authority. Phase 1.6 is the locked canonical result package, not the current engineering phase. This handoff is an entry pointer, not the latest full status source; check the current status/index/cleanup docs before further changes.

## Latest State: Phase 1.9

Read these first:

- `docs/agent_reports/phase1_9_baseline.md`
- `docs/agent_reports/phase1_9_bugfix_report.md`
- `docs/agent_reports/phase1_9_package_integration_report.md`
- `docs/agent_reports/phase1_9_algorithm_upgrade_report.md`
- `docs/agent_reports/phase1_9_origin_plotting_skill_snapshot.md`
- `output/reports/phase1_9_journal_ready_index.csv`
- `output/reports/phase1_9_journal_figure_qc.md`
- `output/reports/phase1_9_data_type_coverage_matrix.md`
- `output/reports/phase1_9_manual_review_required_final.xlsx`

Phase 1.9 did not process new real datasets and did not launch Origin. It hardened algorithms, installed/verified optional packages, generated journal-ready governance artifacts, and kept raw data read-only.

New algorithm/package notes:

- EIS now recognizes common `Z'`, `Z"`, unicode prime, and `Freq/Hz` style headers.
- Mott-Schottky no longer treats `Current/A` as capacitance.
- XPS residual/difference/error columns no longer enter component-area calculations.
- Metadata records algorithm provenance and candidate-method details.
- Raman/PL/FTIR processors add optional pybaselines ASLS baseline/corrected-intensity candidate columns when available.
- Local peak candidates use scipy when available, with the existing fallback retained.
- Installed/import-smoked optional packages are documented in `phase1_9_package_integration_report.md`.
- GPL/expert-system packages remain reference-only and must not be imported into automatic processing.

## Previous State: Phase 1.8

Read these first:

- `docs/agent_reports/PHASE1_10_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`
- `docs/agent_reports/phase1_10_final_validation.md`
- `docs/agent_reports/phase1_10_canonical_freeze_report.md`
- `docs/agent_reports/phase1_10_next_manual_review_batch_plan.md`
- `docs/agent_reports/phase1_8_execution_plan.md`
- `docs/agent_reports/phase1_8_reviewed_queue_report.md`
- `docs/agent_reports/phase1_8_manual_review_required_filtered_report.md`
- `docs/agent_reports/phase1_8_final_validation.md`
- `output/reports/phase1_8_final_summary.md`
- `output/reports/phase1_8_new_auto_process_plan.md`
- `output/reports/readiness_report.md`

Latest locked Origin package: `output\phase1_6_origin_results_20260531_041538`.

## Phase 1.10 Current State

- Canonical package: `output\phase1_6_origin_results_20260531_041538`
- Final locked manifest: `output\final_locked_results\freeze_*`
- Material collection: `output\material_collections\cwo_bobc_bicu_with_xps_unprocessed_20260531_133711`
- Material collection role: mixed secondary material-selection package. It is not canonical and should not be passed directly to `origin-batch`.
- Normalized material manifest: `output\reports\phase1_10_material_collection_normalized_manifest.csv`
- Normalized material dry-run result: 1340 skipped, 0 planned, 0 blocked, no Origin launch.
- Phase 1.10 did not install packages, process MANUAL_REVIEW, launch real Origin export, or modify raw/workspace/F-drive source data.

## What Has Been Processed

- Phase 1.5 no-Origin package: 167 datasets.
- Phase 1.6 Origin package: 167 datasets.
- Successful Origin types: EIS 22, photocurrent 3, Raman 30, Mott-Schottky 90, EPR 13, XPS 9.
- Phase 1.7 and Phase 1.8 processed no new real datasets and exported no new Origin figures.
- Legacy BET outputs exist under `D:\Codex Project\科研数据处理\数据\26.5.29\BET`, but BET has not been incorporated into the standardized Phase 1.6 package.
- Separate XPS figure-output workflows exist outside the Phase 1.8 queue gate. Check `docs\xps_origin_plotting_guardrails.md`, `output\xps_heterojunction_stacked\reports\xps_heterojunction_stacked_summary.md`, and `outputs\xps_in_situ_20260506\xps_data_mapping_report.md` before changing XPS figure logic.

## Phase 1.8 Additions

- `run.py reviewed-queue --proposals ... --write-template` creates a user decision CSV.
- `run.py reviewed-queue --proposals ... --decisions ... --dry-run` validates approved rows and writes a plan with proposal/decision input SHA256 values.
- `run.py auto-queue` creates a dry-run plan and candidate queue from current AUTO_PROCESS items while excluding Phase 1.6 processed hashes.
- `run.py readiness` checks the locked package count, Phase 1.6 `result_summary.json`/`index.csv` consistency, current review artifacts, manual-review CSV/XLSX/report row consistency, desktop manual-review workbook sync, auto-queue dry-run flags, auto-queue plan/queue identity consistency, auto-queue dry-run provenance/no-processing notes, reviewed-queue proposal/template/plan consistency plus stored input SHA256 values and zero blocked approval rows, latest validation report safety markers and freshness, required active entry documents, summary freshness, review dashboard current links, workspace copy, F-drive backup, project-rename path hygiene, and forbidden PPT paths.
- Blank decisions skip rows.
- Only `approve_for_no_origin_queue` can approve a row.
- Approved rows require `approved_by` and `approval_date`.
- High-risk rows require `high_risk_ack=true`.
- Folder/header conflict rows require `folder_header_conflict_ack=true`.
- Decision CSV headers are strict. Missing, duplicate, unknown, blank-`proposal_id`, or malformed rows fail planning.
- Planner checks source path, current hash, current triage state, Phase 1.6 processed hashes, and forbidden types.
- Reviewed-queue and auto-queue both normalize forbidden type variants, including composite labels such as `SEM/TEM/NMR/MS`.
- Planner does not launch Origin and does not call `process`.
- Direct `process --from-queue output/reports/processing_queue.json` is guarded and returns queue-validation failures if the raw queue overlaps Phase 1.6 processed hashes. Queue items must also use a supported registry `data_type` and matching `selected_processor`. `--include-ambiguous` requires explicit promotion/user-approval provenance on each MANUAL_REVIEW queue item. `--auto-select` cannot be combined with `--with-origin` or an explicit `--from-queue`. Use `output/reports/phase1_8_new_auto_process_queue.json` instead.
- Queue-driven output names use a stable hash of the full queue id, so same-stem reviewed-queue files no longer collapse into one `sample_phase1_8` path.
- Current filtered manual-review workbook generated at `output/reports/phase1_8_manual_review_required_filtered.xlsx`.
- Desktop copy generated at `C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx`.

## Current Counts

- Phase 1.8 reviewed-queue proposals: 18
- Current dry-run approved/skipped/blocked: 0/18/0; reviewed-queue input hashes match current proposal and decision files.
- Latest triage: AUTO_PROCESS 188, MANUAL_REVIEW 618
- Current filtered manual-review workbook rows: 493
- Same-data items excluded from the main manual-review workbook: 125
- New AUTO_PROCESS candidate queue after Phase 1.6 exclusion: 105
- New AUTO_PROCESS candidate types: EPR 44, Mott-Schottky 32, EIS 24, photocurrent 5
- Raw `processing_queue.json` contains 83 items already represented in Phase 1.6; do not use it directly for the next batch.
- BET triage status: 0 AUTO_PROCESS, 23 MANUAL_REVIEW, proposals only.

## Paths

- Project root: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- Workspace copy: `workspace_data\LL_detection_copy_20260530`
- Stable F-drive backup: `F:\课题\LL\检测`
- Instruction archive: `D:\Codex Project\科研数据处理\指令归档`

## Commands

```powershell
D:\Python\python.exe -m pytest
D:\Python\python.exe run.py deps-audit
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py readiness
D:\Python\python.exe run.py readiness --no-desktop-review-xlsx
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --write-template
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --decisions output\reports\phase1_8_review_decisions_template.csv --dry-run
D:\Python\python.exe run.py auto-queue
```

## Safety

Do not modify F-drive backup or workspace source files. Do not process all MANUAL_REVIEW. Do not auto-apply override proposals. Do not create PPT paths or kinetics processors. Routine tests and no-Origin planning must not launch Origin. Real processing requires a future explicit user-approved queue.

## Phase 1.9 Suggestion

Next no-Origin expansion can start from `output\reports\phase1_8_new_auto_process_queue.json` after reviewing the dry-run plan. User-approved manual-review rows remain separate and must go through `reviewed-queue`. Do not use `--include-ambiguous` globally. Origin export remains a later explicit step after no-Origin QC. BET should remain manual/proposal-only until its adsorption/desorption columns and standardized package strategy are reviewed.

## Phase 1.11 Release Freeze And Hygiene Handoff

- Canonical package: `output\phase1_6_origin_results_20260531_041538`
- Locked results: `output\final_locked_results\freeze_20260602_011419`
- Locked count: 167
- Phase 1.11 handoff: `docs\agent_reports\PHASE1_11_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`
- Commit-ready report: `docs\agent_reports\phase1_11_commit_ready_report.md`
- Package audit: `docs\agent_reports\phase1_11_final_package_integrity_audit.md`
- Project hygiene audit: `docs\agent_reports\phase1_11_project_hygiene_audit.md`
- Report/script/output indexes live under `docs\indexes\`.

Future Codex agents should not put temporary scripts in the project root. Reusable maintenance scripts go in `scripts\maintenance`, one-off helpers go in `scripts\one_off`, and historical scripts go in `scripts\archive` only after reference checks. Do not move formal result packages, `workspace_data`, or F-drive backup data. Do not confuse `output` and `outputs`: `output` is the primary result repository, while `outputs` is specialized/historical output storage.

## Phase 1.12 Commit Preparation Handoff

- ALLOW_GIT_COMMIT was false.
- No `git add`, `git commit`, or `git tag` was executed.
- Pre-commit validation: `docs\agent_reports\phase1_12_pre_commit_validation.md`
- Git workspace audit: `docs\agent_reports\phase1_12_git_workspace_audit.md`
- Staging strategy: `docs\agent_reports\phase1_12_staging_strategy.md`
- Commit commands: `docs\agent_reports\phase1_12_commit_commands.md`
- Final handoff: `docs\agent_reports\PHASE1_12_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`

Recommended manual path is Scheme A unless the user explicitly wants audit reports in the commit. Never stage raw data, workspace source data, Phase result packages, OPJU/TIF/PNG artifacts, tmp files, `.pytest_cache`, `__pycache__`, or large binary outputs.
