# Readiness Manual Review Consistency Guard

Date: 2026-05-31

## Issue

`run.py readiness` checked that the filtered manual-review CSV, Excel workbook, and Markdown report existed, but did not verify that they represented the same row count.

That could allow a stale Excel workbook or stale Markdown report to pass readiness while the CSV had already been regenerated.

## Change

`run.py readiness` now verifies:

- CSV row count from `phase1_8_manual_review_required_filtered.csv`;
- Excel `Review` sheet row count from `phase1_8_manual_review_required_filtered.xlsx`;
- reported row count from `phase1_8_manual_review_required_filtered_report.md`.

Readiness fails when these counts disagree.

## Current State

The current outputs pass:

- CSV rows: 493
- Excel `Review` rows: 493
- report rows: 493

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 8 tests.
- `D:\Python\python.exe run.py readiness`: passed, 17 checks, 0 failures, 0 warnings.
- `D:\Python\python.exe -m pytest`: passed, 166 tests, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
