# Type-Specific OPJU Mimic Review: Remaining Draft Products

## Scope

This review covers the remaining OPJU-backed draft command:

`run.py remaining-opju-product-drafts`

The command is separate from `opju-product-pilot`, which remains scoped to BET,
XPS in-situ, XPS non-in-situ, XRD, and EPR.

## Product Types

The remaining draft command can prepare:

- EIS
- Raman
- Mott-Schottky
- UV-vis DRS / Tauc
- PL
- photocurrent
- FTIR

It records but does not generate HPLC/LC when only PDF samples and no OPJU
exemplar are available. It records reaction-condition screening as skipped when
OPJU candidates exist but no clear exported data table is found.

## Safety Rules

- Source files are copied before use.
- Reference OPJU files are copied before Origin opens them.
- Original OPJU/OPJ files are not modified.
- F-drive source files are not modified.
- Generated OPJU/TIF/PNG/CSV/JSON/MD outputs are written only under the external
  run root.
- Scientific labels or conclusions from exemplar OPJU files are not copied.

## Type-Specific Boundaries

- EIS: plots Z' versus -Z'' only; no equivalent-circuit conclusion.
- Raman: plots Raman shift versus intensity only; no phase, defect, or bond assignment.
- Mott-Schottky: validates exemplar axis text first; mismatched XRD-style exemplars are skipped.
- UV-vis DRS / Tauc: plots readable wavelength/signal data only; no final bandgap or band-edge conclusion.
- PL: plots emission/excitation table data only; no recombination conclusion.
- photocurrent: plots time-current data only; no carrier-separation conclusion.
- FTIR: plots wavenumber/transmittance curves only; no functional-group assignment.
- reaction_condition_screening: requires a clear condition/value data table; no best-condition claim.
- HPLC/LC: PDF-only, no OPJU exemplar, no OCR, no conversion/selectivity/yield, no product identity assignment.

## Required Manual Review

Every generated product is a draft for manual calibration. The run report records
selected data, selected OPJU exemplar, generated artifact paths, manual review
needs, and forbidden scientific claims avoided for each type.
