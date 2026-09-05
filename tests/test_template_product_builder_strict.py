from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook
from PIL import Image

from src.core.template_product_common import _xps_records_to_offset_table
from src.core.template_product_builder import (
    _apply_template_xps_component_fill,
    _apply_template_xps_peak_annotations,
    _apply_template_xps_y_axis_title_overlay,
    _build_template_acceptance,
    _build_template_epr_table,
    _build_template_eis_table,
    _build_template_bet_multisource_table,
    _build_template_xrd_multisource_table,
    _build_template_xy_multisource_table,
    _select_template_bet_candidate_cohort,
    _template_bet_series_label_from_path,
    _template_candidate_files,
    _template_display_path,
    _template_mott_candidate_files,
    _template_exact_shared_x_overlay_table,
    _template_independent_xy_table,
    _template_photocurrent_candidate_files,
    _template_pl_candidate_files,
    _template_same_x_overlay_table,
    _template_xy_series_label,
    _force_template_axis_titles_visible,
    _infer_template_epr_reference_dir,
    _load_independent_style_replay_evidence,
    _load_manifest_bound_otpu_replay_evidence,
    _position_template_axis_titles_outside_plot,
    _preferred_template_xps_graph_name,
    _adaptive_oth_json_detached_acceptance,
    _adaptive_oth_json_strict_readback_values,
    _relevant_strict_readback_values,
    _require_asset_only_style_integrity,
    _select_template_xps_template_for_product,
    _strict_style_readback,
    _template_conformance_acceptance_reasons,
    _template_origin_processing_script,
    _template_plot_count,
    _template_strict_visual_reasons,
    _validate_independent_style_replay_item,
    _template_epr_origin_processing_script,
    _template_epr_explicit_label,
    _prepare_template_epr_origin_processed_workbook,
    _create_template_epr_origin_processed_graph,
    _write_template_per_type_report,
    _write_template_identity_origin_processing_plan,
    _write_template_origin_processing_plan,
    _write_template_no_label_audit,
    _xps_peak_annotations_from_processed_data,
    build_template_candidate_pool,
    classify_template_project_style_asset_candidates,
    TemplateCandidate,
    TemplateSelection,
    is_template_xps_component_curve_header,
    template_plot_type_for_header,
    _write_template_preview_comparison,
    template_xps_component_fill_pairs,
    prepare_template_product,
)
from src.core.template_product_common import ProductContext, TargetPairing
from src.core.template_format_executor import _prepare_verified_mott_otpu_binding
from src.core.xps_heterojunction import XpsFitRecord
from src.origin.style_mimic import OpjuStyleSnapshot
from src.origin.user_style import ResolvedPlotStyle


