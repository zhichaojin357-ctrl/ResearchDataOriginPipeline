from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.core.file_utils import (
    apply_safe_owned_directory_removal,
    ensure_safe_output_file_target,
    file_sha256 as _file_sha256,
    lexical_absolute_path,
    plan_safe_owned_directory_removal,
)
from src.core.image_artifacts import validate_tif_physical_resolution
from src.core.manifest_schema import (
    ORIGIN_BATCH_REQUIRED_COLUMNS,
    ORIGIN_STATUS_ALIASES,
    SOURCE_LOCATOR_COLUMNS,
    schema_mismatch_message,
)
from src.core.output_sanitizer import sanitize_report_payload as _sanitize_report_payload
from src.core.project import (
    default_output_root,
    ensure_output_path_separate_from_inputs,
    ensure_write_path_allowed,
    report_path,
)
from src.core.runtime_paths import resolve_workspace_root
from src.origin.adapter import (
    export_plot,
    plan_origin_plot_output_paths,
    validate_origin_dataset_id,
)


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
ORIGIN_OUTPUT_SUFFIXES = {
    "origin_file": {".opj", ".opju"},
    "figure_tif": {".tif", ".tiff"},
    "preview_png": {".png"},
}
INPUT_ARTIFACT_FIELDS = ("processed_csv", "metadata")
REQUIRED_MANIFEST_HEADERS = ORIGIN_BATCH_REQUIRED_COLUMNS
ORIGIN_STATUS_HEADERS = ORIGIN_STATUS_ALIASES
SOURCE_LOCATOR_HEADERS = SOURCE_LOCATOR_COLUMNS


class _PackageSourceIndex:
    """Lazy, ordered source lookup owned by one planning or execution phase."""

    def __init__(self, package_root: Path) -> None:
        self.source_root = package_root / "selected_source_data"
        self._paths = None
        self._matches: dict[str, Path] = {}

    def find(self, expected_hash: str) -> Path | None:
        expected = expected_hash.lower()
        if expected in self._matches:
            return self._matches[expected]
        if self._paths is None:
            self._paths = iter(sorted(self.source_root.rglob("*"))) if self.source_root.is_dir() else iter(())
        for path in self._paths:
            if not path.is_file():
                continue
            digest = _file_sha256(path).lower()
            self._matches.setdefault(digest, path)
            if digest == expected:
                return self._matches[digest]
        return None


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
    _resolve_origin_batch_report_paths(project_root, options)
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
    source_index = _PackageSourceIndex(package_root)

    for row_number, row in enumerate(rows, start=2):
        result_id = row.get("result_id") or f"row_{row_number}"
        data_type = row.get("data_type", "")
        base_item = {
            "row_number": row_number,
            "result_id": result_id,
            "queue_id": row.get("queue_id", ""),
            "data_type": data_type,
        }
        try:
            validate_origin_dataset_id(result_id)
        except ValueError as exc:
            blocked.append(
                {
                    **base_item,
                    "reason": "unsafe_result_id",
                    "details": str(exc),
                }
            )
            continue
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

        source_check = _check_source_hash(project_root, package_root, row, source_hash, source_index=source_index)
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
    # Planning may precede execution by hours. Never reuse its content evidence.
    source_index = _PackageSourceIndex(package_root)
    _validate_origin_batch_global_ownership(
        project_root,
        manifest_path,
        package_root,
        rows,
        planned_rows,
        source_index=source_index,
    )
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
            source_check = _check_source_hash(
                project_root, package_root, row, row.get("source_hash", "").strip(),
                source_index=source_index, verify_selected=True,
            )
            if not source_check.get("ok"):
                raise ValueError(str(source_check.get("reason") or "source hash check failed"))
            processed_csv = artifacts["processed_csv"]
            x_title, y_title = _csv_axis_titles(processed_csv)
            source_file = Path(str(source_check.get("source_path_checked"))) if source_check.get("source_path_checked") else None
            _preflight_origin_output_targets(
                artifacts,
                output_root=package_root,
                protected_inputs=tuple(
                    path
                    for path in (manifest_path, source_file)
                    if path is not None
                ),
            )
            stage_root = Path(
                tempfile.mkdtemp(
                    prefix=".origin_batch_",
                    dir=package_root,
                )
            )
            try:
                origin_result = export_plot(
                    project_root,
                    result_id,
                    processed_csv,
                    x_title,
                    y_title,
                    data_type=data_type,
                    source_file=source_file,
                    output_root=stage_root,
                    force=True,
                )
                if not getattr(origin_result, "ok", False):
                    raise RuntimeError(
                        getattr(origin_result, "message", "Origin export failed")
                    )
                source_evidence = getattr(
                    origin_result,
                    "tif_resolution_evidence",
                    None,
                )
                if source_evidence is None:
                    raise RuntimeError(
                        "Origin export reported success without native TIFF "
                        "resolution evidence."
                    )
                # The exporter has already decoded this unchanged staging TIFF.
                # The published copy is still independently checked below.
                staged_tif_evidence = source_evidence
                _publish_origin_artifact_package(
                    (
                        (Path(origin_result.origin_file), artifacts["origin_file"]),
                        (Path(origin_result.figure_tif), artifacts["figure_tif"]),
                        (Path(origin_result.preview_png), artifacts["preview_png"]),
                    ),
                    output_root=package_root,
                )
                tif_evidence = validate_tif_physical_resolution(
                    artifacts["figure_tif"],
                    page_width_origin_units=float(
                        staged_tif_evidence.page_width_origin_units
                    ),
                    page_height_origin_units=float(
                        staged_tif_evidence.page_height_origin_units
                    ),
                    dpi=int(staged_tif_evidence.requested_dpi),
                )
            finally:
                _remove_origin_batch_stage(stage_root, output_root=package_root)
            exported.append(
                {
                    "row_number": row_number,
                    "result_id": result_id,
                    "data_type": data_type,
                    "origin_file": str(artifacts["origin_file"]),
                    "figure_tif": str(artifacts["figure_tif"]),
                    "preview_png": str(artifacts["preview_png"]),
                    "tif_resolution_evidence": tif_evidence.as_dict(),
                    "stage_timings_seconds": getattr(origin_result, "stage_timings_seconds", None) or {},
                }
            )
        except Exception as exc:
            failures.append({"row_number": row_number, "result_id": result_id, "data_type": data_type, "message": str(exc)})
    return _sanitize_report_payload(project_root, {"exported": exported, "failures": failures}, options.output_root)


