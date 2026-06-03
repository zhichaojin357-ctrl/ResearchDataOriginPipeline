# Agent Rules

本项目 Phase 1 仅做科研表征数据扫描、处理、Origin 绘图、.opju 保存、.tif 导出、metadata/report/manual-check 生成。

项目级执行方向：
- 正式入口优先使用 `run.py` 与 `src/cli.py`；不要新增或优先走重复入口来绕过现有流程。
- 面对真实数据任务时，必须先调用项目现有正式子命令和正式模块，例如 `scan`、`triage`、`process`、`origin-batch`、`reviewed-queue`、`auto-queue`、`xps-heterojunction-stacked`、`readiness`、`validate`。
- 如果项目脚本在处理过程中报错、识别错误、绘图不合格、导出失败、缺少 reader/processor/plotter/exporter 或 dry-run 信息不足，不得绕过项目直接交付结果。
- 正确闭环是：先用项目正式入口执行 -> 记录失败 -> 定位到正式代码、配置、模板或测试中的缺陷 -> 修复项目本身 -> 重新运行正式入口验证。
- 可以写临时脚本做诊断、复现、格式检查或算法对比，但临时脚本不能作为最终处理方式；其中有效逻辑必须并入正式模块后，再由项目正式入口重新产出结果。
- 最终结果必须来自项目脚本和正式模块，不能由一次性脚本、大模型手工整理或绕过 reader/processor/plotter/exporter 的方式直接生成。
- 每次修复后，至少重新执行相关 smoke test、对应 dry-run 和正式入口命令，再宣布问题已解决。

硬性规则：
- 不修改、覆盖、删除、移动 `input/raw_data/` 中任何原始数据。
- 所有运行输出必须写入 `output/`。
- 不写 PPT 功能，不创建 `src/ppt/`、`templates/ppt/`、`ppt_layout.yaml`、`slide_plan.json` 或 `presentation.pptx`。
- 不创建 kinetics processor，不把“动力学”文件夹当作实验动力学数据处理。
- “动力学”必须按 `reference_literature` 处理，仅扫描登记。
- 所有 processor 必须输出 `metadata.json`。
- 高风险科研结论必须标记 `manual_check_required`，不得自动证明机理、异质结类型、电子转移方向、价态、自由基、晶面或 LC-MS 产物。
- OriginPro 已安装；只检测调用能力，不安装 OriginPro。
- 每个成功处理的数据集必须保存 `.opju` 并导出 600 dpi `.tif`。
