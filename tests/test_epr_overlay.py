from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook

from src.core.epr_overlay import EprOverlayOptions, build_epr_condition_overlay, run_epr_overlay
from src.core.project import default_output_root


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
    out = tmp_path / "run" / "EPR" / "processed_data"
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
    assert _result_path(tmp_path, result["processed_csv"]).parent == out
    assert _result_path(tmp_path, result["detail_csv"]).parent == out
    assert not Path(result["processed_csv"]).is_absolute()
    with _result_path(tmp_path, result["detail_csv"]).open(encoding="utf-8", newline="") as handle:
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
    out = tmp_path / "run" / "EPR" / "processed_data"
    ref.mkdir()
    _write_xlsx(ref / "BC-OH-light2.xlsx", [-1, 0, 1, 2])
    _write_xlsx(ref / "CWO-OH-light2.xlsx", [-10, 0, 10, 20])
    _write_xlsx(ref / "BOBC-OH-light1.xlsx", [-100, 0, 100, 200])

    result = build_epr_condition_overlay(tmp_path, ref, "OH", with_origin=False, output_data_dir=out)

    metadata = _result_path(tmp_path, result["metadata"])
    assert metadata == out.parent / "metadata" / "epr_oh_overlay" / "metadata.json"
    recorded = json.loads(metadata.read_text(encoding="utf-8"))
    assert recorded["dataset_id"] == "epr_oh_overlay"
    assert recorded["metadata_path"] == "run/EPR/metadata/epr_oh_overlay/metadata.json"
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
