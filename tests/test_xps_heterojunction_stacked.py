from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

import pandas as pd

from src.cli import main
from src.core.xps_heterojunction import (
    XpsHeterojunctionOptions,
    _comparison_peak_details,
    _comparison_x_axis_range,
    _stacked_plot_rows,
    build_comparison_plan,
    load_xps_fit_workbooks,
    run_xps_heterojunction_stacked,
    XpsComparison,
    XpsFitRecord,
    _build_direct_origin_xps_script,
)


def _write_xps_workbook(path: Path, sheets: dict[str, list[str]]) -> None:
    with pd.ExcelWriter(path) as writer:
        for sheet_name, components in sheets.items():
            rows = [["" for _ in range(8)] for _ in range(14)]
            header = ["Binding Energy (E)", *components, "Backgnd.", "Envelope", "Residuals"]
            units = ["eV", *["Counts / s" for _ in components], "Counts / s", "Counts / s", "Counts / s"]
            data = [
                [168.0, 10.0, *([3.0] * (len(components) - 1)), 1.0, 9.5, 0.5],
                [167.5, 40.0, *([12.0] * (len(components) - 1)), 2.0, 38.0, 2.0],
                [167.0, 12.0, *([4.0] * (len(components) - 1)), 1.0, 11.0, 1.0],
            ]
            frame = pd.DataFrame([*rows, header, units, *data])
            frame.to_excel(writer, sheet_name=sheet_name, header=False, index=False)


def test_load_xps_fit_workbooks_extracts_fit_components_and_metadata(tmp_path: Path) -> None:
    bobc = tmp_path / "BOBCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})

    records, manual_review = load_xps_fit_workbooks({"BOBC": [bobc]})

    assert manual_review == []
    assert len(records) == 1
    record = records[0]
    assert record.sample == "BOBC"
    assert record.element == "Bi"
    assert record.region == "Bi4f"
    assert record.raw_label == "Bi4f"
    assert record.background_label == "Backgnd."
    assert record.envelope_label == "Envelope"
    assert record.component_labels == ["Bi4f Scan A"]
    assert record.data[0]["binding_energy_eV"] == 168.0
    assert record.data[1]["raw_intensity"] == 40.0


def test_build_comparison_plan_uses_heterojunction_binary_pairs_and_splits_oxygen(tmp_path: Path) -> None:
    bobc = tmp_path / "BOBCfit.xlsx"
    cwo = tmp_path / "CWOfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"], "O1s Scan": ["O1s", "O1s Scan A"]})
    _write_xps_workbook(cwo, {"W4f Scan": ["W4f", "W4f Scan A"], "O1s Scan": ["O1s", "O1s Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"], "W4f Scan": ["W4f", "W4f Scan A"], "O1s Scan": ["O1s", "O1s Scan A"]})
    records, manual_review = load_xps_fit_workbooks({"BOBC": [bobc], "CWO": [cwo], "BC": [bc]})

    plan = build_comparison_plan(records, manual_review, XpsHeterojunctionOptions(output_dir=tmp_path / "out", with_origin=False))

    names = [item.name for item in plan.comparisons]
    assert names == [
        "XPS_Bi_BOBC_vs_BC_stacked",
        "XPS_O_BOBC_vs_BC_stacked",
        "XPS_O_CWO_vs_BC_stacked",
        "XPS_W_CWO_vs_BC_stacked",
    ]
    assert "XPS_O_BOBC_CWO_BC_stacked" not in names
    assert all([item.sample_a, item.sample_b] in [["BOBC", "BC"], ["CWO", "BC"]] for item in plan.comparisons)
    assert plan.manual_review == []


def test_build_comparison_plan_reports_missing_bc_instead_of_guessing(tmp_path: Path) -> None:
    bobc = tmp_path / "BOBCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    records, manual_review = load_xps_fit_workbooks({"BOBC": [bobc], "BC": []})

    plan = build_comparison_plan(records, manual_review, XpsHeterojunctionOptions(output_dir=tmp_path / "out", with_origin=False))

    assert plan.comparisons == []
    assert any(item["reason"] == "missing_bc_counterpart" and item["element"] == "Bi" for item in plan.manual_review)


def test_cu2p_plot_keeps_five_components_and_smooth_gradient_columns(tmp_path: Path) -> None:
    cwo = tmp_path / "CWOfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    components = ["Cu2p", "Cu2p Scan A", "Cu2p Scan B", "Cu2p Scan C", "Cu2p Scan D", "Cu2p Scan E"]
    _write_xps_workbook(cwo, {"Cu2p Scan": components})
    _write_xps_workbook(bc, {"Cu2p Scan": components})
    records, manual_review = load_xps_fit_workbooks({"CWO": [cwo], "BC": [bc]})
    plan = build_comparison_plan(records, manual_review, XpsHeterojunctionOptions(output_dir=tmp_path / "out", with_origin=False))

    headers, _rows = _stacked_plot_rows(plan.comparisons[0])

    cwo_component_lines = [header for header in headers if header.startswith("CWO component") and header.endswith(" line")]
    bc_component_lines = [header for header in headers if header.startswith("BC component") and header.endswith(" line")]
    assert len(cwo_component_lines) == 5
    assert len(bc_component_lines) == 5
    assert any("fill upper 16" in header for header in headers)
    assert cwo_component_lines[0].split(" color ", 1)[1].split(" ", 1)[0] == bc_component_lines[0].split(" color ", 1)[1].split(" ", 1)[0]


