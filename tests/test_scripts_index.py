from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_INDEX = PROJECT_ROOT / "docs" / "indexes" / "scripts_index.md"
SCRIPT_SUFFIXES = {".py", ".ps1"}


def _normal(path_text: str) -> str:
    return path_text.replace("\\", "/")


def _indexed_script_paths() -> set[str]:
    text = SCRIPT_INDEX.read_text(encoding="utf-8")
    return {_normal(match) for match in re.findall(r"\| `([^`]+)` \|", text)}


def _current_script_paths() -> set[str]:
    paths: set[str] = set()
    for path in (PROJECT_ROOT / "scripts").rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.name == "README.md" or path.suffix.lower() in SCRIPT_SUFFIXES:
            paths.add(path.relative_to(PROJECT_ROOT).as_posix())
    return paths


def test_scripts_index_covers_current_script_sources() -> None:
    indexed = _indexed_script_paths()
    current = _current_script_paths()

    assert sorted(current - indexed) == []
    assert sorted(indexed - current) == []
