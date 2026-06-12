# Method Card: Reaction Condition Screening

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`
- Structured tables of catalysts, light sources, solvents, oxidants, time, conversion, selectivity, yield, or rate.

## Automatic Recognition Signals
- Folder/name keywords: `光反应的条件筛选`, `condition screening`, `screening`, `optimization`.
- Header keywords: `catalyst`, `condition`, `solvent`, `light`, `time`, `conversion`, `selectivity`, `yield`, `rate`, `oxidant`.
- Table pattern: categorical condition columns plus numeric outcome columns.

## Basic Processing Flow
1. Read structured screening table.
2. Detect condition columns and numeric result columns.
3. Preserve replicate/error columns if present.
4. Group by configured condition categories.
5. Plot bar or line summaries in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Candidate best row by selected numeric metric.
- Mean and standard deviation when replicate structure is explicit.
- Unit-preserving sorting and grouping.
- Percent formatting for conversion/selectivity/yield.

## Recommended Origin Plot Type
- Bar chart for categorical condition comparison.
- Line plot for time series or ordered parameter sweeps.
- Grouped bar chart when multiple metrics are present.

## Manual Checks Required
- Confirm formula and basis for conversion, selectivity, yield, or rate.
- Confirm replicate handling and error bars.
- Confirm whether the chosen metric defines "best".
- Confirm experimental conditions are comparable.

## Forbidden Claims
- Do not automatically declare final optimal condition.
- Do not ignore missing replicates or error information.
- Do not infer reaction mechanism from screening table.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `condition_columns`, `metric_columns`, `replicate_columns`, `best_candidate_rule`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `condition_screening_processor`.

## Risk Level
- Medium-high. Ranking candidates are allowed; final optimization claims require manual review.
