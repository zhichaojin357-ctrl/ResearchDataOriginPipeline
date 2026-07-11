# Method Card: EPR

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported EPR/ESR spectra with magnetic field and intensity columns.
- JEOL JES-FA/JES-X3 `cAcqu` raw files with no extension when the binary header is verified.

## Automatic Recognition Signals
- Folder/name keywords: `EPR`, `ESR`, `spin trap`.
- Header keywords: `magnetic field`, `field`, `B`, `G`, `mT`, `intensity`, `signal`.
- Metadata keywords: `microwave frequency`, `frequency`, `GHz`.

## Basic Processing Flow
1. Read exported field-intensity table, or decode verified JEOL `cAcqu` raw files to a field-intensity table.
2. Detect magnetic-field and intensity columns.
3. Sort by field and preserve original signal scale.
4. Apply optional baseline correction only when configured.
5. Plot field-intensity spectrum in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## JEOL cAcqu Raw Decode
- Only enable this path when the file header identifies a JEOL JES-FA/JES-X3 `cAcqu` file.
- Read CH1 from offset 9500 as little-endian float32 values.
- For 65536-point acquisitions, export 4096 points by averaging each consecutive block of 16 CH1 values.
- Use only two columns after decode: `magnetic field` and `intensity`.
- Standalone project export command writes data-only `.xlsx` workbooks with two numeric columns and no header row:
  `python run.py jeol-epr-decode --out epr_jeol_decoded <raw_epr_folder>`.
- Optional reference comparison uses `--reference-dir <known_excel_dir> --report-xlsx <compare.xlsx>`.
- Do not infer radical identity from decoded spectra.

## Automatic Calculations Allowed
- Peak-to-peak intensity candidate.
- Signal extrema candidate.
- Baseline-corrected signal candidate when configured.
- `g_candidate` only if microwave frequency and field units are explicit.

## Recommended Origin Plot Type
- Line plot: EPR intensity versus magnetic field.
- Overlay plot for multiple samples or reaction conditions.
- For EPR overlays, keep the Y-axis title and axis line, but hide Y-axis tick marks and numeric tick labels.
- Prefer direct material/condition labels at the curve tails instead of a boxed legend.

## Manual Checks Required
- Confirm field unit and microwave frequency.
- Confirm baseline correction and smoothing are scientifically acceptable.
- Confirm spin-trap identity and blank/control comparison.
- Confirm radical assignment externally.

## Forbidden Claims
- Do not automatically assign `·O2-`, `·OH`, `h+`, or `1O2`.
- Do not infer reaction mechanism from EPR peaks.
- Do not claim radical dominance without manual validation.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `field_unit`, `microwave_frequency_GHz`, `spin_trap`, `baseline_method`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `epr_processor`.

## Risk Level
- High. Plotting is low risk, but radical assignment is forbidden automatically.
