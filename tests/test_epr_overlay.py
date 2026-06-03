from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook

from src.core.epr_overlay import build_epr_condition_overlay


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
    with Path(result["processed_csv"]).open(encoding="utf-8", newline="") as handle:
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
