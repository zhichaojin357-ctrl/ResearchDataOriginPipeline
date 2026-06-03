from __future__ import annotations

import json
from pathlib import Path

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
