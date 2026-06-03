# BET OPJU Exemplar Optimization

Updated: 2026-06-03

## Answer

BET was only partially optimized before this pass. The project had learned the broad rule that BET isotherms should use line+symbol plots with visible numeric axes, and a prior OPJU regression report marked the BET exemplar row as `PASS`. However, older reports still documented BET as not formally standardized, and the existing plotting path could still accept BET summary-only tables as ordinary XY curves. That failure mode can produce the wrong single-point plot with labels such as `bet_surface_area_m2_g_candidate`.

This pass tightened the BET rule according to the OPJU exemplars under:

`F:\课题\LL\检测\BET`

## OPJU Evidence Used

- `F:\课题\LL\检测\BET\XWM-LL-260428-1-BOBC-All Pore\BOBC.opju`
- `F:\课题\LL\检测\BET\氮气吸附脱附等温曲线\BET -BOBC为负数.opju`
- Existing copied/exported reference pages under:
  - `output\opju_exemplar_regression\reference_exports\opju_exemplar_05_BET\`

## Learned BET Rules

- The valid BET production graph is the adsorption/desorption isotherm:
  - X: `Relative Pressure (P/Po)` or equivalent relative pressure column.
  - Y: `Quantity Adsorbed (cm3/g STP)` or equivalent adsorbed/desorbed volume column.
  - Plot primitive: line+symbol.
  - Y axis line, Y tick marks, and Y numeric tick values: visible.
  - X numeric tick values: visible.
  - Legend: explicit branch/sample rows, no frame, no fill.
- Pore-size distribution is allowed only when exported pore-size/pore-volume curve columns exist.
- Reported BET surface area, pore volume, and average pore diameter are metadata/summary values, not XY plot curves.
- OPJU pages whose X axis is row number are treated as intermediate/error pages, not style targets.

## Changes Made

- `src/origin/adapter.py`
  - Added a BET-specific plot-column selector.
  - BET Origin plotting now requires a relative-pressure isotherm X column plus adsorption/desorption branch Y columns.
  - BET Origin plotting also accepts exported pore-size distribution curve columns when `pore_size/pore_volume` style columns exist.
  - Summary-only BET metric tables are rejected before Origin job generation.
- `src/processors/calculations.py`
  - Added a pore-size distribution curve extraction path for multi-row BET pore-size/pore-volume tables.
  - Single-row BET surface-area / pore-volume / average-diameter summary tables remain metadata-only and are not converted into plot curves.
- `tests/test_origin_adapter.py`
  - Added coverage for valid BET isotherm plotting.
  - Added coverage for valid BET pore-size distribution plotting.
  - Added coverage that summary-only BET metrics are not plotted as single-point curves.
- `tests/test_processor_behaviors.py`
  - Added coverage that BET pore-size distribution tables produce curve CSV columns.
  - Retained coverage that summary-only BET metric tables produce metadata fields only.
- `D:\CodexData\.codex\skills\origin-plotting\SKILL.md`
  - Added explicit BET exemplar rules and negative-example rules.
- `docs/method_cards/bet.md`
  - Clarified OPJU-derived BET plotting method and forbidden summary-to-curve behavior.

## Verification

Targeted tests run:

```powershell
D:\Python\python.exe -m pytest tests/test_origin_adapter.py::OriginSmokeTestUnavailableDependencies::test_bet_isotherm_uses_relative_pressure_and_branch_columns tests/test_origin_adapter.py::OriginSmokeTestUnavailableDependencies::test_bet_summary_metrics_are_not_plotted_as_single_point_curves
```

Result: `2 passed`.

Expanded no-Origin/no-COM regression:

```powershell
D:\Python\python.exe -m pytest tests/test_origin_adapter.py tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_table_extracts_surface_area_pore_volume_and_diameter_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_metric_value_unit_summary_table_extracts_reported_values_without_fitting tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point
```

Result: `33 passed`.

2026-06-03 additional targeted regression after the pore-distribution fix:

```powershell
D:\Python\python.exe -m pytest tests/test_origin_adapter.py::OriginSmokeTestUnavailableDependencies::test_bet_isotherm_uses_relative_pressure_and_branch_columns tests/test_origin_adapter.py::OriginSmokeTestUnavailableDependencies::test_bet_pore_distribution_uses_pore_size_and_volume_curve_columns tests/test_origin_adapter.py::OriginSmokeTestUnavailableDependencies::test_bet_summary_metrics_are_not_plotted_as_single_point_curves
```

Result: `3 passed`.

```powershell
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_pore_distribution_table_extracts_curve_not_summary_point tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_table_extracts_surface_area_pore_volume_and_diameter_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_metric_value_unit_summary_table_extracts_reported_values_without_fitting
```

Result: `4 passed`.

No F-drive source data were modified.
No workspace raw-data tree was modified.
No real Origin export was run in this pass.
