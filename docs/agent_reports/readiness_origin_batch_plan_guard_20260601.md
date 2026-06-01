# Readiness Origin Batch Plan Guard

- Date: 2026-06-01
- Scope: `run.py readiness` coverage for `origin-batch` dry-run plans.

## Fixes

- `readiness` now requires `output/reports/phase1_7_manifest_runner_plan.json`.
- The plan must represent the locked Phase 1.6 package count.
- The plan must have `planned_count=0`, `skipped_count=expected_count`, and `blocked_count=0`.
- The plan must keep `will_launch_origin=false` and `execution.origin_launch=false`.
- Plans with blocked items or Origin launch flags now fail readiness.

## Verification

- RED tests confirmed readiness previously passed when the origin-batch plan had blocked items or Origin launch flags.
- GREEN targeted verification:
  - `D:\Python\python.exe -m pytest tests/test_readiness.py::test_readiness_passes_with_current_required_artifacts tests/test_readiness.py::test_readiness_fails_when_origin_batch_plan_has_blocked_items tests/test_readiness.py::test_readiness_fails_when_origin_batch_plan_would_launch_origin tests/test_readiness.py -q`
  - Result: 20 passed, 2 upstream openpyxl warnings.
- Full verification:
  - `D:\Python\python.exe -m pytest`: 213 passed, 2 upstream openpyxl warnings.
  - `D:\Python\python.exe run.py deps-audit`: exit 0.
  - `D:\Python\python.exe run.py validate`: exit 0.
  - `D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run`: exit 0; 167 skipped; 0 blocked; Origin launch false.
  - `D:\Python\python.exe run.py readiness`: exit 0; 22 checks; 0 failures.
  - `D:\Python\python.exe run.py readiness --no-desktop-review-xlsx --report-json output/reports/readiness_report_no_desktop.json --report-md output/reports/readiness_report_no_desktop.md`: exit 0; 21 checks; 0 failures.

## Safety

- No raw data, workspace source data, or F-drive backup files were modified.
- No real processing was run.
- Origin was not launched.
