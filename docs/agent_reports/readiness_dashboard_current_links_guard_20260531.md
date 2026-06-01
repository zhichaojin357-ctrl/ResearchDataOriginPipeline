# Readiness Dashboard Current Links Guard

Date: 2026-05-31

## Issue

`output/review_dashboard/index.md` is a primary user entry point. If it points to the historical `phase1_8_manual_review_required_after_ai.csv` file instead of the current filtered workbook, the README and dashboard can disagree.

## Change

`run.py readiness` now checks `output/review_dashboard/index.md` and requires:

- `phase1_8_manual_review_required_filtered.xlsx`
- `phase1_8_new_auto_process_plan.md`

It fails readiness if the dashboard contains historical post-AI manual-review guidance or the old `phase1_8_manual_review_required_after_ai.csv` entry as a current action.

## Current State

The current dashboard passes the check and points to the filtered workbook and new AUTO_PROCESS dry-run plan.

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 5 tests.
- `D:\Python\python.exe run.py readiness`: passed, 15 checks, 0 failures, 0 warnings.
- `D:\Python\python.exe -m pytest`: passed, 163 tests, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
