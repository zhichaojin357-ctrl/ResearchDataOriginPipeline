from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.file_utils import file_sha256 as _file_sha256
from src.core.file_utils import is_under_or_equal as _is_under_or_equal
from src.core.output_sanitizer import scrub_output_text
from src.core.project import default_output_root
from src.core.runtime_paths import (
    resolve_optional_f_drive_backup,
    resolve_output_root,
    resolve_locked_result_package,
    resolve_workspace_root,
)


@dataclass(frozen=True)
class ReadinessOptions:
    expected_locked_result_count: int = 167
    workspace_root: Path | None = None
    f_drive_backup: Path | None = None
    locked_result_package: Path | None = None
    strict_artifacts: bool = False
    check_legacy_project_path: bool = True
    desktop_review_xlsx: Path | None = None
    report_json: Path | None = None
    report_md: Path | None = None


def run_readiness(project_root: Path, options: ReadinessOptions) -> int:
    report = build_readiness_report(project_root, options)
    _write_readiness_report(project_root, report, options)
    return 1 if report["summary"]["failures"] else 0


def build_readiness_report(project_root: Path, options: ReadinessOptions) -> dict:
    checks: list[dict] = []
    workspace_root = resolve_workspace_root(project_root, options.workspace_root)
    f_drive_backup = resolve_optional_f_drive_backup(project_root, options.f_drive_backup)
    output_root = resolve_output_root(project_root)
    reports = output_root / "reports"
    package = resolve_locked_result_package(project_root, options.locked_result_package)

    _add_artifact_check(
        checks,
        "workspace_copy_exists",
        workspace_root.exists() and workspace_root.is_dir(),
        str(workspace_root),
        options,
        artifacts_present=workspace_root.exists(),
    )
    if f_drive_backup is not None:
        _add_artifact_check(
            checks,
            "f_drive_backup_exists",
            f_drive_backup.exists() and f_drive_backup.is_dir(),
            str(f_drive_backup),
            options,
            artifacts_present=f_drive_backup.exists(),
        )
    if options.check_legacy_project_path:
        old_project = project_root.parent / "GroupMeetingAutoPPT"
        _add_check(checks, "old_project_path_absent", not old_project.exists(), str(old_project))
    active_docs_ok, active_docs_detail, active_docs_generated_only = _active_project_name_status(project_root)
    _add_check(
        checks,
        "active_project_name_references_current",
        active_docs_ok,
        active_docs_detail,
        fail_status="warning" if active_docs_generated_only and not options.strict_artifacts else "fail",
    )

    index = package / "index.csv"
    index_rows = _csv_row_count(index)
    _add_artifact_check(
        checks,
        "locked_result_index_count",
        index_rows == options.expected_locked_result_count,
        f"{index_rows}/{options.expected_locked_result_count} rows in {index}",
        options,
        artifacts_present=index.is_file(),
    )
    result_summary = package / "result_summary.json"
    _add_artifact_check(
        checks,
        "locked_result_result_summary_exists",
        result_summary.is_file(),
        str(result_summary),
        options,
        artifacts_present=result_summary.exists(),
    )
    summary_ok, summary_detail = _locked_result_summary_status(index, result_summary, options.expected_locked_result_count)
    _add_artifact_check(
        checks,
        "locked_result_result_summary_matches_index",
        summary_ok,
        summary_detail,
        options,
        artifacts_present=index.exists() or result_summary.exists(),
    )

    manual_csv = reports / "manual_review_required_filtered.csv"
    manual_xlsx = reports / "manual_review_required_filtered.xlsx"
    manual_report = reports / "manual_review_required_filtered_report.md"
    _add_artifact_check(
        checks,
        "manual_review_filtered_csv_exists",
        manual_csv.is_file() and manual_csv.stat().st_size > 0,
        str(manual_csv),
        options,
        artifacts_present=manual_csv.exists(),
    )
    _add_artifact_check(
        checks,
        "manual_review_filtered_xlsx_exists",
        manual_xlsx.is_file() and manual_xlsx.stat().st_size > 0,
        str(manual_xlsx),
        options,
        artifacts_present=manual_xlsx.exists(),
    )
    _add_artifact_check(
        checks,
        "manual_review_filtered_report_exists",
        manual_report.is_file() and manual_report.stat().st_size > 0,
        str(manual_report),
        options,
        artifacts_present=manual_report.exists(),
    )
    manual_consistent_ok, manual_consistent_detail = _manual_review_status(manual_csv, manual_xlsx, manual_report)
    _add_artifact_check(
        checks,
        "manual_review_outputs_consistent",
        manual_consistent_ok,
        manual_consistent_detail,
        options,
        artifacts_present=manual_csv.exists() or manual_xlsx.exists() or manual_report.exists(),
    )
    if options.desktop_review_xlsx is not None:
        desktop_xlsx = _resolve_path(project_root, options.desktop_review_xlsx)
        desktop_ok, desktop_detail = _matching_file_status(manual_xlsx, desktop_xlsx)
        _add_check(checks, "manual_review_desktop_xlsx_matches", desktop_ok, desktop_detail)

    auto_plan = reports / "auto_process_plan.json"
    auto_queue = reports / "auto_process_queue.json"
    auto_summary = _json_summary(auto_plan)
    _add_artifact_check(checks, "auto_queue_plan_exists", auto_plan.is_file(), str(auto_plan), options, artifacts_present=auto_plan.exists())
    _add_artifact_check(checks, "auto_queue_file_exists", auto_queue.is_file(), str(auto_queue), options, artifacts_present=auto_queue.exists())
    _add_artifact_check(
        checks,
        "auto_queue_dry_run_flags",
        auto_summary.get("will_run_process") is False and auto_summary.get("will_launch_origin") is False,
        f"will_run_process={auto_summary.get('will_run_process')}; will_launch_origin={auto_summary.get('will_launch_origin')}",
        options,
        artifacts_present=auto_plan.is_file(),
    )
    auto_consistent_ok, auto_consistent_detail = _auto_queue_status(auto_plan, auto_queue)
    _add_artifact_check(
        checks,
        "auto_queue_plan_queue_consistent",
        auto_consistent_ok,
        auto_consistent_detail,
        options,
        artifacts_present=auto_plan.exists() or auto_queue.exists(),
    )

    reviewed_proposals = reports / "override_proposals_after_triage_optimization.json"
    reviewed_decisions = reports / "review_decisions_template.csv"
    reviewed_plan = reports / "reviewed_queue_plan.json"
    reviewed_ok, reviewed_detail = _reviewed_queue_status(reviewed_proposals, reviewed_decisions, reviewed_plan)
    _add_artifact_check(
        checks,
        "reviewed_queue_plan_current",
        reviewed_ok,
        reviewed_detail,
        options,
        artifacts_present=reviewed_proposals.exists() or reviewed_decisions.exists() or reviewed_plan.exists(),
    )

    origin_batch_plan = reports / "origin_batch_plan.json"
    origin_batch_ok, origin_batch_detail = _origin_batch_plan_status(origin_batch_plan, options.expected_locked_result_count)
    _add_artifact_check(
        checks,
        "origin_batch_dry_run_plan_current",
        origin_batch_ok,
        origin_batch_detail,
        options,
        artifacts_present=origin_batch_plan.is_file(),
    )

    validation_report = reports / "validation_report.md"
    validation_ok, validation_detail = _validation_report_status(project_root, validation_report)
    _add_check(checks, "validation_report_current", validation_ok, validation_detail)

    stale_summary_terms = [
        "Post-rule/post-AI manual review CSV",
        "Manual review rows after AI-assisted recognition",
        "Remaining user action: review `manual_review_required_after_ai.csv`",
    ]
    final_summaries = [reports / "review_queue_final_summary.md"]
    missing_summaries = [path for path in final_summaries if not path.is_file()]
    stale_summaries = [path for path in final_summaries if path.is_file() and _contains_any(path, stale_summary_terms)]
    summary_ok = not missing_summaries and not stale_summaries
    summary_detail_parts = []
    if missing_summaries:
        summary_detail_parts.append("missing: " + "; ".join(str(path) for path in missing_summaries))
    if stale_summaries:
        summary_detail_parts.append("stale: " + "; ".join(str(path) for path in stale_summaries))
    if not summary_detail_parts:
        summary_detail_parts.append("; ".join(str(path) for path in final_summaries))
    _add_check(
        checks,
        "reviewed_queue_summary_current",
        summary_ok,
        "; ".join(summary_detail_parts),
        fail_status="fail" if options.strict_artifacts or stale_summaries else "warning",
    )

    dashboard_path = output_root / "review_dashboard" / "index.md"
    dashboard_ok, dashboard_detail = _dashboard_status(dashboard_path, stale_summary_terms)
    _add_artifact_check(
        checks,
        "review_dashboard_current",
        dashboard_ok,
        dashboard_detail,
        options,
        artifacts_present=dashboard_path.exists(),
    )

    forbidden_paths = [
        project_root / "src" / "ppt",
        project_root / "templates" / "ppt",
        project_root / "ppt_layout.yaml",
        project_root / "slide_plan.json",
        project_root / "presentation.pptx",
    ]
    found_forbidden = [path for path in forbidden_paths if path.exists()]
    _add_check(checks, "ppt_forbidden_paths_absent", not found_forbidden, ", ".join(str(path) for path in found_forbidden) or "none")

    failures = sum(1 for check in checks if check["status"] == "fail")
    warnings = sum(1 for check in checks if check["status"] == "warning")
    report = {
        "report": "readiness",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "checks": len(checks),
            "failures": failures,
            "warnings": warnings,
            "ready": failures == 0,
        },
        "checks": checks,
    }
    _sanitize_check_details(project_root, report)
    return report


