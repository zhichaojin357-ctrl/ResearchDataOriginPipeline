# Method Card: Photocurrent Response

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported i-t response tables from electrochemical software.

## Automatic Recognition Signals
- Folder/name keywords: `光电流响应`, `photocurrent response`, `i-t`, `current response`.
- Header keywords: `time`, `current`, `response`, `I`, `mA`, `uA`, `light`.
- Numeric pattern: time column with repeated response pulses or light switching regions.

## Basic Processing Flow
1. Read exported table and preserve source file paths.
2. Identify time-current columns and optional light-state markers.
3. Clean empty rows, sort by time, and keep raw current values traceable.
4. Detect response-cycle candidates only as suggestions.
5. Plot current-time response in Origin.
6. Save `.opju`, export 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Response peak candidate per cycle.
- Baseline current candidate.
- Rise/decay interval candidates if sampling rate is sufficient.
- On/off ratio candidate with explicit or inferred cycle boundaries.

## Recommended Origin Plot Type
- Line plot with optional light-on/off markers.
- Overlay line plot for multiple samples.

## Manual Checks Required
- Confirm light switching times.
- Confirm whether current should be baseline-corrected.
- Confirm cycle boundary detection.
- Confirm comparable illumination, bias, electrolyte, and electrode area.

## Forbidden Claims
- Do not claim response proves carrier separation efficiency.
- Do not infer photocatalytic mechanism from response alone.
- Do not report final ranking without manual check.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `bias_voltage`, `electrolyte`, `light_source`, `cycle_detection_method`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `photocurrent_processor`.

## Risk Level
- Medium. Response metrics are candidates; interpretation remains manual.
