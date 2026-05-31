# Agent Handoff

## Latest State: Phase 1.8

Read these first:

- `docs/agent_reports/phase1_8_execution_plan.md`
- `docs/agent_reports/phase1_8_reviewed_queue_report.md`
- `docs/agent_reports/phase1_8_manual_review_required_after_ai.md`
- `docs/agent_reports/phase1_8_final_validation.md`
- `output/reports/phase1_8_final_summary.md`

Latest locked Origin package: `output\phase1_6_origin_results_20260531_041538`.

## What Has Been Processed

- Phase 1.5 no-Origin package: 167 datasets.
- Phase 1.6 Origin package: 167 datasets.
- Successful Origin types: EIS 22, photocurrent 3, Raman 30, Mott-Schottky 90, EPR 13, XPS 9.
- Phase 1.7 and Phase 1.8 processed no new real datasets and exported no new Origin figures.

## Phase 1.8 Additions

- `run.py reviewed-queue --proposals ... --write-template` creates a user decision CSV.
- `run.py reviewed-queue --proposals ... --decisions ... --dry-run` validates approved rows and writes a plan.
- Blank decisions skip rows.
- Only `approve_for_no_origin_queue` can approve a row.
- Approved rows require `approved_by` and `approval_date`.
- High-risk rows require `high_risk_ack=true`.
- Folder/header conflict rows require `folder_header_conflict_ack=true`.
- Planner checks source path, current hash, current triage state, Phase 1.6 processed hashes, and forbidden types.
- Planner does not launch Origin and does not call `process`.
- Post-rule/post-AI manual review list generated at `output/reports/phase1_8_manual_review_required_after_ai.csv`.

## Current Counts

- Phase 1.8 reviewed-queue proposals: 18
- Current dry-run approved/skipped/blocked: 0/18/0
- Manual review required after AI-assisted recognition: 538
- Already represented in Phase 1.6 and excluded from user-review list: 151
- Duplicate-grouped and excluded from user-review list: 53

## Paths

- Project root: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- Workspace copy: `workspace_data\LL_detection_copy_20260530`
- Stable F-drive backup: `F:\课题\LL\检测`
- Instruction archive: `D:\Codex Project\科研数据处理\指令归档`

## Commands

```powershell
D:\Python\python.exe -m pytest
D:\Python\python.exe run.py deps-audit
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --write-template
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --decisions output\reports\phase1_8_review_decisions_template.csv --dry-run
```

## Safety

Do not modify F-drive backup or workspace source files. Do not process all MANUAL_REVIEW. Do not auto-apply override proposals. Do not create PPT paths or kinetics processors. Routine tests and no-Origin planning must not launch Origin. Real processing requires a future explicit user-approved queue.

## Phase 1.9 Suggestion

After the user fills `phase1_8_review_decisions_template.csv`, build a small no-Origin queue only from approved rows. Do not use `--include-ambiguous` globally. Origin export remains a later explicit step after no-Origin QC.
