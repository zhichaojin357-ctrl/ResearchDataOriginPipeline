# GroupMeetingAutoPPT Phase 1 Codex Goal Spec

## 0. Goal summary

项目名称：
GroupMeetingAutoPPT

项目根目录：
D:\Codex Project\科研数据处理\GroupMeetingAutoPPT

Phase 1 目标：
只完成“实验数据扫描 → 数据处理 → Origin 绘图 → 保存 .opju → 导出 .tif → 生成 metadata/report/manual-check”的基础流水线。

本阶段不要做：
- PPT 生成
- PPT 模板分析
- PPT 排版
- slide_plan
- presentation.pptx
- GUI
- kinetics processor
- 图像类 SEM/TEM 处理
- NMR 处理
- MS 处理

最高优先级：
正确性 > 可追溯性 > 稳定性 > 可维护性 > 自动化程度 > 图像美观。

## 1. Done condition

Phase 1 planning checkpoint 完成条件：
1. 项目骨架存在。
2. .codex/config.toml 存在。
3. .codex/agents/*.toml 存在。
4. .agents/skills/*/SKILL.md 存在。
5. AGENTS.md、README.md、TASK_BOARD.md、PROJECT_STATUS.md、AGENT_HANDOFF.md 存在。
6. data_mapper 完成只读扫描报告。
7. method_researcher 完成 method cards。
8. reuse_auditor 完成 library reuse audit 和 license risk notes。
9. config/processor_registry.yaml 草稿存在。
10. config/claim_policy.yaml 草稿存在。
11. config/plot_style.yaml 存在。
12. config/manual_overrides.yaml 存在。
13. 所有截图中的目录都出现在支持/排除/reference 表中。
14. “动力学”被明确标记为 reference_literature。
15. 未创建 PPT 相关模块。
16. 未创建 kinetics processor。
17. 未进入核心 processor 编码。
18. 输出初始化报告和下一步建议。
19. 等待用户确认后再编码。

Phase 1 coding checkpoint 只有在用户确认后才能开始。

## 2. Absolute rules

1. 不允许覆盖、删除、移动 input/raw_data 中任何原始数据。
2. 所有输出必须写入 output/。
3. OriginPro 已安装；不要安装 OriginPro。
4. 只检测 Python/originpro/COM 是否能调用 Origin。
5. 每个成功处理的数据集必须保存 .opju。
6. 每个成功处理的数据集必须导出 .tif，不要用 JPG 作为主输出。
7. TIF 默认 600 dpi，可在 config/plot_style.yaml 修改。
8. 不写 PPT 功能。
9. 不创建 src/ppt/。
10. 不创建 templates/ppt/。
11. 不创建 ppt_layout.yaml。
12. 不创建 slide_plan.json。
13. 不生成 presentation.pptx。
14. 不自动编造科研结论。
15. 不自动归属 XPS 峰、价态、晶面、自由基、LC-MS 产物、异质结机制。
16. 高风险表征只输出图、表、候选值、人工确认项。
17. 每个 processor 必须输出 metadata.json。
18. 每个阶段完成后必须运行 validate 或相关测试，并给出建议 git commit message。
19. CLI-first，不做 GUI。
20. 不创建 kinetics processor。
21. “动力学”文件夹不是实验动力学数据，只作为 reference_literature 扫描登记。

## 3. Existing raw-data folders and required classification

所有以下目录都必须被 scanner 识别和登记。

### 3.1 Phase 1 supported data folders

1. 20260109 光电流
   - inferred_data_type: photocurrent
   - selected_processor: photocurrent_processor
   - supported_in_phase_1: true

2. BET
   - inferred_data_type: BET
   - selected_processor: bet_processor
   - supported_in_phase_1: true

3. EPR
   - inferred_data_type: EPR
   - selected_processor: epr_processor
   - supported_in_phase_1: true

4. PL
   - inferred_data_type: PL
   - selected_processor: pl_processor
   - supported_in_phase_1: true

5. XPS
   - inferred_data_type: XPS
   - selected_processor: xps_processor
   - supported_in_phase_1: true

6. XRD
   - inferred_data_type: XRD
   - selected_processor: xrd_processor
   - supported_in_phase_1: true

