# Method Card: Raman

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported Raman shift-intensity spectra.
- Native/binary `.spc` files are inventory/manual-review inputs only until a format-specific reader is implemented.

## Automatic Recognition Signals
- Folder/name keywords: `拉曼`, `Raman`.
- Header keywords: `Raman shift`, `shift`, `cm-1`, `cm^-1`, `intensity`, `counts`.
- Numeric pattern: Raman shift paired with intensity values.

## Basic Processing Flow
1. Read exported Raman spectrum.
2. Detect shift and intensity columns.
3. Sort by Raman shift and drop empty rows.
4. Optionally baseline-correct or normalize when configured.
5. Plot spectra in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak-position candidates.
- Peak-intensity candidates.
- Integrated area candidates over configured bands.
- Intensity-ratio candidates only for configured bands and manual review.

## Recommended Origin Plot Type
- Line plot: intensity versus Raman shift.
- Overlay line plot for multiple samples.

## Manual Checks Required
- Confirm laser wavelength and power.
- Confirm baseline correction and fluorescence background handling.
- Confirm band assignments.
- Confirm whether intensity ratios are meaningful for the material system.

## Forbidden Claims
- Do not automatically determine defect type.
- Do not infer crystallinity, phase, or mechanism from Raman alone.
- Do not assign bands as final without manual review.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `laser_wavelength_nm`, `baseline_method`, `normalization`, `band_ranges`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `raman_processor`.

## Risk Level
- Medium-high. Feature extraction is allowed; structural interpretation requires manual review.