def write_origin_batch_reports(project_root: Path, plan: dict, options: OriginBatchOptions) -> tuple[Path, Path]:
    effective_output_root, json_path, md_path = _resolve_origin_batch_report_paths(
        project_root,
        options,
    )
    _atomic_write_origin_batch_reports(
        (
            (json_path, json.dumps(plan, ensure_ascii=False, indent=2)),
            (md_path, _manifest_plan_markdown(plan)),
        ),
        output_root=effective_output_root,
    )
    return json_path, md_path


def _resolve_origin_batch_report_paths(
    project_root: Path,
    options: OriginBatchOptions,
) -> tuple[Path, Path, Path]:
    requested_output_root = options.output_root or default_output_root(project_root)
    if not requested_output_root.is_absolute():
        requested_output_root = project_root / requested_output_root
    effective_output_root = lexical_absolute_path(requested_output_root)
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
    json_path = ensure_safe_output_file_target(
        json_path,
        output_root=effective_output_root,
    )
    md_path = ensure_safe_output_file_target(
        md_path,
        output_root=effective_output_root,
    )
    manifest_path = _resolve_existing_path(project_root, options.manifest)
    package_root = manifest_path.parent
    rows = _read_manifest_rows(manifest_path)
    declared_paths, external_source_paths = _manifest_declared_paths(
        project_root,
        package_root,
        rows,
    )
    ensure_output_path_separate_from_inputs(
        project_root,
        effective_output_root,
        tuple(external_source_paths),
    )
    if _paths_alias(json_path, md_path):
        raise ValueError("Origin batch JSON and Markdown report paths must be distinct.")
    for label, report in (("JSON", json_path), ("Markdown", md_path)):
        if _paths_alias(report, manifest_path):
            raise ValueError(
                f"Origin batch {label} report path aliases the input manifest."
            )
        for declared in declared_paths:
            if _paths_alias(report, declared):
                raise ValueError(
                    f"Origin batch {label} report path aliases a manifest-declared artifact."
                )
        if os.path.lexists(os.fspath(report)) and report.is_dir():
            raise IsADirectoryError(
                f"Origin batch {label} report target is a directory: {report}"
            )
    return effective_output_root, json_path, md_path