def _sanitize_check_details(project_root: Path, report: dict) -> None:
    parent = project_root.parent
    roots = [project_root, parent]
    for check in report.get("checks", []):
        detail = str(check.get("detail", "")).replace("\\", "/")
        for root in roots:
            root_text = str(root).replace("\\", "/").rstrip("/")
            if root_text:
                detail = detail.replace(root_text + "/", "")
                detail = detail.replace(root_text, ".")
        check["detail"] = scrub_output_text(detail, project_root=project_root)


def _write_readiness_report(project_root: Path, report: dict, options: ReadinessOptions) -> None:
    reports = resolve_output_root(project_root) / "reports"
    json_path = _resolve_output(project_root, options.report_json or reports / "readiness_report.json")
    md_path = _resolve_output(project_root, options.report_md or reports / "readiness_report.md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_readiness_markdown(report), encoding="utf-8")


def _readiness_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# Readiness Report",
        "",
        f"- Created at: {report['created_at']}",
        f"- Checks: {summary['checks']}",
        f"- Failures: {summary['failures']}",
        f"- Warnings: {summary['warnings']}",
        f"- Ready: {str(summary['ready']).lower()}",
        "",
        "| check | status | detail |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['name']} | {check['status']} | {check['detail']} |")
    return "\n".join(lines) + "\n"


