# ResearchDataOriginPipeline Agent Rules

## 1. 项目定位与事实来源

本仓库是持续维护的科研表征数据处理与 OriginPro 出图管线，不是旧版 Phase 1 工作区。不要用早期 Phase 1、V4/V5、旧 MEGA 计划或 `docs/agent_reports/` 中的历史报告替代当前状态。

判断项目现状时按以下优先级取证：

1. 当前工作区代码、测试和 `git` 状态。
2. `README.md`、`docs/CURRENT_STATUS.md`、`docs/PROJECT_INDEX.md`、`docs/REAL_DATA_INTAKE_GUIDE.md`。
3. `config/processor_registry.yaml`、`config/claim_policy.yaml`、`config/plot_style.yaml` 和正式方法卡。
4. 最近提交、最近正式运行报告和最近项目对话。
5. 历史文档只用于解释遗留设计，不作为当前验收依据。

若文档、配置和代码不一致，先通过正式入口与测试确认实际行为，再修正过时文档或配置；不得为了让文档“看起来一致”而掩盖真实缺陷。

## 2. 当前维护范围

正式链路包括：

- 扫描、分类、triage、自动队列和人工审核队列。
- 支持数据的表格读取、规范化处理、`metadata.json`、报告和人工检查项。
- OriginPro 作图、`.opju` 保存、600 dpi `.tif` 导出和 PNG 预览。
- XPS、XRD、EPR 等专用产品流程。
- JEOL EPR 原始 `cAcqu` 解码。
- Agilent OpenLab HPLC/LC `.rslt/.dx/.rx` 原始数据到 Excel 的专用导出。

当前维护的数据入口以注册表中 `supported_in_pipeline=true` 的条目为准，现有类型包括：

- photocurrent
- photocurrent_response
- BET
- EPR
- PL
- XPS
- XRD
- UV-vis DRS
- reaction_condition_screening
- FTIR
- Raman
- Mott-Schottky
- EIS
- HPLC/LC exported data
- HPLC/LC OpenLab raw data

SEM、TEM、NMR、MS 和“动力学”文件夹当前仍是扫描/登记类型：

- 不自动进入处理器或 Origin。
- “动力学”必须按 `reference_literature` 处理，不得解释为实验动力学数据。
- 未经用户明确扩展范围、实现正式 reader/processor、补齐测试和验收，不得把扫描型类型改成可处理类型。

## 3. 正式入口与处理闭环

正式入口始终是：

```text
run.py -> src/cli.py -> src/core / src/processors / src/origin
```

必须优先使用现有正式子命令，例如：

- `scan`
- `triage`
- `auto-queue`
- `reviewed-queue`
- `process`
- `origin-batch`
- `template-format-products`
- `origin-style-asset-replay`
- `xps-heterojunction-stacked`
- `xrd-overlay`
- `xrd-no-card-overlay`
- `jeol-epr-decode`
- `epr-overlay`
- `hplc-openlab-export`
- `validate`
- `readiness`
- `origin-governance`

`scripts/` 只存放被正式流程使用的辅助程序、受控回归工具和诊断工具，不得成为绕过 `run.py` 的第二套通用生产入口。临时脚本可以用于复现、读回和对比，但有效修复必须合并到正式模块，并由正式命令重新产出最终结果。

`scripts/data_types/hplc_lc/plot_hplc_calibration_origin.ps1` 是固定茴香硫醚校准数据和指定 HPLC OPJU 的受控回归/重建工具，不是任意 HPLC 数据的 reader 或第二套通用处理器。不得把它接到普通 HPLC 输入，也不得以它的固定数据产物代替 `hplc-openlab-export` 或正式处理结果。

处理真实数据时采用“小批量、先无 Origin、后出图”的顺序：

1. `scan` 和 `triage`。
2. 生成 `auto-queue` 或 `reviewed-queue` dry-run 计划。
3. 只处理明确批准的文件，优先 `process --no-origin`。
4. 核对 processed data、metadata、单位和人工检查项。
5. 最后运行相应 Origin 正式命令。

`process --only-type` 只是筛选 scanner 已识别的数据，并不等于强制把任意文件交给指定处理器。若用户明确给出数据类型，也必须验证文件签名、结构和 reader 能力；不能用类型参数跳过基本格式校验。

