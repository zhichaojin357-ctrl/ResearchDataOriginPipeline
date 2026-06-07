from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

from src.cli import main
from src.core.opju_product_pilot import _xps_records_to_offset_table
from src.core.v3_real_template_rebuild import (
    _apply_v3_xps_component_fill,
    _apply_v3_xps_peak_annotations,
    _apply_v3_xps_y_axis_title_overlay,
    _build_v3_epr_table,
    _build_v3_xy_multisource_table,
    _v3_bet_series_label_from_path,
    _v3_same_x_overlay_table,
    _force_v3_axis_titles_visible,
    _position_v3_axis_titles_outside_plot,
    _preferred_v3_xps_graph_name,
    _select_v3_xps_template_for_product,
    _strict_style_readback,
    _v3_origin_processing_script,
    _v3_epr_origin_processing_script,
    _write_v3_identity_origin_processing_plan,
    _xps_peak_annotations_from_processed_data,
    build_v3_template_candidate_pool,
    V3TemplateCandidate,
    V3TemplateSelection,
    is_v3_xps_component_curve_header,
    v3_plot_type_for_header,
    _write_v3_template_preview_comparison,
    v3_xps_component_fill_pairs,
)
from src.core.opju_product_pilot import ProductContext, TargetPairing
from src.core.v4_strict_template_conformance import (
    V4_STRICT_COMMAND,
    V4_STRICT_GLOBAL_STYLE_OVERRIDE,
    V4_STRICT_SCOPE,
    V4StrictTemplateConformanceOptions,
    build_v4_strict_v3_options,
)
from src.core.xps_heterojunction import XpsFitRecord
from src.origin.style_mimic import OpjuStyleSnapshot
from src.origin.user_style import ResolvedPlotStyle


class _FakeOriginOps:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def _plot_names(self, _graph_name: str) -> list[str]:
        return ["measured", "envelope", "component1", "baseline1"]

    def run_labtalk(self, command: str) -> None:
        self.commands.append(command)


def test_v4_strict_options_use_strict_scope_and_xps_reference_only(tmp_path: Path) -> None:
    pairing = tmp_path / "pairing.json"
    output_root = tmp_path / "external"
    f_root = tmp_path / "f_drive"
    xps_reference = tmp_path / "xps参考图像"

    v3_options = build_v4_strict_v3_options(
        V4StrictTemplateConformanceOptions(
            pairing_path=pairing,
            output_root=output_root,
            timestamp="20260605_220000",
            f_drive_template_root=f_root,
            xps_reference_template_root=xps_reference,
            with_origin=True,
        )
    )

    assert v3_options.run_scope == V4_STRICT_SCOPE
    assert v3_options.command_name == V4_STRICT_COMMAND
    assert v3_options.product_slug_version == "v4_strict"
    assert v3_options.global_style_override == V4_STRICT_GLOBAL_STYLE_OVERRIDE
    assert v3_options.eis_strict_semicircle_branch is True
    assert v3_options.xps_reference_templates_for_all_xps is True
    assert v3_options.xps_templates_from_reference_only is True
    assert v3_options.xps_smooth_gradient_fill is True
    assert v3_options.cleanup_empty_run_layout_dirs is True


def test_v4_strict_candidate_pool_excludes_f_drive_xps_templates(tmp_path: Path) -> None:
    f_root = tmp_path / "f_drive"
    reference_root = tmp_path / "xps参考图像"
    f_xps = f_root / "XPS" / "CWO+BOBC VBXPS谱图.opju"
    ref_xps = reference_root / "xps_in_situ_Bi_Cl_Br.opju"
    f_bet = f_root / "BET" / "BET -BOBC为负数.opju"
    for path in (f_xps, ref_xps, f_bet):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")

    candidates = build_v3_template_candidate_pool(
        [f_xps, f_bet],
        [ref_xps],
        f_drive_root=f_root,
        xps_reference_root=reference_root,
        xps_reference_templates_for_all_xps=True,
        xps_templates_from_reference_only=True,
    )

    xps_candidates = [candidate for candidate in candidates if candidate.product_key.startswith("XPS")]
    assert {candidate.product_key for candidate in xps_candidates} == {"XPS_in_situ", "XPS_non_in_situ"}
    assert {candidate.source for candidate in xps_candidates} == {"xps_reference_scan"}
    assert all(candidate.path == ref_xps for candidate in xps_candidates)
    assert any(candidate.product_key == "BET" and candidate.source == "f_drive_scan" for candidate in candidates)


