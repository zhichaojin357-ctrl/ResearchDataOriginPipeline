# Batch 2D-CALC-BET Fix Log

Date: 2026-06-03

## Files Changed

- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`
- `docs/BATCH2D_CALC_BET_REVIEW.md`
- `docs/BATCH2D_CALC_BET_FIX_LOG.md`

## Logic Changes

- Added explicit BET table-kind candidates:
  - `summary_only`
  - `isotherm`
  - `pore_distribution`
- Added `bet_isotherm_rows()` to separate explicit isotherm extraction from summary numeric fallback.
- Changed BET type-specific results so summary-only tables do not emit `isotherm_points`.
- Changed pore-distribution detection to require distribution-specific y-column evidence such as `dV/dlog`, `dV/dD`, `differential pore volume`, or `pore volume distribution`.
- Kept optional adapter bridge hunks out of this BET batch.

## Test Coverage

Synthetic targeted tests cover:

- Wide summary-only BET table.
- Metric/value/unit summary-only BET table.
- Multirow sample summary with average pore diameter and total pore volume, confirming it does not become a pore-distribution curve.
- Vendor report with adsorption/desorption branch columns.
- Pore-size distribution table with `dV/dlog(D)` evidence.

## Verification

Commands run:

```powershell
D:\Python\python.exe -m py_compile src/processors/calculations.py
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_table_extracts_surface_area_pore_volume_and_diameter_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_metric_value_unit_summary_table_extracts_reported_values_without_fitting tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_like_multirow_table_does_not_become_pore_distribution tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_pore_distribution_table_extracts_curve_not_summary_point -q
```

Results:

- `py_compile` passed.
- Targeted pytest result: 5 passed.

## Output Safety

- Origin was not run.
- Real BET data was not processed.
- No OPJU/TIF/PNG/XLSX/ZIP/large JSON was generated.
- `git status --short -- output outputs` and `git status --short -- output/reports` showed only pre-existing dirty output/report paths.

## Staging Recommendation

Recommend staging only:

- BET hunks in `src/processors/calculations.py`.
- BET hunks in `tests/test_processor_behaviors.py`.
- `docs/BATCH2D_CALC_BET_REVIEW.md`.
- `docs/BATCH2D_CALC_BET_FIX_LOG.md`.

Commit message:

```text
processors: stabilize bet candidate extraction
```
