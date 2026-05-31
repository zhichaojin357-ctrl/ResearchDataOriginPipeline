# Agent Rules

本项目 Phase 1 仅做科研表征数据扫描、处理、Origin 绘图、.opju 保存、.tif 导出、metadata/report/manual-check 生成。

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