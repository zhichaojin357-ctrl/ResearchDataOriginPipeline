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

The remaining plan below excludes those solved changes and focuses on source/config/test work still present in the working tree.

## Remaining Review Order

1. Origin adapter and plot policy preflight
   - Files: `config/plot_style.yaml`, `src/origin/*`, `tests/test_origin_*`.
   - Reason: changes plotting contracts, Graph4 policy fields, Origin job behavior, and image/export behavior.
   - Required boundary: no Origin run until the review explicitly authorizes a live smoke test.

2. JEOL EPR decode and EPR overlay review
   - Files: `config/default.yaml`, `config/data_selection_rules.yaml`, `src/cli.py`, `src/core/epr_jeol.py`, `src/core/epr_overlay.py`, `src/core/runtime_paths.py`, related tests.
   - Reason: promotes formal CLI entry points and workspace path routing.
   - Required boundary: no output generation except tempdir-based tests.

3. Optional adapter package review
   - Files: `src/adapters/`, `tests/test_phase1_13_adapters.py`, and only the minimal processor bridge files if justified.
   - Reason: adapter tests reference processor-calculation bridge behavior; do not commit adapters without the bridge they require.

4. Processor calculations and table reader review
   - Files: `src/processors/base.py`, `src/processors/calculations.py`, `src/core/table_reader.py`, `tests/test_processor_behaviors.py`.
   - Reason: includes BET, photocurrent, spectral baseline, and other data-type behavior changes.
   - Required boundary: do not characterize this as a plotting fix until rerun from raw inputs and reviewed.

5. Phase governance and validation review
   - Files: `src/core/phase1_7.py`, `src/core/phase1_9.py`, `src/core/validate.py`, phase-specific tests.
   - Reason: governance changes are coupled to Origin plot policy fields and test output cleanup.

6. XPS helper review
   - Files: `src/core/xps_heterojunction.py`, `src/core/xps_in_situ.py`, `tests/test_xps_heterojunction_stacked.py`.
   - Reason: large generated Origin-script and artifact-path changes; keep separate from general source cleanup.

## Global Rules

- Do not stage `output/`, `outputs/`, OPJU, TIF, PNG, XLSX, ZIP, or large JSON files.
- Do not run Origin during cleanup reviews.
- Do not use directory-level staging.
- Each remaining batch needs its own allowlist, targeted checks, and post-stage verification.
