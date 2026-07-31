from __future__ import annotations

import os
from pathlib import Path

import pytest

import src.core.file_utils as file_utils
from src.processors.base import process_supported, process_table_dataset


XRD_CLASSIFICATION = {
    "inferred_data_type": "XRD",
    "selected_processor": "xrd_processor",
    "supported_in_pipeline": True,
}


def _xrd_source(tmp_path: Path) -> Path:
    source = tmp_path / "raw" / "sample.csv"
    source.parent.mkdir(parents=True)
    source.write_text(
        "2theta,intensity\n10,1\n20,4\n30,2\n",
        encoding="utf-8",
    )
    return source


def test_process_preflights_metadata_before_writing_processed_csv(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = _xrd_source(tmp_path)
    output_root = tmp_path / "output"
    metadata = output_root / "metadata" / "XRD" / "sample" / "metadata.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_bytes(b"preserve")

    with pytest.raises(FileExistsError, match="force=True"):
        process_table_dataset(
            project,
            XRD_CLASSIFICATION,
            source,
            no_origin=True,
            output_root=output_root,
        )

    assert metadata.read_bytes() == b"preserve"
    assert not (
        output_root / "processed_data" / "XRD" / "sample_processed.csv"
    ).exists()


def test_process_supported_default_does_not_overwrite_existing_outputs(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = _xrd_source(tmp_path)
    output_root = tmp_path / "output"
    manifest = {
        "classifications": [
            {
                **XRD_CLASSIFICATION,
                "files": [str(source)],
            }
        ]
    }

    first = process_supported(
        project,
        manifest,
        no_origin=True,
        output_root=output_root,
    )
    processed = output_root / "processed_data" / "XRD" / "sample_processed.csv"
    original = processed.read_bytes()

    with pytest.raises(FileExistsError, match="force=True"):
        process_supported(
            project,
            manifest,
            no_origin=True,
            output_root=output_root,
        )

    assert first[0]["processing_status"] == "processed_no_origin"
    assert processed.read_bytes() == original


def test_process_force_rejects_reparse_leaf_before_any_output_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = _xrd_source(tmp_path)
    output_root = tmp_path / "output"
    processed = output_root / "processed_data" / "XRD" / "sample_processed.csv"
    processed.parent.mkdir(parents=True)
    processed.write_bytes(b"preserve")
    processed_key = file_utils.lexical_absolute_path(processed)
    original_check = file_utils._path_is_link_or_reparse
    monkeypatch.setattr(
        file_utils,
        "_path_is_link_or_reparse",
        lambda path: file_utils.lexical_absolute_path(path) == processed_key
        or original_check(path),
    )

    with pytest.raises(ValueError, match="symlink, junction, or reparse"):
        process_table_dataset(
            project,
            XRD_CLASSIFICATION,
            source,
            no_origin=True,
            force=True,
            output_root=output_root,
        )

    assert processed.read_bytes() == b"preserve"
    assert not (output_root / "metadata").exists()


def test_process_force_unlinks_hardlink_before_creating_processed_csv(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = _xrd_source(tmp_path)
    output_root = tmp_path / "output"
    external = tmp_path / "external-preserve.bin"
    external.write_bytes(b"external-hardlink-content")
    processed = output_root / "processed_data" / "XRD" / "sample_processed.csv"
    processed.parent.mkdir(parents=True)
    try:
        os.link(external, processed)
    except OSError as exc:
        pytest.skip(f"hard links unavailable in this environment: {exc}")

    metadata = process_table_dataset(
        project,
        XRD_CLASSIFICATION,
        source,
        no_origin=True,
        force=True,
        output_root=output_root,
    )

    assert metadata["processing_status"] == "processed_no_origin"
    assert external.read_bytes() == b"external-hardlink-content"
    assert processed.read_text(encoding="utf-8").startswith(
        "two_theta_deg,intensity"
    )
    assert os.stat(external).st_nlink == 1
