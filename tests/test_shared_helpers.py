from __future__ import annotations

from pathlib import Path

import pytest

from src.core.file_utils import file_sha256, is_under_or_equal
from src.core.image_artifacts import (
    TifResolutionValidationError,
    _metadata_text_contains_local_path,
    _metadata_text_values,
    expected_raster_pixels,
    validate_tif_physical_resolution,
)
from src.core.origin_runtime import (
    cleanup_origin_runtime_directory,
    copy_runtime_artifact,
)
from src.core.output_sanitizer import sanitize_report_payload
from src.core.xrd_helpers import interpolated_y, relative_path, to_finite_float


def test_copy_runtime_artifact_replaces_existing_target(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    target = tmp_path / "nested" / "target.txt"
    source.write_text("new", encoding="utf-8")
    target.parent.mkdir()
    target.write_text("old", encoding="utf-8")

    copy_runtime_artifact(source, target)

    assert target.read_text(encoding="utf-8") == "new"


def test_copy_runtime_artifact_replaces_hardlink_name_without_mutating_sibling(
    tmp_path: Path,
) -> None:
    import os

    source = tmp_path / "source.txt"
    target = tmp_path / "target.txt"
    sibling = tmp_path / "sibling.txt"
    source.write_text("new", encoding="utf-8")
    sibling.write_text("keep-old-inode", encoding="utf-8")
    os.link(sibling, target)

    copy_runtime_artifact(source, target)

    assert target.read_text(encoding="utf-8") == "new"
    assert sibling.read_text(encoding="utf-8") == "keep-old-inode"
    assert not os.path.samefile(target, sibling)


def test_origin_runtime_cleanup_retries_owned_directory_after_transient_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "origin_runtime"
    target = runtime_root / "rdop_origin_transient"
    target.mkdir(parents=True)
    (target / "product.opju").write_bytes(b"runtime")
    from src.core.file_utils import apply_safe_owned_directory_removal

    real_apply = apply_safe_owned_directory_removal
    calls = 0

    def transient_apply(plan, *, output_root: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("synthetic Origin file lock")
        real_apply(plan, output_root=output_root)

    monkeypatch.setattr(
        "src.core.origin_runtime.neutral_origin_runtime_root",
        lambda: runtime_root,
    )
    monkeypatch.setattr(
        "src.core.origin_runtime.apply_safe_owned_directory_removal",
        transient_apply,
    )

    result = cleanup_origin_runtime_directory(
        target,
        retries=3,
        retry_delay_seconds=0,
    )

    assert result["ok"] is True
    assert result["status"] == "removed"
    assert result["attempts"] == 2
    assert not target.exists()


def test_origin_runtime_cleanup_refuses_unowned_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "origin_runtime"
    target = runtime_root / "user_files"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        "src.core.origin_runtime.neutral_origin_runtime_root",
        lambda: runtime_root,
    )

    result = cleanup_origin_runtime_directory(target, retry_delay_seconds=0)

    assert result["ok"] is False
    assert result["status"] == "refused_unowned_runtime_directory"
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_origin_runtime_cleanup_refuses_reparse_target_without_touching_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "origin_runtime"
    target = runtime_root / "rdop_origin_link"
    destination = tmp_path / "user_files"
    runtime_root.mkdir()
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        "src.core.origin_runtime.neutral_origin_runtime_root",
        lambda: runtime_root,
    )
    monkeypatch.setattr(
        "src.core.file_utils._path_is_link_or_reparse",
        lambda path: path == target,
    )

    result = cleanup_origin_runtime_directory(target, retry_delay_seconds=0)

    assert result["ok"] is False
    assert result["status"] == "refused_unsafe_runtime_directory"
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_xrd_helper_interpolates_and_rejects_out_of_range_values() -> None:
    points = [(10.0, 2.0), (20.0, 6.0), (30.0, 10.0)]

    assert interpolated_y(points, 15.0) == 4.0
    assert interpolated_y(points, 20.0) == 6.0
    assert interpolated_y(points, 5.0) is None


def test_xrd_helper_to_finite_float_rejects_invalid_values() -> None:
    assert to_finite_float(" 1.25 ") == 1.25
    assert to_finite_float("nan") is None
    assert to_finite_float("bad") is None


def test_relative_path_uses_forward_slashes_for_nested_paths(tmp_path: Path) -> None:
    root = tmp_path / "root"
    path = root / "a" / "b.txt"
    path.parent.mkdir(parents=True)
    path.write_text("x", encoding="utf-8")

    assert relative_path(root, path) == "a/b.txt"


