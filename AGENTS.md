# ResearchDataOriginPipeline Agent Rules

## 1. 适用范围与事实优先级

本仓库是持续维护的科研表征数据处理与 OriginPro 产品管线，不是任何历史阶段性工作区。所有代理在扫描、处理、修复、Origin 作图、模板资产维护和项目验收时均须遵守本文件。

判断项目现状时按以下顺序取证：

1. 当前工作区代码、测试、配置和 `git status`。
2. `README.md`、`docs/CURRENT_STATUS.md`、`docs/PROJECT_INDEX.md`、`docs/REAL_DATA_INTAKE_GUIDE.md`。
3. `config/processor_registry.yaml`、`config/claim_policy.yaml`、`config/plot_style.yaml` 和正式方法卡。
4. 最近提交、最近正式运行报告和用户在当前任务中确认的事实。
5. 历史提交和历史文档只用于追踪来源与兼容性，不得覆盖当前代码和验收证据。

若文档、配置和代码不一致，先用正式入口和定向测试确认实际行为，再修正文档、配置或实现；不得通过降低检查标准来制造表面一致。

## 2. Git 历史与版本演进

用户指定某个 Git 版本作为参考时，应把它作为本次任务的比较输入，从中提取仍然有效的设计、兼容性和安全约束；不得把该提交号、标签、日期、版本名称或当时的资产清单写成永久运行基线。

历史版本中引入的早期 Origin manifest、批量 `.otpu`、预览、样式导出、注册和回放实现只用于解释资产来源与迁移路径。正式入口优先、失败后修复项目本身、保护原始数据和限制自动科研结论等原则可以保留，但具体实现状态必须动态核对。

版本判断规则：

- 当前工作树、当前 `HEAD`、正式 CLI、注册表、配置、测试和最新正式运行证据始终优先。
- 历史 commit 只用于追溯、回归比较和兼容性分析，不是当前发布或视觉验收证明。
- manifest schema、CLI 命令、支持类型、资产路径和运行时状态必须从当前代码与配置读取，不在本文件维护固定版本、数量或白名单。
- 历史 manifest 的 `accepted`、预览 RMS、文件存在或当时的自回放结果不能自动继承为当前独立验收。
- 是否兼容旧 schema 和旧路径由当前 loader、validator 与测试决定；不得为了贴近历史版本而回滚 reader、processor、输出安全、claim policy、Origin 验收或模板绑定合同。
- 历史版本中的项目内输出路径或批量 `.otpu` 自动 fallback 不得覆盖当前路径解析与资产验证规则。

## 3. 当前维护范围

正式链路包括：

- 扫描、分类、triage、自动队列和人工审核队列。
- 支持数据的表格读取、规范化处理、`metadata.json`、报告和人工检查项。
- OriginPro 作图、`.opju` 保存、原生 600 dpi `.tif` 导出和 PNG 预览。
- XPS、XRD、EPR 等专用产品流程。
- JEOL JES-FA/JES-X3 `cAcqu` EPR 原始数据解码。
- Agilent OpenLab HPLC/LC `.rslt/.dx/.rx` 原始数据到 Excel 的专用导出。

可处理类型始终以当前 `config/processor_registry.yaml` 中 `supported_in_pipeline=true` 的条目为准；本文件不重复维护固定类型名单或数量。每次处理前都必须读取注册表，并核对对应 reader、processor、方法卡和测试。

凡注册表标为不支持、scan-only 或 reference-only 的类型，都不得自动进入处理器或 Origin。“动力学”必须按 `reference_literature` 处理，不得解释为实验动力学数据；未经用户明确扩展范围、正式 reader/processor 实现、注册表更新、测试和真实数据验收，不得改成可处理类型。

## 4. 数据类型路由、执行模式与处理闭环

### 4.1 动态模块映射

混合数据和项目级批处理的通用链路是：

```text
run.py -> src/cli.py -> src/core / src/processors / src/origin
```

但用户明确指定单一数据类型时，不得为了走通用入口而强制执行全库识别。每次任务按当前代码动态确定模块：