7. 固体紫外
   - inferred_data_type: UV-vis DRS
   - selected_processor: uvvis_drs_processor
   - supported_in_phase_1: true

8. 光电流响应
   - inferred_data_type: photocurrent_response
   - selected_processor: photocurrent_processor
   - supported_in_phase_1: true

9. 光反应的条件筛选
   - inferred_data_type: reaction_condition_screening
   - selected_processor: condition_screening_processor
   - supported_in_phase_1: true

10. 红外
    - inferred_data_type: FTIR
    - selected_processor: ftir_processor
    - supported_in_phase_1: true

11. 拉曼
    - inferred_data_type: Raman
    - selected_processor: raman_processor
    - supported_in_phase_1: true

12. 莫特肖特基
    - inferred_data_type: Mott-Schottky
    - selected_processor: mott_schottky_processor
    - supported_in_phase_1: true

13. 液相
    - inferred_data_type: HPLC/LC exported data
    - selected_processor: lc_exported_data_processor
    - supported_in_phase_1: true

14. 阻抗EIS
    - inferred_data_type: EIS
    - selected_processor: eis_processor
    - supported_in_phase_1: true

### 3.2 Deferred folders

1. SEM
   - inferred_data_type: SEM_image_data
   - supported_in_phase_1: false
   - selected_processor: none
   - special_handling: scan_only
   - deferred_reason: image_data_deferred

2. TEM
   - inferred_data_type: TEM_image_data
   - supported_in_phase_1: false
   - selected_processor: none
   - special_handling: scan_only
   - deferred_reason: image_data_deferred

3. 核磁
   - inferred_data_type: NMR
   - supported_in_phase_1: false
   - selected_processor: none
   - special_handling: scan_only
   - deferred_reason: nmr_deferred

4. 质谱
   - inferred_data_type: MS
   - supported_in_phase_1: false
   - selected_processor: none
   - special_handling: scan_only
   - deferred_reason: ms_deferred

### 3.3 Reference literature folder

1. 动力学
   - inferred_data_type: reference_literature
   - supported_in_phase_1: false
   - selected_processor: none
   - special_handling: scan_only
   - deferred_reason: 文献资料文件夹，不是实验动力学数据

Rules for 动力学:
- 不创建 kinetics processor。
- 不做曲线处理。
- 不做拟合。
- 不导入 Origin。
- 不作图。
- 如果包含 PDF、DOCX、CAJ、RIS、BibTeX、EndNote 等文件，只登记文件清单，不分析正文。

## 4. Project structure

Required structure:

GroupMeetingAutoPPT/
├─ AGENTS.md
├─ README.md
├─ requirements.txt
├─ optional_requirements.txt
├─ pyproject.toml
├─ run.py
├─ TASK_BOARD.md
├─ PROJECT_STATUS.md
├─ AGENT_HANDOFF.md
├─ .codex/
│  ├─ config.toml
│  └─ agents/
├─ .agents/
│  └─ skills/
├─ config/
│  ├─ default.yaml
│  ├─ processor_registry.yaml
│  ├─ plot_style.yaml
│  ├─ claim_policy.yaml
│  ├─ sample_registry.yaml
│  └─ manual_overrides.yaml
├─ input/
│  └─ raw_data/
├─ templates/
│  └─ origin/
├─ output/
│  ├─ origin_files/
│  ├─ figures_tif/
│  ├─ processed_data/
│  ├─ metadata/
│  ├─ reports/
│  ├─ review_dashboard/
│  └─ unclassified/
├─ docs/
│  ├─ method_cards/
│  ├─ data_format_notes/
│  ├─ reuse_audit/
│  └─ agent_reports/
├─ examples/
├─ golden_examples/
├─ src/
│  ├─ cli.py
│  ├─ scanner/
│  ├─ core/
│  ├─ processors/
│  └─ origin/
└─ tests/

Forbidden structure:
- src/ppt/
- templates/ppt/
- any kinetics processor
- any presentation output

## 5. CLI targets

### 5.1 scan

Command:
python run.py scan --input input/raw_data --config config/default.yaml

Required behavior:
- 递归扫描 input/raw_data。
- 识别文件夹和文件类型。
- 对 supported_in_phase_1 的目录分类。
- 对 SEM/TEM/核磁/质谱/动力学 标记 deferred/unsupported/reference_literature。
- 生成：
  - output/reports/inventory_manifest.json
  - output/reports/classification_report.md
