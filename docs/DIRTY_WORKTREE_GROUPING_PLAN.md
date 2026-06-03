# Dirty Worktree Grouping Plan

Audit time: 2026-06-03 15:36:34 +08:00.

Scope: read-only整理审计 plus this requested Markdown output. No source code was edited, no output files were moved or deleted, and no git staging/commit was performed.

Important baseline: this plan is based on `git status --short` before creating `DIRTY_WORKTREE_GROUPING_PLAN.md`, `OUTPUT_LAYOUT_CLEANUP_PLAN.md`, and `NEXT_FUNCTION_FIX_ORDER.md`. At that point the worktree had 341 dirty entries. After these three requested docs are written, `git status --short` is expected to increase by 3.

## Repository State

- Branch: `master`
- HEAD: `116b393 (HEAD -> master) Phase 1.10-1.11: stabilize manifests and freeze release baseline`
- Repo root: `D:/Codex Project/科研数据处理/ResearchDataOriginPipeline`
- Current state authority: current disk + git status + `docs/CURRENT_STATUS.md` + `docs/PROJECT_INDEX.md`
- Phase 1.6 interpretation: locked historical/canonical result package, not the current engineering phase.

## Status Counts

`git status --short` before this doc generation:

| status | count |
|---|---:|
| modified | 99 |
| deleted | 1 |
| untracked | 241 |
| total | 341 |

Path-category counts:

| status | source | config/deps | tests | docs | scripts | output | other |
|---|---:|---:|---:|---:|---:|---:|---:|
| modified | 16 | 5 | 11 | 20 | 2 | 45 | 0 |
| deleted | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| untracked | 5 | 0 | 4 | 66 | 4 | 162 | 0 |

`git diff --stat` for tracked changes reports 100 files changed, 41398 insertions, 25841 deletions. Most line churn is generated report JSON/Markdown under `output/reports`.

## Modified Files

Tracked modified files, grouped by path role:

### Source

- `src/cli.py`
- `src/core/deps.py`
- `src/core/epr_jeol.py`
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
- `src/processors/base.py`
- `src/processors/calculations.py`

### Config / Dependency / Project Metadata

- `config/data_selection_rules.yaml`
- `config/default.yaml`
- `config/plot_style.yaml`
- `optional_requirements.txt`
- `pyproject.toml`

### Tests

