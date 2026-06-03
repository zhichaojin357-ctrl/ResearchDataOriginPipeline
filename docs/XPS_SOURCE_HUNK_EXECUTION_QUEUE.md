# XPS Source Hunk Execution Queue

日期：2026-06-03

本文件是 `XPS_SOURCE_HUNK_SPLIT_PREFLIGHT.md` 的后续执行队列。它不是提交计划，也不授权本轮修改源码、测试、stage、commit、运行 Origin、处理真实数据或生成 artifact。

## XPS-SAFE-1：Heterojunction no-artifact contract

目的：

- 将 `src/core/xps_heterojunction.py` 中 preview PNG 不再作为 COM success artifact 的合同拆为最小 source hunk。
- 使 success artifact schema 明确为 OPJU/TIF，`preview_png` 在 COM success 中为空或 `None`。
- 保持 no-Origin/no-artifact 合同，不进行视觉验收。

精确 hunk 类别：

- HJ-A：no-artifact / artifact contract。
- HJ-B：仅与 preview path 合同相关的路径子集。
- TEST-A：fake export 不生成 preview PNG、preview schema 断言。
- HJ-H：仅 preview column/schema removal；不包含视觉 prose。

Allowlist：

- `src/core/xps_heterojunction.py` 中 `_export_origin_for_comparison` 的 success artifact 检查、返回 schema、preview path 临时化。
- `src/core/xps_heterojunction.py` 中 `TASK_SUBDIRS` 的 `figures_preview` 移除，前提是测试覆盖。
- `tests/test_xps_heterojunction_stacked.py` 中 fake export contract 和 preview schema 的 targeted hunk。
- review doc 更新。

禁止事项：

- 不碰 `src/core/xps_in_situ.py`。
- 不碰 `src/cli.py`。
- 不接收 Origin geometry、ticks、native gradient、label formatting、Cu2p algorithm hunk。
- 不运行 Origin。
- 不生成 OPJU/TIF/PNG/PDF/XLSX。

测试方案：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_heterojunction.py
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_heterojunction_stacked.py -q
```

执行 GOAL 可进一步缩小到具体 nodeid，避免过宽。

建议 commit message：

```text
xps: clarify heterojunction no-artifact export contract
```

风险：

- 当前 HJ-A 与 HJ-C/HJ-E/HJ-H 相邻，容易误带 Origin visual/script hunk。
- `preview_png` 在内部 job dir 中仍作为 renderer 临时参数出现；提交信息必须区分“临时 job preview”和“success artifact preview”。

是否可自动：

- 可以，但必须使用精确 hunk allowlist 和 targeted tests。

## XPS-SAFE-2：In-situ run-scoped output path contract

目的：

- 拆出 `src/core/xps_in_situ.py` 的 path/subdir/report/manifest routing 合同。
- 不声明视觉效果，不运行 Origin，不生成真实 artifacts。

精确 hunk 类别：

- IS-A：run-scoped output routing。
- IS-E：panel planning / record filtering 的纯逻辑子集，若单独测试。
- IS-G：schema-only status/report shape 子集。
- IS-F：仅 path/schema 检查，不包含 artifact existence acceptance。

Allowlist：

- `_output_subdirs` 的目录名合同，最好通过 mock 或 path-only test 覆盖。
- `build_xps_in_situ_outputs` 中 report/manifest/table path routing 的最小必要 hunk。
- `_write_figures` / `_save_figure` 签名改动仅在不生成真实文件的测试路径中处理，或延后。
- `_panel_records` complete-record filtering，如有独立 synthetic test。

禁止事项：

- 不接收 `_write_origin_project` grouped OPJU hunk。
- 不接收 `_gradient_fill_between` 或 matplotlib visual style hunk。
- 不接收 TIF/PNG/PDF export 行为变更。
- 不碰 `tests/test_xps_in_situ.py`，除非下一轮明确允许新增 targeted tests。
- 不运行 Origin，不处理真实数据，不生成 artifact。

测试方案：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_in_situ.py
D:\Python\python.exe -m pytest tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ.py -q
```

执行 GOAL 应优先使用 nodeid 或 mock，避免真实图像保存路径。

建议 commit message：

```text
xps: route in-situ output paths through run-scoped subdirs
```

风险：

- `_output_subdirs` 当前会 mkdir；如果测试目标是 no-artifact planning，不能让规划函数创建目录。
- 当前 diff 把 routing 和 figure export 混在一起，必须先切 hunk。

是否可自动：

- 可以，但只限 path/schema/metadata 子集；涉及 file export 的部分不自动。

## XPS-SAFE-3：Heterojunction report schema / status shape

目的：

- 只处理与已接受 source contract 一致的 report/schema 字段。
- 移除 preview column 或将 preview 字段表达为空，不包含未验收视觉样式描述。

精确 hunk 类别：

- HJ-H：preview column removal、figure table schema。
- TEST-D：preview schema assertion。
- HJ-D：仅纯 policy field string contract 时可考虑，但建议独立更小提交。

Allowlist：

- `_write_summary_reports` 的表格列和 preview 字段。
- `tests/test_xps_heterojunction_stacked.py` 中与 preview schema 直接对应的断言。
- review doc 更新。

禁止事项：

- 不接收 y-axis tick prose，除非对应 source/style hunk 已被接受并有证据。
- 不接收 native Gradient Fill prose，除非 Origin/visual 已验收。
- 不接收 Cu2p visual binding-energy windows prose，除非算法 hunk 已被 review/test 接受。

测试方案：

```powershell
D:\Python\python.exe -m pytest tests/test_xps_heterojunction_stacked.py -q
```

执行 GOAL 可收窄到 dry-run summary/report schema nodeid。

建议 commit message：