- 不处理数据。
- 不调用 Origin。

### 5.2 process

Command:
python run.py process --input input/raw_data --config config/default.yaml

Required behavior:
- 运行 scan。
- 只对 supported_in_phase_1 的数据运行 processor。
- 输出 processed_data。
- 调用 Origin 绘图。
- 保存 .opju。
- 导出 .tif。
- 生成 metadata 和 processing_report。
- 不处理 SEM/TEM/核磁/质谱/动力学。
- 不生成 PPT。

### 5.3 origin-test

Command:
python run.py origin-test

Required behavior:
- 测试 Python 是否能调用 Origin。
- 创建一个最小 Origin project。
- 导入测试数据。
- 画简单曲线图。
- 保存：
  - output/origin_files/origin_smoke_test.opju
- 导出：
  - output/figures_tif/origin_smoke_test.tif
- 失败时写：
  - output/reports/origin_errors.md

### 5.4 deps-audit

Command:
python run.py deps-audit

Required behavior:
- 检查 core dependencies 是否可 import。
- 检查 optional dependencies 是否可 import。
- core dependency 缺失才 fail。
- optional dependency 缺失只 warning。
- 生成：
  - output/reports/dependency_audit.json
  - output/reports/dependency_audit.md

Core dependencies:
- pandas
- numpy
- scipy
- openpyxl
- yaml
- pybaselines
- originpro
- win32com

Optional dependencies:
- impedance
- ixdat
- galvani
- eclabfiles
- pygaps
- lmfitxps
- ramanspy
- rampy
- spectrochempy
- hplc
- rainbow
- pymzml
- pyteomics

### 5.5 validate

Command:
python run.py validate

Required behavior:
- 检查依赖。
- 检查 Origin 调用。
- 检查 output 目录。
- 检查配置文件。
- 检查 processor registry。
- 检查是否错误创建 PPT 相关模块。
- 检查是否错误创建 kinetics processor。
- 检查 TIF 导出配置。
- 检查 动力学 是否被标记为 reference_literature。
- 检查 SEM/TEM/核磁/质谱 是否被 deferred。
- 生成 validation_report.md。

## 6. Processor targets

### 6.1 XRD processor

Folder keywords:
- XRD

Input:
- CSV/TXT/XLSX/DAT/XY
- 2theta/intensity
- 2θ/intensity

Processing:
- 读取 2θ-intensity。
- 排序。
- 去空值。
- 可选归一化。
- 可选 scipy.signal.find_peaks 作为峰位候选。
- 输出 processed CSV。
- Origin 绘制单图或堆叠图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动物相归属。
- 不自动晶面标注。
- 不自动写无杂相。

### 6.2 UV-vis DRS processor

Folder keywords:
- 固体紫外
- UV
- DRS

Input:
- wavelength-reflectance
- wavelength-R%
- wavelength-absorbance

Processing:
- 读取 wavelength 和 R%/Abs。
- R% 转 R。
- 计算 Kubelka-Munk: F(R)=(1-R)^2/(2R)。
- 计算 hν=1239.7/λ。
- 生成 DRS 图。
- 生成 Tauc plot。
- 输出 Eg_candidate 和候选线性区间。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动最终确认 Eg。
- 不自动生成能带机制。

### 6.3 EIS processor

Folder keywords:
- 阻抗EIS
- EIS
- impedance

Input:
- frequency
- Re(Z)
- Im(Z)
- -Im(Z)
- |Z|
- phase

Processing:
- 画 Nyquist: -Im(Z) vs Re(Z)。
- 画 Bode: |Z| vs frequency, phase vs frequency。
- 输出 processed CSV。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。
- 不做自动等效电路拟合。

Forbidden:
- 不自动决定等效电路。
- 不自动用 Rct 下最终机理结论。

### 6.4 Photocurrent processor

Folder keywords:
- 20260109 光电流
- 光电流响应
- photocurrent

Input:
- time-current

Processing:
- 画 current-time。
- 如果有 on/off 标记则读取。
- 如果没有标记则给周期候选。
- 计算 peak current、steady current、on/off ratio 候选。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动写光电流越高一定说明载流子分离越好。

### 6.5 Optional i-t / stability processor

