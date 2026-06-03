# Phase 1.12 Commit Commands

ALLOW_GIT_COMMIT is false. These commands were generated but not executed.

## Scheme A: minimal code and governance commit (recommended)
```powershell
git add ".gitignore" "AGENT_HANDOFF.md" "PROJECT_STATUS.md" "README.md" "TASK_BOARD.md" "src/cli.py" "src/core/origin_batch.py" "docs/indexes/" "src/core/manifest_normalizer.py" "src/core/manifest_schema.py" "tests/test_phase1_10_manifest_normalizer.py"
git commit -m "Phase 1.10-1.11: stabilize manifests and freeze release baseline"
```

## Scheme B: code plus key audit reports
```powershell
git add ".gitignore" "AGENT_HANDOFF.md" "PROJECT_STATUS.md" "README.md" "TASK_BOARD.md" "src/cli.py" "src/core/origin_batch.py" "docs/indexes/" "src/core/manifest_normalizer.py" "src/core/manifest_schema.py" "tests/test_phase1_10_manifest_normalizer.py" "docs/agent_reports/PHASE1_10_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md" "docs/agent_reports/PHASE1_11_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md" "docs/agent_reports/phase1_10_baseline.md" "docs/agent_reports/phase1_10_canonical_freeze_report.md" "docs/agent_reports/phase1_10_final_validation.md" "docs/agent_reports/phase1_10_instruction_archive.md" "docs/agent_reports/phase1_10_manifest_schema_audit.md" "docs/agent_reports/phase1_10_next_manual_review_batch_plan.md" "docs/agent_reports/phase1_10_origin_batch_manifest_schema.md" "docs/agent_reports/phase1_10_output_outputs_role_governance.md" "docs/agent_reports/phase1_10_reviewer_report.md" "docs/agent_reports/phase1_10_scientific_safety_review.md" "docs/agent_reports/phase1_11_commit_ready_report.md" "docs/agent_reports/phase1_11_final_package_integrity_audit.md" "docs/agent_reports/phase1_11_final_validation.md" "docs/agent_reports/phase1_11_gitignore_update_report.md" "docs/agent_reports/phase1_11_instruction_archive.md" "docs/agent_reports/phase1_11_project_hygiene_append_instruction_archive.md" "docs/agent_reports/phase1_11_project_hygiene_audit.md" "docs/agent_reports/phase1_11_project_hygiene_final_validation.md" "docs/agent_reports/phase1_11_release_freeze_baseline.md" "docs/agent_reports/phase1_11_temp_cleanup_report.md" "docs/agent_reports/phase1_11_temp_file_audit.md" "docs/agent_reports/phase1_12_instruction_archive.md" "output/reports/PHASE1_10_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json" "output/reports/PHASE1_11_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json"
git commit -m "Phase 1.10-1.11: stabilize manifests, freeze baseline, and add audit handoff"
```

## Scheme C: full audit-record candidate, requires user confirmation
```powershell
git add ".gitignore" "AGENT_HANDOFF.md" "PROJECT_STATUS.md" "README.md" "TASK_BOARD.md" "src/cli.py" "src/core/origin_batch.py" "docs/indexes/" "src/core/manifest_normalizer.py" "src/core/manifest_schema.py" "tests/test_phase1_10_manifest_normalizer.py" "docs/agent_reports/PHASE1_10_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md" "docs/agent_reports/PHASE1_11_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md" "docs/agent_reports/phase1_10_baseline.md" "docs/agent_reports/phase1_10_canonical_freeze_report.md" "docs/agent_reports/phase1_10_final_validation.md" "docs/agent_reports/phase1_10_instruction_archive.md" "docs/agent_reports/phase1_10_manifest_schema_audit.md" "docs/agent_reports/phase1_10_next_manual_review_batch_plan.md" "docs/agent_reports/phase1_10_origin_batch_manifest_schema.md" "docs/agent_reports/phase1_10_output_outputs_role_governance.md" "docs/agent_reports/phase1_10_reviewer_report.md" "docs/agent_reports/phase1_10_scientific_safety_review.md" "docs/agent_reports/phase1_11_commit_ready_report.md" "docs/agent_reports/phase1_11_final_package_integrity_audit.md" "docs/agent_reports/phase1_11_final_validation.md" "docs/agent_reports/phase1_11_gitignore_update_report.md" "docs/agent_reports/phase1_11_instruction_archive.md" "docs/agent_reports/phase1_11_project_hygiene_append_instruction_archive.md" "docs/agent_reports/phase1_11_project_hygiene_audit.md" "docs/agent_reports/phase1_11_project_hygiene_final_validation.md" "docs/agent_reports/phase1_11_release_freeze_baseline.md" "docs/agent_reports/phase1_11_temp_cleanup_report.md" "docs/agent_reports/phase1_11_temp_file_audit.md" "docs/agent_reports/phase1_12_instruction_archive.md" "output/reports/PHASE1_10_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json" "output/reports/PHASE1_11_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json" "output/review_dashboard/index.md" "docs/agent_reports/PHASE1_9_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md" "docs/agent_reports/phase1_9_artifact_and_result_package_inventory.md" "docs/agent_reports/phase1_9_data_type_coverage_for_chatgpt.md" "docs/agent_reports/phase1_9_defect_risk_register.md" "docs/agent_reports/phase1_9_dependency_and_adapter_status.md" "docs/agent_reports/phase1_9_final_handoff_instruction_archive.md" "docs/agent_reports/phase1_9_final_validation_status.md" "docs/agent_reports/phase1_9_git_and_change_state.md" "docs/agent_reports/phase1_9_manual_review_and_override_status.md" "docs/agent_reports/phase1_9_project_structure_inventory.md" "docs/agent_reports/phase1_9_scan_triage_current_snapshot.md" "docs/agent_reports/phase1_9_scientific_safety_and_claims_review.md" "output/review_dashboard/phase1_9_final_handoff_audit_index.md" "output/reports/phase1_12_precommit_origin_batch_dry_run.json" "output/reports/phase1_12_precommit_origin_batch_dry_run.md"
git commit -m "Phase 1.10-1.12: commit release baseline audit records"
```

## Safety check before any manual commit
```powershell
git status --short
git diff --cached --name-only
```

Do not stage workspace_data, raw data, output phase packages, OPJU/TIF/PNG artifacts, tmp files, pycache, or .pytest_cache.
