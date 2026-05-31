# Project Status

## Phase 1.8 Status

Phase 1.8 is the current reviewed-queue safety gate. It turns Phase 1.7 review-only proposals into a user decision template and dry-run plan, but it does not run new real processing and does not launch Origin.

- Phase 1.8 instruction archive: `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_phase1_8_reviewed_queue_and_processing_gate_instruction.md`
- Phase 1.8 instruction SHA256: `B3F2A025FC2235F1920C3EDCBB5B274C970B9C458F9D9B8054D46D0C18F508CA`
- Reviewed-queue template: `output\reports\phase1_8_review_decisions_template.csv`
- Reviewed-queue dry-run plan: `output\reports\phase1_8_reviewed_queue_plan.md`
- Post-AI manual review list: `output\reports\phase1_8_manual_review_required_after_ai.csv`
- Current reviewed-queue dry-run: 18 proposals, 0 approved, 18 skipped, 0 blocked, Origin launch false, process false.

## Phase 1.6 Locked Result

- Package: `output\phase1_6_origin_results_20260531_041538`
- Origin success: 167
- Origin failure: 0
- Visual QC: 167 `QC_PASS`
- Material/color verification: PASS
- XPS repair: 9 no-Origin success, 9 Origin success, 0 failure

## Latest Triage

- Total files: 1589
- AUTO_PROCESS: 18
- MANUAL_REVIEW: 742
- EXCLUDE_INVALID: 121
- DUPLICATE_SUPPRESSED: 53
- AUXILIARY_ONLY: 113
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17
- New safe promotion candidates: 0
- New review-only override proposals: 18

## Manual Review After AI-Assisted Recognition

- Total files still requiring manual review after exclusions: 538
- Classifiable but requiring user approval: 18
- Context-classified but still unprocessable safely due parser failure/skipped probe: 520
- Already represented in Phase 1.6 and excluded from user-review list: 151
- Duplicate-grouped and excluded from user-review list: 53

## Current Blocking Items

- User must review the 167 Origin PNG previews before manuscript use.
- User must fill `phase1_8_review_decisions_template.csv` before any Phase 1.9 no-Origin queue can be built.
- User must review `phase1_8_manual_review_required_after_ai.csv` for files that remain unprocessable or need export/parser decisions.
- This directory is not a git repository; commit requires a `.git` repository or explicit initialization.
- Parallel Origin up to 8 remains blocked until a task-owned instance tracker and user confirmation exist.

## Scope Guards

PPT generation, kinetics processors, SEM/TEM/NMR/MS processors, automatic XPS valence assignment, EPR radical assignment, XRD phase assignment, and full MANUAL_REVIEW batch processing remain forbidden.
