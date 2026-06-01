# Reviewed-Queue Forbidden Type Guard

Generated: 2026-05-31

## Problem

`auto-queue` already normalized forbidden type variants such as `sem_image_data` and `SEM/TEM/NMR/MS`, but `reviewed-queue` used exact string matching. A user-approved proposal row with a composite forbidden label could be blocked later as stale triage, but it was not explicitly rejected as a policy violation.

## Change

`reviewed-queue` now normalizes forbidden type labels and tokenizes composite labels before approval planning.

Blocked examples include:

- `SEM`
- `TEM`
- `NMR`
- `MS`
- `SEM/TEM/NMR/MS`
- `sem_image_data`
- `reference_literature`
- `kinetics`
- `动力学`

## Verification

- `D:\Python\python.exe -m pytest tests\test_phase1_8_reviewed_queue.py -q`: passed, 14 tests.

## Safety

No raw data was modified. No workspace source file was modified. No F-drive backup file was modified. No Origin or Excel process was launched by this change.
