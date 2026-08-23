from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cli import main
from src.core.file_utils import file_sha256
from src.core.project import default_output_root
from src.origin.template_format import build_template_format_plan
from src.origin.style_registry import (
    load_origin_style_manifest,
    origin_style_manifest_path,
    resolve_origin_adaptive_style_asset,
    resolve_origin_runtime_style_asset,
    resolve_origin_style_asset,
    validate_origin_style_asset_integrity,
)


def _write_adaptive_style_bundle(
    tmp_path: Path,
    *,
    role: str,
    status: str = "accepted",
) -> tuple[Path, dict[str, object], dict[str, Path], Path]:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    files = {
        "format_theme": style_root / "format_themes" / "FTIR.oth",
        "graph_template": style_root / "graph_templates" / "FTIR.otpu",
        "style_snapshot": style_root / "snapshots" / "FTIR.json",
        "data_snapshot": style_root / "data_snapshots" / "FTIR.json",
    }
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    files["format_theme"].write_bytes(b"adaptive-oth")
    files["graph_template"].write_bytes(b"verified-primary-otpu")
    files["style_snapshot"].write_text(
        '{"layer_count":1,"plot_count":3}',
        encoding="utf-8",
    )
    files["data_snapshot"].write_text(
        '{"schema_version":1,"plot_count":3,"plots":[]}',
        encoding="utf-8",
    )
    relative_paths = {
        field: str(path.relative_to(style_root)).replace("\\", "/")
        for field, path in files.items()
    }
    entry: dict[str, object] = {
        "product_key": "FTIR",
        "data_type": "FTIR",
        "status": status,
        "graph_page": "Graph3",
        "asset_kind": "otpu",
        "sha256": file_sha256(files["graph_template"]),
        "file_size_bytes": files["graph_template"].stat().st_size,
        "expected_layer_count": 1,
        "expected_plot_count": 3,
        "harvested_at": "2026-08-22T00:00:00",
        "source_mode": "test",
        "format_theme_role": role,
        **relative_paths,
        "file_integrity": {
            field: {
                "path": relative_paths[field],
                "kind": path.suffix.lstrip("."),
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for field, path in files.items()
        },
    }
    manifest = style_root / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )
    return project, entry, files, manifest


def test_origin_format_theme_assets_do_not_embed_workspace_or_assistant_markers() -> None:
    project_root = Path(__file__).resolve().parents[1]
    theme_root = project_root / "templates" / "origin_styles" / "format_themes"
    assets = sorted(theme_root.glob("*.oth"))
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


@pytest.mark.parametrize(
    "role",
    ["adaptive_runtime", "legacy_compatibility_runtime"],
)
def test_adaptive_style_resolver_accepts_complete_runtime_bundle(
    tmp_path: Path,
    role: str,
) -> None:
    project, entry, files, _manifest = _write_adaptive_style_bundle(
        tmp_path,
        role=role,
    )

    resolved = resolve_origin_adaptive_style_asset(project, "FTIR")

    assert resolved is not None
    assert resolved.runtime_asset_kind == "oth_json"
    assert resolved.runtime_asset_path == files["format_theme"]
    assert resolved.runtime_asset_sha256 == file_sha256(files["format_theme"])
    assert resolved.runtime_asset_sha256 != entry["sha256"]
    assert resolved.format_theme_path == files["format_theme"]
    assert resolved.style_snapshot_path == files["style_snapshot"]
    assert resolved.data_snapshot_path == files["data_snapshot"]
    assert resolved.graph_template_path == files["graph_template"]
    assert resolved.format_theme_role == role
    assert resolved.expected_plot_count == 3


@pytest.mark.parametrize(
    "role",
    [
        "adaptive_runtime_candidate",
        "legacy_compatibility_nonruntime",
        "quarantined_nonruntime",
    ],
)
def test_adaptive_style_resolver_exposes_candidate_only_when_explicitly_allowed(
    tmp_path: Path,
    role: str,
) -> None:
    project, _entry, _files, _manifest = _write_adaptive_style_bundle(
        tmp_path,
        role=role,
    )

    assert resolve_origin_adaptive_style_asset(project, "FTIR") is None
    candidate = resolve_origin_adaptive_style_asset(
        project,
        "FTIR",
        allow_candidate=True,
    )
    assert candidate is not None
    assert candidate.format_theme_role == role
    assert candidate.runtime_asset_kind == "oth_json"


@pytest.mark.parametrize(
    ("field", "mutation"),
    [
        ("format_theme", "missing"),
        ("style_snapshot", "missing"),
        ("data_snapshot", "missing"),
        ("format_theme", "tampered"),
        ("style_snapshot", "tampered"),
        ("data_snapshot", "tampered"),
    ],
)
def test_adaptive_style_resolver_fails_closed_for_missing_or_tampered_bundle_file(
    tmp_path: Path,
    field: str,
    mutation: str,
) -> None:
    project, _entry, files, _manifest = _write_adaptive_style_bundle(
        tmp_path,
        role="adaptive_runtime",
    )
    target = files[field]
    if mutation == "missing":
        target.unlink()
    else:
        target.write_bytes(target.read_bytes() + b"-tampered")

    assert resolve_origin_adaptive_style_asset(project, "FTIR") is None


def test_adaptive_style_resolver_requires_accepted_main_entry(tmp_path: Path) -> None:
    project, _entry, _files, _manifest = _write_adaptive_style_bundle(
        tmp_path,
        role="adaptive_runtime_candidate",
        status="quarantined_unvalidated",
    )

    assert (
        resolve_origin_adaptive_style_asset(
            project,
            "FTIR",
            allow_candidate=True,
        )
        is None
    )


