from __future__ import annotations

import json
import hashlib
import math
import re
import shutil
import tempfile
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.file_utils import file_sha256
from src.core.image_artifacts import (
    expected_raster_pixels,
    validate_tif_physical_resolution,
)
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.origin.conformance import compare_style_snapshots
from src.origin.operations import connect_origin, quote_labtalk, safe_origin_name
from src.origin.style_mimic import apply_style_snapshot, read_graph_style_snapshot
from src.origin.style_registry import load_origin_style_manifest, resolve_origin_style_asset
from src.origin.template_binding import resolve_template_binding_contract
from src.origin.template_format import parse_origin_dataset_reference
from src.origin.xrd_annotations import apply_xrd_standard_card_annotations


DEFAULT_STYLE_ASSET_ROOT = Path("templates") / "origin_styles"
PLOT_STYLE_READBACK_OPTIONS = {
    "color": "-c",
    "line_color": "-cl",
    "line_width_origin_units": "-w",
    "line_width_pt": "-wp",
    "line_style": "-l",
    "symbol_shape": "-k",
    "symbol_size": "-z",
    # Keep these two legacy keys for compatibility with harvested snapshots.
    # They historically represented the first-pattern background and
    # foreground colours, not the Fill Area Under Curve enable/mode flags.
    "fill_area": "-pfb",
    "fill_color": "-pfc",
    "fill_enabled": "-pf",
    "fill_mode": "-pfv",
    "fill_above_color": "-pfb",
    "fill_below_color": "-p2fb",
    "fill_above_pattern_color": "-pfc",
    "fill_below_pattern_color": "-p2fc",
    "fill_above_pattern": "-pfp",
    "fill_below_pattern": "-p2fp",
    "fill_transparency": "-paaf",
    "border_color": "-pbc",
    "border_width": "-pbw",
}
PREVIEW_MANIFEST_FIELDS = {
    "preview_png",
    "reference_preview_png",
    "template_preview_comparison_png",
    "preview_rms",
}
DIRECT_TEMPLATE_CLEARABLE_FIELDS = PREVIEW_MANIFEST_FIELDS | {"graph_template"}


@dataclass(frozen=True)
class OriginStyleAssetExportItem:
    product_key: str
    data_type: str
    status: str
    graph_page: str
    origin_file: Path
    format_theme_path: Path
    graph_template_path: Path | None = None
    style_snapshot_path: Path | None = None
    data_snapshot_path: Path | None = None
    template_opju_path: Path | None = None
    preview_png: Path | None = None
    reference_preview_png: Path | None = None
    comparison_png: Path | None = None
    preview_rms: float | None = None
    source_mode: str = "run_harvest"
    style_source_product_key: str = ""
    style_source_theme_path: Path | None = None

    def manifest_entry(self, asset_root: Path) -> dict[str, object]:
        file_paths = {
            "format_theme": self.format_theme_path,
            "graph_template": self.graph_template_path,
            "style_snapshot": self.style_snapshot_path,
            "data_snapshot": self.data_snapshot_path,
            "template_opju": self.template_opju_path,
            "preview_png": self.preview_png,
            "reference_preview_png": self.reference_preview_png,
            "template_preview_comparison_png": self.comparison_png,
            "style_source_theme": self.style_source_theme_path,
        }
        readable_files = {
            field: path
            for field, path in file_paths.items()
            if path is not None and path.is_file()
        }
        primary = readable_files.get("format_theme") or readable_files.get("graph_template")
        layer_count, plot_count = _manifest_snapshot_counts(self.style_snapshot_path)
        entry = {
            "product_key": self.product_key,
            "data_type": self.data_type,
            "status": self.status,
            "graph_page": self.graph_page,
            "source_mode": self.source_mode,
            "format_theme": _relative_or_absolute(self.format_theme_path, asset_root),
            "graph_template": _relative_or_absolute(self.graph_template_path, asset_root)
            if self.graph_template_path
            else "",
            "style_snapshot": _relative_or_absolute(self.style_snapshot_path, asset_root)
            if self.style_snapshot_path
            else "",
            "data_snapshot": _relative_or_absolute(self.data_snapshot_path, asset_root)
            if self.data_snapshot_path
            else "",
            "template_opju": _relative_or_absolute(self.template_opju_path, asset_root)
            if self.template_opju_path
            else "",
            "preview_png": _relative_or_absolute(self.preview_png, asset_root) if self.preview_png else "",
            "reference_preview_png": _relative_or_absolute(self.reference_preview_png, asset_root) if self.reference_preview_png else "",
            "template_preview_comparison_png": _relative_or_absolute(self.comparison_png, asset_root) if self.comparison_png else "",
            "preview_rms": self.preview_rms,
            "style_source_product_key": self.style_source_product_key,
            "style_source_theme": _relative_or_absolute(self.style_source_theme_path, asset_root)
            if self.style_source_theme_path
            else "",
        }
        entry.update(
            {
                "asset_kind": primary.suffix.casefold().lstrip(".") if primary is not None else "",
                "sha256": file_sha256(primary) if primary is not None else "",
                "file_size_bytes": primary.stat().st_size if primary is not None else 0,
                "expected_layer_count": layer_count,
                "expected_plot_count": plot_count,
                "origin_version": "",
                "origin_build": "",
                "pipeline_git_commit": "",
                "harvested_at": datetime.now().isoformat(timespec="seconds"),
                "source_opju_hash": file_sha256(self.template_opju_path)
                if self.template_opju_path is not None and self.template_opju_path.is_file()
                else "",
                "exact_pixel_match": self.preview_rms == 0.0 if self.preview_rms is not None else None,
                "file_integrity": {
                    field: {
                        "kind": path.suffix.casefold().lstrip("."),
                        "sha256": file_sha256(path),
                        "size_bytes": path.stat().st_size,
                    }
                    for field, path in readable_files.items()
                },
            }
        )
        return entry


@dataclass(frozen=True)
class OriginStyleAssetExportPlan:
    project_root: Path
    run_root: Path
    asset_root: Path
    items: list[OriginStyleAssetExportItem]


@dataclass(frozen=True)
class OriginStyleAssetReplayItem:
    product_key: str
    data_type: str
    source_opju: Path
    graph_page: str
    comparison_mode: str = "reference_opju_comparison"
    graph_template_path: Path | None = None
    style_snapshot_path: Path | None = None
    binding_contract_path: Path | None = None
    style_source_product_key: str = ""
    style_source_theme_path: Path | None = None


@dataclass(frozen=True)
class OriginStyleAssetReplayPlan:
    project_root: Path
    output_dir: Path
    items: list[OriginStyleAssetReplayItem]


def _manifest_snapshot_counts(path: Path | None) -> tuple[int, int]:
    if path is None or not path.is_file():
        return 1, 1
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        layer_count = int(payload.get("layer_count") or 1) if isinstance(payload, dict) else 1
        plot_count = int(payload.get("plot_count") or 1) if isinstance(payload, dict) else 1
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 1, 1
    return max(layer_count, 1), max(plot_count, 1)


def build_origin_style_asset_export_plan(
    project_root: Path,
    run_root: Path | None,
    asset_root: Path | None = None,
    *,
    template_plan: Path | None = None,
    template_opju: Path | None = None,
    product_key: str | None = None,
    data_type: str | None = None,
    graph_page: str | None = None,
) -> OriginStyleAssetExportPlan:
    root = asset_root or project_root / DEFAULT_STYLE_ASSET_ROOT
    if template_plan is not None:
        items = [
            _export_item_from_template_plan_row(project_root, root, raw)
            for raw in _load_template_plan_items(template_plan)
        ]
        return OriginStyleAssetExportPlan(project_root=project_root, run_root=run_root or Path(), asset_root=root, items=items)
    if template_opju is not None:
        if not product_key or not graph_page:
            raise ValueError("--product-key and --graph-page are required with --template-opju")
        source = template_opju if template_opju.is_absolute() else project_root / template_opju
        slug = safe_origin_name(product_key, "Style")
        item = OriginStyleAssetExportItem(
            product_key=product_key,
            data_type=data_type or product_key,
            status="accepted",
            graph_page=graph_page,
            origin_file=source,
            format_theme_path=root / "format_themes" / f"{slug}.oth",
            graph_template_path=root / "graph_templates" / f"{slug}.otpu",
            style_snapshot_path=root / "snapshots" / f"{slug}.json",
            data_snapshot_path=root / "data_snapshots" / f"{slug}.json",
            template_opju_path=root / "reference_opju" / f"{slug}.opju",
            source_mode="direct_template_opju",
        )
        return OriginStyleAssetExportPlan(project_root=project_root, run_root=run_root or Path(), asset_root=root, items=[item])
    if run_root is None:
        raise ValueError("--run-root is required unless --template-opju is supplied")
    accepted = _accepted_comparison_items(run_root)
    items: list[OriginStyleAssetExportItem] = []
    for product_type, comparison in accepted.items():
        metadata = _metadata_for_product(run_root, product_type)
        if not metadata:
            continue
        product_dir = Path(str(metadata.get("__product_dir") or ""))
        generated_origin_file = _metadata_artifact_path(product_dir, metadata.get("origin_file"), "origin_files")
        theme_source = _theme_source_opju_from_metadata(run_root, metadata) or generated_origin_file
        if theme_source is None or not theme_source.is_file():
            continue
        product_key = str(metadata.get("product_key") or product_type)
        data_type = str(metadata.get("data_type") or product_type)
        graph_page = _theme_graph_page_from_metadata(metadata)
        if not graph_page:
            continue
        slug = safe_origin_name(product_key, "Style")
        items.append(
            OriginStyleAssetExportItem(
                product_key=product_key,
                data_type=data_type,
                status=str(metadata.get("status") or comparison.get("status") or ""),
                graph_page=graph_page,
                origin_file=theme_source,
                format_theme_path=root / "format_themes" / f"{slug}.oth",
                graph_template_path=root / "graph_templates" / f"{slug}.otpu",
                style_snapshot_path=root / "snapshots" / f"{slug}.json",
                data_snapshot_path=root / "data_snapshots" / f"{slug}.json",
                template_opju_path=root / "reference_opju" / f"{slug}.opju",
                preview_png=_metadata_artifact_path(product_dir, metadata.get("preview_png"), "figures_preview"),
                reference_preview_png=_metadata_artifact_path(product_dir, metadata.get("reference_preview_png"), "reference_exports"),
                comparison_png=_run_artifact_path(run_root, comparison.get("side_by_side_png")),
                preview_rms=_to_float(comparison.get("preview_rms")),
            )
        )
    return OriginStyleAssetExportPlan(project_root=project_root, run_root=run_root, asset_root=root, items=items)


