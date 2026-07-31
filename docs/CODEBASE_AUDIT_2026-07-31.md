# 代码库审计与优化记录（2026-07-31）

## 审计结论

本轮按当前主线而不是早期 Phase 1 副本审计。正式执行链为
`run.py -> src/cli.py -> src/core / src/processors / src/origin`。项目已经具备较完整的
扫描、分流、数值处理、Origin 自动化、元数据、人工复核和验证框架，但审计前存在几类会造成
“文件生成了却不代表产品正确”的缺口：

- 样式验收可以在没有独立参考图时被标记为通过。
- TIFF 的 DPI 标签、像素尺寸和 Origin 页面尺寸没有形成同一条原生导出证据链。
- Origin 原生 TIFF 的 IPTC 字段会携带临时 OPJU 绝对路径。
- 若干正式命令在 `force=False` 时仍可能覆盖已有输出。
- 若干批处理在生成中途失败时可能留下新旧文件混合包，或在正式包提交后被暂存清理错误误报为失败。
- EIS、EPR、JEOL EPR 和依赖审计的边界不够明确。
- `epr-overlay` 绕过统一输出根解析；旧 EPR Excel 还可能携带只覆盖原始磁场跨度约 1/16 的错误横轴。
- CLI 启动、全仓验证和 Origin 临时目录清理存在不必要开销或锁文件风险。

上述问题已在正式模块中修正并补充回归测试。没有修改
`templates/origin_styles/` 内的任何样式资产，也没有修改
`config/plot_style.yaml`。

当前不能把“12 类产品均生成了文件”误写成“12 类产品均通过样式验收”。最新真实 Origin
全类型运行已生成 12 套完整的 `.opju/.tif/.png/processed data/metadata/report`，但新的
独立参考门禁把 12 类全部标记为 `blocked`：当前 `.oth` 生成图与包含不同数据、不同图例文本的
参考 OPJU 不是一对一像素相同。此状态是刻意的 fail-closed 结果，不应通过降低阈值伪造通过。

## 审计范围

- 当前 Git 主线及本轮工作树差异。
- `run.py`、全部 CLI 子命令和 85 个 `src/**/*.py` 模块。
- 处理器注册表中的 15 个维护条目及 scan-only 类型。
- Origin `.oth/.otpu/.opju` 资产、样式清单、导出与重开验证链。
- 现有测试、PowerShell/Python 辅助脚本、依赖和许可边界。
- 项目最近的相关 Codex 对话，重点复核用户曾发现的单线 XRD、错误 `.otpu` 和
  “运行成功不等于样式正确”等问题。
- Gemini 3.1 Pro High 与 Opus 4.6 的独立审阅意见；这些意见只作为查漏提示，
  采纳前均由本地代码、测试或真实 Origin 结果复核。

## 当前模板资产与来源

| 产品键 | 运行时格式 | 隔离记录 | 正确参考 OPJU | 清单来源 |
|---|---|---|---|---|
| BET | `format_themes/BET.oth` | `graph_templates/BET.otpu` | `reference_opju/BET.opju` | `direct_fdrive_template_opju` |
| XPS_in_situ | `format_themes/XPS_in_situ.oth` | `graph_templates/XPS_in_situ.otpu` | `reference_opju/XPS_in_situ.opju` | `direct_template_opju` |
| XPS_non_in_situ | `format_themes/XPS_non_in_situ.oth` | `graph_templates/XPS_non_in_situ.otpu` | `reference_opju/XPS_non_in_situ.opju` | `style_donor_product_key` |
| XRD | `format_themes/XRD.oth` | `graph_templates/XRD.otpu` | `reference_opju/XRD.opju` | `direct_template_opju` |
| EPR | `format_themes/EPR.oth` | `graph_templates/EPR.otpu` | `reference_opju/EPR.opju` | `direct_template_opju` |
| EIS | `format_themes/EIS.oth` | `graph_templates/EIS.otpu` | `reference_opju/EIS.opju` | `direct_fdrive_template_opju` |
| Raman | `format_themes/Raman.oth` | `graph_templates/Raman.otpu` | `reference_opju/Raman.opju` | `direct_fdrive_template_opju` |
| UV-vis DRS / Tauc | `format_themes/UV_vis_DRS_Tauc.oth` | `graph_templates/UV_vis_DRS_Tauc.otpu` | `reference_opju/UV_vis_DRS_Tauc.opju` | `direct_fdrive_template_opju` |
| PL | `format_themes/PL.oth` | `graph_templates/PL.otpu` | `reference_opju/PL.opju` | `direct_fdrive_template_opju` |
| photocurrent | `format_themes/photocurrent.oth` | `graph_templates/photocurrent.otpu` | `reference_opju/photocurrent.opju` | `direct_fdrive_template_opju` |
| FTIR | `format_themes/FTIR.oth` | `graph_templates/FTIR.otpu` | `reference_opju/FTIR.opju` | `direct_fdrive_template_opju` |
| Mott-Schottky | `format_themes/Mott_Schottky.oth` | `graph_templates/Mott_Schottky.otpu` | `reference_opju/Mott_Schottky.opju` | `direct_fdrive_template_opju` |

