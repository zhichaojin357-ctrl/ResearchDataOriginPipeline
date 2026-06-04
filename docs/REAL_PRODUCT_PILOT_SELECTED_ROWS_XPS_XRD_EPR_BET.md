# Real Product Pilot Selected Rows

## BET

- Data: `F:\课题\LL\检测\BET\XWM-LL-260428-1-BOBC-All Pore\XWM-LL-260428-1-BOBC-All Pore.XLS`
- OPJU exemplar: `F:\课题\LL\检测\BET\XWM-LL-260428-1-BOBC-All Pore\BOBC.opju`
- Reason: valid high-confidence exemplar; suitable for isotherm / pore-distribution visual calibration.

## XPS In-Situ

- Data root: `D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\原位`
- Preferred OPJU exemplar: `D:\Codex Project\科研数据处理\xps参考图像\xps_in_situ_Bi_Cl_Br.opju`
- Additional allowed exemplar if needed: `D:\Codex Project\科研数据处理\xps参考图像\xps_in_situ_Cu_W.opju`
- Rule: keep separate from non-in-situ XPS; no valence, electron-transfer, or S-scheme conclusion.

## XPS Non-In-Situ

- Data root: `D:\Codex Project\科研数据处理\26.6.3组会数据\XPS\非原位`
- Preferred rule: use a valid non-in-situ XPS exemplar from `D:\Codex Project\科研数据处理\xps参考图像`.
- Fallback rule: use the archived `XPS_Bi_BOBC_vs_BC_stacked.opju` only after copying it into the run reference folder.
- Rule: keep separate from in-situ XPS; fitted roles are graph roles only.

## XRD

- Data: `F:\课题\LL\检测\XRD\20251110\bobc shuirei.txt`
- OPJU exemplar: `F:\课题\LL\检测\XRD\CWO+BOBC\CWO+BOBC+模板卡.opju`
- Rule: do not automatically copy reference-card/stick content or crystal-plane labels.

## EPR

- Data: `F:\课题\LL\检测\EPR\EPR_Excel导出_20260531\EasySpin_JEOL_verified_4096\20260410-3\BC-O3-dark.xlsx`
- OPJU exemplar: `F:\课题\LL\检测\EPR\epr.opju`
- Rule: overlay/decode visual style only; no radical assignment.
