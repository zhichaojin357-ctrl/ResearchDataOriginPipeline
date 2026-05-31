# ResearchDataOriginPipeline 当前完成情况与下一步行动方案

更新时间：2026-05-31  
项目根目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

## 最新更新：重组目录后的路径和分类修正

- 用户已经把 `workspace_data\LL_detection_copy_20260530` 梳理成编号数据类型目录；后续处理必须尊重这个布局。
- 这次梳理的语义不是简单按类型拆文件，而是保留“已有 `.opju` 项目文件 + 对应原始/处理数据”在同一组。
- 已修正 triage：`.opju/.opj/.otpu/.ogw/.ogwu` 保留同目录数据类型，但归为 `AUXILIARY_ONLY`，不进入自动处理队列。
- 已新增可查性分组：每个文件都有 `traceability_group_id`、`traceability_group_path`、`traceability_role`，用于把同一实验组内的原始数据、处理表、导出图和 Origin 项目对应起来。
- 已生成 `output\reports\traceability_groups.json` 和 `output\reports\traceability_groups.md`。
- 已修正 triage：`13_反应产物分析_液相_质谱_核磁` 下的 `质谱`、`核磁` 子目录优先按 MS/NMR scan-only 处理，即使表头像 HPLC。
- 已修正 triage：短英文目录标签 `MS`、`PL` 必须边界匹配，不再把 EIS/XRD 等上层实验目录里的样品名误判为质谱或 PL。
- 最新 triage：1589 files, 18 AUTO_PROCESS, 737 MANUAL_REVIEW, 121 EXCLUDE_INVALID, 58 DUPLICATE_SUPPRESSED, 113 AUXILIARY_ONLY, 525 DEFERRED_TYPE, 17 REFERENCE_ONLY。
- 最新队列仍为 18 个 EIS 数据集；已用 `--no-origin` 重新处理，成功 18，失败 0。
- 最新可查性分组：109 组；其中 37 组含已有 Origin 项目文件，4 组含当前队列文件。

## 0. 路径注意事项

用户正在继续梳理：

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data\LL_detection_copy_20260530`

因此该目录下的文件路径可能继续变化。后续如果需要核对原始数据，应优先参考稳定备份：

`F:\课题\LL\检测`

注意：

- 不要修改、移动、删除、重命名 F 盘原始备份文件。
- 后续处理应基于工作区副本或重新复制出的工作副本。
- 如果 workspace copy 的路径已经被用户整理过，先重新 scan/triage，再继续处理。

## 1. 已完成的目录和项目整理

已将项目放在：

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

当前主工作区是：

`D:\Codex Project\科研数据处理`

当前可见目录包括：

- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- `D:\Codex Project\科研数据处理\数据`
- `D:\Codex Project\科研数据处理\指令归档`
- `D:\Codex Project\科研数据处理\Jade_FindIt_PDF数据库提取`
- `D:\Codex Project\科研数据处理\Jade程序文件`

## 2. 已完成的指令归档

已建立指令归档目录：

`D:\Codex Project\科研数据处理\指令归档`

当前已确认存在的长指令 Markdown 文件：

- `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_goal_init_instruction_20260530.md`
- `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_phase1_1_real_data_intake_hardening_instruction_20260530.md`
- `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_phase1_2_mixed_data_triage_instruction_20260530.md`
- `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_origin_opju_plotting_skill_update_instruction_20260530.md`
- `D:\Codex Project\科研数据处理\指令归档\README.md`

后续每次用户提供新的大段任务指令，都应继续先转存为 Markdown，再执行。

## 3. 已完成的多智能体设置

项目中已设置：

- `max_threads = 5`
- `max_depth = 1`

含义：

- 需要时可以自动启用多智能体并行构建、测试、审查。
- 最多同时使用 5 个智能体。
- 不允许子智能体继续嵌套开子智能体。
- 不要让多个写入型智能体同时修改同一个文件范围。

## 4. 已完成的项目骨架

项目已经建立以下主要结构：

- CLI 入口：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\run.py`
- 主源码目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\src`
- 配置目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\config`
- 文档目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\docs`
- 测试目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\tests`
- 输出目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output`
- 工作区数据目录：`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data`

已建立的主要配置：

- `config\default.yaml`
- `config\processor_registry.yaml`
- `config\data_selection_rules.yaml`
- `config\manual_overrides.yaml`
- `config\claim_policy.yaml`
- `config\plot_style.yaml`
- `config\sample_registry.yaml`

## 5. 已完成的 CLI 能力

当前 CLI 已支持：

- `scan`
- `triage`
- `process`
- `deps-audit`
- `origin-test`
- `validate`

`process` 已支持：

- `--no-origin`
- `--only-type`
- `--only-folder`
- `--fail-fast`
- `--force`
- `--from-queue`
- `--auto-select`
- `--include-ambiguous`

队列处理规则：

- 使用 `--from-queue` 时默认 no-Origin。
- 会校验 source hash。
- stale 或 missing hash queue item 会记录为 `queue_validation` failure，不直接处理。
- 输出文件名包含 queue-id 后缀，避免同名文件覆盖。

## 6. 已完成的真实数据复制和保护

用户给出的路径是：

`F:\课题\LL\检测中`

项目状态记录显示该请求路径当时不存在，实际使用了 F 盘 LL 检测相关目录作为来源，并复制到工作区副本：

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data\LL_detection_copy_20260530`

