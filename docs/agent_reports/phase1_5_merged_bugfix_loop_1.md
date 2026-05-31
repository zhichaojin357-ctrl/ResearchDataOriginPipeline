# Phase 1.5 Merged Bugfix Loop 1

Created at: 2026-05-31 00:50 +08:00

## Fixed Bugs

### P1-001: Origin execution needed explicit positive authorization

- Modified files:
  - `src\cli.py`
  - `src\core\process.py`
  - `tests\test_phase1_1_process_cli.py`
- Change:
  - Added `--with-origin`.
  - Made `--no-origin` and `--with-origin` mutually exclusive.
  - Normalized `run_process()` to no-Origin unless `with_origin=True`.
- Reason:
  - Phase 1.5 requires ordinary process/queue paths to be no-Origin by default.

### P1-002: Origin failure stage was too generic

- Modified files:
  - `src\core\process.py`
  - `tests\test_phase1_1_process_cli.py`
- Change:
  - Origin-related metadata warnings now produce `failure_stage = origin_export`.
- Reason:
  - Origin lifecycle/export failures must be distinguishable from table processing failures.

## Tests Run

```powershell
D:\Python\python.exe -m pytest tests\test_phase1_1_process_cli.py tests\test_phase1_2_mixed_triage.py -q
```

Result: 21 passed, 4 subtests passed, 2 openpyxl deprecation warnings.

## Unresolved Issues

- P1-003 Origin lifecycle residual-process reporting.
- P1-004 safe promotion queue generation and no-Origin processing.
- P2-001 `.xls` parser gap due missing optional `xlrd`.
- P2-002 global pytest Origin guard.
- P2-003 stale Origin error cleanup.

## Next Loop

Proceed to a small Origin adapter/pytest guard patch if it remains low-risk, then generate safe promotion queues.
