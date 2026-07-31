from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.core.file_utils as file_utils
from src.cli import main
from src.core.xrd_overlay import (
    XrdOverlayOptions,
    build_xrd_overlay_table,
    parse_xrd_reference_card_peaks,
    run_xrd_overlay,
    _replace_graph4_template_data_with_originpro,
    _isolated_xrd_originpro_session,
    _set_template_text_objects,
    _xrd_axis_title_labtalk,
)
from src.core.xrd_no_card_overlay import (
    XrdNoCardOverlayArtifacts,
    XrdNoCardOverlayOptions,
    XrdNoCardOverlayTable,
    _export_with_existing_script,
    _preflight_run_outputs,
    build_xrd_no_card_overlay_table,
    run_xrd_no_card_overlay,
    _origin_process_ids,
    _terminate_task_origin_processes,
)
from src.core.project import default_output_root


PROJECT_ROOT = Path(__file__).resolve().parents[1]
XRD_NO_CARD_ORIGIN_SCRIPT = PROJECT_ROOT / "scripts" / "data_types" / "xrd" / "plot_xrd_no_card_overlay_origin.py"
XRD_NO_CARD_WRAPPER = PROJECT_ROOT / "src" / "core" / "xrd_no_card_overlay.py"


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


def test_xrd_overlay_preflight_blocks_before_manifest_and_force_overwrites(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "bicu.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "bobc.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "card.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")
    output_root = default_output_root(project_root)
    timestamp = "20260731_010101"
    run_root = output_root / "runs" / f"{timestamp}_xrd_bobc_shuire_cwo_overlay"
    existing_report = run_root / "reports" / "xrd_overlay_report.md"
    existing_report.parent.mkdir(parents=True)
    existing_report.write_bytes(b"preserve")
    options = XrdOverlayOptions(
        bicu_source=bicu,
        bobc_source=bobc,
        cwo_source=cwo,
        cwo_card=card,
        reference_opju=tmp_path / "unused.opju",
        output_root=output_root,
        with_origin=False,
        timestamp=timestamp,
        force=False,
    )

    with pytest.raises(FileExistsError, match="force=True"):
        run_xrd_overlay(project_root, options)

    assert existing_report.read_bytes() == b"preserve"
    assert not (run_root / "run_manifest.json").exists()
    assert not (run_root / "processed_data").exists()

    result = run_xrd_overlay(
        project_root,
        XrdOverlayOptions(**{**options.__dict__, "force": True}),
    )

    assert result["origin_status"]["ok"] is False
    assert "- Status: processed_no_origin" in existing_report.read_text(encoding="utf-8")


def test_xrd_overlay_force_rejects_reparse_leaf_without_touching_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "bicu.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "bobc.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "card.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")
    source_before = bicu.read_bytes()
    output_root = default_output_root(project_root)
    timestamp = "20260731_010104"
    run_root = output_root / "runs" / f"{timestamp}_xrd_bobc_shuire_cwo_overlay"
    unsafe_leaf = run_root / "reports" / "xrd_overlay_report.md"
    unsafe_leaf.parent.mkdir(parents=True)
    unsafe_leaf.write_bytes(b"must-not-unlink")
    unsafe_key = file_utils.lexical_absolute_path(unsafe_leaf)
    original_check = file_utils._path_is_link_or_reparse

    monkeypatch.setattr(
        file_utils,
        "_path_is_link_or_reparse",
        lambda path: file_utils.lexical_absolute_path(path) == unsafe_key
        or original_check(path),
    )

    with pytest.raises(ValueError, match="symlink, junction, or reparse"):
        run_xrd_overlay(
            project_root,
            XrdOverlayOptions(
                bicu_source=bicu,
                bobc_source=bobc,
                cwo_source=cwo,
                cwo_card=card,
                reference_opju=tmp_path / "unused.opju",
                output_root=output_root,
                with_origin=False,
                timestamp=timestamp,
                force=True,
            ),
        )

    assert bicu.read_bytes() == source_before
    assert unsafe_leaf.read_bytes() == b"must-not-unlink"
    assert not (run_root / "run_manifest.json").exists()
    assert not (run_root / "processed_data").exists()


