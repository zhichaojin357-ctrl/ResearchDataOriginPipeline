# Phase 1.9 Package Integration Report

- Third-party source copied into project: no.
- GPL/expert-system packages in core automatic flow: no.
- Real data processing triggered by this report: no.

| Package | Version | Import | Tier | License policy | Data types | Use |
| --- | --- | --- | --- | --- | --- | --- |
| `pybaselines` | 1.2.1 | ok | core_optional | permissive | Raman, PL, FTIR, UV-vis DRS, EPR | baseline correction candidate |
| `scipy` | 1.17.1 | ok | core | permissive | spectra, all numeric | find_peaks and numeric routines |
| `vgd-reader` | 0.1.0 | ok | optional_adapter | permissive | XPS | VGD reader probe |
| `pygaps` | 4.6.1 | ok | optional_adapter | permissive | BET | PointIsotherm candidate provenance only; no BET fit/model conclusion |
| `nmrglue` | 0.11 | ok | optional_adapter | permissive | NMR | Bruker processed data reader |
| `tifffile` | 2026.3.3 | ok | core_optional | permissive | SEM, TEM | image metadata and preview |
| `pillow` | 12.2.0 | ok | core_optional | permissive | SEM, TEM, QC | image preview and DPI inspection |
| `scikit-image` | 0.26.0 | ok | future_reference | future_candidate_unused | SEM, TEM | future image-QC candidate only; current adapter uses Pillow/tifffile |
| `ixdat` | 0.3.0 | ok | optional_adapter | permissive | photocurrent, electrochemistry | electrochemical import abstraction |
| `impedance` | 1.7.1 | ok | optional_adapter | MIT | EIS | CustomCircuit draft fit candidate; no circuit conclusion |
| `rainbow-api` | 1.0.10 | ok | optional_adapter | LGPL_optional_boundary | HPLC/LC exported data | chromatography raw reader probe |
| `mocca2` | 0.1.18 | ok | optional_adapter | permissive | HPLC/LC exported data | baseline/peak candidate helper; no product assignment |
| `pymzml` | 2.6.0 | ok | optional_adapter | permissive | MS | mzML reader |
| `pyteomics` | 5.0 | ok | optional_adapter | permissive | MS | mzML/mzXML/MGF/msp reader helpers |
| `cwepr` | 0.5.1 | ok | optional_adapter | BSD | EPR | cw-EPR candidate metrics; no radical assignment |
| `eprpy` | 0.9.0b2 | ok | optional_adapter | MIT | EPR | EPR candidate metrics fallback; no radical assignment |
| `lmfitxps` | 4.2.0 | ok | optional_adapter | MIT_with_internal_license_review | XPS | existing fitted-curve summary only; no automatic fitting or valence assignment |
| `galvani` | 0.5.0 | ok | reference_only | GPL_reference_only | electrochemistry | Bio-Logic reader reference only |
| `eclabfiles` | 0.4.1 | ok | reference_only | GPL_reference_only | electrochemistry | EC-Lab reader reference only |
| `hplc-py` |  | fail | reference_only | reference_only_gpl | HPLC/LC exported data | raw HPLC reader reference only; exported-table flow does not require it |
| `pyopenms` |  | fail | reference_only | heavy_optional_reference | MS | full MS toolkit reference only |
| `matchms` |  | fail | blocked | blocked_core_dependency_change | MS | blocked in Phase 1 because dry-run would change core numpy/scipy versions |
| `pyimpspec` | 5.1.3 | ok | reference_only | GPL_reference_only | EIS | EIS expert analysis reference only |
