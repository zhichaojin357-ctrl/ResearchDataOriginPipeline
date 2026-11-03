# Method Card: Mott-Schottky

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported potential-capacitance or potential-1/C^2 electrochemical tables.

## Automatic Recognition Signals
- Folder/name keywords: `莫特肖特基`, `Mott`, `Schottky`, `Mott-Schottky`.
- Header keywords: `potential`, `voltage`, `E`, `capacitance`, `C`, `1/C2`, `1/C^2`, `frequency`, `Hz`.
- Numeric pattern: potential axis with capacitance-derived values, sometimes grouped by frequency.

## Basic Processing Flow
1. Read exported Mott-Schottky table.
2. Detect potential and capacitance or 1/C^2 columns.
3. Calculate 1/C^2 only when capacitance input is explicit.
4. Group by frequency when present.
5. Plot 1/C^2 versus potential in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- 1/C^2 conversion from explicit capacitance.
- Candidate linear-region fitting over configured or detected ranges.
- Flat-band potential candidate from x-intercept, flagged for manual review.

## Recommended Origin Plot Type
- Line/scatter plot: 1/C^2 versus potential.
- Multi-frequency overlay plot.

## Manual Checks Required
- Confirm reference electrode and potential scale.
- Confirm capacitance unit and area normalization.
- Confirm linear fitting region.
- Confirm semiconductor type and whether assumptions are valid.

## Forbidden Claims
- Do not automatically equate flat-band potential with CB/VB.
- Do not generate energy-band diagram automatically.
- Do not infer heterojunction type or mechanism.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `potential_reference`, `frequency_Hz`, `capacitance_unit`, `linear_region_candidates`, `flat_band_candidate`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `mott_schottky_processor`.

## Risk Level
- High. Flat-band candidates are allowed; band-position interpretation is manual.

## Explicit CHI660E raw-impedance batch branch

`run.py chi-electrochem --help` is the dedicated branch for a user-selected
directory containing CHI EIS and impedance-potential exports. It does not alter
the generic capacitance / precomputed inverse-square processor.

- Read the instrument header, potential in V/mV, impedance in ohm and actual
  frequency; reject unsupported columns/units or frequency disagreement.
- Cs is explicit: `Cs=-1/(2*pi*f*Zimag)` and `1/Cs²=1/(Cs*Cs)` (F and F^-2).
  A supplied historical workbook is inspected directly for its Cs formulas.
- Keep every observation and acquisition order. Nonnegative Zimag is flagged,
  with blank Cs/inverse-square; repeated potentials or reversals withhold plots.
- Copy every raw file and compare its bytes without hashing. BIN is opaque,
  including `.txt.bin` / `.csv.bin`; sibling formats count as one acquisition.
- Preserve filename repeat collisions as separate records, never fill missing
  frequencies from a different repeat. EIS duration is a filename condition.
- Initial EIS intake performs classification/checks; `--replot --with-eis`
  plots every independent measured EIS record. MT uses available 2000–5000 Hz;
  1000 Hz and other frequencies remain in complete data, without plotting.
- Plotting delegates to the established `scripts/origin/origin_plot_from_template.ps1`
  through the existing Origin adapter. The cached Graph4 page/layer geometry,
  Arial bold 36 pt titles, 28/36 pt ticks, 26 pt legend, 3 pt axes/curves and
  native linked legends are preserved.
  Current X/Y values are checked after save/reopen before native 600 dpi
  PNG/TIFF and SVG/PDF export. No fitting guides are introduced.
- XLSX exports use the existing bundled artifact-tool runtime; complete data
  include editable Cs/inverse-square formulas and traceable source line numbers.

Inputs: `--input-dir`, `--output-root`, `--package-name`, `--workbook-node`,
`--node-modules`, optional `--historical-workbook` and `--with-origin`.
`--resume` requires an incomplete matching result and validates existing raw
copies/CSV values before continuation. Completed visual acceptance is protected.
For an explicitly authorized redraw of an existing package use `--replot --force`.
`--with-eis` adds every independent EIS Nyquist record through the same helper.
This path reuses existing MT calculation data, stages native products, then
replaces final figures only after actual preview review. It does not recompute
the input datasets or create a ZIP.
Code: `src/core/chi_electrochem.py`, `src/origin/chi_mott.py`,
`scripts/data_types/electrochem/build_chi_workbooks.mjs`.
