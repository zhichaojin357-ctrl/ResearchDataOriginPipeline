# XPS In-Situ Contract Review

Date: 2026-06-03

## Scope

Reviewed path:

- `src/core/xps_in_situ.py`
- `tests/test_xps_in_situ.py`
- `tests/test_xps_no_artifact_contracts.py`

## Current State

The current in-situ source diff is not safe to stage as a no-artifact batch. It mixes:

- panel planning and missing-record reporting;
- output subdirectory routing for tables/reports/figures/origin projects;
- PNG/PDF/TIF save logic;
- Origin project grouping;
- OPJU save checks;
- style validation files;
- generated-artifact quality checks.

## Safe Contract Captured

`tests/test_xps_no_artifact_contracts.py` now covers synthetic `planned_panels` behavior:

- complete reference/dark/light panels can be planned as metadata;
- incomplete fitted records stay in the missing/manual-review path;
- no OPJU/TIF/PNG/PDF/XLSX/ZIP artifact generation occurs.

The existing `tests/test_xps_in_situ.py` remains safe for this goal because it uses temporary directories and patched Origin functions.

## Not Safe To Commit In This Goal

Do not stage current `src/core/xps_in_situ.py` as-is. The diff contains real figure/export path changes and Origin project behavior.

The in-situ source needs a later split between:

- no-artifact planning/path intent;
- artifact directory layout;
- Origin project generation;
- visual/export quality checks.

## Next Safe Split

The next in-situ batch should isolate pure planning and metadata contract changes before any generated-artifact routing is committed.
