# Batch 2E And Script Consistency Goal Summary

Date: 2026-06-03

## Start State

- Start baseline: `1fb85f0 docs: summarize batch2 autonomous stabilization`
- Starting dirty count: about 305 items.
- Staged files at start: 0.

## Commits Completed

1. `dbe0a58 core: isolate governance report tests`
   - Isolated governance/manifest report tests so they no longer write temporary files under repository `output/reports`.
   - Kept production output guards intact.

2. `a0cedbe docs: sync script layout references`
   - Updated script README files and `docs/indexes/scripts_index.md`.
   - Confirmed current script paths:
     - `scripts/reports/regenerate_manual_review_filtered.py`
     - `scripts/data_types/xps/build_xps_in_situ_20260506.py`
     - `scripts/maintenance/opju_exemplar_regression.py`
     - `scripts/one_off/verify_jeol_epr_decode_against_exports.py`

This summary docs update is intended as the final docs-only commit for the GOAL.

## Batch 2E Verification

Commands run:

- `D:\Python\python.exe -m py_compile src/core/validate.py src/core/readiness.py src/core/phase1_7.py src/core/phase1_9.py`
- `D:\Python\python.exe -m py_compile tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py`
- `D:\Python\python.exe -m pytest tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py -q`

Results:

- py_compile passed.
- First targeted pytest failed with 5 output-guard failures because tests wrote to `tmp_path` outside the active `project_root`.
- Fix round 1 changed those tests to use temporary project roots under `tmp_path`.
- Second targeted pytest passed: `73 passed in 18.71s`.

## Output Safety

- Tests no longer write repository `output/reports/_test_*`.
- The post-test output scan found no `_test_*`, `phase1_7_reports`, `phase1_8_reviewed_queue`, `phase1_10_normalized`, or pytest-named entries under repository `output/reports`.
- Existing dirty `output/` and `output/reports/` entries remain from previous work and were not staged.

## Script Layout Consistency

Completed by `a0cedbe`.

- Current README/index files no longer present old root script paths as active entrypoints.
- Historical references to old paths remain in prior review/status docs and in `patches/xps_in_situ_root_drift.patch`.
- No `.py` script was moved, deleted, renamed, or edited.

## Remaining Dirty Scope

After the script layout commit and before this summary docs update:

- Dirty count: 296 items.
- Staged files: 0.

Remaining source/test work:

- Processor/table-reader micro-batches:
  - `src/core/metadata.py`
  - `src/core/table_reader.py`
  - `src/processors/base.py`
  - `src/processors/calculations.py`
  - `tests/test_processor_behaviors.py`
- XPS source workflow preflight:
  - `src/cli.py`
  - `src/core/xps_heterojunction.py`
  - `src/core/xps_in_situ.py`
  - `tests/test_xps_heterojunction_stacked.py`

Remaining dirty generated/report artifacts:

- Existing `output/`, `output/reports/`, `output/review_dashboard/`, and report/index docs remain dirty and are outside this GOAL's commit scope.

## Safety Statements

- Origin was not run.
- No new data was processed.
- No full pytest was run.
- No output cleanup was performed.
- No `output/`, `outputs/`, OPJU, TIF, PNG, XLSX, ZIP, or large JSON file was staged or committed.
- No scientific mechanism or assignment claim was made.
- No plotting visual issue was fixed or claimed fixed.

## Next Recommendation

Next GOAL:

- `Processor/Table Reader Micro-Batch Preflight`

Suggested first split:

- Start with `Batch 2D-table-reader` only if it can be validated entirely with `tmp_path` fixtures and without real output writes.
- Keep BET, photocurrent unit conversion, adapter bridges, and XPS workflows in separate reviews.
