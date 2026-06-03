# XPS Source Hunk Split Preflight

日期：2026-06-03

仓库根目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

本轮只做 hunk 分类和执行队列规划；未修改源码，未修改测试，未 stage，未 commit，未运行 Origin，未处理真实数据，未生成 OPJU/TIF/PNG/PDF/XLSX/ZIP/large JSON。原始 diff 通过 `git diff` 命令读取分析，未另存 raw diff 快照文件。

## Phase 0 范围检查

已执行命令：

```powershell
git status --short
git diff --cached --name-status
git status --short -- src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py src/cli.py tests/test_xps_in_situ.py tests/test_xps_no_artifact_contracts.py tests/test_output_routing.py
git diff --stat -- src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py
git diff --check -- src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py
```

结果：

| 检查项 | 结果 |
|---|---|
| staged | 0，`git diff --cached --name-status` 无输出 |
| 指定 XPS 范围 dirty | 仅 3 个文件 dirty |
| `src/cli.py` | 无 dirty |
| `tests/test_xps_in_situ.py` | 无 dirty |
| `tests/test_xps_no_artifact_contracts.py` | 无 dirty |
| `tests/test_output_routing.py` | 无 dirty |
| `git diff --check` | 无 whitespace error；仅 LF/CRLF working-copy warning |

当前 XPS dirty 文件：

```text
 M src/core/xps_heterojunction.py
 M src/core/xps_in_situ.py
 M tests/test_xps_heterojunction_stacked.py
```

Diff 规模：

| 文件 | 插入 | 删除 |
|---|---:|---:|
| `src/core/xps_heterojunction.py` | 208 | 112 |
| `src/core/xps_in_situ.py` | 460 | 126 |
| `tests/test_xps_heterojunction_stacked.py` | 156 | 17 |

总 diff stat：

```text
3 files changed, 824 insertions(+), 255 deletions(-)
```

## no-artifact 参考合同

只读参考：`tests/test_xps_no_artifact_contracts.py`。

已提交合同覆盖点：

- `build_comparison_plan(... with_origin=False)` 不创建 output dir，不生成 OPJU/TIF/PNG/PDF/XLSX/ZIP。
- 缺失 counterpart 时只产生 manual review metadata，不生成 artifact。
- in-situ `planned_panels` 只做 metadata planning，不生成 artifact。
- CLI dry-run parser 合同：`with_origin` 默认 false，help text 不包含 visual acceptance 或 S-scheme 自动结论。

这组测试可作为后续 safe hunk 的基准，但不能证明 Origin 输出、视觉样式、真实 XPS 数据解释或 artifact 质量。

## HJ：`src/core/xps_heterojunction.py` hunk inventory

### HJ-A no-artifact / artifact contract

涉及 hunk：

- `_ensure_tif_600_dpi` import。
- `TASK_SUBDIRS` 移除 `figures_preview`。
- `_export_origin_for_comparison` 不再把 preview PNG 作为 success artifact。
- COM success 只要求 OPJU/TIF 存在且非空。
- 成功返回 `preview_png: None`，message 改为 `Origin COM export succeeded`。
- `_write_summary_reports` 的 generated/planned figure 表格移除 preview 列。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 是，但必须只抽取 artifact contract 子集 |
| 需要 Origin | 不需要，若使用 mock export / dry-run 合同测试 |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 不需要 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 部分可用；还需 targeted heterojunction test |
| 需要新增 targeted tests | 是，覆盖 preview PNG 不再是 success artifact |
| 是否应单独 commit | 是 |
| 是否 blocker | 否，前提是与 Origin style hunk 分离 |

推荐队列：`XPS-SAFE-1`。

### HJ-B run-scoped output routing

涉及 hunk：

