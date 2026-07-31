from __future__ import annotations

import json
import csv
import re
from dataclasses import dataclass, replace
from pathlib import Path

from src.core.file_utils import is_under_or_equal
from src.processors.base import process_table_dataset
from src.scanner.scanner import scan_raw_data
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.project import (
    default_output_root,
    ensure_output_path_separate_from_inputs,
    output_dir,
    report_path,
)
from src.core.runtime_paths import resolve_locked_result_index


@dataclass(frozen=True)
class ProcessOptions:
    no_origin: bool = False
    with_origin: bool = False
    only_type: str | None = None
    only_folder: str | None = None
    fail_fast: bool = False
    force: bool = False
    from_queue: Path | None = None
    auto_select: bool = False
    include_ambiguous: bool = False
    output_root: Path | None = None


def run_process(project_root: Path, input_path: Path, options: ProcessOptions | None = None) -> int:
    options = _normalize_origin_mode(options or ProcessOptions())
    _validate_process_mode(options)
    ensure_output_path_separate_from_inputs(
        project_root,
        options.output_root or default_output_root(project_root),
        [input_path],
    )
    if options.auto_select and options.from_queue is None:
        from src.core.triage import TriageOptions, run_triage

        run_triage(
            project_root,
            input_path,
            TriageOptions(only_type=options.only_type, only_folder=options.only_folder, output_root=options.output_root),
        )
        options = ProcessOptions(
            no_origin=True,
            with_origin=False,
            only_type=options.only_type,
            only_folder=options.only_folder,
            fail_fast=options.fail_fast,
            force=options.force,
            from_queue=report_path(project_root, "processing_queue.json", output_root=options.output_root),
            include_ambiguous=options.include_ambiguous,
            output_root=options.output_root,
        )
    elif options.from_queue is not None and not options.with_origin:
        options = ProcessOptions(
            no_origin=True,
            with_origin=False,
            only_type=options.only_type,
            only_folder=options.only_folder,
            fail_fast=options.fail_fast,
            force=options.force,
            from_queue=options.from_queue,
            auto_select=options.auto_select,
            include_ambiguous=options.include_ambiguous,
            output_root=options.output_root,
        )
    manifest = scan_raw_data(project_root, input_path, output_root=options.output_root)
    results: list[dict] = []
    failures: list[dict] = []

    skipped_auxiliary: list[dict] = []
    if options.from_queue is not None:
        work_items = _selected_queue_items(project_root, input_path, options)
    else:
        work_items, skipped_auxiliary = _work_items_from_manifest(manifest, options, project_root=project_root)

    for classification, source, triage_data in work_items:
        if triage_data and triage_data.get("stale_queue_item"):
            failure = _failure_from_queue_validation(classification, source, triage_data, project_root=project_root, output_root=options.output_root)
            failures.append(failure)
            if options.fail_fast:
                break
            continue
        if not classification["supported_in_pipeline"]:
            continue
        try:
            metadata = process_table_dataset(
                project_root,
                classification,
                source,
                no_origin=options.no_origin,
                force=options.force,
                triage=triage_data,
                output_root=options.output_root,
            )
            results.append(metadata)
            if metadata["processing_status"] not in {"success", "processed_no_origin"}:
                failures.append(_failure_from_metadata(metadata, "processing"))
                if options.fail_fast:
                    break
        except Exception as exc:
            failure = _failure_from_exception(classification, source, exc, triage_data, project_root=project_root, output_root=options.output_root)
            failures.append(failure)
            if options.fail_fast:
                break
        if failures and options.fail_fast:
            break

    successes = [item for item in results if item["processing_status"] in {"success", "processed_no_origin"}]
    origin_successes = [item for item in results if item["processing_status"] == "success"]
    report = [
        "# Processing Report",
        "",
        f"Datasets processed: {len(results)}",
        f"Successful/no-Origin processed datasets: {len(successes)}",
        f"Successful Origin exports: {len(origin_successes)}",
        f"Failed or incomplete datasets: {len(failures)}",
        f"Skipped auxiliary/reference sources: {len(skipped_auxiliary)}",
        "",
    ]
    for item in results:
        report.append(f"- `{item['dataset_id']}`: {item['processing_status']}")
    report_path(project_root, "processing_report.md", output_root=options.output_root).write_text("\n".join(report) + "\n", encoding="utf-8")
    report_path(project_root, "processing_report.json", output_root=options.output_root).write_text(
        json.dumps({"results": results, "skipped_auxiliary": skipped_auxiliary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_processing_skipped_auxiliary(project_root, skipped_auxiliary, output_root=options.output_root)
    _write_processing_failures(project_root, failures, output_root=options.output_root)
    _write_processing_summary(project_root, manifest, results, failures, skipped_auxiliary=skipped_auxiliary, output_root=options.output_root)
    _write_review_dashboard(project_root, manifest, results, failures, output_root=options.output_root)
    return 2 if failures else 0


def _work_items_from_manifest(
    manifest: dict,
    options: ProcessOptions,
    *,
    project_root: Path | None = None,
) -> tuple[list[tuple[dict, Path, dict | None]], list[dict]]:
    selected = []
    skipped_auxiliary = []
    for classification in manifest["classifications"]:
        if options.only_type and _normalize(classification["inferred_data_type"]) != _normalize(options.only_type):
            continue
        if options.only_folder and not _folder_matches(classification, options.only_folder):
            continue
        for file_name in classification["files"]:
            source = Path(file_name)
            skip_reason = _manifest_auxiliary_skip_reason(classification, source)
            if skip_reason:
                skipped_auxiliary.append(_skipped_auxiliary_item(classification, source, skip_reason, project_root=project_root, output_root=options.output_root))
                continue
            selected.append((classification, source, None))
    return selected, skipped_auxiliary


def _manifest_auxiliary_skip_reason(classification: dict, source: Path) -> str | None:
    if not classification.get("supported_in_pipeline", False):
        return None
    if str(classification.get("special_handling") or "").startswith("dedicated_"):
        return "dedicated_command_required"
    suffix = source.suffix.casefold()
    data_type = str(classification.get("inferred_data_type") or "")
    name = source.name.casefold()
    if suffix in {".spc", ".dta"}:
        return "native_reader_not_implemented"
    if suffix in {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".caj", ".ris", ".bib", ".enw", ".enl"}:
        return "document_or_report_not_primary_numeric_data"
    if data_type == "XRD" and _xrd_reference_card_name(source):
        return "xrd_reference_card_not_sample_pattern"
    if suffix in {".txt", ".md"} and _note_like_name(name):
        return "note_or_instruction_file_not_primary_numeric_data"
    return None


def _xrd_reference_card_name(source: Path) -> bool:
    name = source.name.casefold()
    return bool("pdf#" in name or "标准卡片" in name or re.search(r"\bstandard[-_\s]*card\b", name))


def _note_like_name(name: str) -> bool:
    stem = Path(name).stem.casefold().strip()
    return stem in {"备注", "note", "notes", "readme"} or any(token in stem for token in ("说明", "教程", "instruction"))


def _skipped_auxiliary_item(
    classification: dict,
    source: Path,
    reason: str,
    *,
    project_root: Path | None = None,
    output_root: Path | None = None,
) -> dict:
    return {
        "source_file": render_output_path(source, project_root=project_root, output_root=output_root),
        "inferred_data_type": classification.get("inferred_data_type"),
        "selected_processor": classification.get("selected_processor"),
        "skip_reason": reason,
        "handling": "recorded_only_not_processed",
    }


def _normalize_origin_mode(options: ProcessOptions) -> ProcessOptions:
    if options.no_origin and options.with_origin:
        raise ValueError("--no-origin and --with-origin cannot be used together.")
    if options.with_origin:
        return replace(options, no_origin=False)
    return replace(options, no_origin=True)


def _validate_process_mode(options: ProcessOptions) -> None:
    if options.auto_select and options.with_origin:
        raise ValueError("--auto-select cannot be combined with --with-origin; build and review an explicit queue first.")
    if options.auto_select and options.from_queue is not None:
        raise ValueError("--auto-select cannot be combined with --from-queue; use one queue source explicitly.")


def _selected_queue_items(project_root: Path, input_path: Path, options: ProcessOptions) -> list[tuple[dict, Path, dict]]:
    from src.core.metadata import file_hash
    from src.core.project import load_json_compatible_yaml, registry_path

    queue_path = options.from_queue if options.from_queue.is_absolute() else project_root / options.from_queue
    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    if not isinstance(queue, dict):
        raise ValueError(f"queue JSON must be an object with an items list: {queue_path}")
    queue_items = queue.get("items", [])
    if not isinstance(queue_items, list):
        raise ValueError(f"queue JSON items must be a list: {queue_path}")
    for index, item in enumerate(queue_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"queue JSON item {index} must be an object: {queue_path}")
    registry = load_json_compatible_yaml(registry_path(project_root))
    by_type = {entry["inferred_data_type"]: entry for entry in registry["entries"]}
    raw_queue_duplicate_items = _raw_queue_locked_result_duplicate_items(project_root, queue_path, queue)
    if raw_queue_duplicate_items:
        message = (
            "raw output/reports/processing_queue.json contains source hashes already represented in the "
            "locked result package; run `run.py auto-queue` and process "
            "output/reports/auto_process_queue.json instead"
        )
        blocked = []
        for item in raw_queue_duplicate_items:
            source, _ = _resolve_queue_source(input_path, item)
            blocked.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item, stale=True, message=message)))
        return blocked
    selected = []
    for item in queue.get("items", []):
        decision = item.get("decision")
        if decision != "AUTO_PROCESS" and not (options.include_ambiguous and decision == "MANUAL_REVIEW"):
            continue
        if decision == "MANUAL_REVIEW" and options.include_ambiguous and not _manual_review_queue_provenance_ok(item):
            source, _ = _resolve_queue_source(input_path, item)
            selected.append((
                _classification_for_queue_item(item, by_type),
                source,
                _triage_from_queue_item(item, stale=True, message="manual review queue item requires promotion provenance before --include-ambiguous processing"),
            ))
            continue
        if options.only_type and _normalize(str(item.get("data_type"))) != _normalize(options.only_type):
            continue
        if options.only_folder and _normalize_path(options.only_folder) not in _normalize_path(str(item.get("relative_path"))):
            continue
        source, source_error = _resolve_queue_source(input_path, item)
        if source_error:
            selected.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item, stale=True, message=source_error)))
            continue
        registry_error = _queue_registry_error(item, by_type)
        if registry_error:
            selected.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item, stale=True, message=registry_error)))
            continue
        if options.with_origin and item.get("origin_export_allowed") is not True:
            selected.append((
                _classification_for_queue_item(item, by_type),
                source,
                _triage_from_queue_item(item, stale=True, message="with-Origin queue items require origin_export_allowed=true"),
            ))
            continue
        if not source.exists():
            selected.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item, stale=True, message="source file missing")))
            continue
        expected_hash = item.get("source_hash")
        if not expected_hash:
            selected.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item, stale=True, message="source hash missing from queue item")))
            continue
        if expected_hash and file_hash(source) != expected_hash:
            selected.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item, stale=True, message="source hash changed since queue creation")))
            continue
        selected.append((_classification_for_queue_item(item, by_type), source, _triage_from_queue_item(item)))
    return selected


