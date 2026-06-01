# Auto-Queue Identity Guard

- Date: 2026-06-01
- Scope: Phase 1.8 auto-queue dry-run plan and generated queue consistency.
- Safety: no raw data changes, no workspace source changes, no F-drive writes, no Origin launch, no processing run.

## Problem

`run.py readiness` verified auto-queue counts and safety/provenance flags, but did not compare the generated queue file against the embedded queue in the dry-run plan. A same-length queue with swapped `queue_id`, `relative_path`, or `source_hash` values could pass readiness.

## Change

`run.py readiness` now compares each auto-queue item identity as:

- `queue_id`
- normalized `relative_path`
- `source_hash`

The generated queue must match `phase1_8_new_auto_process_plan.json`'s embedded `queue.items` in order.

## Verification Snapshot

- RED: `D:\Python\python.exe -m pytest tests/test_readiness.py::test_readiness_fails_when_auto_queue_identity_differs_from_plan -q` failed before implementation.
- GREEN: `D:\Python\python.exe -m pytest tests/test_readiness.py::test_readiness_fails_when_auto_queue_identity_differs_from_plan tests/test_readiness.py -q`: 17 passed, 2 warnings.
- `D:\Python\python.exe -m pytest`: 182 passed, 2 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0; 21 checks, 0 failures, 0 warnings.
- Residual process check after a short wait: no `python`, `EXCEL`, `Origin`, or `OriginPro` process remained.

## Files Updated

- `src/core/readiness.py`
- `tests/test_readiness.py`
- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