def test_origin_style_manifest_v1_remains_compatible(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
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

    result = validate_origin_style_asset_integrity(project, required_product_keys=("BET",))

    assert result["ok"] is True
    assert result["schema_version"] == 1
    assert any("no mandatory per-file hash" in warning for warning in result["warnings"])


def test_origin_style_manifest_v2_detects_asset_tampering(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    snapshot = style_root / "snapshots" / "BET.json"
    data_snapshot = style_root / "data_snapshots" / "BET.json"
    for path in (theme, snapshot, data_snapshot):
        path.parent.mkdir(parents=True, exist_ok=True)
    theme.write_bytes(b"accepted-theme")
    snapshot.write_text('{"layer_count":1,"plot_count":2}', encoding="utf-8")
    data_snapshot.write_text('{"layers":[{"layer_index":1}],"plots":[{"y_dataset":"B","y_values":[1]}]}', encoding="utf-8")
    files = {
        "format_theme": theme,
        "style_snapshot": snapshot,
        "data_snapshot": data_snapshot,
    }
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "status": "accepted",
                        "graph_page": "Graph1",
                        "format_theme": "format_themes/BET.oth",
                        "style_snapshot": "snapshots/BET.json",
                        "data_snapshot": "data_snapshots/BET.json",
                        "asset_kind": "oth",
                        "sha256": file_sha256(theme),
                        "file_size_bytes": theme.stat().st_size,
                        "expected_layer_count": 1,
                        "expected_plot_count": 2,
                        "harvested_at": "2026-07-11T12:00:00",
                        "source_mode": "test",
                        "file_integrity": {
                            field: {
                                "kind": path.suffix.lstrip("."),
                                "sha256": file_sha256(path),
                                "size_bytes": path.stat().st_size,
                            }
                            for field, path in files.items()
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    valid = validate_origin_style_asset_integrity(project, required_product_keys=("BET",))
    theme.write_bytes(b"tampered-theme")
    tampered = validate_origin_style_asset_integrity(project, required_product_keys=("BET",))

    assert valid["ok"] is True
    assert tampered["ok"] is False
    assert any("sha256 mismatch" in failure for failure in tampered["failures"])


def test_origin_style_manifest_rejects_unsupported_schema(tmp_path: Path) -> None:
    project = tmp_path / "project"
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":99,"assets":[]}', encoding="utf-8")

    try:
        load_origin_style_manifest(project)
    except ValueError as exc:
        assert "Unsupported Origin style manifest schema_version 99" in str(exc)
    else:
        raise AssertionError("unsupported schema should fail")


def test_origin_style_manifest_relative_override_is_project_relative(tmp_path: Path) -> None:
    project = tmp_path / "project"
    manifest = project / "config" / "style-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":1,"assets":[]}', encoding="utf-8")

    loaded = load_origin_style_manifest(project, Path("config/style-manifest.json"))

    assert origin_style_manifest_path(project, Path("config/style-manifest.json")) == manifest
    assert loaded["assets"] == []


def test_origin_style_resolver_rejects_assets_outside_manifest_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    outside_theme = tmp_path / "outside.oth"
    outside_theme.write_bytes(b"external")
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "graph_page": "Graph1",
                        "format_theme": str(outside_theme),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert resolve_origin_style_asset(project, "BET") is None


def test_origin_style_registry_keeps_otpu_harvest_record_out_of_runtime(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    graph_template = style_root / "graph_templates" / "BET.otpu"
    graph_template.parent.mkdir(parents=True)
    graph_template.write_bytes(b"unreviewed-graph-template")
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "graph_page": "Graph1",
                        "graph_template": "graph_templates/BET.otpu",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    integrity = validate_origin_style_asset_integrity(project, required_product_keys=("BET",))

    assert resolve_origin_style_asset(project, "BET") is None
    assert integrity["ok"] is False
    assert any(
        "graph_template is harvest-only" in failure
        for failure in integrity["failures"]
    )


def test_origin_style_manifest_v2_reports_malformed_snapshot_counts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    snapshot = style_root / "snapshots" / "BET.json"
    theme.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    theme.write_bytes(b"theme")
    snapshot.write_text('{"layer_count":"invalid","plot_count":1}', encoding="utf-8")
    (style_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "assets": [
                    {
                        "product_key": "BET",
                        "graph_page": "Graph1",
                        "format_theme": "format_themes/BET.oth",
                        "style_snapshot": "snapshots/BET.json",
                        "asset_kind": "oth",
                        "sha256": file_sha256(theme),
                        "file_size_bytes": theme.stat().st_size,
                        "expected_layer_count": 1,
                        "expected_plot_count": 1,
                        "harvested_at": "2026-07-11T12:00:00",
                        "source_mode": "test",
                        "file_integrity": {
                            "format_theme": {"kind": "oth", "sha256": file_sha256(theme), "size_bytes": theme.stat().st_size},
                            "style_snapshot": {"kind": "json", "sha256": file_sha256(snapshot), "size_bytes": snapshot.stat().st_size},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = validate_origin_style_asset_integrity(project, required_product_keys=("BET",))

    assert result["ok"] is False
    assert any("not an integer" in failure for failure in result["failures"])


def test_origin_style_manifest_resolves_project_local_format_theme(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset = project / "templates" / "origin_styles" / "format_themes" / "BET.oth"
    harvest_template = project / "templates" / "origin_styles" / "graph_templates" / "BET.otpu"
    snapshot = project / "templates" / "origin_styles" / "snapshots" / "BET.json"
    data_snapshot = project / "templates" / "origin_styles" / "data_snapshots" / "BET.json"
    template_opju = project / "templates" / "origin_styles" / "reference_opju" / "BET.opju"
    asset.parent.mkdir(parents=True)
    harvest_template.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    data_snapshot.parent.mkdir(parents=True)
    template_opju.parent.mkdir(parents=True)
    asset.write_bytes(b"oth")
    harvest_template.write_bytes(b"otpu")
    snapshot.write_text("{}", encoding="utf-8")
    data_snapshot.write_text("{}", encoding="utf-8")
    template_opju.write_bytes(b"opju")
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "format_theme": "format_themes/BET.oth",
                        "graph_template": "graph_templates/BET.otpu",
                        "style_snapshot": "snapshots/BET.json",
                        "data_snapshot": "data_snapshots/BET.json",
                        "template_opju": "reference_opju/BET.opju",
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
    assert resolved.format_theme_path == asset
    assert resolved.format_theme_path.is_file()
    assert resolved.graph_template_path == harvest_template
    assert resolved.style_snapshot_path == snapshot
    assert resolved.data_snapshot_path == data_snapshot
    assert resolved.template_opju_path == template_opju


def test_schema_v2_runtime_asset_requires_independent_fresh_project_replay(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    manifest = style_root / "manifest.json"
    entry = {
        "product_key": "BET",
        "data_type": "BET",
        "format_theme": "format_themes/BET.oth",
        "asset_kind": "oth",
        "sha256": file_sha256(theme),
        "file_integrity": {
            "format_theme": {
                "kind": "oth",
                "sha256": file_sha256(theme),
                "size_bytes": theme.stat().st_size,
            }
        },
        "status": "accepted",
    }
    manifest.write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )

    from src.origin.style_registry import (
        resolve_origin_runtime_style_asset,
        resolve_origin_style_asset,
    )

    assert resolve_origin_style_asset(project, "BET") is not None
    assert resolve_origin_runtime_style_asset(project, "BET") is not None
    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is None
    assert resolve_origin_runtime_style_asset(project, "BET") is not None

    entry["runtime_validation"] = {
        "status": "accepted",
        "asset_kind": "oth",
        "asset_path": "format_themes/BET.oth",
        "asset_sha256": file_sha256(theme),
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
    }
    manifest.write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )

    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is not None

    entry["status"] = "quarantined_unvalidated"
    manifest.write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )
    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is None
    assert resolve_origin_runtime_style_asset(project, "BET") is None


def test_runtime_validated_bet_otpu_is_bound_to_exact_asset_not_legacy_oth(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    verified = style_root / "graph_templates" / "BET_verified.otpu"
    legacy = style_root / "graph_templates" / "BET.otpu"
    reference = style_root / "reference_opju" / "BET.opju"
    snapshot = style_root / "snapshots" / "BET.json"
    binding = style_root / "binding_contracts" / "BET.json"
    evidence = style_root / "validation_evidence" / "BET.json"
    for path in (theme, verified, legacy, reference, snapshot, binding, evidence):
        path.parent.mkdir(parents=True, exist_ok=True)
    theme.write_bytes(b"legacy-theme")
    verified.write_bytes(b"verified-template")
    legacy.write_bytes(b"bad-historical-template")
    reference.write_bytes(b"reviewed-reference")
    snapshot.write_text('{"status":"extracted"}', encoding="utf-8")
    binding.write_text("{}", encoding="utf-8")
    evidence.write_text("{}", encoding="utf-8")
    entry = {
        "product_key": "BET",
        "data_type": "BET",
        "status": "accepted",
        "graph_page": "Graph5",
        "asset_kind": "otpu",
        "sha256": file_sha256(verified),
        "format_theme": "format_themes/BET.oth",
        "graph_template": "graph_templates/BET_verified.otpu",
        "style_snapshot": "snapshots/BET.json",
        "template_opju": "reference_opju/BET.opju",
        "binding_contract": "binding_contracts/BET.json",
        "runtime_validation_evidence": "validation_evidence/BET.json",
        "source_opju_hash": file_sha256(reference),
        "file_integrity": {
            "format_theme": {
                "kind": "oth",
                "sha256": file_sha256(theme),
                "size_bytes": theme.stat().st_size,
            },
            "graph_template": {
                "kind": "otpu",
                "sha256": file_sha256(verified),
                "size_bytes": verified.stat().st_size,
            },
            "template_opju": {
                "kind": "opju",
                "sha256": file_sha256(reference),
                "size_bytes": reference.stat().st_size,
            },
            "style_snapshot": {
                "kind": "json",
                "sha256": file_sha256(snapshot),
                "size_bytes": snapshot.stat().st_size,
            },
            "binding_contract": {
                "kind": "json",
                "sha256": file_sha256(binding),
                "size_bytes": binding.stat().st_size,
            },
            "runtime_validation_evidence": {
                "kind": "json",
                "sha256": file_sha256(evidence),
                "size_bytes": evidence.stat().st_size,
            },
        },
        "runtime_validation": {
            "status": "accepted",
            "asset_kind": "otpu",
            "asset_path": "graph_templates/BET_verified.otpu",
            "asset_sha256": file_sha256(verified),
            "reference_opju_sha256": file_sha256(reference),
            "binding_contract_sha256": file_sha256(binding),
            "evidence_sha256": file_sha256(evidence),
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
            "axis_title_hard_gate": True,
            "exact_pixel_match": True,
            "same_size": True,
            "changed_pixels": 0,
            "rms": 0,
            "reference_opju_self_replay": False,
        },
    }
    (style_root / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )

    resolved = resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    )

    assert resolved is not None
    assert resolved.runtime_asset_kind == "otpu"
    assert resolved.runtime_asset_path == verified
    assert resolved.format_theme_path == theme
    assert resolved.runtime_asset_path != legacy
    runtime_resolved = resolve_origin_runtime_style_asset(project, "BET")
    assert runtime_resolved is not None
    assert runtime_resolved.runtime_asset_kind == "otpu"
    assert runtime_resolved.runtime_asset_path == verified

    entry["runtime_validation"]["supporting_format_theme_sha256"] = file_sha256(theme)
    (style_root / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )
    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is not None
    theme.write_bytes(b"tampered-theme")
    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is None
    theme.write_bytes(b"legacy-theme")

    reference.unlink()
    resolved_without_reference = resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    )
    assert resolved_without_reference is not None
    assert resolved_without_reference.template_opju_path is None

    entry["runtime_validation"]["asset_path"] = "format_themes/BET.oth"
    (style_root / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )
    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is None


def test_project_eis_otpu_is_enabled_by_validation_evidence_not_product_allowlist() -> None:
    project = Path(__file__).resolve().parents[1]

    resolved = resolve_origin_style_asset(
        project,
        "EIS",
        require_runtime_validation=True,
    )

    assert resolved is not None
    assert resolved.runtime_asset_kind == "otpu"
    assert resolved.runtime_asset_path == (
        project / "templates" / "origin_styles" / "graph_templates" / "EIS.otpu"
    )


def test_project_pl_otpu_requires_accepted_detached_asset_bundle() -> None:
    project = Path(__file__).resolve().parents[1]

    resolved = resolve_origin_style_asset(
        project,
        "PL",
        require_runtime_validation=True,
    )

    assert resolved is not None
    assert resolved.runtime_asset_kind == "otpu"
    assert resolved.runtime_asset_path == (
        project / "templates" / "origin_styles" / "graph_templates" / "PL.otpu"
    )
    assert resolved.format_theme_path == (
        project / "templates" / "origin_styles" / "format_themes" / "PL.oth"
    )
    assert resolved.style_snapshot_path == (
        project / "templates" / "origin_styles" / "snapshots" / "PL.json"
    )
    assert resolved.binding_contract_path == (
        project / "templates" / "origin_styles" / "binding_contracts" / "PL.json"
    )


def test_schema_v1_style_asset_cannot_bypass_runtime_validation_gate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
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
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert resolve_origin_style_asset(project, "BET") is not None
    assert resolve_origin_style_asset(
        project,
        "BET",
        require_runtime_validation=True,
    ) is None


def test_template_plan_uses_project_format_theme_when_opju_is_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset = project / "templates" / "origin_styles" / "format_themes" / "EPR.oth"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"oth")
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "EPR",
                        "data_type": "EPR",
                        "format_theme": "format_themes/EPR.oth",
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
        style_package_path=style_asset.format_theme_path if style_asset else None,
    )

    assert plan.status == "ready"
    assert plan.mode == "saved_format_theme"
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
    preview = run_root / "BET" / "figures_preview" / "BET.png"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"png")
    bet_meta.write_text(
        json.dumps(
            {
                "product_key": "BET",
                "data_type": "BET",
                "status": "accepted",
                "template_graph": "Graph3",
                "origin_file": "external/BET.opju",
                "preview_png": "external/BET.png",
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import build_origin_style_asset_export_plan

    plan = build_origin_style_asset_export_plan(tmp_path / "project", run_root)

    assert [item.product_key for item in plan.items] == ["BET"]
    assert plan.items[0].origin_file == bet_opju
    assert plan.items[0].format_theme_path.name == "BET.oth"
    assert plan.items[0].graph_template_path is not None
    assert plan.items[0].graph_template_path.name == "BET.otpu"
    assert plan.items[0].style_snapshot_path is not None
    assert plan.items[0].style_snapshot_path.name == "BET.json"


def test_style_asset_export_plan_can_harvest_single_template_opju(tmp_path: Path) -> None:
    project = tmp_path / "project"
    template = tmp_path / "reference.opju"
    template.write_bytes(b"opju")

    from src.core.origin_style_assets import build_origin_style_asset_export_plan

    plan = build_origin_style_asset_export_plan(
        project,
        None,
        template_opju=template,
        product_key="XRD",
        data_type="XRD",
        graph_page="Graph4",
    )

    assert [item.product_key for item in plan.items] == ["XRD"]
    assert plan.items[0].origin_file == template
    assert plan.items[0].graph_page == "Graph4"
    assert plan.items[0].source_mode == "direct_template_opju"
    assert plan.items[0].format_theme_path == project / "templates" / "origin_styles" / "format_themes" / "XRD.oth"
    assert plan.items[0].graph_template_path == project / "templates" / "origin_styles" / "graph_templates" / "XRD.otpu"
    assert plan.items[0].style_snapshot_path == project / "templates" / "origin_styles" / "snapshots" / "XRD.json"
    assert plan.items[0].data_snapshot_path == project / "templates" / "origin_styles" / "data_snapshots" / "XRD.json"
    assert plan.items[0].template_opju_path == project / "templates" / "origin_styles" / "reference_opju" / "XRD.opju"


def test_style_asset_export_plan_can_harvest_template_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    template = tmp_path / "bet.opju"
    template.write_bytes(b"opju")
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "source_opju": str(template),
                        "graph_page": "Graph5",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import build_origin_style_asset_export_plan

    plan = build_origin_style_asset_export_plan(project, None, template_plan=plan_json)

    assert [item.product_key for item in plan.items] == ["BET"]
    assert plan.items[0].origin_file == template
    assert plan.items[0].graph_page == "Graph5"
    assert plan.items[0].format_theme_path == project / "templates" / "origin_styles" / "format_themes" / "BET.oth"
    assert plan.items[0].data_snapshot_path == project / "templates" / "origin_styles" / "data_snapshots" / "BET.json"
    assert plan.items[0].source_mode == "direct_template_opju"


def test_template_plan_can_use_style_source_product_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    template = tmp_path / "xps_non.opju"
    template.write_bytes(b"opju")
    theme = project / "templates" / "origin_styles" / "format_themes" / "XPS_in_situ.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    manifest = project / "templates" / "origin_styles" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "XPS_in_situ",
                        "data_type": "XPS",
                        "format_theme": "format_themes/XPS_in_situ.oth",
                        "status": "accepted",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "product_key": "XPS_non_in_situ",
                        "data_type": "XPS",
                        "source_opju": str(template),
                        "graph_page": "Bi_4f",
                        "style_source_product_key": "XPS_in_situ",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import build_origin_style_asset_export_plan, build_origin_style_asset_replay_plan

    export_plan = build_origin_style_asset_export_plan(project, None, template_plan=plan_json)
    replay_plan = build_origin_style_asset_replay_plan(project, plan_json, tmp_path / "out")

    assert export_plan.items[0].style_source_product_key == "XPS_in_situ"
    assert export_plan.items[0].style_source_theme_path == theme
    assert replay_plan.items[0].style_source_product_key == "XPS_in_situ"
    assert replay_plan.items[0].style_source_theme_path == theme


def test_replay_plan_parses_explicit_fresh_project_graph_template_mode(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    source = project / "templates" / "origin_styles" / "reference_opju" / "BET.opju"
    template = tmp_path / "candidate.otpu"
    format_theme = tmp_path / "candidate.oth"
    style_snapshot = tmp_path / "candidate_style.json"
    binding_contract = project / "templates" / "origin_styles" / "binding_contracts" / "BET.json"
    source.parent.mkdir(parents=True)
    binding_contract.parent.mkdir(parents=True)
    source.write_bytes(b"opju")
    template.write_bytes(b"otpu")
    format_theme.write_bytes(b"oth")
    style_snapshot.write_text('{"layout_values":{"page.width":6400}}', encoding="utf-8")
    binding_contract.write_text("{}", encoding="utf-8")
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "product_key": "BET",
                        "data_type": "BET",
                        "source_opju": str(source),
                        "graph_page": "Graph5",
                        "comparison_mode": "fresh_project_graph_template_same_data",
                        "graph_template": str(template),
                        "style_source_theme": str(format_theme),
                        "style_snapshot": str(style_snapshot),
                        "binding_contract": "templates/origin_styles/binding_contracts/BET.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import build_origin_style_asset_replay_plan

    plan = build_origin_style_asset_replay_plan(project, plan_json, tmp_path / "out")

    assert plan.items[0].comparison_mode == "fresh_project_graph_template_same_data"
    assert plan.items[0].graph_template_path == template
    assert plan.items[0].style_source_theme_path == format_theme
    assert plan.items[0].style_snapshot_path == style_snapshot
    assert plan.items[0].binding_contract_path == binding_contract


def test_style_asset_manifest_merge_preserves_other_assets_and_existing_previews(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {"product_key": "BET", "format_theme": "format_themes/BET.oth"},
                    {
                        "product_key": "XRD",
                        "format_theme": "format_themes/old_XRD.oth",
                        "preview_png": "previews/XRD_preview.png",
                        "preview_rms": 48.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import _merge_origin_style_manifest_entries

    merged = _merge_origin_style_manifest_entries(
        manifest,
        [
            {
                "product_key": "XRD",
                "format_theme": "format_themes/XRD.oth",
                "graph_template": "graph_templates/XRD.otpu",
                "style_snapshot": "snapshots/XRD.json",
                "data_snapshot": "data_snapshots/XRD.json",
                "template_opju": "reference_opju/XRD.opju",
                "preview_png": "",
                "preview_rms": None,
            }
        ],
    )

    assert [entry["product_key"] for entry in merged] == ["BET", "XRD"]
    xrd = merged[1]
    assert xrd["format_theme"] == "format_themes/XRD.oth"
    assert xrd["graph_template"] == "graph_templates/XRD.otpu"
    assert xrd["style_snapshot"] == "snapshots/XRD.json"
    assert xrd["data_snapshot"] == "data_snapshots/XRD.json"
    assert xrd["template_opju"] == "reference_opju/XRD.opju"
    assert xrd["preview_png"] == "previews/XRD_preview.png"
    assert xrd["preview_rms"] == 48.0


def test_style_asset_manifest_direct_template_harvest_clears_stale_previews(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "product_key": "XRD",
                        "format_theme": "format_themes/old_XRD.oth",
                        "graph_template": "graph_templates/old_XRD.otpu",
                        "preview_png": "previews/old_preview.png",
                        "reference_preview_png": "previews/old_reference.png",
                        "template_preview_comparison_png": "previews/old_comparison.png",
                        "preview_rms": 48.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import _merge_origin_style_manifest_entries

    merged = _merge_origin_style_manifest_entries(
        manifest,
        [
            {
                "product_key": "XRD",
                "source_mode": "direct_template_opju",
                "format_theme": "format_themes/XRD.oth",
                "graph_template": "",
                "preview_png": "",
                "reference_preview_png": "",
                "template_preview_comparison_png": "",
                "preview_rms": None,
            }
        ],
    )

    xrd = merged[0]
    assert xrd["format_theme"] == "format_themes/XRD.oth"
    assert xrd["graph_template"] == ""
    assert xrd["preview_png"] == ""
    assert xrd["reference_preview_png"] == ""
    assert xrd["template_preview_comparison_png"] == ""
    assert xrd["preview_rms"] is None


def test_style_asset_manifest_merge_deduplicates_existing_product_keys(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {"product_key": "BET", "format_theme": "format_themes/old.oth"},
                    {"product_key": "BET", "format_theme": "format_themes/current.oth"},
                ],
            }
        ),
        encoding="utf-8",
    )

    from src.core.origin_style_assets import _merge_origin_style_manifest_entries

    merged = _merge_origin_style_manifest_entries(manifest, [])

    assert merged == [{"product_key": "BET", "format_theme": "format_themes/current.oth"}]


def test_style_asset_manifest_merge_refuses_to_overwrite_malformed_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{malformed", encoding="utf-8")

    from src.core.origin_style_assets import _merge_origin_style_manifest_entries

    with pytest.raises(json.JSONDecodeError):
        _merge_origin_style_manifest_entries(manifest, [{"product_key": "BET"}])


def test_style_asset_export_without_origin_does_not_rewrite_manifest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset_root = project / "templates" / "origin_styles"
    asset_root.mkdir(parents=True)
    manifest = asset_root / "manifest.json"
    original = '{"schema_version":2,"generated_at":"keep","assets":[]}'
    manifest.write_text(original, encoding="utf-8")
    source = tmp_path / "BET.opju"
    source.write_bytes(b"opju")

    from src.core.origin_style_assets import export_origin_style_assets

    result = export_origin_style_assets(
        project,
        template_opju=source,
        product_key="BET",
        data_type="BET",
        graph_page="Graph1",
        with_origin=False,
    )

    assert result["exported_count"] == 0
    assert result["failure_count"] == 1
    assert manifest.read_text(encoding="utf-8") == original


def test_successful_style_asset_export_writes_valid_v2_manifest_and_preserves_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    asset_root = project / "templates" / "origin_styles"
    asset_root.mkdir(parents=True)
    manifest = asset_root / "manifest.json"
    manifest.write_text('{"schema_version":2,"custom_metadata":"keep","assets":[]}', encoding="utf-8")
    source = tmp_path / "BET.opju"
    source.write_bytes(b"source-opju")

    class FakeOriginOperations:
        def new_project(self):
            return SimpleNamespace(ok=True)

        def load_project(self, _path: Path):
            return SimpleNamespace(ok=True, message="")

        def save_project(self, path: Path):
            path.write_bytes(b"saved-opju")
            return SimpleNamespace(ok=True, message="")

        def save_graph_theme(self, _graph_page: str, path: Path):
            path.write_bytes(b"saved-theme")
            return SimpleNamespace(ok=True, message="")

        def save_graph_template(self, _graph_page: str, path: Path):
            path.write_bytes(b"saved-template")
            return SimpleNamespace(ok=True, message="")

        def close(self):
            return SimpleNamespace(ok=True)

    monkeypatch.setattr("src.core.origin_style_assets.connect_origin", lambda **_kwargs: FakeOriginOperations())
    monkeypatch.setattr(
        "src.core.origin_style_assets.read_graph_style_snapshot",
        lambda *_args, **_kwargs: SimpleNamespace(to_dict=lambda: {"layer_count": 1, "plot_count": 2}),
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.read_graph_data_snapshot",
        lambda *_args, **_kwargs: {"schema_version": 2, "layers": [{"layer_index": 1}], "plots": []},
    )

    from src.core.origin_style_assets import export_origin_style_assets

    result = export_origin_style_assets(
        project,
        template_opju=source,
        product_key="BET",
        data_type="BET",
        graph_page="Graph1",
        with_origin=True,
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert result["exported_count"] == 1
    assert result["failure_count"] == 0
    assert payload["schema_version"] == 2
    assert payload["custom_metadata"] == "keep"
    assert payload["assets"][0]["file_integrity"]["format_theme"]["sha256"] == file_sha256(
        asset_root / "format_themes" / "BET.oth"
    )
    assert validate_origin_style_asset_integrity(project, required_product_keys=("BET",))["ok"] is True

    class CloseFailureOriginOperations(FakeOriginOperations):
        def close(self):
            return SimpleNamespace(ok=False, message="Origin still running")

    monkeypatch.setattr(
        "src.core.origin_style_assets.connect_origin",
        lambda **_kwargs: CloseFailureOriginOperations(),
    )
    close_failure = export_origin_style_assets(
        project,
        template_opju=source,
        product_key="BET",
        data_type="BET",
        graph_page="Graph1",
        with_origin=True,
    )
    assert close_failure["exported_count"] == 1
    assert close_failure["failure_count"] == 1
    assert close_failure["failures"][-1]["failure_stage"] == "origin_close"


def test_style_asset_manifest_writer_preserves_existing_schema_and_uses_v2_for_new_manifest(tmp_path: Path) -> None:
    from src.core.origin_style_assets import _origin_style_manifest_schema_version_for_write

    manifest = tmp_path / "manifest.json"
    assert _origin_style_manifest_schema_version_for_write(manifest) == 2
    manifest.write_text('{"schema_version":1,"assets":[]}', encoding="utf-8")
    assert _origin_style_manifest_schema_version_for_write(manifest) == 1
    manifest.write_text('{"schema_version":2,"assets":[]}', encoding="utf-8")
    assert _origin_style_manifest_schema_version_for_write(manifest) == 2


def test_graph_data_snapshot_records_multilayer_xrd_template_data() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def __init__(self) -> None:
            self.variables = {"__rdop_plot_style_value": float("nan")}
            self.layer_names = {
                1: ["Book2_B", "Book2_D", "Book2_F"],
                2: ["Book2_H"],
                3: ["Book3_F"],
            }
            self.columns = {
                "Book2": [
                    [10.0, 11.0],
                    [100.0, 101.0],
                    [20.0, 21.0],
                    [200.0, 201.0],
                    [30.0, 31.0],
                    [300.0, 301.0],
                    [15.287, 18.192],
                    [25.3, 0.2],
                ],
                "Book3": [
                    [1.0],
                    [2.0],
                    [3.0],
                    [4.0],
                    [32.0, 33.0],
                    [500.0, 501.0],
                ],
            }
            self.styles = {
                ("Book2_H", "-c"): 22106449.0,
                ("Book2_H", "-cl"): 22106449.0,
                ("Book2_H", "-wp"): 0.5,
                ("Book3_F", "-c"): 23709421.0,
                ("Book3_F", "-wp"): 3.0,
            }

        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            names = self.layer_names.get(layer_index)
            if names is None:
                return OperationResult(False, "missing layer")
            return OperationResult(True, "ok", {"plot_dataset_names": names})

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"columns": self.columns[book_name]})

        def get_worksheet_column_designations(self, book_name: str, sheet_name: str) -> OperationResult:
            designations = {
                "Book2": ["X", "Y", "X", "Y", "X", "Y", "X", "Y"],
                "Book3": ["N", "N", "N", "N", "X", "Y"],
            }
            return OperationResult(True, "ok", {"column_designations": designations[book_name]})

        def run_labtalk(self, script: str) -> OperationResult:
            stripped = script.strip()
            if stripped == "__rdop_plot_style_value=nan;":
                self.variables["__rdop_plot_style_value"] = float("nan")
                return OperationResult(True, "ok")
            parts = stripped.rstrip(";").split()
            if len(parts) == 4 and parts[0] == "get" and parts[3] == "__rdop_plot_style_value":
                value = self.styles.get((parts[1], parts[2]), float("nan"))
                self.variables["__rdop_plot_style_value"] = value
                return OperationResult(True, "ok")
            return OperationResult(False, "unsupported")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            return OperationResult(True, "ok", {"value": self.variables.get(name)})

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph4", source_label="CWO+BOBC+标卡.opju")

    assert snapshot["plot_count"] == 5
    assert snapshot["layer_count_with_plots"] == 3
    plots = {plot["y_dataset"]: plot for plot in snapshot["plots"]}
    assert plots["Book2_B"]["x_dataset"] == "Book2_A"
    assert plots["Book2_H"]["x_dataset"] == "Book2_G"
    assert plots["Book2_H"]["x_values"] == [15.287, 18.192]
    assert plots["Book2_H"]["y_values"] == [25.3, 0.2]
    assert plots["Book2_H"]["style"]["color"] == 22106449.0
    assert plots["Book2_H"]["style"]["line_width_pt"] == 0.5
    assert plots["Book3_F"]["x_dataset"] == "Book3_E"
    assert plots["Book3_F"]["layer_index"] == 3
    assert plots["Book3_F"]["style"]["color"] == 23709421.0


def test_graph_data_snapshot_preserves_plot_instance_sheet_creation_indices() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(True, "ok", {"plot_dataset_names": ["Book1_G", "Book1_G@2"]})
            return OperationResult(False, "missing")

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            y_values = [50.0, 60.0] if sheet_name in {"1", "Sheet1", ""} else [70.0, 80.0]
            return OperationResult(
                True,
                "ok",
                {
                    "columns": [
                        [0.0],
                        [1.0],
                        [2.0],
                        [3.0],
                        [4.0],
                        [5.0, 6.0],
                        y_values,
                    ]
                },
            )

        def get_worksheet_column_designations(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"column_designations": ["N", "N", "N", "N", "N", "X", "Y"]})

        def run_labtalk(self, script: str) -> OperationResult:
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            return OperationResult(True, "ok", {"value": float("nan")})

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1")
    plots = snapshot["plots"]

    assert [plot["status"] for plot in plots] == ["ready", "ready"]
    assert [plot["y_dataset"] for plot in plots] == ["Book1_G", "Book1_G@2"]
    assert [plot["x_dataset"] for plot in plots] == ["Book1_F", "Book1_F@2"]
    assert [plot["sheet_name"] for plot in plots] == ["1", "2"]
    assert plots[1]["y_values"] == [70.0, 80.0]
    assert plots[0]["xy_data_sha256"] != plots[1]["xy_data_sha256"]


def test_graph_data_snapshot_supports_shared_x_for_multiple_y_columns() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(True, "ok", {"plot_dataset_names": ["Book1_B", "Book1_C"]})
            return OperationResult(False, "missing")

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"columns": [[1.0, 2.0], [10.0, 20.0], [100.0, 200.0]]})

        def get_worksheet_column_designations(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"column_designations": ["X", "Y", "Y"]})

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1")

    assert snapshot["status"] == "ready"
    assert [plot["x_dataset"] for plot in snapshot["plots"]] == ["Book1_A", "Book1_A"]
    assert [plot["x_values"] for plot in snapshot["plots"]] == [[1.0, 2.0], [1.0, 2.0]]


def test_graph_data_snapshot_prefers_explicit_plot_mapping_over_column_designations() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(
                    True,
                    "ok",
                    {
                        "plot_dataset_names": ["Book1_B", "Book1_C"],
                        "plot_x_dataset_names": ["Book1_A", "Book1_A"],
                    },
                )
            return OperationResult(False, "missing")

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"columns": [[1.0, 2.0], [10.0, 20.0], [100.0, 200.0]]})

        def get_worksheet_column_designations(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"column_designations": ["X", "X", "Y"]})

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1")

    assert snapshot["status"] == "ready"
    assert [plot["x_dataset"] for plot in snapshot["plots"]] == ["Book1_A", "Book1_A"]
    assert {plot["x_mapping_source"] for plot in snapshot["plots"]} == {"graph_plot_mapping"}


