# Phase 1.5 Merged Manual Promotion Proposals

Source manifest: `output/reports/data_triage_manifest.json`
Candidate count: 149

## Rule

MANUAL_REVIEW + parser success + validity >= 0.75 + source hash exists and matches + supported phase 1 + selected processor + no duplicate group + no folder/header conflict + not scan-only/reference types.

## Counts By Type

| data_type | count |
|---|---:|
| EIS | 4 |
| EPR | 13 |
| Mott-Schottky | 90 |
| Raman | 30 |
| XPS | 9 |
| photocurrent | 3 |

## Batches

| batch | data types | count | queue file |
|---|---|---:|---|
| A | EIS | 4 | `phase1_5_merged_promoted_batch_A_no_origin_queue.json` |
| B | Raman, photocurrent | 33 | `phase1_5_merged_promoted_batch_B_no_origin_queue.json` |
| C | Mott-Schottky | 90 | `phase1_5_merged_promoted_batch_C_no_origin_queue.json` |
| D | EPR, XPS | 22 | `phase1_5_merged_promoted_batch_D_no_origin_queue.json` |

## Safety Notes

- Queue items remain `MANUAL_REVIEW` and require `--include-ambiguous`.
- Queue items are no-Origin only; `safe_to_process_with_origin` is false.
- Metadata records original triage decision, promotion rule, batch, confidence, validity, and traceability fields.
- This promotion does not make scientific interpretation claims; manual check remains required.
