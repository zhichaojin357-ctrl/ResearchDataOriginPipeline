from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openpyxl import Workbook

import src.core.epr_overlay as epr_overlay
from src.core.epr_overlay import EprOverlayOptions, build_epr_condition_overlay, run_epr_overlay
from src.core import file_utils
from src.core.project import default_output_root
from src.origin.adapter import plan_origin_plot_output_paths


def _result_path(root: Path, value: object) -> Path:
    path = Path(str(value))
    if path.parts and path.parts[0] == "output":
        return default_output_root(root) / Path(*path.parts[1:])
    return path if path.is_absolute() else root / path


def _write_xlsx(path: Path, ys: list[float]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for index, y in enumerate(ys):
        sheet.append([324.0 + index * 0.0001, y])
    workbook.save(path)


def test_epr_overlay_builds_condition_group_without_normalizing_amplitudes(tmp_path: Path) -> None:
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])

    result = build_epr_condition_overlay(tmp_path, ref, "OH", with_origin=False, normalize=False)

    assert result["status"] == "table_only"
    assert result["labels"] == ["BC", "CWO", "BOBC"]
    assert result["file_labels"] == ["BC-OH-light2", "CWO-OH-light2", "BOBC-OH-light1"]
    assert result["point_count"] == 4
    assert result["offset_step"] > 0
    with _result_path(tmp_path, result["processed_csv"]).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["magnetic_field", "BC", "CWO", "BOBC"]
    # Default EPR overlay preserves relative amplitude; the BOBC centered span remains much larger than BC.
    bc_values = [float(row[1]) for row in rows[1:]]
    bobc_values = [float(row[3]) for row in rows[1:]]
    assert max(bobc_values) - min(bobc_values) > 50 * (max(bc_values) - min(bc_values))


def test_epr_overlay_requires_common_grid_but_not_4096_points(tmp_path: Path) -> None:
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [0.0] * 4)
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [1.0] * 4)
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [2.0] * 3)

    try:
        build_epr_condition_overlay(tmp_path, ref, "OH", with_origin=False)
    except ValueError as exc:
        assert "different row counts" in str(exc)
    else:
        raise AssertionError("Expected common-grid validation failure")


def test_epr_overlay_writes_baseline_smoothing_detail_to_requested_output_dir(tmp_path: Path) -> None:
    ref = tmp_path / "refs"
    output_base = tmp_path.parent / f"{tmp_path.name}_external_output"
    out = output_base / "EPR" / "processed_data"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [10, 12, 16, 18, 20])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [20, 24, 32, 36, 40])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [30, 36, 48, 54, 60])

    result = build_epr_condition_overlay(
        tmp_path,
        ref,
        "OH",
        with_origin=False,
        normalize=False,
        smooth_window=3,
        output_data_dir=out,
    )

    assert result["smoothing"] == "moving_average_window_3"
    assert (out / "epr_oh_overlay_processed.csv").is_file()
    assert (out / "epr_oh_overlay_detail.csv").is_file()
    assert not Path(result["processed_csv"]).is_absolute()
    with (out / "epr_oh_overlay_detail.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == [
        "magnetic_field",
        "BC_raw",
        "BC_baseline",
        "BC_baseline_corrected",
        "BC_offset",
        "CWO_raw",
        "CWO_baseline",
        "CWO_baseline_corrected",
        "CWO_offset",
        "BOBC_raw",
        "BOBC_baseline",
        "BOBC_baseline_corrected",
        "BOBC_offset",
    ]
    assert any(float(row[2]) != 0.0 for row in rows[1:])


def test_epr_overlay_writes_canonical_metadata_next_to_output_package(tmp_path: Path) -> None:
    ref = tmp_path / "refs"
    output_base = tmp_path.parent / f"{tmp_path.name}_external_output"
    out = output_base / "EPR" / "processed_data"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])

    result = build_epr_condition_overlay(tmp_path, ref, "OH", with_origin=False, output_data_dir=out)

    metadata = out.parent / "metadata" / "epr_oh_overlay" / "metadata.json"
    assert metadata == out.parent / "metadata" / "epr_oh_overlay" / "metadata.json"
    recorded = json.loads(metadata.read_text(encoding="utf-8"))
    assert recorded["dataset_id"] == "epr_oh_overlay"
    assert recorded["metadata_path"] == "output/metadata/epr_oh_overlay/metadata.json"
    assert recorded["field_unit"] is None
    assert recorded["manual_check_required"] is True
    assert recorded["forbidden_claims"] == ["no automatic radical assignment", "no automatic mechanism claim"]


