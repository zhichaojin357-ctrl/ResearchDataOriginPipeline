# XPS SAFE-2 In-Situ Output Routing Fix Log

日期：2026-06-03

## 1. 修改的 SAFE-2 hunk

`src/core/xps_in_situ.py`：

- 新增 `OUTPUT_SUBDIRS`，定义 in-situ structured output dirs：
  - `figures_tif`
  - `figures_png`
  - `figures_pdf`
  - `origin_projects`
  - `reports`
  - `tables`
- 新增 `_output_subdirs(output_dir)`，只构造并创建 run-scoped structured directories。
- `build_xps_in_situ_outputs` 将 peak summary destination 路由到 `tables/peak_positions_summary.xlsx`。
- `build_xps_in_situ_outputs` 将 mapping report 路由到 `reports/xps_data_mapping_report.md`。
- `build_xps_in_situ_outputs` 将 manifest 路由到 `reports/xps_in_situ_manifest.json`。
- manifest 新增 `output_dirs` schema，记录 structured path intent。

`tests/test_xps_in_situ_output_routing.py`：

- 新增 `_output_subdirs` path-only contract test。
- 新增 synthetic/mocked `build_xps_in_situ_outputs` routing test。
- 测试不运行 Origin，不读取真实 XPS 数据，不写项目 `output/` 或 `outputs/`。
- fake `_write_peak_summary` 只记录 path，不写 XLSX。
- fake `_write_figures` 不写 PNG/PDF/TIF。

## 2. 排除的 hunk

本次未接收：

- `_write_figures` / `_save_figure` artifact export destination changes。
- grouped OPJU export。
- Origin project structure。
- TIF/PNG/PDF/XLSX 真实生成。
- matplotlib visual style。
- gradient fill。
- panel visual layout。
- real artifact quality checks。
- real data validation。
- heterojunction hunks。

## 3. RED 结果

新增 focused test 后、在 HEAD 基线下运行：

```powershell
D:\Python\python.exe -m pytest tests/test_xps_in_situ_output_routing.py -q
```

结果：失败，原因是旧代码没有 `_output_subdirs` path contract。

失败摘要：

```text
2 failed
AssertionError: assert False
where False = hasattr(xps, '_output_subdirs')
```

## 4. GREEN / py_compile 结果

运行：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_in_situ.py tests/test_xps_in_situ.py tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ_output_routing.py
```

结果：通过。

运行：

```powershell
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ.py tests/test_xps_in_situ_output_routing.py -q
```

结果：

```text
9 passed in 0.52s
```

## 5. Output pollution check

运行：

```powershell
git status --short -- output outputs
git status --short -- output/reports
git status --short -- output outputs | Measure-Object -Line
```

结果：

- `output/outputs` dirty 计数：197。
- 该计数与本 GOAL 前的既有 output/outputs dirty 基线一致。
- 未发现本 GOAL 新增项目 output 路径。
- 未运行 Origin。
- 未处理真实 XPS 数据。
- 未生成项目 OPJU/TIF/PNG/PDF/XLSX/ZIP/large JSON artifacts。

说明：targeted tests 只在 pytest tmp_path 下创建 structured directories 和小型 report/manifest test files；未写入项目 `output/` 或 `outputs/`。

## 6. 是否建议 staging

建议 staging，且仅 stage 以下 allowlist 文件：

- `src/core/xps_in_situ.py`
- `tests/test_xps_in_situ_output_routing.py`
- `docs/XPS_SAFE2_IN_SITU_OUTPUT_ROUTING_REVIEW.md`
- `docs/XPS_SAFE2_IN_SITU_OUTPUT_ROUTING_FIX_LOG.md`

## 7. Commit message

```text
xps: route in-situ output paths without artifacts
```