Enable only if detected:
- i-t
- chronoamperometry
- stability
- 稳定性

Processing:
- time-current。
- initial current。
- final current。
- retention ratio。
- current density if area provided。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动写稳定性极佳。

### 6.6 PL processor

Folder keywords:
- PL

Input:
- wavelength-intensity

Processing:
- 多样品叠加。
- 可选归一化。
- find_peaks 候选。
- 计算峰强和积分面积候选。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动写 PL 降低一定说明复合降低。

### 6.7 FTIR processor

Folder keywords:
- 红外
- FTIR
- IR

Input:
- wavenumber-intensity
- wavenumber-transmittance
- wavenumber-absorbance

Processing:
- 横坐标高到低。
- 可选 baseline correction。
- 可选 find_peaks 或 find valleys。
- 输出峰位候选。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动宣称形成某化学键。

### 6.8 Raman processor

Folder keywords:
- 拉曼
- Raman

Input:
- Raman shift-intensity

Processing:
- Raman shift-intensity。
- 可选 baseline correction。
- 可选 normalization。
- find_peaks 候选。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动判断缺陷类型。

### 6.9 EPR processor

Folder keywords:
- EPR
- ESR

Input:
- magnetic field-intensity

Processing:
- magnetic field-intensity。
- 可选 baseline correction。
- peak-to-peak intensity。
- 如果配置中有 microwave_frequency，计算 g_candidate。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动断定 ·O2− / ·OH / h+ / 1O2。

### 6.10 BET processor

Folder keywords:
- BET

Processing:
- 第一阶段优先读取已导出的 report/table。
- 画 N2 adsorption-desorption isotherm。
- 如果提供 pore size distribution，则作图。
- 如果表中已有，整理：
  - BET surface area
  - pore volume
  - average pore diameter
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动严肃 BET 拟合。
- 不自动判断孔结构。

### 6.11 Mott-Schottky processor

Folder keywords:
- 莫特肖特基
- Mott
- Schottky

Processing:
- potential-capacitance 或 potential-1/C²。
- 如果输入 C，计算 1/C²。
- 按 frequency 分组。
- 画 1/C²-potential。
- 给 flat_band_potential_candidate。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动把 flat-band potential 等同 CB/VB。
- 不自动生成能带图。

### 6.12 Reaction condition screening processor

Folder keywords:
- 光反应的条件筛选
- condition screening
- screening

Processing:
- 读取不同条件下的 conversion/selectivity/yield/rate。
- 生成柱状图或折线图。
- 按 catalyst/light source/solvent/time/oxidant 等条件分组。
- 输出最佳条件候选，但必须标注待人工确认。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动写最终最佳条件。
- 不自动忽略误差和重复实验。

### 6.13 LC / HPLC exported data processor

Folder keywords:
- 液相
- HPLC
- LC

Processing:
- 第一阶段只处理导出的 CSV/TXT/XLSX。
- 不硬解 Agilent .d。
- 不硬解 Waters .raw。
- 读取 retention time-intensity/absorbance。
- 画 chromatogram。
- 如果有 peak table，整理 RT/area/height。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Forbidden:
- 不自动判断底物/产物。
- 不自动计算转化率/选择性，除非输入完整公式和标准曲线。

### 6.14 XPS processor

Folder keywords:
- XPS

Input:
- exported CSV/TXT/XLSX
- binding energy-intensity
- BE-counts
- binding energy-raw intensity
- 如果已有拟合导出表，可读取 raw/background/envelope/component peaks。

Processing:
- 读取 binding energy-intensity。
- 横坐标按 XPS 惯例可高到低显示。
- 可选读取已导出的 background、fit envelope、component peaks。
- 只绘制 raw spectrum、background、fit envelope、component peaks。
- 可选输出 peak_position_candidate、area_candidate。
- 所有峰位和面积必须标注 manual_check_required。
- Origin 绘图。
- 保存 .opju。
- 导出 .tif。

Reusable tools:
- lmfitxps as optional fitting framework only.
- Origin XPS Area / XPS Line apps as optional/manual reference only.

Forbidden:
- 不自动归属价态。
- 不自动判断氧空位。
- 不自动判断金属价态比例。
- 不自动判断电子转移方向。
- 不自动根据 XPS 位移写 S 型异质结、Z 型异质结或反应机理。