def test_epr_overlay_rejects_reports_outside_output_root(tmp_path: Path) -> None:
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])

    try:
        run_epr_overlay(
            tmp_path,
            EprOverlayOptions(reference_dir=ref, group="OH", report_json=tmp_path / "unsafe.json"),
        )
    except ValueError as exc:
        assert "Refusing to write" in str(exc)
    else:
        raise AssertionError("Expected EPR overlay report path guard failure")


def test_epr_overlay_honors_explicit_external_output_root(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_root = tmp_path / "explicit-output"

    code = run_epr_overlay(
        project,
        EprOverlayOptions(
            reference_dir=ref,
            output_root=output_root,
            group="OH",
        ),
    )

    assert code == 0
    assert (
        output_root
        / "processed_data"
        / "EPR"
        / "epr_oh_overlay_processed.csv"
    ).is_file()
    assert (output_root / "reports" / "epr_overlay_report.json").is_file()
    assert not default_output_root(project).exists()


def test_epr_overlay_force_defaults_to_false_and_refuses_partial_overwrite(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    data_dir = output_base / "processed_data" / "EPR"
    data_dir.mkdir(parents=True)
    detail_csv = data_dir / "epr_oh_overlay_detail.csv"
    detail_csv.write_text("existing detail\n", encoding="utf-8")

    assert EprOverlayOptions().force is False
    with pytest.raises(FileExistsError, match="force=True"):
        build_epr_condition_overlay(project, ref, "OH")

    assert detail_csv.read_text(encoding="utf-8") == "existing detail\n"
    assert not (data_dir / "epr_oh_overlay_processed.csv").exists()
    assert not (output_base / "metadata" / "EPR" / "epr_oh_overlay" / "metadata.json").exists()


def test_epr_overlay_force_unlinks_hardlink_before_creating_csv(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    plot_csv = output_base / "processed_data" / "EPR" / "epr_oh_overlay_processed.csv"
    plot_csv.parent.mkdir(parents=True)
    hardlink_source = tmp_path / "hardlink_source.csv"
    hardlink_source.write_text("must remain unchanged\n", encoding="utf-8")
    os.link(hardlink_source, plot_csv)

    result = build_epr_condition_overlay(project, ref, "OH", force=True)

    assert result["status"] == "table_only"
    assert hardlink_source.read_text(encoding="utf-8") == "must remain unchanged\n"
    assert plot_csv.read_text(encoding="utf-8").startswith("magnetic_field,BC,CWO,BOBC")
    assert os.stat(hardlink_source).st_ino != os.stat(plot_csv).st_ino


def test_epr_overlay_rejects_reparse_chain_before_writing_any_output(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    data_dir = output_base / "processed_data" / "EPR"
    real_inspector = file_utils._path_is_link_or_reparse

    def fake_inspector(path: Path) -> bool:
        if path == data_dir:
            return True
        return real_inspector(path)

    with patch("src.core.file_utils._path_is_link_or_reparse", side_effect=fake_inspector):
        with pytest.raises(ValueError, match="reparse point"):
            build_epr_condition_overlay(project, ref, "OH", force=True)

    assert not (data_dir / "epr_oh_overlay_processed.csv").exists()
    assert not (data_dir / "epr_oh_overlay_detail.csv").exists()


def test_epr_overlay_rejects_output_package_overlapping_reference_inputs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    data_dir = ref / "processed_data"

    with pytest.raises(ValueError, match="overlaps protected input"):
        build_epr_condition_overlay(
            project,
            ref,
            "OH",
            output_data_dir=data_dir,
            force=True,
        )

    assert not (data_dir / "epr_oh_overlay_processed.csv").exists()


def test_epr_overlay_direct_api_rejects_runtime_output_inside_project_tree(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    unsafe = project / "src" / "generated"

    with pytest.raises(
        ValueError,
        match="Refusing to write runtime outputs inside project tree",
    ):
        build_epr_condition_overlay(
            project,
            ref,
            "OH",
            output_data_dir=unsafe,
            force=True,
        )

    assert not unsafe.exists()


def test_epr_overlay_staging_failure_preserves_previous_package(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    plot_csv = (
        output_base
        / "processed_data"
        / "EPR"
        / "epr_oh_overlay_processed.csv"
    )
    detail_csv = plot_csv.with_name("epr_oh_overlay_detail.csv")
    metadata = (
        output_base
        / "metadata"
        / "EPR"
        / "epr_oh_overlay"
        / "metadata.json"
    )
    for path, content in (
        (plot_csv, "old plot\n"),
        (detail_csv, "old detail\n"),
        (metadata, '{"old": true}\n'),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    with patch(
        "src.core.epr_overlay._write_epr_overlay_csvs",
        side_effect=RuntimeError("injected staging failure"),
    ):
        with pytest.raises(RuntimeError, match="injected staging failure"):
            build_epr_condition_overlay(
                project,
                ref,
                "OH",
                force=True,
            )

    assert plot_csv.read_text(encoding="utf-8") == "old plot\n"
    assert detail_csv.read_text(encoding="utf-8") == "old detail\n"
    assert metadata.read_text(encoding="utf-8") == '{"old": true}\n'
    assert not list(output_base.glob(".epr-oh-staging-*"))


def test_epr_overlay_preflights_origin_targets_and_passes_force_explicitly(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    origin_paths = plan_origin_plot_output_paths(
        project,
        "EPR_OH_overlay",
        output_root=output_base,
    )
    origin_paths.origin_file.parent.mkdir(parents=True)
    origin_paths.origin_file.write_text("existing OPJU marker", encoding="utf-8")

    with (
        patch(
            "src.core.epr_overlay.check_origin_available",
            return_value=(True, "ok"),
        ),
        patch("src.core.epr_overlay.origin_process_ids", return_value=set()),
        patch("src.core.epr_overlay.export_plot") as export,
    ):
        with pytest.raises(FileExistsError, match="force=True"):
            build_epr_condition_overlay(project, ref, "OH", with_origin=True)
        export.assert_not_called()
    assert not (output_base / "processed_data" / "EPR" / "epr_oh_overlay_processed.csv").exists()

    class Evidence:
        def as_dict(self) -> dict[str, object]:
            return {
                "path": "staged.tif",
                "requested_dpi": 600,
                "page_width_origin_units": 100.0,
                "page_height_origin_units": 100.0,
            }

    def fake_export(
        root: Path,
        dataset_id: str,
        *_args: object,
        **kwargs: object,
    ) -> SimpleNamespace:
        stage_root = Path(kwargs["output_root"])
        staged = plan_origin_plot_output_paths(
            root,
            dataset_id,
            output_root=stage_root,
        )
        for path, content in (
            (staged.origin_file, b"opju"),
            (staged.figure_tif, b"tif"),
            (staged.preview_png, b"png"),
            (staged.plot_csv, b"x,y\n0,1\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return SimpleNamespace(
            ok=True,
            origin_file=staged.origin_file,
            figure_tif=staged.figure_tif,
            preview_png=staged.preview_png,
            message="mock export",
            tif_resolution_evidence=Evidence(),
        )

    with (
        patch(
            "src.core.epr_overlay.check_origin_available",
            return_value=(True, "ok"),
        ),
        patch("src.core.epr_overlay.origin_process_ids", return_value=set()),
        patch(
            "src.core.epr_overlay.export_plot",
            side_effect=fake_export,
        ) as export,
    ):
        result = build_epr_condition_overlay(
            project,
            ref,
            "OH",
            with_origin=True,
            force=True,
        )
    assert result["status"] == "success"
    assert export.call_args.kwargs["force"] is False
    stage_root = Path(export.call_args.kwargs["output_root"])
    assert stage_root.parent == output_base
    assert stage_root.name.startswith(".epr-oh-staging-")
    assert origin_paths.origin_file.read_bytes() == b"opju"
    assert origin_paths.figure_tif.read_bytes() == b"tif"
    assert origin_paths.preview_png.read_bytes() == b"png"


def test_epr_overlay_command_preflights_report_before_group_outputs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    report = output_base / "reports" / "epr_overlay_report.json"
    report.parent.mkdir(parents=True)
    report.write_text("existing report\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="force=True"):
        run_epr_overlay(project, EprOverlayOptions(reference_dir=ref, group="OH"))

    assert report.read_text(encoding="utf-8") == "existing report\n"
    assert not (output_base / "processed_data" / "EPR" / "epr_oh_overlay_processed.csv").exists()


def test_epr_overlay_command_atomically_replaces_hardlinked_report_on_force(tmp_path: Path, monkeypatch) -> None:
    import src.core.epr_overlay as epr_overlay

    read_paths = []
    read_export = epr_overlay.read_verified_jeol_export_series

    def counted_read(path):
        read_paths.append(path)
        return read_export(path)

    monkeypatch.setattr(epr_overlay, "read_verified_jeol_export_series", counted_read)
    project = tmp_path / "project"
    project.mkdir()
    ref = tmp_path / "refs"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])
    output_base = default_output_root(project)
    report = output_base / "reports" / "epr_overlay_report.json"
    report.parent.mkdir(parents=True)
    hardlink_source = tmp_path / "report_source.json"
    hardlink_source.write_text('{"preserve": true}\n', encoding="utf-8")
    os.link(hardlink_source, report)

    code = run_epr_overlay(
        project,
        EprOverlayOptions(reference_dir=ref, group="OH", force=True),
    )

    assert code == 0
    assert hardlink_source.read_text(encoding="utf-8") == '{"preserve": true}\n'
    assert json.loads(report.read_text(encoding="utf-8"))["command"] == "epr-overlay"
    assert os.stat(hardlink_source).st_ino != os.stat(report).st_ino
    assert sorted(path.name for path in read_paths) == ["BC-OH-light2.xlsx", "BOBC-OH-light1.xlsx", "CWO-OH-light2.xlsx"]


def test_epr_overlay_commit_rolls_back_all_previous_files_when_second_install_fails(
    tmp_path: Path,
) -> None:
    """A partial package install must not leave a mixed old/new EPR product."""
    output_root = tmp_path / "output"
    stage_root = output_root / ".stage"
    final_first = output_root / "processed_data" / "first.csv"
    final_second = output_root / "metadata" / "second.json"
    staged_first = stage_root / "processed_data" / "first.csv"
    staged_second = stage_root / "metadata" / "second.json"
    for path, content in (
        (final_first, b"old first\n"),
        (final_second, b"old second\n"),
        (staged_first, b"new first\n"),
        (staged_second, b"new second\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    real_replace = os.replace
    installs = 0

    def fail_second_install(source: Path, target: Path) -> None:
        nonlocal installs
        if target in (final_first, final_second) and source in (staged_first, staged_second):
            installs += 1
            if installs == 2:
                raise OSError("injected second package install failure")
        real_replace(source, target)

    with patch("src.core.epr_overlay._atomic_replace_epr_overlay", side_effect=fail_second_install):
        with pytest.raises(RuntimeError, match="previous outputs were restored"):
            epr_overlay._commit_staged_epr_overlay_files(
                ((staged_first, final_first), (staged_second, final_second)),
                deletion_targets=(),
                replace_existing_targets=(final_first, final_second),
                output_root=output_root,
                stage_root=stage_root,
                force=True,
            )

    assert final_first.read_bytes() == b"old first\n"
    assert final_second.read_bytes() == b"old second\n"


def test_epr_overlay_report_commit_rolls_back_both_reports_when_second_install_fails(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    json_path = output_root / "reports" / "epr_overlay_report.json"
    markdown_path = output_root / "reports" / "epr_overlay_report.md"
    json_path.parent.mkdir(parents=True)
    json_path.write_text('{"old": true}\n', encoding="utf-8")
    markdown_path.write_text("old report\n", encoding="utf-8")

    real_replace = os.replace
    installs = 0

    def fail_second_report_install(source: Path, target: Path) -> None:
        nonlocal installs
        if target in (json_path, markdown_path) and ".epr-overlay.tmp" in source.name:
            installs += 1
            if installs == 2:
                raise OSError("injected second report install failure")
        real_replace(source, target)

    with patch("src.core.epr_overlay.os.replace", side_effect=fail_second_report_install):
        with pytest.raises(OSError, match="injected second report install failure"):
            epr_overlay._write_reports_atomically(
                tmp_path,
                json_path,
                markdown_path,
                {
                    "command": "epr-overlay",
                    "reference_dir": "refs",
                    "baseline_correction": "mean",
                    "normalization": "none",
                    "smoothing": "none",
                    "background_subtraction": "none",
                    "offset_rule": "fixed",
                    "items": [],
                },
                output_root,
                force=True,
            )

    assert json_path.read_text(encoding="utf-8") == '{"old": true}\n'
    assert markdown_path.read_text(encoding="utf-8") == "old report\n"
