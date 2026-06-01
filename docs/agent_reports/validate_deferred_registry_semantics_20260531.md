# Validate Deferred Registry Semantics

Generated: 2026-05-31

## Issue

`run.py validate` checked that SEM/TEM/NMR/MS style entries were `scan_only` and not supported, but it did not also require `selected_processor=none`. The `动力学` reference entry was only checked for `inferred_data_type=reference_literature`, not for `scan_only`, `supported_in_phase_1=false`, and `selected_processor=none`.

That made the validation report weaker than the project safety policy: a deferred/reference data type could accidentally gain a processor and still pass validation.

## Fix

`src/core/validate.py` now checks deferred/reference registry semantics by inferred data type:

- `SEM_image_data`
- `TEM_image_data`
- `NMR`
- `MS`
- `reference_literature` for `动力学`

Each must satisfy:

- `supported_in_phase_1=false`
- `special_handling=scan_only`
- `selected_processor=none`

The validation report now lists the checked folder/type mappings so failures are easier to audit.

## Regression

Added `test_validate_rejects_deferred_registry_entries_with_processors` in `tests/test_phase1_contracts.py`.

Focused verification:

```text
D:\Python\python.exe -m pytest tests\test_phase1_contracts.py -q
14 passed in 6.97s
```

## Safety

No real data processing was run. No Origin or Excel process was launched by this fix.