def _add_check(checks: list[dict], name: str, passed: bool, detail: str, *, fail_status: str = "fail") -> None:
    checks.append({"name": name, "status": "pass" if passed else fail_status, "detail": detail})


def _add_artifact_check(
    checks: list[dict],
    name: str,
    passed: bool,
    detail: str,
    options: ReadinessOptions,
    *,
    artifacts_present: bool,
) -> None:
    fail_status = "fail" if options.strict_artifacts or artifacts_present else "warning"
    _add_check(checks, name, passed, detail, fail_status=fail_status)


def _csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _json_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("summary", {}) if isinstance(payload, dict) else {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _locked_result_summary_status(index_path: Path, summary_path: Path, expected_count: int) -> tuple[bool, str]:
    if not index_path.is_file() or not summary_path.is_file():
        return False, f"missing index or summary: {index_path}; {summary_path}"
    try:
        index_rows = _csv_row_count(index_path)
        summary = _load_json(summary_path)
    except Exception as exc:
        return False, f"failed to read locked result package summary/index: {exc}"
    total_results = summary.get("total_results")
    by_type = summary.get("by_type")
    if total_results != index_rows or index_rows != expected_count:
        return False, f"index_rows={index_rows}; total_results={total_results}; expected={expected_count}"
    if not isinstance(by_type, dict) or not by_type:
        return False, f"missing by_type summary in {summary_path}"
    try:
        by_type_sum = sum(int(value) for value in by_type.values())
    except Exception as exc:
        return False, f"invalid by_type values in {summary_path}: {exc}"
    if by_type_sum != total_results:
        return False, f"index_rows={index_rows}; total_results={total_results}; by_type_sum={by_type_sum}"
    return True, f"index_rows={index_rows}; total_results={total_results}; by_type_sum={by_type_sum}"


def _contains_any(path: Path, patterns: list[str]) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf-8")
    return any(pattern in text for pattern in patterns)


def _validation_report_status(project_root: Path, path: Path) -> tuple[bool, str]:
    if not path.is_file() or path.stat().st_size == 0:
        return False, f"missing or empty: {path}"
    text = path.read_text(encoding="utf-8")
    failure_markers = [
        "\n## Failures",
        "\n# Failures",
        "Deferred/reference registry semantics: fail",
        "PPT forbidden paths: fail",
        "Kinetics processor paths: fail",
    ]
    if any(marker in text for marker in failure_markers):
        return False, f"validation report contains failure markers: {path}"
    required_markers = [
        "Deferred/reference registry semantics: pass",
        "PPT forbidden paths: pass",
        "Kinetics processor paths: pass",
    ]
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        return False, f"validation report missing required pass markers: {', '.join(missing)}"
    stale_inputs = _validation_inputs_newer_than_report(project_root, path)
    if stale_inputs:
        rendered = ", ".join(str(item.relative_to(project_root)) for item in stale_inputs[:5])
        return False, f"validation report older than validation inputs: {rendered}"
    return True, str(path)


def _validation_inputs_newer_than_report(project_root: Path, report: Path) -> list[Path]:
    report_mtime = report.stat().st_mtime
    candidates = [
        project_root / "src" / "core" / "validate.py",
        project_root / "src" / "core" / "deps.py",
        project_root / "src" / "core" / "project.py",
        project_root / "src" / "origin" / "adapter.py",
        project_root / "config" / "default.yaml",
        project_root / "config" / "processor_registry.yaml",
        project_root / "config" / "claim_policy.yaml",
        project_root / "config" / "plot_style.yaml",
        project_root / "config" / "sample_registry.yaml",
        project_root / "config" / "manual_overrides.yaml",
    ]
    return [path for path in candidates if path.is_file() and path.stat().st_mtime > report_mtime + 1e-6]


def _active_project_name_status(project_root: Path) -> tuple[bool, str, bool]:
    active_docs = [
        project_root / "README.md",
        project_root / "PROJECT_STATUS.md",
        project_root / "TASK_BOARD.md",
        project_root / "AGENT_HANDOFF.md",
        project_root / "docs" / "REAL_DATA_INTAKE_GUIDE.md",
        project_root / "docs" / "REAL_DATA_COMPATIBILITY_MATRIX.md",
        resolve_output_root(project_root) / "review_dashboard" / "index.md",
    ]
    stale_patterns = [
        "GroupMeetingAutoPPT",
    ]
    stale_hits: list[str] = []
    missing_active_docs: list[str] = []
    for path in active_docs:
        if not path.exists():
            missing_active_docs.append(str(path))
            continue
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in stale_patterns):
            stale_hits.append(str(path))
    if stale_hits:
        return False, "stale old project references in active docs: " + "; ".join(stale_hits), False
    if missing_active_docs:
        output_root = resolve_output_root(project_root).resolve()
        generated_only = all(
            _is_under_or_equal(Path(path).resolve(), output_root)
            for path in missing_active_docs
        )
        return False, "missing active entry docs: " + "; ".join(missing_active_docs), generated_only
    return True, "no stale old project references in active docs", False


