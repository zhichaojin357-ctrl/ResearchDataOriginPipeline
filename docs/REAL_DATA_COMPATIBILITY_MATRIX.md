# Real Data Compatibility Matrix

Current workspace copy: `workspace_data\LL_detection_copy_20260530`.

| data_type | AUTO_PROCESS | MANUAL_REVIEW | Phase 1.6 Origin | Phase 1.8 status | next action |
|---|---:|---:|---:|---|---|
| EIS | 46 | 37 | 22 success | 24 new auto-queue candidates after Phase 1.6 exclusion; `.xlsm` and delayed headers supported | review existing previews; use only the generated dry-run queue for future no-Origin processing |
| photocurrent | 6 | 9 | 3 success | 5 new auto-queue candidates after Phase 1.6 exclusion; no automatic interpretation | confirm current units/on-off intervals |
| Raman | 0 | 32 | 30 success | headerless-only files remain manual | confirm normalization/offset before any Phase 1.8 queue |
| Mott-Schottky | 92 | 153 | 90 success | 32 new auto-queue candidates after Phase 1.6 exclusion; CHI delayed-header exports recognized; no CB/VB equivalence | review fit ranges manually before processing new queue |
| EPR | 44 | 64 | 13 success | 44 new auto-queue candidates after Phase 1.6 exclusion; JEOL cAcqu and verified field-intensity tables recognized; no radical assignment | review field-intensity plots manually |
| XPS | 0 | 160 | 9 success | raw spectra only | no valence assignment; review raw/background/component exports |
| XRD | 0 | 69 | 0 | 3 reviewed-queue candidates, high-risk ack required | no phase/crystal-plane assignment |
| UV-vis DRS | 0 | 14 | 0 | 7 reviewed-queue candidates | review wavelength/reflectance/absorbance mapping |
| PL | 0 | 19 | 0 | 6 reviewed-queue candidates | no recombination conclusion |
| FTIR | 0 | 30 | 0 | proposals only | review peak regions manually |
| BET | 0 | 23 | 0 | proposals only; legacy OPJU/PNG/TSV/CSV outputs exist outside the standardized package | review adsorption/desorption columns before adding to a standard queue |
| SEM/TEM/NMR/MS | 0 | 0 | 0 | DEFERRED_TYPE scan-only | keep scan-only |
| reference_literature | 0 | 0 | 0 | REFERENCE_ONLY | keep scan-only |

## Aggregate Counts After Phase 1.8 Reviewed-Queue Gate

- Total files: 1644
- AUTO_PROCESS: 188
- MANUAL_REVIEW: 618
- EXCLUDE_INVALID: 113
- DUPLICATE_SUPPRESSED: 66
- AUXILIARY_ONLY: 117
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17

The latest triage improvements increase recognition only. They do not process the new AUTO_PROCESS candidates and do not run Origin. Any new real processing should still start with a reviewed no-Origin queue.

Current automatically recognized queue after excluding already locked Phase 1.6 hashes:

- Accepted candidates: 105
- EPR: 44
- Mott-Schottky: 32
- EIS: 24
- photocurrent: 5
- Report: `output/reports/phase1_8_new_auto_process_plan.md`
- Candidate queue: `output/reports/phase1_8_new_auto_process_queue.json`

Historical Phase 1.8 reviewed-queue gate outputs remain available:

- Reviewed-queue proposals: 18
- Current approved/skipped/blocked dry-run: 0/18/0

Current user-facing manual review workbook:

- Workbook: `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- Rows requiring user review: 493
- Same-data rows excluded from main workbook: 125