1. 从 `config/processor_registry.yaml` 读取该类型的 `supported_in_pipeline`、`selected_processor`、`special_handling` 和方法卡。
2. 从 `src/processors/profiles.py` 核对 processor、manual check 和 forbidden claims。
3. 普通表格类型使用现有 `src.processors.base.process_table_dataset`；它通过 `src/core/table_reader.py`、`src/processors/calculations.py`、`src/processors/eis.py` 和 `src/adapters/` 完成当前类型的读取与计算。
4. `special_handling` 指向 dedicated workflow，或用户要求专用多文件产品时，直接使用当前 `src/cli.py` / `docs/PROJECT_INDEX.md` 登记的既有专用 core API 或正式子命令。
5. `src/origin/type_mimic/` 只定义作图风格与人工检查策略，不是数据 reader 或 processor，不得用于代替数据分析模块。

以当前 `python run.py --help`、`src/cli.py`、processor registry 和 `docs/PROJECT_INDEX.md` 为入口事实来源。本文件不维护可能随版本变化的完整命令或数据类型白名单。

### 4.2 已知单一数据类型：直接处理

当用户已经明确数据类型，且输入是单个文件或同一种数据的明确文件集合时：

1. 只读取对应注册表条目和模块，不运行全项目 `scan`、`triage`、`auto-queue`、`reviewed-queue` 或整棵原始数据目录识别。
2. 使用所选 reader 做最小必要的本地签名检查，包括扩展名、表头、列结构、仪器魔数或厂商格式；这是输入校验，不是重新做全局类型识别。
3. 普通表格数据直接将当前注册表条目作为 classification 传给 `process_table_dataset`，逐个处理用户指定文件；不得手写 processor 名称来绕过注册表。
4. 有现成 dedicated core/CLI 的原始格式或专用产品，直接调用该模块；不得先送入通用 scanner 再转回专用模块。
5. 普通表格优先使用 `python run.py process --source <文件> --only-type <注册表类型> --no-origin`，多个同类型文件可重复 `--source`；此模式不扫描输入目录。专用格式仍使用对应 dedicated API/CLI。
6. 用户声明的类型与 reader 签名不一致时，停止该文件并报告具体结构问题；不得静默改类型、扫描无关目录或临时拼一个解析器交付结果。

不得为了调用既有模块而新建一次性 `.py`、`.ps1`、`.bat`、notebook 或包装 CLI。直接调用现有函数、现有正式子命令或现有批处理 API；多个同类型文件使用模块已有批量能力或逐个调用同一 API。只有用户明确要求修复项目能力时，才修改正式模块并补测试。

### 4.3 未知或混合输入：才运行识别流程

只有以下情况才使用 `scan`、`triage` 和队列：

- 用户要求识别、盘点或分类未知数据。
- 输入目录确实包含多种类型，且用户要求批量处理。
- 文件类型未说明，无法通过目标 reader 的局部结构检查安全确定。
- `MANUAL_REVIEW`、ambiguous 或批量授权需要正式队列留痕。

即使在混合流程中，也采用小批量和先数据后作图；队列只包含当前任务批准的文件，不扩大到无关目录。

### 4.4 数据分析与作图必须分离

根据用户要求选择最小执行模式：

- 用户只说数据处理、数据分析、读取、转换、提取、候选计算、拟合候选或导出表格，且没有明确要求作图时，默认执行完整的数据处理流程但不启动 Origin。
- 普通表格 processor 使用 `no_origin=True`；专用模块使用其当前数据产出的非 Origin 模式，例如 `with_origin=False`。不要把只生成计划、不生成 processed data 的 dry-run 冒充数据处理完成。
- 纯数据任务仍必须生成该流程要求的 processed data、`metadata.json`、报告、来源追踪、candidate 结果和 `manual_check_required`；不得创建空 OPJU、占位 TIF/PNG 或伪造作图成功状态。
- 纯数据任务不得运行 `origin-test`、Origin style harvest/replay、模板回放或其他会启动 Origin 的命令。
- 只有用户明确要求作图、OPJU、TIF、PNG 或 Origin 产品时，才在数据结果核对后对该数据类型运行 Origin 路径；不得顺带绘制其他类型。
- 用户后续再要求作图时，复用已核对的 processed data 和 metadata，不重新扫描或处理无关原始数据。

