# XPS Source Blocked Hunks

日期：2026-06-03

本文件列出当前 XPS 大 diff 中不得进入 safe source commit 的 hunk。blocked 的含义是：当前没有足够证据在 no-Origin/no-artifact/source-contract 目标中接受这些改动；不是说这些改动一定错误。

## BLOCKED-HJ-ORIGIN

文件：`src/core/xps_heterojunction.py`

范围：

- direct Origin renderer script 中 page/layer geometry。
- axis tick、label、second axis、line width、bold/fontbold/fstyle。
- TIF export width 变化。
- preview PNG export 移除后的真实 Origin export 行为。
- `_build_xps_origin_script` 生成的 Origin policy 和 visual field 实际效果。

阻塞原因：

- 需要 Origin。
- 需要 OPJU/TIF/PNG artifact。
- 需要视觉证据。
- compile 或字符串断言不能证明 Origin 渲染效果。

后续需要：

- Origin-specific GOAL。
- synthetic Origin smoke。
- screenshot/visual review。
- artifact existence 和 DPI/size 检查。

## BLOCKED-HJ-GRADIENT-STYLE

文件：`src/core/xps_heterojunction.py`

范围：

- native gradient fill helper。
- layered fill columns 改为 single upper/lower。
- component/measured/background/envelope line width 和 fill style。

阻塞原因：

- 视觉语义变化大。
- 需要 Origin 渲染证据。
- 不应进入 no-artifact contract commit。

后续需要：

- Origin visual GOAL。
- 对比旧/新 rendering。
- 明确视觉验收标准。

## BLOCKED-HJ-LABEL-CHEMISTRY

文件：`src/core/xps_heterojunction.py`

范围：

- sample display 从 Unicode 下标改为 Origin escape 文本。
- bold multiline label helper。
- chemical subscript helper。
- peak/sample label 的 Origin text formatting。

阻塞原因：

- 当前 helper 与 Origin script 混在一起。
- 需要 Origin 显示验证。
- 不能用字符串存在性证明视觉正确。

后续需要：

- 先拆纯 helper unit tests，或进入 Origin visual GOAL。

## BLOCKED-HJ-ALGORITHM

文件：`src/core/xps_heterojunction.py`

范围：

- Cu2p visual binding-energy windows。
- component peak binding helper。
- component color grouping。
- Cu2p annotations 从 omitted 变为 included。
- Cu2p satellite assignment windows。
- major tick helper / tick density变化。

阻塞原因：

- 这是算法/annotation 行为变化，不是单纯 artifact contract。
- 需要 synthetic targeted tests 和人工 review。
- 颜色和 annotation 的最终呈现仍需视觉证据。

后续需要：

- review-only GOAL。
- targeted synthetic tests。
- 明确不生成价态/电子转移/S-scheme/机制结论。

## BLOCKED-HJ-REPORT-VISUAL-PROSE

文件：`src/core/xps_heterojunction.py`

范围：

- Origin native Gradient Fill prose。
- y-axis tick marks shown 的视觉描述。
- visual binding-energy windows 的报告描述。

阻塞原因：

- 文本声明依赖未验收的视觉/算法 hunk。
- 不能早于对应 source behavior 和证据提交。

后续需要：

- 跟随已验收 source hunk 单独更新 report/schema。

## BLOCKED-IS-ARTIFACT

文件：`src/core/xps_in_situ.py`

范围：

- `_ensure_tif_600_dpi`。
- grouped OPJU projects。
- per-panel TIF/PNG/PDF export。
- removal of final PNG image page。
- `origin_files` success behavior。

阻塞原因：

- 会生成 OPJU/TIF/PNG/PDF。
- 需要 Origin。
- 需要 artifact/visual evidence。

后续需要：

- Origin/artifact GOAL。
- run-scoped artifact inventory。
- visual review。

## BLOCKED-IS-ORIGIN-STRUCTURE

文件：`src/core/xps_in_situ.py`

范围：

- `ORIGIN_PROJECT_GROUPS`。
- per-panel graph creation。
- per-record worksheets。
- `_origin_record_columns`。
- counts headers。
- sample offsets。
- Origin panel labels。
- Origin style validation file。
- Origin color helpers。

阻塞原因：

- Origin COM 行为大范围变化。
- 当前没有 Origin evidence。
- 当前不允许生成 validation txt 之外的 artifact；本轮也不应生成任何 artifact。

后续需要：

- Origin-specific execution GOAL。
- 真实或 synthetic fixture。
- OPJU inspection / screenshot-backed evidence。

## BLOCKED-IS-MATPLOTLIB-VISUAL

文件：`src/core/xps_in_situ.py`

范围：

- `_gradient_fill_between`。
- line width 加粗。
- tick direction。
- sample label position/bbox。
- peak guide line。
- y tick label visibility。
- save PNG/PDF/TIF 到 structured subdirs。

阻塞原因：

- 会生成图像 artifact。
- 需要视觉判断。
- 不属于 no-artifact/source-contract safe commit。

后续需要：

- visual QA GOAL。
- synthetic figure generation in temp output。
- screenshot or rendered image review。

## BLOCKED-IS-QUALITY-ARTIFACT-CHECKS

文件：`src/core/xps_in_situ.py`

范围：

- `_quality_checks` 对 grouped OPJU、TIF/PNG/PDF 的 existence / size / DPI 检查。

阻塞原因：

- 虽然检查函数本身不生成 artifact，但它依赖 artifact 生成结果。
- 当前不允许生成或处理 artifacts。

后续需要：

- 跟随 Origin/artifact GOAL。

## BLOCKED-TEST-VISUAL-ORIGIN

文件：`tests/test_xps_heterojunction_stacked.py`

范围：

- Origin script geometry/tick/label/style 字符串断言。
- TIF width / no preview save 字符串断言。
- policy field 字符串断言中与视觉效果绑定的部分。

阻塞原因：

- 这些测试可证明字符串包含字段，但不能证明 Origin 渲染正确。
- 不应把它们作为视觉验收证据。

后续需要：

- 分离 policy contract tests 与 visual acceptance tests。
- visual acceptance 必须在 Origin/visual GOAL 中完成。
