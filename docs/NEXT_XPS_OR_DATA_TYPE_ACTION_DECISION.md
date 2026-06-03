# Next XPS Or Data-Type Action Decision

日期：2026-06-03

## Decision

主推荐：Option C - Output Manual Cleanup Review。

推荐下一步 GOAL：

```text
GOAL: Output Manual Cleanup Review
```

## Current Evidence

当前检查结果：

- HEAD: `abed4e4 docs: summarize xps safe2 in-situ routing split`
- staged: 0
- dirty 总数：278
- `output/outputs` dirty 数：197
- `src/config/tests/scripts/docs` dirty 数：80
- XPS 源码 dirty：否
- XPS 测试 dirty：否
- 当前 XPS 相关 remaining dirty：`docs/CURRENT_RECHECKPOINT_BEFORE_XPS_SOURCE_SPLIT.md`

## Option A: Continue XPS

不推荐作为下一步 source execution。

原因：

- 当前 `src/core/xps_heterojunction.py` 和 `src/core/xps_in_situ.py` 无 dirty diff。
- 当前 XPS 测试无 dirty diff。
- `XPS Algorithmic Peak Color Annotation Review` 当前没有 working-tree source hunk 可处理。
- 剩余 XPS 内容需要 Origin、visual evidence、artifact generation、real data validation 或重新设计 behavior contract。

XPS 可以保留为后续 review-only / planning-only 方向，但不应继续 source split execution。

## Option B: Stop XPS Source Work For Now

成立。

SAFE-1 / SAFE-2 已经吸收可安全提交的 source 子集；剩余 XPS blocker 不应从旧 mixed diff 恢复。若未来继续 XPS，应从当前 HEAD 和新 GOAL 重新开始。

## Option C: Output Manual Cleanup Review

主推荐。

理由：

- 当前 dirty 主要来自 `output/outputs`，计数为 197。
- output/reports 中存在大量历史报告、JSON、Markdown、CSV、XLSX 和 generated output dirty 项。
- 本轮不应自动删除、移动或重命名旧 output；但可以进入 manual cleanup review，先建立清单、分层和用户确认点。
- 该方向不需要运行 Origin，不需要真实数据处理，不需要生成新 artifact，也不需要修改源码。

建议最小范围：

- 只读盘点 `output/` 与 `outputs/` dirty 项。
- 区分 tracked modified、untracked、可能可忽略、可能需归档、必须人工确认的文件。
- 不删除、不移动、不清理。
- 不 stage / commit `output/` 或 `outputs/`。
- 输出人工确认清单和后续 cleanup 计划。

## Option D: Remaining Source Dirty Triage

暂不作为主推荐。

原因：

- `src/config/tests/scripts/docs` dirty 数为 80，但当前 XPS 源码和测试已经干净。
- 非 XPS 的 source/config/tests dirty 是否需要处理，应另开更广的 dirty triage GOAL。
- 在 output dirty 仍占最大比例时，先做 output manual cleanup review 更直接。

## Recommendation

不要继续 `GOAL: XPS Algorithmic Peak Color Annotation Review` 作为源码执行 GOAL。

下一步建议：

```text
GOAL: Output Manual Cleanup Review
```

停止条件建议：

- 如果需要删除、移动或重命名 `output/` / `outputs/`，先停下等待用户确认。
- 如果发现真实数据处理或 artifact generation 需求，另开 GOAL。
- 如果发现 source/config/tests 仍需处理，另开 `GOAL: Remaining Source Dirty Triage`。