### 4.5 失败闭环

目标模块若报错、误读、漏数据、数值异常、导出失败或证据不足，必须：

1. 保存目标调用和失败证据。
2. 定位对应 reader、processor、adapter、exporter、配置或测试缺陷。
3. 用户要求修复时，把有效修复合并到该正式模块；不得以一次性脚本作为最终结果。
4. 运行该模块的定向测试和同一输入的最小复现。
5. 只重新运行目标数据类型和用户指定文件，不重新跑无关识别、处理或 Origin 流程。
6. 只交付正式模块生成且通过检查的结果。

`scripts/` 只存放正式流程使用的辅助程序、受控回归工具和诊断工具，不得成为第二套通用生产入口。已有固定数据回归脚本不能代替通用 reader、processor 或对应正式产品流程。

## 5. 原始数据、外部模板与输出安全

- 不修改、覆盖、删除、移动或重命名 `input/raw_data/`、F 盘原始数据、仪器原始目录或用户提供的外部模板。
- 打开外部 OPJU/OPJ 前，必须复制到本次任务自己的临时目录或外部输出运行目录；不得在原位置保存。
- 不把运行产物写入原始数据目录、外部模板目录或项目源码树。
- 输出根必须通过当前 `config/local.yaml`、环境变量、`config/default.yaml`、运行时路径解析器或命令参数动态解析；不得在本文件或实现中复制固定绝对路径，也不得假定历史项目内 `output/` 仍然有效。
- 显式输出根也必须通过项目树隔离、输入不重叠、目标碰撞、reparse point 和硬链接安全检查；用户提供路径不等于自动安全。
- 不覆盖已有数据产品，除非正式命令支持且用户明确授权 `--force`。受控可变报告只能在解析后的输出根内安全刷新。
- `origin-batch --execute --with-origin` 只授权重试清单中已计划但未完成的行；不得清理已完成行、输入、锁定结果包或无关文件。
- 不修改锁定结果包，也不把旧结果目录当成可写工作区。
- 不把完整本机路径、Codex/Agent 字样、源码注释或隐私信息写入 OPJU 可见工作簿名称、注释、图例或图形文本。
- 每个成功的数据处理结果必须有 `metadata.json`。无 Origin 或 Excel 专用工作流不强制生成 OPJU；每个实际成功的 Origin 作图任务必须生成 `.opju`、原生 600 dpi `.tif` 和 PNG 预览。

## 6. 科学结论边界

以 `config/claim_policy.yaml` 为正式规则。程序输出可追溯数据、候选值和人工检查材料，不自动形成高风险科学定论。

不得自动证明或定论：

- 反应机理、S-scheme/Z-scheme 或异质结类型。
- 电子转移方向和最终能带结构。
- XPS 价态、氧空位或化学态归属。
- EPR 自由基/物种身份。
- 无充分证据的 XRD 晶面、纯相、无杂质或结晶度结论。
- HRTEM 晶格条纹归属。
- LC-MS/MS 产物身份。
- HPLC 转化率、选择性、收率或峰身份，除非用户提供完整标准、公式和审核依据。
- 仅由光电流升高、PL 降低、EIS 圆弧变化或 Mott-Schottky 截距推出的机理结论。

高风险结果必须进入 `manual_check_required`。峰位、拟合区间、Eg、平带电位、g 值和积分面积等默认标为 candidate。

XRD 可使用已配置的本地 Jade/PDF 卡库输出自动物相匹配，但必须记录数据库、卡号、匹配峰、备选相和置信度；单相、无杂质、定量相含量和晶面归属仍需额外证据与人工审核。

## 7. Origin 运行与作图非回归

非作图任务不得顺手改变已确认产品的画布尺寸、图层几何、坐标轴、字体、图例、曲线颜色、线宽、符号、堆叠顺序、范围、刻度或数据类型专用标签。

