# Batch 2D-CALC-BET Goal Summary

Date: 2026-06-03

## Starting State

- Start commit for this GOAL: `e3360e3`
- BET fix commit: `d5a24b1`
- Starting dirty count was approximately 293; dirty count after BET fix commit was 292.
- Staged files before docs summary staging: none.

## Completed Commit

### `d5a24b1` - `processors: stabilize bet candidate extraction`

Files:

- `docs/BATCH2D_CALC_BET_FIX_LOG.md`
- `docs/BATCH2D_CALC_BET_REVIEW.md`
- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`

## BET Candidate Rules Stabilized

- Summary-only BET tables extract reported candidate metrics without emitting `isotherm_points` or `pore_distribution_points`.
- Isotherm candidates require relative pressure and adsorption quantity columns.
- Optional desorption branch values are preserved when available.
- Pore-size distribution candidates require a pore-size/diameter/width x column and distribution-specific volume evidence.
- Ambiguous multirow summary tables with average pore diameter and total pore volume do not become pore-distribution curves.
- All outputs remain candidate metrics only; no BET physical interpretation or material-performance conclusion is made.

## Test Coverage

Covered synthetic cases:

- Wide summary-only table.
- Metric/value/unit summary-only table.
- Ambiguous multirow sample summary table.
- Vendor adsorption/desorption isotherm table.
- Pore-size distribution table.

Verification commands:

```powershell
D:\Python\python.exe -m py_compile src/processors/calculations.py
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_table_extracts_surface_area_pore_volume_and_diameter_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_metric_value_unit_summary_table_extracts_reported_values_without_fitting tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_like_multirow_table_does_not_become_pore_distribution tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_pore_distribution_table_extracts_curve_not_summary_point -q
```

Results:

- `py_compile` passed.
- Targeted pytest result: 5 passed.
- Cached staged versions of `src/processors/calculations.py` and `tests/test_processor_behaviors.py` compiled.

## Safety Record

- Origin was not run.
- Real BET data was not processed.
- No OPJU/TIF/PNG/XLSX/ZIP/large JSON was generated or committed.
- No `output/` or `outputs/` cleanup, move, delete, or rename was performed.
- Existing dirty output/report files were not staged.

## Remaining Work

- Optional adapter bridge remains dirty in `src/processors/calculations.py`.
- XPS workflow preflight remains outside this GOAL.
- Future output routing still needs a separate planning GOAL.

## Next Suggested GOAL

GOAL: Optional Adapter Bridge Micro-Batch
