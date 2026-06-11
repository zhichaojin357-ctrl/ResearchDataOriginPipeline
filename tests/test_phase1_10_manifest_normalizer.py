from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from src.core.manifest_normalizer import normalize_material_collection_manifest
from src.core.manifest_schema import (
    detect_manifest_type,
    explain_schema_mismatch,
    validate_origin_batch_manifest,
)
from src.core.origin_batch import OriginBatchOptions, plan_origin_batch
from src.core.project import default_output_root


def test_standard_phase1_6_manifest_validates_when_available(project_root: Path):
    manifest = default_output_root(project_root) / "phase1_6_origin_results_20260531_041538" / "index.csv"
    if not manifest.exists():
        pytest.skip("real Phase 1.6 package is not available in this checkout")
    assert detect_manifest_type(manifest) == "standard_result_manifest"
    validation = validate_origin_batch_manifest(manifest)
    assert validation["valid"] is True
    assert validation["detected_manifest_type"] == "standard_result_manifest"


def test_material_collection_manifest_is_detected_and_explained(tmp_path: Path):
    manifest = tmp_path / "collection" / "index.csv"
    manifest.parent.mkdir()
    manifest.write_text(
        "collection_id,source_kind,material_key,data_type_guess,xps_status,original_relative_path,"
        "package_relative_path,source_size_bytes,sha256,extension,copy_status,notes,manual_review_hint\n"
        "W0001,workspace_copy,BOBC,XRD,not_xps,01_XRD/a.raw,workspace_matches/a.raw,123,"
        "abc,.raw,copied,,\n",
        encoding="utf-8",
    )

    assert detect_manifest_type(manifest) == "material_collection_manifest"
    mismatch = explain_schema_mismatch(manifest)
    assert mismatch["detected_manifest_type"] == "material_collection_manifest"
    assert "processed_csv" in mismatch["missing_required_columns"]
    assert "metadata" in mismatch["missing_required_columns"]
    assert mismatch["suggested_command"]


def test_material_collection_normalizer_marks_source_only_items_unsafe(tmp_path: Path):
    collection = tmp_path / "collection"
    _write_material_collection_index(
        collection,
        [
            {
                "collection_id": "W0001",
                "source_kind": "workspace_copy",
                "material_key": "BOBC",
                "data_type_guess": "XRD",
                "xps_status": "not_xps",
                "original_relative_path": "01_XRD/a.raw",
                "package_relative_path": "workspace_matches/a.raw",
                "source_size_bytes": "123",
                "sha256": "a" * 64,
                "extension": ".raw",
                "copy_status": "copied",
                "notes": "",
                "manual_review_hint": "",
            }
        ],
    )
    _write(collection / "workspace_matches" / "a.raw", "raw")

    result = normalize_material_collection_manifest(collection / "index.csv", tmp_path)

    assert result.summary["safe_count"] == 0
    assert str(tmp_path) not in json.dumps(result.summary, ensure_ascii=False)
    assert result.summary["source_manifest"] == "collection/index.csv"
    assert result.summary["source_package"] == "collection"
    assert result.items[0]["safe_for_origin_batch"] == "false"
    assert result.items[0]["unprocessed_source_only"] == "true"
    assert result.items[0]["source_package"] == "collection"
    assert "missing_processed_csv" in result.items[0]["cannot_origin_batch_reason"]
    assert "missing_metadata" in result.items[0]["cannot_origin_batch_reason"]
    assert result.items[0]["already_origin_exported"] == "false"


def test_normalized_manifest_dry_run_is_controlled_with_zero_safe_items(tmp_path: Path, project_root: Path):
    test_project = tmp_path / "project"
    collection = tmp_path / "collection"
    _write_material_collection_index(
        collection,
        [
            {
                "collection_id": "W0001",
                "source_kind": "workspace_copy",
                "material_key": "BOBC",
                "data_type_guess": "XRD",
                "xps_status": "not_xps",
                "original_relative_path": "01_XRD/a.raw",
                "package_relative_path": "workspace_matches/a.raw",
                "source_size_bytes": "123",
                "sha256": "a" * 64,
                "extension": ".raw",
                "copy_status": "copied",
                "notes": "",
                "manual_review_hint": "",
            }
        ],
    )
    _write(collection / "workspace_matches" / "a.raw", "raw")
    output_dir = default_output_root(test_project) / "reports" / "phase1_10_normalized"
    normalized = normalize_material_collection_manifest(
        collection / "index.csv",
        test_project,
        output_dir=output_dir,
    )

    plan = plan_origin_batch(test_project, OriginBatchOptions(manifest=normalized.csv_path))

    assert plan["summary"]["total_manifest_items"] == 1
    assert plan["summary"]["planned_count"] == 0
    assert plan["summary"]["blocked_count"] == 0
    assert plan["summary"]["skipped_count"] == 1
    assert plan["skipped_items"][0]["reason"] == "not_safe_for_origin_batch"
    assert plan["execution"]["blocked"] is False


def test_origin_batch_cli_explains_material_collection_schema_mismatch(tmp_path: Path, project_root: Path):
    collection = tmp_path / "collection"
    _write_material_collection_index(collection, [])

    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--manifest", str(collection / "index.csv"), "--dry-run"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "detected manifest type: material_collection_manifest" in result.stderr
    assert "missing columns" in result.stderr
    assert "manifest-normalize" in result.stderr
    assert "Traceback" not in result.stderr


def test_manifest_normalize_cli_writes_origin_batch_compatible_outputs(tmp_path: Path, project_root: Path):
    test_project = tmp_path / "project"
    test_project.mkdir(parents=True)
    reports_dir = default_output_root(test_project) / "reports"
    reports_dir.mkdir(parents=True)
    collection = tmp_path / "collection"
    _write_material_collection_index(collection, [])
    out_csv = reports_dir / "_test_phase1_10_normalized_manifest.csv"
    out_json = reports_dir / "_test_phase1_10_normalized_manifest.json"
    out_md = reports_dir / "_test_phase1_10_normalized_manifest.md"

    result = subprocess.run(
        [
            "D:\\Python\\python.exe",
            str(project_root / "run.py"),
            "manifest-normalize",
            "--manifest",
            str(collection / "index.csv"),
            "--output-csv",
            str(out_csv),
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
        cwd=test_project,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 0
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8-sig", newline="")))
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert rows == []
    assert payload["summary"]["safe_count"] == 0
    assert "0 safe items" in out_md.read_text(encoding="utf-8")


def _write_material_collection_index(collection: Path, rows: list[dict[str, str]]) -> None:
    collection.mkdir(parents=True, exist_ok=True)
    fields = [
        "collection_id",
        "source_kind",
        "material_key",
        "data_type_guess",
        "xps_status",
        "original_relative_path",
        "package_relative_path",
        "source_size_bytes",
        "sha256",
        "extension",
        "copy_status",
        "notes",
        "manual_review_hint",
    ]
    with (collection / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
