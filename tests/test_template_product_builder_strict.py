from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

from src.core.template_product_common import _xps_records_to_offset_table
from src.core.template_product_builder import (
    _apply_template_xps_component_fill,
    _apply_template_xps_peak_annotations,
    _apply_template_xps_y_axis_title_overlay,
    _build_template_epr_table,
    _build_template_xrd_multisource_table,
    _build_template_xy_multisource_table,
    _select_template_bet_candidate_cohort,
    _template_bet_series_label_from_path,
    _template_candidate_files,
    _template_display_path,
    _template_mott_candidate_files,
    _template_photocurrent_candidate_files,
    _template_pl_candidate_files,
    _template_same_x_overlay_table,
    _template_xy_series_label,
    _seed_project_style_reference_preview,
    _force_template_axis_titles_visible,
    _position_template_axis_titles_outside_plot,
    _preferred_template_xps_graph_name,
    _relevant_strict_readback_values,
    _select_template_xps_template_for_product,
    _strict_style_readback,
    _template_origin_processing_script,
    _template_plot_count,
    _template_strict_visual_reasons,
    _template_epr_origin_processing_script,
    _write_template_identity_origin_processing_plan,
    _xps_peak_annotations_from_processed_data,
    build_template_candidate_pool,
    classify_template_project_style_asset_candidates,
    TemplateCandidate,
    TemplateSelection,
    is_template_xps_component_curve_header,
    template_plot_type_for_header,
    _write_template_preview_comparison,
    template_xps_component_fill_pairs,
)
from src.core.template_product_common import ProductContext, TargetPairing
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


