# Phase 1.9 Package Integration Report

- Third-party source copied into project: no.
- GPL/expert-system packages in core automatic flow: no.
- Real data processing triggered by this report: no.

| Package | Version | Import | Tier | License policy | Data types | Use |
| --- | --- | --- | --- | --- | --- | --- |
| `pybaselines` | 1.2.1 | ok | core_optional | permissive | Raman, PL, FTIR, UV-vis DRS, EPR | baseline correction candidate |
| `scipy` | 1.17.1 | ok | core | permissive | spectra, all numeric | find_peaks and numeric routines |
| `vgd-reader` | 0.1.0 | ok | optional_adapter | permissive | XPS | VGD reader probe |
| `pygaps` | 4.6.1 | ok | optional_adapter | permissive | BET | isotherm/BET candidate analysis |
| `nmrglue` | 0.11 | ok | optional_adapter | permissive | NMR | Bruker processed data reader |
| `tifffile` | 2026.3.3 | ok | core_optional | permissive | SEM, TEM | image metadata and preview |
| `pillow` | 12.2.0 | ok | core_optional | permissive | SEM, TEM, QC | image preview and DPI inspection |
| `scikit-image` | 0.26.0 | ok | optional_adapter | permissive | SEM, TEM | image metadata/QC only |
| `ixdat` | 0.3.0 | ok | optional_adapter | permissive | photocurrent, electrochemistry | electrochemical import abstraction |
| `rainbow-api` | 1.0.10 | ok | optional_adapter | LGPL_optional_boundary | HPLC/LC exported data | chromatography raw reader probe |
| `mocca2` | 0.1.18 | ok | optional_adapter | permissive | HPLC/LC exported data | baseline/peak candidate helper; no product assignment |
| `pymzml` | 2.6.0 | ok | optional_adapter | permissive | MS | mzML reader |
| `pyteomics` | 5.0 | ok | optional_adapter | permissive | MS | mzML/mzXML/MGF/msp reader helpers |
| `cwepr` | 0.5.1 | ok | optional_adapter | permissive | EPR | cw-EPR processing helper; no radical assignment |
| `lmfitxps` | 4.2.0 | ok | optional_adapter | permissive_with_review | XPS | manual-review fitting helper; no valence assignment |
| `galvani` | 0.5.0 | ok | reference_only | GPL_reference_only | electrochemistry | Bio-Logic reader reference only |
| `eclabfiles` | 0.4.1 | ok | reference_only | GPL_reference_only | electrochemistry | EC-Lab reader reference only |
| `pyopenms` |  | fail | reference_only | heavy_optional_reference | MS | full MS toolkit reference only |
| `matchms` |  | fail | reference_only | optional_reference | MS | MS similarity reference only |
| `pyimpspec` | 5.1.3 | ok | reference_only | GPL_reference_only | EIS | EIS expert analysis reference only |
