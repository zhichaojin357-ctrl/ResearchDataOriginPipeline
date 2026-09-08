# 第二轮优化复查与验证记录

**最终 Windows 完整回归：1,270 passed、0 failed、2 skipped，另有 59 项子测试通过。运行时 validate / readiness 均零失败；Origin 实际视觉结果尚未验证。**

本轮根据用户“继续寻找优化，并把应该做且可以做的测试仔细完成”的要求开展。继续遵守“不改变作图效果”，保留固定 OTPU 与自适应 OTH + JSON 两条路线。

本文记录第二轮发现、证据和测试；电脑端的正式产品验收步骤仍见 [OPTIMIZATION_HANDOFF.md](OPTIMIZATION_HANDOFF.md)。文中的历史提交仅用于本次比较，不是永久运行基线。

## 1. 模板完整性失败的真正原因

进一步在 Windows、完整仓库资产及项目依赖齐全的环境运行后，仍有资产解析相关测试失败。因此，上一轮把这些失败主要归入本地资产或依赖缺失并不完整。

独立核查发现，manifest 登记的 **24 份样式／数据 JSON 的 SHA256 与 Git 提交字节不符**。其中 18 份可以通过恢复 CRLF 换行精确还原；另 6 份原本混用了 CRLF 和 LF。此前 `.gitattributes` 为这些文件指定 `text eol=lf`，Git 将它们统一成 LF，而 manifest 保留了统一换行前的字节哈希和大小。

恢复全部 24 份文件后，逐项进行了四种核对：

1. 恢复字节的 SHA256 **等于原 manifest 已登记的 SHA256**。
2. 恢复字节数 **等于原 manifest 已登记的 size_bytes**。
3. JSON 解析后的全部内容与修复前相同。
4. 恢复文件仅将 `CRLF` 换为 `LF` 后，**逐字节等于修复前 Git 中的文件**。

第四项比 JSON 内容比较更严格：键顺序、重复键、空格、转义、数值字符和所有文字均保持原样。恢复过程只改变行结束字节，没有改动科学数据或任何样式字段。

逐文件的修复前／恢复后哈希、字节数和内容一致性证明见 [optimization_asset_byte_restoration.json](optimization_asset_byte_restoration.json)。另外使用 `core.autocrlf=true` 核对 Git 入库结果，24 份文件的 Git blob 均与原始候选字节相同。

这些 JSON 自各自的历史晋升提交到本次比较起点 `3ded88689af1a9168a47aaeb6e4c860a2e575191`、再到优化分支，内容没有被本次优化改写。本轮恢复解决的是既有的 Git 交付字节问题。

### 恢复范围

以下路径均相对于 `templates/origin_styles/`。

| 文件组 | 数量 | 精确恢复方式 |
| --- | ---: | --- |
| BET、XRD、Raman、UV_vis_DRS、Tauc、PL、photocurrent、FTIR 的 `snapshots/` 与 `data_snapshots/` JSON | 16 | 恢复 CRLF，保留原来没有末尾换行的状态 |
| `data_snapshots/XPS_in_situ.json`、`data_snapshots/EPR.json` | 2 | 同上 |
| `snapshots/EPR.json` | 1 | 第 132–193、206 行保持 LF，其余 CRLF |
| `snapshots/Mott_Schottky.json` | 1 | 第 145–152、168 行保持 LF，其余 CRLF |
| `data_snapshots/Mott_Schottky.json` | 1 | 五组遮罩字段、第 469、471 行及最后一行保持 LF，其余 CRLF |
| `snapshots/XPS_in_situ.json` | 1 | 第 240、341–356、371 行保持 LF，其余 CRLF |
| `snapshots/XPS_non_in_situ.json` | 1 | 第 222、299–376、386 行保持 LF，其余 CRLF |
| `data_snapshots/XPS_non_in_situ.json` | 1 | 33 组填充字段、各曲线的 `fill_area` / `fill_color` 及末行，共 334 行保持 LF，其余 CRLF |

以上行号只描述本次恢复时的文件，不作为运行时代码规则。程序仍直接核验文件字节，不根据行号调整文件。

六份混合换行文件的核验结果：

| 文件 | 恢复后字节数 | 原 manifest SHA256 前 12 位 |
| --- | ---: | --- |
| `snapshots/EPR.json` | 4,771 | `2913cb4c1616` |
| `snapshots/Mott_Schottky.json` | 4,121 | `599b8963a252` |
| `data_snapshots/Mott_Schottky.json` | 12,946 | `a99b4cb5b197` |
| `snapshots/XPS_in_situ.json` | 8,642 | `b17696ba29ed` |
| `snapshots/XPS_non_in_situ.json` | 7,967 | `98a0d6704fbe` |
| `data_snapshots/XPS_non_in_situ.json` | 166,487 | `acedfe88c492` |