def _raw_queue_locked_result_duplicate_items(project_root: Path, queue_path: Path, queue: dict) -> list[dict]:
    default_queue = report_path(project_root, "processing_queue.json").resolve()
    if queue_path.resolve() != default_queue:
        return []
    processed_hashes = _locked_result_processed_hashes(project_root)
    if not processed_hashes:
        return []
    return [
        item
        for item in queue.get("items", [])
        if str(item.get("source_hash", "")).strip() in processed_hashes
    ]


def _locked_result_processed_hashes(project_root: Path) -> set[str]:
    index = resolve_locked_result_index(project_root)
    if not index.is_file():
        return set()
    with index.open("r", encoding="utf-8-sig", newline="") as handle:
        return {str(row.get("source_hash", "")).strip() for row in csv.DictReader(handle) if str(row.get("source_hash", "")).strip()}


def _resolve_queue_source(input_path: Path, item: dict) -> tuple[Path, str | None]:
    input_root = input_path.resolve()
    relative_raw = str(item.get("relative_path") or "")
    relative = Path(relative_raw)
    if relative.is_absolute() or ".." in relative.parts:
        candidate = (input_root / relative).resolve()
        return candidate, "queue source path resolves outside input root"

    absolute_raw = str(item.get("absolute_path") or "")
    if absolute_raw:
        absolute = Path(absolute_raw)
        if absolute.exists():
            if not _is_under_or_equal(absolute.resolve(), input_root):
                return absolute, "queue absolute_path points outside input root"
            return absolute, None

    candidate = (input_root / relative).resolve()
    if not _is_under_or_equal(candidate, input_root):
        return candidate, "queue source path resolves outside input root"
    return candidate, None