def _manual_review_status(csv_path: Path, xlsx_path: Path, report_path: Path) -> tuple[bool, str]:
    if not csv_path.is_file() or not xlsx_path.is_file() or not report_path.is_file():
        return False, f"missing manual review output: {csv_path}; {xlsx_path}; {report_path}"
    try:
        csv_rows = _csv_row_count(csv_path)
        xlsx_rows = _xlsx_review_row_count(xlsx_path)
        report_rows = _manual_review_report_row_count(report_path)
    except Exception as exc:
        return False, f"manual review output parse failed: {exc}"
    if report_rows is None:
        return False, f"could not find manual review row count in {report_path}"
    if csv_rows != xlsx_rows or csv_rows != report_rows:
        return False, f"csv_rows={csv_rows}; xlsx_review_rows={xlsx_rows}; report_rows={report_rows}"
    return True, f"csv_rows={csv_rows}; xlsx_review_rows={xlsx_rows}; report_rows={report_rows}"


def _xlsx_review_row_count(path: Path) -> int:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["Review"] if "Review" in workbook.sheetnames else workbook.active
    rows = 0
    for index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if index == 1:
            continue
        if any(value is not None and str(value).strip() for value in row):
            rows += 1
    workbook.close()
    return rows


def _manual_review_report_row_count(path: Path) -> int | None:
    import re

    text = path.read_text(encoding="utf-8")
    patterns = [
        r"仍需人工复核[:：]\s*(\d+)",
        r"Rows requiring user review[:：]\s*(\d+)",
        r"Still requiring user review(?: in the workbook)?[:：]\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _auto_queue_status(plan_path: Path, queue_path: Path) -> tuple[bool, str]:
    if not plan_path.is_file() or not queue_path.is_file():
        return False, f"missing plan or queue: {plan_path}; {queue_path}"
    plan = _load_json(plan_path)
    queue = _load_json(queue_path)
    summary = plan.get("summary", {}) if isinstance(plan.get("summary", {}), dict) else {}
    items = queue.get("items", [])
    if not isinstance(items, list):
        return False, f"queue items is not a list: {queue_path}"
    accepted_count = summary.get("accepted_count")
    blocked_count = summary.get("blocked_count", 0)
    if accepted_count != len(items):
        return False, f"accepted_count={accepted_count}; queue_items={len(items)}"
    if blocked_count not in (0, None):
        return False, f"blocked_count={blocked_count}; inspect {plan_path}"
    plan_queue_items = plan.get("queue", {}).get("items", []) if isinstance(plan.get("queue", {}), dict) else []
    if isinstance(plan_queue_items, list) and plan_queue_items:
        plan_identity = [_queue_identity(item) for item in plan_queue_items]
        queue_identity = [_queue_identity(item) for item in items]
        if plan_identity != queue_identity:
            return False, "auto queue items differ from embedded plan queue"
    origin_allowed = [item.get("queue_id") or item.get("relative_path") for item in items if item.get("origin_export_allowed") is True]
    if origin_allowed:
        return False, f"auto queue contains Origin-allowed items: {origin_allowed[:5]}"
    manual_check_missing = [item.get("queue_id") or item.get("relative_path") for item in items if item.get("manual_check_required") is not True]
    if manual_check_missing:
        return False, f"auto queue items missing manual_check_required=true: {manual_check_missing[:5]}"
    provenance_mismatch = [
        item.get("queue_id") or item.get("relative_path")
        for item in items
        if item.get("promoted_by_workflow") != "auto_queue_dry_run"
    ]
    if provenance_mismatch:
        return False, f"auto queue items missing auto_queue_dry_run provenance: {provenance_mismatch[:5]}"
    note_missing = [
        item.get("queue_id") or item.get("relative_path")
        for item in items
        if "no processing has been run by auto-queue" not in str(item.get("queue_note", ""))
    ]
    if note_missing:
        return False, f"auto queue items missing dry-run no-processing note: {note_missing[:5]}"
    return True, (
        f"accepted_count={accepted_count}; queue_items={len(items)}; "
        "identity=match; origin_export_allowed=true count=0; dry_run_provenance=true"
    )


def _queue_identity(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("queue_id", "")),
        str(item.get("relative_path", "")).replace("\\", "/"),
        str(item.get("source_hash", "")),
    )


