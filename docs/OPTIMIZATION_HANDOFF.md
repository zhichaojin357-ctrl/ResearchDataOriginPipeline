# 优化分支：电脑端测试与应用交接

**二轮复查入口：[OPTIMIZATION_SECOND_REVIEW.md](OPTIMIZATION_SECOND_REVIEW.md)。**
本轮已补查跨平台报告路径、进程快照、PowerShell helper、HPLC 与 XPS，
并在完整 Windows 仓库运行 CI。快照换行字节按既有 manifest 哈希恢复，
未通过修改验收哈希消除失败。最新测试状态以二轮报告为准；本文件第 5 节
是首轮环境记录，其中的失败、缺文件及未运行 Windows 状态已不能代表现状。
**真实 Origin 出图和优化前后同路线视觉比较仍待电脑端完成。**

本次目标：减少重复扫描、解析、内存复制及 Origin 通信，保持同一输入、同一作图路线的结果。代码已实现并提交到工作分支；**Windows / Origin 视觉验收尚未完成，不应直接当作已验收版本合并。**

- 分支：`codex/optimize-pipeline-preserve-plots`
- 本次比较起点：`3ded88689af1a9168a47aaeb6e4c860a2e575191`。这个提交只用于本次前后对比，不是永久运行基线。
- 采用一个分支、按职责拆提交。数据准备与两种绘图方式共用接口，拆成两个长期分支会重复修改这些接口。应用完整分支，测试按下表分组。
- `.otpu` 固定路线和 `.oth + JSON` 自适应路线均保留；未更换模板资产、颜色、字体、拟合区间、插值公式或科学评分方法。
- 第二轮仅恢复 24 份样式 / 数据 JSON 的原始换行字节，使其重新匹配既有 manifest 哈希；样式字段和数据内容不变。原始数据、原生模板文件、manifest 与 `master` 均不变，具体恢复证据见顶部链接。真实环境验证后再决定合并。

## 1. 先读这一段

电脑端 Codex 应先读取 `AGENTS.md` 和本文件，检查工作区状态及现有 Python / Origin 环境。取得分支后，在现有环境中测试，不顺手升级依赖或重新采集模板。

```powershell
git fetch origin
git switch --track origin/codex/optimize-pipeline-preserve-plots
```

如果本地已有同名分支，使用普通 `git switch codex/optimize-pipeline-preserve-plots`，保留尚未提交的本地工作。

建议给电脑端 Codex 的任务：

> 按 docs/OPTIMIZATION_HANDOFF.md 验收这个优化分支。先核对现有环境及完整资产，运行受影响测试；对涉及图形的改动，用同一输入、同一路线比较优化前后，核对数据、绑定、样式、原生 TIFF 和 PNG。修复本批引入的问题，记录无关既有问题，不升级依赖、不重采模板、不放宽验收。完成后更新本文件的验收记录；有结果差异时先定位原因，不直接合并。

## 2. 哪些改动需要看图

“不直接绘图”不等于实现不会出错；数据准备也会影响最终曲线。下面的分级用于选择测试范围。

| 标记 | 含义 | 验证重点 |
|---|---|---|
| A | 不参与绘图数据或绘图指令 | 对应测试、报告内容、文件选择或调用次数 |
| B | 修改进入图的数据准备或复用方式，目标是数值完全相同 | 数据值、点数、顺序、缺失值、重复 X、缓存更新；受影响代表图 |
| C | 修改 Origin 通信、图层操作、图片导出或图像处理 | 模拟测试 + Windows 同路线实际产物比较 |

### 优化清单与测试标记

编号对应本次合并审查方案的 20 组建议；测试组命令见下一节。

