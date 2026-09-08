from __future__ import annotations

import re
from pathlib import Path


ASSISTANT_TRACE_PATTERN = re.compile(r"(?i)(codex|codexdata|\.codex|openai|chatgpt)")
WINDOWS_ABSOLUTE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
POSIX_TEXT_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_:/])/(?!/)[^/\r\n;|]+/[^;\r\n|]+"
)


def render_output_path(
    path: str | Path | None,
    *,
    project_root: Path | None = None,
    output_root: Path | None = None,
    external_prefix: str = "external",
) -> str | None:
    """Render a path for output metadata/reports without local machine prefixes."""
    if path is None:
        return None
    text = str(path).replace("\\", "/")
    value = Path(text)
    if not str(value):
        return ""

    roots: list[tuple[str, Path]] = []
    if project_root is not None:
        roots.append(("", project_root))
    if output_root is not None:
        roots.append(("output", output_root))

    for prefix, root in roots:
        if WINDOWS_ABSOLUTE_PATTERN.match(text) and not value.is_absolute():
            # A Windows drive path is not relative to the POSIX process cwd.
            break
        try:
            relative = value.resolve().relative_to(root.resolve()).as_posix()
            if relative == ".":
                return prefix or "."
            return f"{prefix}/{relative}".strip("/")
        except (OSError, ValueError):
            continue

    if WINDOWS_ABSOLUTE_PATTERN.match(text) or text.startswith("/"):
        return f"{external_prefix}/{value.name}"
    return text


def scrub_output_text(text: object, *, project_root: Path | None = None, output_root: Path | None = None) -> str:
    """Best-effort cleanup for strings that may already contain local paths."""
    rendered = str(text).replace("\\", "/")
    for root in (project_root, output_root):
        if root is None:
            continue
        root_text = str(root).replace("\\", "/").rstrip("/")
        if root_text:
            rendered = rendered.replace(root_text + "/", "")
            rendered = rendered.replace(root_text, ".")
    rendered = re.sub(r"(?<![A-Za-z0-9_])[A-Za-z]:/[^\r\n;|]+", _external_text_path, rendered)
    rendered = re.sub(r"(?<![A-Za-z0-9_:])//[^/\r\n;|]+/[^;\r\n|]+", _external_text_path, rendered)
    rendered = POSIX_TEXT_PATH_PATTERN.sub(_external_text_path, rendered)
    return ASSISTANT_TRACE_PATTERN.sub("local", rendered)


def sanitize_report_payload(project_root: Path, value: object, output_root: Path | None = None) -> object:
    if isinstance(value, dict):
        return {str(key): sanitize_report_payload(project_root, item, output_root) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_report_payload(project_root, item, output_root) for item in value]
    if isinstance(value, str):
        return scrub_output_text(value, project_root=project_root, output_root=output_root)
    return value


def _external_text_path(match: re.Match[str]) -> str:
    text = match.group(0).strip()
    tail = text.rstrip("/").split("/")[-1].strip("`'\" .,)]}")
    return f"external/{tail or 'path'}"


def contains_local_absolute_path(value: object) -> bool:
    text = str(value).replace("\\", "/")
    return bool(
        re.search(r"(?:^|[\s\"'`=:\[])[A-Za-z]:/", text)
        or re.search(r"(?<![A-Za-z0-9_:])//[^/]+/[^/]+", text)
        or POSIX_TEXT_PATH_PATTERN.search(text)
    )


def contains_assistant_trace(value: object) -> bool:
    return bool(ASSISTANT_TRACE_PATTERN.search(str(value)))
