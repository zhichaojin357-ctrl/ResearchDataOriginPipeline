# Process Mode And Queue Schema Hardening

- Date: 2026-06-01
- Scope: `run.py process`, `reviewed-queue`, queue-driven output naming, and `readiness` CLI portability.

## Fixes

- `run.py process` now rejects `--auto-select --with-origin` instead of silently downgrading the run to no-Origin.
- `run.py process` now rejects `--auto-select --from-queue` instead of silently ignoring `--auto-select`.
- `reviewed-queue` decision CSV parsing now rejects duplicate headers, missing required headers, unknown columns, blank `proposal_id` rows, row-width mismatches, and malformed CSV parse errors.
- `reviewed-queue` also rejects blank header cells explicitly, so an accidental trailing comma in the header is reported as a schema error.
- `run.py` now converts business `ValueError` and missing-file failures into concise CLI errors with exit code 2 instead of showing a Python traceback.
- `process --from-queue` and `reviewed-queue --proposals` now validate JSON shape before using `items`, so object/list mixups fail with concise CLI errors.
- `process --from-queue` and `reviewed-queue --proposals` now also validate every `items` entry is an object, so malformed string/list entries fail with a precise item number and no traceback.
- `auto-queue --queue` now applies the same JSON schema gate, so malformed current AUTO_PROCESS queues cannot traceback before the dry-run plan is built.
- Queue-driven output naming now derives the dataset suffix from a stable SHA256 digest of the full `queue_id`, preventing reviewed-queue ids such as `phase1_8_*` from collapsing into the same `sample_phase1_8` output name.
- `run.py readiness --no-desktop-review-xlsx` is available for portable checks where the project workbook exists but the desktop copy is intentionally absent.

## Verification

- RED tests confirmed the previous failures for auto-select mode conflicts, reviewed-queue CSV schema validation, and reviewed-queue same-stem output collisions.
- GREEN targeted tests:
  - `D:\Python\python.exe -m pytest tests/test_phase1_1_process_cli.py -q`
  - `D:\Python\python.exe -m pytest tests/test_phase1_8_reviewed_queue.py -q`
  - `D:\Python\python.exe -m pytest tests/test_phase1_1_process_cli.py::Phase11ProcessCliTest::test_cli_reports_non_object_queue_item_without_traceback tests/test_phase1_8_reviewed_queue.py::test_reviewed_queue_cli_reports_non_object_proposal_item_without_traceback -q`
  - `D:\Python\python.exe -m pytest tests/test_auto_queue.py::test_auto_queue_cli_reports_invalid_queue_shape_without_traceback tests/test_auto_queue.py::test_auto_queue_cli_reports_non_object_queue_item_without_traceback tests/test_auto_queue.py -q`
  - `D:\Python\python.exe -m pytest tests/test_processor_behaviors.py tests/test_phase1_2_mixed_triage.py -q`
  - `D:\Python\python.exe -m pytest tests/test_phase1_contracts.py::Phase1ContractsTest::test_readiness_cli_defaults_to_desktop_review_workbook_check tests/test_phase1_contracts.py::Phase1ContractsTest::test_readiness_cli_can_skip_desktop_review_workbook_check -q`
- Full verification:
  - `D:\Python\python.exe -m pytest`: 205 passed, 2 upstream openpyxl warnings.
  - `D:\Python\python.exe run.py deps-audit`: exit 0.
  - `D:\Python\python.exe run.py validate`: exit 0.
  - `D:\Python\python.exe run.py readiness`: exit 0.
  - `D:\Python\python.exe run.py readiness --no-desktop-review-xlsx --report-json output/reports/readiness_report_no_desktop.json --report-md output/reports/readiness_report_no_desktop.md`: exit 0.

## Safety

- No raw data, workspace source data, or F-drive backup files were modified.
- No real processing was run.
- Origin was not launched.
