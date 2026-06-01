# Phase 1.8 最新人工复核清单

- 生成时间: 2026-05-31 20:36:47
- 来源: `output/reports/data_triage_manifest.json` 最新 triage 结果
- 当前 MANUAL_REVIEW 总数: 618
- 已排除同数据已代表项: 125
- 仍需人工复核: 493

## 输出文件

- CSV: `output/reports/phase1_8_manual_review_required_filtered.csv`
- Excel: `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- 排除审计 CSV: `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.csv`
- 排除审计 Excel: `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`
- 桌面副本: `C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx`

## 保留复核统计

| 数据类型 | 数量 |
|---|---:|
| XPS | 160 |
| XRD | 69 |
| EPR | 64 |
| Mott-Schottky | 50 |
| Raman | 32 |
| FTIR | 30 |
| EIS | 26 |
| BET | 23 |
| PL | 19 |
| UV-vis DRS | 14 |
| photocurrent | 3 |
| photocurrent_response | 3 |

## 排除统计

| 数据类型 | 数量 |
|---|---:|
| Mott-Schottky | 103 |
| EIS | 11 |
| photocurrent | 6 |
| photocurrent_response | 5 |

## 说明

- 本清单只保留最新识别算法后仍无法安全自动分类或处理的文件。
- 如果同一份数据已有可自动处理格式或 Phase 1.6 成功成果代表，则不再放入人工复核主表，只写入排除审计表。
- 本步骤没有处理真实数据，没有启动 Origin，没有修改原始数据。
