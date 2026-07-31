from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

from src.core.file_utils import (
    apply_safe_owned_directory_removal,
    ensure_safe_output_file_target,
    lexical_absolute_path,
    plan_safe_owned_directory_removal,
)


def neutral_origin_runtime_root() -> Path:
    candidates: list[Path] = []
    for name in ("LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value) / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path.home() / "AppData" / "Local" / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path("C:/ResearchDataOriginPipeline/origin_runtime"))
    candidates.append(Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime")
    errors: list[str] = []
    for candidate in candidates:
        if "codex" in str(candidate).casefold():
            continue
        candidate = lexical_absolute_path(candidate)
        try:
            ensure_safe_output_file_target(
                candidate / ".rdop_runtime_preflight",
                output_root=candidate,
            )
            candidate.mkdir(parents=True, exist_ok=True)
            ensure_safe_output_file_target(
                candidate / ".rdop_runtime_preflight",
                output_root=candidate,
            )
            return candidate
        except (OSError, ValueError) as exc:
            errors.append(f"{candidate}: {type(exc).__name__}: {exc}")
            continue
    details = "; ".join(errors[-3:]) or "no eligible neutral runtime candidate"
    raise RuntimeError(
        "Could not create a reparse-safe neutral Origin runtime root: " + details
    )


def copy_runtime_artifact(source: Path, target: Path) -> None:
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Origin runtime artifact is missing: {source}")
    target = lexical_absolute_path(target)
    safe_target = ensure_safe_output_file_target(target, output_root=target.parent)
    safe_target.parent.mkdir(parents=True, exist_ok=True)
    safe_target = ensure_safe_output_file_target(
        safe_target,
        output_root=safe_target.parent,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{safe_target.name}.",
        suffix=".tmp",
        dir=safe_target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        ensure_safe_output_file_target(safe_target, output_root=safe_target.parent)
        if os.path.lexists(os.fspath(safe_target)) and safe_target.is_dir():
            raise IsADirectoryError(
                f"Origin runtime artifact target is a directory: {safe_target}"
            )
        os.replace(temporary, safe_target)
    finally:
        if os.path.lexists(os.fspath(temporary)):
            temporary.unlink()


def cleanup_origin_runtime_directory(
    path: Path | None,
    *,
    retries: int = 20,
    retry_delay_seconds: float = 0.1,
) -> dict[str, object]:
    """Remove one owned Origin runtime directory after COM has been released.

    Origin can retain an OPJU file handle briefly after ``Application.Exit``.
    Cleanup is therefore bounded and retryable, but is restricted to a single
    ``rdop_origin_*`` directory below the neutral runtime root.
    """

    if path is None:
        return {"ok": True, "status": "not_created", "attempts": 0}
    target = lexical_absolute_path(path)
    root = lexical_absolute_path(neutral_origin_runtime_root())
    try:
        target.relative_to(root)
    except ValueError:
        return {
            "ok": False,
            "status": "refused_outside_runtime_root",
            "attempts": 0,
            "runtime_directory": target.name,
        }
    if target.parent != root or not target.name.startswith("rdop_origin_"):
        return {
            "ok": False,
            "status": "refused_unowned_runtime_directory",
            "attempts": 0,
            "runtime_directory": target.name,
        }
    try:
        ensure_safe_output_file_target(target, output_root=root)
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "status": "refused_unsafe_runtime_directory",
            "attempts": 0,
            "runtime_directory": target.name,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not os.path.lexists(os.fspath(target)):
        return {
            "ok": True,
            "status": "already_removed",
            "attempts": 0,
            "runtime_directory": target.name,
        }

    last_error = ""
    max_attempts = max(1, int(retries))
    for attempt in range(1, max_attempts + 1):
        try:
            plan = plan_safe_owned_directory_removal(target, output_root=root)
            apply_safe_owned_directory_removal(plan, output_root=root)
            return {
                "ok": True,
                "status": "removed",
                "attempts": attempt,
                "runtime_directory": target.name,
            }
        except FileNotFoundError:
            return {
                "ok": True,
                "status": "already_removed",
                "attempts": attempt,
                "runtime_directory": target.name,
            }
        except (OSError, RuntimeError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < max_attempts and retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)
    return {
        "ok": False,
        "status": "retained_after_bounded_retries",
        "attempts": max_attempts,
        "runtime_directory": target.name,
        "error": last_error,
    }