def _is_under_or_equal(path: Path, parent: Path) -> bool:
    return is_under_or_equal(path.resolve(), parent.resolve())


def _classification_for_queue_item(item: dict, by_type: dict[str, dict]) -> dict:
    data_type = str(item.get("data_type"))
    entry = by_type.get(data_type, {})
    return {
        "inferred_data_type": data_type,
        "selected_processor": item.get("selected_processor") or entry.get("selected_processor", "none"),
        "supported_in_pipeline": bool(entry.get("supported_in_pipeline", False)),
    }


def _queue_registry_error(item: dict, by_type: dict[str, dict]) -> str | None:
    data_type = str(item.get("data_type", "")).strip()
    entry = by_type.get(data_type)
    if entry is None:
        return f"queue data_type is not in processor registry: {data_type}"
    if entry.get("supported_in_pipeline") is not True:
        return f"queue data_type is not supported in pipeline: {data_type}"
    expected_processor = str(entry.get("selected_processor", "none"))
    actual_processor = str(item.get("selected_processor") or expected_processor)
    if actual_processor != expected_processor:
        return f"queue selected_processor does not match processor registry for {data_type}: {actual_processor} != {expected_processor}"
    return None


def _manual_review_queue_provenance_ok(item: dict) -> bool:
    if item.get("original_triage_decision") != "MANUAL_REVIEW":
        return False
    if not str(item.get("promoted_by_workflow", "")).strip():
        return False
    return item.get("promoted_from_manual_review") is True or item.get("current_decision") == "USER_APPROVED_NO_ORIGIN_QUEUE"


