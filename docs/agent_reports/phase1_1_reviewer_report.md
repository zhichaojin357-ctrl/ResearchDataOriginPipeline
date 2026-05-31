# Phase 1.1 Reviewer Report

Date: 2026-05-30

## Review Scope

Reviewed the current project state for Phase 1.1 engineering hardening:

- CLI hardening for `process`.
- Batch failure isolation and failure reports.
- Raw data and output path guards.
- Synthetic fixtures and no-Origin tests.
- Real-data intake documentation.
- Review dashboard and processing summary.
- Guardrails against PPT generation, kinetics processors, raw-data mutation, and routine Origin launches.

## Findings And Fixes

### Fixed: processing summary double-counted failed metadata datasets

The review found that `processing_summary.json` could report an inflated `total_dataset_count` when a dataset produced fail metadata and also emitted a failure record. A regression assertion was added to `tests/test_phase1_1_process_cli.py`, the failing behavior was reproduced, and `src/core/process.py` was updated so totals count failed metadata datasets once.

### Fixed: output write paths use the shared output guard more consistently

The review tightened output writes so scanner reports, unclassified manifests, processed data, metadata, report files, and review dashboard paths flow through `output_dir(...)` or `report_path(...)`, both guarded by `ensure_write_path_allowed(...)`.

### Reviewed: routine tests do not launch Origin

Routine tests use `ProcessOptions(no_origin=True)` or `process --no-origin`. The only processor behavior test that exercises the non-no-Origin branch patches `src.processors.base.export_plot`. Origin adapter tests mock/fake Origin execution paths. Real Origin execution remains isolated to `run.py origin-test`.

### Reviewed: `--no-origin` bypasses Origin export

`src/processors/base.py` sets `processing_status` to `processed_no_origin` and does not call `export_plot(...)` when `no_origin=True`. The test suite patches `export_plot` to raise if called and confirms no-Origin processing succeeds.

### Reviewed: failure records are structured

Failure records include:

- `source_file`
- `inferred_data_type`
- `processor_name`
- `failure_stage`
- `error_message`
- `manual_fix_hint`

They are written to:

- `output/reports/processing_failures.json`
- `output/reports/processing_failures.md`

### Reviewed: raw-data and scope guards remain active

`input/raw_data/` is currently empty. Scan/process/validate/origin-test write to approved project areas only. PPT-related artifacts and kinetics processor paths are checked by validation and were not found.

### Reviewed: data-type boundaries remain intact

`动力学` remains `reference_literature` and scan-only. SEM/TEM/核磁/质谱 remain deferred scan-only. Phase 1.1 does not add PPT, kinetics, SEM/TEM/NMR/MS processors, or full real-data processing.

## Residual Notes

- PowerShell `Get-Content` may display Chinese text as mojibake depending on console encoding. Python UTF-8 reads and test execution confirm the files are parseable and usable.
- The project directory is not a Git repository, so `git status` cannot provide a diff-based proof of raw-data immutability. Current disk inspection shows `input/raw_data/` is empty.

## Verdict

After the summary-counting fix and path-guard tightening, Phase 1.1 implementation is ready for final command verification.
