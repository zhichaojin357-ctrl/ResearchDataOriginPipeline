# BET OPJU 对比修复暂停报告

## 本次小任务范围

- 只处理用户指出明显错误的 BET OPJU 对比测试。
- 使用项目脚本 `run.py process --with-origin` 重新生成图，不用手工 Origin COM 临时补图。
- 不修改 `F:\课题\LL\检测` 原始备份。

## 已核对的参考 OPJU

- 参考 OPJU：`F:\课题\LL\检测\BET\XWM-LL-260428-1-BOBC-All Pore\BOBC.opju`
- 工作区复制件：`output/opju_exemplar_regression/reference_opju/BET/BOBC.opju`
- 已导出参考图页：
  - `output/opju_exemplar_regression/reference_exports/opju_exemplar_05_BET/Graph1.tif`
  - `output/opju_exemplar_regression/reference_exports/opju_exemplar_05_BET/Graph2.tif`
  - `output/opju_exemplar_regression/reference_exports/opju_exemplar_05_BET/Graph3.tif`
  - `output/opju_exemplar_regression/reference_exports/opju_exemplar_05_BET/Graph4.tif`
  - `output/opju_exemplar_regression/reference_exports/opju_exemplar_05_BET/Graph5.tif`

## 学到的 BET 主图要求

- BET 主图应为吸附/脱附等温线。
- X 轴：`Relative Pressure (P/P0)` 或 `Relative Pressure (P/Po)`。
- Y 轴：`Quantity Adsorbed (cm3/g STP)`。
- 至少包含吸附和脱附两条分支。
- Y 轴线、Y 刻度线、Y 数字刻度都应显示。
- 图型应为 line+symbol，不应画 summary 单点候选图。

## 修复的问题

1. `BET_bet_bobc_all_pore...processed.csv` 之前只有 summary 表头，没有数据行。
2. 项目脚本把 `bet_surface_area_m2_g_candidate` / `pore_volume_cm3_g_candidate` 当作 X/Y 作图，生成了错误单点图。
3. BET vendor XLS 的真实等温线表嵌在宽报告中，原处理器没有识别。
4. `desorption_volume_optional` 被 adapter 当作辅助列过滤，导致只画吸附分支。
5. BET 轴题和图例直接使用内部字段名，可读性差。
6. BET 吸附/脱附分支被当作同一材料色，分支区分不清。

## 已修改代码

- `src/processors/calculations.py`
  - 新增 BET vendor report 等温线提取逻辑。
  - 优先提取 `Relative Pressure (P/Po)` + `Quantity Adsorbed` 成对列。
  - 输出 `relative_pressure_p_p0, adsorbed_volume, desorption_volume_optional`。

- `src/processors/base.py`
  - 将 BET 等温线 processed header 映射为正式 Origin 轴题。

- `src/origin/adapter.py`
  - 对明确指定的绘图列允许 `optional` 分支进入图像。
  - 将 `adsorbed_volume` / `desorption_volume_optional` 图例转换为 `Quantity Adsorbed` / `Quantity Desorption`。
  - BET 分支颜色按 branch 处理，不再当作材料身份。

## 新增测试

- `tests/test_processor_behaviors.py`
  - `test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point`

- `tests/test_origin_adapter.py`
  - `test_bet_origin_job_keeps_desorption_optional_branch_as_plot_series`

## 验证结果

- 定向测试：`68 passed, 10 subtests passed`
- BET 单项真实 Origin 导出：成功
- 当前 Origin 进程残留：0

## 当前 BET 输出

- processed CSV：`output/processed_data/BET/bet_bobc_all_pore_q_72e137157e0c_processed.csv`
- OPJU：`output/origin_files/BET_bet_bobc_all_pore_q_72e137157e0c.opju`
- TIF：`output/figures_tif/BET_bet_bobc_al_c149f7d5.tif`
- PNG preview：`output/figures_preview/BET_bet_bobc_al_c149f7d5.png`

TIF 检查：

- 尺寸：`6432 x 4923`
- DPI：`600 x 600`

## 暂停点

BET 这一个小任务已完成到可继续人工查看的状态。后续其它数据类型的 OPJU 对比测试尚未继续执行，按用户要求暂停。
