from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.core.reviewed_queue import (
    APPROVE_DECISION,
    ReviewedQueueOptions,
    TEMPLATE_FIELDS,
    load_proposals,
    plan_reviewed_queue,
    run_reviewed_queue,
    write_decision_template,
)
from src.core.project import default_output_root


@dataclass(frozen=True)
class ReviewedQueueFixture:
    proposals: Path
    workspace_root: Path
    triage_manifest: Path
    processed_index: Path


def test_reviewed_queue_template_generation_covers_all_proposals(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    test_project = tmp_path / "project"
    proposals = load_proposals(test_project, fixture.proposals)
    reports_dir = default_output_root(test_project) / "reports"
    reports_dir.mkdir(parents=True)
    template = reports_dir / "review_template.csv"

    path = write_decision_template(
        test_project,
        proposals,
        ReviewedQueueOptions(proposals=fixture.proposals, write_template=True, template_out=template),
    )

    rows = _read_csv(path)
    assert len(rows) == 3
    assert rows[0]["proposal_id"] == "P18-001"
    assert rows[0]["folder_header_conflict_ack"] == ""
    assert rows[0]["user_decision"] == ""


def test_blank_decisions_create_zero_queue_items(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {})

    plan = _plan(project_root, fixture, decisions)

    assert plan["summary"]["approved_count"] == 0
    assert plan["summary"]["skipped_count"] == 3
    assert plan["summary"]["will_launch_origin"] is False
    assert plan["summary"]["will_run_process"] is False


def test_reviewed_queue_plan_records_input_hashes(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {})

    plan = _plan(project_root, fixture, decisions)

    assert plan["input_hashes"] == {
        "proposals_sha256": _sha256(fixture.proposals),
        "decisions_sha256": _sha256(decisions),
    }
    rendered = json.dumps(plan, ensure_ascii=False)
    assert str(tmp_path) not in rendered
    assert plan["proposals"].startswith("external/")
    assert plan["decisions"].startswith("external/")


def test_explicit_medium_risk_approval_creates_dry_run_queue_item(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = _plan(project_root, fixture, decisions)

    assert plan["summary"]["approved_count"] == 1
    item = plan["approved_queue_items"][0]
    assert item["relative_path"] == "reviewed_queue_fixture/uvvis.txt"
    assert item["origin_export_allowed"] is False
    assert item["promoted_by_workflow"] == "reviewed_queue"


def test_high_risk_approval_requires_ack(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-001": _approval(high_risk_ack="")})

    plan = _plan(project_root, fixture, decisions)

    assert plan["summary"]["approved_count"] == 0
    assert plan["blocked_items"][0]["status"] == "BLOCKED_HIGH_RISK_ACK_REQUIRED"


def test_folder_header_conflict_requires_ack(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-003": _approval()})

    plan = _plan(project_root, fixture, decisions)

    assert plan["summary"]["approved_count"] == 0
    assert plan["blocked_items"][0]["status"] == "BLOCKED_FOLDER_HEADER_CONFLICT_ACK_REQUIRED"


def test_missing_approver_or_date_blocks_approved_rows(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(
        tmp_path,
        proposals,
        {
            "P18-002": _approval(approved_by=""),
            "P18-003": _approval(approval_date="", folder_header_conflict_ack="true"),
        },
    )

    plan = _plan(project_root, fixture, decisions)

    statuses = {item["status"] for item in plan["blocked_items"]}
    assert "BLOCKED_MISSING_APPROVER" in statuses
    assert "BLOCKED_MISSING_APPROVAL_DATE" in statuses


def test_metadata_mismatch_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": {**_approval(), "proposed_processor": "wrong_processor"}})

    plan = _plan(project_root, fixture, decisions)

    assert plan["blocked_items"][0]["status"] == "BLOCKED_DECISION_METADATA_MISMATCH"


def test_hash_mismatch_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path, hash_override="0" * 64)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = _plan(project_root, fixture, decisions)

    assert plan["blocked_items"][0]["status"] == "BLOCKED_HASH_MISMATCH"


def test_processed_hash_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path, processed_ids={"P18-002"})
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = _plan(project_root, fixture, decisions)

    assert plan["blocked_items"][0]["status"] == "BLOCKED_ALREADY_PROCESSED"


def test_path_traversal_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path, relative_override="../outside.txt")
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = _plan(project_root, fixture, decisions)

    assert plan["blocked_items"][0]["status"] == "BLOCKED_POLICY"


def test_composite_forbidden_type_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    for proposal in proposals:
        if proposal["proposal_id"] == "P18-002":
            proposal["proposed_data_type"] = "SEM/TEM/NMR/MS"
            proposal["proposed_processor"] = "none"
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = plan_reviewed_queue(
        project_root,
        proposals,
        ReviewedQueueOptions(
            proposals=fixture.proposals,
            decisions=decisions,
            workspace_root=fixture.workspace_root,
            triage_manifest=fixture.triage_manifest,
            processed_index=fixture.processed_index,
        ),
    )

    assert plan["blocked_items"][0]["status"] == "BLOCKED_POLICY"
    assert "forbidden_data_type" in plan["blocked_items"][0]["reason"]


def test_chinese_kinetics_type_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    for proposal in proposals:
        if proposal["proposal_id"] == "P18-002":
            proposal["proposed_data_type"] = "动力学"
            proposal["proposed_processor"] = "none"
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = plan_reviewed_queue(
        project_root,
        proposals,
        ReviewedQueueOptions(
            proposals=fixture.proposals,
            decisions=decisions,
            workspace_root=fixture.workspace_root,
            triage_manifest=fixture.triage_manifest,
            processed_index=fixture.processed_index,
        ),
    )

    assert plan["blocked_items"][0]["status"] == "BLOCKED_POLICY"
    assert plan["blocked_items"][0]["reason"] == "forbidden_data_type:动力学"


def test_current_triage_drift_blocks_approved_row(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path, triage_decision_override={"P18-002": "DUPLICATE_SUPPRESSED"})
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})

    plan = _plan(project_root, fixture, decisions)

    assert plan["blocked_items"][0]["status"] == "BLOCKED_STALE_PROPOSAL"


