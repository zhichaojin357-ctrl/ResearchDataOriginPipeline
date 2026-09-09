from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from src.core.file_utils import is_under_or_equal as _is_under_or_equal


REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_READS: ContextVar[dict[Path, dict] | None] = ContextVar("project_config_reads", default=None)
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


def ensure_output_path_within_root(project_root: Path, path: Path, output_root: Path) -> Path:
    resolved_project = project_root.resolve()
    resolved_root = output_root if output_root.is_absolute() else resolved_project / output_root
    resolved_path = path if path.is_absolute() else resolved_root / path
    resolved_root = resolved_root.resolve()
    resolved_path = resolved_path.resolve()
    if not _is_under_or_equal(resolved_path, resolved_root):
        raise ValueError(f"Output path must stay under the configured output root: {path}")
    ensure_write_path_allowed(project_root, resolved_path, output_root=resolved_root)
    return resolved_path


def ensure_output_path_separate_from_inputs(
    project_root: Path,
    output_path: Path,
    input_paths: list[Path] | tuple[Path, ...],
) -> Path:
    resolved_project = project_root.resolve()
    resolved_output = output_path if output_path.is_absolute() else resolved_project / output_path
    resolved_output = resolved_output.resolve()
    protected_inputs = [resolved_project / "input" / "raw_data", *input_paths]
    for input_path in protected_inputs:
        resolved_input = input_path if input_path.is_absolute() else resolved_project / input_path
        resolved_input = resolved_input.resolve()
        if _is_under_or_equal(resolved_output, resolved_input) or _is_under_or_equal(resolved_input, resolved_output):
            raise ValueError(
                f"Output path overlaps protected input path: output={resolved_output}; input={resolved_input}"
            )
    return resolved_output


def output_dir(project_root: Path, *parts: str, output_root: Path | None = None) -> Path:
    base = output_root if output_root is not None else default_output_root(project_root)
    if not base.is_absolute():
        base = project_root / base
    return ensure_dir(ensure_write_path_allowed(project_root, base / Path(*parts), output_root=base))


def report_path(project_root: Path, name: str, *, output_root: Path | None = None) -> Path:
    return output_dir(project_root, "reports", output_root=output_root) / name


def load_json_compatible_yaml(path: Path):
    import json

    cache = _CONFIG_READS.get()
    key = path.resolve()
    if cache is not None and key in cache:
        return cache[key]
    config = json.loads(path.read_text(encoding="utf-8"))
    if cache is not None:
        cache[key] = config
    return config


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
        config = read_project_yaml(path)
    local_path = project_root / "config" / "local.yaml"
    if local_path.exists() and local_path != path:
        config = _deep_merge(config, read_project_yaml(local_path))
    return config


@contextmanager
def project_config_scope():
    """Reuse parsed configuration within one command, never across commands."""
    if _CONFIG_READS.get() is not None:
        yield
        return
    token = _CONFIG_READS.set({})
    try:
        yield
    finally:
        _CONFIG_READS.reset(token)


def read_project_yaml(path: Path) -> dict:
    cache = _CONFIG_READS.get()
    key = path.resolve()
    if cache is not None and key in cache:
        return cache[key]
    config = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    if cache is not None:
        cache[key] = config
    return config


def configured_path(project_root: Path, config: dict, section: str, key: str, default: str) -> Path:
    value = config.get(section, {}).get(key, default)
    path = Path(str(value))
    return path if path.is_absolute() else project_root / path


def _parse_simple_yaml(text: str) -> dict:
    import yaml

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError:
        repaired = _escape_double_quoted_windows_paths(text)
        try:
            loaded = yaml.safe_load(repaired)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid project YAML configuration: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Project configuration must be a YAML mapping")
    return loaded


def _escape_double_quoted_windows_paths(text: str) -> str:
    pattern = re.compile(
        r'^(?P<prefix>\s*[^#\s][^:\r\n]*:\s*)"(?P<path>(?:[A-Za-z]:\\|\\\\)[^"\r\n]*)"(?P<suffix>\s*(?:#.*)?)$',
        re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        escaped = match.group("path").replace("\\", "\\\\")
        return f'{match.group("prefix")}"{escaped}"{match.group("suffix")}'

    return pattern.sub(replace, text)


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