核验实际使用完整的 64 位 SHA256；表中仅为便于阅读而缩写。

### 修复边界

根据 [Git 官方 gitattributes 文档](https://git-scm.com/docs/gitattributes)，对这些需要按原始字节核验的 JSON 使用 Git `-text` 属性，防止下一次提交或 checkout 再次改变换行，同时保留文本差异查看能力。manifest 的现有哈希、文件大小、接受状态、验证证据及作图规则保持不变。另逐项比对了远程树中的 77 份原生模板、参考工程、PNG、厂商 ZIP 及 manifest，均与原比较起点的 Git blob 相同。

**这是恢复已登记资产的原始字节，不是重新晋升模板，也没有继承或新增 Origin 视觉验收结论。** 数据绑定、保存重开、样式读回、原生 TIFF 和实际 PNG 检查仍按正式流程执行。

## 2. 第二轮模板实现精简

在 `src/core/template_format_executor.py` 中，XPS in-situ 归一化函数已经生成独立的新表，工作簿导入前又逐行复制了一遍。本轮删除第二次整表复制，直接使用该函数已经拥有的结果。

归一化公式、三个样品的竖直偏移、组分顺序、填充基线、目标列及图层绑定均不变；行数检查继续保留。

同时增强两个真实工作场景的回归检查：

| 场景 | 检查内容 | 测试位置 |
| --- | --- | --- |
| XPS 归一化后继续作图 | 原输入表未被改写；任务缓存读到写回后的 CSV；三本工作簿全部 18 个目标列与 CSV 精确一致 | `tests/test_template_format_executor.py` 的 `test_xps_in_situ_verified_binding_and_workbook_preserve_reviewed_native_topology` |
| 一次导出失败后再次运行 | 上次的 CSV 与样式 JSON 不进入新任务；输入作用域在失败后正常释放 | `tests/test_template_execution_inputs.py` 的 `test_failed_export_does_not_reuse_inputs_in_next_job` |

已有 EPR 用例继续核对 Origin 处理后的 CSV 重新读取，以及运行期间模板源字节变化会阻止验收。

## 3. 独立旧新结果对照

对照读取原始提交对应源码中的函数，执行旧实现和当前实现，并比较完整返回值或产物。没有让两种不同绘图路线互相充当基线。

| 对照对象 | 范围 | 结果 |
| --- | --- | --- |
| 共享横轴插值 | 固定随机种子 `260908`；600 组输入、61,986 个查询，包含重复 X、近似相等阈值、范围外查询、空表及不同数值尺度 | 每个结果精确相同，未使用近似容差 |
| Mott 共同截距拟合 | 30 组输入，3–8 个点、1–5 条曲线，保留原搜索网格与迭代 | 截距、斜率、R²、目标函数返回值精确相同 |
| 有效行范围 | 200 组，包含首尾空值、内部缺口和非有限值 | 结果精确相同 |
| EPR 原生标签 | 2、3、4 条曲线与 15、40、1,920、4,000 点，共 12 组 | 标签文字、坐标、属性和 LabTalk 指令完全相同 |
| PNG 去元数据 | RGB、RGBA、L、P、1、I;16 六种模式，含文本元数据和 DPI | 旧新导出的文件字节完全相同 |
| XPS 工作簿准备 | 首次归一化，以及已归一化数据再次进入 | CSV 文件字节、18 列数据、列 metadata、返回结果完全相同；源表未变 |

已验收 Mott 数据的永久回归用例还保留完整精度断言：共同截距为 `-1.040673375074791`，三个斜率和三个 R² 均逐项精确比较。

上述对照核实的是数据、图形指令与图片处理步骤的等价性。它们不能替代实际 Origin 渲染和人工预览。

## 4. 已运行的模板定向测试

本轮首次模板定向运行：

```powershell
python -m pytest -q tests/test_template_execution_inputs.py tests/test_template_format_executor.py tests/test_origin_template_binding.py tests/test_origin_template_format.py
```

结果为 **220 passed**。随后增加失败任务缓存释放用例，再运行 `tests/test_template_execution_inputs.py`，结果为 **11 passed**。两次有重叠，不能相加当作独立用例总数；本轮最终完整测试结果见下节。

开发中的定向检查、旧新对照和 `git diff --check` 均已通过。涉及真实 Origin 的部分仍应按第一轮交接文档，在同一环境、同一输入、同一路线下比较优化前后。

## 5. 其他优化与完整环境验收

### 新增优化及实际行为

| 模块 | 本轮修改 | 验证与保留规则 |
| --- | --- | --- |
| HPLC 分组 | 合并组时维护已有日期范围；手工排除后一次索引证据边，避免每组重新扫全部关系 | 跨日期、手工排除及完整分析结果一致；分组阈值、边顺序和评分方法不变 |
| XPS 专用流程 | 父进程及 renderer 使用共享 Windows 进程查询；CSV 表头、X 和显示 Y 范围一次流式读取，原为 3 次、回退时 4 次 | 仍只管理本任务拥有的进程；保留 measured / Envelope 优先和全 Y 回退；生产代码净减少 98 行 |
| Origin 样式读回 | 一条曲线的 18 个查询命令合并执行，再读回各值；批量拒绝时使用原逐项回退 | 本轮通常由 36 次往返降至 19 次，RGB 情况由 38 次降至 20 次；只改变读取方式 |
| 报告路径 | 同时正确清洗 POSIX、Windows、UNC 绝对路径；HTTPS 不再被误认成 UNC | 已知根目录仍优先相对化，来源字段保留；不改变真实输入路径或作图指令 |
| 回归基础设施 | 增加显式触发的完整 Windows CI，实际执行 PowerShell、Win32 进程枚举与完整模板／vendor ZIP 检查 | 不为每个小源码或文档提交默认跑全套；报告写到 runner 临时输出根 |

新测试覆盖了这次改动中的实际分支：CSV 重写与失败后再次运行、遮罩非 1 起点和 512 行分块边界、批量返回截断后的回退、单行中文表头的 PowerShell 数值数组、真实 Windows Toolhelp 自身 PID、跨日期手工排除。跨平台测试使用明确的 Path 语义，不靠改预期值掩盖结果错误。

### 补充独立结果对照

| 对照 | 范围与结果 |
| --- | --- |
| 共享 X 完整建表 | 2,000 组，旧新完整表精确一致 |
| XPS CSV 流式读回 | 400 组有效、缺失、非有限值、不同表头与错误输入，数值以及错误类型／消息完全一致 |
| XPS Excel 解析 | 2 个实际生成的多 sheet 工作簿，解析结果一致 |
| EPR 数据准备 | 12 组含背景扣除、平滑、归一化的曲线，处理数据完全一致 |
| 预览图片 | 6 对不同模式 PNG，RMS、尺寸、并排图解码像素完全一致 |
| 原始副本哈希查询 | 61 次，重复内容仍选择原来的第一个匹配路径 |
| Origin 样式 | 从 87 份真实仓库曲线样式构造普通／RGB 共 174 次读回，旧新完整字典一致；模拟通信总数从原比较起点的 10,701 次降至 3,393 次 |
| HPLC／LC | 100 组各 60 条记录、8 组各 15 条记录的完整分析、100 组表头候选、4 种 LC 处理模式及峰检测边界，旧新结果一致 |

通信次数是模拟接口调用计数，不等于实机耗时。HPLC 局部 2,000 条记录、500 组、3,000 条关系的对照计时约 0.1173 秒 → 0.0416 秒，仅说明该步骤减少重复扫描，不能外推整个项目的提速比例。

### 正式入口和实际 Excel 产物

使用受控合成输入分别从本次比较起点和当前代码执行正式 `process --no-origin`：XRD 601 点、PL 351 点、EIS 80 点。三个 `processed_data.csv` 逐字节一致；metadata 除本轮有意修复的外部 `source_files` 路径清洗外，所有字段一致。再运行明确文件的 `process --source ... --only-type XRD --no-origin`，其 CSV 也一致。

另外实际执行 OpenLab 解析及现有 workbook builder，使用 3 份受控 DX／RX 输入形成 2 个批次、3 个结果集、9 个峰。旧新各生成：

- split 模式：3 个 XLSX、10 张工作表；
- analysis 模式：1 个 XLSX、7 张工作表。

所有单元格、顺序、样式、行高、列宽、冻结窗格和合并区域一致，17 张预览的解码像素一致，并实际打开代表预览检查。本 Linux 环境缺少部分中文字形，两边表现相同；电脑端仍应在现有中文字体环境检查文字显示。本项是实际 XLSX 生成，不是只模拟 workbook。未执行需要 Agilent 授权软件的原始数据重新积分。

### 最终整套检查

以下记录按最终整套结果统计，不累加开发期间重叠的定向测试。

| 项目 | 最终记录 |
| --- | --- |
| Windows 完整 checkout、依赖与二进制资产的全套测试 | **1,270 passed、0 failed、2 skipped、59 subtests passed，98.14 秒**；[完整工作流](https://github.com/zhichaojin357-ctrl/ResearchDataOriginPipeline/actions/runs/34181999035)，执行提交 `375840d04f74600bfd3a50f344e32b13ece4e49a` |
| Linux 最终 pytest | **1,244 passed、18 failed、10 skipped、59 subtests passed，20.68 秒**；18 项均为当前环境缺少 12 项 OTPU 相关资产检查、2 项真实 vendor ZIP、4 项 powershell.exe。最终 Windows 完整 checkout 另行覆盖这些检查 |
| `validate --scope runtime` | **28 项检查，0 failures、5 skipped**；其中完整 14 项 Origin 资产组的完整性检查通过。跳过 Origin 调用、历史 PPT／产物及不能代表视觉证据的项目 |
| `readiness --scope runtime` | **6 项检查，0 failures、0 warnings、3 skipped**；`ready=true`、`scope_ready=true`、`release_ready=false`。三个跳过项是 runtime 范围之外的历史包、旧路径、用户 PPT |
| 24 份恢复文件及远程 Git 字节 | 全部匹配原 manifest SHA／size；`core.autocrlf=true` 的 Git 入库过滤保持字节；已逐项核对远程树中这批 43 个源码、测试、配置及资产 blob 与本地一致 |
| Windows / Origin 实际作图、保存重开和可见效果对比 | 尚未完成，不标记为通过 |

Windows 的 2 个跳过项需要用户真实历史锁定结果包。PowerShell 5 个动态 helper 测试、真实 Win32 Toolhelp 进程枚举、文件身份／junction、vendor ZIP 与完整模板检查均已在 Windows 执行，未用伪资产替代。

首次完整 Windows 运行在修复快照字节前得到 1,222 passed、10 failed、2 skipped；10 个失败都属于资产解析／绑定检查。恢复原字节并加入本轮测试后，最终这 10 项全部通过。Linux 的环境失败由 Windows 对应实际检查覆盖，没有简单删除或跳过失败用例。

工作流 artifact 名为 `windows-no-origin-regression`，包含原始 pytest XML 与两份 runtime JSON，保留 14 天。运行链接和本文的统计、范围、提交记录可用于后续追踪。验收后的收尾提交只更新说明文档，未再改变源码、测试或资产。

### 环境与证据边界

Linux 使用 Python 3.12.13、NumPy 2.3.5、SciPy 1.17.0、pandas 2.2.3、Pillow 12.3.0、pytest 9.1.1；缺失的 pybaselines 1.2.1、pyGAPS 4.6.1、impedance 1.7.1 及其必要依赖放入隔离测试目录，没有升级原有科学计算包或修改项目依赖声明。

Windows CI 使用 Python 3.12.10、NumPy 2.5.3、SciPy 1.18.1、pandas 3.0.5、pytest 9.1.1、originpro 1.1.15、OriginExt 1.2.5、pywin32 312；完整版本见工作流安装日志。它使用全新 runner 和完整仓库，按项目声明安装依赖。该环境用于跨平台自动回归，不能代替用户已验收的 Origin 和字体环境。电脑端应继续使用现有依赖，避免把环境升级与本次优化混在一起。旧新数据与 Excel 差分均在相同环境运行。

`compileall`、OpenLab JS 语法检查及 `git diff --check` 均通过。完整 Windows 工作流保留 pytest XML、validation JSON 和 readiness JSON，日志还记录依赖版本及项目检查内容。只允许 `contents: read`，不接触原始数据、不启动 Origin。

## 6. 电脑端仍需完成的验收

使用本机现有项目环境，不在性能优化时顺手升级 Origin 或科学计算依赖。完整自动测试与模板完整性检查通过后，对第一轮交接文档列出的受影响代表图执行：

- 同输入、同路线比较处理数据、点数、顺序、缺失值及遮罩。
- 保存并重开 OPJU，读回曲线绑定、图层、可见性和关键样式。
- 检查原生 TIFF 的页面物理尺寸、像素和有效 DPI。
- 比较最终 PNG 解码像素，并实际查看标签、字体、图例、坐标轴和是否存在模板残留。

资产的原始哈希恢复、自动测试通过或读取到完整模板，都不能单独证明作图效果没有变化。正式合并验收应保留这一区别。
