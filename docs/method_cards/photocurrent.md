# Method Card: Photocurrent

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported electrochemical workstation tables with time-current columns.

## Automatic Recognition Signals
- Folder/name keywords: `20260109 光电流`, `photocurrent`, `current-time`, `chronoamperometry`.
- Header keywords: `time`, `t`, `current`, `I`, `photocurrent`, `mA`, `uA`, `A`.
- Numeric pattern: monotonically increasing time column plus current response column.

## Basic Processing Flow
1. Read exported table without modifying source files.
2. Detect time and current columns; normalize units only when unit metadata is explicit.
3. Drop empty rows and sort by time.
4. Preserve sample grouping from filename, sheet name, or explicit sample column.
5. Plot current versus time in Origin and export `.opju` plus 600 dpi `.tif`.
6. Write processed CSV and `metadata.json` with manual-check fields.

## Automatic Calculations Allowed
- Peak current candidate.
- Steady current candidate over configurable end-of-cycle windows.
- On/off ratio candidate when on/off markers or stable cycles are detectable.
- Cycle boundary candidates when no marker exists.

## Recommended Origin Plot Type
- Line plot: current-time.
- Multi-sample overlay or stacked line plot when multiple samples are present.

## Manual Checks Required
- Confirm light on/off timing and cycle segmentation.
- Confirm electrode area before any current-density calculation.
- Confirm baseline drift and noisy segments.
- Confirm whether samples are directly comparable.

## Forbidden Claims
- Do not state that higher photocurrent proves better carrier separation.
- Do not infer mechanism, charge-transfer direction, or heterojunction type.
- Do not rank final performance without comparable conditions and manual confirmation.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `current_unit`, `time_unit`, `light_cycle_source`, `electrode_area_cm2`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `photocurrent_processor`.

## Risk Level
- Medium. Numeric plotting and candidate metrics are allowed, but interpretation is high risk.