如果正式命令报错、误识别、漏数据、图形不合格、导出失败或报告信息不足，正确闭环是：

1. 保存失败证据和正式命令。
2. 定位 reader、processor、plotter、exporter、配置、模板或测试缺陷。
3. 修复项目本身。
4. 运行定向测试和对应 dry-run。
5. 重新运行正式入口。
6. 只交付正式流程生成的结果。

## 4. 原始数据、外部模板与输出安全

- 不修改、覆盖、删除、移动或重命名 `input/raw_data/`、F 盘原始数据、仪器原始目录或用户提供的外部模板。
- 打开外部 OPJU/OPJ 前必须复制到任务自己的临时目录或输出运行目录；不得在原位置保存。
- 不把运行产物写进原始数据目录、外部模板目录或项目源码目录。
- 默认输出根是项目同级目录 `../输出`，即通常为 `D:\Codex Project\科研数据处理\输出`。实际运行应通过 `config/local.yaml`、环境变量、`config/default.yaml` 或命令明确提供的输出根参数（如 `--output-root`、`--out`）解析，禁止照抄文档中的乱码路径。
- 命令明确提供的外部输出根必须先通过项目树隔离、原始输入不重叠和目标碰撞检查；不得把“用户传了一个路径”本身当成跳过安全检查的理由。
- 除明确的项目源文件修改外，所有运行产物都必须位于配置解析后的外部输出根。
- 不覆盖已有数据产品，除非正式命令支持且用户明确要求 `--force`。固定名的扫描索引、状态摘要、
  readiness/validate 报告和去重错误日志属于受控可变报告，可由对应正式命令刷新，但必须限制在
  输出根内，并采用拒绝 reparse point、避免硬链接原位截断的安全写入方式。
- `origin-batch --execute --with-origin` 是对清单中已计划但未完成行的显式受控重试授权：只允许
  预检并替换该行声明的 Origin 目标及其通用暂存文件；已完成行、输入文件和锁定结果包不得清理。
- 不修改锁定结果包，不把旧结果目录当作可写工作区。
- 不把完整本机路径、Codex/Agent 字样、源文件注释或隐私信息写入 OPJU 工作簿长名称、注释、图例或可见图形文本。
- 每个成功的数据处理结果必须生成 `metadata.json`。无 Origin/Excel 专用工作流不强制生成 OPJU；每个实际成功的 Origin 作图任务必须生成 `.opju`、600 dpi `.tif` 和 PNG 预览。

## 5. 科学结论边界

代码输出的是可追溯数据、候选值和人工检查材料，不是自动科学定论。

以下内容不得由程序自动证明或定论：

- 反应机理、S-scheme/Z-scheme 或异质结类型。
- 电子转移方向和最终能带结构。
- XPS 价态、氧空位和化学态归属。
- EPR 自由基/物种身份。
- XRD 相、晶面、纯相或结晶度结论。
- HRTEM 晶格条纹归属。
- LC-MS/MS 产物身份。
- HPLC 转化率、选择性、收率或峰身份，除非用户提供完整标准、公式和审核依据。
- 仅凭光电流升高、PL 降低、EIS 圆弧变化或 Mott-Schottky 截距得出的机理结论。

高风险结果必须写入 `manual_check_required`。峰位、拟合区间、Eg、平带电位、g 值、积分面积等只能标为 candidate，除非用户提供并确认了计算和解释依据。

## 6. Origin 运行与作图非回归规则

用户要求所有优化都保持现有正确 Origin 产品样式不变。非作图任务不得顺手修改：

- 画布尺寸和图层几何。
- X/Y 轴长度、位置、方向和粗细。
- 字体、字号和粗体规则。
- 图例位置、格式和边框策略。
- 曲线颜色、线宽、符号和堆叠顺序。
- 坐标范围、刻度和数据类型特有的显示方式。
- XPS 组分颜色、峰标签布局及其他专用图形约定。

Origin 使用规则：