def test_graph_data_snapshot_prefers_explicit_plot_row_bounds_over_x_name_hint() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def get_graph_plot_dataset_names(
            self,
            _graph_name: str,
            layer_index: int = 1,
        ) -> OperationResult:
            if layer_index != 1:
                return OperationResult(False, "missing")
            return OperationResult(
                True,
                "ok",
                {
                    "plot_dataset_names": ["Book1_B"],
                    "plot_x_dataset_names": ["Book1_A"],
                },
            )

        def get_graph_plot_dataset_mappings(
            self,
            _graph_name: str,
            layer_index: int = 1,
        ) -> OperationResult:
            return OperationResult(
                True,
                "ok",
                {
                    "plot_mappings": [
                        {
                            "plot_index": 1,
                            "x_dataset": "Book1_A",
                            "y_dataset": "Book1_B",
                            "row_from": 1,
                            "row_to": 2,
                        }
                    ]
                },
            )

        def get_worksheet_data(self, _book_name: str, _sheet_name: str) -> OperationResult:
            return OperationResult(
                True,
                "ok",
                {"columns": [[1.0, 2.0, 999.0], [10.0, 20.0, 999.0]]},
            )

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1", max_layers=1)
    [plot] = snapshot["plots"]

    assert plot["plot_row_from"] == 1
    assert plot["plot_row_to"] == 2
    assert plot["plot_row_range_source"] == "graph_plot_mapping"
    assert plot["x_values"] == [1.0, 2.0]
    assert plot["y_values"] == [10.0, 20.0]