复制原则：

- F 盘原始数据只读访问。
- 没有修改、移动、删除、重命名原始数据。
- 后续处理基于 workspace copy。

复制校验记录：

- 原始复制批次：1582 个文件。
- 字节数：2642973440。
- source 与 workspace copy 数量和大小一致。

当前 `workspace_data\LL_detection_copy_20260530` 目录已经被用户重新梳理，现场统计为：

- 1589 个文件。
- 2643322364 字节。

## 7. 已生成的数据副本 manifest

已生成：

- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data\manifests\LL_detection_copy_20260530_summary.json`
- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\workspace_data\manifests\LL_detection_copy_20260530_files.csv`

## 8. 已完成 Phase 1.1

Phase 1.1 已完成：

- no-Origin 数据处理路径。
- scoped processing filters。
- batch failure isolation。
- raw-data write guards。
- synthetic fixtures。
- intake docs。
- compatibility matrix。
- processing summary。
- review dashboard。
- 回归测试。

## 9. 已完成 Phase 1.2-Mixed 真实数据 triage

已实现 file-level triage，可对混乱真实数据逐文件判断，并生成队列、歧义文件、排除文件、重复文件、hash 索引和 dashboard。

最新 triage 结果：

- Total files: 1589
- AUTO_PROCESS: 18
- MANUAL_REVIEW: 737
- EXCLUDE_INVALID: 121
- DUPLICATE_SUPPRESSED: 58
- AUXILIARY_ONLY: 113
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17

已生成的 triage 报告：

- `output\reports\data_triage_manifest.json`
- `output\reports\data_triage_report.md`
- `output\reports\processing_queue.json`
- `output\reports\processing_queue.md`
- `output\reports\ambiguous_files.md`
- `output\reports\excluded_files.md`
- `output\reports\duplicate_candidates.md`
- `output\reports\source_hash_index.json`
- `output\reports\traceability_groups.json`
- `output\reports\traceability_groups.md`
- `output\review_dashboard\triage_index.md`

## 10. 已完成 18 个高置信 EIS 数据集处理

当前 `processing_queue` 处理的是 18 个 EIS 数据集。

处理结果：

- Total datasets: 18
- Success count: 18
- Failure count: 0
- Processor: EIS
- Metadata files: 18
- Processed CSV files: 18
- no-Origin 模式下未生成 Origin 图，这符合当前保护规则。

输出目录：

- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\processed_data\EIS`
- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\metadata\EIS`

## 11. 已完成项目验证

项目状态记录中的验证结果：

- `D:\Python\python.exe -m pytest`：73 passed，2 个 openpyxl deprecation warnings。
- `D:\Python\python.exe run.py deps-audit`：exit 0。
- `D:\Python\python.exe run.py validate`：exit 0。
- `D:\Python\python.exe run.py scan --config config/default.yaml`：exit 0。
- `D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain`：exit 0。
- `D:\Python\python.exe run.py process --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --from-queue output\reports\processing_queue.json --force`：exit 0。

## 12. 已完成 dependency audit

已确认可用依赖：

- `pandas`
- `numpy`
- `scipy`
- `openpyxl`
- `yaml`
- `pybaselines`
- `originpro`
- `win32com`
- `impedance`
- `pymzml`

缺失但属于 optional warning 的依赖：

- `ixdat`
- `galvani`
- `eclabfiles`
- `pygaps`
- `lmfitxps`
- `ramanspy`
- `rampy`
- `spectrochempy`
- `hplc`
- `rainbow`
- `pyteomics`