def _reviewed_queue_status(proposals_path: Path, decisions_path: Path, plan_path: Path) -> tuple[bool, str]:
    if not proposals_path.is_file() or not decisions_path.is_file() or not plan_path.is_file():
        return False, f"missing reviewed-queue artifact: {proposals_path}; {decisions_path}; {plan_path}"
    try:
        proposals = _load_json(proposals_path)
        proposal_items = proposals.get("items", [])
        if not isinstance(proposal_items, list):
            return False, f"proposal items is not a list: {proposals_path}"
        decision_rows = _csv_row_count(decisions_path)
        plan = _load_json(plan_path)
        summary = plan.get("summary", {}) if isinstance(plan.get("summary", {}), dict) else {}
    except Exception as exc:
        return False, f"reviewed-queue parse failed: {exc}"
    total_proposals = summary.get("total_proposals")
    plan_decision_rows = summary.get("decision_rows")
    approved_count = summary.get("approved_count")
    skipped_count = summary.get("skipped_count")
    blocked_count = summary.get("blocked_count")
    queue_item_count = summary.get("queue_item_count")
    if total_proposals != len(proposal_items):
        return False, f"total_proposals={total_proposals}; proposal_items={len(proposal_items)}"
    if plan_decision_rows != decision_rows or decision_rows != len(proposal_items):
        return False, f"plan_decision_rows={plan_decision_rows}; decision_rows={decision_rows}; proposal_items={len(proposal_items)}"
    if summary.get("will_launch_origin") is not False or summary.get("will_run_process") is not False:
        return False, f"will_launch_origin={summary.get('will_launch_origin')}; will_run_process={summary.get('will_run_process')}"
    if queue_item_count != approved_count:
        return False, f"queue_item_count={queue_item_count}; approved_count={approved_count}"
    if not all(isinstance(value, int) for value in (approved_count, skipped_count, blocked_count)):
        return False, f"invalid reviewed-queue summary counts: {summary}"
    if approved_count + skipped_count + blocked_count != total_proposals:
        return False, (
            f"approved+skipped+blocked={approved_count + skipped_count + blocked_count}; "
            f"total_proposals={total_proposals}"
        )
    if blocked_count:
        return False, f"blocked_count={blocked_count}; inspect {plan_path}"
    input_hashes = plan.get("input_hashes")
    if not isinstance(input_hashes, dict):
        return False, f"reviewed-queue plan missing input_hashes: {plan_path}"
    expected_hashes = {
        "proposals_sha256": _file_sha256(proposals_path),
        "decisions_sha256": _file_sha256(decisions_path),
    }
    hash_mismatches = [
        f"{key}: plan={input_hashes.get(key)} actual={actual}"
        for key, actual in expected_hashes.items()
        if input_hashes.get(key) != actual
    ]
    if hash_mismatches:
        return False, "reviewed-queue input hash mismatch: " + "; ".join(hash_mismatches)
    latest_input_mtime = max(proposals_path.stat().st_mtime, decisions_path.stat().st_mtime)
    if plan_path.stat().st_mtime + 1e-6 < latest_input_mtime:
        return False, f"reviewed-queue plan is older than proposals or decisions: {plan_path}"
    return True, (
        f"proposals={len(proposal_items)}; decision_rows={decision_rows}; "
        f"approved={approved_count}; blocked={blocked_count}; input_hashes=match; "
        f"will_launch_origin=false; will_run_process=false"
    )