def test_graph_data_snapshot_comparison_requires_same_values_and_explicit_mapping() -> None:
    from src.core.origin_style_assets import compare_graph_data_snapshots

    base = {
        "schema_version": 3,
        "status": "ready",
        "plot_count": 1,
        "layer_count_with_plots": 1,
        "plot_values_sha256": "1" * 64,
        "plot_mapping_sha256": "2" * 64,
        "plots": [
            {
                "layer_index": 1,
                "plot_index": 1,
                "x_mapping_source": "graph_plot_mapping",
                "plot_row_range_source": "graph_plot_mapping",
                "plot_row_from": 1,
                "plot_row_to": 2,
                "row_count": 2,
                "x_data_sha256": "3" * 64,
                "y_data_sha256": "4" * 64,
                "xy_data_sha256": "5" * 64,
            }
        ],
    }

    matched = compare_graph_data_snapshots(base, dict(base))
    different_values = compare_graph_data_snapshots(
        base,
        {**base, "plot_values_sha256": "3" * 64},
    )
    inferred_mapping = compare_graph_data_snapshots(
        base,
        {
            **base,
            "plots": [
                {
                    **base["plots"][0],
                    "x_mapping_source": "worksheet_column_designations",
                }
            ],
        },
    )

    assert matched["same_data"] is True
    assert different_values["same_data"] is False
    assert "plotted X/Y values differ" in different_values["reasons"]
    assert inferred_mapping["same_data"] is False
    assert any("lack explicit Origin plotdata" in reason for reason in inferred_mapping["reasons"])