def test_v4_strict_candidate_pool_can_add_non_in_situ_xps_stack_templates(tmp_path: Path) -> None:
    f_root = tmp_path / "f_drive"
    reference_root = tmp_path / "xps_reference"
    non_in_situ_root = tmp_path / "xps_heterojunction_stacked" / "origin_projects"
    ref_xps = reference_root / "xps_in_situ_Bi_Cl_Br.opju"
    stacked = non_in_situ_root / "XPS_Bi_BOBC_vs_BC_stacked.opju"
    cwo_stacked = non_in_situ_root / "XPS_Cu_CWO_vs_BC_stacked.opju"
    f_bet = f_root / "BET" / "BET.opju"
    for path in (ref_xps, stacked, cwo_stacked, f_bet):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")

    candidates = build_v3_template_candidate_pool(
        [f_bet],
        [ref_xps],
        f_drive_root=f_root,
        xps_reference_root=reference_root,
        xps_reference_templates_for_all_xps=True,
        xps_templates_from_reference_only=True,
        xps_non_in_situ_paths=[stacked, cwo_stacked],
        xps_non_in_situ_root=non_in_situ_root,
    )

    non_in_situ_candidates = [candidate for candidate in candidates if candidate.product_key == "XPS_non_in_situ"]
    assert any(candidate.path == stacked for candidate in non_in_situ_candidates)
    assert max(non_in_situ_candidates, key=lambda item: item.path_score).path == stacked


