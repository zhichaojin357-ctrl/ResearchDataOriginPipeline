from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core import hplc_openlab_vendor as vendor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = PROJECT_ROOT / "vendor" / "agilent_openlab_processing" / "2.5"


@pytest.mark.parametrize("cache_state", ["missing", "existing", "concurrent"])
def test_bundled_runtime_validates_final_payload_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cache_state: str,
) -> None:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    archive_path = bundle_root / "runtime.zip"
    files = {"Bin/bridge.exe": b"bridge", "Methods/default.amx": b"method"}
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "1.0",
        "archive": {
            "path": archive_path.name,
            "size_bytes": archive_path.stat().st_size,
            "sha256": archive_sha256,
        },
        "payload": {
            "file_count": len(files),
            "files": [
                {"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in files.items()
            ],
        },
        "entrypoints": {"bridge": "Bin/bridge.exe", "default_processing_method": "Methods/default.amx"},
    }
    manifest_path = bundle_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cache_root = tmp_path / "runtime-cache"
    runtime_root = cache_root / f"agilent_openlab_processing_2_5_{archive_sha256[:12]}"
    monkeypatch.setattr(vendor, "_BUNDLED_RUNTIME_ROOT", bundle_root)
    monkeypatch.setattr(vendor, "_BUNDLED_RUNTIME_MANIFEST", manifest_path)
    monkeypatch.setattr(vendor, "_LOCAL_RUNTIME_CACHE", cache_root)
    if cache_state == "existing":
        runtime_root.mkdir(parents=True)
        vendor._extract_bundled_runtime(archive_path, runtime_root, manifest)
    elif cache_state == "concurrent":
        def concurrent_replace(staging: Path, destination: Path) -> None:
            shutil.copytree(staging, destination)
            raise FileExistsError(destination)

        monkeypatch.setattr(vendor.os, "replace", concurrent_replace)

    with patch.object(vendor, "_validate_extracted_runtime", wraps=vendor._validate_extracted_runtime) as validate:
        assets = vendor.resolve_bundled_openlab_vendor_assets()

    validate.assert_called_once_with(runtime_root, manifest)
    assert assets.bridge_exe.read_bytes() == files["Bin/bridge.exe"]
    assert assets.processing_method.read_bytes() == files["Methods/default.amx"]
    assert json.loads((runtime_root / ".bundle_manifest.json").read_text(encoding="utf-8")) == manifest
    assert not list(cache_root.glob(".agilent-openlab-extract-*"))

    # Each later resolution still validates the current cache, including hashes.
    assets.bridge_exe.write_bytes(b"broken")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        vendor.resolve_bundled_openlab_vendor_assets()


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