def _origin_batch_plan_status(plan_path: Path, expected_count: int) -> tuple[bool, str]:
    if not plan_path.is_file() or plan_path.stat().st_size == 0:
        return False, f"missing or empty origin-batch plan: {plan_path}"
    try:
        plan = _load_json(plan_path)
        summary = plan.get("summary", {}) if isinstance(plan.get("summary", {}), dict) else {}
        execution = plan.get("execution", {}) if isinstance(plan.get("execution", {}), dict) else {}
    except Exception as exc:
        return False, f"origin-batch plan parse failed: {exc}"
    total = summary.get("total_manifest_items")
    planned = summary.get("planned_count")
    skipped = summary.get("skipped_count")
    blocked = summary.get("blocked_count")
    will_launch_origin = summary.get("will_launch_origin")
    execution_origin_launch = execution.get("origin_launch")
    execution_blocked = execution.get("blocked")
    if total != expected_count:
        return False, f"total_manifest_items={total}; expected={expected_count}"
    if planned != 0 or skipped != expected_count or blocked != 0:
        return False, f"planned={planned}; skipped={skipped}; blocked={blocked}; expected_skipped={expected_count}"
    if will_launch_origin is not False or execution_origin_launch is not False:
        return False, f"will_launch_origin={will_launch_origin}; execution.origin_launch={execution_origin_launch}"
    if execution_blocked is not False:
        return False, f"execution.blocked={execution_blocked}; inspect {plan_path}"
    return True, (
        f"total={total}; planned=0; skipped={skipped}; blocked=0; "
        "will_launch_origin=false; execution.origin_launch=false"
    )


