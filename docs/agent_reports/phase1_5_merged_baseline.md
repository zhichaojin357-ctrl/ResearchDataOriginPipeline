# Phase 1.5 Merged Baseline

Created at: 2026-05-31 00:39 +08:00

## Git

- Current branch: unavailable.
- `git status`: failed because `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline` is not a git repository.
- Lightweight tag `phase1_5_merged_start_baseline`: not created because this directory is not a git repository.

## Interpreter

- Project interpreter: `D:\Python\python.exe`
- Python version: 3.12.5
- PATH `python` resolution order:
  - `D:\MestReNova\python.exe`
  - `D:\Python\python.exe`
  - `C:\Users\lenovo\AppData\Local\Microsoft\WindowsApps\python.exe`

Use `D:\Python\python.exe` explicitly for project commands.

## Paths

- Project root: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- Workspace copy exists: yes
- Workspace copy path: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data\LL_detection_copy_20260530`
- Workspace copy files: 1589
- Workspace copy bytes: 2643322364
- F-drive backup exists: yes
- F-drive backup path: `F:\课题\LL\检测`
- F-drive backup files: 1582
- F-drive backup bytes: 2642973440

The workspace copy has been reorganized by the user and intentionally differs from the original backup count/size.

## Origin State

- Origin process before baseline commands: none detected.
- Origin process after baseline validation commands: none detected.
- Ordinary baseline validation did not intentionally launch Origin.

## Verification Commands

- `D:\Python\python.exe -m pytest`: exit 0; 75 passed, 2 openpyxl deprecation warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.

## Dependency Audit Summary

- Core dependencies available: `pandas`, `numpy`, `scipy`, `openpyxl`, `yaml`, `pybaselines`, `originpro`, `win32com`.
- Optional dependencies available: `impedance`, `pymzml`.
- Optional dependencies missing as warnings: `ixdat`, `galvani`, `eclabfiles`, `pygaps`, `lmfitxps`, `ramanspy`, `rampy`, `spectrochempy`, `hplc`, `rainbow`, `pyteomics`.

## Validation Summary

- Dependency audit: pass.
- Origin callability: pass by importability check.
- Required output directories/config files: pass.
- Processor registry entries: 19.
- Phase 1 supported entries: 14.
- PPT forbidden paths/artifacts: pass.
- Kinetics processor paths: pass.
- TIF export config: pass.
- Origin Graph4 contract checks: pass.
- `max_threads = 5`.
- `max_depth = 1`.
- Claim policy forbidden claims: 14.

## Current Data Baseline

- Total files: 1589
- AUTO_PROCESS: 18
- MANUAL_REVIEW: 737
- EXCLUDE_INVALID: 121
- DUPLICATE_SUPPRESSED: 58
- AUXILIARY_ONLY: 113
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17
- Current processing queue: 18 EIS items.
- Current no-Origin processed EIS datasets: 18 success, 0 failure.
- Processing failures: none recorded.
- Missing processed artifacts: none recorded.
- Traceability groups: 109.
- Groups with existing Origin project/template files: 37.
- Groups with queued files: 4.

## Key Reports Present

- `output\reports\data_triage_manifest.json`
- `output\reports\data_triage_report.md`
- `output\reports\processing_queue.json`
- `output\reports\processing_queue.md`
- `output\reports\ambiguous_files.json`
- `output\reports\ambiguous_files.md`
- `output\reports\excluded_files.json`
- `output\reports\excluded_files.md`
- `output\reports\duplicate_candidates.json`
- `output\reports\duplicate_candidates.md`
- `output\reports\source_hash_index.json`
- `output\reports\traceability_groups.json`
- `output\reports\traceability_groups.md`
- `output\reports\processing_summary.json`
- `output\reports\processing_summary.md`
- `output\reports\processing_failures.json`
- `output\reports\processing_failures.md`
- `output\reports\validation_report.md`
- `output\reports\dependency_audit.md`

## Known Success State

- Scan/triage/process pipeline exists and is working for high-confidence EIS queue items.
- Queue processing defaults to no-Origin when `--from-queue` is used.
- Queue items include source hashes and stale queue checks.
- Metadata and processed CSV outputs exist for the 18 EIS queue items.
- Traceability grouping is present for grouped data, existing `.opju` files, and output reports.
- Routine tests pass without leaving an Origin process running.

## Known Gaps To Continue

- The CLI does not yet expose an explicit `--with-origin` flag for queue processing; current behavior silently converts `--from-queue` to no-Origin unless `--no-origin` is bypassed internally.
- MANUAL_REVIEW files still need systematic clustering and safe promotion proposals.
- Non-EIS supported data types have not yet been promoted and no-Origin processed at scale.
- EIS and non-EIS Origin output queues still need guarded construction and execution/review under Phase 1.5 rules.
- The user-requested final result folder with selected data copies, processed outputs, previews/screenshots, and clear source-output labels still needs to be built.
- Phase 1.5 bug radar, path safety audit, output consistency audit, visual preview audit, reviewer report, and final validation report still need to be generated.
