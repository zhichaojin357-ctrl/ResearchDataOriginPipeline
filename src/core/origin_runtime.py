from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def neutral_origin_runtime_root() -> Path:
    candidates: list[Path] = []
    for name in ("LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value) / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path.home() / "AppData" / "Local" / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path("C:/ResearchDataOriginPipeline/origin_runtime"))
    candidates.append(Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime")
    for candidate in candidates:
        if "codex" in str(candidate).casefold():
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    fallback = Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def copy_runtime_artifact(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    shutil.copy2(source, target)
