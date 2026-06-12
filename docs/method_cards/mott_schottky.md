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
