# Method Card: XRD

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`, `.xy`
- Exported two-column diffraction data.

## Automatic Recognition Signals
- Folder/name keywords: `XRD`, `x-ray diffraction`, `2theta`, `2θ`.
- Header keywords: `2theta`, `2θ`, `angle`, `intensity`, `counts`.
- Numeric pattern: angle range commonly between 0 and 90 degrees with intensity values.

## Basic Processing Flow
1. Read diffraction table.
2. Detect 2theta/intensity columns.
3. Sort by 2theta and remove empty rows.
4. Optionally normalize intensity when configured.
5. Plot single or stacked patterns in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak-position candidates using `scipy.signal.find_peaks`.
- Relative intensity normalization.
- Basic smoothing only if explicitly configured and reported.

## Recommended Origin Plot Type
- Line plot: intensity versus 2theta.
- Stacked line plot for multiple samples.

## Manual Checks Required
- Confirm wavelength/source and scan range.
- Confirm background subtraction or smoothing choices.
- Confirm candidate peaks and any reference pattern comparison.
- Confirm phase and crystal-plane assignments manually.

## Forbidden Claims
- Do not automatically assign phases.
- Do not automatically label crystal planes.
- Do not claim no impurity phase automatically.
- Do not infer crystallinity mechanism.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `x_axis_unit`, `normalization`, `peak_detection_parameters`, `radiation_source`

## Phase 1 Implementation Status
- Supported in Phase 1.
- Planned processor: `xrd_processor`.

## Risk Level
- Medium-high. Peak candidates are acceptable; phase interpretation is forbidden automatically.
