# Phase 1.13 Package Install Plan

- `ALLOW_PIP_INSTALL`: true
- Core dependency upgrades: blocked unless user confirms
- Before freeze: `output/reports/phase1_13_pip_freeze_before.txt`

## Current Import Status

| Package | Module | Available | Version |
|---|---|---:|---|
| `pybaselines` | `pybaselines` | True | 1.2.1 |
| `scipy` | `scipy` | True | 1.17.1 |
| `impedance` | `impedance` | True | 1.7.1 |
| `Pillow` | `PIL` | True | 12.2.0 |
| `matplotlib` | `matplotlib` | True | 3.10.8 |
| `originpro` | `originpro` | True | 1.1.15 |
| `pywin32` | `win32com` | True | 311 |
| `pygaps` | `pygaps` | True | 4.6.1 |
| `lmfitxps` | `lmfitxps` | True | 4.2.0 |
| `nmrglue` | `nmrglue` | True | 0.11 |
| `tifffile` | `tifffile` | True | 2026.3.3 |
| `scikit-image` | `skimage` | True | 0.26.0 |
| `pyimpspec` | `pyimpspec` | False |  |
| `ixdat` | `ixdat` | True | 0.3.0 |
| `galvani` | `galvani` | False |  |
| `eclabfiles` | `eclabfiles` | False |  |
| `cwepr` | `cwepr` | True | 0.5.1 |
| `EPRpy` | `EPRpy` | False |  |
| `hplc-py` | `hplc` | False |  |
| `rainbow-api` | `rainbow` | True | 1.0.10 |
| `MOCCA2` | `mocca2` | True | 0.1.18 |
| `pymzML` | `pymzml` | True | 2.6.0 |
| `pyteomics` | `pyteomics` | True | 5.0 |
| `matchms` | `matchms` | False |  |

## Planned Actions

- 0 installed/project: pybaselines, scipy, impedance, Pillow, matplotlib, originpro, pywin32. use existing imports through lazy adapters; no install
- 1 install/smoke: pygaps, lmfitxps, nmrglue, tifffile, scikit-image, pyimpspec. smoke installed packages; pyimpspec dry-run then install only if no core dependency upgrade
- 2 evaluate/install if low risk: ixdat, galvani, eclabfiles, cwepr, EPRpy, hplc-py, rainbow-api, MOCCA2, pymZML, pyteomics, matchms. smoke installed packages; dry-run missing packages; GPL/reference packages not used in core automatic flow
- 3 reference only: pyOpenMS, HyperSpy, LumiSpy, GSAS-II, xrayutilities, RamanSPy, SpectroChemPy. do not install in this run unless explicitly needed; record as reference/heavy
