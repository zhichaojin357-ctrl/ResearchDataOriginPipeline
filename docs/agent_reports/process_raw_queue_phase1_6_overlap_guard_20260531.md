# Process Raw Queue Phase 1.6 Overlap Guard

Date: 2026-05-31

## Issue

The documentation warns users not to process the raw `output/reports/processing_queue.json` because it still contains items already represented in the locked Phase 1.6 Origin package. Before this change, `run.py process --from-queue output/reports/processing_queue.json` could still process that raw queue directly.

## Change

`run.py process --from-queue output/reports/processing_queue.json` now checks the locked Phase 1.6 package index:

`output/phase1_6_origin_results_20260531_041538/index.csv`

If the raw queue contains any matching `source_hash`, the run is blocked before processing and writes queue-validation failures pointing users to:

`output/reports/phase1_8_new_auto_process_queue.json`

Custom vetted queues and generated Phase 1.8 queues are not blocked by this specific raw-queue guard.

The `process --auto-select` help text was also clarified. It is a legacy shortcut, and current Phase 1.8 work should use `run.py auto-queue` first, review the dry-run plan, then process an explicit vetted queue. A regression test confirms `--auto-select` is still blocked when its generated raw queue overlaps Phase 1.6 processed hashes.

## Verification

- `D:\Python\python.exe -m pytest tests\test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_process_blocks_raw_queue_when_phase1_6_processed_hashes_are_present -q`: passed.
- `D:\Python\python.exe -m pytest tests\test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_auto_select_blocks_phase1_6_processed_hashes_from_raw_queue -q`: passed.
- `D:\Python\python.exe -m pytest tests\test_phase1_2_mixed_triage.py tests\test_auto_queue.py tests\test_readiness.py -q`: passed, 25 tests.
- `D:\Python\python.exe -m pytest`: passed, 161 tests, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0, 13 checks, 0 failures, 0 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
