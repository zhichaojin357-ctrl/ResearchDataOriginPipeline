# Readiness Project Rename Path Guard

Generated: 2026-05-31

## Problem

The project was physically renamed from `GroupMeetingAutoPPT` to `ResearchDataOriginPipeline`. A future stale junction, copied old directory, or active document that still points to the old path could make users or scripts operate from the wrong workspace.

## Change

`run.py readiness` now adds two checks:

- `old_project_path_absent`: the old sibling path `GroupMeetingAutoPPT` must not exist beside the current project.
- `active_project_name_references_current`: active entry documents must not contain the old project name/path.

The check intentionally allows historical rename audit reports to keep old-name evidence. It only scans active entry points such as README, status, task board, handoff, intake guide, compatibility matrix, and review dashboard.

## Current Result

- Old sibling path: absent
- Active entry documents: no stale old-project references
- Current readiness: 20 checks, 0 failures, 0 warnings

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 11 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.

## Safety

No raw data was modified. No workspace source file was modified. No F-drive backup file was modified. No Origin or Excel process was launched by this change.