def _triage_from_queue_item(item: dict, *, stale: bool = False, message: str | None = None) -> dict:
    decision = str(item.get("decision"))
    warning = "processed only because --include-ambiguous was explicitly set" if decision == "MANUAL_REVIEW" else None
    triage = {
        "queue_id": item.get("queue_id"),
        "triage_decision": decision,
        "confidence_score": item.get("confidence_score"),
        "validity_score": item.get("validity_score"),
        "decision_reasons": item.get("reasons", []),
        "source_hash": item.get("source_hash"),
        "evidence": item.get("evidence", []),
        "manual_override_used": False,
        "manual_override_keys": [],
        "folder_type_conflict": item.get("folder_type_conflict", False),
        "duplicate_group_id": item.get("duplicate_group_id"),
        "duplicate_representative": item.get("duplicate_representative"),
        "origin_export_allowed": item.get("origin_export_allowed", False),
        "stale_queue_item": stale,
    }
    for key in (
        "original_triage_decision",
        "promoted_from_manual_review",
        "promoted_by_workflow",
        "promoted_workflow_batch",
        "promoted_confidence",
        "promoted_validity",
        "promotion_reason",
        "promotion_evidence",
        "promotion_rule",
        "current_decision",
        "origin_export_risk_level",
        "origin_export_notes",
        "traceability_group_id",
        "traceability_group_path",
        "traceability_role",
        "traceability_basis",
    ):
        if key in item:
            triage[key] = item[key]
    if warning:
        triage["triage_warning"] = warning
    if message:
        triage["message"] = message
    return triage


def _failure_from_queue_validation(
    classification: dict,
    source: Path,
    triage: dict,
    *,
    project_root: Path | None = None,
    output_root: Path | None = None,
) -> dict:
    return {
        "source_file": render_output_path(source, project_root=project_root, output_root=output_root),
        "source_hash": triage.get("source_hash"),
        "inferred_data_type": classification.get("inferred_data_type"),
        "selected_processor": classification.get("selected_processor"),
        "processor_name": classification.get("selected_processor"),
        "triage_decision": triage.get("triage_decision"),
        "failure_stage": "queue_validation",
        "error_message": scrub_output_text(triage.get("message", "queue item is stale or invalid"), project_root=project_root, output_root=output_root),
        "manual_fix_hint": "Regenerate the triage queue, or use an explicit manual override after confirming the source file.",
        "whether_retry_with_manual_override_is_possible": True,
    }


