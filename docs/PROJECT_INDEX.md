# Project Index

MEGA update: 2026-06-04.

This file still preserves the 2026-06-03 structure map below. For current Git and dirty counts, use `docs/MEGA_CONVERGENCE_FINAL_SELF_AUDIT.md` after it is generated. Current MEGA convergence changed the repository policy state:

- generated `output/reports` JSON/CSV/TXT and generated Markdown report families are no longer tracked by default;
- `docs/agent_reports` is formal documentation/provenance and is clean after the MEGA agent-report commit;
- `src/config/tests/scripts` remains clean;
- `output/reports/README.md`, `output/review_dashboard`, and any remaining documentation edits require explicit policy or user decisions;
- data-type plotting/visual acceptance still requires future no-Origin planning or explicit Origin/visual goals.

This index maps the current repository by role. It is based on the current disk state on 2026-06-03, not only on the latest git commit.

## Repository Root

Project root:

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

Primary command:

`D:\Python\python.exe run.py <command>`

Historical branch/commit from the 2026-06-03 snapshot:

- Branch: `master`
- HEAD: `116b393 Phase 1.10-1.11: stabilize manifests and freeze release baseline`
- Worktree: dirty, with substantial Phase 1.13/1.14-era uncommitted work

## Main Entrypoints

- `run.py`: thin CLI wrapper; imports `src.cli.main`
- `src/cli.py`: authoritative command surface
- `src/core/process.py`: process orchestration and queue validation
- `src/core/runtime_paths.py`: runtime path resolution, locked package lookup, and run-scoped output helpers
- `src/core/triage.py`: current data triage/classification workflow
- `src/core/auto_queue.py`: Phase 1.8 AUTO_PROCESS dry-run queue builder
- `src/core/reviewed_queue.py`: user-reviewed proposal/decision dry-run planner
- `src/core/origin_batch.py`: package manifest dry-run planner
- `src/core/readiness.py`: readiness/preflight checks
- `src/core/validate.py`: project validation checks
- `src/core/deps.py`: dependency audit

## Source Layout

- `src/scanner/`: registry-driven raw-data scan and classification report generation
- `src/processors/`: supported data-type processor profiles, table processing, and candidate calculations
- `src/core/`: CLI-backed orchestration, queues, manifests, readiness, validation, EPR/XPS dedicated workflows, and phase reports
- `src/origin/`: Origin export adapter, operation helpers, plot policies, and text formatting
- `src/adapters/`: optional lazy scientific adapters added in Phase 1.13; use for candidate/provenance only

## Configuration

- `config/default.yaml`: paths, processing defaults, safety defaults
- `config/processor_registry.yaml`: data-type registry; current source of supported vs scan-only data types
- `config/plot_style.yaml`: Origin/Graph4 style contract and export settings
- `config/claim_policy.yaml`: forbidden scientific claims and manual-review constraints
- `config/data_selection_rules.yaml`: data selection/triage rule support
- `config/manual_overrides.yaml`: manual override area
- `config/local.example.yaml`: example machine-local paths
- `config/local.yaml`: machine-local paths; gitignored by policy but currently present locally

## Formal Commands

Use these as the supported command surface:

- `scan`: scan input/raw data and write inventory/classification reports
- `triage`: classify files into AUTO_PROCESS, MANUAL_REVIEW, deferred, excluded, duplicates, and reference-only buckets
- `process`: process supported table data and optionally export Origin outputs
- `origin-test`: smoke-test Origin callability
- `origin-batch`: dry-run package manifest execution planning
- `manifest-normalize`: normalize mixed material collection indexes for dry-run planning
- `reviewed-queue`: build user-reviewed no-Origin queue plans
- `auto-queue`: build current no-Origin AUTO_PROCESS candidate queues after Phase 1.6 exclusion
- `xps-heterojunction-stacked`: dedicated fitted XPS stacked comparison output
- `xrd-overlay`: dedicated reviewed XRD overlay with CuWO4 reference-card sticks
- `jeol-epr-decode`: verified JEOL cAcqu cwESR decode to data-only Excel tables
- `epr-overlay`: JEOL EPR condition overlay tables and optional Origin figures
- `deps-audit`: dependency availability report
- `validate`: project contract validation
- `readiness`: current artifact and safety preflight
- `phase1-9-governance`: governance/index report generation

## Future Output Routing

New code-level run output routing is documented in `docs/FUTURE_OUTPUT_ROUTING_GOAL_SUMMARY.md`.

Future generated artifacts can be routed to:

`output/runs/YYYYMMDD_HHMMSS_<scope>/`

Supported core contracts now include process/no-Origin artifacts, metadata, scanner side reports, triage reports, auto-queue reports, reviewed-queue reports, origin-batch dry-run reports, and Origin adapter path construction. Legacy output paths remain readable and are preserved for historical traceability. No old `output/` or `outputs/` content has been moved by this routing work.

## Supported Data Types

Formal Phase 1 supported types from `config/processor_registry.yaml`:

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

Scan-only/deferred/reference:

- `SEM_image_data`
- `TEM_image_data`
- `NMR`
- `MS`
- `reference_literature`

## Tests

Test root:

`tests/`

Current test coverage areas include:

- queue planning and safety gates
- readiness checks
- processor behavior
- Origin adapter and plot policy
- Origin operations layer
- Phase 1.10 manifest normalization
- Phase 1.13 adapters
- JEOL EPR decode
- EPR overlay
- XPS heterojunction stacked workflow
- XPS in-situ helper workflow

Latest cited report evidence includes successful runs up to:

