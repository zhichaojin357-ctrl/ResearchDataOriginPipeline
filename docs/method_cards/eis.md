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
3. Require explicit impedance units (`ohm/Ω`, `kOhm/kΩ`, `MOhm/MΩ`, or `mOhm/mΩ`) before emitting normalized Ohm columns.
4. Convert frequency and phase only from explicit units (`Hz` families or `rad/s`; `deg` or `rad`). Unknown optional units are omitted and derived where scientifically valid.
5. Convert sign convention for Nyquist plotting only when the column meaning is explicit: preserve signed `-Im(Z)` values; negate signed raw `Im(Z)` values; resolve a bare vendor `Z''`/`Z"` header only when an explicit-unit phase column gives a clear consistency result, otherwise require manual review. Never use an absolute-value shortcut.
6. Retain parsed measured points in source order; do not automatically choose a semicircle branch or fitting interval.
7. Generate Nyquist and Bode-ready data where columns are available. If magnitude or phase is absent or has an unknown unit, derive it from the converted measured impedance components and record that provenance.
8. Mark equivalent-circuit fitting as `status=not_run`, `reason=blocked_by_policy`.
9. Plot in Origin.
10. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Nyquist coordinates: `-Im(Z)` versus `Re(Z)`.
- Bode magnitude/phase plotting.
- High-frequency intercept candidate when clearly detectable.
- No automatic equivalent-circuit fitting in the current automated pipeline.
- `draft_fit_eis_randles_cpe` remains an explicit diagnostic API for separately approved manual-review work; the formal default processor does not call it.

## Recommended Origin Plot Type
- Nyquist scatter-line plot.
- Bode line plot: `|Z|` and phase versus frequency, often log-scaled.

## Manual Checks Required
- Confirm sign convention for imaginary impedance.
- Confirm frequency, impedance, and phase units plus any log scaling.
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

## Current Automated Pipeline Implementation Status
- Supported in the current automated pipeline.
- Implemented processor: `eis_processor`.
- Formal output contains measured Nyquist/Bode-ready columns only; it does not emit fit columns, fit parameters, or fit sidecars.

## Risk Level
- Medium-high. EIS plots are allowed; circuit fitting and mechanistic interpretation are manual.
