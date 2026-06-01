# Readiness Preflight

Generated: 2026-05-31

## Change

Added `run.py readiness` as a lightweight project preflight command. It is intended to make the project easier to resume and safer to use before Phase 1.9 or any future no-Origin processing.

## Checks

The command verifies:

- Workspace copy exists.
- F-drive backup exists.
- Locked Phase 1.6 package `index.csv` has the expected 167 rows.
- Locked Phase 1.6 `result_summary.json` exists.
- Current filtered manual-review CSV/XLSX/report exist.
- Current auto-queue plan and queue exist.
- Auto-queue flags still show `will_run_process=false` and `will_launch_origin=false`.
- Phase 1.8 final summaries no longer point to stale `after_ai` artifacts as the current list.
- PPT forbidden paths are absent.

## Current Run

Command:

```powershell
D:\Python\python.exe run.py readiness
```

Output:

- `output/reports/readiness_report.json`
- `output/reports/readiness_report.md`

Current result:

- Checks: 12
- Failures: 0
- Warnings: 0
- Ready: true

## Safety

The readiness command does not process data, does not launch Origin, and does not write into workspace source folders or the F-drive backup.
