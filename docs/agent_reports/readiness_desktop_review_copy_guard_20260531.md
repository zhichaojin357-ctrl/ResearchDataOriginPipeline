# Readiness Desktop Review Copy Guard

Date: 2026-05-31

## Issue

The README and handoff files point the user to the desktop manual-review workbook:

`C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx`

Before this change, `run.py readiness` checked only the project copy under `output/reports/`. A stale desktop copy could therefore pass readiness while showing the user outdated manual-review rows.

## Change

`run.py readiness` now compares the desktop review workbook against:

`output/reports/phase1_8_manual_review_required_filtered.xlsx`

The check uses SHA256 and fails readiness when the desktop copy is missing, empty, or different from the project copy.

The direct Python API keeps the desktop check optional through `ReadinessOptions.desktop_review_xlsx`; the CLI enables the machine-local desktop check by default.

## Current State

Current desktop copy matches the project workbook:

`940945e6b6f9460df476b97aedb6d8b713c87802471c6fbea1373807daeebeb2`

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 4 tests.
- `D:\Python\python.exe run.py readiness`: passed, 14 checks, 0 failures, 0 warnings.
- `D:\Python\python.exe -m pytest`: passed, 162 tests, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
