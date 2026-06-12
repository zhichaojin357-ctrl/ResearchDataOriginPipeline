# Method Card: EIS

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported impedance tables with frequency and complex impedance columns.

## Automatic Recognition Signals
- Folder/name keywords: `阻抗EIS`, `EIS`, `impedance`, `Nyquist`, `Bode`.
- Header keywords: `frequency`, `freq`, `Hz`, `Re(Z)`, `Zre`, `Im(Z)`, `Zim`, `-Im(Z)`, `|Z|`, `phase`.
- Numeric pattern: frequency sweep plus real/imaginary impedance values.

## Basic Processing Flow
1. Read exported impedance table.
2. Detect frequency, real impedance, imaginary impedance, magnitude, and phase columns.
3. Convert sign convention for Nyquist plot only when column meaning is explicit.
4. Generate Nyquist and Bode data where columns are available.
5. Plot in Origin.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Nyquist coordinates: `-Im(Z)` versus `Re(Z)`.
- Bode magnitude/phase plotting.
- High-frequency intercept candidate when clearly detectable.
- No automatic equivalent-circuit fitting in the current automated pipeline.

## Recommended Origin Plot Type
- Nyquist scatter-line plot.
- Bode line plot: `|Z|` and phase versus frequency, often log-scaled.

## Manual Checks Required
- Confirm sign convention for imaginary impedance.
- Confirm frequency units and log scaling.
- Confirm electrode area and electrolyte conditions.
- Confirm equivalent circuit, fitting quality, and Rct interpretation manually.

## Forbidden Claims
- Do not automatically choose an equivalent circuit.
- Do not use Rct as final mechanism proof.
- Do not infer charge-transfer pathway or heterojunction type.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `frequency_unit`, `impedance_unit`, `imaginary_sign_convention`, `plot_panels`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `eis_processor`.

## Risk Level
- Medium-high. EIS plots are allowed; circuit fitting and mechanistic interpretation are manual.
