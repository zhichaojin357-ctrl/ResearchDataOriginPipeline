from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_WORKSPACE_RELATIVE = Path("workspace_data") / "LL_detection_copy_20260530"
PHASE1_6_PACKAGE_RELATIVE = Path("output") / "phase1_6_origin_results_20260531_041538"
APPROVE_DECISION = "approve_for_no_origin_queue"
SKIP_DECISIONS = {"reject", "keep_manual_review", "do_not_process"}
HIGH_RISK_TYPES = {"XPS", "EPR", "XRD", "Mott-Schottky", "HPLC/LC exported data"}
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
TEMPLATE_FIELDS = (
    "proposal_id",
    "relative_path",
    "source_hash",
    "proposed_data_type",
    "proposed_processor",
    "risk_level",
    "reason",
    "recommended_action",
    "user_decision",
    "high_risk_ack",
    "folder_header_conflict_ack",
    "approved_by",
    "approval_date",
    "user_notes",
)


@dataclass(frozen=True)
class ReviewedQueueOptions:
    proposals: Path
    decisions: Path | None = None
    write_template: bool = False
    dry_run: bool = True
    template_out: Path | None = None
    report_json: Path | None = None
    report_md: Path | None = None
    workspace_root: Path | None = None
    triage_manifest: Path | None = None
    processed_index: Path | None = None


def run_reviewed_queue(project_root: Path, options: ReviewedQueueOptions) -> int:
    proposals = load_proposals(project_root, options.proposals)
    if options.write_template:
        write_decision_template(project_root, proposals, options)
    if options.decisions is not None:
        plan = plan_reviewed_queue(project_root, proposals, options)
        write_reviewed_queue_reports(project_root, plan, options)
        return 0
    return 0