def test_cli_unified_v4_strict_passes_required_paths(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")
    output_root = tmp_path / "external"
    f_root = tmp_path / "f_drive"
    xps_reference = tmp_path / "xps参考图像"
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: V4StrictTemplateConformanceOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(output_root / "runs" / "20260605_220000_unified_v4_strict_template_conformance_all_types"),
            "summary": {"product_count": 11, "success_count": 11, "blocked_count": 0, "failed_count": 0},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.run_v4_strict_template_conformance_all_types", fake_run)

    code = main(
        [
            "unified-v4-strict-template-conformance-all-types",
            "--pairing",
            str(pairing),
            "--output-root",
            str(output_root),
            "--with-origin",
            "--timestamp",
            "20260605_220000",
            "--f-drive-template-root",
            str(f_root),
            "--xps-reference-template-root",
            str(xps_reference),
        ]
    )

    assert code == 0
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, V4StrictTemplateConformanceOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.f_drive_template_root == f_root
    assert options.xps_reference_template_root == xps_reference
    assert options.with_origin is True


def test_v4_strict_xps_component_fill_keeps_template_line_plot_not_area_plot() -> None:
    assert v3_plot_type_for_header("XPS_in_situ", "BOBC_component_1", "line") == "line"
    assert v3_plot_type_for_header("XPS_non_in_situ", "BOBC_component_1", "line") == "line"
    assert v3_plot_type_for_header("BET", "BOBC_component_1", "line+symbol") == "line+symbol"
    assert is_v3_xps_component_curve_header("BOBC_component_1")
    assert not is_v3_xps_component_curve_header("BOBC_component_1_fill_baseline")


def test_v4_strict_xps_components_are_followed_by_template_fill_baselines() -> None:
    record = XpsFitRecord(
        sample="BOBC",
        element="Bi",
        region="Bi4f",
        source_file=Path("BOBCfit.xlsx"),
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=["Bi4f Scan A", "Bi4f Scan B"],
        data=[
            {
                "binding_energy_eV": 160.0,
                "raw_intensity": 10.0,
                "background": 10.0,
                "Backgnd.": 10.0,
                "envelope": 9.0,
                "Bi4f Scan A": 14.0,
                "Bi4f Scan B": 13.0,
            },
            {
                "binding_energy_eV": 159.0,
                "raw_intensity": 20.0,
                "background": 12.0,
                "Backgnd.": 12.0,
                "envelope": 18.0,
                "Bi4f Scan A": 18.0,
                "Bi4f Scan B": 16.0,
            },
        ],
    )

    headers, rows = _xps_records_to_offset_table(
        [record],
        include_envelope=True,
        include_components=True,
        component_fill_mode="template_line_fill",
    )

    assert headers == [
        "binding_energy_eV",
        "BOBC_measured",
        "BOBC_envelope",
        "BOBC_component_1",
        "BOBC_component_1_fill_baseline",
        "BOBC_component_2",
        "BOBC_component_2_fill_baseline",
    ]
    assert rows[0][4] == 0.0
    assert rows[1][4] == 0.2
    assert rows[0][6] == 0.0
    assert rows[1][6] == 0.2
    assert v3_xps_component_fill_pairs(headers) == [(3, 4), (5, 6)]


def test_v4_strict_xps_fill_baseline_is_masked_to_component_valid_points() -> None:
    record = XpsFitRecord(
        sample="BOBC",
        element="Bi",
        region="Bi4f",
        source_file=Path("BOBCfit.xlsx"),
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=["Bi4f Scan A", "Bi4f Scan B"],
        data=[
            {
                "binding_energy_eV": 160.0,
                "raw_intensity": 10.0,
                "Backgnd.": 10.0,
                "envelope": 9.0,
                "Bi4f Scan A": "",
                "Bi4f Scan B": 13.0,
            },
            {
                "binding_energy_eV": 159.0,
                "raw_intensity": 20.0,
                "Backgnd.": 12.0,
                "envelope": 18.0,
                "Bi4f Scan A": 18.0,
                "Bi4f Scan B": "",
            },
        ],
    )

    headers, rows = _xps_records_to_offset_table(
        [record],
        include_envelope=True,
        include_components=True,
        component_fill_mode="template_line_fill",
    )

    assert headers == [
        "binding_energy_eV",
        "BOBC_measured",
        "BOBC_envelope",
        "BOBC_component_1",
        "BOBC_component_1_fill_baseline",
        "BOBC_component_2",
        "BOBC_component_2_fill_baseline",
    ]
    assert rows[0][3] is None
    assert rows[0][4] is None
    assert rows[1][3] is not None
    assert rows[1][4] == 0.2
    assert rows[0][5] is not None
    assert rows[0][6] == 0.0
    assert rows[1][5] is None
    assert rows[1][6] is None


def test_v4_strict_writes_template_vs_generated_preview_comparison(tmp_path: Path) -> None:
    reference = tmp_path / "BET" / "reference_exports" / "BET_reference.png"
    generated = tmp_path / "BET" / "figures_preview" / "BET_preview.png"
    metadata = tmp_path / "BET" / "metadata" / "BET.json"
    reference.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), "white").save(reference)
    Image.new("RGB", (16, 12), "black").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 3,
                "origin_status": {
                    "product_style": {"plot_count": 1},
                    "conformance": {"compared_fields": 4, "matched_fields": 2},
                },
                "source_files": ["raw1.csv"],
            }
        ),
        encoding="utf-8",
    )

    audit = _write_v3_template_preview_comparison(
        tmp_path,
        [
            {
                "type": "BET",
                "status": "accepted",
                "reference_preview_png": str(reference),
                "preview_png": str(generated),
                "metadata": str(metadata),
            }
        ],
    )

    side_by_side = tmp_path / "reports" / "template_preview_comparisons" / "BET_template_vs_generated.png"
    assert side_by_side.exists()
    assert (tmp_path / "reports" / "template_preview_comparison.md").exists()
    assert audit["ready_count"] == 1
    assert audit["items"][0]["side_by_side_png"] == str(side_by_side)
    assert audit["items"][0]["preview_rms"] > 0
    assert audit["items"][0]["template_plot_count"] == 3
    assert audit["items"][0]["product_plot_count"] == 1
    assert audit["items"][0]["plot_count_delta"] == -2
    assert audit["items"][0]["strict_visual_match"] is False
    assert audit["items"][0]["strict_status"] == "blocked_not_one_to_one"
    assert (tmp_path / "reports" / "template_data_completeness.md").exists()


