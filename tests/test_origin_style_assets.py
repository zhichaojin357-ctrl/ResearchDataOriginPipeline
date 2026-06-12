from __future__ import annotations

import json
from pathlib import Path

from src.cli import main
from src.origin.template_format import build_template_format_plan


def test_reference_opju_assets_do_not_embed_workspace_or_assistant_markers() -> None:
    project_root = Path(__file__).resolve().parents[1]
    reference_root = project_root / "templates" / "origin_styles" / "reference_opju"
    assets = sorted(reference_root.glob("*.opju"))
    forbidden = [
        b"codex",
        b"openai",
        b"chatgpt",
        b"assistant",
        b"Codex Project",
        b"ResearchDataOriginPipeline",
        b"D:\\Codex",
        b"D:/Codex",
    ]

    assert assets
    hits: list[str] = []
    for asset in assets:
        data = asset.read_bytes()
        lowered = data.lower()
        for pattern in forbidden:
            if pattern.lower() in lowered:
                hits.append(f"{asset.name}: {pattern.decode('utf-8', 'ignore')}")

    assert hits == []


def test_origin_style_manifest_resolves_project_local_template(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset = project / "templates" / "origin_styles" / "graph_templates" / "BET.otpu"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"otpu")
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "graph_template": "graph_templates/BET.otpu",
                        "status": "accepted",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    from src.origin.style_registry import resolve_origin_style_asset

    resolved = resolve_origin_style_asset(project, "BET")

    assert resolved is not None
    assert resolved.product_key == "BET"
    assert resolved.graph_template_path == asset
    assert resolved.graph_template_path.is_file()


def test_template_plan_uses_project_style_asset_when_opju_is_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset = project / "templates" / "origin_styles" / "graph_templates" / "EPR.otpu"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"otpu")
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "EPR",
                        "data_type": "EPR",
                        "graph_template": "graph_templates/EPR.otpu",
                        "status": "accepted",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    from src.origin.style_registry import resolve_origin_style_asset

    style_asset = resolve_origin_style_asset(project, "EPR")
    plan = build_template_format_plan(
        "EPR",
        opju_path=tmp_path / "missing.opju",
        style_package_path=style_asset.graph_template_path if style_asset else None,
    )

    assert plan.status == "ready"
    assert plan.mode == "cached_style_package"
    assert plan.style_package_path == asset


def test_style_asset_export_plan_requires_accepted_products(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    reports = run_root / "reports"
    reports.mkdir(parents=True)
    reports.joinpath("template_preview_comparison.json").write_text(
        json.dumps(
            {
                "items": [
                    {"type": "BET", "status": "accepted", "strict_visual_match": True, "preview_rms": 1.0},
                    {"type": "EPR", "status": "blocked", "strict_visual_match": False, "preview_rms": 99.0},
                ]
            }
        ),
        encoding="utf-8",
    )
    bet_meta = run_root / "BET" / "metadata" / "BET.json"
    bet_meta.parent.mkdir(parents=True)
    bet_opju = run_root / "BET" / "origin_files" / "BET.opju"
    bet_opju.parent.mkdir(parents=True)
    bet_opju.write_bytes(b"opju")
    bet_meta.write_text(
        json.dumps(
            {
                "product_key": "BET",
                "data_type": "BET",
                "status": "accepted",
                "template_graph": "Graph3",
                "origin_file": str(bet_opju),
                "preview_png": str(run_root / "BET" / "figures_preview" / "BET.png"),
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import build_origin_style_asset_export_plan

    plan = build_origin_style_asset_export_plan(tmp_path / "project", run_root)

    assert [item.product_key for item in plan.items] == ["BET"]
    assert plan.items[0].graph_template_path.name == "BET.otpu"


def test_style_asset_export_plan_matches_uv_vis_report_name_to_folder(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    reports = run_root / "reports"
    reports.mkdir(parents=True)
    reports.joinpath("template_preview_comparison.json").write_text(
        json.dumps(
            {
                "items": [
                    {"type": "UV-vis DRS / Tauc", "status": "accepted", "strict_visual_match": True, "preview_rms": 0.0}
                ]
            }
        ),
        encoding="utf-8",
    )
    meta = run_root / "UV_vis_DRS_Tauc" / "metadata" / "UV.json"
    meta.parent.mkdir(parents=True)
    opju = run_root / "UV_vis_DRS_Tauc" / "origin_files" / "UV.opju"
    opju.parent.mkdir(parents=True)
    opju.write_bytes(b"opju")
    meta.write_text(
        json.dumps(
            {
                "product_key": "UV_vis_DRS_Tauc",
                "data_type": "UV-vis DRS / Tauc",
                "status": "accepted",
                "template_graph": "Graph1",
                "origin_file": str(opju),
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import build_origin_style_asset_export_plan

    plan = build_origin_style_asset_export_plan(tmp_path / "project", run_root)

    assert [item.product_key for item in plan.items] == ["UV_vis_DRS_Tauc"]


def test_cli_export_origin_style_assets_passes_options(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    run_root = tmp_path / "accepted_run"
    asset_root = project_root / "templates" / "origin_styles"
    captured: dict[str, object] = {}

    def fake_export(project: Path, run: Path, *, asset_root: Path | None = None, with_origin: bool = False) -> dict[str, object]:
        captured["project"] = project
        captured["run_root"] = run
        captured["asset_root"] = asset_root
        captured["with_origin"] = with_origin
        return {
            "asset_root": str(asset_root),
            "manifest": str(asset_root / "manifest.json") if asset_root else "",
            "planned_count": 11,
            "exported_count": 11,
            "failure_count": 0,
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.export_origin_style_assets", fake_export)

    code = main(
        [
            "export-origin-style-assets",
            "--run-root",
            str(run_root),
            "--asset-root",
            str(asset_root),
            "--with-origin",
        ]
    )

    assert code == 0
    assert captured == {
        "project": project_root,
        "run_root": run_root,
        "asset_root": asset_root,
        "with_origin": True,
    }
