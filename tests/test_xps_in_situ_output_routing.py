from __future__ import annotations

import json
from pathlib import Path

from src.core import xps_in_situ as xps


ARTIFACT_SUFFIXES = {".opju", ".tif", ".tiff", ".png", ".pdf", ".xlsx", ".zip"}


def _artifact_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in ARTIFACT_SUFFIXES)


def test_output_subdirs_are_structured_and_artifact_free(tmp_path: Path) -> None:
    assert hasattr(xps, "_output_subdirs")
    output_dir = tmp_path / "run" / "xps_in_situ"

    subdirs = xps._output_subdirs(output_dir)

    assert subdirs == {
        "figures_tif": output_dir / "figures_tif",
        "figures_png": output_dir / "figures_png",
        "figures_pdf": output_dir / "figures_pdf",
        "origin_projects": output_dir / "origin_projects",
        "metadata": output_dir / "metadata",
        "reports": output_dir / "reports",
        "tables": output_dir / "tables",
    }
    assert all(path.is_dir() for path in subdirs.values())
    assert _artifact_paths(tmp_path) == []


def test_build_xps_in_situ_routes_metadata_outputs_to_structured_subdirs(tmp_path: Path, monkeypatch) -> None:
    assert hasattr(xps, "_output_subdirs")
    project_root = tmp_path / "project"
    project_root.mkdir()
    output_dir = project_root / "run" / "xps_in_situ"
    resolved_output = output_dir.resolve()
    panel = xps.InSituPanelPlan(element="Bi", region="Bi4f", reference_sample="BOBC")
    captured: dict[str, object] = {}

    monkeypatch.setattr(xps, "discover_input_files", lambda _xps_root: ({"CWO": [], "BOBC": [], "BC Dark": [], "BC Light": []}, [], []))
    monkeypatch.setattr(xps, "load_xps_fit_workbooks", lambda _sample_files: ([], []))
    monkeypatch.setattr(xps, "_select_best_records", lambda _records: {})
    monkeypatch.setattr(xps, "_record_statuses", lambda _selected: [])
    monkeypatch.setattr(xps, "planned_panels", lambda _statuses: ([panel], {}))
    monkeypatch.setattr(xps, "_panel_records", lambda _panels, _selected: {panel: []})
    monkeypatch.setattr(xps, "_write_figures", lambda _panel_records, _output_dir: {"Bi 4f": []})
    monkeypatch.setattr(xps, "_peak_summary_rows", lambda _panel_records: [{"Element": "Bi"}])
    monkeypatch.setattr(xps, "_quality_checks", lambda _output_dir, _panel_records, _origin_status: {"mocked": True})
    monkeypatch.setattr(xps, "_mapping_report", lambda **_kwargs: "mapping report\n")

    def fake_write_peak_summary(path: Path, rows: list[dict[str, object]]) -> None:
        captured["peak_summary_path"] = path
        captured["peak_summary_rows"] = rows

    monkeypatch.setattr(xps, "_write_peak_summary", fake_write_peak_summary)

    result = xps.build_xps_in_situ_outputs(project_root, output_dir, with_origin=False)

    reports_dir = resolved_output / "reports"
    tables_dir = resolved_output / "tables"
    assert result.output_dir == resolved_output
    assert captured["peak_summary_path"] == tables_dir / "peak_positions_summary.xlsx"
    assert captured["peak_summary_rows"] == [{"Element": "Bi"}]
    assert (reports_dir / "xps_data_mapping_report.md").read_text(encoding="utf-8") == "mapping report\n"
    manifest = json.loads((reports_dir / "xps_in_situ_manifest.json").read_text(encoding="utf-8"))
    metadata_path = resolved_output / "metadata" / "xps_in_situ" / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["dataset_id"] == "xps_in_situ"
    assert metadata["metadata_path"] == "metadata/xps_in_situ/metadata.json"
    assert metadata["manual_check_required"] is True
    assert manifest["metadata"] == "metadata/xps_in_situ/metadata.json"
    assert manifest["output_dirs"]["reports"] == "reports"
    assert manifest["output_dirs"]["tables"] == "tables"
    assert manifest["output_dirs"]["origin_projects"] == "origin_projects"
    assert all(not Path(value).is_absolute() for value in manifest["output_dirs"].values())
    assert not (resolved_output / "xps_data_mapping_report.md").exists()
    assert not (resolved_output / "xps_in_situ_manifest.json").exists()
    assert not (resolved_output / "peak_positions_summary.xlsx").exists()
    assert _artifact_paths(project_root) == []
