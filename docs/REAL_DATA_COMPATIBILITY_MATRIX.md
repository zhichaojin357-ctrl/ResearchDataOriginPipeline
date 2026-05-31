# Real Data Compatibility Matrix

Current workspace copy: `workspace_data\LL_detection_copy_20260530`.

| data_type | AUTO_PROCESS | MANUAL_REVIEW | Phase 1.6 Origin | Phase 1.8 status | next action |
|---|---:|---:|---:|---|---|
| EIS | 18 | 54 | 22 success | manifest dry-run skips completed outputs | review existing previews; approve any new queue manually |
| photocurrent | 0 | 15 | 3 success | no automatic interpretation | confirm current units/on-off intervals |
| Raman | 0 | 32 | 30 success | headerless-only files remain manual | confirm normalization/offset before any Phase 1.8 queue |
| Mott-Schottky | 0 | 252 | 90 success | no CB/VB equivalence | review fit ranges manually |
| EPR | 0 | 58 | 13 success | no radical assignment | review field-intensity plots manually |
| XPS | 0 | 165 | 9 success | raw spectra only | no valence assignment; review raw/background/component exports |
| XRD | 0 | 69 | 0 | 3 reviewed-queue candidates, high-risk ack required | no phase/crystal-plane assignment |
| UV-vis DRS | 0 | 14 | 0 | 7 reviewed-queue candidates | review wavelength/reflectance/absorbance mapping |
| PL | 0 | 19 | 0 | 6 reviewed-queue candidates | no recombination conclusion |
| FTIR | 0 | 30 | 0 | proposals only | review peak regions manually |
| BET | 0 | 23 | 0 | proposals only | review adsorption/desorption columns |
| SEM/TEM/NMR/MS | 0 | 0 | 0 | DEFERRED_TYPE scan-only | keep scan-only |
| reference_literature | 0 | 0 | 0 | REFERENCE_ONLY | keep scan-only |

## Aggregate Counts After Phase 1.8 Reviewed-Queue Gate

- Total files: 1589
- AUTO_PROCESS: 18
- MANUAL_REVIEW: 742
- EXCLUDE_INVALID: 121
- DUPLICATE_SUPPRESSED: 53
- AUXILIARY_ONLY: 113
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17

Phase 1.8 keeps automatic processing unchanged. It adds a user-reviewed queue gate and a post-rule/post-AI manual review list:

- Reviewed-queue proposals: 18
- Current approved/skipped/blocked dry-run: 0/18/0
- Manual review required after AI-assisted recognition: 538
- Already represented in Phase 1.6 and excluded from the user-review list: 151
- Duplicate-grouped and excluded from the user-review list: 53