def load_proposals(project_root: Path, proposals_path: Path) -> list[dict]:
    path = _resolve_existing_path(project_root, proposals_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_items = payload.get("items", [])
    proposals = []
    for index, item in enumerate(raw_items, start=1):
        proposal = dict(item)
        proposal.setdefault("proposal_id", f"P18-{index:03d}")
        proposals.append(proposal)
    return proposals


def write_decision_template(project_root: Path, proposals: list[dict], options: ReviewedQueueOptions) -> Path:
    template_path = options.template_out or project_root / "output" / "reports" / "phase1_8_review_decisions_template.csv"
    _guard_output_path(project_root, template_path)
    rows = [_template_row(proposal) for proposal in proposals]
    template_path.parent.mkdir(parents=True, exist_ok=True)
    with template_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TEMPLATE_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    return template_path


def plan_reviewed_queue(project_root: Path, proposals: list[dict], options: ReviewedQueueOptions) -> dict:
    if options.decisions is None:
        raise ValueError("A decisions CSV is required for reviewed-queue dry-run planning.")
    decisions_path = _resolve_existing_path(project_root, options.decisions)
    decision_rows = _read_decision_rows(decisions_path)
    decisions, duplicate_decision_ids = _decision_lookup(decision_rows)
    triage_items = _load_current_triage_items(project_root, options.triage_manifest)
    processed_hashes = _phase1_6_processed_hashes(project_root, options.processed_index)
    planned = []
    skipped = []
    blocked = []

    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id", ""))
        decision = decisions.get(proposal_id) or {}
        base = _base_item(proposal)
        user_decision = str(decision.get("user_decision", "")).strip().casefold()

        if proposal_id in duplicate_decision_ids:
            blocked.append({**base, "status": "BLOCKED_DUPLICATE_DECISION_ROW", "reason": "duplicate_proposal_id_in_decisions"})
            continue
        if not user_decision:
            skipped.append({**base, "status": "SKIPPED_NOT_APPROVED", "reason": "blank_user_decision"})
            continue
        if user_decision in SKIP_DECISIONS:
            skipped.append({**base, "status": "SKIPPED_REJECTED", "reason": user_decision})
            continue
        if user_decision != APPROVE_DECISION:
            blocked.append({**base, "status": "BLOCKED_POLICY", "reason": f"unknown_user_decision:{user_decision}"})
            continue

        mismatches = _decision_metadata_mismatches(proposal, decision)
        if mismatches:
            blocked.append({**base, "status": "BLOCKED_DECISION_METADATA_MISMATCH", "reason": "decision_row_does_not_match_proposal", "mismatches": mismatches})
            continue

        block = _approval_block(project_root, proposal, decision, triage_items, processed_hashes, options.workspace_root)
        if block:
            blocked.append({**base, **block})
            continue
        planned.append(_approved_queue_item(proposal, decision))

    plan = {
        "runner": "reviewed-queue",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "proposals": str(_resolve_existing_path(project_root, options.proposals)),
        "decisions": str(decisions_path),
        "options": {"dry_run": True, "write_template": options.write_template},
        "summary": {
            "total_proposals": len(proposals),
            "decision_rows": len(decision_rows),
            "approved_count": len(planned),
            "skipped_count": len(skipped),
            "blocked_count": len(blocked),
            "queue_item_count": len(planned),
            "will_launch_origin": False,
            "will_run_process": False,
        },
        "approved_queue_items": planned,
        "skipped_items": skipped,
        "blocked_items": blocked,
    }
    return plan


def write_reviewed_queue_reports(project_root: Path, plan: dict, options: ReviewedQueueOptions) -> tuple[Path, Path]:
    reports_dir = project_root / "output" / "reports"
    json_path = options.report_json or reports_dir / "phase1_8_reviewed_queue_plan.json"
    md_path = options.report_md or reports_dir / "phase1_8_reviewed_queue_plan.md"
    _guard_output_path(project_root, json_path)
    _guard_output_path(project_root, md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_plan_markdown(plan), encoding="utf-8")
    agent_report = project_root / "docs" / "agent_reports" / "phase1_8_reviewed_queue_report.md"
    agent_report.parent.mkdir(parents=True, exist_ok=True)
    agent_report.write_text(_plan_markdown(plan), encoding="utf-8")
    return json_path, md_path


def _template_row(proposal: dict) -> dict[str, str]:
    return {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "relative_path": str(proposal.get("relative_path", "")),
        "source_hash": str(proposal.get("source_hash", "")),
        "proposed_data_type": str(proposal.get("proposed_data_type", "")),
        "proposed_processor": str(proposal.get("proposed_processor", "")),
        "risk_level": _risk_level(proposal),
        "reason": str(proposal.get("reason", "")),
        "recommended_action": str(proposal.get("recommended_action", "")),
        "user_decision": "",
        "high_risk_ack": "",
        "folder_header_conflict_ack": "",
        "approved_by": "",
        "approval_date": "",
        "user_notes": "",
    }


def _approval_block(
    project_root: Path,
    proposal: dict,
    decision: dict,
    triage_items: dict[tuple[str, str], dict],
    processed_hashes: set[str],
    workspace_root: Path | None,
) -> dict | None:
    if not str(decision.get("approved_by", "")).strip():
        return {"status": "BLOCKED_MISSING_APPROVER", "reason": "approved_by_required"}
    if not str(decision.get("approval_date", "")).strip():
        return {"status": "BLOCKED_MISSING_APPROVAL_DATE", "reason": "approval_date_required"}
    data_type = str(proposal.get("proposed_data_type", ""))
    if _is_forbidden_type(data_type):
        return {"status": "BLOCKED_POLICY", "reason": f"forbidden_data_type:{data_type}"}
    if _risk_level(proposal) == "high" and not _truthy(decision.get("high_risk_ack", "")):
        return {"status": "BLOCKED_HIGH_RISK_ACK_REQUIRED", "reason": "high_risk_ack_required"}
    if _requires_folder_header_conflict_ack(proposal) and not _truthy(decision.get("folder_header_conflict_ack", "")):
        return {"status": "BLOCKED_FOLDER_HEADER_CONFLICT_ACK_REQUIRED", "reason": "folder_header_conflict_ack_required"}

    relative_path = str(proposal.get("relative_path", "")).strip()
    source_hash = str(proposal.get("source_hash", "")).strip()
    source_path, path_error = _resolve_workspace_source(project_root, relative_path, workspace_root)
    if path_error:
        return path_error
    if not source_path.exists() or not source_path.is_file():
        return {"status": "BLOCKED_SOURCE_MISSING", "reason": "workspace_source_missing", "relative_path": relative_path}
    actual_hash = _file_sha256(source_path)
    if actual_hash.lower() != source_hash.lower():
        return {
            "status": "BLOCKED_HASH_MISMATCH",
            "reason": "source_hash_mismatch",
            "expected_hash": source_hash,
            "actual_hash": actual_hash,
        }
    triage_item = triage_items.get((relative_path.replace("\\", "/"), source_hash))
    if triage_item is None:
        return {"status": "BLOCKED_STALE_PROPOSAL", "reason": "not_found_in_current_triage_manifest"}
    stale_block = _current_triage_state_block(proposal, triage_item)
    if stale_block:
        return stale_block
    if source_hash in processed_hashes:
        return {"status": "BLOCKED_ALREADY_PROCESSED", "reason": "source_hash_in_phase1_6_package"}
    return None


def _approved_queue_item(proposal: dict, decision: dict) -> dict:
    source_hash = str(proposal.get("source_hash", ""))
    data_type = str(proposal.get("proposed_data_type", ""))
    return {
        "queue_id": f"phase1_8_{source_hash[:16]}",
        "relative_path": str(proposal.get("relative_path", "")),
        "source_hash": source_hash,
        "data_type": data_type,
        "selected_processor": str(proposal.get("proposed_processor", "")),
        "original_triage_decision": "MANUAL_REVIEW",
        "current_decision": "USER_APPROVED_NO_ORIGIN_QUEUE",
        "decision": "AUTO_PROCESS",
        "promoted_from_manual_review": True,
        "promoted_by_phase": "phase1_8",
        "promoted_confidence": proposal.get("confidence_score", 0),
        "promoted_validity": proposal.get("validity_score", 0),
        "promotion_reason": str(proposal.get("reason", "")),
        "promotion_evidence": proposal.get("evidence", []),
        "manual_check_required": True,
        "manual_override_used": False,
        "origin_export_allowed": False,
        "forbidden_claims": _forbidden_claims(data_type),
        "approved_by": str(decision.get("approved_by", "")).strip(),
        "approval_date": str(decision.get("approval_date", "")).strip(),
        "high_risk_ack": _truthy(decision.get("high_risk_ack", "")),
        "folder_header_conflict_ack": _truthy(decision.get("folder_header_conflict_ack", "")),
        "user_notes": str(decision.get("user_notes", "")).strip(),
    }


def _base_item(proposal: dict) -> dict[str, str]:
    return {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "relative_path": str(proposal.get("relative_path", "")),
        "source_hash": str(proposal.get("source_hash", "")),
        "proposed_data_type": str(proposal.get("proposed_data_type", "")),
    }


def _read_decision_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _decision_lookup(rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], set[str]]:
    lookup = {}
    duplicate_ids = set()
    for row in rows:
        proposal_id = str(row.get("proposal_id", "")).strip()
        if proposal_id:
            if proposal_id in lookup:
                duplicate_ids.add(proposal_id)
            else:
                lookup[proposal_id] = row
    return lookup, duplicate_ids