| 编号 | 已实施内容与主要位置 | 标记 | 测试组 / 电脑端补验 |
|---|---|---|---|
| 1 | executor 去 PNG 元数据改用图像复制，取消整图 Python 像素列表 | C | T3；RGB、RGBA、灰度、调色板等模式像素与 DPI；不重编码 TIFF |
| 2 | builder 先判断 Raman、PL、光电流专用输入，再决定是否通用扫描 | B | T2；选中文件及曲线顺序一致 |
| 3 | scanner 一次目录遍历；队列不再全目录扫描；新增 process 明确文件入口；triage 先限定目录 | B | T1；扫描分类与队列范围；单文件处理 |
| 4 | EIS 发现与建表复用清洗结果；DRS/Tauc 共享原始转换；EPR、XPS 复用已核对数据；Excel 单次打开后读多表 | B | T2、T4；所列类型的 processed data 与代表图 |
| 5 | `template_product_tables.py` 用递增区间指针处理原有共享 X 插值 | B | T2；重复 X、近似相等、范围外及原算式完全一致；独立 X 不改为共享 X |
| 6 | Origin 样式查询合并；遮罩按列及范围缓存并分块读回；读取实际图层数；对象名称查找；同图层激活去重；轻量进程查询 | C | T3；多层、空中间层、遮罩、对象、用户已有 Origin |
| 7 | `origin_batch.py` 建立单次执行的原始副本哈希索引，正式导出前仍重新核对选中文件 | A | T5；同内容首选路径、执行前源文件变化、发布失败 |
| 8 | `style_registry.py` 与 `project.py` 任务内复用 manifest / JSON / YAML / 哈希；任务结束清除缓存 | B | T1、T3；任务间配置更新；结束时资产哈希必须重新计算 |
| 9 | OpenLab 厂商缓存命中后只做一次完整文件校验 | A | T4；真实 vendor ZIP 完整性及缓存命中 |
| 10 | `template_inputs.py` 将 CSV、合同、绑定结果在选路与执行间共享；EPR / XPS 重写数据后显式更新 | B | T3；重写后不使用旧数据；两种路线及自动选路 |
| 11 | 自适应 XPS 可变曲线模式不创建随后必然删除的参考文字对象 | C | T2、T3；两种 XPS 的实际图例、标签和曲线数 |
| 12 | HPLC 日期有序窗口提前结束、相似度按有序键复用；Excel 按批次、结果集、进样建立索引 | B | T4；重打识别、Excel 内容、峰排序及格式 |
| 13 | JEOL 中间对象不长期保留已无用途原始通道；HPLC 正式入口避免重复深拷贝；compact XPS 不构造未输出的 raw rows | B | T2、T4；公开深拷贝接口仍保持原行为；输出字段和数值一致 |
| 14 | Mott 均值 / 总变差移出候选循环；EPR 最近点有限选择；表头评分复用统计；峰检测去重；LC / XPS 只准备所需信息；DX 减少数组复制 | B | T2、T3、T4；拟合、标签坐标、表头、峰候选与基线一致 |
| 15 | 通用批处理取消中间一次 TIFF 完整解码；保留导出器检查及发布后最终文件检查 | A | T5；最终物理尺寸 / 600 dpi 失败仍能检出 |
| 16 | 通用 adapter + PowerShell helper 在同一个独立 Origin 中保存、清空、重开、导出；整列写入有明确失败回退；增加阶段计时 | C | T3、T5；实际 COM 数组写入、原 PNG 尺寸像素、重开后原生 TIFF |
| 17 | 拆出输入准备、数值计算、共享横轴、预览比较、样式校验及进程快照模块；原有必要导入兼容保留 | B / C | T2、T3；大文件职责变小，未引入插件框架 |
| 18 | 正式计划 JSON 避免连续重写；比较预览共享一次图片解码；元数据读取复用；报告依据实际路线与 EIS `not_run`；通用 process 批末汇总配色报告 | A / C | T1、T2、T3；正常和受控异常退出的成功产品记录、报告内容与比较像素 |
| 19 | 删除已定义末行后的恒假检查；连续行范围减少列表；绘图合同规范化一次；错误 YAML 明确报错，保留 Windows 路径兼容 | B / C | T1、T3；缺失 / 断行 / 绑定拒绝、有效配置不变 |
| 20 | 删除恒为 None 的私有模板 OPJU 入口、无生产调用的旧 TIFF 改标签工具及对应旧测试；共用 manifest 常量；说明配置占位字段 | A | T1、T3、T5；保留正式物理 DPI 验证、外部参考路线及必要兼容入口 |
| 工作流 | AGENTS 第 10 节按影响范围测试；测试临时目录隔离；validate 读实际配置值并输出 JSON；readiness 读结构化报告；新增可选 runtime 范围 | A | T1；runtime 不声称 full release ready，默认仍为 full |