## 13. 已完成 validation report

当前文件：

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\reports\validation_report.md`

关键结果：

- Dependency audit: pass
- Origin callability: pass
- Required output directories: pass
- Required config files: pass
- Processor registry entries: 19
- Phase 1 supported entries: 14
- Processor registry required fields: pass
- PPT forbidden paths: pass
- Forbidden presentation artifacts: pass
- Kinetics processor paths: pass
- TIF export config: pass
- Origin contract Graph4 reference page: pass
- Origin contract Origin.Application automation: pass
- Origin contract avoid Origin.ApplicationSI: pass
- Origin contract PNG preview inspection: pass
- Origin contract explicit bold legend rows: pass
- Origin contract line width 3: pass
- max_threads = 5
- max_depth = 1

## 14. 已完成 method cards

已建立多种数据类型的方法卡：

- `docs\method_cards\xrd.md`
- `docs\method_cards\xps.md`
- `docs\method_cards\uvvis_drs.md`
- `docs\method_cards\eis.md`
- `docs\method_cards\photocurrent.md`
- `docs\method_cards\photocurrent_response.md`
- `docs\method_cards\bet.md`
- `docs\method_cards\ftir.md`
- `docs\method_cards\raman.md`
- `docs\method_cards\epr.md`
- `docs\method_cards\mott_schottky.md`
- `docs\method_cards\hplc_lc_exported_data.md`
- `docs\method_cards\reaction_condition_screening.md`

## 15. 已完成 scan-only/deferred 数据说明

已对暂不自动处理的数据类型建立说明：

- `docs\data_format_notes\nmr_scan_only.md`
- `docs\data_format_notes\ms_scan_only.md`
- `docs\data_format_notes\sem_scan_only.md`
- `docs\data_format_notes\tem_scan_only.md`
- `docs\data_format_notes\kinetics_reference_literature.md`

当前规则：

- SEM/TEM/NMR/MS 暂时 scan-only。
- kinetics/reference folders 只作为 reference_literature。

## 16. 已完成 OPJU 示例文件盘点

已扫描 `F:\课题\LL` 和 `F:\课题\LL\检测` 下已有处理好的 OPJU 文件，并生成：

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\reports\opju_inventory_20260530.csv`

盘点到的 OPJU 类型包括：

- Energy level diagram
- BET
- EPR
- PL / excitation-emission
- XPS
- XRD
- UV-vis DRS / Tauc
- Photocurrent
- Reaction screening / calibration
- FTIR

这些文件只作为数据类型和绘图风格参考，没有原地修改。

## 17. 已完成 Origin 全局绘图默认规则确认

当前 Origin 绘图全局默认风格来自用户默认 `Graph4` 参考样式。

已确认并缓存的核心参数：

- Page width: `6432`
- Page height: `4923`
- Layer left: `17.89`
- Layer top: `11.6`
- Layer width: `68.19`
- Layer height: `71.81`
- X range: `5..80`
- X major step: `10`
- Y range: `-6000..19000`
- Y major step: `5000`
- Axis thickness: `3`
- X tick label size: `28`
- Y tick label size: `36`
- X/Y title size: `36`
- Sample curve line width: `3`

## 18. 已更新 `origin-plotting` skill

主文件：

`D:\CodexData\.codex\skills\origin-plotting\SKILL.md`

已改成：

- 默认使用硬编码 `Graph4` 缓存样式。
- 默认不再每次读取参考 OPJU。
- 只有用户明确要求刷新模板、传入 `-ReferenceOpju` 或 `-RefreshReferenceStyle` 时才读取参考 OPJU。
- 画布尺寸、X/Y 轴框长度、字体、线宽、图例位置等固定遵从缓存模板。
- 数据类型规则只允许改变科学表达内容，例如坐标范围、log/linear、Y 轴数字刻度是否显示、类别标签、注释等。
- 不能因为数据类型或标签拥挤而改变画布尺寸、轴框尺寸、线宽、标题字号、tick-label 字号。

## 19. 已完成各数据类型 Y 轴刻度规则

已写入 skill：

