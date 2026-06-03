# XPS Blocked Hunks Preservation Status

日期：2026-06-03

## 1. 曾经存在的 blocked XPS hunks

根据 `docs/XPS_SOURCE_HUNK_SPLIT_PREFLIGHT.md`、`docs/XPS_SOURCE_HUNK_EXECUTION_QUEUE.md` 和 `docs/XPS_SOURCE_BLOCKED_HUNKS.md`，pre-split 阶段记录过以下 blocked hunk 类别：

- Heterojunction Origin script/export visual style：Origin page/layer geometry、axis/tick/label/style、TIF export width、direct Origin renderer script。
- Heterojunction native gradient / visual style：native gradient fill、fill columns、line width、component/background/envelope style。
- Heterojunction label / chemistry formatting：Origin escape text、bold multiline labels、chemical subscript helpers、peak/sample label formatting。
- Heterojunction algorithm / annotation：Cu2p component color grouping、component peak binding、Cu2p annotations、satellite windows、tick density helpers。
- Heterojunction report visual prose：visual binding-energy windows、native Gradient Fill prose、y-axis tick prose。
- In-situ artifact handling：grouped OPJU projects、per-panel TIF/PNG/PDF export、final PNG image page behavior、`origin_files` success behavior。
- In-situ Origin project structure：per-panel Origin graphs、per-record worksheets、Origin columns/headers/offsets/labels/style validation/color helpers。
- In-situ matplotlib visual style：gradient fill、line width、sample label placement、peak guide lines、tick direction、PNG/PDF/TIF save behavior。
- In-situ artifact quality checks：grouped OPJU/TIF/PNG/PDF existence, size, and DPI checks。
- Visual/Origin test assertions：string-level Origin script assertions that do not prove rendered visual correctness。
- Real XPS data validation and any automatic valence-state, electron-transfer, heterojunction-mechanism, carrier-path, or S-scheme conclusion。

## 2. 已通过 SAFE-1 / SAFE-2 安全吸收的内容

SAFE-1 已吸收的子集：

- Commit: `1ae381f xps: relax heterojunction preview artifact success contract`
- `src/core/xps_heterojunction.py` 中的 heterojunction preview PNG success-artifact contract hunk。
- `TASK_SUBDIRS` 中移除 `figures_preview`。
- Origin COM success artifact requirement 从 OPJU/TIF/preview PNG 收窄为 OPJU/TIF。
- COM success result 中 `preview_png` 为 `None`。
- `tests/test_xps_heterojunction_stacked.py` 中的 fake export / preview schema contract test。

SAFE-2 已吸收的子集：

- Commit: `5b9c823 xps: route in-situ output paths without artifacts`
- `src/core/xps_in_situ.py` 中的 run-scoped output path / structured subdir / report-table-manifest path contract。
- 新增 `OUTPUT_SUBDIRS` 和 `_output_subdirs(output_dir)`。
- peak summary 路由到 `tables/peak_positions_summary.xlsx`。
- mapping report 和 manifest 路由到 `reports/`。
- manifest 新增 `output_dirs` schema。
- `tests/test_xps_in_situ_output_routing.py` 使用 `tmp_path` 和 mocked writers 验证 path contract，不生成项目 artifacts。

相关总结：

- `302b490 docs: summarize xps safe1 no-artifact split`
- `abed4e4 docs: summarize xps safe2 in-situ routing split`

## 3. 没有进入源码的内容

以下内容当前没有进入 working tree 源码 diff，也没有作为 SAFE-1 / SAFE-2 的源码提交被接受：

- Origin script/export visual style。
- Origin COM execution behavior beyond the accepted no-artifact contract。
- OPJU/TIF/PNG/PDF/XLSX artifact generation。
- grouped OPJU project structure。
- in-situ per-panel graph/worksheet Origin project design。
- matplotlib visual style / gradient / tick / label changes。
- artifact existence / DPI / size quality checks。
- Cu2p component color grouping and peak annotation behavior。
- label/chemistry Origin visual formatting。
- report prose that claims unverified visual behavior。
- real XPS data validation and scientific interpretation claims。

## 4. 文档形式保留的内容

Blocked hunk 的描述已通过以下文档保留：

- `docs/XPS_SOURCE_BLOCKED_HUNKS.md`
- `docs/XPS_SOURCE_HUNK_EXECUTION_QUEUE.md`
- `docs/XPS_SOURCE_HUNK_SPLIT_PREFLIGHT.md`
- `docs/XPS_ARTIFACT_VISUAL_BLOCKERS.md`
- `docs/XPS_NO_ARTIFACT_GOAL_SUMMARY.md`
- `docs/XPS_SAFE1_GOAL_SUMMARY.md`
- `docs/XPS_SAFE2_GOAL_SUMMARY.md`

`docs/CURRENT_RECHECKPOINT_BEFORE_XPS_SOURCE_SPLIT.md` 是 SAFE-1 / SAFE-2 之前生成的历史 checkpoint；其中 HEAD 和 dirty counts 是 pre-split snapshot，不代表当前 post-split 状态。

## 5. patch 形式保留的内容

当前 `patches/` 下只发现：

- `patches/xps_in_situ_root_drift.patch`

该 patch 的检查结果：

- `git apply --check patches/xps_in_situ_root_drift.patch` 失败。
- 失败原因：patch 目标文件 `scripts/build_xps_in_situ_20260506.py` 当前不存在。
- patch 内容涉及脚本入口 root/output-dir 处理，不是当前 `src/core/xps_heterojunction.py` 或 `src/core/xps_in_situ.py` 的 blocked core-source hunk。

结论：当前没有可直接应用的 patch 保存 pre-split XPS core/source blocked hunks。除 SAFE-1 / SAFE-2 已提交内容外，其余 blocked hunk 只以文档描述形式保留。

## 6. blocked hunk 是否已从 working tree 消失

是。

当前检查：

```powershell
git diff --name-status -- src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py tests/test_xps_in_situ.py tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ_output_routing.py
git diff --stat -- src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py tests/test_xps_in_situ.py tests/test_xps_no_artifact_contracts.py tests/test_xps_in_situ_output_routing.py
```

结果均无输出。当前 XPS 源码和 XPS 测试没有 unstaged diff。

## 7. 是否可视为 intentionally rejected unverified AI-generated change

除 SAFE-1 / SAFE-2 已提交的安全子集外，其余 pre-split mixed hunks 可以视为 intentionally not accepted / intentionally rejected unverified changes。

理由：

- 它们曾经被明确记录为 Origin、visual、artifact、algorithm、real-data blocker。
- 当前不在 working tree。
- 当前没有可应用 patch 保存这些 source hunks。
- 没有 Origin、artifact、visual、real-data 证据支持恢复它们。

## 8. 是否有必要尝试恢复

不建议恢复。

如果未来要重新进入这些方向，应从当前 HEAD、现有 blocker 文档、明确的新 GOAL 和新的 targeted tests / visual evidence 出发重新设计，不应按旧 mixed diff 或不可应用 patch 恢复源码。

## 9. 是否建议继续保留 blocked 状态

是。

继续 blocked 的范围：

- Origin execution。
- OPJU/TIF/PNG/PDF/XLSX artifact generation。
- visual/style acceptance。
- Cu2p algorithm / peak color / annotation behavior。
- real XPS data validation。
- scientific interpretation claims。

当前不建议继续 source hunk split execution；建议转入下一步决策文档中指定的非 XPS source-repair GOAL。
