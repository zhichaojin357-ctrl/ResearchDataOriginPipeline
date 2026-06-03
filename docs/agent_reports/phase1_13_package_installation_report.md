# Phase 1.13 Package Installation Report

- Third-party source copied into project: no.
- Core dependency upgrades/downgrades allowed: no.
- `matchms` blocked because dry-run would change `numpy/scipy`.

| Package | OK | Version | Policy | Core default |
|---|---:|---|---|---:|
| `pybaselines` | True | 1.2.1 | optional adapter | True |
| `scipy` | True | 1.17.1 | optional adapter | True |
| `impedance` | True | 1.7.1 | optional adapter | True |
| `Pillow` | True | 12.2.0 | optional adapter | True |
| `matplotlib` | True | 3.10.8 | optional adapter | True |
| `pygaps` | True | 4.6.1 | optional adapter | True |
| `lmfitxps` | True | 4.2.0 | optional adapter | True |
| `nmrglue` | True | 0.11 | optional adapter | True |
| `tifffile` | True | 2026.3.3 | optional adapter | True |
| `scikit-image` | True | 0.26.0 | optional adapter | True |
| `pyimpspec` | True | 5.1.3 | GPL reference-only | False |
| `ixdat` | True | 0.3.0 | optional adapter | True |
| `galvani` | True | 0.5.0 | GPL reference-only | False |
| `eclabfiles` | True | 0.4.1 | license unknown reference-only | False |
| `cwepr` | True | 0.5.1 | optional adapter | True |
| `EPRpy` | True | 0.9.0b2 | optional adapter | True |
| `hplc-py` | True | 0.2.7 | GPL reference-only | False |
| `rainbow-api` | True | 1.0.10 | LGPL optional boundary | False |
| `MOCCA2` | True | 0.1.18 | optional adapter | True |
| `pymzML` | True | 2.6.0 | optional adapter | True |
| `pyteomics` | True | 5.0 | optional adapter | True |
| `matchms` | False |  | blocked_core_dependency_change | False |
