# Light Cleanup Execution A Report

Execution time: 2026-06-03 15:36:34 +08:00.

Scope: light整理 execution A. No plotting functionality was changed, no new data was processed, Origin was not run, no files were deleted or moved, and no git staging/commit was performed.

## Commands Run

Allowed checks run:

- `git status --short`
- `git diff --stat`
- `git diff --check`
- `git grep -n --untracked "scripts/regenerate_manual_review_filtered.py"`
- `git grep -n --untracked "regenerate_manual_review_filtered"`
- `git grep -n "def |if __name__|build_rows|write_csv|write_xlsx" HEAD -- scripts/regenerate_manual_review_filtered.py`
- `git grep -n --untracked "def |if __name__|build_rows|write_csv|write_xlsx" -- scripts/reports/regenerate_manual_review_filtered.py`
- `git grep -n --untracked "scripts.reports.regenerate_manual_review_filtered|scripts/reports/regenerate_manual_review_filtered.py|scripts\\reports\\regenerate_manual_review_filtered.py"`

No `validate`, `readiness`, full `pytest`, data processing command, Origin command, `git add`, or `git commit` was run.

## Files Changed This Round

Minimal root-level status pointer updates:

- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`

New light-cleanup docs:

- `docs/LIGHT_CLEANUP_EXECUTION_A_REPORT.md`
- `docs/PROPOSED_COMMIT_BATCHES.md`

The root document edits only add a short top-level pointer:

- current state authority is `docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md`
- Phase 1.6 is the locked canonical result package, not the current engineering phase
- existing historical content may lag current dirty worktree

No source, config, tests, scripts, output directories, reports, OPJU, TIF, PNG, XLSX, or ZIP files were modified by this round.

## Git State Observed

Before this report and `PROPOSED_COMMIT_BATCHES.md` were written, `git status --short` total was 344 entries.

The 344-entry state included previously created整理 docs:

- `docs/CURRENT_STATUS.md`
- `docs/PROJECT_INDEX.md`
- `docs/DIRTY_WORKTREE_GROUPING_PLAN.md`
- `docs/OUTPUT_LAYOUT_CLEANUP_PLAN.md`
- `docs/NEXT_FUNCTION_FIX_ORDER.md`

After writing this report pair, the expected total is 346 entries because two new untracked docs were added.

Tracked diff remains broad and pre-existing. `git diff --stat` still reports 100 tracked files changed with large churn dominated by generated reports under `output/reports`.

`git diff --check` completed without whitespace/conflict-marker errors. It printed line-ending warnings for existing working-copy files because Git reports LF-to-CRLF conversion warnings on this Windows checkout.

## Script Deletion Check

Tracked deletion under review:

- `scripts/regenerate_manual_review_filtered.py`

Candidate replacement:

- `scripts/reports/regenerate_manual_review_filtered.py`

### Reference Search Evidence

Exact old path search:

- `git grep -n --untracked "scripts/regenerate_manual_review_filtered.py"` found only status/整理 documentation references:
  - `docs/CURRENT_STATUS.md`
  - `docs/DIRTY_WORKTREE_GROUPING_PLAN.md`
  - `docs/PROJECT_INDEX.md`

Generic script-name search found functional references to the new path:

- `docs/indexes/scripts_index.md` lists `scripts\reports\regenerate_manual_review_filtered.py`
- `tests/test_manual_review_filtered_report.py` imports `scripts.reports.regenerate_manual_review_filtered`
- `output/reports/phase1_11_project_hygiene_audit.json` records the new report-script path

### Interface Equivalence Evidence

Using `git grep` against `HEAD -- scripts/regenerate_manual_review_filtered.py` and against the untracked replacement showed the same function/entrypoint names:

- `norm_key`
- `short_reason`
- `action_for`
- `phase16_keys`
- `build_rows`
- `write_csv`
- `write_xlsx`
- `write_report`
- `main`
- `if __name__ == "__main__"`

### Decision

There is enough evidence to mark the tracked deletion as a candidate for confirmation in a later script-layout commit:

`scripts/regenerate_manual_review_filtered.py` can be confirmed deleted later if `scripts/reports/regenerate_manual_review_filtered.py` is staged with the corresponding tests and script index.

No deletion was committed in this round. The final Batch 3 review should still include a focused diff/test review before accepting the deletion.

## Output/Report Files Left Unprocessed

Per user instruction, this round did not stage, commit, move, delete, or rewrite output/report files.

Still intentionally unprocessed:

- all modified tracked files under `output/reports/`
- all untracked files under `output/reports/`
- `output/adapter_shadow_runs/`
- `output/bet_reference_compare/`
- `output/final_locked_results/`
- `output/opju_exemplar_regression/`
- `output/processed_data/`
- `output/metadata/`
- `output/origin_files/`
- `output/figures_tif/`
- `output/figures_preview/`
- `output/material_collections/`
- `output/xps_heterojunction_stacked/`
- `outputs/xps_in_situ_20260506/`

Clearly temporary/report-debug candidates are still only listed, not moved:

- `output/reports/tmp_opju_compare.*`
- `output/reports/_tmp_*`
- `output/reports/phase1_13_pip_*.txt`
- `output/bet_reference_compare/title_fix_trial*`
- `output/opju_exemplar_regression/temp_preview_compare/`
- `output/opju_exemplar_regression/_tmp_preview/`

## Current Risk Notes

- The worktree remains heavily dirty. This is expected and was not resolved by this phase.
- Root status docs now point to current status docs, but their historical sections still contain older phase material.
- Output reports remain mixed and should not be bulk staged.
- The script deletion has enough routing/equivalence evidence for later candidate deletion, but it is not committed and should still be reviewed in Batch 3.
- No validation report was refreshed in this round; do not infer new pass/fail status from this cleanup.

## Can We Enter Candidate Commit Batch Review?

Yes, for Batch 1 staging review only, if the user agrees that Batch 1 is documentation-only and limited to current status/index/cleanup planning docs plus the four root pointer updates.

Do not start Batch 2, Batch 3, or any output/report staging until Batch 1 is reviewed separately.