def _write_template_eis_csv(path: Path, points: list[tuple[float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Freq (Hz);Z' (kOhm);-Z'' (kOhm)"]
    lines.extend(f"{1000 / (index + 1)};{real};{imag}" for index, (real, imag) in enumerate(points))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validated_style_entry(
    product_key: str,
    graph_page: str,
    format_theme: str,
    **extra: object,
) -> dict[str, object]:
    return {
        "product_key": product_key,
        "data_type": product_key,
        "status": "accepted",
        "graph_page": graph_page,
        "format_theme": format_theme,
        "runtime_validation": {
            "status": "accepted",
            "comparison_scope": "fresh_project_same_data",
            "fresh_project_verified": True,
            "style_asset_only": True,
            "same_data_verified": True,
            "reference_plot_values_sha256": "1" * 64,
            "generated_plot_values_sha256": "1" * 64,
            "reference_plot_mapping_sha256": "2" * 64,
            "generated_plot_mapping_sha256": "2" * 64,
            "saved_reopened": True,
            "native_tif_600dpi_verified": True,
            "manual_preview_passed": True,
            "exact_pixel_match": True,
            "same_size": True,
            "changed_pixels": 0,
            "rms": 0,
            "reference_opju_self_replay": False,
        },
        **extra,
    }


def _adaptive_oth_json_export_status(*, series_count: int = 2) -> dict[str, object]:
    conformance = {
        "status": "pass",
        "compared_fields": 8,
        "matched_fields": 8,
        "axis_title_bold": True,
        "issues": [],
    }
    validation = {
        "ok": True,
        "status": "accepted",
        "current_csv_pair_count": series_count,
        "reopened_plot_count": series_count,
        "series_cardinality_relaxed": True,
        "one_to_one_claim_allowed": False,
        "saved_reopened": True,
        "native_tif_600dpi_required": True,
    }
    tif = {
        "requested_dpi": 600,
        "width_px": 1200,
        "height_px": 900,
        "expected_width_px": 1200,
        "expected_height_px": 900,
        "pixel_tolerance_x": 6,
        "pixel_tolerance_y": 5,
        "tagged_dpi_x": 600.0,
        "tagged_dpi_y": 600.0,
        "effective_dpi_x": 600.0,
        "effective_dpi_y": 600.0,
        "sensitive_metadata_scan": "pass",
    }
    return {
        "ok": True,
        "product_style": {
            "plot_count": series_count,
            "plot_line_widths": [30.0] * series_count,
        },
        "strict_style_readback": {
            "font_family_arial": True,
            "axis_title_font_size_36": True,
            "axis_title_bold": True,
            "axis_title_visible": True,
            "axis_title_no_overlap": True,
            "legend_no_frame": True,
            "legend_bold": True,
        },
        "conformance": conformance,
        "adaptive_oth_json_validation": validation,
        "tif_resolution_evidence": tif,
        "origin_processing": {
            "applied": True,
            "processing_location": "Origin clean target graph with project-local OTH and JSON",
            "method": "saved_format_theme_apply",
            "style_execution_mode": "variable_structure_oth_json",
            "adaptive_oth_json_validation": validation,
            "tif_resolution_evidence": tif,
            "reference_opju_loaded": False,
            "reference_opju_used_as_product_base": False,
        },
    }


class _FakeOriginOps:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def _plot_names(self, _graph_name: str) -> list[str]:
        return ["measured", "envelope", "component1", "baseline1"]

    def run_labtalk(self, command: str) -> None:
        self.commands.append(command)


def test_reference_opju_self_replay_cannot_validate_saved_style_asset(
    tmp_path: Path,
) -> None:
    result = _validate_independent_style_replay_item(
        tmp_path,
        "BET",
        {
            "product_key": "BET",
            "status": "reference_opju_self_replay",
            "style_asset_validated": False,
            "comparison_scope": "reference_opju_self_replay",
            "asset_generation_mode": "reference_opju_reexport",
            "source_opju_sha256": "a" * 64,
            "generated_opju_sha256": "a" * 64,
            "comparison": {"exact_pixel_match": True, "rms": 0.0},
        },
    )

    assert result["ok"] is False
    reason = str(result["reason"])
    assert "status is not matched" in reason
    assert "style_asset_validated is false" in reason
    assert "comparison_scope is not fresh_project_same_data" in reason
    assert "source and generated OPJU hashes are identical" in reason


def test_checked_in_bet_otpu_evidence_is_manifest_bound_and_tamper_detected(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[1]
    evidence = (
        project
        / "templates"
        / "origin_styles"
        / "validation_evidence"
        / "BET_verified_20260813.json"
    )

    loaded = _load_independent_style_replay_evidence(project, evidence)

    assert loaded["bet"]["ok"] is True
    assert loaded["bet"]["asset_generation_mode"] == "new_graph_plus_verified_otpu"

    tampered = tmp_path / "BET_tampered.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["pixels"]["changed_pixels"] = 1
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    rejected = _load_independent_style_replay_evidence(project, tampered)

    assert rejected["bet"]["ok"] is False
    assert "changed-pixel count is not zero" in rejected["bet"]["reason"]
    assert "validation evidence does not match" in rejected["bet"]["reason"]


def test_asset_only_autoloads_current_manifest_bound_otpu_evidence() -> None:
    project = Path(__file__).resolve().parents[1]

    loaded = _require_asset_only_style_integrity(project, ("BET", "EIS"))

    assert set(loaded) == {"bet", "eis"}
    assert all(item["ok"] is True for item in loaded.values())
    assert loaded["eis"]["asset_generation_mode"] == "new_graph_plus_verified_otpu"


def test_manifest_autoload_fails_closed_when_bound_otpu_evidence_is_tampered(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[1]
    copied_styles = tmp_path / "templates" / "origin_styles"
    shutil.copytree(project / "templates" / "origin_styles", copied_styles)
    evidence = copied_styles / "validation_evidence" / "EIS_verified_20260822.json"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["pixels"]["changed_pixels"] = 1
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    loaded = _load_manifest_bound_otpu_replay_evidence(tmp_path, ("EIS",))

    assert loaded["eis"]["ok"] is False
    assert "unavailable" in str(loaded["eis"]["reason"])
    try:
        _require_asset_only_style_integrity(tmp_path, ("EIS",))
    except ValueError as exc:
        assert "runtime style asset" in str(exc)
    else:
        raise AssertionError("asset-only mode must reject a tampered manifest-bound OTPU evidence file")


def test_no_label_audit_excludes_internal_run_manifest_paths_only(tmp_path: Path) -> None:
    (tmp_path / "run_manifest.json").write_text(
        json.dumps({"input_paths": [".codex_tmp/Codex_pairing.json"]}),
        encoding="utf-8",
    )
    visible_text = tmp_path / "products" / "EIS" / "visible_graph_label.txt"
    visible_text.parent.mkdir(parents=True)
    visible_text.write_text("Generated by Codex", encoding="utf-8")

    audit = _write_template_no_label_audit(tmp_path)

    assert audit["hit_count"] == 2
    assert audit["path_only_hit_count"] == 0
    assert {item["label"] for item in audit["hits"]} == {"Codex", "Generated by"}
    assert all(item["path"] != "run_manifest.json" for item in audit["hits"])


def test_no_label_audit_ignores_origin_dataset_provenance_but_checks_visible_labels(
    tmp_path: Path,
) -> None:
    metadata = tmp_path / "products" / "EPR" / "metadata.json"
    metadata.parent.mkdir(parents=True)
    payload = {
        "template_binding": {
            "plots": [
                {
                    "x_dataset": "CodexProjectR_A",
                    "y_dataset": "CodexProjectR_B",
                }
            ]
        },
        "label_policy": {"objects": {"DL1": "BC"}},
    }
    metadata.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    provenance_only = _write_template_no_label_audit(tmp_path)

    assert provenance_only["pass"] is True
    payload["label_policy"] = {"objects": {"DL1": "Codex"}}
    metadata.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    visible_label = _write_template_no_label_audit(tmp_path)

    assert visible_label["pass"] is False
    assert any(item["path"] == "products/EPR/metadata.json" for item in visible_label["hits"])


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


def test_template_mott_candidate_selection_preserves_all_explicit_frequencies(tmp_path: Path) -> None:
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

    assert [path.stem for path in selected] == [
        "1000",
        "1500",
        "2000",
        "2500",
        "3000",
        "3500",
        "4000",
    ]


def test_template_mott_auto_five_series_builder_output_satisfies_fixed_binding(
    tmp_path: Path,
) -> None:
    paths: list[Path] = []
    for series_index, frequency in enumerate((1500, 2000, 2500, 3000, 3500), start=1):
        path = tmp_path / f"{frequency}.csv"
        path.write_text(
            "potential,1/c2\n"
            f"-0.05,{series_index}.0\n"
            f"0.00,{series_index + 1}.0\n"
            f"0.05,{series_index + 2}.0\n",
            encoding="utf-8",
        )
        paths.append(path)
    reference = tmp_path / "Mott_Schottky.opju"
    reference.write_bytes(b"opju placeholder")
    pairing = TargetPairing(
        product_key="Mott-Schottky",
        data_type="Mott-Schottky",
        xps_subtype="",
        data_root_label="test",
        data_paths=paths,
        opju_root_label="test",
        reference_opju=reference,
    )
    template = TemplateCandidate(
        "Mott-Schottky",
        reference,
        "unit",
        graph_page="Graph2",
        plot_count=5,
    )

    built = _build_template_xy_multisource_table(
        pairing,
        template,
        origin_style_mode="auto",
    )

    assert built is not None
    assert built["alignment"]["style_execution_mode_selected"] == "otpu"
    assert built["labels"]["legend_entries"] == [
        "1500Hz BiOBr0.5Cl0.5",
        "2000Hz BiOBr0.5Cl0.5",
        "2500Hz BiOBr0.5Cl0.5",
        "3000Hz BiOBr0.5Cl0.5",
        "3500Hz BiOBr0.5Cl0.5",
    ]
    product = ProductContext(
        product_key="Mott-Schottky",
        slug="Mott_Schottky",
        pairing=pairing,
        type_root=tmp_path,
        processed_data=tmp_path / "processed.csv",
        input_copies=[],
        reference_opju_copy=reference,
        reference_preview_png=tmp_path / "reference.png",
        origin_file=tmp_path / "product.opju",
        figure_tif=tmp_path / "product.tif",
        preview_png=tmp_path / "product.png",
        x_label=str(built["labels"]["x_label"]),
        y_label=str(built["labels"]["y_label"]),
        graph_title=str(built["labels"]["title"]),
        plot_type=str(built["labels"]["plot_type"]),
        legend_entries=list(built["labels"]["legend_entries"]),
    )
    contract = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "Mott_Schottky.json"
    )

    binding = _prepare_verified_mott_otpu_binding(
        product,
        list(built["headers"]),
        list(built["rows"]),
        contract_path=contract,
    )

    assert binding["ok"] is True
    assert binding["book_name"] == "Book1"
    assert len(binding["xy_ranges"]) == 5


def test_template_mott_exact_shared_x_rejects_interpolation() -> None:
    headers, rows = _template_exact_shared_x_overlay_table(
        "potential_v",
        [
            ("1500_one_over_c_squared", [[-0.1, 1.0], [0.0, 2.0]]),
            ("2000_one_over_c_squared", [[-0.1, 3.0], [0.0, 4.0]]),
        ],
    )

    assert headers == [
        "potential_v",
        "1500_one_over_c_squared",
        "2000_one_over_c_squared",
    ]
    assert rows == [[-0.1, 1.0, 3.0], [0.0, 2.0, 4.0]]
    with pytest.raises(ValueError, match="interpolation is forbidden"):
        _template_exact_shared_x_overlay_table(
            "potential_v",
            [
                ("1500_one_over_c_squared", [[-0.1, 1.0], [0.0, 2.0]]),
                ("2000_one_over_c_squared", [[-0.1, 3.0], [0.1, 4.0]]),
            ],
        )


def test_template_display_path_hides_workspace_prefixes() -> None:
    template = Path("D:/Codex Project/科研数据处理/ResearchDataOriginPipeline/templates/origin_styles/format_themes/BET.oth")
    external = Path("F:/课题/LL/检测/BET/BOBC.opju")

    assert _template_display_path(template) == "templates/origin_styles/format_themes/BET.oth"
    assert _template_display_path(external) == "external/BOBC.opju"


def test_project_style_asset_candidate_does_not_preseed_manifest_preview_as_runtime_reference(tmp_path: Path) -> None:
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
                "schema_version": 2,
                "assets": [
                    _validated_style_entry(
                        "Raman",
                        "Graph4",
                        "format_themes/Raman.oth",
                        reference_preview_png="previews/Raman_reference.png",
                        template_plot_count=3,
                        layer_count=1,
                    )
                ],
            }
        ),
        encoding="utf-8",
    )

    [candidate] = classify_template_project_style_asset_candidates(project)
    copied = tmp_path / "run" / "Raman" / "reference_exports" / "Raman_reference.png"

    assert candidate.plot_count == 3
    assert candidate.layer_count == 1
    assert candidate.metadata["style_asset"]["reference_preview_png"]
    assert not copied.exists()


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
                "schema_version": 2,
                "assets": [
                    _validated_style_entry(
                        "BET",
                        "Graph5",
                        "format_themes/BET.oth",
                        style_snapshot="snapshots/BET.json",
                    )
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
                "schema_version": 2,
                "assets": [
                    _validated_style_entry(
                        "photocurrent",
                        "Graph1",
                        "format_themes/photocurrent.oth",
                        template_opju="reference_opju/photocurrent.opju",
                        template_plot_count=3,
                    )
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
                "Bi4f Scan B": 19.0,
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

    reviewed_headers, reviewed_rows = _xps_records_to_offset_table(
        [record],
        include_envelope=True,
        include_components=True,
        component_fill_mode="template_line_fill",
        series_layout="in_situ_template",
        vertical_offsets=(2.82,),
        higher_binding_component_first=True,
    )
    assert reviewed_headers == in_situ_headers
    assert min(row[1] for row in reviewed_rows) == pytest.approx(2.82)
    assert max(row[1] for row in reviewed_rows) == pytest.approx(3.82)
    assert reviewed_rows[0][2] > reviewed_rows[1][2]
    assert reviewed_rows[0][4] < reviewed_rows[1][4]

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


def test_template_writes_template_vs_generated_preview_comparison(tmp_path: Path, monkeypatch) -> None:
    reference = tmp_path / "BET" / "reference_exports" / "BET_reference.png"
    generated = tmp_path / "BET" / "figures_preview" / "BET_preview.png"
    metadata = tmp_path / "BET" / "metadata" / "BET.json"
    reference.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), "white").save(reference)
    Image.new("RGB", (16, 12), "black").save(generated)
    opened_paths = []
    image_open = Image.open

    def counted_open(path, *args, **kwargs):
        opened_paths.append(path)
        return image_open(path, *args, **kwargs)

    monkeypatch.setattr(Image, "open", counted_open)
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
    assert audit["items"][0]["preview_rms"] == 255.0
    assert opened_paths.count(reference) == 1
    assert opened_paths.count(generated) == 1
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


def test_saved_format_theme_requires_ready_preview_comparison_even_when_plot_count_matches(tmp_path: Path) -> None:
    generated = tmp_path / "BET" / "figures_preview" / "BET_preview.png"
    metadata = tmp_path / "BET" / "metadata" / "BET.json"
    report = tmp_path / "BET" / "reports" / "BET_report.md"
    generated.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), "white").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "status": "accepted",
                "visual_acceptance": True,
                "acceptance_notes": [],
                "template_plot_count": 1,
                "origin_status": {
                    "template_format_plan": {"mode": "saved_format_theme"},
                    "origin_processing": {"method": "saved_format_theme_apply"},
                    "product_style": {"plot_count": 1},
                    "conformance": {"compared_fields": 4, "matched_fields": 4},
                },
                "origin_processing": {"method": "saved_format_theme_apply"},
                "source_files": ["raw1.csv"],
            }
        ),
        encoding="utf-8",
    )
    report.write_text(
        "# BET template-format report\n\n- Status: accepted\n- Visual acceptance: True\n",
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "visual_acceptance": True,
        "reference_preview_png": str(tmp_path / "missing_reference.png"),
        "preview_png": str(generated),
        "metadata": str(metadata),
        "report": str(report),
        "template_format_mode": "saved_format_theme",
        "origin_processing_method": "saved_format_theme_apply",
        "notes": "Origin saved format-theme export succeeded.",
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    assert product["status"] == "blocked"
    assert audit["ready_count"] == 0
    assert audit["items"][0]["strict_status"] == "blocked_not_one_to_one"
    assert audit["items"][0]["saved_style_asset_mode"] is True
    assert audit["items"][0]["plot_count_delta"] == 0
    assert "comparison is not ready" in audit["items"][0]["message"]
    persisted = json.loads(metadata.read_text(encoding="utf-8"))
    assert persisted["status"] == "blocked"
    assert persisted["visual_acceptance"] is False
    assert persisted["reference_preview_available"] is False
    assert persisted["template_preview_comparison_ready"] is False
    assert persisted["visual_acceptance_audit"]["strict_status"] == "blocked_not_one_to_one"
    persisted_report = report.read_text(encoding="utf-8")
    assert "- Status: blocked" in persisted_report
    assert "- Visual acceptance: False" in persisted_report
    assert "## Final visual acceptance audit" in persisted_report
    assert "- Independent reference preview: missing" in persisted_report


def test_template_acceptance_requires_independent_reference_preview(tmp_path: Path) -> None:
    type_root = tmp_path / "BET"
    type_root.mkdir()
    product = ProductContext(
        product_key="BET",
        slug="BET_template",
        pairing=TargetPairing("BET", "BET", "", "", [], "", tmp_path / "template.opju"),
        type_root=type_root,
        processed_data=type_root / "processed.csv",
        input_copies=[],
        reference_opju_copy=type_root / "template.opju",
        reference_preview_png=type_root / "reference.png",
        origin_file=type_root / "product.opju",
        figure_tif=type_root / "product.tif",
        preview_png=type_root / "product.png",
        x_label="Relative Pressure",
        y_label="Quantity Adsorbed",
        graph_title="BET",
        plot_type="line",
        x_descending=False,
    )
    for path in (product.processed_data, product.reference_opju_copy, product.origin_file, product.figure_tif):
        path.write_bytes(b"artifact")
    Image.new("RGB", (16, 12), "white").save(product.preview_png)
    template = TemplateCandidate(
        product_key="BET",
        path=product.reference_opju_copy,
        source="unit",
        status="valid",
        graph_page="Graph1",
        layer_count=1,
        plot_count=1,
    )
    export_status = {
        "ok": True,
        "product_style": {"plot_line_widths": [30.0]},
        "conformance": {"axis_title_bold": True},
        "axis_title_bold_policy": True,
        "origin_processing": {
            "applied": True,
            "processing_location": "Origin workbook",
            "method": "opju_template_base_workbook_replacement",
        },
    }

    missing_reference = _build_template_acceptance(product, export_status, template, {})

    assert missing_reference.status == "blocked"
    assert missing_reference.visual_acceptance is False
    assert any("independent reference preview" in note for note in missing_reference.notes)

    verified_status = {
        **export_status,
        "origin_processing": {
            **export_status["origin_processing"],
            "method": "fresh_graph_verified_otpu_explicit_xy",
        },
    }
    verified_without_runtime_reference = _build_template_acceptance(
        product,
        verified_status,
        template,
        {},
    )

    assert verified_without_runtime_reference.status == "accepted"
    assert verified_without_runtime_reference.visual_acceptance is True
    assert not any(
        "independent reference preview" in note
        for note in verified_without_runtime_reference.notes
    )

    Image.new("RGB", (16, 12), "black").save(product.reference_preview_png)
    with_reference = _build_template_acceptance(product, export_status, template, {})

    assert with_reference.status == "accepted"
    assert with_reference.visual_acceptance is True


def test_adaptive_oth_json_acceptance_uses_detached_current_product_evidence_without_reference_preview(
    tmp_path: Path,
) -> None:
    type_root = tmp_path / "FTIR"
    type_root.mkdir()
    product = ProductContext(
        product_key="FTIR",
        slug="FTIR_product",
        pairing=TargetPairing("FTIR", "FTIR", "", "", [], "", tmp_path / "template.opju"),
        type_root=type_root,
        processed_data=type_root / "processed.csv",
        input_copies=[],
        reference_opju_copy=type_root / "template.opju",
        reference_preview_png=type_root / "missing_reference.png",
        origin_file=type_root / "product.opju",
        figure_tif=type_root / "product.tif",
        preview_png=type_root / "product.png",
        x_label="Wavenumber",
        y_label="Transmittance",
        graph_title="FTIR",
        plot_type="line",
        x_descending=True,
    )
    for path in (product.processed_data, product.reference_opju_copy, product.origin_file, product.figure_tif):
        path.write_bytes(b"artifact")
    Image.new("RGB", (16, 12), "white").save(product.preview_png)
    template = TemplateCandidate(
        "FTIR",
        product.reference_opju_copy,
        "unit",
        status="valid",
        graph_page="Graph3",
        layer_count=1,
        plot_count=3,
    )
    export_status = _adaptive_oth_json_export_status(series_count=2)

    accepted = _build_template_acceptance(product, export_status, template, {})

    assert accepted.status == "accepted"
    assert accepted.visual_acceptance is True
    assert not any("independent reference preview" in note for note in accepted.notes)

    missing_tif_evidence = dict(export_status)
    missing_tif_evidence["tif_resolution_evidence"] = {}
    missing_tif_evidence["origin_processing"] = {
        **export_status["origin_processing"],
        "tif_resolution_evidence": {},
    }
    blocked = _build_template_acceptance(product, missing_tif_evidence, template, {})

    assert blocked.status == "blocked"
    assert any("native 600 dpi TIFF evidence" in note for note in blocked.notes)


def test_adaptive_oth_json_preview_gate_allows_template_plot_delta_but_never_one_to_one(
    tmp_path: Path,
) -> None:
    product_root = tmp_path / "FTIR"
    product_root.mkdir()
    generated = product_root / "product.png"
    Image.new("RGB", (16, 12), "white").save(generated)
    origin_status = _adaptive_oth_json_export_status(series_count=2)
    metadata = product_root / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "extra": {"template": {"plot_count": 3}},
                "origin_status": origin_status,
                "source_files": ["BOBC.dpt", "BC.dpt"],
            }
        ),
        encoding="utf-8",
    )
    product = {
        "type": "FTIR",
        "status": "accepted",
        "visual_acceptance": True,
        "metadata": str(metadata),
        "reference_preview_png": str(product_root / "missing_reference.png"),
        "preview_png": str(generated),
        "conformance": origin_status["conformance"],
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    item = audit["items"][0]
    assert item["plot_count_delta"] == -1
    assert item["strict_visual_match"] is True
    assert item["strict_status"] == "adaptive_oth_json_style_match"
    assert item["style_data_binding"]["runtime_reference_preview_required"] is False
    assert item["style_data_binding"]["plot_structure_pass"] is True
    assert item["one_to_one_exact_match"] is False
    assert product["one_to_one_exact_match"] is False
    assert product["status"] == "accepted"


def test_eis_formal_acceptance_requires_all_measured_points_and_no_fit_outputs(tmp_path: Path) -> None:
    type_root = tmp_path / "EIS"
    type_root.mkdir()
    product = ProductContext(
        product_key="EIS",
        slug="EIS_template",
        pairing=TargetPairing("EIS", "EIS", "", "", [], "", tmp_path / "template.opju"),
        type_root=type_root,
        processed_data=type_root / "processed.csv",
        input_copies=[],
        reference_opju_copy=type_root / "template.opju",
        reference_preview_png=type_root / "reference.png",
        origin_file=type_root / "product.opju",
        figure_tif=type_root / "product.tif",
        preview_png=type_root / "product.png",
        x_label="Z' (kOhm)",
        y_label="-Z'' (kOhm)",
        graph_title="EIS measured data",
        plot_type="line+symbol",
        x_descending=False,
    )
    product.processed_data.write_text(
        "measured_z_real_kohm,measured_minus_z_imag_kohm\n1,2\n2,3\n3,4\n",
        encoding="utf-8",
    )
    for path in (product.reference_opju_copy, product.origin_file, product.figure_tif):
        path.write_bytes(b"artifact")
    Image.new("RGB", (16, 12), "black").save(product.reference_preview_png)
    Image.new("RGB", (16, 12), "white").save(product.preview_png)
    template = TemplateCandidate(
        product_key="EIS",
        path=product.reference_opju_copy,
        source="unit",
        status="valid",
        graph_page="Graph1",
        layer_count=1,
        plot_count=1,
    )
    export_status = {
        "ok": True,
        "product_style": {"plot_line_widths": [30.0]},
        "conformance": {"axis_title_bold": True},
        "axis_title_bold_policy": True,
        "origin_processing": {
            "applied": True,
            "processing_location": "Origin workbook",
            "method": "opju_template_base_workbook_replacement",
        },
    }
    extra = {
        "eis_cleaning": {
            "mode": "formal_measured_points_only",
            "raw_point_count": 3,
            "plotted_point_count": 3,
            "fit": {"status": "not_run"},
        }
    }

    accepted = _build_template_acceptance(product, export_status, template, extra)

    assert accepted.status == "accepted"
    assert accepted.visual_acceptance is True
    assert not any("fit" in note.casefold() for note in accepted.notes)
    report_path = _write_template_per_type_report(
        tmp_path,
        product,
        export_status,
        ResolvedPlotStyle(),
        extra,
        template,
        accepted,
    )
    report_text = report_path.read_text(encoding="utf-8")
    assert "## EIS measured-data product" in report_text
    assert "Fit status: not_run" in report_text
    assert "EIS cleaning and draft fit" not in report_text
    assert "Model A: Rs + (Rct || CPE)" not in report_text

    product.processed_data.write_text(
        "measured_z_real_kohm,measured_minus_z_imag_kohm,draft_fit_minus_z_imag_kohm\n1,2,2\n",
        encoding="utf-8",
    )
    fit_column_blocked = _build_template_acceptance(product, export_status, template, extra)

    assert fit_column_blocked.status == "blocked"
    assert fit_column_blocked.visual_acceptance is False
    assert any("fit columns" in note for note in fit_column_blocked.notes)

    product.processed_data.write_text(
        "measured_z_real_kohm,measured_minus_z_imag_kohm\n1,2\n2,3\n3,4\n",
        encoding="utf-8",
    )
    fit_sidecar = type_root / "debug" / "eis_randles_cpe_fit_curve.csv"
    fit_sidecar.parent.mkdir(exist_ok=True)
    fit_sidecar.write_text("x,y\n1,2\n", encoding="utf-8")
    fit_sidecar_blocked = _build_template_acceptance(product, export_status, template, extra)

    assert fit_sidecar_blocked.status == "blocked"
    assert fit_sidecar_blocked.visual_acceptance is False
    assert any("fit sidecars" in note for note in fit_sidecar_blocked.notes)


def test_label_audit_failure_is_persisted_after_successful_preview_comparison(tmp_path: Path) -> None:
    product_root = tmp_path / "BET"
    reference = product_root / "reference.png"
    generated = product_root / "generated.png"
    metadata = product_root / "metadata.json"
    report = product_root / "report.md"
    product_root.mkdir()
    Image.new("RGB", (16, 12), "white").save(reference)
    Image.new("RGB", (16, 12), "white").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "status": "accepted",
                "visual_acceptance": True,
                "acceptance_notes": [],
                "template_plot_count": 1,
                "origin_status": {
                    "product_style": {"plot_count": 1},
                    "conformance": {"compared_fields": 4, "matched_fields": 4},
                },
            }
        ),
        encoding="utf-8",
    )
    report.write_text(
        "# BET template-format report\n\n- Status: accepted\n- Visual acceptance: True\n",
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "visual_acceptance": True,
        "reference_preview_png": str(reference),
        "preview_png": str(generated),
        "metadata": str(metadata),
        "report": str(report),
    }

    audit = _write_template_preview_comparison(
        tmp_path,
        [product],
        label_audit={"hit_count": 1, "path_only_hits": []},
    )

    assert audit["items"][0]["strict_visual_match"] is True
    assert audit["items"][0]["status"] == "blocked"
    assert product["status"] == "blocked"
    assert product["visual_acceptance"] is False
    persisted = json.loads(metadata.read_text(encoding="utf-8"))
    assert persisted["status"] == "blocked"
    assert persisted["visual_acceptance"] is False
    assert persisted["visual_acceptance_audit"]["label_audit_pass"] is False
    assert "no-label audit failed" in persisted["acceptance_notes"]
    persisted_report = report.read_text(encoding="utf-8")
    assert "- Final status: blocked" in persisted_report
    assert "- No-label audit pass: False" in persisted_report


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
    assert audit["items"][0]["strict_visual_match_deprecated"] is True
    assert audit["items"][0]["style_data_binding"]["status"] == "matched"
    assert audit["items"][0]["same_data_exact"]["status"] == "not_evaluated"
    assert audit["items"][0]["current_product_pixel_exact"]["claim_allowed"] is False
    assert audit["items"][0]["one_to_one_exact_match"] is False
    assert audit["items"][0]["reference_preview_png"] == "BET/reference_exports/BET_reference.png"
    assert audit["items"][0]["generated_preview_png"] == "BET/figures_preview/BET_preview.png"
    assert audit["items"][0]["side_by_side_png"] == "reports/template_preview_comparisons/BET_template_vs_generated.png"


