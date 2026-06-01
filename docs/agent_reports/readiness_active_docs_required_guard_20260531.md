# Readiness Active Docs Required Guard

Generated: 2026-05-31

## Problem

`run.py readiness` checked active entry documents for stale old-project references, but missing documents were treated as skipped. That could allow a project state with no README, status, task board, handoff, intake guide, compatibility matrix, or dashboard entry to still report ready.

## Change

`run.py readiness` now fails `active_project_name_references_current` if any required active entry document is missing.

Required active entry documents:

- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
- `docs/REAL_DATA_INTAKE_GUIDE.md`
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- `output/review_dashboard/index.md`

## Current Result

- Required active entry documents: present
- Stale old-project references in active documents: none
- Current readiness: 20 checks, 0 failures, 0 warnings

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 13 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.

## Safety

No raw data was modified. No workspace source file was modified. No F-drive backup file was modified. No Origin or Excel process was launched by this change.
