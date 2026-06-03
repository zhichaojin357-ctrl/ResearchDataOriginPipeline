# Batch 2D-PB Processor Base Contracts Review

Date: 2026-06-03

## Purpose

Stabilize shared processor-base contracts for:

- Data-type-aware axis title selection before Origin export.
- Algorithm provenance fields that document optional adapter policy without making scientific claims.

This batch does not run Origin. The targeted test patches `src.processors.base.export_plot` and uses temporary directories only.

## Strict Allowlist

Allowed staged paths:

- `src/processors/base.py`
- `tests/test_processor_base_contracts.py`
- `docs/BATCH2D_PROCESSOR_BASE_REVIEW.md`

## Excluded Nearby Files

Do not stage:

- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`
- `src/core/table_reader.py`
- `src/core/metadata.py`
- Any config file.
- Any output/report/generated artifact.

## Diff Summary

`src/processors/base.py`:

- Passes `data_type` into `_origin_axis_titles()`.
- Adds axis-title defaults for processed BET/photocurrent headers and generic spectral/XRD/EPR axis names.
- Records optional adapter layer and lazy-fallback adapter policy in algorithm provenance.
- Records candidate adapter names when relevant candidate outputs or data types are present.

`tests/test_processor_base_contracts.py`:

- Verifies Raman generic `x,intensity` processed data passes Raman axis titles to the Origin export boundary without running Origin.
- Verifies algorithm provenance records the optional adapter layer and fallback policy for candidate calculations.

## Risk Assessment

Output risk: LOW. Tests write only inside pytest `tmp_path`.

Real data risk: LOW. Tests use synthetic CSV fixtures.

Scientific claim risk: LOW. Provenance text states candidate metrics only and manual review policy.

Origin risk: NONE. The export boundary is patched; Origin is not launched.

## Verification Commands

```powershell
git diff --stat -- src/processors/base.py tests/test_processor_base_contracts.py
git diff --check -- src/processors/base.py tests/test_processor_base_contracts.py docs/BATCH2D_PROCESSOR_BASE_REVIEW.md
D:\Python\python.exe -m py_compile src/processors/base.py tests/test_processor_base_contracts.py
D:\Python\python.exe -m pytest tests/test_processor_base_contracts.py -q
git status --short -- output outputs
git status --short -- output/reports
```

## Staging Recommendation

Recommend staging only if:

- `py_compile` passes.
- The targeted processor-base test file passes.
- No new production `output/` or `outputs/` pollution appears.

Commit message:

```text
processors: tighten processor base contracts
```