def test_replay_column_merge_accepts_short_prefix_and_longer_range() -> None:
    from src.core.origin_style_assets import _merge_replay_worksheet_column_record

    short = {"row_from": 1, "row_to": 2, "values": [10.0, 20.0]}
    long = {"row_from": 1, "row_to": 4, "values": [10.0, 20.0, 30.0, 40.0]}

    merged = _merge_replay_worksheet_column_record(
        _merge_replay_worksheet_column_record(
            None, short, sheet_index=1, column_index=1
        ),
        long,
        sheet_index=1,
        column_index=1,
    )

    assert merged["row_from"] == 1
    assert merged["row_to"] == 4
    assert merged["values"] == [10.0, 20.0, 30.0, 40.0]


def test_replay_column_merge_accepts_shifted_partial_overlap() -> None:
    from src.core.origin_style_assets import _merge_replay_worksheet_column_record

    first = {"row_from": 2, "row_to": 4, "values": [20.0, 30.0, 40.0]}
    second = {"row_from": 4, "row_to": 6, "values": [40.0, 50.0, 60.0]}

    merged = _merge_replay_worksheet_column_record(
        _merge_replay_worksheet_column_record(
            None, first, sheet_index=1, column_index=2
        ),
        second,
        sheet_index=1,
        column_index=2,
    )

    assert merged["row_from"] == 2
    assert merged["row_to"] == 6
    assert merged["values"] == [20.0, 30.0, 40.0, 50.0, 60.0]


def test_replay_column_merge_allows_masked_rows_added_outside_existing_overlap() -> None:
    from src.core.origin_style_assets import _merge_replay_worksheet_column_record

    existing = _merge_replay_worksheet_column_record(
        None,
        {
            "row_from": 1,
            "row_to": 2,
            "values": [10.0, 20.0],
            "masked_rows": [],
        },
        sheet_index=1,
        column_index=2,
    )
    merged = _merge_replay_worksheet_column_record(
        existing,
        {
            "row_from": 1,
            "row_to": 4,
            "values": [10.0, 20.0, 30.0, 40.0],
            "masked_rows": [3, 4],
        },
        sheet_index=1,
        column_index=2,
    )

    assert merged["values"] == [10.0, 20.0, 30.0, 40.0]
    assert merged["masked_rows"] == [3, 4]


def test_replay_column_merge_keeps_nonadjacent_gap_as_nan() -> None:
    from src.core.origin_style_assets import _merge_replay_worksheet_column_record

    merged = _merge_replay_worksheet_column_record(
        _merge_replay_worksheet_column_record(
            None,
            {"row_from": 1, "row_to": 2, "values": [10.0, 20.0]},
            sheet_index=1,
            column_index=3,
        ),
        {"row_from": 5, "row_to": 6, "values": [50.0, 60.0]},
        sheet_index=1,
        column_index=3,
    )

    assert merged["row_from"] == 1
    assert merged["row_to"] == 6
    assert merged["values"][:2] == [10.0, 20.0]
    assert all(math.isnan(value) for value in merged["values"][2:4])
    assert merged["values"][4:] == [50.0, 60.0]


def test_replay_column_merge_rejects_different_overlapping_values() -> None:
    from src.core.origin_style_assets import _merge_replay_worksheet_column_record

    existing = _merge_replay_worksheet_column_record(
        None,
        {"row_from": 1, "row_to": 3, "values": [10.0, 20.0, 30.0]},
        sheet_index=2,
        column_index=4,
    )

    with pytest.raises(
        RuntimeError,
        match=r"worksheet 2 column 4 at row 3: 30\.0 != 99\.0",
    ):
        _merge_replay_worksheet_column_record(
            existing,
            {"row_from": 3, "row_to": 4, "values": [99.0, 40.0]},
            sheet_index=2,
            column_index=4,
        )


def test_replay_column_merge_treats_overlapping_nans_as_equal() -> None:
    from src.core.origin_style_assets import _merge_replay_worksheet_column_record

    merged = _merge_replay_worksheet_column_record(
        _merge_replay_worksheet_column_record(
            None,
            {"row_from": 1, "row_to": 2, "values": [math.nan, 2.0]},
            sheet_index=1,
            column_index=5,
        ),
        {"row_from": 1, "row_to": 3, "values": [math.nan, 2.0, 3.0]},
        sheet_index=1,
        column_index=5,
    )

    assert math.isnan(merged["values"][0])
    assert merged["values"][1:] == [2.0, 3.0]


