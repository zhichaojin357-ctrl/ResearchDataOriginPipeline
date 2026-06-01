from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.metadata import file_hash
from src.core.runtime_paths import resolve_phase1_6_index, resolve_workspace_root


FORBIDDEN_TYPES = {
    "SEM",
    "TEM",
    "NMR",
    "MS",
    "SEM_image_data",
    "TEM_image_data",
    "reference_literature",
    "kinetics",
    "动力学",
}
FORBIDDEN_TYPE_TOKENS = {
    "sem",
    "tem",
    "nmr",
    "ms",
    "sem-image-data",
    "tem-image-data",
    "reference-literature",
    "kinetics",
    "动力学",
}


@dataclass(frozen=True)
class AutoQueueOptions:
    queue: Path = Path("output/reports/processing_queue.json")
    workspace_root: Path | None = None
    processed_index: Path | None = None
    report_json: Path | None = None
    report_md: Path | None = None
    queue_out: Path | None = None
    only_type: str | None = None


def run_auto_queue(project_root: Path, options: AutoQueueOptions) -> int:
    plan = plan_auto_queue(project_root, options)
    write_auto_queue_outputs(project_root, plan, options)
    return 0


def plan_auto_queue(project_root: Path, options: AutoQueueOptions) -> dict:
    queue_path = _resolve_existing(project_root, options.queue)
    workspace_root = resolve_workspace_root(project_root, options.workspace_root)
    processed_index = resolve_phase1_6_index(project_root, options.processed_index)
    processed_hashes = _phase1_6_hashes(processed_index)
    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(queue_payload, dict):
        raise ValueError(f"auto-queue JSON must be an object with an items list: {queue_path}")
    queue_items = queue_payload.get("items", [])
    if not isinstance(queue_items, list):
        raise ValueError(f"auto-queue JSON items must be a list: {queue_path}")
    for index, item in enumerate(queue_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"auto-queue JSON item {index} must be an object: {queue_path}")

    accepted: list[dict] = []
    skipped: list[dict] = []
    blocked: list[dict] = []
    seen_hashes: set[str] = set()

    for item in queue_items:
        base = _base_item(item)
        if item.get("decision") != "AUTO_PROCESS":
            skipped.append({**base, "status": "SKIPPED_NOT_AUTO_PROCESS", "reason": str(item.get("decision", ""))})
            continue
        if options.only_type and _normalize(item.get("data_type")) != _normalize(options.only_type):
            skipped.append({**base, "status": "SKIPPED_TYPE_FILTER", "reason": f"only_type={options.only_type}"})
            continue
        data_type = str(item.get("data_type", ""))
        if _is_forbidden_type(data_type):
            blocked.append({**base, "status": "BLOCKED_FORBIDDEN_TYPE", "reason": data_type})
            continue
        source_hash = str(item.get("source_hash", "")).strip()
        if not source_hash:
            blocked.append({**base, "status": "BLOCKED_MISSING_HASH", "reason": "source_hash_missing"})
            continue
        if source_hash in processed_hashes:
            skipped.append({**base, "status": "SKIPPED_PHASE1_6_ALREADY_PROCESSED", "reason": "source_hash_in_phase1_6"})
            continue
        if source_hash in seen_hashes:
            skipped.append({**base, "status": "SKIPPED_DUPLICATE_IN_QUEUE", "reason": "duplicate_source_hash_in_current_queue"})
            continue
        source_path, path_error = _resolve_source(workspace_root, item)
        if path_error:
            blocked.append({**base, **path_error})
            continue
        if not source_path.exists() or not source_path.is_file():
            blocked.append({**base, "status": "BLOCKED_SOURCE_MISSING", "reason": "workspace_source_missing"})
            continue
        actual_hash = file_hash(source_path)
        if actual_hash != source_hash:
            blocked.append(
                {
                    **base,
                    "status": "BLOCKED_HASH_MISMATCH",
                    "reason": "source_hash_changed",
                    "expected_hash": source_hash,
                    "actual_hash": actual_hash,
                }
            )
            continue
        seen_hashes.add(source_hash)
        accepted.append(_queue_item(item))

    summary = {
        "source_queue_items": len(queue_items),
        "accepted_count": len(accepted),
        "skipped_count": len(skipped),
        "blocked_count": len(blocked),
        "phase1_6_hashes": len(processed_hashes),
        "will_run_process": False,
        "will_launch_origin": False,
    }
    return {
        "runner": "auto-queue",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_queue": str(queue_path),
        "workspace_root": str(workspace_root),
        "processed_index": str(processed_index),
        "options": {"dry_run": True, "only_type": options.only_type},
        "summary": summary,
        "queue": {"queue_version": "1.0", "created_at": datetime.now().isoformat(timespec="seconds"), "items": accepted},
        "accepted_items": accepted,
        "skipped_items": skipped,
        "blocked_items": blocked,
    }


