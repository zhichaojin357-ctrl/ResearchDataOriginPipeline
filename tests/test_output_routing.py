from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from src.core.process import ProcessOptions, run_process
from src.core.runtime_paths import create_run_output_layout


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
    assert layout.root == tmp_path / "output" / "runs" / "20260603_120000_process_no_origin"
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
    assert manifest["output_root"] == str(layout.root)
    assert manifest["produced_artifact_directories"]["processed_data"] == str(layout.processed_data)
    assert manifest["input_paths"] == [str(tmp_path / "input" / "raw_data")]


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
