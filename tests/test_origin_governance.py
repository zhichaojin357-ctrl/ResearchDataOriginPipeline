from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from src.core.origin_governance import (
    REQUIRED_JOURNAL_INDEX_COLUMNS,
    _package_import_status,
    run_origin_governance,
)
from src.core.validate import validate
from src.core.project import default_output_root


def test_origin_governance_governance_generates_skill_snapshot_and_journal_index(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    package = default_output_root(project) / "locked_origin_results_20260531_041538"
    skill_dir = tmp_path / "origin-plotting"
    raw_source = project / "workspace_data" / "LL_detection_copy_20260530" / "source.csv"
    raw_source.parent.mkdir(parents=True)
    raw_source.write_text("x,y\n1,2\n", encoding="utf-8")
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Graph4\nY-axis title size 36\n", encoding="utf-8")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "helper.ps1").write_text("# helper\n", encoding="utf-8")
    package.mkdir(parents=True)
    _write_package_index(package / "index.csv")

    outputs = run_origin_governance(project, skill_dir=skill_dir, package_dir=package)

    assert outputs.snapshot_md.exists()
    assert outputs.snapshot_json.exists()
    assert outputs.journal_index_csv.exists()
    snapshot = json.loads(outputs.snapshot_json.read_text(encoding="utf-8"))
    assert snapshot["skill_sha256"] == outputs.skill_sha256
    with outputs.journal_index_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert REQUIRED_JOURNAL_INDEX_COLUMNS.issubset(rows[0])
    assert rows[0]["plotting_skill_sha256"] == outputs.skill_sha256
    assert rows[0]["plot_style_profile"] == "Origin Graph4 cached style"
    assert rows[0]["y_tick_policy"] == "show_y_axis_ticks_and_numeric_values"
    assert rows[0]["plot_primitive"] == "line+symbol"
    assert rows[0]["y_axis_visible"] == "true"
    assert rows[0]["y_ticks_visible"] == "true"
    assert rows[0]["y_tick_values_visible"] == "true"
    assert rows[0]["marker_policy"] == "markers_preferred"
    assert rows[0]["plot_policy_reason"]
    assert raw_source.read_text(encoding="utf-8") == "x,y\n1,2\n"


def test_validate_checks_origin_governance_governance_files_when_present(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    _write_minimal_validate_project(project)
    package = default_output_root(project) / "locked_origin_results_20260531_041538"
    skill_dir = tmp_path / "origin-plotting"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Graph4\n", encoding="utf-8")
    package.mkdir(parents=True)
    _write_package_index(package / "index.csv")
    run_origin_governance(project, skill_dir=skill_dir, package_dir=package)

    validate(project)
    report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")
    assert "- Origin governance plotting governance files: pass" in report
    assert "- Origin governance plotting skill SHA256 recorded: pass" in report
    assert "- Origin governance journal-ready index columns: pass" in report
    assert "- Origin governance journal-ready index skill hash: pass" in report
    assert "- Origin governance journal-ready index policy values: pass" in report


def test_validate_does_not_require_generated_origin_governance_outputs_for_docs_only_snapshot(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    _write_minimal_validate_project(project)
    docs = project / "docs" / "reports"
    docs.mkdir(parents=True)
    (docs / "origin_plotting_skill_snapshot.md").write_text(
        "# Historical Origin Plotting Skill Snapshot\n",
        encoding="utf-8",
    )

    validate(project)
    report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")

    assert "- Origin governance plotting governance files: not checked (no generated output artifacts)" in report
    assert "missing Origin governance plotting governance files" not in report


def test_validate_rejects_invalid_origin_governance_journal_policy_values(tmp_path: Path):
    project = tmp_path / "ResearchDataOriginPipeline"
    _write_minimal_validate_project(project)
    package = default_output_root(project) / "locked_origin_results_20260531_041538"
    skill_dir = tmp_path / "origin-plotting"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("Graph4\n", encoding="utf-8")
    package.mkdir(parents=True)
    _write_package_index(package / "index.csv")
    run_origin_governance(project, skill_dir=skill_dir, package_dir=package)

    journal_csv = default_output_root(project) / "reports" / "journal_ready_index.csv"
    with journal_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0].keys())
    rows[0]["y_axis_visible"] = "maybe"
    rows[0]["marker_policy"] = "unexpected_marker_mode"
    with journal_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    exit_code = validate(project)
    report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")

    assert exit_code == 1
    assert "- Origin governance journal-ready index policy values: fail" in report
    assert "unexpected_marker_mode" in report


def test_origin_governance_cli_help_documents_governance_command(project_root: Path):
    result = subprocess.run(
        [sys.executable, "run.py", "origin-governance", "--help"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0
    assert "--skill-dir" in result.stdout
    assert "--package-dir" in result.stdout


def test_reference_and_diagnostic_package_probe_does_not_import_module(monkeypatch):
    imported: list[str] = []

    monkeypatch.setattr(
        "src.core.origin_governance.importlib.import_module",
        lambda module: imported.append(module),
    )
    monkeypatch.setattr(
        "src.core.origin_governance.importlib.util.find_spec",
        lambda module: object(),
    )

    result = _package_import_status(
        "pyimpspec",
        "pyimpspec",
        allow_import=False,
    )

    assert result["import_status"] == "available_not_imported"
    assert result["smoke_status"] == "not_run_by_policy"
    assert imported == []


def _write_package_index(path: Path) -> None:
    fields = [
        "result_id",
        "queue_id",
        "data_type",
        "source_file",
        "source_hash",
        "processed_csv",
        "metadata",
        "origin_file",
        "figure_tif",
        "preview_png",
        "origin_status",
        "qc_status",
        "manual_check_required",
        "forbidden_claims",
        "notes",
    ]
    row = {
        "result_id": "EIS_sample",
        "queue_id": "queue-1",
        "data_type": "EIS",
        "source_file": "selected_source_data/EIS/sample.csv",
        "source_hash": "a" * 64,
        "processed_csv": "processed_tables/EIS/sample.csv",
        "metadata": "metadata/EIS/sample_metadata.json",
        "origin_file": "origin_files/EIS/sample.opju",
        "figure_tif": "figures_tif/EIS/sample.tif",
        "preview_png": "previews/origin/EIS/sample.png",
        "origin_status": "success",
        "qc_status": "QC_PASS",
        "manual_check_required": "true",
        "forbidden_claims": "do not infer mechanism automatically",
        "notes": "copied_package",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def _write_minimal_validate_project(project: Path) -> None:
    for rel in [
        "config",
        "output/origin_files",
        "output/figures_tif",
        "output/figures_preview",
        "output/processed_data",
        "output/metadata",
        "output/reports",
        "output/origin_jobs",
        "output/review_dashboard",
        "output/unclassified",
        "src",
    ]:
        (project / rel).mkdir(parents=True, exist_ok=True)
    for name in ["default.yaml", "plot_style.yaml", "sample_registry.yaml", "manual_overrides.yaml"]:
        (project / "config" / name).write_text("{}\n", encoding="utf-8")
    (project / "config" / "plot_style.yaml").write_text(
        'format: "tif"\n'
        "dpi: 600\n"
        'default_graph_page: "Graph4"\n'
        'automation_entrypoint: "Origin.Application"\n'
        'avoid_entrypoint: "Origin.ApplicationSI"\n'
        "axis_title_size: 36\n"
        "x_tick_label_size: 28\n"
        "y_tick_label_size: 36\n"
        "legend_font_size: 26\n"
        "annotation_font_size: 26\n"
        "font_bold: true\n"
        "Export PNG preview and visually inspect\n"
        "explicit legend rows\n"
        "line_width: 3\n"
        "axis_line_width: 3\n",
        encoding="utf-8",
    )
    (project / "config" / "claim_policy.yaml").write_text(
        json.dumps({"forbidden_claims": ["do not infer mechanism automatically"]}),
        encoding="utf-8",
    )
    entries = []
    supported = [
        "XRD",
        "UV-vis DRS",
        "photocurrent",
        "photocurrent_response",
        "PL",
        "FTIR",
        "Raman",
        "BET",
        "EPR",
        "Mott-Schottky",
        "XPS",
        "reaction_condition_screening",
        "HPLC/LC exported data",
        "EIS",
    ]
    for data_type in supported:
        entries.append(
            {
                "folder_name": data_type,
                "inferred_data_type": data_type,
                "supported_in_pipeline": True,
                "selected_processor": "table",
                "special_handling": "auto",
            }
        )
    for folder, data_type in [
        ("SEM", "SEM_image_data"),
        ("TEM", "TEM_image_data"),
        ("鏍哥", "NMR"),
        ("璐ㄨ氨", "MS"),
        ("鍔ㄥ姏瀛?", "reference_literature"),
    ]:
        entries.append(
            {
                "folder_name": folder,
                "inferred_data_type": data_type,
                "supported_in_pipeline": False,
                "selected_processor": "none",
                "special_handling": "scan_only",
            }
        )
    (project / "config" / "processor_registry.yaml").write_text(
        json.dumps(
            {
                "required_fields": [
                    "folder_name",
                    "inferred_data_type",
                    "supported_in_pipeline",
                    "selected_processor",
                    "special_handling",
                ],
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )
