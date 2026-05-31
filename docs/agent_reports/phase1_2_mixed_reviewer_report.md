# Phase 1.2-Mixed Reviewer Report

Date: 2026-05-30

## Review Scope

Reviewed the Phase 1.2 triage and queue-processing implementation against the current goal:

- File-level triage for messy real data.
- Data validity and confidence scoring.
- Duplicate suppression.
- Processing queue generation.
- Selected processing from queue.
- Triage reports and review dashboard updates.
- No-Origin routine testing.
- Raw-data safety.
- Forbidden PPT, kinetics, SEM/TEM/NMR/MS processor scope.

## Issues Found And Fixed

1. Exact duplicates with a backup/copy filename could stay in `MANUAL_REVIEW` instead of being suppressed.
   - Fix: duplicate suppression now uses an AUTO_PROCESS representative and suppresses exact-hash supported copies even if their filename triggered manual review.
   - Regression: `test_triage_creates_queue_reports_and_never_modifies_raw_files`.

2. Same-stem files from different folders overwrote metadata and processed CSV outputs during queue processing.
   - Fix: queue processing now appends a short queue-id suffix to dataset ids, metadata directories, and processed CSV names.
   - Regression: `test_queue_processing_keeps_same_stem_files_from_overwriting_outputs`.

3. Stale queue items were skipped silently when the source hash changed after queue creation.
   - Fix: stale/missing queue items now create `queue_validation` failure records and are not processed.
   - Regression: `test_process_from_queue_reports_stale_hash_without_processing`.

4. The main review dashboard did not include triage summary counts.
   - Fix: `output/review_dashboard/index.md` now includes a `Triage Summary` section when triage reports are present.
   - Regression: `test_process_from_queue_no_origin_processes_only_auto_process_and_records_triage_metadata`.

5. Validation treated copied raw-source `.pptx` files under `workspace_data/` as forbidden generated presentation artifacts.
   - Fix: validation now excludes source data roots `workspace_data/` and `input/raw_data/` from generated-presentation artifact checks while still rejecting presentation files under output/project code paths.
   - Regression: `test_validate_allows_presentation_files_inside_workspace_data_copy` plus existing rejection test.

6. Queue processing could launch Origin if a caller used `--from-queue` but forgot `--no-origin`.
   - Fix: `run_process` now normalizes queue and auto-select processing to no-Origin by default.
   - Regression: `test_process_from_queue_defaults_to_no_origin_even_without_flag`.

7. Queue validation skipped stale checks when a queue item lacked `source_hash`.
   - Fix: missing `source_hash` now creates a `queue_validation` failure and the item is not processed.
   - Regression: `test_process_from_queue_reports_missing_source_hash_without_processing`.

8. Exact duplicates could remain unsuppressed when all matching files were `MANUAL_REVIEW`.
   - Fix: duplicate suppression now chooses a representative from the duplicate group even when no AUTO_PROCESS item exists.
   - Regression: `test_exact_duplicate_suppression_also_handles_manual_review_groups`.

9. No-Origin queue successes were incorrectly listed as missing Origin artifacts.
   - Fix: no-Origin successes now require only `processed_data` and `metadata_path`; `.opju`, `.tif`, and preview PNG are required only for real Origin successes.
   - Regression: `test_process_from_queue_no_origin_processes_only_auto_process_and_records_triage_metadata`.

10. No-Origin missing-artifact reporting checked only whether artifact paths were non-null, not whether the files existed.
    - Fix: processing summary now resolves relative artifact paths against the project root and reports missing required no-Origin artifacts when the files are absent.
    - Regression: `test_processing_summary_reports_missing_no_origin_artifact_files`.

## Verified Scope Guards

- No PPT artifacts were introduced.
- No kinetics processor was introduced.
- SEM/TEM/NMR/MS remain deferred scan-only.
- Routine tests did not launch Origin.
- Queue processing defaults to no-Origin when `--from-queue` is used; verified by running without `--no-origin`.
- Original F-drive data was copied read-only into `workspace_data/`.

## Residual Risks

- Many non-EIS files are still `MANUAL_REVIEW`; promoting them requires explicit manual overrides or improved parser/header rules.
- The requested path `F:\课题\LL\检测中` does not exist; the current real-copy result is based on the existing sibling folder `F:\课题\LL\检测`.
- Origin export for real queue items has not been run in this phase, by user preference for no-Origin routine tests.

## Final Verification

- `D:\Python\python.exe -m pytest`: 73 passed, 2 openpyxl deprecation warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py scan --config config/default.yaml`: exit 0.
- `D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain`: exit 0.
- `D:\Python\python.exe run.py process --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --from-queue output\reports\processing_queue.json --force`: exit 0; processed no-Origin by queue default.
- `origin-test` was intentionally not run during final verification.