def _atomic_write_origin_batch_reports(
    payloads: tuple[tuple[Path, str], ...],
    *,
    output_root: Path,
) -> None:
    safe_payloads = tuple(
        (
            ensure_safe_output_file_target(path, output_root=output_root),
            text,
        )
        for path, text in payloads
    )
    for target, _text in safe_payloads:
        target.parent.mkdir(parents=True, exist_ok=True)
    safe_payloads = tuple(
        (
            ensure_safe_output_file_target(path, output_root=output_root),
            text,
        )
        for path, text in safe_payloads
    )

    temporary_paths: list[tuple[Path, Path]] = []
    try:
        for target, body in safe_payloads:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                if os.path.lexists(os.fspath(temporary)):
                    temporary.unlink()
                raise
            temporary_paths.append((temporary, target))

        for _temporary, target in temporary_paths:
            ensure_safe_output_file_target(target, output_root=output_root)
            if os.path.lexists(os.fspath(target)) and target.is_dir():
                raise IsADirectoryError(
                    f"Origin batch report target became a directory: {target}"
                )
        for temporary, target in temporary_paths:
            os.replace(temporary, target)
    finally:
        for temporary, _target in temporary_paths:
            if os.path.lexists(os.fspath(temporary)):
                temporary.unlink()


def _csv_axis_titles(path: Path) -> tuple[str, str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            row = next(csv.reader(handle), [])
    except (OSError, StopIteration):
        return "X", "Y"
    x_title = str(row[0]).strip() if len(row) >= 1 and str(row[0]).strip() else "X"
    y_title = str(row[1]).strip() if len(row) >= 2 and str(row[1]).strip() else "Y"
    return x_title, y_title


def _preflight_origin_output_targets(
    artifacts: dict[str, Path],
    *,
    output_root: Path,
    protected_inputs: tuple[Path, ...] = (),
    extra_targets: tuple[Path, ...] = (),
) -> None:
    """Validate every retry target without modifying any existing artifact."""

    root = lexical_absolute_path(output_root)
    input_paths = tuple(
        lexical_absolute_path(path)
        for path in (
            *(
                artifacts[field]
                for field in PACKAGE_ARTIFACT_FIELDS
                if field in artifacts and field not in ORIGIN_OUTPUT_FIELDS
            ),
            *protected_inputs,
        )
    )
    manifest_output_items = tuple(
        (field, lexical_absolute_path(artifacts[field]))
        for field in ORIGIN_OUTPUT_FIELDS
        if field in artifacts
    )
    for index, (left_label, left_path) in enumerate(manifest_output_items):
        for right_label, right_path in manifest_output_items[index + 1 :]:
            if _paths_alias(left_path, right_path):
                raise ValueError(
                    "Origin manifest output targets must be mutually distinct: "
                    f"{left_label} aliases {right_label}"
                )
    output_items = manifest_output_items + tuple(
        (f"generic_retry_target_{index}", lexical_absolute_path(path))
        for index, path in enumerate(extra_targets, start=1)
    )
    output_paths = tuple(path for _label, path in output_items)

    safe_outputs = tuple(
        ensure_safe_output_file_target(path, output_root=root)
        for path in output_paths
    )
    for field, target in output_items:
        for input_path in input_paths:
            if _paths_alias(target, input_path):
                raise ValueError(
                    f"Origin output target aliases a required input artifact: {field}"
                )

    directories = [
        path
        for path in safe_outputs
        if os.path.lexists(os.fspath(path)) and path.is_dir()
    ]
    if directories:
        rendered = ", ".join(str(path) for path in directories[:8])
        raise IsADirectoryError(
            "Origin batch output target collides with a directory: " + rendered
        )


def _publish_origin_artifact_package(
    items: tuple[tuple[Path, Path], ...],
    *,
    output_root: Path,
) -> None:
    """Publish one validated Origin artifact set with rollback on commit failure."""

    root = lexical_absolute_path(output_root)
    token = uuid.uuid4().hex
    prepared: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for source, requested_target in items:
            source = lexical_absolute_path(source)
            target = ensure_safe_output_file_target(
                requested_target,
                output_root=root,
            )
            if not source.is_file() or source.stat().st_size == 0:
                raise RuntimeError(
                    f"Origin export did not produce a non-empty staged artifact: {source}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target = ensure_safe_output_file_target(target, output_root=root)
            if os.path.lexists(os.fspath(target)) and target.is_dir():
                raise IsADirectoryError(
                    f"Origin batch publish target is a directory: {target}"
                )
            temporary = target.parent / f".{target.name}.{token}.publish"
            ensure_safe_output_file_target(temporary, output_root=root)
            if os.path.lexists(os.fspath(temporary)):
                raise FileExistsError(
                    f"Origin batch temporary publish target already exists: {temporary}"
                )
            shutil.copy2(source, temporary)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise RuntimeError(
                    f"Origin batch staged copy is missing or empty: {temporary}"
                )
            prepared.append((temporary, target))

        for temporary, target in prepared:
            ensure_safe_output_file_target(target, output_root=root)
            if os.path.lexists(os.fspath(target)):
                backup = target.parent / f".{target.name}.{token}.rollback"
                ensure_safe_output_file_target(backup, output_root=root)
                if os.path.lexists(os.fspath(backup)):
                    raise FileExistsError(
                        f"Origin batch rollback target already exists: {backup}"
                    )
                os.replace(target, backup)
                backups.append((backup, target))
            os.replace(temporary, target)
            installed.append(target)
    except Exception:
        for target in reversed(installed):
            if os.path.lexists(os.fspath(target)):
                ensure_safe_output_file_target(target, output_root=root).unlink()
        for backup, target in reversed(backups):
            if os.path.lexists(os.fspath(backup)):
                os.replace(backup, target)
        raise
    else:
        for backup, _target in backups:
            if os.path.lexists(os.fspath(backup)):
                backup.unlink()
    finally:
        for temporary, _target in prepared:
            if os.path.lexists(os.fspath(temporary)):
                temporary.unlink()


def _remove_origin_batch_stage(stage_root: Path, *, output_root: Path) -> bool:
    if not os.path.lexists(os.fspath(stage_root)):
        return True
    try:
        plan = plan_safe_owned_directory_removal(
            stage_root,
            output_root=output_root,
        )
        apply_safe_owned_directory_removal(plan, output_root=output_root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        # A cleanup failure must never roll back or invalidate an already
        # committed scientific package.  The bounded, uniquely named staging
        # directory is retained for manual cleanup instead.
        return False
    return True


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
    for field, expected_suffixes in ORIGIN_OUTPUT_SUFFIXES.items():
        if field not in resolved:
            continue
        suffix = resolved[field].suffix.casefold()
        if suffix not in expected_suffixes:
            errors.append(
                {
                    "field": field,
                    "value": row.get(field, ""),
                    "reason": "unexpected_output_suffix",
                    "expected": sorted(expected_suffixes),
                }
            )
    output_items = [
        (field, resolved[field])
        for field in ORIGIN_OUTPUT_FIELDS
        if field in resolved
    ]
    for index, (left_field, left_path) in enumerate(output_items):
        for right_field, right_path in output_items[index + 1 :]:
            if _paths_alias(left_path, right_path):
                errors.append(
                    {
                        "field": left_field,
                        "aliases": right_field,
                        "reason": "origin_output_paths_alias",
                    }
                )
        for input_field, input_path in resolved.items():
            if input_field in ORIGIN_OUTPUT_FIELDS:
                continue
            if _paths_alias(left_path, input_path):
                errors.append(
                    {
                        "field": left_field,
                        "aliases": input_field,
                        "reason": "origin_output_aliases_input_artifact",
                    }
                )
    return errors, resolved


def _manifest_declared_paths(
    project_root: Path,
    package_root: Path,
    rows: list[dict[str, str]],
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    declared: list[Path] = []
    external_sources: list[Path] = []
    package_root_lexical = lexical_absolute_path(package_root)
    for row in rows:
        _errors, artifacts = _resolve_artifact_paths(package_root, row)
        declared.extend(artifacts.values())
        for field in SOURCE_LOCATOR_HEADERS:
            value = str(row.get(field) or "").strip()
            if not value:
                continue
            raw = Path(value)
            if field == "source_file":
                if raw.is_absolute() or ".." in raw.parts:
                    continue
                candidate = resolve_workspace_root(project_root).absolute() / raw
            else:
                if raw.is_absolute() or ".." in raw.parts:
                    continue
                candidate = package_root / raw
            candidate = lexical_absolute_path(candidate)
            if not os.path.lexists(os.fspath(candidate)):
                continue
            declared.append(candidate)
            try:
                candidate.relative_to(package_root_lexical)
            except ValueError:
                if field == "source_file":
                    external_sources.append(candidate)
    return (
        tuple(dict.fromkeys(lexical_absolute_path(path) for path in declared)),
        tuple(dict.fromkeys(lexical_absolute_path(path) for path in external_sources)),
    )


def _validate_origin_batch_global_ownership(
    project_root: Path,
    manifest_path: Path,
    package_root: Path,
    rows: list[dict[str, str]],
    planned_rows: set[int],
    *,
    source_index: _PackageSourceIndex | None = None,
) -> None:
    row_artifacts: dict[int, dict[str, Path]] = {}
    protected_inputs: list[tuple[str, Path]] = [("manifest", manifest_path)]
    declared_outputs: list[tuple[int, str, Path]] = []
    generic_outputs: list[tuple[int, str, Path]] = []

    for row_number, row in enumerate(rows, start=2):
        _errors, artifacts = _resolve_artifact_paths(package_root, row)
        row_artifacts[row_number] = artifacts
        for field, path in artifacts.items():
            if field in ORIGIN_OUTPUT_FIELDS:
                declared_outputs.append((row_number, field, path))
            else:
                protected_inputs.append((f"row_{row_number}:{field}", path))
        source_check = _check_source_hash(
            project_root,
            package_root,
            row,
            str(row.get("source_hash") or "").strip(),
            source_index=source_index,
        )
        source_checked = str(source_check.get("source_path_checked") or "").strip()
        if source_checked:
            protected_inputs.append(
                (f"row_{row_number}:source", Path(source_checked))
            )
        if row_number in planned_rows:
            result_id = str(row.get("result_id") or f"row_{row_number}")
            paths = plan_origin_plot_output_paths(
                project_root,
                result_id,
                output_root=package_root,
            )
            generic_outputs.extend(
                (
                    (row_number, "generic_plot_csv", paths.plot_csv),
                    (row_number, "generic_job_script", paths.job_script),
                    (row_number, "generic_origin_file", paths.origin_file),
                    (row_number, "generic_figure_tif", paths.figure_tif),
                    (row_number, "generic_preview_png", paths.preview_png),
                )
            )

    for row_number in planned_rows:
        artifacts = row_artifacts.get(row_number, {})
        planned_targets = [
            (field, artifacts[field])
            for field in ORIGIN_OUTPUT_FIELDS
            if field in artifacts
        ] + [
            (label, path)
            for owner, label, path in generic_outputs
            if owner == row_number
        ]
        for label, target in planned_targets:
            for protected_label, protected in protected_inputs:
                if _paths_alias(target, protected):
                    raise ValueError(
                        "Origin batch planned output aliases a package input: "
                        f"row {row_number} {label} -> {protected_label}"
                    )
            for owner, other_label, other in declared_outputs:
                if owner == row_number:
                    continue
                if _paths_alias(target, other):
                    raise ValueError(
                        "Origin batch planned output aliases another manifest "
                        f"row: row {row_number} {label} -> row {owner} {other_label}"
                    )
            for owner, other_label, other in generic_outputs:
                if owner == row_number:
                    continue
                if _paths_alias(target, other):
                    raise ValueError(
                        "Origin batch generic outputs collide across rows: "
                        f"row {row_number} {label} -> row {owner} {other_label}"
                    )


def _check_source_hash(
    project_root: Path, package_root: Path, row: dict[str, str], expected_hash: str,
    *, source_index: _PackageSourceIndex | None = None, verify_selected: bool = False,
) -> dict:
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

    packaged_source = (
        source_index.find(expected_hash) if source_index is not None
        else _find_package_source_copy_by_hash(package_root, expected_hash)
    )
    if packaged_source is not None:
        if verify_selected:
            actual_hash = _file_sha256(packaged_source)
            if actual_hash.lower() != expected_hash.lower():
                return {
                    "ok": False, "reason": "source_hash_mismatch",
                    "source_copy": str(packaged_source.relative_to(package_root).as_posix()),
                    "expected_hash": expected_hash, "actual_hash": actual_hash,
                }
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
    return _PackageSourceIndex(package_root).find(expected_hash)


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


def _guard_output_path(project_root: Path, path: Path, output_root: Path) -> None:
    ensure_write_path_allowed(project_root, path, output_root=output_root)


def _paths_alias(left: Path, right: Path) -> bool:
    left_path = lexical_absolute_path(left)
    right_path = lexical_absolute_path(right)
    if os.path.normcase(os.fspath(left_path)) == os.path.normcase(os.fspath(right_path)):
        return True
    if (
        os.path.lexists(os.fspath(left_path))
        and os.path.lexists(os.fspath(right_path))
    ):
        try:
            return os.path.samefile(left_path, right_path)
        except OSError:
            return False
    return False


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _reason_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = str(item.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    return counts