def test_v4_strict_xy_alignment_uses_adjacent_real_sources_without_fabricating_missing_series(tmp_path: Path) -> None:
    data_root = tmp_path / "raman"
    data_root.mkdir()
    first = data_root / "BOBC.txt"
    second = data_root / "CWO.txt"
    first.write_text("100 10\n200 12\n300 14\n", encoding="utf-8")
    second.write_text("100 20\n200 22\n300 24\n", encoding="utf-8")
    template_path = data_root / "template.opju"
    template_path.write_bytes(b"opju placeholder")

    pairing = TargetPairing(
        product_key="Raman",
        data_type="Raman",
        xps_subtype="",
        data_root_label="tmp",
        data_paths=[first],
        opju_root_label="tmp",
        reference_opju=template_path,
    )
    template = V3TemplateCandidate(
        product_key="Raman",
        path=template_path,
        source="unit",
        status="extracted",
        graph_page="Graph1",
        layer_count=1,
        plot_count=3,
    )

    aligned = _build_v3_xy_multisource_table(pairing, template)

    assert aligned is not None
    assert aligned["headers"] == ["raman_shift_cm-1", "BOBC_intensity", "CWO_intensity"]
    assert aligned["rows"][0] == [100.0, 10.0, 20.0]
    alignment = aligned["alignment"]
    assert alignment["template_plot_count"] == 3
    assert alignment["product_series_count"] == 2
    assert alignment["missing_template_series_count"] == 1
    assert alignment["fabrication_policy"] == "do_not_synthesize_missing_template_series"


def test_v4_strict_overlay_table_unions_x_grid_without_truncating_longer_series() -> None:
    headers, rows = _v3_same_x_overlay_table(
        "x",
        [
            ("short", [[0.0, 0.0], [1.0, 10.0]]),
            ("long", [[0.0, 0.0], [0.5, 5.0], [1.0, 20.0]]),
        ],
    )

    assert headers == ["x", "short", "long"]
    assert [row[0] for row in rows] == [0.0, 0.5, 1.0]
    assert rows[1] == [0.5, 5.0, 5.0]
    assert rows[2] == [1.0, 10.0, 20.0]


def test_v4_strict_bet_series_label_matches_template_short_names() -> None:
    assert _v3_bet_series_label_from_path(Path("XWM-LL-260421-1-BOBC-All Pore.XLS")) == "BOBC"
    assert _v3_bet_series_label_from_path(Path("XWM-LL-260421-2-CWO-All Pore.XLS")) == "CWO"
    assert _v3_bet_series_label_from_path(Path("XWM-LL-260421-3-BiCu-All Pore.XLS")) == "BiCu"
    assert _v3_bet_series_label_from_path(Path("XWM-LL-260421-4-BOBC-4-XIN-All Pore.XLS")) == "BOBC-4-XIN"


def test_v4_strict_xps_fill_uses_origin_fill_to_next_plot_mode() -> None:
    ops = _FakeOriginOps()

    status = _apply_v3_xps_component_fill(
        ops,
        "Graph1",
        ["binding_energy_eV", "BOBC_measured", "BOBC_envelope", "BOBC_component_1", "BOBC_component_1_fill_baseline"],
        {"required": True},
        style=ResolvedPlotStyle(line_width_pt=3.0),
    )

    joined = "\n".join(ops.commands)
    assert status["applied"] is True
    assert "-pf 1" in joined
    assert "-pfv 8" in joined
    assert "-pfm 3" in joined
    assert "-pff 33554431" in joined
    assert "-pfb 30586738" in joined
    assert "set baseline1 -s 1" in joined


def test_v4_strict_simple_types_write_origin_processing_plan(tmp_path: Path) -> None:
    plan = _write_v3_identity_origin_processing_plan(
        "XRD",
        tmp_path / "XRD",
        "XRD_BOBC_exemplar_v4_strict",
        ["two_theta_deg", "intensity"],
        [[10.0, 100.0], [11.0, 120.0]],
    )

    raw_input = Path(plan["raw_origin_input_csv"])
    plan_path = tmp_path / "XRD" / "metadata" / "origin_processing_plan.json"
    script = _v3_origin_processing_script("XRDBook", int(plan["raw_column_count"]), list(plan["transforms"]))

    assert plan["processing_location"] == "Origin workbook LabTalk after raw data import"
    assert raw_input.exists()
    assert plan_path.exists()
    assert "col(3)=col(1)" in script
    assert "col(4)=col(2)" in script
    assert "wks.col1.hidden=1" in script