这组 `.opju` 并不全部等同于用户原始模板文件的直接复制。尤其
`XPS_non_in_situ` 的清单来源是 `style_donor_product_key`，即由已生成并复核的产品作为样式
供体形成；其余条目由直接模板或 F 盘模板采集。

### `.otpu` 的定性

现有 `.otpu` 不是正式运行模板，也不能视为与相应 `.opju` 等价的“完成版”。
它们是历史采集流程顺带保存的 graph-template 记录，其中多个文件未通过独立视觉验收。
正式代码已禁止把 `.otpu` 当作 `.oth` 缺失时的后备资产。

这些文件本轮没有删除，原因是它们仍属于清单可追溯的采集记录，直接删除会改变资产集合，
且没有带来运行收益。若以后要清理，应通过一次独立的资产清单迁移完成，而不是在一般代码
优化中静默删除。

## 已实施的主要优化

### Origin 产品与样式安全

- 样式验收必须使用独立加载的参考 OPJU 预览；禁止把生成图复制成自己的参考图。
- 项目内参考 OPJU 只从隔离、只读工作副本打开，并在前后校验源文件哈希。
- 最终 TIFF 必须从已保存并重新打开的最终 OPJU 原生导出。
- TIFF 同时校验 600 dpi 标签、动态页面尺寸对应的像素尺寸和有效物理 DPI；禁止先导出低分辨率
  再插值放大或只改 DPI 标签。
- 导出前通过 Origin 的 `doc -rn`/`doc -s` 清除当前工程路径身份，并验证 `%X` 为空、
  `%G` 为 `UNTITLED`，避免原生 TIFF 的 IPTC 字段泄露临时绝对路径。对照试验确认该操作不改变
  解码后像素。
- Origin 临时目录只允许位于中性运行根目录且名称严格匹配 `rdop_origin_*`；删除前逐项拒绝
  symlink/junction/reparse point，清理锁文件会重试，失败时保留诊断证据而不是扩大删除范围。
- 模板产品、样式采集、样式回放和重开 OPJU 导出均把 Origin 关闭/退出纳入成功条件；未确认退出
  时结果失败关闭，不会保留一个表面上的成功状态。
- `.oth`、`.opju` 和样式清单均未被本轮改写。

### 科研数据处理边界

- 正式 EIS 产品只保留测得点和明确单位，不再自动清洗、外推或拟合等效电路。
- EPR 不再对无显式单位的磁场轴猜测单位。
- JEOL EPR 解码新增运行所有权、原文件前后哈希、碰撞与 `force` 保护、完整 metadata 和人工复核项；
  EPR overlay 只在官方 decoder metadata 与 XLSX 哈希、点数和原始文件前后哈希一致时接受其中的
  `G/mT` 单位证据。
- `epr-overlay` 已接入 `--output-root`、配置和环境输出根，正式包先在同一输出根暂存并验证，再事务提交；
  旧 Excel 的错误磁场轴不会被原地修补，必须从 JEOL 原始文件只读重解码到新结果目录。
- 原生 `.spc/.dta` 若无受支持 reader 会明确阻断，不再以“看似可读”代替格式支持。
- 通用 process、HPLC、XRD、XPS、EPR 和 JEOL EPR 正式路径统一了输入/输出碰撞、已有产物、
  symlink/junction/reparse、硬链接与 `force` 覆盖契约。
- Origin batch 的 `--execute --with-origin` 是对清单中“已计划但未完成”行的受控重试授权；它会
  在同一输出根生成并验证完整暂存包，再事务替换该行声明的正式目标；提交失败会恢复旧文件，
  不会处理已完成行或扩大到其他目录。
- XPS 能量窗口生成的轨道标签保留原可见文本，同时在 CSV/metadata 中明确记录为
  `binding_energy_window_candidate` 并要求人工核对。
- 高风险的价态、自由基、机理、异质结方向、晶面和 LC-MS 产物结论继续保持人工复核边界。

### 工程质量

- CLI 改为按子命令惰性导入，`python -S run.py --help` 可在无 site-packages 环境启动。
- 依赖审计补充包版本、许可和正式运行路径；reference-only/GPL 候选不会被误列为默认依赖。
- `readiness.summary.ready` 与 `release_ready` 分离：前者只要求零硬失败，后者还要求零警告。
- 全仓验证预先解析允许根目录，遍历时不跟随 junction/symlink，避免重复扫描外部输出树。
- PowerShell 脚本统一 UTF-8 边界；脚本索引补齐正式辅助脚本。
- HPLC OpenLab、固定 HPLC 校准、Origin batch、XRD、XPS、EPR overlay 和 JEOL EPR 的多文件结果
  改为“完整暂存与验证后提交”，并增加第二文件安装失败、报告提交失败及旧包恢复的故障注入测试。
