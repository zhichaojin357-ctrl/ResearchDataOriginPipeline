from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.core.project import ensure_write_path_allowed


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_metadata(
    *,
    project_root: Path | None = None,
    path: Path,
    dataset_id: str,
    data_type: str,
    source_file: Path,
    processor_name: str,
    processing_status: str,
    plot_type: str,
    origin_file: Path | None,
    figure_tif: Path | None,
    processed_data: Path | None,
    preview_png: Path | None = None,
    manual_check_items: list[str],
    forbidden_claims: list[str] | None = None,
    warnings: list[str],
    key_results: dict,
    triage: dict | None = None,
    parameters: dict | None = None,
) -> dict:
    if processing_status == "success":
        required = {
            "origin_file": origin_file,
            "figure_tif": figure_tif,
            "preview_png": preview_png,
            "processed_data": processed_data,
        }
        missing = [name for name, value in required.items() if value is None or not value.exists()]
        if missing:
            raise ValueError("Successful metadata requires existing artifacts: " + ", ".join(missing))
        if project_root is not None:
            outside_output = [
                name
                for name, value in required.items()
                if value is not None and not _is_under(value, project_root / "output")
            ]
            if outside_output:
                raise ValueError("Successful metadata artifacts must be under output/: " + ", ".join(outside_output))

    def render_path(value: Path | None) -> str | None:
        if value is None:
            return None
        if project_root:
            try:
                return str(value.resolve().relative_to(project_root.resolve())).replace("\\", "/")
            except ValueError:
                pass
        return str(value)

    origin_template_used = None
    if processing_status == "success" and origin_file and figure_tif:
        origin_template_used = "Graph4 cached snapshot from D:\\CodexData\\.codex\\skills\\origin-plotting"

    metadata = {
        "dataset_id": dataset_id,
        "metadata_path": render_path(path),
        "data_type": data_type,
        "subtype": data_type,
        "source_files": [render_path(source_file)],
        "source_hash": file_hash(source_file),
        "processor_name": processor_name,
        "processing_status": processing_status,
        "plot_type": plot_type,
        "origin_template_used": origin_template_used,
        "origin_file": render_path(origin_file),
        "figure_tif": render_path(figure_tif),
        "preview_png": render_path(preview_png),
        "processed_data": render_path(processed_data),
        "manual_check_required": True,
        "manual_check_items": _manual_check_items(processing_status, manual_check_items, preview_png),
        "forbidden_claims": forbidden_claims or [],
        "warnings": warnings,
        "parameters": parameters or {},
        "key_results": key_results,
        "triage": triage or {},
        "confidence_level": {
            "data_reading": "medium",
            "plotting": "medium" if processing_status == "success" else "low",
            "calculation": "medium",
            "interpretation": "low",
        },
    }
    if project_root is not None:
        ensure_write_path_allowed(project_root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def _manual_check_items(processing_status: str, items: list[str], preview_png: Path | None) -> list[str]:
    output = list(items)
    if processing_status == "success" and preview_png is not None:
        preview_item = "Inspect PNG preview for Graph4 style match, explicit bold legend rows without a frame/fill box, chemical formula subscripts, curve width 3, and no template residue."
        if preview_item not in output:
            output.append(preview_item)
    return output


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
