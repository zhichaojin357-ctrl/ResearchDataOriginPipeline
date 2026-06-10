from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.output_sanitizer import render_output_path


DEFAULT_STYLE_MANIFEST = Path("templates") / "origin_styles" / "manifest.json"


@dataclass(frozen=True)
class OriginStyleAsset:
    product_key: str
    data_type: str
    graph_template_path: Path
    status: str = ""
    graph_page: str = ""
    source_run_root: str = ""
    preview_png: Path | None = None
    reference_preview_png: Path | None = None

    def to_dict(self, project_root: Path) -> dict[str, object]:
        return {
            "product_key": self.product_key,
            "data_type": self.data_type,
            "graph_template": _relative_or_absolute(self.graph_template_path, project_root / "templates" / "origin_styles"),
            "status": self.status,
            "graph_page": self.graph_page,
            "source_run_root": render_output_path(self.source_run_root) if self.source_run_root else "",
            "preview_png": _relative_or_absolute(self.preview_png, project_root / "templates" / "origin_styles") if self.preview_png else "",
            "reference_preview_png": _relative_or_absolute(self.reference_preview_png, project_root / "templates" / "origin_styles") if self.reference_preview_png else "",
        }


def origin_style_manifest_path(project_root: Path, manifest_path: Path | None = None) -> Path:
    return manifest_path if manifest_path is not None else project_root / DEFAULT_STYLE_MANIFEST


def load_origin_style_manifest(project_root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    path = origin_style_manifest_path(project_root, manifest_path)
    if not path.exists():
        return {"schema_version": 1, "assets": []}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Origin style manifest must be a JSON object: {path}")
    assets = loaded.get("assets")
    if not isinstance(assets, list):
        raise ValueError(f"Origin style manifest must contain an assets list: {path}")
    return loaded


def resolve_origin_style_asset(
    project_root: Path,
    product_key: str,
    manifest_path: Path | None = None,
) -> OriginStyleAsset | None:
    manifest_file = origin_style_manifest_path(project_root, manifest_path)
    manifest = load_origin_style_manifest(project_root, manifest_file)
    base = manifest_file.parent
    requested = _style_key(product_key)
    for raw in manifest.get("assets", []):
        if not isinstance(raw, dict):
            continue
        keys = {str(raw.get("product_key", "")), str(raw.get("data_type", ""))}
        if requested not in {_style_key(key) for key in keys}:
            continue
        graph_template = _resolve_manifest_path(base, raw.get("graph_template"))
        if graph_template is None or not graph_template.is_file():
            continue
        return OriginStyleAsset(
            product_key=str(raw.get("product_key") or product_key),
            data_type=str(raw.get("data_type") or product_key),
            graph_template_path=graph_template,
            status=str(raw.get("status") or ""),
            graph_page=str(raw.get("graph_page") or ""),
            source_run_root=str(raw.get("source_run_root") or manifest.get("source_run_root") or ""),
            preview_png=_resolve_manifest_path(base, raw.get("preview_png")),
            reference_preview_png=_resolve_manifest_path(base, raw.get("reference_preview_png")),
        )
    return None


def _resolve_manifest_path(base: Path, value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else base / path


def _relative_or_absolute(path: Path | None, base: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(render_output_path(path))


def _style_key(value: str) -> str:
    return str(value).casefold().replace("/", "_").replace("-", "_").replace(" ", "_").strip("_")
