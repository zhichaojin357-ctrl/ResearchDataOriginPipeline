# Readiness Reviewed-Queue Consistency Guard

Generated: 2026-05-31

## Problem

`run.py readiness` checked auto-queue artifacts but did not verify the Phase 1.8 reviewed-queue proposal JSON, user decision CSV template, and dry-run plan. If the user edited the decision CSV and forgot to rerun `reviewed-queue --dry-run`, readiness could still report ready while the plan was stale.

## Change

`run.py readiness` now adds `reviewed_queue_plan_current`.

The check verifies:

- `phase1_7_new_override_proposals_after_optimization.json` exists and has an `items` list.
- `phase1_8_review_decisions_template.csv` row count matches proposal count.
- `phase1_8_reviewed_queue_plan.json` summary matches proposal and decision counts.
- approved + skipped + blocked equals total proposals.
- queue item count equals approved count.
- will_launch_origin is false.
- will_run_process is false.
- the plan file is not older than the proposal JSON or decision CSV.

## Current Result

- Proposals: 18
- Decision rows: 18
- Approved: 0
- Blocked: 0
- Will launch Origin: false
- Will run process: false
- Current readiness: 21 checks, 0 failures, 0 warnings

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 14 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.

## Safety

No raw data was modified. No workspace source file was modified. No F-drive backup file was modified. No Origin or Excel process was launched by this change.
