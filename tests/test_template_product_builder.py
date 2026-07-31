from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from src.core.epr_jeol import JeolEprExportSeries
from src.processors.eis import EisCleaningResult, EisPoint

from src.core.template_product_builder import (
    TEMPLATE_ACCEPTED_TYPES,
    TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES,
    TEMPLATE_TARGET_TYPES,
    TemplateProductBuilderOptions,
    TemplateCandidate,
    TemplateSelection,
    classify_template_project_style_asset_candidates,
    classify_template_xps_reference_candidates,
    classify_template_candidates,
    prepare_template_product,
    run_template_product_builder_all_types,
    select_template,
    validate_template_candidates,
    template_acceptance_status,
    _build_pairing_template_candidates,
    _build_template_eis_table,
    _repair_exemplar_driven_pairings,
    _prioritized_template_validation_targets,
    _build_template_xrd_multisource_table,
    _resolve_run_relative_artifact,
    _template_xrd_normalized_offset_rows,
    _template_xrd_target_sample_series_count,
    _write_template_preview_comparison,
    _blocked_product_record,
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


def test_asset_only_builder_never_scans_external_template_roots(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    style_root.mkdir(parents=True)
    (style_root / "manifest.json").write_text('{"schema_version":1,"assets":[]}', encoding="utf-8")
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")

    def fail_external_scan(_root: Path | None) -> list[Path]:
        raise AssertionError("asset-only mode must not scan external template roots")

    monkeypatch.setattr("src.core.template_product_builder.scan_template_f_drive_template_paths", fail_external_scan)
    monkeypatch.setattr("src.core.template_product_builder.scan_template_optional_template_paths", fail_external_scan)
    monkeypatch.setattr(
        "src.core.template_product_builder.validate_origin_style_asset_integrity",
        lambda *_args, **_kwargs: {"ok": True, "schema_version": 2, "failures": []},
    )

    result = run_template_product_builder_all_types(
        project_root,
        TemplateProductBuilderOptions(
            pairing_path=pairing,
            output_root=tmp_path / "out",
            timestamp="20260711_120000",
            asset_only=True,
            external_reference_preview_comparison=True,
            f_drive_template_root=tmp_path / "external_f",
            xps_reference_template_root=tmp_path / "external_xps",
            xps_non_in_situ_template_root=tmp_path / "external_xps_non",
        ),
    )

    assert result["summary"]["asset_only"] is True
    assert result["summary"]["external_template_dependency"] is False
    manifest = json.loads((Path(result["run_root"]) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "asset_only_no_origin"
    assert len(manifest["input_paths"]) == 2
    assert all("external_" not in value for value in manifest["input_paths"])


def test_asset_only_builder_requires_hash_verified_v2_manifest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"theme")
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "graph_page": "Graph1",
                        "format_theme": "format_themes/BET.oth",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")

    try:
        run_template_product_builder_all_types(
            project,
            TemplateProductBuilderOptions(pairing_path=pairing, asset_only=True, only_type="BET"),
        )
    except ValueError as exc:
        assert "schema v2 is required" in str(exc)
    else:
        raise AssertionError("asset-only generation must reject a manifest without mandatory hashes")


def test_blocked_product_records_report_external_template_dependency(tmp_path: Path) -> None:
    external = TemplateCandidate(
        product_key="BET",
        path=tmp_path / "external.opju",
        source="f_drive_scan",
        status="valid",
        graph_page="Graph1",
    )
    selection = TemplateSelection(product_key="BET", status="selected", selected=external, candidates=(external,))

    normal = _blocked_product_record(tmp_path / "normal", "BET", selection)
    asset_only = _blocked_product_record(tmp_path / "asset", "BET", selection, asset_only=True)

    assert normal["external_template_dependency"] is True
    assert asset_only["external_template_dependency"] is False


def test_asset_only_builder_rejects_exemplar_driven_mode(tmp_path: Path) -> None:
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")

    try:
        run_template_product_builder_all_types(
            tmp_path,
            TemplateProductBuilderOptions(pairing_path=pairing, asset_only=True, exemplar_driven=True),
        )
    except ValueError as exc:
        assert "mutually exclusive" in str(exc)
    else:
        raise AssertionError("asset-only and exemplar-driven modes must not run together")


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


def test_embedded_template_preview_rejects_nonzero_plot_count_delta(tmp_path: Path) -> None:
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
    assert item["strict_status"] == "blocked_embedded_template_snapshot"
    assert item["strict_visual_match"] is False
    assert item["plot_count_delta"] == -8
    assert item["style_match_ratio"] == 0.5
    assert product["status"] == "blocked"


def test_embedded_xrd_card_legend_does_not_exempt_plot_count_delta(tmp_path: Path) -> None:
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
    assert item["strict_status"] == "blocked_embedded_template_snapshot"
    assert item["strict_visual_match"] is False
    assert item["plot_count_delta"] == 3
    assert product["status"] == "blocked"


def test_embedded_template_preview_high_rms_cannot_pass_structural_readback(
    tmp_path: Path,
) -> None:
    product_root = tmp_path / "products" / "BET"
    product_root.mkdir(parents=True)
    reference = product_root / "reference.png"
    generated = product_root / "generated.png"
    Image.new("RGB", (64, 48), "white").save(reference)
    Image.new("RGB", (64, 48), "black").save(generated)
    metadata = product_root / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "template_plot_count": 1,
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
                    "conformance": {"compared_fields": 10, "matched_fields": 10},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    product = {
        "type": "BET",
        "status": "accepted",
        "visual_acceptance": True,
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
        "conformance": {"compared_fields": 10, "matched_fields": 10},
    }

    audit = _write_template_preview_comparison(tmp_path, [product])

    item = audit["items"][0]
    assert item["embedded_template_snapshot_mode"] is True
    assert item["preview_rms"] > 35.0
    assert item["strict_visual_match"] is False
    assert item["strict_status"] == "blocked_embedded_template_snapshot"
    assert product["visual_acceptance"] is False
    assert product["status"] == "blocked"
    assert "preview RMS" in product["notes"]


def test_xrd_clean_rebuild_preview_rejects_nonzero_plot_count_delta(tmp_path: Path) -> None:
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
    assert item["strict_status"] == "blocked_xrd_clean_graph_rebuild"
    assert item["strict_visual_match"] is False
    assert item["plot_count_delta"] == 2
    assert item["style_match_ratio"] == 0.5
    assert product["status"] == "blocked"


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


def test_template_xrd_finds_card_beside_pairing_opju_when_style_asset_is_elsewhere(tmp_path: Path) -> None:
    reference_dir = tmp_path / "XRD" / "CWO+BOBC"
    data_dir = tmp_path / "XRD" / "current"
    style_dir = tmp_path / "templates" / "origin_styles" / "format_themes"
    reference_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    style_dir.mkdir(parents=True)
    reference = reference_dir / "CWO+BOBC+card.opju"
    reference.write_bytes(b"opju")
    (reference_dir / "CWO PDF#04-009-8466.txt").write_text("10 0 100\n", encoding="utf-8")
    source = data_dir / "sample.txt"
    source.write_text("5 1\n6 2\n", encoding="utf-8")
    template = TemplateCandidate(
        product_key="XRD",
        path=style_dir / "XRD.oth",
        source="project_origin_style_asset",
        graph_page="Graph4",
        plot_count=5,
    )
    pairing = TargetPairing("XRD", "XRD", "", "root", [source], "root", reference)

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


def test_all_template_target_modes_include_mott() -> None:
    assert "Mott-Schottky" in TEMPLATE_TARGET_TYPES
    assert "Mott-Schottky" in TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES
    assert TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES == TEMPLATE_TARGET_TYPES


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


def test_prepare_template_product_compact_eis_keeps_all_measured_points_without_fit_sidecars(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
    monkeypatch.setattr(
        "src.core.template_product_builder.clean_eis_file",
        lambda _path: EisCleaningResult(
            points,
            points[:2],
            [],
            {"z_real_ohm": "Zreal", "minus_z_imag_ohm": "Zimag"},
        ),
    )
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

    product, extra = prepare_template_product(
        tmp_path / "run",
        pairing,
        template,
        compact_output=True,
        eis_strict_semicircle_branch=True,
    )

    assert product.type_root == tmp_path / "run" / "products" / "EIS"
    assert product.processed_data.parent == product.type_root
    lines = product.processed_data.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "measured_z_real_kohm,measured_minus_z_imag_kohm"
    assert lines[1:] == ["0.01,0.001", "0.02,0.005", "0.03,0.002"]
    eis = extra["eis_cleaning"]
    assert eis["mode"] == "formal_measured_points_only"
    assert eis["raw_point_count"] == 3
    assert eis["plotted_point_count"] == 3
    assert eis["fit"]["status"] == "not_run"
    assert eis["strict_semicircle_branch"] is False
    assert eis["strict_semicircle_branch_requested"] is True
    assert not (product.type_root / "debug" / "eis_randles_cpe_fit_curve.csv").exists()
    assert not (product.type_root / "debug" / "eis_fit_parameters.json").exists()
    assert not (product.type_root / "processed_data").exists()
    assert not (product.type_root / "metadata").exists()
    assert not (product.type_root / "reports").exists()


def test_template_eis_overlay_selects_exact_real_source_family_for_template_count(tmp_path: Path, monkeypatch) -> None:
    eis_root = tmp_path / "EIS"
    source_dir = eis_root / "20260202"
    reference_dir = eis_root / "20260203"
    old_dir = eis_root / "20251106" / "BOBC"
    source_dir.mkdir(parents=True)
    reference_dir.mkdir(parents=True)
    old_dir.mkdir(parents=True)
    names = ["b11-2-z", "b11-z", "b3", "b7", "b9-2z", "b9-z", "bobc-z", "cwo-z"]
    for name in names:
        (source_dir / f"{name}.txt").write_text("measured", encoding="utf-8")
    old_data = old_dir / "EIS-1.txt"
    old_data.write_text("old", encoding="utf-8")
    reference = reference_dir / "2eis20260202.opju"
    reference.write_bytes(b"opju")

    def fake_clean(path: Path) -> EisCleaningResult:
        base = float(sum(ord(char) for char in path.stem) % 10 + 1)
        points = [
            EisPoint(1, 1000.0, base * 1000.0, base * 500.0),
            EisPoint(2, 100.0, base * 2000.0, base * 700.0),
        ]
        # Discovery requires at least ten raw points; retain deterministic values.
        points = [EisPoint(index + 1, 1000.0 / (index + 1), point.z_real_ohm + index, point.minus_z_imag_ohm + index) for index in range(10) for point in points[:1]]
        return EisCleaningResult(points, points, [], {"z_real_ohm": "Zreal", "minus_z_imag_ohm": "Zimag"})

    monkeypatch.setattr("src.core.template_product_builder.clean_eis_file", fake_clean)
    pairing = TargetPairing(
        product_key="EIS",
        data_type="EIS",
        xps_subtype="",
        data_root_label="f_drive_detection",
        data_paths=[old_data],
        opju_root_label="f_drive_detection",
        reference_opju=reference,
        raw={},
    )
    template = TemplateCandidate(
        product_key="EIS",
        path=tmp_path / "templates" / "EIS.oth",
        source="project_origin_style_asset",
        status="valid",
        graph_page="Graph1",
        layer_count=1,
        plot_count=8,
    )

    headers, rows, labels, extra = _build_template_eis_table(
        pairing,
        tmp_path / "run" / "EIS",
        template,
        strict_semicircle_branch=True,
        compact_output=True,
    )

    assert len(headers) == 16
    assert len(rows) == 10
    assert labels["legend_entries"] == ["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"]
    assert [Path(path).name for path in extra["eis_overlay"]["source_files"]] == [f"{name}.txt" for name in names]
    assert extra["eis_cleaning"]["mode"] == "reviewed_template_multi_source_overlay"
    assert extra["eis_cleaning"]["plotted_source_count"] == 8
    assert (tmp_path / "run" / "EIS" / "debug" / "eis_cleaning_and_fit_metadata.json").is_file()


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

    def fake_read_verified_jeol_export_series(path: Path) -> JeolEprExportSeries:
        offset = {"bc.xlsx": 0.0, "cwo.xlsx": 1.0, "bobc.xlsx": 2.0}[path.name]
        return JeolEprExportSeries(
            [1.0, 2.0, 3.0],
            [offset + 1.0, offset + 2.0, offset + 3.0],
            "G",
            "test_fixture",
            None,
        )

    monkeypatch.setattr(
        "src.core.template_product_builder.read_verified_jeol_export_series",
        fake_read_verified_jeol_export_series,
    )
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


def test_ordinary_template_origin_export_imports_every_y_column(tmp_path: Path, monkeypatch) -> None:
    from src.core import template_product_builder as builder
    from src.core.template_product_common import ProductContext
    from src.origin.operations import OperationResult
    from src.origin.style_mimic import OpjuStyleSnapshot
    from src.origin.user_style import ResolvedPlotStyle

    headers = ["x", *[f"y{index}" for index in range(1, 12)]]
    processed = tmp_path / "product" / "processed.csv"
    processed.parent.mkdir(parents=True)
    processed.write_text(",".join(headers) + "\n" + ",".join(str(index) for index in range(len(headers))) + "\n", encoding="utf-8")
    reference = tmp_path / "reference.opju"
    reference.write_bytes(b"reference")
    pairing = TargetPairing("PL", "PL", "", "fixture", [processed], "fixture", reference)
    product = ProductContext(
        product_key="PL",
        slug="pl_many_series",
        pairing=pairing,
        type_root=processed.parent,
        processed_data=processed,
        input_copies=[],
        reference_opju_copy=reference,
        reference_preview_png=processed.parent / "reference.png",
        origin_file=processed.parent / "product.opju",
        figure_tif=processed.parent / "product.tif",
        preview_png=processed.parent / "product.png",
        x_label="X",
        y_label="Y",
        graph_title="PL",
    )
    snapshot = OpjuStyleSnapshot("reference.opju", "extracted", graph_page=None, plot_count=11)

    class FakeConformance:
        def to_dict(self) -> dict[str, object]:
            return {"status": "pass", "compared_fields": 1, "matched_fields": 1}

    class FakeOriginOps:
        def __init__(self) -> None:
            self.y_columns: list[int] = []

        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def import_csv_to_worksheet(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok", {"book_name": "Book1"})

        def create_graph(self, _graph: str, _book: str, _sheet: str, _x: int, y: int, **_kwargs) -> OperationResult:
            self.y_columns.append(y)
            return OperationResult(True, "ok", {"graph_name": "Graph1"})

        def add_plot_to_graph(self, _graph: str, _book: str, _sheet: str, _x: int, y: int, **_kwargs) -> OperationResult:
            self.y_columns.append(y)
            return OperationResult(True, "ok")

        def _plot_names(self, _graph: str) -> list[str]:
            return []

        def run_labtalk(self, _script: str) -> OperationResult:
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            assert name in {"page.width", "page.height"}
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            return OperationResult(True, "ok")

        def set_axis_labels(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok")

        def set_graph_font(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok")

        def set_tick_style(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok")

        def set_axis_and_tick_visibility(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok")

        def set_legend(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok")

        def set_plot_style(self, *_args, **_kwargs) -> OperationResult:
            return OperationResult(True, "ok")

        def save_project(self, path: Path) -> OperationResult:
            path.write_bytes(b"opju")
            return OperationResult(True, "ok")

        def load_project(self, _path: Path) -> OperationResult:
            return OperationResult(True, "ok")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "ok", {"pages": [{"name": "Graph1", "type": "graph"}]})

        def export_graph(self, _graph: str, path: Path, _fmt: str, **_kwargs) -> OperationResult:
            path.parent.mkdir(parents=True, exist_ok=True)
            if _fmt == "tif":
                Image.new("RGB", (60, 60), "white").save(path, format="TIFF", dpi=(600, 600))
            else:
                path.write_bytes(b"image")
            return OperationResult(True, "ok")

        def close(self) -> OperationResult:
            return OperationResult(True, "closed")

    operations = FakeOriginOps()
    monkeypatch.setattr(builder, "connect_origin", lambda **_kwargs: operations)
    monkeypatch.setattr(builder, "_extract_template_product_reference_snapshot", lambda *_args: snapshot)
    monkeypatch.setattr(builder, "apply_style_snapshot", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(builder, "read_graph_style_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(builder, "compare_style_snapshots", lambda *_args, **_kwargs: FakeConformance())

    result = builder.export_template_product_with_origin(product, ResolvedPlotStyle())

    assert result["ok"] is True
    assert operations.y_columns == list(range(2, len(headers) + 1))
    assert result["tif_resolution_evidence"]["width_px"] == 60
    assert result["tif_resolution_evidence"]["effective_dpi_x"] == 600.0

    operations.close = lambda: OperationResult(False, "Origin still running")
    close_failure = builder.export_template_product_with_origin(product, ResolvedPlotStyle())
    assert close_failure["ok"] is False
    assert close_failure["failure_stage"] == "origin_close"
    assert "Origin still running" in str(close_failure["message"])


def test_native_tif_export_resets_identity_after_readback_and_reactivates_graph(tmp_path: Path) -> None:
    from src.core.template_product_builder import _export_native_tif_with_physical_validation
    from src.origin.operations import OperationResult

    calls: list[str] = []

    class FakeOriginOps:
        def run_labtalk(self, script: str) -> OperationResult:
            calls.append(f"labtalk:{script}")
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            calls.append(f"read:{name}")
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            calls.append("reset_identity")
            return OperationResult(True, "ok")

        def export_graph(
            self,
            graph_name: str,
            path: Path,
            fmt: str,
            *,
            dpi: int,
            pixel_width: int,
        ) -> OperationResult:
            calls.append(f"export:{graph_name}:{fmt}:{dpi}:{pixel_width}")
            Image.new("RGB", (60, 60), "white").save(path, format="TIFF", dpi=(600, 600))
            return OperationResult(True, "ok")

    target = tmp_path / "product.tif"
    result = _export_native_tif_with_physical_validation(
        FakeOriginOps(),
        "Graph1",
        target,
        dpi=600,
    )

    assert result["ok"] is True
    assert calls == [
        'labtalk:win -a "Graph1";',
        "read:page.width",
        "read:page.height",
        "reset_identity",
        'labtalk:win -a "Graph1";',
        "export:Graph1:tif:600:60",
    ]


def test_native_tif_export_rejects_unverified_identity_without_leaking_prior_path(tmp_path: Path) -> None:
    from src.core.template_product_builder import _export_native_tif_with_physical_validation
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def run_labtalk(self, _script: str) -> OperationResult:
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, _name: str) -> OperationResult:
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            return OperationResult(False, "D:/private/project/secret.opju")

        def export_graph(self, *_args, **_kwargs) -> OperationResult:
            raise AssertionError("TIFF export must not run after identity verification failure")

    target = tmp_path / "product.tif"
    result = _export_native_tif_with_physical_validation(
        FakeOriginOps(),
        "Graph1",
        target,
        dpi=600,
    )

    assert result["ok"] is False
    assert "identity verification failed" in result["message"]
    assert "private" not in result["message"]
    assert not target.exists()
