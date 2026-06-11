# Phase 1.13 Current Algorithm Source Audit

| Data type | Current source | External candidate | Phase 1.13 decision |
|---|---|---|---|
| XRD | src.processors.calculations.local_peak_positions plus scipy.signal.find_peaks when available | scipy.signal.find_peaks | keep scipy-backed candidate peaks; no phase or plane assignment |
| UV-vis DRS | src.processors.calculations.uvvis_results / uvvis_processed_table | pybaselines baseline candidate plus current Kubelka-Munk/Tauc candidate math | adapter can provide baseline provenance; no final band gap |
| EIS | src.processors.calculations.eis_results and Origin column selection | impedance.py optional adapter; pyimpspec reference-only GPL boundary | adapter validation/Nyquist/Bode only; pyimpspec import smoke/reference, not default processing |
| photocurrent | src.processors.calculations.photocurrent_results/table reader | ixdat installed; scipy numeric helpers | adapter import/provenance only; no carrier-separation conclusion |
| photocurrent_response | same photocurrent processor | ixdat installed | same as photocurrent |
| XPS | src.processors.calculations.xps_export_results/xps_processed_table plus xps_in_situ/xps_heterojunction | lmfitxps and vgd-reader optional adapters | adapter only for existing curves/manual fit helpers; no valence or electron-transfer claims |
| PL | spectral_package_baseline_records already uses pybaselines ASLS if available; local/scipy peak candidates | pybaselines + scipy | centralize as baseline/peak adapters; no recombination claim |
| FTIR | same spectral logic plus valley candidates | pybaselines + scipy | centralize adapter provenance; no bond assignment |
| Raman | same spectral logic | pybaselines + scipy; RamanSPy remains reference/heavy | centralize adapters; no defect assignment |
| BET | BET exported summary/isotherm table only | pyGAPS installed | add pyGAPS adapter for candidate isotherm/BET provenance; manual_check_required |
| EPR | JEOL decoder plus EPR extrema/g candidate | cwepr and EPRpy optional adapters | adapter wrapper/provenance; no radical assignment |
| Mott-Schottky | candidate OLS linear regions / 1/C^2 conversion | scipy/numpy only; no external scientific conclusion package | keep current, improve provenance only; no CB/VB |
| reaction_condition_screening | table summary in calculations.py | none needed | keep fallback |
| HPLC/LC exported data | exported chromatogram/peak table parser only | rainbow-api and MOCCA2 optional adapters; hplc-py reference-only | adapter import/probe only; no product assignment |
| SEM/TEM image metadata | scan-only/deferred; xps_in_situ QC uses Pillow | Pillow/tifffile current adapter; scikit-image future reference | metadata/thumbnail adapter only; no morphology/crystal claims |
| NMR scan/read | scan-only registry | nmrglue installed | read/peaklist index adapter only; no structure |
| MS scan/read | scan-only registry | pymzML + pyteomics optional probes; matchms blocked for current dependency set | standard-format reader/probe only; no product assignment |
