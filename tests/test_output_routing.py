from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from src.core.auto_queue import AutoQueueOptions, run_auto_queue
from src.core.project import default_output_root, output_dir
from src.core.process import ProcessOptions, run_process
from src.core.reviewed_queue import ReviewedQueueOptions, run_reviewed_queue
from src.core.runtime_paths import create_run_output_layout
from src.core.triage import TriageOptions, run_triage
from src.core.origin_batch import OriginBatchOptions, run_origin_batch
from src.core.metadata import file_hash
from src.origin.adapter import build_origin_plot_job, export_plot


def test_create_run_output_layout_creates_standard_dirs_and_manifest(tmp_path: Path):
    layout = create_run_output_layout(
        tmp_path,
        scope="process no origin",
        command="process",
        mode="no_origin",
        input_paths=[tmp_path / "input" / "raw_data"],
        timestamp="20260603_120000",
        no_origin=True,
        dry_run=False,
    )

    assert layout.run_id == "20260603_120000_process_no_origin"
    assert layout.root == default_output_root(tmp_path) / "runs" / "20260603_120000_process_no_origin"
    assert layout.processed_data.is_dir()
    assert layout.metadata.is_dir()
    assert layout.origin_files.is_dir()
    assert layout.figures_tif.is_dir()
    assert layout.figures_preview.is_dir()
    assert layout.reports.is_dir()
    assert layout.logs.is_dir()

    manifest = json.loads((layout.root / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == layout.run_id
    assert manifest["scope"] == "process_no_origin"
    assert manifest["command"] == "process"
    assert manifest["mode"] == "no_origin"
    assert manifest["no_origin"] is True
    assert manifest["dry_run"] is False
    assert manifest["compatibility_mode"] == "run_scoped"
    assert manifest["output_root"] == "output/20260603_120000_process_no_origin"
    assert manifest["produced_artifact_directories"]["processed_data"] == "output/20260603_120000_process_no_origin/processed_data"
    assert manifest["input_paths"] == ["input/raw_data"]
    assert not Path(manifest["output_root"]).is_absolute()


def test_output_dir_allows_explicit_external_output_root(tmp_path: Path):
    external_root = tmp_path.parent / f"{tmp_path.name}_external_output"

    reports = output_dir(tmp_path, "reports", output_root=external_root)

    assert reports == external_root / "reports"
    assert reports.is_dir()
    assert not (tmp_path / "output").exists()


def test_run_process_can_route_no_origin_artifacts_into_run_root(tmp_path: Path):
    source = tmp_path / "input" / "raw_data" / "XRD" / "sample.csv"
    source.parent.mkdir(parents=True)
    source.write_text("2theta,intensity\n10,1\n20,4\n30,2\n", encoding="utf-8")
    layout = create_run_output_layout(
        tmp_path,
        scope="process_no_origin",
        command="process",
        mode="no_origin",
        input_paths=[tmp_path / "input" / "raw_data"],
        timestamp="20260603_120001",
        no_origin=True,
        dry_run=False,
    )

    with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
        code = run_process(
            tmp_path,
            tmp_path / "input" / "raw_data",
            ProcessOptions(no_origin=True, force=True, output_root=layout.root),
        )

    assert code == 0
    metadata_files = list(layout.metadata.rglob("metadata.json"))
    processed_files = list(layout.processed_data.rglob("*_processed.csv"))
    assert len(metadata_files) == 1
    assert len(processed_files) == 1
    assert (layout.reports / "processing_report.md").exists()
    assert (layout.reports / "processing_summary.json").exists()
    assert not (tmp_path / "output" / "metadata").exists()
    assert not (tmp_path / "output" / "processed_data").exists()

    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["processing_status"] == "processed_no_origin"
    assert metadata["run_output_root"] == "output/runs/20260603_120001_process_no_origin"
    assert metadata["processed_data"].startswith("output/runs/20260603_120001_process_no_origin/processed_data/")
    assert not Path(metadata["processed_data"]).is_absolute()


def test_run_triage_can_route_reports_into_run_root(tmp_path: Path):
    source = tmp_path / "input" / "raw_data" / "XRD" / "sample.csv"
    source.parent.mkdir(parents=True)
    source.write_text("2theta,intensity\n10,1\n20,4\n30,2\n40,3\n", encoding="utf-8")
    layout = create_run_output_layout(
        tmp_path,
        scope="triage",
        command="triage",
        mode="dry_run_false",
        input_paths=[tmp_path / "input" / "raw_data"],
        timestamp="20260603_120002",
        dry_run=False,
    )

    result = run_triage(
        tmp_path,
        tmp_path / "input" / "raw_data",
        TriageOptions(force_refresh=True, output_root=layout.root),
    )

    assert result["summary"]["total_files"] == 1
    assert (layout.reports / "data_triage_manifest.json").exists()
    assert (layout.reports / "processing_queue.json").exists()
    assert (layout.reports / "triage_index.md").exists()
    assert not (tmp_path / "output" / "reports").exists()
    assert not (tmp_path / "output" / "review_dashboard").exists()


def test_process_auto_select_uses_same_output_root_for_triage_queue(tmp_path: Path):
    source = tmp_path / "input" / "raw_data" / "XRD" / "sample.csv"
    source.parent.mkdir(parents=True)
    source.write_text("2theta,intensity\n10,1\n20,4\n30,2\n40,3\n", encoding="utf-8")
    layout = create_run_output_layout(
        tmp_path,
        scope="process_auto_select",
        command="process",
        mode="no_origin",
        input_paths=[tmp_path / "input" / "raw_data"],
        timestamp="20260603_120002_auto",
        no_origin=True,
        dry_run=False,
    )

    with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
        code = run_process(
            tmp_path,
            tmp_path / "input" / "raw_data",
            ProcessOptions(auto_select=True, force=True, output_root=layout.root),
        )

    assert code == 0
    assert (layout.reports / "processing_queue.json").exists()
    assert (layout.reports / "processing_report.json").exists()
    assert not (tmp_path / "output" / "reports" / "processing_queue.json").exists()


def test_auto_queue_can_route_reports_into_run_root_without_agent_report(tmp_path: Path):
    source = tmp_path / "input" / "raw_data" / "XRD" / "sample.csv"
    source.parent.mkdir(parents=True)
    source.write_text("2theta,intensity\n10,1\n20,4\n30,2\n40,3\n", encoding="utf-8")
    layout = create_run_output_layout(
        tmp_path,
        scope="auto_queue",
        command="auto-queue",
        mode="dry_run",
        input_paths=[source],
        timestamp="20260603_120003",
        dry_run=True,
    )
    queue_path = layout.reports / "processing_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "queue_id": "q1",
                        "relative_path": "input/raw_data/XRD/sample.csv",
                        "source_hash": file_hash(source),
                        "data_type": "XRD",
                        "decision": "AUTO_PROCESS",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    code = run_auto_queue(
        tmp_path,
        AutoQueueOptions(
            queue=queue_path,
            workspace_root=tmp_path,
            processed_index=tmp_path / "missing_locked_result.csv",
            output_root=layout.root,
        ),
    )

    assert code == 0
    assert (layout.reports / "auto_process_plan.json").exists()
    assert (layout.reports / "auto_process_plan.md").exists()
    assert (layout.reports / "auto_process_queue.json").exists()
    assert not (tmp_path / "docs" / "reports").exists()


def test_reviewed_queue_template_can_route_into_run_root_without_agent_report(tmp_path: Path):
    layout = create_run_output_layout(
        tmp_path,
        scope="reviewed_queue",
        command="reviewed-queue",
        mode="template",
        timestamp="20260603_120004",
        dry_run=True,
    )
    proposals_path = layout.reports / "proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "proposal_id": "P1",
                        "relative_path": "input/raw_data/XRD/sample.csv",
                        "source_hash": "abc",
                        "proposed_data_type": "XRD",
                        "proposed_processor": "xrd",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    code = run_reviewed_queue(
        tmp_path,
        ReviewedQueueOptions(proposals=proposals_path, write_template=True, output_root=layout.root),
    )

    assert code == 0
    assert (layout.reports / "review_decisions_template.csv").exists()
    assert not (tmp_path / "docs" / "reports").exists()


def test_origin_batch_dry_run_reports_can_route_into_run_root(tmp_path: Path):
    package = tmp_path / "package"
    (package / "processed_data").mkdir(parents=True)
    (package / "metadata").mkdir(parents=True)
    source = package / "source.csv"
    processed = package / "processed_data" / "sample_processed.csv"
    metadata = package / "metadata" / "sample_metadata.json"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    processed.write_text("x,y\n1,2\n", encoding="utf-8")
    metadata.write_text("{}", encoding="utf-8")
    manifest = package / "index.csv"
    manifest.write_text(
        "\n".join(
            [
                "result_id,data_type,source_hash,processed_csv,metadata,origin_file,figure_tif,preview_png,qc_status,origin_status,source_copy",
                f"r1,XRD,{file_hash(source)},processed_data/sample_processed.csv,metadata/sample_metadata.json,origin_files/sample.opju,figures_tif/sample.tif,figures_preview/sample.png,pending,pending,source.csv",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    layout = create_run_output_layout(
        tmp_path,
        scope="origin_batch_dry_run",
        command="origin-batch",
        mode="dry_run",
        input_paths=[manifest],
        timestamp="20260603_120005",
        dry_run=True,
    )

    code = run_origin_batch(tmp_path, OriginBatchOptions(manifest=manifest, output_root=layout.root))

    assert code == 0
    assert (layout.reports / "origin_batch_plan.json").exists()
    assert (layout.reports / "origin_batch_plan.md").exists()
    assert not (tmp_path / "output" / "reports").exists()


def test_origin_job_paths_can_route_into_run_root_without_origin(tmp_path: Path):
    processed = tmp_path / "processed.csv"
    processed.write_text("x,y\n1,2\n", encoding="utf-8")
    layout = create_run_output_layout(
        tmp_path,
        scope="process_with_origin",
        command="process",
        mode="with_origin",
        input_paths=[processed],
        timestamp="20260603_120006",
        no_origin=False,
        dry_run=False,
    )

    job = build_origin_plot_job(
        tmp_path,
        "dataset",
        processed,
        "x",
        "y",
        "XRD",
        output_root=layout.root,
    )

    assert job.plot_csv.parent == layout.logs / "origin_jobs"
    assert job.job_script.parent == layout.logs / "origin_jobs"
    assert job.origin_file.parent == layout.origin_files
    assert job.figure_tif.parent == layout.figures_tif
    assert job.preview_png.parent == layout.figures_preview
    assert not (tmp_path / "output" / "origin_files").exists()
    assert not (tmp_path / "output" / "figures_tif").exists()
    assert not (tmp_path / "output" / "figures_preview").exists()


def test_export_plot_origin_unavailable_reports_into_run_root(tmp_path: Path, monkeypatch):
    processed = tmp_path / "processed.csv"
    processed.write_text("x,y\n1,2\n", encoding="utf-8")
    layout = create_run_output_layout(
        tmp_path,
        scope="process_with_origin",
        command="process",
        mode="with_origin",
        input_paths=[processed],
        timestamp="20260603_120007",
        no_origin=False,
        dry_run=False,
    )
    monkeypatch.setenv("RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN", "1")

    result = export_plot(tmp_path, "dataset", processed, "x", "y", "XRD", output_root=layout.root)

    assert result.ok is False
    assert (layout.reports / "origin_errors.md").exists()
    assert not (tmp_path / "output" / "reports").exists()
