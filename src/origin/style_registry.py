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
    "UV-vis DRS",
    "Tauc",
    "PL",
    "photocurrent",
    "FTIR",
    "Mott-Schottky",
)
STYLE_ASSET_FILE_FIELDS = (
    "format_theme",
    "graph_template",
    "binding_contract",
    "runtime_validation_evidence",
    "adaptive_runtime_validation_evidence",
    "style_snapshot",
    "data_snapshot",
    "template_opju",
    "style_source_theme",
    "preview_png",
    "reference_preview_png",
    "template_preview_comparison_png",
)
RUNTIME_VALIDATION_SCOPE = "fresh_project_same_data"
ADAPTIVE_RUNTIME_FORMAT_THEME_ROLES = frozenset(
    {"adaptive_runtime", "legacy_compatibility_runtime"}
)
ADAPTIVE_CANDIDATE_FORMAT_THEME_ROLES = frozenset(
    {
        "adaptive_runtime_candidate",
        "legacy_compatibility_nonruntime",
        "quarantined_nonruntime",
    }
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
    runtime_asset_kind: str = ""
    runtime_asset_path: Path | None = None
    runtime_asset_sha256: str = ""
    binding_contract_path: Path | None = None
    runtime_validation_evidence_path: Path | None = None
    format_theme_role: str = ""
    expected_plot_count: int = 0

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
            "runtime_asset_kind": self.runtime_asset_kind,
            "runtime_asset": _relative_or_absolute(
                self.runtime_asset_path,
                project_root / "templates" / "origin_styles",
            )
            if self.runtime_asset_path
            else "",
            "runtime_asset_sha256": self.runtime_asset_sha256,
            "binding_contract": _relative_or_absolute(
                self.binding_contract_path,
                project_root / "templates" / "origin_styles",
            )
            if self.binding_contract_path
            else "",
            "runtime_validation_evidence": _relative_or_absolute(
                self.runtime_validation_evidence_path,
                project_root / "templates" / "origin_styles",
            )
            if self.runtime_validation_evidence_path
            else "",
            "format_theme_role": self.format_theme_role,
            "expected_plot_count": self.expected_plot_count,
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

        if "format_theme" not in resolved_files:
            if "graph_template" in resolved_files:
                item_failures.append(
                    "no readable format_theme; graph_template is harvest-only and cannot satisfy runtime integrity"
                )
            else:
                item_failures.append("no readable format_theme")
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
    asset_kind = str(asset.get("asset_kind") or "").casefold().lstrip(".")
    primary_field = {"oth": "format_theme", "otpu": "graph_template"}.get(
        asset_kind
    )
    primary = resolved_files.get(primary_field) if primary_field else None
    required = ("asset_kind", "sha256", "file_size_bytes", "expected_layer_count", "expected_plot_count", "harvested_at", "source_mode")
    missing = [field for field in required if asset.get(field) in (None, "")]
    if missing:
        failures.append("manifest v2 fields missing: " + ", ".join(missing))
    if primary_field is None and asset_kind:
        failures.append(f"unsupported runtime asset_kind: {asset_kind}")
    elif primary is None and primary_field is not None:
        failures.append(
            f"asset_kind {asset_kind} requires a readable {primary_field}"
        )
    if primary is not None:
        _validate_recorded_file(primary, asset.get("sha256"), asset.get("file_size_bytes"), "primary asset", failures)
        expected_kind = primary.suffix.casefold().lstrip(".")
        if asset_kind != expected_kind:
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
    *,
    require_runtime_validation: bool = False,
    loaded_manifest: dict[str, Any] | None = None,
) -> OriginStyleAsset | None:
    manifest_file = origin_style_manifest_path(project_root, manifest_path)
    manifest = loaded_manifest if loaded_manifest is not None else load_origin_style_manifest(project_root, manifest_file)
    base = manifest_file.parent
    schema_version = int(manifest.get("schema_version", 1))
    requested = _style_key(product_key)
    for raw in manifest.get("assets", []):
        if not isinstance(raw, dict):
            continue
        keys = {str(raw.get("product_key", "")), str(raw.get("data_type", ""))}
        if requested not in {_style_key(key) for key in keys}:
            continue
        # Resolution is also used by harvest/replay diagnostics, which must be
        # able to inspect quarantined candidates.  Formal product callers opt
        # into this gate explicitly so diagnostics cannot accidentally promote
        # their own input by making it unresolvable.
        if require_runtime_validation and not origin_style_asset_runtime_validated(raw):
            continue
        format_theme = _resolve_local_manifest_path(base, raw.get("format_theme"))
        graph_template = _resolve_local_manifest_path(base, raw.get("graph_template"))
        if format_theme is None or not format_theme.is_file():
            continue
        if graph_template is not None and not graph_template.is_file():
            graph_template = None
        template_opju = _resolve_local_manifest_path(base, raw.get("template_opju") or raw.get("source_opju"))
        if template_opju is not None and not template_opju.is_file():
            template_opju = None
        style_snapshot = _resolve_local_manifest_path(base, raw.get("style_snapshot"))
        if style_snapshot is not None and not style_snapshot.is_file():
            style_snapshot = None
        data_snapshot = _resolve_local_manifest_path(base, raw.get("data_snapshot"))
        if data_snapshot is not None and not data_snapshot.is_file():
            data_snapshot = None
        binding_contract = _resolve_local_manifest_path(base, raw.get("binding_contract"))
        if binding_contract is not None and not binding_contract.is_file():
            binding_contract = None
        validation_evidence = _resolve_local_manifest_path(
            base,
            raw.get("runtime_validation_evidence"),
        )
        if validation_evidence is not None and not validation_evidence.is_file():
            validation_evidence = None
        runtime_kind, runtime_field, runtime_relative, runtime_sha256 = (
            _runtime_style_asset_binding(raw)
        )
        runtime_asset = {
            "format_theme": format_theme,
            "graph_template": graph_template,
        }.get(runtime_field)
        if require_runtime_validation:
            validation = raw.get("runtime_validation")
            validation = validation if isinstance(validation, dict) else {}
            integrity = raw.get("file_integrity")
            integrity = integrity if isinstance(integrity, dict) else {}
            snapshot_record = integrity.get("style_snapshot")
            snapshot_sha256 = str(
                snapshot_record.get("sha256")
                if isinstance(snapshot_record, dict)
                else ""
            ).casefold()
            theme_record = integrity.get("format_theme")
            theme_sha256 = str(
                theme_record.get("sha256")
                if isinstance(theme_record, dict)
                else ""
            ).casefold()
            required_theme_sha256 = str(
                validation.get("supporting_format_theme_sha256") or ""
            ).casefold()
            if (
                runtime_asset is None
                or not runtime_asset.is_file()
            ):
                continue
            if runtime_kind == "otpu" and (
                not runtime_relative
                or file_sha256(runtime_asset).casefold() != runtime_sha256
                or style_snapshot is None
                or file_sha256(style_snapshot).casefold() != snapshot_sha256
                or (
                    required_theme_sha256
                    and (
                        format_theme is None
                        or file_sha256(format_theme).casefold()
                        != required_theme_sha256
                        or required_theme_sha256 != theme_sha256
                    )
                )
                or binding_contract is None
                or file_sha256(binding_contract).casefold()
                != str(validation.get("binding_contract_sha256") or "").casefold()
                or validation_evidence is None
                or file_sha256(validation_evidence).casefold()
                != str(validation.get("evidence_sha256") or "").casefold()
            ):
                continue
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
            runtime_asset_kind=runtime_kind,
            runtime_asset_path=runtime_asset,
            runtime_asset_sha256=runtime_sha256,
            binding_contract_path=binding_contract,
            runtime_validation_evidence_path=validation_evidence,
            format_theme_role=str(raw.get("format_theme_role") or ""),
            expected_plot_count=_positive_int_or_zero(raw.get("expected_plot_count")),
        )
    return None