def test_template_candidate_pool_excludes_f_drive_xps_templates(tmp_path: Path) -> None:
    f_root = tmp_path / "f_drive"
    reference_root = tmp_path / "xps_reference"
    f_xps = f_root / "XPS" / "CWO+BOBC VBXPS.opju"
    ref_xps = reference_root / "xps_in_situ_Bi_Cl_Br.opju"
    f_bet = f_root / "BET" / "BET_BOBC.opju"
    for path in (f_xps, ref_xps, f_bet):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")

    candidates = build_template_candidate_pool(
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


def test_template_mott_candidate_selection_matches_centered_reviewed_frequency_window(tmp_path: Path) -> None:
    paths = []
    for frequency in range(1000, 4001, 500):
        path = tmp_path / f"{frequency}.xlsx"
        path.write_bytes(b"xlsx")
        paths.append(path)
    pairing = TargetPairing(
        product_key="Mott-Schottky",
        data_type="Mott-Schottky",
        xps_subtype="",
        data_root_label="test",
        data_paths=paths,
        opju_root_label="test",
        reference_opju=tmp_path / "reference.opju",
    )

    selected = _template_mott_candidate_files(pairing, paths, 5)

    assert [path.stem for path in selected] == ["1500", "2000", "2500", "3000", "3500"]


def test_template_display_path_hides_workspace_prefixes() -> None:
    template = Path("D:/Codex Project/科研数据处理/ResearchDataOriginPipeline/templates/origin_styles/format_themes/BET.oth")
    external = Path("F:/课题/LL/检测/BET/BOBC.opju")

    assert _template_display_path(template) == "templates/origin_styles/format_themes/BET.oth"
    assert _template_display_path(external) == "external/BOBC.opju"


def test_project_style_asset_candidate_uses_manifest_plot_count_and_reference_preview(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    template = style_root / "format_themes" / "Raman.oth"
    reference = style_root / "previews" / "Raman_reference.png"
    template.parent.mkdir(parents=True)
    reference.parent.mkdir(parents=True)
    template.write_bytes(b"oth")
    Image.new("RGB", (16, 12), "white").save(reference)
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "Raman",
                        "data_type": "Raman",
                        "status": "accepted",
                        "graph_page": "Graph4",
                        "format_theme": "format_themes/Raman.oth",
                        "reference_preview_png": "previews/Raman_reference.png",
                        "template_plot_count": 3,
                        "layer_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    [candidate] = classify_template_project_style_asset_candidates(project)
    copied = tmp_path / "run" / "Raman" / "reference_exports" / "Raman_reference.png"
    _seed_project_style_reference_preview(candidate, copied)

    assert candidate.plot_count == 3
    assert candidate.layer_count == 1
    assert copied.exists()


def test_project_style_asset_candidate_uses_snapshot_plot_count_when_manifest_omits_it(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    snapshot = style_root / "snapshots" / "BET.json"
    theme.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    snapshot.write_text(json.dumps({"layer_count": 2, "plot_count": 6}), encoding="utf-8")
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "status": "accepted",
                        "graph_page": "Graph5",
                        "format_theme": "format_themes/BET.oth",
                        "style_snapshot": "snapshots/BET.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    [candidate] = classify_template_project_style_asset_candidates(project)

    assert candidate.layer_count == 2
    assert candidate.plot_count == 6


def test_project_style_asset_prefers_saved_format_theme_over_copied_opju(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    format_theme = style_root / "format_themes" / "photocurrent.oth"
    template_opju = style_root / "reference_opju" / "photocurrent.opju"
    format_theme.parent.mkdir(parents=True)
    template_opju.parent.mkdir(parents=True)
    format_theme.write_bytes(b"oth")
    template_opju.write_bytes(b"opju")
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "photocurrent",
                        "data_type": "photocurrent",
                        "status": "accepted",
                        "graph_page": "Graph1",
                        "format_theme": "format_themes/photocurrent.oth",
                        "template_opju": "reference_opju/photocurrent.opju",
                        "template_plot_count": 3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    [candidate] = classify_template_project_style_asset_candidates(project)

    assert candidate.path == format_theme
    assert candidate.source == "project_origin_style_asset"
    assert candidate.path_score == 1
    assert candidate.plot_count == 3


def test_template_candidate_files_prioritize_manifest_data_hints(tmp_path: Path) -> None:
    hinted = tmp_path / "hinted" / "XWM-LL-260421-1-BOBC-All Pore.XLS"
    sibling = tmp_path / "pairing" / "ZPF-LL-20260327-4-BOBC-BET.XLS"
    template_path = tmp_path / "project" / "templates" / "origin_styles" / "reference_opju" / "BET.opju"
    for path in (hinted, sibling, template_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")
    pairing = TargetPairing(
        product_key="BET",
        data_type="BET",
        xps_subtype="",
        data_root_label="tmp",
        data_paths=[sibling],
        opju_root_label="tmp",
        reference_opju=template_path,
    )
    template = TemplateCandidate(
        product_key="BET",
        path=template_path,
        source="project_origin_template_asset",
        status="valid",
        graph_page="Graph3",
        layer_count=1,
        plot_count=8,
        metadata={"manifest_entry": {"data_hint_paths": [str(hinted)]}},
    )

    candidates = _template_candidate_files(pairing, template, suffixes=(".xls", ".xlsx"), prefer_template_parent=True)

    assert candidates[0] == hinted
    assert sibling in candidates


def test_template_candidate_pool_can_add_non_in_situ_xps_stack_templates(tmp_path: Path) -> None:
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

    candidates = build_template_candidate_pool(
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

def test_template_xps_component_fill_keeps_template_line_plot_not_area_plot() -> None:
    assert template_plot_type_for_header("XPS_in_situ", "BOBC_component_1", "line") == "line"
    assert template_plot_type_for_header("XPS_non_in_situ", "BOBC_component_1", "line") == "line"
    assert template_plot_type_for_header("BET", "BOBC_component_1", "line+symbol") == "line+symbol"
    assert is_template_xps_component_curve_header("BOBC_component_1")
    assert is_template_xps_component_curve_header("BOBC_component_1_line")
    assert not is_template_xps_component_curve_header("BOBC_component_1_fill_upper")
    assert not is_template_xps_component_curve_header("BOBC_component_1_fill_baseline")


def test_template_xps_components_are_followed_by_template_fill_baselines() -> None:
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
    assert template_xps_component_fill_pairs(headers) == [(3, 4), (5, 6)]

    in_situ_headers, _in_situ_rows = _xps_records_to_offset_table(
        [record],
        include_envelope=True,
        include_components=True,
        component_fill_mode="template_line_fill",
        series_layout="in_situ_template",
    )
    assert in_situ_headers == [
        "binding_energy_eV",
        "BOBC_measured",
        "BOBC_component_1",
        "BOBC_component_1_fill_baseline",
        "BOBC_component_2",
        "BOBC_component_2_fill_baseline",
        "BOBC_background",
        "BOBC_envelope",
    ]
    assert template_xps_component_fill_pairs(in_situ_headers) == [(2, 3), (4, 5)]

    non_in_situ_headers, _non_in_situ_rows = _xps_records_to_offset_table(
        [record],
        include_envelope=True,
        include_components=True,
        component_fill_mode="template_line_fill",
        series_layout="non_in_situ_template",
    )
    assert non_in_situ_headers == [
        "binding_energy_eV",
        "BOBC_component_1_fill_upper",
        "BOBC_component_1_fill_baseline",
        "BOBC_component_1_line",
        "BOBC_component_2_fill_upper",
        "BOBC_component_2_fill_baseline",
        "BOBC_component_2_line",
        "BOBC_measured",
        "BOBC_background",
        "BOBC_envelope",
    ]
    assert template_xps_component_fill_pairs(non_in_situ_headers) == [(1, 2), (4, 5)]


def test_template_xps_fill_baseline_is_masked_to_component_valid_points() -> None:
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


def test_template_writes_template_vs_generated_preview_comparison(tmp_path: Path) -> None:
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

    audit = _write_template_preview_comparison(
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
    assert audit["items"][0]["side_by_side_png"] == "reports/template_preview_comparisons/BET_template_vs_generated.png"
    assert audit["items"][0]["preview_rms"] > 0
    assert audit["items"][0]["template_plot_count"] == 3
    assert audit["items"][0]["product_plot_count"] == 1
    assert audit["items"][0]["plot_count_delta"] == -2
    assert audit["items"][0]["strict_visual_match"] is False
    assert audit["items"][0]["strict_status"] == "blocked_not_one_to_one"
    assert (tmp_path / "reports" / "template_data_completeness.md").exists()


def test_saved_format_theme_does_not_exempt_nonzero_plot_count_delta(tmp_path: Path) -> None:
    generated = tmp_path / "BET" / "figures_preview" / "BET_preview.png"
    metadata = tmp_path / "BET" / "metadata" / "BET.json"
    generated.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), "white").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 3,
                "origin_status": {
                    "template_format_plan": {"mode": "saved_format_theme"},
                    "origin_processing": {"method": "saved_format_theme_apply"},
                    "product_style": {"plot_count": 1},
                },
                "origin_processing": {"method": "saved_format_theme_apply"},
                "source_files": ["raw1.csv"],
            }
        ),
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "reference_preview_png": str(tmp_path / "missing_reference.png"),
        "preview_png": str(generated),
        "metadata": str(metadata),
        "template_format_mode": "saved_format_theme",
        "origin_processing_method": "saved_format_theme_apply",
        "notes": "Origin saved format-theme export succeeded.",
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    assert product["status"] == "blocked"
    assert audit["items"][0]["strict_status"] == "blocked_not_one_to_one"
    assert audit["items"][0]["saved_style_asset_mode"] is True
    assert audit["items"][0]["plot_count_delta"] == -2


def test_template_preview_comparison_resolves_run_relative_artifacts(tmp_path: Path) -> None:
    reference = tmp_path / "BET" / "reference_exports" / "BET_reference.png"
    generated = tmp_path / "BET" / "figures_preview" / "BET_preview.png"
    metadata = tmp_path / "BET" / "metadata" / "BET.json"
    reference.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), "white").save(reference)
    Image.new("RGB", (16, 12), "white").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 1,
                "origin_status": {
                    "product_style": {"plot_count": 1},
                    "conformance": {"compared_fields": 4, "matched_fields": 4},
                },
                "source_files": ["raw1.csv"],
            }
        ),
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "reference_preview_png": "BET/reference_exports/BET_reference.png",
        "preview_png": "BET/figures_preview/BET_preview.png",
        "metadata": "BET/metadata/BET.json",
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    assert audit["ready_count"] == 1
    assert audit["strict_match_count"] == 1
    assert audit["items"][0]["ready"] is True
    assert audit["items"][0]["strict_visual_match"] is True
    assert audit["items"][0]["reference_preview_png"] == "BET/reference_exports/BET_reference.png"
    assert audit["items"][0]["generated_preview_png"] == "BET/figures_preview/BET_preview.png"
    assert audit["items"][0]["side_by_side_png"] == "reports/template_preview_comparisons/BET_template_vs_generated.png"
    report = (tmp_path / "reports" / "template_preview_comparison.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in report


def test_template_xy_alignment_uses_adjacent_real_sources_without_fabricating_missing_series(tmp_path: Path) -> None:
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
    template = TemplateCandidate(
        product_key="Raman",
        path=template_path,
        source="unit",
        status="extracted",
        graph_page="Graph1",
        layer_count=1,
        plot_count=3,
    )

    aligned = _build_template_xy_multisource_table(pairing, template)

    assert aligned is not None
    assert aligned["headers"] == ["raman_shift_cm-1", "BOBC_intensity", "CWO_intensity"]
    assert aligned["rows"][0] == [100.0, 10.0, 20.0]
    alignment = aligned["alignment"]
    assert alignment["template_plot_count"] == 3
    assert alignment["product_series_count"] == 2
    assert alignment["missing_template_series_count"] == 1
    assert alignment["fabrication_policy"] == "do_not_synthesize_missing_template_series"


def test_template_overlay_table_unions_x_grid_without_truncating_longer_series() -> None:
    headers, rows = _template_same_x_overlay_table(
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


def test_template_bet_series_label_matches_template_short_names() -> None:
    assert _template_bet_series_label_from_path(Path("XWM-LL-260421-1-BOBC-All Pore.XLS")) == "BOBC"
    assert _template_bet_series_label_from_path(Path("XWM-LL-260421-2-CWO-All Pore.XLS")) == "CWO"
    assert _template_bet_series_label_from_path(Path("XWM-LL-260421-3-BiCu-All Pore.XLS")) == "BiCu"
    assert _template_bet_series_label_from_path(Path("XWM-LL-260421-4-BOBC-4-XIN-All Pore.XLS")) == "BOBC-4-XIN"


def test_template_xps_fill_uses_origin_fill_to_next_plot_mode() -> None:
    ops = _FakeOriginOps()

    status = _apply_template_xps_component_fill(
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


def test_template_simple_types_write_origin_processing_plan(tmp_path: Path) -> None:
    plan = _write_template_identity_origin_processing_plan(
        "XRD",
        tmp_path / "XRD",
        "XRD_BOBC_exemplar_template",
        ["two_theta_deg", "intensity"],
        [[10.0, 100.0], [11.0, 120.0]],
    )

    plan_path = tmp_path / "XRD" / "metadata" / "origin_processing_plan.json"
    raw_input = (plan_path.parent / Path(plan["raw_origin_input_csv"])).resolve()
    script = _template_origin_processing_script("XRDBook", int(plan["raw_column_count"]), list(plan["transforms"]))

    assert plan["processing_location"] == "Origin workbook LabTalk after raw data import"
    assert raw_input.exists()
    assert plan_path.exists()
    assert "col(3)=col(1)" in script
    assert "col(4)=col(2)" in script
    assert "wks.col1.hidden=1" in script


def test_template_xrd_multisource_labels_use_greek_theta_axis_title(tmp_path: Path) -> None:
    xrd_source = tmp_path / "XRD" / "bobc.txt"
    xrd_source.parent.mkdir()
    xrd_source.write_text(
        "\n".join([";RAW4.00", "[Data]", "Angle, PSD", "5, 824", "6, 900", ""]),
        encoding="utf-8",
    )
    pairing = TargetPairing("XRD", "XRD", "", "root", [xrd_source], "root", tmp_path / "template.opju")
    template = TemplateCandidate("XRD", tmp_path / "template.opju", "unit", graph_page="Graph4", plot_count=1)

    table = _build_template_xrd_multisource_table(pairing, template)

    assert table is not None
    assert table["labels"]["x_label"] == "2θ (degree)"


def test_template_origin_processing_script_supports_xps_normalize_offset() -> None:
    script = _template_origin_processing_script(
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
    assert "double __template_min_1=min(col(2))" in script
    assert "col(5)=(col(2)-__template_min_1)/__template_span_1+0" in script
    assert "double __template_min_2=min(col(3))" in script
    assert "col(6)=(col(3)-__template_min_2)/__template_span_2+1.35" in script


def test_template_epr_uses_template_group_overlay_not_single_seed_file(tmp_path: Path) -> None:
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
    template = TemplateCandidate(
        "EPR",
        tmp_path / "epr.opju",
        "f_drive_scan",
        status="extracted",
        graph_page="ohG",
        layer_count=1,
        plot_count=3,
    )

    headers, rows, labels, extra = _build_template_epr_table(pairing, tmp_path / "EPR", template, "EPR_OH_overlay_exemplar_template")

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
    plan_path = tmp_path / "EPR" / "metadata" / "epr_origin_processing_plan.json"
    raw_input = (plan_path.parent / Path(overlay["raw_origin_input_csv"])).resolve()
    assert raw_input.parent == tmp_path / "EPR" / "processed_data"
    assert raw_input.exists()
    final_csv = (plan_path.parent / Path(overlay["final_product_processed_csv"])).resolve()
    assert final_csv.parent == tmp_path / "EPR" / "processed_data"


def test_template_bet_selects_one_material_each_from_coherent_cohort(tmp_path: Path) -> None:
    bet_root = tmp_path / "BET"
    seed = bet_root / "new_single" / "20260701-BOBC.XLS"
    scattered = bet_root / "old_single" / "20260101-CWO.XLS"
    cohort = bet_root / "grouped" / "20260421"
    grouped = [
        cohort / "1-BOBC-All Pore.XLS",
        cohort / "2-CWO-All Pore.XLS",
        cohort / "3-BiCu-All Pore.XLS",
        cohort / "4-BOBC-4-XIN-All Pore.XLS",
    ]
    for path in [seed, scattered, *grouped]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")

    selected, selected_cohort = _select_template_bet_candidate_cohort(
        [seed, scattered, *grouped],
        3,
    )

    assert selected_cohort == cohort
    assert [_template_bet_series_label_from_path(path) for path in selected] == ["BOBC", "CWO", "BiCu"]


def test_template_pl_selects_only_requested_scan_family_and_material_labels(tmp_path: Path) -> None:
    root = tmp_path / "PL" / "bobc+cwo+bc"
    root.mkdir(parents=True)
    for index, emission in ((1, 640), (2, 445), (3, 630)):
        (root / f"{index}-EM-ex340nm.txt").write_text("360 1\n361 2\n", encoding="utf-8")
        (root / f"{index}-EX-em{emission}nm.txt").write_text("250 1\n251 2\n", encoding="utf-8")
    pairing = TargetPairing("PL", "PL", "", "root", [root / "1-EM-ex340nm.txt"], "root", tmp_path / "pl.opju")
    template = TemplateCandidate("PL", tmp_path / "pl.opju", "unit", graph_page="EXJF", plot_count=3)

    selected = _template_pl_candidate_files(pairing, template, 3)
    built = _build_template_xy_multisource_table(pairing, template)

    assert [path.name for path in selected] == ["1-EX-em640nm.txt", "2-EX-em445nm.txt", "3-EX-em630nm.txt"]
    assert [_template_xy_series_label("PL", path) for path in selected] == ["BOBC", "CWO", "BC"]
    assert built is not None
    assert built["headers"] == ["wavelength_nm", "BOBC_counts", "CWO_counts", "BC_counts"]
    assert len(set(built["headers"])) == len(built["headers"])


def test_template_photocurrent_uses_sample_directory_labels(tmp_path: Path) -> None:
    root = tmp_path / "photocurrent" / "1bobc+2cwo+3bicu-10"
    paths = [
        root / "BOBC" / "1-(OCP).txt",
        root / "CWO" / "2-(OCP).txt",
        root / "bicu" / "1-(OCP)-bicu.txt",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("0 1\n1 2\n", encoding="utf-8")
    pairing = TargetPairing("photocurrent", "photocurrent", "", "root", [paths[0]], "root", tmp_path / "pc.opju")
    template = TemplateCandidate("photocurrent", tmp_path / "pc.opju", "unit", graph_page="Graph1", plot_count=3)

    selected = _template_photocurrent_candidate_files(pairing, template, 3)
    built = _build_template_xy_multisource_table(pairing, template)

    assert [_template_xy_series_label("photocurrent", path) for path in selected] == ["BOBC", "CWO", "BiCu-10"]
    assert built is not None
    assert built["headers"] == ["time_s", "BOBC_current_a", "CWO_current_a", "BiCu-10_current_a"]
    assert len(set(built["headers"])) == len(built["headers"])


def test_template_epr_origin_processing_script_uses_origin_median_and_smooth() -> None:
    script = _template_epr_origin_processing_script("EPRBook", ["BC", "CWO", "BOBC"])

    assert 'win -a "EPRBook"' in script
    assert "median(col(14))" in script
    assert "smooth iy:=col(5) method:=aav npts:=7 oy:=col(8)" in script
    assert "smooth iy:=col(6) method:=aav npts:=7 oy:=col(9)" in script
    assert "smooth iy:=col(7) method:=aav npts:=7 oy:=col(10)" in script
    assert "col(11)=col(8)+2*step" in script


def test_template_style_readback_requires_legend_bold_and_full_no_frame() -> None:
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


def test_template_base_readback_ignores_optional_font_size_and_legend_frame_requirements() -> None:
    readback = {
        "font_family_arial": True,
        "axis_title_font_size_36": False,
        "axis_title_bold": True,
        "axis_title_visible": True,
        "legend_no_frame": False,
        "legend_bold": False,
        "axis_title_no_overlap": True,
    }

    relevant = _relevant_strict_readback_values(readback, template_base_mode=True)

    assert relevant == {
        "font_family_arial": True,
        "axis_title_bold": True,
        "axis_title_visible": True,
        "axis_title_no_overlap": True,
    }


def test_cached_style_readback_only_requires_axis_title_visibility() -> None:
    readback = {
        "font_family_arial": True,
        "axis_title_font_size_36": False,
        "axis_title_bold": False,
        "axis_title_visible": True,
        "legend_no_frame": False,
        "legend_bold": False,
        "axis_title_no_overlap": True,
    }

    relevant = _relevant_strict_readback_values(
        readback,
        template_base_mode=False,
        saved_style_asset_mode=True,
    )

    assert relevant == {"axis_title_visible": True}


def test_strict_preview_rejects_plot_count_delta_even_with_low_rms_and_strong_style_match() -> None:
    reasons = _template_strict_visual_reasons(
        ready=True,
        plot_count_delta=-2,
        style_match_ratio=1.0,
        preview_rms=24.9,
    )

    assert reasons == ["plot count differs from template by -2"]


def test_strict_preview_records_high_rms_as_nonblocking_when_style_and_plot_count_match() -> None:
    reasons = _template_strict_visual_reasons(
        ready=True,
        plot_count_delta=0,
        style_match_ratio=0.98,
        preview_rms=61.0,
    )

    assert reasons == []


def test_strict_preview_accepts_text_only_legend_delta_when_plot_count_matches() -> None:
    reasons = _template_strict_visual_reasons(
        ready=True,
        plot_count_delta=0,
        style_match_ratio=0.88,
        preview_rms=57.7,
        text_only_legend=True,
    )

    assert reasons == []


def test_template_plot_count_uses_visible_template_count_not_available_source_series() -> None:
    metadata = {
        "template_plot_count": 3,
        "extra": {
            "template_data_alignment": {
                "visual_template_plot_count": 5,
            }
        },
    }

    assert _template_plot_count({}, metadata) == 3


def test_template_axis_titles_are_explicitly_shown() -> None:
    ops = _FakeOriginOps()

    _force_template_axis_titles_visible(ops, "Graph1")

    joined = "\n".join(ops.commands)
    assert "xb.show=1" in joined
    assert "yl.show=1" in joined
    assert "layer.x.label.show=1" in joined
    assert "layer.y.label.show=1" in joined
    assert "xb.bold=1" in joined
    assert "yl.bold=1" in joined


def test_template_y_axis_title_position_handles_reversed_binding_energy_axis() -> None:
    ops = _FakeOriginOps()

    _position_template_axis_titles_outside_plot(ops, "Graph1")

    joined = "\n".join(ops.commands)
    assert "if(layer.x.from>layer.x.to)" in joined
    assert "yl.x=layer.x.from+0.06*abs(layer.x.to-layer.x.from)" in joined


def test_template_y_axis_title_position_uses_template_offset_ratio() -> None:
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

    _position_template_axis_titles_outside_plot(ops, "Graph1", snapshot)

    joined = "\n".join(ops.commands)
    assert "yl.x=layer.x.from+0.061" in joined
    assert "xb.y=layer.y.from-0.180" in joined
    assert "0.08*abs(layer.x.to-layer.x.from)" not in joined


def test_template_xps_y_axis_title_overlay_uses_rotated_named_label(tmp_path: Path) -> None:
    ops = _FakeOriginOps()
    product = ProductContext(
        product_key="XPS_non_in_situ",
        slug="XPS_non_in_situ_BOBC_BC_exemplar_template",
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
        graph_title="XPS non-in-situ Bi exemplar",
        plot_type="line",
        x_descending=True,
    )

    status = _apply_template_xps_y_axis_title_overlay(ops, "Graph1", product, ResolvedPlotStyle())

    joined = "\n".join(ops.commands)
    assert status["applied"] is True
    assert 'label -p 8 50 -n TemplateYTitleFix "\\b(Intensity (a.u.))";' in joined
    assert "TemplateYTitleFix.rotate=90;" in joined
    assert "TemplateYTitleFix.x=layer.x.from+0.04*abs(layer.x.to-layer.x.from)" in joined
    assert "label -p -" not in joined


def test_template_xps_peak_annotations_use_current_peak_positions(tmp_path: Path) -> None:
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

    annotations = _xps_peak_annotations_from_processed_data(processed, product_title="XPS in-situ Bi exemplar")

    assert [item["text"] for item in annotations] == ["Bi 4f5/2 165.00 eV", "Bi 4f7/2 160.00 eV"]
    assert annotations[0]["x"] == 165.0
    assert annotations[1]["x"] == 160.0


def test_template_xps_peak_annotations_emit_origin_labels(tmp_path: Path) -> None:
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

    status = _apply_template_xps_peak_annotations(
        ops,
        "Graph1",
        processed,
        product_title="XPS in-situ Bi exemplar",
        style=ResolvedPlotStyle(title_font_size=18),
    )

    joined = "\n".join(ops.commands)
    assert status["applied"] is True
    assert status["annotation_count"] == 1
    assert "label -a 165" in joined
    assert "Bi 4f" in joined
    assert "165.00 eV" in joined
    assert "\\b(" not in joined


def test_template_prefers_xps_template_graph_matching_product_element() -> None:
    assert _preferred_template_xps_graph_name("XPS non-in-situ Bi exemplar", ["Br_3d", "Bi_4f", "Cl_2p"]) == "Bi_4f"
    assert _preferred_template_xps_graph_name("XPS in-situ W exemplar", ["Cu_2p", "W_4f"]) == "W_4f"


def test_template_selects_xps_reference_opju_containing_matching_graph(tmp_path: Path) -> None:
    pairing = TargetPairing("XPS_in_situ", "XPS", "XPS_in_situ", "", [], "", tmp_path / "unused.opju")
    product = ProductContext(
        product_key="XPS_in_situ",
        slug="XPS_in_situ_BOBC_exemplar_template",
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
        graph_title="XPS in-situ Bi exemplar",
        plot_type="line",
        x_descending=True,
    )
    cu_w = TemplateCandidate(
        "XPS_in_situ",
        tmp_path / "xps_in_situ_Cu_W.opju",
        "xps_reference_scan",
        status="extracted",
        graph_page="W_4f",
        layer_count=1,
        plot_count=14,
        metadata={"snapshot": {"graph_pages": ["Cu_2p", "W_4f"]}},
    )
    bi_cl_br = TemplateCandidate(
        "XPS_in_situ",
        tmp_path / "xps_in_situ_Bi_Cl_Br.opju",
        "xps_reference_scan",
        status="extracted",
        graph_page="Cl_2p",
        layer_count=1,
        plot_count=21,
        metadata={"snapshot": {"graph_pages": ["Br_3d", "Bi_4f", "Cl_2p"]}},
    )
    selection = TemplateSelection("XPS_in_situ", "selected", selected=cu_w, candidates=(cu_w, bi_cl_br))

    selected = _select_template_xps_template_for_product(product, selection)

    assert selected.path.name == "xps_in_situ_Bi_Cl_Br.opju"
    assert selected.graph_page == "Bi_4f"


def _write_epr_xlsx(path: Path, ys: list[float]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for index, y in enumerate(ys):
        sheet.append([324.0 + index * 0.0001, y])
    workbook.save(path)
