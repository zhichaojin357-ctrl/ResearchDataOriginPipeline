# Phase 1.13 Adapter A/B Comparison

| Area | Fallback | Adapter | Decision |
|---|---|---|---|
| spectral_peak_detection | local neighbor peak candidates | scipy.signal.find_peaks | adapter_default_safe_candidate_detection |
| spectral_baseline | no baseline or direct pybaselines call in calculations | pybaselines ASLS adapter | adapter_default_safe_candidate_baseline |
| EIS | manual numeric magnitude/sign handling | impedance adapter numeric validation | adapter_optional_validation_no_circuit_fit |
| BET | exported summary/isotherm points | pyGAPS adapter candidate summary | optional_adapter_manual_check_required |
| XPS | existing component curve parsing | lmfitxps availability + existing curve summary | optional_adapter_no_auto_fit_or_valence |
| EPR | JEOL decoder + extrema | cwepr/EPRpy availability + candidate metrics | optional_adapter_no_radical_assignment |
| image_metadata | minimal scan-only | Pillow/tifffile/scikit-image metadata | adapter_safe_for_metadata_only |
| NMR | scan-only | nmrglue/peaklist probe | adapter_scan_only_no_structure |
| MS | scan-only | pymzML/pyteomics standard format probe | adapter_scan_only_no_product_assignment |
| electrochem_import | table reader | ixdat plus reference-only galvani/eclabfiles | adapter_probe_only |
| HPLC_LC | exported table reader | rainbow/MOCCA2/hplc-py import probe | optional_adapter_no_product_assignment |
| pyimpspec | not present | pyimpspec import smoke | reference_only_due_GPL |