def test_validated_otpu_current_data_rms_is_review_signal_not_style_failure(
    tmp_path: Path,
) -> None:
    product_root = tmp_path / "products" / "BET"
    product_root.mkdir(parents=True)
    reference = product_root / "reference.png"
    generated = product_root / "generated.png"
    metadata = product_root / "metadata.json"
    Image.new("RGB", (32, 24), "white").save(reference)
    Image.new("RGB", (32, 24), "black").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 1,
                "origin_status": {
                    "template_format_plan": {"mode": "verified_graph_template"},
                    "origin_processing": {
                        "method": "fresh_graph_verified_otpu_explicit_xy"
                    },
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
        "visual_acceptance": True,
        "template_format_mode": "verified_graph_template",
        "origin_processing_method": "fresh_graph_verified_otpu_explicit_xy",
        "reference_preview_png": str(reference),
        "preview_png": str(generated),
        "metadata": str(metadata),
    }

    audit = _write_template_preview_comparison(
        tmp_path,
        [product],
        style_replay_evidence={"bet": {"ok": True, "reason": "validated"}},
    )

    item = audit["items"][0]
    assert item["preview_rms"] > 35.0
    assert item["style_data_binding"]["status"] == "matched"
    assert item["style_data_binding"]["preview_review_is_diagnostic_only"] is True
    assert item["style_data_binding"]["review_reasons"]
    assert item["strict_visual_match"] is True
    assert product["status"] == "accepted"
    report = (tmp_path / "reports" / "template_preview_comparison.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in report


def test_validated_otpu_does_not_require_runtime_reference_preview(tmp_path: Path) -> None:
    product_root = tmp_path / "products" / "BET"
    product_root.mkdir(parents=True)
    generated = product_root / "generated.png"
    metadata = product_root / "metadata.json"
    Image.new("RGB", (32, 24), "white").save(generated)
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 1,
                "origin_status": {
                    "template_format_plan": {"mode": "verified_graph_template"},
                    "origin_processing": {
                        "method": "fresh_graph_verified_otpu_explicit_xy"
                    },
                    "product_style": {"plot_count": 1},
                    "conformance": {"compared_fields": 4, "matched_fields": 4},
                },
            }
        ),
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "visual_acceptance": True,
        "template_format_mode": "verified_graph_template",
        "reference_preview_png": str(product_root / "missing_reference.png"),
        "preview_png": str(generated),
        "metadata": str(metadata),
    }

    audit = _write_template_preview_comparison(
        tmp_path,
        [product],
        style_replay_evidence={"bet": {"ok": True, "reason": "validated"}},
    )

    item = audit["items"][0]
    assert item["strict_visual_match"] is True
    assert item["style_data_binding"]["status"] == "matched"
    assert item["style_data_binding"]["preview_comparison_ready"] is False
    assert item["style_data_binding"]["runtime_reference_preview_required"] is False
    assert product["status"] == "accepted"


