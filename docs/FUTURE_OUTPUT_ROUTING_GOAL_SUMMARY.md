# Future Output Routing Goal Summary

Date: 2026-06-03

## Scope

This section-level goal implemented run-scoped output routing for future generated artifacts. It did not move, delete, rename, or clean legacy `output/` or `outputs/` content.

## Commits

- `a114121 core: add run-scoped output path helpers`
- `4c6ab10 core: route process artifacts into run outputs`
- `49e207c core: route queue reports through run outputs`
- `c9052f1 origin: accept run-scoped artifact paths`

## Run Output Root

Future run-scoped output helpers create:

```text
output/runs/YYYYMMDD_HHMMSS_<scope>/
  processed_data/
  metadata/
  origin_files/
  figures_tif/
  figures_preview/
  reports/
  logs/
  run_manifest.json
```

The manifest records `run_id`, timestamp, command, mode, scope, project root, output root, input paths, dry-run/no-origin flags, warnings, compatibility mode, and produced artifact directories.

## Implemented Routing

- Runtime path helpers: `src/core/runtime_paths.py`
- Legacy-compatible output helpers with optional `output_root`: `src/core/project.py`
- Process/no-Origin artifacts: `src/core/process.py`, `src/scanner/scanner.py`, `src/processors/base.py`, `src/core/metadata.py`
- Triage reports and queue outputs: `src/core/triage.py`
- Auto-queue dry-run reports and candidate queue: `src/core/auto_queue.py`
- Reviewed-queue decision templates and plan reports: `src/core/reviewed_queue.py`
- Origin-batch dry-run plan reports: `src/core/origin_batch.py`
- Origin path construction and Origin-disabled error reports: `src/origin/adapter.py`

## Legacy Compatibility

The default behavior remains legacy-compatible when `output_root` is not supplied. The following remain historical/compatibility paths and were not moved:

- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`
- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`
- `output/reports`
- `output/review_dashboard`
- `outputs/xps_in_situ_20260506`

Phase 1.6 remains a locked canonical result package, not the current engineering phase.

## Verification

Commands run:

```powershell
D:\Python\python.exe -m py_compile src/core/runtime_paths.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_output_routing.py -q
D:\Python\python.exe -m py_compile src/core/project.py src/core/process.py src/core/metadata.py src/processors/base.py src/scanner/scanner.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_phase1_1_process_cli.py tests/test_output_routing.py -q
D:\Python\python.exe -m py_compile src/core/triage.py src/core/auto_queue.py src/core/reviewed_queue.py src/core/origin_batch.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_auto_queue.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_7_manifest_runner.py tests/test_phase1_2_mixed_triage.py tests/test_output_routing.py -q
D:\Python\python.exe -m py_compile src/origin/adapter.py src/processors/base.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_origin_adapter.py tests/test_output_routing.py -q
```

Results:

- Runtime/output routing focused tests passed.
- Process CLI and output routing tests passed.
- Queue/report routing targeted tests passed.
- Origin adapter path-contract tests passed.
- Tests used tmp-path projects and did not intentionally write real output.

## Explicit Non-Actions

- Origin was not run.
- Real data was not processed.
- Legacy `output/` or `outputs/` directories were not moved, deleted, renamed, or cleaned.
- No OPJU, TIF, PNG, XLSX, ZIP, or large JSON artifacts were staged or committed.
- No visual plotting fixes or data-type scientific interpretations were attempted.

## Remaining Boundaries

- `src/cli.py` currently has unrelated XPS dirty content and was not modified or staged for this goal.
- The CLI does not yet expose a new user-facing `--output-root` or `--run-output` option in this goal. Core callers can use the new option-level contracts; CLI surfacing should be a separate preflight because `src/cli.py` is already dirty.
- XPS workflow dirty files remain outside this goal.
- Legacy `output/reports` and generated artifacts remain dirty and require a separate cleanup or routing migration decision.

## Next Recommendation

Next GOAL: XPS Workflow Preflight.
