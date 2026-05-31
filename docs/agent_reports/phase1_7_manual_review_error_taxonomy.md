# Phase 1.7 Manual Review Error Taxonomy

- Total MANUAL_REVIEW: 742

## unknown_data_type

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## weak_data_type_evidence

- Count: 740
- Likely data types: {'Mott-Schottky': 252, 'XPS': 165, 'XRD': 69, 'EPR': 58, 'EIS': 52, 'Raman': 32, 'FTIR': 30, 'BET': 23, 'PL': 19, 'photocurrent': 15}
- Rule optimization possible: True
- User confirmation required: True
- Suggested safe fix: Add header aliases and unit-stripping rules without lowering thresholds.
- Representatives: ['01_XRD/20251110/bobc shuirei.raw', '01_XRD/20251110/bobc shuirei2.raw', '01_XRD/20251110/bobcshuirei+cwo15%.raw', '01_XRD/20251110/kit-6-1.raw', '01_XRD/20251110/kit-6-2.raw', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.dql', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.raw', '01_XRD/20260326LL BOB BOC BCN/CL.dql', '01_XRD/20260326LL BOB BOC BCN/CL.raw', '01_XRD/20260326LL BOB BOC BCN/NH4.dql']

## folder_header_conflict

- Count: 2
- Likely data types: {'EIS': 2}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['04_莫特肖特基/LLKT ms/20250905/1mbMT1000.xlsx', '04_莫特肖特基/LLKT ms/20250905/1MT2000-2.xlsx']

## severe_folder_header_conflict

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## mild_folder_header_conflict

- Count: 2
- Likely data types: {'EIS': 2}
- Rule optimization possible: True
- User confirmation required: True
- Suggested safe fix: Generate user-reviewed override proposal, not automatic processing.
- Representatives: ['04_莫特肖特基/LLKT ms/20250905/1mbMT1000.xlsx', '04_莫特肖特基/LLKT ms/20250905/1MT2000-2.xlsx']

## missing_required_columns

- Count: 0
- Likely data types: {}
- Rule optimization possible: True
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## unnamed_columns_with_numeric_data