def test_template_raman_uses_only_explicit_independent_pairs_without_interpolation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("src.core.template_product_builder._template_candidate_files", lambda *args: pytest.fail("explicit Raman sources must not trigger a discarded directory scan"))
    data_root = tmp_path / "raman"
    data_root.mkdir()
    first = data_root / "BOBC.txt"
    second = data_root / "CWO.txt"
    unrelated = data_root / "unrelated.txt"
    first.write_text("300 14\n100 10\n100 11\n", encoding="utf-8")
    second.write_text("500 20\n600 22\n", encoding="utf-8")
    unrelated.write_text("1 999\n2 999\n", encoding="utf-8")
    template_path = data_root / "template.opju"
    template_path.write_bytes(b"opju placeholder")

    pairing = TargetPairing(
        product_key="Raman",
        data_type="Raman",
        xps_subtype="",
        data_root_label="tmp",
        data_paths=[first, second],
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
    assert aligned["headers"] == [
        "BOBC_raman_shift_cm-1",
        "BOBC_intensity",
        "CWO_raman_shift_cm-1",
        "CWO_intensity",
    ]
    assert aligned["rows"] == [
        [300.0, 14.0, 500.0, 20.0],
        [100.0, 10.0, 600.0, 22.0],
        [100.0, 11.0, None, None],
    ]
    assert aligned["labels"]["legend_entries"] == ["BOBC", "CWO"]
    alignment = aligned["alignment"]
    assert alignment["template_plot_count"] == 3
    assert alignment["product_series_count"] == 2
    assert alignment["missing_template_series_count"] == 1
    assert alignment["fabrication_policy"] == "do_not_synthesize_missing_template_series"
    assert alignment["used_files"] == [str(first), str(second)]
    assert alignment["interpolation"] == "not_applied"


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


def test_template_independent_xy_table_preserves_order_and_does_not_interpolate() -> None:
    headers, rows = _template_independent_xy_table(
        "relative_pressure_p_p0",
        "quantity_adsorbed_cm3_g_stp",
        [
            ("sample_adsorption", [[0.1, 10.0], [0.9, 90.0]]),
            ("sample_desorption", [[0.95, 95.0], [0.4, 40.0], [0.2, 20.0]]),
        ],
    )

    assert headers == [
        "sample_adsorption_relative_pressure_p_p0",
        "sample_adsorption_quantity_adsorbed_cm3_g_stp",
        "sample_desorption_relative_pressure_p_p0",
        "sample_desorption_quantity_adsorbed_cm3_g_stp",
    ]
    assert rows == [
        [0.1, 10.0, 0.95, 95.0],
        [0.9, 90.0, 0.4, 40.0],
        [None, None, 0.2, 20.0],
    ]


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


def test_template_epr_finds_the_current_chinese_export_directory(
    tmp_path: Path,
) -> None:
    epr_root = tmp_path / "EPR"
    reference_dir = epr_root / "导出后的数据"
    reference_dir.mkdir(parents=True)
    for name in (
        "BC-OH-light2.xlsx",
        "CWO-OH-light2.xlsx",
        "BOBC-OH-light1.xlsx",
    ):
        (reference_dir / name).write_bytes(b"placeholder")

    selected = _infer_template_epr_reference_dir(
        [epr_root / "seed.xlsx"],
        "OH",
    )

    assert selected == reference_dir


def test_template_eis_explicit_oth_json_uses_only_paired_curves_and_preserves_lengths(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "EIS" / "current"
    selected = [
        source_dir / "sample_A.csv",
        source_dir / "sample_B.csv",
    ]
    _write_template_eis_csv(selected[0], [(1.0, 0.5), (2.0, 0.4), (3.0, 0.2)])
    _write_template_eis_csv(selected[1], [(10.0, 2.0), (20.0, 1.5)])
    neighbour = source_dir / "neighbour.csv"
    _write_template_eis_csv(neighbour, [(999.0, 999.0), (1000.0, 999.0)])
    reference = tmp_path / "template.opju"
    reference.write_bytes(b"placeholder")
    pairing = TargetPairing("EIS", "EIS", "", "root", selected, "root", reference)
    template = TemplateCandidate("EIS", reference, "unit", graph_page="Graph1", plot_count=8)

    product, extra = prepare_template_product(
        tmp_path / "run",
        pairing,
        template,
        compact_output=True,
        origin_style_mode="oth-json",
    )

    assert product.pairing.data_paths == selected
    assert extra["eis_overlay"]["source_files"] == [str(path) for path in selected]
    assert extra["eis_overlay"]["plotted_source_count"] == 2
    assert extra["eis_overlay"]["visible_plot_indices"] == [1, 2]
    assert extra["eis_overlay"]["visible_series_labels"] == ["sample A", "sample B"]
    assert extra["eis_overlay"]["selection_policy"].startswith("Use exactly pairing.data_paths")
    assert extra["eis_overlay"]["source_selection_mode"] == "explicit_pairing_adaptive_oth_json"
    assert product.legend_entries == ["sample A", "sample B"]
    rows = product.processed_data.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "sample_A_z_real_kohm,sample_A_minus_z_imag_kohm,sample_B_z_real_kohm,sample_B_minus_z_imag_kohm"
    assert len(rows) == 4
    assert rows[-1].endswith(",,")
    assert "999" not in product.processed_data.read_text(encoding="utf-8")


def test_template_eis_fixed_route_keeps_exactly_eight_discovered_curves(tmp_path: Path) -> None:
    source_dir = tmp_path / "EIS" / "reviewed_cohort"
    selected = source_dir / "trace_1.csv"
    paths = [source_dir / f"trace_{index}.csv" for index in range(1, 9)]
    for index, path in enumerate(paths, start=1):
        _write_template_eis_csv(
            path,
            [(float(index + point), 0.5 / (point + 1)) for point in range(10)],
        )
    reference = tmp_path / "template.opju"
    reference.write_bytes(b"placeholder")
    pairing = TargetPairing("EIS", "EIS", "", "root", [selected], "root", reference)
    template = TemplateCandidate("EIS", reference, "unit", graph_page="Graph1", plot_count=8)

    _headers, _rows, _labels, extra = _build_template_eis_table(pairing, tmp_path / "run", template)

    overlay = extra["eis_overlay"]
    assert overlay["plotted_source_count"] == 8
    assert [Path(value).name for value in overlay["source_files"]] == [path.name for path in paths]
    assert overlay["visible_plot_indices"] == [3, 4, 5]
    assert overlay["source_selection_mode"] == "reviewed_coherent_source_family"


def test_template_epr_explicit_oth_json_uses_only_four_paired_traces(tmp_path: Path) -> None:
    selected_dir = tmp_path / "EPR" / "current"
    selected_dir.mkdir(parents=True)
    selected = [
        selected_dir / "sample A.xlsx",
        selected_dir / "sample_A.xlsx",
        selected_dir / "third trace.xlsx",
        selected_dir / "第四条曲线.xlsx",
    ]
    for index, path in enumerate(selected, start=1):
        _write_epr_xlsx(path, [index, index + 1, index + 2, index + 3, index + 4])
    # These are deliberately valid, nearby legacy group members.  The explicit
    # adaptive route must not discover or substitute them.
    for name in ("BC-OH-light2.xlsx", "CWO-OH-light2.xlsx", "BOBC-OH-light1.xlsx"):
        _write_epr_xlsx(selected_dir / name, [999, 999, 999, 999, 999])
    reference = tmp_path / "template.opju"
    reference.write_bytes(b"placeholder")
    pairing = TargetPairing("EPR", "EPR", "", "root", selected, "root", reference)
    template = TemplateCandidate("EPR", reference, "unit", graph_page="ohG", plot_count=3)

    product, extra = prepare_template_product(
        tmp_path / "run",
        pairing,
        template,
        origin_style_mode="oth-json",
    )

    overlay = extra["epr_overlay"]
    assert overlay["source_selection_mode"] == "explicit_pairing_adaptive_oth_json"
    assert overlay["selected_group_rule"].startswith("explicit oth-json pairing.data_paths")
    assert overlay["input_files"] == [str(path) for path in selected]
    assert overlay["trace_count"] == 4
    assert overlay["labels"] == ["sample_A", "sample_A_2", "third_trace", "dataset"]
    assert overlay["final_headers"] == ["magnetic_field", *overlay["labels"]]
    assert overlay["output_column_layout"]["final_offset_columns"] == [14, 15, 16, 17]
    assert product.pairing.data_paths == selected
    assert all("BC-OH-light2.xlsx" not in value for value in overlay["input_files"])


def test_template_epr_explicit_labels_strip_measurement_condition_and_stay_unique() -> None:
    used: set[str] = set()

    assert _template_epr_explicit_label(Path("BC-OH-light2.xlsx"), used, 1) == "BC"
    assert _template_epr_explicit_label(Path("BOBC-O3-dark-none.xlsx"), used, 2) == "BOBC"
    assert _template_epr_explicit_label(Path("BiCu-10.xlsx"), used, 3) == "BiCu-10"
    assert _template_epr_explicit_label(Path("BC-OH-light1.xlsx"), used, 4) == "BC-OH-light1"


def test_template_epr_adaptive_four_trace_origin_columns_and_graph_are_dynamic(tmp_path: Path) -> None:
    selected_dir = tmp_path / "EPR" / "current"
    selected_dir.mkdir(parents=True)
    selected = [selected_dir / f"trace_{index}.xlsx" for index in range(1, 5)]
    for index, path in enumerate(selected, start=1):
        _write_epr_xlsx(path, [index, index + 1, index + 2, index + 3, index + 4])
    reference = tmp_path / "template.opju"
    reference.write_bytes(b"placeholder")
    pairing = TargetPairing("EPR", "EPR", "", "root", selected, "root", reference)
    template = TemplateCandidate("EPR", reference, "unit", graph_page="ohG", plot_count=3)
    product, _extra = prepare_template_product(
        tmp_path / "run",
        pairing,
        template,
        origin_style_mode="oth-json",
    )

    class Result:
        def __init__(self, *, payload: dict[str, object] | None = None) -> None:
            self.ok = True
            self.message = "ok"
            self.payload = payload or {}

    class Operations:
        def __init__(self) -> None:
            self.scripts: list[str] = []
            self.graph_calls: list[tuple[int, int]] = []
            self.added_columns: list[int] = []

        def import_csv_to_worksheet(self, _path: Path, *, book_name: str) -> Result:
            return Result(payload={"book_name": book_name})

        def run_labtalk(self, script: str) -> Result:
            self.scripts.append(script)
            return Result()

        def get_worksheet_data(self, _book_name: str, _sheet_name: str) -> Result:
            return Result(payload={"columns": [[column * 10.0, column * 10.0 + 1.0] for column in range(1, 22)]})

        def create_graph(self, _graph_name: str, _book_name: str, _sheet_name: str, x_col: int, y_col: int, *, plot_type: str) -> Result:
            assert plot_type == "line"
            self.graph_calls.append((x_col, y_col))
            return Result(payload={"graph_name": "EPRGraph"})

        def add_plot_to_graph(self, _graph_name: str, _book_name: str, _sheet_name: str, x_col: int, y_col: int, *, plot_type: str) -> Result:
            assert x_col == 1
            assert plot_type == "line"
            self.added_columns.append(y_col)
            return Result()

    operations = Operations()
    processed = _prepare_template_epr_origin_processed_workbook(operations, product)

    assert processed["ok"] is True
    assert processed["final_origin_columns"] == [1, 14, 15, 16, 17]
    assert processed["origin_processing"]["detail_headers"] == [
        "magnetic_field",
        "trace_1_raw", "trace_1_baseline_corrected", "trace_1_smoothed", "trace_1_offset",
        "trace_2_raw", "trace_2_baseline_corrected", "trace_2_smoothed", "trace_2_offset",
        "trace_3_raw", "trace_3_baseline_corrected", "trace_3_smoothed", "trace_3_offset",
        "trace_4_raw", "trace_4_baseline_corrected", "trace_4_smoothed", "trace_4_offset",
    ]
    assert "wks.nCols=21" in operations.scripts[-1]
    assert "col(14)=col(10)+3*step" in operations.scripts[-1]
    assert "col(17)=col(13)+0*step" in operations.scripts[-1]
    assert "median(__template_epr_ranges)" in operations.scripts[-1]
    assert product.processed_data.read_text(encoding="utf-8").splitlines()[0] == "magnetic_field,trace_1,trace_2,trace_3,trace_4"

    created = _create_template_epr_origin_processed_graph(operations, product)
    assert created["ok"] is True
    assert operations.graph_calls[-1] == (1, 14)
    assert operations.added_columns == [15, 16, 17]


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


def test_template_pl_explicit_oth_json_uses_only_paired_current_curves(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("src.core.template_product_builder._template_candidate_files", lambda *args: pytest.fail("explicit PL sources must not trigger a discarded directory scan"))
    root = tmp_path / "PL" / "bobc+cwo+bc"
    root.mkdir(parents=True)
    paths = [root / f"{index}-EX-em640nm.txt" for index in range(1, 4)]
    for index, path in enumerate(paths, start=1):
        path.write_text(f"250 {index}\n251 {index + 1}\n", encoding="utf-8")
    pairing = TargetPairing(
        "PL",
        "PL",
        "",
        "root",
        [paths[2], paths[0]],
        "root",
        tmp_path / "pl.opju",
    )
    template = TemplateCandidate(
        "PL",
        tmp_path / "pl.opju",
        "unit",
        graph_page="EXJF",
        plot_count=3,
    )

    built = _build_template_xy_multisource_table(
        pairing,
        template,
        origin_style_mode="oth-json",
    )

    assert built is not None
    assert built["headers"] == ["wavelength_nm", "BC_counts", "BOBC_counts"]
    assert built["labels"]["legend_entries"] == ["BC", "BOBC"]
    assert all("CWO" not in header for header in built["headers"])


def test_template_photocurrent_uses_sample_directory_labels(tmp_path: Path) -> None:
    root = tmp_path / "photocurrent" / "1bobc+2cwo+3bicu-10"
    paths = [
        root / "BOBC" / "1-(OCP).txt",
        root / "CWO" / "2-(OCP).txt",
        root / "bicu" / "1-(OCP)-bicu.txt",
    ]
    rows_by_path = {
        paths[0]: "0 1\n1 2\n2 3\n",
        paths[1]: "10 4\n11 5\n",
        paths[2]: "0 6\n0 7\n2 8\n",
    }
    for path, content in rows_by_path.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    pairing = TargetPairing("photocurrent", "photocurrent", "", "root", [paths[0]], "root", tmp_path / "pc.opju")
    template = TemplateCandidate("photocurrent", tmp_path / "pc.opju", "unit", graph_page="Graph1", plot_count=3)

    selected = _template_photocurrent_candidate_files(pairing, template, 3)
    built = _build_template_xy_multisource_table(pairing, template)

    assert [_template_xy_series_label("photocurrent", path) for path in selected] == ["BOBC", "CWO", "BiCu-10"]
    assert built is not None
    assert built["headers"] == [
        "BOBC_time_s",
        "BOBC_current_a",
        "CWO_time_s",
        "CWO_current_a",
        "BiCu-10_time_s",
        "BiCu-10_current_a",
    ]
    assert built["rows"] == [
        [0.0, 1.0, 10.0, 4.0, 0.0, 6.0],
        [1.0, 2.0, 11.0, 5.0, 0.0, 7.0],
        [2.0, 3.0, None, None, 2.0, 8.0],
    ]
    assert built["labels"]["legend_entries"] == ["BOBC", "CWO", "BiCu-10"]
    assert built["alignment"]["product_series_count"] == 3
    assert built["alignment"]["missing_template_series_count"] == 0
    assert len(set(built["headers"])) == len(built["headers"])


def test_template_photocurrent_preserves_independent_xy_order_duplicate_x_and_tail_padding(tmp_path: Path) -> None:
    root = tmp_path / "photocurrent" / "bobc+cwo+bicu-10"
    paths = [
        root / "BOBC" / "1-(OCP).txt",
        root / "CWO" / "2-(OCP).txt",
        root / "bicu" / "3-(OCP).txt",
    ]
    contents = [
        "2 20\n1 10\n1 11\n",
        "100 30\n101 31\n",
        "5 40\n6 41\n7 42\n8 43\n",
    ]
    for path, content in zip(paths, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    template_path = tmp_path / "photocurrent.opju"
    template_path.write_bytes(b"opju placeholder")
    pairing = TargetPairing("photocurrent", "photocurrent", "", "root", [paths[0]], "root", template_path)
    template = TemplateCandidate("photocurrent", template_path, "unit", graph_page="Graph1", plot_count=3)

    built = _build_template_xy_multisource_table(pairing, template)

    assert built is not None
    assert built["headers"] == [
        "BOBC_time_s", "BOBC_current_a",
        "CWO_time_s", "CWO_current_a",
        "BiCu-10_time_s", "BiCu-10_current_a",
    ]
    assert built["rows"] == [
        [2.0, 20.0, 100.0, 30.0, 5.0, 40.0],
        [1.0, 10.0, 101.0, 31.0, 6.0, 41.0],
        [1.0, 11.0, None, None, 7.0, 42.0],
        [None, None, None, None, 8.0, 43.0],
    ]
    assert built["alignment"]["product_series_count"] == 3


def test_template_photocurrent_same_directory_uses_unique_filename_material_labels(
    tmp_path: Path,
) -> None:
    root = tmp_path / "photocurrent" / "第一次CWO BOBC BC数据"
    paths = [
        root / "4-BOBC-(OCP).txt",
        root / "5-CWO-(OCP) .txt",
        root / "6-BC-11-(OCP).txt",
    ]
    for index, path in enumerate(paths, start=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"0 {index}\n1 {index + 1}\n", encoding="utf-8")
    pairing = TargetPairing(
        "photocurrent",
        "photocurrent",
        "",
        "root",
        paths,
        "root",
        tmp_path / "pc.opju",
    )
    template = TemplateCandidate(
        "photocurrent",
        tmp_path / "pc.opju",
        "unit",
        graph_page="Graph2",
        plot_count=3,
    )

    built = _build_template_xy_multisource_table(
        pairing,
        template,
        origin_style_mode="auto",
    )

    assert built is not None
    assert built["labels"]["legend_entries"] == ["BOBC", "CWO", "BC-11"]
    assert built["headers"] == [
        "BOBC_time_s",
        "BOBC_current_a",
        "CWO_time_s",
        "CWO_current_a",
        "BC-11_time_s",
        "BC-11_current_a",
    ]
    assert len(set(built["headers"])) == len(built["headers"])


def test_template_ftir_uses_explicit_three_dpt_files_independent_grids_and_net_offsets(tmp_path: Path) -> None:
    root = tmp_path / "FTIR" / "BOBC+CWO+BiCu-10"
    paths = [
        root / "BC.0.dpt",
        root / "CWO.0.dpt",
        root / "BOBC.0.dpt",
    ]
    contents = [
        "9 30\n9 31\n8 32\n7 33\n",
        "100 20\n101 21\n",
        "3 10\n2 11\n2 12\n",
    ]
    for path, content in zip(paths, contents, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    unrelated = root / "unrelated-neighbour.dpt"
    unrelated.write_text("1 999\n2 999\n", encoding="utf-8")
    pairing = TargetPairing("FTIR", "FTIR", "", "root", paths, "root", tmp_path / "FTIR.opju")
    template = TemplateCandidate("FTIR", tmp_path / "FTIR.opju", "unit", graph_page="Graph3", plot_count=3)

    built = _build_template_xy_multisource_table(pairing, template, origin_style_mode="auto")

    assert built is not None
    assert built["headers"] == [
        "BiOBr0.5Cl0.5_wavenumber_cm-1", "BiOBr0.5Cl0.5_transmittance",
        "CuWO4_wavenumber_cm-1", "CuWO4_transmittance",
        "BiCu-10_wavenumber_cm-1", "BiCu-10_transmittance",
    ]
    raw_to_plotted = [0.6992644978783592, 0.48749646393210766, -0.174144271570014]
    assert built["rows"] == [
        [3.0, 10.0 + raw_to_plotted[0], 100.0, 20.0 + raw_to_plotted[1], 9.0, 30.0 + raw_to_plotted[2]],
        [2.0, 11.0 + raw_to_plotted[0], 101.0, 21.0 + raw_to_plotted[1], 9.0, 31.0 + raw_to_plotted[2]],
        [2.0, 12.0 + raw_to_plotted[0], None, None, 8.0, 32.0 + raw_to_plotted[2]],
        [None, None, None, None, 7.0, 33.0 + raw_to_plotted[2]],
    ]
    alignment = built["alignment"]
    assert alignment["used_files"] == [str(paths[2]), str(paths[1]), str(paths[0])]
    assert alignment["raw_to_plotted_vertical_offsets"] == raw_to_plotted
    assert alignment["last_origin_curve_translate_annotations"] == [
        0.69926449787836,
        0.48749646393211,
        -0.62347949080622,
    ]
    assert alignment["interpolation"] == "not_applied"
    assert alignment["smoothing"] == "not_applied"
    assert alignment["normalization"] == "not_applied"
    assert alignment["style_execution_mode_requested"] == "auto"
    assert alignment["style_execution_mode_selected"] == "otpu"
    assert alignment["current_series_count"] == 3
    assert alignment["fixed_contract_series_count"] == 3
    assert alignment["fixed_contract_exact_shape"] is True
    assert 999.0 not in [value for row in built["rows"] for value in row if value is not None]

    plan = _write_template_origin_processing_plan(
        pairing,
        tmp_path / "product",
        "FTIR_product",
        built["headers"],
        built["rows"],
    )
    assert plan["raw_to_plotted_vertical_offsets"] == raw_to_plotted
    assert plan["last_origin_curve_translate_annotations"][-1] == -0.62347949080622
    assert plan["offset_application"] == "pointwise_y_plus_raw_to_plotted_offset_before_Origin_import"
    assert plan["interpolation"] == "not_applied"


def test_template_ftir_rejects_missing_reviewed_binding_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "FTIR"
    paths = [root / "BOBC.0.dpt", root / "CWO.0.dpt", root / "BC.0.dpt"]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("1 10\n2 11\n", encoding="utf-8")
    pairing = TargetPairing("FTIR", "FTIR", "", "root", paths, "root", tmp_path / "FTIR.opju")
    template = TemplateCandidate("FTIR", tmp_path / "FTIR.opju", "unit", graph_page="Graph3", plot_count=3)
    monkeypatch.setattr(
        "src.core.template_product_builder.origin_style_manifest_path",
        lambda _project_root: tmp_path / "styles" / "manifest.json",
    )

    with pytest.raises(ValueError, match="binding contract is unavailable"):
        _build_template_xy_multisource_table(pairing, template)


def test_template_ftir_auto_two_series_uses_explicit_subset_contract_order_and_no_neighbour(
    tmp_path: Path,
) -> None:
    root = tmp_path / "FTIR" / "cohort"
    bicu = root / "BC.0.dpt"
    bobc = root / "BOBC.0.dpt"
    neighbour = root / "CWO.0.dpt"
    for path, content in (
        (bicu, "9 30\n8 31\n"),
        (bobc, "3 10\n2 11\n2 12\n"),
        (neighbour, "100 999\n101 999\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    pairing = TargetPairing("FTIR", "FTIR", "", "root", [bicu, bobc], "root", tmp_path / "FTIR.opju")
    template = TemplateCandidate("FTIR", tmp_path / "FTIR.opju", "unit", graph_page="Graph3", plot_count=3)

    built = _build_template_xy_multisource_table(pairing, template, origin_style_mode="auto")

    assert built is not None
    assert built["headers"] == [
        "BiOBr0.5Cl0.5_wavenumber_cm-1",
        "BiOBr0.5Cl0.5_transmittance",
        "BiCu-10_wavenumber_cm-1",
        "BiCu-10_transmittance",
    ]
    bobc_offset = 0.6992644978783592
    bicu_offset = -0.174144271570014
    assert built["rows"] == [
        [3.0, 10.0 + bobc_offset, 9.0, 30.0 + bicu_offset],
        [2.0, 11.0 + bobc_offset, 8.0, 31.0 + bicu_offset],
        [2.0, 12.0 + bobc_offset, None, None],
    ]
    alignment = built["alignment"]
    assert alignment["used_files"] == [str(bobc), str(bicu)]
    assert str(neighbour) not in alignment["used_files"]
    assert alignment["raw_to_plotted_vertical_offsets"] == [bobc_offset, bicu_offset]
    assert alignment["style_execution_mode_requested"] == "auto"
    assert alignment["style_execution_mode_selected"] == "oth-json"
    assert alignment["current_series_count"] == 2
    assert alignment["fixed_contract_series_count"] == 3
    assert alignment["fixed_contract_exact_shape"] is False
    assert alignment["interpolation"] == "not_applied"
    assert alignment["smoothing"] == "not_applied"
    assert alignment["normalization"] == "not_applied"

    plan = _write_template_origin_processing_plan(
        pairing,
        tmp_path / "product",
        "FTIR_product",
        built["headers"],
        built["rows"],
        origin_style_mode="auto",
        alignment=alignment,
    )
    assert plan["style_execution_mode_selected"] == "oth-json"
    assert plan["current_series_count"] == 2
    assert plan["raw_to_plotted_vertical_offsets"] == [bobc_offset, bicu_offset]
    assert plan["last_origin_curve_translate_annotations"] == [0.69926449787836, -0.62347949080622]


@pytest.mark.parametrize("series_count", [2, 4])
def test_template_photocurrent_oth_json_preserves_explicit_series_count_and_does_not_scan_neighbours(
    tmp_path: Path,
    series_count: int,
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.core.template_product_builder._template_candidate_files", lambda *args: pytest.fail("explicit photocurrent sources must not trigger a discarded directory scan"))
    root = tmp_path / "photocurrent"
    paths = [
        root / "CWO" / "2-(OCP).txt",
        root / "BOBC" / "1-(OCP).txt",
        root / "BiCu-10" / "3-(OCP).txt",
        root / "sample-4" / "4-(OCP).txt",
    ]
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{index + 2} {index + 20}\n1 {index + 10}\n1 {index + 11}\n", encoding="utf-8")
    neighbour = root / "not-selected" / "99-(OCP).txt"
    neighbour.parent.mkdir(parents=True)
    neighbour.write_text("0 999\n1 999\n", encoding="utf-8")
    explicit = paths[:series_count]
    pairing = TargetPairing("photocurrent", "photocurrent", "", "root", explicit, "root", tmp_path / "pc.opju")
    template = TemplateCandidate("photocurrent", tmp_path / "pc.opju", "unit", graph_page="Graph1", plot_count=3)

    built = _build_template_xy_multisource_table(pairing, template, origin_style_mode="oth-json")

    assert built is not None
    alignment = built["alignment"]
    assert alignment["used_files"] == [str(path) for path in explicit]
    assert str(neighbour) not in alignment["used_files"]
    assert alignment["current_series_count"] == series_count
    assert alignment["fixed_contract_series_count"] == 3
    assert alignment["fixed_contract_exact_shape"] is (series_count == 3)
    assert alignment["style_execution_mode_requested"] == "oth-json"
    assert alignment["style_execution_mode_selected"] == "oth-json"
    assert len(built["headers"]) == series_count * 2
    assert built["rows"][0][:4] == [2.0, 20.0, 3.0, 21.0]
    assert built["rows"][1][:4] == [1.0, 10.0, 1.0, 11.0]
    assert built["rows"][2][:4] == [1.0, 11.0, 1.0, 12.0]


def test_template_photocurrent_otpu_mode_keeps_verified_fixed_contract_discovery(tmp_path: Path) -> None:
    root = tmp_path / "photocurrent" / "cohort"
    paths = [
        root / "BOBC" / "1-(OCP).txt",
        root / "CWO" / "2-(OCP).txt",
        root / "BiCu-10" / "3-(OCP).txt",
    ]
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"0 {index + 1}\n1 {index + 2}\n", encoding="utf-8")
    pairing = TargetPairing("photocurrent", "photocurrent", "", "root", [paths[0]], "root", tmp_path / "pc.opju")
    template = TemplateCandidate("photocurrent", tmp_path / "pc.opju", "unit", graph_page="Graph1", plot_count=3)

    built = _build_template_xy_multisource_table(pairing, template, origin_style_mode="otpu")

    assert built is not None
    assert built["alignment"]["used_files"] == [str(path) for path in paths]
    assert built["alignment"]["style_execution_mode_selected"] == "otpu"
    assert built["alignment"]["fixed_contract_exact_shape"] is True


def _write_bet_isotherm(path: Path, rows: list[tuple[float, float, float | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Relative Pressure (P/P0)", "Quantity Adsorbed", "Desorption"])
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)


def test_template_bet_auto_exact_six_curves_uses_explicit_cohort_contract_order_and_tail_padding(
    tmp_path: Path,
) -> None:
    root = tmp_path / "BET" / "same-cohort"
    cwo = root / "CWO-BET.xlsx"
    bicu = root / "BiCu-BET.xlsx"
    bobc = root / "BOBC-BET.xlsx"
    _write_bet_isotherm(cwo, [(0.1, 1.0, 10.0), (0.2, 2.0, 11.0), (0.3, 3.0, None)])
    _write_bet_isotherm(bicu, [(0.4, 4.0, 14.0), (0.5, 5.0, 15.0)])
    _write_bet_isotherm(bobc, [(0.6, 6.0, 16.0), (0.7, 7.0, 17.0), (0.8, 8.0, 18.0), (0.9, 9.0, None)])
    pairing = TargetPairing("BET", "BET", "", "root", [bobc, cwo, bicu], "root", tmp_path / "BET.opju")
    template = TemplateCandidate("BET", tmp_path / "BET.opju", "unit", graph_page="Graph5", plot_count=6)

    built = _build_template_bet_multisource_table(pairing, template, origin_style_mode="auto")

    assert built is not None
    assert built["headers"] == [
        "BOBC_adsorption_relative_pressure_p_p0", "BOBC_adsorption_quantity_adsorbed_cm3_g_stp",
        "BOBC_desorption_relative_pressure_p_p0", "BOBC_desorption_quantity_adsorbed_cm3_g_stp",
        "CWO_adsorption_relative_pressure_p_p0", "CWO_adsorption_quantity_adsorbed_cm3_g_stp",
        "CWO_desorption_relative_pressure_p_p0", "CWO_desorption_quantity_adsorbed_cm3_g_stp",
        "BiCu_adsorption_relative_pressure_p_p0", "BiCu_adsorption_quantity_adsorbed_cm3_g_stp",
        "BiCu_desorption_relative_pressure_p_p0", "BiCu_desorption_quantity_adsorbed_cm3_g_stp",
    ]
    assert built["labels"]["legend_entries"] == [
        "BOBC adsorption", "BOBC desorption", "CWO adsorption", "CWO desorption", "BiCu adsorption", "BiCu desorption",
    ]
    assert built["rows"] == [
        [0.6, 6.0, 0.6, 16.0, 0.1, 1.0, 0.1, 10.0, 0.4, 4.0, 0.4, 14.0],
        [0.7, 7.0, 0.7, 17.0, 0.2, 2.0, 0.2, 11.0, 0.5, 5.0, 0.5, 15.0],
        [0.8, 8.0, 0.8, 18.0, 0.3, 3.0, None, None, None, None, None, None],
        [0.9, 9.0, None, None, None, None, None, None, None, None, None, None],
    ]
    alignment = built["alignment"]
    assert alignment["used_files"] == [str(bobc), str(cwo), str(bicu)]
    assert alignment["style_execution_mode_selected"] == "otpu"
    assert alignment["current_series_count"] == 6
    assert alignment["fixed_contract_series_count"] == 6
    assert alignment["fixed_contract_exact_shape"] is True
    assert alignment["interpolation"] == alignment["smoothing"] == alignment["normalization"] == "not_applied"


def test_template_bet_auto_one_explicit_file_uses_oth_json_and_never_scans_neighbour(
    tmp_path: Path,
) -> None:
    root = tmp_path / "BET" / "cohort"
    selected = root / "BOBC-BET.xlsx"
    neighbour = root / "CWO-BET.xlsx"
    _write_bet_isotherm(selected, [(0.1, 1.0, 2.0), (0.2, 3.0, 4.0), (0.3, 5.0, None)])
    _write_bet_isotherm(neighbour, [(0.1, 999.0, 999.0), (0.2, 999.0, 999.0)])
    pairing = TargetPairing("BET", "BET", "", "root", [selected], "root", tmp_path / "BET.opju")
    template = TemplateCandidate("BET", tmp_path / "BET.opju", "unit", graph_page="Graph5", plot_count=6)

    built = _build_template_bet_multisource_table(pairing, template, origin_style_mode="auto")

    assert built is not None
    assert built["headers"] == [
        "BOBC_adsorption_relative_pressure_p_p0", "BOBC_adsorption_quantity_adsorbed_cm3_g_stp",
        "BOBC_desorption_relative_pressure_p_p0", "BOBC_desorption_quantity_adsorbed_cm3_g_stp",
    ]
    assert built["alignment"]["used_files"] == [str(selected)]
    assert str(neighbour) not in built["alignment"]["used_files"]
    assert built["alignment"]["style_execution_mode_selected"] == "oth-json"
    assert built["alignment"]["current_series_count"] == 2
    assert built["alignment"]["fixed_contract_series_count"] == 6
    assert all(value != 999.0 for row in built["rows"] for value in row if value is not None)

    explicit_oth = _build_template_bet_multisource_table(pairing, template, origin_style_mode="oth-json")
    assert explicit_oth is not None
    assert explicit_oth["alignment"]["used_files"] == [str(selected)]
    assert explicit_oth["alignment"]["style_execution_mode_selected"] == "oth-json"

    _product, extra = prepare_template_product(
        tmp_path / "product",
        pairing,
        template,
        compact_output=True,
        origin_style_mode="auto",
    )
    assert extra["template_data_alignment"]["style_execution_mode_selected"] == "oth-json"
    assert extra["origin_processing"]["current_series_count"] == 2


def test_template_bet_explicit_otpu_missing_contract_curves_does_not_fill_from_neighbour(
    tmp_path: Path,
) -> None:
    root = tmp_path / "BET" / "cohort"
    selected = root / "BOBC-BET.xlsx"
    neighbour = root / "CWO-BET.xlsx"
    _write_bet_isotherm(selected, [(0.1, 1.0, 2.0), (0.2, 3.0, 4.0)])
    _write_bet_isotherm(neighbour, [(0.1, 999.0, 999.0), (0.2, 999.0, 999.0)])
    pairing = TargetPairing("BET", "BET", "", "root", [selected], "root", tmp_path / "BET.opju")
    template = TemplateCandidate("BET", tmp_path / "BET.opju", "unit", graph_page="Graph5", plot_count=6)

    built = _build_template_bet_multisource_table(pairing, template, origin_style_mode="otpu")

    assert built is not None
    assert built["alignment"]["used_files"] == [str(selected)]
    assert built["alignment"]["current_series_count"] == 2
    assert built["alignment"]["fixed_contract_exact_shape"] is False
    assert all(value != 999.0 for row in built["rows"] for value in row if value is not None)


def test_template_bet_explicit_paths_strictly_reject_duplicates_missing_and_non_isotherms(tmp_path: Path) -> None:
    valid = tmp_path / "BET" / "BOBC-BET.xlsx"
    _write_bet_isotherm(valid, [(0.1, 1.0, 2.0), (0.2, 3.0, 4.0)])
    template = TemplateCandidate("BET", tmp_path / "BET.opju", "unit", graph_page="Graph5", plot_count=6)

    duplicate = TargetPairing("BET", "BET", "", "root", [valid, valid], "root", tmp_path / "BET.opju")
    with pytest.raises(ValueError, match="duplicate"):
        _build_template_bet_multisource_table(duplicate, template, origin_style_mode="oth-json")

    missing = TargetPairing("BET", "BET", "", "root", [tmp_path / "missing.xlsx"], "root", tmp_path / "BET.opju")
    with pytest.raises(ValueError, match="missing"):
        _build_template_bet_multisource_table(missing, template, origin_style_mode="oth-json")

    summary = tmp_path / "BET" / "summary.xlsx"
    workbook = Workbook()
    workbook.active.append(["BET Surface Area", "Pore Volume"])
    workbook.active.append([100.0, 0.2])
    workbook.save(summary)
    non_isotherm = TargetPairing("BET", "BET", "", "root", [summary], "root", tmp_path / "BET.opju")
    with pytest.raises(ValueError, match="non-isotherm"):
        _build_template_bet_multisource_table(non_isotherm, template, origin_style_mode="oth-json")


def test_template_epr_origin_processing_script_uses_origin_median_and_smooth() -> None:
    script = _template_epr_origin_processing_script("EPRBook", ["BC", "CWO", "BOBC"])

    assert 'win -a "EPRBook"' in script
    assert "wks.nCols=16" in script
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


def test_adaptive_oth_json_readback_requires_current_native_style_not_fixed_legend_geometry() -> None:
    export_status = _adaptive_oth_json_export_status(series_count=2)
    export_status["exemplar_style"] = {
        "audit_numeric_values": {"legend.background": 1, "legend.bold": 0},
    }
    export_status["product_style"]["audit_numeric_values"] = {
        "legend.background": 0,
        "legend.bold": 1,
    }

    result = _adaptive_oth_json_detached_acceptance(export_status)

    assert result["ok"] is True
    assert result["reasons"] == []


def test_adaptive_oth_json_accepts_review_only_data_bound_axis_range_changes() -> None:
    export_status = _adaptive_oth_json_export_status(series_count=18)
    export_status["conformance"] = {
        "status": "review",
        "compared_fields": 134,
        "matched_fields": 132,
        "issues": [
            {
                "field": "layer.y.from",
                "category": "axis",
                "severity": "review",
                "message": "numeric style value differs from exemplar beyond tolerance",
            },
            {
                "field": "layer.y.to",
                "category": "axis",
                "severity": "review",
                "message": "numeric style value differs from exemplar beyond tolerance",
            },
        ],
    }

    result = _adaptive_oth_json_detached_acceptance(export_status)

    assert result["ok"] is True
    assert result["reasons"] == []


@pytest.mark.parametrize("failed_key", ["axis_title_visible", "legend_no_frame"])
def test_adaptive_oth_json_readback_rejects_missing_current_native_style_gate(
    failed_key: str,
) -> None:
    export_status = _adaptive_oth_json_export_status(series_count=2)
    export_status["strict_style_readback"][failed_key] = False

    result = _adaptive_oth_json_detached_acceptance(export_status)

    assert result["ok"] is False
    assert result["reasons"] == ["adaptive OTH+JSON strict style readback did not pass"]


def test_adaptive_oth_json_readback_fails_when_required_gate_is_missing() -> None:
    readback = dict(_adaptive_oth_json_export_status()["strict_style_readback"])
    del readback["axis_title_bold"]

    relevant = _adaptive_oth_json_strict_readback_values(readback)

    assert relevant["axis_title_bold"] is None
    assert all(relevant[key] is True for key in relevant if key != "axis_title_bold")


def test_cached_style_readback_compares_reported_title_and_legend_style_to_exemplar() -> None:
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
        exemplar_style={
            "audit_numeric_values": {
                "xb.fsize": 28,
                "yl.fsize": 28,
                "xb.bold": 0,
                "yl.bold": 0,
                "legend.background": 1,
                "legend.bold": 0,
            },
            "audit_string_values": {
                "xb.font$": "Calibri",
                "yl.font$": "Calibri",
                "legend.font$": "Calibri",
            },
        },
        product_style={
            "audit_numeric_values": {
                "xb.fsize": 28,
                "yl.fsize": 28,
                "xb.bold": 0,
                "yl.bold": 0,
                "legend.background": 1,
                "legend.bold": 0,
            },
            "audit_string_values": {
                "xb.font$": "Calibri",
                "yl.font$": "Calibri",
                "legend.font$": "Calibri",
            },
        },
    )

    assert relevant == {
        "axis_title_visible": True,
        "axis_title_font_size_matches_exemplar": True,
        "axis_title_bold_matches_exemplar": True,
        "axis_title_font_matches_exemplar": True,
        "legend_frame_matches_exemplar": True,
        "legend_bold_matches_exemplar": True,
        "legend_font_matches_exemplar": True,
    }


def test_saved_style_conformance_blocks_non_range_review_but_allows_data_range_review() -> None:
    assert _template_conformance_acceptance_reasons(
        {
            "status": "review",
            "issues": [
                {
                    "field": "layer.x.from",
                    "severity": "review",
                }
            ],
        }
    ) == []

    reasons = _template_conformance_acceptance_reasons(
        {
            "status": "review",
            "issues": [
                {
                    "field": "legend.x",
                    "severity": "review",
                }
            ],
        }
    )

    assert reasons == ["style conformance requires review for non-data-range fields: legend.x"]


def test_saved_style_conformance_blocks_fail_severity_and_axis_title_overlap_risk() -> None:
    reasons = _template_conformance_acceptance_reasons(
        {
            "status": "fail",
            "axis_title_no_overlap_check": "risk",
            "issues": [
                {
                    "field": "xb.bold",
                    "severity": "fail",
                }
            ],
        }
    )

    assert reasons == [
        "style conformance has fail-severity differences: xb.bold",
        "axis-title readback indicates overlap risk",
    ]


def test_strict_preview_rejects_plot_count_delta_even_with_low_rms_and_strong_style_match() -> None:
    reasons = _template_strict_visual_reasons(
        ready=True,
        plot_count_delta=-2,
        style_match_ratio=1.0,
        preview_rms=24.9,
    )

    assert reasons == ["plot count differs from template by -2"]


def test_strict_preview_blocks_high_rms_even_when_style_and_plot_count_match() -> None:
    reasons = _template_strict_visual_reasons(
        ready=True,
        plot_count_delta=0,
        style_match_ratio=0.98,
        preview_rms=61.0,
    )

    assert reasons == ["preview RMS 61.00 is above 35.00"]


def test_strict_preview_blocks_high_rms_for_text_only_legend_policy() -> None:
    reasons = _template_strict_visual_reasons(
        ready=True,
        plot_count_delta=0,
        style_match_ratio=0.88,
        preview_rms=57.7,
        text_only_legend=True,
    )

    assert reasons == ["preview RMS 57.70 is above 35.00"]


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