def resolve_origin_runtime_style_asset(
    project_root: Path,
    product_key: str,
    manifest_path: Path | None = None,
    *,
    loaded_manifest: dict[str, Any] | None = None,
) -> OriginStyleAsset | None:
    """Resolve a runtime asset without changing legacy OTH behavior.

    Existing OTH assets remain the compatibility path until their data type is
    migrated and visually accepted. Detached graph templates are fail-closed:
    an OTPU can run only after the exact asset/evidence binding passes.
    """

    candidate = resolve_origin_style_asset(
        project_root,
        product_key,
        manifest_path,
        require_runtime_validation=False,
        loaded_manifest=loaded_manifest,
    )
    if candidate is None:
        return candidate
    if candidate.runtime_asset_kind == "oth":
        return candidate if candidate.status.casefold() == "accepted" else None
    return resolve_origin_style_asset(
        project_root,
        product_key,
        manifest_path,
        require_runtime_validation=True,
        loaded_manifest=loaded_manifest,
    )


def resolve_origin_adaptive_style_asset(
    project_root: Path,
    product_key: str,
    manifest_path: Path | None = None,
    *,
    allow_candidate: bool = False,
) -> OriginStyleAsset | None:
    """Resolve an independently selected OTH + JSON adaptive style bundle.

    This does not reinterpret the manifest's primary ``asset_kind``.  In
    particular, a verified OTPU entry remains an OTPU entry; this resolver
    returns its separately recorded format theme and JSON snapshots only when
    that complete secondary bundle is eligible and passes schema-v2 integrity
    checks.  Candidate roles are visible only to explicit validation callers.
    """

    manifest_file = origin_style_manifest_path(project_root, manifest_path)
    manifest = load_origin_style_manifest(project_root, manifest_file)
    if int(manifest.get("schema_version", 1)) != 2:
        return None

    allowed_roles = set(ADAPTIVE_RUNTIME_FORMAT_THEME_ROLES)
    if allow_candidate:
        allowed_roles.update(ADAPTIVE_CANDIDATE_FORMAT_THEME_ROLES)

    base = manifest_file.parent.resolve()
    requested = _style_key(product_key)
    for raw in manifest.get("assets", []):
        if not isinstance(raw, dict):
            continue
        keys = {str(raw.get("product_key", "")), str(raw.get("data_type", ""))}
        if requested not in {_style_key(key) for key in keys}:
            continue
        if str(raw.get("status") or "").casefold() != "accepted":
            continue
        format_theme_role = str(raw.get("format_theme_role") or "").casefold()
        if format_theme_role not in allowed_roles:
            continue

        paths = {
            field: _resolve_local_manifest_path(base, raw.get(field))
            for field in ("format_theme", "style_snapshot", "data_snapshot")
        }
        expected_suffixes = {
            "format_theme": ".oth",
            "style_snapshot": ".json",
            "data_snapshot": ".json",
        }
        if any(
            path is None
            or not path.is_file()
            or path.suffix.casefold() != expected_suffixes[field]
            for field, path in paths.items()
        ):
            continue

        integrity = raw.get("file_integrity")
        if not isinstance(integrity, dict) or any(
            not _adaptive_integrity_record_matches(
                base,
                raw,
                integrity,
                field,
                paths[field],
            )
            for field in paths
        ):
            continue

        payloads: dict[str, dict[str, object]] = {}
        invalid_json = False
        for field in ("style_snapshot", "data_snapshot"):
            try:
                payload = json.loads(paths[field].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invalid_json = True
                break
            if not isinstance(payload, dict):
                invalid_json = True
                break
            payloads[field] = payload
        if invalid_json:
            continue

        expected_plot_count = _positive_int_or_zero(raw.get("expected_plot_count"))
        if expected_plot_count <= 0:
            continue
        if any(
            payload.get("plot_count") is not None
            and _positive_int_or_zero(payload.get("plot_count"))
            != expected_plot_count
            for payload in payloads.values()
        ):
            continue

        theme_record = integrity["format_theme"]
        graph_template = _resolve_local_manifest_path(base, raw.get("graph_template"))
        if graph_template is not None and not graph_template.is_file():
            graph_template = None
        template_opju = _resolve_local_manifest_path(
            base,
            raw.get("template_opju") or raw.get("source_opju"),
        )
        if template_opju is not None and not template_opju.is_file():
            template_opju = None
        return OriginStyleAsset(
            product_key=str(raw.get("product_key") or product_key),
            data_type=str(raw.get("data_type") or product_key),
            format_theme_path=paths["format_theme"],
            graph_template_path=graph_template,
            style_snapshot_path=paths["style_snapshot"],
            data_snapshot_path=paths["data_snapshot"],
            template_opju_path=template_opju,
            status=str(raw.get("status") or ""),
            graph_page=str(raw.get("graph_page") or ""),
            source_run_root=str(
                raw.get("source_run_root") or manifest.get("source_run_root") or ""
            ),
            preview_png=_resolve_local_manifest_path(base, raw.get("preview_png")),
            reference_preview_png=_resolve_local_manifest_path(
                base,
                raw.get("reference_preview_png"),
            ),
            runtime_asset_kind="oth_json",
            runtime_asset_path=paths["format_theme"],
            runtime_asset_sha256=str(theme_record.get("sha256") or "").casefold(),
            binding_contract_path=_existing_local_manifest_path(
                base,
                raw.get("binding_contract"),
            ),
            runtime_validation_evidence_path=_existing_local_manifest_path(
                base,
                raw.get("adaptive_runtime_validation_evidence")
                or raw.get("runtime_validation_evidence"),
            ),
            format_theme_role=format_theme_role,
            expected_plot_count=expected_plot_count,
        )
    return None


def _adaptive_integrity_record_matches(
    base: Path,
    raw: dict[str, object],
    integrity: dict[str, object],
    field: str,
    path: Path | None,
) -> bool:
    if path is None:
        return False
    record = integrity.get(field)
    if not isinstance(record, dict):
        return False
    expected_kind = path.suffix.casefold().lstrip(".")
    if str(record.get("kind") or "").casefold().lstrip(".") != expected_kind:
        return False
    recorded_path = str(
        record.get("path") or record.get("relative_path") or ""
    ).strip()
    if recorded_path:
        resolved_recorded_path = _resolve_local_manifest_path(base, recorded_path)
        if resolved_recorded_path is None or resolved_recorded_path.resolve() != path.resolve():
            return False
    manifest_path = _resolve_local_manifest_path(base, raw.get(field))
    if manifest_path is None or manifest_path.resolve() != path.resolve():
        return False
    digest = str(record.get("sha256") or "").strip().casefold()
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None or file_sha256(path) != digest:
        return False
    try:
        size = int(record.get("size_bytes"))
    except (TypeError, ValueError):
        return False
    return size == path.stat().st_size


def _existing_local_manifest_path(base: Path, value: object) -> Path | None:
    path = _resolve_local_manifest_path(base, value)
    return path if path is not None and path.is_file() else None


def _positive_int_or_zero(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def origin_style_asset_runtime_validated(raw: dict[str, object]) -> bool:
    """Return whether an asset passed an independent fresh-project replay.

    File hashes and a reference-OPJU self replay are integrity evidence, not
    proof that an .oth/.otpu asset can recreate the reviewed graph in a clean
    Origin project.
    """

    validation = raw.get("runtime_validation")
    if not isinstance(validation, dict):
        return False
    runtime_kind, runtime_field, runtime_path, runtime_sha256 = (
        _runtime_style_asset_binding(raw)
    )
    if runtime_kind not in {"oth", "otpu"} or not runtime_field:
        return False
    # OTPU activation is evidence-driven.  Historical templates remain
    # quarantined because they lack the exact asset/reference/binding/evidence
    # contract below; a product-name allowlist would have to be edited for
    # every independently validated data type and can drift from the manifest.
    integrity = raw.get("file_integrity")
    runtime_record = integrity.get(runtime_field) if isinstance(integrity, dict) else None
    reference_record = integrity.get("template_opju") if isinstance(integrity, dict) else None
    binding_record = integrity.get("binding_contract") if isinstance(integrity, dict) else None
    evidence_record = (
        integrity.get("runtime_validation_evidence")
        if isinstance(integrity, dict)
        else None
    )
    validation_asset_kind = str(validation.get("asset_kind") or "").casefold().lstrip(".")
    validation_asset_path = str(validation.get("asset_path") or "").replace("\\", "/")
    validation_asset_sha256 = str(validation.get("asset_sha256") or "").casefold()
    validation_reference_sha256 = str(
        validation.get("reference_opju_sha256") or ""
    ).casefold()
    validation_binding_sha256 = str(
        validation.get("binding_contract_sha256") or ""
    ).casefold()
    validation_evidence_sha256 = str(
        validation.get("evidence_sha256") or ""
    ).casefold()
    validation_theme_sha256 = str(
        validation.get("supporting_format_theme_sha256") or ""
    ).casefold()
    strict_otpu_binding = runtime_kind == "otpu"
    recorded_runtime_sha256 = str(
        runtime_record.get("sha256") if isinstance(runtime_record, dict) else ""
    ).casefold()
    recorded_reference_sha256 = str(
        reference_record.get("sha256") if isinstance(reference_record, dict) else ""
    ).casefold()
    recorded_binding_sha256 = str(
        binding_record.get("sha256") if isinstance(binding_record, dict) else ""
    ).casefold()
    recorded_evidence_sha256 = str(
        evidence_record.get("sha256") if isinstance(evidence_record, dict) else ""
    ).casefold()
    theme_record = integrity.get("format_theme") if isinstance(integrity, dict) else None
    recorded_theme_sha256 = str(
        theme_record.get("sha256") if isinstance(theme_record, dict) else ""
    ).casefold()
    reference_values_hash = str(validation.get("reference_plot_values_sha256") or "").casefold()
    generated_values_hash = str(validation.get("generated_plot_values_sha256") or "").casefold()
    reference_mapping_hash = str(validation.get("reference_plot_mapping_sha256") or "").casefold()
    generated_mapping_hash = str(validation.get("generated_plot_mapping_sha256") or "").casefold()
    return (
        str(raw.get("status") or "").casefold() == "accepted"
        and str(validation.get("status") or "").casefold() == "accepted"
        and (
            not strict_otpu_binding
            or (
                validation_asset_kind == runtime_kind
                and validation_asset_path == runtime_path
                and re.fullmatch(r"[0-9a-f]{64}", runtime_sha256) is not None
                and validation_asset_sha256
                == runtime_sha256
                == recorded_runtime_sha256
                and re.fullmatch(r"[0-9a-f]{64}", validation_reference_sha256)
                is not None
                and validation_reference_sha256
                == str(raw.get("source_opju_hash") or "").casefold()
                == recorded_reference_sha256
                and re.fullmatch(r"[0-9a-f]{64}", validation_binding_sha256)
                is not None
                and validation_binding_sha256 == recorded_binding_sha256
                and re.fullmatch(r"[0-9a-f]{64}", validation_evidence_sha256)
                is not None
                and validation_evidence_sha256 == recorded_evidence_sha256
                and (
                    not validation_theme_sha256
                    or (
                        re.fullmatch(r"[0-9a-f]{64}", validation_theme_sha256)
                        is not None
                        and validation_theme_sha256 == recorded_theme_sha256
                    )
                )
                and validation.get("axis_title_hard_gate") is True
            )
        )
        and str(validation.get("comparison_scope") or "").casefold()
        == RUNTIME_VALIDATION_SCOPE
        and validation.get("fresh_project_verified") is True
        and validation.get("style_asset_only") is True
        and validation.get("same_data_verified") is True
        and re.fullmatch(r"[0-9a-f]{64}", reference_values_hash) is not None
        and reference_values_hash == generated_values_hash
        and re.fullmatch(r"[0-9a-f]{64}", reference_mapping_hash) is not None
        and reference_mapping_hash == generated_mapping_hash
        and validation.get("saved_reopened") is True
        and validation.get("native_tif_600dpi_verified") is True
        and validation.get("manual_preview_passed") is True
        and validation.get("exact_pixel_match") is True
        and validation.get("same_size") is True
        and validation.get("changed_pixels") == 0
        and validation.get("rms") == 0
        and validation.get("reference_opju_self_replay") is not True
    )


def _runtime_style_asset_binding(
    raw: dict[str, object],
) -> tuple[str, str, str, str]:
    kind = str(raw.get("asset_kind") or "").casefold().lstrip(".")
    if not kind and str(raw.get("format_theme") or "").strip():
        # Backward-compatible OTH entries keep their established runtime
        # behavior.  Exact asset/path/hash binding is mandatory for newly
        # activated OTPU assets, not retroactively for unrelated OTH users.
        kind = "oth"
    field = {"oth": "format_theme", "otpu": "graph_template"}.get(kind, "")
    relative_path = str(raw.get(field) or "").strip().replace("\\", "/") if field else ""
    return kind, field, relative_path, str(raw.get("sha256") or "").casefold()


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
