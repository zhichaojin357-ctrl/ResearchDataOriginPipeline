# Batch 2D-CALC-BET Review

Date: 2026-06-03

## Purpose

Stabilize BET candidate extraction so exported BET tables are classified as candidate-only summary, isotherm, or pore-size distribution inputs without requiring real BET data or Origin.

## Dirty Files In Scope

Current BET-related dirty files:

- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`

No dirty changes were present in `src/processors/base.py`, `src/core/table_reader.py`, `src/core/process.py`, or `config/processor_registry.yaml` for this GOAL.

## Previously Covered Work

Commit `870d088` already covered photocurrent processed output units. This BET batch must not re-stage or re-commit photocurrent hunks.

## Current BET Risks

- Summary-only BET values can be counted as `isotherm_points` because prior logic used generic numeric row count for all BET tables.
- Pore-size distribution detection is too broad if plain `pore volume` is accepted as a distribution y column.
- A summary table with multiple sample rows could be mistaken for a pore-size distribution if it contains `average pore diameter` and `total pore volume`.
- Existing isotherm detection works for explicit relative-pressure / adsorbed-quantity rows, but table kind should be candidate-only metadata, not a scientific interpretation.

## Desired Candidate Rules

Summary-only tables:

- Extract summary candidate metrics.
- Do not emit `isotherm_points`.
- Do not emit `pore_distribution_points`.
- Mark table kind as `summary_only`.

Isotherm tables:

- Require relative pressure and adsorption quantity columns.
- Optional desorption is allowed.
- Mark table kind as `isotherm`.

Pore-size distribution tables:

- Require a pore size/diameter/width x column.
- Require distribution-specific volume evidence such as `dV/dlog`, `dV/dD`, `differential pore volume`, or `pore volume distribution`.
- Mark table kind as `pore_distribution`.

Ambiguous tables:

- Do not force a pore distribution or isotherm candidate.
- Keep summary/manual-review candidate behavior only.

## Risk Search Result

- `output/` matched only existing process queue guard text in `src/core/process.py`.
- `outputs/` had no matches in the reviewed allowlist.
- Existing BET references in `tests/test_origin_adapter.py` were not used for this GOAL because they test Origin job construction and this GOAL must not run Origin.
- Existing and new BET tests use temporary directories and synthetic CSV fixtures.

## Strict Allowlist

Allowed staged paths:

- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`
- `docs/BATCH2D_CALC_BET_REVIEW.md`
- `docs/BATCH2D_CALC_BET_FIX_LOG.md`

Do not stage:

- Optional adapter bridge hunks in `src/processors/calculations.py`.
- `src/adapters/`
- `src/origin/`
- `output/`
- `outputs/`
- `docs/agent_reports/`
- `output/reports/`

## Targeted Tests

```powershell
D:\Python\python.exe -m py_compile src/processors/calculations.py
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_table_extracts_surface_area_pore_volume_and_diameter_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_metric_value_unit_summary_table_extracts_reported_values_without_fitting tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_summary_like_multirow_table_does_not_become_pore_distribution tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_bet_pore_distribution_table_extracts_curve_not_summary_point -q
```

## Staging Recommendation

Proceed to fix and staging only if:

- Tests use only synthetic fixtures.
- `py_compile` passes.
- Targeted BET tests pass.
- Output status shows no new pollution.
- Cached diff excludes optional adapter bridge hunks.

Commit message:

```text
processors: stabilize bet candidate extraction
```