- `TASK_SUBDIRS` 中与输出子目录有关的变化。
- `preview_png` 从 `figures_preview` 转到 `origin_projects/origin_jobs` 的 job 临时位置。
- report schema 中输出路径字段随 artifact contract 变化。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 可以，但应与 HJ-A 分开确认边界 |
| 需要 Origin | 不需要，路径构造可用 tmp_path 验证 |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 不需要 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 部分可用 |
| 需要新增 targeted tests | 是，覆盖目录不创建或只在执行路径创建 |
| 是否应单独 commit | 是，若从 artifact contract 中独立出来 |
| 是否 blocker | 否，但边界不清时先留到 preflight 后续 |

推荐队列：可并入 `XPS-SAFE-1` 的路径合同部分，或在执行时拆为独立小提交。

### HJ-C Origin script/export

涉及 hunk：

- direct Origin script 移除 PNG export，只导出 TIF。
- TIF export width 从 3600 改为 6432。
- page/layer geometry、axis thickness、ticks、label show/hide、label size、second axis 设置。
- Origin helper script 文本大量变化。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 否，除非只做纯字符串合同断言 |
| 需要 Origin | 是，实际行为需要 Origin |
| 需要真实 XPS 数据 | 不一定，但至少需要 synthetic Origin smoke |
| 需要视觉判断 | 是 |
| 会生成 artifact | 是，OPJU/TIF/PNG 相关 |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，且需要 Origin/visual GOAL |
| 是否应单独 commit | 是，未来 Origin 专项提交 |
| 是否 blocker | 是 |

推荐队列：`XPS-BLOCKED-1`。

### HJ-D plot policy propagation

涉及 hunk：

- 新增 `get_plot_policy("XPS fitted")`。
- generated helper script 注入 `PlotType`、`PlotPrimitive`、`MarkerMode`、`FitOverlayMode`、axis/tick visibility 字段。
- 测试新增 `_build_xps_origin_script` 字符串断言。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 可做纯字符串合同小提交，但不应声明视觉验收 |
| 需要 Origin | 字符串合同不需要；行为验收需要 |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 若宣称样式正确则需要 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 否，需新 targeted test |
| 需要新增 targeted tests | 是，字符串合同即可 |
| 是否应单独 commit | 是 |
| 是否 blocker | 部分 blocker：合同字段可 safe，视觉效果 blocked |

推荐队列：合同字段可进 `XPS-SAFE-3` 或独立 safe；实际 Origin 效果进 `XPS-BLOCKED-1`。

### HJ-E native gradient fill / visual style

涉及 hunk：

- `apply_native_gradient_fill` / `_apply_native_gradient_fill`。
- layered gradient columns 改为 single upper/lower pair。
- component/measured/background/envelope line width 和 fill style 改动。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 否，默认 blocked |
| 需要 Origin | 是 |
| 需要真实 XPS 数据 | 不一定，但需 representative synthetic/fixture |
| 需要视觉判断 | 是 |
| 会生成 artifact | 是 |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，且需要视觉证据 |
| 是否应单独 commit | 是，未来视觉/Origin 专项 |
| 是否 blocker | 是 |

推荐队列：`XPS-BLOCKED-1`。

### HJ-F label and chemistry formatting

涉及 hunk：

- `SAMPLE_DISPLAY_NAMES` 从 Unicode 下标文本改为 Origin escape 文本。
- `bold_multiline` / `_bold_multiline`。
- `chemical_subscripts` / `_chemical_subscripts`。
- label bold/fontbold/fstyle 设置。
- peak label 和 sample label 通过 bold/subscript helper 生成。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 只有纯 helper 字符串转换可自动；当前混在 Origin script 中不宜自动 |
| 需要 Origin | 行为效果需要 Origin |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 是，若声明显示正确 |
| 会生成 artifact | 行为验收会 |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，纯 helper 可用 unit tests |
| 是否应单独 commit | 是 |
| 是否 blocker | 当前状态是 blocker，除非先抽纯函数 |

推荐队列：纯 helper 可作为后续小 safe review；当前混合 hunk 归 `XPS-BLOCKED-1`。

