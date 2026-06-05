from __future__ import annotations

from pathlib import Path

from src.cli import main
from src.core.v3_real_template_rebuild import build_v3_template_candidate_pool
from src.core.v4_strict_template_conformance import (
    V4_STRICT_COMMAND,
    V4_STRICT_GLOBAL_STYLE_OVERRIDE,
    V4_STRICT_SCOPE,
    V4StrictTemplateConformanceOptions,
    build_v4_strict_v3_options,
)


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
