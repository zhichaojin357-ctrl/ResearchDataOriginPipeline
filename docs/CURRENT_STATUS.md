# Current Status

MEGA update: 2026-06-04.

The sections below preserve the 2026-06-03 audit snapshot. For the current MEGA convergence state, use these newer documents first:

- `docs/MEGA_CONVERGENCE_START_SNAPSHOT.md`
- `docs/OUTPUT_REPORTS_FULL_POLICY_REVIEW.md`
- `docs/OUTPUT_REPORTS_KEEP_AND_USER_DECISION.md`
- `docs/AGENT_REPORTS_POLICY_REVIEW.md`
- `docs/ROOT_AND_PROJECT_DOCS_CONSISTENCY_REVIEW.md`
- `docs/MEGA_CONVERGENCE_FINAL_SELF_AUDIT.md` after it is generated

Current MEGA facts before final self-audit:

- `src/config/tests/scripts` is clean.
- XPS source/test files are clean.
- `docs/agent_reports` has been committed as formal documentation/provenance.
- Generated `output/reports` JSON, CSV, TXT, and generated Markdown report families are now ignored/untracked by policy.
- The remaining visible `output/reports` item is `output/reports/README.md`, a tracked modified user-decision item.
- Origin, real-data processing, OPJU/TIF/PNG/PDF/XLSX generation, and visual acceptance remain blocked unless a future explicit goal permits them.

Audit time: 2026-06-03 15:13:54 +08:00.

Scope: status audit only. No source code was changed, no files were deleted, and no git staging or commit was performed. This audit read the current working tree, git state, source entry points, configs, and latest reports. The validation/readiness reports were not regenerated during this audit; the latest existing reports from 2026-06-03 were used as evidence to avoid adding extra generated-report churn.

## Executive Summary

The current locked result package is still Phase 1.6:

`output/phase1_6_origin_results_20260531_041538`

That package contains 167 completed Origin result rows and remains the canonical result package/release baseline. It is not the current engineering phase.

The working tree has moved beyond the committed Phase 1.10-1.11 baseline. Current disk evidence includes Phase 1.13 adapter/package integration and Phase 1.14 OPJU-exemplar regression work, plus BET, XRD, EPR, and path-cleanup follow-up reports. The repository is dirty and contains many uncommitted source, test, config, report, and output changes.

## Git State

- Branch: `master`
- HEAD: `116b393 (HEAD -> master) Phase 1.10-1.11: stabilize manifests and freeze release baseline`
- Dirty worktree before adding this status/index pair:
  - 100 tracked modified/deleted paths
  - 239 untracked paths
  - 339 total `git status --short` entries
- Historical root report helper `scripts/regenerate_manual_review_filtered.py` has been migrated to `scripts/reports/regenerate_manual_review_filtered.py`.
- Important implication: current disk state is ahead of the latest commit. Do not treat commit `116b393` as the full current project state.

## Formal Entry Points

Use the repo root:

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

Use the pinned Python executable:

`D:\Python\python.exe run.py ...`

`run.py` is a thin wrapper that imports `src.cli.main`. The formal CLI command surface currently includes:

- `scan`
- `triage`
- `process`
- `origin-test`
- `origin-batch`
- `manifest-normalize`
- `reviewed-queue`
- `auto-queue`
- `xps-heterojunction-stacked`
- `jeol-epr-decode`
- `epr-overlay`
- `deps-audit`
- `validate`
- `readiness`
- `phase1-9-governance`

Important command semantics:

- `process` defaults to no-Origin unless `--with-origin` is explicit.
- `origin-batch` is a planner/dry-run path by default and should not be treated as a live Origin executor.
- Do not run the raw `output/reports/processing_queue.json` directly for the next batch. Use `output/reports/phase1_8_new_auto_process_plan.json` and `output/reports/phase1_8_new_auto_process_queue.json` after review.
- `reviewed-queue` and `auto-queue` are safety gates; they plan queues and do not launch Origin or process data by themselves.

## Latest Effective Documents

