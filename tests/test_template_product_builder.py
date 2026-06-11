from __future__ import annotations

from pathlib import Path

from src.processors.eis import EisFitResult, EisPoint

from src.core.template_product_builder import (
    TEMPLATE_ACCEPTED_TYPES,
    TEMPLATE_TARGET_TYPES,
    TemplateProductBuilderOptions,
    TemplateCandidate,
    classify_template_project_style_asset_candidates,
    classify_template_xps_reference_candidates,
    classify_template_candidates,
    clip_eis_fit_to_measured_range,
    run_template_product_builder_all_types,
    select_template,
    template_acceptance_status,
)


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


def test_classify_template_project_style_asset_candidates_use_cached_graph_templates(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    graph_dir = style_root / "graph_templates"
    graph_dir.mkdir(parents=True)
    template = graph_dir / "BET.otpu"
    template.write_text("cached style package", encoding="utf-8")
    (style_root / "manifest.json").write_text(
        """{
  "schema_version": 1,
  "assets": [
    {
      "product_key": "BET",
      "data_type": "BET",
      "graph_template": "graph_templates/BET.otpu",
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
    assert candidate.path == template
    assert candidate.source == "project_origin_style_asset"
    assert candidate.status == "valid"
    assert candidate.graph_page == "Graph1"
    assert candidate.metadata["style_asset"]["graph_template"] == "graph_templates/BET.otpu"


def test_template_builder_uses_project_style_assets_without_default_external_scan(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    style_root = project_root / "templates" / "origin_styles"
    graph_dir = style_root / "graph_templates"
    graph_dir.mkdir(parents=True)
    (graph_dir / "BET.otpu").write_bytes(b"otpu")
    (style_root / "manifest.json").write_text(
        """{
  "schema_version": 1,
  "assets": [
    {"product_key":"BET","data_type":"BET","graph_template":"graph_templates/BET.otpu","status":"accepted","graph_page":"Graph1"}
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
