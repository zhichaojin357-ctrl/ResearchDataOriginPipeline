# Batch 2D-TR Table Reader Contracts Review

Date: 2026-06-03

## Purpose

Stabilize text table reader contracts for two exported text-table shapes using synthetic fixtures only:

- EIS ZPlotW text exports with `Freq(Hz)`, `Z'`, and `Z''` columns.
- Bracketed `[Data]` text sections such as XRD RAW4-style exports.

This batch does not run Origin, does not process real data, and does not write production `output/` or `outputs/`.

## Strict Allowlist

Allowed staged paths:

- `src/core/table_reader.py`
- `tests/test_processor_behaviors.py`
- `docs/BATCH2D_TABLE_READER_REVIEW.md`

For `tests/test_processor_behaviors.py`, only the two table-reader synthetic test hunks should be staged:

- `test_text_reader_accepts_zplotw_eis_export`
- `test_xrd_reads_raw4_text_data_section`

## Excluded Nearby Files And Hunks

Do not stage:

- `src/processors/base.py`
- `src/processors/calculations.py`
- `src/core/metadata.py`
- Any config file.
- Any output/report/generated artifact.
- Photocurrent test expectation changes in `tests/test_processor_behaviors.py`.
- BET vendor isotherm or pore distribution tests in `tests/test_processor_behaviors.py`.

## Diff Summary

`src/core/table_reader.py`:

- Adds `freq`/`hz` x-column labels and real impedance y-column labels.
- Attempts ZPlotW and bracketed `[Data]` parsing before generic headerless numeric fallback.
- Adds `_zplotw_table_result()` for ZPlotW text exports.
- Adds `_bracketed_data_table_result()` for bracketed data sections.

`tests/test_processor_behaviors.py`:

- Adds one synthetic ZPlotW fixture test.
- Adds one synthetic RAW4-like `[Data]` fixture test.

## Risk Assessment

Output risk: LOW. Tests use temporary directories and do not write production output.

Real data risk: LOW. Fixtures are synthetic inline text.

Scientific claim risk: LOW. This only verifies table extraction, not EIS circuit fitting or XRD phase/crystal-plane assignment.

Origin risk: NONE. No Origin command is run or required.

## Verification Commands

```powershell
git diff --stat -- src/core/table_reader.py tests/test_processor_behaviors.py
git diff --check -- src/core/table_reader.py tests/test_processor_behaviors.py docs/BATCH2D_TABLE_READER_REVIEW.md
D:\Python\python.exe -m py_compile src/core/table_reader.py
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_text_reader_accepts_zplotw_eis_export tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_xrd_reads_raw4_text_data_section -q
git status --short -- output outputs
git status --short -- output/reports
```

## Staging Recommendation

Recommend staging only if:

- `py_compile` passes.
- Both targeted pytest nodeids pass.
- No new production `output/` or `outputs/` pollution appears.
- Cached diff for `tests/test_processor_behaviors.py` contains only the two table-reader synthetic tests.

Commit message:

```text
core: stabilize table reader contracts
```