Origin 运行规则：

- OriginPro 已安装，不得安装、替换或升级 OriginPro。
- 使用 `Origin.Application`，不得使用 `Origin.ApplicationSI`。
- 启动前检查现有 Origin 进程；若可能包含用户未保存工作，停止并询问，不得复用、强关或抢占。
- 只操作本次任务自己的临时副本和输出文件。
- 保存最终 OPJU 后重新打开，读回目标图页和关键属性，再导出 TIF/PNG。
- Origin 页面尺寸单位为 0.001 inch；600 dpi 期望像素为 `round(page_dimension * 600 / 1000)`。必须同时核对 TIFF 标签、宽高像素和由最终页面物理尺寸反算的有效 DPI。
- 禁止插值放大低分辨率图、仅修改 DPI 标签，或把未重开最终 OPJU 前的临时导出冒充最终证据。
- 必须实际查看 PNG，检查数据完整性、字体、图例、坐标轴、标签遮挡、模板残留和空白图；文件存在不等于作图成功。
- 最终图不得残留旧样品名、旧材料名、旧峰标签、旧 JCPDS/PDF 卡、旧机理文字或模板占位符。
- 标准卡、峰归属和拟合标注只能来自本次明确提供或核验的数据。

样式权威顺序：

1. 用户本次明确指定并确认正确的 OPJU/OPJ 及图页。
2. 对应数据类型经人工确认的正确参考 OPJU。
3. 对应数据类型经独立回放和人工预览确认的项目样式资产。
4. 项目默认样式；Graph4 只在没有更合适的数据类型证据时作为基础来源。

数据类型参考可覆盖全局默认中的专用设置；不得为了统一常数改变已经确认正确的 HPLC、XPS、XRD、BET 等产品样式。

## 8. OPJU、OTH、OTPU 与样式资产

资产职责必须分开：

- `manifest.json`：按当前 schema 登记资产、完整性、来源和运行时验证状态；兼容范围以当前 reader、validator 和测试为准。
- `format_themes/*.oth`：未迁移类型的兼容运行时格式主题；manifest 登记或哈希通过不等于独立视觉验收。
- `reference_opju/*.opju`：参考、恢复和独立样式/视觉证据，不是默认产品底板或数据来源。
- `snapshots/*.json`：关键样式读回。
- `data_snapshots/*.json`：参考数据、图层、X/Y 映射和逐曲线样式的审计记录。
- `graph_templates/*.otpu`：默认视为候选或隔离资产；只有 manifest 明确登记为已晋升运行时资产且配套绑定合同和独立验证证据时才可使用。
- `binding_contracts/*.json`、`validation_plans/*.json`、`validation_evidence/*.json`：单个资产的显式绑定和晋升证据。

### 8.1 历史批量资产

历史版本批量创建的 `.otpu` 默认只是采集记录。除非某个资产后来被逐个重新生成，并由当前 manifest、resolver、validator 和正式证据共同认定为运行时资产：

- 不得作为运行时模板或自动 fallback。
- 不得因为旧 manifest 的 `accepted`、预览相似、文件存在或哈希一致就声称正确。
- 不得用于更新 `.oth`、参考 OPJU、图形常数或新产品。
- 不得把历史资产的自身回放当作独立视觉验收。

### 8.2 动态运行时判定

不得在 `AGENTS.md` 中维护按产品名、文件名、日期或提交号编写的 `.otpu` 运行时白名单。每次使用资产时必须通过当前项目的 style registry、manifest loader 和 validator 动态解析，并确认：

- 当前 manifest 将该资产登记为可运行且已接受，而不是 historical、candidate、quarantined 或 nonruntime。
- 当前登记的资产类型、路径、绑定合同、验证计划和验证证据完整且互相一致。
- 正式 executor 确实会分派该资产；文件存在或未提交候选文件本身不构成授权。
- 相关验证没有被更晚的 manifest、审计、代码或用户决定撤销。

