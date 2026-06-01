# Reviewed-Queue Forbidden Type Guard

`reviewed-queue` now normalizes forbidden type labels and blocks composite labels such as `SEM/TEM/NMR/MS` as policy violations before creating any future queue candidate.

Verification:

- `D:\Python\python.exe -m pytest tests\test_phase1_8_reviewed_queue.py -q`: passed, 14 tests.
