# Phase 1.8 Current Summary

Updated: 2026-06-01

1. Phase 1.8 instruction archive: `D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_phase1_8_reviewed_queue_and_processing_gate_instruction.md`
2. Phase 1.8 instruction SHA256: `B3F2A025FC2235F1920C3EDCBB5B274C970B9C458F9D9B8054D46D0C18F508CA`
3. Phase 1.8 execution plan: `docs/agent_reports/phase1_8_execution_plan.md`
4. Reviewed-queue CLI implemented: `run.py reviewed-queue`
5. Decision template: `output/reports/phase1_8_review_decisions_template.csv`
6. Reviewed-queue plan: `output/reports/phase1_8_reviewed_queue_plan.md`
7. Reviewed-queue dry-run: 18 proposals, 0 approved, 18 skipped, 0 blocked
8. Origin launch: false
9. Process run: false
10. Current manual-review workbook: `output/reports/phase1_8_manual_review_required_filtered.xlsx`
11. Current manual-review CSV: `output/reports/phase1_8_manual_review_required_filtered.csv`
12. Current manual-review report: `output/reports/phase1_8_manual_review_required_filtered_report.md`
13. Current manual-review rows requiring user review: 493
14. Same-data rows excluded from main workbook because a processed/processable representative exists: 125
15. Historical post-AI CSV retained only for traceability: `output/reports/phase1_8_manual_review_required_after_ai.csv`
16. Current triage summary: total 1644, AUTO_PROCESS 188, MANUAL_REVIEW 618, EXCLUDE_INVALID 113, DUPLICATE_SUPPRESSED 66, AUXILIARY_ONLY 117, DEFERRED_TYPE 525, REFERENCE_ONLY 17
17. New AUTO_PROCESS dry-run planner implemented: `run.py auto-queue`
18. New AUTO_PROCESS plan: `output/reports/phase1_8_new_auto_process_plan.md`
19. New AUTO_PROCESS candidate queue: `output/reports/phase1_8_new_auto_process_queue.json`
20. New AUTO_PROCESS dry-run: 188 source items, 105 accepted, 83 skipped as already represented in Phase 1.6, 0 blocked
21. New AUTO_PROCESS accepted types: EPR 44, Mott-Schottky 32, EIS 24, photocurrent 5
22. Auto-queue safety guard: forbidden type variants such as `sem_image_data`, `SEM/TEM/NMR/MS`, `reference_literature`, and `动力学` are blocked before queue output
23. BET status: legacy OPJU/PNG/TSV/CSV outputs exist under `D:\Codex Project\科研数据处理\数据\26.5.29\BET`, but BET is not standardized into the Phase 1.6 package or current auto-queue
24. New/modified code in this phase line: `src/core/reviewed_queue.py`, `src/core/auto_queue.py`, `src/core/readiness.py`, `src/core/process.py`, `src/core/origin_batch.py`, `src/processors/base.py`, `src/cli.py`
25. New/modified tests in this phase line: `tests/test_phase1_8_reviewed_queue.py`, `tests/test_auto_queue.py`, `tests/test_phase1_7_manifest_runner.py`, `tests/test_manual_review_filtered_report.py`, `tests/test_readiness.py`, `tests/test_xps_heterojunction_stacked.py`, `tests/test_phase1_1_process_cli.py`, `tests/test_phase1_2_mixed_triage.py`, `tests/test_phase1_contracts.py`, `tests/test_processor_behaviors.py`
26. New/modified docs/reports: README, PROJECT_STATUS, TASK_BOARD, AGENT_HANDOFF, REAL_DATA_INTAKE_GUIDE, REAL_DATA_COMPATIBILITY_MATRIX, dashboard, Phase 1.8 reports
27. Latest pytest: 217 passed, 2 warnings
28. deps-audit: exit 0
29. validate: exit 0
30. auto-queue dry-run: exit 0
31. reviewed-queue dry-run: exit 0
32. readiness: exit 0, 22 checks, 0 failures, 0 warnings
33. portable readiness without desktop workbook: exit 0, 21 checks, 0 failures, 0 warnings
34. Reviewed-queue readiness now fails if approved rows are blocked, input SHA256 values are stale, or the plan would run process/Origin.
35. Additional hardening: auto-select mode conflicts are rejected, reviewed-queue decision CSV schema is strict, process/reviewed-queue/auto-queue JSON shape and per-item object schema are validated, origin-batch manifest CSV headers and row widths are validated, origin-batch can verify older package manifests through package-local source-copy hashes, readiness now guards the origin-batch dry-run plan, XPS stacked CLI explicit input paths are validated before outputs are created, scan/triage/process input directories are validated before outputs are written, CLI business/missing-file errors are concise instead of tracebacks, and queue-driven output suffixes are derived from full queue-id hashes.
36. No new real data processing or Origin export was run by Phase 1.8 dry-run tools
37. Remaining user action: review `phase1_8_manual_review_required_filtered.xlsx`, review `phase1_8_new_auto_process_plan.md`, and fill `phase1_8_review_decisions_template.csv` only for rows you approve
38. Suggested Phase 1.9: run a small no-Origin batch only from reviewed queue files, starting with low-risk entries in `phase1_8_new_auto_process_queue.json` or explicitly approved Phase 1.8 rows; QC before any Origin export

Suggested commit message: `Phase 1.8: harden reviewed queues and refresh manual review artifacts`
