# 优化整合：本机验收记录

本次整合来自 `codex/optimize-pipeline-preserve-plots`，比较起点为
`3ded886`，收到的分支 HEAD 为 `1cdfc0e`。提交号仅标识本次比较。
在现有 Windows、Python 和 Origin 环境执行，未安装或升级依赖。

## 本次追加修正

- 样式批量读回改用短 LabTalk 变量名。原变量在真实 Origin 中赋值成功却读回
  0，模拟测试未暴露；短名保留批量通信，并恢复颜色、线宽和填充等原始读数。
  XPS 的 21 条曲线已与旧版逐项读回完整对照一致。
  命名依据见 [Origin 官方变量文档](https://docs.originlab.com/labtalk/guide/data-types-and-vars/)。
- PowerShell 中文表头测试明确使用 UTF-8 输出和解码，避免本机代码页影响测试。
- 通用 helper 的进程检查与退出等待排除明确的零线程进程残影。实际进程和
  无法读取线程状态的进程仍被视为活跃，不使用 `AllowRunningOrigin` 绕过保护。
- validation 报告的新鲜度改用文件修改时间和大小，不再为普通源码检查逐个
  计算哈希；模板 manifest 的正式完整性检查保留。
- `AGENTS.md` 合入按影响范围测试、整批集中回归、私有冗余代码可同步迁移测试等
  规则，并登记已实现的 `process --source --only-type --no-origin` 直达入口。
  `runtime` 检查不能冒充完整发布就绪或图形验收。
- 未采纳会重复读取整张表并可能误判 PL/UV-vis 等别名的额外类型猜测补丁；
  不借优化扩展自动分类策略。明确文件入口仍需用户正确指定注册表类型。
- 未采纳通用导出的单 Origin 会话方案：实机出现重开后 PNG 缺曲线，而旧流程
  的即时 PNG 有曲线。保留旧流程的 PNG 导出时机和独立重开 TIFF 路径；整列
  数据写入、轻量进程检查、配置复用等不依赖这个方案的优化仍保留。

## 比较方法与范围

基线放在独立工作树，只有原交接中已说明的 24 份样式/数据 JSON 换行字节
恢复、对应 `.gitattributes` 及本机路径配置同步到基线。通用导出比较另在
基线三处进程查询应用相同零线程过滤，使已退出的本机残影不阻断原流程。
未复制优化后的
数据计算或绘图实现。两边原生 OTPU、OTH、参考 OPJU 和 manifest 未改动。

本机产物位于配置输出根下的 `optimization_merge_20260909/`。以下目录均相对
该目录；原始数据、用户模板和既有结果包未覆盖。
其中 `人工核对/` 只收集本次通过的原生 PNG 副本，按类型分别标注示例/优化后
或优化前/优化后；失败与探索样例不放入该文件夹。

| 核对项 | 实际结果 | 证据目录 |
|---|---|---|
| 固定 OTPU 同数据回放 | BET、EIS、EPR、FTIR、Mott-Schottky、光电流、PL、Raman、Tauc、UV-vis DRS、XRD 有卡、XPS 非原位：12 项 PNG 与独立参考解码像素零差异，均保存重开并通过原生 600 dpi TIFF 检查；已查看并排图 | `fixed_*/summary.json`、`products/<type>/side_by_side.png` |
| XPS 原位固定简单回放 | 新旧代码的全部数据、映射、逐曲线样式及 candidate PNG 完全一致；但两版都未复刻参考渐变，不能标成独立模板验收通过 | `before_fixed_XPS_in_situ/`、`fixed_XPS_in_situ_readback_fix/` |
| EPR OTH+JSON 正式入口 | 相同两份真实输入，旧新版均 accepted；processed CSV 字节一致、PNG 像素一致，已看图 | `before/runs/EPR_oth_json_template_format_products/`、对应 `after/` |
| XPS 原位 OTH+JSON 正式入口 | 相同真实输入，旧新版均 accepted；processed CSV 字节一致、PNG 像素一致，已看图，蓝/粉渐变正常 | `before/runs/XPS_in_situ_oth_json_template_format_products/`、对应 `after/` |
| 单文件数据直达 | 一份真实 EIS `b3.txt` 经 `process --source --only-type EIS --no-origin` 生成 processed CSV、metadata 和报告，未启动 Origin | `direct_EIS/` |
| 通用导出保留旧生命周期 | 撤回单会话方案后，同一 `b3_processed.csv` 的输入 CSV 字节、PNG 和 TIFF 尺寸/解码像素均与旧版完全一致，已看 PNG；仅证明没有引入变化，旧 TIFF 缺曲线仍记录在下节 | `before_generic_b3/`、`after_generic_b3_preserved/` |

固定回放最初发现的零值读回已经单独修复并实机验证；此前的像素对照是真实导出
结果，但不把当时的零值属性快照当成正确样式证据。修复后复核 XPS 两类，未把
不相关的整批图再次重复生成。固定回放使用参考样例，因此保留参考标签属于本次
同数据验证；不能把它们当作新样品产品。

## 没有扩大处理的既有限制

- XPS 原位简单 `origin-style-asset-replay` 没有正式 executor 的完整填充处理，
  新旧都出现相同灰色结果；正式 OTH+JSON 产品正常。未修改填充或放宽验收。
- 所选 XPS 原位 pairing 在显式固定模式被判定为非 Bi 输入区间并拒绝；这是
  旧版已有行为，不强行把不匹配输入塞进固定合同。
- XRD 无卡的登记 validation plan 不是通用 replay 的 `items` 输入格式，未
  临时转换计划来冒充正式产品测试，也未声称这条专用路线本次完成实际验收。
- XPS 非原位的 asset-only 预检即使显式选择 OTH+JSON，也会验证固定模板的
  旧证据；旧证据内 binding 摘要已过期，两版都在启动前拒绝。未修改证据或
  放宽校验；本次这类图只完成独立固定同数据回放，不宣称正式自适应验收。
- 通用 EIS 样例的旧版最终 TIFF 已缺曲线，新单会话方案导出的最终 TIFF 与之
  完全一致，PNG 却因此从即时曲线图变成了缺图。原生刷新未解决，未继续堆叠
  workaround；本次撤回该项预览时序改动，不把原有 TIFF 问题标为修复或通过。
  最初将模板专用多列 CSV 输入通用 adapter 的探索样例不作为验收证据；最终
  对照使用正式 `process --no-origin` 输出的 `b3_processed.csv`。

本次判断是优化前后的行为非回归，不是重新宣称项目所有模板、输入形状或历史
结果均已完整验收。未穷举所有曲线数，也不据局部通信次数估算整管线提速比例。

## 自动检查

- Windows 整批 `python -m pytest -q`：1269 passed、3 skipped、59 subtests
  passed，153.04 秒。此后撤回单会话导出，按影响范围仅复测对应模块。
- 最后定向 `tests/test_origin_adapter.py tests/test_origin_helper_script.py
  tests/test_origin_batch_manifest_runner.py`：81 passed、1 skipped、17 subtests
  passed。删除单会话专属测试，保留并恢复独立重开调用及 TIFF 失败传播检查。
- 最终 `validate --scope runtime`：28 checks、0 failures、4 skipped。
- 随后 `readiness --scope runtime --no-desktop-review-xlsx`：6 checks、
  0 failures、0 warnings、3 skipped，`ready=true`、`scope_ready=true`、
  `release_ready=false`。这是限定的软件检查，不是完整发布或所有图形通过。
- 原生 OTPU、OTH、参考 OPJU 和 manifest 相对本次比较起点没有改动。

## 整合结论

采用通过本机核对的优化与 AGENTS 规则，修复读回回归；不采用改变 PNG 行为的
单会话提速项，不顺带改样式去处理既有问题。按此范围整合到主分支，而不是把
本次结果称为所有产品均无条件发布就绪。
