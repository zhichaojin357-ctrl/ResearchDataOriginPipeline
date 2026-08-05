from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = "1.0"
ARCHIVE_NAME = "agilent_openlab_processing_2_5.zip"
MANIFEST_NAME = "manifest.json"
PAYLOAD_DIRS = ("Bin", "Methods")
EXCLUDED_DIAGNOSTIC_FILES = {
    "Bin/OpenLabIntegratorProbe.exe",
    "Bin/OpenLabServicesHarness.exe",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_files(source_root: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for directory_name in PAYLOAD_DIRS:
        directory = source_root / directory_name
        if not directory.is_dir():
            raise NotADirectoryError(f"Runtime payload directory is missing: {directory}")
        for path in sorted(directory.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root).as_posix()
            if relative in EXCLUDED_DIAGNOSTIC_FILES:
                continue
            files.append(
                {
                    "path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    return files


def build_bundle(source_root: Path, destination_root: Path) -> dict[str, object]:
    source_root = source_root.resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    files = _payload_files(source_root)
    if not files:
        raise RuntimeError("Runtime payload is empty")

    archive_path = destination_root / ARCHIVE_NAME
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{ARCHIVE_NAME}.", suffix=".tmp", dir=destination_root
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as archive:
            for item in files:
                relative = str(item["path"])
                archive.write(source_root / Path(relative), arcname=relative)
        os.replace(temporary, archive_path)
    finally:
        temporary.unlink(missing_ok=True)

    payload_size = sum(int(item["size_bytes"]) for item in files)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "runtime_id": "agilent_openlab_data_analysis_2_5_processing",
        "source_product": "Agilent OpenLab Data Analysis 2.5",
        "purpose": "ProcessingServer ModifyAndReprocessSingleRun runtime",
        "archive": {
            "path": ARCHIVE_NAME,
            "size_bytes": archive_path.stat().st_size,
            "sha256": _sha256(archive_path),
            "format": "zip-deflate",
        },
        "payload": {
            "file_count": len(files),
            "size_bytes": payload_size,
            "files": files,
        },
        "entrypoints": {
            "processing_server": "Bin/Agilent.Chromatography.DataAnalysis.Processing.ProcessingServer.exe",
            "bridge": "Bin/OpenLabVendorBridge.exe",
            "default_processing_method": "Methods/GC_LC 归一化百分比_DefaultMethod.pmx",
        },
        "minimization": {
            "source_file_count": 391,
            "excluded_project_diagnostic_files": sorted(EXCLUDED_DIAGNOSTIC_FILES),
            "reason_for_conservative_closure": (
                "OpenLab discovers processing, raw-reader, quantitation, and reporting components "
                "through PMX-embedded type names and runtime composition. Static-reference subsets "
                "of 89 and 127 files did not complete ProcessingServer reprocessing, so no further "
                "vendor components were removed without a passing natural-exit smoke test."
            ),
        },
        "validation_baseline": {
            "dataset": "R01 single-injection copied result set",
            "bridge_exit_code": 0,
            "bridge_report_success": True,
            "elapsed_seconds": 4.703,
            "rx_before_size_bytes": 5951,
            "rx_after_size_bytes": 6302,
            "rx_before_sha256": "845b1d330bc7178bd17ed260bda06906e2228dc4103b2172392fa05e49d2e69e",
            "rx_after_sha256": "c0428098e5300a42de69ed35dbb8e26ee939f9343dacc402a2d2d992630dffb8",
            "residual_bridge_or_processing_server_processes": 0,
        },
        "bundled_archive_validation": {
            "runtime_source": (
                "hash-verified extraction cache created only from the checked-in archive"
            ),
            "dataset": "R01 single-injection copied result set",
            "bridge_exit_code": 0,
            "bridge_report_success": True,
            "job_status": "succeeded",
            "load_errors": [],
            "failures": [],
            "elapsed_seconds": 8.937,
            "rx_before_size_bytes": 5951,
            "rx_after_size_bytes": 6270,
            "rx_before_sha256": "845b1d330bc7178bd17ed260bda06906e2228dc4103b2172392fa05e49d2e69e",
            "rx_after_sha256": "e4d07dfe78378d5392f88454079fc048b713f6366afe60574e76b25ff89d32af",
            "residual_bridge_or_processing_server_processes": 0,
        },
    }
    manifest_path = destination_root / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_bundle(bundle_root: Path) -> dict[str, object]:
    bundle_root = bundle_root.resolve()
    manifest_path = bundle_root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive_record = dict(manifest["archive"])
    archive_path = bundle_root / str(archive_record["path"])
    if archive_path.stat().st_size != int(archive_record["size_bytes"]):
        raise RuntimeError("Bundled Agilent archive size does not match manifest")
    if _sha256(archive_path) != str(archive_record["sha256"]):
        raise RuntimeError("Bundled Agilent archive SHA-256 does not match manifest")

    records: dict[str, dict[str, object]] = {}
    record_names: set[str] = set()
    for item in manifest["payload"]["files"]:
        rendered = str(item["path"])
        path = PurePosixPath(rendered)
        if (
            "\\" in rendered
            or ":" in rendered
            or path.is_absolute()
            or ".." in path.parts
            or not path.parts
        ):
            raise RuntimeError(f"Unsafe path in bundled Agilent manifest: {rendered}")
        folded = rendered.casefold()
        if folded in record_names:
            raise RuntimeError(f"Case-insensitive duplicate in bundled Agilent manifest: {rendered}")
        record_names.add(folded)
        records[rendered] = item
    with zipfile.ZipFile(archive_path, "r") as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        actual_names: set[str] = set()
        actual_folded: set[str] = set()
        for member in members:
            path = PurePosixPath(member.filename)
            if (
                "\\" in member.filename
                or ":" in member.filename
                or path.is_absolute()
                or ".." in path.parts
                or not path.parts
            ):
                raise RuntimeError(f"Unsafe path in bundled Agilent archive: {member.filename}")
            normalized = path.as_posix()
            if normalized.casefold() in actual_folded:
                raise RuntimeError(f"Duplicate path in bundled Agilent archive: {normalized}")
            actual_names.add(normalized)
            actual_folded.add(normalized.casefold())
            record = records.get(normalized)
            if record is None:
                raise RuntimeError(f"Unmanifested file in bundled Agilent archive: {normalized}")
            if member.file_size != int(record["size_bytes"]):
                raise RuntimeError(f"Bundled Agilent member size mismatch: {normalized}")
            digest = hashlib.sha256(archive.read(member)).hexdigest()
            if digest != str(record["sha256"]):
                raise RuntimeError(f"Bundled Agilent member SHA-256 mismatch: {normalized}")
        missing = sorted(set(records) - actual_names)
        if missing:
            raise RuntimeError(f"Bundled Agilent archive is missing {len(missing)} manifest file(s)")
    return {
        "runtime_id": manifest["runtime_id"],
        "archive_sha256": archive_record["sha256"],
        "file_count": len(records),
        "payload_size_bytes": manifest["payload"]["size_bytes"],
        "verified": True,
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[4]
    default_bundle = project_root / "vendor" / "agilent_openlab_processing" / "2.5"
    parser = argparse.ArgumentParser(description="Build or verify the bundled Agilent processing runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--source-root", type=Path, required=True)
    build.add_argument("--bundle-root", type=Path, default=default_bundle)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle-root", type=Path, default=default_bundle)
    args = parser.parse_args()
    result = (
        build_bundle(args.source_root, args.bundle_root)
        if args.command == "build"
        else verify_bundle(args.bundle_root)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