- XRD、XPS、PL、FTIR、Raman、EPR：归一化、堆叠或 offset 时可隐藏 Y 数字刻度，但保留 Y 轴标题和刻度线。
- UV-vis、Tauc、EIS、photocurrent、Mott-Schottky、BET、HPLC/LC、calibration curves、反应筛选柱状图：保留 Y 数字刻度。
- TRPL：非 offset 或 semilog 衰减图保留 Y 数字刻度，只有刻意 offset 时隐藏。
- Energy-level diagrams：定量能级轴显示数值，纯示意图不强制坐标刻度。
- SEM/TEM/EDS：不用图坐标轴刻度，使用比例尺和标签。

## 20. 已完成 calibration curve 专项规则更新

已写入：

- X/Y 轴标题都必须 Arial bold size `36`。
- Y 轴标题也必须 36 号。
- 不允许为了避免重叠而缩小缓存 tick-label 字号。
- 重叠只能用 offset、紧凑数字格式、页面空白、允许的 tick-label visibility 或用户明确同意的 layout change 解决。
- 页面尺寸、主 layer 几何、X/Y 轴框长度只有用户明确要求 resize/layout change 时才可改。

## 21. 已更新 Origin helper 脚本

脚本：

`D:\CodexData\.codex\skills\origin-plotting\scripts\origin_plot_from_template.ps1`

关键改动：

- 增加 `-RefreshReferenceStyle`。
- 增加 `-KeepIntermediate`。
- 默认走缓存样式，不读取参考 OPJU。
- 默认缓存模式不创建 `origin_templates`。
- 只有刷新或显式参考模板时才创建 run-unique 临时目录。
- 清理只删除本次运行创建的临时目录，不会误删旧目录。
- 修正页面尺寸写入：先关闭保持宽高比，再写入 `6432 x 4923`。
- 支持无头运行，避免影响用户使用电脑。

## 22. 已更新 Origin helper 回归测试

脚本：

`D:\CodexData\.codex\skills\origin-plotting\scripts\test_origin_plot_from_template.ps1`

当前测试：

- 默认 `-Headless`。
- 默认不读取参考 OPJU。
- 检查缓存画布尺寸。
- 检查主 layer 几何。
- 检查轴范围、tick direction。
- 检查 X/Y 标题 Arial bold size `36`。
- 检查 tick label 字体和字号。
- 检查图例文本是否是显式 bold rows。
- 检查没有旧模板残留。
- 检查默认缓存模式不会创建 `origin_templates`。

验证结果：

- PowerShell AST 解析：`PARSE_OK`
- 无头 Origin helper 回归测试：`PASS origin plotting helper regression`

## 23. 已完成 HPLC calibration Origin 图

当前保留的最终 HPLC OPJU：

`D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\HPLC_calibration_curves_20260530_230503.opju`

当前保留的最终预览图：

- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\preview\Cal_Sulfide_20260530_230503.png`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\preview\Cal_Sulfone_20260530_230503.png`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\preview\Cal_Sulfoxide_20260530_230503.png`

当前保留的数据和脚本：

- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\data\final_calibration_data.tsv`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\data\Sulfide_plot_data.tsv`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\data\Sulfone_plot_data.tsv`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\data\Sulfoxide_plot_data.tsv`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\plot_hplc_calibration_origin.ps1`
- `D:\Codex Project\科研数据处理\数据\26.5.30\HPLC_calibration_origin\origin_run_log.txt`

## 24. 已保留已有 XRD 绘图成果

当前可见 XRD 输出包括：

- `D:\Codex Project\科研数据处理\数据\26.5.28\XRD\XRD_grouped_final_clean.opju`
- `D:\Codex Project\科研数据处理\数据\26.5.29\XRD\XRD_BMO_qiu_CBB_origin_final2.opju`

旧中间模板目录已清理，但最终 OPJU 和最终预览未删除。

## 25. 已保留已有 BET 绘图成果

当前可见 BET 输出包括：

- `D:\Codex Project\科研数据处理\数据\26.5.29\BET\BET_N2_isotherm_and_pore_distribution_graph4_pointline_20260529_214645.opju`
- `D:\Codex Project\科研数据处理\数据\26.5.29\BET\processed_origin\BET_N2_Isotherm_graph4_pointline_20260529_214645.png`
- `D:\Codex Project\科研数据处理\数据\26.5.29\BET\processed_origin\BET_Pore_Distribution_graph4_pointline_20260529_214645.png`

BET 的 `.otpu` 临时模板已清理。

## 26. 已完成构建/测试无用文件清理

已清理确定无用的产物，包括：

- 旧技能测试目录。
- smoke test OPJU。
- smoke test PNG/TIF。
- smoke test 输入数据。
- `origin_templates` 中间目录。
- `.otpu` 临时模板。
- HPLC 校准旧草稿 OPJU。
- HPLC 校准旧预览图。