### HJ-G component / peak / annotation algorithm

涉及 hunk：

- `_plot_component_specs_by_record` 从 binding key 全局排序改为 peak binding / visual group。
- 新增 `_component_peak_binding`。
- 新增 `_cu2p_visual_color_group`。
- `_component_peak_binding_key` 语义变化。
- `_major_component_labels` 不再优先 `_highest_local_peak`。
- Cu2p peak assignment 增加 satellite windows。
- `_comparison_peak_details` 不再对 Cu2p 直接返回空。
- `_nice_step` 从 span/5 改为 span/8，新增 `_major_tick_values`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 不建议直接自动；先 review-only |
| 需要 Origin | 不一定 |
| 需要真实 XPS 数据 | 不一定，但需要 carefully designed synthetic tests |
| 需要视觉判断 | 部分需要，尤其颜色和 annotation 视觉效果 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是 |
| 是否应单独 commit | 是 |
| 是否 blocker | 当前应 blocker 或 review-only |

推荐队列：`XPS-SAFE-4` review-only；视觉接受仍进 blocker。

### HJ-H report/schema/content

涉及 hunk：

- summary prose 从 layered fill 改为 Origin native Gradient Fill。
- y-axis tick 描述从隐藏 tick 改为显示 tick、隐藏 tick values。
- Cu2p color assignment 文本改为 visual binding-energy windows。
- generated/planned figures table 移除 preview 列。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 可以，但只能提交与已接受 source contract 一致的 schema 文本 |
| 需要 Origin | 文本/schema 不需要；视觉声明需要证据 |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 视觉声明需要 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 部分可用 |
| 需要新增 targeted tests | 是，report/schema assertion |
| 是否应单独 commit | 是 |
| 是否 blocker | 与未验收视觉绑定的文字应 blocked |

推荐队列：`XPS-SAFE-3` 只接收 preview schema；视觉描述进 `XPS-BLOCKED-1`。

## IS：`src/core/xps_in_situ.py` hunk inventory

### IS-A run-scoped output routing

涉及 hunk：

- 新增 `_output_subdirs`，创建 `figures_tif/`、`figures_png/`、`figures_pdf/`、`origin_projects/`、`reports/`、`tables/`。
- `build_xps_in_situ_outputs` 将 peak summary、manifest、mapping report、figure save 路由到结构化子目录。
- `_write_figures` 和 `_save_figure` 签名改为接受 `output_dirs`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 是，但只限路径/manifest/report routing |
| 需要 Origin | 不需要 |
| 需要真实 XPS 数据 | 不需要，可用 synthetic tmp_path |
| 需要视觉判断 | 不需要 |
| 会生成 artifact | 执行完整函数会生成图像；safe test 应只测 path contract 或 mock save |
| 可用现有 no-artifact tests 验证 | 部分可用，主要参考 planning no-artifact |
| 需要新增 targeted tests | 是 |
| 是否应单独 commit | 是 |
| 是否 blocker | 否，前提是隔离 artifact generation |

推荐队列：`XPS-SAFE-2`。

### IS-B artifact handling

涉及 hunk：

- `_ensure_tif_600_dpi`。
- grouped OPJU projects。
- per-panel TIF/PNG/PDF export。
- 移除 combined final PNG image page。
- Origin status 从单 `origin_file` 改为 `origin_files`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 否 |
| 需要 Origin | 是 |
| 需要真实 XPS 数据 | 可能需要 representative input |
| 需要视觉判断 | 是 |
| 会生成 artifact | 是 |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，Origin/visual/artifact 专项 |
| 是否应单独 commit | 是 |
| 是否 blocker | 是 |

推荐队列：`XPS-BLOCKED-2`。

### IS-C Origin project structure

涉及 hunk：