- `tests/test_jeol_epr_decode.py`
- `tests/test_manual_review_filtered_report.py`
- `tests/test_origin_adapter.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_1_process_cli.py`
- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_phase1_contracts.py`
- `tests/test_processor_behaviors.py`
- `tests/test_xps_heterojunction_stacked.py`

### Docs / Governance

- `AGENTS.md`
- `AGENT_HANDOFF.md`
- `PROJECT_STATUS.md`
- `README.md`
- `TASK_BOARD.md`
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- `docs/REAL_DATA_INTAKE_GUIDE.md`
- `docs/agent_reports/README.md`
- `docs/agent_reports/phase1_6_material_color_map.md`
- `docs/agent_reports/phase1_8_new_auto_process_queue_report.md`
- `docs/agent_reports/phase1_9_journal_ready_index.md`
- `docs/agent_reports/phase1_9_origin_plotting_skill_snapshot.md`
- `docs/agent_reports/phase1_9_package_integration_report.md`
- `docs/agent_reports/phase1_9_summary.md`
- `docs/indexes/output_reports_index.md`
- `docs/indexes/outputs_index.md`
- `docs/indexes/scripts_index.md`
- `docs/method_cards/README.md`
- `docs/method_cards/bet.md`
- `docs/method_cards/epr.md`

### Scripts

- `scripts/README.md`
- `scripts/build_xps_in_situ_20260506.py`

### Output Reports / Dashboards

- `output/reports/README.md`
- `output/reports/ambiguous_files.json`
- `output/reports/ambiguous_files.md`
- `output/reports/classification_report.md`
- `output/reports/data_triage_manifest.json`
- `output/reports/data_triage_report.md`
- `output/reports/dependency_audit.json`
- `output/reports/dependency_audit.md`
- `output/reports/duplicate_candidates.json`
- `output/reports/duplicate_candidates.md`
- `output/reports/excluded_files.json`
- `output/reports/excluded_files.md`
- `output/reports/inventory_manifest.json`
- `output/reports/origin_errors.md`
- `output/reports/pending_cleanup_candidates.md`
- `output/reports/phase1_6_material_color_map.json`
- `output/reports/phase1_6_material_color_map.md`
- `output/reports/phase1_8_new_auto_process_plan.json`
- `output/reports/phase1_8_new_auto_process_plan.md`
- `output/reports/phase1_8_new_auto_process_queue.json`
- `output/reports/phase1_9_journal_figure_qc.json`
- `output/reports/phase1_9_journal_figure_qc.md`
- `output/reports/phase1_9_journal_ready_index.csv`
- `output/reports/phase1_9_journal_ready_index.md`
- `output/reports/phase1_9_manual_review_required_final.xlsx`
- `output/reports/phase1_9_origin_plotting_skill_snapshot.json`
- `output/reports/phase1_9_origin_plotting_skill_snapshot.md`
- `output/reports/phase1_9_package_integration_report.json`
- `output/reports/phase1_9_package_integration_report.md`
- `output/reports/processing_queue.json`
- `output/reports/processing_queue.md`
- `output/reports/processing_report.json`
- `output/reports/processing_report.md`
- `output/reports/processing_summary.json`
- `output/reports/processing_summary.md`
- `output/reports/readiness_report.json`
- `output/reports/readiness_report.md`
- `output/reports/readiness_report_no_desktop.json`
- `output/reports/readiness_report_no_desktop.md`
- `output/reports/source_hash_index.json`
- `output/reports/traceability_groups.json`
- `output/reports/traceability_groups.md`
- `output/reports/validation_report.md`
- `output/review_dashboard/index.md`
- `output/review_dashboard/triage_index.md`

## Deleted Files

- `scripts/regenerate_manual_review_filtered.py`

This is the only tracked deletion. It appears to be related to script reorganization because `scripts/reports/regenerate_manual_review_filtered.py` is present as an untracked file. Do not assume deletion is safe until references are checked and the replacement path is confirmed.

## Untracked Files

Untracked paths are currently dominated by phase reports, output artifacts, OPJU regression material, new adapters, new Origin helper modules, and new tests.

### Untracked Docs

- `docs/CURRENT_STATUS.md`
- `docs/PROJECT_INDEX.md`
- 5 phase handoff files under `docs/agent_reports/PHASE1_*_HANDOFF...`
- Phase 1.9 to Phase 1.14 report files under `docs/agent_reports/`
- OPJU/BET/XRD/non-XRD reports under `docs/agent_reports/`

These are not all equal. `docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md` should be retained as current orientation docs. Many `docs/agent_reports/*` are generated reports and should be reviewed before committing.

### Untracked Source

- `src/adapters/`
- `src/core/epr_overlay.py`
- `src/origin/operations.py`
- `src/origin/plot_policy.py`
- `src/origin/text_format.py`

These look like real formal-code additions from Phase 1.13/1.14 work, not temporary files.

### Untracked Tests

- `tests/test_epr_overlay.py`
- `tests/test_origin_operations.py`
- `tests/test_origin_plot_policy.py`
- `tests/test_phase1_13_adapters.py`

These should be paired with the corresponding source additions if a commit is prepared.

### Untracked Scripts

- `scripts/data_types/`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `scripts/reports/`

These need staging review by purpose. `scripts/reports/regenerate_manual_review_filtered.py` may be the replacement for the deleted tracked root script.

### Untracked Output / Reports

Major untracked output groups:

- `output/adapter_shadow_runs/`
- `output/bet_reference_compare/`
- `output/final_locked_results/`
- `output/opju_exemplar_regression/`
- many `output/reports/phase1_10*`, `phase1_11*`, `phase1_12*`, `phase1_13*`, `phase1_14*`
- EPR overlay/decode reports under `output/reports/epr_*` and `output/reports/jeol_*`
- XRD OPJU comparison reports under `output/reports/xrd_*`
- `output/reports/xps_template_compare/`
- `output/review_dashboard/phase1_9_final_handoff_audit_index.md`

These should be retained on disk for provenance, but should not be bulk staged. Large OPJU/TIF/PNG/regression outputs should remain uncommitted unless the user explicitly chooses a narrow artifact commit.

## Grouping Plan

### A. Keep And Candidate For Commit

Scope: source/config/test/docs changes that preserve formal pipeline behavior and governance.

Candidate A paths:

- `src/cli.py`
- `src/core/*.py` modified files listed above
- `src/origin/*.py`
- `src/processors/*.py`
- `src/adapters/`
- `config/default.yaml`
- `config/plot_style.yaml`
- `config/data_selection_rules.yaml`
- `optional_requirements.txt`
- `pyproject.toml`
- `tests/*.py` modified and untracked test files listed above
- `scripts/README.md`
- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/reports/README.md`
- `scripts/reports/regenerate_manual_review_filtered.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `docs/CURRENT_STATUS.md`
- `docs/PROJECT_INDEX.md`
- current整理审计 docs from this turn
- `docs/REAL_DATA_INTAKE_GUIDE.md`
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- `docs/method_cards/*.md`
- `docs/indexes/*.md`, after confirming index freshness

Commit condition: only after a focused `git diff` review and explicit verification commands. Do not mix A with large output artifacts.

### B. Keep On Disk But Usually Do Not Commit

Scope: output results, generated reports, large generated artifacts, OPJU/TIF/PNG, copied references, comparison inputs, and package outputs.

Candidate B paths:

- `output/processed_data/`
- `output/metadata/`
- `output/origin_files/`
- `output/figures_tif/`
- `output/figures_preview/`
- `output/opju_exemplar_regression/`
- `output/bet_reference_compare/`
- `output/adapter_shadow_runs/`
- `output/final_locked_results/`
- `output/material_collections/`
- `output/phase1_5_processed_results_20260531_005613/`
- `output/phase1_6_origin_results_20260531_041538/`
- `output/xps_heterojunction_stacked/`
- `outputs/xps_in_situ_20260506/`
- most `output/reports/*.json`, `*.xlsx`, `*.zip`, `*.txt`

Important nuance: some `output/reports/*.md` are lightweight and useful for audit history, but the current output report volume is too high for bulk commit. Select only reports that are needed to explain code/config changes.

### C. Needs Human Confirmation

Scope: changes whose intent is plausible but staging policy is unclear.

- Root docs: `AGENTS.md`, `AGENT_HANDOFF.md`, `PROJECT_STATUS.md`, `README.md`, `TASK_BOARD.md`
  - Reason: they are tracked and modified but some current root docs are known to be partially stale. Confirm whether to update them now or leave `docs/CURRENT_STATUS.md` as the current authority.
- `docs/agent_reports/*`
  - Reason: many generated/handoff files are useful but may not all belong in git.
- `output/reports/*`
  - Reason: tracked output reports are already modified, and untracked output reports are numerous. Decide whether this repo should continue versioning output reports broadly or only keep selected audit reports.
- `scripts/build_xps_in_situ_20260506.py`
  - Reason: dedicated XPS helper, not the general pipeline. Confirm whether it remains tracked at root or should live only under `scripts/data_types/xps/`.
- `scripts/regenerate_manual_review_filtered.py` deletion
  - Reason: likely replaced by `scripts/reports/regenerate_manual_review_filtered.py`, but references must be checked.
- `config/plot_style.yaml`
  - Reason: formal style config, but any style changes should be tied to OPJU evidence and tests.

### D. Temporary / Cache / One-Off Debug Artifacts

Visible dirty items that look temporary or one-off:

- `output/reports/_tmp_xps_bi_check.png`
- `output/reports/tmp_opju_compare.json`
- `output/reports/tmp_opju_compare.md`
- `output/reports/xps_template_compare/axis_label_test.py`
- `output/reports/xps_template_compare/export_template_previews.py`
- `output/reports/xps_template_compare/query_axis_props.py`
- `output/opju_exemplar_regression/_tmp_preview/`
- `output/opju_exemplar_regression/temp_preview_compare/`
- `output/bet_reference_compare/title_fix_trial*/`
- `output/bet_reference_compare/trial_ref_graph1*`
- `output/reports/phase1_13_pip_*.txt`

Do not delete them in this phase. In a later light整理 execution phase, quarantine/ignore/keep decisions should be explicit and path-scoped.

### E. Deleted Tracked Files

- `scripts/regenerate_manual_review_filtered.py`

Recommendation: do not commit the deletion until one of these is true:

1. References to the old path are absent or intentionally updated.
2. `scripts/reports/regenerate_manual_review_filtered.py` is confirmed as the replacement.
3. The script index and README point to the replacement.
4. A final diff review confirms no accidental loss of behavior.

If those checks fail, restore the tracked file in the light整理 execution phase.

## Suggested Commit Batches For Later

No commit should be made in this phase. If the user approves a later staging phase, use small batches:

1. Core formal code and tests: `src/`, `tests/`, selected `config/`, `pyproject.toml`, `optional_requirements.txt`.
2. Script layout: `scripts/README.md`, `scripts/data_types/`, `scripts/maintenance/`, `scripts/reports/`, `scripts/one_off/`, plus resolved deletion/replacement of `scripts/regenerate_manual_review_filtered.py`.
3. Current orientation docs: `docs/CURRENT_STATUS.md`, `docs/PROJECT_INDEX.md`, this整理 doc set, selected method/intake docs.
4. Selected phase reports only if needed to explain batch 1-3.
5. No large output artifacts unless explicitly requested.
