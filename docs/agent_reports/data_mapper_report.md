# Data Mapper Report

Date: 2026-05-30

Scope: read-only planning scan for Phase 1 classification. No files under `input/raw_data/` were modified, moved, deleted, or processed. No Origin, PPT, processor, or kinetics work was performed.

## Source Documents Read

- `AGENTS.md`
- `TASK_BOARD.md`
- `PROJECT_STATUS.md`
- `AGENT_HANDOFF.md`
- `docs/CODEX_GOAL_PHASE1.md`

All documents were read with UTF-8 encoding.

## Raw Data Scan Evidence

Scan target: `input/raw_data/`

Observed result: the directory currently contains no visible child files or folders from a shallow read-only scan using `Get-ChildItem -Force`.

Interpretation: every required folder below is included because it is required by the Phase 1 goal spec, but `physical_presence` is currently `absent`.

## Required Directory Classification

| folder_name | physical_presence | inferred_data_type | supported_in_phase_1 | selected_processor | expected_file_extensions | special_handling | reason | confidence |
|---|---|---|---|---|---|---|---|---|
| 20260109 光电流 | absent | photocurrent | true | photocurrent_processor | .csv, .txt, .xlsx, .xls, .dat | process_when_present | Phase 1 supported photocurrent time-current data folder from goal spec. | high |
| BET | absent | BET | true | bet_processor | .csv, .txt, .xlsx, .xls, .pdf, .docx | process_when_present | Phase 1 supported BET exported report/table and isotherm data folder from goal spec. | high |
| EPR | absent | EPR | true | epr_processor | .csv, .txt, .xlsx, .xls, .dat, .dta, .spc | process_when_present | Phase 1 supported magnetic field-intensity spectrum folder from goal spec. | high |
| PL | absent | PL | true | pl_processor | .csv, .txt, .xlsx, .xls, .dat | process_when_present | Phase 1 supported wavelength-intensity photoluminescence folder from goal spec. | high |
| XPS | absent | XPS | true | xps_processor | .csv, .txt, .xlsx, .xls, .dat | process_when_present_manual_check | Phase 1 supported exported XPS spectrum/fitting table folder; peak positions and areas require manual check. | high |
| XRD | absent | XRD | true | xrd_processor | .csv, .txt, .xlsx, .xls, .dat, .xy | process_when_present_manual_check | Phase 1 supported 2theta-intensity diffraction folder; phase and crystal-plane claims are forbidden. | high |
| 固体紫外 | absent | UV-vis DRS | true | uvvis_drs_processor | .csv, .txt, .xlsx, .xls, .dat | process_when_present_manual_check | Phase 1 supported diffuse reflectance/Tauc candidate folder; final Eg and mechanism need manual confirmation. | high |
| 光电流响应 | absent | photocurrent_response | true | photocurrent_processor | .csv, .txt, .xlsx, .xls, .dat | process_when_present | Phase 1 supported photocurrent response folder mapped to the shared photocurrent processor. | high |
| 光反应的条件筛选 | absent | reaction_condition_screening | true | condition_screening_processor | .csv, .txt, .xlsx, .xls | process_when_present_manual_check | Phase 1 supported condition screening folder; best-condition claims remain candidates only. | high |
| 红外 | absent | FTIR | true | ftir_processor | .csv, .txt, .xlsx, .xls, .dat, .spc | process_when_present_manual_check | Phase 1 supported wavenumber-intensity/transmittance/absorbance folder; bond assignment is forbidden. | high |
| 拉曼 | absent | Raman | true | raman_processor | .csv, .txt, .xlsx, .xls, .dat, .spc | process_when_present_manual_check | Phase 1 supported Raman shift-intensity folder; defect interpretation is forbidden. | high |
| 莫特肖特基 | absent | Mott-Schottky | true | mott_schottky_processor | .csv, .txt, .xlsx, .xls, .dat | process_when_present_manual_check | Phase 1 supported potential-capacitance or potential-1/C2 folder; band-edge claims are forbidden. | high |
| 液相 | absent | HPLC/LC exported data | true | lc_exported_data_processor | .csv, .txt, .xlsx, .xls | process_when_present_manual_check | Phase 1 supports only exported LC/HPLC data; raw vendor folders should not be hard-decoded. | high |
| 阻抗EIS | absent | EIS | true | eis_processor | .csv, .txt, .xlsx, .xls, .dat, .z, .mpt | process_when_present_manual_check | Phase 1 supported impedance folder for Nyquist/Bode plots; equivalent-circuit claims are forbidden. | high |
| SEM | absent | SEM_image_data | false | none | .tif, .tiff, .jpg, .jpeg, .png, .bmp, .dm3, .dm4 | scan_only | Deferred image data; register files only, no processing, no Origin, no particle analysis. | high |
| TEM | absent | TEM_image_data | false | none | .tif, .tiff, .jpg, .jpeg, .png, .bmp, .dm3, .dm4 | scan_only | Deferred image data; register files only, no processing, no Origin, no lattice-fringe assignment. | high |
| 核磁 | absent | NMR | false | none | .fid, .1r, .1i, .csv, .txt, .xlsx, .xls, .jdx, .dx | scan_only | Deferred NMR data; register files only, no processing and no Origin. | high |
| 质谱 | absent | MS | false | none | .mzml, .mzxml, .raw, .cdf, .csv, .txt, .xlsx, .xls | scan_only | Deferred mass spectrometry data; register files only, no LC-MS product confirmation. | high |
| 动力学 | absent | reference_literature | false | none | .pdf, .doc, .docx, .caj, .ris, .bib, .enl, .txt | scan_only | Reference literature folder only; not experimental kinetics data. Do not fit, plot, call Origin, or create a kinetics processor. | high |

## Phase 1 Guardrails Confirmed

- `动力学` is classified as `reference_literature`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`.
- `SEM`, `TEM`, `核磁`, and `质谱` are deferred scan-only folders.
- No raw data was processed.
- No manifest was generated because `input/raw_data/` is empty and this report captures the current evidence without creating extra output artifacts.

## Limitations

- Physical presence is based on the current shallow read-only scan only.
- Expected file extensions are planning expectations from the goal spec and common exported formats; they are not evidence of actual files.
- Classifications should be re-run after raw data folders are populated.
