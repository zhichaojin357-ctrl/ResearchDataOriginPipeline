# Non-XRD Reorganization Path Audit

- Created at: 2026-06-03T14:28:17
- Project root: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- Current workspace root: `D:\Codex Project\科研数据处理\数据\workspace_data\LL_detection_copy_20260530`
- Readiness: {'checks': 21, 'failures': 0, 'warnings': 0, 'ready': True}
- Triage summary: {'total_files': 1644, 'decision_counts': {'AUTO_PROCESS': 209, 'MANUAL_REVIEW': 663, 'EXCLUDE_INVALID': 42, 'DUPLICATE_SUPPRESSED': 71, 'AUXILIARY_ONLY': 117, 'DEFERRED_TYPE': 525, 'REFERENCE_ONLY': 17}}
- Auto-queue summary: {'source_queue_items': 209, 'accepted_count': 126, 'skipped_count': 83, 'blocked_count': 0, 'phase1_6_hashes': 167, 'will_run_process': False, 'will_launch_origin': False}

## Fixes Applied
- output/review_dashboard/index.md: restored current Phase 1.8 workbook and auto-queue links required by readiness.
- src/core/epr_overlay.py: default EPR verified export directory now resolves from configured workspace_root.
- scripts/one_off/verify_jeol_epr_decode_against_exports.py: default EPR root now resolves from configured workspace_root.
- src/core/validate.py: allowed source artifact roots now include configured external workspace_root.
- src/core/phase1_7.py: Origin process inspection now uses UTF-8 replacement decoding and handles empty stdout.
- src/origin/adapter.py and tests/test_origin_adapter.py: pre-export Origin process wait shortened and mocked in unit tests to avoid hanging on user-owned Origin sessions.
- src/core/xps_in_situ.py: restored conservative complete-record panel planning and compatibility for _try_write_origin_project/_quality_checks test calls.
- src/core/xps_heterojunction.py: direct XPS Origin script now keeps X tick labels visible, hides Y numeric labels, and uses locked XPS layer left offset.

## OPJU-Learned Rule Landing
- Formal strategy module: `src/origin/plot_policy.py`
- Formal style config: `config/plot_style.yaml`
- Formal Origin adapter: `src/origin/adapter.py`
- Formal operations layer: `src/origin/operations.py`
- Formal XPS entry: `src/core/xps_heterojunction.py`
- Phase report entry: `src/core/phase1_9.py`
- Temporary comparison script: `scripts/maintenance/opju_exemplar_regression.py`
- Conclusion: OPJU-learned plotting rules are present in formal shared modules and entry points; regression scripts are comparison tools, not the only place containing the rules.

## Cleanup
- Scope: non-XRD task-generated files under `output/origin_jobs` only.
- Pass 1 deleted: 1
- Pass 2 deleted: 36
- Remaining non-XRD origin job files: 0
- Validate after quarantine: exit 0
- Formal OPJU/TIF/PNG/processed CSV/metadata were not deleted.

## Active Path Scan
- `output/reports/data_triage_manifest.json`: {'exists': True, 'old_project_workspace_refs': 1, 'old_project_name_refs': 0, 'external_workspace_refs': 0}
- `output/reports/data_triage_report.md`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 0, 'external_workspace_refs': 0}
- `output/reports/processing_queue.json`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 0, 'external_workspace_refs': 0}
- `output/reports/phase1_8_new_auto_process_plan.json`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 0, 'external_workspace_refs': 0}
- `output/reports/phase1_8_new_auto_process_plan.md`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 0, 'external_workspace_refs': 0}
- `output/reports/phase1_8_new_auto_process_queue.json`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 0, 'external_workspace_refs': 0}
- `output/reports/readiness_report.json`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 1, 'external_workspace_refs': 0}
- `output/reports/readiness_report.md`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 1, 'external_workspace_refs': 0}
- `output/reports/readiness_report_no_desktop.json`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 1, 'external_workspace_refs': 0}
- `output/reports/readiness_report_no_desktop.md`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 1, 'external_workspace_refs': 0}
- `output/review_dashboard/index.md`: {'exists': True, 'old_project_workspace_refs': 0, 'old_project_name_refs': 0, 'external_workspace_refs': 0}

## Verification
- pytest: 290 passed, 28 subtests passed
- deps_audit: exit 0
- validate: exit 0
- readiness_no_desktop: exit 0
- origin_batch_dry_run: exit 0
- real_origin_launch: not launched by this task

## Notes
- Existing Origin64 processes were observed before verification and were not closed because they were not task-owned.
- The remaining old project name references in readiness reports are intentional old_project_path_absent guard entries.
- One old project workspace string remains inside data_triage_manifest observed_column_headers as literal content from an input row, not as the current source root.
- config/local.yaml still contains user-machine F-drive backup/XPS paths; this was treated as machine-local configuration rather than a project-reorganization bug in this goal.
