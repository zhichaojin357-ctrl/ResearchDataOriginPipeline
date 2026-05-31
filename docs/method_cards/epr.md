# Method Card: EPR

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported EPR/ESR spectra with magnetic field and intensity columns.

## Automatic Recognition Signals
- Folder/name keywords: `EPR`, `ESR`, `spin trap`.
- Header keywords: `magnetic field`, `field`, `B`, `G`, `mT`, `intensity`, `signal`.
- Metadata keywords: `microwave frequency`, `frequency`, `GHz`.

## Basic Processing Flow
1. Read exported field-intensity table.
2. Detect magnetic-field and intensity columns.
3. Sort by field and preserve original signal scale.
4. Apply optional baseline correction only when configured.
5. Plot field-intensity spectrum in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Peak-to-peak intensity candidate.
- Signal extrema candidate.
- Baseline-corrected signal candidate when configured.
- `g_candidate` only if microwave frequency and field units are explicit.

## Recommended Origin Plot Type
- Line plot: EPR intensity versus magnetic field.
- Overlay plot for multiple samples or reaction conditions.

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

## Phase 1 Implementation Status
- Supported in Phase 1.
- Planned processor: `epr_processor`.

## Risk Level
- High. Plotting is low risk, but radical assignment is forbidden automatically.
