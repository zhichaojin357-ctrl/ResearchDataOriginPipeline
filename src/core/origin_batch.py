from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.core.manifest_schema import schema_mismatch_message
from src.core.output_sanitizer import scrub_output_text
from src.core.project import default_output_root, ensure_write_path_allowed, report_path
from src.core.runtime_paths import resolve_workspace_root
from src.origin.adapter import export_plot


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
REQUIRED_MANIFEST_HEADERS = {
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
ORIGIN_STATUS_HEADERS = {"origin_status", "origin_export_status"}
SOURCE_LOCATOR_HEADERS = {"source_file", "source_copy", "selected_source_copy", "selected_source_data"}


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
    output_root: Path | None = None


def run_origin_batch(project_root: Path, options: OriginBatchOptions) -> int:
    plan = plan_origin_batch(project_root, options)
    if not plan["execution"]["blocked"] and options.execute and options.with_origin:
        execution = execute_origin_batch_exports(project_root, options, plan)
        plan["execution"].update(
            {
                "reason": "executed_with_origin",
                "origin_launch": True,
                "exported": execution["exported"],
                "failures": execution["failures"],
            }
        )
        plan["summary"]["exported_count"] = len(execution["exported"])
        plan["summary"]["failure_count"] = len(execution["failures"])
        plan["summary"]["will_launch_origin"] = True
    write_origin_batch_reports(project_root, plan, options)
    if plan["execution"]["blocked"]:
        return 2
    if int(plan["summary"].get("failure_count", 0)):
        return 1
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
        if _normalize(row.get("safe_for_origin_batch", "")) == "false":
            skipped.append({**base_item, "reason": "not_safe_for_origin_batch", "details": row.get("notes", "")})
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
                "origin_status": _origin_status(row),
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
        execution_reason = "ready_to_execute_with_origin"

    plan = {
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
            "will_launch_origin": bool(options.execute and options.with_origin and not execution_blocked),
            "exported_count": 0,
            "failure_count": 0,
        },
        "execution": {
            "blocked": execution_blocked,
            "reason": execution_reason,
            "origin_launch": bool(options.execute and options.with_origin and not execution_blocked),
            "notes": "origin-batch is dry-run by default; real Origin export requires both --execute and --with-origin.",
        },
        "planned_items": planned,
        "skipped_items": skipped,
        "blocked_items": blocked,
    }
    return _sanitize_report_payload(project_root, plan, options.output_root)


def execute_origin_batch_exports(project_root: Path, options: OriginBatchOptions, plan: dict) -> dict[str, list[dict[str, object]]]:
    project_root = project_root.absolute()
    manifest_path = _resolve_existing_path(project_root, options.manifest)
    package_root = manifest_path.parent.absolute()
    rows = _read_manifest_rows(manifest_path)
    planned_rows = {int(item["row_number"]) for item in plan.get("planned_items", [])}
    exported: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=2):
        if row_number not in planned_rows:
            continue
        result_id = row.get("result_id") or f"row_{row_number}"
        data_type = row.get("data_type", "")
        try:
            path_errors, artifacts = _resolve_artifact_paths(package_root, row)
            if path_errors:
                raise ValueError(f"artifact path validation failed: {path_errors}")
            source_check = _check_source_hash(project_root, package_root, row, row.get("source_hash", "").strip())
            if not source_check.get("ok"):
                raise ValueError(str(source_check.get("reason") or "source hash check failed"))
            processed_csv = artifacts["processed_csv"]
            x_title, y_title = _csv_axis_titles(processed_csv)
            source_file = Path(str(source_check.get("source_path_checked"))) if source_check.get("source_path_checked") else None
            origin_result = export_plot(
                project_root,
                result_id,
                processed_csv,
                x_title,
                y_title,
                data_type=data_type,
                source_file=source_file,
                output_root=package_root,
            )
            if not getattr(origin_result, "ok", False):
                raise RuntimeError(getattr(origin_result, "message", "Origin export failed"))
            _copy_exported_artifact(origin_result.origin_file, artifacts.get("origin_file"))
            _copy_exported_artifact(origin_result.figure_tif, artifacts.get("figure_tif"))
            _copy_exported_artifact(origin_result.preview_png, artifacts.get("preview_png"))
            missing = _missing_or_empty(artifacts, ORIGIN_OUTPUT_FIELDS)
            if missing:
                raise RuntimeError("Origin export did not produce manifest outputs: " + ", ".join(missing))
            exported.append(
                {
                    "row_number": row_number,
                    "result_id": result_id,
                    "data_type": data_type,
                    "origin_file": str(artifacts["origin_file"]),
                    "figure_tif": str(artifacts["figure_tif"]),
                    "preview_png": str(artifacts["preview_png"]),
                }
            )
        except Exception as exc:
            failures.append({"row_number": row_number, "result_id": result_id, "data_type": data_type, "message": str(exc)})
    return _sanitize_report_payload(project_root, {"exported": exported, "failures": failures}, options.output_root)


def write_origin_batch_reports(project_root: Path, plan: dict, options: OriginBatchOptions) -> tuple[Path, Path]:
    effective_output_root = options.output_root or default_output_root(project_root)
    json_path = options.report_json or report_path(
        project_root,
        "origin_batch_plan.json",
        output_root=options.output_root,
    )
    md_path = options.report_md or report_path(
        project_root,
        "origin_batch_plan.md",
        output_root=options.output_root,
    )
    _guard_output_path(project_root, json_path, effective_output_root)
    _guard_output_path(project_root, md_path, effective_output_root)
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_manifest_plan_markdown(plan), encoding="utf-8")
    return json_path, md_path


