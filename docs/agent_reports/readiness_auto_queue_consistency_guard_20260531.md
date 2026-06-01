# Readiness Auto-Queue Consistency Guard

Date: 2026-05-31

## Issue

`run.py readiness` checked that the Phase 1.8 auto-queue plan and generated queue existed, but it did not verify that the plan summary matched the queue contents.

That left room for stale or edited queue files where:

- `summary.accepted_count` did not match the number of generated queue items;
- the plan reported blocked items but readiness still passed;
- queue items accidentally allowed Origin export;
- queue items did not require manual checking.

## Change

`run.py readiness` now checks:

- `accepted_count == len(phase1_8_new_auto_process_queue.json.items)`;
- `blocked_count == 0`;
- every generated queue item has `origin_export_allowed` not true;
- every generated queue item has `manual_check_required=true`.

## Current State

The current files pass:

- accepted_count: 105
- queue items: 105
- Origin-allowed items: 0

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 7 tests.
- `D:\Python\python.exe run.py readiness`: passed, 16 checks, 0 failures, 0 warnings.
- `D:\Python\python.exe -m pytest`: passed, 165 tests, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