def test_cu2p_peak_annotations_are_omitted(tmp_path: Path) -> None:
    cwo = tmp_path / "CWOfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    components = ["Cu2p", "Cu2p Scan A", "Cu2p Scan B", "Cu2p Scan C", "Cu2p Scan D", "Cu2p Scan E"]
    _write_xps_workbook(cwo, {"Cu2p Scan": components})
    _write_xps_workbook(bc, {"Cu2p Scan": components})
    records, manual_review = load_xps_fit_workbooks({"CWO": [cwo], "BC": [bc]})

    plan = build_comparison_plan(records, manual_review, XpsHeterojunctionOptions(output_dir=tmp_path / "out", with_origin=False))

    peak_details = _comparison_peak_details(plan.comparisons[0])
    assert peak_details == []


def test_comparison_x_axis_range_uses_overlap_range(tmp_path: Path) -> None:
    record_a = XpsFitRecord(
        sample="BOBC",
        element="Bi",
        region="Bi4f",
        source_file=tmp_path / "a.xlsx",
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=[],
        data=[
            {"binding_energy_eV": 900.0, "raw_intensity": 12.0},
            {"binding_energy_eV": 800.0, "raw_intensity": 10.0},
            {"binding_energy_eV": 700.0, "raw_intensity": 8.0},
        ],
    )
    record_b = XpsFitRecord(
        sample="BC",
        element="Bi",
        region="Bi4f",
        source_file=tmp_path / "b.xlsx",
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=[],
        data=[
            {"binding_energy_eV": 850.0, "raw_intensity": 20.0},
            {"binding_energy_eV": 800.0, "raw_intensity": 18.0},
            {"binding_energy_eV": 750.0, "raw_intensity": 16.0},
        ],
    )
    comparison = XpsComparison(
        name="XPS_Bi_BOBC_vs_BC_stacked",
        element="Bi",
        sample_a="BOBC",
        sample_b="BC",
        record_a=record_a,
        record_b=record_b,
    )
    x_from, x_to = _comparison_x_axis_range(comparison, [900.0, 800.0, 700.0, 850.0, 750.0])
    assert x_from == 850.0
    assert x_to == 750.0


def test_comparison_x_axis_range_prefers_signal_region_overlap(tmp_path: Path) -> None:
    record_a = XpsFitRecord(
        sample="BOBC",
        element="Bi",
        region="Bi4f",
        source_file=tmp_path / "a.xlsx",
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=[],
        data=[
            {"binding_energy_eV": 100.0, "raw_intensity": 1.0},
            {"binding_energy_eV": 90.0, "raw_intensity": 1.0},
            {"binding_energy_eV": 80.0, "raw_intensity": 12.0},
            {"binding_energy_eV": 70.0, "raw_intensity": 11.0},
            {"binding_energy_eV": 60.0, "raw_intensity": 10.0},
            {"binding_energy_eV": 50.0, "raw_intensity": 9.0},
        ],
    )
    record_b = XpsFitRecord(
        sample="BC",
        element="Bi",
        region="Bi4f",
        source_file=tmp_path / "b.xlsx",
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=[],
        data=[
            {"binding_energy_eV": 100.0, "raw_intensity": 1.0, "background": 1.0, "envelope": 1.0},
            {"binding_energy_eV": 90.0, "raw_intensity": 1.0, "background": 1.0, "envelope": 1.0},
            {"binding_energy_eV": 80.0, "raw_intensity": 12.0, "background": 5.0, "envelope": 4.0},
            {"binding_energy_eV": 70.0, "raw_intensity": 11.0, "background": 4.0, "envelope": 3.5},
            {"binding_energy_eV": 60.0, "raw_intensity": 10.0, "background": 4.0, "envelope": 3.0},
            {"binding_energy_eV": 50.0, "raw_intensity": 9.0, "background": 4.0, "envelope": 3.0},
        ],
    )
    comparison = XpsComparison(
        name="XPS_Bi_BOBC_vs_BC_stacked",
        element="Bi",
        sample_a="BOBC",
        sample_b="BC",
        record_a=record_a,
        record_b=record_b,
    )
    x_from, x_to = _comparison_x_axis_range(comparison, [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 100.0, 90.0, 80.0, 70.0, 60.0, 50.0])
    assert x_from == 80.0
    assert x_to == 50.0


