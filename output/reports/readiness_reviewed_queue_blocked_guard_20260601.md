# Readiness Reviewed-Queue Blocked Guard

- Date: 2026-06-01
- Scope: `run.py readiness`
- Change: readiness now fails when `output/reports/phase1_8_reviewed_queue_plan.json` reports any blocked reviewed-queue approval rows.
- Reason: blocked rows require inspection before the project is treated as ready for the next processing phase.
- Safety: no raw data, workspace source data, F-drive backup data, no-Origin outputs, or Origin outputs were modified.
- Origin: not launched.
- Targeted verification: 19 readiness-related tests passed with 2 upstream openpyxl warnings.

