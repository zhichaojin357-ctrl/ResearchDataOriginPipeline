# Batch 2 Remaining Plan

Date: 2026-06-03

This plan lists source/config/test changes intentionally left out of the automatic Batch 2 commits.

## Current Continuation State

Continuation baseline: `209d9f3 deps: record optional adapter metadata`.

Current dirty count at GOAL Phase 0: 327 items.

Staged files at GOAL Phase 0: 0.

Already completed in Batch 2:

- `fb152fc core: accept utf-8-sig process json`
- `209d9f3 deps: record optional adapter metadata`
- `76c3c5c origin: stabilize plotting policy helpers`
- `cc2e13e epr: stabilize jeol decode and overlay workflows`
- `f09fcf3 adapters: add optional scientific adapter shims`
- `b860453 tests: update manual review generator import`
- `dbe0a58 core: isolate governance report tests`
- `a0cedbe docs: sync script layout references`

The remaining plan below excludes those solved changes and focuses on source/config/test work still present in the working tree.

## Remaining Review Order

1. Processor calculations and table reader review
   - Files: `src/processors/base.py`, `src/processors/calculations.py`, `src/core/table_reader.py`, `tests/test_processor_behaviors.py`.
   - Reason: includes BET, photocurrent, spectral baseline, and other data-type behavior changes.
   - Required boundary: do not characterize this as a plotting fix until rerun from raw inputs and reviewed.

2. XPS helper review
   - Files: `src/core/xps_heterojunction.py`, `src/core/xps_in_situ.py`, `tests/test_xps_heterojunction_stacked.py`.
   - Reason: large generated Origin-script and artifact-path changes; keep separate from general source cleanup.

3. CLI XPS help-text hunk
   - File: `src/cli.py`.
   - Reason: one remaining unstaged hunk changes XPS `--with-origin` help text; keep with XPS helper review rather than EPR.

## Completed Review Order Items

1. Origin adapter and plot policy preflight
   - Files: `config/plot_style.yaml`, `src/origin/*`, `tests/test_origin_*`.
   - Completed by `76c3c5c`.
   - Validation: py_compile for Origin helper modules and targeted Origin helper pytest, without live Origin.

2. JEOL EPR decode and EPR overlay review
   - Files: `config/default.yaml`, `config/data_selection_rules.yaml`, `src/cli.py`, `src/core/epr_jeol.py`, `src/core/epr_overlay.py`, `src/core/runtime_paths.py`, related tests.
   - Completed by `cc2e13e`.
   - Validation: py_compile for EPR modules/CLI and targeted JEOL/EPR overlay pytest, without live Origin.

3. Optional adapter package review
   - Files: `src/adapters/`, `tests/test_phase1_13_adapters.py`.
   - Completed by `f09fcf3`.
   - Validation: py_compile for adapter modules and targeted adapter pytest, without live Origin.

4. Manual review generator test import cleanup
   - Files: `tests/test_manual_review_filtered_report.py`.
   - Completed by `b860453`.
   - Validation: py_compile for the targeted test and targeted pytest using `tmp_path`, without repository-output writes.

5. Governance and validation output-safe review
   - Files: `src/core/phase1_7.py`, `src/core/phase1_9.py`, `src/core/validate.py`, `tests/test_phase1_7_manifest_runner.py`, `tests/test_phase1_8_reviewed_queue.py`, `tests/test_phase1_9_governance.py`, `tests/test_phase1_10_manifest_normalizer.py`, `tests/test_phase1_contracts.py`.
   - Completed by `dbe0a58`.
   - Validation: source/test py_compile and targeted pytest, `73 passed`, without repository `output/reports/_test_*` writes.

6. Script layout consistency sync
   - Files: script README files, `docs/indexes/scripts_index.md`, `docs/SCRIPT_LAYOUT_CONSISTENCY_REVIEW.md`, `docs/SCRIPT_LAYOUT_REMAINING_PLAN.md`.
   - Completed by `a0cedbe`.
   - Validation: docs/index-only `git diff --check`; no `.py` scripts moved or edited.

## Global Rules

- Do not stage `output/`, `outputs/`, OPJU, TIF, PNG, XLSX, ZIP, or large JSON files.
- Do not run Origin during cleanup reviews.
- Do not use directory-level staging.
- Each remaining batch needs its own allowlist, targeted checks, and post-stage verification.
