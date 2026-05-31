# Phase 1.6 Origin Export Summary

- Updated: 2026-05-31 09:27:11

| type | queue | success | failure |
|---|---:|---:|---:|
| eis | 22 | 22 | 0 |
| photocurrent | 3 | 3 | 0 |
| raman | 30 | 30 | 0 |
| mott_schottky | 90 | 90 | 0 |
| epr | 13 | 13 | 0 |
| xps | 9 | 9 | 0 |

## XPS Repair Addendum

- XPS was originally blocked because processed CSV files had headers but no data rows.
- The reader/processor bug was fixed and the 9 XPS datasets were reprocessed and exported through explicit with-Origin repair queue.
- XPS outputs are raw spectrum plots only; no valence-state assignment was added.
