# Phase 1.6 Baseline

Created at: 2026-05-31T01:41:09

## Instruction Archive

- Path: `D:\Codex Project\科研数据处理\指令归档\GroupMeetingAutoPPT_phase1_6_origin_production_and_second_wave_instruction.md`
- Exists: True
- SHA256: `993AF1806AA5DB86FCA8E25FDE2DADC3806D3F74429EF9A8B6160109A5C356DF`

## Git

- Branch command output: `fatal: not a git repository (or any of the parent directories): .git`
- Git status exit code: 128
- Git status summary: `fatal: not a git repository (or any of the parent directories): .git`
- Tag command exit code: 128
- Tag command output: `fatal: not a git repository (or any of the parent directories): .git`

## Baseline Commands

- `D:\Python\python.exe -m pytest`: exit 0, 82 passed, 2 openpyxl deprecation warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.

## Environment

- Project root: `D:\Codex Project\科研数据处理\GroupMeetingAutoPPT`
- Python executable: `D:\Python\python.exe`
- PATH python: `D:\MestReNova\python.EXE`
- Workspace copy exists: True (`D:\Codex Project\科研数据处理\GroupMeetingAutoPPT\workspace_data\LL_detection_copy_20260530`)
- F-drive backup exists: True (`F:\课题\LL\检测`)
- Phase 1.5 result folder exists: True (`D:\Codex Project\科研数据处理\GroupMeetingAutoPPT\output\phase1_5_processed_results_20260531_005613`)
- Phase 1.5 completion report exists: True (`D:\Codex Project\科研数据处理\GroupMeetingAutoPPT\docs\agent_reports\phase1_5_merged_completion_report.md`)

## Origin Process State Before Real Export

- Raw query output: `no Origin process`

## Current Output Reports

- `output/reports/ambiguous_files.json`
- `output/reports/ambiguous_files.md`
- `output/reports/classification_report.md`
- `output/reports/data_triage_manifest.json`
- `output/reports/data_triage_report.md`
- `output/reports/dependency_audit.json`
- `output/reports/dependency_audit.md`
- `output/reports/duplicate_candidates.json`
- `output/reports/duplicate_candidates.md`
- `output/reports/excluded_files.json`
- `output/reports/excluded_files.md`
- `output/reports/inventory_manifest.json`
- `output/reports/opju_inventory_20260530.csv`
- `output/reports/origin_errors.md`
- `output/reports/phase1_5_batch_A_processing_failures.json`
- `output/reports/phase1_5_batch_A_processing_report.json`
- `output/reports/phase1_5_batch_A_processing_report.md`
- `output/reports/phase1_5_batch_A_processing_summary.json`
- `output/reports/phase1_5_batch_B_processing_failures.json`
- `output/reports/phase1_5_batch_B_processing_report.json`
- `output/reports/phase1_5_batch_B_processing_report.md`
- `output/reports/phase1_5_batch_B_processing_summary.json`
- `output/reports/phase1_5_batch_C_processing_failures.json`
- `output/reports/phase1_5_batch_C_processing_report.json`
- `output/reports/phase1_5_batch_C_processing_report.md`
- `output/reports/phase1_5_batch_C_processing_summary.json`
- `output/reports/phase1_5_batch_D_processing_failures.json`
- `output/reports/phase1_5_batch_D_processing_report.json`
- `output/reports/phase1_5_batch_D_processing_report.md`
- `output/reports/phase1_5_batch_D_processing_summary.json`
- `output/reports/phase1_5_merged_bug_radar.json`
- `output/reports/phase1_5_merged_bug_radar.md`
- `output/reports/phase1_5_merged_completion_report.md`
- `output/reports/phase1_5_merged_manual_override_proposals.json`
- `output/reports/phase1_5_merged_manual_override_proposals.md`
- `output/reports/phase1_5_merged_promoted_batch_A_no_origin_queue.json`
- `output/reports/phase1_5_merged_promoted_batch_B_no_origin_queue.json`
- `output/reports/phase1_5_merged_promoted_batch_C_no_origin_queue.json`
- `output/reports/phase1_5_merged_promoted_batch_D_no_origin_queue.json`
- `output/reports/processing_failures.json`
- `output/reports/processing_failures.md`
- `output/reports/processing_queue.json`
- `output/reports/processing_queue.md`
- `output/reports/processing_report.json`
- `output/reports/processing_report.md`
- `output/reports/processing_summary.json`
- `output/reports/processing_summary.md`
- `output/reports/source_hash_index.json`
- `output/reports/traceability_groups.json`
- `output/reports/traceability_groups.md`
- `output/reports/validation_report.md`

## Known Success State

- Phase 1.5 has 167 no-Origin result records in the result package.
- Routine tests pass without launching Origin.
- validate passes and confirms Origin importability.

## Known Gaps For Phase 1.6

- Real Origin OPJU/TIF/PNG production has not yet been executed in Phase 1.6.
- 167 no-Origin results still need consistency audit before Origin queue admission.
- Remaining MANUAL_REVIEW items need second-wave clustering and stricter safe-promotion proposals.