def _normalized_relative(value: object) -> str:
    return str(value).replace("\\", "/")


def _decision_metadata_mismatches(proposal: dict, decision: dict) -> list[dict[str, str]]:
    fields = ("relative_path", "source_hash", "proposed_data_type", "proposed_processor", "risk_level", "reason")
    mismatches = []
    for field in fields:
        proposal_value = _metadata_value(proposal, field)
        decision_value = _metadata_value(decision, field)
        if proposal_value != decision_value:
            mismatches.append({"field": field, "proposal": proposal_value, "decision": decision_value})
    return mismatches


def _metadata_value(row: dict, field: str) -> str:
    if field == "relative_path":
        return _normalized_relative(row.get(field, "")).strip()
    if field == "risk_level":
        return _risk_level(row).strip().casefold()
    return str(row.get(field, "")).strip()


def _requires_folder_header_conflict_ack(proposal: dict) -> bool:
    text = " ".join(
        str(proposal.get(field, ""))
        for field in ("reason", "recommended_action")
    ).casefold()
    evidence = " ".join(str(item) for item in proposal.get("evidence", [])).casefold()
    return "folder_header_conflict" in text or "folder/header" in evidence


def _current_triage_state_block(proposal: dict, triage_item: dict) -> dict | None:
    decision = str(triage_item.get("decision", ""))
    if decision != "MANUAL_REVIEW":
        return {"status": "BLOCKED_STALE_PROPOSAL", "reason": f"current_triage_decision_is_{decision}"}
    if triage_item.get("supported_in_phase_1") is not True:
        return {"status": "BLOCKED_POLICY", "reason": "current_triage_not_supported_in_phase_1"}
    if triage_item.get("parser_probe_status") != "success":
        return {"status": "BLOCKED_POLICY", "reason": "current_parser_probe_not_success"}
    proposed_type = str(proposal.get("proposed_data_type", "")).strip()
    current_type = str(triage_item.get("data_type_candidate", "")).strip()
    if proposed_type and current_type and proposed_type != current_type:
        return {"status": "BLOCKED_STALE_PROPOSAL", "reason": "current_data_type_candidate_changed", "current_data_type_candidate": current_type}
    proposed_processor = str(proposal.get("proposed_processor", "")).strip()
    current_processor = str(triage_item.get("selected_processor", "")).strip()
    if proposed_processor and current_processor and proposed_processor != current_processor:
        return {"status": "BLOCKED_STALE_PROPOSAL", "reason": "current_processor_changed", "current_processor": current_processor}
    return None


def _load_current_triage_items(project_root: Path, triage_manifest: Path | None = None) -> dict[tuple[str, str], dict]:
    manifest_path = triage_manifest or project_root / "output" / "reports" / "data_triage_manifest.json"
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = {}
    for item in payload.get("items", []):
        relative_path = str(item.get("relative_path", "")).replace("\\", "/")
        source_hash = str(item.get("source_hash", "")).strip()
        if relative_path and source_hash:
            items[(relative_path, source_hash)] = item
    return items