The root files `README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, and `AGENT_HANDOFF.md` still contain older Phase 1.9/1.13 framing and some stale queue counts. They are useful historical entry points but are not sufficient as the current state of record.

Current evidence should prioritize these latest files:

- `output/reports/readiness_report.md`
- `output/reports/validation_report.md`
- `output/reports/dependency_audit.md`
- `docs/agent_reports/non_xrd_reorg_path_audit_20260603.md`
- `docs/agent_reports/xrd_path_and_temp_script_cleanup_20260603.md`
- `output/reports/xrd_opju_exemplar_comparison_20260602.md`
- `output/reports/phase1_14_opju_exemplar_regression_comparison.md`
- `docs/agent_reports/phase1_14_opju_exemplar_driven_requirement_update.md`
- `docs/agent_reports/bet_opju_exemplar_optimization_20260602.md`
- `docs/agent_reports/phase1_13_final_validation.md`
- `docs/agent_reports/PHASE1_13_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`
- `docs/agent_reports/phase1_11_release_freeze_baseline.md`

Current effective phase interpretation:

- Locked result package: Phase 1.6.
- Release-freeze/governance baseline: Phase 1.10-1.11, committed at `116b393`.
- Adapter/package integration: Phase 1.13, present in current dirty tree.
- Latest active work on disk: Phase 1.14 OPJU exemplar regression, BET OPJU fix, XRD OPJU comparison/path cleanup, non-XRD path audit.

## Validation Evidence

Latest existing reports show:

- `validate`: pass
- `readiness`: 21 checks, 0 failures, 0 warnings, ready true
- `origin-batch` dry-run on Phase 1.6 package: total 167, planned 0, skipped 167, blocked 0, no Origin launch
- `deps-audit`: core dependencies available; optional `ramanspy`, `rampy`, and `spectrochempy` missing as warnings

These reports are current as files on disk from 2026-06-03 14:25-14:28, but they were not rerun by this audit.

## Phase 1.6 Status

Phase 1.6 is a historical/canonical result package, not the current engineering version.

Evidence from `output/phase1_6_origin_results_20260531_041538/index.csv`:

- Rows: 167
- Types:
  - `Mott-Schottky`: 90
  - `Raman`: 30
  - `EIS`: 22
  - `EPR`: 13
  - `XPS`: 9
  - `photocurrent`: 3
- `origin-batch --dry-run` skips all 167 as already complete.

## Supported Data Types

`config/processor_registry.yaml` currently declares 14 Phase 1 supported data types:

- `photocurrent`
- `BET`
- `EPR`
- `PL`
- `XPS`
- `XRD`
- `UV-vis DRS`
- `photocurrent_response`
- `reaction_condition_screening`
- `FTIR`
- `Raman`
- `Mott-Schottky`
- `HPLC/LC exported data`
- `EIS`

Scan-only/deferred/reference types currently include:

- `SEM_image_data`
- `TEM_image_data`
- `NMR`
- `MS`
- `reference_literature`

Do not convert scan-only/deferred types into processors without explicit approval. Kinetics/reference-literature folders remain reference-only, not experimental kinetics processing.

## Formal Pipeline Capabilities

Already in formal code/CLI:

- Raw data scanning: `scan`
- Triage/classification and queue generation: `triage`, `auto-queue`, `reviewed-queue`
- Table processing and metadata writing: `process`
- Origin plot export through shared adapter: `src/origin/adapter.py`
- Origin operations/style support: `src/origin/operations.py`, `src/origin/plot_policy.py`, `src/origin/text_format.py`, `config/plot_style.yaml`
- Manifest normalization and dry-run package planning: `manifest-normalize`, `origin-batch`
- Validation/governance: `validate`, `readiness`, `deps-audit`, `phase1-9-governance`
- JEOL EPR raw decode: `jeol-epr-decode`
- EPR condition overlays: `epr-overlay`
- XPS heterojunction stacked comparison figures: `xps-heterojunction-stacked`
- Optional lazy adapters under `src/adapters/` for candidate/provenance use only

The formal automatic flow remains candidate-metric only. It must not auto-assign XPS valence, EPR radicals, XRD phase/planes, MS products, heterojunction mechanisms, photocurrent carrier separation, PL recombination, or CB/VB positions.

## Current OPJU Exemplar Status

Phase 1.14 OPJU comparison evidence:

- `output/reports/phase1_14_opju_exemplar_regression_comparison.md`: 8 total, 7 PASS, 1 warning
- Warning item: Raman, verdict `WARNING_OPJU_CONTRACT_DELTA`
- `output/reports/xrd_opju_exemplar_comparison_20260602.md`: 2 XRD BWO items, both PASS
- EPR has been corrected to a condition-overlay OPJU comparison contract and currently reports PASS for OH/O3 overlay outputs in the Phase 1.14 comparison report
- BET OPJU fix is present in code/tests/reports and has real generated outputs, but the report still says follow-up OPJU comparisons for other types were paused

Important remaining gap:

- I did not find a clear current report proving XPS has completed the same OPJU-exemplar comparison against a user OPJU reference. Existing XPS output/QC is not the same as completed OPJU exemplar regression.

## Output Directory State

`output/` is the primary output root, but it is mixed and easy to misuse.

Current top-level output inventory:

- `output/phase1_6_origin_results_20260531_041538`: canonical locked 167-result package
- `output/final_locked_results`: release-freeze pointer/manifest artifacts
- `output/reports`: versioned reports and many phase artifacts
- `output/review_dashboard`: review dashboards
- `output/processed_data`, `output/metadata`, `output/origin_files`, `output/figures_tif`, `output/figures_preview`: active/generated result artifacts
- `output/opju_exemplar_regression`: copied OPJU references, reference exports, comparison inputs, and temporary compare material
- `output/material_collections`: large mixed secondary package, not a direct standard result package
- `output/phase1_5_processed_results_20260531_005613`: historical no-Origin package
- `output/xps_heterojunction_stacked`: specialized XPS outputs
- `output/origin_jobs`: currently empty after cleanup

`outputs/` is separate and currently holds specialized/historical output:

- `outputs/xps_in_situ_20260506`

Conclusion: the output tree is operational but crowded. Do not infer current status from folder names alone. Use reports, manifests, and CLI dry-runs.

## Temporary, Demo, Or Historical Paths

Do not treat these as the general formal pipeline:

- `output/reports/tmp_opju_compare.*`
- `output/reports/_tmp_xps_bi_check.png`
- `output/opju_exemplar_regression/_tmp_preview`
- `output/opju_exemplar_regression/temp_preview_compare`
- `scripts/one_off/*`
- `scripts/maintenance/opju_exemplar_regression.py` as a comparison/regression helper, not a production processor
- `scripts/data_types/xps/build_xps_in_situ_20260506.py` as a dedicated XPS figure helper, not the general queue pipeline; the old root-level helper path is historical only
- `output/phase1_5_processed_results_20260531_005613` as historical no-Origin output
- raw `output/reports/processing_queue.json` for future batch processing

## Most Important Next Fixes

1. Cleanly reconcile and stage the dirty worktree in batches. Current disk state is useful but not committed; commit scope must avoid large/generated artifacts unless intentionally selected.
2. Update or supersede stale root status docs. Current root docs still contain older Phase 1.9/1.13 wording and older queue counts.
3. Complete XPS OPJU-exemplar comparison with an explicit current report, not just existing XPS outputs/QC.
4. Fix the Raman OPJU contract warning or document why the visual/structure delta is acceptable.
5. Keep BET changes formalized, but review generated BET previews before treating the new outputs as accepted production style.
6. Do not bulk-process `MANUAL_REVIEW`. Latest non-XRD audit reports `MANUAL_REVIEW=663`; current filtered user workbook remains 493 rows requiring review.
7. If processing new data, start with a small explicitly approved no-Origin queue from `phase1_8_new_auto_process_queue.json`, not the raw processing queue.
8. Keep optional dependency warnings as non-blocking unless Raman-specific package work is explicitly approved.
