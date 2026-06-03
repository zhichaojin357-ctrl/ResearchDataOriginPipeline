# XPS SAFE-2 In-Situ Output Routing Review

日期：2026-06-03

## 1. SAFE-2 目的

本 SAFE-2 只处理 XPS in-situ workflow 的 run-scoped output path / structured output directories / report-table-manifest path contract。目标是让 in-situ workflow 明确构造 run-scoped 子目录，并把 report、manifest、table destination 路由到结构化目录；本轮不运行 Origin、不处理真实 XPS 数据、不生成项目 OPJU/TIF/PNG/PDF/XLSX/ZIP/large JSON artifacts。

## 2. Strict allowlist

允许修改：

- `src/core/xps_in_situ.py`
- `tests/test_xps_in_situ.py`
- `tests/test_xps_no_artifact_contracts.py`
- `tests/test_xps_in_situ_output_routing.py`
- `docs/XPS_SAFE2_IN_SITU_OUTPUT_ROUTING_REVIEW.md`
- `docs/XPS_SAFE2_IN_SITU_OUTPUT_ROUTING_FIX_LOG.md`

允许的 source 行为：

- 新增 in-situ output subdir path helper。
- 构造 `figures_tif/`、`figures_png/`、`figures_pdf/`、`origin_projects/`、`reports/`、`tables/` 的路径合同。
- 将 peak summary destination 路由到 `tables/peak_positions_summary.xlsx`。
- 将 mapping report destination 路由到 `reports/xps_data_mapping_report.md`。
- 将 manifest destination 路由到 `reports/xps_in_situ_manifest.json`。
- 在 manifest 中记录 structured output dirs schema。

## 3. `src/core/xps_in_situ.py` 中识别到的 SAFE-2 hunk

可拆出的 SAFE-2 hunk：

- `_output_subdirs(output_dir)` 的 structured path construction。
- `build_xps_in_situ_outputs` 中 report/table/manifest destination routing。
- manifest 中的 `output_dirs` schema。

需要排除或延后：

- `_write_figures` / `_save_figure` 保存路径重写，因为这会改变 TIF/PNG/PDF artifact generation destination。
- `_try_write_origin_project` grouped OPJU 结构，因为需要 Origin/artifact GOAL。
- `_quality_checks` 对 OPJU/TIF/PNG/PDF existence 的新预期，因为依赖真实 artifact。
- `_panel_records` complete-record filtering，因为是逻辑 hunk，不属于本 SAFE-2 最小路径合同。

## 4. 对应 test hunk

新增 focused test 文件：

- `tests/test_xps_in_situ_output_routing.py`

测试目标：

- `_output_subdirs` 返回固定子目录映射，并且只创建目录，不创建 OPJU/TIF/PNG/PDF/XLSX/ZIP artifacts。
- `build_xps_in_situ_outputs` 在 synthetic/mocked writer 下把 peak summary path 传给 `tables/`，把 report/manifest 写入 `reports/`，并不写 root-level report/manifest/table。
- 测试不运行 Origin，不调用真实 parser，不处理真实 XPS 数据，不生成项目 output。

## 5. 明确排除的 hunk

本 SAFE-2 明确排除：

- grouped OPJU export。
- TIF/PNG/PDF/XLSX 真实生成。
- Origin project structure。
- matplotlib visual style。
- gradient fill。
- panel visual layout。
- real artifact quality checks。
- real data validation。
- heterojunction hunks。

## 6. 测试计划

计划执行：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_in_situ.py tests/test_xps_in_situ.py tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ_output_routing.py
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ.py tests/test_xps_in_situ_output_routing.py -q
git status --short -- output outputs
git status --short -- output/reports
```

如果 `tests/test_xps_in_situ.py` 的 artifact-missing test 与 SAFE-2 schema change 冲突，只允许在该文件内做 path/schema 级调整；不允许运行 Origin 或生成 artifacts。

## 7. 风险等级

风险等级：中。

主要风险：

- 当前 `src/core/xps_in_situ.py` working diff 混入大量 visual/Origin/artifact hunk，必须先回到 HEAD 再只应用 SAFE-2。
- `_output_subdirs` 会创建目录；这属于 path contract，不是 OPJU/TIF/PNG/PDF/XLSX artifact，但测试必须确认未生成 artifact suffix 文件。
- 不能把 future figure/Origin artifact destination 误提交为已验收导出行为。

## 8. 是否建议进入修复/拆分

建议进入修复/拆分。SAFE-2 hunk 可以与当前 mixed diff 中的 Origin/visual/artifact hunk 分开；可通过 synthetic/tmp_path + mocked writer 的 targeted tests 验证，不需要 Origin、真实 XPS 数据或项目 artifact generation。