def test_reviewed_queue_blocks_duplicate_decision_csv_headers(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    decisions = tmp_path / "duplicate_headers.csv"
    decisions.write_text(
        "proposal_id,proposal_id,relative_path,source_hash,proposed_data_type,proposed_processor,risk_level,reason,recommended_action,user_decision,high_risk_ack,folder_header_conflict_ack,approved_by,approval_date,user_notes\n"
        "P18-001,P18-002,reviewed_queue_fixture/uvvis.txt,hash,UV-vis DRS,uvvis_drs_processor,medium,reason,user_review_before_reviewed_queue_queue,approve_for_no_origin_queue,,,user,2026-05-31,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate decision CSV header"):
        _plan(project_root, fixture, decisions)


def test_reviewed_queue_blocks_missing_required_decision_headers(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    decisions = tmp_path / "missing_headers.csv"
    decisions.write_text(
        "proposal_id,relative_path,source_hash,user_decision\n"
        "P18-002,reviewed_queue_fixture/uvvis.txt,hash,approve_for_no_origin_queue\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing decision CSV headers"):
        _plan(project_root, fixture, decisions)


def test_reviewed_queue_blocks_unknown_decision_csv_columns(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})
    text = decisions.read_text(encoding="utf-8")
    header, rest = text.split("\n", 1)
    decisions.write_text(f"{header},surprise\n{rest}", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown decision CSV headers"):
        _plan(project_root, fixture, decisions)


def test_reviewed_queue_blocks_blank_extra_decision_csv_header(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})
    text = decisions.read_text(encoding="utf-8")
    header, rest = text.split("\n", 1)
    decisions.write_text(f"{header},\n{rest}", encoding="utf-8")

    with pytest.raises(ValueError, match="blank decision CSV header"):
        _plan(project_root, fixture, decisions)


def test_reviewed_queue_blocks_blank_proposal_id_rows(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    proposals = load_proposals(project_root, fixture.proposals)
    decisions = _make_decisions(tmp_path, proposals, {"P18-002": _approval()})
    with decisions.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TEMPLATE_FIELDS))
        writer.writerow({"proposal_id": "", "user_decision": APPROVE_DECISION})

    with pytest.raises(ValueError, match="blank proposal_id"):
        _plan(project_root, fixture, decisions)


