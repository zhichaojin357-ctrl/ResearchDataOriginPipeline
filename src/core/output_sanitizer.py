from __future__ import annotations

import re
from pathlib import Path


ASSISTANT_TRACE_PATTERN = re.compile(r"(?i)(codex|codexdata|\.codex|openai|chatgpt)")
WINDOWS_ABSOLUTE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
UNC_ABSOLUTE_PATTERN = re.compile(r"^[\\/]{2}[^\\/]+[\\/][^\\/]+")


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
    value = Path(str(path))
    if not str(value):
        return ""

    roots: list[tuple[str, Path]] = []
    if project_root is not None:
        roots.append(("", project_root))
    if output_root is not None:
        roots.append(("output", output_root))

    for prefix, root in roots:
        try:
            relative = value.resolve().relative_to(root.resolve()).as_posix()
            if relative == ".":
                return prefix or "."
            return f"{prefix}/{relative}".strip("/")
        except (OSError, ValueError):
            continue

    text = str(path).replace("\\", "/")
    if WINDOWS_ABSOLUTE_PATTERN.match(text) or UNC_ABSOLUTE_PATTERN.match(text):
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
    rendered = re.sub(r"(?<![A-Za-z0-9_])//[^/\r\n;|]+/[^;\r\n|]+", _external_text_path, rendered)
    return ASSISTANT_TRACE_PATTERN.sub("local", rendered)


def _external_text_path(match: re.Match[str]) -> str:
    text = match.group(0).strip()
    tail = text.rstrip("/").split("/")[-1].strip("`'\" .,)]}")
    return f"external/{tail or 'path'}"


def contains_local_absolute_path(value: object) -> bool:
    text = str(value).replace("\\", "/")
    return bool(
        re.search(r"(?:^|[\s\"'`=:\[])[A-Za-z]:/", text)
        or re.search(r"(?:^|[\s\"'`=:\[])/{2}[^/]+/[^/]+", text)
    )


def contains_assistant_trace(value: object) -> bool:
    return bool(ASSISTANT_TRACE_PATTERN.search(str(value)))