## 7. Deferred data handling

### SEM

- Mark as deferred_image_data.
- Scan and register file list only.
- Do not process.
- Do not call Origin.
- Do not attempt particle analysis.

### TEM

- Mark as deferred_image_data.
- Scan and register file list only.
- Do not process.
- Do not call Origin.
- Do not assign lattice fringes.

### 核磁 / NMR

- Mark as deferred_nmr.
- Scan and register file list only.
- Do not process.
- Do not call Origin.

### 质谱 / MS

- Mark as deferred_ms.
- Scan and register file list only.
- Do not process.
- Do not call Origin.
- If mzML/CSV exists, report that future LC-MS/MS processor may be enabled.

### 动力学

- Mark as reference_literature.
- Scan and register file list only.
- Do not process.
- Do not fit.
- Do not plot.
- Do not call Origin.
- Do not create kinetics processor.

## 8. Unified metadata schema

Every successfully processed dataset must output metadata.json:

{
  "dataset_id": "...",
  "data_type": "...",
  "subtype": "...",
  "source_files": ["..."],
  "source_hash": "...",
  "processor_name": "...",
  "processing_status": "success/fail/deferred/reference_literature",
  "plot_type": "...",
  "origin_template_used": "...",
  "origin_file": "output/origin_files/xxx.opju",
  "figure_tif": "output/figures_tif/xxx.tif",
  "processed_data": "output/processed_data/xxx.csv",
  "manual_check_required": true,
  "manual_check_items": [],
  "forbidden_claims": [],
  "warnings": [],
  "parameters": {},
  "key_results": {},
  "confidence_level": {
    "data_reading": "high/medium/low",
    "plotting": "high/medium/low",
    "calculation": "high/medium/low",
    "interpretation": "low"
  }
}

## 9. plot_style.yaml

config/plot_style.yaml must include:

font_family: "Arial"
axis_label_size: 18
tick_label_size: 14
legend_font_size: 14
line_width: 2.0
marker_size: 6
graph_width_cm: 12
graph_height_cm: 8
axis_line_width: 1.5
export:
  format: "tif"
  dpi: 600
  compression: "lzw"

## 10. processor_registry.yaml

config/processor_registry.yaml must contain mappings for:
- folder_keywords
- filename_keywords
- extensions
- header_keywords
- column_keywords
- numeric_range_hints
- selected_processor
- supported_in_phase_1
- confidence_rules
- deferred_reason
- special_handling

It must explicitly include:

动力学:
  inferred_data_type: reference_literature
  supported_in_phase_1: false
  selected_processor: none
  special_handling: scan_only
  deferred_reason: "文献资料文件夹，不是实验动力学数据"

SEM:
  inferred_data_type: SEM_image_data
  supported_in_phase_1: false
  selected_processor: none
  special_handling: scan_only
  deferred_reason: "image_data_deferred"

TEM:
  inferred_data_type: TEM_image_data
  supported_in_phase_1: false
  selected_processor: none
  special_handling: scan_only
  deferred_reason: "image_data_deferred"

核磁:
  inferred_data_type: NMR
  supported_in_phase_1: false
  selected_processor: none
  special_handling: scan_only
  deferred_reason: "nmr_deferred"

质谱:
  inferred_data_type: MS
  supported_in_phase_1: false
  selected_processor: none
  special_handling: scan_only
  deferred_reason: "ms_deferred"

## 11. claim_policy.yaml

config/claim_policy.yaml must include:

allowed_claims:
- 可以描述图谱趋势
- 可以描述峰位候选
- 可以描述电流响应候选
- 可以描述 EIS 半圆大小变化
- 可以描述 Tauc 拟合候选
- 可以描述 LC 峰面积表中已有数据
- 可以描述 XPS 原始谱图和已导出拟合曲线
- 可以描述 BET 表中已有数值
- 可以描述 Mott-Schottky 候选线性区间

forbidden_claims:
- 不得自动证明 S 型异质结
- 不得自动证明 Z 型异质结
- 不得自动证明电子转移方向
- 不得自动归属 XPS 价态
- 不得自动归属 EPR 自由基
- 不得自动归属 HRTEM 晶面
- 不得自动确认 LC-MS 产物
- 不得自动判断反应机理
- 不得自动把光电流增强等同于载流子分离效率提高
- 不得自动把 PL 降低等同于复合降低
- 不得自动把 flat-band potential 等同于 CB/VB
- 不得自动把动力学文件夹当实验数据处理
- 不得创建 kinetics processor

