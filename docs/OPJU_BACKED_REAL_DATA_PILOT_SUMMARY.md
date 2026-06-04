# OPJU-Backed Real Data Pilot Summary

## Outcome

The external output root migration and legacy output archive steps are complete. The real-data OPJU exemplar pilot completed inventory, OPJU validation, data-to-OPJU pairing, HPLC/LC deferral, dry-run planning, and product-label audit.

No Phase 9 Origin generation was executed because the dry-run found no row that was safe for unattended generation. Valid OPJU graph pages were present, but generic per-exemplar style mapping has not yet been reviewed or implemented for arbitrary OPJU files.

## Output Roots

- External output root: `D:\Codex Project\科研数据处理\输出`
- Run root: `D:\Codex Project\科研数据处理\输出\runs\20260604_180334_opju_backed_real_data_pilot`
- Legacy archive: `D:\Codex Project\科研数据处理\输出\老版输出\20260604_180002_project_output_archive`

## Protection Status

- F-drive data modified: no
- Original OPJ/OPJU files modified: no
- Output products committed to Git: no
- New Origin projects generated in this pilot: no
- New previews generated in this pilot: no

## Validation Counts

- OPJ/OPJU files inventoried: 100
- Valid OPJU exemplars: 99
- Data-only OPJU exemplars: 1
- Unreadable OPJU exemplars: 0

## Per-Type Status

| Data type | OPJU status | Confidence | Origin generation |
|---|---|---|---|
| BET | valid | high | skipped: needs reviewed style mapping |
| EIS | valid | medium | skipped: manual match required |
| Raman | valid | medium | skipped: needs reviewed style mapping |
| XRD | valid | medium | skipped: manual match required |
| XPS in-situ | valid | high | skipped: needs reviewed style mapping |
| XPS non-in-situ | valid | medium | skipped: manual match required |
| EPR | valid | medium | skipped: manual match required |
| Mott-Schottky | valid | high | skipped: needs reviewed style mapping |
| UV-vis DRS / Tauc | valid | medium | skipped: manual match required |
| PL | valid | medium | skipped: manual match required |
| photocurrent | valid | high | skipped: needs reviewed style mapping |
| FTIR | valid | medium | skipped: manual match required |
| HPLC/LC | missing OPJU | none | deferred |

## Next Manual Calibration Order

1. XPS in-situ
2. XPS non-in-situ
3. BET
4. photocurrent
5. Mott-Schottky
6. EPR
7. XRD
8. EIS
9. Raman / PL / UV-vis DRS / FTIR
10. HPLC/LC after an OPJU exemplar or generic style approval is provided
