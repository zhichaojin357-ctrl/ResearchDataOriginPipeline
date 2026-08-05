from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.core import hplc_openlab_vendor as vendor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = PROJECT_ROOT / "vendor" / "agilent_openlab_processing" / "2.5"


def test_bundled_openlab_archive_matches_per_file_manifest() -> None:
    manifest = json.loads((BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    archive = BUNDLE_ROOT / manifest["archive"]["path"]

    assert archive.stat().st_size == manifest["archive"]["size_bytes"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive"]["sha256"]
    records = {item["path"]: item for item in manifest["payload"]["files"]}
    assert len(records) == manifest["payload"]["file_count"] == 390
    assert manifest["entrypoints"]["bridge"] in records
    assert manifest["entrypoints"]["processing_server"] in records
    assert manifest["entrypoints"]["default_processing_method"] in records
    assert "Bin/OpenLabIntegratorProbe.exe" not in records
    assert "Bin/OpenLabServicesHarness.exe" not in records


def test_bundled_openlab_runtime_extracts_to_hash_keyed_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vendor, "_LOCAL_RUNTIME_CACHE", tmp_path / "runtime-cache")

    assets = vendor.resolve_bundled_openlab_vendor_assets()

    assert assets.runtime_root.parent == (tmp_path / "runtime-cache").resolve()
    assert assets.runtime_root.name.endswith(assets.archive_sha256[:12])
    assert assets.bridge_exe.is_file()
    assert assets.processing_method.is_file()
    assert (assets.runtime_bin / "Agilent.Chromatography.DataAnalysis.Processing.ProcessingServer.exe").is_file()
    assert assets.manifest["bundled_archive_validation"]["bridge_report_success"] is True


@pytest.mark.parametrize("unsafe_path", ["../outside.dll", r"..\outside.dll", "C:outside.dll"])
def test_bundled_runtime_manifest_rejects_path_traversal(unsafe_path: str) -> None:
    manifest = {
        "payload": {
            "file_count": 1,
            "files": [
                {
                    "path": unsafe_path,
                    "size_bytes": 1,
                    "sha256": "0" * 64,
                }
            ],
        }
    }

    with pytest.raises(RuntimeError, match="Unsafe path"):
        vendor._runtime_records(manifest)
