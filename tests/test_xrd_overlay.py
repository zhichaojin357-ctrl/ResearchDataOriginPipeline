from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import src.core.file_utils as file_utils
from src.cli import main
from src.core.xrd_overlay import (
    XrdOverlayOptions,
    build_xrd_overlay_table,
    parse_xrd_reference_card_peaks,
    run_xrd_overlay,
    _apply_xrd_native_text_and_axes,
    _build_fresh_xrd_overlay_with_operations,
    _fresh_xrd_xy_ranges,
    _write_xrd_overlay_worksheets,
    _xrd_axis_title_labtalk,
)
from src.origin.operations import OperationResult
from src.core.xrd_no_card_overlay import (
    XrdNoCardOverlayArtifacts,
    XrdNoCardOverlayOptions,
    XrdNoCardOverlayTable,
    _export_with_existing_script,
    _preflight_run_outputs,
    _xrd_no_card_style_mode,
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
    graph_template = project_root / "templates" / "origin_styles" / "graph_templates" / "XRD.otpu"
    graph_template.parent.mkdir(parents=True)
    graph_template.write_bytes(b"otpu")
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


def test_xrd_overlay_fresh_worksheet_layout_uses_processed_data_exactly(tmp_path: Path) -> None:
    bicu = _write_raw4(tmp_path / "bicu.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "bobc.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "card.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")
    table = build_xrd_overlay_table(bicu, bobc, cwo, card)
    operations = _FakeFreshXrdOperations()

    book2, book3 = _write_xrd_overlay_worksheets(operations, table)

    assert (book2, book3) == ("Book2", "Book3")
    assert operations.columns[("Book2", "Sheet1")][1] == [row[3] for row in table.rows]
    assert operations.columns[("Book2", "Sheet1")][3] == [row[2] for row in table.rows]
    assert operations.columns[("Book2", "Sheet1")][7] == [row[4] for row in table.rows]
    assert operations.columns[("Book3", "Sheet1")][5] == [row[1] for row in table.rows]


def test_xrd_overlay_fresh_graph_ranges_use_only_new_worksheets() -> None:
    ranges = _fresh_xrd_xy_ranges("Book2", "Book3", 42)

    assert [(item["layer_index"], item["book_name"], item["x_col"], item["y_col"]) for item in ranges] == [
        (1, "Book2", 1, 2),
        (1, "Book2", 3, 4),
        (2, "Book2", 7, 8),
        (3, "Book3", 5, 6),
    ]
    assert {item["row_to"] for item in ranges} == {42}


def test_xrd_overlay_direct_origin_path_sets_greek_theta_axis_title() -> None:
    labtalk = _xrd_axis_title_labtalk("Graph4")

    assert 'xb.text$="\\b(2θ (degree))"' in labtalk
    assert 'yl.text$="\\b(Intensity (a.u.))"' in labtalk
    assert "2theta (degree)" not in labtalk


def test_xrd_overlay_fresh_builder_never_loads_or_copies_reference_opju() -> None:
    source = inspect.getsource(_build_fresh_xrd_overlay_with_operations)

    assert "load_project(options.reference_opju)" not in source
    assert "copy2(options.reference_opju" not in source
    assert "load_project(artifacts.origin_file)" in source
    assert "create_graph_from_xy_pairs_template" in source
    assert "export_graph(\"Graph4\", artifacts.preview_png, \"png\", dpi=600)" in source
    assert "_export_native_xrd_tif_with_physical_validation" in source
    assert "originpro" not in source


def test_xrd_overlay_preserves_otpu_axis_title_objects_without_recreating_them() -> None:
    source = inspect.getsource(_apply_xrd_native_text_and_axes)

    assert "_xrd_axis_title_labtalk" not in source
    assert "__rdop_xrd_x_title$=xb.text$" in source
    assert "__rdop_xrd_y_title$=yl.text$" in source


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
    assert metadata["style_mode"] == "adaptive_oth_json"
    assert metadata["reference_opju_loaded"] is False
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


def test_xrd_no_card_style_dispatches_fixed_only_for_nine_curves() -> None:
    assert _xrd_no_card_style_mode(9) == "fixed_otpu"
    assert _xrd_no_card_style_mode(8) == "adaptive_oth_json"
    assert _xrd_no_card_style_mode(10) == "adaptive_oth_json"


def test_xrd_no_card_origin_script_uses_detached_assets_and_never_loads_reference() -> None:
    script_text = XRD_NO_CARD_ORIGIN_SCRIPT.read_text(encoding="utf-8")
    wrapper_text = XRD_NO_CARD_WRAPPER.read_text(encoding="utf-8")

    assert 'FIXED_TEMPLATE = STYLE_ROOT / "graph_templates" / "XRD_no_card.otpu"' in script_text
    assert 'ADAPTIVE_THEME = STYLE_ROOT / "format_themes" / "XRD_no_card.oth"' in script_text
    assert 'return "fixed_otpu", FIXED_TEMPLATE' in script_text
    assert 'return "adaptive_oth_json", ADAPTIVE_THEME' in script_text
    assert "OriginOperations(app).apply_graph_theme(graph_name, style_asset)" in script_text
    assert "fixed_template=style_asset if style_mode == \"fixed_otpu\" else None" in script_text
    assert "inspect_reference_style" not in script_text
    assert "resolve_origin_reference_pattern" not in wrapper_text
    assert "reference_opju_loaded\": False" in script_text
    assert "reference_opju_loaded\": False" in wrapper_text


def test_xrd_no_card_origin_script_is_native_origin_only_and_rebuilds_template_labels() -> None:
    script_text = XRD_NO_CARD_ORIGIN_SCRIPT.read_text(encoding="utf-8")

    assert "win32com.client.DispatchEx(\"Origin.Application\")" in script_text
    assert "app.NewProject()" in script_text
    assert "matplotlib" not in script_text.casefold()
    assert "from PIL" not in script_text
    assert "InsertImage" not in script_text
    assert "label -r DL{index}" in script_text
    assert "max(FIXED_CURVE_COUNT, len(labels))" in script_text


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


class _FakeFreshXrdOperations:
    def __init__(self) -> None:
        self.columns: dict[tuple[str, str], list[list[float]]] = {}

    def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
        self.columns[(book_name, sheet_name)] = []
        return OperationResult(True, "created", {"book_name": book_name, "sheet_name": sheet_name})

    def set_worksheet_data(
        self,
        book_name: str,
        sheet_name: str,
        columns,
        column_names=None,
    ) -> OperationResult:
        values = [list(column) for column in columns]
        self.columns[(book_name, sheet_name)] = values
        return OperationResult(True, "written", {"columns": len(values), "rows": len(values[0])})

    def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
        return OperationResult(True, "read", {"columns": self.columns[(book_name, sheet_name)]})
