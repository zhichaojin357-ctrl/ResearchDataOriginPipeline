# Batch 2D-CALC-PHOTOCURRENT Review

Date: 2026-06-03

## Purpose

Stabilize photocurrent processed-table candidate units without changing scientific interpretation.

This batch only converts processed photocurrent output columns from amperes to microamps and optional current density to microamps per square centimeter. It does not infer carrier separation or photocatalytic mechanism.

## Strict Allowlist

Allowed staged paths:

- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`
- `docs/BATCH2D_CALCULATIONS_PHOTOCURRENT_REVIEW.md`

For `src/processors/calculations.py`, only the `photocurrent_processed_table()` unit/header hunk should be staged.

For `tests/test_processor_behaviors.py`, only photocurrent expectation hunks should be staged.

## Excluded Nearby Files And Hunks

Do not stage:

- BET vendor isotherm or pore-distribution calculation hunks.
- Optional adapter bridge hunks for peak detection or baseline correction.
- BET tests in `tests/test_processor_behaviors.py`.
- `src/processors/base.py`.
- Any output/report/generated artifact.

## Diff Summary

`src/processors/calculations.py`:

- Emits `photocurrent_uA` instead of raw `current` in processed tables.
- Emits `current_density_uA_cm2_optional` instead of raw optional current density.

`tests/test_processor_behaviors.py`:

- Updates synthetic photocurrent expectations for the new processed headers and microamp values.

## Risk Assessment

Output risk: LOW. Tests use temporary directories only.

Real data risk: LOW for this batch. Fixtures are synthetic CSV rows.

Scientific claim risk: MEDIUM. Photocurrent values remain candidate numeric outputs only; this batch does not assert mechanism or carrier separation conclusions.

Origin risk: NONE. No Origin command is run or required.

## Verification Commands

```powershell
git diff --stat -- src/processors/calculations.py tests/test_processor_behaviors.py
git diff --check -- src/processors/calculations.py tests/test_processor_behaviors.py docs/BATCH2D_CALCULATIONS_PHOTOCURRENT_REVIEW.md
D:\Python\python.exe -m py_compile src/processors/calculations.py
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_photocurrent_outputs_peak_and_steady_current_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_photocurrent_response_outputs_peak_and_steady_current_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_photocurrent_uses_light_markers_for_cycles_and_current_density_candidate -q
git status --short -- output outputs
git status --short -- output/reports
```

After partial staging, also compile the cached staged versions:

```powershell
git show :src/processors/calculations.py | D:\Python\python.exe -c "import sys; compile(sys.stdin.read(), 'src/processors/calculations.py', 'exec')"
git show :tests/test_processor_behaviors.py | D:\Python\python.exe -c "import sys; compile(sys.stdin.read(), 'tests/test_processor_behaviors.py', 'exec')"
```

## Staging Recommendation

Recommend staging only if:

- `py_compile` passes.
- Photocurrent targeted pytest nodeids pass.
- Cached staged versions compile.
- Cached diffs contain no BET or optional-adapter bridge hunks.
- No new production `output/` or `outputs/` pollution appears.

Commit message:

```text
processors: express photocurrent outputs in microamps
```
