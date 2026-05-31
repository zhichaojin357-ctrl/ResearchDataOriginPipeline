from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


PACKAGE_ARTIFACT_FIELDS = (
    "processed_csv",
    "metadata",
    "origin_file",
    "figure_tif",
    "preview_png",
    "original_no_origin_preview",
    "contact_sheet",
)
ORIGIN_OUTPUT_FIELDS = ("origin_file", "figure_tif", "preview_png")
INPUT_ARTIFACT_FIELDS = ("processed_csv", "metadata")
DEFAULT_WORKSPACE_RELATIVE = Path("workspace_data") / "LL_detection_copy_20260530"


@dataclass(frozen=True)
class OriginBatchOptions:
    manifest: Path
    dry_run: bool = True
    execute: bool = False
    with_origin: bool = False
    only_type: str | None = None
    only_missing: bool = False
    report_json: Path | None = None
    report_md: Path | None = None


def run_origin_batch(project_root: Path, options: OriginBatchOptions) -> int:
    plan = plan_origin_batch(project_root, options)
    write_origin_batch_reports(project_root, plan, options)
    if plan["execution"]["blocked"]:
        return 2
    return 0 if not plan["summary"]["blocked_count"] else 1


def plan_origin_batch(project_root: Path, options: OriginBatchOptions) -> dict:
    project_root = project_root.absolute()
    manifest_path = _resolve_existing_path(project_root, options.manifest)
    package_root = manifest_path.parent.absolute()
    rows = _read_manifest_rows(manifest_path)
    planned = []
    skipped = []
    blocked = []

    for row_number, row in enumerate(rows, start=2):
        result_id = row.get("result_id") or f"row_{row_number}"
        data_type = row.get("data_type", "")
        base_item = {
            "row_number": row_number,
            "result_id": result_id,
            "queue_id": row.get("queue_id", ""),
            "data_type": data_type,
        }
        if options.only_type and _normalize(data_type) != _normalize(options.only_type):
            skipped.append({**base_item, "reason": "only_type_filter"})
            continue

        path_errors, resolved_artifacts = _resolve_artifact_paths(package_root, row)
        if path_errors:
            blocked.append({**base_item, "reason": "path_traversal_or_absolute_artifact_path", "details": path_errors})
            continue

        source_hash = row.get("source_hash", "").strip()
        if not source_hash:
            blocked.append({**base_item, "reason": "source_hash_missing"})
            continue

        source_check = _check_source_hash(project_root, package_root, row, source_hash)
        if not source_check["ok"]:
            blocked.append({**base_item, **source_check})
            continue

        missing_inputs = _missing_or_empty(resolved_artifacts, INPUT_ARTIFACT_FIELDS)
        if missing_inputs:
            blocked.append({**base_item, "reason": "required_input_artifact_missing", "missing": missing_inputs})
            continue

        missing_outputs = _missing_or_empty(resolved_artifacts, ORIGIN_OUTPUT_FIELDS)
        complete = _is_complete(row, resolved_artifacts, missing_outputs)
        if complete:
            skipped.append({**base_item, "reason": "already_complete"})
            continue
        if options.only_missing and not missing_outputs:
            skipped.append({**base_item, "reason": "not_missing_origin_outputs"})
            continue

        planned.append(
            {
                **base_item,
                "source_file": row.get("source_file", ""),
                "source_hash": source_hash,
                "missing_origin_outputs": missing_outputs,
                "origin_status": row.get("origin_status", ""),
                "qc_status": row.get("qc_status", ""),
                "action": "origin_export_candidate",
            }
        )

    execution_blocked = False
    execution_reason = "dry_run_only"
    if options.execute and not options.with_origin:
        execution_blocked = True
        execution_reason = "execute_requires_explicit_with_origin"
    elif options.execute and options.with_origin:
        execution_blocked = True
        execution_reason = "phase1_7_runner_implements_planning_only_no_export"

    return {
        "runner": "origin-batch",
        "manifest": str(manifest_path),
        "package_root": str(package_root),
        "options": {
            "dry_run": bool(options.dry_run or not options.execute),
            "execute": options.execute,
            "with_origin": options.with_origin,
            "only_type": options.only_type,
            "only_missing": options.only_missing,
        },
        "summary": {
            "total_manifest_items": len(rows),
            "planned_count": len(planned),
            "skipped_count": len(skipped),
            "blocked_count": len(blocked),
            "will_launch_origin": False,
        },
        "execution": {
            "blocked": execution_blocked,
            "reason": execution_reason,
            "origin_launch": False,
            "notes": "Phase 1.7 origin-batch is a manifest-driven dry-run planner; it never launches Origin during dry-run.",
        },
        "planned_items": planned,
        "skipped_items": skipped,
        "blocked_items": blocked,
    }


def write_origin_batch_reports(project_root: Path, plan: dict, options: OriginBatchOptions) -> tuple[Path, Path]:
    reports_dir = project_root / "output" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = options.report_json or reports_dir / "phase1_7_manifest_runner_plan.json"
    md_path = options.report_md or reports_dir / "phase1_7_manifest_runner_plan.md"
    _guard_output_path(project_root, json_path)
    _guard_output_path(project_root, md_path)
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_manifest_plan_markdown(plan), encoding="utf-8")
    return json_path, md_path


