# Batch 2D-MD Metadata Manual Review Contract

Date: 2026-06-03

## Purpose

Stabilize the success metadata manual-review checklist wording for PNG preview inspection.

This batch only changes metadata checklist text and a targeted metadata contract assertion. It does not run Origin, process real data, or write production `output/`.

## Strict Allowlist

Allowed staged paths:

- `src/core/metadata.py`
- `tests/test_phase1_contracts.py`
- `docs/BATCH2D_METADATA_REVIEW.md`

## Excluded Nearby Files

Do not stage:

- `src/core/table_reader.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`
- Any config file.
- Any output/report/generated artifact.

## Diff Summary

`src/core/metadata.py`:

- Extends the success preview manual-review item to mention legend frame/fill box checks and chemical formula subscripts.

`tests/test_phase1_contracts.py`:

- Adds targeted assertions that the generated manual check item includes the new preview-review wording.

## Risk Assessment

Output risk: LOW. The targeted test uses `tempfile.TemporaryDirectory()`.

Real data risk: LOW. The test uses synthetic local files under the temporary project root.

Scientific claim risk: LOW. This is a manual-review checklist contract, not an automated scientific interpretation.

Origin risk: NONE. No Origin command is run or required.

## Verification Commands

```powershell
git diff --stat -- src/core/metadata.py tests/test_phase1_contracts.py
git diff --check -- src/core/metadata.py tests/test_phase1_contracts.py docs/BATCH2D_METADATA_REVIEW.md
D:\Python\python.exe -m py_compile src/core/metadata.py
D:\Python\python.exe -m pytest tests/test_phase1_contracts.py::Phase1ContractsTest::test_success_metadata_requires_and_records_png_preview_for_manual_visual_check -q
git status --short -- output outputs
git status --short -- output/reports
```

## Staging Recommendation

Recommend staging only if:

- `py_compile` passes.
- The targeted metadata pytest nodeid passes.
- No new production `output/` or `outputs/` pollution appears.

Commit message:

```text
core: tighten metadata preview review checklist
```
