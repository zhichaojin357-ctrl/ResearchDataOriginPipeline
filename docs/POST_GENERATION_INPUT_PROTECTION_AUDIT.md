# Post-generation input protection audit

- Method: inspect product metadata source_files/reference_opju, copied-reference policy in reports, selected F-drive mtimes, and git status separately.
- Selected source/reference records checked: 28
- F-drive selected records with mtime after run timestamp: 0
- Product artifacts are under external output run roots only.

## Possible source/reference mtime anomalies

- none

## Checked records

| Run id | Type | Role | Exists | Under F root | Last write time | Path |
|---|---|---|---|---|---|---|
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | BET | source_file | yes | yes | 2026-04-30 23:14:55 | F:\课题\LL\检测\BET\XWM-LL-260428-1-BOBC-All Pore\XWM-LL-260428-1-BOBC-All Pore.XLS |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | BET | reference_opju | yes | yes | 2026-05-03 16:37:01 | F:\课题\LL\检测\BET\XWM-LL-260428-1-BOBC-All Pore\BOBC.opju |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | EPR | source_file | yes | yes | 2026-05-31 18:44:58 | F:\课题\LL\检测\EPR\EPR_Excel导出_20260531\EasySpin_JEOL_verified_4096\20260410-3\BC-O3-dark.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | EPR | reference_opju | yes | yes | 2026-05-06 10:54:50 | F:\课题\LL\检测\EPR\epr.opju |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_in_situ | source_file | yes | no | 2026-02-04 16:02:33 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\原位\BOBC数据拟合后2.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_in_situ | source_file | yes | no | 2026-05-06 11:21:13 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\原位\cu-20260506.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_in_situ | source_file | yes | no | 2026-05-06 11:10:57 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\原位\DARK-20260506.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_in_situ | source_file | yes | no | 2026-05-06 11:12:54 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\原位\LINGT-20260506.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_in_situ | reference_opju | yes | no | 2026-06-03 13:58:50 | D:\Codex Project\科研数据处理\xps参考图像\xps_in_situ_Bi_Cl_Br.opju |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_non_in_situ | source_file | yes | no | 2026-02-04 16:57:18 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\非原位\bc拟合后的数据.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_non_in_situ | source_file | yes | no | 2026-02-04 16:02:33 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\非原位\BOBC数据拟合后2.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_non_in_situ | source_file | yes | no | 2026-05-06 11:21:13 | D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\非原位\cu-20260506.xlsx |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XPS_non_in_situ | reference_opju | yes | no | 2026-06-02 20:10:36 | D:\Codex Project\科研数据处理\26.6.3组会数据\结果汇总\XPS\xps_heterojunction_stacked\origin_projects\XPS_Bi_BOBC_vs_BC_stacked.opju |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XRD | source_file | yes | yes | 2025-11-10 19:07:44 | F:\课题\LL\检测\XRD\20251110\bobc shuirei.txt |
| 20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet | XRD | reference_opju | yes | yes | 2026-04-13 20:47:17 | F:\课题\LL\检测\XRD\CWO+BOBC\CWO+BOBC+标卡.opju |
| 20260605_000310_remaining_opju_product_drafts | EIS | source_file | yes | yes | 2025-11-06 10:18:10 | F:\课题\LL\检测\阻抗EIS\20251106阻抗李永进\BOBC\EIS-1.txt |
| 20260605_000310_remaining_opju_product_drafts | EIS | reference_opju | yes | yes | 2026-04-13 00:41:49 | F:\课题\LL\检测\阻抗EIS\20260203李永进CWO+BOBC\2eis图20260202.opju |
| 20260605_000310_remaining_opju_product_drafts | FTIR | source_file | yes | yes | 2025-09-19 19:39:31 | F:\课题\LL\检测\红外\cwo+bobc\BOBC.0.dpt |
| 20260605_000310_remaining_opju_product_drafts | FTIR | source_file | yes | yes | 2025-10-14 15:00:02 | F:\课题\LL\检测\红外\cwo+bobc\CWO 15.0.dpt |
| 20260605_000310_remaining_opju_product_drafts | FTIR | reference_opju | yes | yes | 2026-04-13 20:47:11 | F:\课题\LL\检测\红外\cwo+bobc\CWO+BOBC红外.opju |
| 20260605_000310_remaining_opju_product_drafts | photocurrent | source_file | yes | yes | 2026-03-31 18:29:45 | F:\课题\LL\检测\光电流响应\1bobc+2cwo+3bicu-10\BOBC\1-(OCP).txt |
| 20260605_000310_remaining_opju_product_drafts | photocurrent | reference_opju | yes | yes | 2026-04-22 15:20:46 | F:\课题\LL\检测\光电流响应\1bobc+2cwo+3bicu-10\I-T BOBC+CWO 4.22.opju |
| 20260605_000310_remaining_opju_product_drafts | PL | source_file | yes | yes | 2026-04-07 13:54:51 | F:\课题\LL\检测\PL\bobc+cwo+bc\1-EM-ex340nm.txt |
| 20260605_000310_remaining_opju_product_drafts | PL | reference_opju | yes | yes | 2026-04-13 20:35:21 | F:\课题\LL\检测\PL\激发谱发射谱.opju |
| 20260605_000310_remaining_opju_product_drafts | Raman | source_file | yes | yes | 2025-10-22 10:20:58 | F:\课题\LL\检测\拉曼\20251021\BOBC.txt |
| 20260605_000310_remaining_opju_product_drafts | Raman | reference_opju | yes | yes | 2026-04-13 16:10:59 | F:\课题\LL\检测\拉曼\cwo+bobc raman.opju |
| 20260605_000310_remaining_opju_product_drafts | UV-vis DRS / Tauc | source_file | yes | yes | 2025-10-30 09:46:04 | F:\课题\LL\检测\固体紫外\20251017-LL\20251017\bobc.TXT |
| 20260605_000310_remaining_opju_product_drafts | UV-vis DRS / Tauc | reference_opju | yes | yes | 2025-11-20 13:19:58 | F:\课题\LL\检测\固体紫外\BOBC+MS.opju |
