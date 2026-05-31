# Data Triage Report

Source root: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data\LL_detection_copy_20260530`

- AUTO_PROCESS: 18
- MANUAL_REVIEW: 742
- EXCLUDE_INVALID: 121
- DUPLICATE_SUPPRESSED: 53
- AUXILIARY_ONLY: 113
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17

## Files

| decision | data_type | traceability_role | traceability_group | confidence | validity | relative_path | reasons |
|---|---|---|---|---:|---:|---|---|
| EXCLUDE_INVALID | unknown | raw_or_exported_numeric_table | `00_索引与说明` | 0.0 | 0.25 | `00_索引与说明/duplicate_opju_sha256.csv` | insufficient_numeric_table |
| EXCLUDE_INVALID | unknown | raw_or_exported_numeric_table | `00_索引与说明` | 0.0 | 0.25 | `00_索引与说明/file_snapshot_after.csv` | insufficient_numeric_table |
| EXCLUDE_INVALID | unknown | raw_or_exported_numeric_table | `00_索引与说明` | 0.0 | 0.25 | `00_索引与说明/file_snapshot_before.csv` | insufficient_numeric_table |
| EXCLUDE_INVALID | unknown | raw_or_exported_numeric_table | `00_索引与说明` | 0.0 | 0.25 | `00_索引与说明/move_log.csv` | insufficient_numeric_table |
| EXCLUDE_INVALID | unknown | raw_or_exported_numeric_table | `00_索引与说明` | 0.0 | 0.25 | `00_索引与说明/opju_数据对应索引.csv` | insufficient_numeric_table |
| EXCLUDE_INVALID | unknown | raw_or_exported_numeric_table | `00_索引与说明` | 0.0 | 0.25 | `00_索引与说明/opju_精细对应关系.csv` | insufficient_numeric_table |
| EXCLUDE_INVALID | unknown | auxiliary_file | `00_索引与说明` | 0.0 | 0.0 | `00_索引与说明/整理说明.md` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20251110` | 0.35 | 0.0 | `01_XRD/20251110/bobc shuirei.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_or_exported_numeric_table | `01_XRD/20251110` | 0.45 | 0.25 | `01_XRD/20251110/bobc shuirei.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20251110` | 0.35 | 0.0 | `01_XRD/20251110/bobc shuirei2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_or_exported_numeric_table | `01_XRD/20251110` | 0.45 | 0.25 | `01_XRD/20251110/bobc shuirei2.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20251110` | 0.35 | 0.0 | `01_XRD/20251110/bobcshuirei+cwo15%.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_or_exported_numeric_table | `01_XRD/20251110` | 0.45 | 0.25 | `01_XRD/20251110/bobcshuirei+cwo15%.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20251110` | 0.35 | 0.0 | `01_XRD/20251110/kit-6-1.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_or_exported_numeric_table | `01_XRD/20251110` | 0.45 | 0.25 | `01_XRD/20251110/kit-6-1.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20251110` | 0.35 | 0.0 | `01_XRD/20251110/kit-6-2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_or_exported_numeric_table | `01_XRD/20251110` | 0.45 | 0.25 | `01_XRD/20251110/kit-6-2.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20260326LL BOB BOC BCN` | 0.35 | 0.0 | `01_XRD/20260326LL BOB BOC BCN/BICSNH4.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20260326LL BOB BOC BCN` | 0.35 | 0.0 | `01_XRD/20260326LL BOB BOC BCN/BICSNH4.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20260326LL BOB BOC BCN` | 0.35 | 0.0 | `01_XRD/20260326LL BOB BOC BCN/CL.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20260326LL BOB BOC BCN` | 0.35 | 0.0 | `01_XRD/20260326LL BOB BOC BCN/CL.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20260326LL BOB BOC BCN` | 0.35 | 0.0 | `01_XRD/20260326LL BOB BOC BCN/NH4.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/20260326LL BOB BOC BCN` | 0.35 | 0.0 | `01_XRD/20260326LL BOB BOC BCN/NH4.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/BOBC+MS/250530` | 0.35 | 0.0 | `01_XRD/BOBC+MS/250530/bm.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_or_exported_numeric_table | `01_XRD/BOBC+MS/250530` | 0.45 | 0.25 | `01_XRD/BOBC+MS/250530/bm.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/BOBC+MS/250530` | 0.35 | 0.0 | `01_XRD/BOBC+MS/250530/BOBC.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_or_exported_numeric_table | `01_XRD/BOBC+MS/250530` | 0.45 | 0.85 | `01_XRD/BOBC+MS/250530/BOBC.TXT` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/origin_project/20251024 MOSE2的量需要更多更多，没有明显峰，标准卡片没有导入.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XRD | processed_table | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/processed_tables/mb9.jip` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/raw_data/bobc.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.45 | 0.25 | `01_XRD/BOBC+MS/251024/raw_data/bobc.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/raw_data/mb9.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.45 | 0.25 | `01_XRD/BOBC+MS/251024/raw_data/mb9.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/raw_data/MOSE2 10MIN.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/raw_data/MOSE2 10MIN.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.45 | 0.25 | `01_XRD/BOBC+MS/251024/raw_data/mose2 10min.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/raw_data/MOSE2 5MIN.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.35 | 0.0 | `01_XRD/BOBC+MS/251024/raw_data/MOSE2 5MIN.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/BOBC+MS/251024` | 0.45 | 0.25 | `01_XRD/BOBC+MS/251024/raw_data/mose2 5min.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | exported_figure | `01_XRD/BOBC+MS` | 0.35 | 0.0 | `01_XRD/BOBC+MS/MS+BOBC.tif` | plot_image_not_raw_numeric_data |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/BPO` | 0.35 | 0.0 | `01_XRD/BPO/BPO+MS.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_or_exported_numeric_table | `01_XRD/BPO` | 0.45 | 0.85 | `01_XRD/BPO/BPO+MS.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | XRD | auxiliary_file | `01_XRD/BPO` | 0.35 | 0.0 | `01_XRD/BPO/BPO.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_or_exported_numeric_table | `01_XRD/BPO` | 0.45 | 0.85 | `01_XRD/BPO/BPO.TXT` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/BWO` | 0.35 | 0.0 | `01_XRD/BWO/origin_project/BWO.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BWO` | 0.35 | 0.0 | `01_XRD/BWO/raw_data/A BWO.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/BWO` | 0.45 | 0.25 | `01_XRD/BWO/raw_data/A BWO.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/BWO` | 0.35 | 0.0 | `01_XRD/BWO/raw_data/M BWO.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/BWO` | 0.45 | 0.25 | `01_XRD/BWO/raw_data/M BWO.TXT` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/origin_project/CWO+BOBC+标卡.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/BOBC/BOBC.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/BOBC/BOBC.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/BOBC/BOBC600度/BOBC600.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/BOBC/BOBC600度/BOBC600.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/BOBC/BOBC600度/bobc600.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/CWO  PDF#04-009-8466.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/BC-15/BOBC+BOBC15%.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/BC-15/BOBC+BOBC15%.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/BC-15/BOBC+CWO15%.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/BC-15/BOBC+CWO15%.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/BC-30/BC30.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/BC-30/BC30.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/CWO为主体/cwo10.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/CWO为主体/cwo10.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/CWO为主体/cwo15.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/CWO为主体/cwo15.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/CWO为主体/cwo5.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/CWO为主体/cwo5.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo+bobc/XRD2.tif` | plot_image_not_raw_numeric_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo八面体/cwo 8.jip` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo八面体/cwo 8.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo八面体/cwo 8面体.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo沉淀法+合适的标准卡片/CWO 对 沉淀PDF#04-009-6293.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo沉淀法+合适的标准卡片/cwo.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo沉淀法+合适的标准卡片/cwo.jip` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.35 | 0.0 | `01_XRD/CWO+BOBC/raw_data/cwo沉淀法+合适的标准卡片/cwo.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/CWO+BOBC` | 0.45 | 0.25 | `01_XRD/CWO+BOBC/raw_data/cwo沉淀法+合适的标准卡片/cwo.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | exported_figure | `01_XRD/KIT-6` | 0.35 | 0.0 | `01_XRD/KIT-6/exported_figures/kit-6.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/KIT-6` | 0.35 | 0.0 | `01_XRD/KIT-6/origin_project/kit-6.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/KIT-6` | 0.35 | 0.0 | `01_XRD/KIT-6/origin_project/KIT-6第二批.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/KIT-6` | 0.35 | 0.0 | `01_XRD/KIT-6/raw_data/kit-6bo.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/KIT-6` | 0.45 | 0.25 | `01_XRD/KIT-6/raw_data/kit-6bo.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/KIT-6` | 0.35 | 0.0 | `01_XRD/KIT-6/raw_data/kit-6bo2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/KIT-6` | 0.45 | 0.25 | `01_XRD/KIT-6/raw_data/kit-6bo2.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/KIT-6` | 0.35 | 0.0 | `01_XRD/KIT-6/raw_data/kit-6fe.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/KIT-6` | 0.45 | 0.25 | `01_XRD/KIT-6/raw_data/kit-6fe.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | exported_figure | `01_XRD/MS/MSXRD` | 0.5 | 0.0 | `01_XRD/MS/MSXRD/exported_figures/1mmolmose2的XRD.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/origin_project/MOSE2.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/origin_project/MS.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/MS/MSXRD` | 0.5 | 0.0 | `01_XRD/MS/MSXRD/origin_project/球磨第二批XRD.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose3.1.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose3.1.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose3.2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose3.2.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose4.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose4.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose4re.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose4re.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose5.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/4种方法/mose5.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/XRD2.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.5 | 0.0 | `01_XRD/MS/MSXRD/raw_data/4种方法/XRD同.pdf` | document_or_report_not_primary_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/2h.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/QIUMO/2h.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/6h.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/QIUMO/6h.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO1.1.dql` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO1.1.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO1.2.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO1.2.TXT` | insufficient_numeric_table |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO1.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO2.1.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO2.1.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO2.2.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/QIUMO/球磨第一次/QIUMO2.2.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/SHUIRE/mose new 啥也不是.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/SHUIRE/mose new.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/SHUIRE/mose3bei.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/SHUIRE/mose方法4，放大3bei.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/SHUIRE/re mose3bei.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/SHUIRE/re mose3bei.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/初版PEG/PDF#00-029-0914.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/初版PEG/PEG/MS-200.raw` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/初版PEG/PEG/MS200.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/初版PEG/PEG/MS200.TXT` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.35 | 0.0 | `01_XRD/MS/MSXRD/raw_data/初版PEG/PEG/MS400.RAW` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/MS/MSXRD` | 0.45 | 0.25 | `01_XRD/MS/MSXRD/raw_data/初版PEG/PEG/MS400.TXT` | insufficient_numeric_table |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/MS` | 0.35 | 0.0 | `01_XRD/MS/origin_project/BPO+MS.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XRD | origin_project_reference | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/origin_project/20241125XRD.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl-TiO2 2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.45 | 0.25 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl-TiO2 2.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl-TiO2.bc` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl-TiO2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.45 | 0.25 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl-TiO2.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.45 | 0.25 | `01_XRD/研一上xrd数据及图片/raw_data/BiOBrCl.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/raw_data/TiO2.bc` | parser_probe_not_success |
| MANUAL_REVIEW | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.35 | 0.0 | `01_XRD/研一上xrd数据及图片/raw_data/TiO2.raw` | parser_probe_not_success |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.45 | 0.25 | `01_XRD/研一上xrd数据及图片/raw_data/TiO2.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | XRD | raw_data | `01_XRD/研一上xrd数据及图片` | 0.45 | 0.25 | `01_XRD/研一上xrd数据及图片/raw_data/TIO2标准卡片PDF#98-000-0081.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS` | 0.35 | 0.0 | `02_XPS/origin_project/BC-OW.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS` | 0.5 | 0.0 | `02_XPS/origin_project/bc-XPS.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS` | 0.5 | 0.0 | `02_XPS/origin_project/bobc xps.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS` | 0.5 | 0.0 | `02_XPS/origin_project/cwo xps.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS` | 0.35 | 0.0 | `02_XPS/origin_project/CWO+BOBC VBXPS谱图.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_archives/26010989730.rar` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.5 | 0.0 | `02_XPS/raw_archives/原位XPS.zip` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/BC-11.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/bc拟合后的数据.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/BI.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/Valence.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.5 | 0.0 | `02_XPS/raw_data/26010989730/BC-11/XPS Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/bc拟合后的数据.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/BOBC.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/BOBC数据拟合后2.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/Valence.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.5 | 0.0 | `02_XPS/raw_data/26010989730/BOBC/XPS Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/BOBC数据拟合后2.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/CWO/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/CWO/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/CWO/CWO.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/CWO/CWO数据拟合后.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/CWO/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/CWO/Valence.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/26010989730/CWO/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.5 | 0.0 | `02_XPS/raw_data/26010989730/CWO/XPS Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/26010989730/CWO数据拟合后.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Bi4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Br3d Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Cl2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Cu2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/O1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Valence.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/Valence_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/W4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.5 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/XPS Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.5 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.DATA/XPS Survey_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BC拟合后/Data Grid.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.45 | 0.0 | `02_XPS/raw_data/BOBC拟合后/BOBC数据拟合后2.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Bi4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Br3d Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Cl2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/O1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Valence.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/Valence_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.5 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/XPS Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.5 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.DATA/XPS Survey_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/BOBC拟合后/Data Grid.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.45 | 0.0 | `02_XPS/raw_data/CWO拟合后/cu-20260506.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.45 | 0.0 | `02_XPS/raw_data/CWO拟合后/cu-260506.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.45 | 0.0 | `02_XPS/raw_data/CWO拟合后/CWO数据拟合后.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/Cu2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/O1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/Valence.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/Valence_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/W4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.5 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/XPS Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.5 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.DATA/XPS Survey_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data` | 0.35 | 0.0 | `02_XPS/raw_data/CWO拟合后/Data Grid.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/1#-light.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/1#.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1-light.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/26041816225/Processing View #1.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/原位XPS/DARK-20260506.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Bi4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Br3d Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Cl2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Cu2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/O1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/Survey_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.DATA/W4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/DARK.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Bi4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Br3d Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Cl2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Cu2p Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/O1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/Survey_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/raw_data/原位XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.DATA/W4f Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.35 | 0.0 | `02_XPS/raw_data/原位XPS/light .vgp CU没有拟合.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/原位XPS/LIGHT.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/原位XPS/LINGT-20260506.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | raw_data | `02_XPS` | 0.45 | 0.0 | `02_XPS/raw_data/原位XPS/新建 Microsoft Excel 工作表.xls` | parser_probe_not_success |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS/电荷未矫正第一次` | 0.5 | 0.0 | `02_XPS/电荷未矫正第一次/origin_project/xps 全数据BI.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS/电荷未矫正第一次` | 0.5 | 0.0 | `02_XPS/电荷未矫正第一次/origin_project/xps全数据CU.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | XPS | origin_project_reference | `02_XPS/电荷未矫正第一次` | 0.5 | 0.0 | `02_XPS/电荷未矫正第一次/origin_project/xps全数据版.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/processed_tables/dark拟合第一遍.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次` | 0.45 | 0.0 | `02_XPS/电荷未矫正第一次/processed_tables/dark拟合第一遍.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/processed_tables/light拟合第一遍.vgp` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次` | 0.45 | 0.0 | `02_XPS/电荷未矫正第一次/processed_tables/light拟合第一遍.xls` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/dark拟合第一遍.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/Bi4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/Br3d Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/C1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/C1s Scan_0.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/Cl2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/Cu2p Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/O1s Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/Survey.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | XPS | processed_table | `02_XPS/电荷未矫正第一次/raw_data` | 0.35 | 0.0 | `02_XPS/电荷未矫正第一次/raw_data/light拟合第一遍.DATA/W4f Scan.VGD` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | auxiliary_file | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.35 | 0.0 | `03_光电流/20260109_光电流/26010964564/Photocurrent/1-BOC-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.45 | 0.85 | `03_光电流/20260109_光电流/26010964564/Photocurrent/1-BOC-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent | auxiliary_file | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.35 | 0.0 | `03_光电流/20260109_光电流/26010964564/Photocurrent/2-MCS-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.45 | 0.85 | `03_光电流/20260109_光电流/26010964564/Photocurrent/2-MCS-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent | auxiliary_file | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.35 | 0.0 | `03_光电流/20260109_光电流/26010964564/Photocurrent/3-BM-10-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.45 | 0.85 | `03_光电流/20260109_光电流/26010964564/Photocurrent/3-BM-10-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent | auxiliary_file | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.35 | 0.0 | `03_光电流/20260109_光电流/26010964564/Photocurrent/4-BOBC-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.45 | 0.85 | `03_光电流/20260109_光电流/26010964564/Photocurrent/4-BOBC-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent | auxiliary_file | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.35 | 0.0 | `03_光电流/20260109_光电流/26010964564/Photocurrent/5-CWO-(OCP) .bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.45 | 0.85 | `03_光电流/20260109_光电流/26010964564/Photocurrent/5-CWO-(OCP) .txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent | auxiliary_file | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.35 | 0.0 | `03_光电流/20260109_光电流/26010964564/Photocurrent/6-BC-11-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564/Photocurrent` | 0.45 | 0.85 | `03_光电流/20260109_光电流/26010964564/Photocurrent/6-BC-11-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | photocurrent | document_or_report | `03_光电流/20260109_光电流/26010964564` | 0.5 | 0.0 | `03_光电流/20260109_光电流/26010964564/光电流基线处理教程.pdf` | document_or_report_not_primary_data |
| EXCLUDE_INVALID | photocurrent | raw_or_exported_numeric_table | `03_光电流/20260109_光电流/26010964564` | 0.45 | 0.4 | `03_光电流/20260109_光电流/26010964564/备注.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | photocurrent_response | origin_project_reference | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.35 | 0.0 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/origin_project/I-T BOBC+CWO 4.22.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.35 | 0.0 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/bicu/1-（OCP）.bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.45 | 0.85 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/bicu/1-（OCP）.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.35 | 0.0 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/BOBC/1-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.45 | 0.85 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/BOBC/1-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.35 | 0.0 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/CWO/2-(OCP).bin` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10` | 0.45 | 0.85 | `03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/CWO/2-(OCP).txt` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | photocurrent_response | origin_project_reference | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/origin_project/SECOND.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | photocurrent_response | origin_project_reference | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/origin_project/光电流相应CWO+BOBC.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_archives/2758_1774879987011_26032562524.zip` | parser_probe_not_success |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_archives/2758_1776699905862_26041550465.zip` | parser_probe_not_success |
| EXCLUDE_INVALID | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.45 | 0.4 | `03_光电流/光电流响应/raw_data/备注.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第一次CWO BOBC BC数据/4-BOBC-(OCP).bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.45 | 0.85 | `03_光电流/光电流响应/raw_data/第一次CWO BOBC BC数据/4-BOBC-(OCP).txt` | exact_duplicate_suppressed |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第一次CWO BOBC BC数据/5-CWO-(OCP) .bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.45 | 0.85 | `03_光电流/光电流响应/raw_data/第一次CWO BOBC BC数据/5-CWO-(OCP) .txt` | exact_duplicate_suppressed |
| MANUAL_REVIEW | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第一次CWO BOBC BC数据/6-BC-11-(OCP).bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.45 | 0.85 | `03_光电流/光电流响应/raw_data/第一次CWO BOBC BC数据/6-BC-11-(OCP).txt` | exact_duplicate_suppressed |
| MANUAL_REVIEW | photocurrent | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第三次光电流补测/26041550465/Photocurrent/1-（OCP）.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | photocurrent | raw_data | `03_光电流/光电流响应` | 0.45 | 0.85 | `03_光电流/光电流响应/raw_data/第三次光电流补测/26041550465/Photocurrent/1-（OCP）.txt` | exact_duplicate_suppressed |
| AUXILIARY_ONLY | photocurrent | raw_data | `03_光电流/光电流响应` | 0.5 | 0.0 | `03_光电流/光电流响应/raw_data/第三次光电流补测/26041550465/光电流基线处理教程.pdf` | document_or_report_not_primary_data |
| EXCLUDE_INVALID | photocurrent | raw_data | `03_光电流/光电流响应` | 0.45 | 0.4 | `03_光电流/光电流响应/raw_data/第三次光电流补测/26041550465/备注.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | photocurrent | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第二次BOBC BC/26032562524/Photocurrent/1-(OCP).bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | photocurrent | raw_data | `03_光电流/光电流响应` | 0.45 | 0.85 | `03_光电流/光电流响应/raw_data/第二次BOBC BC/26032562524/Photocurrent/1-(OCP).txt` | exact_duplicate_suppressed |
| MANUAL_REVIEW | photocurrent | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第二次BOBC BC/26032562524/Photocurrent/2-(OCP).bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | photocurrent | raw_data | `03_光电流/光电流响应` | 0.45 | 0.85 | `03_光电流/光电流响应/raw_data/第二次BOBC BC/26032562524/Photocurrent/2-(OCP).txt` | exact_duplicate_suppressed |
| AUXILIARY_ONLY | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.35 | 0.0 | `03_光电流/光电流响应/raw_data/第二次BOBC BC/26032562524/光电流基线处理教程.pdf` | document_or_report_not_primary_data |
| EXCLUDE_INVALID | photocurrent_response | raw_data | `03_光电流/光电流响应` | 0.45 | 0.4 | `03_光电流/光电流响应/raw_data/第二次BOBC BC/26032562524/备注.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | photocurrent_response | document_or_report | `03_光电流/光电流响应/reports_notes` | 0.35 | 0.0 | `03_光电流/光电流响应/reports_notes/光电流基线处理教程.pdf` | document_or_report_not_primary_data |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC-2-1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC-2-1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC-2-1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC-2-1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC-2-2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC-2-2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC-2-2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC-2-2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC-2-3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC-2-3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC-2-3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC-2-3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20251126/BOBC/BOBC3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20251126/BOBC/BOBC3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-4000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-4500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-4500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-2-5000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO-2-5000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO-MT-YS1.xlsx` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/20251126/CWO` | 0.35 | 0.0 | `04_莫特肖特基/20251126/CWO/CWO3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/20251126/CWO` | 0.45 | 0.85 | `04_莫特肖特基/20251126/CWO/CWO3500.csv` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/origin_project/BOBC.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/origin_project/CWO新.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC4000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC4500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC4500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC5000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC5000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO1000废.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO1000废.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO3500-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO3500-2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO4000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO4500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO4500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.35 | 0.0 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO5000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/CWO5000.csv` | below_auto_process_threshold_or_ambiguous |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC2000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC2500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC3000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC3500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC4000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC4500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/BOBC5000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO1000废.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO1500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO2000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO2500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO3000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO3500-2.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO3500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO4000.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO4500.csv` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/20260121CWO+BOBC` | 0.45 | 0.85 | `04_莫特肖特基/20260121CWO+BOBC/raw_data/MT/CWO5000.csv` | exact_duplicate_suppressed |
| AUXILIARY_ONLY | Mott-Schottky | exported_figure | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/exported_figures/BOBCMOSE能带.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | Mott-Schottky | exported_figure | `04_莫特肖特基/BOBC` | 0.5 | 0.0 | `04_莫特肖特基/BOBC/exported_figures/BOBC莫特肖特基.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | Mott-Schottky | exported_figure | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/exported_figures/CWO+BOBC莫特.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/origin_project/bobc.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC3500 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC3500 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC4000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/BOBC/raw_data/BOBC4500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/BOBC/raw_data/BOBC4500.csv` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/origin_project/CWO MT-0.6.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/origin_project/CWO MT-2 +0.3.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO1000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO1500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO2000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO3000RE.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS1000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS1500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS2000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS2500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS3000.xlsx` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | Mott-Schottky | processed_table | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/李霖25年11月20日.pptx` | document_or_report_not_primary_data |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT1/CWO1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT1/CWO1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT1/CWO1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT1/CWO1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT1/CWO2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT1/CWO2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT1/CWO2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT1/CWO2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT1/CWO3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT1/CWO3000RE.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT2/CWO1500 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT2/CWO1500 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT2/CWO2000 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT2/CWO2000 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT2/CWO2500 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT2/CWO2500 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT2/CWO3000 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT2/CWO3000 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT2/CWO3500 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT2/CWO3500 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.35 | 0.0 | `04_莫特肖特基/CWO/raw_data/MT2/CWO3500 3.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/CWO` | 0.45 | 0.85 | `04_莫特肖特基/CWO/raw_data/MT2/CWO3500 3.csv` | below_auto_process_threshold_or_ambiguous |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/CWO1000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/CWO1500.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/CWO2000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/CWO3000RE.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/MS数据处理版/MS1000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/MS数据处理版/MS1500.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/MS数据处理版/MS2000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/MS数据处理版/MS2500.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/CWO莫特肖特基数据处理版` | 0.45 | 1.0 | `04_莫特肖特基/CWO莫特肖特基数据处理版/MS数据处理版/MS3000.xlsx` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LL/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/LL/BOBC/4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/LL/BOBC/4000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC1000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC1500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC2000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC3000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC4000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC5000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/BOBC6000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/MS1000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/MS2000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/MS4000 re2.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/MS4000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/MS4000RE.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LL/BOBC20251023` | 0.45 | 1.0 | `04_莫特肖特基/LL/BOBC20251023/MS5000.xlsx` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/LL/bobc数据处理版本` | 0.35 | 0.0 | `04_莫特肖特基/LL/bobc数据处理版本/origin_project/bobc.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/1000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/1500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/2000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/2500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/3000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/3500.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | processed_table | `04_莫特肖特基/LL/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/LL/bobc数据处理版本/processed_tables/4000.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/11MB EIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/11MB EIS.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/13MBEIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/13MBEIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/13MBEIS2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/13MBEIS2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/13MBEIS2.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1mbMT1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/1mbMT1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EIS | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.85 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/1mbMT1000.xlsx` | mild_folder_header_type_conflict |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1msEIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/1msEIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/1msEIS.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1MT1000-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/1MT1000-2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1MT2000-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/1MT2000-2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EIS | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.85 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/1MT2000-2.xlsx` | mild_folder_header_type_conflict |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1MT3000-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/1MT3000-2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/1MT3000-2.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1MT4000-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/1MT5000-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/3mbEIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/3mbEIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/3mbEIS.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/5MB EIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/5MB EIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 1.0 | `04_莫特肖特基/LLKT ms/20250905/5MB EIS.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/5MBEIS2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/5MBEIS2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/7BMEIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bm.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/LL/1bm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bm2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/LL/1bm2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt2000.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt3000.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt4000-2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt4000-2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.35 | 0.0 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms/20250905/LL` | 0.45 | 0.85 | `04_莫特肖特基/LLKT ms/20250905/LL/1bmmt4000.txt` | below_auto_process_threshold_or_ambiguous |
| EXCLUDE_INVALID | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/LLKT ms` | 0.45 | 0.25 | `04_莫特肖特基/LLKT ms/MOSE.TXT` | insufficient_numeric_table |
| AUXILIARY_ONLY | Mott-Schottky | exported_figure | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/exported_figures/MOSE模特肖特基.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/origin_project/ms.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS1000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS1000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS1500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS1500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS2000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS2000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS2500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS2500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS3000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS3000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500  2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500  2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500  3.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500  3.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500  4.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500  4.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500 5.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500 5.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS3500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS4000 2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS4000 2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS4000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS4000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS4500.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS4500.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.35 | 0.0 | `04_莫特肖特基/MoSe2MT/raw_data/MS5000.bin` | parser_probe_not_success |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/MoSe2MT` | 0.45 | 0.85 | `04_莫特肖特基/MoSe2MT/raw_data/MS5000.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/1000.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/1000.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/1500.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/1500.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/2000.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/2000.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/2500.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/2500.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/3000.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/3000.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/3500.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/3500.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | auxiliary_file | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/BOBC/4000.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_or_exported_numeric_table | `04_莫特肖特基/第一体系确定版本/BOBC` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/BOBC/4000.csv` | exact_duplicate_suppressed |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/origin_project/bobc.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/origin_project/bobc格式美化版本.opju` | origin_project_file_grouped_with_same_folder_data |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/1000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/1500.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/2000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/2500.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/3000.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/3500.xlsx` | exact_duplicate_suppressed |
| DUPLICATE_SUPPRESSED | Mott-Schottky | processed_table | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本` | 0.45 | 1.0 | `04_莫特肖特基/第一体系确定版本/bobc数据处理版本/processed_tables/4000.xlsx` | exact_duplicate_suppressed |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/origin_project/CWO MT-2 +0.3.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | Mott-Schottky | origin_project_reference | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/origin_project/CWO MT-2 +0.3数据美化版本.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO1500 2.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO1500 2.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO2000 2.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO2000 2.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO2500 2.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO2500 2.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO3000 2.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO3000 2.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO3500 2.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO3500 2.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.35 | 0.0 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO3500 3.bin` | parser_probe_not_success |
| DUPLICATE_SUPPRESSED | Mott-Schottky | raw_data | `04_莫特肖特基/第一体系确定版本/MT2` | 0.45 | 0.85 | `04_莫特肖特基/第一体系确定版本/MT2/raw_data/CWO3500 3.csv` | exact_duplicate_suppressed |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 0.5 | 0.0 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-1` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-1.txt` | high_confidence_valid_numeric_data |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-1.xlsx` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 0.5 | 0.0 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-2GOOD` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-2GOOD.txt` | high_confidence_valid_numeric_data |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-2GOOD.xlsx` | high_confidence_valid_numeric_data |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 0.6 | 0.25 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-2GOODZVIEW.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/BOBC` | 0.6 | 0.25 | `05_阻抗EIS/20251106阻抗李永进/BOBC/EIS-2GOOD拟合后.txt` | insufficient_numeric_table |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/CWO` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/CWO/EIS-1.txt` | high_confidence_valid_numeric_data |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/CWO` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/CWO/EIS-1.xlsx` | high_confidence_valid_numeric_data |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/CWO` | 0.6 | 0.25 | `05_阻抗EIS/20251106阻抗李永进/CWO/EIS-1ZVIEW.txt` | insufficient_numeric_table |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/CWO` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/CWO/EIS-2.txt` | high_confidence_valid_numeric_data |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/CWO` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/CWO/EIS-2.xlsx` | high_confidence_valid_numeric_data |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/CWO` | 0.6 | 0.25 | `05_阻抗EIS/20251106阻抗李永进/CWO/EIS-2ZVIEW.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20251106阻抗李永进/MOSE` | 0.5 | 0.0 | `05_阻抗EIS/20251106阻抗李永进/MOSE/EIS` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/MOSE` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/MOSE/EIS.txt` | high_confidence_valid_numeric_data |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/MOSE` | 1.0 | 1.0 | `05_阻抗EIS/20251106阻抗李永进/MOSE/EIS.xlsx` | high_confidence_valid_numeric_data |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/MOSE` | 0.45 | 0.25 | `05_阻抗EIS/20251106阻抗李永进/MOSE/EISZVIEW.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20251106阻抗李永进/MOSE` | 0.6 | 0.25 | `05_阻抗EIS/20251106阻抗李永进/MOSE/EIS拟合MS.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS` | 0.35 | 0.0 | `05_阻抗EIS/20251106阻抗李永进.zip` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-2-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-2-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-2-Z` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-2-Z.txt` | insufficient_numeric_table |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-E.xlsm` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B11-Z.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B3` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B3-Z` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B3-Z.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B3-Z.xlsm` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B3.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B7-A` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B7-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B7-Z` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-2-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-2-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-2-Z` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-2-Z.txt` | insufficient_numeric_table |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-E.xlsm` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/B9-Z.txt` | insufficient_numeric_table |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-2-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-2-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-2-Z` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-2-Z.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-2-Z.xlsm` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-Z` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/BOBC-Z.txt` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/CWO-A` | parser_probe_not_success |
| AUTO_PROCESS | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.85 | 1.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/CWO-A.txt` | high_confidence_valid_numeric_data |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/CWO-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/CWO-Z` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC` | 0.45 | 0.25 | `05_阻抗EIS/20260121 李永进阻抗 CWO+BOBC/CWO-Z.txt` | insufficient_numeric_table |
| AUXILIARY_ONLY | EIS | origin_project_reference | `05_阻抗EIS/20260202` | 0.5 | 0.0 | `05_阻抗EIS/20260202/origin_project/eis图20260202.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | EIS | origin_project_reference | `05_阻抗EIS/20260202` | 0.5 | 0.0 | `05_阻抗EIS/20260202/origin_project/eis图BOBC+CWO.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/b11-2-z.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b11-2-z.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b11-2-z.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/b11-z.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b11-z.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b11-z.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/b3.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b3.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b3.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/b7.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b7.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b7.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/b9-2z.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b9-2z.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b9-2z.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/b9-z.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b9-z.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/b9-z.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/bobc-z.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/bobc-z.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/bobc-z.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | raw_data | `05_阻抗EIS/20260202` | 0.35 | 0.0 | `05_阻抗EIS/20260202/raw_data/cwo-z.lst` | parser_probe_not_success |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/cwo-z.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/20260202` | 0.45 | 0.25 | `05_阻抗EIS/20260202/raw_data/cwo-z.z` | insufficient_numeric_table |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS` | 0.35 | 0.0 | `05_阻抗EIS/20260202.zip` | parser_probe_not_success |
| AUXILIARY_ONLY | EIS | origin_project_reference | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/origin_project/2eis图20260202.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/B11-2-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/B11-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/B7-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/B9-2-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/B9-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/BOBC-2-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/BOBC-2-Z.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/BOBC-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/BOBC-Z3.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | processed_table | `05_阻抗EIS/20260203李永进CWO+BOBC` | 0.35 | 0.0 | `05_阻抗EIS/20260203李永进CWO+BOBC/processed_tables/CWO-E.xlsm` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/308阻抗/BOBC/EIS` | 0.35 | 0.0 | `05_阻抗EIS/308阻抗/BOBC/EIS/BOBC.bin` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/308阻抗/BOBC/EIS` | 0.45 | 0.85 | `05_阻抗EIS/308阻抗/BOBC/EIS/BOBC.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/308阻抗/CWO/EIS` | 0.5 | 0.0 | `05_阻抗EIS/308阻抗/CWO/EIS/CWO EIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/308阻抗/CWO/EIS` | 0.6 | 0.85 | `05_阻抗EIS/308阻抗/CWO/EIS/CWO EIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/308阻抗/CWO/EIS` | 0.35 | 0.0 | `05_阻抗EIS/308阻抗/CWO/EIS/CWOEIS2.bin` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/308阻抗/CWO/EIS` | 0.45 | 0.85 | `05_阻抗EIS/308阻抗/CWO/EIS/CWOEIS2.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS/308阻抗/MS` | 0.5 | 0.0 | `05_阻抗EIS/308阻抗/MS/MS EIS.bin` | parser_probe_not_success |
| MANUAL_REVIEW | EIS | raw_or_exported_numeric_table | `05_阻抗EIS/308阻抗/MS` | 0.6 | 0.85 | `05_阻抗EIS/308阻抗/MS/MS EIS.csv` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EIS | auxiliary_file | `05_阻抗EIS` | 0.35 | 0.0 | `05_阻抗EIS/308阻抗.zip` | parser_probe_not_success |
| AUXILIARY_ONLY | EIS | exported_figure | `05_阻抗EIS/BM重新拟合版本` | 0.35 | 0.0 | `05_阻抗EIS/BM重新拟合版本/exported_figures/BM阻抗.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | EIS | origin_project_reference | `05_阻抗EIS/BM重新拟合版本` | 0.35 | 0.0 | `05_阻抗EIS/BM重新拟合版本/origin_project/BM.opju` | origin_project_file_grouped_with_same_folder_data |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/1.TXT` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/3.TXT` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/5.TXT` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/7.TXT` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/9.TXT` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/bm1.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/bm3.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/bm5z.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/bm7.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/bm9.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/bobc.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/BM重新拟合版本` | 0.45 | 0.25 | `05_阻抗EIS/BM重新拟合版本/raw_data/MOSE2.TXT` | insufficient_numeric_table |
| AUXILIARY_ONLY | EIS | exported_figure | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.5 | 0.0 | `05_阻抗EIS/EIS-20251025拟合后师妹/exported_figures/LL-EIS-BM-X.png` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | EIS | origin_project_reference | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.35 | 0.0 | `05_阻抗EIS/EIS-20251025拟合后师妹/origin_project/BM-X.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | EIS | origin_project_reference | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.35 | 0.0 | `05_阻抗EIS/EIS-20251025拟合后师妹/origin_project/拟合后BM-X.opju` | origin_project_file_grouped_with_same_folder_data |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/1.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/3.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/5.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/7.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/9.txt` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/bm1.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/bm3.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/bm5z.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/bm7.z` | insufficient_numeric_table |
| EXCLUDE_INVALID | EIS | raw_data | `05_阻抗EIS/EIS-20251025拟合后师妹` | 0.45 | 0.25 | `05_阻抗EIS/EIS-20251025拟合后师妹/raw_data/bm9.z` | insufficient_numeric_table |
| AUXILIARY_ONLY | EIS | exported_figure | `05_阻抗EIS` | 0.35 | 0.0 | `05_阻抗EIS/阻抗图.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | FTIR | exported_figure | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/exported_figures/BOBC+MS-FTRIR.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | FTIR | origin_project_reference | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/origin_project/BOBC+MS.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/LL-BM1.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/LL-BM3.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/LL-BM5.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/LL-BM7.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/LL-BM9.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM1.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM1.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM3.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM3.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM5.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM5.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM7.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM7.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM9.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BM9.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BOBC.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/BOBC+MS 以前水热的Mose` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/raw_data/李永进组版本/BOBC.0.dpt` | parser_probe_not_success |
| AUXILIARY_ONLY | FTIR | document_or_report | `06_红外/BOBC+MS 以前水热的Mose/reports_notes` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/reports_notes/LL-BM1.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | FTIR | document_or_report | `06_红外/BOBC+MS 以前水热的Mose/reports_notes` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/reports_notes/LL-BM3.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | FTIR | document_or_report | `06_红外/BOBC+MS 以前水热的Mose/reports_notes` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/reports_notes/LL-BM5.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | FTIR | document_or_report | `06_红外/BOBC+MS 以前水热的Mose/reports_notes` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/reports_notes/LL-BM7.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | FTIR | document_or_report | `06_红外/BOBC+MS 以前水热的Mose/reports_notes` | 0.35 | 0.0 | `06_红外/BOBC+MS 以前水热的Mose/reports_notes/LL-BM9.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | FTIR | exported_figure | `06_红外/cwo+bobc` | 0.5 | 0.0 | `06_红外/cwo+bobc/exported_figures/CWO+BOBC FTIR 2026018新制备.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | FTIR | exported_figure | `06_红外/cwo+bobc` | 0.5 | 0.0 | `06_红外/cwo+bobc/exported_figures/CWO+BOBC FTIR.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | FTIR | exported_figure | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/exported_figures/FTIR2.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | FTIR | exported_figure | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/exported_figures/hongwai.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | FTIR | origin_project_reference | `06_红外/cwo+bobc` | 0.5 | 0.0 | `06_红外/cwo+bobc/origin_project/CWO+BOBC红外.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/BOBC.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/CWO 15.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/CWO 15.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/cwo 20260128 李永进组/BC-10 环己烷.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/cwo 20260128 李永进组/BC-10.0环己烷.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/CWO.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/cwo+bobc` | 0.35 | 0.0 | `06_红外/cwo+bobc/raw_data/CWO.0.dpt` | parser_probe_not_success |
| AUXILIARY_ONLY | FTIR | origin_project_reference | `06_红外/红外MS+BPO 暑期版本` | 0.5 | 0.0 | `06_红外/红外MS+BPO 暑期版本/origin_project/红外.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/红外MS+BPO 暑期版本` | 0.35 | 0.0 | `06_红外/红外MS+BPO 暑期版本/raw_data/20250715-1/3.bpo.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/红外MS+BPO 暑期版本` | 0.35 | 0.0 | `06_红外/红外MS+BPO 暑期版本/raw_data/20250715-1/3.bpo.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/红外MS+BPO 暑期版本` | 0.35 | 0.0 | `06_红外/红外MS+BPO 暑期版本/raw_data/20250715-1/4.ms-bpo.0.dpt` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/红外MS+BPO 暑期版本` | 0.35 | 0.0 | `06_红外/红外MS+BPO 暑期版本/raw_data/20250715-1/4.msF-bpo.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/红外MS+BPO 暑期版本` | 0.35 | 0.0 | `06_红外/红外MS+BPO 暑期版本/raw_data/20250715-1/5.ms.0` | parser_probe_not_success |
| MANUAL_REVIEW | FTIR | raw_data | `06_红外/红外MS+BPO 暑期版本` | 0.35 | 0.0 | `06_红外/红外MS+BPO 暑期版本/raw_data/20250715-1/5.ms.0.dpt` | parser_probe_not_success |
| AUXILIARY_ONLY | Raman | exported_figure | `07_拉曼/20251021` | 0.35 | 0.0 | `07_拉曼/20251021/exported_figures/ranman.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | Raman | origin_project_reference | `07_拉曼/20251021` | 0.35 | 0.0 | `07_拉曼/20251021/origin_project/bobc+ms.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/20251021` | 0.45 | 0.85 | `07_拉曼/20251021/raw_data/BOBC.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/20251021` | 0.45 | 0.85 | `07_拉曼/20251021/raw_data/BOBCMS9.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/20251021` | 0.45 | 0.85 | `07_拉曼/20251021/raw_data/MOSE2_6.txt` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | Raman | origin_project_reference | `07_拉曼` | 0.5 | 0.0 | `07_拉曼/origin_project/cwo+bobc raman.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/BOBC2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/CWO+BOBC+2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/CWO+BOBC+3.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/CWO+BOBC.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/CWO_1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/MoTe2_1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/MoTe2_2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/MoTe2_3.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/20251027/WYT/MoTe2_5.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.35 | 0.0 | `07_拉曼/raw_data/BC-30/bc30_1.l6s` | parser_probe_not_success |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/BC-30/bc30_1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/BC-30/bc30_3 2 50-2000.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/BC-30/bc30_3 2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/BC-30/bc30_5 500-2000.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼` | 0.45 | 0.85 | `07_拉曼/raw_data/bc30 HUANG_1 100-2000.txt` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | Raman | exported_figure | `07_拉曼/老版本BOBC+MS+BPO` | 0.5 | 0.0 | `07_拉曼/老版本BOBC+MS+BPO/exported_figures/BOBC+MS-RAMAN.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | Raman | origin_project_reference | `07_拉曼/老版本BOBC+MS+BPO` | 0.35 | 0.0 | `07_拉曼/老版本BOBC+MS+BPO/origin_project/BOBC+MS+BPO.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | Raman | origin_project_reference | `07_拉曼/老版本BOBC+MS+BPO` | 0.35 | 0.0 | `07_拉曼/老版本BOBC+MS+BPO/origin_project/BOBC+MS.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BM1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BM2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BM3.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BOBC1.txt` | below_auto_process_threshold_or_ambiguous |
| DUPLICATE_SUPPRESSED | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BOBC2.txt` | exact_duplicate_suppressed |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPO1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPO2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPO3.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPOM1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPOM2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPOM3.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/BPOM4.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/MS1.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/MS2.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | Raman | raw_data | `07_拉曼/老版本BOBC+MS+BPO` | 0.45 | 0.85 | `07_拉曼/老版本BOBC+MS+BPO/raw_data/MS3.txt` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | UV-vis DRS | exported_figure | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/exported_figures/CWO+BOBC紫外.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | UV-vis DRS | exported_figure | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/exported_figures/CWO+BOBC紫外tacu.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | UV-vis DRS | exported_figure | `08_固体紫外` | 0.5 | 0.0 | `08_固体紫外/exported_figures/MS+BOBC固体紫外200-800.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | UV-vis DRS | exported_figure | `08_固体紫外` | 0.5 | 0.0 | `08_固体紫外/exported_figures/MS+BOBC固体紫外260-800.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | UV-vis DRS | exported_figure | `08_固体紫外` | 0.5 | 0.0 | `08_固体紫外/exported_figures/MS+BOBC固体紫外tacu.tif` | plot_image_not_raw_numeric_data |
| AUXILIARY_ONLY | UV-vis DRS | origin_project_reference | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/origin_project/BOBC+MS.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/20251017/bobc.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/20251017/bobc.UDS` | parser_probe_not_success |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/20251017/bobcms.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/20251017/bobcms.UDS` | parser_probe_not_success |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/20251017/cwo.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/20251017/cwo.UDS` | parser_probe_not_success |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/20251017/cwobobc.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/20251017/cwobobc.UDS` | parser_probe_not_success |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/20251017/ms.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/20251017/ms.UDS` | parser_probe_not_success |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/BOBC CWO10%(bc10%环己烷)/bc10-2.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/BOBC CWO10%(bc10%环己烷)/bc10-2.UDS` | parser_probe_not_success |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.45 | 0.85 | `08_固体紫外/raw_data/20251017-LL/BOBC CWO10%(bc10%环己烷)/bc10.TXT` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | UV-vis DRS | raw_data | `08_固体紫外` | 0.35 | 0.0 | `08_固体紫外/raw_data/20251017-LL/BOBC CWO10%(bc10%环己烷)/bc10.UDS` | parser_probe_not_success |
| AUXILIARY_ONLY | UV-vis DRS | origin_project_reference | `08_固体紫外/固体紫外CWO+BOBC` | 0.35 | 0.0 | `08_固体紫外/固体紫外CWO+BOBC/origin_project/BOBC+CWO.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | BET | origin_project_reference | `09_BET/XWM-LL-260428-1-BOBC-All Pore` | 0.35 | 0.0 | `09_BET/XWM-LL-260428-1-BOBC-All Pore/origin_project/BOBC.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | BET | processed_table | `09_BET/XWM-LL-260428-1-BOBC-All Pore` | 0.35 | 0.0 | `09_BET/XWM-LL-260428-1-BOBC-All Pore/processed_tables/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | processed_table | `09_BET/XWM-LL-260428-1-BOBC-All Pore` | 0.35 | 0.0 | `09_BET/XWM-LL-260428-1-BOBC-All Pore/processed_tables/MICDIR.DB3-journal` | empty_file |
| MANUAL_REVIEW | BET | processed_table | `09_BET/XWM-LL-260428-1-BOBC-All Pore` | 0.45 | 0.0 | `09_BET/XWM-LL-260428-1-BOBC-All Pore/processed_tables/XWM-LL-260428-1-BOBC-All Pore.XLS` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/XWM-LL-260428-1-BOBC-All Pore` | 0.35 | 0.0 | `09_BET/XWM-LL-260428-1-BOBC-All Pore/raw_data/XWM-LL-260428-1-BOBC-All Pore.SMP` | parser_probe_not_success |
| AUXILIARY_ONLY | BET | document_or_report | `09_BET/XWM-LL-260428-1-BOBC-All Pore/reports_notes` | 0.45 | 0.0 | `09_BET/XWM-LL-260428-1-BOBC-All Pore/reports_notes/XWM-LL-260428-1-BOBC-All Pore.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-4-BOBC-BET` | 0.35 | 0.0 | `09_BET/ZPF-LL-20260327-4-BOBC-BET/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-4-BOBC-BET` | 0.35 | 0.0 | `09_BET/ZPF-LL-20260327-4-BOBC-BET/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | document_or_report | `09_BET/ZPF-LL-20260327-4-BOBC-BET` | 0.6 | 0.0 | `09_BET/ZPF-LL-20260327-4-BOBC-BET/ZPF-LL-20260327-4-BOBC-BET.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-4-BOBC-BET` | 0.5 | 0.0 | `09_BET/ZPF-LL-20260327-4-BOBC-BET/ZPF-LL-20260327-4-BOBC-BET.SMP` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_or_exported_numeric_table | `09_BET/ZPF-LL-20260327-4-BOBC-BET` | 0.6 | 0.0 | `09_BET/ZPF-LL-20260327-4-BOBC-BET/ZPF-LL-20260327-4-BOBC-BET.XLS` | parser_probe_not_success |
| MANUAL_REVIEW | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-7-CWO-BET` | 0.35 | 0.0 | `09_BET/ZPF-LL-20260327-7-CWO-BET/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-7-CWO-BET` | 0.35 | 0.0 | `09_BET/ZPF-LL-20260327-7-CWO-BET/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | document_or_report | `09_BET/ZPF-LL-20260327-7-CWO-BET` | 0.6 | 0.0 | `09_BET/ZPF-LL-20260327-7-CWO-BET/ZPF-LL-20260327-7-CWO-BET.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | raw_or_exported_numeric_table | `09_BET/ZPF-LL-20260327-7-CWO-BET` | 0.6 | 0.0 | `09_BET/ZPF-LL-20260327-7-CWO-BET/ZPF-LL-20260327-7-CWO-BET.XLS` | parser_probe_not_success |
| MANUAL_REVIEW | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-8-BC-BET` | 0.35 | 0.0 | `09_BET/ZPF-LL-20260327-8-BC-BET/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | auxiliary_file | `09_BET/ZPF-LL-20260327-8-BC-BET` | 0.35 | 0.0 | `09_BET/ZPF-LL-20260327-8-BC-BET/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | document_or_report | `09_BET/ZPF-LL-20260327-8-BC-BET` | 0.6 | 0.0 | `09_BET/ZPF-LL-20260327-8-BC-BET/ZPF-LL-20260327-8-CWO-BET.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | raw_or_exported_numeric_table | `09_BET/ZPF-LL-20260327-8-BC-BET` | 0.6 | 0.0 | `09_BET/ZPF-LL-20260327-8-BC-BET/ZPF-LL-20260327-8-CWO-BET.XLS` | parser_probe_not_success |
| AUXILIARY_ONLY | BET | origin_project_reference | `09_BET/氮气吸附脱附等温曲线` | 0.5 | 0.0 | `09_BET/氮气吸附脱附等温曲线/origin_project/BET -BOBC为负数.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/MICDIR.DB3-journal` | empty_file |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-1-BOBC-All Pore/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-1-BOBC-All Pore/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-1-BOBC-All Pore/XWM-LL-260421-1-BOBC-All Pore.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-1-BOBC-All Pore/XWM-LL-260421-1-BOBC-All Pore.SMP` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-1-BOBC-All Pore/XWM-LL-260421-1-BOBC-All Pore.XLS` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-2-CWO-All Pore/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-2-CWO-All Pore/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-2-CWO-All Pore/XWM-LL-260421-2-CWO-All Pore.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-2-CWO-All Pore/XWM-LL-260421-2-CWO-All Pore.SMP` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-2-CWO-All Pore/XWM-LL-260421-2-CWO-All Pore.XLS` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-3-BiCu-All Pore/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-3-BiCu-All Pore/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-3-BiCu-All Pore/XWM-LL-260421-3-BiCu-All Pore.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-3-BiCu-All Pore/XWM-LL-260421-3-BiCu-All Pore.SMP` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-3-BiCu-All Pore/XWM-LL-260421-3-BiCu-All Pore.XLS` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-4-BOBC-4-XIN-All Pore/MICDIR.DB3` | parser_probe_not_success |
| EXCLUDE_INVALID | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-4-BOBC-4-XIN-All Pore/MICDIR.DB3-journal` | empty_file |
| AUXILIARY_ONLY | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-4-BOBC-4-XIN-All Pore/XWM-LL-260421-4-BOBC-4-XIN-All Pore.PDF` | document_or_report_not_primary_data |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.35 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-4-BOBC-4-XIN-All Pore/XWM-LL-260421-4-BOBC-4-XIN-All Pore.SMP` | parser_probe_not_success |
| MANUAL_REVIEW | BET | raw_data | `09_BET/氮气吸附脱附等温曲线` | 0.45 | 0.0 | `09_BET/氮气吸附脱附等温曲线/raw_data/20260421/XWM-LL-260421-4-BOBC-4-XIN-All Pore/XWM-LL-260421-4-BOBC-4-XIN-All Pore.XLS` | parser_probe_not_success |
| AUXILIARY_ONLY | EPR | origin_project_reference | `10_EPR_PL/EPR` | 0.5 | 0.0 | `10_EPR_PL/EPR/origin_project/epr.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_archives/20260430-1.zip` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-O3-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-O3-light1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-O3-light2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-O3-light3` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-O3-light4` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-O3-light5` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-OH-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-OH-dark2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-OH-light1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-OH-light2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BC-OH-light3` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-O3-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-O3-dark-none` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-O3-light1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-O3-light2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-O3-light3` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-OH-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/BOBC-OH-light1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/CWO-O3-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/CWO-O3-dark-none` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/CWO-O3-light1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/CWO-OH-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/CWO-OH-light1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260410-3/CWO-OH-light2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/10%-O2-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/10%-O2-light-1` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/10%-O2-light-2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/10%-OH-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/10%-OH-light` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/6.7%-O2-light` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/6.7%-O2-light-2` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/6.7%-OH-dark` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260421/6.7%-OH-light` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/1-O3-light-1min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/1-O3-light-2min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/1-O3-light-3min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/1-OH-light-1min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/1-OH-light-2min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/3-O3-light-1min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/3-O3-light-2min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/3-O3-light-3min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/3-OH-light-1min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/3-OH-light-2min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.35 | 0.0 | `10_EPR_PL/EPR/raw_data/20260430-1/20260430-1/3-OH-light-3min` | parser_probe_not_success |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BC-O3-dark.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BC-O3-light5.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BC-OH-dark.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BC-OH-light2.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BOBC-O3-dark.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BOBC-O3-light1.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BOBC-O3-light2.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BOBC-O3-light3.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/BOBC-OH-light1.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/CWO-O3-dark.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/CWO-O3-light1.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/CWO-OH-dark.xlsx` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | EPR | raw_data | `10_EPR_PL/EPR` | 0.45 | 0.85 | `10_EPR_PL/EPR/raw_data/导出后的数据/CWO-OH-light2.xlsx` | below_auto_process_threshold_or_ambiguous |
| AUXILIARY_ONLY | PL | origin_project_reference | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/origin_project/激发谱发射谱.opju` | origin_project_file_grouped_with_same_folder_data |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_archives/3176_1775399174649_26032574877.zip` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EM-ex340nm.FS` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.45 | 0.85 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EM-ex340nm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EM-ex340nm.wmf` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EX-em640nm.FS` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.45 | 0.85 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EX-em640nm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EX-em640nm.wmf` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EM-ex340nm.FS` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.45 | 0.85 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EM-ex340nm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EM-ex340nm.wmf` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EX-em445nm.FS` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.45 | 0.85 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EX-em445nm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EX-em445nm.wmf` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EM-ex340nm.FS` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.45 | 0.85 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EM-ex340nm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EM-ex340nm.wmf` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EX-em630nm.FS` | parser_probe_not_success |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.45 | 0.85 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EX-em630nm.txt` | below_auto_process_threshold_or_ambiguous |
| MANUAL_REVIEW | PL | raw_data | `10_EPR_PL/PL` | 0.35 | 0.0 | `10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EX-em630nm.wmf` | parser_probe_not_success |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选/CL` | 0.0 | 0.0 | `11_光反应条件筛选/CL/origin_project/催化剂筛选.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选/CL` | 0.0 | 0.0 | `11_光反应条件筛选/CL/origin_project/循环实验.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选/CL` | 0.0 | 0.0 | `11_光反应条件筛选/CL/origin_project/溶剂筛选.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选/CL` | 0.0 | 0.0 | `11_光反应条件筛选/CL/origin_project/自由基猝灭.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选` | 0.0 | 0.0 | `11_光反应条件筛选/origin_project/溶剂筛选.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选` | 0.0 | 0.0 | `11_光反应条件筛选/origin_project/自由基捕获.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选/标曲` | 0.0 | 0.0 | `11_光反应条件筛选/标曲/origin_project/BBAD1.opju` | origin_project_file_grouped_with_same_folder_data |
| AUXILIARY_ONLY | unknown | origin_project_reference | `11_光反应条件筛选/标曲` | 0.0 | 0.0 | `11_光反应条件筛选/标曲/origin_project/BZA2.opju` | origin_project_file_grouped_with_same_folder_data |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/BIOBRCL` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/BIOBRCL/3-1.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/BIOBRCL` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/BIOBRCL/3-2.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/BIOBRCL` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/BIOBRCL/3-3.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/BIOBRCL` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/BIOBRCL/3-4.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/BIOBRCL` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/BIOBRCL/3-5.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO/1001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO/1002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO/1003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO/1004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO/1005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO/1006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1013.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1014.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1015.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1016.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/CWO-BOBC` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/1017.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | document_or_report | `12_显微_SEM_TEM/SEM/CWO-BOBC/EDS` | 0.35 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/EDS/LL-1.docx` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | document_or_report | `12_显微_SEM_TEM/SEM/CWO-BOBC/EDS` | 0.35 | 0.0 | `12_显微_SEM_TEM/SEM/CWO-BOBC/EDS/LL.docx` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1013.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1014.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1015.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1016.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1017.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1018.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1019.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1020.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20250721SEN` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20250721SEN/1021.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun013.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun014.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun015.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun016.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun017.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun018.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun019.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun020.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun021.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/bobc` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/bobc/10wt_shui_yichun022.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun023.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun024.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun025.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun026.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun027.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun028.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun029.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun030.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun031.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun032.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun033.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun034.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun035.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/ll20260126/fh` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126/fh/10wt_shui_yichun036.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | document_or_report | `12_显微_SEM_TEM/SEM/ll20260126-eds` | 0.35 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126-eds/~$ 1_区 1_2026-01-26_10-04-27.docx` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | document_or_report | `12_显微_SEM_TEM/SEM/ll20260126-eds` | 0.35 | 0.0 | `12_显微_SEM_TEM/SEM/ll20260126-eds/项目 1_区 1_2026-01-26_10-04-27.docx` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/LL20260429SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/LL20260429SEM/1013.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法3/MS_3013.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | document_or_report | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.35 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/0416HOU.docx` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | document_or_report | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.35 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/0416HOU.pdf` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法4/MS_4011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5010.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5011.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5013.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5014.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5015.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/MOSE2/MS方法5/MS_5016.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/FUHE` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/FUHE/300.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/FUHE` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/FUHE/301.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/FUHE001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/FUHE002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/FUHE003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/FUHE008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/FUHE009.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2001.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2002.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2003.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2004.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2005.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2006.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2007.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2008.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2012.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2014.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2015.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2017.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2021.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2022.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/LL20241113SEM/TiO2023.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/TIO2` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/TIO2/302.tif` | deferred_scan_only |
| DEFERRED_TYPE | SEM_image_data | exported_figure | `12_显微_SEM_TEM/SEM/师姐电镜/TIO2` | 0.45 | 0.0 | `12_显微_SEM_TEM/SEM/师姐电镜/TIO2/303.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0001 - BC Camera 36000 x Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0001 - BC Camera 36000 x Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0002 - BC Camera 630 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0002 - BC Camera 630 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0003 - BC Camera 630 kx Ceta B DCFI(Ceta).tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0003 - BC Camera 630 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0003 - BC Camera 630 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0004 - BC Camera 630 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0004 - BC Camera 630 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0005 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0005 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0006 - BC Camera 46000 x Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0006 - BC Camera 46000 x Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0007 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0007 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0008 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0008 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0009 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0009 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0010 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0010 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0011 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0011 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0012 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0012 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0013 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0013 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0014 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0014 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0015 - BC Camera 74000 x Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0015 - BC Camera 74000 x Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0016 - BC Camera 74000 x Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0016 - BC Camera 74000 x Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0017 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0017 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0018 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0018 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0019 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0019 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0019 0.2845nm .tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0020 - BC Camera 58000 x Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0020 - BC Camera 58000 x Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0021 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0021 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0022 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0022 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0023 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0023 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0024 - BC Camera 820 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0024 - BC Camera 820 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0025 - BC Camera 120 kx Ceta Ceta.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/0025 - BC Camera 120 kx Ceta.emd` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/24 0.272 0.33-2.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/24 0.272 0.33.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/24 0.272.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/24 0.272NM.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-0.4-CWO-0.204.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-0.282-0.204.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-BOBC 0.292.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-BOBC-0.282-2.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-BOBC-0.282.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-BOBC-0.284.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-BOBC-0.286-3.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-BOBC-0.286.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/BC-04-CWO-0.204-2.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/C19 0.2845.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/c24 0.33nm.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/HRTEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/Profile Of BC-04-BOBC-0.286.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/HRTEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/HRTEM/Thumbs.db` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | auxiliary_file | `12_显微_SEM_TEM/TEM/TEM` | 0.35 | 0.0 | `12_显微_SEM_TEM/TEM/TEM/#20260326.mdb` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/TEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/TEM/Img8713.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/TEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/TEM/Img8714.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/TEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/TEM/Img8715.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/TEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/TEM/Img8716.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM/TEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/TEM/Img8717.tif` | deferred_scan_only |
| DEFERRED_TYPE | TEM_image_data | exported_figure | `12_显微_SEM_TEM/TEM` | 0.45 | 0.0 | `12_显微_SEM_TEM/TEM/TEM文献晶格图/BOBC+TIO2.png` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/acqu` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/acqus` | deferred_scan_only |
| DEFERRED_TYPE | NMR | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.45 | 0.25 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/audita.txt` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/fid` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/format.temp` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/fq1list` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/1i` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/1r` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.45 | 0.25 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/auditp.txt` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/intrng` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/outd` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.45 | 0.25 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/parm.txt` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/peaklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/peakrng` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/peaks` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/proc` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/procs` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pdata/1/title` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/prosol_History` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/pulseprogram` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/scon2` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/shimvalues` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/specpar` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/uxnmr.info` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-1/10/uxnmr.par` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/acqu` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/acqus` | deferred_scan_only |
| DEFERRED_TYPE | NMR | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.45 | 0.25 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/audita.txt` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/fid` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/format.temp` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/fq1list` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/1i` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/1r` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.45 | 0.25 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/auditp.txt` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/intrng` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/outd` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.45 | 0.25 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/parm.txt` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/peaklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/peakrng` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/peaks` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/proc` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/procs` | deferred_scan_only |
| DEFERRED_TYPE | NMR | processed_table | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pdata/1/title` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/prosol_History` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/pulseprogram` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/scon2` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/shimvalues` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/specpar` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/uxnmr.info` | deferred_scan_only |
| DEFERRED_TYPE | NMR | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/核磁/ZPF-LL-1125-2/10/uxnmr.par` | deferred_scan_only |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/11%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/5%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/7%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/9%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹/15%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹/20%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹/3%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹/5%.pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | HPLC/LC exported data | document_or_report | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/液相/新建文件夹/80%.pdf` | document_or_report_not_primary_data |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/1.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/2.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/2CH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/2CH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/3CH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/3CH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4BR.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4BR.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4CH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4CH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4CL.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4cl.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/4OCH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/KANG.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/KANG1.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/KANG2.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/LM.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/LM405.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/N8h.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/N8h.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/OCH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/S8h.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/S8h.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/SHUDINGJI.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/SHUDINGJI.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/AcqMethod.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/BinPump1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/BinPump1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/Contents.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/DefaultMassCal.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/DeviceConfigInfo.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/Devices.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/191_1.stg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/BinPump_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/BinPump_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/DaMethod/Qual/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/DaMethod/Qual/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/DaMethod/Qual/qualitative.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/DaMethod/Quant/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/DaMethod/Quant/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/HiP-ALS_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/HiP-ALS_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/HiP-ALS_1_Pretreatment.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/TCC_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/JYH.m/TCC_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSActualDefs.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSMassCal.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSPeriodicActuals.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSProfile.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSScan.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSScan.xsd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/MSTS.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/sample_info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/TCC1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/TCC1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/AcqData/Worklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+2CH3.d/desktop.ini` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/AcqMethod.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/BinPump1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/BinPump1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/Contents.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/DefaultMassCal.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/DeviceConfigInfo.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/Devices.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/191_1.stg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/BinPump_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/BinPump_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/DaMethod/Qual/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/DaMethod/Qual/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/DaMethod/Qual/qualitative.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/DaMethod/Quant/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/DaMethod/Quant/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/HiP-ALS_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/HiP-ALS_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/HiP-ALS_1_Pretreatment.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/TCC_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/JYH.m/TCC_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSActualDefs.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSMassCal.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSPeriodicActuals.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSProfile.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSScan.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSScan.xsd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/MSTS.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/sample_info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/TCC1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/TCC1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/AcqData/Worklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+3CH3.d/desktop.ini` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/AcqMethod.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/BinPump1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/BinPump1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/Contents.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/DefaultMassCal.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/DeviceConfigInfo.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/Devices.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/191_1.stg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/BinPump_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/BinPump_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/DaMethod/Qual/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/DaMethod/Qual/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/DaMethod/Qual/qualitative.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/DaMethod/Quant/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/DaMethod/Quant/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/HiP-ALS_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/HiP-ALS_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/HiP-ALS_1_Pretreatment.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/TCC_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/JYH.m/TCC_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSActualDefs.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSMassCal.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSPeriodicActuals.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSProfile.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSScan.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSScan.xsd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/MSTS.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/sample_info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/TCC1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/TCC1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/AcqData/Worklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4BR3.d/desktop.ini` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/AcqMethod.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/BinPump1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/BinPump1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/Contents.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/DefaultMassCal.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/DeviceConfigInfo.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/Devices.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/191_1.stg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/BinPump_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/BinPump_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/DaMethod/Qual/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/DaMethod/Qual/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/DaMethod/Qual/qualitative.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/DaMethod/Quant/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/DaMethod/Quant/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/HiP-ALS_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/HiP-ALS_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/HiP-ALS_1_Pretreatment.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/TCC_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/JYH.m/TCC_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSActualDefs.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSMassCal.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSPeriodicActuals.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSProfile.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSScan.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSScan.xsd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/MSTS.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/sample_info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/TCC1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/TCC1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/AcqData/Worklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CH3.d/desktop.ini` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/AcqMethod.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/BinPump1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/BinPump1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/Contents.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/DefaultMassCal.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/DeviceConfigInfo.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/Devices.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/191_1.stg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/BinPump_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/BinPump_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/DaMethod/Qual/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/DaMethod/Qual/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/DaMethod/Qual/qualitative.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/DaMethod/Quant/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/DaMethod/Quant/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/HiP-ALS_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/HiP-ALS_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/HiP-ALS_1_Pretreatment.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/TCC_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/JYH.m/TCC_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSActualDefs.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSMassCal.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSPeriodicActuals.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSProfile.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSScan.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSScan.xsd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/MSTS.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/sample_info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/TCC1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/TCC1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/AcqData/Worklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4CL.d/desktop.ini` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/AcqMethod.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/BinPump1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/BinPump1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/Contents.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/DefaultMassCal.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/DeviceConfigInfo.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/Devices.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/191_1.stg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/BinPump_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/BinPump_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/DaMethod/Qual/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/DaMethod/Qual/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/DaMethod/Qual/qualitative.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/DaMethod/Quant/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/DaMethod/Quant/method.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/HiP-ALS_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/HiP-ALS_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/HiP-ALS_1_Pretreatment.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/TCC_1.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/JYH.m/TCC_1_MethodMetaData.XML` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSActualDefs.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSMassCal.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSPeriodicActuals.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSProfile.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSScan.bin` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSScan.xsd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/MSTS.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/sample_info.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/TCC1.cd` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/TCC1.cg` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/AcqData/Worklist.xml` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260316+4OCH3.d/desktop.ini` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/2CH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/2CH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/3CH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/3CH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4BR.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4BR.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4CH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4CH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4CL.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4cl.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/4OCH3.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_data | `13_反应产物分析_液相_质谱_核磁/质谱` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/底物拓展原文件/20260317-LL 2+3+4甲基，4CL、BR、甲氧基/OCH3.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基/KANG.xps` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基/KANG1.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | raw_or_exported_numeric_table | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基` | 0.45 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基/SHUDINGJI.xls` | deferred_scan_only |
| DEFERRED_TYPE | MS | auxiliary_file | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基` | 0.35 | 0.0 | `13_反应产物分析_液相_质谱_核磁/质谱/糠胺叔丁基/SHUDINGJI.xps` | deferred_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/COFIn2S3 S 型光催化剂具有增强的光吸收和 H2O2 生成活性以及 fs-TA 研究.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/S 型 g-C3N4CdS 异质结构接枝单个 Pd 原子以实现超快电荷传输和高效可见光驱动的 H2 演化.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/S型量子点异质结光催化剂：组装类型、机理见解和设计策略.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学/yue` | 0.45 | 0.0 | `14_动力学/动力学/yue/Advanced Materials - 2024 - Gu - Unveiling Charge Carrier Dynamics at Organic Inorganic S‐Scheme Heterojunction Interfaces .pdf` | reference_literature_scan_only |
| AUXILIARY_ONLY | EPR | document_or_report | `14_动力学/动力学/yue/EPR` | 0.35 | 0.0 | `14_动力学/动力学/yue/EPR/SI Advanced Materials - 2024 - Gu - Unveiling Charge Carrier Dynamics at Organic Inorganic S‐Scheme Heterojunction Interfaces .pdf` | document_or_report_not_primary_data |
| AUXILIARY_ONLY | EPR | document_or_report | `14_动力学/动力学/yue/EPR` | 0.5 | 0.0 | `14_动力学/动力学/yue/EPR/使用高级 EPR 探索 S 型异质结界面的电荷转移动力学.pdf` | document_or_report_not_primary_data |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学/yue/KPFM` | 0.45 | 0.0 | `14_动力学/动力学/yue/KPFM/SI K.docx` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学/yue/KPFM` | 0.45 | 0.0 | `14_动力学/动力学/yue/KPFM/开尔文探针力显微镜揭示了 CdSBiOBr S 型异质结光催化剂中的空间分辨电荷转移机制.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学/yue` | 0.6 | 0.0 | `14_动力学/动力学/yue/S 型光催化剂中的电荷转移动力学.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/从CdS量子点到原子分散Pt的超快电子转移用于增强H2演化和增值化学合成.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/双功能 g-C3N4 纳米球CdZnS QDs S 型光催化剂，具有增强的 H2 析出和糠醛合成机制.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/双功能 TiO2COF S 型光催化剂具有增强的 H2O2 产生和糠酸合成机制.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/在核壳NiS@Au助催化剂上实现自由电子转移反转和 dz2 轨道占用调制，实现高选择性 H2O2 光合作用.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/异质结光催化剂制备表征与机理研究_王中辽 (1).pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学/新建文件夹` | 0.45 | 0.0 | `14_动力学/动力学/新建文件夹/ZnOCOF S-Scheme 光催化剂中通过 Zn─N 键的界面电荷转移.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学/新建文件夹` | 0.45 | 0.0 | `14_动力学/动力学/新建文件夹/用于光催化 H2 析出中超快电荷分离和转移的超晶格界面和 S 型异质结.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/用于 CO2 光还原的 In2O3Nb2O5 S 型界面的超快电子转移.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/过渡金属硫族化合物助剂的结构调控及其光催化析氢性能_钟威.pdf` | reference_literature_scan_only |
| REFERENCE_ONLY | reference_literature | document_or_report | `14_动力学/动力学` | 0.45 | 0.0 | `14_动力学/动力学/铋 S 型异质结界面处的氧空位修饰的快速电荷传输通道促进光催化性能.pdf` | reference_literature_scan_only |
