from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.output_sanitizer import render_output_path
from src.core.project import default_output_root
from src.core.project import ensure_write_path_allowed
from src.core.project import load_project_config
from src.core.project import _parse_simple_yaml


DEFAULT_LOCKED_RESULT_PACKAGE_NAME = Path("locked_origin_results_20260531_041538")
LEGACY_WORKSPACE_ROOT = Path("workspace_data") / "LL_detection_copy_20260530"
LEGACY_F_DRIVE_BACKUP = Path("F:/课题/LL/检测")
LEGACY_ORIGIN_HELPER = Path("scripts") / "origin" / "origin_plot_from_template.ps1"
LEGACY_ORIGIN_REFERENCE_PATTERN = "templates/origin_styles/reference_opju/XRD.opju"

LOCKED_RESULT_PACKAGE_ENV = "RESEARCHDATAORIGINPIPELINE_LOCKED_RESULT_PACKAGE"
WORKSPACE_ROOT_ENV = "RESEARCHDATAORIGINPIPELINE_WORKSPACE_ROOT"
F_DRIVE_BACKUP_ENV = "RESEARCHDATAORIGINPIPELINE_F_DRIVE_BACKUP"
ORIGIN_HELPER_ENV = "RESEARCHDATAORIGINPIPELINE_ORIGIN_HELPER"
ORIGIN_REFERENCE_PATTERN_ENV = "RESEARCHDATAORIGINPIPELINE_ORIGIN_REFERENCE_PATTERN"
OUTPUT_ROOT_ENV = "RESEARCH_PIPELINE_OUTPUT_ROOT"
OUTPUT_ROOT_COMPAT_ENV = "RESEARCHDATAORIGINPIPELINE_OUTPUT_ROOT"
RUN_OUTPUT_SUBDIRS = (
    "processed_data",
    "metadata",
    "origin_files",
    "figures_tif",
    "figures_preview",
    "reports",
    "logs",
)


@dataclass(frozen=True)
class RunOutputLayout:
    run_id: str
    root: Path
    processed_data: Path
    metadata: Path
    origin_files: Path
    figures_tif: Path
    figures_preview: Path
    reports: Path
    logs: Path
    manifest: Path


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def resolve_output_root(
    project_root: Path,
    explicit: str | Path | None = None,
    *,
    config_path: str | Path | None = None,
) -> Path:
    explicit_value = str(explicit).strip() if explicit is not None else ""
    if explicit_value:
        return _checked_output_root(project_root, resolve_project_path(project_root, explicit_value))

    local_path = project_root / "config" / "local.yaml"
    value = _config_file_value(local_path, "paths", "output_root")
    if value:
        return _checked_output_root(project_root, resolve_project_path(project_root, value))

    value = _first_nonempty(os.environ.get(OUTPUT_ROOT_ENV), os.environ.get(OUTPUT_ROOT_COMPAT_ENV))
    if value:
        return _checked_output_root(project_root, resolve_project_path(project_root, value))

    default_path = Path(config_path) if config_path is not None else Path("config/default.yaml")
    value = _first_nonempty(
        _config_file_value(_resolve_config_path(project_root, default_path), "paths", "output_root"),
        _config_file_value(_resolve_config_path(project_root, default_path), "paths", "output"),
    )
    return _checked_output_root(project_root, resolve_project_path(project_root, value)) if value else default_output_root(project_root)


def create_run_output_layout(
    project_root: Path,
    *,
    scope: str,
    command: str,
    mode: str,
    input_paths: list[Path] | tuple[Path, ...] | None = None,
    timestamp: str | None = None,
    no_origin: bool | None = None,
    dry_run: bool | None = None,
    output_base: Path | None = None,
    warnings: list[str] | None = None,
    compatibility_mode: str = "run_scoped",
) -> RunOutputLayout:
    normalized_scope = _safe_run_scope(scope)
    run_timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{run_timestamp}_{normalized_scope}"
    base = output_base or resolve_output_root(project_root) / "runs"
    root = base / run_id
    ensure_write_path_allowed(project_root, root, output_root=base)
    directories = {name: root / name for name in RUN_OUTPUT_SUBDIRS}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "run_manifest.json"
    manifest_payload = {
        "run_id": run_id,
        "timestamp": run_timestamp,
        "command": command,
        "mode": mode,
        "scope": normalized_scope,
        "project_root": ".",
        "output_root": render_output_path(root, project_root=project_root, output_root=base),
        "input_paths": [
            render_output_path(path, project_root=project_root, output_root=base) for path in input_paths or []
        ],
        "no_origin": no_origin,
        "dry_run": dry_run,
        "produced_artifact_directories": {
            name: render_output_path(path, project_root=project_root, output_root=base)
            for name, path in directories.items()
        },
        "warnings": list(warnings or []),
        "compatibility_mode": compatibility_mode,
    }
    import json

    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return RunOutputLayout(
        run_id=run_id,
        root=root,
        processed_data=directories["processed_data"],
        metadata=directories["metadata"],
        origin_files=directories["origin_files"],
        figures_tif=directories["figures_tif"],
        figures_preview=directories["figures_preview"],
        reports=directories["reports"],
        logs=directories["logs"],
        manifest=manifest_path,
    )


