from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.file_utils import file_sha256
from src.core.output_sanitizer import render_output_path


DEFAULT_STYLE_MANIFEST = Path("templates") / "origin_styles" / "manifest.json"
SUPPORTED_STYLE_MANIFEST_VERSIONS = {1, 2}
REQUIRED_STYLE_PRODUCT_KEYS = (
    "BET",
    "XPS_in_situ",
    "XPS_non_in_situ",
    "XRD",
    "EPR",
    "EIS",
    "Raman",
    "UV-vis DRS / Tauc",
    "PL",
    "photocurrent",
    "FTIR",
    "Mott-Schottky",
)
STYLE_ASSET_FILE_FIELDS = (
    "format_theme",
    "graph_template",
    "style_snapshot",
    "data_snapshot",
    "template_opju",
    "style_source_theme",
    "preview_png",
    "reference_preview_png",
    "template_preview_comparison_png",
)


@dataclass(frozen=True)
class OriginStyleAsset:
    product_key: str
    data_type: str
    format_theme_path: Path
    graph_template_path: Path | None = None
    style_snapshot_path: Path | None = None
    data_snapshot_path: Path | None = None
    template_opju_path: Path | None = None
    status: str = ""
    graph_page: str = ""
    source_run_root: str = ""
    preview_png: Path | None = None
    reference_preview_png: Path | None = None

    def to_dict(self, project_root: Path) -> dict[str, object]:
        return {
            "product_key": self.product_key,
            "data_type": self.data_type,
            "format_theme": _relative_or_absolute(self.format_theme_path, project_root / "templates" / "origin_styles"),
            "graph_template": _relative_or_absolute(self.graph_template_path, project_root / "templates" / "origin_styles")
            if self.graph_template_path
            else "",
            "style_snapshot": _relative_or_absolute(self.style_snapshot_path, project_root / "templates" / "origin_styles")
            if self.style_snapshot_path
            else "",
            "data_snapshot": _relative_or_absolute(self.data_snapshot_path, project_root / "templates" / "origin_styles")
            if self.data_snapshot_path
            else "",
            "template_opju": _relative_or_absolute(self.template_opju_path, project_root / "templates" / "origin_styles")
            if self.template_opju_path
            else "",
            "status": self.status,
            "graph_page": self.graph_page,
            "source_run_root": render_output_path(self.source_run_root) if self.source_run_root else "",
            "preview_png": _relative_or_absolute(self.preview_png, project_root / "templates" / "origin_styles") if self.preview_png else "",
            "reference_preview_png": _relative_or_absolute(self.reference_preview_png, project_root / "templates" / "origin_styles") if self.reference_preview_png else "",
        }


def origin_style_manifest_path(project_root: Path, manifest_path: Path | None = None) -> Path:
    root = project_root.resolve()
    if manifest_path is None:
        return root / DEFAULT_STYLE_MANIFEST
    path = Path(manifest_path)
    return path.resolve() if path.is_absolute() else root / path


