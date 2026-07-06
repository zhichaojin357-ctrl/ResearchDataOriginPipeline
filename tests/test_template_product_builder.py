from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from src.processors.eis import EisCleaningResult, EisFitResult, EisPoint

from src.core.template_product_builder import (
    TEMPLATE_ACCEPTED_TYPES,
    TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES,
    TEMPLATE_TARGET_TYPES,
    TemplateProductBuilderOptions,
    TemplateCandidate,
    classify_template_project_style_asset_candidates,
    classify_template_xps_reference_candidates,
    classify_template_candidates,
    clip_eis_fit_to_measured_range,
    prepare_template_product,
    run_template_product_builder_all_types,
    select_template,
    validate_template_candidates,
    template_acceptance_status,
    _build_pairing_template_candidates,
    _repair_exemplar_driven_pairings,
    _prioritized_template_validation_targets,
    _build_template_xrd_multisource_table,
    _resolve_run_relative_artifact,
    _template_xrd_normalized_offset_rows,
    _template_xrd_target_sample_series_count,
    _write_template_preview_comparison,
)
from src.core.template_product_common import TargetPairing
from src.core.template_product_common import _resolve_pairing_path


def test_classify_templates_uses_f_drive_type_paths_and_separates_xps_subtypes() -> None:
    root = Path("F:/template_root")
    paths = [
        root / "BET" / "BOBC.opju",
        root / "XPS" / "in_situ" / "insitu.opju",
        root / "XPS" / "bobc xps.opju",
        root / "XRD" / "CWO+BOBC" / "CWO+BOBC+鏍囧崱.opju",
        root / "EIS" / "BOBC" / "2eis.opju",
        root / "UV" / "BOBC+MS.opju",
        root / "photocurrent" / "I-T BOBC+CWO 4.22.opju",
    ]

    classified = classify_template_candidates(paths, f_drive_root=root)

    assert {item.product_key for item in classified} >= {
        "BET",
        "XPS_in_situ",
        "XPS_non_in_situ",
        "XRD",
        "EIS",
        "UV-vis DRS / Tauc",
        "photocurrent",
    }
    assert [item.path.name for item in classified if item.product_key == "XPS_in_situ"] == ["insitu.opju"]
    assert [item.path.name for item in classified if item.product_key == "XPS_non_in_situ"] == ["bobc xps.opju"]
    assert tuple(TEMPLATE_TARGET_TYPES) == tuple(TEMPLATE_ACCEPTED_TYPES)


def test_classify_template_xps_reference_root_uses_in_situ_reference_opjus(tmp_path: Path) -> None:
    reference_root = tmp_path / "xps_reference"
    reference_root.mkdir()
    bi_cl_br = reference_root / "xps_in_situ_Bi_Cl_Br.opju"
    cu_w = reference_root / "xps_in_situ_Cu_W.opju"
    non_in_situ = reference_root / "xps_non_in_situ_overview.opju"
    note = reference_root / "notes.txt"
    for path in (bi_cl_br, cu_w, non_in_situ, note):
        path.write_text("placeholder", encoding="utf-8")

    classified = classify_template_xps_reference_candidates(
        [bi_cl_br, cu_w, non_in_situ, note],
        reference_root=reference_root,
    )

    assert [item.path.name for item in classified] == [
        "xps_in_situ_Bi_Cl_Br.opju",
        "xps_in_situ_Cu_W.opju",
    ]
    assert {item.product_key for item in classified} == {"XPS_in_situ"}
    assert {item.source for item in classified} == {"xps_reference_scan"}
    assert all(item.path_score > 30 for item in classified)


def test_classify_template_project_style_asset_candidates_use_saved_format_themes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    theme_dir = style_root / "format_themes"
    theme_dir.mkdir(parents=True)
    theme = theme_dir / "BET.oth"
    theme.write_text("saved format theme", encoding="utf-8")
    (style_root / "manifest.json").write_text(
        """{
  "schema_version": 1,
  "assets": [
    {
      "product_key": "BET",
      "data_type": "BET",
      "format_theme": "format_themes/BET.oth",
      "status": "accepted",
      "graph_page": "Graph1",
      "source_run_root": "output/runs/source_run"
    }
  ]
}
""",
        encoding="utf-8",
    )

    candidates = classify_template_project_style_asset_candidates(project_root)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.product_key == "BET"
    assert candidate.path == theme
    assert candidate.source == "project_origin_style_asset"
    assert candidate.status == "valid"
    assert candidate.graph_page == "Graph1"
    assert candidate.metadata["style_asset"]["format_theme"] == "format_themes/BET.oth"


