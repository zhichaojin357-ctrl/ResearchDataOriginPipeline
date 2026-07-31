from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from src.core.xps_in_situ import (
    InSituRecordStatus,
    _try_write_origin_project,
    _write_origin_project,
    planned_panels,
    sample_from_path,
)


def test_lingt_filename_maps_to_bc_light() -> None:
    path = Path("XPS") / "in_situ" / "LINGT-20260506.xlsx"

    assert sample_from_path(path) == "BC Light"


def test_planned_panels_skip_incomplete_fit_records() -> None:
    statuses = [
        InSituRecordStatus("BOBC", "Bi", "Bi4f", True),
        InSituRecordStatus("BC Dark", "Bi", "Bi4f", True),
        InSituRecordStatus("BC Light", "Bi", "Bi4f", True),
        InSituRecordStatus("CWO", "W", "W4f", True),
        InSituRecordStatus("BC Dark", "W", "W4f", False, "missing fitted envelope"),
        InSituRecordStatus("BC Light", "W", "W4f", True),
        InSituRecordStatus("CWO", "O", "O1s", True),
        InSituRecordStatus("BC Dark", "O", "O1s", True),
        InSituRecordStatus("BC Light", "O", "O1s", False, "missing component peaks"),
    ]

    panels, missing = planned_panels(statuses)

    assert [panel.element for panel in panels] == ["Bi"]
    assert missing["W"] == ["BC Dark: missing fitted envelope"]
    assert missing["O"] == ["BC Light: missing component peaks"]


def test_origin_export_reports_failure_when_expected_artifacts_are_missing() -> None:
    with TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        output_dir = project / "outputs"
        output_dir.mkdir()

        with patch("src.core.xps_in_situ.check_origin_available", return_value=(True, "ok")), patch(
            "src.core.xps_in_situ._write_origin_project",
            return_value=None,
        ):
            status = _try_write_origin_project(project, {}, output_dir)

        assert status["requested"] is True
        assert status["ok"] is False
        assert "missing or empty" in status["message"]


def test_origin_export_success_requires_opju_tif_and_preview() -> None:
    with TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        output_dir = project / "outputs"
        output_dir.mkdir()

        class Evidence:
            def as_dict(self) -> dict[str, object]:
                return {
                    "path": "temporary.tif",
                    "requested_dpi": 600,
                    "width_px": 3859,
                    "height_px": 2953,
                }

        def fake_write(_panel_records, origin_file: Path, preview_png: Path, _final_png: Path, figure_tif: Path) -> Evidence:
            for path in (origin_file, preview_png, figure_tif):
                path.write_text("artifact", encoding="utf-8")
            return Evidence()

        with patch("src.core.xps_in_situ.check_origin_available", return_value=(True, "ok")), patch(
            "src.core.xps_in_situ._write_origin_project",
            side_effect=fake_write,
        ):
            status = _try_write_origin_project(project, {}, output_dir)

        assert status["ok"] is True
        assert status["origin_file"] == "xps_in_situ_combined.opju"
        assert status["figure_tif"] == "xps_in_situ_combined.tif"
        assert status["preview_png"] == "xps_in_situ_combined_origin_preview.png"
        assert status["tif_resolution_evidence"] == {
            "path": "xps_in_situ_combined.tif",
            "requested_dpi": 600,
            "width_px": 3859,
            "height_px": 2953,
        }


def test_origin_project_reopens_saved_opju_for_tif_after_origin_exit(tmp_path: Path) -> None:
    origin_file = tmp_path / "xps_in_situ_combined.opju"
    preview_png = tmp_path / "xps_in_situ_combined_origin_preview.png"
    final_png = tmp_path / "xps_in_situ_combined.png"
    figure_tif = tmp_path / "xps_in_situ_combined.tif"
    call_order: list[str] = []

    class FakeGraph:
        name = ""

        def save_fig(self, path: str, **_kwargs) -> str:
            call_order.append("preview")
            Path(path).write_bytes(b"png")
            return path

    fake_graph = FakeGraph()

    def fake_save(path: str) -> bool:
        call_order.append("save")
        Path(path).write_bytes(b"opju")
        return True

    def fake_exit() -> None:
        call_order.append("exit")

    fake_originpro = SimpleNamespace(
        set_show=lambda _visible: None,
        new=lambda: None,
        new_graph=lambda _name: fake_graph,
        lt_exec=lambda _script: None,
        save=fake_save,
        exit=fake_exit,
    )

    def fake_reexport(opju: Path, graph_page: str, tif: Path, *, dpi: int):
        call_order.append("reopen")
        assert call_order[-2] == "exit"
        assert opju == origin_file
        assert graph_page == "xps_in_situ_combined"
        assert tif == figure_tif
        assert dpi == 600
        tif.write_bytes(b"native tif")
        return SimpleNamespace()

    with patch.dict(sys.modules, {"originpro": fake_originpro}):
        with patch("src.core.xps_in_situ._origin_layer_positions", return_value=[]):
            with patch(
                "src.core.xps_in_situ.reexport_tif_from_reopened_opju",
                side_effect=fake_reexport,
            ):
                _write_origin_project({}, origin_file, preview_png, final_png, figure_tif)

    assert call_order == ["save", "preview", "exit", "reopen"]
    assert figure_tif.read_bytes() == b"native tif"