若上述任一条件无法由当前正式代码和证据确认，资产必须按隔离候选处理。新增或替换运行时资产只更新 manifest 与配套证据，不需要再次修改本文件。

后续资产只有同时满足以下条件才可晋升：

1. 从经审核参考重新生成，而不是批量继承旧状态。
2. 有明确的逐层、逐曲线 X/Y 绑定合同，并验证同一数据和同一映射。
3. 在全新 Origin 工程中仅使用候选资产生成，参考 OPJU 不作为产品底板，也不在 fresh plot 阶段加载。
4. 保存并重开生成 OPJU，完成结构和样式读回。
5. 原生导出并验证 600 dpi TIFF。
6. 与独立参考同尺寸、解码像素零差异，并通过关键样式 hard gate。
7. 由人工实际检查 PNG，确认无旧标签、空图或布局问题。
8. 由当前正式资产回放命令生成证据并写入当前 schema 的 manifest；不得由诊断脚本自行“晋升”。

若 source OPJU 与项目 `reference_opju` 内容相同，逐像素一致只能记为 `reference_opju_self_replay`，只证明确定性导出，不能证明 `.oth`、`.otpu` 或新数据产品独立正确。

使用项目内或外部参考 OPJU 时，必须先复制到隔离目录并只读打开。除非存在针对该数据形状的完整、已验证替换合同，否则不得把参考 OPJU 当作通用 workbook 底板。用户本次指定的外部参考优先，但同样不得原位保存。

修改 `templates/origin_styles/` 前必须保留基线，并限定到用户授权的单个或明确资产集合；未经明确要求不得批量重新采集、覆盖或晋升。资产哈希只用于 manifest 完整性和明确的验证合同，不能替代视觉检查。

## 9. 实现、重构与依赖

- 优先复用可靠、许可证兼容且项目已有的库、reader 和 adapter；不要重复实现成熟解析器或算法。
- 不为单个数据类型复制整条平行管线；共性进入共享模块，差异保留在明确的 reader、processor 和 plot policy 中。
- 不新增绕过 `run.py` 的通用入口。
- 删除代码前必须核对正式入口、导入、配置、厂商和历史兼容用途；“看起来没用”不是证据。仅由测试引用的私有实现可以在保持对外行为后同步迁移测试，不为固定旧写法永久保留失效生产分支。
- 对中文路径、旧表头、厂商格式和 Origin COM workaround 保持兼容谨慎。
- `src/core/xps_in_situ.py` 是隔离的旧兼容/测试链，不是当前正式 XPS in-situ 入口；未完成接口迁移、测试清理和实际 Origin 非回归前，不得重新接入或直接删除。
- 低风险重构也必须保持数据值、metadata schema、输出路径、CLI 契约和 Origin 样式不变。
- 数值计算、列识别、单位换算、拟合、基线、归一化或平滑改动必须有可复现测试并保留原始值追踪。
- 不静默降级到非 Origin 图或替代格式；fallback 必须明确记录，且不能标记为正式成功。
- 外部模型或其他代理的意见只用于补漏；必须用当前代码、测试和实际产物逐条验证后才能采纳。
- 使用满足 `pyproject.toml` 和 `requirements.txt` 的现有环境；默认 Python 缺依赖时先找项目已有环境，不得硬编码失效路径或绕过正式入口。
- 安装依赖前检查现有包、缓存、许可证和必要性；预计产生较大网络流量的下载必须先说明流量并取得用户明确同意。
- 普通科研数据处理不得无故引入 GPU；GPU/CUDA 任务遵守机器级专用运行时规则。

## 10. 验证与完成条件

验证按本次改动的实际影响范围执行，不对每个小改动默认全仓验收：