PNG 导出在合并后的通用路线中移到了保存重开之后，导出参数保持原样。这涉及执行顺序，必须比较基线 PNG，不能只验证 TIFF。

## 3. 可直接运行的测试组

以下命令在仓库根目录执行，使用电脑已有项目 Python 环境。单元测试默认禁止真实 Origin；PowerShell 模拟测试需要 Windows，但不依赖实际图形效果。

只修一组时先运行该组。整批收尾直接完整测试一次，不需要再把所有组重复一遍。

### 二轮新增或补强的定向检查

这些命令用于修改相应模块后的快速回归；完整测试已覆盖它们时不再逐组重复。

| 范围 | 本轮重点 | 电脑端仍需补验 |
|---|---|---|
| 报告路径 | POSIX / Windows / UNC 路径、路径空格、已知根相对路径；保留 URL 和科学单位 | 在本机真实输入运行报告，核对来源追踪不丢失 |
| 进程快照 | 枚举、结构和异常；Windows 真实 Toolhelp 读取当前 Python 进程 | Origin 正常退出；已有用户实例不被接管或关闭 |
| PowerShell helper | 单实例保存重开、批量写列及失败回退、输出根约束 | 真实 COM 写入后的点数与数值，重开后的 PNG / 原生 TIFF |
| HPLC | 重打分组维护日期范围、一次整理组内证据；保留人工排除和证据顺序 | 现有 HPLC 重打分组、Excel 内容 / 格式 |
| XPS | 一次读取 CSV 供多图层使用；专用子进程复用统一进程管理 | `xps-heterojunction-stacked` 同输入前后数据 / 图形；正常退出和已有 Origin 拒绝 |

```powershell
python -m pytest -q tests/test_output_sanitizer.py tests/test_powershell_helpers.py tests/test_project_contracts.py tests/test_reviewed_queue.py tests/test_triage_and_process_queue_validation.py tests/test_xrd_overlay.py
python -m pytest -q tests/test_origin_process_snapshot.py tests/test_origin_operations.py
python -m pytest -q tests/test_origin_helper_script.py tests/test_origin_adapter.py tests/test_hplc_calibration_origin_script.py
python -m pytest -q tests/test_hplc_analysis.py tests/test_hplc_openlab.py tests/test_hplc_openlab_vendor_runtime.py tests/test_xps_heterojunction_stacked.py tests/test_xps_no_artifact_contracts.py
```

Windows CI 的通过只覆盖其中可自动执行的代码、PowerShell 及进程测试。
它没有安装、启动 Origin，也没有替代第 4 节的实际图形验收。具体本轮修改与
最终各环境测试证据见二轮报告，不沿用首轮失败数字判断当前版本。

**T1：扫描、配置、队列、项目验收与临时目录**

```powershell
python -m pytest -q tests/test_runtime_path_configuration.py tests/test_process_cli.py tests/test_output_routing.py tests/test_auto_queue.py tests/test_reviewed_queue.py tests/test_triage_and_process_queue_validation.py tests/test_triage_recognition.py tests/test_readiness.py tests/test_project_contracts.py tests/test_origin_governance.py tests/test_processor_profiles.py
```

明确单一普通表格的最小正式调用：从已有数据中选一份输入，将 `$source`、`$type`、`$outputRoot` 设置为真实路径、注册表类型及新的外部输出目录。

```powershell
python run.py process --source $source --only-type $type --output-root $outputRoot --no-origin
```

同类型多个文件可重复 `--source`。厂商原始格式使用其原有专用入口，不通过这个命令绕过注册表。队列报告中的 `inventory_scope` 现在表示本次选择范围，不再暗示已经盘点全库。

**T2：模板数据准备、共享横轴、XPS / EPR 与预览**

```powershell
python -m pytest -q tests/test_template_product_builder.py tests/test_template_product_builder_strict.py tests/test_epr_overlay.py tests/test_xps_heterojunction_stacked.py
```

**T3：两种模板执行、Origin 通信、遮罩与通用导出**

