from pathlib import Path

import pytest

from src.core.file_utils import (
    ensure_safe_output_file_target,
    lexical_absolute_path,
)


def test_safe_output_file_target_rejects_symlink_leaf_even_when_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    target = output_root / "result.xlsx"
    target_key = lexical_absolute_path(target)
    original_is_symlink = Path.is_symlink

    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: lexical_absolute_path(path) == target_key
        or original_is_symlink(path),
    )

    with pytest.raises(ValueError, match="symlink, junction, or reparse"):
        ensure_safe_output_file_target(target, output_root=output_root)


def test_safe_output_file_target_rejects_junction_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    unsafe_parent = output_root / "linked"
    unsafe_parent.mkdir(parents=True)
    target = unsafe_parent / "result.xlsx"
    parent_key = lexical_absolute_path(unsafe_parent)
    original_is_junction = Path.is_junction

    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: lexical_absolute_path(path) == parent_key
        or original_is_junction(path),
    )

    with pytest.raises(ValueError, match="symlink, junction, or reparse"):
        ensure_safe_output_file_target(target, output_root=output_root)


def test_safe_output_file_target_rejects_lexical_escape(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    escaped = output_root / ".." / "raw" / "source.dat"

    with pytest.raises(ValueError, match="escapes output root"):
        ensure_safe_output_file_target(escaped, output_root=output_root)
