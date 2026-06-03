# Root Docs Extra Changes Hold

Date: 2026-06-03

Scope: holding note only. This file is not a Batch 1 staging candidate.

This note preserves the non-pointer root-document changes that were present before Batch 1 pointer-only cleanup. They may be reviewed later as a separate documentation batch, but they are intentionally excluded from the current Batch 1 candidate set.

## README.md

Extra changes found before pointer-only cleanup:

- Scan and triage examples changed from project-local `workspace_data\LL_detection_copy_20260530` to the external workspace path `D:\Codex Project\科研数据处理\数据\workspace_data\LL_detection_copy_20260530`.
- Data-safety section changed the workspace copy path to the same external workspace path.
- Project layout rules added `scripts/reports/` and `scripts/data_types/`, and changed `workspace_data/` guidance to an external path.
- Added `Phase 1.13 Optional Scientific Package Adapters` section covering `src/adapters/`, optional packages, blocked `matchms`, and related reports.
- Added `JEOL EPR Decode` section with the `jeol-epr-decode` command and binary decode details.

## PROJECT_STATUS.md

Extra changes found before pointer-only cleanup:

- Phase 1.8 section added external workspace data-copy path.
- Added `Phase 1.13 Package Adapter Execution` section covering optional package installation/verification, blocked `matchms`, lazy adapters, tests, and read-only data/package boundaries.

## TASK_BOARD.md

Extra changes found before pointer-only cleanup:

- Added `Phase 1.13 Completed / In Progress` checklist covering instruction archive, baseline validation, pip state, package installation, blocked `matchms`, adapters, tests, reports, and a pending final full validation item.

## AGENT_HANDOFF.md

Extra changes found before pointer-only cleanup:

- Workspace copy path changed from project-local `workspace_data\LL_detection_copy_20260530` to the external workspace path.
- Script-layout guidance expanded from maintenance/one_off/archive to also include `scripts\reports` and `scripts\data_types\<data_type>`.
- Guidance added that workspace data lives outside the project and should not be recreated inside the project tree.
- Added `Phase 1.13 Package Adapter Handoff` section covering optional adapter scope, `src/adapters/`, safe/default helpers, GPL/license-unclear reference-only packages, and related reports.

## Suggested Later Review

If these items are needed, review them after Batch 1 as a separate documentation-scope batch. That later batch should decide whether root docs should carry this detail or whether the detail belongs only in `docs/agent_reports/`, `docs/PROJECT_INDEX.md`, `docs/CURRENT_STATUS.md`, and script-layout preflight docs.