```powershell
python -m pytest -q tests/test_template_execution_inputs.py tests/test_template_format_executor.py tests/test_origin_operations.py tests/test_origin_style_assets.py tests/test_origin_adapter.py tests/test_origin_helper_script.py
```

**T4：科学数据、JEOL 与 HPLC / Excel**

```powershell
python -m pytest -q tests/test_hplc_analysis.py tests/test_jeol_epr_decode.py tests/test_adapter_bridges.py tests/test_hplc_openlab.py tests/test_hplc_openlab_vendor_runtime.py tests/test_processor_behaviors.py tests/test_eis_cleaning_and_fitting.py
node --check scripts/data_types/hplc_lc/build_openlab_workbook.mjs
```

使用已有 OpenLab 小批数据再执行一次正式 `hplc-openlab-export`，检查进样、批次、峰顺序、工作表、数值、格式及预览。语法检查和模拟 workbook 比较不能替代实际 XLSX 生成。保留原来的 vendor ZIP 校验，不用空压缩包替代。

**T5：清单、哈希索引、发布及最终 TIFF 验证**

```powershell
python -m pytest -q tests/test_origin_batch_manifest_runner.py tests/test_shared_helpers.py tests/test_origin_adapter.py
```

**整批收尾**

先配置新的、位于源码及原始数据之外的输出根。以下两个项目检查共用该输出根，使 readiness 读取刚生成的 validation JSON。

```powershell
python -m pytest -q
python run.py validate --scope runtime
python run.py readiness --scope runtime --no-desktop-review-xlsx
```

`runtime` 检查软件、配置及模板资产，不要求历史锁定包、队列或用户 PPT 全部存在；它的 `release_ready` 始终为 false。需要审查整个既有运行环境时，再依次运行默认的 `validate`、`readiness --no-desktop-review-xlsx`。这些命令均不能代替实际看图。

## 4. Windows / Origin 必须补的验收

### 同输入、同路线的基线

可以将比较起点放在独立工作树，输出写到两个不同的新目录。不要在同一输出目录覆盖前后结果。

```powershell
git worktree add ..\ResearchDataOriginPipeline-before-opt 3ded88689af1a9168a47aaeb6e4c860a2e575191
```

**比较起点也存在同样的 24 份 JSON 换行失配。** 如果基线因此被正式资产
校验拒绝，不修改 manifest、阈值或校验代码。可以在这个隔离基线工作区中，
仅应用二轮报告列出的同一批 24 份 JSON 原始字节恢复及对应 `.gitattributes`
规则，再运行原 manifest 的完整性检查。不要把优化后的 Python / PowerShell
代码复制到基线。

