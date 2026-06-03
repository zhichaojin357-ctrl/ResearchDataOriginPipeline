# Future Output Routing Review

## Scope

This review covers future output routing only. It does not move, delete, rewrite, or clean any existing `output/` or `outputs/` artifacts.

## Current Output Writers

Current formal code paths that write output include:

- `src.core.project.output_dir()` and `report_path()`: central legacy helpers for `output/<area>` and `output/reports`.
- `src.processors.base.process_table_dataset()`: writes `processed_data/`, `metadata/`, and calls Origin export when explicitly enabled.
- `src.core.process.run_process()`: writes processing reports, failures, summary, and review dashboard.
- `src.core.triage.run_triage()`: writes triage reports, queue JSON/Markdown, source hash index, traceability groups, and review dashboard.
- `src.core.auto_queue.write_auto_queue_outputs()`: writes queue plan reports under `output/reports` and one docs agent report.
- `src.core.reviewed_queue.write_decision_template()` / `write_reviewed_queue_reports()`: writes reviewed queue templates and plans.
- `src.core.origin_batch.write_origin_batch_reports()`: writes manifest runner dry-run reports.
- `src.core.readiness.run_readiness()` / `src.core.validate.validate()`: write readiness/validation reports.
- `src.origin.adapter`: writes Origin project files, TIF/PNG previews, Origin jobs, and Origin error reports.
- `src.scanner.scanner.scan_raw_data()`: writes inventory/classification reports and unclassified output.

## Legacy Compatibility Paths

The following paths remain historical/legacy and must not be moved in this GOAL:

- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`
- existing `output/processed_data`, `output/metadata`, `output/origin_files`, `output/figures_tif`, `output/figures_preview`
- existing `output/reports`
- existing `output/review_dashboard`
- existing `outputs/`

Phase 1.6 is a locked canonical result package and is not the current engineering phase.

## Future Run-Scoped Target

New future runs should be routed under:

```text
output/runs/YYYYMMDD_HHMMSS_<scope>/
```

Standard subdirectories:

- `processed_data/`
- `metadata/`
- `origin_files/`
- `figures_tif/`
- `figures_preview/`
- `reports/`
- `logs/`
- `run_manifest.json`

## Command Mapping

- `process --no-origin`: should write processed tables, metadata, reports, and dashboard material into one run root.
- `process --with-origin`: should use the same run root for processed tables, metadata, Origin files, TIF, PNG, and reports, without changing Origin behavior.
- `triage`: should write triage reports and queue artifacts into run-root `reports/`.
- `auto-queue`, `reviewed-queue`, `origin-batch`: already accept explicit report paths and should be migrated to run-root report helpers in focused batches.
- `validate` / `readiness`: keep legacy compatibility by default; tests already isolate output through temporary project roots.

## Strict Batch Recommendation

1. OR-1 Runtime Path Contract
   - Files: `src/core/runtime_paths.py`, `tests/test_output_routing.py`, this review, and implementation plan.
   - Risk: LOW.

2. OR-2 Process / Metadata Output Routing
   - Files: `src/core/process.py`, `src/processors/base.py`, `src/core/metadata.py`, `src/core/project.py`, `tests/test_output_routing.py`.
   - Risk: MEDIUM because processor output paths are shared.

3. OR-3 Queue / Report Routing
   - Files: `src/core/triage.py`, focused queue/report modules, `tests/test_output_routing.py`.
   - Risk: MEDIUM.

4. OR-4 Origin Adapter Path Acceptance
   - Files: `src/origin/adapter.py`, focused Origin adapter tests.
   - Risk: MEDIUM; must not run Origin.

5. OR-5 Documentation / Policy
   - Files: routing summary and index/cleanup-plan docs.
   - Risk: LOW.

## Targeted Tests

```powershell
D:\Python\python.exe -m py_compile src/core/runtime_paths.py
D:\Python\python.exe -m pytest tests/test_output_routing.py -q
git status --short -- output outputs
```

Later batches must add their own focused py_compile and pytest commands.

## Recommendation

Proceed with OR-1 first. Do not alter legacy output artifacts. Do not run Origin or real data processing.
