# HPLC/LC Module Review

Date: 2026-06-04

## Current Repository State

- Current HEAD: `24ad5da414c12110cdbceaed51f3d884fa7915c7`
- Current dirty state at audit start: `0`
- Current staged state at audit start: `0`
- Scoped state for `config src tests docs output outputs` at audit start: clean
- Recent HPLC/LC contract commit: `24ad5da hplc: define exported data plot contracts`
- Pre-HPLC readiness commit: `41de3d8 docs: record pre-hplc readiness gate`

## HPLC/LC Submitted Content

The previous HPLC/LC contract commit added:

- `docs/HPLC_LC_ACCEPTANCE_CRITERIA.md`
- `docs/HPLC_LC_GOAL_SUMMARY.md`
- `docs/HPLC_LC_PLOT_CONTRACT_PREFLIGHT.md`
- `docs/HPLC_LC_SYNTHETIC_TEST_PLAN.md`
- `tests/test_hplc_lc_contracts.py`
- HPLC/LC candidate logic in `src/processors/base.py`
- HPLC/LC candidate logic in `src/processors/calculations.py`

Those tests covered chromatogram, peak table, calibration, no-calibration blocking, ambiguous table handling, and direct processor-level run-root routing.

## Registry Status

`config/processor_registry.yaml` already registers `HPLC/LC exported data` as Phase 1 supported:

- `id`: `lc_exported_data`
- `selected_processor`: `lc_exported_data_processor`
- supported extensions: `.csv`, `.txt`, `.xlsx`, `.xls`
- declared scope: exported tables only
- method card: `docs/method_cards/hplc_lc_exported_data.md`

The registry does not claim support for Agilent `.d`, Waters `.raw`, or LC-MS raw decoding.

## Processor Support Status

HPLC/LC uses the formal `process_table_dataset()` processor path with type-specific helpers in `src/processors/calculations.py`.

Current support:

- exported chromatogram table candidate;
- exported peak table candidate;
- exported calibration table candidate;
- no-calibration quantification boundary;
- ambiguous table manual-review boundary;
- metadata plot intent;
- algorithm provenance markers;
- run-scoped output root support when `output_root` is passed.

Current implementation is intentionally candidate-only and no-Origin safe.

## Current Tests

Existing HPLC/LC-specific test file:

- `tests/test_hplc_lc_contracts.py`

Related general tests:

- `tests/test_processor_behaviors.py`
- `tests/test_output_routing.py`
- `tests/test_origin_plot_policy.py`

Missing before this MEGA GOAL:

- `tests/test_hplc_lc_process_integration.py`
- `tests/test_hplc_lc_output_routing.py`

## Current Gaps

- The HPLC/LC helper surface is still named as internal `lc_*` functions rather than a clear module-level candidate-extraction API.
- There is no dedicated process-level synthetic no-Origin test that calls the formal `run_process()` path for HPLC/LC.
- There is no dedicated HPLC/LC output-routing test that checks plot intent and run-root metadata across chromatogram, peak-table, calibration, no-calibration, and ambiguous paths.
- The method card should be updated to reflect calibration and ambiguous-table support while keeping raw vendor formats blocked.
- The real-sample dry-run plan and module completion summary are not yet written.

## Recommended Batches

1. Candidate helpers batch:
   - add a clear HPLC/LC candidate extraction helper API;
   - extend contract tests for helper API, peak-name safety, and retention-time safety;
   - keep implementation in `src/processors/calculations.py` and `src/processors/base.py`.
2. Process integration batch:
   - add process-level synthetic tests using `run_process()` with a temporary run root;
   - confirm no Origin call and no repository `output/outputs` pollution.
3. Output routing batch:
   - add HPLC/LC run-scoped metadata and plot-intent tests.
4. Documentation batch:
   - update method card and acceptance docs;
   - add real sample dry-run plan and blockers.
5. Completion batch:
   - write final module completion summary;
   - run final targeted test set;
   - confirm clean worktree.

## Strict Safety Boundary

- Do not run Origin.
- Do not process real HPLC/LC data.
- Do not decode Agilent `.d`, Waters `.raw`, or LC-MS raw data.
- Do not generate OPJU/TIF/PNG/PDF/XLSX/ZIP or large JSON artifacts.
- Do not modify, move, delete, stage, or commit `output/` or `outputs/`.
- Do not infer product identity from peak name.
- Do not infer product identity from retention time.
- Do not calculate real conversion, selectivity, or yield without calibration and explicit manual mapping.
- Keep all automatic outputs candidate-level and manual-check gated.
