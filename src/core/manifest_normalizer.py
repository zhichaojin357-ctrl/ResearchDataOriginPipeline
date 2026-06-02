from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.manifest_schema import CANONICAL_MANIFEST_VERSION, CANONICAL_ORIGIN_BATCH_COLUMNS
from src.core.origin_batch import INPUT_ARTIFACT_FIELDS, ORIGIN_OUTPUT_FIELDS, _missing_or_empty, _resolve_artifact_paths


@dataclass(frozen=True)
class ManifestNormalizationResult:
    csv_path: Path
    json_path: Path
    md_path: Path
    items: list[dict[str, str]]
    summary: dict


def normalize_material_collection_manifest(
    manifest_path: Path,
    project_root: Path,
    *,
    output_dir: Path | None = None,
    output_csv: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> ManifestNormalizationResult:
    project_root = project_root.absolute()
    manifest_path = manifest_path.absolute()
    collection_root = manifest_path.parent
    out_dir = output_dir or project_root / "output" / "reports"
    csv_path = _resolve_output_path(project_root, output_csv or out_dir / "phase1_10_material_collection_normalized_manifest.csv")
    json_path = _resolve_output_path(project_root, output_json or out_dir / "phase1_10_material_collection_normalized_manifest.json")
    md_path = _resolve_output_path(project_root, output_md or out_dir / "phase1_10_material_collection_normalized_manifest.md")

    rows = _read_rows(manifest_path)
    items = [_normalize_row(row, collection_root, manifest_path) for row in rows]
    safe_count = sum(1 for item in items if item["safe_for_origin_batch"] == "true")
    summary = {
        "manifest_version": CANONICAL_MANIFEST_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_manifest": str(manifest_path),
        "source_package": str(collection_root),
        "total_items": len(items),
        "safe_count": safe_count,
        "unsafe_count": len(items) - safe_count,
        "can_origin_batch": safe_count > 0,
        "notes": "Material collection normalization only marks complete result-like items safe; unprocessed/source-only items remain skipped.",
    }

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_ORIGIN_BATCH_COLUMNS)
        writer.writeheader()
        writer.writerows(items)
    json_path.write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(summary, items), encoding="utf-8")
    return ManifestNormalizationResult(csv_path=csv_path, json_path=json_path, md_path=md_path, items=items, summary=summary)


def _normalize_row(row: dict[str, str], collection_root: Path, manifest_path: Path) -> dict[str, str]:
    item_id = row.get("collection_id", "")
    result_id = _extract_note_value(row.get("notes", ""), "result_id") or item_id
    source_file = _extract_note_value(row.get("notes", ""), "source_file") or row.get("original_relative_path", "")
    source_hash = row.get("sha256", "")
    data_type = row.get("data_type_guess", "")
    output = {
        "manifest_version": CANONICAL_MANIFEST_VERSION,
        "package_id": collection_root.name,
        "package_role": "material_collection_normalized",
        "generated_at": "",
        "source_package": str(collection_root),
        "item_id": item_id,
        "result_id": result_id,
        "queue_id": item_id,
        "data_type": data_type,
        "source_file": source_file,
        "source_hash": source_hash,
        "processed_csv": "",
        "metadata": "",
        "origin_file": "",
        "figure_tif": "",
        "preview_png": "",
        "contact_sheet": "",
        "qc_status": "NOT_CHECKED",
        "manual_check_required": "true",
        "forbidden_claims": "do not automatically infer scientific conclusions from a normalized material collection manifest",
        "origin_export_status": "not_exported",
        "origin_export_allowed": "false",
        "already_origin_exported": "false",
        "safe_for_origin_batch": "false",
        "can_origin_batch": "false",
        "cannot_origin_batch_reason": "",
        "missing_processed_csv": "false",
        "missing_metadata": "false",
        "missing_origin_file": "false",
        "missing_tif": "false",
        "missing_preview": "false",
        "unprocessed_source_only": "false",
        "already_result_item": "false",
        "notes": "",
    }

    source_kind = row.get("source_kind", "")
    package_relative = row.get("package_relative_path", "")
    if source_kind.startswith("phase1_6_"):
        field = _artifact_field_for_source_kind(source_kind)
        if field:
            output[field] = package_relative
            output["already_result_item"] = "true"
            if source_kind == "phase1_6_origin_file":
                output["already_origin_exported"] = "true"
                output["origin_export_status"] = "success"

    reasons = _unsafe_reasons(output, collection_root, row)
    if not reasons:
        output["safe_for_origin_batch"] = "true"
        output["can_origin_batch"] = "true"
        output["origin_export_allowed"] = "true"
        output["notes"] = "normalized complete result-like item; dry-run only unless explicitly executed in a later phase"
    else:
        _set_reason_flags(output, reasons)
        output["cannot_origin_batch_reason"] = "; ".join(reasons)
        output["notes"] = "; ".join(reasons)
    return output


