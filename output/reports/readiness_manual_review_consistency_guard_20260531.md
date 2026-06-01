# Readiness Manual Review Consistency Guard

Date: 2026-05-31

`run.py readiness` now verifies that the filtered manual-review CSV, Excel workbook, and Markdown report agree on row count.

Current state:

- CSV rows: 493
- Excel `Review` rows: 493
- report rows: 493
- readiness: 17 checks, 0 failures, 0 warnings

Verification:

- Full pytest: passed, 166 tests, 2 warnings.
- validate/deps-audit: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