def test_graph_data_snapshot_scans_past_empty_middle_layer() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def get_graph_plot_dataset_names(
            self,
            _graph_name: str,
            layer_index: int = 1,
        ) -> OperationResult:
            if layer_index == 1:
                return OperationResult(
                    True,
                    "ok",
                    {
                        "plot_dataset_names": ["Book1_B"],
                        "plot_mappings": [
                            {
                                "plot_index": 1,
                                "x_dataset": "Book1_A",
                                "y_dataset": "Book1_B",
                                "row_from": 1,
                                "row_to": 2,
                            }
                        ],
                    },
                )
            if layer_index == 2:
                return OperationResult(True, "ok", {"plot_dataset_names": []})
            if layer_index == 3:
                return OperationResult(
                    True,
                    "ok",
                    {
                        "plot_dataset_names": ["Book2_B"],
                        "plot_mappings": [
                            {
                                "plot_index": 1,
                                "x_dataset": "Book2_A",
                                "y_dataset": "Book2_B",
                                "row_from": 1,
                                "row_to": 2,
                            }
                        ],
                    },
                )
            return OperationResult(False, "missing")

        def get_worksheet_data(self, book_name: str, _sheet_name: str) -> OperationResult:
            offset = 0.0 if book_name == "Book1" else 100.0
            return OperationResult(
                True,
                "ok",
                {"columns": [[1.0, 2.0], [10.0 + offset, 20.0 + offset]]},
            )

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1", max_layers=4)

    assert snapshot["status"] == "ready"
    assert [item["layer_index"] for item in snapshot["layers"]] == [1, 3]
    assert [(item["layer_index"], item["plot_index"]) for item in snapshot["plots"]] == [
        (1, 1),
        (3, 1),
    ]


def test_graph_data_snapshot_uses_origin_findx_readback_when_designations_are_not_exposed() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def __init__(self) -> None:
            self.x_column = float("nan")

        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(True, "ok", {"plot_dataset_names": ["Book1_C"]})
            return OperationResult(False, "missing")

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"columns": [[1.0, 2.0], [10.0, 20.0], [100.0, 200.0]]})

        def run_labtalk(self, script: str) -> OperationResult:
            if ".findX()" in script:
                self.x_column = 1.0
                return OperationResult(True, "ok")
            return OperationResult(False, "unsupported")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            return OperationResult(True, "ok", {"value": self.x_column})

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1")

    assert snapshot["status"] == "ready"
    assert snapshot["plots"][0]["x_dataset"] == "Book1_A"
    assert snapshot["plots"][0]["x_mapping_source"] == "origin_wks_col_findx"


def test_graph_data_snapshot_fails_when_x_mapping_cannot_be_read_reliably() -> None:
    from src.core.origin_style_assets import read_graph_data_snapshot
    from src.origin.operations import OperationResult

    class FakeOriginOps:
        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(True, "ok", {"plot_dataset_names": ["Book1_C"]})
            return OperationResult(False, "missing")

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"columns": [[1.0], [2.0], [3.0]]})

    snapshot = read_graph_data_snapshot(FakeOriginOps(), "Graph1")

    assert snapshot["status"] == "failed"
    assert snapshot["plots"][0]["status"] == "x_mapping_unavailable"
    assert "x_dataset" not in snapshot["plots"][0]


def test_graph_data_snapshot_normalization_preserves_missing_cells() -> None:
    from src.core.origin_style_assets import _json_safe_value

    assert _json_safe_value(None) is None
    assert _json_safe_value("") is None
    assert _json_safe_value("None") == "None"


def test_style_asset_export_loads_working_copy_not_source_opju(tmp_path: Path, monkeypatch) -> None:
    from src.core import origin_style_assets
    from src.origin.operations import OperationResult

    project = tmp_path / "project"
    source_dir = tmp_path / "manual_save"
    source_dir.mkdir()
    source = source_dir / "CWO+BOBC+标卡.opju"
    source.write_bytes(b"opju")
    loaded_paths: list[Path] = []

    class Snapshot:
        def to_dict(self) -> dict[str, object]:
            return {"graph_page": "Graph4"}

    class FakeOriginOps:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def load_project(self, file_path: Path) -> OperationResult:
            loaded_paths.append(Path(file_path))
            return OperationResult(True, "ok")

        def save_project(self, file_path: Path) -> OperationResult:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).write_bytes(b"opju")
            return OperationResult(True, "ok")

        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(True, "ok", {"plot_dataset_names": ["Book2_B"]})
            return OperationResult(False, "missing layer")

        def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"columns": [[10.0], [100.0]]})

        def get_worksheet_column_designations(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "ok", {"column_designations": ["X", "Y"]})

        def save_graph_theme(self, graph_name: str, file_path: Path) -> OperationResult:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).write_bytes(b"oth")
            return OperationResult(True, "ok")

        def save_graph_template(self, graph_name: str, file_path: Path) -> OperationResult:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).write_bytes(b"otpu")
            return OperationResult(True, "ok")

        def close(self) -> OperationResult:
            return OperationResult(True, "closed")

    monkeypatch.setattr(origin_style_assets, "connect_origin", lambda **_kwargs: FakeOriginOps())
    monkeypatch.setattr(origin_style_assets, "read_graph_style_snapshot", lambda *_args, **_kwargs: Snapshot())

    result = origin_style_assets.export_origin_style_assets(
        project,
        None,
        asset_root=project / "templates" / "origin_styles",
        with_origin=True,
        template_opju=source,
        product_key="XRD",
        data_type="XRD",
        graph_page="Graph4",
    )

    assert result["exported_count"] == 1
    assert loaded_paths
    assert loaded_paths[0] != source
    assert loaded_paths[0].parent != source.parent
    assert loaded_paths[0].name == "XRD.opju"
    data_snapshot = project / "templates" / "origin_styles" / "data_snapshots" / "XRD.json"
    assert json.loads(data_snapshot.read_text(encoding="utf-8"))["plots"][0]["x_dataset"] == "Book2_A"


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

    def fake_export(
        project: Path,
        run: Path | None = None,
        *,
        asset_root: Path | None = None,
        with_origin: bool = False,
        template_plan: Path | None = None,
        template_opju: Path | None = None,
        product_key: str | None = None,
        data_type: str | None = None,
        graph_page: str | None = None,
    ) -> dict[str, object]:
        captured["project"] = project
        captured["run_root"] = run
        captured["asset_root"] = asset_root
        captured["with_origin"] = with_origin
        captured["template_plan"] = template_plan
        captured["template_opju"] = template_opju
        captured["product_key"] = product_key
        captured["data_type"] = data_type
        captured["graph_page"] = graph_page
        return {
            "asset_root": str(asset_root),
            "manifest": str(asset_root / "manifest.json") if asset_root else "",
            "planned_count": 11,
            "exported_count": 11,
            "failure_count": 0,
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.core.origin_style_assets.export_origin_style_assets", fake_export)

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
        "template_plan": None,
        "template_opju": None,
        "product_key": None,
        "data_type": None,
        "graph_page": None,
    }


