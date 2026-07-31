from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_under_or_equal(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return path == parent


def lexical_absolute_path(path: Path) -> Path:
    """Return an absolute normalized path without resolving filesystem links."""

    return Path(os.path.abspath(os.fspath(path)))


def ensure_safe_output_file_target(path: Path, *, output_root: Path) -> Path:
    """Validate a planned file target without following its leaf or parents.

    Output deletion and overwrite callers must operate on the returned lexical
    path only.  Any symlink, junction, or other Windows reparse point in the
    target chain is rejected, including when an explicit force option is used.
    """

    target = lexical_absolute_path(path)
    root = lexical_absolute_path(output_root)
    if not is_under_or_equal(target, root):
        raise ValueError(f"Planned output file escapes output root: {path}")

    for candidate in (target, *target.parents):
        if _path_is_link_or_reparse(candidate):
            raise ValueError(
                "Refusing output file target through a symlink, junction, or "
                f"reparse point: {candidate}"
            )
        if candidate != target and candidate.exists() and not candidate.is_dir():
            raise NotADirectoryError(
                f"Planned output file has a non-directory parent: {candidate}"
            )
    return target


def prepare_safe_output_file_targets(
    paths: tuple[Path, ...] | list[Path],
    *,
    output_root: Path,
    force: bool,
    context: str = "output",
) -> tuple[Path, ...]:
    """Validate all planned files, then optionally unlink existing names.

    Unlink-before-create is intentional: it prevents a force overwrite from
    truncating another pathname that shares the same inode through a hard link.
    No deletion occurs until every target has passed the link/reparse and root
    boundary checks.
    """

    safe_paths = tuple(
        dict.fromkeys(
            ensure_safe_output_file_target(path, output_root=output_root)
            for path in paths
        )
    )
    existing = [
        path for path in safe_paths if os.path.lexists(os.fspath(path))
    ]
    directories = [path for path in existing if path.is_dir()]
    if directories:
        rendered = ", ".join(str(path) for path in directories[:8])
        raise IsADirectoryError(
            f"Planned {context} file target collides with a directory: {rendered}"
        )
    if existing and not force:
        rendered = ", ".join(str(path) for path in existing[:8])
        raise FileExistsError(
            f"One or more planned {context} files already exist; "
            f"rerun with force=True to overwrite: {rendered}"
        )
    if force:
        for path in existing:
            path.unlink()
    return safe_paths


def plan_safe_owned_directory_removal(
    directory: Path,
    *,
    output_root: Path,
) -> tuple[Path, tuple[Path, ...], tuple[Path, ...]]:
    """Validate one task-owned directory tree and return a safe removal plan.

    The function performs no deletion. Every descendant is inspected before a
    caller removes anything, so a reparse point or special filesystem entry
    fails the whole overwrite transaction without partially clearing outputs.
    """

    root = ensure_safe_output_file_target(directory, output_root=output_root)
    if not os.path.lexists(os.fspath(root)):
        return root, (), ()
    if not root.is_dir():
        raise NotADirectoryError(f"Owned output directory target is not a directory: {root}")

    files: list[Path] = []
    directories: list[Path] = []

    def visit(parent: Path) -> None:
        for child in parent.iterdir():
            safe_child = ensure_safe_output_file_target(child, output_root=output_root)
            if safe_child.is_dir():
                visit(safe_child)
                directories.append(safe_child)
            elif safe_child.is_file():
                files.append(safe_child)
            else:
                raise ValueError(
                    f"Owned output directory contains an unsupported filesystem entry: {safe_child}"
                )

    visit(root)
    return root, tuple(files), tuple(directories)


def apply_safe_owned_directory_removal(
    plan: tuple[Path, tuple[Path, ...], tuple[Path, ...]],
    *,
    output_root: Path,
) -> None:
    """Apply a previously validated task-owned directory removal plan."""

    root, files, directories = plan
    for path in files:
        safe_path = ensure_safe_output_file_target(path, output_root=output_root)
        if not safe_path.is_file():
            raise RuntimeError(f"Owned output file changed after preflight: {safe_path}")
        safe_path.unlink()
    for path in directories:
        safe_path = ensure_safe_output_file_target(path, output_root=output_root)
        if not safe_path.is_dir():
            raise RuntimeError(f"Owned output directory changed after preflight: {safe_path}")
        safe_path.rmdir()
    safe_root = ensure_safe_output_file_target(root, output_root=output_root)
    if not safe_root.is_dir():
        raise RuntimeError(f"Owned output directory changed after preflight: {safe_root}")
    safe_root.rmdir()


def _path_is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            return False
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(reparse_flag and attributes & reparse_flag)
    except OSError as exc:
        raise ValueError(f"Unable to inspect planned output path safely: {path}") from exc
