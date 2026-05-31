# Reuse Auditor Report

## Summary

Phase 1 should use a conservative core Python stack for exported tabular/spectral data and Origin automation:

- `pandas`, `numpy`, `scipy`, `openpyxl`, `PyYAML`
- `pybaselines` for reusable baseline correction
- `originpro`, `pywin32` for OriginPro/COM integration on Windows

Domain-specific packages should remain optional candidates only. They are useful discovery items for future adapters, vendor parsers, or advanced fitting, but they must not expand Phase 1 beyond scan, process exported data, plot in Origin, save `.opju`, export `.tif`, and write metadata/report/manual-check outputs.

## Core Recommendation

Use core dependencies for:

- Generic table loading from CSV/TXT/XLSX.
- Numeric cleanup, sorting, normalization, candidate peak detection, and simple formulas.
- Baseline correction where useful for FTIR/Raman/EPR/PL style spectra.
- YAML configuration loading.
- OriginPro automation and Windows COM smoke testing.

Core dependencies are suitable for all supported Phase 1 data types: XRD, UV-vis DRS, EIS, photocurrent, photocurrent_response, reaction condition screening, FTIR, Raman, EPR, PL, BET, Mott-Schottky, HPLC/LC exported data, and XPS.

## Optional Recommendation

Keep these categories optional:

- Electrochemistry/vendor file helpers: `impedance`, `pyimpspec`, `ixdat`, `galvani`, `eclabfiles`.
- Spectroscopy helpers: `ramanspy`, `rampy`, `spectrochempy`, EPR-specific tools.
- Surface/chromatography/MS/NMR/image packages: `pyGAPS`, `hplc-py`, `rainbow-api`, `mocca`, `pymzML`, `pyteomics`, `matchms`, `nmrglue`, `hyperspy`, `exspy`, `scikit-image`.
- XPS fitting: `lmfitxps`, adapter-only and disabled by default.

Optional packages must import lazily, fail gracefully, and write warnings instead of blocking core processing.

## License And Scope Risks

Key risks:

- `originpro` license metadata and OriginPro redistribution boundaries need verification.
- Many domain-specific optional packages need license verification before use.
- GPL-family or unclear-license projects must not be copied or vendored.
- Optional packages must not trigger forbidden scientific conclusions, such as XPS valence assignment, EPR radical assignment, LC-MS product confirmation, automatic equivalent-circuit selection, or band mechanism claims.
- SEM, TEM, NMR, and MS remain scan-only/deferred even if optional libraries are available.

## Output Files

- `docs/reuse_audit/library_reuse_matrix.md`
- `docs/reuse_audit/license_risk_notes.md`
- `requirements.txt`
- `optional_requirements.txt`
- `docs/agent_reports/reuse_auditor_report.md`

## Validation Not Run

No dependency installation, import audit, or processor tests were run. This task is a planning audit and the repo has not entered Phase 1 coding.