def load_origin_style_manifest(project_root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    path = origin_style_manifest_path(project_root, manifest_path)
    if not path.exists():
        return {"schema_version": 1, "assets": []}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Origin style manifest must be a JSON object: {path}")
    try:
        schema_version = int(loaded.get("schema_version", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Origin style manifest schema_version must be an integer: {path}") from exc
    if schema_version not in SUPPORTED_STYLE_MANIFEST_VERSIONS:
        supported = ", ".join(str(value) for value in sorted(SUPPORTED_STYLE_MANIFEST_VERSIONS))
        raise ValueError(f"Unsupported Origin style manifest schema_version {schema_version}; supported: {supported}: {path}")
    loaded["schema_version"] = schema_version
    assets = loaded.get("assets")
    if not isinstance(assets, list):
        raise ValueError(f"Origin style manifest must contain an assets list: {path}")
    return loaded


def validate_origin_style_asset_integrity(
    project_root: Path,
    manifest_path: Path | None = None,
    *,
    required_product_keys: tuple[str, ...] = REQUIRED_STYLE_PRODUCT_KEYS,
) -> dict[str, Any]:
    manifest_file = origin_style_manifest_path(project_root, manifest_path)
    failures: list[str] = []
    warnings: list[str] = []
    items: list[dict[str, object]] = []
    if not manifest_file.is_file():
        return {
            "ok": False,
            "schema_version": 0,
            "asset_count": 0,
            "failures": [f"Origin style manifest missing: {manifest_file}"],
            "warnings": [],
            "items": [],
        }
    try:
        manifest = load_origin_style_manifest(project_root, manifest_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "schema_version": 0,
            "asset_count": 0,
            "failures": [str(exc)],
            "warnings": [],
            "items": [],
        }

    schema_version = int(manifest.get("schema_version", 1))
    asset_root = manifest_file.parent.resolve()
    raw_assets = manifest.get("assets", [])
    assets = [item for item in raw_assets if isinstance(item, dict)]
    keys: list[str] = []
    for index, asset in enumerate(assets, start=1):
        product_key = str(asset.get("product_key") or asset.get("data_type") or "").strip()
        label = product_key or f"asset[{index}]"
        item_failures: list[str] = []
        item_warnings: list[str] = []
        if not product_key:
            item_failures.append("product_key is missing")
        else:
            keys.append(product_key)
        if not str(asset.get("graph_page") or "").strip():
            item_failures.append("graph_page is missing")

        resolved_files: dict[str, Path] = {}
        for field in STYLE_ASSET_FILE_FIELDS:
            raw_path = str(asset.get(field) or "").strip()
            if not raw_path:
                continue
            resolved = _resolve_manifest_path(asset_root, raw_path)
            if resolved is None or not _is_within(resolved, asset_root):
                item_failures.append(f"{field} escapes the project style-asset root")
                continue
            if not resolved.is_file():
                item_failures.append(f"{field} file is missing: {raw_path}")
                continue
            resolved_files[field] = resolved

        if "format_theme" not in resolved_files and "graph_template" not in resolved_files:
            item_failures.append("no readable format_theme or graph_template")
        for field in ("style_snapshot", "data_snapshot"):
            path = resolved_files.get(field)
            if path is not None:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("root is not an object")
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    item_failures.append(f"{field} is not valid JSON: {exc}")

        if schema_version >= 2:
            _validate_v2_style_asset_entry(asset, resolved_files, item_failures)
        else:
            item_warnings.append("schema v1 has no mandatory per-file hash verification")

        if product_key == "XRD" and "data_snapshot" in resolved_files:
            _validate_xrd_data_snapshot(resolved_files["data_snapshot"], item_failures)

        failures.extend(f"{label}: {message}" for message in item_failures)
        warnings.extend(f"{label}: {message}" for message in item_warnings)
        items.append(
            {
                "product_key": product_key,
                "ok": not item_failures,
                "file_count": len(resolved_files),
                "failures": item_failures,
                "warnings": item_warnings,
            }
        )

    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        failures.append("duplicate product keys: " + ", ".join(duplicates))
    missing = [key for key in required_product_keys if key not in keys]
    if missing:
        failures.append("missing required style products: " + ", ".join(missing))
    return {
        "ok": not failures,
        "schema_version": schema_version,
        "asset_count": len(assets),
        "failures": failures,
        "warnings": warnings,
        "items": items,
    }


def _validate_v2_style_asset_entry(
    asset: dict[str, object],
    resolved_files: dict[str, Path],
    failures: list[str],
) -> None:
    primary = resolved_files.get("format_theme") or resolved_files.get("graph_template")
    required = ("asset_kind", "sha256", "file_size_bytes", "expected_layer_count", "expected_plot_count", "harvested_at", "source_mode")
    missing = [field for field in required if asset.get(field) in (None, "")]
    if missing:
        failures.append("manifest v2 fields missing: " + ", ".join(missing))
    if primary is not None:
        _validate_recorded_file(primary, asset.get("sha256"), asset.get("file_size_bytes"), "primary asset", failures)
        expected_kind = primary.suffix.casefold().lstrip(".")
        if str(asset.get("asset_kind") or "").casefold().lstrip(".") != expected_kind:
            failures.append(f"asset_kind does not match primary asset extension {expected_kind}")

    for field in ("expected_layer_count", "expected_plot_count"):
        try:
            if int(asset.get(field) or 0) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            failures.append(f"{field} must be a positive integer")

    integrity = asset.get("file_integrity")
    if not isinstance(integrity, dict):
        failures.append("file_integrity must be an object")
        return
    for field, path in resolved_files.items():
        record = integrity.get(field)
        if not isinstance(record, dict):
            failures.append(f"file_integrity.{field} is missing")
            continue
        _validate_recorded_file(path, record.get("sha256"), record.get("size_bytes"), f"file_integrity.{field}", failures)
        kind = str(record.get("kind") or "").casefold().lstrip(".")
        expected_kind = path.suffix.casefold().lstrip(".")
        if kind != expected_kind:
            failures.append(f"file_integrity.{field}.kind does not match {expected_kind}")

    style_snapshot = resolved_files.get("style_snapshot")
    if style_snapshot is not None:
        try:
            payload = json.loads(style_snapshot.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        for manifest_field, snapshot_field in (
            ("expected_layer_count", "layer_count"),
            ("expected_plot_count", "plot_count"),
        ):
            snapshot_value = payload.get(snapshot_field) if isinstance(payload, dict) else None
            if snapshot_value is None:
                continue
            try:
                manifest_value = int(asset.get(manifest_field) or 0)
                snapshot_count = int(snapshot_value)
            except (TypeError, ValueError):
                failures.append(f"{manifest_field} or style snapshot {snapshot_field} is not an integer")
                continue
            if manifest_value != snapshot_count:
                failures.append(f"{manifest_field} does not match style snapshot {snapshot_field}")

    source_opju = resolved_files.get("template_opju")
    source_hash = str(asset.get("source_opju_hash") or "").strip().casefold()
    if source_opju is not None and source_hash and source_hash != file_sha256(source_opju):
        failures.append("source_opju_hash mismatch")


def _validate_recorded_file(
    path: Path,
    expected_hash: object,
    expected_size: object,
    label: str,
    failures: list[str],
) -> None:
    digest = str(expected_hash or "").strip().casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        failures.append(f"{label} sha256 is missing or malformed")
    elif digest != file_sha256(path):
        failures.append(f"{label} sha256 mismatch")
    try:
        size = int(expected_size)
    except (TypeError, ValueError):
        failures.append(f"{label} size is missing or invalid")
    else:
        if size != path.stat().st_size:
            failures.append(f"{label} size mismatch")


def _validate_xrd_data_snapshot(path: Path, failures: list[str]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    layers = payload.get("layers") if isinstance(payload, dict) else None
    plots = payload.get("plots") if isinstance(payload, dict) else None
    if not isinstance(layers, list) or not layers:
        failures.append("XRD data_snapshot.layers must be a non-empty list")
    if not isinstance(plots, list) or not plots:
        failures.append("XRD data_snapshot.plots must be a non-empty list")
        return
    for index, plot in enumerate(plots, start=1):
        if not isinstance(plot, dict) or not str(plot.get("y_dataset") or "").strip():
            failures.append(f"XRD data_snapshot plot {index} lacks y_dataset")
            break
        if not isinstance(plot.get("y_values"), list) or not plot.get("y_values"):
            failures.append(f"XRD data_snapshot plot {index} lacks y_values")
            break


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


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
        format_theme = _resolve_local_manifest_path(base, raw.get("format_theme"))
        graph_template = _resolve_local_manifest_path(base, raw.get("graph_template"))
        if format_theme is None or not format_theme.is_file():
            if graph_template is None or not graph_template.is_file():
                continue
            format_theme = graph_template
        elif graph_template is not None and not graph_template.is_file():
            graph_template = None
        if graph_template is not None and not graph_template.is_file():
            graph_template = None
        if format_theme is None or not format_theme.is_file():
            continue
        template_opju = _resolve_local_manifest_path(base, raw.get("template_opju") or raw.get("source_opju"))
        if template_opju is not None and not template_opju.is_file():
            template_opju = None
        style_snapshot = _resolve_local_manifest_path(base, raw.get("style_snapshot"))
        if style_snapshot is not None and not style_snapshot.is_file():
            style_snapshot = None
        data_snapshot = _resolve_local_manifest_path(base, raw.get("data_snapshot"))
        if data_snapshot is not None and not data_snapshot.is_file():
            data_snapshot = None
        return OriginStyleAsset(
            product_key=str(raw.get("product_key") or product_key),
            data_type=str(raw.get("data_type") or product_key),
            format_theme_path=format_theme,
            graph_template_path=graph_template,
            style_snapshot_path=style_snapshot,
            data_snapshot_path=data_snapshot,
            template_opju_path=template_opju,
            status=str(raw.get("status") or ""),
            graph_page=str(raw.get("graph_page") or ""),
            source_run_root=str(raw.get("source_run_root") or manifest.get("source_run_root") or ""),
            preview_png=_resolve_local_manifest_path(base, raw.get("preview_png")),
            reference_preview_png=_resolve_local_manifest_path(base, raw.get("reference_preview_png")),
        )
    return None


def _resolve_manifest_path(base: Path, value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else base / path


def _resolve_local_manifest_path(base: Path, value: object) -> Path | None:
    path = _resolve_manifest_path(base, value)
    return path if path is not None and _is_within(path, base) else None


def _relative_or_absolute(path: Path | None, base: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(render_output_path(path))


def _style_key(value: str) -> str:
    return str(value).casefold().replace("/", "_").replace("-", "_").replace(" ", "_").strip("_")