- Phase 1.13: 249 passed, 29 warnings
- Non-XRD audit: 290 passed, 28 subtests passed

This audit did not rerun the full test suite.

## Documentation

Root status docs:

- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`

These are useful but currently partially stale relative to latest Phase 1.14/path-audit reports. Prefer the current status file:

- `docs/CURRENT_STATUS.md`

Core documentation areas:

- `docs/agent_reports/`: phase reports, handoffs, audits, and validation summaries
- `docs/indexes/`: report/script/output indexes
- `docs/method_cards/`: data-type method cards
- `docs/data_format_notes/`: scan-only/deferred format notes
- `docs/REAL_DATA_INTAKE_GUIDE.md`: intake expectations
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`: compatibility matrix
- `docs/xps_origin_plotting_guardrails.md`: XPS-specific Origin plotting guardrails
- `docs/CODEX_GOAL_PHASE1.md`: original Phase 1 goal context

Current high-value reports:

- `docs/agent_reports/non_xrd_reorg_path_audit_20260603.md`
- `docs/agent_reports/xrd_path_and_temp_script_cleanup_20260603.md`
- `output/reports/xrd_opju_exemplar_comparison_20260602.md`
- `output/reports/phase1_14_opju_exemplar_regression_comparison.md`
- `docs/agent_reports/phase1_14_opju_exemplar_driven_requirement_update.md`
- `docs/agent_reports/bet_opju_exemplar_optimization_20260602.md`
- `docs/agent_reports/PHASE1_13_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md`
- `docs/agent_reports/phase1_13_final_validation.md`
- `docs/agent_reports/phase1_11_release_freeze_baseline.md`

## Output Layout

Primary output root:

- `output/`

Important output directories:

- `output/phase1_6_origin_results_20260531_041538`: canonical 167-result Origin package
- `output/final_locked_results`: release-freeze pointer/manifest artifacts
- `output/reports`: report JSON/Markdown/CSV/XLSX artifacts
- `output/review_dashboard`: current dashboards and review indexes
- `output/processed_data`: active/generated processed CSVs
- `output/metadata`: generated metadata JSON
- `output/origin_files`: generated OPJU files
- `output/figures_tif`: generated 600 dpi TIF files
- `output/figures_preview`: generated PNG previews
- `output/opju_exemplar_regression`: copied OPJU references, exported reference pages, comparison input, and temporary comparison material
- `output/material_collections`: large mixed material-selection collection; not a standard result package by itself
- `output/phase1_5_processed_results_20260531_005613`: historical no-Origin package
- `output/xps_heterojunction_stacked`: dedicated XPS stacked comparison outputs
- `output/origin_jobs`: currently empty after cleanup

Secondary/specialized output root:

- `outputs/xps_in_situ_20260506`: dedicated/historical XPS in-situ output, not raw data

## Result Package Interpretation

- Phase 1.5: historical no-Origin package
- Phase 1.6: canonical completed Origin result package, 167 rows
- Phase 1.10-1.11: release-freeze/governance baseline around the Phase 1.6 package
- Phase 1.13: optional package and adapter integration in current dirty tree
- Phase 1.14: OPJU exemplar regression and plotting-contract work in current dirty tree

Do not call Phase 1.6 the current engineering phase. It is the locked package that later phases protect, audit, compare against, or extend around.

## Scripts

Current script organization:

- `scripts/maintenance/`: reusable maintenance helpers not exposed as public CLI
- `scripts/reports/`: reusable report/index generation helpers
- `scripts/one_off/`: one-time audit or migration helpers retained for traceability
- `scripts/data_types/xps/`: XPS-specific helper scripts
- `scripts/archive/`: historical script storage

Current caution:

- `scripts/maintenance/opju_exemplar_regression.py` is a regression/comparison helper, not a production data processor.
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py` is one-off verification support.
- `scripts/build_xps_in_situ_20260506.py` and `scripts/data_types/xps/build_xps_in_situ_20260506.py` are dedicated XPS helper paths, not the general queue pipeline.
- The tracked root script `scripts/regenerate_manual_review_filtered.py` is currently deleted in the working tree, while report-script structure exists under `scripts/reports/`.

## Files To Avoid As Next-Batch Inputs

- `output/reports/processing_queue.json`: raw current queue; contains overlaps/old state and is not the next-batch source
- `output/material_collections/*/index.csv`: mixed material selection indexes; normalize before any dry-run
- `output/opju_exemplar_regression/*`: regression/reference material, not raw production queue input unless a focused validation queue says so
- `outputs/*`: specialized/historical outputs, not raw inputs

## Safe Next-Batch Pattern

1. Run/inspect `readiness` and `validate`.
2. Inspect `output/reports/phase1_8_new_auto_process_plan.md`.
3. Choose a small explicit no-Origin batch from `output/reports/phase1_8_new_auto_process_queue.json`.
4. Run `process --from-queue ... --no-origin` only after confirming the queue scope.
5. Review processed CSV/metadata/no-Origin previews.
6. Only then decide whether any Origin export is needed.

## Current Open Items

- Dirty worktree needs staging discipline before any commit.
- Root docs need refresh or supersession because some counts and phase labels are stale.
- XPS OPJU-exemplar comparison still needs an explicit completed report.
- Raman OPJU comparison has a warning and should be fixed or justified.
- BET OPJU changes need visual acceptance before being treated as fully production-approved.
- 167 Phase 1.6 Origin PNG previews still need user visual review before manuscript use.
- 493 current manual-review workbook rows still need human decisions.
- Bulk `MANUAL_REVIEW` processing remains forbidden.
