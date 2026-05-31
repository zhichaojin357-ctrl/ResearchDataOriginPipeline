# Phase 1.5 Merged Triage Refresh Report

Created at: 2026-05-31 00:46 +08:00

## Commands

```powershell
D:\Python\python.exe run.py scan --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml
D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh
```

Both commands exited 0.

## Current Triage Counts

| decision | count |
|---|---:|
| AUTO_PROCESS | 18 |
| MANUAL_REVIEW | 737 |
| EXCLUDE_INVALID | 121 |
| DUPLICATE_SUPPRESSED | 58 |
| AUXILIARY_ONLY | 113 |
| DEFERRED_TYPE | 525 |
| REFERENCE_ONLY | 17 |

Total files: 1589.

## Difference From Previous Phase 1.5 Baseline

No count differences from the immediately preceding Phase 1.5 baseline:

- Total files: 1589 -> 1589
- AUTO_PROCESS: 18 -> 18
- MANUAL_REVIEW: 737 -> 737
- EXCLUDE_INVALID: 121 -> 121
- DUPLICATE_SUPPRESSED: 58 -> 58
- AUXILIARY_ONLY: 113 -> 113
- DEFERRED_TYPE: 525 -> 525
- REFERENCE_ONLY: 17 -> 17

## Queue Summary

- Current processing queue items: 18
- EIS AUTO_PROCESS items: 18
- Stale queue items detected during triage refresh: 0
- Hash mismatch items detected during triage refresh: 0
- Missing file items detected during triage refresh: 0

## Non-EIS Manual Review Distribution

| data type | MANUAL_REVIEW |
|---|---:|
| Mott-Schottky | 252 |
| XPS | 166 |
| XRD | 66 |
| EPR | 58 |
| Raman | 32 |
| FTIR | 30 |
| PL | 23 |
| BET | 23 |
| photocurrent | 15 |
| photocurrent_response | 11 |
| UV-vis DRS | 7 |
| HPLC/LC exported data | 0 |
| reaction_condition_screening | 0 |

## Candidate Counts Requested By Type

- XRD candidates: 66
- UV-vis candidates: 7
- Photocurrent candidates: 15
- Photocurrent response candidates: 11
- XPS candidates: 166
- PL candidates: 23
- FTIR candidates: 30
- Raman candidates: 32
- BET candidates: 23
- EPR candidates: 58
- Mott-Schottky candidates: 252
- LC/HPLC candidates: 0
- Reaction screening candidates: 0

## Deferred And Reference Counts

| deferred/reference type | count |
|---|---:|
| MS | 239 |
| SEM_image_data | 160 |
| TEM_image_data | 76 |
| NMR | 50 |
| reference_literature | 17 |

SEM/TEM/NMR/MS remain scan-only. Reference literature remains scan-only.

## Conflicts And Parser Errors

- Folder/header conflict count: 44
- Top parser error:
  - 35 files: `Import xlrd` failed; `.xls` support requires `xlrd >= 2.0.1`.

## Top Ambiguous Reasons

| reason | count |
|---|---:|
| parser_probe_not_success | 514 |
| below_auto_process_threshold_or_ambiguous | 205 |
| folder_header_type_conflict | 18 |

## Top Excluded Reasons

| reason | count |
|---|---:|
| insufficient_numeric_table | 111 |
| empty_file | 9 |
| parser_probe_not_success | 1 |

## Top Auxiliary Reasons

| reason | count |
|---|---:|
| origin_project_file_grouped_with_same_folder_data | 59 |
| document_or_report_not_primary_data | 31 |
| plot_image_not_raw_numeric_data | 23 |

## Notes

- The triage refresh preserved the current queue: 18 high-confidence EIS items.
- `.opju` and related Origin project/template files remain grouped with their data via traceability fields but are not processing inputs.
- The main blocker for broader automatic processing remains MANUAL_REVIEW confidence, parser failure for some `.xls` files, and scientific ambiguity for high-risk types.