def test_xrd_overlay_rejects_source_inside_output_root_before_writing(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    output_root = default_output_root(project_root)
    output_root.mkdir(parents=True)
    bicu = _write_raw4(output_root / "bicu.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "bobc.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "card.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")

    with pytest.raises(ValueError, match="overlaps protected input"):
        run_xrd_overlay(
            project_root,
            XrdOverlayOptions(
                bicu_source=bicu,
                bobc_source=bobc,
                cwo_source=cwo,
                cwo_card=card,
                output_root=output_root,
                with_origin=False,
                timestamp="20260731_010102",
            ),
        )

    assert not (output_root / "runs").exists()


def test_xrd_origin_failure_has_matching_fail_status_in_metadata_and_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "bicu.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "bobc.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "card.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")
    reference = tmp_path / "reference.opju"
    reference.write_bytes(b"opju")
    monkeypatch.setattr(
        "src.core.xrd_overlay._export_xrd_overlay_with_origin",
        lambda *_args, **_kwargs: {"ok": False, "message": "synthetic Origin failure"},
    )

    result = run_xrd_overlay(
        project_root,
        XrdOverlayOptions(
            bicu_source=bicu,
            bobc_source=bobc,
            cwo_source=cwo,
            cwo_card=card,
            reference_opju=reference,
            output_root=default_output_root(project_root),
            with_origin=True,
            timestamp="20260731_010103",
        ),
    )

    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    report = (project_root / result["report"]).read_text(encoding="utf-8")
    assert metadata["processing_status"] == "fail"
    assert "- Status: fail" in report
    assert "processed_no_origin" not in report


def test_run_xrd_overlay_defaults_to_project_local_reference_opju(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    reference = project_root / "templates" / "origin_styles" / "reference_opju" / "XRD.opju"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"opju")
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
            output_root=project_root / "output",
            with_origin=False,
            timestamp="20260610_120002",
        ),
    )

    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    assert metadata["origin_reference_opju"] == "templates/origin_styles/reference_opju/XRD.opju"


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