def export_origin_style_assets(
    project_root: Path,
    run_root: Path | None = None,
    *,
    asset_root: Path | None = None,
    with_origin: bool = False,
    template_plan: Path | None = None,
    template_opju: Path | None = None,
    product_key: str | None = None,
    data_type: str | None = None,
    graph_page: str | None = None,
) -> dict[str, object]:
    plan = build_origin_style_asset_export_plan(
        project_root,
        run_root,
        asset_root,
        template_plan=template_plan,
        template_opju=template_opju,
        product_key=product_key,
        data_type=data_type,
        graph_page=graph_page,
    )
    plan.asset_root.mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "format_themes").mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "graph_templates").mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "snapshots").mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "data_snapshots").mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "reference_opju").mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "previews").mkdir(parents=True, exist_ok=True)
    exported: list[dict[str, object]] = []
    exported_items: list[OriginStyleAssetExportItem] = []
    failures: list[dict[str, object]] = []
    if with_origin:
        operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
        runtime_dirs_to_cleanup: list[Path] = []
        try:
            for item in plan.items:
                runtime_dir = Path(tempfile.mkdtemp(prefix="rdop_style_asset_"))
                runtime_dirs_to_cleanup.append(runtime_dir)
                runtime_source = runtime_dir / f"{safe_origin_name(item.product_key, 'Template')}{item.origin_file.suffix}"
                try:
                    shutil.copy2(item.origin_file, runtime_source)
                except OSError as exc:
                    failures.append(
                        {
                            "product_key": item.product_key,
                            "message": scrub_output_text(
                                f"template OPJU working-copy creation failed: {exc}",
                                project_root=project_root,
                            ),
                        }
                    )
                    continue
                operations.new_project()
                loaded = operations.load_project(runtime_source)
                if not getattr(loaded, "ok", False):
                    failures.append({"product_key": item.product_key, "message": getattr(loaded, "message", "load failed")})
                    continue
                if item.style_source_theme_path is not None:
                    applied = operations.apply_graph_theme(item.graph_page, item.style_source_theme_path)
                    if not getattr(applied, "ok", False):
                        failures.append(
                            {
                                "product_key": item.product_key,
                                "message": scrub_output_text(
                                    getattr(applied, "message", "style source theme apply failed"),
                                    project_root=project_root,
                                ),
                                "style_source_theme": render_output_path(
                                    item.style_source_theme_path,
                                    project_root=project_root,
                                ),
                            }
                        )
                        continue
                if item.template_opju_path is not None:
                    item.template_opju_path.parent.mkdir(parents=True, exist_ok=True)
                    runtime_template_opju = runtime_dir / f"{safe_origin_name(item.product_key, 'Template')}_reference{item.template_opju_path.suffix}"
                    saved_project = operations.save_project(runtime_template_opju)
                    if not getattr(saved_project, "ok", False):
                        failures.append({"product_key": item.product_key, "message": scrub_output_text(getattr(saved_project, "message", "project-local template OPJU save failed"), project_root=project_root)})
                        continue
                    if not runtime_template_opju.is_file():
                        failures.append({"product_key": item.product_key, "message": "project-local template OPJU save did not produce a file"})
                        continue
                    shutil.copy2(runtime_template_opju, item.template_opju_path)
                if item.style_snapshot_path is not None:
                    item.style_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                    item.style_snapshot_path.write_text(
                        json.dumps(
                            read_graph_style_snapshot(
                                operations,
                                item.graph_page,
                                source_label=item.origin_file.name,
                                prefer_custom_rgb=item.product_key == "Mott-Schottky",
                            ).to_dict(),
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                if item.data_snapshot_path is not None:
                    item.data_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                    item.data_snapshot_path.write_text(
                        json.dumps(read_graph_data_snapshot(operations, item.graph_page, source_label=item.origin_file.name), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                saved = operations.save_graph_theme(item.graph_page, item.format_theme_path)
                if not getattr(saved, "ok", False):
                    failures.append({"product_key": item.product_key, "message": scrub_output_text(getattr(saved, "message", "format theme save failed"), project_root=project_root)})
                    continue
                if not item.format_theme_path.is_file() or item.format_theme_path.stat().st_size <= 0:
                    failures.append({"product_key": item.product_key, "message": "format theme save did not produce a non-empty file"})
                    continue
                saved_template = None
                if item.graph_template_path is not None:
                    runtime_graph_template = runtime_dir / f"{safe_origin_name(item.product_key, 'Template')}.otpu"
                    saved_template = operations.save_graph_template(item.graph_page, runtime_graph_template)
                graph_template_warning = ""
                if saved_template is not None and not getattr(saved_template, "ok", False):
                    graph_template_warning = scrub_output_text(
                        getattr(saved_template, "message", "graph template save failed"),
                        project_root=project_root,
                    )
                if item.graph_template_path is not None:
                    if runtime_graph_template.is_file():
                        item.graph_template_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(runtime_graph_template, item.graph_template_path)
                    elif not graph_template_warning:
                        graph_template_warning = "graph template save did not produce a file"
                exported.append(
                    {
                        "product_key": item.product_key,
                        "format_theme": render_output_path(item.format_theme_path, project_root=project_root),
                        "graph_template": render_output_path(item.graph_template_path, project_root=project_root)
                        if item.graph_template_path and item.graph_template_path.is_file()
                        else "",
                        "graph_template_warning": graph_template_warning,
                        "style_snapshot": render_output_path(item.style_snapshot_path, project_root=project_root)
                        if item.style_snapshot_path
                        else "",
                        "data_snapshot": render_output_path(item.data_snapshot_path, project_root=project_root)
                        if item.data_snapshot_path
                        else "",
                        "template_opju": render_output_path(item.template_opju_path, project_root=project_root)
                        if item.template_opju_path
                        else "",
                        "style_source_product_key": item.style_source_product_key,
                        "style_source_theme": render_output_path(item.style_source_theme_path, project_root=project_root)
                        if item.style_source_theme_path
                        else "",
                    }
                )
                exported_items.append(item)
        finally:
            try:
                close_result = operations.close()
            except Exception as exc:
                failures.append(
                    {
                        "message": scrub_output_text(
                            f"Origin lifecycle close failed: {type(exc).__name__}: {exc}",
                            project_root=project_root,
                        ),
                        "failure_stage": "origin_close",
                    }
                )
            else:
                if not getattr(close_result, "ok", False):
                    failures.append(
                        {
                            "message": scrub_output_text(
                                getattr(
                                    close_result,
                                    "message",
                                    "Origin lifecycle close did not confirm success.",
                                ),
                                project_root=project_root,
                            ),
                            "failure_stage": "origin_close",
                        }
                    )
            for runtime_dir in runtime_dirs_to_cleanup:
                shutil.rmtree(runtime_dir, ignore_errors=True)
    else:
        failures.append({"message": "Origin export was not requested; pass --with-origin to create .oth format theme files."})

    manifest_path = plan.asset_root / "manifest.json"
    entries = []
    for item in exported_items:
        preview = _copy_preview(item.preview_png, plan.asset_root, item.product_key, "preview")
        reference = _copy_preview(item.reference_preview_png, plan.asset_root, item.product_key, "reference")
        comparison = _copy_preview(item.comparison_png, plan.asset_root, item.product_key, "comparison")
        manifest_item = OriginStyleAssetExportItem(
            product_key=item.product_key,
            data_type=item.data_type,
            status=item.status,
            graph_page=item.graph_page,
            origin_file=item.origin_file,
            format_theme_path=item.format_theme_path,
            graph_template_path=item.graph_template_path if item.graph_template_path and item.graph_template_path.is_file() else None,
            style_snapshot_path=item.style_snapshot_path if item.style_snapshot_path and item.style_snapshot_path.is_file() else None,
            data_snapshot_path=item.data_snapshot_path if item.data_snapshot_path and item.data_snapshot_path.is_file() else None,
            template_opju_path=item.template_opju_path if item.template_opju_path and item.template_opju_path.is_file() else None,
            preview_png=preview,
            reference_preview_png=reference,
            comparison_png=comparison,
            preview_rms=item.preview_rms,
            source_mode=item.source_mode,
            style_source_product_key=item.style_source_product_key,
            style_source_theme_path=item.style_source_theme_path,
        )
        entries.append(manifest_item.manifest_entry(plan.asset_root))

    if entries:
        entries = _merge_origin_style_manifest_entries(manifest_path, entries)
        manifest = _origin_style_manifest_for_write(manifest_path)
        manifest.update(
            {
                "schema_version": _origin_style_manifest_schema_version_for_write(manifest_path),
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "asset_root": render_output_path(plan.asset_root, project_root=project_root),
                "origin_dependency_boundary": "Current formal exact-style runs use isolated reviewed reference_opju copies. Harvested .oth/.otpu assets remain quarantined until a fresh-project replay uses identical explicit per-plot X/Y data and mappings, saves and reopens the generated OPJU, exports native 600 dpi, has zero decoded-pixel difference, and passes manual preview.",
                "assets": entries,
            }
        )
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "asset_root": render_output_path(plan.asset_root, project_root=project_root),
        "manifest": render_output_path(manifest_path, project_root=project_root),
        "planned_count": len(plan.items),
        "exported_count": len(exported),
        "failure_count": len(failures),
        "exported": exported,
        "failures": failures,
    }


def _load_template_plan_items(template_plan: Path) -> list[dict[str, object]]:
    loaded = json.loads(template_plan.read_text(encoding="utf-8"))
    raw_items = loaded.get("items") if isinstance(loaded, dict) else loaded
    if not isinstance(raw_items, list):
        raise ValueError("Template plan must be a JSON object with an items list or a JSON list.")
    return [dict(item) for item in raw_items if isinstance(item, dict)]


def _export_item_from_template_plan_row(
    project_root: Path,
    asset_root: Path,
    raw: dict[str, object],
) -> OriginStyleAssetExportItem:
    product_key = str(raw.get("product_key") or raw.get("data_type") or "").strip()
    source_text = str(raw.get("source_opju") or raw.get("template_opju") or "").strip()
    graph_page = str(raw.get("graph_page") or "").strip()
    if not product_key or not source_text or not graph_page:
        raise ValueError(f"Template plan item is missing product_key/source_opju/graph_page: {raw}")
    source = Path(source_text)
    if not source.is_absolute():
        source = project_root / source
    style_source_product_key = str(raw.get("style_source_product_key") or "").strip()
    style_source_theme_path = _style_source_theme_from_plan(project_root, raw, style_source_product_key)
    slug = safe_origin_name(product_key, "Style")
    return OriginStyleAssetExportItem(
        product_key=product_key,
        data_type=str(raw.get("data_type") or product_key),
        status=str(raw.get("status") or "accepted"),
        graph_page=graph_page,
        origin_file=source,
        format_theme_path=asset_root / "format_themes" / f"{slug}.oth",
        graph_template_path=asset_root / "graph_templates" / f"{slug}.otpu",
        style_snapshot_path=asset_root / "snapshots" / f"{slug}.json",
        data_snapshot_path=asset_root / "data_snapshots" / f"{slug}.json",
        template_opju_path=asset_root / "reference_opju" / f"{slug}.opju",
        source_mode=str(raw.get("source_mode") or "direct_template_opju"),
        style_source_product_key=style_source_product_key,
        style_source_theme_path=style_source_theme_path,
    )


def _style_source_theme_from_plan(
    project_root: Path,
    raw: dict[str, object],
    style_source_product_key: str,
) -> Path | None:
    style_theme_text = str(raw.get("style_source_theme") or raw.get("style_source_theme_path") or "").strip()
    if style_theme_text:
        style_theme = Path(style_theme_text)
        if not style_theme.is_absolute():
            style_theme = project_root / style_theme
        if not style_theme.is_file():
            raise ValueError(f"style_source_theme does not exist: {style_theme}")
        return style_theme
    if not style_source_product_key:
        return None
    asset = resolve_origin_style_asset(project_root, style_source_product_key)
    if asset is None or asset.format_theme_path is None or not asset.format_theme_path.is_file():
        raise ValueError(f"style_source_product_key has no project-local format theme: {style_source_product_key}")
    return asset.format_theme_path


def run_origin_style_asset_replay(
    project_root: Path,
    plan_path: Path,
    output_dir: Path,
    *,
    with_origin: bool = False,
) -> dict[str, object]:
    plan = build_origin_style_asset_replay_plan(project_root, plan_path, output_dir)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    (plan.output_dir / "products").mkdir(parents=True, exist_ok=True)
    if not with_origin:
        summary = {
            "planned_count": len(plan.items),
            "compared_count": 0,
            "self_replay_count": 0,
            "inconclusive_count": 0,
            "failure_count": len(plan.items),
            "items": [
                {
                    "product_key": item.product_key,
                    "data_type": item.data_type,
                    "status": "blocked",
                    "message": "Origin replay comparison requires --with-origin.",
                }
                for item in plan.items
            ],
        }
        _write_replay_summary(plan.output_dir, summary)
        return {
            "output_dir": render_output_path(plan.output_dir, project_root=project_root),
            **summary,
        }

    operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    results: list[dict[str, object]] = []
    close_failure = ""
    try:
        for item in plan.items:
            results.append(_replay_compare_one_item(operations, project_root, plan.output_dir, item))
    finally:
        try:
            close_result = operations.close()
        except Exception as exc:
            close_failure = scrub_output_text(
                f"Origin lifecycle close failed: {type(exc).__name__}: {exc}",
                project_root=project_root,
            )
        else:
            if not getattr(close_result, "ok", False):
                close_failure = scrub_output_text(
                    getattr(
                        close_result,
                        "message",
                        "Origin lifecycle close did not confirm success.",
                    ),
                    project_root=project_root,
                )
    compared_count = sum(
        1
        for item in results
        if item.get("status") in {"matched", "fresh_project_same_data_match"}
    )
    self_replay_count = sum(
        1 for item in results if item.get("status") == "reference_opju_self_replay"
    )
    item_failure_count = sum(
        1 for item in results if item.get("status") in {"failed", "mismatch", "blocked"}
    )
    lifecycle_failure_count = 1 if close_failure else 0
    failure_count = item_failure_count + lifecycle_failure_count
    summary = {
        "planned_count": len(plan.items),
        "compared_count": compared_count,
        "self_replay_count": self_replay_count,
        "inconclusive_count": self_replay_count,
        "failure_count": failure_count,
        "item_failure_count": item_failure_count,
        "lifecycle_failure_count": lifecycle_failure_count,
        "origin_close_ok": not bool(close_failure),
        "origin_close_message": close_failure,
        "items": results,
    }
    _write_replay_summary(plan.output_dir, summary)
    return {
        "output_dir": render_output_path(plan.output_dir, project_root=project_root),
        **summary,
    }


def build_origin_style_asset_replay_plan(
    project_root: Path,
    plan_path: Path,
    output_dir: Path,
) -> OriginStyleAssetReplayPlan:
    loaded = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_items = loaded.get("items") if isinstance(loaded, dict) else loaded
    if not isinstance(raw_items, list):
        raise ValueError("Origin style asset replay plan must be a JSON object with an items list or a JSON list.")
    items: list[OriginStyleAssetReplayItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        product_key = str(raw.get("product_key") or raw.get("data_type") or "").strip()
        source_text = str(raw.get("source_opju") or raw.get("template_opju") or "").strip()
        graph_page = str(raw.get("graph_page") or "").strip()
        if not product_key or not source_text or not graph_page:
            raise ValueError(f"Replay plan item is missing product_key/source_opju/graph_page: {raw}")
        source = Path(source_text)
        if not source.is_absolute():
            source = project_root / source
        comparison_mode = str(
            raw.get("comparison_mode") or "reference_opju_comparison"
        ).strip()
        if comparison_mode not in {
            "reference_opju_comparison",
            "fresh_project_graph_template_same_data",
        }:
            raise ValueError(
                f"Unsupported Origin style replay comparison_mode: {comparison_mode}"
            )
        graph_template_path: Path | None = None
        graph_template_text = str(raw.get("graph_template") or "").strip()
        if graph_template_text:
            graph_template_path = Path(graph_template_text)
            if not graph_template_path.is_absolute():
                graph_template_path = project_root / graph_template_path
        if (
            comparison_mode == "fresh_project_graph_template_same_data"
            and graph_template_path is None
        ):
            raise ValueError(
                "fresh_project_graph_template_same_data replay requires graph_template"
            )
        style_snapshot_path: Path | None = None
        style_snapshot_text = str(raw.get("style_snapshot") or "").strip()
        if style_snapshot_text:
            style_snapshot_path = Path(style_snapshot_text)
            if not style_snapshot_path.is_absolute():
                style_snapshot_path = project_root / style_snapshot_path
        binding_contract_path: Path | None = None
        binding_contract_text = str(raw.get("binding_contract") or "").strip()
        if binding_contract_text:
            binding_contract_path = Path(binding_contract_text)
            if not binding_contract_path.is_absolute():
                binding_contract_path = project_root / binding_contract_path
        style_source_product_key = str(raw.get("style_source_product_key") or "").strip()
        style_source_theme_path = _style_source_theme_from_plan(project_root, raw, style_source_product_key)
        items.append(
            OriginStyleAssetReplayItem(
                product_key=product_key,
                data_type=str(raw.get("data_type") or product_key),
                source_opju=source,
                graph_page=graph_page,
                comparison_mode=comparison_mode,
                graph_template_path=graph_template_path,
                style_snapshot_path=style_snapshot_path,
                binding_contract_path=binding_contract_path,
                style_source_product_key=style_source_product_key,
                style_source_theme_path=style_source_theme_path,
            )
        )
    return OriginStyleAssetReplayPlan(project_root=project_root, output_dir=output_dir, items=items)


def _replay_compare_one_item(
    operations: object,
    project_root: Path,
    output_dir: Path,
    item: OriginStyleAssetReplayItem,
) -> dict[str, object]:
    product_dir = output_dir / "products" / safe_origin_name(item.product_key, "Product")
    product_dir.mkdir(parents=True, exist_ok=True)
    if item.comparison_mode == "fresh_project_graph_template_same_data":
        return _replay_fresh_graph_template_same_data(
            operations,
            project_root,
            product_dir,
            item,
        )
    asset = resolve_origin_style_asset(project_root, item.product_key)
    if asset is None or asset.template_opju_path is None or not asset.template_opju_path.is_file():
        result = {
            "product_key": item.product_key,
            "data_type": item.data_type,
            "status": "failed",
            "message": "Project-local template OPJU asset is missing.",
            "source_opju": render_output_path(item.source_opju, project_root=project_root),
            "graph_page": item.graph_page,
        }
        (product_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    if not item.source_opju.is_file():
        result = {
            "product_key": item.product_key,
            "data_type": item.data_type,
            "status": "failed",
            "message": "Source template OPJU is missing.",
            "source_opju": render_output_path(item.source_opju, project_root=project_root),
            "asset_opju": render_output_path(asset.template_opju_path, project_root=project_root),
            "graph_page": item.graph_page,
        }
        (product_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    source = _export_replay_graph(
        operations,
        item.source_opju,
        item.graph_page,
        product_dir,
        "source_template",
        theme_path=item.style_source_theme_path,
    )
    asset_export = _export_replay_graph(operations, asset.template_opju_path, item.graph_page or asset.graph_page, product_dir, "project_asset")
    source_sha256 = file_sha256(item.source_opju)
    asset_sha256 = file_sha256(asset.template_opju_path)
    same_reference_content = source_sha256 == asset_sha256
    result = {
        "product_key": item.product_key,
        "data_type": item.data_type,
        "source_opju": render_output_path(item.source_opju, project_root=project_root),
        "asset_opju": render_output_path(asset.template_opju_path, project_root=project_root),
        "graph_page": item.graph_page,
        "source_export": source,
        "asset_export": asset_export,
        "style_source_product_key": item.style_source_product_key,
        "style_source_theme": render_output_path(item.style_source_theme_path, project_root=project_root)
        if item.style_source_theme_path
        else "",
        "source_opju_sha256": source_sha256,
        "asset_opju_sha256": asset_sha256,
        "same_reference_content": same_reference_content,
    }
    if not source.get("ok") or not asset_export.get("ok"):
        result.update({"status": "failed", "message": "Source or project asset graph export failed."})
        (product_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    comparison = _compare_replay_pngs(Path(str(source["png"])), Path(str(asset_export["png"])), product_dir)
    exact_pixel_match = bool(comparison.get("exact_pixel_match"))
    if exact_pixel_match and same_reference_content:
        status = "reference_opju_self_replay"
        message = (
            "The same reference OPJU content re-exported pixel-identically. "
            "This is deterministic-export evidence only and does not validate "
            "the product format theme on a newly constructed graph."
        )
        comparison_scope = "deterministic_reference_opju_export"
        style_asset_validated = False
    else:
        status = "reference_opju_match" if exact_pixel_match else "mismatch"
        message = (
            "Two reference OPJU exports were compared. Even an exact result "
            "does not validate the .oth asset because the project-side graph "
            "was not newly constructed from data and the saved theme."
        )
        comparison_scope = "reference_opju_comparison"
        style_asset_validated = False
    result.update(
        {
            "status": status,
            "message": message,
            "comparison_scope": comparison_scope,
            "style_asset_validated": style_asset_validated,
            "comparison": comparison,
        }
    )
    (product_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _replay_fresh_graph_template_same_data(
    operations: object,
    project_root: Path,
    product_dir: Path,
    item: OriginStyleAssetReplayItem,
) -> dict[str, object]:
    """Validate one OTP/OTPU in a new project with exact reference plot data.

    The reference OPJU is copied and opened only to read the reviewed graph,
    its explicit X/Y mappings, column metadata, and reference pixels.  The
    candidate project is then created from scratch and receives only those
    values plus the detached graph template and its optional detached style
    snapshot.  The reference OPJU is never a product base and is not loaded
    while the candidate graph is constructed.
    """

    template_path = item.graph_template_path
    base_result: dict[str, object] = {
        "product_key": item.product_key,
        "data_type": item.data_type,
        "comparison_mode": item.comparison_mode,
        "comparison_scope": "fresh_project_same_data",
        "source_opju": render_output_path(item.source_opju, project_root=project_root),
        "graph_template": render_output_path(template_path, project_root=project_root)
        if template_path is not None
        else "",
        "style_snapshot": render_output_path(
            item.style_snapshot_path,
            project_root=project_root,
        )
        if item.style_snapshot_path is not None
        else "",
        "format_theme": render_output_path(
            item.style_source_theme_path,
            project_root=project_root,
        )
        if item.style_source_theme_path is not None
        else "",
        "graph_page": item.graph_page,
        "reference_opju_used_as_product_base": False,
        "runtime_reference_opju_loaded_during_fresh_plot": False,
        "manual_preview_required": True,
        "style_asset_validated": False,
    }
    if not item.source_opju.is_file():
        return _write_fresh_template_replay_failure(
            product_dir,
            base_result,
            "Source reference OPJU is missing.",
        )
    if (
        template_path is None
        or not template_path.is_file()
        or template_path.suffix.casefold() not in {".otp", ".otpu"}
    ):
        return _write_fresh_template_replay_failure(
            product_dir,
            base_result,
            "Candidate graph template is missing or is not OTP/OTPU.",
        )

    source_hash_before = file_sha256(item.source_opju)
    template_hash_before = file_sha256(template_path)
    style_snapshot_hash_before = (
        file_sha256(item.style_snapshot_path)
        if item.style_snapshot_path is not None and item.style_snapshot_path.is_file()
        else ""
    )
    format_theme_hash_before = (
        file_sha256(item.style_source_theme_path)
        if item.style_source_theme_path is not None
        and item.style_source_theme_path.is_file()
        else ""
    )
    runtime_dir = Path(
        tempfile.mkdtemp(
            prefix=f"rdop_fresh_replay_{safe_origin_name(item.product_key, 'Style')}_"
        )
    )
    runtime_reference = runtime_dir / f"reference{item.source_opju.suffix.casefold()}"
    runtime_template = runtime_dir / f"candidate{template_path.suffix.casefold()}"
    runtime_theme = runtime_dir / "candidate.oth"
    runtime_candidate_opju = runtime_dir / "candidate.opju"
    runtime_reference_png = runtime_dir / "reference_same_data.png"
    runtime_candidate_png = runtime_dir / "candidate_same_data.png"
    runtime_candidate_tif = runtime_dir / "candidate_600dpi.tif"
    final_reference_png = product_dir / "reference_same_data.png"
    final_candidate_png = product_dir / "candidate_same_data.png"
    final_candidate_tif = product_dir / "candidate_600dpi.tif"
    final_candidate_opju = product_dir / f"{safe_origin_name(item.product_key, 'Product')}.opju"
    result = dict(base_result)
    try:
        shutil.copy2(item.source_opju, runtime_reference)
        shutil.copy2(template_path, runtime_template)
        if item.style_source_theme_path is not None:
            if not item.style_source_theme_path.is_file():
                raise RuntimeError("Detached candidate Origin format theme is missing.")
            shutil.copy2(item.style_source_theme_path, runtime_theme)
        operations.new_project()
        loaded = operations.load_project(runtime_reference)
        if not getattr(loaded, "ok", False):
            raise RuntimeError(getattr(loaded, "message", "Reference OPJU load failed."))

        reference_data = read_graph_data_snapshot(
            operations,
            item.graph_page,
            source_label="isolated_reference_copy.opju",
        )
        if str(reference_data.get("status") or "") != "ready":
            raise RuntimeError("Reference graph data snapshot is not ready.")
        plot_records = [
            dict(plot)
            for plot in reference_data.get("plots", [])
            if isinstance(plot, dict)
        ]
        mapping_records = [
            {
                "layer_index": plot.get("layer_index"),
                "plot_index": plot.get("plot_index"),
                "x_dataset": plot.get("x_dataset"),
                "y_dataset": plot.get("y_dataset"),
                "row_from": plot.get("plot_row_from"),
                "row_to": plot.get("plot_row_to"),
            }
            for plot in plot_records
        ]
        binding = resolve_template_binding_contract(
            item.product_key,
            item.graph_page,
            mapping_records,
            path=item.binding_contract_path,
        )
        if not binding.ok or binding.contract is None:
            raise RuntimeError(binding.message)
        if source_hash_before != binding.contract.reference_opju_sha256:
            raise RuntimeError(
                "Reference OPJU hash does not match the reviewed binding contract."
            )
        if any(int(plot.get("layer_index") or 0) < 1 for plot in plot_records):
            raise RuntimeError(
                "Fresh graph-template replay requires positive graph-layer indices."
            )

        # A reviewed graph can legitimately bind plots from multiple source
        # workbooks and layers (XRD Graph4 is one example).  Recreate the same
        # workbook/sheet/column topology in the fresh project so both the
        # plotted values and Origin's explicit X/Y mapping remain comparable.
        book_sheet_indices: dict[str, set[int]] = {}
        book_sheet_column_records: dict[
            str, dict[int, dict[int, dict[str, object]]]
        ] = {}
        xy_ranges: list[dict[str, object]] = []
        for plot in plot_records:
            x_book = str(plot.get("x_book_name") or "").strip()
            y_book = str(plot.get("book_name") or "").strip()
            if not x_book or x_book != y_book:
                raise RuntimeError(
                    "Fresh graph-template replay requires each plot's X/Y datasets in the same named workbook."
                )
            x_sheet_index = int(plot.get("x_sheet_index") or 0)
            y_sheet_index = int(plot.get("sheet_index") or 0)
            if x_sheet_index < 1 or x_sheet_index != y_sheet_index:
                raise RuntimeError(
                    "Fresh graph-template replay requires each plot's X/Y datasets on the same worksheet."
                )
            book_sheet_indices.setdefault(y_book, set()).add(y_sheet_index)
            x_col = int(plot.get("x_col_index")) + 1
            y_col = int(plot.get("y_col_index")) + 1
            row_from = int(plot.get("plot_row_from"))
            row_to = int(plot.get("plot_row_to"))
            x_values = [
                math.nan if value is None else float(value)
                for value in list(plot.get("x_values") or [])
            ]
            y_values = [
                math.nan if value is None else float(value)
                for value in list(plot.get("y_values") or [])
            ]
            expected_value_count = row_to - row_from + 1
            if (
                row_from < 1
                or row_to < row_from
                or len(x_values) != expected_value_count
                or len(y_values) != expected_value_count
            ):
                raise RuntimeError(
                    f"Reference plot {plot.get('plot_index')} has inconsistent row bounds or value counts."
                )
            column_records = book_sheet_column_records.setdefault(y_book, {}).setdefault(
                y_sheet_index, {}
            )
            for index, values, masked_rows in (
                (x_col, x_values, list(plot.get("x_masked_rows") or [])),
                (y_col, y_values, list(plot.get("y_masked_rows") or [])),
            ):
                record = {
                    "row_from": row_from,
                    "row_to": row_to,
                    "values": values,
                    "masked_rows": masked_rows,
                }
                existing = column_records.get(index)
                column_records[index] = _merge_replay_worksheet_column_record(
                    existing,
                    record,
                    sheet_index=y_sheet_index,
                    column_index=index,
                )
            xy_ranges.append(
                {
                    "book_name": y_book,
                    "sheet_index": y_sheet_index,
                    "layer_index": int(plot.get("layer_index")),
                    "x_col": x_col,
                    "y_col": y_col,
                    "row_from": row_from,
                    "row_to": row_to,
                }
            )
        if not book_sheet_indices:
            raise RuntimeError("Fresh graph-template replay found no source workbooks.")
        for book_name, sheet_indices in book_sheet_indices.items():
            expected_sheet_indices = set(range(1, max(sheet_indices) + 1))
            if sheet_indices != expected_sheet_indices:
                raise RuntimeError(
                    "Fresh graph-template replay requires contiguous worksheet creation "
                    f"indices starting at 1 for workbook {book_name}."
                )
        sheet_payloads: list[dict[str, object]] = []
        for book_name, sheet_indices in book_sheet_indices.items():
            for sheet_index in sorted(sheet_indices):
                records = book_sheet_column_records.get(book_name, {}).get(
                    sheet_index, {}
                )
                if not records:
                    raise RuntimeError(
                        f"Reference worksheet [{book_name}]{sheet_index} has no contracted plot columns."
                    )
                max_column = max(records)
                max_row = max(int(record["row_to"]) for record in records.values())
                columns: list[list[float]] = []
                for column_index in range(1, max_column + 1):
                    values = [math.nan] * max_row
                    record = records.get(column_index)
                    if record is not None:
                        start = int(record["row_from"]) - 1
                        plotted_values = [float(value) for value in list(record["values"])]
                        values[start : start + len(plotted_values)] = plotted_values
                    columns.append(values)
                metadata_read = operations.get_worksheet_column_metadata(
                    book_name,
                    range(1, max_column + 1),
                    sheet_index=sheet_index,
                )
                if not getattr(metadata_read, "ok", False):
                    raise RuntimeError(
                        getattr(
                            metadata_read,
                            "message",
                            "Reference column metadata read failed.",
                        )
                    )
                sheet_payloads.append(
                    {
                        "book_name": book_name,
                        "sheet_index": sheet_index,
                        "columns": columns,
                        "mask_rows_by_column": {
                            int(column_index): list(record.get("masked_rows") or [])
                            for column_index, record in records.items()
                        },
                        "column_metadata": list(
                            metadata_read.payload.get("columns", [])
                        ),
                    }
                )
        source_schema = dict(binding.contract.source_schema)
        plot_type = str(source_schema.get("plot_type") or "line+symbol").strip()
        group_plots = bool(source_schema.get("group_plots", False))
        raw_group_layers = source_schema.get("group_layer_indices") or []
        if not isinstance(raw_group_layers, list):
            raise RuntimeError(
                "Binding source_schema.group_layer_indices must be an array."
            )
        group_layer_indices = list(raw_group_layers)
        raw_stack_offsets = source_schema.get("individual_stack_offsets") or []
        if not isinstance(raw_stack_offsets, list) or any(
            not isinstance(item, dict) for item in raw_stack_offsets
        ):
            raise RuntimeError(
                "Binding source_schema.individual_stack_offsets must be an array of objects."
            )
        individual_stack_offsets = [dict(item) for item in raw_stack_offsets]
        raw_plot_formats = source_schema.get("plot_format_contracts") or []
        if not isinstance(raw_plot_formats, list) or any(
            not isinstance(item, dict) for item in raw_plot_formats
        ):
            raise RuntimeError(
                "Binding source_schema.plot_format_contracts must be an array of objects."
            )
        plot_format_contracts = [dict(item) for item in raw_plot_formats]
        raw_page_mask_override = source_schema.get("page_mask_override")
        page_mask_override: int | None = None
        if raw_page_mask_override is not None:
            try:
                page_mask_override = int(raw_page_mask_override)
            except (TypeError, ValueError):
                raise RuntimeError(
                    "Binding source_schema.page_mask_override must be numeric."
                )
            if page_mask_override not in {0, 1, 2}:
                raise RuntimeError(
                    "Binding source_schema.page_mask_override must be 0, 1, or 2."
                )
        activated_layer = operations.run_labtalk(
            f'win -a "{quote_labtalk(item.graph_page)}"; layer -s 1;'
        )
        if not getattr(activated_layer, "ok", False):
            raise RuntimeError(
                getattr(
                    activated_layer,
                    "message",
                    "Could not activate reference graph layer 1 for style readback.",
                )
            )
        reference_style = read_graph_style_snapshot(
            operations,
            item.graph_page,
            source_label="isolated_reference_copy.opju",
            prefer_custom_rgb=item.product_key == "Mott-Schottky",
        )
        try:
            page_width = int(round(float(reference_style.layout_values["page.width"])))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("Reference graph page width readback failed.") from exc
        reference_png_export = operations.export_graph(
            item.graph_page,
            runtime_reference_png,
            "png",
            dpi=600,
            pixel_width=page_width,
        )
        if not getattr(reference_png_export, "ok", False):
            raise RuntimeError(
                getattr(reference_png_export, "message", "Reference PNG export failed.")
            )

        operations.new_project()
        actual_books: dict[str, str] = {}
        actual_sheet_names: dict[tuple[str, int], str] = {}
        for reference_book, sheet_indices in book_sheet_indices.items():
            created = operations.create_worksheet(reference_book, "Sheet1")
            if not getattr(created, "ok", False):
                raise RuntimeError(
                    getattr(created, "message", "Fresh worksheet creation failed.")
                )
            actual_book = str(created.payload.get("book_name") or "")
            if not actual_book:
                raise RuntimeError(
                    f"Fresh workbook creation returned no name for {reference_book}."
                )
            actual_books[reference_book] = actual_book
            actual_sheet_names[(reference_book, 1)] = str(
                created.payload.get("sheet_name") or "Sheet1"
            )
            for sheet_index in range(2, max(sheet_indices) + 1):
                added = operations.add_worksheet(
                    actual_book, f"Sheet{sheet_index}"
                )
                if not getattr(added, "ok", False):
                    raise RuntimeError(
                        getattr(added, "message", "Fresh worksheet append failed.")
                    )
                actual_sheet_names[(reference_book, sheet_index)] = str(
                    added.payload.get("sheet_name") or f"Sheet{sheet_index}"
                )
        for payload in sheet_payloads:
            reference_book = str(payload["book_name"])
            actual_book = actual_books[reference_book]
            sheet_index = int(payload["sheet_index"])
            written = operations.set_worksheet_data(
                actual_book,
                actual_sheet_names[(reference_book, sheet_index)],
                list(payload["columns"]),
            )
            if not getattr(written, "ok", False):
                raise RuntimeError(
                    getattr(written, "message", "Fresh worksheet data write failed.")
                )
            metadata_write = operations.set_worksheet_column_metadata(
                actual_book,
                list(payload["column_metadata"]),
                sheet_index=sheet_index,
            )
            if not getattr(metadata_write, "ok", False):
                raise RuntimeError(
                    getattr(metadata_write, "message", "Fresh worksheet metadata write failed.")
                )
            for column_index, masked_rows in dict(
                payload.get("mask_rows_by_column") or {}
            ).items():
                if not masked_rows:
                    continue
                mask_write = operations.set_worksheet_column_mask_rows(
                    actual_book,
                    int(column_index),
                    list(masked_rows),
                    sheet_index=sheet_index,
                )
                if not getattr(mask_write, "ok", False):
                    raise RuntimeError(
                        getattr(
                            mask_write,
                            "message",
                            "Fresh worksheet mask-state write failed.",
                        )
                    )
        fresh_xy_ranges = [
            {
                **xy_range,
                "book_name": actual_books[str(xy_range["book_name"])],
            }
            for xy_range in xy_ranges
        ]
        default_book = actual_books[next(iter(book_sheet_indices))]
        plotted = operations.create_graph_from_xy_pairs_template(
            item.graph_page,
            runtime_template,
            default_book,
            fresh_xy_ranges,
            plot_type=plot_type,
            rescale=False,
            legend=False,
            group_plots=group_plots,
            group_layer_indices=group_layer_indices,
            individual_stack_offsets=individual_stack_offsets,
            plot_format_contracts=plot_format_contracts,
        )
        if not getattr(plotted, "ok", False):
            raise RuntimeError(
                getattr(plotted, "message", "Fresh graph-template plot failed.")
            )
        initial_plot_format_readback = list(
            plotted.payload.get("plot_format_readback", [])
        )
        final_plot_format_readback = list(initial_plot_format_readback)
        # Multi-layer templates leave the final populated layer active.  The
        # reviewed detached theme/snapshot for the graph is anchored to layer
        # 1, so make that target explicit before applying any style.  Without
        # this, Origin applies the layer-1 style to the last populated overlay
        # (for example XRD's top sample layer), duplicating axes and retaining
        # placeholder legend text even though all data mappings are correct.
        activated_candidate_layer = operations.run_labtalk(
            f'win -a "{quote_labtalk(item.graph_page)}"; layer -s 1;'
        )
        if not getattr(activated_candidate_layer, "ok", False):
            raise RuntimeError(
                getattr(
                    activated_candidate_layer,
                    "message",
                    "Could not activate candidate graph layer 1 before style apply.",
                )
            )
        if item.style_source_theme_path is not None:
            themed = operations.apply_graph_theme(item.graph_page, runtime_theme)
            if not getattr(themed, "ok", False):
                raise RuntimeError(
                    getattr(themed, "message", "Detached Origin format theme apply failed.")
                )
        if item.style_snapshot_path is not None:
            if not item.style_snapshot_path.is_file():
                raise RuntimeError("Detached candidate style snapshot is missing.")
            style_payload = json.loads(
                item.style_snapshot_path.read_text(encoding="utf-8")
            )
            if not isinstance(style_payload, dict) or not apply_style_snapshot(
                operations,
                item.graph_page,
                style_payload,
                apply_default_font=False,
                apply_axis_titles=True,
                preserve_custom_rgb=item.product_key == "Mott-Schottky",
            ):
                raise RuntimeError("Detached candidate style snapshot could not be applied.")
        if plot_format_contracts:
            reapplied_formats = operations.apply_graph_plot_format_contracts(
                item.graph_page,
                plot_format_contracts,
            )
            if not getattr(reapplied_formats, "ok", False):
                raise RuntimeError(
                    getattr(
                        reapplied_formats,
                        "message",
                        "Native plot-format contracts could not be restored after detached style application.",
                    )
                )
            final_plot_format_readback = list(
                reapplied_formats.payload.get("plot_format_readback", [])
            )
        if page_mask_override is not None:
            mask_display = operations.run_labtalk(
                f'win -a "{quote_labtalk(item.graph_page)}"; '
                f"page.mask={page_mask_override};"
            )
            if not getattr(mask_display, "ok", False):
                raise RuntimeError(
                    "Detached candidate page-level mask display could not be applied."
                )
        annotation_contract = source_schema.get("xrd_standard_card_annotations")
        annotation_policy: dict[str, object] = {
            "applied": True,
            "status": "not_required",
        }
        if annotation_contract is not None:
            annotation_policy = apply_xrd_standard_card_annotations(
                operations,
                item.graph_page,
                annotation_contract,
            )
            if not annotation_policy.get("applied"):
                raise RuntimeError(
                    "Detached candidate XRD annotation contract could not be applied: "
                    + json.dumps(annotation_policy, ensure_ascii=False, sort_keys=True)
                )
        saved = operations.save_project(runtime_candidate_opju)
        if not getattr(saved, "ok", False) or not runtime_candidate_opju.is_file():
            raise RuntimeError(
                getattr(saved, "message", "Fresh candidate OPJU save failed.")
            )

        operations.new_project()
        reopened = operations.load_project(runtime_candidate_opju)
        if not getattr(reopened, "ok", False):
            raise RuntimeError(
                getattr(reopened, "message", "Fresh candidate OPJU reopen failed.")
            )
        candidate_data = read_graph_data_snapshot(
            operations,
            item.graph_page,
            source_label="fresh_graph_template_candidate.opju",
        )
        # Data snapshot traversal intentionally visits every graph layer and
        # therefore leaves the final layer active.  Restore layer 1 so style
        # readback and export inspect the same graph context as the reference.
        reactivated_candidate_layer = operations.run_labtalk(
            f'win -a "{quote_labtalk(item.graph_page)}"; layer -s 1;'
        )
        if not getattr(reactivated_candidate_layer, "ok", False):
            raise RuntimeError(
                getattr(
                    reactivated_candidate_layer,
                    "message",
                    "Could not reactivate candidate graph layer 1 for final readback.",
                )
            )
        candidate_style = read_graph_style_snapshot(
            operations,
            item.graph_page,
            source_label="fresh_graph_template_candidate.opju",
            prefer_custom_rgb=item.product_key == "Mott-Schottky",
        )
        candidate_png_export = operations.export_graph(
            item.graph_page,
            runtime_candidate_png,
            "png",
            dpi=600,
            pixel_width=page_width,
        )
        if not getattr(candidate_png_export, "ok", False):
            raise RuntimeError(
                getattr(candidate_png_export, "message", "Candidate PNG export failed.")
            )
        tif_evidence = _export_replay_tif_with_physical_validation(
            operations,
            item.graph_page,
            runtime_candidate_tif,
            dpi=600,
        )

        same_data = compare_graph_data_snapshots(reference_data, candidate_data)
        style_conformance = compare_style_snapshots(
            reference_style,
            candidate_style,
            required_line_width_pt=None,
            # A detached asset must reproduce the reference template, not a
            # global bold-axis policy.  Some valid Origin templates use
            # dynamic axis-title expressions and non-bold titles.
            require_axis_title_bold=_fresh_template_reference_axis_titles_bold(
                reference_style
            ),
        ).to_dict()
        pixels = _compare_replay_pngs(
            runtime_reference_png,
            runtime_candidate_png,
            product_dir,
        )
        axis_gate = _fresh_template_axis_title_gate(reference_style, candidate_style)
        source_hash_after = file_sha256(item.source_opju)
        template_hash_after = file_sha256(template_path)
        style_snapshot_hash_after = (
            file_sha256(item.style_snapshot_path)
            if item.style_snapshot_path is not None
            and item.style_snapshot_path.is_file()
            else ""
        )
        format_theme_hash_after = (
            file_sha256(item.style_source_theme_path)
            if item.style_source_theme_path is not None
            and item.style_source_theme_path.is_file()
            else ""
        )
        automated_pass = bool(
            same_data.get("same_data")
            and style_conformance.get("status") == "pass"
            and axis_gate.get("pass")
            and pixels.get("exact_pixel_match")
            and tif_evidence.get("ok")
            and source_hash_before == source_hash_after
            and template_hash_before == template_hash_after
            and style_snapshot_hash_before == style_snapshot_hash_after
            and format_theme_hash_before == format_theme_hash_after
        )
        for source, target in (
            (runtime_reference_png, final_reference_png),
            (runtime_candidate_png, final_candidate_png),
            (runtime_candidate_tif, final_candidate_tif),
            (runtime_candidate_opju, final_candidate_opju),
        ):
            if source.is_file() and source.stat().st_size > 0:
                shutil.copy2(source, target)
        result.update(
            {
                "status": (
                    "fresh_project_same_data_match"
                    if automated_pass
                    else "mismatch"
                ),
                "message": (
                    "Fresh-project same-data graph-template replay passed all automated gates; manual preview is still required."
                    if automated_pass
                    else "Fresh-project same-data graph-template replay failed one or more automated gates."
                ),
                "automated_acceptance_passed": automated_pass,
                "candidate_graph_template_sha256": template_hash_before,
                "candidate_graph_template_unchanged": template_hash_before
                == template_hash_after,
                "candidate_style_snapshot_sha256": style_snapshot_hash_before,
                "candidate_style_snapshot_unchanged": style_snapshot_hash_before
                == style_snapshot_hash_after,
                "candidate_format_theme_sha256": format_theme_hash_before,
                "candidate_format_theme_unchanged": format_theme_hash_before
                == format_theme_hash_after,
                "source_opju_sha256": source_hash_before,
                "source_opju_unchanged": source_hash_before == source_hash_after,
                "binding_contract": binding.to_dict(),
                "annotation_policy": annotation_policy,
                "reference_column_metadata": (
                    list(sheet_payloads[0]["column_metadata"])
                    if len(sheet_payloads) == 1
                    else []
                ),
                "reference_column_metadata_by_sheet": [
                    {
                        "sheet_index": int(payload["sheet_index"]),
                        "columns": list(payload["column_metadata"]),
                    }
                    for payload in sheet_payloads
                ],
                "plot_type": plot_type,
                "group_plots": group_plots,
                "group_layer_indices": group_layer_indices,
                "individual_stack_offsets": individual_stack_offsets,
                "individual_stack_readback": list(
                    plotted.payload.get("individual_stack_readback", [])
                ),
                "plot_format_contracts": plot_format_contracts,
                "page_mask_override": page_mask_override,
                "initial_plot_format_readback": initial_plot_format_readback,
                "plot_format_readback": final_plot_format_readback,
                "template_axis_scales": dict(
                    plotted.payload.get("template_axis_scales", {})
                ),
                "axis_scale_readback": dict(
                    plotted.payload.get("axis_scale_readback", {})
                ),
                "reference_data": reference_data,
                "candidate_data": candidate_data,
                "same_data_comparison": same_data,
                "reference_style": reference_style.to_dict(),
                "candidate_style": candidate_style.to_dict(),
                "style_conformance": style_conformance,
                "axis_title_hard_gate": axis_gate,
                "comparison": pixels,
                "tif_resolution_evidence": tif_evidence,
                "artifacts": {
                    "reference_png": str(final_reference_png),
                    "candidate_png": str(final_candidate_png),
                    "candidate_tif": str(final_candidate_tif),
                    "candidate_opju": str(final_candidate_opju),
                },
                "reference_plot_values_sha256": reference_data.get(
                    "plot_values_sha256", ""
                ),
                "generated_plot_values_sha256": candidate_data.get(
                    "plot_values_sha256", ""
                ),
                "reference_plot_mapping_sha256": reference_data.get(
                    "plot_mapping_sha256", ""
                ),
                "generated_plot_mapping_sha256": candidate_data.get(
                    "plot_mapping_sha256", ""
                ),
                "saved_reopened": True,
                "native_tif_600dpi_verified": bool(tif_evidence.get("ok")),
                "exact_pixel_match": bool(pixels.get("exact_pixel_match")),
                "same_size": bool(pixels.get("same_size")),
                "changed_pixels": pixels.get("changed_pixels"),
                "rms": pixels.get("rms"),
                "reference_opju_self_replay": False,
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": "failed",
                "message": scrub_output_text(
                    f"Fresh graph-template replay failed: {type(exc).__name__}: {exc}",
                    project_root=project_root,
                ),
                "automated_acceptance_passed": False,
                "source_opju_sha256": source_hash_before,
                "candidate_graph_template_sha256": template_hash_before,
            }
        )
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
    (product_dir / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _merge_replay_worksheet_column_record(
    existing: dict[str, object] | None,
    incoming: dict[str, object],
    *,
    sheet_index: int,
    column_index: int,
) -> dict[str, object]:
    """Merge plotted ranges that share a worksheet column without losing gaps.

    A reference graph can legitimately use a long source column for one plot and
    a shorter overlapping prefix (or another subrange) for a second plot.  The
    fresh replay needs one worksheet column containing the union of those
    ranges.  Values are checked exactly where the ranges overlap; rows between
    non-adjacent ranges remain missing values in the constructed worksheet.
    """
    incoming_from = int(incoming["row_from"])
    incoming_to = int(incoming["row_to"])
    incoming_values = [float(value) for value in list(incoming["values"])]
    incoming_masks = {
        int(row) for row in list(incoming.get("masked_rows") or [])
    }
    if any(row < incoming_from or row > incoming_to for row in incoming_masks):
        raise RuntimeError(
            f"Reference worksheet {sheet_index} column {column_index} has a mask outside its incoming row range."
        )
    if incoming_to - incoming_from + 1 != len(incoming_values):
        raise RuntimeError(
            f"Reference worksheet {sheet_index} column {column_index} has an invalid incoming row range."
        )
    if existing is None:
        return {
            "row_from": incoming_from,
            "row_to": incoming_to,
            "values": incoming_values,
            "masked_rows": sorted(incoming_masks),
            "_covered_rows": frozenset(range(incoming_from, incoming_to + 1)),
        }

    existing_from = int(existing["row_from"])
    existing_to = int(existing["row_to"])
    existing_values = [float(value) for value in list(existing["values"])]
    if existing_to - existing_from + 1 != len(existing_values):
        raise RuntimeError(
            f"Reference worksheet {sheet_index} column {column_index} has an invalid existing row range."
        )
    existing_covered_rows = set(
        existing.get("_covered_rows", range(existing_from, existing_to + 1))
    )
    covered_rows = set(existing_covered_rows)
    existing_masks = {
        int(row) for row in list(existing.get("masked_rows") or [])
    }
    merged_from = min(existing_from, incoming_from)
    merged_to = max(existing_to, incoming_to)
    merged_values = [math.nan] * (merged_to - merged_from + 1)

    for row in covered_rows:
        if existing_from <= row <= existing_to:
            merged_values[row - merged_from] = existing_values[row - existing_from]
    for offset, incoming_value in enumerate(incoming_values):
        row = incoming_from + offset
        slot = row - merged_from
        if row in covered_rows:
            existing_value = merged_values[slot]
            if not _replay_column_values_equal(existing_value, incoming_value):
                raise RuntimeError(
                    f"Reference plots disagree on worksheet {sheet_index} column {column_index} "
                    f"at row {row}: {existing_value!r} != {incoming_value!r}."
                )
        else:
            merged_values[slot] = incoming_value
            covered_rows.add(row)
    incoming_rows = set(range(incoming_from, incoming_to + 1))
    for row in existing_covered_rows & incoming_rows:
        if (row in existing_masks) != (row in incoming_masks):
            raise RuntimeError(
                f"Reference plots disagree on mask state for worksheet {sheet_index} "
                f"column {column_index} at row {row}."
            )
    return {
        "row_from": merged_from,
        "row_to": merged_to,
        "values": merged_values,
        "masked_rows": sorted(existing_masks | incoming_masks),
        "_covered_rows": frozenset(covered_rows),
    }


def _replay_column_values_equal(left: float, right: float) -> bool:
    return math.isnan(left) and math.isnan(right) or left == right


def _fresh_template_axis_title_gate(
    reference_style: object,
    candidate_style: object,
) -> dict[str, object]:
    reference_strings = dict(getattr(reference_style, "audit_string_values", {}) or {})
    candidate_strings = dict(getattr(candidate_style, "audit_string_values", {}) or {})
    reference_numeric = {
        **dict(getattr(reference_style, "layout_values", {}) or {}),
        **dict(getattr(reference_style, "audit_numeric_values", {}) or {}),
    }
    candidate_numeric = {
        **dict(getattr(candidate_style, "layout_values", {}) or {}),
        **dict(getattr(candidate_style, "audit_numeric_values", {}) or {}),
    }
    reference_x_text = str(reference_strings.get("xb.text$", ""))
    candidate_x_text = str(candidate_strings.get("xb.text$", ""))
    reference_y_text = str(reference_strings.get("yl.text$", ""))
    candidate_y_text = str(candidate_strings.get("yl.text$", ""))
    reference_x_normalized = reference_x_text.strip()
    candidate_x_normalized = candidate_x_text.strip()
    reference_y_normalized = reference_y_text.strip()
    candidate_y_normalized = candidate_y_text.strip()

    def _title_text_matches(
        reference_text: str,
        candidate_text: str,
        *,
        dynamic_expression: str,
    ) -> bool:
        # Origin expands %(?X)/%(?Y) when a template is saved and reopened.
        # The expansion is valid only for that exact reference expression;
        # static title text remains an exact (outer-whitespace-normalized)
        # contract.
        if reference_text == dynamic_expression:
            return bool(candidate_text)
        return candidate_text == reference_text

    def _title_rich_text_bold(text: str) -> bool:
        return "\\b(" in text

    gate: dict[str, object] = {
        "reference_x_text": reference_x_text,
        "candidate_x_text": candidate_x_text,
        "reference_y_text": reference_y_text,
        "candidate_y_text": candidate_y_text,
        "x_text_matches": _title_text_matches(
            reference_x_normalized,
            candidate_x_normalized,
            dynamic_expression="%(?X)",
        ),
        "y_text_matches": _title_text_matches(
            reference_y_normalized,
            candidate_y_normalized,
            dynamic_expression="%(?Y)",
        ),
        "x_title_numeric_bold_matches": candidate_numeric.get("xb.bold")
        == reference_numeric.get("xb.bold"),
        "y_title_numeric_bold_matches": candidate_numeric.get("yl.bold")
        == reference_numeric.get("yl.bold"),
        "x_title_rich_text_bold_matches": _title_rich_text_bold(
            candidate_x_normalized
        )
        == _title_rich_text_bold(reference_x_normalized),
        "y_title_rich_text_bold_matches": _title_rich_text_bold(
            candidate_y_normalized
        )
        == _title_rich_text_bold(reference_y_normalized),
        "x_size_matches": candidate_numeric.get("xb.fsize")
        == reference_numeric.get("xb.fsize"),
        "y_size_matches": candidate_numeric.get("yl.fsize")
        == reference_numeric.get("yl.fsize"),
        "x_tick_bold_matches": candidate_numeric.get("layer.x.label.bold")
        == reference_numeric.get("layer.x.label.bold"),
        "y_tick_bold_matches": candidate_numeric.get("layer.y.label.bold")
        == reference_numeric.get("layer.y.label.bold"),
    }
    gate["pass"] = all(
        value is True for key, value in gate.items() if key.endswith("_matches")
    )
    return gate


def _fresh_template_reference_axis_titles_bold(reference_style: object) -> bool:
    """Return whether the reference itself requires the bold-title policy.

    The generic conformance helper only knows how to require bold titles.  A
    fresh template replay must enable that requirement only when both
    reference titles are bold; equality of per-axis bold state is enforced by
    :func:`_fresh_template_axis_title_gate` for every reference template.
    """
    reference_strings = dict(getattr(reference_style, "audit_string_values", {}) or {})
    reference_numeric = {
        **dict(getattr(reference_style, "layout_values", {}) or {}),
        **dict(getattr(reference_style, "audit_numeric_values", {}) or {}),
    }
    return all(
        reference_numeric.get(numeric_field) == 1.0
        or "\\b(" in str(reference_strings.get(text_field, "")).strip()
        for numeric_field, text_field in (("xb.bold", "xb.text$"), ("yl.bold", "yl.text$"))
    )


def _write_fresh_template_replay_failure(
    product_dir: Path,
    base_result: dict[str, object],
    message: str,
) -> dict[str, object]:
    result = {
        **base_result,
        "status": "failed",
        "message": message,
        "automated_acceptance_passed": False,
    }
    (product_dir / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _export_replay_graph(
    operations: object,
    source_opju: Path,
    graph_page: str,
    product_dir: Path,
    label: str,
    *,
    theme_path: Path | None = None,
) -> dict[str, object]:
    runtime_dir = Path(tempfile.mkdtemp(prefix=f"rdop_replay_{safe_origin_name(label, 'Replay')}_"))
    final_png = product_dir / f"{label}.png"
    final_tif = product_dir / f"{label}.tif"
    final_opju_name = f"{product_dir.name}.opju" if label == "project_asset" else f"{label}.opju"
    final_opju = product_dir / final_opju_name
    try:
        for target in (final_png, final_tif, final_opju):
            if target.exists():
                if not target.is_file():
                    return {"ok": False, "message": f"Replay output target is not a file: {target}"}
                target.unlink()
        runtime_opju = runtime_dir / f"{safe_origin_name(label, 'Replay')}{source_opju.suffix}"
        shutil.copy2(source_opju, runtime_opju)
        operations.new_project()
        loaded = operations.load_project(runtime_opju)
        if not getattr(loaded, "ok", False):
            return {"ok": False, "message": getattr(loaded, "message", "Origin project load failed")}
        pages_result = operations.list_worksheets()
        graph_pages = [
            str(page["name"])
            for page in getattr(pages_result, "payload", {}).get("pages", [])
            if isinstance(page, dict) and page.get("type") == "graph"
        ]
        if graph_page not in graph_pages:
            return {
                "ok": False,
                "message": f"Requested graph page does not exist: {graph_page}",
                "requested_graph_page": graph_page,
                "exported_graph_page": "",
                "graph_pages": graph_pages,
                "theme_path": str(theme_path) if theme_path else "",
            }
        graph_name = graph_page
        if theme_path is not None:
            applied = operations.apply_graph_theme(graph_name, theme_path)
            if not getattr(applied, "ok", False):
                return {
                    "ok": False,
                    "message": getattr(applied, "message", "Origin graph theme apply failed"),
                    "requested_graph_page": graph_page,
                    "exported_graph_page": graph_name,
                    "graph_pages": graph_pages,
                    "theme_path": str(theme_path),
                }
        runtime_png = runtime_dir / f"{label}.png"
        runtime_tif = runtime_dir / f"{label}.tif"
        png = operations.export_graph(graph_name, runtime_png, "png", dpi=600)
        tif = _export_replay_tif_with_physical_validation(
            operations,
            graph_name,
            runtime_tif,
            dpi=600,
        )
        export_message = f"{getattr(png, 'message', '')}; {tif.get('message', '')}".strip("; ")
        if not getattr(png, "ok", False) or not bool(tif.get("ok")):
            return {
                "ok": False,
                "message": export_message or "Origin replay graph export failed",
                "requested_graph_page": graph_page,
                "exported_graph_page": graph_name,
                "graph_pages": graph_pages,
                "theme_path": str(theme_path) if theme_path else "",
            }
        missing_runtime = [path for path in (runtime_png, runtime_tif, runtime_opju) if not path.is_file() or path.stat().st_size == 0]
        if missing_runtime:
            return {
                "ok": False,
                "message": "Replay export did not produce nonempty runtime artifacts: " + ", ".join(path.name for path in missing_runtime),
                "requested_graph_page": graph_page,
                "exported_graph_page": graph_name,
                "graph_pages": graph_pages,
                "theme_path": str(theme_path) if theme_path else "",
            }
        shutil.copy2(runtime_png, final_png)
        shutil.copy2(runtime_tif, final_tif)
        shutil.copy2(runtime_opju, final_opju)
        artifacts_ok = all(path.is_file() and path.stat().st_size > 0 for path in (final_png, final_tif, final_opju))
        return {
            "ok": artifacts_ok,
            "message": export_message,
            "requested_graph_page": graph_page,
            "exported_graph_page": graph_name,
            "graph_pages": graph_pages,
            "theme_path": str(theme_path) if theme_path else "",
            "opju": str(final_opju),
            "opju_size": final_opju.stat().st_size if final_opju.exists() else 0,
            "png": str(final_png),
            "png_size": final_png.stat().st_size if final_png.exists() else 0,
            "tif": str(final_tif),
            "tif_size": final_tif.stat().st_size if final_tif.exists() else 0,
            "tif_resolution_evidence": tif.get("evidence", {}),
        }
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)


def _export_replay_tif_with_physical_validation(
    operations: object,
    graph_name: str,
    target: Path,
    *,
    dpi: int,
) -> dict[str, object]:
    activated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if not getattr(activated, "ok", False):
        return {"ok": False, "message": f"Could not activate replay graph {graph_name!r} before TIFF export."}
    dimensions: dict[str, float] = {}
    for name in ("page.width", "page.height"):
        result = operations.get_labtalk_variable(name)
        if not getattr(result, "ok", False):
            return {"ok": False, "message": f"Could not read {name} from replay graph {graph_name!r}."}
        try:
            value = float(getattr(result, "payload", {}).get("value"))
        except (TypeError, ValueError, OverflowError):
            return {"ok": False, "message": f"Replay graph returned an invalid {name} value."}
        if not math.isfinite(value) or value <= 0:
            return {"ok": False, "message": f"Replay graph returned a non-positive {name} value."}
        dimensions[name] = value
    expected_width, _expected_height = expected_raster_pixels(
        dimensions["page.width"],
        dimensions["page.height"],
        dpi=dpi,
    )
    reset_identity = getattr(operations, "reset_project_identity_for_export", None)
    if not callable(reset_identity):
        return {
            "ok": False,
            "message": "Origin project identity reset is unavailable before replay TIFF export.",
        }
    try:
        identity = reset_identity()
    except Exception:
        return {
            "ok": False,
            "message": "Origin project identity reset failed before replay TIFF export.",
        }
    if not getattr(identity, "ok", False):
        return {
            "ok": False,
            "message": "Origin project identity verification failed before replay TIFF export.",
        }
    reactivated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if not getattr(reactivated, "ok", False):
        return {
            "ok": False,
            "message": f"Could not reactivate replay graph {graph_name!r} after project identity reset.",
        }
    exported = operations.export_graph(
        graph_name,
        target,
        "tif",
        dpi=dpi,
        pixel_width=expected_width,
    )
    if not getattr(exported, "ok", False):
        return {"ok": False, "message": getattr(exported, "message", "Origin replay TIFF export failed")}
    try:
        evidence = validate_tif_physical_resolution(
            target,
            page_width_origin_units=dimensions["page.width"],
            page_height_origin_units=dimensions["page.height"],
            dpi=dpi,
        ).as_dict()
    except Exception as exc:
        return {"ok": False, "message": scrub_output_text(str(exc))}
    evidence["path"] = target.name
    return {
        "ok": True,
        "message": "Origin replay TIFF passed physical-resolution validation.",
        "evidence": evidence,
    }


def _compare_replay_pngs(source_png: Path, asset_png: Path, product_dir: Path) -> dict[str, object]:
    from PIL import Image, ImageChops, ImageStat

    source = Image.open(source_png).convert("RGBA")
    asset = Image.open(asset_png).convert("RGBA")
    if source.size != asset.size:
        return {
            "image_size": list(source.size),
            "asset_image_size": list(asset.size),
            "same_size": False,
            "changed_pixels": None,
            "exact_pixel_match": False,
            "rms": math.inf,
            "diff_bbox": "size_mismatch",
        }
    diff = ImageChops.difference(source, asset)
    stat = ImageStat.Stat(diff)
    rms = math.sqrt(sum(value * value for value in stat.rms))
    # Pillow's RGBA ``getbbox()`` can return ``None`` when RGB channels differ
    # but the alpha-difference band is entirely zero.  Collapse all decoded
    # channels into one non-zero mask so opaque color changes cannot be
    # misclassified as an exact match.
    diff_bands = diff.split()
    change_mask = diff_bands[0]
    for band in diff_bands[1:]:
        change_mask = ImageChops.lighter(change_mask, band)
    bbox = change_mask.getbbox()
    changed_pixels = 0 if bbox is None else sum(change_mask.histogram()[1:])
    side_by_side = product_dir / "side_by_side.png"
    side = Image.new("RGBA", (source.width * 2, source.height), "white")
    side.paste(source, (0, 0))
    side.paste(asset, (source.width, 0))
    side.save(side_by_side)
    return {
        "image_size": list(source.size),
        "asset_image_size": list(asset.size),
        "same_size": True,
        "changed_pixels": changed_pixels,
        "rms": float(rms),
        "diff_bbox": list(bbox) if bbox else None,
        "exact_pixel_match": bbox is None and rms == 0.0,
        "side_by_side_png": str(side_by_side),
    }


def _write_replay_summary(output_dir: Path, summary: dict[str, object]) -> None:
    summary_json = output_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = summary.get("items") if isinstance(summary.get("items"), list) else []
    summary_csv = output_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["product_key", "data_type", "status", "graph_page", "rms", "exact_pixel_match", "message"],
        )
        writer.writeheader()
        for row in rows:
            if not isinstance(row, dict):
                continue
            comparison = row.get("comparison") if isinstance(row.get("comparison"), dict) else {}
            writer.writerow(
                {
                    "product_key": row.get("product_key", ""),
                    "data_type": row.get("data_type", ""),
                    "status": row.get("status", ""),
                    "graph_page": row.get("graph_page", ""),
                    "rms": comparison.get("rms", ""),
                    "exact_pixel_match": comparison.get("exact_pixel_match", ""),
                    "message": row.get("message", ""),
                }
            )


def read_graph_data_snapshot(
    operations: object,
    graph_page: str,
    *,
    source_label: str = "",
    sheet_name: str = "Sheet1",
    max_layers: int = 12,
    prefer_custom_rgb: bool = False,
) -> dict[str, object]:
    plots: list[dict[str, object]] = []
    layers: list[dict[str, object]] = []
    worksheet_cache: dict[tuple[str, int], dict[str, object]] = {}
    mask_cache: dict[tuple[str, int, int], dict[str, object]] = {}
    layer_limit = max_layers
    count_reader = getattr(operations, "get_graph_layer_count", None)
    if callable(count_reader):
        count_result = count_reader(graph_page)
        if getattr(count_result, "ok", False):
            layer_limit = min(max_layers, int(count_result.payload["layer_count"]))
        else:
            layer_limit = 0
    for layer_index in range(1, layer_limit + 1):
        result = operations.get_graph_plot_dataset_names(graph_page, layer_index=layer_index)
        if not getattr(result, "ok", False):
            continue
        result_payload = dict(getattr(result, "payload", {}) or {})
        names = [str(name) for name in result_payload.get("plot_dataset_names", []) if str(name).strip()]
        if not names:
            continue
        explicit_plot_mappings = _read_explicit_plot_mappings(
            operations,
            graph_page,
            layer_index,
            names,
            result_payload,
        )
        layer_plots: list[dict[str, object]] = []
        for plot_index, dataset in enumerate(names, start=1):
            plot_record = _graph_plot_data_record(
                operations,
                graph_page,
                layer_index,
                plot_index,
                dataset,
                worksheet_cache,
                sheet_name=sheet_name,
                explicit_mapping=explicit_plot_mappings.get((plot_index, dataset)),
                prefer_custom_rgb=prefer_custom_rgb,
                mask_cache=mask_cache,
            )
            plots.append(plot_record)
            layer_plots.append(plot_record)
        layers.append(
            {
                "layer_index": layer_index,
                "plot_count": len(layer_plots),
                "plot_datasets": [str(plot["y_dataset"]) for plot in layer_plots],
            }
        )
    failed_plots = [plot for plot in plots if plot.get("status") != "ready"]
    data_digest_rows = [
        {
            "layer_index": plot.get("layer_index"),
            "plot_index": plot.get("plot_index"),
            "xy_data_sha256": plot.get("xy_data_sha256"),
            "mask_data_sha256": plot.get("mask_data_sha256"),
        }
        for plot in plots
        if plot.get("status") == "ready"
    ]
    mapping_digest_rows = [
        {
            "layer_index": plot.get("layer_index"),
            "plot_index": plot.get("plot_index"),
            "x_dataset": plot.get("x_dataset"),
            "y_dataset": plot.get("y_dataset"),
            "x_mapping_source": plot.get("x_mapping_source"),
            "plot_row_from": plot.get("plot_row_from"),
            "plot_row_to": plot.get("plot_row_to"),
        }
        for plot in plots
        if plot.get("status") == "ready"
    ]
    plot_values_sha256 = _stable_json_sha256(data_digest_rows) if data_digest_rows else ""
    plot_mapping_sha256 = _stable_json_sha256(mapping_digest_rows) if mapping_digest_rows else ""
    return {
        "schema_version": 3,
        "status": "ready" if plots and not failed_plots else "failed",
        "source_opju": source_label,
        "graph_page": graph_page,
        "sheet_name": sheet_name,
        "layer_count_with_plots": len(layers),
        "plot_count": len(plots),
        "layers": layers,
        "plots": plots,
        "plot_values_sha256": plot_values_sha256,
        "plot_mapping_sha256": plot_mapping_sha256,
        "plot_data_sha256": _stable_json_sha256(
            {"values": plot_values_sha256, "mapping": plot_mapping_sha256}
        )
        if data_digest_rows
        else "",
        "mapping_failure_count": len(failed_plots),
        "mapping_policy": "Use Origin range -wx/-wy plus nameof(range)$ first, preserving @sheet creation indices and plotted row bounds; worksheet designations/findX are diagnostic fallbacks only and cannot prove same-data exact replay.",
        "same_data_exact_requirement": "Reference and generated graphs must have identical plot_values_sha256 and plot_mapping_sha256 values from explicit Origin plotdata X/Y readback before pixel equality may be accepted as one-to-one evidence.",
    }


def compare_graph_data_snapshots(
    reference: dict[str, object],
    generated: dict[str, object],
    *,
    require_explicit_plotdata_mapping: bool = True,
) -> dict[str, object]:
    """Verify that two graph snapshots use the same plotted data and mapping."""

    reasons: list[str] = []
    for label, snapshot in (("reference", reference), ("generated", generated)):
        try:
            schema_version = int(snapshot.get("schema_version", 0) or 0)
        except (TypeError, ValueError):
            schema_version = 0
        if schema_version != 3:
            reasons.append(f"{label} graph data snapshot is not schema_version 3")
    if str(reference.get("status") or "") != "ready":
        reasons.append("reference graph data snapshot is not ready")
    if str(generated.get("status") or "") != "ready":
        reasons.append("generated graph data snapshot is not ready")
    for field in ("plot_count", "layer_count_with_plots"):
        if reference.get(field) != generated.get(field):
            reasons.append(f"{field} differs")

    reference_values_hash = str(reference.get("plot_values_sha256") or "")
    generated_values_hash = str(generated.get("plot_values_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", reference_values_hash):
        reasons.append("reference plot-values hash is missing or malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", generated_values_hash):
        reasons.append("generated plot-values hash is missing or malformed")
    if reference_values_hash and generated_values_hash and reference_values_hash != generated_values_hash:
        reasons.append("plotted X/Y values differ")

    reference_mapping_hash = str(reference.get("plot_mapping_sha256") or "")
    generated_mapping_hash = str(generated.get("plot_mapping_sha256") or "")
    if reference_mapping_hash != generated_mapping_hash:
        reasons.append("plot X/Y dataset mapping differs")

    plot_records: dict[str, dict[tuple[int, int], dict[str, object]]] = {}
    for label, snapshot in (("reference", reference), ("generated", generated)):
        indexed: dict[tuple[int, int], dict[str, object]] = {}
        raw_plots = snapshot.get("plots")
        if not isinstance(raw_plots, list) or not raw_plots:
            reasons.append(f"{label} plot records are missing")
            plot_records[label] = indexed
            continue
        for raw in raw_plots:
            if not isinstance(raw, dict):
                reasons.append(f"{label} contains a non-object plot record")
                continue
            try:
                key = (int(raw.get("layer_index")), int(raw.get("plot_index")))
            except (TypeError, ValueError):
                reasons.append(f"{label} plot record lacks numeric layer/plot identity")
                continue
            if key in indexed:
                reasons.append(f"{label} contains duplicate plot identity {key}")
                continue
            indexed[key] = raw
            for hash_field in ("x_data_sha256", "y_data_sha256", "xy_data_sha256"):
                if re.fullmatch(r"[0-9a-f]{64}", str(raw.get(hash_field) or "")) is None:
                    reasons.append(f"{label} plot {key} has no valid {hash_field}")
        plot_records[label] = indexed

    reference_plots = plot_records.get("reference", {})
    generated_plots = plot_records.get("generated", {})
    if set(reference_plots) != set(generated_plots):
        reasons.append("layer/plot identities differ")
    for key in sorted(set(reference_plots) & set(generated_plots)):
        reference_plot = reference_plots[key]
        generated_plot = generated_plots[key]
        for field, message in (
            ("x_data_sha256", "X values differ"),
            ("y_data_sha256", "Y values differ"),
            ("xy_data_sha256", "paired X/Y values differ"),
            ("mask_data_sha256", "worksheet mask state differs"),
            ("x_masked_rows", "X mask rows differ"),
            ("y_masked_rows", "Y mask rows differ"),
            ("plot_row_from", "displayed row start differs"),
            ("plot_row_to", "displayed row end differs"),
            ("row_count", "displayed row count differs"),
        ):
            if reference_plot.get(field) != generated_plot.get(field):
                reasons.append(f"plot {key} {message}")

    if require_explicit_plotdata_mapping:
        for label, snapshot in (("reference", reference), ("generated", generated)):
            plots = snapshot.get("plots")
            if not isinstance(plots, list) or not plots:
                continue
            fallback_indices = [
                str(plot.get("plot_index") or "?")
                for plot in plots
                if not isinstance(plot, dict)
                or str(plot.get("x_mapping_source") or "") != "graph_plot_mapping"
                or str(plot.get("plot_row_range_source") or "") != "graph_plot_mapping"
            ]
            if fallback_indices:
                reasons.append(
                    f"{label} plots lack explicit Origin plotdata X/Y readback: "
                    + ", ".join(fallback_indices)
                )

    return {
        "status": "matched" if not reasons else "mismatch",
        "same_data": not reasons,
        "reference_plot_values_sha256": reference_values_hash,
        "generated_plot_values_sha256": generated_values_hash,
        "reference_plot_mapping_sha256": reference_mapping_hash,
        "generated_plot_mapping_sha256": generated_mapping_hash,
        "reasons": reasons,
    }


def _graph_plot_data_record(
    operations: object,
    graph_page: str,
    layer_index: int,
    plot_index: int,
    dataset: str,
    worksheet_cache: dict[tuple[str, int], dict[str, object]],
    *,
    sheet_name: str,
    explicit_mapping: dict[str, object] | None = None,
    prefer_custom_rgb: bool = False,
    mask_cache: dict[tuple[str, int, int], dict[str, object]] | None = None,
) -> dict[str, object]:
    parsed = parse_origin_dataset_reference(dataset)
    base = {
        "graph_page": graph_page,
        "layer_index": int(layer_index),
        "plot_index": int(plot_index),
        "y_dataset": dataset,
    }
    if parsed is None:
        return {**base, "status": "unparsed_dataset_name"}
    book_name = parsed.book_name
    y_col_index = parsed.column_index
    y_sheet_index = parsed.sheet_index
    y_worksheet = _cached_worksheet_data(
        operations,
        worksheet_cache,
        book_name,
        y_sheet_index,
        default_sheet_name=sheet_name,
    )
    if not y_worksheet.get("ok"):
        return {
            **base,
            "status": "worksheet_read_failed",
            "book_name": book_name,
            "sheet_name": str(y_sheet_index),
            "sheet_index": y_sheet_index,
            "message": str(y_worksheet.get("message") or ""),
        }
    y_columns = list(y_worksheet.get("columns", []))
    actual_sheet_name = str(y_worksheet.get("sheet_name") or "")

    mapping_source = ""
    explicit_x_dataset = str((explicit_mapping or {}).get("x_dataset") or "").strip()
    if explicit_x_dataset:
        parsed_x = parse_origin_dataset_reference(explicit_x_dataset)
        if parsed_x is None:
            return {
                **base,
                "status": "x_mapping_invalid",
                "book_name": book_name,
                "sheet_name": actual_sheet_name,
                "x_dataset_readback": explicit_x_dataset,
                "message": "explicit graph plot X dataset name could not be parsed",
            }
        x_book_name = parsed_x.book_name
        x_col_index = parsed_x.column_index
        x_sheet_index = parsed_x.sheet_index
        mapping_source = "graph_plot_mapping"
    else:
        resolved_x = _resolve_corresponding_x_column(
            operations,
            book_name,
            actual_sheet_name,
            y_col_index,
        )
        if resolved_x is None:
            return {
                **base,
                "status": "x_mapping_unavailable",
                "book_name": book_name,
                "sheet_name": actual_sheet_name,
                "y_col_index": y_col_index,
                "message": "Origin plot mapping, worksheet designation, and wks.col.findX() readback were unavailable",
            }
        x_col_index, mapping_source = resolved_x
        x_book_name = book_name
        x_sheet_index = y_sheet_index

    x_worksheet = (
        y_worksheet
        if x_book_name == book_name and x_sheet_index == y_sheet_index
        else _cached_worksheet_data(
            operations,
            worksheet_cache,
            x_book_name,
            x_sheet_index,
            default_sheet_name=sheet_name,
        )
    )
    if not x_worksheet.get("ok"):
        return {
            **base,
            "status": "x_worksheet_read_failed",
            "book_name": book_name,
            "sheet_name": actual_sheet_name,
            "x_book_name": x_book_name,
            "x_sheet_index": x_sheet_index,
            "message": str(x_worksheet.get("message") or ""),
        }
    x_columns = list(x_worksheet.get("columns", []))
    x_sheet_name = str(x_worksheet.get("sheet_name") or "")
    if y_col_index >= len(y_columns) or x_col_index >= len(x_columns):
        return {
            **base,
            "status": "column_missing",
            "book_name": book_name,
            "sheet_name": actual_sheet_name,
            "x_book_name": x_book_name,
            "x_col_index": x_col_index,
            "y_col_index": y_col_index,
            "available_y_columns": len(y_columns),
            "available_x_columns": len(x_columns),
        }
    x_values = [_json_safe_value(value) for value in x_columns[x_col_index]]
    y_values = [_json_safe_value(value) for value in y_columns[y_col_index]]
    available_row_count = min(len(x_values), len(y_values))
    raw_row_from = (explicit_mapping or {}).get("row_from")
    raw_row_to = (explicit_mapping or {}).get("row_to")
    try:
        plot_row_from = int(raw_row_from) if raw_row_from is not None else 1
        plot_row_to = int(raw_row_to) if raw_row_to is not None else available_row_count
    except (TypeError, ValueError):
        plot_row_from = 0
        plot_row_to = -1
    if (
        plot_row_from < 1
        or plot_row_to < plot_row_from
        or plot_row_to > available_row_count
    ):
        return {
            **base,
            "status": "plot_row_range_invalid",
            "book_name": book_name,
            "sheet_name": actual_sheet_name,
            "x_dataset": explicit_x_dataset,
            "plot_row_from": plot_row_from,
            "plot_row_to": plot_row_to,
            "available_row_count": available_row_count,
        }
    start = plot_row_from - 1
    stop = plot_row_to
    x_values = x_values[start:stop]
    y_values = y_values[start:stop]
    row_count = len(x_values)
    x_dataset = explicit_x_dataset or _format_origin_dataset_reference(
        x_book_name,
        x_col_index,
        x_sheet_index,
    )
    x_masks = _read_dataset_mask_rows(
        operations,
        x_dataset,
        row_from=plot_row_from,
        row_to=plot_row_to,
        cache=mask_cache,
    )
    y_masks = _read_dataset_mask_rows(
        operations,
        dataset,
        row_from=plot_row_from,
        row_to=plot_row_to,
        cache=mask_cache,
    )
    x_masked_rows = list(x_masks.get("masked_rows", []))
    y_masked_rows = list(y_masks.get("masked_rows", []))
    mask_payload = {
        "x_masked_rows": x_masked_rows,
        "y_masked_rows": y_masked_rows,
    }
    _activate_graph_layer_for_style_readback(operations, graph_page, layer_index)
    return {
        **base,
        "status": "ready",
        "book_name": book_name,
        "sheet_name": actual_sheet_name,
        "sheet_index": y_sheet_index,
        "x_dataset": x_dataset,
        "x_book_name": x_book_name,
        "x_sheet_name": x_sheet_name,
        "x_sheet_index": x_sheet_index,
        "x_mapping_source": mapping_source,
        "x_col_index": x_col_index,
        "y_col_index": y_col_index,
        "x_col_letter": _origin_column_letters(x_col_index),
        "y_col_letter": _origin_column_letters(y_col_index),
        "row_count": row_count,
        "plot_row_from": plot_row_from,
        "plot_row_to": plot_row_to,
        "plot_row_range_source": (
            "graph_plot_mapping"
            if raw_row_from is not None and raw_row_to is not None
            else "full_worksheet_fallback"
        ),
        "mask_readback_status": (
            "ready"
            if x_masks.get("status") == "ready" and y_masks.get("status") == "ready"
            else "unavailable"
        ),
        "x_masked_rows": x_masked_rows,
        "y_masked_rows": y_masked_rows,
        "mask_data_sha256": _stable_json_sha256(mask_payload),
        "style": _read_plot_style_properties(
            operations,
            dataset,
            prefer_custom_rgb=prefer_custom_rgb,
        ),
        "x_values": x_values,
        "y_values": y_values,
        "x_data_sha256": _stable_json_sha256(x_values),
        "y_data_sha256": _stable_json_sha256(y_values),
        "xy_data_sha256": _stable_json_sha256(
            {"x": x_values, "y": y_values, **mask_payload}
        ),
    }


def _read_dataset_mask_rows(
    operations: object,
    dataset: str,
    *,
    row_from: int,
    row_to: int,
    cache: dict[tuple[str, int, int], dict[str, object]] | None = None,
) -> dict[str, object]:
    # The cache belongs to one immutable graph readback; no result survives a
    # save/reopen, worksheet replacement, or another snapshot.
    key = (dataset, int(row_from), int(row_to))
    if cache is not None and key in cache:
        return cache[key]
    result = _read_dataset_mask_rows_uncached(
        operations, dataset, row_from=row_from, row_to=row_to,
    )
    if cache is not None and result.get("status") == "ready":
        cache[key] = result
    return result


def _read_dataset_mask_rows_uncached(
    operations: object,
    dataset: str,
    *,
    row_from: int,
    row_to: int,
) -> dict[str, object]:
    if parse_origin_dataset_reference(dataset) is None:
        return {"status": "unavailable", "masked_rows": []}
    variable = "__rdop_mask_state"
    try:
        counted = operations.run_labtalk(f"{variable}=ismasked(0,{dataset});")
        if not getattr(counted, "ok", False):
            return {"status": "unavailable", "masked_rows": []}
        raw_count = operations.get_labtalk_variable(variable).payload.get("value")
        count = int(round(float(raw_count)))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return {"status": "unavailable", "masked_rows": []}
    if count <= 0:
        return {"status": "ready", "masked_rows": [], "dataset_mask_count": 0}
    masked_rows = _read_mask_rows_in_blocks(
        operations, dataset, row_from=row_from, row_to=row_to,
    )
    if masked_rows is None:
        # Preserve the existing reader for older COM/LabTalk bridges. A failed
        # block is never accepted as an all-unmasked range.
        masked_rows = _read_mask_rows_individually(
            operations, dataset, row_from=row_from, row_to=row_to,
        )
    if masked_rows is None:
        return {"status": "unavailable", "masked_rows": []}
    return {"status": "ready", "masked_rows": masked_rows, "dataset_mask_count": count}


def _read_mask_rows_in_blocks(
    operations: object,
    dataset: str,
    *,
    row_from: int,
    row_to: int,
) -> list[int] | None:
    masked_rows: list[int] = []
    for start in range(row_from, row_to + 1, 512):
        stop = min(start + 511, row_to)
        script = (
            'string rdmask$=""; '
            f'for(rdmi={start};rdmi<={stop};rdmi++) {{ '
            f'if(ismasked(rdmi,{dataset})) {{ rdmask$=rdmask$+"1"; }} '
            'else { rdmask$=rdmask$+"0"; } };'
        )
        try:
            read = operations.run_labtalk(script)
            if not getattr(read, "ok", False):
                return None
            bits = operations.get_labtalk_variable("rdmask$").payload.get("value")
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
        if not isinstance(bits, str) or len(bits) != stop - start + 1 or set(bits) - {"0", "1"}:
            return None
        masked_rows.extend(start + offset for offset, bit in enumerate(bits) if bit == "1")
    return masked_rows


def _read_mask_rows_individually(
    operations: object,
    dataset: str,
    *,
    row_from: int,
    row_to: int,
) -> list[int] | None:
    variable = "__rdop_mask_state"
    masked_rows: list[int] = []
    for row in range(int(row_from), int(row_to) + 1):
        try:
            read = operations.run_labtalk(
                f"{variable}=ismasked({row},{dataset});"
            )
            if not getattr(read, "ok", False):
                return None
            raw_state = getattr(
                operations.get_labtalk_variable(variable),
                "payload",
                {},
            ).get("value")
            state = int(round(float(raw_state)))
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
        if state:
            masked_rows.append(row)
    return masked_rows


def _read_explicit_plot_mappings(
    operations: object,
    graph_page: str,
    layer_index: int,
    plot_dataset_names: list[str],
    initial_payload: dict[str, object],
) -> dict[tuple[int, str], dict[str, object]]:
    payloads = [initial_payload]
    for method_name in ("get_graph_plot_dataset_mappings", "get_graph_plot_xy_mappings"):
        method = getattr(operations, method_name, None)
        if method is None:
            continue
        try:
            result = method(graph_page, layer_index=layer_index)
        except Exception:
            continue
        if getattr(result, "ok", False):
            payloads.append(dict(getattr(result, "payload", {}) or {}))

    resolved: dict[tuple[int, str], dict[str, object]] = {}
    for payload in payloads:
        for key in ("plot_x_dataset_names", "x_dataset_names"):
            x_names = payload.get(key)
            if not isinstance(x_names, (list, tuple)):
                continue
            for index, value in enumerate(x_names, start=1):
                if index <= len(plot_dataset_names) and str(value).strip():
                    dataset = plot_dataset_names[index - 1]
                    resolved.setdefault(
                        (index, dataset),
                        {"plot_index": index, "x_dataset": str(value).strip(), "y_dataset": dataset},
                    )

        for key in ("plot_mappings", "plot_dataset_mappings", "plot_xy_mappings", "plots"):
            mappings = payload.get(key)
            if isinstance(mappings, dict):
                mappings = [
                    {"y_dataset": y_dataset, "x_dataset": x_dataset}
                    for y_dataset, x_dataset in mappings.items()
                ]
            if not isinstance(mappings, (list, tuple)):
                continue
            for row in mappings:
                if not isinstance(row, dict):
                    continue
                x_dataset = str(row.get("x_dataset") or row.get("x") or "").strip()
                y_dataset = str(row.get("y_dataset") or row.get("y") or "").strip()
                if not x_dataset:
                    continue
                raw_index = row.get("plot_index")
                try:
                    plot_index = int(raw_index) if raw_index is not None else 0
                except (TypeError, ValueError):
                    plot_index = 0
                if plot_index < 1 and y_dataset in plot_dataset_names:
                    plot_index = plot_dataset_names.index(y_dataset) + 1
                if 1 <= plot_index <= len(plot_dataset_names):
                    dataset = plot_dataset_names[plot_index - 1]
                    if not y_dataset or y_dataset == dataset:
                        candidate = {
                            "plot_index": plot_index,
                            "x_dataset": x_dataset,
                            "y_dataset": dataset,
                            "row_from": row.get("row_from"),
                            "row_to": row.get("row_to"),
                            "row_count": row.get("row_count"),
                        }
                        key = (plot_index, dataset)
                        existing = resolved.get(key)
                        candidate_has_range = (
                            candidate.get("row_from") is not None
                            and candidate.get("row_to") is not None
                        )
                        existing_has_range = bool(
                            existing
                            and existing.get("row_from") is not None
                            and existing.get("row_to") is not None
                        )
                        if existing is None or (candidate_has_range and not existing_has_range):
                            resolved[key] = candidate
    return resolved


def _cached_worksheet_data(
    operations: object,
    worksheet_cache: dict[tuple[str, int], dict[str, object]],
    book_name: str,
    sheet_index: int,
    *,
    default_sheet_name: str,
) -> dict[str, object]:
    cache_key = (book_name, int(sheet_index))
    cached = worksheet_cache.get(cache_key)
    if cached is not None:
        return {"ok": True, **cached}
    read = _read_worksheet_data_with_fallback(
        operations,
        book_name,
        str(int(sheet_index)),
        default_sheet_name=default_sheet_name if int(sheet_index) == 1 else "",
    )
    if not getattr(read, "ok", False):
        return {"ok": False, "message": str(getattr(read, "message", ""))}
    payload = dict(getattr(read, "payload", {}) or {})
    cached = {
        "columns": list(payload.get("columns", [])),
        "sheet_name": str(payload.get("sheet_name") or ""),
    }
    worksheet_cache[cache_key] = cached
    return {"ok": True, **cached}


def _resolve_corresponding_x_column(
    operations: object,
    book_name: str,
    sheet_name: str,
    y_col_index: int,
) -> tuple[int, str] | None:
    designation_index = _x_column_from_designations(operations, book_name, sheet_name, y_col_index)
    if designation_index is not None:
        return designation_index, "worksheet_column_designations"
    findx_index = _x_column_from_origin_findx(operations, book_name, sheet_name, y_col_index)
    if findx_index is not None:
        return findx_index, "origin_wks_col_findx"
    return None


def _x_column_from_designations(
    operations: object,
    book_name: str,
    sheet_name: str,
    y_col_index: int,
) -> int | None:
    method = getattr(operations, "get_worksheet_column_designations", None)
    if method is None:
        return None
    try:
        result = method(book_name, sheet_name)
    except Exception:
        return None
    if not getattr(result, "ok", False):
        return None
    payload = dict(getattr(result, "payload", {}) or {})
    designations = payload.get("column_designations", payload.get("designations", payload.get("column_types")))
    if not isinstance(designations, (list, tuple)) or y_col_index >= len(designations):
        return None
    if _normalized_column_designation(designations[y_col_index]) != "Y":
        return None
    for index in range(y_col_index - 1, -1, -1):
        if _normalized_column_designation(designations[index]) == "X":
            return index
    return None


def _normalized_column_designation(value: object) -> str:
    numeric = _to_float(value) if not isinstance(value, bool) else None
    if numeric is not None:
        number = int(numeric)
        if numeric == number:
            return {1: "Y", 4: "X"}.get(number, "")
    text = str(value or "").strip().upper()
    return text if text in {"X", "Y"} else ""


def _x_column_from_origin_findx(
    operations: object,
    book_name: str,
    sheet_name: str,
    y_col_index: int,
) -> int | None:
    runner = getattr(operations, "run_labtalk", None)
    getter = getattr(operations, "get_labtalk_variable", None)
    if runner is None or getter is None:
        return None
    sheet_reference = sheet_name or "1"
    if any(token in book_name for token in "[]!;") or any(token in sheet_reference for token in "[]!;"):
        return None
    variable = "__rdop_snapshot_x_col"
    script = (
        f"{variable}=nan; range __rdop_snapshot_wks=[{book_name}]{sheet_reference}!; "
        f"{variable}=__rdop_snapshot_wks.col{int(y_col_index) + 1}.findX();"
    )
    try:
        executed = runner(script)
        if not getattr(executed, "ok", False):
            return None
        read = getter(variable)
        value = _to_float(getattr(read, "payload", {}).get("value"))
    except Exception:
        return None
    if value is None:
        return None
    one_based = int(round(value))
    if one_based < 1 or abs(value - one_based) > 1e-6:
        return None
    return one_based - 1


def _read_worksheet_data_with_fallback(
    operations: object,
    book_name: str,
    sheet_name: str,
    *,
    default_sheet_name: str = "",
) -> object:
    attempts: list[str] = []
    for candidate in (sheet_name, default_sheet_name, ""):
        if candidate in attempts:
            continue
        attempts.append(candidate)
        read = operations.get_worksheet_data(book_name, candidate)
        if getattr(read, "ok", False):
            payload = dict(getattr(read, "payload", {}) or {})
            payload["sheet_name"] = candidate
            return type(read)(getattr(read, "ok", False), getattr(read, "message", ""), payload)
    return read


def _activate_graph_layer_for_style_readback(operations: object, graph_page: str, layer_index: int) -> None:
    runner = getattr(operations, "run_labtalk", None)
    if runner is None:
        return
    try:
        runner(f'win -a "{quote_labtalk(graph_page)}"; layer -s {int(layer_index)};')
    except Exception:
        return


def _origin_column_letters(zero_based_index: int) -> str:
    value = int(zero_based_index) + 1
    if value <= 0:
        return ""
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _format_origin_dataset_reference(
    book_name: str,
    zero_based_column_index: int,
    sheet_index: int,
) -> str:
    suffix = f"@{int(sheet_index)}" if int(sheet_index) != 1 else ""
    return f"{book_name}_{_origin_column_letters(zero_based_column_index)}{suffix}"


def _stable_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json_safe_value(value: object) -> object:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text if text else None
    return number if math.isfinite(number) else None


def _read_plot_style_properties(
    operations: object,
    dataset: str,
    *,
    prefer_custom_rgb: bool = False,
) -> dict[str, float]:
    if not hasattr(operations, "run_labtalk") or not hasattr(operations, "get_labtalk_variable"):
        return {}
    # Legacy snapshot fields alias the same Origin property. Query each option
    # once and retain every original output key for schema compatibility.
    options = list(dict.fromkeys(PLOT_STYLE_READBACK_OPTIONS.values()))
    if prefer_custom_rgb:
        options.append("-cse")
    values: dict[str, float] = {}
    variable = "__rdop_plot_style_value"
    for option in options:
        try:
            result = operations.run_labtalk(f"{variable}=nan; get {dataset} {option} {variable};")
            if not getattr(result, "ok", False):
                continue
            read = operations.get_labtalk_variable(variable)
            safe = _json_safe_value(getattr(read, "payload", {}).get("value"))
        except Exception:
            continue
        if isinstance(safe, float):
            values[option] = safe
    style = {
        key: values[option]
        for key, option in PLOT_STYLE_READBACK_OPTIONS.items()
        if option in values
    }
    symbol_edge = values.get("-cse")
    if symbol_edge is not None and 0x01000000 <= int(round(symbol_edge)) <= 0x01FFFFFF:
        style["color"] = symbol_edge
    return style


def _merge_origin_style_manifest_entries(manifest_path: Path, new_entries: list[dict[str, object]]) -> list[dict[str, object]]:
    if not manifest_path.is_file():
        return new_entries
    existing = load_origin_style_manifest(manifest_path.parent, manifest_path)
    existing_entries = existing["assets"]
    by_key: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for entry in existing_entries:
        if not isinstance(entry, dict):
            continue
        key = _entry_key(entry)
        if not key:
            continue
        by_key[key] = dict(entry)
        if key not in order:
            order.append(key)
    for entry in new_entries:
        key = _entry_key(entry)
        if not key:
            continue
        previous = by_key.get(key, {})
        merged = dict(previous)
        clear_previous_previews = _preview_fields_should_clear(entry)
        for field, value in entry.items():
            if clear_previous_previews and field in DIRECT_TEMPLATE_CLEARABLE_FIELDS:
                merged[field] = value
            elif value not in ("", None):
                merged[field] = value
            elif field not in merged:
                merged[field] = value
        by_key[key] = merged
        if key not in order:
            order.append(key)
    return [by_key[key] for key in order if key in by_key]


def _origin_style_manifest_schema_version_for_write(manifest_path: Path) -> int:
    if not manifest_path.is_file():
        return 2
    manifest = load_origin_style_manifest(manifest_path.parent, manifest_path)
    return int(manifest["schema_version"])


def _origin_style_manifest_for_write(manifest_path: Path) -> dict[str, object]:
    if not manifest_path.is_file():
        return {}
    return dict(load_origin_style_manifest(manifest_path.parent, manifest_path))


def _preview_fields_should_clear(entry: dict[str, object]) -> bool:
    return str(entry.get("source_mode") or "") == "direct_template_opju"


def _entry_key(entry: dict[str, object]) -> str:
    return _type_key(str(entry.get("product_key") or entry.get("data_type") or ""))


def _accepted_comparison_items(run_root: Path) -> dict[str, dict[str, object]]:
    path = run_root / "reports" / "template_preview_comparison.json"
    if not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    items = loaded.get("items") if isinstance(loaded, dict) else []
    accepted: dict[str, dict[str, object]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        product_type = str(item.get("type") or "")
        if product_type and item.get("status") == "accepted" and (bool(item.get("ready")) or bool(item.get("strict_visual_match"))):
            accepted[product_type] = item
    return accepted


def _metadata_for_product(run_root: Path, product_type: str) -> dict[str, Any]:
    product_dir = _product_dir_for_type(run_root, product_type)
    if product_dir is None:
        return {}
    metadata_dir = product_dir / "metadata"
    if not metadata_dir.exists():
        return {}
    candidates = [*sorted(metadata_dir.rglob("metadata.json")), *sorted(metadata_dir.glob("*.json"))]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and loaded.get("origin_file") and loaded.get("product_key"):
            loaded["__metadata_file"] = str(path)
            loaded["__product_dir"] = str(product_dir)
            return loaded
    return {}


def _product_dir_for_type(run_root: Path, product_type: str) -> Path | None:
    direct = run_root / _type_key(product_type)
    if direct.exists():
        return direct
    requested = _type_key(product_type)
    for child in run_root.iterdir() if run_root.exists() else []:
        if child.is_dir() and _type_key(child.name) == requested:
            return child
    return None


def _graph_page_from_metadata(metadata: dict[str, Any]) -> str:
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    return str(origin_status.get("reopened_graph") or metadata.get("template_graph") or "").strip()


def _theme_graph_page_from_metadata(metadata: dict[str, Any]) -> str:
    external_preview = metadata.get("external_reference_preview") if isinstance(metadata.get("external_reference_preview"), dict) else {}
    if external_preview.get("ok") and str(external_preview.get("graph_page") or "").strip():
        return str(external_preview.get("graph_page")).strip()
    external_template = metadata.get("external_reference_template") if isinstance(metadata.get("external_reference_template"), dict) else {}
    if external_template.get("selected") and str(external_template.get("graph_page") or "").strip():
        return str(external_template.get("graph_page")).strip()
    return _graph_page_from_metadata(metadata)


def _theme_source_opju_from_metadata(run_root: Path, metadata: dict[str, Any]) -> Path | None:
    external_preview = metadata.get("external_reference_preview") if isinstance(metadata.get("external_reference_preview"), dict) else {}
    external_template = metadata.get("external_reference_template") if isinstance(metadata.get("external_reference_template"), dict) else {}
    for value in (
        external_preview.get("source_opju"),
        external_template.get("source_opju"),
    ):
        path = _run_artifact_path(run_root, value)
        if path is not None:
            return path
    return None


def _type_key(product_type: str) -> str:
    text = str(product_type).casefold()
    return "".join(char if char.isalnum() else "_" for char in text).strip("_").replace("__", "_").replace("__", "_")


def _existing_path(value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_file() else None


def _metadata_artifact_path(product_dir: Path, value: object, preferred_dir: str) -> Path | None:
    direct = _existing_path(value)
    if direct is not None:
        return direct
    text = str(value or "").strip()
    if not text or not product_dir.exists():
        return None
    name = Path(text).name
    if not name:
        return None
    preferred = product_dir / preferred_dir / name
    if preferred.is_file():
        return preferred
    matches = sorted(path for path in product_dir.rglob(name) if path.is_file())
    return matches[0] if matches else None


def _run_artifact_path(run_root: Path, value: object) -> Path | None:
    direct = _existing_path(value)
    if direct is not None:
        return direct
    text = str(value or "").strip()
    if not text:
        return None
    path = run_root / text
    return path if path.is_file() else None


def _copy_preview(source: Path | None, asset_root: Path, product_key: str, suffix: str) -> Path | None:
    if source is None or not source.is_file():
        return None
    target = asset_root / "previews" / f"{safe_origin_name(product_key, 'Style')}_{suffix}{source.suffix.lower()}"
    shutil.copy2(source, target)
    return target


def _relative_or_absolute(path: Path | None, base: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path)


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
