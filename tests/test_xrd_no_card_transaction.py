from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.core.xrd_no_card_overlay import (
    XrdNoCardOverlayArtifacts,
    XrdNoCardOverlayOptions,
    _preflight_run_outputs,
    run_xrd_no_card_overlay,
)


TIMESTAMP = "20260731_091500"
STEM = "XRD_BOBXC1_X_no_card_overlay"
RUN_NAME = f"{TIMESTAMP}_{STEM.casefold()}"


def _write_xrd(path: Path, payload: bytes | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload or b"two_theta,intensity\n5,10\n6,20\n7,15\n")
    return path


def _options(source: Path, output_root: Path, **overrides: object) -> XrdNoCardOverlayOptions:
    values: dict[str, object] = {
        "sources": (source,),
        "output_root": output_root,
        "with_origin": False,
        "timestamp": TIMESTAMP,
        "output_stem": STEM,
    }
    values.update(overrides)
    return XrdNoCardOverlayOptions(**values)


def test_no_force_collision_leaves_existing_manifest_and_run_tree_unchanged(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = _write_xrd(tmp_path / "source.csv")
    output_root = tmp_path / "output"
    run_root = output_root / "runs" / RUN_NAME
    manifest = run_root / "run_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b'{"sentinel":"must-not-change"}')

    with pytest.raises(FileExistsError, match="rerun with --force"):
        run_xrd_no_card_overlay(project_root, _options(source, output_root))

    assert manifest.read_bytes() == b'{"sentinel":"must-not-change"}'
    assert sorted(path.name for path in run_root.iterdir()) == ["run_manifest.json"]
    assert not (run_root / "processed_data").exists()


def test_force_rejects_source_inside_planned_output_without_deleting_it(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    output_root = tmp_path / "output"
    run_root = output_root / "runs" / RUN_NAME
    source = _write_xrd(run_root / "processed_data" / f"{STEM}.csv")
    original = source.read_bytes()

    with pytest.raises(ValueError, match="overlaps protected input"):
        run_xrd_no_card_overlay(
            project_root,
            _options(source, output_root, force=True),
        )

    assert source.read_bytes() == original
    assert not (run_root / "run_manifest.json").exists()


def test_force_rejects_reference_inside_planned_output_without_deleting_it(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = _write_xrd(tmp_path / "source.csv")
    output_root = tmp_path / "output"
    run_root = output_root / "runs" / RUN_NAME
    reference = run_root / "origin_files" / f"{STEM}.opju"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"reference-must-survive")

    with pytest.raises(ValueError, match="overlaps protected input"):
        run_xrd_no_card_overlay(
            project_root,
            _options(source, output_root, force=True, reference_opju=reference),
        )

    assert reference.read_bytes() == b"reference-must-survive"
    assert not (run_root / "run_manifest.json").exists()


def test_force_replaces_only_the_known_run_products(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = _write_xrd(tmp_path / "source.csv")
    output_root = tmp_path / "output"
    first = run_xrd_no_card_overlay(project_root, _options(source, output_root))
    run_root = Path(first["run_root"])
    processed = Path(first["processed_data"])
    manifest = run_root / "run_manifest.json"
    unrelated = run_root / "keep-user-note.txt"
    processed.write_bytes(b"stale-product")
    unrelated.write_bytes(b"not-a-planned-product")

    second = run_xrd_no_card_overlay(
        project_root,
        _options(source, output_root, force=True),
    )

    assert Path(second["run_root"]) == run_root
    assert processed.read_bytes() != b"stale-product"
    assert b'"command": "xrd-no-card-overlay"' in manifest.read_bytes()
    assert unrelated.read_bytes() == b"not-a-planned-product"


def test_force_rejects_symlink_product_without_unlinking_or_touching_target(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = _write_xrd(tmp_path / "source.csv")
    output_root = tmp_path / "output"
    run_root = output_root / "runs" / RUN_NAME
    run_root.mkdir(parents=True)
    protected = tmp_path / "protected-manifest.json"
    protected.write_bytes(b"external-target")
    manifest_link = run_root / "run_manifest.json"
    try:
        os.symlink(protected, manifest_link)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"file symlink creation is unavailable: {exc}")

    with pytest.raises(RuntimeError, match="symlink/junction/reparse"):
        run_xrd_no_card_overlay(
            project_root,
            _options(source, output_root, force=True),
        )

    assert manifest_link.is_symlink()
    assert protected.read_bytes() == b"external-target"


def test_force_fails_closed_when_leaf_is_classified_as_reparse_point(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "product.opju"
    artifact.write_bytes(b"must-survive")
    artifacts = XrdNoCardOverlayArtifacts(
        processed_data=tmp_path / "processed.csv",
        metadata=tmp_path / "metadata.json",
        report=tmp_path / "report.md",
        origin_file=artifact,
        figure_tif=tmp_path / "figure.tif",
        preview_png=tmp_path / "preview.png",
        script_output_dir=tmp_path / "stage",
    )
    monkeypatch.setattr(
        "src.core.xrd_no_card_overlay._is_reparse_point",
        lambda path: path == artifact,
    )

    with pytest.raises(RuntimeError, match="symlink/junction/reparse"):
        _preflight_run_outputs(artifacts, force=True)

    assert artifact.read_bytes() == b"must-survive"