- OriginPro 已安装，不得安装或替换 OriginPro。
- 使用 `Origin.Application`，不得使用 `Origin.ApplicationSI`。
- 启动前检查是否已有 Origin 进程；若存在且可能包含用户未保存工作，停止并询问，不得强行复用或关闭。
- 只操作任务自己的临时副本和输出文件。
- 保存后重新打开并读回关键属性，再导出 TIF/PNG。
- 600 dpi 必须是最终 OPJU 中目标图页的真实物理分辨率证据：Origin 页面尺寸单位为 0.001 inch，期望像素为 `round(page_dimension * 600 / 1000)`。必须同时核对 TIFF 标签、两个像素维度和由页面物理尺寸反算的有效 DPI。
- 禁止用 Pillow、System.Drawing 或其他工具插值放大低分辨率图来冒充 600 dpi；禁止只改 TIFF DPI 标签；禁止在未重开最终 OPJU 的情况下把早期临时导出当最终 DPI 证据。
- 必须实际查看 PNG 预览，检查数据完整性、字体、图例、坐标轴、标签遮挡、模板残留和空白图；文件存在不等于作图成功。
- 最终图不得含旧样品名、旧材料名、旧峰标签、旧 JCPDS/PDF 卡片、旧机理文字或模板占位符。
- 标准卡片、峰归属和拟合标注只能来自本次明确提供或核验的数据。

样式权威顺序：

1. 用户本次明确指定并确认正确的 OPJU/OPJ 及图页。
2. 对应数据类型经过人工确认的正确参考 OPJU。
3. 对应数据类型经过视觉核验的项目样式资产和样式读回。
4. 项目默认样式；Graph4 只在没有更合适的数据类型模板时作为基础样式来源。

数据类型的正确参考图可以覆盖全局默认中的数据类型特有设置。例如 HPLC、XPS、XRD、BET 等可能具有不同的刻度、图层或标签规则；不得为了统一常数而改变已经确认正确的产品。

## 7. OPJU、OTH、OTPU 与模板资产

模板资产必须按职责区分：

- `reference_opju/*.opju`：完整参考工程或项目内净化副本，包含数据、工作簿和图页。
- `format_themes/*.oth`：当前正式产品路径优先使用的 Origin 格式主题。
- `graph_templates/*.otpu`：历史批量采集留下的隔离记录；当前不是运行时模板，也不是结构回退。
- `snapshots/*.json`：样式读回记录。
- `data_snapshots/*.json`：模板数据集和绘图映射记录。
- `manifest.json`：资产登记和完整性信息。

当前 `graph_templates/*.otpu` 是批量脚本派生资产，用户已确认多个文件内容有问题。除非后续逐个重新生成并通过独立视觉验收：

- 不得把现有 `.otpu` 当作正确模板。
- 不得自动回退到 `.otpu`。
- 不得因为 manifest 状态为 `accepted`、文件存在或 SHA-256 匹配就声称 `.otpu` 正确。
- 不得用错误 `.otpu` 更新 `.oth`、OPJU 或图形常数。

现有 `.opju` 也不全是用户原始模板：部分来自用户 F 盘模板的 Origin 重保存副本，部分是管线生成产品。使用前必须检查 `source_mode`、快照、图页和实际来源，不得笼统声称“全部来自用户原始模板”。

项目内 `reference_opju/*.opju` 可在资产模式中作为独立样式/视觉证据，但边界必须严格：

- 先复制到本次运行自己的隔离目录，再只读打开。
- 只允许导出参考预览和读取参考图页样式，不得把参考 OPJU 当成产品底板、数据来源或可写工程。
- 本次数据必须写入新建的运行工程；最终 OPJU 必须由正式产品路径保存。
- 用户本次明确指定的外部参考优先于项目内参考证据，但外部参考同样只能操作副本。

模板来源记录应至少保存：

- 原始来源路径或经过脱敏但可追踪的标识。
- 原始文件 SHA-256。
- 项目内净化副本 SHA-256。
- 图页名称。
- 生成方式、Origin 版本、时间和代码提交。
- 来源是用户模板还是管线生成产品。

资产哈希只证明文件未变化，不证明视觉正确。模板接受必须包含实际 Origin 打开、测试数据替换、OPJU/TIF/PNG 导出、结构读回和人工预览。修改模板资产前必须保留修改前基线；未经用户明确要求，不得批量重新采集或覆盖 `templates/origin_styles/`。

如果回放中的 source OPJU 与项目 `reference_opju` 内容哈希相同，即使导出图逐像素相同，也只能
记为 `reference_opju_self_replay`（确定性导出证据），不得算作 `.oth` 或新数据产品的独立视觉验收。

