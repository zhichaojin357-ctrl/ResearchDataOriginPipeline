# Method Card: FTIR

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported wavenumber-transmittance, wavenumber-absorbance, or wavenumber-intensity spectra.

## Automatic Recognition Signals
- Folder/name keywords: `红外`, `FTIR`, `IR`, `infrared`.
- Header keywords: `wavenumber`, `cm-1`, `cm^-1`, `transmittance`, `absorbance`, `intensity`.
- Numeric pattern: wavenumber axis commonly shown from high to low values.

## Basic Processing Flow
1. Read exported FTIR table.
2. Detect wavenumber and signal columns.
3. Sort/display x-axis high-to-low by convention when configured.
4. Optionally apply baseline correction if configured.
5. Plot spectra in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak or valley position candidates.
- Baseline-corrected spectra when configured.
- Normalized spectra when configured.
- Integrated area candidates over configured ranges.

## Recommended Origin Plot Type
- Line plot: transmittance/absorbance/intensity versus wavenumber.
- Overlay line plot for multiple samples.

## Manual Checks Required
- Confirm signal type and y-axis direction.
- Confirm baseline correction.
- Confirm peak/valley assignments and reference literature.
- Confirm sample preparation method.

## Forbidden Claims
- Do not automatically claim formation of a chemical bond.
- Do not assign functional groups as final without manual review.
- Do not infer reaction mechanism.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `signal_type`, `x_axis_reversed`, `baseline_method`, `peak_detection_parameters`

## Phase 1 Implementation Status
- Supported in Phase 1.
- Planned processor: `ftir_processor`.

## Risk Level
- Medium-high. Spectral features are candidates; assignments require manual validation.
