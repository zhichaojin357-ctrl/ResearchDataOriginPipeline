# Readiness Reviewed-Queue Blocked Guard

- Date: 2026-06-01
- Scope: `run.py readiness`
- Change: readiness now fails when `output/reports/phase1_8_reviewed_queue_plan.json` reports any blocked reviewed-queue approval rows.
- Reason: a reviewed-queue plan with blocked rows means at least one user approval could not be safely converted into a future dry-run queue item. Treating that state as ready can hide hash, policy, stale-triage, or acknowledgement failures.
- Safety: no raw data, workspace source data, F-drive backup data, no-Origin outputs, or Origin outputs were modified.
- Origin: not launched.
- Tests:
  - `D:\Python\python.exe -m pytest tests/test_readiness.py::test_readiness_fails_when_reviewed_queue_has_blocked_approvals tests/test_phase1_contracts.py::Phase1ContractsTest::test_readiness_cli_defaults_to_desktop_review_workbook_check tests/test_readiness.py -q`
  - Result: 19 passed, 2 warnings.

