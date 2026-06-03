# XPS Output Routing Integration Review

Date: 2026-06-03

## Scope

Reviewed XPS output-routing state after the future output routing core work.

Relevant files:

- `src/core/runtime_paths.py`
- `src/core/process.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `src/cli.py`
- XPS tests

## Current State

Run-scoped output helpers exist for future runs, but the XPS dedicated workflows are not yet cleanly connected to that layer.

Clean in this XPS scope:

- `src/core/runtime_paths.py`
- `src/core/process.py`

Dirty:

- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `src/cli.py`
- `tests/test_xps_heterojunction_stacked.py`

The dirty XPS workflows still operate through explicit `output_dir` arguments. That can remain a compatibility layer, but a future integration should map those output directories from a run-scoped layout instead of hard-coded legacy locations.

## CLI Routing Flag

No `--run-output`, `output_run`, or `run_scoped` hunk is present in `src/cli.py`.

The previous output routing summary records that user-facing CLI surfacing was deferred because `src/cli.py` was already dirty. This XPS goal did not add that CLI flag.

## Heterojunction Routing

The current heterojunction dirty diff changes artifact subdirectories and removes official preview PNG output, but it does not use `src/core/runtime_paths.py` run-root helpers. It should not be treated as complete run-scoped integration.

## In-Situ Routing

The current in-situ dirty diff introduces subdirectories such as `figures_tif`, `figures_png`, `figures_pdf`, `origin_projects`, `reports`, and `tables` under the provided output directory. It does not yet prove integration with `output/runs/<run_id>_<scope>/`.

## Recommendation

Do not commit XPS output-routing source changes in this GOAL.

Future safe batch:

- create a dedicated `XPS Output Routing Micro-Batch`;
- add non-generating tests that validate path construction only;
- keep image/Excel/Origin artifact generation out of tests;
- map XPS `output_dir` from a run-scoped layout while preserving compatibility with explicit legacy output directories.
