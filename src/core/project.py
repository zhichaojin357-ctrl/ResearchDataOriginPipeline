from __future__ import annotations

from pathlib import Path

from src.core.file_utils import is_under_or_equal as _is_under_or_equal


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_OUTPUT_DIRS = (
    "origin_files",
    "figures_tif",
    "figures_preview",
    "processed_data",
    "metadata",
    "reports",
    "origin_jobs",
    "review_dashboard",
    "unclassified",
)


def default_output_root(project_root: Path) -> Path:
    return (project_root.resolve().parent / "\u8f93\u51fa").resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_write_path_allowed(project_root: Path, path: Path, *, output_root: Path | None = None) -> Path:
    resolved_project = project_root.resolve()
    resolved_path = path.resolve()
    resolved_default_output = default_output_root(project_root)
    resolved_project_output = (resolved_project / "output").resolve()
    allowed_roots = [
        resolved_default_output,
    ]
    if output_root is not None:
        resolved_output_root = output_root if output_root.is_absolute() else resolved_project / output_root
        resolved_output_root = resolved_output_root.resolve()
        if _is_under_or_equal(resolved_output_root, resolved_project) and not _is_under_or_equal(
            resolved_output_root,
            resolved_project_output,
        ):
            raise ValueError(f"Refusing to write runtime outputs inside project tree: {output_root}")
        allowed_roots.append(resolved_output_root)
    if not any(_is_under_or_equal(resolved_path, root) for root in allowed_roots):
        raise ValueError(f"Refusing to write outside allowed project areas: {path}")
    return path


def output_dir(project_root: Path, *parts: str, output_root: Path | None = None) -> Path:
    base = output_root if output_root is not None else default_output_root(project_root)
    if not base.is_absolute():
        base = project_root / base
    return ensure_dir(ensure_write_path_allowed(project_root, base / Path(*parts), output_root=base))


def report_path(project_root: Path, name: str, *, output_root: Path | None = None) -> Path:
    return output_dir(project_root, "reports", output_root=output_root) / name


def load_json_compatible_yaml(path: Path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def ensure_output_structure(project_root: Path, *, output_root: Path | None = None) -> None:
    for name in REQUIRED_OUTPUT_DIRS:
        output_dir(project_root, name, output_root=output_root)


def load_project_config(project_root: Path, config_path: Path | None) -> dict:
    path = config_path or Path("config/default.yaml")
    if not path.is_absolute():
        path = project_root / path
    if not path.exists():
        config: dict = {}
    else:
        config = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    local_path = project_root / "config" / "local.yaml"
    if local_path.exists() and local_path != path:
        config = _deep_merge(config, _parse_simple_yaml(local_path.read_text(encoding="utf-8")))
    return config


def configured_path(project_root: Path, config: dict, section: str, key: str, default: str) -> Path:
    value = config.get(section, {}).get(key, default)
    path = Path(str(value))
    return path if path.is_absolute() else project_root / path


def _parse_simple_yaml(text: str) -> dict:
    result: dict[str, object] = {}
    current_section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")) and line.endswith(":"):
            current_section = line[:-1].strip()
            result[current_section] = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        parsed: object = value.strip().strip('"')
        if parsed == "true":
            parsed = True
        elif parsed == "false":
            parsed = False
        if raw_line.startswith((" ", "\t")) and current_section:
            section = result.setdefault(current_section, {})
            if isinstance(section, dict):
                section[key] = parsed
        else:
            result[key] = parsed
    return result


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = value
    return result


def registry_path(project_root: Path) -> Path:
    local = project_root / "config" / "processor_registry.yaml"
    if local.exists():
        return local
    return REPO_ROOT / "config" / "processor_registry.yaml"


def claim_policy_path(project_root: Path) -> Path:
    local = project_root / "config" / "claim_policy.yaml"
    if local.exists():
        return local
    return REPO_ROOT / "config" / "claim_policy.yaml"
