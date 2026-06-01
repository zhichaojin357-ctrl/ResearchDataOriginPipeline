# Project Status

## Phase 1.8 Status

Phase 1.8 is the current reviewed-queue safety gate. It turns Phase 1.7 review-only proposals into a user decision template and dry-run plan, but it does not run new real processing and does not launch Origin.

- Phase 1.8 instruction archive: `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_phase1_8_reviewed_queue_and_processing_gate_instruction.md`
- Phase 1.8 instruction SHA256: `B3F2A025FC2235F1920C3EDCBB5B274C970B9C458F9D9B8054D46D0C18F508CA`
- Reviewed-queue template: `output\reports\phase1_8_review_decisions_template.csv`
- Reviewed-queue dry-run plan: `output\reports\phase1_8_reviewed_queue_plan.md`
- Current manual review workbook: `output\reports\phase1_8_manual_review_required_filtered.xlsx`
- Current manual review CSV: `output\reports\phase1_8_manual_review_required_filtered.csv`
- Current reviewed-queue dry-run: 18 proposals, 0 approved, 18 skipped, 0 blocked, Origin launch false, process false, input SHA256 values recorded.
- New AUTO_PROCESS dry-run plan: `output\reports\phase1_8_new_auto_process_plan.md`
- New AUTO_PROCESS candidate queue: `output\reports\phase1_8_new_auto_process_queue.json`
- BET status: legacy processed OPJU/PNG/TSV/CSV outputs exist under `D:\Codex Project\科研数据处理\数据\26.5.29\BET`, but BET is not yet part of the standardized Phase 1.6 package or current auto-queue.
- Auto-queue guard: forbidden type variants such as `sem_image_data`, `SEM/TEM/NMR/MS`, `reference_literature`, and `动力学` are normalized and blocked before any future queue output.
- Reviewed-queue guard: user-approved proposal rows also normalize and block forbidden composite type labels such as `SEM/TEM/NMR/MS` before any future queue candidate is created. Decision CSV headers are now strict: missing, duplicate, unknown, blank-`proposal_id`, or malformed rows fail planning instead of being silently skipped.
- Process queue guard: direct `process --from-queue output/reports/processing_queue.json` is blocked when that raw queue still contains source hashes already represented in the Phase 1.6 package; queue items also must use a supported registry `data_type` and matching `selected_processor`; `--include-ambiguous` requires explicit promotion/user-approval provenance; `--auto-select` cannot be combined with `--with-origin` or an explicit queue. Use `phase1_8_new_auto_process_queue.json` after reviewing the dry-run plan.
- Queue output guard: queue-driven processed/metadata/Origin artifact names now use a stable hash of the full `queue_id`, preventing reviewed-queue `phase1_8_*` ids with the same source stem from collapsing into one output path.
- Readiness report: `output\reports\readiness_report.md`; latest run reported 21 checks, 0 failures, 0 warnings.
- Validate guard: deferred/reference registry entries must remain `scan_only`, `supported_in_phase_1=false`, and `selected_processor=none`.
- Readiness guard: `run.py readiness` now fails if `output\reports\validation_report.md` contains failure markers, is missing the deferred/reference, PPT, or kinetics pass markers, or is older than validation-related source/config files.
- Phase 1.6 package summary guard: `run.py readiness` now verifies that `index.csv`, `result_summary.total_results`, and `result_summary.by_type` all agree with the locked 167-result count.
- Project rename/docs guard: `run.py readiness` now verifies that the old sibling project path is absent and required active entry documents exist and no longer point to the old project path.
- Manual-review consistency guard: `run.py readiness` now verifies that the filtered manual-review CSV row count, Excel `Review` sheet row count, and report row count all match.
- Desktop review workbook guard: `run.py readiness` now verifies that `C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx` matches the project copy by SHA256. Use `--no-desktop-review-xlsx` only for portable/CI-style checks where the desktop copy is intentionally absent.
- Review dashboard guard: `run.py readiness` now verifies that `output\review_dashboard\index.md` points to the current filtered workbook and auto-queue plan, not the historical post-AI list.
- Auto-queue consistency guard: `run.py readiness` now verifies that accepted_count matches the generated queue length, the queue identities match the embedded dry-run plan queue, blocked_count is 0, all queue items remain `origin_export_allowed=false`, all queue items require manual checks, and every candidate keeps Phase 1.8 dry-run provenance/no-processing notes.
- Reviewed-queue consistency guard: `run.py readiness` now verifies that proposal JSON, user decision template, and reviewed-queue dry-run plan agree; the plan must be newer than both inputs, stored input SHA256 values must match current files, blocked approval rows must be zero, and the plan must remain no-Origin/no-process.

## Phase 1.6 Locked Result

- Package: `output\phase1_6_origin_results_20260531_041538`
- Origin success: 167
- Origin failure: 0
- Visual QC: 167 `QC_PASS`
- Material/color verification: PASS
- XPS repair: 9 no-Origin success, 9 Origin success, 0 failure

## Separate XPS Figure Outputs

- Phase 1.8 queue status does not include separate XPS figure-output workflows.
- Guardrails: `docs\xps_origin_plotting_guardrails.md`
- Stacked heterojunction summary: `output\xps_heterojunction_stacked\reports\xps_heterojunction_stacked_summary.md`
- In-situ XPS mapping: `outputs\xps_in_situ_20260506\xps_data_mapping_report.md`

## Latest Triage

- Total files: 1644
- AUTO_PROCESS: 188
- MANUAL_REVIEW: 618
- EXCLUDE_INVALID: 113
- DUPLICATE_SUPPRESSED: 66
- AUXILIARY_ONLY: 117
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17
- New safe promotion candidates: 0
- New review-only override proposals: 18
- New AUTO_PROCESS candidates after excluding Phase 1.6 processed hashes: 105
- New AUTO_PROCESS candidate types: EPR 44, Mott-Schottky 32, EIS 24, photocurrent 5

## Current Manual Review Workbook

- Current filtered workbook: `output\reports\phase1_8_manual_review_required_filtered.xlsx`
- Desktop copy: `C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx`
- Current MANUAL_REVIEW total: 618
- Excluded from main user-review workbook because same data already has a successful/processable representative: 125
- Still requiring user review in the current workbook: 493
- Historical post-AI list remains available at `output\reports\phase1_8_manual_review_required_after_ai.csv`, but it is no longer the current user-facing list.

## Current Blocking Items

- User must review the 167 Origin PNG previews before manuscript use.
- User must fill `phase1_8_review_decisions_template.csv` before any Phase 1.9 reviewed manual queue can be built.
- User should review `phase1_8_manual_review_required_filtered.xlsx` for files that remain unprocessable or need export/parser decisions.
- Future no-Origin processing should use `phase1_8_new_auto_process_queue.json`, not the raw `processing_queue.json`, because 83 raw queue items are already represented in Phase 1.6.
- This directory is not currently confirmed clean for commit; run `git status` and commit only after reviewing the dirty worktree.
- Parallel Origin up to 8 remains blocked until a task-owned instance tracker and user confirmation exist.

## Scope Guards

PPT generation, kinetics processors, SEM/TEM/NMR/MS processors, automatic XPS valence assignment, EPR radical assignment, XRD phase assignment, and full MANUAL_REVIEW batch processing remain forbidden.