## 8. 代码优化与删除原则

- 优先复用可靠、许可证兼容且已存在的库和适配器；不要重复实现成熟解析器或算法。
- 不为一个数据类型复制整条平行管线；共性逻辑进入共享模块，数据类型差异保留在明确的 reader/processor/plot policy 中。
- 不新增绕过 `run.py` 的入口。
- 删除代码前必须证明无正式入口、无导入、无配置引用、无测试覆盖需求、无兼容用途；“看起来没用”不是删除依据。
- 对历史兼容字符串、厂商格式、中文路径、旧表头和 Origin COM workaround 要特别谨慎。
- `src/core/xps_in_situ.py` 是旧兼容/测试链，不是当前正式 XPS in-situ 入口；正式路径位于模板产品流程。除非先完成接口迁移、测试清理和实际 Origin 非回归，不得重新接入，也不得因“不可达”直接删除。
- 低风险重构必须保持数据值、metadata schema、输出路径、CLI 契约和 Origin 样式不变。
- 涉及数值计算、列识别、单位换算、拟合、基线、归一化或平滑的修改，必须增加可复现测试并保留原始值追踪。
- 不静默降级到非 Origin 图或替代格式；任何 fallback 都必须明确记录，并且不能被标记为正式成功。
- 外部模型、Antigravity/Gemini、Claude/Opus 或其他代理的意见只用于补漏。主代理必须用当前代码、测试和实际产物逐条验证后才能采纳，不得盲目执行建议。

## 9. 依赖与环境

- 使用满足 `pyproject.toml` 和 `requirements.txt` 的现有 Python 环境；不要硬编码已经失效的 Python 路径。
- 若默认 `python` 缺依赖，应先查找项目已有可用环境，不得通过绕过正式入口解决。
- 安装新依赖前先确认现有包、缓存、许可证和必要性。
- 任何预计产生较大网络流量的下载必须先说明大致流量并取得用户明确同意。
- GPU/CUDA 任务遵循机器级 GPU 运行时规则；普通表征数据处理不得无故引入 GPU 依赖。

## 10. 验证与完成条件

修改后按风险执行验证，至少包括：

1. 受影响模块的定向测试。
2. 对应正式命令的 dry-run 或 `--no-origin`。
3. 完整测试：

   ```powershell
   python -m pytest
   ```

4. 按顺序运行，不要与 readiness 并行：

   ```powershell
   python run.py validate
   python run.py readiness --no-desktop-review-xlsx
   ```

`readiness` 的 `ready` 仅表示没有硬失败，用于保持旧调用方兼容；正式发布判断使用 `release_ready`，它要求 failures 和 warnings 都为 0。不得在 `ready=true`、`release_ready=false` 时宣称项目已经无条件发布就绪。

5. 若改动会影响 Origin、模板、绘图、图例、坐标轴、导出或图像验收，必须再运行对应正式 Origin 命令，保存并重新打开 OPJU，检查 600 dpi TIF，并人工查看 PNG。

`validate`、`readiness`、哈希、测试通过和文件存在都不能代替图形人工检查。未执行实际 Origin 验证时，必须明确说明“未验证 Origin 视觉结果”，不得宣称样式完全不变。

只有满足以下条件才能宣布完成：

- 正式入口成功。
- 所需 processed data、metadata、报告和产物齐全。
- 没有修改原始数据或外部模板。
- 科学结论边界符合 claim policy。
- 对应测试和验证命令通过。
- 涉及作图时，实际预览已检查且正确样式无回归。

## 11. 明确禁止

- 创建 PPT 功能、`src/ppt/`、PPT 模板、slide plan 或演示文稿。
- 创建 kinetics processor，或把“动力学”文献当实验动力学数据处理。
- 修改原始数据、用户模板或锁定结果包。
- 未经审核批量处理 `MANUAL_REVIEW` 或 ambiguous 文件。
- 自动生成高风险科学结论。
- 用一次性脚本输出冒充正式项目结果。
- 为通过测试而降低验收标准、放宽像素/结构检查或隐藏错误。
- 在没有视觉证据时把 `.otpu`、`.oth`、OPJU 或生成图标记为正确模板。