def _dashboard_status(path: Path, stale_terms: list[str]) -> tuple[bool, str]:
    if not path.is_file() or path.stat().st_size == 0:
        return False, f"missing or empty: {path}"
    text = path.read_text(encoding="utf-8")
    required_terms = [
        "manual_review_required_filtered.xlsx",
        "auto_process_plan.md",
    ]
    missing = [term for term in required_terms if term not in text]
    stale = [term for term in stale_terms + ["manual_review_required_after_ai.csv"] if term in text]
    if missing:
        return False, f"dashboard missing current links: {', '.join(missing)}"
    if stale:
        return False, f"dashboard contains stale guidance: {', '.join(stale)}"
    return True, str(path)


def _matching_file_status(source: Path, copy: Path) -> tuple[bool, str]:
    if not source.is_file() or source.stat().st_size == 0:
        return False, f"source missing or empty: {source}"
    if not copy.is_file() or copy.stat().st_size == 0:
        return False, f"copy missing or empty: {copy}"
    source_hash = _file_sha256(source)
    copy_hash = _file_sha256(copy)
    if source_hash != copy_hash:
        return False, f"hash mismatch: source={source_hash}; copy={copy_hash}; copy={copy}"
    return True, f"{copy} matches {source.name} ({source_hash})"


def _resolve_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def _resolve_output(project_root: Path, path: Path) -> Path:
    output_root = resolve_output_root(project_root).resolve()
    resolved = path if path.is_absolute() else output_root / path
    if not _is_under_or_equal(resolved.resolve(), output_root):
        raise ValueError(f"Output path must stay under configured output root: {resolved}")
    return resolved
