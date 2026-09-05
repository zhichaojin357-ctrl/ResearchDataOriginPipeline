from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

import src.core.file_utils as file_utils
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
    _cleanup_failed_renderer_origin,
    _export_origin_for_comparison,
    _terminate_owned_origin_processes,
    _validated_origin_artifacts,
)
from src.core.project import default_output_root


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


def test_load_xps_fit_workbooks_extracts_fit_components_and_metadata(tmp_path: Path, monkeypatch) -> None:
    bobc = tmp_path / "BOBCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"], "O1s Scan": ["O1s", "O1s Scan A"]})
    opened_workbooks = []
    excel_file = pd.ExcelFile

    def counted_open(path, *args, **kwargs):
        opened_workbooks.append(path)
        return excel_file(path, *args, **kwargs)

    monkeypatch.setattr(pd, "ExcelFile", counted_open)
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: pytest.fail("sheets must reuse the already open workbook"))

    records, manual_review = load_xps_fit_workbooks({"BOBC": [bobc]})

    assert manual_review == []
    assert len(records) == 2
    assert opened_workbooks == [bobc]
    assert records[1].element == "O"
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


@pytest.mark.parametrize("product_key", ["XPS_in_situ", "XPS_non_in_situ"])
@pytest.mark.parametrize("compact_output", [False, True])
def test_template_xps_preparation_reuses_selected_workbook_records(
    tmp_path: Path, monkeypatch, product_key: str, compact_output: bool
) -> None:
    import csv

    import src.core.template_product_builder as builder
    import src.core.template_product_common as common

    names = ["BOBCfit.xlsx", "BC Dark.xlsx", "BC Light.xlsx"] if product_key == "XPS_in_situ" else ["BOBCfit.xlsx", "BCfit.xlsx"]
    paths = [tmp_path / name for name in names]
    for path in paths:
        _write_xps_workbook(path, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A", "Bi4f Scan B"]})
    pairing = common.TargetPairing(product_key, product_key, "", "test", paths, "test", tmp_path / "reference.json")
    expected_headers, expected_rows, expected_labels = common._build_processed_plot_table(
        pairing, xps_component_fill_mode="template_line_fill"
    )
    loads = []
    load_workbooks = builder.load_xps_fit_workbooks

    def counted_load(sample_files):
        loads.append(sample_files)
        return load_workbooks(sample_files)

    monkeypatch.setattr(builder, "load_xps_fit_workbooks", counted_load)
    monkeypatch.setattr(common, "load_xps_fit_workbooks", lambda *args: pytest.fail("table and Origin plan must share selected XPS records"))
    product, extra = builder.prepare_template_product(
        tmp_path / "run",
        pairing,
        builder.TemplateCandidate(product_key, pairing.reference_opju, "embedded_template_snapshot", plot_count=len(expected_headers) - 1),
        xps_smooth_gradient_fill=True,
        compact_output=compact_output,
    )

    with product.processed_data.open(encoding="utf-8", newline="") as handle:
        written = list(csv.reader(handle))
    assert written == [expected_headers, *[["" if value is None else str(value) for value in row] for row in expected_rows]]
    assert product.graph_title == expected_labels["title"]
    assert extra["origin_processing"]["source_files"] == [str(path) for path in paths]
    assert len(loads) == 1
    assert bool(list(product.type_root.rglob("*_origin_raw_input.csv"))) is (not compact_output)


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


def test_binding_energy_window_assignments_are_explicit_manual_check_candidates(
    tmp_path: Path,
) -> None:
    def record(sample: str, peak_binding_energy: float) -> XpsFitRecord:
        return XpsFitRecord(
            sample=sample,
            element="Bi",
            region="Bi4f",
            source_file=tmp_path / f"{sample}.xlsx",
            sheet_name="Bi4f Scan",
            raw_label="Bi4f",
            background_label=None,
            envelope_label=None,
            residual_label=None,
            component_labels=[],
            data=[
                {
                    "binding_energy_eV": peak_binding_energy + 0.5,
                    "raw_intensity": 1.0,
                },
                {
                    "binding_energy_eV": peak_binding_energy,
                    "raw_intensity": 5.0,
                },
                {
                    "binding_energy_eV": peak_binding_energy - 0.5,
                    "raw_intensity": 1.0,
                },
            ],
        )

    comparison = XpsComparison(
        name="XPS_Bi_BOBC_vs_BC_stacked",
        element="Bi",
        sample_a="BOBC",
        sample_b="BC",
        record_a=record("BOBC", 164.0),
        record_b=record("BC", 159.0),
    )

    peak_details = _comparison_peak_details(comparison)

    assert {item["peak_assignment"] for item in peak_details} == {
        "Bi 4f5/2",
        "Bi 4f7/2",
    }
    assert all(
        item["peak_assignment_candidate"] == item["peak_assignment"]
        for item in peak_details
    )
    assert {
        item["peak_assignment_method"] for item in peak_details
    } == {"binding_energy_window_candidate"}
    assert all(
        item["peak_assignment_manual_check_required"] is True
        for item in peak_details
    )


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
        XpsHeterojunctionOptions(output_dir=default_output_root(project_root) / "xps_heterojunction_stacked", with_origin=False),
    )

    assert result["will_launch_origin"] is False
    assert result["comparison_count"] == 1
    output = default_output_root(project_root) / "xps_heterojunction_stacked"
    assert (output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked.csv").exists()
    plot_csv = output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked_origin_plot.csv"
    assert "BOBC component 1" in plot_csv.read_text(encoding="utf-8").splitlines()[0]
    peak_table = output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked_peak_annotations.csv"
    assert peak_table.exists()
    peak_header = peak_table.read_text(encoding="utf-8-sig").splitlines()[0].split(",")
    assert "peak_assignment" in peak_header
    assert "peak_assignment_candidate" in peak_header
    assert "peak_assignment_method" in peak_header
    assert "peak_assignment_manual_check_required" in peak_header
    assert (output / "reports" / "xps_heterojunction_stacked_summary.md").exists()
    assert (output / "reports" / "xps_heterojunction_stacked_summary.csv").exists()
    assert (output / "reports" / "manual_review.csv").exists()
    metadata_path = output / "metadata" / "XPS_Bi_BOBC_vs_BC_stacked" / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["metadata_path"] == "metadata/XPS_Bi_BOBC_vs_BC_stacked/metadata.json"
    assert result["figures"][0]["metadata"] == "metadata/XPS_Bi_BOBC_vs_BC_stacked/metadata.json"
    assert not (output / "metadata" / "XPS_Bi_BOBC_vs_BC_stacked_metadata.json").exists()
    summary = (output / "reports" / "xps_heterojunction_stacked_summary.md").read_text(encoding="utf-8")
    assert "non-in-situ fitted XPS heterojunction stacked comparisons" in summary
    assert "no mechanism conclusion is generated" in summary


def test_xps_preflight_blocks_all_writes_without_force_and_force_overwrites(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    output = default_output_root(project_root) / "xps_heterojunction_stacked"
    existing_summary = output / "reports" / "xps_heterojunction_stacked_summary.json"
    existing_summary.parent.mkdir(parents=True)
    existing_summary.write_bytes(b"preserve")

    with pytest.raises(FileExistsError, match="force=True"):
        run_xps_heterojunction_stacked(
            project_root,
            {"BOBC": [bobc], "CWO": [], "BC": [bc]},
            XpsHeterojunctionOptions(
                output_dir=output,
                with_origin=False,
                force=False,
            ),
        )

    assert existing_summary.read_bytes() == b"preserve"
    assert not (
        output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked.csv"
    ).exists()
    assert not (output / "metadata").exists()

    result = run_xps_heterojunction_stacked(
        project_root,
        {"BOBC": [bobc], "CWO": [], "BC": [bc]},
        XpsHeterojunctionOptions(
            output_dir=output,
            with_origin=False,
            force=True,
        ),
    )

    assert result["comparison_count"] == 1
    assert json.loads(existing_summary.read_text(encoding="utf-8"))["comparison_count"] == 1


def test_xps_force_with_existing_origin_preserves_every_existing_product(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    output = default_output_root(project_root) / "xps_heterojunction_stacked"
    protected_products = {
        output / "origin_projects" / "XPS_Bi_BOBC_vs_BC_stacked.opju": b"old opju",
        output / "figures_tif" / "XPS_Bi_BOBC_vs_BC_stacked.tif": b"old tif",
        output
        / "origin_projects"
        / "origin_jobs"
        / "XPS_Bi_BOBC_vs_BC_stacked.png": b"old png",
        output
        / "processed_tables"
        / "XPS_Bi_BOBC_vs_BC_stacked.csv": b"old processed table",
    }
    for path, content in protected_products.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    with patch(
        "src.core.xps_heterojunction._origin_process_ids",
        return_value={9001},
    ):
        with pytest.raises(RuntimeError, match="before any existing product"):
            run_xps_heterojunction_stacked(
                project_root,
                {"BOBC": [bobc], "CWO": [], "BC": [bc]},
                XpsHeterojunctionOptions(
                    output_dir=output,
                    with_origin=True,
                    force=True,
                ),
            )

    for path, content in protected_products.items():
        assert path.read_bytes() == content
    assert not (output / "metadata").exists()
    assert not (output / "reports").exists()


@pytest.mark.parametrize(
    "readiness_message",
    (
        "Origin disabled by RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN=1",
        "originpro unavailable: import failed",
        "win32com unavailable: import failed",
    ),
)
def test_xps_force_with_unavailable_origin_preserves_existing_package(
    tmp_path: Path,
    readiness_message: str,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    output = default_output_root(project_root) / "xps_heterojunction_stacked"
    protected_products = {
        output / "origin_projects" / "XPS_Bi_BOBC_vs_BC_stacked.opju": b"old opju",
        output / "figures_tif" / "XPS_Bi_BOBC_vs_BC_stacked.tif": b"old tif",
        output
        / "origin_projects"
        / "origin_jobs"
        / "XPS_Bi_BOBC_vs_BC_stacked.png": b"old png",
        output
        / "processed_tables"
        / "XPS_Bi_BOBC_vs_BC_stacked.csv": b"old processed table",
        output
        / "metadata"
        / "XPS_Bi_BOBC_vs_BC_stacked"
        / "metadata.json": b"old metadata",
        output
        / "reports"
        / "xps_heterojunction_stacked_summary.json": b"old report",
    }
    for path, content in protected_products.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    with patch(
        "src.core.xps_heterojunction._origin_process_ids",
        return_value=set(),
    ):
        with patch(
            "src.core.xps_heterojunction.check_origin_available",
            return_value=(False, readiness_message),
        ) as readiness:
            with pytest.raises(RuntimeError, match="readiness check failed"):
                run_xps_heterojunction_stacked(
                    project_root,
                    {"BOBC": [bobc], "CWO": [], "BC": [bc]},
                    XpsHeterojunctionOptions(
                        output_dir=output,
                        with_origin=True,
                        force=True,
                    ),
                )

    readiness.assert_called_once_with()
    for path, content in protected_products.items():
        assert path.read_bytes() == content
    assert {
        path.relative_to(output)
        for path in output.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(output)
        for path in protected_products
    }


def test_xps_force_rejects_reparse_output_leaf_before_unlink(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    output = default_output_root(project_root) / "xps_heterojunction_stacked"
    unsafe_leaf = output / "reports" / "xps_heterojunction_stacked_summary.json"
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
        run_xps_heterojunction_stacked(
            project_root,
            {"BOBC": [bobc], "CWO": [], "BC": [bc]},
            XpsHeterojunctionOptions(
                output_dir=output,
                with_origin=False,
                force=True,
            ),
        )

    assert unsafe_leaf.read_bytes() == b"must-not-unlink"
    assert not (
        output / "processed_tables" / "XPS_Bi_BOBC_vs_BC_stacked.csv"
    ).exists()


def test_xps_direct_api_rejects_input_under_output_before_writing(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    output = default_output_root(project_root) / "xps_heterojunction_stacked"
    output.mkdir(parents=True)
    bobc = output / "BOBCfit.xlsx"
    bc = output / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})

    with pytest.raises(ValueError, match="overlaps protected input"):
        run_xps_heterojunction_stacked(
            project_root,
            {"BOBC": [bobc], "CWO": [], "BC": [bc]},
            XpsHeterojunctionOptions(output_dir=output, with_origin=False),
        )

    assert not (output / "reports").exists()
    assert not (output / "processed_tables").exists()


def test_run_xps_heterojunction_stacked_with_origin_updates_required_artifact_paths(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    _write_xps_workbook(bobc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})
    _write_xps_workbook(bc, {"Bi4f Scan": ["Bi4f", "Bi4f Scan A"]})

    def fake_export(
        _project_root: Path,
        comparison,
        plot_csv: Path,
        output_dirs: dict[str, Path],
        peak_details,
        *,
        force: bool,
    ):
        assert force is False
        assert "figures_preview" not in output_dirs
        origin = output_dirs["origin_projects"] / f"{comparison.name}.opju"
        tif = output_dirs["figures_tif"] / f"{comparison.name}.tif"
        preview = output_dirs["origin_projects"] / "origin_jobs" / f"{comparison.name}.png"
        for path in (origin, tif, preview):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("artifact", encoding="utf-8")
        return {
            "ok": True,
            "origin_file": origin,
            "figure_tif": tif,
            "preview_png": preview,
            "message": "fake",
            "tif_resolution": {
                "requested_dpi": 600,
                "effective_dpi_x": 600.0,
                "effective_dpi_y": 600.0,
            },
        }

    with patch("src.core.xps_heterojunction._origin_process_ids", return_value=set()):
        with patch("src.core.xps_heterojunction.check_origin_available", return_value=(True, "ok")):
            with patch("src.core.xps_heterojunction._export_origin_for_comparison", side_effect=fake_export) as export:
                result = run_xps_heterojunction_stacked(
                    project_root,
                    {"BOBC": [bobc], "CWO": [], "BC": [bc]},
                    XpsHeterojunctionOptions(output_dir=default_output_root(project_root) / "xps_heterojunction_stacked", with_origin=True),
                )

    assert export.call_count == 1
    assert result["will_launch_origin"] is True
    figure = result["figures"][0]
    assert figure["status"] == "success"
    assert figure["origin_file"].endswith(".opju")
    assert figure["figure_tif"].endswith(".tif")
    assert figure["preview_png"].endswith(".png")
    assert figure["tif_resolution_evidence"]["effective_dpi_x"] == 600.0
    metadata_path = (
        default_output_root(project_root)
        / "xps_heterojunction_stacked"
        / "metadata"
        / "XPS_Bi_BOBC_vs_BC_stacked"
        / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["tif_resolution_evidence"]["effective_dpi_y"] == 600.0


def test_xps_origin_success_requires_preview_png(tmp_path: Path) -> None:
    origin = tmp_path / "plot.opju"
    tif = tmp_path / "plot.tif"
    for path in (origin, tif):
        path.write_text("artifact", encoding="utf-8")

    checked = _validated_origin_artifacts({"ok": True, "origin_file": origin, "figure_tif": tif, "preview_png": None})

    assert checked["ok"] is False
    assert "preview_png" in checked["message"]


def test_cli_xps_with_origin_returns_failure_when_export_status_fails(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    bobc.write_text("placeholder", encoding="utf-8")
    bc.write_text("placeholder", encoding="utf-8")
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(
        "src.core.xps_heterojunction.run_xps_heterojunction_stacked",
        lambda *_args, **_kwargs: {"figures": [{"status": "origin_failed"}]},
    )

    code = main(["xps-heterojunction-stacked", "--bobc", str(bobc), "--bc", str(bc), "--with-origin"])

    assert code == 1


def test_cli_xps_returns_failure_when_no_figures_are_planned(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bobc = tmp_path / "BOBCfit.xlsx"
    bc = tmp_path / "BCfit.xlsx"
    bobc.write_text("placeholder", encoding="utf-8")
    bc.write_text("placeholder", encoding="utf-8")
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(
        "src.core.xps_heterojunction.run_xps_heterojunction_stacked",
        lambda *_args, **_kwargs: {"figures": []},
    )

    code = main(["xps-heterojunction-stacked", "--bobc", str(bobc), "--bc", str(bc), "--dry-run"])

    assert code == 1


def test_cli_xps_rejects_output_directory_that_contains_an_input_file(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    bobc = input_root / "BOBCfit.xlsx"
    bc = input_root / "BCfit.xlsx"
    bobc.write_text("placeholder", encoding="utf-8")
    bc.write_text("placeholder", encoding="utf-8")
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(
        "src.core.xps_heterojunction.run_xps_heterojunction_stacked",
        lambda *_args, **_kwargs: {"figures": [{"status": "planned"}]},
    )

    with pytest.raises(ValueError, match="overlaps protected input"):
        main(
            [
                "xps-heterojunction-stacked",
                "--bobc",
                str(bobc),
                "--bc",
                str(bc),
                "--dry-run",
                "--output-dir",
                str(input_root),
            ]
        )


def test_cli_xps_allows_an_independent_external_output_directory(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    bobc = input_root / "BOBCfit.xlsx"
    bc = input_root / "BCfit.xlsx"
    bobc.write_text("placeholder", encoding="utf-8")
    bc.write_text("placeholder", encoding="utf-8")
    external_output = tmp_path / "external-output"
    captured: dict[str, object] = {}

    def fake_run(_project_root: Path, _sample_files, options: XpsHeterojunctionOptions, **_kwargs) -> dict:
        captured["output_dir"] = options.output_dir
        captured["force"] = options.force
        return {"figures": [{"status": "planned"}]}

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.core.xps_heterojunction.run_xps_heterojunction_stacked", fake_run)

    code = main(
        [
            "xps-heterojunction-stacked",
            "--bobc",
            str(bobc),
            "--bc",
            str(bc),
            "--dry-run",
            "--output-dir",
            str(external_output),
            "--force",
        ]
    )

    assert code == 0
    assert captured["output_dir"] == external_output
    assert captured["force"] is True


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
        tmp_path / "origin_lifecycle.json",
        "Graph1",
        [],
    )

    compile(script, "<generated_xps_origin_script>", "exec")
    assert 'graph.save_fig(payload["preview_png"]' in script
    assert 'graph.save_fig(payload["figure_tif"]' not in script
    assert '"figure_tif"' not in script
    assert '"origin_lifecycle_path"' in script
    assert '"owned_origin_pids"' in script
    assert '"remaining_owned_pids"' in script
    assert "Origin lifecycle finalization failed; product acceptance is blocked" in script


def test_xps_origin_export_reopens_saved_opju_for_native_tif(tmp_path: Path) -> None:
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
            background_label=None,
            envelope_label=None,
            residual_label=None,
            component_labels=[],
            data=[{"binding_energy_eV": 1.0, "raw_intensity": 2.0}],
        )

    comparison = XpsComparison(
        "XPS_Cu_CWO_vs_BC_stacked",
        "Cu",
        "CWO",
        "BC",
        record("CWO"),
        record("BC"),
    )
    output_dirs = {
        "origin_projects": tmp_path / "origin_projects",
        "figures_tif": tmp_path / "figures_tif",
    }
    origin_file = output_dirs["origin_projects"] / f"{comparison.name}.opju"
    preview_png = output_dirs["origin_projects"] / "origin_jobs" / f"{comparison.name}.png"
    lifecycle_file = output_dirs["origin_projects"] / "origin_jobs" / f"{comparison.name}_origin_lifecycle.json"
    figure_tif = output_dirs["figures_tif"] / f"{comparison.name}.tif"
    call_order: list[str] = []

    def fake_run(*_args, **_kwargs):
        call_order.append("renderer_exited")
        origin_file.parent.mkdir(parents=True, exist_ok=True)
        preview_png.parent.mkdir(parents=True, exist_ok=True)
        origin_file.write_bytes(b"opju")
        preview_png.write_bytes(b"png")
        lifecycle_file.write_text(
            json.dumps(
                {
                    "baseline_origin_pids": [],
                    "owned_origin_pids": [4242],
                    "remaining_owned_pids": [],
                    "exit_ok": True,
                    "exit_error": "",
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_reexport(opju: Path, graph_page: str, tif: Path, *, dpi: int):
        call_order.append("reopened_opju")
        assert opju == origin_file
        assert graph_page
        assert tif == figure_tif
        assert dpi == 600
        assert not tif.exists()
        tif.parent.mkdir(parents=True, exist_ok=True)
        tif.write_bytes(b"native tif")
        return SimpleNamespace(as_dict=lambda: {"path": str(tif), "requested_dpi": 600})

    with patch("src.core.xps_heterojunction.check_origin_available", return_value=(True, "ok")):
        with patch("src.core.xps_heterojunction._origin_process_ids", return_value=set()):
            with patch("src.core.xps_heterojunction._run_xps_origin_renderer", side_effect=fake_run):
                with patch(
                    "src.core.xps_heterojunction.reexport_tif_from_reopened_opju",
                    side_effect=fake_reexport,
                ):
                    result = _export_origin_for_comparison(
                        tmp_path,
                        comparison,
                        plot_csv,
                        output_dirs,
                        [],
                    )

    assert result["ok"] is True
    assert result["figure_tif"] == figure_tif
    assert result["tif_resolution"] == {"requested_dpi": 600}
    assert call_order == ["renderer_exited", "reopened_opju"]
    assert not lifecycle_file.exists()


def test_xps_origin_export_refuses_pre_existing_origin_session(tmp_path: Path) -> None:
    plot_csv, comparison, output_dirs = _minimal_origin_export_case(tmp_path)
    project_root = tmp_path / "project"

    with patch(
        "src.core.xps_heterojunction._origin_process_ids",
        return_value={9001},
    ):
        with patch("src.core.xps_heterojunction.check_origin_available") as available:
            with patch("src.core.xps_heterojunction._run_xps_origin_renderer") as renderer:
                result = _export_origin_for_comparison(
                    project_root,
                    comparison,
                    plot_csv,
                    output_dirs,
                    [],
                )

    assert result["ok"] is False
    assert result["pre_existing_origin_pids"] == [9001]
    assert "already running" in result["message"]
    available.assert_not_called()
    renderer.assert_not_called()


def test_xps_origin_exit_failure_blocks_success_and_tif_reexport(tmp_path: Path) -> None:
    plot_csv, comparison, output_dirs = _minimal_origin_export_case(tmp_path)
    project_root = tmp_path / "project"
    origin_file = output_dirs["origin_projects"] / f"{comparison.name}.opju"
    job_dir = output_dirs["origin_projects"] / "origin_jobs"
    preview_png = job_dir / f"{comparison.name}.png"
    lifecycle_file = job_dir / f"{comparison.name}_origin_lifecycle.json"

    def fake_renderer(_job_script: Path):
        origin_file.parent.mkdir(parents=True, exist_ok=True)
        job_dir.mkdir(parents=True, exist_ok=True)
        origin_file.write_bytes(b"opju")
        preview_png.write_bytes(b"png")
        lifecycle_file.write_text(
            json.dumps(
                {
                    "baseline_origin_pids": [],
                    "owned_origin_pids": [5151],
                    "remaining_owned_pids": [],
                    "exit_ok": False,
                    "exit_error": "RuntimeError: exit failed",
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch("src.core.xps_heterojunction._origin_process_ids", return_value=set()):
        with patch("src.core.xps_heterojunction.check_origin_available", return_value=(True, "ok")):
            with patch(
                "src.core.xps_heterojunction._run_xps_origin_renderer",
                side_effect=fake_renderer,
            ):
                with patch(
                    "src.core.xps_heterojunction.reexport_tif_from_reopened_opju"
                ) as reexport:
                    result = _export_origin_for_comparison(
                        project_root,
                        comparison,
                        plot_csv,
                        output_dirs,
                        [],
                    )

    assert result["ok"] is False
    assert "exit failed" in result["message"]
    reexport.assert_not_called()


def test_xps_origin_bounded_exit_failure_only_cleans_proven_owned_pid(
    tmp_path: Path,
) -> None:
    plot_csv, comparison, output_dirs = _minimal_origin_export_case(tmp_path)
    project_root = tmp_path / "project"
    origin_file = output_dirs["origin_projects"] / f"{comparison.name}.opju"
    job_dir = output_dirs["origin_projects"] / "origin_jobs"
    preview_png = job_dir / f"{comparison.name}.png"
    lifecycle_file = job_dir / f"{comparison.name}_origin_lifecycle.json"

    def fake_renderer(_job_script: Path):
        origin_file.parent.mkdir(parents=True, exist_ok=True)
        job_dir.mkdir(parents=True, exist_ok=True)
        origin_file.write_bytes(b"opju")
        preview_png.write_bytes(b"png")
        lifecycle_file.write_text(
            json.dumps(
                {
                    "baseline_origin_pids": [],
                    "owned_origin_pids": [5151],
                    "remaining_owned_pids": [5151],
                    "exit_ok": False,
                    "exit_error": "",
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch(
        "src.core.xps_heterojunction._origin_process_ids",
        side_effect=[set(), set(), {5151}],
    ):
        with patch("src.core.xps_heterojunction.check_origin_available", return_value=(True, "ok")):
            with patch(
                "src.core.xps_heterojunction._run_xps_origin_renderer",
                side_effect=fake_renderer,
            ):
                with patch(
                    "src.core.xps_heterojunction._terminate_owned_origin_processes"
                ) as terminate:
                    with patch(
                        "src.core.xps_heterojunction._wait_for_origin_pids_exit",
                        return_value=set(),
                    ):
                        result = _export_origin_for_comparison(
                            project_root,
                            comparison,
                            plot_csv,
                            output_dirs,
                            [],
                        )

    assert result["ok"] is False
    assert "bounded exit wait" in result["message"]
    terminate.assert_called_once_with({5151})


def test_xps_failed_renderer_never_terminates_unowned_origin_pid(tmp_path: Path) -> None:
    lifecycle_file = tmp_path / "origin_lifecycle.json"
    lifecycle_file.write_text(
        json.dumps(
            {
                "baseline_origin_pids": [],
                "owned_origin_pids": [5151],
                "remaining_owned_pids": [5151],
                "exit_ok": False,
            }
        ),
        encoding="utf-8",
    )
    payload = json.loads(lifecycle_file.read_text(encoding="utf-8"))

    with patch(
        "src.core.xps_heterojunction._origin_process_ids",
        return_value={5151, 6161},
    ):
        with patch(
            "src.core.xps_heterojunction._terminate_owned_origin_processes"
        ) as terminate:
            error = _cleanup_failed_renderer_origin(
                payload,
                expected_baseline=set(),
            )

    assert "unowned Origin PID" in error
    assert "6161" in error
    terminate.assert_not_called()


def test_xps_origin_cleanup_command_targets_only_proven_owned_pids() -> None:
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch(
        "src.core.xps_heterojunction.subprocess.run",
        return_value=completed,
    ) as run:
        _terminate_owned_origin_processes({5151, 4242})

    command = run.call_args.args[0]
    assert command[:3] == ["powershell", "-NoProfile", "-Command"]
    script = command[3]
    assert "$ids = @(4242,5151)" in script
    assert "Get-Process -Id $ids" in script
    assert "ProcessName -like 'Origin*'" in script
    assert "Get-Process -Name Origin*" not in script


def _minimal_origin_export_case(
    tmp_path: Path,
) -> tuple[Path, XpsComparison, dict[str, Path]]:
    project_root = tmp_path / "project"
    project_root.mkdir()
    plot_csv = tmp_path / "plot.csv"
    plot_csv.write_text(
        "binding_energy_eV,CWO measured,BC measured\n1,2,3\n",
        encoding="utf-8",
    )

    def record(sample: str) -> XpsFitRecord:
        return XpsFitRecord(
            sample=sample,
            element="Cu",
            region="Cu2p",
            source_file=tmp_path / f"{sample}.xlsx",
            sheet_name="Cu2p",
            raw_label="measured",
            background_label=None,
            envelope_label=None,
            residual_label=None,
            component_labels=[],
            data=[{"binding_energy_eV": 1.0, "raw_intensity": 2.0}],
        )

    comparison = XpsComparison(
        "XPS_Cu_CWO_vs_BC_stacked",
        "Cu",
        "CWO",
        "BC",
        record("CWO"),
        record("BC"),
    )
    return (
        plot_csv,
        comparison,
        {
            "origin_projects": tmp_path / "external_output" / "origin_projects",
            "figures_tif": tmp_path / "external_output" / "figures_tif",
        },
    )


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
    assert (default_output_root(project_root) / "xps_heterojunction_stacked" / "reports" / "xps_heterojunction_stacked_summary.md").exists()


def test_cli_xps_relative_output_dir_is_routed_to_external_output_root(tmp_path: Path, monkeypatch) -> None:
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
            "--output-dir",
            "output/xps_custom",
        ]
    )

    assert code == 0
    assert not (project_root / "output").exists()
    assert (default_output_root(project_root) / "output" / "xps_custom" / "reports" / "xps_heterojunction_stacked_summary.md").exists()


def test_cli_xps_heterojunction_stacked_reports_missing_explicit_file_without_outputs(tmp_path: Path, project_root: Path) -> None:
    missing = tmp_path / "missing_bobc.xlsx"
    output_dir = default_output_root(project_root) / f"_test_missing_xps_input_{tmp_path.name}"

    result = subprocess.run(
        [
            sys.executable,
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
