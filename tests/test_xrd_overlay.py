from __future__ import annotations

import json
from pathlib import Path

from src.cli import main
from src.core.xrd_overlay import (
    XrdOverlayArtifacts,
    XrdOverlayOptions,
    XrdOverlayTable,
    build_xrd_overlay_table,
    parse_xrd_reference_card_peaks,
    run_xrd_overlay,
    _origin_job_script,
    _set_template_text_objects,
    _xrd_axis_title_labtalk,
)
from src.core.project import default_output_root


def test_build_xrd_overlay_table_orders_requested_series_and_card(tmp_path: Path) -> None:
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0), (7.0, 15.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 4.0), (6.0, 8.0), (7.0, 6.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 2.0), (6.0, 4.0), (7.0, 3.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")

    table = build_xrd_overlay_table(bicu, bobc, cwo, card)

    assert table.headers == [
        "two_theta_deg",
        "BiCu-10",
        "BiOBr\\-(0.5)Cl\\-(0.5)",
        "CuWO\\-(4)",
        "CuWO\\-(4) JCPDS card No.04-009-6293",
    ]
    assert table.legend_labels[:3] == ["BiCu-10", "BiOBr\\-(0.5)Cl\\-(0.5)", "CuWO\\-(4)"]
    assert table.origin_ocolors[:3] == [23709421, 33518174, 16814848]
    assert table.rows[0][1] > table.rows[0][2] > table.rows[0][3] > table.rows[0][4]
    assert table.rows[1][4] > 0
    assert table.metadata["reference_card"]["peak_count"] == 2


def test_parse_xrd_reference_card_peaks_accepts_pdf_text_rows(tmp_path: Path) -> None:
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("18.68 3.12 44\nbad row\n23.91 2.22 100\n", encoding="utf-8")

    assert parse_xrd_reference_card_peaks(card) == [(18.68, 44.0), (23.91, 100.0)]


def test_run_xrd_overlay_dry_run_writes_metadata_without_origin(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")
    reference = tmp_path / "CWO+BOBC+标卡.opju"
    reference.write_bytes(b"opju")

    result = run_xrd_overlay(
        project_root,
        XrdOverlayOptions(
            bicu_source=bicu,
            bobc_source=bobc,
            cwo_source=cwo,
            cwo_card=card,
            reference_opju=reference,
            output_root=default_output_root(project_root),
            with_origin=False,
            timestamp="20260610_120000",
        ),
    )

    assert result["will_launch_origin"] is False
    processed = project_root / result["processed_data"]
    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    report = (project_root / result["report"]).read_text(encoding="utf-8")
    assert processed.exists()
    assert metadata["manual_check_required"] is True
    assert metadata["origin_status"]["ok"] is False
    assert metadata["source_files"] == ["external/BOBCshuirecwo.txt", "external/BOBCshuire.txt", "external/cwo.txt"]
    assert metadata["origin_reference_opju"] == "external/CWO+BOBC+标卡.opju"
    rendered_metadata = json.dumps(metadata, ensure_ascii=False)
    assert "Codex Project" not in rendered_metadata
    assert ":/" not in rendered_metadata.replace("Origin export skipped by --dry-run/--no-origin.", "")
    assert str(reference) not in report
    assert "external/CWO+BOBC+标卡.opju" in report
    assert "BiOBr\\-(0.5)Cl\\-(0.5)" in processed.read_text(encoding="utf-8").splitlines()[0]


def test_run_xrd_overlay_dry_run_does_not_require_reference_opju(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")

    result = run_xrd_overlay(
        project_root,
        XrdOverlayOptions(
            bicu_source=bicu,
            bobc_source=bobc,
            cwo_source=cwo,
            cwo_card=card,
            reference_opju=tmp_path / "missing_reference.opju",
            output_root=default_output_root(project_root),
            with_origin=False,
            timestamp="20260610_120001",
        ),
    )

    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    assert result["will_launch_origin"] is False
    assert metadata["processing_status"] == "processed_no_origin"
    assert metadata["origin_reference_opju"].endswith("missing_reference.opju")


def test_xrd_overlay_cli_parses_required_sources(tmp_path: Path) -> None:
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n", encoding="utf-8")
    reference = tmp_path / "CWO+BOBC+标卡.opju"
    reference.write_bytes(b"opju")

    rc = main(
        [
            "xrd-overlay",
            "--bicu-source",
            str(bicu),
            "--bobc-source",
            str(bobc),
            "--cwo-source",
            str(cwo),
            "--cwo-card",
            str(card),
            "--reference-opju",
            str(reference),
            "--output-root",
            str(tmp_path / "out"),
            "--timestamp",
            "20260610_120000",
            "--dry-run",
        ]
    )

    assert rc == 0


def test_xrd_overlay_template_text_uses_uniform_legend_format() -> None:
    layer1 = _FakeLayer({"Legend": _FakeGraphObject(), "Text": _FakeGraphObject()})
    layer2 = _FakeLayer({"Text": _FakeGraphObject()})
    graph = _FakeGraph([layer1, layer2])

    _set_template_text_objects(graph)

    legend = layer1.obj.GraphObjects["Legend"]
    top_text = layer1.obj.GraphObjects["Text"]
    card_text = layer2.obj.GraphObjects["Text"]
    assert legend.Text == "\\l(2)\\b( BiOBr\\-(0.5)Cl\\-(0.5))\r\n\\l(1)\\b( CuWO\\-(4))"
    assert top_text.Text == "\\b(BiCu-10)"
    assert legend.props["fsize"] == top_text.props["fsize"] == 26
    assert legend.props["font"] == top_text.props["font"] == 67
    assert legend.props["bold"] == top_text.props["bold"] == 1
    assert legend.props["frame"] == legend.props["fill"] == legend.props["fillarea"] == 0
    assert top_text.Left == 4110
    assert legend.Left == 3569
    assert legend.Top > top_text.Top
    assert "fsize" not in card_text.props


def test_xrd_overlay_origin_script_uses_greek_theta_axis_title(tmp_path: Path) -> None:
    table = XrdOverlayTable(
        headers=["two_theta_deg", "BOBC"],
        rows=[[5.0, 1.0], [6.0, 2.0]],
        legend_labels=["BOBC"],
        origin_ocolors=[16814848],
        metadata={},
    )
    options = XrdOverlayOptions(
        bicu_source=tmp_path / "bicu.txt",
        bobc_source=tmp_path / "bobc.txt",
        cwo_source=tmp_path / "cwo.txt",
        cwo_card=tmp_path / "card.txt",
        reference_opju=tmp_path / "reference.opju",
    )
    artifacts = XrdOverlayArtifacts(
        processed_data=tmp_path / "processed.csv",
        metadata=tmp_path / "metadata.json",
        report=tmp_path / "report.md",
        origin_file=tmp_path / "plot.opju",
        figure_tif=tmp_path / "plot.tif",
        preview_png=tmp_path / "plot.png",
        job_script=tmp_path / "job.ps1",
    )

    script = _origin_job_script(tmp_path, options, table, artifacts)

    assert "XTitle = '2θ (degree)'" in script
    assert "2theta (degree)" not in script


def test_xrd_overlay_direct_origin_path_sets_greek_theta_axis_title() -> None:
    labtalk = _xrd_axis_title_labtalk("Graph4")

    assert 'xb.text$="\\b(2θ (degree))"' in labtalk
    assert 'yl.text$="\\b(Intensity (a.u.))"' in labtalk
    assert "2theta (degree)" not in labtalk


def _write_raw4(path: Path, rows: list[tuple[float, float]]) -> Path:
    lines = [";RAW4.00", "[RawHeader]", "Date=06/10/2026", "", "[Data]", "Angle, PSD"]
    lines.extend(f"{x}, {y}" for x, y in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class _FakeGraphObject:
    def __init__(self) -> None:
        self.Text = ""
        self.Left = 0
        self.Top = 0
        self.Width = 0
        self.Height = 0
        self.props: dict[str, object] = {}

    def SetNumProp(self, prop: str, value: object) -> None:
        self.props[prop] = value


class _FakeLayerObject:
    def __init__(self, objects: dict[str, _FakeGraphObject]) -> None:
        self.GraphObjects = objects


class _FakeLayer:
    def __init__(self, objects: dict[str, _FakeGraphObject]) -> None:
        self.obj = _FakeLayerObject(objects)


class _FakeGraph:
    def __init__(self, layers: list[_FakeLayer]) -> None:
        self._layers = layers

    def __getitem__(self, index: int) -> _FakeLayer:
        return self._layers[index]