def _csv_axis_titles(path: Path) -> tuple[str, str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            row = next(csv.reader(handle), [])
    except (OSError, StopIteration):
        return "X", "Y"
    x_title = str(row[0]).strip() if len(row) >= 1 and str(row[0]).strip() else "X"
    y_title = str(row[1]).strip() if len(row) >= 2 and str(row[1]).strip() else "Y"
    return x_title, y_title


def _copy_exported_artifact(source: Path | str | None, target: Path | None) -> None:
    if source is None or target is None:
        return
    source_path = Path(source)
    if not source_path.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() == target.resolve():
        return
    shutil.copy2(source_path, target)


def _manifest_plan_markdown(plan: dict) -> str:
    summary = plan["summary"]
    lines = [
        "# Origin Batch Plan",
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
        try:
            reader = csv.reader(handle, strict=True)
            raw_header = next(reader, None)
            headers = _validate_manifest_headers(raw_header, path)
            rows: list[dict[str, str]] = []
            for line_number, row in enumerate(reader, start=2):
                if not row or not any(str(cell).strip() for cell in row):
                    continue
                if len(row) != len(headers):
                    raise ValueError(f"manifest CSV row {line_number} has {len(row)} columns; expected {len(headers)}: {path}")
                rows.append(dict(zip(headers, row, strict=True)))
            return rows
        except csv.Error as exc:
            raise ValueError(f"manifest CSV parse error: {exc}: {path}") from exc


def _validate_manifest_headers(fieldnames: list[str] | None, path: Path) -> list[str]:
    if not fieldnames:
        raise ValueError(f"manifest CSV missing headers: {path}")
    headers = [str(field).strip() for field in fieldnames]
    if any(not header for header in headers):
        raise ValueError(f"manifest CSV blank header: {path}")
    duplicates = sorted({header for header in headers if headers.count(header) > 1})
    if duplicates:
        raise ValueError(f"manifest CSV duplicate header: {', '.join(duplicates)}: {path}")
    header_set = set(headers)
    missing = sorted(REQUIRED_MANIFEST_HEADERS - header_set)
    if not header_set.intersection(ORIGIN_STATUS_HEADERS):
        missing.append("origin_status")
    if missing:
        raise ValueError(f"manifest CSV missing required headers: {', '.join(missing)}: {path}; {schema_mismatch_message(path)}")
    if not header_set.intersection(SOURCE_LOCATOR_HEADERS):
        choices = ", ".join(sorted(SOURCE_LOCATOR_HEADERS))
        raise ValueError(f"manifest CSV must include one source locator header ({choices}): {path}")
    return headers


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

    packaged_source = _find_package_source_copy_by_hash(package_root, expected_hash)
    if packaged_source is not None:
        return {
            "ok": True,
            "source_copy": str(packaged_source.relative_to(package_root).as_posix()),
            "source_path_checked": str(packaged_source),
            "source_copy_resolution": "selected_source_data_hash_match",
        }

    source_value = (row.get("source_file") or "").strip()
    if not source_value:
        return {"ok": False, "reason": "source_file_missing_from_manifest"}
    source_relative = Path(source_value)
    if source_relative.is_absolute() or ".." in source_relative.parts:
        return {"ok": False, "reason": "source_file_path_traversal_or_absolute"}
    workspace_root = resolve_workspace_root(project_root).absolute()
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


def _find_package_source_copy_by_hash(package_root: Path, expected_hash: str) -> Path | None:
    source_root = package_root / "selected_source_data"
    if not source_root.is_dir():
        return None
    expected = expected_hash.lower()
    for path in sorted(source_root.rglob("*")):
        if path.is_file() and _file_sha256(path).lower() == expected:
            return path
    return None


def _missing_or_empty(paths: dict[str, Path], fields: tuple[str, ...]) -> list[str]:
    missing = []
    for field in fields:
        path = paths.get(field)
        if path is None or not path.exists() or not path.is_file() or path.stat().st_size == 0:
            missing.append(field)
    return missing


def _is_complete(row: dict[str, str], artifacts: dict[str, Path], missing_outputs: list[str]) -> bool:
    status_ok = _normalize(_origin_status(row)) == "success"
    qc_ok = _normalize(row.get("qc_status", "")) == "qc_pass"
    outputs_ok = not missing_outputs
    inputs_ok = not _missing_or_empty(artifacts, INPUT_ARTIFACT_FIELDS)
    return status_ok and qc_ok and outputs_ok and inputs_ok


def _origin_status(row: dict[str, str]) -> str:
    return row.get("origin_status") or row.get("origin_export_status", "")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guard_output_path(project_root: Path, path: Path, output_root: Path) -> None:
    ensure_write_path_allowed(project_root, path, output_root=output_root)


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _reason_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(item.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _sanitize_report_payload(project_root: Path, value: object, output_root: Path | None = None) -> object:
    if isinstance(value, dict):
        return {str(key): _sanitize_report_payload(project_root, item, output_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_report_payload(project_root, item, output_root) for item in value]
    if isinstance(value, str):
        return scrub_output_text(value, project_root=project_root, output_root=output_root)
    return value