def _phase1_6_processed_hashes(project_root: Path, processed_index: Path | None = None) -> set[str]:
    index_path = processed_index or project_root / PHASE1_6_PACKAGE_RELATIVE / "index.csv"
    if not index_path.is_absolute():
        index_path = project_root / index_path
    if not index_path.exists():
        return set()
    with index_path.open(encoding="utf-8-sig", newline="") as handle:
        return {row.get("source_hash", "").strip() for row in csv.DictReader(handle) if row.get("source_hash", "").strip()}


def _resolve_workspace_source(project_root: Path, relative_path: str, workspace_root_override: Path | None = None) -> tuple[Path, dict | None]:
    path = Path(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts:
        return project_root, {"status": "BLOCKED_POLICY", "reason": "path_traversal_or_absolute_source_path"}
    workspace_root = workspace_root_override or project_root / DEFAULT_WORKSPACE_RELATIVE
    if not workspace_root.is_absolute():
        workspace_root = project_root / workspace_root
    workspace_root = workspace_root.resolve()
    candidate = (workspace_root / path).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError:
        return candidate, {"status": "BLOCKED_POLICY", "reason": "source_resolves_outside_workspace"}
    return candidate, None


def _risk_level(proposal: dict) -> str:
    risk = str(proposal.get("risk_level", "")).strip().casefold()
    if risk:
        return risk
    data_type = str(proposal.get("proposed_data_type", ""))
    return "high" if data_type in HIGH_RISK_TYPES else "medium"


def _is_forbidden_type(data_type: str) -> bool:
    normalized = data_type.strip().casefold()
    return any(normalized == item.casefold() for item in FORBIDDEN_TYPES)


def _forbidden_claims(data_type: str) -> list[str]:
    claims = {
        "XPS": "do not automatically assign valence states",
        "EPR": "do not automatically assign radical identity",
        "XRD": "do not automatically assign phase or facets",
        "Mott-Schottky": "do not equate flat-band potential with CB/VB",
        "photocurrent": "do not infer carrier separation efficiency automatically",
        "PL": "do not infer recombination suppression automatically",
        "Raman": "do not assign defect type automatically",
    }
    return [claims[data_type]] if data_type in claims else []


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _truthy(value: object) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "ack", "acknowledged"}


def _resolve_existing_path(project_root: Path, raw_path: Path) -> Path:
    path = raw_path if raw_path.is_absolute() else project_root / raw_path
    absolute = path.absolute()
    if not absolute.exists():
        raise FileNotFoundError(f"Required file not found: {raw_path}")
    return absolute


def _guard_output_path(project_root: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = [
        (project_root / "output").resolve(),
        (project_root / "docs").resolve(),
        (project_root / "tests" / "fixtures").resolve(),
    ]
    if not any(_is_under_or_equal(resolved, root) for root in allowed):
        raise ValueError(f"Refusing to write reviewed-queue report outside allowed output areas: {path}")


def _is_under_or_equal(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return path == parent


def _plan_markdown(plan: dict) -> str:
    summary = plan["summary"]
    lines = [
        "# Phase 1.8 Reviewed Queue Plan",
        "",
        f"- Total proposals: {summary['total_proposals']}",
        f"- Decision rows: {summary['decision_rows']}",
        f"- Approved queue items: {summary['approved_count']}",
        f"- Skipped items: {summary['skipped_count']}",
        f"- Blocked items: {summary['blocked_count']}",
        f"- Will launch Origin: {summary['will_launch_origin']}",
        f"- Will run process: {summary['will_run_process']}",
        "",
        "## Approved Queue Items",
    ]
    if plan["approved_queue_items"]:
        for item in plan["approved_queue_items"]:
            lines.append(f"- `{item['relative_path']}` -> {item['data_type']} ({item['selected_processor']})")
    else:
        lines.append("- None.")
    lines.extend(["", "## Skipped Items"])
    if plan["skipped_items"]:
        for item in plan["skipped_items"]:
            lines.append(f"- `{item['relative_path']}`: {item['status']} ({item['reason']})")
    else:
        lines.append("- None.")
    lines.extend(["", "## Blocked Items"])
    if plan["blocked_items"]:
        for item in plan["blocked_items"]:
            lines.append(f"- `{item['relative_path']}`: {item['status']} ({item['reason']})")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- This planner does not launch Origin.",
            "- This planner does not run real data processing.",
            "- Approved rows are only dry-run queue candidates until a future explicit processing phase.",
        ]
    )
    return "\n".join(lines) + "\n"
