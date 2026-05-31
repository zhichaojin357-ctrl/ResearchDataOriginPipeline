# Method Card: HPLC/LC Exported Data

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`
- Exported chromatograms and peak tables.
- Vendor raw folders such as Agilent `.d` and Waters `.raw` are not decoded in Phase 1.

## Automatic Recognition Signals
- Folder/name keywords: `液相`, `HPLC`, `LC`, `chromatogram`, `peak table`.
- Header keywords: `retention time`, `RT`, `time`, `intensity`, `absorbance`, `area`, `height`, `mAU`.
- Table pattern: chromatogram time-signal columns or peak table with RT/area/height.

## Basic Processing Flow
1. Read only exported tabular files.
2. Detect chromatogram columns or peak-table columns.
3. Plot chromatogram when time-signal data exist.
4. Summarize RT, area, and height when peak table exists.
5. Preserve sample and detector metadata where available.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak table formatting and sorting.
- Area percentage only if already exported or formula is explicit.
- Conversion/selectivity only if complete formula, calibration, and standards are supplied.
- Basic chromatogram plotting.

## Recommended Origin Plot Type
- Line plot: detector signal versus retention time.
- Bar/table summary for peak areas when provided.

## Manual Checks Required
- Confirm peak identity and retention-time matching.
- Confirm integration boundaries.
- Confirm calibration curve and response factors.
- Confirm formula before conversion/selectivity/yield calculations.

## Forbidden Claims
- Do not automatically identify substrate or product.
- Do not automatically confirm LC-MS products.
- Do not calculate conversion or selectivity without complete formula and calibration basis.
- Do not decode proprietary raw vendor directories in Phase 1.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `detector`, `wavelength_nm`, `calibration_source`, `peak_table_source`

## Phase 1 Implementation Status
- Supported in Phase 1 for exported data only.
- Planned processor: `lc_exported_data_processor`.

## Risk Level
- High. Plotting and table extraction are allowed; identity and quantitation are manual unless fully specified.
