# 在另一台 Windows 电脑使用

2026-11-08，`codex/drs-origin-batch-20261103` 的全部改动已整合到默认分支 `master`，包括 CHI 电化学、GC 标定、DRS/Tauc、XRD 和图例维护改动。直接克隆默认分支即可取得完整代码；代码合并不代表这些新增改动均已完成正式产品验收。

仓库已设为公开，另一台电脑无需登录 GitHub 即可运行：

```powershell
git clone https://github.com/zhichaojin357-ctrl/ResearchDataOriginPipeline.git
cd ResearchDataOriginPipeline
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --help
```

Python 需为 3.10 或以上。安装依赖会产生网络下载；先检查新电脑已有环境和缓存，再决定是否安装。若新电脑使用 Codex，建议将项目放入独立的项目父目录，使默认的 `../输出` 也处于允许写入的工作区内。

已有本仓库时，先保存本机改动，再获取更新并切换到默认分支：

```powershell
git fetch origin
git switch master
git pull --ff-only origin master
```

## 需要在新电脑配置的内容

- 原始实验数据、项目外的 `输出`、忽略的 `workspace_data` 和 `input/raw_data` 不在 GitHub 同步范围内，按需要单独复制。
- `config/local.yaml` 和 `config/*.local.yaml` 不入库。参考 `config/default.yaml` 重新配置数据、输出和外部模板路径，或使用命令参数指定。不要直接沿用旧电脑绝对路径。
- 数据处理优先使用支持的 `--no-origin` 或专用命令的数据模式。生成 Origin 图形需要另行安装并授权 OriginPro；GitHub 不包含 OriginPro 安装包。
- `chi-electrochem` 初次导出 Excel 还需要 Node 和现有的 `@oai/artifact-tool` 运行库，通过 `--workbook-node`、`--node-modules` 指定新电脑路径。它不是 `requirements.txt` 中的 Python 依赖；可由 Codex 的 `load_workspace_dependencies` 工具定位本机已有运行库。
- Jade/PDF 卡库、OpenLab 厂商运行时和外部参考模板是否需要，取决于选用的命令。不要假定 Git 克隆会带齐这些本机资源；按对应方法卡配置。

## 本次检查范围

在原 Windows 工作站使用现有 Python 环境，对 CHI、GC、UV-vis bundle、XRD、processor profiles、Origin adapter/operations 和 template builder/executor 的 11 个相关测试文件执行定向检查：547 passed，49 subtests passed。

测试禁止启动 Origin。本次同步未验证 Origin 视觉结果，也没有把工作版本标记为已验收发布。原始数据和已有结果包没有修改。
