# XPS Workflow Goal Summary

Date: 2026-06-03

## Goal

XPS Workflow + CLI Hunk Separation + No-Origin Contract Stabilization.

The goal was to split current XPS/CLI dirty hunks, commit only no-Origin-safe changes, and document the remaining Origin/visual/artifact blockers.

## Completed Commit

### `b34d2bf` - `cli: clarify xps with-origin artifact contract`

Files:

- `src/cli.py`
- `docs/XPS_CLI_HUNK_SPLIT_REVIEW.md`

Validation:

```powershell
git diff --stat -- src/cli.py docs/XPS_CLI_HUNK_SPLIT_REVIEW.md
git diff --check -- src/cli.py
D:\Python\python.exe -m py_compile src/cli.py
git diff --cached --stat
git diff --cached --name-status
git diff --cached --check
```

Result:

- `py_compile` passed.
- cached diff was limited to the CLI allowlist.
- no output files or generated artifacts were staged.

## CLI Hunk Status

`src/cli.py` hunk separation is complete for the current dirty state.

The only CLI diff was an XPS `--with-origin` help-text clarification. No `--run-output`, `output_run`, or `run_scoped` CLI hunk exists in current `src/cli.py`.

Future output routing CLI surfacing remains separate from this XPS goal.

## XPS Heterojunction Status

Not committed in this GOAL.

The current dirty heterojunction diff is mixed:

- no-Origin-adjacent artifact contract changes;
- Origin script generation changes;
- TIF/PNG/OPJU artifact policy changes;
- plot styling, gradient, axis/tick, page geometry changes;
- Cu2p color and annotation behavior changes;
- report schema and wording changes.

It passed `py_compile`, but was not accepted as stable because the available pytest coverage creates temporary XLSX/OPJU/PNG/TIF artifacts and the diff requires visual/Origin validation.

## XPS In-Situ Status

Not committed in this GOAL.

The current dirty in-situ diff is mixed:

- output subdirectory changes;
- report and manifest relocation;
- `peak_positions_summary.xlsx` relocation;
- PNG/PDF/TIF figure export changes;
- two Origin OPJU project groups;
- Origin style validation output.

It passed `py_compile`, but was not accepted as stable because the workflow writes image/Excel/Origin artifacts and needs separate validation.

## Run-Scoped Output Integration

Core future output routing exists, but dedicated XPS workflows are not yet proven integrated with run-scoped output roots.

Current status:

- `src/core/runtime_paths.py`: clean in this XPS scope.
- `src/core/process.py`: clean in this XPS scope.
- dedicated XPS workflows still use direct `output_dir` contracts.
- no output-routing CLI flag was added in this GOAL.

## Tests And Validation

Executed:

```powershell
D:\Python\python.exe -m py_compile src/cli.py
D:\Python\python.exe -m py_compile src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py tests/test_xps_in_situ.py
git diff --check -- src/cli.py src/core/xps_heterojunction.py src/core/xps_in_situ.py tests/test_xps_heterojunction_stacked.py tests/test_xps_in_situ.py
```

Not executed:

- XPS pytest nodes, because available focused tests create temporary XLSX/OPJU/PNG/TIF files or exercise artifact-writing workflows.
- Origin.
- real XPS data processing.

## Blockers

Recorded in:

- `docs/XPS_WORKFLOW_NO_ORIGIN_REVIEW.md`
- `docs/XPS_OUTPUT_ROUTING_INTEGRATION_REVIEW.md`
- `docs/XPS_OPJU_VISUAL_BLOCKERS.md`

Main blockers:

- heterojunction source/test diff mixes no-Origin, Origin, visual, and artifact-policy behavior;
- in-situ source diff mixes output layout, matplotlib export, Origin grouping, and artifact quality checks;
- no safe no-artifact pytest path currently validates these workflows;
- XPS OPJU exemplar/visual acceptance remains unproven in this GOAL.

## Safety Statement

This GOAL did not:

- run Origin;
- process real XPS data;
- generate OPJU/TIF/PNG/XLSX/ZIP artifacts;
- modify, move, delete, or clean `output/` or `outputs/`;
- submit scientific claims about XPS valence, charge transfer, heterojunction mechanism, S-scheme behavior, or carrier migration.

## Next Recommendation

Recommended next GOAL:

```text
GOAL: XPS No-Artifact Contract Test Design
```

That goal should design tests that validate XPS table/path/report contracts without creating XLSX/OPJU/TIF/PNG artifacts. After that, XPS heterojunction and in-situ diffs can be split into smaller source commits.
