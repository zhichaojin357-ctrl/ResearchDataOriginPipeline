# XPS SAFE-1 Heterojunction No-Artifact Fix Log

日期：2026-06-03

## 1. 修改的 SAFE-1 hunk

`src/core/xps_heterojunction.py`：

- 从 `TASK_SUBDIRS` 移除 `figures_preview`。
- `_export_origin_for_comparison` 中 preview PNG 改为 `origin_projects/origin_jobs` 下的 renderer job 临时路径。
- Origin COM success cleanup 和 missing-artifact 检查只要求 `origin_file` 与 `figure_tif`。
- success return 中 `preview_png` 改为 `None`，message 改为 `Origin COM export succeeded`。

`tests/test_xps_heterojunction_stacked.py`：

- 将测试重命名为 `test_run_xps_heterojunction_stacked_with_origin_updates_required_artifact_paths`。
- fake export 断言 `figures_preview` 不在 `output_dirs` 中。
- fake export 只写 synthetic tmp_path 下的 OPJU/TIF placeholder，不写 preview PNG。
- result schema 断言 `figure["preview_png"] == ""`。

## 2. 排除的 hunk

本次未接收：

- Origin script/export visual hunk。
- native gradient fill hunk。
- label/chemical formatting hunk。
- Cu2p component color grouping hunk。
- peak annotation algorithm hunk。
- report prose/schema hunk。
- `src/core/xps_in_situ.py` 的全部 hunk。
- `src/cli.py`、`tests/test_xps_in_situ.py`、`tests/test_output_routing.py` 的任何 hunk。

## 3. RED 结果

临时把 `figures_preview` 放回 `TASK_SUBDIRS` 后运行：

```powershell
D:\Python\python.exe -m pytest tests/test_xps_heterojunction_stacked.py::test_run_xps_heterojunction_stacked_with_origin_updates_required_artifact_paths -q
```

结果：失败，原因是 fake export 中的断言捕捉到 `output_dirs` 仍包含 `figures_preview`。

失败摘要：

```text
AssertionError: assert 'figures_preview' not in output_dirs
1 failed
```

## 4. GREEN / py_compile 结果

恢复 SAFE-1 source hunk 后运行：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_heterojunction.py tests/test_xps_heterojunction_stacked.py
```

结果：通过。

运行：

```powershell
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_heterojunction_stacked.py::test_run_xps_heterojunction_stacked_with_origin_updates_required_artifact_paths -q
```

结果：

```text
5 passed in 0.59s
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
- 该计数与 recheckpoint 中的既有 output/outputs dirty 数一致。
- 未发现本 GOAL 新增项目 output 路径。
- 未运行 Origin。
- 未处理真实 XPS 数据。

说明：targeted pytest 在 pytest 临时目录中创建 synthetic workbook/input placeholder；未写入项目 `output/` 或 `outputs/`。

## 6. 是否建议 staging

建议 staging，且仅 stage 以下 allowlist 文件：

- `src/core/xps_heterojunction.py`
- `tests/test_xps_heterojunction_stacked.py`
- `docs/XPS_SAFE1_HETEROJUNCTION_NO_ARTIFACT_REVIEW.md`
- `docs/XPS_SAFE1_HETEROJUNCTION_NO_ARTIFACT_FIX_LOG.md`

## 7. Commit message

```text
xps: relax heterojunction preview artifact success contract
```
