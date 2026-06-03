from __future__ import annotations

import os
from pathlib import Path

from src.core.project import load_project_config


LEGACY_PHASE1_6_PACKAGE = Path("output") / "phase1_6_origin_results_20260531_041538"
LEGACY_WORKSPACE_ROOT = Path("D:/Codex Project/科研数据处理/数据/workspace_data/LL_detection_copy_20260530")
LEGACY_F_DRIVE_BACKUP = Path("F:/课题/LL/检测")
LEGACY_ORIGIN_HELPER = Path(r"D:\CodexData\.codex\skills\origin-plotting\scripts\origin_plot_from_template.ps1")
LEGACY_ORIGIN_REFERENCE_PATTERN = r"D:\OriginFlies\Manual Save\CWO+BOBC+*.opju"

PHASE1_6_PACKAGE_ENV = "RESEARCHDATAORIGINPIPELINE_PHASE1_6_PACKAGE"
WORKSPACE_ROOT_ENV = "RESEARCHDATAORIGINPIPELINE_WORKSPACE_ROOT"
F_DRIVE_BACKUP_ENV = "RESEARCHDATAORIGINPIPELINE_F_DRIVE_BACKUP"
ORIGIN_HELPER_ENV = "RESEARCHDATAORIGINPIPELINE_ORIGIN_HELPER"
ORIGIN_REFERENCE_PATTERN_ENV = "RESEARCHDATAORIGINPIPELINE_ORIGIN_REFERENCE_PATTERN"


def resolve_project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else project_root / path


def resolve_phase1_6_package(project_root: Path, override: str | Path | None = None) -> Path:
    value = _first_nonempty(
        str(override) if override is not None else None,
        os.environ.get(PHASE1_6_PACKAGE_ENV),
        _config_value(project_root, "paths", "phase1_6_origin_results"),
    )
    if value:
        path = resolve_project_path(project_root, value)
        return path.parent if path.name.casefold() == "index.csv" else path
    discovered = _latest_existing_dir(project_root / "output", "phase1_6_origin_results_*")
    if discovered is not None:
        return discovered
    return project_root / LEGACY_PHASE1_6_PACKAGE


def resolve_phase1_6_index(project_root: Path, override: str | Path | None = None) -> Path:
    if override is not None:
        path = resolve_project_path(project_root, override)
        return path if path.suffix.casefold() == ".csv" else path / "index.csv"
    return resolve_phase1_6_package(project_root) / "index.csv"


def resolve_workspace_root(project_root: Path, override: str | Path | None = None) -> Path:
    value = _first_nonempty(
        str(override) if override is not None else None,
        os.environ.get(WORKSPACE_ROOT_ENV),
        _config_value(project_root, "paths", "workspace_root"),
        _config_value(project_root, "paths", "current_workspace_copy"),
        _config_value(project_root, "paths", "phase1_2_source_copy"),
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
    return resolve_project_path(project_root, value or LEGACY_ORIGIN_HELPER)


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


def _latest_existing_dir(parent: Path, pattern: str) -> Path | None:
    if not parent.exists():
        return None
    candidates = [item for item in parent.glob(pattern) if item.is_dir()]
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
    from src.core.project import _parse_simple_yaml

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
