# BET Standardization Gap Report

Generated: 2026-05-31

BET has legacy OPJU/PNG/TSV/CSV outputs under `D:\Codex Project\科研数据处理\数据\26.5.29\BET`, but it is not yet in the standardized Phase 1.6 package or current Phase 1.8 AUTO_PROCESS queue.

Key evidence:

- Workspace BET files: 42
- BET triage decisions: `AUXILIARY_ONLY` 10, `MANUAL_REVIEW` 23, `EXCLUDE_INVALID` 9
- BET parser status: `skipped` 34, `fail` 8
- BET `.xls` parser failure reason: `legacy .xls requires xlrd or explicit Excel COM processing`
- Phase 1.6 standardized BET rows: 0
- Current Phase 1.8 AUTO_PROCESS BET rows: 0

Recommendation: treat existing BET plots as preserved legacy outputs, then add a future explicit BET normalization step before standardized no-Origin and Origin packaging.
