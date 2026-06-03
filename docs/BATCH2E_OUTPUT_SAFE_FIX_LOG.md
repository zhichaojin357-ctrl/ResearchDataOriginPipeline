# Batch 2E Output-Safe Fix Log

Date: 2026-06-03

## Files Changed

Source/governance:

- `src/core/phase1_7.py`
- `src/core/phase1_9.py`
- `src/core/validate.py`

Tests:

- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_contracts.py`

Docs:

- `docs/BATCH2E_OUTPUT_SAFE_REVIEW.md`
- `docs/BATCH2E_OUTPUT_SAFE_FIX_LOG.md`

## Output Isolation Changes

- `tests/test_phase1_7_manifest_runner.py`
  - Report write test now uses a temporary project root under `tmp_path`.
  - Reports are written under that temporary project root's `output/reports`, not the repository `output/reports`.
- `tests/test_phase1_8_reviewed_queue.py`
  - Template/report tests now use a temporary project root under `tmp_path`.
  - Fixture proposals, workspace, triage manifest, and processed index remain under `tmp_path`.
- `tests/test_phase1_10_manifest_normalizer.py`
  - Normalize outputs now write under a temporary project root.
  - CLI smoke test runs repository `run.py` with `cwd` set to the temporary project root, so output guards still apply without touching repository output.
- `tests/test_phase1_contracts.py`
  - `test_validate_reports_scope_guards_and_registry_semantics` now runs `validate` against a temporary project with copied config files.
  - It no longer writes `ROOT/output/reports/validation_report.md`.

## Production Guard Decision

The first targeted pytest run failed because production guards correctly rejected writes outside the current `project_root`:

- `src/core/origin_batch.py`
- `src/core/reviewed_queue.py`
- `src/core/manifest_normalizer.py`

Those guards were not relaxed. The tests were changed to use temporary project roots instead.

## Checks Run

Initial py_compile:

- `D:\Python\python.exe -m py_compile src/core/validate.py src/core/readiness.py src/core/phase1_7.py src/core/phase1_9.py`
- `D:\Python\python.exe -m py_compile tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py`

Result: passed.

First targeted pytest:

- `D:\Python\python.exe -m pytest tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py -q`

Result: failed, `68 passed`, `5 failed`. Failures were all output-guard rejections caused by attempting to write to `tmp_path` outside the active project root.

Second py_compile after fix round 1:

- Same source py_compile command.
- Same test py_compile command.

Result: passed.

Second targeted pytest:

- `D:\Python\python.exe -m pytest tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py -q`

Result: passed, `73 passed in 18.71s`.

## Output Status Check

Post-test checks:

- `git status --short -- output outputs`
- `git status --short -- output/reports`
- `git status --short -- output/reports | rg '_test_|phase1_7_reports|phase1_8_reviewed_queue|phase1_10_normalized|pytest'`

Result:

- The repository already has many dirty `output/` and `output/reports/` entries from earlier work.
- No new `_test_*`, `phase1_7_reports`, `phase1_8_reviewed_queue`, `phase1_10_normalized`, or pytest-named report entry appeared under repository `output/reports`.
- No Origin was run.
- No OPJU/TIF/PNG/XLSX/ZIP/large JSON was staged or committed.

## Staging Recommendation

Recommended. The Batch 2E files are now output-safe under targeted pytest, and production output guards remain intact.

## Commit Message

`core: isolate governance report tests`
