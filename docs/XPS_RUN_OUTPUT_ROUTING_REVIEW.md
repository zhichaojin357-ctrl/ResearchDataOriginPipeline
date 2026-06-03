# XPS Run Output Routing Review

Date: 2026-06-03

## Scope

Reviewed paths:

- `src/core/runtime_paths.py`
- `src/core/process.py`
- `src/core/metadata.py`
- `src/origin/adapter.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_output_routing.py`
- `tests/test_xps_no_artifact_contracts.py`

## Current State

The project has general run-scoped output helpers from the earlier future output routing section. In this XPS goal, no clean dirty hunk was found in `runtime_paths`, `process`, `metadata`, or `origin/adapter` that could be staged for XPS-specific run routing.

The active XPS source diffs still use dedicated output directory arguments and include generated artifact paths. Those changes are not safe to commit until the XPS source hunks are split.

## Safe Coverage

The new no-artifact tests use `tmp_path` and synthetic run-like paths, proving that XPS planning/parser contracts can be checked without writing real `output/` or `outputs/`.

## Not Completed

XPS workflow source code has not yet been committed to route generated artifacts through `output/runs/<run_id>/...`.

This remains blocked because the current XPS source diffs combine path routing with OPJU/TIF/PNG/PDF/XLSX generation and visual behavior.

## Next Step

After source hunk splitting, add an XPS-specific run-output batch that verifies:

- no-Origin metadata/report destinations under a temporary run root;
- future Origin artifact path construction under `origin_files`, `figures_tif`, and `figures_preview`;
- no real artifact generation in tests.
