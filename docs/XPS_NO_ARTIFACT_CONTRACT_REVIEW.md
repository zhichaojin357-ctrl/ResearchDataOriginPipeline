# XPS No-Artifact Contract Review

Date: 2026-06-03

## Scope

This review covers only the safe, no-artifact part of the current XPS workflow dirty diff.

Allowed paths for this section:

- `src/cli.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `src/core/runtime_paths.py`
- `src/core/process.py`
- `src/core/metadata.py`
- `src/origin/adapter.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- XPS-focused tests and review docs

## Current Dirty Files

Current XPS-related dirty files found in the start audit:

- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`

`src/cli.py`, `src/core/runtime_paths.py`, `src/core/process.py`, `src/core/metadata.py`, `src/origin/adapter.py`, `scripts/data_types/xps/`, `tests/test_xps_in_situ.py`, and `tests/test_output_routing.py` did not show active dirty hunks in this XPS scope.

## Classification

| File | Area | No-artifact content | Artifact/Origin/visual content | Recommendation |
| --- | --- | --- | --- | --- |
| `src/core/xps_heterojunction.py` | XPS stacked comparison workflow | Planning, manual-review metadata, forbidden-claim notes, path contracts | Origin scripts, OPJU/TIF/PNG paths, visual layout helpers | Do not stage as-is; split later |
| `src/core/xps_in_situ.py` | In-situ XPS workflow | Panel planning, missing-record reporting, no-Origin status | Origin project grouping, TIF/PNG/PDF/XLSX paths, quality checks for generated artifacts | Do not stage as-is; split later |
| `tests/test_xps_heterojunction_stacked.py` | XPS tests | Some parser/planning checks | Temp `.xlsx`, `.opju`, `.png`, `.tif` artifact expectations | Do not run or stage wholesale |

## Safe Batch Recommendation

The current source diffs are too mixed to stage in this goal. The safe first batch is a no-artifact contract test suite that uses stable public APIs:

- `build_comparison_plan`
- `planned_panels`
- CLI parser construction and parsing

The test suite must not:

- run Origin;
- run XPS real data processing;
- create OPJU/TIF/PNG/PDF/XLSX/ZIP artifacts;
- write real `output/` or `outputs/`;
- make XPS scientific claims.

## Blocked Content

The following remains blocked until a separate Origin/visual/review phase:

- OPJU exemplar comparison;
- TIF/PNG/PDF/XLSX generation;
- Origin COM execution;
- visual acceptance;
- real XPS workbook validation;
- any automatic XPS valence, electron-transfer, heterojunction-mechanism, or S-scheme claim.

## Suggested Batch Split

| Batch | Files | Risk | Status |
| --- | --- | --- | --- |
| XPS-A no-artifact tests | `tests/test_xps_no_artifact_contracts.py`, this review, test design | LOW | Recommended |
| XPS-B heterojunction source split | `src/core/xps_heterojunction.py`, focused tests | MEDIUM/HIGH | Block until source hunks are split |
| XPS-C in-situ source split | `src/core/xps_in_situ.py`, focused tests | MEDIUM/HIGH | Block until source hunks are split |
| XPS-D run output integration | runtime/process/origin path helpers if dirty | MEDIUM | No active safe hunk found in this goal |
| XPS-E CLI contract | `src/cli.py`, CLI tests | LOW | CLI source is clean; test-only coverage is safe |
| XPS-F artifact/visual blockers | blocker docs | LOW | Recommended |
