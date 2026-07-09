from __future__ import annotations

from pathlib import Path

from src.core.file_utils import file_sha256, is_under_or_equal
from src.core.image_artifacts import ensure_tif_600_dpi_metadata
from src.core.origin_runtime import copy_runtime_artifact
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


def test_ensure_tif_600_dpi_metadata_updates_dpi_without_changing_pixels(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "figure.tif"
    Image.new("RGB", (10, 8), "white").save(path, format="TIFF", dpi=(300, 300))

    ensure_tif_600_dpi_metadata(path)

    with Image.open(path) as image:
        assert image.size == (10, 8)
        assert tuple(round(value) for value in image.info.get("dpi", (0, 0))) == (600, 600)
