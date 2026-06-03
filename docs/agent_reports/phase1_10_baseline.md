# Phase 1.10 Baseline

- Generated: 2026-06-02T01:14:19
- Git status short lines: 54
- pytest: 237 passed, 30 warnings
- deps-audit: exit 0
- validate: exit 0
- readiness at baseline: exit 1, expected P1 failure before refresh (`origin_batch_dry_run_plan_current`)
- Python interpreter: `D:\Python\python.exe`
- Workspace copy exists: True
- F backup exists: False
- Standard result package exists: True
- Latest material collection exists: True
- Origin process residue before work: none observed
- P0: none known
- P1: material collection index schema mismatch for origin-batch

## Git Status Short

```text
port.json
 M output/reports/readiness_report.md
 M src/cli.py
 M src/core/origin_batch.py
?? docs/agent_reports/PHASE1_9_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.md
?? docs/agent_reports/phase1_10_instruction_archive.md
?? docs/agent_reports/phase1_9_artifact_and_result_package_inventory.md
?? docs/agent_reports/phase1_9_data_type_coverage_for_chatgpt.md
?? docs/agent_reports/phase1_9_defect_risk_register.md
?? docs/agent_reports/phase1_9_dependency_and_adapter_status.md
?? docs/agent_reports/phase1_9_final_handoff_instruction_archive.md
?? docs/agent_reports/phase1_9_final_validation_status.md
?? docs/agent_reports/phase1_9_git_and_change_state.md
?? docs/agent_reports/phase1_9_manual_review_and_override_status.md
?? docs/agent_reports/phase1_9_project_structure_inventory.md
?? docs/agent_reports/phase1_9_scan_triage_current_snapshot.md
?? docs/agent_reports/phase1_9_scientific_safety_and_claims_review.md
?? output/reports/PHASE1_9_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json
?? output/reports/_phase1_9_generate_handoff_audit.py
?? output/reports/phase1_10_material_collection_normalized_dry_run.json
?? output/reports/phase1_10_material_collection_normalized_dry_run.md
?? output/reports/phase1_10_material_collection_normalized_manifest.csv
?? output/reports/phase1_10_material_collection_normalized_manifest.json
?? output/reports/phase1_10_material_collection_normalized_manifest.md
?? output/reports/phase1_10_readiness_stdout.txt
?? output/reports/phase1_10_standard_origin_batch_dry_run.json
?? output/reports/phase1_10_standard_origin_batch_dry_run.md
?? output/reports/phase1_9_artifact_and_result_package_inventory.json
?? output/reports/phase1_9_artifact_and_result_package_inventory.md
?? output/reports/phase1_9_command_snapshots.json
?? output/reports/phase1_9_data_type_coverage_for_chatgpt.json
?? output/reports/phase1_9_data_type_coverage_for_chatgpt.md
?? output/reports/phase1_9_defect_risk_register.json
?? output/reports/phase1_9_defect_risk_register.md
?? output/reports/phase1_9_dependency_and_adapter_status.json
?? output/reports/phase1_9_dependency_and_adapter_status.md
?? output/reports/phase1_9_final_validation_status.json
?? output/reports/phase1_9_final_validation_status.md
?? output/reports/phase1_9_git_and_change_state.json
?? output/reports/phase1_9_handoff_report_bundle.zip
?? output/reports/phase1_9_manual_review_and_override_status.json
?? output/reports/phase1_9_manual_review_and_override_status.md
?? output/reports/phase1_9_project_structure_inventory.json
?? output/reports/phase1_9_scan_triage_current_snapshot.json
?? output/reports/phase1_9_scan_triage_current_snapshot.md
?? output/reports/phase1_9_scientific_safety_and_claims_review.json
?? output/reports/phase1_9_scientific_safety_and_claims_review.md
?? output/review_dashboard/phase1_9_final_handoff_audit_index.md
?? src/core/manifest_normalizer.py
?? src/core/manifest_schema.py
?? tests/test_phase1_10_manifest_normalizer.py
?? tmp_cli_probe/
?? tmp_malformed.csv
?? tmp_out.txt

```
