# XPS CLI Explicit Input Guard

- Date: 2026-06-01
- Scope: `run.py xps-heterojunction-stacked` explicit input paths.

## Fixes

- Explicit `--bobc`, `--cwo`, and `--bc` paths are now validated before output directories are created.
- Missing explicit XPS input files now fail with a concise CLI error and exit code 2.
- Explicit input paths that are directories now fail before processing.
- Dry-run behavior remains no-Origin unless `--with-origin` is explicitly set.

## Verification

- RED test confirmed a missing explicit XPS input path previously returned exit 0 and created output artifacts.
- GREEN targeted verification:
  - `D:\Python\python.exe -m pytest tests/test_xps_heterojunction_stacked.py::test_cli_xps_heterojunction_stacked_reports_missing_explicit_file_without_outputs tests/test_xps_heterojunction_stacked.py -q`
  - Result: 11 passed, 2 upstream openpyxl warnings.
- Full verification:
  - `D:\Python\python.exe -m pytest`: 214 passed, 2 upstream openpyxl warnings.
  - `D:\Python\python.exe run.py deps-audit`: exit 0.
  - `D:\Python\python.exe run.py validate`: exit 0.
  - `D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run`: exit 0.
  - `D:\Python\python.exe run.py readiness`: exit 0.
  - `D:\Python\python.exe run.py readiness --no-desktop-review-xlsx --report-json output/reports/readiness_report_no_desktop.json --report-md output/reports/readiness_report_no_desktop.md`: exit 0.

## Safety

- No raw data, workspace source data, or F-drive backup files were modified.
- No real processing of user data was run.
- Origin was not launched.
- Test-only `_test_missing_xps_input_*` output left by the RED run was removed after verifying it was under project `output/`.