def write_auto_queue_outputs(project_root: Path, plan: dict, options: AutoQueueOptions) -> tuple[Path, Path, Path]:
    reports = project_root / "output" / "reports"
    json_path = _resolve_output(project_root, options.report_json or reports / "phase1_8_new_auto_process_plan.json")
    md_path = _resolve_output(project_root, options.report_md or reports / "phase1_8_new_auto_process_plan.md")
    queue_path = _resolve_output(project_root, options.queue_out or reports / "phase1_8_new_auto_process_queue.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(plan, queue_path), encoding="utf-8")
    queue_path.write_text(json.dumps(plan["queue"], ensure_ascii=False, indent=2), encoding="utf-8")
    agent_report = project_root / "docs" / "agent_reports" / "phase1_8_new_auto_process_queue_report.md"
    agent_report.parent.mkdir(parents=True, exist_ok=True)
    agent_report.write_text(_markdown(plan, queue_path), encoding="utf-8")
    return json_path, md_path, queue_path


def _queue_item(item: dict) -> dict:
    output = dict(item)
    output["origin_export_allowed"] = False
    output["manual_check_required"] = True
    output["promoted_by_phase"] = output.get("promoted_by_phase") or "phase1_8_auto_queue_dry_run"
    output["queue_note"] = "New AUTO_PROCESS candidate not represented in Phase 1.6; no processing has been run by auto-queue."
    return output


def _base_item(item: dict) -> dict:
    return {
        "queue_id": str(item.get("queue_id", "")),
        "relative_path": str(item.get("relative_path", "")),
        "source_hash": str(item.get("source_hash", "")),
        "data_type": str(item.get("data_type", "")),
    }


def _resolve_source(workspace_root: Path, item: dict) -> tuple[Path, dict | None]:
    relative = Path(str(item.get("relative_path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        return workspace_root / relative, {"status": "BLOCKED_PATH_TRAVERSAL", "reason": "relative_path_not_safe"}
    candidate = (workspace_root / relative).resolve()
    if not _is_under_or_equal(candidate, workspace_root.resolve()):
        return candidate, {"status": "BLOCKED_PATH_TRAVERSAL", "reason": "resolved_outside_workspace"}
    return candidate, None


def _phase1_6_hashes(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    import csv

    hashes: set[str] = set()
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source_hash = str(row.get("source_hash", "")).strip()
            if source_hash:
                hashes.add(source_hash)
    return hashes


def _resolve_existing(project_root: Path, path: Path) -> Path:
    resolved = _resolve_path(project_root, path)
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    return resolved


def _resolve_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def _resolve_output(project_root: Path, path: Path) -> Path:
    resolved = _resolve_path(project_root, path)
    allowed = [project_root / "output", project_root / "docs"]
    if not any(_is_under_or_equal(resolved.resolve(), base.resolve()) for base in allowed):
        raise ValueError(f"Output path must stay under output/ or docs/: {resolved}")
    return resolved


def _is_under_or_equal(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return path == parent


def _normalize(value: object) -> str:
    return str(value or "").casefold().replace("_", "-").strip()


def _is_forbidden_type(data_type: object) -> bool:
    normalized = _normalize(data_type)
    if normalized in {_normalize(value) for value in FORBIDDEN_TYPES}:
        return True
    tokens = [
        token.strip()
        for part in normalized.replace("\\", "/").replace("|", "/").replace(",", "/").replace(";", "/").split("/")
        for token in (part,)
        if token.strip()
    ]
    return any(token in FORBIDDEN_TYPE_TOKENS for token in tokens)


def _markdown(plan: dict, queue_path: Path) -> str:
    summary = plan["summary"]
    lines = [
        "# Phase 1.8 New AUTO_PROCESS Queue Plan",
        "",
        f"- Created at: {plan['created_at']}",
        f"- Source queue: `{plan['source_queue']}`",
        f"- Candidate queue: `{queue_path}`",
        f"- Source queue items: {summary['source_queue_items']}",
        f"- Accepted new candidates: {summary['accepted_count']}",
        f"- Skipped: {summary['skipped_count']}",
        f"- Blocked: {summary['blocked_count']}",
        f"- Phase 1.6 processed hashes: {summary['phase1_6_hashes']}",
        "- Will run process: false",
        "- Will launch Origin: false",
        "",
        "## Accepted By Type",
        "",
        "| data_type | count |",
        "|---|---:|",
    ]
    from collections import Counter

    for data_type, count in Counter(item.get("data_type", "") for item in plan["accepted_items"]).most_common():
        lines.append(f"| {data_type} | {count} |")
    lines += ["", "## Skipped / Blocked Reasons", "", "| status | count |", "|---|---:|"]
    for status, count in Counter(item.get("status", "") for item in [*plan["skipped_items"], *plan["blocked_items"]]).most_common():
        lines.append(f"| {status} | {count} |")
    lines += [
        "",
        "## Policy",
        "",
        "- This planner is dry-run only.",
        "- It does not call `process`.",
        "- It does not launch Origin.",
        "- It excludes source hashes already present in the Phase 1.6 Origin package.",
        "- The resulting queue is for a future explicit no-Origin run after review.",
    ]
    return "\n".join(lines) + "\n"
