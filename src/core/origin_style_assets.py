from __future__ import annotations

import json
import math
import shutil
import tempfile
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.origin.operations import connect_origin, quote_labtalk, safe_origin_name
from src.origin.style_mimic import read_graph_style_snapshot
from src.origin.style_registry import resolve_origin_style_asset
from src.origin.template_format import parse_origin_dataset_name


DEFAULT_STYLE_ASSET_ROOT = Path("templates") / "origin_styles"
PLOT_STYLE_READBACK_OPTIONS = {
    "color": "-c",
    "line_color": "-cl",
    "line_width_origin_units": "-w",
    "line_width_pt": "-wp",
    "line_style": "-l",
    "symbol_shape": "-k",
    "symbol_size": "-z",
    "fill_area": "-pfb",
    "fill_color": "-pfc",
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
        return {
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
    style_source_product_key: str = ""
    style_source_theme_path: Path | None = None


@dataclass(frozen=True)
class OriginStyleAssetReplayPlan:
    project_root: Path
    output_dir: Path
    items: list[OriginStyleAssetReplayItem]


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
                        json.dumps(read_graph_style_snapshot(operations, item.graph_page, source_label=item.origin_file.name).to_dict(), ensure_ascii=False, indent=2),
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
        finally:
            operations.close()
            for runtime_dir in runtime_dirs_to_cleanup:
                shutil.rmtree(runtime_dir, ignore_errors=True)
    else:
        failures.append({"message": "Origin export was not requested; pass --with-origin to create .oth format theme files."})

    entries = []
    for item in plan.items:
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

    entries = _merge_origin_style_manifest_entries(plan.asset_root / "manifest.json", entries)
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "asset_root": render_output_path(plan.asset_root, project_root=project_root),
        "origin_dependency_boundary": "Project-local .oth Graph Themes store copied Origin graph formats, .otpu Graph Templates preserve complex graph-layer structure when needed, JSON snapshots store readback plot colours and key numeric style values, and reference_opju/*.opju stores reviewed complex templates that require exact multi-layer/data-replacement reuse. Product runs use these project-local assets without requiring external template OPJU files.",
        "assets": entries,
    }
    manifest_path = plan.asset_root / "manifest.json"
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
    try:
        for item in plan.items:
            results.append(_replay_compare_one_item(operations, project_root, plan.output_dir, item))
    finally:
        operations.close()
    compared_count = sum(1 for item in results if item.get("status") == "matched")
    failure_count = sum(1 for item in results if item.get("status") != "matched")
    summary = {
        "planned_count": len(plan.items),
        "compared_count": compared_count,
        "failure_count": failure_count,
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
        style_source_product_key = str(raw.get("style_source_product_key") or "").strip()
        style_source_theme_path = _style_source_theme_from_plan(project_root, raw, style_source_product_key)
        items.append(
            OriginStyleAssetReplayItem(
                product_key=product_key,
                data_type=str(raw.get("data_type") or product_key),
                source_opju=source,
                graph_page=graph_page,
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
    }
    if not source.get("ok") or not asset_export.get("ok"):
        result.update({"status": "failed", "message": "Source or project asset graph export failed."})
        (product_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    comparison = _compare_replay_pngs(Path(str(source["png"])), Path(str(asset_export["png"])), product_dir)
    status = "matched" if comparison.get("exact_pixel_match") else "mismatch"
    result.update({"status": status, "message": "Replay comparison completed.", "comparison": comparison})
    (product_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
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
    try:
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
        graph_name = graph_page if graph_page in graph_pages else (graph_pages[0] if graph_pages else graph_page)
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
        tif = operations.export_graph(graph_name, runtime_tif, "tif", dpi=600)
        final_png = product_dir / f"{label}.png"
        final_tif = product_dir / f"{label}.tif"
        final_opju_name = f"{product_dir.name}.opju" if label == "project_asset" else f"{label}.opju"
        final_opju = product_dir / final_opju_name
        if runtime_png.exists():
            shutil.copy2(runtime_png, final_png)
        if runtime_tif.exists():
            shutil.copy2(runtime_tif, final_tif)
        if runtime_opju.exists():
            shutil.copy2(runtime_opju, final_opju)
        return {
            "ok": bool(getattr(png, "ok", False))
            and bool(getattr(tif, "ok", False))
            and final_png.is_file()
            and final_tif.is_file()
            and final_opju.is_file(),
            "message": f"{getattr(png, 'message', '')}; {getattr(tif, 'message', '')}".strip("; "),
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
        }
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)


def _compare_replay_pngs(source_png: Path, asset_png: Path, product_dir: Path) -> dict[str, object]:
    from PIL import Image, ImageChops, ImageStat

    source = Image.open(source_png).convert("RGBA")
    asset = Image.open(asset_png).convert("RGBA")
    if source.size != asset.size:
        return {
            "image_size": list(source.size),
            "asset_image_size": list(asset.size),
            "exact_pixel_match": False,
            "rms": math.inf,
            "diff_bbox": "size_mismatch",
        }
    diff = ImageChops.difference(source, asset)
    stat = ImageStat.Stat(diff)
    rms = math.sqrt(sum(value * value for value in stat.rms))
    bbox = diff.getbbox()
    side_by_side = product_dir / "side_by_side.png"
    side = Image.new("RGBA", (source.width * 2, source.height), "white")
    side.paste(source, (0, 0))
    side.paste(asset, (source.width, 0))
    side.save(side_by_side)
    return {
        "image_size": list(source.size),
        "rms": float(rms),
        "diff_bbox": list(bbox) if bbox else None,
        "exact_pixel_match": bbox is None,
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
) -> dict[str, object]:
    plots: list[dict[str, object]] = []
    layers: list[dict[str, object]] = []
    worksheet_cache: dict[str, dict[str, object]] = {}
    for layer_index in range(1, max_layers + 1):
        result = operations.get_graph_plot_dataset_names(graph_page, layer_index=layer_index)
        if not getattr(result, "ok", False):
            if plots:
                break
            continue
        names = [str(name) for name in getattr(result, "payload", {}).get("plot_dataset_names", []) if str(name).strip()]
        if not names and plots:
            break
        if not names:
            continue
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
    return {
        "schema_version": 1,
        "source_opju": source_label,
        "graph_page": graph_page,
        "sheet_name": sheet_name,
        "layer_count_with_plots": len(layers),
        "plot_count": len(plots),
        "layers": layers,
        "plots": plots,
        "mapping_policy": "Each Origin Y dataset name Book_Col is paired with the preceding worksheet column as X, matching the reviewed XRD Graph4 paired-XY workbook layout.",
    }


def _graph_plot_data_record(
    operations: object,
    graph_page: str,
    layer_index: int,
    plot_index: int,
    dataset: str,
    worksheet_cache: dict[str, dict[str, object]],
    *,
    sheet_name: str,
) -> dict[str, object]:
    parsed = parse_origin_dataset_name(dataset)
    base = {
        "graph_page": graph_page,
        "layer_index": int(layer_index),
        "plot_index": int(plot_index),
        "y_dataset": dataset,
    }
    if parsed is None:
        return {**base, "status": "unparsed_dataset_name"}
    book_name, y_col_index = parsed
    x_col_index = max(int(y_col_index) - 1, 0)
    actual_sheet_name = sheet_name
    cached = worksheet_cache.get(book_name)
    if cached is not None:
        columns = list(cached.get("columns", []))
        actual_sheet_name = str(cached["sheet_name"]) if "sheet_name" in cached else sheet_name
    else:
        read = _read_worksheet_data_with_fallback(operations, book_name, sheet_name)
        if not getattr(read, "ok", False):
            return {
                **base,
                "status": "worksheet_read_failed",
                "book_name": book_name,
                "sheet_name": sheet_name,
                "message": str(getattr(read, "message", "")),
            }
        columns = list(getattr(read, "payload", {}).get("columns", []))
        read_payload = getattr(read, "payload", {}) or {}
        actual_sheet_name = str(read_payload["sheet_name"]) if "sheet_name" in read_payload else sheet_name
        worksheet_cache[book_name] = {"columns": columns, "sheet_name": actual_sheet_name}
    if y_col_index >= len(columns) or x_col_index >= len(columns):
        return {
            **base,
            "status": "column_missing",
            "book_name": book_name,
            "sheet_name": sheet_name,
            "x_col_index": x_col_index,
            "y_col_index": y_col_index,
            "available_columns": len(columns),
        }
    x_values = [_json_safe_value(value) for value in columns[x_col_index]]
    y_values = [_json_safe_value(value) for value in columns[y_col_index]]
    row_count = min(len(x_values), len(y_values))
    _activate_graph_layer_for_style_readback(operations, graph_page, layer_index)
    return {
        **base,
        "status": "ready",
        "book_name": book_name,
        "sheet_name": actual_sheet_name,
        "x_dataset": f"{book_name}_{_origin_column_letters(x_col_index)}",
        "x_col_index": x_col_index,
        "y_col_index": y_col_index,
        "x_col_letter": _origin_column_letters(x_col_index),
        "y_col_letter": _origin_column_letters(y_col_index),
        "row_count": row_count,
        "style": _read_plot_style_properties(operations, dataset),
        "x_values": x_values,
        "y_values": y_values,
    }


def _read_worksheet_data_with_fallback(operations: object, book_name: str, sheet_name: str) -> object:
    attempts: list[str] = []
    for candidate in (sheet_name, ""):
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


def _json_safe_value(value: object) -> object:
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text if text else None
    return number if math.isfinite(number) else None


def _read_plot_style_properties(operations: object, dataset: str) -> dict[str, float]:
    if not hasattr(operations, "run_labtalk") or not hasattr(operations, "get_labtalk_variable"):
        return {}
    style: dict[str, float] = {}
    variable = "__rdop_plot_style_value"
    for key, option in PLOT_STYLE_READBACK_OPTIONS.items():
        try:
            operations.run_labtalk(f"{variable}=nan;")
            result = operations.run_labtalk(f"get {dataset} {option} {variable};")
            if not getattr(result, "ok", False):
                continue
            read = operations.get_labtalk_variable(variable)
            value = getattr(read, "payload", {}).get("value")
        except Exception:
            continue
        safe = _json_safe_value(value)
        if isinstance(safe, float):
            style[key] = safe
    return style


def _merge_origin_style_manifest_entries(manifest_path: Path, new_entries: list[dict[str, object]]) -> list[dict[str, object]]:
    if not manifest_path.is_file():
        return new_entries
    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return new_entries
    existing_entries = existing.get("assets") if isinstance(existing, dict) else []
    if not isinstance(existing_entries, list):
        return new_entries
    by_key: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for entry in existing_entries:
        if not isinstance(entry, dict):
            continue
        key = _entry_key(entry)
        if not key:
            continue
        by_key[key] = dict(entry)
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