```text
xps: align heterojunction report schema with no-preview contract
```

风险：

- 报告文字很容易提前声明未验收视觉行为。

是否可自动：

- 可以，但只限 schema，不含视觉声明。

## XPS-SAFE-4：Algorithmic peak/color/annotation review

目的：

- 对 Cu2p component color grouping、component peak binding、annotation behavior 做 review-only 或独立 synthetic-test 准备。
- 不运行 Origin，不做视觉验收。

精确 hunk 类别：

- HJ-G：component / peak / annotation algorithm。
- TEST-C：Cu2p color grouping、annotation inclusion synthetic tests。

Allowlist：

- `_component_peak_binding`、`_cu2p_visual_color_group`、`_plot_component_specs_by_record` 的纯算法 hunk。
- `_infer_peak_assignment` 的 Cu2p windows hunk。
- 对应 synthetic tests。

禁止事项：

- 不接收 Origin script/export hunk。
- 不接收 native gradient/visual style hunk。
- 不把算法正确性等同于视觉正确性。
- 不写 XPS 价态、电子转移、S-scheme 或异质结机制自动结论。

测试方案：

```powershell
D:\Python\python.exe -m py_compile src/core/xps_heterojunction.py
D:\Python\python.exe -m pytest tests/test_xps_heterojunction_stacked.py -q
```

建议先跑具体 algorithm nodeid，而不是整个文件。

建议 commit message：

```text
xps: isolate Cu2p component color grouping logic
```

风险：

- 当前算法改变了旧合同：Cu2p annotations 从 omitted 变为 included。
- 需要明确这是 plotting metadata/annotation behavior，不是化学机制结论。

是否可自动：

- 建议先 review-only；若测试合同明确后可自动执行小提交。

## XPS-BLOCKED-1：Origin script/export visual style

目的：

- 后续 Origin 专项 GOAL 才能处理 heterojunction Origin script/export 和 visual style。

精确 hunk 类别：

- HJ-C：Origin script/export。
- HJ-E：native gradient fill / visual style。
- HJ-F：label and chemistry formatting 中依赖 Origin 显示的部分。
- TEST-B 中 Origin script visual string assertions。

Allowlist：

- 仅在 Origin/visual GOAL 中允许。

禁止事项：

- 不在 safe commit 中接收。
- 不用 compile/string assertion 代替 visual evidence。

测试方案：

- 需要 Origin 可用性检查、synthetic Origin export、截图/视觉证据、artifact existence/quality 检查。

建议 commit message：

```text
xps: update heterojunction Origin visual renderer
```

风险：

- 需要 OPJU/TIF/PNG 生成和视觉审查。

是否可自动：

- 否。

## XPS-BLOCKED-2：In-situ grouped OPJU / artifact generation

目的：

- 后续 Origin 专项 GOAL 才能处理 grouped OPJU、per-panel graphs、per-record worksheets、TIF/PNG/PDF export。

精确 hunk 类别：

- IS-B：artifact handling。
- IS-C：Origin project structure。
- IS-F 中 grouped OPJU/TIF/PNG/PDF existence checks。
- IS-G 中 Origin success status/message 的行为部分。

Allowlist：

- 仅在 Origin/artifact GOAL 中允许。

禁止事项：

- 不在 path-only safe commit 中接收。
- 不生成 OPJU/TIF/PNG/PDF/XLSX。

测试方案：

- Origin smoke。
- grouped OPJU existence。
- per-panel TIF/PNG/PDF export verification。
- visual inspection or screenshot-backed evidence。

建议 commit message：

```text
xps: split in-situ Origin projects by element group
```

风险：

- 大范围 Origin COM 行为，当前无视觉证据。

是否可自动：

- 否。

## XPS-BLOCKED-3：Matplotlib visual style changes

目的：

- 后续 visual GOAL 才能处理 in-situ matplotlib gradient fill、line width、labels、ticks、save artifacts。

精确 hunk 类别：

- IS-D：matplotlib visual。
- `_gradient_fill_between`。
- sample display / label placement / peak guide line / tick direction。

Allowlist：

- 仅在 visual QA GOAL 中允许。

禁止事项：

- 不在 no-artifact/source-contract commit 中接收。
- 不生成 PNG/PDF/TIF。

测试方案：

- Synthetic figure generation in temp output。
- Screenshot or rendered image inspection。
- Optional pixel/size/DPI checks。

建议 commit message：

```text
xps: revise in-situ matplotlib visual style
```

风险：

- 视觉变化没有当前验收证据。

是否可自动：

- 否。

## XPS-BLOCKED-4：Real data validation

目的：

- 后续真实 XPS 数据 GOAL 才能处理实际数据兼容性、真实峰位、真实报告和科学解释边界。

精确 hunk 类别：

- 所有需要真实 XPS workbook、真实输出和人工科学判断的 hunk。

Allowlist：

- 仅在明确允许真实数据处理的 GOAL 中允许。

禁止事项：

- 当前不处理真实数据。
- 不写价态、电子转移、S-scheme 或异质结机制自动结论。

测试方案：

- 明确输入样本。
- run-scoped output。
- artifact inventory。
- manual review 标记。

建议 commit message：

```text
xps: validate source split against real XPS fixtures
```

风险：

- 高，需要人工科学审查。

是否可自动：

- 否。

## 推荐下一步 GOAL

推荐下一步：

`GOAL: XPS SAFE-1 Heterojunction No-Artifact Contract Source Split`

最小范围：

- 只处理 HJ-A 中 preview PNG success artifact removal。
- 只处理 TEST-A 中 fake export / preview schema 断言。
- 可附带最小 review doc。
- 不碰 `src/core/xps_in_situ.py`。
- 不接收任何 Origin visual/style/algorithm hunk。
