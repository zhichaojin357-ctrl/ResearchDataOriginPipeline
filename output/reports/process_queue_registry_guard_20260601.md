# Process Queue Registry Guard

- Date: 2026-06-01
- Scope: `run.py process --from-queue` queue validation.
- Safety: no raw data changes, no workspace source changes, no F-drive writes, no Origin launch in validation.

## Problem

A crafted queue item with a valid source path/hash but an unknown `data_type` could previously fall back to generic processing because missing registry entries defaulted to `supported_in_phase_1=true`.

## Change

`run.py process --from-queue` now rejects queue items before processing when:

- `data_type` is absent from `config/processor_registry.yaml`.
- `data_type` is scan-only or unsupported in Phase 1.
- `selected_processor` does not match the registry entry for that `data_type`.

Failures are recorded as `queue_validation` failures and no metadata/processed output is written for those items.

## Verification Snapshot

- RED: `D:\Python\python.exe -m pytest tests/test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_process_from_queue_blocks_unknown_registry_data_type -q` returned code 0 instead of expected queue-validation failure before implementation.
- GREEN: `D:\Python\python.exe -m pytest tests/test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_process_from_queue_blocks_unknown_registry_data_type tests/test_phase1_2_mixed_triage.py -q`: 18 passed.
- `D:\Python\python.exe -m pytest`: 182 passed, 2 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0; 21 checks, 0 failures, 0 warnings.
- Residual process check after a short wait: no `python`, `EXCEL`, `Origin`, or `OriginPro` process remained.

## Files Updated

- `src/core/process.py`
- `tests/test_phase1_2_mixed_triage.py`
- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