def test_reviewed_queue_blocks_malformed_csv_as_parse_error(tmp_path: Path, project_root: Path):
    fixture = _make_fixture(tmp_path)
    decisions = tmp_path / "malformed.csv"
    decisions.write_text(
        ",".join(TEMPLATE_FIELDS) + "\n"
        'P18-002,reviewed_queue_fixture/uvvis.txt,"unterminated\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="malformed decision CSV"):
        _plan(project_root, fixture, decisions)


def test_reviewed_queue_cli_help_and_blank_dry_run(tmp_path: Path, project_root: Path):
    help_result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "reviewed-queue", "--help"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert help_result.returncode == 0
    assert "--write-template" in help_result.stdout
    assert "--decisions" in help_result.stdout

    fixture = _make_fixture(tmp_path)
    test_project = tmp_path / "project"
    proposals = fixture.proposals
    reports_dir = default_output_root(test_project) / "reports"
    reports_dir.mkdir(parents=True)
    template = reports_dir / "_test_review_decisions_template.csv"
    report_json = reports_dir / "_test_reviewed_queue_plan.json"
    report_md = reports_dir / "_test_reviewed_queue_plan.md"
    run_reviewed_queue(test_project, ReviewedQueueOptions(proposals=proposals, write_template=True, template_out=template))
    code = run_reviewed_queue(
        test_project,
        ReviewedQueueOptions(
            proposals=proposals,
            decisions=template,
            report_json=report_json,
            report_md=report_md,
            workspace_root=fixture.workspace_root,
            triage_manifest=fixture.triage_manifest,
            processed_index=fixture.processed_index,
        ),
    )
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["summary"]["approved_count"] == 0
    assert payload["summary"]["will_launch_origin"] is False
    assert payload["summary"]["will_run_process"] is False


def test_reviewed_queue_cli_reports_missing_proposals_without_traceback(project_root: Path):
    result = subprocess.run(
        [
            "D:\\Python\\python.exe",
            "run.py",
            "reviewed-queue",
            "--proposals",
            "output/reports/missing_reviewed_queue_proposals.json",
            "--write-template",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "missing_reviewed_queue_proposals.json" in result.stderr
    assert "Traceback" not in result.stderr


def test_reviewed_queue_cli_reports_invalid_proposals_shape_without_traceback(tmp_path: Path, project_root: Path):
    proposals = tmp_path / "bad_proposals.json"
    proposals.write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [
            "D:\\Python\\python.exe",
            "run.py",
            "reviewed-queue",
            "--proposals",
            str(proposals),
            "--write-template",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "proposal JSON must be an object" in result.stderr
    assert "Traceback" not in result.stderr


def test_reviewed_queue_cli_reports_invalid_proposals_items_without_traceback(tmp_path: Path, project_root: Path):
    proposals = tmp_path / "bad_proposals_items.json"
    proposals.write_text('{"items": {}}', encoding="utf-8")

    result = subprocess.run(
        [
            "D:\\Python\\python.exe",
            "run.py",
            "reviewed-queue",
            "--proposals",
            str(proposals),
            "--write-template",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "proposal JSON items must be a list" in result.stderr
    assert "Traceback" not in result.stderr


def test_reviewed_queue_cli_reports_non_object_proposal_item_without_traceback(tmp_path: Path, project_root: Path):
    proposals = tmp_path / "bad_proposals_item.json"
    proposals.write_text('{"items": ["not-an-object"]}', encoding="utf-8")

    result = subprocess.run(
        [
            "D:\\Python\\python.exe",
            "run.py",
            "reviewed-queue",
            "--proposals",
            str(proposals),
            "--write-template",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "proposal JSON item 1 must be an object" in result.stderr
    assert "Traceback" not in result.stderr


def test_reviewed_queue_module_does_not_import_origin_or_process(project_root: Path):
    text = (project_root / "src" / "core" / "reviewed_queue.py").read_text(encoding="utf-8")
    assert "src.origin" not in text
    assert "from src.core.process" not in text
    assert "import src.core.process" not in text
    assert "process_table_dataset" not in text


def _plan(project_root: Path, fixture: ReviewedQueueFixture, decisions: Path) -> dict:
    return plan_reviewed_queue(
        project_root,
        load_proposals(project_root, fixture.proposals),
        ReviewedQueueOptions(
            proposals=fixture.proposals,
            decisions=decisions,
            workspace_root=fixture.workspace_root,
            triage_manifest=fixture.triage_manifest,
            processed_index=fixture.processed_index,
        ),
    )


def _make_fixture(
    tmp_path: Path,
    *,
    hash_override: str | None = None,
    relative_override: str | None = None,
    processed_ids: set[str] | None = None,
    triage_decision_override: dict[str, str] | None = None,
) -> ReviewedQueueFixture:
    workspace = tmp_path / "workspace"
    xrd = _write(workspace / "reviewed_queue_fixture" / "xrd.txt", "angle,intensity\n10,20\n")
    uvvis = _write(workspace / "reviewed_queue_fixture" / "uvvis.txt", "wavelength,reflectance\n300,0.2\n")
    eis = _write(workspace / "reviewed_queue_fixture" / "eis.txt", "frequency,re_z,im_z\n1,2,3\n")
    items = [
        _proposal("P18-001", "reviewed_queue_fixture/xrd.txt", _sha256(xrd), "XRD", "xrd_processor", "high", "safe_numeric_review_candidate_requires_user_confirmation"),
        _proposal(
            "P18-002",
            relative_override or "reviewed_queue_fixture/uvvis.txt",
            hash_override or _sha256(uvvis),
            "UV-vis DRS",
            "uvvis_drs_processor",
            "medium",
            "safe_numeric_review_candidate_requires_user_confirmation",
        ),
        _proposal("P18-003", "reviewed_queue_fixture/eis.txt", _sha256(eis), "EIS", "eis_processor", "high", "mild_folder_header_conflict_requires_user_review"),
    ]
    proposals_path = tmp_path / "proposals.json"
    proposals_path.write_text(json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    triage_path = tmp_path / "triage.json"
    _write_fixture_triage(triage_path, items, triage_decision_override or {})
    processed_index = tmp_path / "processed_index.csv"
    _write_processed_index(processed_index, items, processed_ids or set())
    return ReviewedQueueFixture(proposals_path, workspace, triage_path, processed_index)


def _proposal(proposal_id: str, relative_path: str, source_hash: str, data_type: str, processor: str, risk: str, reason: str) -> dict:
    return {
        "proposal_id": proposal_id,
        "relative_path": relative_path,
        "source_hash": source_hash,
        "proposed_data_type": data_type,
        "proposed_processor": processor,
        "confidence_score": 0.9,
        "validity_score": 0.9,
        "decision": "MANUAL_REVIEW",
        "reason": reason,
        "risk_level": risk,
        "recommended_action": "user_review_before_reviewed_queue_queue",
        "evidence": ["parser_probe_status=success"],
    }


def _write_fixture_triage(path: Path, proposals: list[dict], decision_override: dict[str, str]) -> None:
    items = []
    for proposal in proposals:
        items.append(
            {
                "relative_path": proposal["relative_path"],
                "source_hash": proposal["source_hash"],
                "decision": decision_override.get(proposal["proposal_id"], "MANUAL_REVIEW"),
                "supported_in_pipeline": True,
                "parser_probe_status": "success",
                "data_type_candidate": proposal["proposed_data_type"],
                "selected_processor": proposal["proposed_processor"],
            }
        )
    path.write_text(json.dumps({"items": items, "summary": {"total_files": len(items)}}, ensure_ascii=False), encoding="utf-8")


def _write_processed_index(path: Path, proposals: list[dict], processed_ids: set[str]) -> None:
    rows = [{"source_hash": proposal["source_hash"]} for proposal in proposals if proposal["proposal_id"] in processed_ids]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_hash"])
        writer.writeheader()
        writer.writerows(rows)


def _make_decisions(tmp_path: Path, proposals: list[dict], overrides: dict[str, dict[str, str]]) -> Path:
    rows = []
    for proposal in proposals:
        row = {
            "proposal_id": proposal["proposal_id"],
            "relative_path": proposal["relative_path"],
            "source_hash": proposal["source_hash"],
            "proposed_data_type": proposal["proposed_data_type"],
            "proposed_processor": proposal["proposed_processor"],
            "risk_level": proposal["risk_level"],
            "reason": proposal["reason"],
            "recommended_action": proposal["recommended_action"],
            "user_decision": "",
            "high_risk_ack": "",
            "folder_header_conflict_ack": "",
            "approved_by": "",
            "approval_date": "",
            "user_notes": "",
        }
        row.update(overrides.get(proposal["proposal_id"], {}))
        rows.append(row)
    path = tmp_path / "decisions.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _approval(
    *,
    high_risk_ack: str = "true",
    folder_header_conflict_ack: str = "",
    approved_by: str = "user",
    approval_date: str = "2026-05-31",
) -> dict[str, str]:
    return {
        "user_decision": APPROVE_DECISION,
        "high_risk_ack": high_risk_ack,
        "folder_header_conflict_ack": folder_header_conflict_ack,
        "approved_by": approved_by,
        "approval_date": approval_date,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