def _unsafe_reasons(item: dict[str, str], collection_root: Path, original_row: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    if original_row.get("xps_status") == "xps_unprocessed" or original_row.get("source_kind") == "workspace_xps_unprocessed":
        reasons.append("unprocessed_xps_extracted_only")
    if original_row.get("source_kind") in {"workspace_copy", "workspace_xps_unprocessed"}:
        reasons.append("unprocessed_source_only")
    path_errors, artifacts = _resolve_artifact_paths(collection_root, item)
    if path_errors:
        reasons.append("path_traversal_or_absolute_artifact_path")
    for field in _missing_or_empty(artifacts, INPUT_ARTIFACT_FIELDS):
        reasons.append(f"missing_{field}")
    for field in _missing_or_empty(artifacts, ORIGIN_OUTPUT_FIELDS):
        reasons.append(f"missing_{field}")
    if not item.get("source_hash"):
        reasons.append("missing_source_hash")
    if not item.get("data_type"):
        reasons.append("missing_data_type")
    return sorted(set(reasons))


def _set_reason_flags(item: dict[str, str], reasons: list[str]) -> None:
    mapping = {
        "missing_processed_csv": "missing_processed_csv",
        "missing_metadata": "missing_metadata",
        "missing_origin_file": "missing_origin_file",
        "missing_figure_tif": "missing_tif",
        "missing_preview_png": "missing_preview",
        "unprocessed_source_only": "unprocessed_source_only",
    }
    reason_set = set(reasons)
    for reason, field in mapping.items():
        if reason in reason_set:
            item[field] = "true"


def _artifact_field_for_source_kind(source_kind: str) -> str | None:
    return {
        "phase1_6_processed_csv": "processed_csv",
        "phase1_6_metadata": "metadata",
        "phase1_6_origin_file": "origin_file",
        "phase1_6_figure_tif": "figure_tif",
        "phase1_6_preview_png": "preview_png",
        "phase1_6_contact_sheet": "contact_sheet",
    }.get(source_kind)


def _extract_note_value(notes: str, key: str) -> str:
    prefix = f"{key}="
    for part in notes.split(";"):
        stripped = part.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _resolve_output_path(project_root: Path, path: Path) -> Path:
    resolved = path if path.is_absolute() else project_root / path
    allowed = [(project_root / "output").resolve(), (project_root / "docs").resolve()]
    if not any(_is_under_or_equal(resolved.resolve(), root) for root in allowed):
        raise ValueError(f"Refusing to write normalized manifest outside output/ or docs/: {resolved}")
    return resolved


def _is_under_or_equal(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return path == parent


def _markdown(summary: dict, items: list[dict[str, str]]) -> str:
    lines = [
        "# Phase 1.10 Material Collection Normalized Manifest",
        "",
        f"- Source manifest: `{summary['source_manifest']}`",
        f"- Total items: {summary['total_items']}",
        f"- Safe items: {summary['safe_count']}",
        f"- Unsafe items: {summary['unsafe_count']}",
        f"- Can origin-batch: {str(summary['can_origin_batch']).lower()}",
        "",
        "0 safe items means no export action should be taken from this material collection.",
        "",
        "## Unsafe Reason Counts",
    ]
    counts: dict[str, int] = {}
    for item in items:
        for reason in str(item.get("notes", "")).split("; "):
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
    if counts:
        for reason, count in sorted(counts.items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"
