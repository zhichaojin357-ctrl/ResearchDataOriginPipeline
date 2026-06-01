# Task Board

## Phase 1.8 Completed

- [x] Archived Phase 1.8 instruction and SHA256.
- [x] Wrote Phase 1.8 execution plan.
- [x] Added `reviewed-queue` decision-template and dry-run planner.
- [x] Added metadata, hash, current-triage, processed-hash, high-risk, folder/header-conflict, and path safety gates.
- [x] Added Phase 1.8 reviewed-queue tests.
- [x] Generated `phase1_8_review_decisions_template.csv`.
- [x] Generated `phase1_8_reviewed_queue_plan.json` and `.md`.
- [x] Generated current filtered manual-review workbook and same-data exclusion audit.
- [x] Added `auto-queue` dry-run planner for current AUTO_PROCESS items.
- [x] Generated `phase1_8_new_auto_process_plan.json`, `.md`, and `phase1_8_new_auto_process_queue.json`.
- [x] Documented BET legacy-output versus standardized-package gap.
- [x] Hardened `auto-queue` forbidden-type filtering for variant labels such as `sem_image_data`, `SEM/TEM/NMR/MS`, and `动力学`.
- [x] Hardened `reviewed-queue` forbidden-type filtering for composite labels such as `SEM/TEM/NMR/MS`.
- [x] Refreshed Phase 1.8 final summary so it points to the current filtered workbook and auto-queue plan.
- [x] Added `run.py readiness` project preflight and generated current readiness reports.
- [x] Hardened `run.py validate` so deferred/reference registry entries must stay scan-only and processor-free.
- [x] Hardened `run.py readiness` so it also checks the latest validation report safety markers.
- [x] Hardened `run.py readiness` so stale validation reports fail when validation-related source/config files are newer.
- [x] Hardened `run.py readiness` so Phase 1.6 `result_summary.json` must match the locked package `index.csv`.
- [x] Hardened `run.py readiness` so the old project path and active-document references cannot silently return.
- [x] Hardened `run.py readiness` so missing active entry documents fail readiness.
- [x] Hardened `run.py readiness` so manual-review CSV, Excel, and report row counts must match.
- [x] Hardened `run.py readiness` so the desktop manual-review workbook must match the project copy.
- [x] Hardened `run.py readiness` so the review dashboard must point to current Phase 1.8 entry files.
- [x] Hardened `run.py readiness` so the auto-queue plan and generated queue must agree and stay no-Origin/manual-check/dry-run provenance only.
- [x] Hardened `run.py readiness` so the generated auto-queue item identities must match the embedded dry-run plan queue.
- [x] Hardened `run.py readiness` so reviewed-queue proposals, decision template, and dry-run plan must stay current and no-Origin/no-process.
- [x] Hardened `reviewed-queue` and `run.py readiness` so reviewed-queue plans record and verify proposal/decision input SHA256 values.
- [x] Hardened `run.py readiness` so reviewed-queue plans with blocked approval rows fail readiness instead of looking ready.
- [x] Hardened `run.py process --from-queue` so the stale raw `processing_queue.json` cannot be used directly when it overlaps the Phase 1.6 package.
- [x] Hardened `run.py process --from-queue` so unknown, scan-only, or processor-mismatched queue data types fail queue validation before processing.
- [x] Hardened `run.py process --from-queue --include-ambiguous` so MANUAL_REVIEW items require explicit promotion/user-approval provenance.
- [x] Hardened `run.py process` so `--auto-select` cannot silently override `--with-origin` or conflict with an explicit `--from-queue`.
- [x] Hardened reviewed-queue decision CSV parsing so malformed schema, missing/duplicate/blank/unknown headers, blank proposal ids, and malformed CSV fail before planning.
- [x] Hardened queue-driven output naming so reviewed-queue items with the same source stem get distinct processed/metadata/artifact paths.
- [x] Hardened `run.py` so user-facing missing-file and business-rule CLI failures return concise errors instead of tracebacks.
- [x] Hardened queue/proposal JSON shape validation so malformed `items` containers fail cleanly before planning or processing.
- [x] Hardened queue/proposal JSON element validation so non-object `items` entries fail with item-numbered CLI errors and no traceback.
- [x] Hardened `auto-queue --queue` JSON validation so malformed current AUTO_PROCESS queues fail cleanly before dry-run planning.
- [x] Hardened `origin-batch --manifest` CSV header validation so malformed manifests fail cleanly before dry-run planning.
- [x] Hardened `origin-batch --manifest` CSV row-width validation so malformed manifest rows fail cleanly before dry-run planning.
- [x] Hardened `origin-batch --manifest` so older Phase 1.6 package manifests can verify package-local source copies by hash even after workspace files are reorganized.
- [x] Hardened `run.py readiness` so it fails if the origin-batch dry-run plan has blocked items or Origin launch flags.
- [x] Hardened `xps-heterojunction-stacked` so missing explicit XPS input files fail before output directories are created.
- [x] Hardened `scan`, `triage`, and `process` so missing input directories fail before empty outputs are created.
- [x] Added `run.py readiness --no-desktop-review-xlsx` for portable checks while keeping the desktop workbook check enabled by default.
- [x] Updated README, project status, task board, handoff, intake guide, and dashboard.

## Still Open For User

- [ ] Review 167 Phase 1.6 PNG previews: `output/reports/phase1_7_origin_preview_review_checklist.csv`.
- [ ] Fill reviewed decisions only for files you approve: `output/reports/phase1_8_review_decisions_template.csv`.
- [ ] Review unresolved files in the current filtered workbook: `output/reports/phase1_8_manual_review_required_filtered.xlsx`.
- [ ] Review the new AUTO_PROCESS dry-run plan: `output/reports/phase1_8_new_auto_process_plan.md`.
- [ ] Use `D:\Python\python.exe run.py readiness` before Phase 1.9 processing to confirm current artifacts are still consistent.
- [ ] Decide whether BET legacy `.xls` exports should be normalized into the standard package in a future explicit phase.
- [ ] Decide whether proprietary/binary/parser-failed files should be exported to numeric tables or kept scan-only.
- [ ] Phase 1.9: run a small no-Origin batch only from reviewed queue files, starting with low-risk entries in `output/reports/phase1_8_new_auto_process_queue.json` or explicitly approved Phase 1.8 rows.
- [ ] Future: implement task-owned Origin instance tracker before any parallel Origin export.
- [ ] Future hardening should prioritize major usability or safety bugs; defer cosmetic cleanup and minor edge cases.

## Always Forbidden

PPT generation, kinetics processor creation, SEM/TEM/NMR/MS processing, raw-data modification, F-drive modification, and unreviewed bulk MANUAL_REVIEW processing remain forbidden.