def _manifest_plan_markdown(plan: dict) -> str:
    summary = plan["summary"]
    lines = [
        "# Phase 1.7 Manifest Runner Plan",
        "",
        f"- Manifest: `{plan['manifest']}`",
        f"- Total manifest items: {summary['total_manifest_items']}",
        f"- Planned items: {summary['planned_count']}",
        f"- Skipped items: {summary['skipped_count']}",
        f"- Blocked items: {summary['blocked_count']}",
        f"- Will launch Origin: {summary['will_launch_origin']}",
        f"- Execution state: {plan['execution']['reason']}",
        "",
        "## Planned Items",
    ]
    if plan["planned_items"]:
        for item in plan["planned_items"]:
            missing = ", ".join(item.get("missing_origin_outputs", [])) or "incomplete_status"
            lines.append(f"- `{item['result_id']}` ({item['data_type']}): {missing}")
    else:
        lines.append("- None. Completed results are skipped.")
    lines.extend(["", "## Skip Reasons"])
    reason_counts = _reason_counts(plan["skipped_items"])
    if reason_counts:
        for reason, count in sorted(reason_counts.items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Blocked Items"])
    if plan["blocked_items"]:
        for item in plan["blocked_items"]:
            lines.append(f"- `{item['result_id']}` ({item['data_type']}): {item.get('reason')}")
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def _read_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _resolve_existing_path(project_root: Path, raw_path: Path) -> Path:
    path = raw_path if raw_path.is_absolute() else project_root / raw_path
    absolute = path.absolute()
    if not absolute.exists():
        raise FileNotFoundError(f"Manifest not found: {raw_path}")
    return absolute


def _resolve_artifact_paths(package_root: Path, row: dict[str, str]) -> tuple[list[dict], dict[str, Path]]:
    errors: list[dict] = []
    resolved: dict[str, Path] = {}
    package_root_resolved = package_root.resolve()
    for field in PACKAGE_ARTIFACT_FIELDS:
        value = (row.get(field) or "").strip()
        if not value:
            continue
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            errors.append({"field": field, "value": value})
            continue
        candidate = package_root / path
        candidate_resolved = candidate.resolve()
        try:
            candidate_resolved.relative_to(package_root_resolved)
        except ValueError:
            errors.append({"field": field, "value": value})
            continue
        resolved[field] = candidate
    return errors, resolved


def _check_source_hash(project_root: Path, package_root: Path, row: dict[str, str], expected_hash: str) -> dict:
    source_copy_value = (row.get("source_copy") or row.get("selected_source_copy") or row.get("selected_source_data") or "").strip()
    if source_copy_value:
        source_copy = Path(source_copy_value)
        if source_copy.is_absolute() or ".." in source_copy.parts:
            return {"ok": False, "reason": "source_copy_path_traversal_or_absolute"}
        source_path = package_root / source_copy
        source_path_resolved = source_path.resolve()
        try:
            source_path_resolved.relative_to(package_root.resolve())
        except ValueError:
            return {"ok": False, "reason": "source_copy_resolves_outside_package"}
        if not source_path.exists() or not source_path.is_file():
            return {"ok": False, "reason": "source_copy_missing_for_hash_check", "source_copy": source_copy_value}
        actual_hash = _file_sha256(source_path)
        if actual_hash.lower() != expected_hash.lower():
            return {
                "ok": False,
                "reason": "source_hash_mismatch",
                "source_copy": source_copy_value,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            }
        return {"ok": True, "source_copy": source_copy_value, "source_path_checked": str(source_path)}

    source_value = (row.get("source_file") or "").strip()
    if not source_value:
        return {"ok": False, "reason": "source_file_missing_from_manifest"}
    source_relative = Path(source_value)
    if source_relative.is_absolute() or ".." in source_relative.parts:
        return {"ok": False, "reason": "source_file_path_traversal_or_absolute"}
    workspace_root = (project_root / DEFAULT_WORKSPACE_RELATIVE).absolute()
    workspace_root_resolved = workspace_root.resolve()
    source_path = workspace_root / source_relative
    source_path_resolved = source_path.resolve()
    try:
        source_path_resolved.relative_to(workspace_root_resolved)
    except ValueError:
        return {"ok": False, "reason": "source_file_resolves_outside_workspace"}
    if not source_path.exists() or not source_path.is_file():
        return {"ok": False, "reason": "source_file_missing_for_hash_check", "source_file": source_value}
    actual_hash = _file_sha256(source_path)
    if actual_hash.lower() != expected_hash.lower():
        return {
            "ok": False,
            "reason": "source_hash_mismatch",
            "source_file": source_value,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }
    return {"ok": True, "source_file": source_value, "source_path_checked": str(source_path)}


def _missing_or_empty(paths: dict[str, Path], fields: tuple[str, ...]) -> list[str]:
    missing = []
    for field in fields:
        path = paths.get(field)
        if path is None or not path.exists() or not path.is_file() or path.stat().st_size == 0:
            missing.append(field)
    return missing


def _is_complete(row: dict[str, str], artifacts: dict[str, Path], missing_outputs: list[str]) -> bool:
    status_ok = _normalize(row.get("origin_status", "")) == "success"
    qc_ok = _normalize(row.get("qc_status", "")) == "qc_pass"
    outputs_ok = not missing_outputs
    inputs_ok = not _missing_or_empty(artifacts, INPUT_ARTIFACT_FIELDS)
    return status_ok and qc_ok and outputs_ok and inputs_ok


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guard_output_path(project_root: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = [(project_root / "output").resolve(), (project_root / "docs").resolve(), (project_root / "tests" / "fixtures").resolve()]
    if not any(_is_under_or_equal(resolved, root) for root in allowed):
        raise ValueError(f"Refusing to write report outside allowed output areas: {path}")


def _is_under_or_equal(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return path == parent


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _reason_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(item.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    return counts
