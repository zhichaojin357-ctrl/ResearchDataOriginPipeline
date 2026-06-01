# Phase 1.8 Review Dashboard

- Last refreshed: 2026-05-31
- Project root: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- Stable F-drive backup: `F:\课题\LL\检测`
- Latest locked Origin package: `output\phase1_6_origin_results_20260531_041538`

## Status Summary

- Phase 1.6 Origin success/failure: 167/0
- Origin visual QC: 167 `QC_PASS`
- Reviewed-queue proposals: 18
- Current reviewed-queue dry-run approved/skipped/blocked: 0/18/0
- Will launch Origin: false
- Will run process: false
- Manual review rows in current filtered workbook: 493
- Same-data items excluded from the main workbook: 125
- Current triage: AUTO_PROCESS 188, MANUAL_REVIEW 618
- New AUTO_PROCESS queue after Phase 1.6 exclusion: 105 candidates
- New AUTO_PROCESS queue types: EPR 44, Mott-Schottky 32, EIS 24, photocurrent 5

## Phase 1.8 Links

- [Reviewed queue decision template](../reports/phase1_8_review_decisions_template.csv)
- [Reviewed queue dry-run plan](../reports/phase1_8_reviewed_queue_plan.md)
- [Current filtered manual-review report](../reports/phase1_8_manual_review_required_filtered_report.md)
- [Current filtered manual-review workbook](../reports/phase1_8_manual_review_required_filtered.xlsx)
- [New AUTO_PROCESS dry-run plan](../reports/phase1_8_new_auto_process_plan.md)
- [New AUTO_PROCESS candidate queue](../reports/phase1_8_new_auto_process_queue.json)
- [Phase 1.8 execution plan](../../docs/agent_reports/phase1_8_execution_plan.md)

## Phase 1.7 Links

- [Preview gallery](phase1_7_preview_gallery.md)
- [Preview gallery by type](phase1_7_preview_gallery_by_type.md)
- [Preview checklist](../reports/phase1_7_origin_preview_review_checklist.md)
- [High-priority manual review](../reports/phase1_7_high_priority_manual_review.md)
- [Manual override decision table](../reports/phase1_7_manual_override_decision_table.md)
- [Manifest runner plan](../reports/phase1_7_manifest_runner_plan.md)
- [Origin COM proof](../reports/phase1_7_origin_com_isolation_proof.md)
- [Triage recognition comparison](../reports/phase1_7_triage_recognition_before_after_comparison.md)
- [New override proposals](../reports/phase1_7_new_override_proposals_after_optimization.md)

## User Steps

1. Review the 167 completed Origin previews.
2. Open `phase1_8_review_decisions_template.csv`.
3. For any row to approve, set `user_decision=approve_for_no_origin_queue`, fill `approved_by` and `approval_date`, and add required acknowledgement fields.
4. Leave uncertain rows blank.
5. Re-run reviewed-queue dry-run and inspect accepted/skipped/blocked results before any future processing.
6. Review `phase1_8_new_auto_process_plan.md` before using any automatically recognized queue.

## Safety

Do not process the remaining MANUAL_REVIEW set in bulk. Use user-approved rows only. Do not run real Origin export from Phase 1.8 dry-run reports.
