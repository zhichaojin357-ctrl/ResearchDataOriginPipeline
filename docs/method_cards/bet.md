# Method Card: BET

## Common File Formats
- `.csv`, `.txt`, `.tsv`, `.xlsx`, `.xls`, `.dat`, exported instrument reports.
- Tables containing adsorption/desorption isotherms, pore distribution, or summary values.
- Legacy OLE `.xls` files can be read through `xlrd` when available, or a private hidden Excel COM fallback on Windows.

## Automatic Recognition Signals
- Folder/name keywords: `BET`, `surface area`, `adsorption`, `desorption`, `pore`.
- Header keywords: `relative pressure`, `P/P0`, `quantity adsorbed`, `adsorption`, `desorption`, `pore size`, `BET surface area`.
- Report text containing `m2/g`, `cm3/g`, or `nm`.

## Basic Processing Flow
1. Prefer instrument-exported tables and reports.
2. Extract adsorption/desorption isotherm columns when present.
3. Extract pore-size distribution columns when present.
4. Collect instrument-reported BET surface area, pore volume, and average pore diameter.
5. Plot isotherm and optional pore distribution in Origin only when a real curve X column is present.
6. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Formatting and unit normalization for reported values.
- Adsorption/desorption curve plotting.
- Pore distribution plotting from already exported data.
- Summary table extraction from reports.

## Recommended Origin Plot Type
- Line+symbol isotherm plot: `Quantity Adsorbed (cm3/g STP)` versus `Relative Pressure (P/Po)`.
- Adsorption and desorption branches must be plotted as branch curves, not collapsed into a single summary point.
- Pore-size distribution uses line or line+symbol with quantitative axes when exported pore-diameter/pore-volume columns exist.
- Summary-only tables containing BET surface area, pore volume, or average pore diameter are metadata/report outputs; do not send them to Origin as XY curves.

## Local OPJU Exemplar Notes
- `F:\课题\LL\检测\BET` contains local OPJU exemplars. The BET target page is the multi-branch adsorption/desorption isotherm equivalent to the exported `Graph5`: relative pressure on X, quantity adsorbed on Y, line+symbol branches, visible numeric X/Y ticks, and explicit branch/sample legend rows.
- Exemplar pages using row number as X, or pages that only visualize report metrics, are treated as intermediate/error pages and must not drive automatic plotting.

## Manual Checks Required
- Confirm BET fitting range and correlation quality in source report.
- Confirm units and STP conventions.
- Confirm whether hysteresis interpretation is appropriate.
- Confirm sample degassing conditions.
- Confirm that legacy `.xls` exports were opened from trusted local instrument output.

## Forbidden Claims
- Do not perform or claim rigorous BET fitting automatically.
- Do not assign pore structure type automatically.
- Do not infer catalytic mechanism from surface area alone.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `adsorbate`, `temperature_K`, `degassing_condition`, `surface_area_source`

## Phase 1 Implementation Status
- Supported in Phase 1.
- Planned processor: `bet_processor`.

## Risk Level
- Medium-high. Plotting and extraction are acceptable; BET model validation is manual.
