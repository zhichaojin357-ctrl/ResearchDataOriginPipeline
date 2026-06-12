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
    format_theme_path: Path
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
            "format_theme": _relative_or_absolute(self.format_theme_path, asset_root),
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
                preview_png=_metadata_artifact_path(product_dir, metadata.get("preview_png"), "figures_preview"),
                reference_preview_png=_metadata_artifact_path(product_dir, metadata.get("reference_preview_png"), "reference_exports"),
                comparison_png=_run_artifact_path(run_root, comparison.get("side_by_side_png")),
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
    (plan.asset_root / "format_themes").mkdir(parents=True, exist_ok=True)
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
                saved = operations.save_graph_theme(item.graph_page, item.format_theme_path)
                if not getattr(saved, "ok", False):
                    failures.append({"product_key": item.product_key, "message": scrub_output_text(getattr(saved, "message", "format theme save failed"), project_root=project_root)})
                    continue
                exported.append({"product_key": item.product_key, "format_theme": render_output_path(item.format_theme_path, project_root=project_root)})
        finally:
            operations.close()
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
        "origin_dependency_boundary": "Project-local .oth Graph Themes store copied Origin graph formats. Product runs create clean target graphs from current data and apply these saved formats without requiring external template OPJU files.",
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