| 改动 | 开发中必要验证 | 批次收尾 |
|---|---|---|
| 文档、报告文案、已确认不可达的私有代码清理 | diff、引用和事实检查；涉及行为再运行定向测试 | 不启动 Origin，不运行无关全套检查 |
| 扫描、队列、读表、配置、索引或数据复用 | 对应模块测试及同一小输入的结果比较 | 按实际调用范围补整合检查 |
| 数值或数据准备优化 | 完整数据值、顺序和边界规则等价对照 | 影响进入图的数据时，对受影响类型做同路线比较 |
| Origin 调用、绑定、样式、标签和导出 | 对应测试；Windows 上受影响的正式产品 | 保存重开、数据与样式读回、原生 TIFF 和 PNG 比较 |
| 公共底层重构或整批优化准备合并 | 开发中先定向检查 | 整批完成后集中完整回归一次，并运行适用范围的项目检查 |

需要完整批次验收时按以下顺序运行；不要为每个小提交反复执行：

```powershell
python -m pytest
python run.py validate
python run.py readiness --no-desktop-review-xlsx
```

`validate` 与 `readiness` 顺序执行，报告说明检查范围；历史运行包的状态不得冒充本次代码或产品状态。修复失败项后按影响范围重跑，只有修复再次涉及公共底层时才扩大全量回归。

代码优化批次可对两个命令均使用 `--scope runtime`，检查当前软件、配置和模板资产；只有审查完整既有运行环境时才使用默认 `full` 范围。`runtime` 不要求历史结果包、旧队列或用户 PPT，其 `release_ready` 始终为 false，也不能代替本次 Origin 图形验收。

与本次修改无关的既有问题只记录，不自动扩展任务去修；本次引入或直接影响本次结果的问题应在本次解决。优先复用现有测试，不为可逆的小修改增加大量假想场景、源码排版断言或新验收框架。

需要 CLI 验证时使用目标模块的真实数据模式、dry-run 或 `--no-origin`，并区分“只规划”和“实际生成数据”。在没有 Windows/Origin 的环境交付待测试代码时，应记录已执行测试和待执行的具体命令及代表图；可以提交到工作分支，但不得将未做的视觉验收记为通过或合并为已验收发布。

`ready=true` 只表示没有硬失败。正式发布判断使用 `release_ready`，要求 failures 和 warnings 均为 0；`ready=true`、`release_ready=false` 时不得宣称无条件发布就绪。

只有涉及 Origin、模板、绘图、图例、坐标轴、图形导出或视觉验收时，才运行对应正式 Origin 命令，保存并重开 OPJU，核验原生 600 dpi TIFF，并人工查看 PNG。纯数据处理不运行这些步骤。

`validate`、`readiness`、哈希、测试通过和文件存在都不能代替视觉检查。任务本应验证作图但未实际运行 Origin 时，必须明确写出“未验证 Origin 视觉结果”，不得声称样式完全不变；纯数据任务无需生成或验证视觉结果。

只有同时满足以下条件才能宣布完成：

- 目标正式模块、专用 API 或正式入口成功。
- 所需 processed data、metadata、报告和产物齐全。
- 原始数据、外部模板和锁定结果包未被修改。
- 科学结论符合 claim policy。
- 对应测试与验证命令通过。
- 涉及作图时，最终预览已实际检查且正确样式无回归。

纯文档修改至少运行 `git diff --check`，并核对文档引用的命令、路径和事实；不应仅为文档改动启动 Origin。

## 11. 明确禁止

- 用户已明确单一数据类型时，仍无必要地运行全库 `scan`、`triage`、队列或无关类型处理。
- 为调用现有模块而创建一次性脚本、包装入口或平行处理链。
- 在纯数据分析任务中启动 Origin、生成占位图形，或把 dry-run 计划冒充处理结果。
- 创建 kinetics processor，或把“动力学”文献当实验动力学数据处理。
- 修改原始数据、用户模板或锁定结果包。
- 未经审核批量处理 `MANUAL_REVIEW` 或 ambiguous 文件。
- 自动生成高风险科学定论。
- 用一次性脚本或手工整理产物冒充正式项目结果。
- 为通过测试而降低验收标准、放宽像素/结构检查或隐藏错误。
- 在没有独立证据和人工预览时把 `.otpu`、`.oth`、OPJU 或生成图标记为正确模板。
- 把任何历史提交、标签或旧版状态直接当作当前运行时或发布验收状态。
