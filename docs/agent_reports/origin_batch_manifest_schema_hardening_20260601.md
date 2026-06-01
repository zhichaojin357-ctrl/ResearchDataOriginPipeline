# Origin Batch Manifest Schema Hardening

- Date: 2026-06-01
- Scope: `run.py origin-batch` manifest CSV input validation.

## Fixes

- `origin-batch` now validates manifest CSV headers before planning.
- Missing required manifest headers now fail as concise CLI schema errors.
- Duplicate or blank manifest headers now fail before row planning.
- Manifest rows with too many or too few columns now fail as concise CLI schema errors with row number and expected column count.
- Low-level CSV parse errors are converted into concise CLI schema errors.
- A manifest must include at least one source locator header: `source_file`, `source_copy`, `selected_source_copy`, or `selected_source_data`.
- When an older package manifest lacks a `source_copy` column, `origin-batch` now resolves package source copies by matching `source_hash` under `selected_source_data` before falling back to the mutable workspace path.
- The runner remains dry-run/planning-only and still does not launch Origin.

## Verification

- RED tests confirmed malformed manifest headers previously returned an unhelpful exit 1 without a schema error.
- GREEN targeted test:
  - `D:\Python\python.exe -m pytest tests/test_phase1_7_manifest_runner.py::test_origin_batch_cli_reports_missing_manifest_headers_without_traceback tests/test_phase1_7_manifest_runner.py::test_origin_batch_cli_reports_duplicate_manifest_headers_without_traceback tests/test_phase1_7_manifest_runner.py::test_origin_batch_cli_reports_missing_source_locator_header_without_traceback tests/test_phase1_7_manifest_runner.py -q`
  - Result: 18 passed.
- Real Phase 1.6 package dry-run:
  - `D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run`
  - Result: exit 0; 167 skipped as already complete; 0 planned; 0 blocked; Origin launch false.
- Full verification after this hardening:
  - `D:\Python\python.exe -m pytest`: 211 passed, 2 upstream openpyxl warnings.
  - `D:\Python\python.exe run.py deps-audit`: exit 0.
  - `D:\Python\python.exe run.py validate`: exit 0.
  - `D:\Python\python.exe run.py readiness`: exit 0.
  - `D:\Python\python.exe run.py readiness --no-desktop-review-xlsx --report-json output/reports/readiness_report_no_desktop.json --report-md output/reports/readiness_report_no_desktop.md`: exit 0.

## Safety

- No raw data, workspace source data, or F-drive backup files were modified.
- No real processing was run.
- Origin was not launched.
