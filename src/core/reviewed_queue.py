from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.file_utils import file_sha256 as _file_sha256
from src.core.file_utils import is_under_or_equal as _is_under_or_equal
from src.core.output_sanitizer import sanitize_report_payload as _sanitize_report_payload
from src.core.project import report_path, project_config_scope
from src.core.runtime_paths import resolve_locked_result_index, resolve_output_root, resolve_workspace_root


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
    output_root: Path | None = None
    workspace_root: Path | None = None
    triage_manifest: Path | None = None
    processed_index: Path | None = None


@project_config_scope()
def run_reviewed_queue(project_root: Path, options: ReviewedQueueOptions) -> int:
    proposals = load_proposals(project_root, options.proposals)
    if options.write_template:
        write_decision_template(project_root, proposals, options)
    if options.decisions is not None:
        plan = plan_reviewed_queue(project_root, proposals, options)
        write_reviewed_queue_reports(project_root, plan, options)
        return 1 if plan["summary"]["blocked_count"] else 0
    return 0


def load_proposals(project_root: Path, proposals_path: Path) -> list[dict]:
    path = _resolve_existing_path(project_root, proposals_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"proposal JSON must be an object with an items list: {path}")
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError(f"proposal JSON items must be a list: {path}")
    proposals = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"proposal JSON item {index} must be an object: {path}")
        proposal = dict(item)
        proposal.setdefault("proposal_id", f"RQ-{index:03d}")
        proposals.append(proposal)
    return proposals


def write_decision_template(project_root: Path, proposals: list[dict], options: ReviewedQueueOptions) -> Path:
    template_path = options.template_out or report_path(
        project_root,
        "review_decisions_template.csv",
        output_root=options.output_root,
    )
    _guard_output_path(project_root, template_path)
    rows = [_template_row(proposal) for proposal in proposals]
    template_path.parent.mkdir(parents=True, exist_ok=True)
    with template_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TEMPLATE_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    return template_path


@project_config_scope()
def plan_reviewed_queue(project_root: Path, proposals: list[dict], options: ReviewedQueueOptions) -> dict:
    if options.decisions is None:
        raise ValueError("A decisions CSV is required for reviewed-queue dry-run planning.")
    proposals_path = _resolve_existing_path(project_root, options.proposals)
    decisions_path = _resolve_existing_path(project_root, options.decisions)
    decision_rows = _read_decision_rows(decisions_path)
    decisions, duplicate_decision_ids = _decision_lookup(decision_rows)
    triage_items = _load_current_triage_items(project_root, options.triage_manifest, options.output_root)
    processed_hashes = _locked_result_processed_hashes(project_root, options.processed_index)
    workspace_root = resolve_workspace_root(project_root, options.workspace_root)
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

        block = _approval_block(project_root, proposal, decision, triage_items, processed_hashes, workspace_root)
        if block:
            blocked.append({**base, **block})
            continue
        planned.append(_approved_queue_item(proposal, decision))

    plan = {
        "runner": "reviewed-queue",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "proposals": str(proposals_path),
        "decisions": str(decisions_path),
        "input_hashes": {
            "proposals_sha256": _file_sha256(proposals_path),
            "decisions_sha256": _file_sha256(decisions_path),
        },
        "options": {"dry_run": True, "write_template": options.write_template},
        "summary": {
            "total_proposals": len(proposals),
            "decision_rows": len(decision_rows),
            "approved_count": len(planned),
            "skipped_count": len(skipped),
            "blocked_count": len(blocked),
            "plan_complete": not blocked,
            "blocked_semantics": "blocked items are explicitly approved rows that could not form safe executable queue entries",
            "queue_item_count": len(planned),
            "will_launch_origin": False,
            "will_run_process": False,
        },
        "approved_queue_items": planned,
        "skipped_items": skipped,
        "blocked_items": blocked,
    }
    return _sanitize_report_payload(project_root, plan, options.output_root)


def write_reviewed_queue_reports(project_root: Path, plan: dict, options: ReviewedQueueOptions) -> tuple[Path, Path]:
    json_path = options.report_json or report_path(
        project_root,
        "reviewed_queue_plan.json",
        output_root=options.output_root,
    )
    md_path = options.report_md or report_path(
        project_root,
        "reviewed_queue_plan.md",
        output_root=options.output_root,
    )
    _guard_output_path(project_root, json_path)
    _guard_output_path(project_root, md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_plan_markdown(plan), encoding="utf-8")
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
        return {"status": "BLOCKED_ALREADY_PROCESSED", "reason": "source_hash_in_locked_result_package"}
    return None


