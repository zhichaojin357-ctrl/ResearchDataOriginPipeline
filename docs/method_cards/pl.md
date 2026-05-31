# Method Card: PL

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported photoluminescence spectra with wavelength-intensity columns.

## Automatic Recognition Signals
- Folder/name keywords: `PL`, `photoluminescence`, `fluorescence`.
- Header keywords: `wavelength`, `nm`, `intensity`, `counts`, `emission`.
- Numeric pattern: wavelength range paired with spectral intensity.

## Basic Processing Flow
1. Read exported spectra.
2. Detect wavelength and intensity columns.
3. Sort by wavelength and remove empty rows.
4. Optionally normalize if configured.
5. Plot single or multi-sample spectra in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak-position candidates.
- Peak-intensity candidates.
- Integrated area candidates over configured ranges.
- Normalized spectra when explicitly requested.

## Recommended Origin Plot Type
- Line plot: intensity versus wavelength.
- Multi-sample overlay line plot.

## Manual Checks Required
- Confirm excitation wavelength and slit/settings.
- Confirm normalization method.
- Confirm background subtraction.
- Confirm comparability of sample concentration, loading, and test conditions.

## Forbidden Claims
- Do not state that PL decrease proves lower recombination.
- Do not infer charge-transfer mechanism from PL alone.
- Do not assign emission origin automatically.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `excitation_wavelength_nm`, `normalization`, `integration_ranges`

## Phase 1 Implementation Status
- Supported in Phase 1.
- Planned processor: `pl_processor`.

## Risk Level
- Medium-high. Quantitative candidates are allowed; mechanistic interpretation is high risk.