def test_xrd_overlay_cli_passes_force_to_options(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(_project_root: Path, options: XrdOverlayOptions) -> dict:
        captured["force"] = options.force
        return {
            "run_root": "run",
            "processed_data": "processed.csv",
            "metadata": "metadata.json",
            "origin_file": "plot.opju",
            "figure_tif": "plot.tif",
            "preview_png": "plot.png",
            "origin_status": {"ok": False},
        }

    monkeypatch.setattr("src.core.xrd_overlay.run_xrd_overlay", fake_run)
    rc = main(
        [
            "xrd-overlay",
            "--bicu-source",
            str(tmp_path / "bicu.txt"),
            "--bobc-source",
            str(tmp_path / "bobc.txt"),
            "--cwo-source",
            str(tmp_path / "cwo.txt"),
            "--cwo-card",
            str(tmp_path / "card.txt"),
            "--output-root",
            str(tmp_path / "out"),
            "--timestamp",
            "20260731_050000",
            "--dry-run",
            "--force",
        ]
    )

    assert rc == 0
    assert captured["force"] is True


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


def test_xrd_overlay_direct_origin_path_sets_greek_theta_axis_title() -> None:
    labtalk = _xrd_axis_title_labtalk("Graph4")

    assert 'xb.text$="\\b(2θ (degree))"' in labtalk
    assert 'yl.text$="\\b(Intensity (a.u.))"' in labtalk
    assert "2theta (degree)" not in labtalk


def test_xrd_overlay_reopens_saved_runtime_opju_for_native_tif() -> None:
    source = inspect.getsource(_replace_graph4_template_data_with_originpro)

    assert source.index("with _isolated_xrd_originpro_session()") < source.index(
        "reexport_tif_from_reopened_opju("
    )
    assert "op.exit()" in inspect.getsource(_isolated_xrd_originpro_session)
    assert "graph.save_fig(str(runtime_tif)" not in source
    assert "_ensure_tif_600_dpi" not in source


def test_xrd_overlay_refuses_preexisting_origin_before_import(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.xrd_overlay._xrd_origin_process_ids",
        lambda: {24740},
    )
    monkeypatch.delitem(sys.modules, "originpro", raising=False)

    with pytest.raises(RuntimeError, match="already running.*24740"):
        with _isolated_xrd_originpro_session():
            raise AssertionError("session must not be yielded")


def test_xrd_overlay_origin_exit_exception_blocks_success(monkeypatch) -> None:
    fake_originpro = SimpleNamespace(
        exit=lambda: (_ for _ in ()).throw(RuntimeError("synthetic exit failure"))
    )
    monkeypatch.setitem(sys.modules, "originpro", fake_originpro)
    monkeypatch.setattr(
        "src.core.xrd_overlay._xrd_origin_process_ids",
        lambda: set(),
    )
    monkeypatch.setattr(
        "src.core.xrd_overlay._wait_for_xrd_origin_exit",
        lambda *_args, **_kwargs: set(),
    )

    with pytest.raises(RuntimeError, match="exit raised RuntimeError: synthetic exit failure"):
        with _isolated_xrd_originpro_session() as yielded:
            assert yielded is fake_originpro


def test_xrd_overlay_remaining_new_origin_pid_blocks_success(monkeypatch) -> None:
    fake_originpro = SimpleNamespace(exit=lambda: None)
    monkeypatch.setitem(sys.modules, "originpro", fake_originpro)
    monkeypatch.setattr(
        "src.core.xrd_overlay._xrd_origin_process_ids",
        lambda: set(),
    )
    monkeypatch.setattr(
        "src.core.xrd_overlay._wait_for_xrd_origin_exit",
        lambda *_args, **_kwargs: {13579},
    )

    with pytest.raises(RuntimeError, match="remained.*13579"):
        with _isolated_xrd_originpro_session():
            pass


def test_xrd_no_card_overlay_accepts_mixed_xrd_text_formats(tmp_path: Path) -> None:
    raw4 = _write_raw4(tmp_path / "bob.txt", [(5.0, 10.0), (6.0, 20.0), (7.0, 15.0)])
    exported = _write_simple_xrd_export(tmp_path / "BOB0.5C0.5.TXT", [(5.0, 2.0), (6.0, 6.0), (7.0, 4.0)])

    table = build_xrd_no_card_overlay_table((raw4, exported), ("bob", "BOB0.5C0.5"))

    assert table.headers == ["two_theta_deg", "bob", "BOB0.5C0.5"]
    assert table.metadata["standard_card_added"] is False
    assert table.metadata["point_counts"] == {"bob": 3, "BOB0.5C0.5": 3}
    assert table.rows[0][1] > table.rows[0][2]


def test_run_xrd_no_card_overlay_dry_run_writes_metadata_without_origin(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    raw4 = _write_raw4(tmp_path / "bob.txt", [(5.0, 10.0), (6.0, 20.0), (7.0, 15.0)])
    exported = _write_simple_xrd_export(tmp_path / "BOB0.5C0.5.TXT", [(5.0, 2.0), (6.0, 6.0), (7.0, 4.0)])

    result = run_xrd_no_card_overlay(
        project_root,
        XrdNoCardOverlayOptions(
            sources=(raw4, exported),
            output_root=project_root / "output",
            with_origin=False,
            timestamp="20260705_120000",
        ),
    )

    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    assert result["will_launch_origin"] is False
    assert metadata["processing_status"] == "processed_no_origin"
    assert metadata["standard_card_added"] is False
    assert metadata["origin_file"] is None
    assert "no standard-card sticks" in " ".join(metadata["manual_check_items"])


def test_xrd_no_card_overlay_cli_parses_input_dir(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    input_dir = tmp_path / "BOBXC1-X"
    input_dir.mkdir()
    _write_raw4(input_dir / "bob.txt", [(5.0, 10.0), (6.0, 20.0), (7.0, 15.0)])

    rc = main(
        [
            "xrd-no-card-overlay",
            "--input-dir",
            str(input_dir),
            "--output-root",
            str(project_root / "output"),
            "--timestamp",
            "20260705_120001",
            "--dry-run",
        ]
    )

    assert rc == 0


def test_xrd_no_card_overlay_rejects_missing_explicit_reference(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = _write_raw4(tmp_path / "bob.txt", [(5.0, 10.0), (6.0, 20.0)])

    try:
        run_xrd_no_card_overlay(
            project_root,
            XrdNoCardOverlayOptions(
                sources=(source,),
                output_root=project_root / "output",
                with_origin=False,
                reference_opju=tmp_path / "missing_reference.opju",
            ),
        )
    except FileNotFoundError as exc:
        assert "Explicit XRD no-card reference OPJU does not exist" in str(exc)
    else:
        raise AssertionError("missing explicit reference OPJU should fail")


def test_xrd_no_card_origin_script_restricts_output_dir_to_output_root() -> None:
    script_text = XRD_NO_CARD_ORIGIN_SCRIPT.read_text(encoding="utf-8")
    wrapper_text = XRD_NO_CARD_WRAPPER.read_text(encoding="utf-8")

    assert "def ensure_output_dir_allowed(output_dir: Path, output_root: Path | None) -> Path:" in script_text
    assert "resolve_output_root(PROJECT_ROOT, explicit=output_root)" in script_text
    assert "is_under_or_equal(lexical_output_dir, resolved_output_root)" in script_text
    assert "ensure_safe_output_file_target(" in script_text
    assert "--output-dir must stay under the configured output root" in script_text
    assert 'parser.add_argument("--output-root", type=Path, default=None)' in script_text
    assert "args.output_dir = ensure_output_dir_allowed(args.output_dir, args.output_root)" in script_text
    assert '"--output-root",' in wrapper_text
    assert "str(artifacts.script_output_dir.parents[1])" in wrapper_text


def test_xrd_no_card_origin_script_reopens_final_opju_for_native_600_dpi() -> None:
    script_text = XRD_NO_CARD_ORIGIN_SCRIPT.read_text(encoding="utf-8")

    preview_index = script_text.index("png = export_preview(")
    exit_index = script_text.index("app.Exit()", preview_index)
    reexport_index = script_text.index("resolution = reexport_tif_from_reopened_opju(", exit_index)

    assert exit_index < reexport_index
    assert "dpi=600" in script_text[reexport_index:]
    assert "ensure_tif_600_dpi" not in script_text
    assert "output.resize(" not in script_text
    assert "expGraph type:=tif" not in script_text


def test_xrd_no_card_origin_script_preflights_before_mkdir_or_unlink() -> None:
    script_text = XRD_NO_CARD_ORIGIN_SCRIPT.read_text(encoding="utf-8")
    start = script_text.index("args.output_dir = ensure_output_dir_allowed")
    preflight = script_text.index("preflight_output_targets(", start)
    origin_guard = script_text.index("running_origin = existing_origin_process_ids()", preflight)
    cleanup = script_text.index("prepare_safe_output_file_targets(", origin_guard)
    mkdir = script_text.index("args.output_dir.mkdir(", origin_guard)

    assert preflight < origin_guard < cleanup < mkdir
    assert 'parser.add_argument("--force", action="store_true")' in script_text
    assert "Input CSV and reference OPJU must be outside --output-dir" in script_text
    assert "sha256_before" in script_text
    assert "sha256_after" in script_text


def test_xrd_no_card_output_preflight_requires_force_for_existing_targets(tmp_path: Path) -> None:
    artifact = tmp_path / "product.opju"
    artifact.write_bytes(b"keep")
    artifacts = XrdNoCardOverlayArtifacts(
        processed_data=tmp_path / "processed.csv",
        metadata=tmp_path / "metadata.json",
        report=tmp_path / "report.md",
        origin_file=artifact,
        figure_tif=tmp_path / "figure.tif",
        preview_png=tmp_path / "preview.png",
        script_output_dir=tmp_path / "stage",
    )

    try:
        _preflight_run_outputs(artifacts, force=False)
    except FileExistsError as exc:
        assert "rerun with --force" in str(exc)
    else:
        raise AssertionError("existing output must fail closed without --force")
    assert artifact.read_bytes() == b"keep"

    _preflight_run_outputs(artifacts, force=True)

    assert not artifact.exists()


def test_xrd_no_card_wrapper_blocks_preexisting_origin_without_launching_script(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    run_root = tmp_path / "run"
    artifacts = XrdNoCardOverlayArtifacts(
        processed_data=run_root / "processed.csv",
        metadata=run_root / "metadata.json",
        report=run_root / "report.md",
        origin_file=run_root / "origin" / "product.opju",
        figure_tif=run_root / "tif" / "product.tif",
        preview_png=run_root / "png" / "product.png",
        script_output_dir=run_root / "logs" / "stage",
    )
    options = XrdNoCardOverlayOptions(
        sources=(tmp_path / "source.txt",),
        with_origin=True,
    )
    table = XrdNoCardOverlayTable(
        headers=["two_theta_deg", "sample"],
        rows=[[5.0, 1.0], [6.0, 2.0]],
        labels=["sample"],
        metadata={},
    )
    monkeypatch.setattr(
        "src.core.xrd_no_card_overlay.check_origin_available",
        lambda: (True, "ok"),
    )
    monkeypatch.setattr(
        "src.core.xrd_no_card_overlay._origin_process_ids",
        lambda *_args, **_kwargs: [24740],
    )

    def fail_launch(*_args, **_kwargs):
        raise AssertionError("the helper script must not launch while Origin is open")

    monkeypatch.setattr(
        "src.core.xrd_no_card_overlay.subprocess.run",
        fail_launch,
    )

    status = _export_with_existing_script(
        project_root,
        options,
        table,
        artifacts,
        None,
    )

    assert status["ok"] is False
    assert status["pre_existing_origin_pids"] == [24740]
    assert "already running" in status["message"]


def test_xrd_no_card_origin_cleanup_preserves_preexisting_origin_pid(monkeypatch) -> None:
    calls: list[list[str]] = []

    class Completed:
        stdout = "24740\n12345\nnot-a-pid\n"
        stderr = ""
        returncode = 0

    def fake_run(command, **_kwargs):
        calls.append(list(command))
        return Completed()

    monkeypatch.setattr("src.core.xrd_no_card_overlay.subprocess.run", fake_run)

    assert _origin_process_ids({24740}) == [12345]
    _terminate_task_origin_processes({24740})

    stop_command = calls[-1][-1]
    assert "12345" in stop_command
    assert "24740" not in stop_command


def _write_raw4(path: Path, rows: list[tuple[float, float]]) -> Path:
    lines = [";RAW4.00", "[RawHeader]", "Date=06/10/2026", "", "[Data]", "Angle, PSD"]
    lines.extend(f"{x}, {y}" for x, y in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_simple_xrd_export(path: Path, rows: list[tuple[float, float]]) -> Path:
    lines = [
        "Sample\tLL-1",
        "Start\t5",
        "Stop\t80",
        "Step\t0.1",
    ]
    lines.extend(f"{x}\t{y}" for x, y in rows)
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
