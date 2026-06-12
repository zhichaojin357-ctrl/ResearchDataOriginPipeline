# Method Card: XPS

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, exported fitting tables.
- Columns may contain raw intensity, background, envelope, or component peaks.

## Automatic Recognition Signals
- Folder/name keywords: `XPS`, `survey`, `C 1s`, `O 1s`, `N 1s`, `metal 2p`.
- Header keywords: `binding energy`, `BE`, `counts`, `intensity`, `background`, `envelope`, `component`, `fit`.
- Numeric pattern: binding energy axis paired with intensity or fitted components.

## Basic Processing Flow
1. Read exported XPS spectra or fitting table.
2. Identify binding-energy and intensity-like columns.
3. Preserve raw, background, envelope, and component columns when present.
4. Display binding energy in descending XPS convention when configured.
5. Plot raw/fitted spectra in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak-position candidates.
- Area candidates from already exported component columns.
- Basic curve plotting and tabulation.
- Optional use of fitting framework only after explicit configuration; all fit outputs remain candidates.

## Recommended Origin Plot Type
- Line plot: intensity versus binding energy with reversed x-axis.
- Multi-line plot for raw, background, envelope, and component peaks.

## Manual Checks Required
- Confirm charge correction reference.
- Confirm background model and fitting constraints.
- Confirm all peak assignments and component counts.
- Confirm area normalization and sensitivity factors.

## Forbidden Claims
- Do not automatically assign valence states.
- Do not infer oxygen vacancies.
- Do not infer metal-valence ratios as final.
- Do not infer electron-transfer direction, S-scheme, Z-scheme, or mechanism.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `energy_reference`, `background_model`, `fit_source`, `x_axis_reversed`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `xps_processor`.

## Risk Level
- High. XPS plotting is allowed; interpretation and assignments require manual review.
