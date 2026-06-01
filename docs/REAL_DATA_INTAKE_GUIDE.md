# Real Data Intake Guide

Use this guide for Phase 1.8 reviewed decisions and the next explicitly approved processing phase.

## Principles

- Do not modify, move, delete, or rename original raw data.
- Do not write outputs into `workspace_data\LL_detection_copy_20260530` source folders.
- Do not write into `F:\课题\LL\检测`.
- Use scan and triage first.
- Do not process all `MANUAL_REVIEW`.
- Do not auto-apply manual override proposals.
- Keep SEM, TEM, NMR, MS, and kinetics/reference folders scan-only.

## Review Before Processing

Start with:

- `output/reports/phase1_7_origin_preview_review_checklist.csv`
- `output/reports/phase1_8_review_decisions_template.csv`
- `output/reports/phase1_8_reviewed_queue_plan.md`
- `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- `output/reports/phase1_8_new_auto_process_plan.md`

Only rows explicitly approved in the Phase 1.8 decision CSV may become future no-Origin queue candidates.

## How To Fill The Phase 1.8 Decision CSV

Allowed values:

- Blank `user_decision`: skip.
- `reject`, `keep_manual_review`, `do_not_process`: skip with a recorded reason.
- `approve_for_no_origin_queue`: candidate for a future no-Origin queue after dry-run validation.

Required for approved rows:

- `approved_by`
- `approval_date`
- `high_risk_ack=true` for high-risk rows.
- `folder_header_conflict_ack=true` for folder/header conflict rows.

Do not edit traceability columns. Save the CSV as UTF-8.

## Reviewed Queue Dry-Run

```powershell
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --write-template
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --decisions output\reports\phase1_8_review_decisions_template.csv --dry-run
```

The planner blocks stale proposals, hash mismatches, missing source files, missing approval metadata, high-risk rows without acknowledgement, already processed hashes, forbidden data types, and path traversal.

## New AUTO_PROCESS Dry-Run Queue

Use this command to rebuild the current automatically recognized candidate queue without processing data:

```powershell
D:\Python\python.exe run.py auto-queue
```

Current generated files:

- Plan: `output/reports/phase1_8_new_auto_process_plan.md`
- Candidate queue: `output/reports/phase1_8_new_auto_process_queue.json`

The latest plan accepts 105 new candidates after excluding 83 raw queue items already represented by the locked Phase 1.6 Origin package. It is still dry-run only: it does not call `process`, does not launch Origin, and is intended for a future explicit no-Origin batch after review.

## Current Manual Review Workbook

`output/reports/phase1_8_manual_review_required_filtered.xlsx` is the current list of files still requiring user attention after rule-based recognition, triage refresh, and same-data filtering. It excludes files already represented by a successful Phase 1.6 result or by another AUTO_PROCESS/DUPLICATE_SUPPRESSED format in the same data group.

Current counts:

- Latest `MANUAL_REVIEW`: 618
- Excluded from main workbook because same data already has a representative: 125
- Still requiring user review in the workbook: 493

The older `output/reports/phase1_8_manual_review_required_after_ai.csv` is historical and should not be used as the current review list.

## BET Status

`D:\Codex Project\科研数据处理\数据\26.5.29\BET` already contains legacy BET OPJU/PNG/TSV/CSV outputs. Those files are preserved as existing work, but BET has not yet been incorporated into the locked Phase 1.6 standardized results package. Current triage still keeps BET in manual review/proposal mode until adsorption/desorption columns and source format handling are reviewed.

## Origin Policy

Normal tests must not launch Origin. no-Origin planning must not launch Origin. Only a future explicit `--with-origin` queue may export OPJU/TIF/PNG. Parallel Origin remains disabled until task-owned instance tracking is implemented and approved.