def test_v4_strict_origin_processing_script_supports_xps_normalize_offset() -> None:
    script = _v3_origin_processing_script(
        "XPSBook",
        3,
        [
            {"header": "binding_energy_eV", "kind": "copy", "source_col": 1},
            {"header": "BOBC_measured", "kind": "normalize_with_offset", "source_col": 2, "scale_col": 2, "offset": 0.0},
            {"header": "BC_measured", "kind": "normalize_with_offset", "source_col": 3, "scale_col": 3, "offset": 1.35},
        ],
    )

    assert 'win -a "XPSBook"' in script
    assert "col(4)=col(1)" in script
    assert "double __v3_min_1=min(col(2))" in script
    assert "col(5)=(col(2)-__v3_min_1)/__v3_span_1+0" in script
    assert "double __v3_min_2=min(col(3))" in script
    assert "col(6)=(col(3)-__v3_min_2)/__v3_span_2+1.35" in script


def test_v4_strict_epr_uses_template_group_overlay_not_single_seed_file(tmp_path: Path) -> None:
    reference_dir = tmp_path / "F_drive" / "EPR" / "refs"
    reference_dir.mkdir(parents=True)
    _write_epr_xlsx(reference_dir / "BC-O3-dark.xlsx", [1, 2, 3, 4, 5])
    _write_epr_xlsx(reference_dir / "BC-OH-light2.xlsx", [10, 12, 14, 16, 18])
    _write_epr_xlsx(reference_dir / "CWO-OH-light2.xlsx", [20, 24, 28, 32, 36])
    _write_epr_xlsx(reference_dir / "BOBC-OH-light1.xlsx", [30, 36, 42, 48, 54])
    pairing = TargetPairing(
        "EPR",
        "EPR",
        "",
        "f_drive_scan",
        [reference_dir / "BC-O3-dark.xlsx"],
        "f_drive_scan",
        tmp_path / "epr.opju",
    )
    template = V3TemplateCandidate(
        "EPR",
        tmp_path / "epr.opju",
        "f_drive_scan",
        status="extracted",
        graph_page="ohG",
        layer_count=1,
        plot_count=3,
    )

    headers, rows, labels, extra = _build_v3_epr_table(pairing, tmp_path / "EPR", template, "EPR_OH_overlay_exemplar_v4_strict")

    overlay = extra["epr_overlay"]
    assert headers == ["magnetic_field", "BC", "CWO", "BOBC"]
    assert len(rows) == 5
    assert labels["plot_type"] == "line"
    assert overlay["group"] == "OH"
    assert overlay["processing_location"] == "Origin LabTalk workbook after raw data import"
    assert overlay["smoothing"] == "Origin smooth X-Function, adjacent averaging, npts=7"
    assert overlay["baseline_correction"] == "Origin LabTalk edge-region median baseline subtraction"
    assert [Path(path).name for path in overlay["input_files"]] == [
        "BC-OH-light2.xlsx",
        "CWO-OH-light2.xlsx",
        "BOBC-OH-light1.xlsx",
    ]
    assert "BC-O3-dark.xlsx" not in ",".join(overlay["input_files"])
    assert Path(overlay["raw_origin_input_csv"]).parent == tmp_path / "EPR" / "processed_data"
    assert Path(overlay["raw_origin_input_csv"]).exists()
    assert Path(overlay["final_product_processed_csv"]).parent == tmp_path / "EPR" / "processed_data"


def test_v4_strict_epr_origin_processing_script_uses_origin_median_and_smooth() -> None:
    script = _v3_epr_origin_processing_script("EPRBook", ["BC", "CWO", "BOBC"])

    assert 'win -a "EPRBook"' in script
    assert "median(col(14))" in script
    assert "smooth iy:=col(5) method:=aav npts:=7 oy:=col(8)" in script
    assert "smooth iy:=col(6) method:=aav npts:=7 oy:=col(9)" in script
    assert "smooth iy:=col(7) method:=aav npts:=7 oy:=col(10)" in script
    assert "col(11)=col(8)+2*step" in script