清理统计：

- 64 项。
- 约 9.6 MB。

没有删除：

- 原始数据。
- F 盘示例 OPJU。
- 最终 OPJU。
- 最终预览图。
- 处理后数据。
- 报告文件。

## 27. 已完成 Origin 环境清理

用户明确允许清理所有 Origin 环境后，已清理 Origin/Origin64 进程和本轮测试临时目录。

当前确认：

- `Origin*` 进程残留：0。
- 已删除测试临时目录：`F:\Codex_Temp\codex_origin_plotting_skill_test`。

## 28. 已完成代码审查和修正

并行审查发现并修正：

- skill 文案不应允许为了重叠缩小 tick-label 字号。
- skill 文案不应允许为了当前图随意调整页面/轴框几何。
- helper 脚本不应删除固定 `origin_templates`，应只删除本次运行创建的 run-unique 临时目录。

修正后已通过无头回归测试。

## 29. 当前还没有完成的内容

还没有完成：

- 823 个 MANUAL_REVIEW 文件的人工整理/提升。
- 498 个 DEFERRED_TYPE 文件的后续处理策略。
- 全部数据类型的最终 Origin OPJU/TIF/PNG 生成。
- 对所有非 EIS 数据类型的 no-Origin 自动处理。
- 对所有 Origin 图进行最终图像级人工审查。

当前已经完成的是：项目骨架、指令归档、真实数据只读复制、file-level triage、18 个 EIS 队列 no-Origin 处理、项目验证、OPJU 示例盘点、Origin plotting skill 改造、HPLC calibration 最终 OPJU/预览、清理与验证。

## 30. 下一步行动方案

### 30.1 先重新确认 workspace 路径

因为用户正在整理：

`workspace_data\LL_detection_copy_20260530`

路径可能变化。下一步开始前先运行：

```powershell
D:\Python\python.exe run.py scan --config config/default.yaml
```

如果用户已经大量整理文件路径，应重新执行 triage：

```powershell
D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh
```

如需核对原始稳定来源，参考：

`F:\课题\LL\检测`

### 30.2 先处理人工复核队列

重点看：

- `output\reports\ambiguous_files.md`
- `output\reports\data_triage_report.md`
- `output\reports\processing_queue.md`
- `output\reports\excluded_files.md`
- `output\reports\duplicate_candidates.md`

目标：

- 判断哪些非 EIS 文件可以通过 manual override 提升为下一批可处理队列。
- 不要直接处理低置信文件。
- 不要处理路径已经变化但 hash 未确认的队列项。

### 30.3 下一批优先 no-Origin 数据处理

建议顺序：

1. 复核已处理的 18 个 EIS 结果。
2. Photocurrent / photocurrent response。
3. UV-vis DRS / Tauc。
4. XPS。
5. PL / TRPL。
6. FTIR / Raman / EPR。
7. BET / Mott-Schottky。
8. Reaction screening / calibration。
9. HPLC/LC。

每一类先生成：

- processed CSV。
- metadata JSON。
- processing summary。
- failure report。

确认无误后再生成 Origin 图。

### 30.4 Origin 绘图必须遵守当前 skill

后续 Origin 绘图使用：

`D:\CodexData\.codex\skills\origin-plotting`

要求：

- 默认硬编码 `Graph4` 缓存样式。
- 不要每次读取模板 OPJU。
- 优先无头运行。
- 必须导出 PNG 预览。
- 必须检查旧模板文字残留。
- 必须保持画布尺寸、X/Y 轴框长度、字体、线宽等缓存样式不变。
- 数据类型只能改变科学呈现策略，例如 Y 数字刻度是否显示。

### 30.5 每完成一批就审查和清理

每批完成后执行：

- 项目测试。
- 输出文件存在性检查。
- PNG 预览检查。
- skill/配置一致性检查。
- 清理确定无用的临时目录、`.otpu`、失败草稿。
- 保留最终 OPJU、最终预览、processed data、metadata、报告。

### 30.6 持续遵守限制

后续继续保持：

- 最多 5 个智能体。
- 不嵌套开智能体。
- routine tests 不启动可见 Origin。
- 不碰 F 盘原始数据。
- 不做 PPT。
- 不做 kinetics processor。
- SEM/TEM/NMR/MS 暂时 scan-only。
- 每个新大段指令都继续保存为 Markdown。