- Count: 44
- Likely data types: {'Mott-Schottky': 36, 'PL': 6, 'EIS': 2}
- Rule optimization possible: True
- User confirmation required: False
- Suggested safe fix: Use folder-confirmed numeric fallback with manual_check_required=true.
- Representatives: ['04_莫特肖特基/20251126/CWO/CWO-2-3000.csv', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO1000.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO1500.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO2000.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/CWO3000RE.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS1000.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS1500.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS2000.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS2500.xlsx', '04_莫特肖特基/CWO/raw_data/CWO莫特肖特基数据处理版/MS数据处理版/MS3000.xlsx']

## headerless_numeric_table

- Count: 31
- Likely data types: {'Raman': 31}
- Rule optimization possible: True
- User confirmation required: False
- Suggested safe fix: Use x/y fallback only after parser success and enough numeric rows.
- Representatives: ['07_拉曼/20251021/raw_data/BOBC.txt', '07_拉曼/20251021/raw_data/BOBCMS9.txt', '07_拉曼/20251021/raw_data/MOSE2_6.txt', '07_拉曼/raw_data/20251027/BOBC2.txt', '07_拉曼/raw_data/20251027/WYT/CWO+BOBC+2.txt', '07_拉曼/raw_data/20251027/WYT/CWO+BOBC+3.txt', '07_拉曼/raw_data/20251027/WYT/CWO+BOBC.txt', '07_拉曼/raw_data/20251027/WYT/CWO_1.txt', '07_拉曼/raw_data/20251027/WYT/MoTe2_1.txt', '07_拉曼/raw_data/20251027/WYT/MoTe2_2.txt']

## excel_multi_sheet_ambiguity

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## sheet_name_not_selected

- Count: 51
- Likely data types: {'XPS': 22, 'EIS': 20, 'BET': 8, 'Mott-Schottky': 1}
- Rule optimization possible: True
- User confirmation required: True
- Suggested safe fix: Score sheets by numeric density and header signatures; keep risky conflicts manual.
- Representatives: ['02_XPS/raw_data/26010989730/BC-11/BC-11.xls', '02_XPS/raw_data/26010989730/BC-11/bc拟合后的数据.xlsx', '02_XPS/raw_data/26010989730/BC-11/BI.xlsx', '02_XPS/raw_data/26010989730/bc拟合后的数据.xlsx', '02_XPS/raw_data/26010989730/BOBC/BOBC.xls', '02_XPS/raw_data/26010989730/BOBC/BOBC数据拟合后2.xlsx', '02_XPS/raw_data/26010989730/BOBC数据拟合后2.xlsx', '02_XPS/raw_data/26010989730/CWO/CWO.xls', '02_XPS/raw_data/26010989730/CWO/CWO数据拟合后.xlsx', '02_XPS/raw_data/26010989730/CWO数据拟合后.xlsx']

## parser_probe_failure

- Count: 532
- Likely data types: {'XPS': 165, 'Mott-Schottky': 117, 'XRD': 66, 'EIS': 48, 'EPR': 45, 'FTIR': 30, 'BET': 23, 'PL': 13, 'photocurrent': 9, 'photocurrent_response': 8}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['01_XRD/20251110/bobc shuirei.raw', '01_XRD/20251110/bobc shuirei2.raw', '01_XRD/20251110/bobcshuirei+cwo15%.raw', '01_XRD/20251110/kit-6-1.raw', '01_XRD/20251110/kit-6-2.raw', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.dql', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.raw', '01_XRD/20260326LL BOB BOC BCN/CL.dql', '01_XRD/20260326LL BOB BOC BCN/CL.raw', '01_XRD/20260326LL BOB BOC BCN/NH4.dql']

## encoding_issue

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## too_few_numeric_rows

- Count: 532
- Likely data types: {'XPS': 165, 'Mott-Schottky': 117, 'XRD': 66, 'EIS': 48, 'EPR': 45, 'FTIR': 30, 'BET': 23, 'PL': 13, 'photocurrent': 9, 'photocurrent_response': 8}
- Rule optimization possible: True
- User confirmation required: False
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['01_XRD/20251110/bobc shuirei.raw', '01_XRD/20251110/bobc shuirei2.raw', '01_XRD/20251110/bobcshuirei+cwo15%.raw', '01_XRD/20251110/kit-6-1.raw', '01_XRD/20251110/kit-6-2.raw', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.dql', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.raw', '01_XRD/20260326LL BOB BOC BCN/CL.dql', '01_XRD/20260326LL BOB BOC BCN/CL.raw', '01_XRD/20260326LL BOB BOC BCN/NH4.dql']

## too_few_numeric_columns

- Count: 532
- Likely data types: {'XPS': 165, 'Mott-Schottky': 117, 'XRD': 66, 'EIS': 48, 'EPR': 45, 'FTIR': 30, 'BET': 23, 'PL': 13, 'photocurrent': 9, 'photocurrent_response': 8}
- Rule optimization possible: True
- User confirmation required: False
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['01_XRD/20251110/bobc shuirei.raw', '01_XRD/20251110/bobc shuirei2.raw', '01_XRD/20251110/bobcshuirei+cwo15%.raw', '01_XRD/20251110/kit-6-1.raw', '01_XRD/20251110/kit-6-2.raw', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.dql', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.raw', '01_XRD/20260326LL BOB BOC BCN/CL.dql', '01_XRD/20260326LL BOB BOC BCN/CL.raw', '01_XRD/20260326LL BOB BOC BCN/NH4.dql']

## invalid_numeric_range

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## duplicate_ambiguity

- Count: 53
- Likely data types: {'Mott-Schottky': 46, 'photocurrent': 3, 'photocurrent_response': 3, 'Raman': 1}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['03_光电流/20260109_光电流/26010964564/Photocurrent/4-BOBC-(OCP).txt', '03_光电流/20260109_光电流/26010964564/Photocurrent/5-CWO-(OCP) .txt', '03_光电流/20260109_光电流/26010964564/Photocurrent/6-BC-11-(OCP).txt', '03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/bicu/1-（OCP）.txt', '03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/BOBC/1-(OCP).txt', '03_光电流/光电流响应/1bobc+2cwo+3bicu-10/raw_data/CWO/2-(OCP).txt', '04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC2000.csv', '04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC2500.csv', '04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC3000.csv', '04_莫特肖特基/20260121CWO+BOBC/raw_data/BOBC3500.csv']

## backup_copy_old_ambiguity

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## auxiliary_report_like

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## image_or_plot_not_raw_data

- Count: 6
- Likely data types: {'PL': 6}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EM-ex340nm.wmf', '10_EPR_PL/PL/raw_data/bobc+cwo+bc/1-EX-em640nm.wmf', '10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EM-ex340nm.wmf', '10_EPR_PL/PL/raw_data/bobc+cwo+bc/2-EX-em445nm.wmf', '10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EM-ex340nm.wmf', '10_EPR_PL/PL/raw_data/bobc+cwo+bc/3-EX-em630nm.wmf']

## requires_scientific_context

- Count: 292
- Likely data types: {'XPS': 165, 'XRD': 69, 'EPR': 58}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: ['01_XRD/20251110/bobc shuirei.raw', '01_XRD/20251110/bobc shuirei2.raw', '01_XRD/20251110/bobcshuirei+cwo15%.raw', '01_XRD/20251110/kit-6-1.raw', '01_XRD/20251110/kit-6-2.raw', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.dql', '01_XRD/20260326LL BOB BOC BCN/BICSNH4.raw', '01_XRD/20260326LL BOB BOC BCN/CL.dql', '01_XRD/20260326LL BOB BOC BCN/CL.raw', '01_XRD/20260326LL BOB BOC BCN/NH4.dql']

## requires_calibration_or_formula

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## blocked_by_policy

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []

## already_processed_or_duplicate_of_processed

- Count: 0
- Likely data types: {}
- Rule optimization possible: False
- User confirmation required: True
- Suggested safe fix: Keep as MANUAL_REVIEW or generate a user decision proposal.
- Representatives: []
