# Phase 1.6 No-Origin Result Consistency

Total items: 167

## Status Counts

| status | count |
|---|---:|
| ACCEPT_FOR_ORIGIN | 158 |
| BLOCKED | 9 |

## ACCEPT_FOR_ORIGIN By Type

| data_type | count |
|---|---:|
| EIS | 22 |
| EPR | 13 |
| Mott-Schottky | 90 |
| Raman | 30 |
| photocurrent | 3 |

## BLOCKED By Type

| data_type | count |
|---|---:|
| XPS | 9 |

## Main Findings

- 18 AUTO EIS metadata records were fixed to include explicit AUTO_PROCESS provenance.
- 9 XPS records have processed CSV files with headers only and are BLOCKED from Origin export.
- 158 records are accepted for Origin candidate queues.

## Issues

| result_id | issue |
|---|---|
| `XPS_BI_64d751af` | processed_csv_has_no_data_rows |
| `XPS_cu-20260506_0491cce0` | processed_csv_has_no_data_rows |
| `XPS_cu-260506_0d4a12c7` | processed_csv_has_no_data_rows |
| `XPS_DARK-20260506_be31e8e2` | processed_csv_has_no_data_rows |
| `XPS_dark_7bcffc32` | processed_csv_has_no_data_rows |
| `XPS_light_a0ea8cb1` | processed_csv_has_no_data_rows |
| `XPS_LIGHT_bf658e4e` | processed_csv_has_no_data_rows |
| `XPS_LINGT-20260506_5dde5fe2` | processed_csv_has_no_data_rows |
| `XPS_Microsoft_Excel_c402d286` | processed_csv_has_no_data_rows |