def test_v4_strict_style_readback_requires_legend_bold_and_full_no_frame() -> None:
    passed = _strict_style_readback(
        {
            "audit_numeric_values": {
                "xb.fsize": 36,
                "yl.fsize": 36,
                "xb.bold": 1,
                "yl.bold": 1,
                "xb.show": 1,
                "yl.show": 1,
                "legend.show": 1,
                "legend.background": 0,
                "legend.border": 0,
                "legend.frame": 0,
                "legend.fill": 0,
                "legend.fillColor": 0,
                "legend.borderColor": 0,
                "legend.lineWidth": 0,
                "legend.bold": 1,
            },
            "audit_string_values": {"xb.font$": "Arial", "yl.font$": "Arial"},
        }
    )
    failed = _strict_style_readback(
        {
            "audit_numeric_values": {
                "xb.fsize": 36,
                "yl.fsize": 36,
                "xb.bold": 1,
                "yl.bold": 1,
                "xb.show": 1,
                "yl.show": 1,
                "legend.show": 1,
                "legend.background": 0,
                "legend.border": 0,
                "legend.frame": 0,
                "legend.fill": 0,
                "legend.fillColor": 0,
                "legend.borderColor": 0,
                "legend.lineWidth": 1,
                "legend.bold": 0,
            },
            "audit_string_values": {"xb.font$": "Arial", "yl.font$": "Arial"},
        }
    )

    assert passed["legend_no_frame"] is True
    assert passed["legend_bold"] is True
    assert failed["legend_no_frame"] is False
    assert failed["legend_bold"] is False


def test_v4_strict_axis_titles_are_explicitly_shown() -> None:
    ops = _FakeOriginOps()

    _force_v3_axis_titles_visible(ops, "Graph1")

    joined = "\n".join(ops.commands)
    assert "xb.show=1" in joined
    assert "yl.show=1" in joined
    assert "layer.x.label.show=1" in joined
    assert "layer.y.label.show=1" in joined
    assert "xb.bold=1" in joined
    assert "yl.bold=1" in joined


def test_v4_strict_y_axis_title_position_handles_reversed_binding_energy_axis() -> None:
    ops = _FakeOriginOps()

    _position_v3_axis_titles_outside_plot(ops, "Graph1")

    joined = "\n".join(ops.commands)
    assert "if(layer.x.from>layer.x.to)" in joined
    assert "yl.x=layer.x.from+0.06*abs(layer.x.to-layer.x.from)" in joined


def test_v4_strict_y_axis_title_position_uses_template_offset_ratio() -> None:
    ops = _FakeOriginOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="template.opju",
        status="extracted",
        graph_page="Bi_4f",
        layout_values={
            "layer.x.from": 168.18,
            "layer.x.to": 154.22,
            "yl.x": 169.04255357957138,
            "layer.y.from": -0.25358644399754776,
            "layer.y.to": 4.896041702188032,
            "xb.y": -1.1829959934364163,
        },
    )

    _position_v3_axis_titles_outside_plot(ops, "Graph1", snapshot)

    joined = "\n".join(ops.commands)
    assert "yl.x=layer.x.from+0.061" in joined
    assert "xb.y=layer.y.from-0.180" in joined
    assert "0.08*abs(layer.x.to-layer.x.from)" not in joined


def test_v4_strict_xps_y_axis_title_overlay_uses_rotated_named_label(tmp_path: Path) -> None:
    ops = _FakeOriginOps()
    product = ProductContext(
        product_key="XPS_non_in_situ",
        slug="XPS_non_in_situ_BOBC_BC_exemplar_v4_strict",
        pairing=TargetPairing("XPS_non_in_situ", "XPS", "XPS_non_in_situ", "", [], "", tmp_path / "template.opju"),
        type_root=tmp_path,
        processed_data=tmp_path / "xps.csv",
        input_copies=[],
        reference_opju_copy=tmp_path / "template.opju",
        reference_preview_png=tmp_path / "reference.png",
        origin_file=tmp_path / "product.opju",
        figure_tif=tmp_path / "product.tif",
        preview_png=tmp_path / "product.png",
        x_label="Binding Energy (eV)",
        y_label="Intensity (a.u.)",
        graph_title="XPS non-in-situ Bi pilot",
        plot_type="line",
        x_descending=True,
    )

    status = _apply_v3_xps_y_axis_title_overlay(ops, "Graph1", product, ResolvedPlotStyle())

    joined = "\n".join(ops.commands)
    assert status["applied"] is True
    assert 'label -p 8 50 -n V3YTitleFix "\\b(Intensity (a.u.))";' in joined
    assert "V3YTitleFix.rotate=90;" in joined
    assert "V3YTitleFix.x=layer.x.from+0.04*abs(layer.x.to-layer.x.from)" in joined
    assert "label -p -" not in joined