def _approved_queue_item(proposal: dict, decision: dict) -> dict:
    source_hash = str(proposal.get("source_hash", ""))
    data_type = str(proposal.get("proposed_data_type", ""))
    return {
        "queue_id": f"reviewed_queue_{source_hash[:16]}",
        "relative_path": str(proposal.get("relative_path", "")),
        "source_hash": source_hash,
        "data_type": data_type,
        "selected_processor": str(proposal.get("proposed_processor", "")),
        "original_triage_decision": "MANUAL_REVIEW",
        "current_decision": "USER_APPROVED_NO_ORIGIN_QUEUE",
        "decision": "AUTO_PROCESS",
        "promoted_from_manual_review": True,
        "promoted_by_workflow": "reviewed_queue",
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
        try:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if header is None:
                raise ValueError("missing decision CSV headers")
            _validate_decision_header(header)
            rows: list[dict[str, str]] = []
            for line_number, row in enumerate(reader, start=2):
                if not row or not any(str(cell).strip() for cell in row):
                    continue
                if len(row) != len(header):
                    raise ValueError(
                        f"malformed decision CSV row {line_number}: expected {len(header)} columns, got {len(row)}"
                    )
                mapped = dict(zip(header, row, strict=True))
                if not str(mapped.get("proposal_id", "")).strip():
                    raise ValueError(f"blank proposal_id in decision CSV row {line_number}")
                rows.append(mapped)
            return rows
        except csv.Error as exc:
            raise ValueError(f"malformed decision CSV: {exc}") from exc


def _validate_decision_header(header: list[str]) -> None:
    normalized = [str(field).strip() for field in header]
    if any(not field for field in normalized):
        raise ValueError("blank decision CSV header")
    duplicates = sorted({field for field in normalized if field and normalized.count(field) > 1})
    if duplicates:
        raise ValueError(f"duplicate decision CSV header: {', '.join(duplicates)}")
    expected = set(TEMPLATE_FIELDS)
    actual = set(normalized)
    missing = sorted(expected - actual)
    unknown = sorted(field for field in actual - expected if field)
    if missing:
        raise ValueError(f"missing decision CSV headers: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"unknown decision CSV headers: {', '.join(unknown)}")


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
    if triage_item.get("supported_in_pipeline") is not True:
        return {"status": "BLOCKED_POLICY", "reason": "current_triage_not_supported_in_pipeline"}
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


def _load_current_triage_items(
    project_root: Path,
    triage_manifest: Path | None = None,
    output_root: Path | None = None,
) -> dict[tuple[str, str], dict]:
    manifest_path = triage_manifest or report_path(project_root, "data_triage_manifest.json", output_root=output_root)
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


def _locked_result_processed_hashes(project_root: Path, processed_index: Path | None = None) -> set[str]:
    index_path = resolve_locked_result_index(project_root, processed_index)
    if not index_path.exists():
        return set()
    with index_path.open(encoding="utf-8-sig", newline="") as handle:
        return {row.get("source_hash", "").strip() for row in csv.DictReader(handle) if row.get("source_hash", "").strip()}


def _resolve_workspace_source(project_root: Path, relative_path: str, workspace_root_override: Path | None = None) -> tuple[Path, dict | None]:
    path = Path(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts:
        return project_root, {"status": "BLOCKED_POLICY", "reason": "path_traversal_or_absolute_source_path"}
    workspace_root = resolve_workspace_root(project_root, workspace_root_override)
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
    normalized = _normalize_type_label(data_type)
    if normalized in {_normalize_type_label(item) for item in FORBIDDEN_TYPES}:
        return True
    tokens = [
        token.strip()
        for part in normalized.replace("\\", "/").replace("|", "/").replace(",", "/").replace(";", "/").split("/")
        for token in (part,)
        if token.strip()
    ]
    return any(token in FORBIDDEN_TYPE_TOKENS for token in tokens)


def _normalize_type_label(value: object) -> str:
    return str(value or "").casefold().replace("_", "-").strip()


def _forbidden_claims(data_type: str) -> list[str]:
    claims = {
        "XPS": "do not automatically assign valence states",
        "EPR": "do not automatically assign radical identity",
        "XRD": "do not automatically label facets or claim phase purity; local Jade/PDF phase matching with card provenance is allowed",
        "Mott-Schottky": "do not equate flat-band potential with CB/VB",
        "photocurrent": "do not infer carrier separation efficiency automatically",
        "PL": "do not infer recombination suppression automatically",
        "Raman": "do not assign defect type automatically",
    }
    return [claims[data_type]] if data_type in claims else []


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
    output_root = resolve_output_root(project_root).resolve()
    if not _is_under_or_equal(resolved, output_root):
        raise ValueError(f"Refusing to write reviewed-queue report outside configured output root: {path}")


def _plan_markdown(plan: dict) -> str:
    summary = plan["summary"]
    input_hashes = plan.get("input_hashes", {})
    lines = [
        "# Reviewed Queue Plan",
        "",
        f"- Total proposals: {summary['total_proposals']}",
        f"- Decision rows: {summary['decision_rows']}",
        f"- Approved queue items: {summary['approved_count']}",
        f"- Skipped items: {summary['skipped_count']}",
        f"- Blocked items: {summary['blocked_count']}",
        f"- Plan complete: {str(summary['plan_complete']).lower()}",
        f"- Will launch Origin: {summary['will_launch_origin']}",
        f"- Will run process: {summary['will_run_process']}",
        f"- Proposals SHA256: `{input_hashes.get('proposals_sha256', '')}`",
        f"- Decisions SHA256: `{input_hashes.get('decisions_sha256', '')}`",
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
            "- Approved rows are only dry-run queue candidates until an explicit processing run.",
        ]
    )
    return "\n".join(lines) + "\n"
