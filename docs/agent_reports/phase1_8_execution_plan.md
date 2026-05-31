# Phase 1.8 Execution Plan

## Goal

Make Phase 1.8 a safe decision gate between Phase 1.7 review-only proposals and any future real processing. The project should let the user review candidate rows, explicitly approve selected rows, and run a dry-run planner that proves what would or would not enter a future no-Origin queue.

## Boundaries

- Do not process new real data.
- Do not start Origin.
- Do not repeat the 167 completed Phase 1.6 Origin outputs.
- Do not auto-apply manual overrides.
- Do not bulk process `MANUAL_REVIEW`.
- Do not write into raw data, workspace source data, or the F-drive backup.

## Files To Create Or Modify

- Create `src/core/reviewed_queue.py`: reviewed proposal template generation, decision validation, hash checks, dry-run plan, reports.
- Modify `src/cli.py`: add `reviewed-queue` command.
- Create `tests/test_phase1_8_reviewed_queue.py`: focused unit and CLI tests.
- Update `README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, `AGENT_HANDOFF.md`, `docs/REAL_DATA_INTAKE_GUIDE.md`, `output/review_dashboard/index.md`.
- Generate `output/reports/phase1_8_review_decisions_template.csv`, `output/reports/phase1_8_reviewed_queue_plan.json`, `output/reports/phase1_8_reviewed_queue_plan.md`, `docs/agent_reports/phase1_8_reviewed_queue_report.md`.
- Generate final reports under `docs/agent_reports` and `output/reports`.

## Tasks

### Task 1: Baseline And Instruction Archive

- [x] Save Phase 1.8 instruction to `D:\Codex Project\科研数据处理\指令归档\GroupMeetingAutoPPT_phase1_8_reviewed_queue_and_processing_gate_instruction.md`.
- [x] Compute instruction SHA256.
- [x] Run baseline commands and record results in `docs/agent_reports/phase1_8_baseline.md`.

### Task 2: Reviewed Queue Planner

- [x] Add `ReviewedQueueOptions`.
- [x] Load Phase 1.7 proposal JSON.
- [x] Generate decision CSV template with one row per proposal.
- [x] Load user decision CSV.
- [x] Treat blank decisions as skipped.
- [x] Accept only `approve_for_no_origin_queue`.
- [x] Require `approved_by` and `approval_date` on approved rows.
- [x] Require `high_risk_ack=true` for high-risk rows.
- [x] Require `folder_header_conflict_ack=true` for folder/header conflict rows.
- [x] Check proposal path traversal.
- [x] Check source file still exists under workspace copy.
- [x] Check current source hash matches proposal hash.
- [x] Check current triage still contains the source hash/path and remains `MANUAL_REVIEW`.
- [x] Block processed Phase 1.6 source hashes.
- [x] Write dry-run plan and Markdown report.

### Task 3: CLI Integration

- [x] Add `run.py reviewed-queue --proposals ... --write-template`.
- [x] Add `run.py reviewed-queue --proposals ... --decisions ... --dry-run`.
- [x] Keep planner no-Origin and no-process by construction.
- [x] Return nonzero only for invalid inputs or execution-blocking misuse, not for a blank approval template.

### Task 4: Tests

- [x] Template generation covers all proposal rows.
- [x] Blank decisions produce zero approved items.
- [x] Approved low/medium-risk row enters plan.
- [x] High-risk row without acknowledgement is blocked.
- [x] Missing approver/date blocks approved row.
- [x] Hash mismatch blocks approved row.
- [x] Already processed hashes are blocked.
- [x] Path traversal is blocked.
- [x] CLI help and dry-run work.
- [x] Tests confirm reviewed-queue does not import or call Origin/process APIs.

### Task 5: Reports And Documentation

- [x] Generate Phase 1.8 reviewed-queue template and dry-run plan.
- [x] Generate post-rule/post-AI manual review required list.
- [x] Update dashboard and handoff docs with Phase 1.8 workflow.
- [x] Record that no real processing and no Origin export occurred.
- [x] Record remaining user actions before Phase 1.9.

### Task 6: Final Verification

- [ ] Run `D:\Python\python.exe -m pytest`.
- [ ] Run `D:\Python\python.exe run.py deps-audit`.
- [ ] Run `D:\Python\python.exe run.py validate`.
- [ ] Run reviewed-queue template generation.
- [ ] Run reviewed-queue dry-run with blank template.
- [ ] Confirm Origin process residual is 0.
- [ ] Write final summary.

## Definition Of Enough For This Phase

The project is sufficiently usable for the current safety boundary when the user can open a generated decision CSV, approve exact proposal rows, and run a dry-run that proves which rows would be accepted or blocked before any future real no-Origin processing. Further progress requires user approval of candidate rows.
