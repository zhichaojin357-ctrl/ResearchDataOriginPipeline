from __future__ import annotations

from pathlib import Path

from src.cli import main
from src.processors.eis import EisFitResult, EisPoint

from src.core.v3_real_template_rebuild import (
    V3_ACCEPTED_TYPES,
    V3RealTemplateRebuildOptions,
    V3_TARGET_TYPES,
    V3TemplateCandidate,
    classify_v3_project_style_asset_candidates,
    classify_v3_xps_reference_candidates,
    classify_v3_template_candidates,
    clip_eis_fit_to_measured_range,
    select_v3_template,
    v3_acceptance_status,
)


def test_classify_v3_templates_uses_f_drive_type_paths_and_separates_xps_subtypes() -> None:
    root = Path("F:/课题/LL/检测")
    paths = [
        root / "BET" / "BOBC.opju",
        root / "XPS" / "原位" / "insitu.opju",
        root / "XPS" / "bobc xps.opju",
        root / "XRD" / "CWO+BOBC" / "CWO+BOBC+标卡.opju",
        root / "阻抗EIS" / "20260203李永进CWO+BOBC" / "2eis图20260202.opju",
        root / "固体紫外" / "BOBC+MS.opju",
        root / "光电流响应" / "I-T BOBC+CWO 4.22.opju",
    ]

    classified = classify_v3_template_candidates(paths, f_drive_root=root)

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
    assert tuple(V3_TARGET_TYPES) == tuple(V3_ACCEPTED_TYPES)


def test_classify_v3_xps_reference_root_uses_in_situ_reference_opjus(tmp_path: Path) -> None:
    reference_root = tmp_path / "xps参考图像"
    reference_root.mkdir()
    bi_cl_br = reference_root / "xps_in_situ_Bi_Cl_Br.opju"
    cu_w = reference_root / "xps_in_situ_Cu_W.opju"
    non_in_situ = reference_root / "xps_non_in_situ_overview.opju"
    note = reference_root / "notes.txt"
    for path in (bi_cl_br, cu_w, non_in_situ, note):
        path.write_text("placeholder", encoding="utf-8")

    classified = classify_v3_xps_reference_candidates(
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


def test_classify_v3_project_style_asset_candidates_use_cached_graph_templates(tmp_path: Path) -> None:
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

    candidates = classify_v3_project_style_asset_candidates(project_root)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.product_key == "BET"
    assert candidate.path == template
    assert candidate.source == "project_origin_style_asset"
    assert candidate.status == "valid"
    assert candidate.graph_page == "Graph1"
    assert candidate.metadata["style_asset"]["graph_template"] == "graph_templates/BET.otpu"


def test_select_v3_template_blocks_missing_or_data_only_candidates() -> None:
    root = Path("F:/课题/LL/检测")
    candidates = [
        V3TemplateCandidate(
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

    selection = select_v3_template("XPS_in_situ", candidates)
    missing = select_v3_template("Raman", candidates)

    assert selection.status == "blocked"
    assert "data-only" in selection.reason
    assert missing.status == "blocked"
    assert "No F-drive OPJU/OPJ template candidate" in missing.reason


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


def test_v3_acceptance_status_uses_strict_accepted_blocked_terms_only(tmp_path: Path) -> None:
    artifact = tmp_path / "ok.bin"
    artifact.write_text("x", encoding="utf-8")
    accepted = v3_acceptance_status(
        has_required_artifacts=True,
        no_label_pass=True,
        readback_pass=True,
        visual_acceptance=True,
        line_width_acceptance=True,
        axis_title_acceptance=True,
        exemplar_similarity=True,
        notes=[],
    )
    blocked = v3_acceptance_status(
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


def test_cli_unified_v3_passes_template_root_and_output_options(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")
    output_root = tmp_path / "external"
    f_root = tmp_path / "f_drive"
    xps_reference_root = tmp_path / "xps参考图像"
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: V3RealTemplateRebuildOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(output_root / "runs" / "fake"),
            "summary": {"product_count": 11, "accepted_count": 10, "blocked_count": 1, "failed_count": 0},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.run_v3_real_template_rebuild_all_types", fake_run)

    code = main(
        [
            "unified-v3-real-template-rebuild-all-types",
            "--pairing",
            str(pairing),
            "--output-root",
            str(output_root),
            "--with-origin",
            "--timestamp",
            "20260605_180000",
            "--f-drive-template-root",
            str(f_root),
            "--xps-reference-template-root",
            str(xps_reference_root),
        ]
    )

    assert code == 0
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, V3RealTemplateRebuildOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.with_origin is True
    assert options.timestamp == "20260605_180000"
    assert options.f_drive_template_root == f_root
    assert options.xps_reference_template_root == xps_reference_root