def test_file_sha256_and_path_containment_helpers(tmp_path: Path) -> None:
    root = tmp_path / "root"
    child = root / "child" / "data.txt"
    child.parent.mkdir(parents=True)
    child.write_text("abc", encoding="utf-8")

    assert file_sha256(child) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert is_under_or_equal(child, root)
    assert is_under_or_equal(root, root)
    assert not is_under_or_equal(tmp_path / "other.txt", root)


def test_sanitize_report_payload_recurses_through_nested_values(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = tmp_path / "output"
    payload = {
        "path": str(project / "input" / "raw_data" / "sample.csv"),
        "items": [str(output / "reports" / "plan.json"), {"keep": 3}],
    }

    cleaned = sanitize_report_payload(project, payload, output)

    assert cleaned["path"] == "input/raw_data/sample.csv"
    assert cleaned["items"][0] == "reports/plan.json"
    assert cleaned["items"][1]["keep"] == 3


def test_validate_tif_physical_resolution_returns_read_only_evidence(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "native_600.tif"
    page_width = 6432.0
    page_height = 4923.0
    expected_size = expected_raster_pixels(page_width, page_height, dpi=600)
    Image.new("RGB", expected_size, "white").save(path, format="TIFF", dpi=(600, 600))
    digest_before = file_sha256(path)
    mtime_before = path.stat().st_mtime_ns

    evidence = validate_tif_physical_resolution(
        path,
        page_width_origin_units=page_width,
        page_height_origin_units=page_height,
        dpi=600,
    )

    assert (evidence.expected_width_px, evidence.expected_height_px) == expected_size
    assert (evidence.width_px, evidence.height_px) == expected_size
    assert evidence.tagged_dpi_x == pytest.approx(600, abs=1)
    assert evidence.tagged_dpi_y == pytest.approx(600, abs=1)
    assert evidence.effective_dpi_x == pytest.approx(600, abs=1)
    assert evidence.effective_dpi_y == pytest.approx(600, abs=1)
    assert evidence.sensitive_metadata_scan == "pass"
    assert file_sha256(path) == digest_before
    assert path.stat().st_mtime_ns == mtime_before


def test_validate_tif_physical_resolution_rejects_low_pixels_with_600_tag_without_mutation(
    tmp_path: Path,
) -> None:
    from PIL import Image

    path = tmp_path / "retagged_500_as_600.tif"
    Image.new("RGB", (3216, 2461), "white").save(path, format="TIFF", dpi=(600, 600))
    digest_before = file_sha256(path)

    with pytest.raises(
        TifResolutionValidationError,
        match=r"pixel dimensions.*effective physical DPI",
    ):
        validate_tif_physical_resolution(
            path,
            page_width_origin_units=6432.0,
            page_height_origin_units=4923.0,
            dpi=600,
        )

    assert file_sha256(path) == digest_before


def test_validate_tif_physical_resolution_rejects_wrong_tag_at_native_pixel_size(
    tmp_path: Path,
) -> None:
    from PIL import Image

    path = tmp_path / "native_pixels_wrong_tag.tif"
    expected_size = expected_raster_pixels(6983.0, 4678.0, dpi=600)
    Image.new("RGB", expected_size, "white").save(path, format="TIFF", dpi=(300, 300))

    with pytest.raises(TifResolutionValidationError, match="TIFF DPI tag"):
        validate_tif_physical_resolution(
            path,
            page_width_origin_units=6983.0,
            page_height_origin_units=4678.0,
            dpi=600,
        )


def test_validate_tif_physical_resolution_rejects_local_path_metadata_without_mutation(
    tmp_path: Path,
) -> None:
    from PIL import Image, TiffImagePlugin

    path = tmp_path / "native_with_local_path.tif"
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[270] = r"<Path>Source:D:\private\project\source.opju"
    Image.new("RGB", (60, 60), "white").save(
        path,
        format="TIFF",
        dpi=(600, 600),
        tiffinfo=tags,
    )
    digest_before = file_sha256(path)
    mtime_before = path.stat().st_mtime_ns

    with pytest.raises(
        TifResolutionValidationError,
        match=r"sensitive local-path or tool-trace metadata.*270",
    ):
        validate_tif_physical_resolution(
            path,
            page_width_origin_units=100.0,
            page_height_origin_units=100.0,
            dpi=600,
        )

    assert file_sha256(path) == digest_before
    assert path.stat().st_mtime_ns == mtime_before


def test_tiff_metadata_scanner_decodes_utf16_and_blocks_tool_trace_labels() -> None:
    utf16_value = r"Source:D:\private\project\source.opju".encode("utf-16le")

    decoded = _metadata_text_values(utf16_value)

    assert any(r"D:\private" in value for value in decoded)
    assert any(_metadata_text_contains_local_path(value) for value in decoded)
    assert _metadata_text_contains_local_path("<Path>/home/user/project/file.opju")
    assert _metadata_text_contains_local_path("Software=Codex agent")