- 删除了可以证明无调用且无兼容价值的小型死代码；对有公共导入、测试或政策含义的模块没有盲删。

## 冗余与不可达模块审计

以所有正式 CLI 子命令为根，85 个 `src` Python 模块中 77 个可在真实执行分支到达，8 个不可从
正式 CLI 到达。不可达不等于可删除：

| 模块 | 当前判断 |
|---|---|
| `src/adapters/eis_pyimpspec_adapter.py` | GPL/reference-only 许可隔离探针，保留 |
| `src/adapters/electrochem_import_adapter.py` | 未来格式与许可探针，保留/延后 |
| `src/adapters/hplc_adapter.py` | 能力/许可目录；正式 OpenLab 走 `src/core/hplc_openlab.py`，可在未来统一 |
| `src/adapters/image_metadata_adapter.py` | SEM/TEM scan-only 探针，保留 |
| `src/adapters/nmr_adapter.py` | NMR scan-only 探针，保留 |
| `src/adapters/ms_adapter.py` | MS scan-only 探针，保留 |
| `src/adapters/raman_adapter.py` | 与正式 Raman 基线/寻峰组合重复，是最明确的未来协同退役候选 |
| `src/core/xps_in_situ.py` | 已隔离的兼容/测试实现；正式 XPS 路线不调用，迁移测试和外部 API 前不得删除 |

本轮没有一个模块满足“删除文件且不破坏 CLI、测试、公共导入、文档政策或 Origin 样式”的条件。
因此没有为了减少文件数而制造兼容性破坏。

可在未来单独安排的结构性合并包括：有限浮点解析、CSV 写入、EPR 公共网格验证、Origin 富文本转义
和依赖清单。但这些小重复分布在格式处理或 Origin 敏感路径上，当前收益不足以抵消回归风险。

## Origin 非回归证据

### 资产不变

- 基线 95 个样式/配置文件集合 SHA-256：
  `2884abf6d13baad45314abd661909c7476be6a73630f987b63894b8abdd2bb39`。
- `git diff -- templates/origin_styles config/plot_style.yaml` 为空。
- 2026-07-31 的旧回放对 12 个条目都得到 `exact_pixel_match = true`、`rms = 0.0`、
  `diff_bbox = null`，但复核发现每个条目的 source OPJU 与项目 `reference_opju` 内容哈希相同。
  这只证明同一参考 OPJU 的 Origin 导出是确定性的。代码现将其标为
  `reference_opju_self_replay`，统计为 12 个 inconclusive self-replay、0 个独立 match；
  它不验证 `.oth` 在新建图上的视觉正确性。

### 最近主线产品对照

当前 OPJU 与 2026-07-11 最近主线产品的结构字段对照中（该对照不是独立视觉验收）：

- BET、EPR、FTIR、photocurrent、PL、Raman、UV-vis、两类 XPS 和 XRD 均为 42/42 样式字段通过。
- Mott-Schottky 的原始样式快照零差异；门禁仍提示其历史线宽不满足统一 3 pt 政策，这不是本轮新增差异。
- EIS 的格式字段保持一致；差异位于测量数据范围、坐标范围及随范围自动定位的图例。正式 EIS
  已改为 measured-only，因此不能用旧拟合曲线的像素作为科学正确性的强制基准。
- 当前 PNG 的像素尺寸约为旧产品的两倍，来源是修复后的实际导出分辨率，不是页面比例、字体、
  颜色或线型的样式修改。

### HPLC 固定校准图回归

受控 HPLC 校准脚本以用户指定的正确 OPJU 为样式基线重建 3 个图页。修复后的 3 张 PNG 均为
3216 × 2461，和基线逐像素相同：`ChangedPixels = 0`、`MeanAbsDelta = 0`、`Max = 0`。
源模板 SHA-256 在运行前后相同。该证据只适用于这一固定数据/固定模板回归工具，不把脚本提升为
通用 HPLC reader，也不证明其他 HPLC 产品已经视觉验收。

事务化改造后的实机运行位于
`输出/diagnostics/20260731_goal_hplc_calibration_transaction_regression`。首次运行和显式
`-Force` 重跑都成功；新旧 3 张 PNG 的文件压缩字节可不同，但解码后的 3216 × 2461 像素均为
逐像素相同、`changed_pixels = 0`。正确 OPJU 模板 SHA-256 始终为
`0238cad46bb0bad0d2a67c52d084b93a88d4735d5845b648ec95972ae487744d`，运行结束后 Origin 进程数为 0。

