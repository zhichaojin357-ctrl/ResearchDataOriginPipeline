from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.origin.operations import connect_origin, safe_origin_name


DEFAULT_STYLE_ASSET_ROOT = Path("templates") / "origin_styles"


@dataclass(frozen=True)
class OriginStyleAssetExportItem:
    product_key: str
    data_type: str
    status: str
    graph_page: str
    origin_file: Path
    graph_template_path: Path
    preview_png: Path | None = None
    reference_preview_png: Path | None = None
    comparison_png: Path | None = None
    preview_rms: float | None = None

    def manifest_entry(self, asset_root: Path) -> dict[str, object]:
        return {
            "product_key": self.product_key,
            "data_type": self.data_type,
            "status": self.status,
            "graph_page": self.graph_page,
            "graph_template": _relative_or_absolute(self.graph_template_path, asset_root),
            "preview_png": _relative_or_absolute(self.preview_png, asset_root) if self.preview_png else "",
            "reference_preview_png": _relative_or_absolute(self.reference_preview_png, asset_root) if self.reference_preview_png else "",
            "template_preview_comparison_png": _relative_or_absolute(self.comparison_png, asset_root) if self.comparison_png else "",
            "preview_rms": self.preview_rms,
        }


@dataclass(frozen=True)
class OriginStyleAssetExportPlan:
    project_root: Path
    run_root: Path
    asset_root: Path
    items: list[OriginStyleAssetExportItem]


def build_origin_style_asset_export_plan(
    project_root: Path,
    run_root: Path,
    asset_root: Path | None = None,
) -> OriginStyleAssetExportPlan:
    root = asset_root or project_root / DEFAULT_STYLE_ASSET_ROOT
    accepted = _accepted_comparison_items(run_root)
    items: list[OriginStyleAssetExportItem] = []
    for product_type, comparison in accepted.items():
        metadata = _metadata_for_product(run_root, product_type)
        if not metadata:
            continue
        origin_file = Path(str(metadata.get("origin_file") or ""))
        if not origin_file.is_file():
            continue
        product_key = str(metadata.get("product_key") or product_type)
        data_type = str(metadata.get("data_type") or product_type)
        graph_page = _graph_page_from_metadata(metadata)
        if not graph_page:
            continue
        slug = safe_origin_name(product_key, "Style")
        items.append(
            OriginStyleAssetExportItem(
                product_key=product_key,
                data_type=data_type,
                status=str(metadata.get("status") or comparison.get("status") or ""),
                graph_page=graph_page,
                origin_file=origin_file,
                graph_template_path=root / "graph_templates" / f"{slug}.otpu",
                preview_png=_existing_path(metadata.get("preview_png")),
                reference_preview_png=_existing_path(metadata.get("reference_preview_png")),
                comparison_png=_existing_path(comparison.get("side_by_side_png")),
                preview_rms=_to_float(comparison.get("preview_rms")),
            )
        )
    return OriginStyleAssetExportPlan(project_root=project_root, run_root=run_root, asset_root=root, items=items)


def export_origin_style_assets(
    project_root: Path,
    run_root: Path,
    *,
    asset_root: Path | None = None,
    with_origin: bool = False,
) -> dict[str, object]:
    plan = build_origin_style_asset_export_plan(project_root, run_root, asset_root)
    plan.asset_root.mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "graph_templates").mkdir(parents=True, exist_ok=True)
    (plan.asset_root / "previews").mkdir(parents=True, exist_ok=True)
    exported: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    if with_origin:
        operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
        try:
            for item in plan.items:
                operations.new_project()
                loaded = operations.load_project(item.origin_file)
                if not getattr(loaded, "ok", False):
                    failures.append({"product_key": item.product_key, "message": getattr(loaded, "message", "load failed")})
                    continue
                saved = operations.save_graph_template(item.graph_page, item.graph_template_path)
                if not getattr(saved, "ok", False):
                    failures.append({"product_key": item.product_key, "message": scrub_output_text(getattr(saved, "message", "template save failed"), project_root=project_root)})
                    continue
                exported.append({"product_key": item.product_key, "graph_template": render_output_path(item.graph_template_path, project_root=project_root)})
        finally:
            operations.close()
    else:
        failures.append({"message": "Origin export was not requested; pass --with-origin to create .otpu files."})

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
            graph_template_path=item.graph_template_path,
            preview_png=preview,
            reference_preview_png=reference,
            comparison_png=comparison,
            preview_rms=item.preview_rms,
        )
        entries.append(manifest_item.manifest_entry(plan.asset_root))

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "asset_root": render_output_path(plan.asset_root, project_root=project_root),
        "origin_dependency_boundary": "Project-local .otpu Graph Templates are the style-package fallback when external OPJU exemplars are unavailable.",
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
        if product_type and item.get("status") == "accepted" and bool(item.get("strict_visual_match")):
            accepted[product_type] = item
    return accepted


def _metadata_for_product(run_root: Path, product_type: str) -> dict[str, Any]:
    product_dir = _product_dir_for_type(run_root, product_type)
    if product_dir is None:
        return {}
    metadata_dir = product_dir / "metadata"
    if not metadata_dir.exists():
        return {}
    for path in sorted(metadata_dir.glob("*.json")):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and loaded.get("origin_file") and loaded.get("product_key"):
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


def _type_key(product_type: str) -> str:
    text = str(product_type).casefold()
    return "".join(char if char.isalnum() else "_" for char in text).strip("_").replace("__", "_").replace("__", "_")


def _existing_path(value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
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
