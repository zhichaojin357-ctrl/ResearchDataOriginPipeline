# XPS SAFE-1 Heterojunction No-Artifact Review

日期：2026-06-03

## 1. SAFE-1 目的

本 SAFE-1 只处理 heterojunction preview PNG 不再作为 Origin COM success artifact 的 source/test hunk。目标是让成功合同只依赖可声明的 OPJU/TIF 字段，`preview_png` 不再是 success 必需项；本轮不运行 Origin、不处理真实 XPS 数据、不生成 OPJU/TIF/PNG/PDF/XLSX。

## 2. Strict allowlist

允许修改：

- `src/core/xps_heterojunction.py`
- `tests/test_xps_heterojunction_stacked.py`
- `docs/XPS_SAFE1_HETEROJUNCTION_NO_ARTIFACT_REVIEW.md`
- `docs/XPS_SAFE1_HETEROJUNCTION_NO_ARTIFACT_FIX_LOG.md`

允许的 source/test 行为：

- 从 heterojunction success artifact contract 中移除 preview PNG。
- `TASK_SUBDIRS` 不再包含 `figures_preview`。
- `_export_origin_for_comparison` 不再要求 preview PNG 存在或非空。
- `_export_origin_for_comparison` 成功返回时 `preview_png` 为 `None`。
- 测试 fake export 只构造 OPJU/TIF path，不创建 preview PNG。
- 测试只断言 path/schema/contract，不运行 Origin，不要求真实 artifact。

## 3. `src/core/xps_heterojunction.py` 中识别到的 SAFE-1 hunk

可拆出的 SAFE-1 hunk：

- `TASK_SUBDIRS` 移除 `figures_preview`。
- `_export_origin_for_comparison` 中 `preview_png` 从 `output_dirs["figures_preview"]` 改为 `origin_projects/origin_jobs` 下的临时 job path。
- cleanup 和 missing-artifact 检查只覆盖 `origin_file` 与 `figure_tif`。
- success 返回 `preview_png: None`。
- success message 明确为 Origin COM export 成功。

边界说明：

- `_ensure_tif_600_dpi` 属于 TIF quality/artifact 后处理，不是 preview success artifact 的最小必要 hunk，本 SAFE-1 不接收。
- direct Origin script 内的 PNG export、TIF width、layout、ticks、gradient、labels 都不属于 SAFE-1。
- report prose/table schema 不进入本 SAFE-1。

## 4. `tests/test_xps_heterojunction_stacked.py` 中识别到的 assertion hunk

可拆出的 SAFE-1 hunk：

- `test_run_xps_heterojunction_stacked_with_origin_updates_artifact_paths` 中 fake export 不再创建 `figures_preview` PNG。
- fake export 返回 `preview_png: None`。
- result figure row 中 `preview_png` 序列化为空字符串。

边界说明：

- 不接收 Cu2p component color grouping 测试。
- 不接收 Cu2p annotation inclusion 测试。
- 不接收 plot policy / Origin helper script visual 字符串断言。
- 不接收 y-axis report prose 断言。
- 不接收 direct Origin script style/geometry/label 断言。

## 5. 明确排除的 hunk

本 SAFE-1 明确排除：

- Origin script/export hunk。
- visual style hunk。
- native gradient fill hunk。
- label/chemical formatting hunk。
- Cu2p color grouping hunk。
- peak annotation algorithm hunk。
- report prose/schema hunk。
- `src/core/xps_in_situ.py` 的全部 hunk。

## 6. 测试计划

计划执行：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_heterojunction.py tests/test_xps_heterojunction_stacked.py
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_heterojunction_stacked.py::test_run_xps_heterojunction_stacked_with_origin_updates_artifact_paths -q
git status --short -- output outputs
git status --short -- output/reports
```

说明：不运行整个 `tests/test_xps_heterojunction_stacked.py`，因为该文件当前 HEAD/working tree 还包含非 SAFE-1 的 wider behavior tests；本 GOAL 只验证 no-artifact 合同与目标 fake export nodeid。

## 7. 风险等级

风险等级：低到中。

主要风险：

- 当前 working tree 中同一文件混有大量 blocked hunk，需要先剥离。
- 若误带 Origin script/style/algorithm hunk，会破坏 SAFE-1 边界。
- 若运行过宽测试，可能触发与本 GOAL 无关的 blocked behavior。

## 8. 是否建议进入修复/拆分

建议进入修复/拆分。SAFE-1 hunk 可以与 visual/style/algorithm/report prose hunk 分开，且可通过 synthetic/tmp_path targeted tests 验证，不需要 Origin、真实数据或 artifact generation。