### EPR 原始解码与 Origin 事务回归

- 旧 `BC-OH-light2.xlsx` 的横轴只有 `324.0–324.6249`，而同名 JEOL `cAcqu` 原始文件头明确为
  `324–334 mT`；因此旧 Excel 被安全预检阻断，没有原地改写。
- 正式 `jeol-epr-decode` 在
  `输出/diagnostics/20260731_goal_final_epr_raw_redecode` 只读重解码 24 个原始文件，生成
  24 个 XLSX 和 24 个 metadata；原始树集合哈希前后均为
  `6a5f78d6f190a8487c935c4d17989a994511e2a80ef409abbf019d64b5063ef9`。
- 正式 `epr-overlay --group OH --with-origin --output-root ...` 在
  `输出/diagnostics/20260731_goal_final_epr_origin_transaction_v2` 成功生成 OPJU/TIF/PNG。
  三条曲线的单位来源均为 `verified_jeol_decoder_metadata`，metadata 记录 `mT`、人工复核和
  禁止自由基/机理自动结论。
- 最终 TIFF 为 3859 × 2953，标签 600 × 600 dpi，按 Origin 页面 6432 × 4923 反算的有效
  DPI 为约 599.97 × 599.84；PNG 已人工查看，画布、三色曲线、直接标签、轴线和当前仓库既有的
  “隐藏 Y 数值”策略正常。该结果验证最终 EPR 事务/导出链，不把旧错误数据范围的归档图当像素基线，
  也不替代独立样式资产验收。

### 直接用 OPJU 作为产品基底的否决试验

为核实“正确 OPJU 能否直接作为新数据产品基底”，本轮仅对 XRD 做了隔离诊断：

- 样式字段匹配率从 `.oth` 路线的约 0.79 提高到约 0.98；
- 但模板工作簿列与当前数据结构不一一对应，真实产品出现水平线、重叠图例和重叠标卡文字；
- 因而该路线被否决，没有并入正式代码。

这说明“OPJU 本身是正确参考”与“OPJU 可安全承载任意新数据”是两个不同命题。当前正确做法是
把 OPJU 作为独立视觉/样式证据，把 `.oth` 用于当前数据的新图，同时由严格门禁阻止不合格产品
被误报为通过。

## 验证状态

最终验证已完成：

- `D:\Python\python.exe -m pytest`：844 passed，3 skipped，共 847 项。
- `compileall`、PowerShell 两个正式辅助脚本语法解析、依赖审计和
  `python -S run.py --help` 均通过。
- 正式 `process --no-origin --fail-fast` 对合成夹具生成 16 个数据集 metadata，覆盖 15 个维护类型，
  全部为 `processed_no_origin` 且保留人工复核项。
- `python run.py validate`：退出码 0。
- `python run.py readiness --no-desktop-review-xlsx`：21 项检查、0 failures、15 warnings；
  `ready=true`、`release_ready=false`。
- 最终代码的 12 类 asset-only 无 Origin 运行：12 blocked、0 failed，严格门禁按预期失败关闭。
- 12 类真实 Origin asset-only 运行（早于最后一轮 EPR 事务包装改造）已生成完整产物；最终代码又单独
  实机复跑 HPLC 固定校准和 EPR OH overlay。未把前一轮全类型运行冒充为最后提交状态的全类型重验。
- 12 类参考 OPJU 确定性 self-replay（已明确为 inconclusive，而非 `.oth` 验收）。
- 核心 TIFF、Origin 身份清理、覆盖保护、EIS/EPR/JEOL、模板验收和 CLI 的定向回归测试。
- Gemini 3.1 Pro High 与 Opus 4.6 的首轮独立意见已逐项本地复核；只采纳了能由代码、测试或
  真实 Origin 产物证明的建议。Gemini 后续与本地证据冲突的结论被否决，Opus 后续重试遇到额度限制，
  两者均未替代主代理的验收判断。

## 仍需人工决定或延后的事项

- 12 类当前生成产品与独立参考 OPJU 不是一对一视觉相同，正式状态保持 `blocked`。需要基于同数据
  的人工确认或重新采集适配当前数据结构的已审阅模板，不能简单放宽 RMS/样式阈值。
- `src/core/xps_heterojunction.py` 的自动峰位窗口仍只生成元素轨道候选标签，不自动推出价态；
  CSV/metadata 已显式标注 candidate、方法和人工核对要求，可见图中文字保持原样。
- XRD no-card 兼容辅助图的 Y 轴刻度线隐藏属于既有样式。没有正确视觉基线前不改。
- readiness 的可选依赖/历史证据警告需要按实际发布范围逐项处理；不能把 `ready=true` 等同于
  `release_ready=true`。