- `ORIGIN_PROJECT_GROUPS`。
- per-panel Origin graphs。
- per-record worksheets。
- `_origin_record_columns`、`_origin_counts_header`。
- `_origin_sample_offsets`。
- `_add_origin_panel_labels`。
- `_append_origin_style_validation`。
- `_hex_to_rgb`、`_origin_color_cmd`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 否 |
| 需要 Origin | 是 |
| 需要真实 XPS 数据 | 不一定，但需要 representative fixture |
| 需要视觉判断 | 是 |
| 会生成 artifact | 是 |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，Origin-specific |
| 是否应单独 commit | 是 |
| 是否 blocker | 是 |

推荐队列：`XPS-BLOCKED-2`。

### IS-D matplotlib visual

涉及 hunk：

- sample display 文本改动。
- tick direction 从 in 改为 out。
- raw/background/component/envelope line width 加粗。
- component fill 改为 `_gradient_fill_between`。
- sample label placement 和 bbox。
- peak guide line 加粗。
- 不再 `set_yticklabels([])`。
- `_save_figure` 路由到结构化输出目录并保存 PNG/PDF/TIF。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 否 |
| 需要 Origin | 不需要 matplotlib 部分，但需要 visual review |
| 需要真实 XPS 数据 | 可先用 synthetic fixture |
| 需要视觉判断 | 是 |
| 会生成 artifact | 是，PNG/PDF/TIF |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，截图/像素/视觉 review |
| 是否应单独 commit | 是 |
| 是否 blocker | 是 |

推荐队列：`XPS-BLOCKED-3`。

### IS-E panel planning / record filtering

涉及 hunk：

- `planned_panels` 中新增 `complete_samples` 但当前未实际使用。
- `_panel_records` 从直接索引 selected 改为 `selected.get` 并过滤 `_record_is_complete(record)[0]`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 可能可以，但需独立 review |
| 需要 Origin | 不需要 |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 不需要 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 部分可用，已有 planned_panels no-artifact test |
| 需要新增 targeted tests | 是，覆盖 incomplete/missing record filtering |
| 是否应单独 commit | 是 |
| 是否 blocker | 暂不 blocker，但不能混入视觉/export hunk |

推荐队列：可作为 `XPS-SAFE-2` 的子项，或单独后续 safe logic commit。

### IS-F quality checks

涉及 hunk：

- `_quality_checks` 签名支持 `output_dirs`。
- 检查 structured subdir 下的 TIF/PNG/PDF。
- 检查 grouped OPJU `xps_in_situ_Bi_Cl_Br.opju`、`xps_in_situ_Cu_W.opju`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 只有 no-artifact path/schema 部分可 |
| 需要 Origin | 若检查 OPJU 存在则需要后续 Origin/artifact GOAL |
| 需要真实 XPS 数据 | 不一定 |
| 需要视觉判断 | artifact quality 需要 |
| 会生成 artifact | 检查本身不生成，但依赖 artifact |
| 可用现有 no-artifact tests 验证 | 否 |
| 需要新增 targeted tests | 是，mock path existence 或 artifact GOAL |
| 是否应单独 commit | 是 |
| 是否 blocker | artifact existence 预期部分 blocked |

推荐队列：path-only 可进 `XPS-SAFE-2`；artifact existence 进 `XPS-BLOCKED-2`。

### IS-G status/report shape

涉及 hunk：

- `origin_status` 从 `origin_file` 转为 `origin_files`。
- success message 改为 grouped editable graph projects。
- message 声明 no final PNG image page。
- mapping report/manifest 写入 `reports/`。

判断：

| 问题 | 判断 |
|---|---|
| 可后续自动处理 | 可以，但需和 artifact handling 分离 |
| 需要 Origin | schema 字段不需要；真实 success 需要 |
| 需要真实 XPS 数据 | 不需要 |
| 需要视觉判断 | 不需要 schema；message 中视觉/Origin 声明需证据 |
| 会生成 artifact | 不应生成 |
| 可用现有 no-artifact tests 验证 | 部分可用 |
| 需要新增 targeted tests | 是 |
| 是否应单独 commit | 是 |
| 是否 blocker | 与 Origin success 行为绑定的内容 blocked |

