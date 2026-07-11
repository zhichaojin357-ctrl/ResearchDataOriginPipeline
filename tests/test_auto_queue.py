from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.auto_queue import AutoQueueOptions, plan_auto_queue, run_auto_queue
from src.core.project import default_output_root


def _project_root(tmp_path: Path) -> Path:
    project = tmp_path / "ResearchDataOriginPipeline"
    project.mkdir(parents=True, exist_ok=True)
    return project


def test_auto_queue_excludes_locked_result_hash_and_accepts_new_auto_process(tmp_path: Path):
    project = _project_root(tmp_path)
    workspace = project / "workspace"
    reports = default_output_root(project) / "reports"
    package = default_output_root(project) / "locked_origin_results_20260531_041538"
    reports.mkdir(parents=True)
    package.mkdir(parents=True)
    old_source = _write(workspace / "EIS" / "old.csv", "x,y\n1,2\n")
    new_source = _write(workspace / "EIS" / "new.csv", "x,y\n3,4\n")
    queue = {
        "items": [
            _queue_item("EIS/old.csv", _sha256(old_source)),
            _queue_item("EIS/new.csv", _sha256(new_source)),
        ]
    }
    queue_path = reports / "processing_queue.json"
    queue_path.write_text(json.dumps(queue), encoding="utf-8")
    with (package / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_hash"])
        writer.writeheader()
        writer.writerow({"source_hash": _sha256(old_source)})

    plan = plan_auto_queue(
        project,
        AutoQueueOptions(queue=queue_path, workspace_root=workspace, processed_index=package / "index.csv"),
    )

    assert plan["summary"]["accepted_count"] == 1
    assert plan["summary"]["skipped_count"] == 1
    assert plan["accepted_items"][0]["relative_path"] == "EIS/new.csv"
    assert plan["accepted_items"][0]["origin_export_allowed"] is False
    assert plan["skipped_items"][0]["status"] == "SKIPPED_LOCKED_RESULT_ALREADY_PROCESSED"


def test_auto_queue_blocks_hash_mismatch_and_path_traversal(tmp_path: Path):
    project = _project_root(tmp_path)
    workspace = project / "workspace"
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    source = _write(workspace / "EIS" / "new.csv", "x,y\n3,4\n")
    queue = {
        "items": [
            _queue_item("EIS/new.csv", "0" * 64),
            _queue_item("../outside.csv", _sha256(source)),
        ]
    }
    queue_path = reports / "processing_queue.json"
    queue_path.write_text(json.dumps(queue), encoding="utf-8")

    plan = plan_auto_queue(project, AutoQueueOptions(queue=queue_path, workspace_root=workspace))

    assert plan["summary"]["accepted_count"] == 0
    statuses = {item["status"] for item in plan["blocked_items"]}
    assert "BLOCKED_HASH_MISMATCH" in statuses
    assert "BLOCKED_PATH_TRAVERSAL" in statuses
    assert run_auto_queue(project, AutoQueueOptions(queue=queue_path, workspace_root=workspace)) == 1


def test_auto_queue_returns_zero_when_candidates_are_only_normally_skipped(tmp_path: Path):
    project = _project_root(tmp_path)
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    item = _queue_item("EIS/not_selected.csv", "a" * 64)
    item["decision"] = "MANUAL_REVIEW"
    queue_path = reports / "processing_queue.json"
    queue_path.write_text(json.dumps({"items": [item]}), encoding="utf-8")

    code = run_auto_queue(project, AutoQueueOptions(queue=queue_path, workspace_root=project / "workspace"))
    plan = json.loads((reports / "auto_process_plan.json").read_text(encoding="utf-8"))

    assert code == 0
    assert plan["summary"]["skipped_count"] == 1
    assert plan["summary"]["blocked_count"] == 0


def test_auto_queue_blocks_forbidden_type_variants(tmp_path: Path):
    project = _project_root(tmp_path)
    workspace = project / "workspace"
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    sem_source = _write(workspace / "SEM" / "image.csv", "x,y\n1,2\n")
    mixed_source = _write(workspace / "mixed" / "blocked.csv", "x,y\n3,4\n")
    kinetic_source = _write(workspace / "kinetic" / "blocked.csv", "x,y\n5,6\n")
    queue_path = reports / "processing_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    _queue_item("SEM/image.csv", _sha256(sem_source), data_type="sem_image_data"),
                    _queue_item("mixed/blocked.csv", _sha256(mixed_source), data_type="SEM/TEM/NMR/MS"),
                    _queue_item("kinetic/blocked.csv", _sha256(kinetic_source), data_type="动力学"),
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    plan = plan_auto_queue(project, AutoQueueOptions(queue=queue_path, workspace_root=workspace))

    assert plan["summary"]["accepted_count"] == 0
    assert plan["summary"]["blocked_count"] == 3
    assert {item["status"] for item in plan["blocked_items"]} == {"BLOCKED_FORBIDDEN_TYPE"}


def test_auto_queue_writes_plan_and_never_requests_origin_or_process(tmp_path: Path):
    project = _project_root(tmp_path)
    workspace = project / "workspace"
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    source = _write(workspace / "EPR" / "sample.txt", "1,2\n3,4\n")
    queue_path = reports / "processing_queue.json"
    queue_path.write_text(json.dumps({"items": [_queue_item("EPR/sample.txt", _sha256(source), data_type="EPR")]}), encoding="utf-8")

    code = run_auto_queue(project, AutoQueueOptions(queue=queue_path, workspace_root=workspace))
    plan = json.loads((reports / "auto_process_plan.json").read_text(encoding="utf-8"))
    output_queue = json.loads((reports / "auto_process_queue.json").read_text(encoding="utf-8"))

    assert code == 0
    assert plan["summary"]["will_launch_origin"] is False
    assert plan["summary"]["will_run_process"] is False
    assert output_queue["items"][0]["origin_export_allowed"] is False
    report_md = (reports / "auto_process_plan.md").read_text(encoding="utf-8")
    assert str(project) not in report_md
    assert "- Candidate queue: `output/reports/auto_process_queue.json`" in report_md


def test_auto_queue_rejects_report_outside_output_or_docs(tmp_path: Path):
    project = _project_root(tmp_path)
    workspace = project / "workspace"
    reports = default_output_root(project) / "reports"
    reports.mkdir(parents=True)
    source = _write(workspace / "EIS" / "new.csv", "x,y\n3,4\n")
    queue_path = reports / "processing_queue.json"
    queue_path.write_text(json.dumps({"items": [_queue_item("EIS/new.csv", _sha256(source))]}), encoding="utf-8")

    with pytest.raises(ValueError):
        run_auto_queue(
            project,
            AutoQueueOptions(queue=queue_path, workspace_root=workspace, report_json=tmp_path / "unsafe.json"),
        )


def test_auto_queue_cli_reports_invalid_queue_shape_without_traceback(tmp_path: Path, project_root: Path):
    queue_path = tmp_path / "bad_processing_queue.json"
    queue_path.write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "run.py",
            "auto-queue",
            "--queue",
            str(queue_path),
            "--workspace-root",
            str(tmp_path / "workspace"),
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "auto-queue JSON must be an object with an items list" in result.stderr
    assert "Traceback" not in result.stderr


def test_auto_queue_cli_reports_non_object_queue_item_without_traceback(tmp_path: Path, project_root: Path):
    queue_path = tmp_path / "bad_processing_queue_item.json"
    queue_path.write_text('{"items": ["not-an-object"]}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "run.py",
            "auto-queue",
            "--queue",
            str(queue_path),
            "--workspace-root",
            str(tmp_path / "workspace"),
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "auto-queue JSON item 1 must be an object" in result.stderr
    assert "Traceback" not in result.stderr


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
