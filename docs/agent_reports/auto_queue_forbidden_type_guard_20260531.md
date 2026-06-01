# Auto Queue Forbidden Type Guard

Generated: 2026-05-31

## Issue

`auto-queue` blocked forbidden data types by exact string comparison. That was safe for canonical values such as `SEM` or `TEM`, but weaker for variant spellings such as:

- `sem_image_data`
- `SEM/TEM/NMR/MS`
- `reference_literature`
- `动力学`

These values should never enter a future no-Origin queue from the automatic planner.

## Fix

`src/core/auto_queue.py` now normalizes forbidden data type names before checking them. It also tokenizes slash/comma/semicolon/pipe-separated combined labels, so combined blocked labels are rejected as a group.

## Tests

Added `test_auto_queue_blocks_forbidden_type_variants` in `tests/test_auto_queue.py`.

Focused verification:

```text
D:\Python\python.exe -m pytest tests\test_auto_queue.py -q
5 passed in 0.07s
```

## Safety

No real data processing was run. No Origin or Excel process was launched.