def test_template_builder_uses_project_style_assets_without_default_external_scan(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    style_root = project_root / "templates" / "origin_styles"
    theme_dir = style_root / "format_themes"
    theme_dir.mkdir(parents=True)
    (theme_dir / "BET.oth").write_bytes(b"oth")
    (style_root / "manifest.json").write_text(
        """{
  "schema_version": 1,
  "assets": [
    {"product_key":"BET","data_type":"BET","format_theme":"format_themes/BET.oth","status":"accepted","graph_page":"Graph1"}
  ]
}
""",
        encoding="utf-8",
    )
    roots = {"f_drive_detection": tmp_path / "raw", "workspace_xps_reference": tmp_path / "xps_reference", "workspace_group_data": tmp_path / "group"}
    data = roots["f_drive_detection"] / "BET" / "bet.csv"
    data.parent.mkdir(parents=True)
    data.write_text("relative_pressure_p_p0,quantity_adsorbed\n0.1,1\n0.5,2\n", encoding="utf-8")
    reference = roots["f_drive_detection"] / "BET" / "reference.opju"
    reference.write_bytes(b"opju")
    pairing = tmp_path / "pairing.json"
    pairing.write_text(
        """[
  {
    "data_type":"BET",
    "xps_subtype":"",
    "selected_data_root_label":"f_drive_detection",
    "selected_data_relative_paths":["BET/bet.csv"],
    "selected_opju_root_label":"f_drive_detection",
    "selected_opju_relative_path":"BET/reference.opju"
  }
]
""",
        encoding="utf-8",
    )

    def fail_external_scan(_root: Path) -> list[Path]:
        raise AssertionError("default external template scan should not run when project style assets are available")

    monkeypatch.setattr("src.core.template_product_builder.scan_template_f_drive_template_paths", fail_external_scan)

    result = run_template_product_builder_all_types(
        project_root,
        TemplateProductBuilderOptions(
            pairing_path=pairing,
            output_root=tmp_path / "out",
            timestamp="20260611_190000",
            project_style_asset_fallback=True,
        ),
        root_map=roots,
    )

    bet = next(product for product in result["products"] if product["type"] == "BET")
    assert bet["status"] == "blocked"
    assert Path(str(bet["processed_data"])).name == "BET_BOBC_exemplar.csv"
    assert result["summary"]["product_count"] == len(TEMPLATE_TARGET_TYPES)


def test_select_template_blocks_missing_or_data_only_candidates() -> None:
    root = Path("F:/template_root")
    candidates = [
        TemplateCandidate(
            product_key="XPS_in_situ",
            path=root / "XPS" / "table_only.opju",
            source="f_drive_scan",
            path_score=10,
            status="data_only",
            graph_page="",
            layer_count=0,
            plot_count=0,
            reason="no graph pages",
        )
    ]

    selection = select_template("XPS_in_situ", candidates)
    missing = select_template("Raman", candidates)

    assert selection.status == "blocked"
    assert "data-only" in selection.reason
    assert missing.status == "blocked"
    assert "No OPJU/OPJ template or project-local style asset candidate" in missing.reason


def test_clip_eis_fit_to_measured_range_keeps_main_plot_from_large_full_arc() -> None:
    cleaned = [
        EisPoint(1, 1000.0, 10.0, 1.0),
        EisPoint(2, 100.0, 100.0, 20.0),
        EisPoint(3, 10.0, 500.0, 240.0),
    ]
    full = EisFitResult(
        method="least_squares_randles_cpe",
        points=[(10, 1), (100, 25), (500, 230), (5000, 9000), (50000, 10)],
        parameters={"Rs": 8.0, "Rct": 50000.0, "Q": 1e-4, "n": 0.8},
        semicircle_classification="depressed semicircle candidate",
    )

    clipped = clip_eis_fit_to_measured_range(cleaned, full, x_pad_fraction=0.05, y_pad_fraction=0.15)

    assert clipped.parameters == full.parameters
    assert clipped.method == "least_squares_randles_cpe_measured_range_visual_segment"
    assert clipped.points == [(10, 1), (100, 25), (500, 230)]
    assert max(x for x, _ in clipped.points) <= 500.0 * 1.05
    assert max(y for _, y in clipped.points) <= 240.0 * 1.15
    assert "full fit retained in debug" in clipped.warning


def test_template_acceptance_status_uses_strict_accepted_blocked_terms_only(tmp_path: Path) -> None:
    artifact = tmp_path / "ok.bin"
    artifact.write_text("x", encoding="utf-8")
    accepted = template_acceptance_status(
        has_required_artifacts=True,
        no_label_pass=True,
        readback_pass=True,
        visual_acceptance=True,
        line_width_acceptance=True,
        axis_title_acceptance=True,
        exemplar_similarity=True,
        notes=[],
    )
    blocked = template_acceptance_status(
        has_required_artifacts=True,
        no_label_pass=True,
        readback_pass=True,
        visual_acceptance=False,
        line_width_acceptance=True,
        axis_title_acceptance=True,
        exemplar_similarity=True,
        notes=["preview still looks like a default thin-line plot"],
    )

    assert accepted.status == "accepted"
    assert blocked.status == "blocked"
    assert "success" not in {accepted.status, blocked.status}
    assert "review" not in {accepted.status, blocked.status}


def test_embedded_template_preview_acceptance_uses_readback_not_opju_one_to_one(tmp_path: Path) -> None:
    product_root = tmp_path / "products" / "BET"
    product_root.mkdir(parents=True)
    reference = product_root / "reference.png"
    generated = product_root / "generated.png"
    Image.new("RGB", (64, 48), "white").save(reference)
    Image.new("RGB", (64, 48), "white").save(generated)
    metadata = product_root / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 9,
                "strict_style_readback": {
                    "font_family_arial": True,
                    "axis_title_bold": True,
                    "axis_title_visible": True,
                    "axis_title_no_overlap": True,
                },
                "origin_processing": {
                    "applied": True,
                    "method": "embedded_template_snapshot_graph",
                    "legend_policy": {"line_samples_removed": True},
                },
                "origin_status": {
                    "template_format_plan": {"mode": "embedded_template_snapshot"},
                    "product_style": {"plot_count": 1},
                    "conformance": {"compared_fields": 10, "matched_fields": 5},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "template_format_mode": "embedded_template_snapshot",
        "origin_processing_method": "embedded_template_snapshot_graph",
        "reference_preview_png": "products/BET/reference.png",
        "preview_png": "products/BET/generated.png",
        "metadata": "products/BET/metadata.json",
        "has_opju": True,
        "has_tif": True,
        "has_png": True,
        "has_reference_preview": True,
        "has_processed_data": True,
        "has_metadata": True,
        "has_report": True,
        "conformance": {"compared_fields": 10, "matched_fields": 5},
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    item = audit["items"][0]
    assert item["embedded_template_snapshot_mode"] is True
    assert item["strict_status"] == "embedded_template_snapshot_match"
    assert item["strict_visual_match"] is True
    assert item["plot_count_delta"] == -8
    assert item["style_match_ratio"] == 0.5
    assert product["status"] == "accepted"


def test_embedded_template_preview_accepts_xrd_card_line_sample_legend(tmp_path: Path) -> None:
    product_root = tmp_path / "products" / "XRD"
    product_root.mkdir(parents=True)
    reference = product_root / "reference.png"
    generated = product_root / "generated.png"
    Image.new("RGB", (64, 48), "white").save(reference)
    Image.new("RGB", (64, 48), "white").save(generated)
    metadata = product_root / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "product_key": "XRD",
                "strict_style_readback": {
                    "font_family_arial": True,
                    "axis_title_bold": True,
                    "axis_title_visible": True,
                    "axis_title_no_overlap": True,
                    "legend_bold": True,
                    "legend_no_frame": True,
                },
                "origin_processing": {
                    "applied": True,
                    "method": "embedded_template_snapshot_graph",
                    "legend_policy": {
                        "line_samples_removed": False,
                        "method": "template_line_sample_legend_preserved",
                        "xrd_standard_card_reference_sticks_present": True,
                    },
                },
                "origin_status": {
                    "template_format_plan": {"mode": "embedded_template_snapshot", "data_type": "XRD"},
                    "product_style": {"plot_count": 3},
                    "conformance": {"compared_fields": 10, "matched_fields": 7},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    product = {
        "type": "XRD",
        "status": "accepted",
        "template_format_mode": "embedded_template_snapshot",
        "origin_processing_method": "embedded_template_snapshot_graph",
        "reference_preview_png": "products/XRD/reference.png",
        "preview_png": "products/XRD/generated.png",
        "metadata": "products/XRD/metadata.json",
        "has_opju": True,
        "has_tif": True,
        "has_png": True,
        "has_reference_preview": True,
        "has_processed_data": True,
        "has_metadata": True,
        "has_report": True,
        "conformance": {"compared_fields": 10, "matched_fields": 7},
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    item = audit["items"][0]
    assert item["strict_status"] == "embedded_template_snapshot_match"
    assert item["strict_visual_match"] is True
    assert product["status"] == "accepted"


def test_xrd_clean_rebuild_preview_accepts_current_data_plot_count(tmp_path: Path) -> None:
    product_root = tmp_path / "products" / "XRD"
    product_root.mkdir(parents=True)
    reference = product_root / "reference.png"
    generated = product_root / "generated.png"
    Image.new("RGB", (64, 48), "white").save(reference)
    Image.new("RGB", (64, 48), "white").save(generated)
    metadata = product_root / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "product_key": "XRD",
                "template_plot_count": 3,
                "strict_style_readback": {
                    "font_family_arial": True,
                    "axis_title_bold": True,
                    "axis_title_visible": True,
                    "axis_title_no_overlap": True,
                    "legend_bold": True,
                    "legend_no_frame": True,
                },
                "origin_status": {
                    "template_base_replacement": {
                        "xrd_clean_graph_rebuild": True,
                    },
                    "product_style": {"plot_count": 5},
                    "conformance": {"compared_fields": 10, "matched_fields": 5},
                    "origin_processing": {
                        "applied": True,
                        "method": "opju_template_snapshot_fallback_graph",
                        "legend_policy": {
                            "line_samples_removed": False,
                            "method": "template_line_sample_legend_preserved",
                            "xrd_standard_card_reference_sticks_present": True,
                        },
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    product = {
        "type": "XRD",
        "status": "accepted",
        "template_format_mode": "opju_template_base",
        "origin_processing_method": "opju_template_snapshot_fallback_graph",
        "reference_preview_png": "products/XRD/reference.png",
        "preview_png": "products/XRD/generated.png",
        "metadata": "products/XRD/metadata.json",
        "has_opju": True,
        "has_tif": True,
        "has_png": True,
        "has_reference_preview": True,
        "has_processed_data": True,
        "has_metadata": True,
        "has_report": True,
        "conformance": {"compared_fields": 10, "matched_fields": 5},
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    item = audit["items"][0]
    assert item["xrd_clean_graph_rebuild_mode"] is True
    assert item["strict_status"] == "xrd_clean_graph_rebuild_match"
    assert item["strict_visual_match"] is True
    assert item["plot_count_delta"] == 2
    assert item["style_match_ratio"] == 0.5
    assert product["status"] == "accepted"


def test_template_xrd_rows_use_reviewed_no_card_offset_spacing() -> None:
    rows = _template_xrd_normalized_offset_rows(
        ["two_theta_deg", "top", "middle", "CWO_PDF_JCPDS_card_sticks", "bottom"],
        [
            [5.0, 10.0, 20.0, 0.0, 100.0],
            [6.0, 20.0, 30.0, 0.75, 200.0],
        ],
    )

    assert rows[0][1:] == [3.45, 2.3, 0.0, 1.15]
    assert rows[1][1:] == [4.45, 3.3, 0.75, 2.15]


def test_template_xrd_standard_card_plot_count_is_not_sample_count(tmp_path: Path) -> None:
    template_dir = tmp_path / "XRD" / "CWO+BOBC"
    template_dir.mkdir(parents=True)
    card = template_dir / "CWO PDF#04-009-8466.txt"
    card.write_text("10 0 100\n", encoding="utf-8")
    template = TemplateCandidate(
        product_key="XRD",
        path=template_dir / "CWO+BOBC+card.opju",
        source="pairing_plan_exemplar",
        path_score=100,
        status="extracted",
        graph_page="Graph4",
        layer_count=3,
        plot_count=5,
    )
    pairing = TargetPairing(
        product_key="XRD",
        data_type="XRD",
        xps_subtype="",
        data_root_label="test",
        data_paths=[template_dir / "sample.txt"],
        opju_root_label="test",
        reference_opju=template.path,
    )

    assert _template_xrd_target_sample_series_count(pairing, template) == 4


def test_template_xrd_uses_pairing_data_before_template_adjacent_files(tmp_path: Path) -> None:
    template_dir = tmp_path / "template"
    data_dir = tmp_path / "data"
    template_dir.mkdir()
    data_dir.mkdir()
    (template_dir / "old_template_A.txt").write_text("5 100\n6 101\n", encoding="utf-8")
    (template_dir / "old_template_B.txt").write_text("5 200\n6 201\n", encoding="utf-8")
    current_a = data_dir / "current_A.txt"
    current_b = data_dir / "current_B.txt"
    current_a.write_text("5 1\n6 2\n", encoding="utf-8")
    current_b.write_text("5 3\n6 4\n", encoding="utf-8")
    template = TemplateCandidate(
        product_key="XRD",
        path=template_dir / "CWO+BOBC+card.opju",
        source="pairing_plan_exemplar",
        path_score=100,
        status="extracted",
        graph_page="Graph4",
        layer_count=1,
        plot_count=2,
    )
    pairing = TargetPairing(
        product_key="XRD",
        data_type="XRD",
        xps_subtype="",
        data_root_label="project_data",
        data_paths=[current_a],
        opju_root_label="origin_manual_save",
        reference_opju=template.path,
    )

    built = _build_template_xrd_multisource_table(pairing, template)

    assert built is not None
    assert built["headers"] == ["two_theta_deg", "current_A", "current_B"]
    assert [Path(path) for path in built["alignment"]["used_files"]] == [current_a, current_b]


def test_exemplar_driven_target_types_include_mott_without_changing_default_targets() -> None:
    assert "Mott-Schottky" not in TEMPLATE_TARGET_TYPES
    assert "Mott-Schottky" in TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES


def test_template_validation_prioritizes_product_keys_present_in_candidates() -> None:
    root = Path("F:/template_root")
    candidates = [
        TemplateCandidate(
            product_key="Mott-Schottky",
            path=root / "Mott" / "finished.opju",
            source="pairing_plan_exemplar",
            path_score=100,
        )
    ]

    targets = _prioritized_template_validation_targets(candidates, max_per_type=1)

    assert targets == candidates


def test_exemplar_driven_candidates_prefer_pairing_opju_before_embedded_snapshot(tmp_path: Path) -> None:
    reference = tmp_path / "BET" / "BOBC.opju"
    reference.parent.mkdir()
    reference.write_bytes(b"opju")
    pairing = TargetPairing(
        product_key="BET",
        data_type="BET",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[tmp_path / "BET" / "source.xls"],
        opju_root_label="f_drive_detection",
        reference_opju=reference,
        raw={},
    )

    candidates = _build_pairing_template_candidates({"BET": pairing}, ("BET",))
    validated_pairing = replace(candidates[0], status="extracted", graph_page="Graph1", layer_count=1, plot_count=1)
    selection = select_template("BET", [validated_pairing, candidates[1]])

    assert [candidate.source for candidate in candidates] == ["pairing_plan_exemplar", "embedded_template_snapshot"]
    assert candidates[0].path_score > candidates[1].path_score
    assert selection.status == "selected"
    assert selection.selected is not None
    assert selection.selected.source == "pairing_plan_exemplar"


def test_exemplar_driven_candidates_use_embedded_snapshot_when_pairing_missing() -> None:
    candidates = _build_pairing_template_candidates({}, ("BET",))
    selection = select_template("BET", candidates)

    assert [candidate.source for candidate in candidates] == ["embedded_template_snapshot"]
    assert selection.status == "selected"
    assert selection.selected is not None
    assert selection.selected.source == "embedded_template_snapshot"
    assert selection.selected.graph_page == "Graph5"


def test_missing_pairing_opju_falls_back_to_embedded_snapshot(tmp_path: Path) -> None:
    pairing = TargetPairing(
        product_key="BET",
        data_type="BET",
        xps_subtype="",
        data_root_label="test",
        data_paths=[tmp_path / "source.xls"],
        opju_root_label="test",
        reference_opju=tmp_path / "missing" / "template.opju",
        raw={},
    )
    candidates = _build_pairing_template_candidates({"BET": pairing}, ("BET",))

    validated = validate_template_candidates(candidates, tmp_path / "scan", max_per_type=2)
    selection = select_template("BET", validated)

    assert any(candidate.status == "load_failed" for candidate in validated)
    assert selection.status == "selected"
    assert selection.selected is not None
    assert selection.selected.source == "embedded_template_snapshot"


def test_pairing_path_repairs_single_opju_mojibake_basename(tmp_path: Path) -> None:
    real = tmp_path / "XRD" / "CWO+BOBC" / "CWO+BOBC+标卡.opju"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"opju")

    resolved = _resolve_pairing_path(tmp_path, r"XRD\CWO+BOBC\CWO+BOBC+깃엥.opju")

    assert resolved == real


def test_empty_run_relative_artifact_does_not_resolve_to_current_directory(tmp_path: Path) -> None:
    resolved = _resolve_run_relative_artifact(tmp_path, "")

    assert resolved == tmp_path / ".missing_artifact"
    assert not resolved.exists()


def test_exemplar_driven_repairs_mott_xrd_mismatch_to_mott_folder(tmp_path: Path) -> None:
    f_root = tmp_path / "f_drive"
    wrong = f_root / "XRD" / "BOBC+MS" / "bad没有明显峰.opju"
    wrong.parent.mkdir(parents=True)
    wrong.write_bytes(b"bad")
    mott_dir = f_root / "莫特肖特基" / "第一体系确定版本" / "bobc数据处理版本"
    finished = mott_dir / "bobc格式美化版本.opju"
    finished.parent.mkdir(parents=True)
    finished.write_bytes(b"x" * 150_000)
    data = mott_dir / "1000.xlsx"
    data.write_bytes(b"xlsx")
    pairing = TargetPairing(
        product_key="Mott-Schottky",
        data_type="Mott-Schottky",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[f_root / "莫特肖特基" / "old.csv"],
        opju_root_label="f_drive_detection",
        reference_opju=wrong,
        raw={"selected_opju_relative_path": "XRD/BOBC+MS/bad没有明显峰.opju"},
    )

    _first, remaining = _repair_exemplar_driven_pairings({}, {"Mott-Schottky": pairing}, {"f_drive_detection": f_root})

    repaired = remaining["Mott-Schottky"]
    assert repaired.reference_opju == finished
    assert repaired.data_paths == [data]
    assert repaired.raw["exemplar_driven_repair"] == "mott_pairing_reference_replaced_with_mott_folder_opju"


def test_exemplar_driven_repairs_epr_to_group_meeting_origin_package(tmp_path: Path) -> None:
    group_root = tmp_path / "group"
    origin_dir = (
        group_root
        / "\u7ed3\u679c\u6c47\u603b"
        / "EPR"
        / "final_EPR_OPJU_package_20260602"
        / "origin_files"
    )
    origin_dir.mkdir(parents=True)
    old = tmp_path / "f_drive" / "EPR" / "epr.opju"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    preferred = origin_dir / "epr_20260519_1_CuWO4_BiOBrCl_BiCu-10_OH_light_overlay.opju"
    secondary = origin_dir / "epr_20260601_2_CuWO4_BiOBrCl_BiCu-10_light_overlay.opju"
    preferred.write_bytes(b"preferred")
    secondary.write_bytes(b"secondary")
    pairing = TargetPairing(
        product_key="EPR",
        data_type="EPR",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[tmp_path / "f_drive" / "EPR" / "BC-O3-dark.xlsx"],
        opju_root_label="f_drive_detection",
        reference_opju=old,
        raw={"selected_opju_relative_path": "EPR/epr.opju"},
    )

    first, _remaining = _repair_exemplar_driven_pairings(
        {"EPR": pairing},
        {},
        {"workspace_group_data": group_root},
    )

    repaired = first["EPR"]
    assert repaired.reference_opju == preferred
    assert repaired.opju_root_label == "workspace_group_data"
    assert str(repaired.raw["selected_opju_relative_path"]).replace("\\", "/") == (
        "\u7ed3\u679c\u6c47\u603b/EPR/final_EPR_OPJU_package_20260602/origin_files/"
        "epr_20260519_1_CuWO4_BiOBrCl_BiCu-10_OH_light_overlay.opju"
    )
    assert repaired.raw["exemplar_driven_repair"] == "epr_pairing_reference_replaced_with_group_meeting_origin_package"


def test_prepare_template_product_compact_output_uses_flat_type_product_dir(tmp_path: Path) -> None:
    data = tmp_path / "BET" / "bet.csv"
    data.parent.mkdir()
    data.write_text("relative_pressure_p_p0,quantity_adsorbed\n0.1,1\n0.5,2\n", encoding="utf-8")
    reference = tmp_path / "BET" / "reference.opju"
    reference.write_bytes(b"opju")
    pairing = TargetPairing(
        product_key="BET",
        data_type="BET",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[data],
        opju_root_label="f_drive_detection",
        reference_opju=reference,
        raw={},
    )
    template = TemplateCandidate(
        product_key="BET",
        path=reference,
        source="pairing_plan_exemplar",
        status="valid",
        graph_page="Graph1",
        layer_count=1,
        plot_count=2,
    )

    product, _extra = prepare_template_product(tmp_path / "run", pairing, template, compact_output=True)

    assert product.type_root == tmp_path / "run" / "products" / "BET"
    assert product.processed_data.parent == product.type_root
    assert product.origin_file.parent == product.type_root
    assert product.figure_tif.parent == product.type_root
    assert product.preview_png.parent == product.type_root
    assert product.input_copies == []
    assert product.reference_opju_copy == reference


def test_prepare_template_product_compact_keeps_original_reference_source(tmp_path: Path) -> None:
    data = tmp_path / "BET" / "bet.csv"
    data.parent.mkdir()
    data.write_text("relative_pressure_p_p0,quantity_adsorbed\n0.1,1\n0.5,2\n", encoding="utf-8")
    reference = tmp_path / "BET" / "reference.opju"
    reference.write_bytes(b"opju")
    scan_copy = tmp_path / "scan" / "001_reference.opju"
    scan_copy.parent.mkdir()
    scan_copy.write_bytes(b"scan")
    pairing = TargetPairing(
        product_key="BET",
        data_type="BET",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[data],
        opju_root_label="f_drive_detection",
        reference_opju=reference,
        raw={},
    )
    template = TemplateCandidate(
        product_key="BET",
        path=reference,
        source="pairing_plan_exemplar",
        status="valid",
        graph_page="Graph1",
        layer_count=1,
        plot_count=2,
        metadata={"scan_copy": str(scan_copy)},
    )

    product, _extra = prepare_template_product(tmp_path / "run", pairing, template, compact_output=True)

    assert product.reference_opju_copy == reference


def test_prepare_template_product_compact_eis_keeps_sidecars_in_debug(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "EIS" / "eis.txt"
    data.parent.mkdir()
    data.write_text("placeholder", encoding="utf-8")
    reference = tmp_path / "EIS" / "reference.opju"
    reference.write_bytes(b"opju")
    points = [
        EisPoint(1, 1000.0, 10.0, 1.0),
        EisPoint(2, 100.0, 20.0, 5.0),
        EisPoint(3, 10.0, 30.0, 2.0),
    ]
    fit = EisFitResult(
        method="stub_fit",
        points=[(10.0, 1.0), (20.0, 5.0), (30.0, 2.0)],
        parameters={"Rs": 1.0, "Rct": 2.0, "Q": 3.0, "n": 0.9},
        residual_sse=0.0,
        robust_cost=0.0,
    )
    monkeypatch.setattr(
        "src.core.template_product_builder.clean_eis_file",
        lambda _path: EisCleaningResult(points, points, [], {"z_real_ohm": "Zreal", "minus_z_imag_ohm": "Zimag"}),
    )
    monkeypatch.setattr("src.core.template_product_builder.draft_fit_eis_randles_cpe", lambda _points: fit)
    monkeypatch.setattr("src.core.template_product_builder.clip_eis_fit_to_measured_range", lambda _points, full_fit: full_fit)
    pairing = TargetPairing(
        product_key="EIS",
        data_type="EIS",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[data],
        opju_root_label="f_drive_detection",
        reference_opju=reference,
        raw={},
    )
    template = TemplateCandidate(
        product_key="EIS",
        path=reference,
        source="pairing_plan_exemplar",
        status="valid",
        graph_page="Graph1",
        layer_count=1,
        plot_count=2,
    )

    product, _extra = prepare_template_product(tmp_path / "run", pairing, template, compact_output=True)

    assert product.type_root == tmp_path / "run" / "products" / "EIS"
    assert product.processed_data.parent == product.type_root
    assert (product.type_root / "debug" / "raw_eis_data.csv").is_file()
    assert (product.type_root / "debug" / "eis_cleaning_and_fit_metadata.json").is_file()
    assert not (product.type_root / "processed_data").exists()
    assert not (product.type_root / "metadata").exists()
    assert not (product.type_root / "reports").exists()


def test_prepare_template_product_compact_epr_uses_debug_plan_without_input_copies(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "EPR"
    data_dir.mkdir()
    for file_name in ("bc.xlsx", "cwo.xlsx", "bobc.xlsx"):
        (data_dir / file_name).write_bytes(b"xlsx")
    reference = tmp_path / "EPR" / "reference.opju"
    reference.write_bytes(b"opju")

    monkeypatch.setattr(
        "src.core.template_product_builder.DEFAULT_EPR_GROUPS",
        {"OH": [("BC", "bc.xlsx"), ("CWO", "cwo.xlsx"), ("BOBC", "bobc.xlsx")]},
    )

    def fake_read_xy_xlsx(path: Path) -> tuple[list[float], list[float]]:
        offset = {"bc.xlsx": 0.0, "cwo.xlsx": 1.0, "bobc.xlsx": 2.0}[path.name]
        return [1.0, 2.0, 3.0], [offset + 1.0, offset + 2.0, offset + 3.0]

    monkeypatch.setattr("src.core.template_product_builder.read_xy_xlsx", fake_read_xy_xlsx)
    pairing = TargetPairing(
        product_key="EPR",
        data_type="EPR",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[data_dir / "bc.xlsx"],
        opju_root_label="f_drive_detection",
        reference_opju=reference,
        raw={},
    )
    template = TemplateCandidate(
        product_key="EPR",
        path=reference,
        source="pairing_plan_exemplar",
        status="valid",
        graph_page="ohG",
        layer_count=1,
        plot_count=3,
    )

    product, _extra = prepare_template_product(tmp_path / "run", pairing, template, compact_output=True)
    plan_path = product.type_root / "debug" / "epr_origin_processing_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert product.type_root == tmp_path / "run" / "products" / "EPR"
    assert product.input_copies == []
    assert product.processed_data.parent == product.type_root
    assert plan["final_product_processed_csv"] == "../EPR_OH_overlay_exemplar.csv"
    assert plan["raw_origin_input_csv"] == "epr_oh_overlay_origin_raw_input.csv"
    assert plan["origin_detail_csv"] == "epr_oh_overlay_origin_detail.csv"
    assert not (product.type_root / "input_copies").exists()
    assert not (product.type_root / "processed_data").exists()
    assert not (product.type_root / "metadata").exists()
