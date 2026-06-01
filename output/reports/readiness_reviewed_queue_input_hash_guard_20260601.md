# Reviewed-Queue Input Hash Guard

- Date: 2026-06-01
- Scope: Phase 1.8 reviewed-queue dry-run planning and readiness validation.
- Safety: no raw data changes, no workspace source changes, no F-drive writes, no Origin launch, no processing run.

## Problem

The previous reviewed-queue freshness guard relied mainly on file modification time. That can miss stale plans after copy, restore, checkout, archive extraction, or manual timestamp changes.

## Change

- `reviewed-queue` dry-run plans now record `input_hashes.proposals_sha256` and `input_hashes.decisions_sha256`.
- `run.py readiness` now recomputes both hashes and fails `reviewed_queue_plan_current` if either stored hash differs from the current input file.
- The existing mtime check remains as an additional guard.
- The Markdown reviewed-queue plan prints both input hashes.

## Current Real Plan

- Plan: `output/reports/phase1_8_reviewed_queue_plan.json`
- Proposals SHA256: `bb02770fbb18d4cc212ba900df1ed7a56a6fbab028d5a974771025e9e1945842`
- Decisions SHA256: `46bef8ae78c8833b2fc722bdcc98d81c614b3cc3718555d61c62414275a461c1`
- Proposals: 18
- Decision rows: 18
- Approved/skipped/blocked: 0/18/0
- Will launch Origin: false
- Will run process: false

## Verification Snapshot

- `D:\Python\python.exe -m pytest tests/test_phase1_8_reviewed_queue.py tests/test_readiness.py -q`: 30 passed, 2 warnings.
- `D:\Python\python.exe -m pytest`: 178 passed, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0; 21 checks, 0 failures, 0 warnings; reviewed-queue input hashes match.
- Residual process check: no `python`, `EXCEL`, `Origin`, or `OriginPro` process remained after validation.

## Files Updated

- `src/core/reviewed_queue.py`
- `src/core/readiness.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_readiness.py`
- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
