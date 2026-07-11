from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


CANONICAL_MANIFEST_VERSION = "origin_batch_manifest_v1"

CANONICAL_ORIGIN_BATCH_COLUMNS = [
    "manifest_version",
    "package_id",
    "package_role",
    "generated_at",
    "source_package",
    "item_id",
    "result_id",
    "queue_id",
    "data_type",
    "source_file",
    "source_hash",
    "processed_csv",
    "metadata",
    "origin_file",
    "figure_tif",
    "preview_png",
    "contact_sheet",
    "qc_status",
    "manual_check_required",
    "forbidden_claims",
    "origin_export_status",
    "origin_export_allowed",
    "already_origin_exported",
    "safe_for_origin_batch",
    "can_origin_batch",
    "cannot_origin_batch_reason",
    "missing_processed_csv",
    "missing_metadata",
    "missing_origin_file",
    "missing_tif",
    "missing_preview",
    "unprocessed_source_only",
    "already_result_item",
    "notes",
]

ORIGIN_BATCH_REQUIRED_COLUMNS = {
    "result_id",
    "data_type",
    "source_hash",
    "processed_csv",
    "metadata",
    "origin_file",
    "figure_tif",
    "preview_png",
    "qc_status",
}
ORIGIN_STATUS_ALIASES = {"origin_status", "origin_export_status"}
SOURCE_LOCATOR_COLUMNS = {"source_file", "source_copy", "selected_source_copy", "selected_source_data"}
MATERIAL_COLLECTION_COLUMNS = {
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
}


def read_csv_headers(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        raw_headers = next(reader, [])
    return [str(header).strip() for header in raw_headers]


def detect_manifest_type(path: Path) -> str:
    headers = set(read_csv_headers(path))
    if not headers:
        return "unknown_manifest"
    if ORIGIN_BATCH_REQUIRED_COLUMNS.issubset(headers) and headers.intersection(ORIGIN_STATUS_ALIASES) and headers.intersection(SOURCE_LOCATOR_COLUMNS):
        return "standard_result_manifest"
    if MATERIAL_COLLECTION_COLUMNS.issubset(headers):
        return "material_collection_manifest"
    return "unknown_manifest"


def validate_origin_batch_manifest(path: Path) -> dict:
    headers = read_csv_headers(path)
    header_set = set(headers)
    missing = sorted(ORIGIN_BATCH_REQUIRED_COLUMNS - header_set)
    if not header_set.intersection(ORIGIN_STATUS_ALIASES):
        missing.append("origin_status")
    missing_source_locator = not header_set.intersection(SOURCE_LOCATOR_COLUMNS)
    return {
        "valid": not missing and not missing_source_locator,
        "detected_manifest_type": detect_manifest_type(path),
        "headers": headers,
        "missing_required_columns": missing,
        "missing_source_locator": missing_source_locator,
        "source_locator_choices": sorted(SOURCE_LOCATOR_COLUMNS),
    }


def explain_schema_mismatch(path: Path) -> dict:
    validation = validate_origin_batch_manifest(path)
    detected = validation["detected_manifest_type"]
    suggested_command = subprocess.list2cmdline(
        [
            sys.executable,
            "run.py",
            "manifest-normalize",
            "--manifest",
            str(path),
            "--output-csv",
            "reports/material_collection_normalized_manifest.csv",
        ]
    )
    return {
        **validation,
        "suggested_command": suggested_command
        if detected == "material_collection_manifest"
        else "Use a standard result package index.csv or generate a compatible manifest first.",
        "normalized_manifest_path": "reports/material_collection_normalized_manifest.csv"
        if detected == "material_collection_manifest"
        else "",
        "safe_items_known": "unknown",
    }


def schema_mismatch_message(path: Path) -> str:
    mismatch = explain_schema_mismatch(path)
    missing = ", ".join(mismatch["missing_required_columns"]) or "none"
    source_locator = "missing" if mismatch["missing_source_locator"] else "present"
    return (
        f"detected manifest type: {mismatch['detected_manifest_type']}; "
        f"missing columns: {missing}; "
        f"source locator: {source_locator}; "
        f"suggested command: {mismatch['suggested_command']}; "
        f"normalized manifest path: {mismatch['normalized_manifest_path'] or 'n/a'}"
    )
