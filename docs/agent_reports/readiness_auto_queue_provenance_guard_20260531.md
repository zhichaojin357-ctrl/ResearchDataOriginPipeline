# Readiness Auto-Queue Provenance Guard

Generated: 2026-05-31

## Problem

`run.py readiness` already checked that the Phase 1.8 auto-queue plan and queue agreed, stayed no-Origin, and required manual checks. It did not verify that each queue item still carried the expected dry-run provenance and explicit no-processing note.

That could allow a manually edited queue to pass readiness while no longer clearly representing a Phase 1.8 dry-run candidate list.

## Change

`run.py readiness` now verifies every item in `output/reports/phase1_8_new_auto_process_queue.json` has:

- `promoted_by_phase = phase1_8_auto_queue_dry_run`
- a `queue_note` containing `no processing has been run by auto-queue`

## Current Result

- Candidate queue items: 105
- Origin-allowed items: 0
- Missing manual-check items: 0
- Missing dry-run provenance items: 0
- Missing no-processing note items: 0
- Current readiness: 20 checks, 0 failures, 0 warnings

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 12 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.

## Safety

No raw data was modified. No workspace source file was modified. No F-drive backup file was modified. No Origin or Excel process was launched by this change.
