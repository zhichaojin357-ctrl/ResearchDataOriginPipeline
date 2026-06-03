# XPS SAFE-2 Goal Summary

日期：2026-06-03

## 1. SAFE-2 是否提交

已提交。

- Commit: `5b9c823 xps: route in-situ output paths without artifacts`
- 文件清单：
  - `src/core/xps_in_situ.py`
  - `tests/test_xps_in_situ_output_routing.py`
  - `docs/XPS_SAFE2_IN_SITU_OUTPUT_ROUTING_REVIEW.md`
  - `docs/XPS_SAFE2_IN_SITU_OUTPUT_ROUTING_FIX_LOG.md`

## 2. SAFE-2 实际修改

本轮只处理 XPS in-situ workflow 的 run-scoped output path / structured output directories / report-table-manifest path contract。

- 新增 `OUTPUT_SUBDIRS`，声明 `figures_tif`、`figures_png`、`figures_pdf`、`origin_projects`、`reports`、`tables`。
- 新增 `_output_subdirs(output_dir)`，只创建结构化运行目录，不生成 OPJU/TIF/PNG/PDF/XLSX/ZIP artifacts。
- 将 peak summary destination 路由到 `tables/peak_positions_summary.xlsx`。
- 将 mapping report 路由到 `reports/xps_data_mapping_report.md`。
- 将 manifest 路由到 `reports/xps_in_situ_manifest.json`。
- 在 manifest 中新增 `output_dirs` schema，记录结构化路径意图。
- 新增 focused path-contract tests，使用 `tmp_path` 和 mocked writers 验证路径合同。

## 3. 仍 blocked 的 XPS in-situ hunk

以下内容未进入 SAFE-2，仍保持 blocker：

- grouped OPJU export。
- TIF/PNG/PDF/XLSX 真实导出。
- Origin project structure。
- matplotlib visual style。
- gradient fill。
- panel visual layout。
- real artifact existence quality checks。
- real XPS data validation。
- XPS algorithm / peak color annotation。
- heterojunction 相关剩余 hunk。

## 4. Origin / 真实数据 / artifacts / output

- 是否运行 Origin：否。
- 是否处理真实 XPS 数据：否。
- 是否运行真实 pipeline：否。
- 是否生成项目 OPJU/TIF/PNG/PDF/XLSX/ZIP/large JSON artifacts：否。
- 是否修改、移动、删除旧 `output/` 或 `outputs/`：否。
- 测试只在 pytest `tmp_path` 内创建小型临时目录、report 和 manifest，不写入项目 `output/` 或 `outputs/`。

## 5. 验证结果

已运行：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_in_situ.py tests/test_xps_in_situ.py tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ_output_routing.py
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ.py tests/test_xps_in_situ_output_routing.py -q
git status --short -- output outputs | Measure-Object -Line
```

结果：

- `py_compile` 通过。
- targeted pytest：`9 passed in 0.51s`。
- `output/outputs` dirty 计数：197。
- staged：0。

## 6. 当前 dirty 状态

第一笔 SAFE-2 commit 后：

- 当前 dirty 总数：278。
- `output/outputs` dirty 数：197。
- staged：0。

说明：这些 dirty 项主要来自本轮前已存在的 docs / output / reports 工作区状态；SAFE-2 未 stage 或 commit 任何 `output/`、`outputs/`、`docs/agent_reports/` 或 `output/reports/` 文件。

## 7. 下一步建议

建议下一步进入：

```text
GOAL: XPS Algorithmic Peak Color Annotation Review
```

理由：SAFE-2 已把 in-situ path contract 从混合 diff 中安全拆出；剩余 XPS in-situ 内容中，visual/export/Origin/artifact generation 仍需 blocker 管控，而 algorithm / peak color annotation 可先以审查型 GOAL 明确是否能继续安全拆分。