def _folder_matches(classification: dict, selector: str) -> bool:
    needle = _normalize_path(selector)
    candidates = [classification.get("folder_name", "")]
    candidates.extend(str(path) for path in classification.get("folder_paths", []))
    return any(needle in _normalize_path(candidate) for candidate in candidates)


def _normalize(value: str) -> str:
    return value.casefold().strip()


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").casefold().strip("/")


def _failure_from_metadata(metadata: dict, stage: str) -> dict:
    triage = metadata.get("triage", {})
    warnings = metadata.get("warnings", [])
    if stage == "processing" and any("Origin export" in str(warning) or "Origin unavailable" in str(warning) for warning in warnings):
        stage = "origin_export"
    return {
        "source_file": metadata["source_files"][0] if metadata.get("source_files") else None,
        "source_hash": metadata.get("source_hash"),
        "inferred_data_type": metadata.get("data_type"),
        "selected_processor": metadata.get("processor_name"),
        "processor_name": metadata.get("processor_name"),
        "triage_decision": triage.get("triage_decision"),
        "failure_stage": stage,
        "error_message": "; ".join(warnings) or metadata.get("processing_status", "failed"),
        "manual_fix_hint": _manual_fix_hint(stage, metadata.get("data_type")),
        "whether_retry_with_manual_override_is_possible": True,
    }


def _failure_from_exception(
    classification: dict,
    source: Path,
    exc: Exception,
    triage: dict | None = None,
    *,
    project_root: Path | None = None,
    output_root: Path | None = None,
) -> dict:
    from src.core.metadata import file_hash

    triage = triage or {}
    source_hash = file_hash(source) if source.exists() and source.is_file() else None
    return {
        "source_file": render_output_path(source, project_root=project_root, output_root=output_root),
        "source_hash": source_hash,
        "inferred_data_type": classification.get("inferred_data_type"),
        "selected_processor": classification.get("selected_processor"),
        "processor_name": classification.get("selected_processor"),
        "triage_decision": triage.get("triage_decision"),
        "failure_stage": _failure_stage(exc),
        "error_message": scrub_output_text(exc, project_root=project_root, output_root=output_root),
        "manual_fix_hint": _manual_fix_hint(_failure_stage(exc), classification.get("inferred_data_type")),
        "whether_retry_with_manual_override_is_possible": True,
    }


def _failure_stage(exc: Exception) -> str:
    text = str(exc).lower()
    if "read" in text or "decode" in text:
        return "read_table"
    if "origin" in text:
        return "origin_export"
    if "output already exists" in text:
        return "output_overwrite"
    return "processing"


def _manual_fix_hint(stage: str, data_type: str | None) -> str:
    if stage == "origin_export":
        return "Check Origin availability and rerun this dataset after no-Origin processing succeeds."
    if stage == "output_overwrite":
        return "Use --force only after confirming the existing output can be replaced."
    if stage == "read_table":
        return "Export the instrument table as CSV/TXT/XLSX with readable headers and at least two numeric columns."
    return f"Check required columns and units for {data_type or 'this data type'} in docs/REAL_DATA_INTAKE_GUIDE.md."