推荐队列：schema-only 可进 `XPS-SAFE-2`；Origin success 行为进 `XPS-BLOCKED-2`。

## TEST：`tests/test_xps_heterojunction_stacked.py` hunk inventory

### TEST-A no-artifact contract assertions

涉及 hunk：

- `test_run_xps_heterojunction_stacked_with_origin_com_updates_tif_path` 中 fake export 不再创建 preview PNG。
- 断言 `figure["preview_png"] == ""`。
- 可跟随 HJ-A。

判断：可后续自动处理；不需要 Origin、真实数据、视觉判断；不应生成 artifact；需要保持 mock/export fake 范围；适合 `XPS-SAFE-1`。

### TEST-B artifact / visual assertions

涉及 hunk：

- `test_direct_origin_xps_generated_script_compiles` 新增大量 Origin script 字符串断言：ticks、geometry、bold/fontbold/fstyle、TIF width、无 preview save。
- `test_xps_origin_helper_script_receives_plot_policy_fields` 检查 helper script policy 字段。

判断：字符串 compile/contract 不运行 Origin，但多数断言实质服务于 Origin visual style；不能作为视觉验收。可拆出 policy contract 小 hunk，其余默认 blocked。

### TEST-C algorithm assertions

涉及 hunk：

- `test_cu2p_component_colors_match_peak_order_across_samples`。
- `test_cu2p_peak_annotations_are_included` 替代旧的 Cu2p annotations omitted 合同。
- 既有 smooth gradient columns 测试改成比较完整 color list。

判断：算法 hunk；不需要 Origin；需要 synthetic targeted tests；不应混入 artifact/visual commit；先进入 review-only `XPS-SAFE-4`。

### TEST-D report/schema assertions

涉及 hunk：

- dry-run summary 断言新增 `Y-axis tick marks are shown; y-axis numeric labels are hidden`。
- fake export success 后 preview 字段为空字符串。

判断：preview schema 可跟随 HJ-A/HJ-H safe；y tick prose 绑定视觉样式，未有视觉证据前应 blocked 或延后。

## 当前 hunk 分类结论

可作为后续 safe 执行的最小候选：

- HJ-A 中 preview PNG 不再作为 success artifact 的合同子集。
- HJ-B 中纯路径合同子集。
- IS-A 中 run-scoped output path/subdir/report/manifest routing 的非 artifact 子集。
- IS-E 中 panel planning / record filtering 的纯逻辑子集，但需独立 synthetic tests。
- HJ-H / IS-G 中只与已接受合同一致的 schema/report 子集。

必须继续 blocker：

- HJ-C、HJ-E、HJ-F 当前混合 Origin script/visual formatting 部分。
- HJ-G 算法和 annotation 行为，至少先 review-only，不直接提交。
- IS-B、IS-C、IS-D、IS-F artifact existence 部分。
- 任何需要 Origin、OPJU/TIF/PNG/PDF/XLSX、真实数据、截图或视觉判断的 hunk。

## 是否建议继续执行 source hunk split

建议继续，但下一轮应是 source execution 的最小安全切片，而不是一次性提交当前 XPS 大 diff。

优先级建议：

1. `XPS-SAFE-1`：先处理 heterojunction no-artifact / preview PNG contract。
2. `XPS-SAFE-2`：再处理 in-situ run-scoped output path contract，严格 mock 或 path-only。
3. `XPS-SAFE-3`：再处理 report/schema/status shape，避免视觉声明。
4. `XPS-SAFE-4`：算法 peak/color/annotation 先 review-only，再补 targeted synthetic tests。
5. 所有 Origin/visual/artifact/real-data 内容保持 blocked。