def _safe_run_scope(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().casefold())
    return cleaned.strip("_") or "run"


def _checked_output_root(project_root: Path, output_root: Path) -> Path:
    ensure_write_path_allowed(project_root, output_root, output_root=output_root)
    return output_root


def resolve_locked_result_package(project_root: Path, override: str | Path | None = None) -> Path:
    explicit_value = _first_nonempty(
        str(override) if override is not None else None,
        os.environ.get(LOCKED_RESULT_PACKAGE_ENV),
    )
    if explicit_value:
        path = resolve_project_path(project_root, explicit_value)
        return path.parent if path.name.casefold() == "index.csv" else path

    configured_value = _config_value(project_root, "paths", "locked_origin_results")
    if configured_value:
        path = resolve_project_path(project_root, configured_value)
        if path.exists():
            return path.parent if path.name.casefold() == "index.csv" else path

    output_root = resolve_output_root(project_root)
    discovered = _latest_existing_dir_with_index(output_root, "*origin_results*")
    if discovered is not None:
        return discovered
    if configured_value:
        path = resolve_project_path(project_root, configured_value)
        return path.parent if path.name.casefold() == "index.csv" else path
    return output_root / DEFAULT_LOCKED_RESULT_PACKAGE_NAME.name


def resolve_locked_result_index(project_root: Path, override: str | Path | None = None) -> Path:
    if override is not None:
        path = resolve_project_path(project_root, override)
        return path if path.suffix.casefold() == ".csv" else path / "index.csv"
    return resolve_locked_result_package(project_root) / "index.csv"


def resolve_workspace_root(project_root: Path, override: str | Path | None = None) -> Path:
    value = _first_nonempty(
        str(override) if override is not None else None,
        os.environ.get(WORKSPACE_ROOT_ENV),
        _config_value(project_root, "paths", "workspace_root"),
        _config_value(project_root, "paths", "current_workspace_copy"),
        _config_value(project_root, "paths", "workspace_source_copy"),
    )
    return resolve_project_path(project_root, value or LEGACY_WORKSPACE_ROOT)


def resolve_optional_f_drive_backup(project_root: Path, override: str | Path | None = None) -> Path | None:
    value = _first_nonempty(
        str(override) if override is not None else None,
        os.environ.get(F_DRIVE_BACKUP_ENV),
        _config_value(project_root, "paths", "f_drive_backup"),
        _config_value(project_root, "paths", "stable_raw_backup"),
    )
    if value:
        return resolve_project_path(project_root, value)
    return None


def resolve_origin_helper(project_root: Path, override: str | Path | None = None) -> Path:
    value = _first_nonempty(
        str(override) if override is not None else None,
        os.environ.get(ORIGIN_HELPER_ENV),
        _plot_style_value(project_root, "helper_script"),
        _config_value(project_root, "origin_template", "helper_script"),
        _config_value(project_root, "paths", "origin_helper_script"),
    )
    if value:
        return resolve_project_path(project_root, value)
    project_helper = resolve_project_path(project_root, LEGACY_ORIGIN_HELPER)
    if project_helper.exists():
        return project_helper
    repo_helper = Path(__file__).resolve().parents[2] / LEGACY_ORIGIN_HELPER
    return repo_helper if repo_helper.exists() else project_helper


def resolve_origin_reference_pattern(project_root: Path, override: str | None = None) -> str:
    value = _first_nonempty(
        override,
        os.environ.get(ORIGIN_REFERENCE_PATTERN_ENV),
        _plot_style_value(project_root, "reference_search_pattern"),
        _plot_style_value(project_root, "default_reference_project"),
        _config_value(project_root, "origin_template", "reference_search_pattern"),
        _config_value(project_root, "origin_template", "default_reference_project"),
    )
    return str(value or LEGACY_ORIGIN_REFERENCE_PATTERN)


def _latest_existing_dir_with_index(parent: Path, pattern: str) -> Path | None:
    if not parent.exists():
        return None
    candidates = [item for item in parent.glob(pattern) if item.is_dir() and (item / "index.csv").is_file()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.stat().st_mtime, item.name), reverse=True)[0]


def _config_value(project_root: Path, section: str, key: str) -> str | None:
    config = load_project_config(project_root, Path("config/default.yaml"))
    value = config.get(section, {}).get(key) if isinstance(config.get(section), dict) else None
    text = str(value).strip() if value is not None else ""
    return text or None


def _plot_style_value(project_root: Path, key: str) -> str | None:
    path = project_root / "config" / "plot_style.yaml"
    if not path.exists():
        return None
    config = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    value = config.get(key)
    if value is None and isinstance(config.get("origin_template"), dict):
        value = config["origin_template"].get(key)
    text = str(value).strip() if value is not None else ""
    return text or None


def _first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _resolve_config_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def _config_file_value(path: Path, section: str, key: str) -> str | None:
    if not path.exists():
        return None
    config = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    section_value = config.get(section)
    value = section_value.get(key) if isinstance(section_value, dict) else None
    text = str(value).strip() if value is not None else ""
    return text or None
