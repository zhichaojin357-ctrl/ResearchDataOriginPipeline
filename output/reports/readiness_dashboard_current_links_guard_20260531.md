# Readiness Dashboard Current Links Guard

Date: 2026-05-31

`run.py readiness` now checks that `output/review_dashboard/index.md` points to the current manual-review workbook and new AUTO_PROCESS dry-run plan.

Required dashboard links:

- `phase1_8_manual_review_required_filtered.xlsx`
- `phase1_8_new_auto_process_plan.md`

Current readiness: 15 checks, 0 failures, 0 warnings.

Verification:

- Full pytest: passed, 163 tests, 2 warnings.
- validate/deps-audit: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
