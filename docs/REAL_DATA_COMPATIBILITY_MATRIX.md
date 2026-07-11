# Real Data Compatibility Matrix

This matrix records the current supported behavior of the maintained pipeline. Fresh counts must be regenerated with the formal `triage`, `readiness`, and `validate` commands before making a release decision.

| data_type | automated processing | Origin product | required manual checks |
|---|---|---|---|
| XRD | reviewed/manual only for real files | supported through template-backed products and the XRD overlay command | no automatic phase, crystal-plane, or reference-card assignment |
| XPS | reviewed/manual only for raw spectra and fitted exports | supported for in-situ and non-in-situ template-backed products | no automatic valence, electron-transfer, or heterojunction-mechanism conclusion |
| EPR | supported for verified field-intensity tables; JEOL raw decode is available through the maintained decoder | supported through template-backed products | no automatic radical/species assignment |
| BET | supported for adsorption/desorption and pore-distribution tables | supported through template-backed products | confirm branch, units, area basis, and pore-size transform |
| EIS | supported for Nyquist/Bode style tables | supported through template-backed products | no automatic equivalent-circuit conclusion without user-reviewed fit range/model |
| photocurrent | supported for time-current exports | supported through template-backed products | confirm illumination intervals and units; no automatic carrier-separation conclusion |
| photocurrent_response | supported for time-current response exports; shares the photocurrent processor and style | supported through the photocurrent Origin path | confirm response-cycle boundaries and units; no automatic carrier-separation conclusion |
| Mott-Schottky | supported for potential-capacitance exports | supported through template-backed products | confirm fit range and axis transform; no automatic band-edge conclusion |
| UV-vis DRS / Tauc | supported for reflectance/absorbance/Tauc-style tables | supported through template-backed products | confirm transform mode and wavelength range |
| PL | supported for emission/intensity tables | supported through template-backed products | no automatic recombination conclusion |
| FTIR | supported for wavenumber/intensity tables | supported through template-backed products | no automatic functional-group assignment |
| Raman | supported for shift/intensity tables | supported through template-backed products | no automatic phase/defect assignment |
| HPLC/LC exported data | supported for exported chromatograms, peak tables, and calibration products | supported for calibration products through the Origin script/module path | confirm standards, units, and regression choice |
| reaction_condition_screening | supported when a clear categorical-condition/numeric-response table exists | supported through the generic Origin processor path | confirm condition semantics manually |
| SEM/TEM/NMR/MS | scan-only unless a maintained processor is added | no automatic Origin product | keep as metadata/manual-review records |
| reference_literature | scan-only | no automatic Origin product | never process as experimental kinetic data |

## Regeneration Commands

- `python run.py triage`
- `python run.py readiness --no-desktop-review-xlsx`
- `python run.py validate`

Generated reports belong under the configured external output root, usually `../输出/reports` or `../输出/runs/<timestamp>_*`.
