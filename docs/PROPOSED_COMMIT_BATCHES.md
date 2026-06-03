# Proposed Commit Batches

This is a staging-review plan only. Do not execute `git add`, `git commit`, or deletion/move operations from this document without explicit user approval.

## Global Rules

- Do not commit OPJU, TIF, PNG, XLSX, ZIP, large generated JSON, copied raw/workspace data, or large output directories.
- Do not commit `output/processed_data`, `output/metadata`, `output/origin_files`, `output/figures_tif`, `output/figures_preview`, `output/material_collections`, `output/opju_exemplar_regression`, `output/bet_reference_compare`, `output/xps_heterojunction_stacked`, or `outputs/xps_in_situ_20260506`.
- Do not bulk stage `output/reports/`.
- Do not use Phase 1.6 as the current engineering phase. It is the locked canonical result package.
- Each batch should be reviewed with `git diff --cached --stat`, `git diff --cached --name-status`, and an explicit file list before commit.

## Batch 1: Current Status / Index / Cleanup Docs

Purpose: establish the current source of truth and cleanup policy before touching code.

Candidate paths:

- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
- `docs/CURRENT_STATUS.md`
- `docs/PROJECT_INDEX.md`
- `docs/DIRTY_WORKTREE_GROUPING_PLAN.md`
- `docs/OUTPUT_LAYOUT_CLEANUP_PLAN.md`
- `docs/NEXT_FUNCTION_FIX_ORDER.md`
- `docs/LIGHT_CLEANUP_EXECUTION_A_REPORT.md`
- `docs/PROPOSED_COMMIT_BATCHES.md`

Notes:

- Root docs should contain only pointer-level updates in this batch.
- Do not include `docs/agent_reports/*` in Batch 1 unless a specific lightweight report is explicitly approved.
- Do not include any `output/` paths.

Suggested review commands for a later staging phase:

```powershell
git diff -- README.md PROJECT_STATUS.md TASK_BOARD.md AGENT_HANDOFF.md docs/CURRENT_STATUS.md docs/PROJECT_INDEX.md docs/DIRTY_WORKTREE_GROUPING_PLAN.md docs/OUTPUT_LAYOUT_CLEANUP_PLAN.md docs/NEXT_FUNCTION_FIX_ORDER.md docs/LIGHT_CLEANUP_EXECUTION_A_REPORT.md docs/PROPOSED_COMMIT_BATCHES.md
git status --short
```

## Batch 2: Core Source / Config / Tests

Purpose: stage formal code/config/test changes only after Batch 1 has fixed the status baseline.

Candidate paths:

- `src/cli.py`
- `src/core/deps.py`
- `src/core/epr_jeol.py`
- `src/core/epr_overlay.py`
- `src/core/metadata.py`
- `src/core/phase1_7.py`
- `src/core/phase1_9.py`
- `src/core/process.py`
- `src/core/runtime_paths.py`
- `src/core/table_reader.py`
- `src/core/validate.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `src/origin/__init__.py`
- `src/origin/adapter.py`
- `src/origin/operations.py`
- `src/origin/plot_policy.py`
- `src/origin/text_format.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `src/adapters/`
- `config/data_selection_rules.yaml`
- `config/default.yaml`
- `config/plot_style.yaml`
- `optional_requirements.txt`
- `pyproject.toml`
- targeted tests under `tests/`

Candidate test paths:

- `tests/test_epr_overlay.py`
- `tests/test_jeol_epr_decode.py`
- `tests/test_manual_review_filtered_report.py`
- `tests/test_origin_adapter.py`
- `tests/test_origin_operations.py`
- `tests/test_origin_plot_policy.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_13_adapters.py`
- `tests/test_phase1_1_process_cli.py`
- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_phase1_contracts.py`
- `tests/test_processor_behaviors.py`
- `tests/test_xps_heterojunction_stacked.py`

Notes:

- This batch must be reviewed by domain because it contains real behavior changes.
- Do not include generated outputs.
- Do not include new phase reports unless needed for the code review.
- Run only agreed targeted verification commands during staging review.

## Batch 3: Script Directory Migration

Purpose: make script layout coherent after confirming references.

Candidate paths:

- `scripts/README.md`
- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `scripts/reports/README.md`
- `scripts/reports/regenerate_manual_review_filtered.py`
- possible deletion confirmation: `scripts/regenerate_manual_review_filtered.py`

Deletion condition for `scripts/regenerate_manual_review_filtered.py`:

- old path has no functional references
- new `scripts/reports/regenerate_manual_review_filtered.py` is staged
- `tests/test_manual_review_filtered_report.py` imports the new path
- `docs/indexes/scripts_index.md` points to the new path
- focused script-related tests or import checks pass

Do not confirm the deletion without staging the replacement and test updates in the same batch.

## Batch 4: Necessary Lightweight Reports

Purpose: include only small, necessary report files that explain code/config/script changes.

Candidate report classes:

- selected `docs/agent_reports/*.md`
- selected `docs/indexes/*.md`
- selected small `output/reports/*.md` if explicitly approved

Do not bulk include:

- `output/reports/*.json`
- `output/reports/*.xlsx`
- `output/reports/*.zip`
- `output/reports/*.txt`
- large generated Markdown reports
- OPJU/TIF/PNG reference exports or previews

Batch 4 should be optional. If Batch 1-3 can stand without generated reports, skip Batch 4.

## Absolute Do-Not-Commit List

Do not stage or commit these unless the user explicitly overrides this plan:

- `output/phase1_6_origin_results_20260531_041538/`
- `output/final_locked_results/`
- `output/phase1_5_processed_results_20260531_005613/`
- `output/material_collections/`
- `output/processed_data/`
- `output/metadata/`
- `output/origin_files/`
- `output/figures_tif/`
- `output/figures_preview/`
- `output/opju_exemplar_regression/`
- `output/bet_reference_compare/`
- `output/xps_heterojunction_stacked/`
- `outputs/xps_in_situ_20260506/`
- `output/reports/_tmp_*`
- `output/reports/tmp_opju_compare.*`
- `output/reports/phase1_13_pip_*.txt`
- `output/reports/phase1_9_handoff_report_bundle.zip`
- `output/reports/xps_template_compare/`
- any OPJU/TIF/PNG/XLSX/ZIP generated artifact

## Recommended Next Step

Start with Batch 1 staging review only. The expected result should be a small documentation commit that makes the current status and cleanup policy clear before any code or report staging begins.
