from pathlib import Path

import openpyxl
import pytest

from src.cli import build_parser
from src.core.gc_calibration import read_selected_gc_calibrations, run_gc_calibration


def workbook(tmp_path, values=None):
    path = tmp_path / "selected.xlsx"
    w = openpyxl.Workbook()
    s = w.active
    s.title = "selected"
    s.append(["A", None, None, "B"])
    s.append(["Concentration (mM)", "Peak area", None, "浓度 (mM)", "实测峰面积"])
    for x, y in (values or [(1, 12), (2, 22), (3, 32)]):
        s.append([x, y, None, x, 2 * y if isinstance(y, (int, float)) else y])
    w.save(path)
    return path


def test_selected_blocks_keep_all_values_and_cell_provenance(tmp_path):
    path = workbook(tmp_path)
    curves = read_selected_gc_calibrations(path, "selected")
    assert [c["analyte"] for c in curves] == ["A", "B"]
    assert curves[0]["slope_candidate"] == 10
    assert curves[0]["intercept_candidate"] == 2
    assert curves[0]["r_squared"] == 1
    assert curves[0]["points"][0]["area_cell"] == "B3"
    assert curves[1]["points"][0]["area_cell"] == "E3"
    assert curves[1]["slope_candidate"] == 20


@pytest.mark.parametrize("values", [[(1, 2), (2, None), (3, 4)], [(1, 2), (1, 3), (1, 4)], [(1, 2), (2, 2), (3, 2)], [(1, 2), (2, -1), (3, 4)]])
def test_invalid_points_fail_without_subsetting(tmp_path, values):
    with pytest.raises(ValueError):
        read_selected_gc_calibrations(workbook(tmp_path, values), "selected")


def test_missing_explicit_sheet_fails(tmp_path):
    with pytest.raises(ValueError, match="sheet does not exist"):
        read_selected_gc_calibrations(workbook(tmp_path), "other")


def test_analyte_names_left_of_same_row_headers(tmp_path):
    path = tmp_path / "same_row.xlsx"
    w = openpyxl.Workbook()
    s = w.active
    s.title = "selected"
    s.append(["DHIQ", "浓度 (mM)", "峰面积", "IQ", "浓度 (mM)", "峰面积"])
    for x in [1, 2, 3]:
        s.append([None, x, 10 * x, None, x, 20 * x])
    s.append([None] * 6)
    s.append(["斜率", 10, None, "斜率", 20])
    w.save(path)
    curves = read_selected_gc_calibrations(path, "selected")
    assert [c["analyte"] for c in curves] == ["DHIQ", "IQ"]
    assert [c["point_count"] for c in curves] == [3, 3]
    assert curves[0]["points"][0]["area_cell"] == "C2"


def test_data_only_outputs_and_source_preserved(tmp_path):
    project = Path(__file__).resolve().parents[1]
    source = workbook(tmp_path)
    before = source.read_bytes()
    output = tmp_path / "outputs"
    result = run_gc_calibration(project, source=source, sheet_name="selected", output_root=output,
                               selection_note="User supplied selected standards")
    assert result["processing_status"] == "processed_no_origin"
    assert result["origin_launched"] is False
    assert result["manual_check_required"] is True
    assert source.read_bytes() == before
    assert len(list(output.rglob("*_processed.csv"))) == 2
    assert len(list(output.rglob("metadata.json"))) == 1
    assert not list(output.rglob("*.opju"))
    assert not list(output.rglob("*.tif"))


def test_dedicated_cli_requires_provenance():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["gc-calibration", "--source", "x.xlsx", "--sheet", "selected"])
