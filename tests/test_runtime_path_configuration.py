from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import patch

from src.core.auto_queue import AutoQueueOptions, plan_auto_queue
from src.core.project import default_output_root, load_project_config
from src.core.readiness import ReadinessOptions, run_readiness
from src.core.runtime_paths import create_run_output_layout
from src.core.runtime_paths import resolve_origin_helper, resolve_origin_reference_pattern, resolve_output_root, resolve_phase1_6_index
from src.core.xps_heterojunction import discover_default_xps_sample_files
from src.origin.adapter import build_origin_plot_job


def test_phase16_index_auto_discovers_latest_package(tmp_path: Path):
    output_root = default_output_root(tmp_path)
    older = output_root / "phase1_6_origin_results_20260101_000000"
    newer = output_root / "phase1_6_origin_results_20260201_000000"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "index.csv").write_text("source_hash\nold\n", encoding="utf-8")
    (newer / "index.csv").write_text("source_hash\nnew\n", encoding="utf-8")

    assert resolve_phase1_6_index(tmp_path) == newer / "index.csv"


def test_default_output_root_is_workspace_sibling_output_folder(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    project.mkdir()

    assert resolve_output_root(project) == default_output_root(project)


def test_create_run_output_layout_defaults_to_workspace_sibling_output_folder(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    project.mkdir()

    layout = create_run_output_layout(
        project,
        scope="default output",
        command="process",
        mode="no_origin",
        timestamp="20260611_160000",
        no_origin=True,
        dry_run=False,
    )

    assert layout.root == default_output_root(project) / "runs" / "20260611_160000_default_output"
    assert layout.reports.is_dir()
    assert not (project / "output").exists()
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    assert manifest["output_root"] == "output/20260611_160000_default_output"


def test_output_root_resolution_priority_uses_explicit_then_local_then_env(tmp_path: Path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    local_root = tmp_path.parent / f"{tmp_path.name}_local_output"
    env_root = tmp_path.parent / f"{tmp_path.name}_env_output"
    explicit_root = tmp_path.parent / f"{tmp_path.name}_explicit_output"
    (config / "default.yaml").write_text("paths:\n  output_root: output/default-root\n", encoding="utf-8")
    (config / "local.yaml").write_text(f"paths:\n  output_root: {local_root}\n", encoding="utf-8")
    monkeypatch.setenv("RESEARCH_PIPELINE_OUTPUT_ROOT", str(env_root))

    assert resolve_output_root(tmp_path, explicit=explicit_root) == explicit_root
    assert resolve_output_root(tmp_path) == local_root

    (config / "local.yaml").unlink()
    assert resolve_output_root(tmp_path) == env_root


def test_create_run_output_layout_uses_configured_external_output_root(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    external_root = tmp_path.parent / f"{tmp_path.name}_external_output"
    (config / "default.yaml").write_text(f"paths:\n  output_root: {external_root}\n", encoding="utf-8")

    layout = create_run_output_layout(
        tmp_path,
        scope="external pilot",
        command="process",
        mode="no_origin",
        timestamp="20260604_120000",
        no_origin=True,
        dry_run=False,
    )

    assert layout.root == external_root / "runs" / "20260604_120000_external_pilot"
    assert layout.reports.is_dir()
    assert not (tmp_path / "output").exists()
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    assert manifest["output_root"] == "output/20260604_120000_external_pilot"
    assert not Path(manifest["output_root"]).is_absolute()


def test_auto_queue_uses_env_phase16_package_when_processed_index_not_explicit(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = _write(workspace / "EIS" / "old.csv", "x,y\n1,2\n")
    source_hash = _sha256(source)
    queue_path = tmp_path / "output" / "reports" / "processing_queue.json"
    queue_path.parent.mkdir(parents=True)
    queue_path.write_text(
        json.dumps({"items": [_queue_item("EIS/old.csv", source_hash)]}),
        encoding="utf-8",
    )
    package = tmp_path / "custom_package"
    package.mkdir()
    with (package / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_hash"])
        writer.writeheader()
        writer.writerow({"source_hash": source_hash})
    monkeypatch.setenv("RESEARCHDATAORIGINPIPELINE_PHASE1_6_PACKAGE", str(package))

    plan = plan_auto_queue(tmp_path, AutoQueueOptions(queue=queue_path, workspace_root=workspace))

    assert plan["summary"]["skipped_count"] == 1
    assert plan["processed_index"] == "custom_package/index.csv"
    assert not Path(plan["processed_index"]).is_absolute()


def test_readiness_can_skip_legacy_project_path_check(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    legacy = tmp_path / "GroupMeetingAutoPPT"
    legacy.mkdir()
    _write_minimal_readiness_project(project)

    code = run_readiness(
        project,
        ReadinessOptions(
            expected_phase1_6_count=1,
            f_drive_backup=None,
            check_legacy_project_path=False,
        ),
    )
    report = json.loads((resolve_output_root(project) / "reports" / "readiness_report.json").read_text(encoding="utf-8"))

    assert code == 0
    assert "old_project_path_absent" not in {check["name"] for check in report["checks"]}


def test_origin_helper_script_can_be_configured(tmp_path: Path):
    helper = tmp_path / "tools" / "origin_plot_from_template.ps1"
    helper.parent.mkdir()
    helper.write_text("# helper\n", encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    (config / "plot_style.yaml").write_text(
        "\n".join(
            [
                "line_width: 3",
                "axis_line_width: 3",
                "origin_template:",
                f'  helper_script: "{helper}"',
                '  default_graph_page: "Graph4"',
            ]
        ),
        encoding="utf-8",
    )
    data = tmp_path / "processed.csv"
    data.write_text("x,y\n0,1\n", encoding="utf-8")

    job = build_origin_plot_job(tmp_path, "configured_helper", data, "x", "y", "XRD")

    assert job.helper_script == helper


def test_local_config_overlays_default_and_origin_paths(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "default.yaml").write_text("paths:\n  workspace_root: workspace_data/default\n", encoding="utf-8")
    (config / "local.yaml").write_text(
        "paths:\n  workspace_root: workspace_data/local\norigin_template:\n  helper_script: tools/helper.ps1\n  reference_search_pattern: refs/*.opju\n",
        encoding="utf-8",
    )

    loaded = load_project_config(tmp_path, Path("config/default.yaml"))

    assert loaded["paths"]["workspace_root"] == "workspace_data/local"
    assert resolve_origin_helper(tmp_path) == tmp_path / "tools" / "helper.ps1"
    assert resolve_origin_reference_pattern(tmp_path) == "refs/*.opju"


def test_xps_default_discovery_reads_configured_sample_dirs(tmp_path: Path):
    bobc_dir = tmp_path / "xps" / "bobc"
    cwo_dir = tmp_path / "xps" / "cwo"
    bc_dir = tmp_path / "xps" / "bc"
    for directory in (bobc_dir, cwo_dir, bc_dir):
        directory.mkdir(parents=True)
        _write_minimal_xlsx(directory / "fit.xlsx")
    config = tmp_path / "config"
    config.mkdir()
    (config / "default.yaml").write_text(
        "\n".join(
            [
                "xps_heterojunction:",
                f"  bobc_input_dir: {bobc_dir}",
                f"  cwo_input_dir: {cwo_dir}",
                f"  bc_input_dir: {bc_dir}",
            ]
        ),
        encoding="utf-8",
    )

    sample_files, notes = discover_default_xps_sample_files(tmp_path)

    assert {sample: [path.name for path in paths] for sample, paths in sample_files.items()} == {
        "BOBC": ["fit.xlsx"],
        "CWO": ["fit.xlsx"],
        "BC": ["fit.xlsx"],
    }
    assert notes == []


def test_xps_in_situ_quality_check_skips_dpi_when_pillow_missing(tmp_path: Path):
    from src.core import xps_in_situ

    def fake_import(name, *args, **kwargs):
        if name == "PIL":
            raise ImportError("No module named PIL")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    with patch("builtins.__import__", side_effect=fake_import):
        result = xps_in_situ._quality_checks(tmp_path, {}, {"ok": True})

    assert result["tif_dpi"] == {}
    assert result["warnings"] == ["Pillow is not installed; skipped TIF DPI quality checks."]


def test_xps_in_situ_quality_check_uses_output_relative_file_keys(tmp_path: Path):
    from src.core import xps_in_situ

    for name in ("xps_in_situ_combined.tif", "xps_in_situ_combined.png", "xps_in_situ_combined.pdf"):
        (tmp_path / name).write_bytes(b"artifact")

    result = xps_in_situ._quality_checks(tmp_path, {}, {"ok": True})
    rendered = json.dumps(result, ensure_ascii=False)

    assert str(tmp_path) not in rendered
    assert "xps_in_situ_combined.tif" in result["files_saved"]


def test_phase1_7_baseline_uses_current_python_executable(tmp_path: Path):
    from src.core.phase1_7 import write_baseline_report

    write_baseline_report(tmp_path, "sha", {"pytest": {"exit_code": 0, "summary": f"ok {tmp_path}"}})
    report = (tmp_path / "docs" / "agent_reports" / "phase1_7_baseline.md").read_text(encoding="utf-8")

    assert "- Current Python interpreter: `external/python.exe`" in report
    assert str(tmp_path) not in report


def _queue_item(relative_path: str, source_hash: str, *, data_type: str = "EIS") -> dict:
    return {
        "queue_id": source_hash[:16],
        "relative_path": relative_path,
        "source_hash": source_hash,
        "data_type": data_type,
        "selected_processor": f"{data_type.casefold().replace('-', '_')}_processor",
        "decision": "AUTO_PROCESS",
        "confidence_score": 0.85,
        "validity_score": 1.0,
    }


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_minimal_readiness_project(project: Path) -> None:
    workspace = project / "workspace_data" / "LL_detection_copy_20260530"
    output_root = default_output_root(project)
    package = output_root / "phase1_6_origin_results_20260531_041538"
    reports = output_root / "reports"
    dashboard = output_root / "review_dashboard"
    docs = project / "docs" / "agent_reports"
    workspace.mkdir(parents=True)
    package.mkdir(parents=True)
    reports.mkdir(parents=True)
    dashboard.mkdir(parents=True)
    docs.mkdir(parents=True)
    with (package / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_hash"])
        writer.writeheader()
        writer.writerow({"source_hash": "hash-a"})
    (package / "result_summary.json").write_text(
        json.dumps({"total_results": 1, "by_type": {"EIS": 1}}),
        encoding="utf-8",
    )
    (reports / "phase1_8_manual_review_required_filtered.csv").write_text("relative_path\na.csv\n", encoding="utf-8")
    _write_review_xlsx(reports / "phase1_8_manual_review_required_filtered.xlsx")
    (reports / "phase1_8_manual_review_required_filtered_report.md").write_text("Rows requiring user review: 1\n", encoding="utf-8")
    (reports / "phase1_8_new_auto_process_plan.json").write_text(
        json.dumps({"summary": {"accepted_count": 1, "blocked_count": 0, "will_run_process": False, "will_launch_origin": False}}),
        encoding="utf-8",
    )
    (reports / "phase1_8_new_auto_process_queue.json").write_text(
        json.dumps({"items": [{"origin_export_allowed": False, "manual_check_required": True, "promoted_by_phase": "phase1_8_auto_queue_dry_run", "queue_note": "New AUTO_PROCESS candidate not represented in Phase 1.6; no processing has been run by auto-queue."}]}),
        encoding="utf-8",
    )
    (reports / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    (docs / "phase1_8_final_summary.md").write_text("Current manual-review workbook\n", encoding="utf-8")
    (reports / "validation_report.md").write_text(
        "# Validation Report\n\n"
        "- Deferred/reference registry semantics: pass\n"
        "- PPT forbidden paths: pass\n"
        "- Kinetics processor paths: pass\n",
        encoding="utf-8",
    )
    (reports / "phase1_7_manifest_runner_plan.json").write_text(
        json.dumps(
            {
                "summary": {"total_manifest_items": 1, "planned_count": 0, "skipped_count": 1, "blocked_count": 0, "will_launch_origin": False},
                "execution": {"blocked": False, "origin_launch": False},
                "skipped_items": [{"result_id": "one"}],
                "blocked_items": [],
            }
        ),
        encoding="utf-8",
    )
    (reports / "phase1_7_new_override_proposals_after_optimization.json").write_text(json.dumps({"items": [], "count": 0}), encoding="utf-8")
    (reports / "phase1_8_review_decisions_template.csv").write_text("proposal_id\n", encoding="utf-8")
    (reports / "phase1_8_reviewed_queue_plan.json").write_text(
        json.dumps(
            {
                "input_hashes": {
                    "proposals_sha256": _sha256(reports / "phase1_7_new_override_proposals_after_optimization.json"),
                    "decisions_sha256": _sha256(reports / "phase1_8_review_decisions_template.csv"),
                },
                "summary": {"total_proposals": 0, "decision_rows": 0, "approved_count": 0, "skipped_count": 0, "blocked_count": 0, "queue_item_count": 0, "will_launch_origin": False, "will_run_process": False},
            }
        ),
        encoding="utf-8",
    )
    for name in ["README.md", "PROJECT_STATUS.md", "TASK_BOARD.md", "AGENT_HANDOFF.md"]:
        (project / name).write_text("ResearchDataOriginPipeline\n", encoding="utf-8")
    docs_root = project / "docs"
    (docs_root / "REAL_DATA_INTAKE_GUIDE.md").write_text("ResearchDataOriginPipeline\n", encoding="utf-8")
    (docs_root / "REAL_DATA_COMPATIBILITY_MATRIX.md").write_text("ResearchDataOriginPipeline\n", encoding="utf-8")
    dashboard.joinpath("index.md").write_text(
        "[Current](../reports/phase1_8_manual_review_required_filtered.xlsx)\n"
        "[Plan](../reports/phase1_8_new_auto_process_plan.md)\n",
        encoding="utf-8",
    )


def _write_review_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    review = workbook.active
    review.title = "Review"
    review.append(["relative_path"])
    review.append(["a.csv"])
    workbook.save(path)


def _write_minimal_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Binding Energy", "Intensity"])
    sheet.append([1, 2])
    workbook.save(path)