def _write_processing_failures(project_root: Path, failures: list[dict], *, output_root: Path | None = None) -> None:
    report_path(project_root, "processing_failures.json", output_root=output_root).write_text(
        json.dumps({"failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Processing Failures",
        "",
        f"Failure count: {len(failures)}",
        "",
        "| source_file | inferred_data_type | processor_name | failure_stage | error_message | manual_fix_hint |",
        "|---|---|---|---|---|---|",
    ]
    for failure in failures:
        lines.append(
            "| {source_file} | {inferred_data_type} | {processor_name} | {failure_stage} | {error_message} | {manual_fix_hint} |".format(
                **{key: _md_cell(value) for key, value in failure.items()}
            )
        )
    report_path(project_root, "processing_failures.md", output_root=output_root).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_processing_skipped_auxiliary(project_root: Path, skipped: list[dict], *, output_root: Path | None = None) -> None:
    report_path(project_root, "processing_skipped_auxiliary.json", output_root=output_root).write_text(
        json.dumps({"items": skipped}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Processing Skipped Auxiliary Sources",
        "",
        f"Skipped count: {len(skipped)}",
        "",
        "| source_file | inferred_data_type | selected_processor | skip_reason | handling |",
        "|---|---|---|---|---|",
    ]
    for item in skipped:
        lines.append(
            "| {source_file} | {inferred_data_type} | {selected_processor} | {skip_reason} | {handling} |".format(
                **{key: _md_cell(value) for key, value in item.items()}
            )
        )
    report_path(project_root, "processing_skipped_auxiliary.md", output_root=output_root).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_processing_summary(
    project_root: Path,
    manifest: dict,
    results: list[dict],
    failures: list[dict],
    *,
    skipped_auxiliary: list[dict] | None = None,
    output_root: Path | None = None,
) -> None:
    skipped_auxiliary = skipped_auxiliary or []
    type_stats: dict[str, dict[str, int]] = {}
    result_sources = set()
    for metadata in results:
        if metadata.get("source_files"):
            result_sources.add(metadata["source_files"][0])
        stats = type_stats.setdefault(metadata["data_type"], {"success": 0, "failure": 0})
        if metadata["processing_status"] in {"success", "processed_no_origin"}:
            stats["success"] += 1
        else:
            stats["failure"] += 1
    for failure in failures:
        if failure.get("source_file") in result_sources:
            continue
        dtype = str(failure.get("inferred_data_type") or "unknown")
        stats = type_stats.setdefault(dtype, {"success": 0, "failure": 0})
        stats["failure"] += 1
    deferred = [
        item for item in manifest["classifications"]
        if item["special_handling"] == "scan_only" and item["inferred_data_type"] != "reference_literature"
    ]
    reference = [item for item in manifest["classifications"] if item["inferred_data_type"] == "reference_literature"]
    missing_artifacts = []
    manual_checks = []
    forbidden_claims = []
    for metadata in results:
        if metadata["processing_status"] == "success":
            required_artifacts = ("origin_file", "figure_tif", "preview_png", "processed_data", "metadata_path")
        else:
            required_artifacts = ("processed_data", "metadata_path")
        missing = [
            name for name in required_artifacts
            if _artifact_missing(project_root, metadata, name, output_root=output_root)
        ]
        if missing:
            missing_artifacts.append({"dataset_id": metadata["dataset_id"], "missing": missing})
        if metadata.get("manual_check_required"):
            manual_checks.append(metadata["dataset_id"])
        forbidden_claims.append({"dataset_id": metadata["dataset_id"], "forbidden_claim_count": len(metadata.get("forbidden_claims", []))})
    exception_failures = [failure for failure in failures if failure.get("source_file") not in result_sources]
    failed_dataset_count = sum(
        1 for item in results if item["processing_status"] not in {"success", "processed_no_origin"}
    ) + len(exception_failures)
    summary = {
        "total_dataset_count": len(results) + len(exception_failures),
        "success_count": sum(1 for item in results if item["processing_status"] in {"success", "processed_no_origin"}),
        "failure_count": failed_dataset_count,
        "skipped_auxiliary_count": len(skipped_auxiliary),
        "deferred_count": sum(1 for item in deferred if item["physical_presence"] == "present"),
        "reference_literature_count": sum(1 for item in reference if item["physical_presence"] == "present"),
        "processor_stats": type_stats,
        "missing_artifacts": missing_artifacts,
        "manual_check_required": manual_checks,
        "forbidden_claims": forbidden_claims,
    }
    report_path(project_root, "processing_summary.json", output_root=output_root).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Processing Summary",
        "",
        f"- Total datasets: {summary['total_dataset_count']}",
        f"- Success count: {summary['success_count']}",
        f"- Failure count: {summary['failure_count']}",
        f"- Skipped auxiliary/reference source count: {summary['skipped_auxiliary_count']}",
        f"- Deferred present count: {summary['deferred_count']}",
        f"- Reference literature present count: {summary['reference_literature_count']}",
        "",
        "## Processor Stats",
    ]
    for dtype, stats in sorted(type_stats.items()):
        lines.append(f"- {dtype}: success {stats['success']}, failure {stats['failure']}")
    lines.extend(["", "## Missing Artifacts"])
    for item in missing_artifacts:
        lines.append(f"- {item['dataset_id']}: {', '.join(item['missing'])}")
    lines.extend(["", "## Manual Check Required"])
    for dataset_id in manual_checks:
        lines.append(f"- {dataset_id}")
    lines.extend(["", "## Skipped Auxiliary/Reference Sources"])
    for item in skipped_auxiliary:
        lines.append(f"- {item['source_file']}: {item['skip_reason']}")
    report_path(project_root, "processing_summary.md", output_root=output_root).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _artifact_missing(project_root: Path, metadata: dict, name: str, *, output_root: Path | None = None) -> bool:
    value = metadata.get(name)
    if value is None:
        return True
    path = Path(str(value))
    if not path.is_absolute():
        if path.parts and path.parts[0] == "output":
            base = output_root or default_output_root(project_root)
            if not base.is_absolute():
                base = project_root / base
            if is_under_or_equal(base.resolve(), project_root.resolve()):
                path = project_root / path
            else:
                if base.parent.name == "runs":
                    base = base.parent.parent
                path = base / Path(*path.parts[1:])
        else:
            path = project_root / path
    return not path.exists()


def _write_review_dashboard(project_root: Path, manifest: dict, results: list[dict], failures: list[dict], *, output_root: Path | None = None) -> None:
    summary = json.loads(report_path(project_root, "processing_summary.json", output_root=output_root).read_text(encoding="utf-8"))
    dashboard = output_dir(project_root, "review_dashboard", output_root=output_root)
    triage_manifest = _load_report_json(project_root, "data_triage_manifest.json", output_root=output_root)
    processing_queue = _load_report_json(project_root, "processing_queue.json", output_root=output_root)
    lines = [
        "# Review Dashboard",
        "",
        f"- Total datasets: {summary['total_dataset_count']}",
        f"- Success count: {summary['success_count']}",
        f"- Failure count: {summary['failure_count']}",
        f"- Skipped auxiliary/reference source count: {summary.get('skipped_auxiliary_count', 0)}",
        f"- Deferred present count: {summary['deferred_count']}",
        f"- Reference literature present count: {summary['reference_literature_count']}",
    ]
    if triage_manifest or processing_queue:
        lines.extend(["", "## Triage Summary"])
        if triage_manifest:
            triage_summary = triage_manifest.get("summary", {})
            lines.append(f"- Total files: {triage_summary.get('total_files', 0)}")
            for decision, count in triage_summary.get("decision_counts", {}).items():
                lines.append(f"- {decision}: {count}")
        if processing_queue:
            lines.append(f"- Queue items: {len(processing_queue.get('items', []))}")
    lines.extend(["", "## Processor Success/Failure"])
    for dtype, stats in sorted(summary["processor_stats"].items()):
        lines.append(f"- {dtype}: success {stats['success']}, failure {stats['failure']}")
    lines.extend(["", "## Missing Artifacts"])
    for item in summary["missing_artifacts"]:
        lines.append(f"- {item['dataset_id']}: {', '.join(item['missing'])}")
    lines.extend(["", "## Manual Check Required"])
    for dataset_id in summary["manual_check_required"]:
        lines.append(f"- {dataset_id}")
    lines.extend(["", "## Forbidden Claims Check"])
    for item in summary["forbidden_claims"]:
        lines.append(f"- {item['dataset_id']}: {item['forbidden_claim_count']} forbidden claims recorded")
    related_reports = (
        ("Current filtered manual-review workbook", "manual_review_required_filtered.xlsx"),
        ("AUTO_PROCESS dry-run plan", "auto_process_plan.md"),
    )
    available_reports = [
        (label, name)
        for label, name in related_reports
        if report_path(project_root, name, output_root=output_root).is_file()
    ]
    if available_reports:
        lines.extend(["", "## Related Review Artifacts"])
        lines.extend(f"- [{label}](../reports/{name})" for label, name in available_reports)
    (dashboard / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_report_json(project_root: Path, name: str, *, output_root: Path | None = None) -> dict:
    path = report_path(project_root, name, output_root=output_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