def test_run_xps_heterojunction_stacked_dry_run_writes_reports_and_tables(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})

    result = run_xps_heterojunction_stacked(
        project_root,
        {"BOBC": [bobc], "CWO": [], "BC": [bc]},
        XpsHeterojunctionOptions(output_dir=project_root / "output" / "xps_heterojunction_stacked", with_origin=False),
    )

    assert result["will_launch_origin"] is False
    assert result["comparison_count"] == 1
    output = project_root / "output" / "xps_heterojunction_stacked"
    assert (output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked.csv").exists()
    plot_csv = output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked_origin_plot.csv"
    assert "BOBC component 1" in plot_csv.read_text(encoding="utf-8").splitlines()[0]
    assert (output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked_peak_annotations.csv").exists()
    assert (output / "reports" / "xps_heterojunction_stacked_summary.md").exists()
    assert (output / "reports" / "xps_heterojunction_stacked_summary.csv").exists()
    assert (output / "reports" / "manual_review.csv").exists()
    summary = (output / "reports" / "xps_heterojunction_stacked_summary.md").read_text(encoding="utf-8")
    assert "non-in-situ fitted XPS heterojunction stacked comparisons" in summary
    assert "no mechanism conclusion is generated" in summary


def test_run_xps_heterojunction_stacked_with_origin_updates_artifact_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})

    def fake_export(_project_root: Path, comparison, plot_csv: Path, output_dirs: dict[str, Path], peak_details):
        origin = output_dirs["origin_projects"] / f"{comparison.name}.opju"
        tif = output_dirs["figures_tif"] / f"{comparison.name}.tif"
        png = output_dirs["figures_preview"] / f"{comparison.name}.png"
        for path in (origin, tif, png):
            path.write_text("artifact", encoding="utf-8")
        return {"ok": True, "origin_file": origin, "figure_tif": tif, "preview_png": png, "message": "fake"}

    with patch("src.core.xps_heterojunction._export_origin_for_comparison", side_effect=fake_export) as export:
        result = run_xps_heterojunction_stacked(
            project_root,
            {"BOBC": [bobc], "CWO": [], "BC": [bc]},
            XpsHeterojunctionOptions(output_dir=project_root / "output" / "xps_heterojunction_stacked", with_origin=True),
        )

    assert export.call_count == 1
    assert result["will_launch_origin"] is True
    figure = result["figures"][0]
    assert figure["status"] == "success"
    assert figure["origin_file"].endswith(".opju")
    assert figure["figure_tif"].endswith(".tif")
    assert figure["preview_png"].endswith(".png")


def test_direct_origin_xps_generated_script_compiles(tmp_path: Path) -> None:
    plot_csv = tmp_path / "plot.csv"
    plot_csv.write_text("binding_energy_eV,CWO measured,BC measured\n1,2,3\n", encoding="utf-8")

    def record(sample: str) -> XpsFitRecord:
        return XpsFitRecord(
            sample=sample,
            element="Cu",
            region="Cu2p",
            source_file=tmp_path / f"{sample}.xlsx",
            sheet_name="Cu2p",
            raw_label="measured",
            background_label="Backgnd.",
            envelope_label="Envelope",
            residual_label=None,
            component_labels=["c1"],
            data=[{"binding_energy_eV": 1.0, "raw_intensity": 2.0, "background": 0.5, "envelope": 1.5, "c1": 0.8}],
        )

    script = _build_direct_origin_xps_script(
        XpsComparison("XPS_Cu_CWO_vs_BC_stacked", "Cu", "CWO", "BC", record("CWO"), record("BC")),
        plot_csv,
        tmp_path / "out.opju",
        tmp_path / "out.png",
        tmp_path / "out.tif",
        "Graph1",
        [],
    )

    compile(script, "<generated_xps_origin_script>", "exec")


def test_cli_xps_heterojunction_stacked_dry_run_uses_explicit_sample_paths(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    monkeypatch.chdir(project_root)

    code = main(
        [
            "xps-heterojunction-stacked",
            "--bobc",
            str(bobc),
            "--bc",
            str(bc),
            "--dry-run",
        ]
    )

    assert code == 0
    assert (project_root / "output" / "xps_heterojunction_stacked" / "reports" / "xps_heterojunction_stacked_summary.md").exists()


def test_cli_xps_heterojunction_stacked_reports_missing_explicit_file_without_outputs(tmp_path: Path, project_root: Path) -> None:
    missing = tmp_path / "missing_bobc.xlsx"
    output_dir = project_root / "output" / f"_test_missing_xps_input_{tmp_path.name}"

    result = subprocess.run(
        [
            "D:\\Python\\python.exe",
            "run.py",
            "xps-heterojunction-stacked",
            "--bobc",
            str(missing),
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "explicit XPS input file does not exist" in result.stderr
    assert "missing_bobc.xlsx" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output_dir.exists()
