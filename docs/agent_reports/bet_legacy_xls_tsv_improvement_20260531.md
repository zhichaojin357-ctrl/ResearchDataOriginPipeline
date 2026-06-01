# BET / Legacy Excel / XLSM Parsing Improvement

## Scope

This report covers the parsing and triage improvements made for BET-related exported tables and nearby Excel formats. It does not claim formal BET production processing or Origin plotting.

## Problem

- BET instrument exports under `D:\Codex Project\科研数据处理\数据\26.5.29\BET` include legacy OLE `.XLS`, `.SMP`, `.DB3`, `.PDF`, and existing `.tsv/.csv/.png/.opju` artifacts.
- The project could identify BET folders, but legacy `.XLS` parsing failed when `xlrd` was unavailable.
- BET `.DB3` files are SQLite files, but inspected files mostly contain only `Attributes` and `LastModified`; most per-sample databases do not expose curve rows directly.
- Ordinary triage must not launch Excel COM, so legacy `.xls` COM fallback is disabled during triage probes.
- EIS `.xlsm` files were previously treated as unsupported/manual even though they can be read safely by pandas/openpyxl without running macros.

## Changes

- Added a hidden private Excel COM fallback for actual legacy `.xls` reads when pandas reports missing `xlrd`.
- Hardened Excel COM reads by disabling visible UI, alerts, events, link prompts, update links, and macros.
- Kept triage safe and fast by disabling Excel COM fallback in parser probes.
- Added `.tsv` to generic table-extension probing and to the BET registry entry.
- Added `.xlsm` support for safe workbook reads and enabled it for the EIS registry entry.
- Fixed two Excel parser crashes found by full triage:
  - empty sheets no longer raise `max() arg is an empty sequence`;
  - duplicated Excel headers are deduplicated before numeric-column scoring.
- Added generic `x` and `y` aliases for two-column numeric table recognition.
- Updated the BET method card to document legacy `.xls` handling and manual checks.

## Read-Only Evidence

- `D:\Codex Project\科研数据处理\数据\26.5.29\BET`: 87 files observed.
- Legacy `.XLS`: 6 files observed.
- `MICDIR.DB3`: 7 files observed; SQLite format.
- Existing BET `.tsv/.csv/.png/.opju` artifacts are present in source/organized folders, but they are treated as existing/reference artifacts unless explicitly selected.
- One real workspace BET `.XLS` was parsed through the fallback into 168 rows and 59 numeric pairs, then processed no-Origin in a temporary output directory only.

## Current BET Status

- BET is more readable by the pipeline than before, especially for `.tsv` and legacy `.xls` sources.
- BET has not yet been formally batch processed into the main results package.
- BET has not yet been formally exported as new Origin OPJU/TIF/PNG outputs by this project.
- Latest triage still leaves BET as:
  - `MANUAL_REVIEW`: 23
  - `AUXILIARY_ONLY`: 10
  - `EXCLUDE_INVALID`: 9

## XLSM Impact

After enabling safe `.xlsm` workbook reads for EIS:

- Total `.xlsm` files in the current workspace triage: 20.
- Parser status for `.xlsm`: 20 success.
- Decisions:
  - `AUTO_PROCESS`: 10
  - `DUPLICATE_SUPPRESSED`: 10
- EIS decision distribution after refresh:
  - `AUTO_PROCESS`: 28
  - `MANUAL_REVIEW`: 34
  - `EXCLUDE_INVALID`: 52
  - `DUPLICATE_SUPPRESSED`: 10
  - `AUXILIARY_ONLY`: 9

## Safety

- No raw data or F-drive backup file was modified.
- No Origin instance was launched.
- Ordinary triage does not use Excel COM.
- Excel COM fallback is only used for explicit legacy `.xls` reads outside triage.
- No residual Excel or Origin process was found after validation.

## Verification

Fresh verification after the `.xlsm` update:

- `D:\Python\python.exe -m pytest`: 145 passed, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py scan --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml`: exit 0.
- `D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh`: exit 0.

Refreshed triage at the XLSM/BET checkpoint, before the later Mott-Schottky header improvement:

- Total files: 1644
- `AUTO_PROCESS`: 72
- `MANUAL_REVIEW`: 723
- `EXCLUDE_INVALID`: 123
- `DUPLICATE_SUPPRESSED`: 67
- `AUXILIARY_ONLY`: 117
- `DEFERRED_TYPE`: 525
- `REFERENCE_ONLY`: 17
- Parser probe success: 530
- Parser probe fail: 35
- Parser probe skipped: 1079

For the newer Mott-Schottky recognition pass, see `docs/agent_reports/triage_mott_schottky_header_improvement_20260531.md`.

## Remaining Work

- BET should remain manual-review/proposal-only until adsorption/desorption columns and sample identity are confirmed.
- Formal BET production still requires an explicit queue and validation pass before generating processed CSV, metadata, OPJU, TIF, and PNG results.
- Remaining parser failures are expected primarily from legacy `.xls` files where triage intentionally refuses to launch Excel COM.