def test_cli_origin_style_asset_replay_passes_options(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    plan = project_root / "plan.json"
    plan.write_text('{"items":[]}', encoding="utf-8")
    output_dir = default_output_root(project_root) / "runs" / "replay"
    captured: dict[str, object] = {}

    def fake_replay(project: Path, plan_path: Path, out: Path, *, with_origin: bool = False) -> dict[str, object]:
        captured["project"] = project
        captured["plan_path"] = plan_path
        captured["output_dir"] = out
        captured["with_origin"] = with_origin
        return {
            "output_dir": str(out),
            "planned_count": 1,
            "compared_count": 1,
            "failure_count": 0,
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.core.origin_style_assets.run_origin_style_asset_replay", fake_replay)

    code = main(
        [
            "origin-style-asset-replay",
            "--template-plan",
            str(plan),
            "--output-dir",
            str(output_dir),
            "--with-origin",
        ]
    )

    assert code == 0
    assert captured == {
        "project": project_root,
        "plan_path": plan,
        "output_dir": output_dir,
        "with_origin": True,
    }


def test_replay_comparison_writes_side_by_side_without_diff_png(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _compare_replay_pngs

    source = tmp_path / "source.png"
    asset = tmp_path / "asset.png"
    Image.new("RGBA", (2, 2), "white").save(source)
    Image.new("RGBA", (2, 2), "white").save(asset)

    comparison = _compare_replay_pngs(source, asset, tmp_path)

    assert comparison["exact_pixel_match"] is True
    assert "diff_png" not in comparison
    assert (tmp_path / "side_by_side.png").is_file()
    assert not (tmp_path / "diff.png").exists()


def test_replay_comparison_detects_opaque_rgb_change_with_equal_alpha(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _compare_replay_pngs

    source = tmp_path / "source.png"
    asset = tmp_path / "asset.png"
    source_image = Image.new("RGBA", (2, 2), (255, 255, 255, 255))
    asset_image = source_image.copy()
    asset_image.putpixel((1, 0), (0, 255, 255, 255))
    source_image.save(source)
    asset_image.save(asset)

    comparison = _compare_replay_pngs(source, asset, tmp_path)

    assert comparison["same_size"] is True
    assert comparison["exact_pixel_match"] is False
    assert comparison["changed_pixels"] == 1
    assert comparison["diff_bbox"] == [1, 0, 2, 1]
    assert comparison["rms"] > 0.0


def test_replay_same_opju_content_is_determinism_evidence_not_style_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.core.origin_style_assets import (
        OriginStyleAssetReplayItem,
        _replay_compare_one_item,
    )

    project = tmp_path / "project"
    source = project / "source.opju"
    asset = project / "templates" / "origin_styles" / "reference_opju" / "BET.opju"
    source.parent.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    source.write_bytes(b"identical-reference-project")
    asset.write_bytes(source.read_bytes())
    output = tmp_path / "out"

    monkeypatch.setattr(
        "src.core.origin_style_assets.resolve_origin_style_asset",
        lambda *_args, **_kwargs: SimpleNamespace(
            template_opju_path=asset,
            graph_page="Graph1",
        ),
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets._export_replay_graph",
        lambda *_args, **_kwargs: {"ok": True, "png": str(tmp_path / "unused.png")},
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets._compare_replay_pngs",
        lambda *_args, **_kwargs: {"exact_pixel_match": True, "rms": 0.0},
    )

    result = _replay_compare_one_item(
        object(),
        project,
        output,
        OriginStyleAssetReplayItem(
            product_key="BET",
            data_type="BET",
            source_opju=source,
            graph_page="Graph1",
        ),
    )

    assert result["status"] == "reference_opju_self_replay"
    assert result["comparison_scope"] == "deterministic_reference_opju_export"
    assert result["style_asset_validated"] is False
    assert result["same_reference_content"] is True


def test_replay_dispatches_fresh_graph_template_mode_without_resolving_legacy_asset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.core.origin_style_assets import (
        OriginStyleAssetReplayItem,
        _replay_compare_one_item,
    )

    source = tmp_path / "BET.opju"
    template = tmp_path / "BET_verified.otpu"
    source.write_bytes(b"opju")
    template.write_bytes(b"otpu")
    captured: dict[str, object] = {}

    def fake_fresh(_operations, project_root, product_dir, item):
        captured.update(
            {
                "project_root": project_root,
                "product_dir": product_dir,
                "item": item,
            }
        )
        return {"status": "fresh_project_same_data_match"}

    monkeypatch.setattr(
        "src.core.origin_style_assets._replay_fresh_graph_template_same_data",
        fake_fresh,
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.resolve_origin_style_asset",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy asset resolver must not run")
        ),
    )

    item = OriginStyleAssetReplayItem(
        product_key="BET",
        data_type="BET",
        source_opju=source,
        graph_page="Graph5",
        comparison_mode="fresh_project_graph_template_same_data",
        graph_template_path=template,
    )
    result = _replay_compare_one_item(object(), tmp_path, tmp_path / "out", item)

    assert result["status"] == "fresh_project_same_data_match"
    assert captured["item"] is item


def test_fresh_template_axis_title_gate_ignores_only_outer_whitespace() -> None:
    from src.core.origin_style_assets import (
        _fresh_template_axis_title_gate,
        _fresh_template_reference_axis_titles_bold,
    )

    reference = SimpleNamespace(
        audit_string_values={
            "xb.text$": "\\b(X title)\r\n",
            "yl.text$": "\\b(Y title)",
        },
        layout_values={"xb.fsize": 36.0, "yl.fsize": 36.0},
        audit_numeric_values={
            "layer.x.label.bold": 1.0,
            "layer.y.label.bold": 1.0,
        },
    )
    candidate = SimpleNamespace(
        audit_string_values={
            "xb.text$": "\\b(X title)",
            "yl.text$": "\\b(Y title)",
        },
        layout_values={"xb.fsize": 36.0, "yl.fsize": 36.0},
        audit_numeric_values={
            "layer.x.label.bold": 1.0,
            "layer.y.label.bold": 1.0,
        },
    )

    assert _fresh_template_axis_title_gate(reference, candidate)["pass"] is True
    assert _fresh_template_reference_axis_titles_bold(reference) is True
    candidate.audit_string_values["xb.text$"] = "\\b(X changed)"
    assert _fresh_template_axis_title_gate(reference, candidate)["pass"] is False


def test_fresh_template_axis_title_gate_accepts_nonbold_dynamic_title_expansion() -> None:
    from src.core.origin_style_assets import (
        _fresh_template_axis_title_gate,
        _fresh_template_reference_axis_titles_bold,
    )

    reference = SimpleNamespace(
        audit_string_values={"xb.text$": "%(?X)", "yl.text$": "%(?Y)"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )
    candidate = SimpleNamespace(
        audit_string_values={"xb.text$": "A", "yl.text$": "B"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )

    assert _fresh_template_reference_axis_titles_bold(reference) is False
    assert _fresh_template_axis_title_gate(reference, candidate)["pass"] is True


def test_fresh_template_axis_title_gate_rejects_empty_dynamic_title_expansion() -> None:
    from src.core.origin_style_assets import _fresh_template_axis_title_gate

    reference = SimpleNamespace(
        audit_string_values={"xb.text$": "%(?X)", "yl.text$": "%(?Y)"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )
    candidate = SimpleNamespace(
        audit_string_values={"xb.text$": "", "yl.text$": "B"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )

    assert _fresh_template_axis_title_gate(reference, candidate)["pass"] is False


def test_fresh_template_axis_title_gate_rejects_candidate_added_bold() -> None:
    from src.core.origin_style_assets import _fresh_template_axis_title_gate

    reference = SimpleNamespace(
        audit_string_values={"xb.text$": "%(?X)", "yl.text$": "%(?Y)"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )
    candidate = SimpleNamespace(
        audit_string_values={"xb.text$": "\\b(A)", "yl.text$": "B"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )

    gate = _fresh_template_axis_title_gate(reference, candidate)
    assert gate["x_title_rich_text_bold_matches"] is False
    assert gate["pass"] is False


def test_fresh_template_axis_title_gate_rejects_static_text_change() -> None:
    from src.core.origin_style_assets import _fresh_template_axis_title_gate

    reference = SimpleNamespace(
        audit_string_values={"xb.text$": "Wavelength", "yl.text$": "Intensity"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )
    candidate = SimpleNamespace(
        audit_string_values={"xb.text$": "Wavelength", "yl.text$": "Counts"},
        layout_values={"xb.fsize": 24.0, "yl.fsize": 24.0, "xb.bold": 0.0, "yl.bold": 0.0},
        audit_numeric_values={"layer.x.label.bold": 0.0, "layer.y.label.bold": 0.0},
    )

    gate = _fresh_template_axis_title_gate(reference, candidate)
    assert gate["y_text_matches"] is False
    assert gate["pass"] is False


def test_replay_summary_excludes_self_replay_from_compared_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.core.origin_style_assets import (
        OriginStyleAssetReplayItem,
        OriginStyleAssetReplayPlan,
        run_origin_style_asset_replay,
    )

    item = OriginStyleAssetReplayItem(
        product_key="BET",
        data_type="BET",
        source_opju=tmp_path / "BET.opju",
        graph_page="Graph1",
    )
    plan = OriginStyleAssetReplayPlan(
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        items=[item],
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.build_origin_style_asset_replay_plan",
        lambda *_args, **_kwargs: plan,
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets._replay_compare_one_item",
        lambda *_args, **_kwargs: {"status": "reference_opju_self_replay"},
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.connect_origin",
        lambda **_kwargs: SimpleNamespace(close=lambda: SimpleNamespace(ok=True)),
    )

    result = run_origin_style_asset_replay(
        tmp_path,
        tmp_path / "plan.json",
        plan.output_dir,
        with_origin=True,
    )

    assert result["planned_count"] == 1
    assert result["compared_count"] == 0
    assert result["self_replay_count"] == 1
    assert result["inconclusive_count"] == 1
    assert result["failure_count"] == 0
    assert result["origin_close_ok"] is True


def test_replay_summary_counts_fresh_same_data_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.core.origin_style_assets import (
        OriginStyleAssetReplayItem,
        OriginStyleAssetReplayPlan,
        run_origin_style_asset_replay,
    )

    item = OriginStyleAssetReplayItem(
        product_key="BET",
        data_type="BET",
        source_opju=tmp_path / "BET.opju",
        graph_page="Graph5",
        comparison_mode="fresh_project_graph_template_same_data",
        graph_template_path=tmp_path / "BET.otpu",
    )
    plan = OriginStyleAssetReplayPlan(
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        items=[item],
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.build_origin_style_asset_replay_plan",
        lambda *_args, **_kwargs: plan,
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets._replay_compare_one_item",
        lambda *_args, **_kwargs: {"status": "fresh_project_same_data_match"},
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.connect_origin",
        lambda **_kwargs: SimpleNamespace(close=lambda: SimpleNamespace(ok=True)),
    )

    result = run_origin_style_asset_replay(
        tmp_path,
        tmp_path / "plan.json",
        plan.output_dir,
        with_origin=True,
    )

    assert result["compared_count"] == 1
    assert result["failure_count"] == 0


def test_replay_summary_fails_when_origin_close_is_not_confirmed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.core.origin_style_assets import (
        OriginStyleAssetReplayItem,
        OriginStyleAssetReplayPlan,
        run_origin_style_asset_replay,
    )

    item = OriginStyleAssetReplayItem(
        product_key="BET",
        data_type="BET",
        source_opju=tmp_path / "BET.opju",
        graph_page="Graph1",
    )
    plan = OriginStyleAssetReplayPlan(
        project_root=tmp_path,
        output_dir=tmp_path / "out",
        items=[item],
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.build_origin_style_asset_replay_plan",
        lambda *_args, **_kwargs: plan,
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets._replay_compare_one_item",
        lambda *_args, **_kwargs: {"status": "matched"},
    )
    monkeypatch.setattr(
        "src.core.origin_style_assets.connect_origin",
        lambda **_kwargs: SimpleNamespace(
            close=lambda: SimpleNamespace(ok=False, message="Origin still running")
        ),
    )

    result = run_origin_style_asset_replay(
        tmp_path,
        tmp_path / "plan.json",
        plan.output_dir,
        with_origin=True,
    )

    assert result["compared_count"] == 1
    assert result["failure_count"] == 1
    assert result["item_failure_count"] == 0
    assert result["lifecycle_failure_count"] == 1
    assert result["origin_close_ok"] is False
    assert result["origin_close_message"] == "Origin still running"


def test_export_replay_graph_copies_opju_into_product_dir(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _export_replay_graph
    from src.origin.operations import OperationResult

    source_opju = tmp_path / "asset.opju"
    source_opju.write_bytes(b"origin-project")
    product_dir = tmp_path / "products" / "BET"
    product_dir.mkdir(parents=True)
    calls: list[str] = []

    class FakeOriginOps:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def load_project(self, file_path: Path) -> OperationResult:
            assert file_path.name == "project_asset.opju"
            return OperationResult(True, "ok")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "ok", {"pages": [{"name": "Graph5", "type": "graph"}]})

        def run_labtalk(self, script: str) -> OperationResult:
            calls.append(f"labtalk:{script}")
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            assert name in {"page.width", "page.height"}
            calls.append(f"read:{name}")
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            calls.append("reset_identity")
            return OperationResult(True, "ok")

        def export_graph(
            self,
            graph_name: str,
            file_path: Path,
            fmt: str,
            dpi: int = 600,
            pixel_width: int | None = None,
        ) -> OperationResult:
            assert graph_name == "Graph5"
            assert dpi == 600
            calls.append(f"export:{fmt}")
            if fmt == "tif":
                assert pixel_width == 60
                Image.new("RGB", (60, 60), "white").save(file_path, format="TIFF", dpi=(600, 600))
            else:
                Image.new("RGB", (2, 2), "white").save(file_path, format="PNG")
            return OperationResult(True, "ok")

    result = _export_replay_graph(FakeOriginOps(), source_opju, "Graph5", product_dir, "project_asset")

    exported_opju = product_dir / "BET.opju"
    assert result["ok"] is True
    assert result["opju"] == str(exported_opju)
    assert result["opju_size"] == len(b"origin-project")
    assert exported_opju.read_bytes() == b"origin-project"
    assert result["tif_resolution_evidence"]["expected_width_px"] == 60
    assert result["tif_resolution_evidence"]["width_px"] == 60
    assert calls == [
        "export:png",
        'labtalk:win -a "Graph5";',
        "read:page.width",
        "read:page.height",
        "reset_identity",
        'labtalk:win -a "Graph5";',
        "export:tif",
    ]
    with Image.open(result["tif"]) as image:
        assert tuple(round(float(value)) for value in image.info.get("dpi", (0, 0))) == (600, 600)


def test_export_replay_graph_rejects_missing_requested_graph_page(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _export_replay_graph
    from src.origin.operations import OperationResult

    source_opju = tmp_path / "asset.opju"
    source_opju.write_bytes(b"origin-project")
    product_dir = tmp_path / "products" / "BET"
    product_dir.mkdir(parents=True)
    exported_graphs: list[str] = []

    class FakeOriginOps:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def load_project(self, _file_path: Path) -> OperationResult:
            return OperationResult(True, "ok")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "ok", {"pages": [{"name": "Graph5", "type": "graph"}]})

        def export_graph(self, graph_name: str, file_path: Path, fmt: str, dpi: int = 600) -> OperationResult:
            exported_graphs.append(graph_name)
            if fmt == "tif":
                Image.new("RGB", (2, 2), "white").save(file_path, format="TIFF", dpi=(600, 600))
            else:
                Image.new("RGB", (2, 2), "white").save(file_path, format="PNG")
            return OperationResult(True, "ok")

    result = _export_replay_graph(FakeOriginOps(), source_opju, "MissingGraph", product_dir, "project_asset")

    assert result["ok"] is False
    assert result["requested_graph_page"] == "MissingGraph"
    assert result["graph_pages"] == ["Graph5"]
    assert exported_graphs == []


def test_export_replay_graph_rejects_corrupt_tif_even_when_origin_reports_success(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _export_replay_graph
    from src.origin.operations import OperationResult

    source_opju = tmp_path / "asset.opju"
    source_opju.write_bytes(b"origin-project")
    product_dir = tmp_path / "products" / "BET"
    product_dir.mkdir(parents=True)

    class FakeOriginOps:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def load_project(self, _file_path: Path) -> OperationResult:
            return OperationResult(True, "ok")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "ok", {"pages": [{"name": "Graph5", "type": "graph"}]})

        def run_labtalk(self, _script: str) -> OperationResult:
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            assert name in {"page.width", "page.height"}
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            return OperationResult(True, "ok")

        def export_graph(
            self,
            _graph_name: str,
            file_path: Path,
            fmt: str,
            dpi: int = 600,
            pixel_width: int | None = None,
        ) -> OperationResult:
            if fmt == "tif":
                assert pixel_width == 60
                file_path.write_bytes(b"not-a-tiff")
            else:
                Image.new("RGB", (2, 2), "white").save(file_path, format="PNG")
            return OperationResult(True, "ok")

    result = _export_replay_graph(FakeOriginOps(), source_opju, "Graph5", product_dir, "project_asset")

    assert result["ok"] is False
    assert "TIFF" in result["message"]
    assert not (product_dir / "project_asset.tif").exists()


def test_export_replay_graph_rejects_merely_retagged_low_resolution_tif(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _export_replay_graph
    from src.origin.operations import OperationResult

    source_opju = tmp_path / "asset.opju"
    source_opju.write_bytes(b"origin-project")
    product_dir = tmp_path / "products" / "BET"
    product_dir.mkdir(parents=True)

    class FakeOriginOps:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def load_project(self, _file_path: Path) -> OperationResult:
            return OperationResult(True, "ok")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "ok", {"pages": [{"name": "Graph5", "type": "graph"}]})

        def run_labtalk(self, _script: str) -> OperationResult:
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            assert name in {"page.width", "page.height"}
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            return OperationResult(True, "ok")

        def export_graph(
            self,
            _graph_name: str,
            file_path: Path,
            fmt: str,
            dpi: int = 600,
            pixel_width: int | None = None,
        ) -> OperationResult:
            if fmt == "tif":
                assert pixel_width == 60
                Image.new("RGB", (30, 30), "white").save(file_path, format="TIFF", dpi=(600, 600))
            else:
                Image.new("RGB", (2, 2), "white").save(file_path, format="PNG")
            return OperationResult(True, "ok")

    result = _export_replay_graph(FakeOriginOps(), source_opju, "Graph5", product_dir, "project_asset")

    assert result["ok"] is False
    assert "pixel dimensions" in result["message"]
    assert not (product_dir / "project_asset.tif").exists()


def test_export_replay_graph_rejects_unverified_project_identity_without_leak(tmp_path: Path) -> None:
    from PIL import Image

    from src.core.origin_style_assets import _export_replay_graph
    from src.origin.operations import OperationResult

    source_opju = tmp_path / "asset.opju"
    source_opju.write_bytes(b"origin-project")
    product_dir = tmp_path / "products" / "BET"
    product_dir.mkdir(parents=True)
    exported_formats: list[str] = []

    class FakeOriginOps:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "ok")

        def load_project(self, _file_path: Path) -> OperationResult:
            return OperationResult(True, "ok")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "ok", {"pages": [{"name": "Graph5", "type": "graph"}]})

        def run_labtalk(self, _script: str) -> OperationResult:
            return OperationResult(True, "ok")

        def get_labtalk_variable(self, name: str) -> OperationResult:
            assert name in {"page.width", "page.height"}
            return OperationResult(True, "ok", {"value": 100.0})

        def reset_project_identity_for_export(self) -> OperationResult:
            return OperationResult(False, "D:/private/project/secret.opju")

        def export_graph(
            self,
            _graph_name: str,
            file_path: Path,
            fmt: str,
            dpi: int = 600,
            pixel_width: int | None = None,
        ) -> OperationResult:
            exported_formats.append(fmt)
            Image.new("RGB", (2, 2), "white").save(file_path, format="PNG")
            return OperationResult(True, "ok")

    result = _export_replay_graph(FakeOriginOps(), source_opju, "Graph5", product_dir, "project_asset")

    assert result["ok"] is False
    assert "identity verification failed" in result["message"]
    assert "private" not in result["message"]
    assert exported_formats == ["png"]
    assert not (product_dir / "project_asset.tif").exists()
