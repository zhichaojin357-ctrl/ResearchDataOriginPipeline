from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

from openpyxl import Workbook

from src.core.project import default_output_root
from src.core.readiness import ReadinessOptions, run_readiness


def test_readiness_passes_with_current_required_artifacts(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a", "hash-b"])
    _write_result_summary(package / "result_summary.json", total=2)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")
    _write_origin_batch_plan(project, total=2)
    _write_active_entry_docs(project)

    code = run_readiness(
        project,
        ReadinessOptions(
            expected_phase1_6_count=2,
            f_drive_backup=f_backup,
        ),
    )
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 0
    assert report["summary"]["failures"] == 0
    assert report["summary"]["warnings"] == 0
    assert {check["status"] for check in report["checks"]} == {"pass"}


def test_readiness_portable_mode_warns_for_missing_generated_history(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    _write_active_entry_docs(project)
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(
        project,
        ReadinessOptions(
            expected_phase1_6_count=1,
            f_drive_backup=tmp_path / "missing_f_backup",
        ),
    )
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 0
    assert report["summary"]["failures"] == 0
    assert report["summary"]["warnings"] > 0
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    assert statuses["validation_report_current"] == "pass"
    assert statuses["phase1_6_index_count"] == "warning"
    assert statuses["manual_review_filtered_xlsx_exists"] == "warning"
    assert statuses["review_dashboard_current"] == "warning"


def test_readiness_strict_mode_fails_for_missing_generated_history(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    _write_active_entry_docs(project)
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(
        project,
        ReadinessOptions(
            expected_phase1_6_count=1,
            f_drive_backup=tmp_path / "missing_f_backup",
            strict_artifacts=True,
        ),
    )
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "phase1_6_index_count" in failed_names
    assert "manual_review_filtered_xlsx_exists" in failed_names


def test_readiness_fails_on_stale_summary_and_processing_plan_that_would_run(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "will_run_process": True, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    stale = "Post-rule/post-AI manual review CSV: output/reports/phase1_8_manual_review_required_after_ai.csv\n"
    (reports / "phase1_8_final_summary.md").write_text(stale, encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text(stale, encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "auto_queue_dry_run_flags" in failed_names
    assert "phase1_8_summary_current" in failed_names


def test_readiness_fails_when_validation_report_contains_failures(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    (reports / "validation_report.md").write_text(
        "# Validation Report\n\n## Failures\n\n- Deferred/reference registry semantics failed\n",
        encoding="utf-8",
    )

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "validation_report_current" in failed_names


def test_readiness_fails_when_validation_report_is_older_than_validation_inputs(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    validate_source = project / "src" / "core" / "validate.py"
    validate_source.parent.mkdir(parents=True)
    validate_source.write_text("# changed validation logic\n", encoding="utf-8")
    validation_report = default_output_root(project) / "reports" / "validation_report.md"
    os.utime(validation_report, (1000, 1000))
    os.utime(validate_source, (2000, 2000))

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((default_output_root(project) / "reports" / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "validation_report_current" in failed_names


def test_readiness_fails_when_desktop_review_copy_is_stale(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    desktop_copy = project / "desktop" / "phase1_8_manual_review_required_filtered.xlsx"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    desktop_copy.parent.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    desktop_copy.write_bytes(b"stale workbook")
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(
        project,
        ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup, desktop_review_xlsx=desktop_copy),
    )
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "manual_review_desktop_xlsx_matches" in failed_names


def test_readiness_fails_when_dashboard_points_to_historical_manual_review_list(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    (dashboard / "index.md").write_text(
        "- Review `phase1_8_manual_review_required_after_ai.csv`\n",
        encoding="utf-8",
    )
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "review_dashboard_current" in failed_names


def test_readiness_fails_when_auto_queue_plan_and_queue_disagree(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 2, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "auto_queue_plan_queue_consistent" in failed_names


def test_readiness_fails_when_auto_queue_identity_differs_from_plan(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    reports = default_output_root(project) / "reports"
    planned_item = {
        "queue_id": "planned-1",
        "relative_path": "EIS/planned.csv",
        "source_hash": "hash-planned",
        "origin_export_allowed": False,
        "manual_check_required": True,
        "promoted_by_phase": "phase1_8_auto_queue_dry_run",
        "queue_note": "New AUTO_PROCESS candidate not represented in Phase 1.6; no processing has been run by auto-queue.",
    }
    actual_item = {
        **planned_item,
        "queue_id": "actual-1",
        "relative_path": "EIS/actual.csv",
        "source_hash": "hash-actual",
    }
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps(
            {
                "summary": {
                    "accepted_count": 1,
                    "blocked_count": 0,
                    "will_run_process": False,
                    "will_launch_origin": False,
                },
                "queue": {"items": [planned_item]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (reports / "phase1_8_new_auto_process_queue.json").write_text(
        json.dumps({"items": [actual_item]}, ensure_ascii=False),
        encoding="utf-8",
    )

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "auto_queue_plan_queue_consistent" in failed_names


def test_readiness_fails_when_auto_queue_allows_origin(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": True, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "auto_queue_plan_queue_consistent" in failed_names


def test_readiness_fails_when_auto_queue_lacks_dry_run_provenance(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(
        reports / "phase1_8_new_auto_process_queue.json",
        [{"origin_export_allowed": False, "manual_check_required": True, "promoted_by_phase": "manual_edit"}],
    )
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "auto_queue_plan_queue_consistent" in failed_names


def test_readiness_fails_when_manual_review_outputs_disagree(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=2)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "manual_review_outputs_consistent" in failed_names


def test_readiness_fails_when_phase1_6_summary_disagrees_with_index(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    f_backup = project / "fake_f_backup"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir()
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=2)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "phase1_6_result_summary_matches_index" in failed_names


def test_readiness_fails_when_old_project_path_exists(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    (tmp_path / "GroupMeetingAutoPPT").mkdir()

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((default_output_root(project) / "reports" / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "old_project_path_absent" in failed_names


def test_readiness_fails_when_active_docs_reference_old_project_path(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    (project / "README.md").write_text(
        "Use D:\\Codex Project\\科研数据处理\\GroupMeetingAutoPPT for the active project.\n",
        encoding="utf-8",
    )

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((default_output_root(project) / "reports" / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "active_project_name_references_current" in failed_names


def test_readiness_fails_when_required_active_entry_doc_is_missing(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    (project / "README.md").unlink()

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((default_output_root(project) / "reports" / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "active_project_name_references_current" in failed_names


def test_readiness_fails_when_reviewed_queue_plan_is_older_than_decisions(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    reports = default_output_root(project) / "reports"
    template = reports / "phase1_8_review_decisions_template.csv"
    plan = reports / "phase1_8_reviewed_queue_plan.json"
    os.utime(plan, (1000, 1000))
    os.utime(template, (2000, 2000))

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "reviewed_queue_plan_current" in failed_names


def test_readiness_fails_when_reviewed_queue_input_hashes_do_not_match(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    reports = default_output_root(project) / "reports"
    plan_path = reports / "phase1_8_reviewed_queue_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["input_hashes"]["decisions_sha256"] = "0" * 64
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "reviewed_queue_plan_current" in failed_names


def test_readiness_fails_when_reviewed_queue_has_blocked_approvals(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    reports = default_output_root(project) / "reports"
    plan_path = reports / "phase1_8_reviewed_queue_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["summary"]["skipped_count"] = 0
    plan["summary"]["blocked_count"] = 1
    plan["blocked_items"] = [
        {
            "proposal_id": "P18-001",
            "status": "BLOCKED_HASH_MISMATCH",
            "reason": "source hash mismatch",
        }
    ]
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "reviewed_queue_plan_current" in failed_names


def test_readiness_fails_when_origin_batch_plan_has_blocked_items(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    reports = default_output_root(project) / "reports"
    plan_path = reports / "phase1_7_manifest_runner_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["summary"]["skipped_count"] = 0
    plan["summary"]["blocked_count"] = 1
    plan["blocked_items"] = [{"result_id": "bad", "reason": "source_hash_mismatch"}]
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "origin_batch_dry_run_plan_current" in failed_names


def test_readiness_fails_when_origin_batch_plan_would_launch_origin(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    f_backup = tmp_path / "fake_f_backup"
    _write_minimal_ready_project(project, f_backup)
    reports = default_output_root(project) / "reports"
    plan_path = reports / "phase1_7_manifest_runner_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["summary"]["will_launch_origin"] = True
    plan["execution"]["origin_launch"] = True
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    code = run_readiness(project, ReadinessOptions(expected_phase1_6_count=1, f_drive_backup=f_backup))
    report = json.loads((reports / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 1
    failed_names = {check["name"] for check in report["checks"] if check["status"] == "fail"}
    assert "origin_batch_dry_run_plan_current" in failed_names


def _write_minimal_ready_project(project: Path, f_backup: Path) -> None:
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    package = default_output_root(project) / "phase1_6_origin_results_20260531_041538"
    reports = default_output_root(project) / "reports"
    dashboard = default_output_root(project) / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    f_backup.mkdir(parents=True)
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    _write_index(package / "index.csv", ["hash-a"])
    _write_result_summary(package / "result_summary.json", total=1)
    _write_csv(reports / "phase1_8_manual_review_required_filtered.csv", [{"relative_path": "a.csv"}])
    _write_manual_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx", rows=1)
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    _write_auto_queue(reports / "phase1_8_new_auto_process_queue.json", [{"origin_export_allowed": False, "manual_check_required": True}])
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_current_dashboard(dashboard / "index.md")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    _write_passing_validation_report(reports / "validation_report.md")
    _write_active_entry_docs(project)


def _write_active_entry_docs(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    for name in ["README.md", "PROJECT_STATUS.md", "TASK_BOARD.md", "AGENT_HANDOFF.md"]:
        (project / name).write_text("ResearchDataOriginPipeline current active document\n", encoding="utf-8")
    docs = project / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "REAL_DATA_INTAKE_GUIDE.md").write_text("ResearchDataOriginPipeline intake guide\n", encoding="utf-8")
    (docs / "REAL_DATA_COMPATIBILITY_MATRIX.md").write_text("ResearchDataOriginPipeline compatibility matrix\n", encoding="utf-8")


def _write_index(path: Path, hashes: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_hash"])
        writer.writeheader()
        for source_hash in hashes:
            writer.writerow({"source_hash": source_hash})


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path"])
        writer.writeheader()
        writer.writerows(rows)


def _write_result_summary(path: Path, *, total: int) -> None:
    path.write_text(json.dumps({"total_results": total, "by_type": {"EIS": total}}), encoding="utf-8")


def _write_passing_validation_report(path: Path) -> None:
    path.write_text(
        "# Validation Report\n\n"
        "- Dependency audit: pass\n"
        "- Deferred/reference registry semantics: pass\n"
        "- PPT forbidden paths: pass\n"
        "- Kinetics processor paths: pass\n",
        encoding="utf-8",
    )
    _write_reviewed_queue_artifacts_in_reports(path.parent)
    _write_origin_batch_plan_in_reports(path.parent)


def _write_origin_batch_plan(project: Path, *, total: int = 1) -> None:
    _write_origin_batch_plan_in_reports(default_output_root(project) / "reports", total=total)


def _write_origin_batch_plan_in_reports(reports: Path, *, total: int = 1) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "phase1_7_manifest_runner_plan.json").write_text(
        json.dumps(
            {
                "runner": "origin-batch",
                "summary": {
                    "total_manifest_items": total,
                    "planned_count": 0,
                    "skipped_count": total,
                    "blocked_count": 0,
                    "will_launch_origin": False,
                },
                "execution": {
                    "blocked": False,
                    "origin_launch": False,
                    "reason": "dry_run_only",
                },
                "planned_items": [],
                "skipped_items": [{"result_id": f"item_{index}", "reason": "already_complete"} for index in range(total)],
                "blocked_items": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_reviewed_queue_artifacts(project: Path) -> None:
    _write_reviewed_queue_artifacts_in_reports(default_output_root(project) / "reports")


def _write_reviewed_queue_artifacts_in_reports(reports: Path) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    proposals = [
        {
            "proposal_id": "P18-001",
            "relative_path": "a.csv",
            "source_hash": "hash-a",
            "proposed_data_type": "EIS",
            "proposed_processor": "eis_processor",
            "risk_level": "medium",
            "reason": "fixture",
            "recommended_action": "keep_manual_review",
        }
    ]
    (reports / "phase1_7_new_override_proposals_after_optimization.json").write_text(
        json.dumps({"items": proposals}, ensure_ascii=False),
        encoding="utf-8",
    )
    with (reports / "phase1_8_review_decisions_template.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "proposal_id",
            "relative_path",
            "source_hash",
            "proposed_data_type",
            "proposed_processor",
            "risk_level",
            "reason",
            "recommended_action",
            "user_decision",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({**proposals[0], "user_decision": ""})
    (reports / "phase1_8_reviewed_queue_plan.json").write_text(
        json.dumps(
            {
                "input_hashes": {
                    "proposals_sha256": _sha256(reports / "phase1_7_new_override_proposals_after_optimization.json"),
                    "decisions_sha256": _sha256(reports / "phase1_8_review_decisions_template.csv"),
                },
                "summary": {
                    "total_proposals": 1,
                    "decision_rows": 1,
                    "approved_count": 0,
                    "skipped_count": 1,
                    "blocked_count": 0,
                    "queue_item_count": 0,
                    "will_launch_origin": False,
                    "will_run_process": False,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_current_dashboard(path: Path) -> None:
    path.write_text(
        "# Phase 1.8 Review Dashboard\n\n"
        "- [Current filtered manual-review workbook](../reports/phase1_8_manual_review_required_filtered.xlsx)\n"
        "- [New AUTO_PROCESS dry-run plan](../reports/phase1_8_new_auto_process_plan.md)\n",
        encoding="utf-8",
    )


def _write_auto_queue(path: Path, items: list[dict]) -> None:
    normalized = []
    for item in items:
        output = dict(item)
        output.setdefault("promoted_by_phase", "phase1_8_auto_queue_dry_run")
        output.setdefault("queue_note", "New AUTO_PROCESS candidate not represented in Phase 1.6; no processing has been run by auto-queue.")
        normalized.append(output)
    path.write_text(json.dumps({"items": normalized}, ensure_ascii=False), encoding="utf-8")


def _write_manual_review_xlsx(path: Path, *, rows: int) -> None:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    summary.append(["metric", "value"])
    summary.append(["rows_requiring_user_review", rows])
    review = workbook.create_sheet("Review")
    review.append(["relative_path"])
    for index in range(rows):
        review.append([f"file_{index}.csv"])
    workbook.save(path)
