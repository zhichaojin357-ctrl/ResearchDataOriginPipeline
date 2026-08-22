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
5. Search the configured local Jade/PDF card database when phase identification is requested.
6. Record card identifiers, matched and unmatched peaks, alternatives, tolerances, and confidence.
7. Plot single or stacked patterns in Origin when requested.
8. Save processed CSV, `metadata.json`, and any requested Origin artifacts.

## Automatic Calculations Allowed
- Peak-position candidates using `scipy.signal.find_peaks`.
- Local Jade/PDF reference-card search and automatic phase matching with traceable card identifiers.
- Relative intensity normalization.
- Basic smoothing only if explicitly configured and reported.

## Recommended Origin Plot Type
- Line plot: intensity versus 2theta.
- Stacked line plot for multiple samples.
- Standard-card overlay: the reviewed fixed-shape `XRD.otpu` path, with current
  data and card peaks bound as native Origin worksheet plots.
- No-card overlay: exactly nine curves use the reviewed
  `XRD_no_card.otpu`; other positive curve counts use the retained adaptive
  `XRD_no_card.oth` plus explicit JSON/style replay. Both paths rebuild labels
  from current data and do not load a reference OPJU as the product base.

## Manual Checks Required
- Confirm wavelength/source and scan range.
- Confirm background subtraction or smoothing choices.
- Confirm candidate peaks, database version, card identifiers, tolerances, and competing phase matches.
- Confirm crystal-plane labels and any purity or quantitative-phase conclusion manually.

## Forbidden Claims
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

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `xrd_processor`.

## Risk Level
- Medium-high. Automatic database-backed phase matching is allowed with card provenance and confidence; purity, quantitative phase fractions, and crystal-plane claims require additional evidence.