记录基线提交、这一步预处理的文件清单和资产哈希，并确认两边使用的资产
SHA256 完全相同、各自的正式完整性检查通过。随后比较“相同资产下的旧代码
与新代码”。这样既能运行原代码，也不会用更换样式或放宽校验掩盖差异。
24 份文件的内容等价及原哈希恢复证据见
[二轮报告第 1 节](OPTIMIZATION_SECOND_REVIEW.md#1-模板完整性失败的真正原因)。

电脑端 Codex 应读取本机现有 pairing、配置、用户样式及已核验模板位置，分别在基线与优化分支使用同一个环境、输入和配置。新工作树的本机配置不会自动继承，需要明确传入或使用同样的本机设置。

正式模板命令示例，变量必须取现有真实输入；前后各执行一次，只替换输出目录：

```powershell
python run.py template-format-products --pairing $pairing --output-root $outputRoot --asset-only --only-type $type --origin-style-mode $route --with-origin
```

`$route` 为 `otpu` 或 `oth-json`。既有任务需要用户样式或独立 replay 报告时，两次都传入相同参数。不要把更换模板、缩减曲线数或改走另一条路线当作修复。

### 代表产品与真实分支

| 路线 / 改动 | 必测对象 | 核对内容 |
|---|---|---|
| 固定 OTPU | 当前 manifest 的 14 个正式产品，各取一份已验证形状的现有输入 | 公共绑定和校验已变动，每类已有样例各跑一次；固定样品数、隐藏曲线、独立 X/Y、多层与标准卡 |
| 自适应 OTH + JSON | 当前 14 个产品的已有代表输入；EPR、两种 XPS 补一个合法的不同曲线数 | 颜色循环、直接标签、图例、图层规则；不能沿用旧模板样品文字 |
| 自动选路 | 一份正好匹配固定合同的输入；一份合法可变曲线数的输入 | 与基线选择同一路线；显式路线不能偷偷 fallback |
| 遮罩读回 | 有遮罩 / 无遮罩；超过 512 行、跨第 512 / 513 行边界；多曲线共享 X 列 | 批量与逐行结果相同，范围起点及尾块正确，失败回退有记录 |
| 图层与对象 | 多层图，含空中间层；对象名称查找；保存重开后再访问 | 图层不能漏读，旧对象不能跨重开使用，标签不能串层 |
| 通用 process / origin-batch | XRD；含独立 X/Y 的 EIS 或等价现有样例；中文列名与缺失值 | 只有一个 Origin 实例；整列 COM 写入与逐单元格结果一致；受控回退仍可用 |
| 进程管理 | 无用户 Origin 的正常启动 / 退出；已有用户 Origin 时的启动拒绝 | 不接管、不关闭用户实例；仅清理本次任务拥有的进程 |

这次两条路线的公共底层都改变了，首轮对当前全部产品各取一个既有样例；不要求穷举每种曲线数和点数。之后只修某一类型时，重跑受影响项即可。已有输入不能覆盖某分支时，记录缺口，不伪造通过。

### 通过条件

1. processed data 的数值、点数、排列、缺失值、遮罩及拟合结果保持一致。
2. OPJU 能重开，曲线可编辑，X/Y 绑定、图层、显示 / 隐藏状态及顺序一致。
3. 颜色、线宽、符号、字体、坐标范围、刻度、图例、标签与版式一致。
4. TIFF 继续由 Origin 原生导出，尺寸与物理 600 dpi 一致；PNG 参数、尺寸、透明度和解码像素一致。
5. 复用现有预览比较函数生成差异与并排图，并实际打开检查。比较同一路线优化前后，不要求 OTPU 和 OTH + JSON 互相像素一致。

OPJU 文件字节可能含保存时间等变化，不要求整个工程文件哈希一致。数据、绑定、可见结果和原生导出必须核对；像素差异出现时记录并定位，不能自动提高容差。

### 计时怎么读

通用导出返回 `OriginResult.stage_timings_seconds`；`origin-batch` 成功执行行也保存该字段。helper 输出 `ORIGIN_STAGE_TIMINGS=`，包括启动、导入、绘图样式、保存、重开、图片导出和退出；Python 补充准备、helper 总耗时和 TIFF 验证时间。字段存在重叠，不要全部相加当作总时间。

分别记录同一环境的首次启动及后续运行；对比相同输入。模板路线尚无同等粒度的完整计时字段，可记录正式命令总时长。局部插值或 COM 调用次数减少不能换算成整个项目的提速百分比。

## 5. 首轮历史记录（已被二轮报告更新）

以下数字和环境限制仅记录首轮执行时的状态；当前通过 / 失败 / 跳过及
资产完整性结果以 [二轮报告](OPTIMIZATION_SECOND_REVIEW.md) 为准。

执行环境为 Linux，未安装 Windows / Origin；通过 GitHub 文本快照获取源码。本地未能取得仓库中的 61 个二进制文件（14 OTPU、13 OPJU、33 PNG、1 vendor ZIP）。远程提交基于原始完整 Git tree 构造，**没有删除这些资产**。

| 检查 | 本次结果 |
|---|---|
| 整批 pytest | 1193 passed、33 failed、8 skipped、59 subtests passed；20.27 秒，仅代表本地测试环境 |
| 整批后修复 | 其中 1 项新增测试自身替换全局 importlib 导致干扰；改为模块内接口补丁，该测试文件定向复测 6 passed |
| 剩余 32 项失败分类 | 14 项缺二进制资产；4 项需要 powershell.exe；5 项缺当前依赖；9 项既有 Windows 路径 / Linux 路径断言或清洗差异 |
| validate runtime | 28 项检查，2 项失败：依赖不全、模板资产完整性；5 项未检查 / 不在范围内。文本快照还存在与既有资产记录不一致的字节哈希，需在完整电脑工作区核对 |
| readiness runtime | 6 项检查，1 项失败：上述 validation 未通过；3 项不在范围内。ready / scope_ready / release_ready 均为 false |
| 数值对照 | 共享横轴、缺失 / 独立 X/Y、Mott 搜索、EPR 最近点使用旧实现与新实现对照，结果一致 |
| 图像处理对照 | PNG 多种模式的解码像素一致；预览并排及差异计算的旧 / 新结果一致 |
| Origin 模拟 | 样式、遮罩、合同、进程、helper 证据及导出测试已运行；常规每条曲线样式通信由 60 次减为 36 次 |
| OpenLab JS | 语法检查通过，模拟 workbook 的工作表、值、格式、顺序与旧实现一致；真实 Excel 待电脑验证 |
| 独立审查 | 复查了 Origin diff、调用关系、Load / PutWorksheet 官方接口；未发现确定回归，实机行为仍待验证 |
| 实际 Origin 与图片 | 未执行，不能声明本批作图效果已验收 |

不通过修改测试期望、补空模板、跳过最终图像检查或改变科学参数来消除上述环境失败。电脑端若同一失败仍出现，先与比较起点复现，区分既有问题和本批回归。

已定位一项既有资产字节问题：BET 的 style / data snapshot 在 Git 中为 LF 换行，manifest 记录的哈希与 CRLF 字节匹配，而 `.gitattributes` 要求这些 JSON 使用 LF。新工作树可能同样触发该检查。电脑端应核对原已验收工作区与比较起点的实际字节；本次没有批量改模板、重写 manifest 哈希或放宽完整性验证。

Origin 接口审查参考官方 [Application.Load](https://docs.originlab.com/com/classes/application/load/) 与 [Application.PutWorksheet](https://docs.originlab.com/com/classes/application/putworksheet/)；接口文档确认不能代替实际 COM / Origin 测试。

## 6. 没有强行实施的建议

- 跨多个产品长期复用同一 Origin：仅在实测启动耗时值得且产品间状态隔离通过后再做；本次已合并单个通用产品的两次生命周期。
- 不换 GPU、拟合器、XRD Jade 排名、峰匹配优先级或强度规则。XRD 部分相似排序分支实际有重复峰次序差异，未强行合并。
- 已拆出确定职责、清理重复计划与报告事实；没有全面重写历史验收状态机及对外 JSON schema，也没有删除仍有兼容用途的 XPS 旧链和受控校准工具。
- 保留公开函数需要的旧语义和兼容入口。运行参数、注册表外部结构及既有默认阈值保持；`force_refresh` 等原有兼容占位项不借本次优化激活新的行为。
- 有效配置不变；错误 YAML 在已有 Windows 路径修复后仍不合法时，现在明确报错。该错误处理变化已测试并在此说明。

这些项涉及行为扩展、科学结果或尚无计时依据的更大改造，不属于已经证明可等价替换的冗余工作。

## 7. 电脑端追加验收记录

完成每组后在这里记录，避免下次 Codex 重复调查：

| 项目 | 状态 | 待填写证据 |
|---|---|---|
| 完整工作区 / 环境 / 资产 | 待执行 | 分支 HEAD、Python / Origin / 依赖版本、资产校验 |
| 整批测试 | 待执行 | 命令、通过 / 失败 / 跳过及既有问题 |
| 固定 OTPU | 待执行 | 输入、运行目录、数据与样式读回、PNG 比较 |
| 自适应 OTH + JSON | 待执行 | 同上，另记 EPR / XPS 可变曲线数 |
| 自动选路与遮罩 / 多层 | 待执行 | 代表样例及结果 |
| 通用单实例导出 | 待执行 | 实例数、重开、COM 写入、PNG / TIFF、计时 |
| JEOL / OpenLab | 待执行 | 数据与 Excel 前后对照 |
| runtime 项目检查 | 待执行 | validation / readiness 报告 |
| 合并决定 | 待验收 | 依据实际结果，不继承历史 accepted 状态 |