def test_v4_strict_xps_peak_annotations_use_current_peak_positions(tmp_path: Path) -> None:
    processed = tmp_path / "xps.csv"
    processed.write_text(
        "\n".join(
            [
                "binding_energy_eV,BOBC_measured,BOBC_envelope,BOBC_component_1,BOBC_component_1_fill_baseline,BOBC_component_2,BOBC_component_2_fill_baseline",
                "166,0,0,0.1,0.0,0.2,0.0",
                "165,0,0,0.5,0.0,0.3,0.0",
                "160,0,0,0.2,0.0,0.9,0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    annotations = _xps_peak_annotations_from_processed_data(processed, product_title="XPS in-situ Bi pilot")

    assert [item["text"] for item in annotations] == ["Bi 4f5/2 165.00 eV", "Bi 4f7/2 160.00 eV"]
    assert annotations[0]["x"] == 165.0
    assert annotations[1]["x"] == 160.0


def test_v4_strict_xps_peak_annotations_emit_origin_labels(tmp_path: Path) -> None:
    processed = tmp_path / "xps.csv"
    processed.write_text(
        "\n".join(
            [
                "binding_energy_eV,BOBC_measured,BOBC_envelope,BOBC_component_1,BOBC_component_1_fill_baseline",
                "166,0,0,0.1,0.0",
                "165,0,0,0.5,0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ops = _FakeOriginOps()

    status = _apply_v3_xps_peak_annotations(
        ops,
        "Graph1",
        processed,
        product_title="XPS in-situ Bi pilot",
        style=ResolvedPlotStyle(title_font_size=18),
    )

    joined = "\n".join(ops.commands)
    assert status["applied"] is True
    assert status["annotation_count"] == 1
    assert "label -a 165" in joined
    assert "Bi 4f" in joined
    assert "165.00 eV" in joined
    assert "\\b(" not in joined


def test_v4_strict_prefers_xps_template_graph_matching_product_element() -> None:
    assert _preferred_v3_xps_graph_name("XPS non-in-situ Bi pilot", ["Br_3d", "Bi_4f", "Cl_2p"]) == "Bi_4f"
    assert _preferred_v3_xps_graph_name("XPS in-situ W pilot", ["Cu_2p", "W_4f"]) == "W_4f"


def test_v4_strict_selects_xps_reference_opju_containing_matching_graph(tmp_path: Path) -> None:
    pairing = TargetPairing("XPS_in_situ", "XPS", "XPS_in_situ", "", [], "", tmp_path / "unused.opju")
    product = ProductContext(
        product_key="XPS_in_situ",
        slug="XPS_in_situ_BOBC_exemplar_v4_strict",
        pairing=pairing,
        type_root=tmp_path,
        processed_data=tmp_path / "xps.csv",
        input_copies=[],
        reference_opju_copy=tmp_path / "wrong.opju",
        reference_preview_png=tmp_path / "ref.png",
        origin_file=tmp_path / "out.opju",
        figure_tif=tmp_path / "out.tif",
        preview_png=tmp_path / "out.png",
        x_label="Binding Energy (eV)",
        y_label="Intensity (a.u.)",
        graph_title="XPS in-situ Bi pilot",
        plot_type="line",
        x_descending=True,
    )
    cu_w = V3TemplateCandidate(
        "XPS_in_situ",
        tmp_path / "xps_in_situ_Cu_W.opju",
        "xps_reference_scan",
        status="extracted",
        graph_page="W_4f",
        layer_count=1,
        plot_count=14,
        metadata={"snapshot": {"graph_pages": ["Cu_2p", "W_4f"]}},
    )
    bi_cl_br = V3TemplateCandidate(
        "XPS_in_situ",
        tmp_path / "xps_in_situ_Bi_Cl_Br.opju",
        "xps_reference_scan",
        status="extracted",
        graph_page="Cl_2p",
        layer_count=1,
        plot_count=21,
        metadata={"snapshot": {"graph_pages": ["Br_3d", "Bi_4f", "Cl_2p"]}},
    )
    selection = V3TemplateSelection("XPS_in_situ", "selected", selected=cu_w, candidates=(cu_w, bi_cl_br))

    selected = _select_v3_xps_template_for_product(product, selection)

    assert selected.path.name == "xps_in_situ_Bi_Cl_Br.opju"
    assert selected.graph_page == "Bi_4f"


def _write_epr_xlsx(path: Path, ys: list[float]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for index, y in enumerate(ys):
        sheet.append([324.0 + index * 0.0001, y])
    workbook.save(path)
