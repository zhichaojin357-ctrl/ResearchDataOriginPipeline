# CLI Input Directory Guard

- Date: 2026-06-01
- Scope: `run.py scan`, `run.py triage`, and `run.py process` input paths.

## Fixes

- `scan`, `triage`, and `process` now validate the input path before scanning or writing outputs.
- Missing input directories now fail with a concise CLI error and exit code 2.
- File paths passed as input now fail before scanning or processing.
- This prevents typoed paths from producing empty reports, empty queues, or misleading processing summaries.

## Verification

- RED tests confirmed `scan`, `triage`, and `process --no-origin` previously returned exit 0 for missing input directories.
- GREEN targeted verification:
  - `D:\Python\python.exe -m pytest tests/test_phase1_contracts.py::Phase1ContractsTest::test_scan_cli_reports_missing_input_directory_without_outputs tests/test_phase1_contracts.py::Phase1ContractsTest::test_triage_cli_reports_missing_input_directory_without_outputs tests/test_phase1_contracts.py::Phase1ContractsTest::test_process_cli_reports_missing_input_directory_without_outputs tests/test_phase1_contracts.py -q`
  - Result: 19 passed.
- Full verification:
  - `D:\Python\python.exe -m pytest`: 217 passed, 2 upstream openpyxl warnings.
  - `D:\Python\python.exe run.py deps-audit`: exit 0.
  - `D:\Python\python.exe run.py validate`: exit 0.
  - `D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run`: exit 0.
  - `D:\Python\python.exe run.py readiness`: exit 0.
  - `D:\Python\python.exe run.py readiness --no-desktop-review-xlsx --report-json output/reports/readiness_report_no_desktop.json --report-md output/reports/readiness_report_no_desktop.md`: exit 0.

## Safety

- No raw data, workspace source data, or F-drive backup files were modified.
- No real processing was run.
- Origin was not launched.
