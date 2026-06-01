from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.xps_in_situ import InSituRecordStatus, _try_write_origin_project, planned_panels, sample_from_path


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