## 12. Dependency reuse strategy

Do not implement mature algorithms from scratch when reliable packages exist.

Adapter-first principle:
- 自研代码负责目录识别、列名识别、单位映射、metadata、manual_check、Origin 导入导出、报告生成。
- 数据处理算法优先调用现有库。
- 对许可证不清楚或 GPL 类项目，不复制源码进项目。
- optional dependencies 不要强制安装。
- dependency discovery 不得扩大当前阶段边界。

Core dependency candidates:
- pandas
- numpy
- scipy
- openpyxl
- PyYAML
- pybaselines
- originpro
- pywin32

Optional dependency candidates:
- impedance.py
- pyimpspec
- DearEIS
- ixdat
- galvani
- eclabfiles
- pyGAPS
- lmfitxps
- RamanSPy
- RamPy
- SpectroChemPy
- hplc-py
- rainbow
- MOCCA
- EPyR Tools
- cwepr
- eprpy
- CustomXepr
- absorption_tauc_plot
- xrdfit
- pymzML
- Pyteomics
- matchms
- nmrglue
- HyperSpy
- eXSpy
- scikit-image

Required audit outputs:
- docs/reuse_audit/library_reuse_matrix.md
- docs/reuse_audit/license_risk_notes.md
- requirements.txt
- optional_requirements.txt

## 13. Multi-agent acceleration plan

Use max 5 concurrent subagents.

Planning checkpoint:
- data_mapper: scan raw_data only.
- method_researcher: write method cards.
- reuse_auditor: write dependency and license audit.
- reviewer: review after reports are produced.
- origin_worker may draft Origin integration plan but should not implement core code before confirmation.

Coding checkpoint after user confirmation:
- processor_worker implements one processor or shared module at a time.
- origin_worker implements Origin adapter and origin-test.
- reviewer reviews after each checkpoint.
- data_mapper reruns scan after registry changes.
- reuse_auditor updates optional dependencies only when new processors need them.

No subagent may open another subagent.

## 14. Required planning steps

Step 1:
Initialize project skeleton and agent/skill configuration.
Do not write core processor code.
Do not write PPT code.
Do not write kinetics processor.

Step 2:
Run data_mapper subagent.
Output:
- docs/agent_reports/data_mapper_report.md

Step 3:
Run method_researcher subagent.
Output:
- docs/method_cards/
- docs/agent_reports/method_researcher_report.md

Step 4:
Run reuse_auditor subagent.
Output:
- docs/reuse_audit/library_reuse_matrix.md
- docs/reuse_audit/license_risk_notes.md
- requirements.txt
- optional_requirements.txt
- docs/agent_reports/reuse_auditor_report.md

Step 5:
Main agent summarizes reports and generates:
- config/processor_registry.yaml
- config/claim_policy.yaml
- config/plot_style.yaml
- config/manual_overrides.yaml
- TASK_BOARD.md update
- PROJECT_STATUS.md update
- AGENT_HANDOFF.md update

Step 6:
Run reviewer subagent.
Output:
- docs/agent_reports/reviewer_report.md

Step 7:
Stop and wait for user confirmation before coding.

## 15. Coding order after user confirmation

Only after user confirms:

1. scanner
2. metadata protocol
3. deps-audit
4. origin-test
5. generic table reader
6. XRD processor
7. UV-vis DRS processor
8. EIS processor
9. photocurrent processor
10. XPS processor
11. PL / FTIR / Raman processors
12. condition screening / LC exported data processors
13. BET / EPR / Mott-Schottky processors
14. validate

## 16. Final response format for each checkpoint

At the end of each checkpoint, output:

1. 已创建/修改的文件列表
2. 各 subagent 的任务和输出路径
3. 当前项目状态
4. 第一阶段支持/排除/reference 数据目录表
5. “动力学”文件夹 reference_literature 处理记录
6. 复用工具/依赖审计摘要
7. 未解决风险点
8. 已运行的测试或未运行原因
9. 下一步建议
10. 建议 git commit message
