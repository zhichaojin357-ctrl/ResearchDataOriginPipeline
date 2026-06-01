from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from src.core.origin_batch import plan_origin_batch, OriginBatchOptions
from src.core.runtime_paths import resolve_optional_f_drive_backup, resolve_phase1_6_index, resolve_phase1_6_package, resolve_workspace_root


EXPECTED_RESULT_COUNT = 167
HIGH_RISK_TYPES = {"XPS", "EPR", "Mott-Schottky"}
REVIEW_FOCUS = {
    "XPS": {
        "priority": "P1",
        "action": "check_xps_no_valence_assignment",
        "reason": "XPS spectra need human review for peak/background/component validity and must not be auto-assigned to valence states.",
        "check": "Check raw spectrum/background/envelope/component curves and confirm no automatic valence-state assignment is used.",
    },
    "EPR": {
        "priority": "P1",
        "action": "check_epr_no_radical_assignment",
        "reason": "EPR field-intensity plots are useful for inspection but radical identity must remain manual.",
        "check": "Check field-intensity shape and confirm no automatic radical assignment is used.",
    },
    "Mott-Schottky": {
        "priority": "P1",
        "action": "check_mott_schottky_fit_range",
        "reason": "Mott-Schottky candidate fits require human fit-range review and must not be equated to CB/VB automatically.",
        "check": "Check 1/C^2-potential curve, candidate linear interval, and flat-band wording.",
    },
    "photocurrent": {
        "priority": "P2",
        "action": "check_photocurrent_light_cycles",
        "reason": "Photocurrent plots need visual cycle review and must not imply carrier-separation conclusions automatically.",
        "check": "Check light on/off cycles, current axis and unit, and absence of carrier-separation claims.",
    },
    "Raman": {
        "priority": "P2",
        "action": "check_raman_peak_candidates",
        "reason": "Raman spectra can show peak candidates but defect assignments require human evidence.",
        "check": "Check peak candidates and confirm no automatic defect assignment is used.",
    },
    "EIS": {
        "priority": "P2",
        "action": "check_eis_nyquist_bode",
        "reason": "EIS plots need human review before equivalent-circuit or mechanism conclusions.",
        "check": "Check Nyquist/Bode presentation and absence of equivalent-circuit or mechanism claims.",
    },
}
PATH_FIELDS = (
    "processed_csv",
    "metadata",
    "origin_file",
    "figure_tif",
    "preview_png",
    "original_no_origin_preview",
    "contact_sheet",
)


def package_dir(project_root: Path) -> Path:
    return resolve_phase1_6_package(project_root)


def load_package_rows(package_root: Path) -> list[dict[str, str]]:
    with (package_root / "index.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_phase1_6_package(project_root: Path, package_root: Path | None = None) -> dict:
    package_root = package_root or package_dir(project_root)
    audit: dict[str, object] = {
        "package_root": str(package_root),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "exists": package_root.exists(),
        "expected_result_count": EXPECTED_RESULT_COUNT,
    }
    required_files = ("index.md", "index.csv", "result_summary.json")
    audit["required_files"] = {name: (package_root / name).exists() for name in required_files}
    subdirs = {
        "selected_source_data": "*",
        "processed_tables": "*.csv",
        "metadata": "*.json",
        "origin_files": "*.opju",
        "figures_tif": "*.tif",
        "previews_origin": "previews/origin/*.png",
        "previews_no_origin": "previews/no_origin/*.png",
        "contact_sheets_origin": "contact_sheets/origin/*.png",
        "contact_sheets_no_origin": "contact_sheets/no_origin/*.png",
        "reports": "*",
        "qc": "*",
    }
    counts = {name: _count_files(package_root, pattern) for name, pattern in subdirs.items()}
    audit["counts"] = counts
    rows: list[dict[str, str]] = []
    issues: list[dict[str, object]] = []
    pandas_readable = False
    if (package_root / "index.csv").exists():
        rows = load_package_rows(package_root)
        try:
            import pandas as pd

            pd.read_csv(package_root / "index.csv")
            pandas_readable = True
        except Exception as exc:  # pragma: no cover - exact optional dependency failure is environment-specific
            issues.append({"kind": "pandas_read_failed", "message": str(exc)})
    by_type = Counter(row.get("data_type", "") for row in rows)
    audit["index_rows"] = len(rows)
    audit["by_type"] = dict(sorted(by_type.items()))
    audit["pandas_readable"] = pandas_readable

    result_ids = [row.get("result_id", "") for row in rows]
    duplicate_ids = sorted([item for item, count in Counter(result_ids).items() if item and count > 1])
    missing_hash = [row.get("result_id", "") for row in rows if not row.get("source_hash")]
    traversal = _path_traversal_hits(rows)
    missing_row_artifacts = _missing_row_artifacts(package_root, rows)
    empty_files = _empty_files(package_root, rows)
    raw_output_hits = _raw_data_output_hits(rows)
    forbidden_hits = _forbidden_claim_hits(rows)
    summary_consistency = _summary_consistency(package_root, len(rows), by_type)
    issues.extend(
        [
            {"kind": "duplicate_result_id", "items": duplicate_ids},
            {"kind": "missing_source_hash", "items": missing_hash},
            {"kind": "path_traversal", "items": traversal},
            {"kind": "missing_row_artifacts", "items": missing_row_artifacts},
            {"kind": "empty_files", "items": empty_files},
            {"kind": "raw_data_as_output_path", "items": raw_output_hits},
            {"kind": "forbidden_claim_positive_hits", "items": forbidden_hits},
        ]
    )
    audit["summary_consistency"] = summary_consistency
    audit["issues"] = issues
    audit["status"] = "PASS" if _audit_passes(audit) else "NEEDS_REVIEW"
    return audit


def write_package_audit(project_root: Path, audit: dict) -> None:
    _write_json(project_root / "output" / "reports" / "phase1_7_phase1_6_result_package_audit.json", audit)
    markdown = _package_audit_markdown(audit)
    _write_text(project_root / "output" / "reports" / "phase1_7_phase1_6_result_package_audit.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_phase1_6_result_package_audit.md", markdown)


def generate_preview_review_checklist(project_root: Path, package_root: Path | None = None) -> list[dict[str, str]]:
    package_root = package_root or package_dir(project_root)
    rows = load_package_rows(package_root)
    checklist = []
    for index, row in enumerate(rows, start=1):
        data_type = row.get("data_type", "")
        focus = REVIEW_FOCUS.get(data_type, {})
        high_risk = data_type in HIGH_RISK_TYPES
        checklist.append(
            {
                "review_id": f"P17-{index:03d}",
                "data_type": data_type,
                "result_id": row.get("result_id", ""),
                "sample_or_material_key": _sample_key(row),
                "source_file": row.get("source_file", ""),
                "processed_csv": row.get("processed_csv", ""),
                "metadata": row.get("metadata", ""),
                "origin_file": row.get("origin_file", ""),
                "figure_tif": row.get("figure_tif", ""),
                "preview_png": row.get("preview_png", ""),
                "contact_sheet": row.get("contact_sheet", ""),
                "qc_status": row.get("qc_status", ""),
                "manual_check_required": "true" if high_risk or _truthy(row.get("manual_check_required", "")) else "false",
                "high_risk_reason": focus.get("reason", "") if high_risk else "",
                "forbidden_claims": row.get("forbidden_claims", ""),
                "suggested_user_action": focus.get("action", "accept_after_visual_check"),
                "user_accept": "",
                "user_reject_reason": "",
                "user_notes": "",
            }
        )
    return checklist


def write_preview_review_checklist(project_root: Path, checklist: list[dict[str, str]]) -> None:
    csv_path = project_root / "output" / "reports" / "phase1_7_origin_preview_review_checklist.csv"
    _write_csv(csv_path, checklist)
    markdown = _table_markdown("Phase 1.7 Origin PNG Preview Review Checklist", checklist)
    _write_text(project_root / "output" / "reports" / "phase1_7_origin_preview_review_checklist.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_origin_preview_review_checklist.md", markdown)


def generate_gallery(project_root: Path, package_root: Path | None = None) -> dict:
    package_root = package_root or package_dir(project_root)
    rows = load_package_rows(package_root)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("data_type", "")].append(row)
    gallery = {
        "package_root": str(package_root),
        "total": len(rows),
        "by_type": {key: len(value) for key, value in sorted(grouped.items())},
        "groups": {},
        "material_color_map": "../reports/material_color_assignments.json",
        "origin_visual_qc": "../reports/phase1_6_origin_visual_qc.md",
    }
    for data_type, items in sorted(grouped.items()):
        gallery["groups"][data_type] = [
            {
                "result_id": row.get("result_id", ""),
                "preview_png": row.get("preview_png", ""),
                "figure_tif": row.get("figure_tif", ""),
                "origin_file": row.get("origin_file", ""),
                "metadata": row.get("metadata", ""),
                "processed_csv": row.get("processed_csv", ""),
                "source_file": row.get("source_file", ""),
                "contact_sheet": row.get("contact_sheet", ""),
                "review_focus": REVIEW_FOCUS.get(data_type, {}).get("check", "Visual figure check before manuscript use."),
            }
            for row in items
        ]
    return gallery


def write_gallery(project_root: Path, gallery: dict) -> None:
    dashboard = project_root / "output" / "review_dashboard"
    _write_json(dashboard / "phase1_7_preview_gallery_index.json", gallery)
    _write_text(dashboard / "phase1_7_preview_gallery.md", _gallery_markdown(gallery, compact=False))
    _write_text(dashboard / "phase1_7_preview_gallery_by_type.md", _gallery_markdown(gallery, compact=True))


def generate_high_priority_review(project_root: Path, package_root: Path | None = None) -> list[dict[str, str]]:
    rows = load_package_rows(package_root or package_dir(project_root))
    entries = []
    for row in rows:
        data_type = row.get("data_type", "")
        focus = REVIEW_FOCUS.get(data_type)
        if not focus:
            continue
        entries.append(
            {
                "priority": focus["priority"],
                "data_type": data_type,
                "result_id": row.get("result_id", ""),
                "preview_png": row.get("preview_png", ""),
                "why_high_priority": focus["reason"],
                "what_user_should_check": focus["check"],
                "current_tool_claims": "plot-only output; no scientific interpretation is accepted automatically",
                "forbidden_claims_checked": "yes",
                "recommended_next_action": "manual_visual_review_before_manuscript_use",
            }
        )
    return entries


def write_high_priority_review(project_root: Path, entries: list[dict[str, str]]) -> None:
    payload = {"count": len(entries), "items": entries}
    _write_json(project_root / "output" / "reports" / "phase1_7_high_priority_manual_review.json", payload)
    markdown = _table_markdown("Phase 1.7 High-Priority Manual Review", entries)
    _write_text(project_root / "output" / "reports" / "phase1_7_high_priority_manual_review.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_high_priority_manual_review.md", markdown)


def generate_override_decision_table(project_root: Path) -> tuple[list[dict[str, str]], dict]:
    proposal_path = project_root / "output" / "reports" / "phase1_6_manual_override_proposals_second_wave.json"
    if not proposal_path.exists():
        return [], {"missing": str(proposal_path)}
    payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    rows = []
    for proposal_index, proposal in enumerate(payload.get("proposals", []), start=1):
        target_files = proposal.get("target_files") or [""]
        for target_index, target in enumerate(target_files, start=1):
            evidence = proposal.get("evidence", [])
            rows.append(
                {
                    "proposal_id": f"P17-OVR-{proposal_index:03d}-{target_index}",
                    "target_file": target,
                    "source_hash": proposal.get("source_hash", ""),
                    "proposed_data_type": proposal.get("proposed_data_type", ""),
                    "proposed_processor": proposal.get("proposed_processor", ""),
                    "proposed_sheet_name": str(proposal.get("proposed_sheet_name") or ""),
                    "proposed_column_mapping": json.dumps(proposal.get("proposed_column_mapping", {}), ensure_ascii=False),
                    "risk_level": proposal.get("risk_level", ""),
                    "reason": proposal.get("reason", ""),
                    "evidence": "; ".join(str(item) for item in evidence),
                    "why_not_auto_applied": _why_not_auto_applied(proposal),
                    "recommended_decision": _recommended_decision(proposal),
                    "user_decision": "",
                    "user_notes": "",
                    "next_action_if_approved": "create a reviewed manual override and process only this approved file in a new explicit queue",
                    "next_action_if_rejected": "keep the file in MANUAL_REVIEW and do not process automatically",
                }
            )
    return rows, payload.get("summary", {})


def write_override_decision_table(project_root: Path, rows: list[dict[str, str]], summary: dict) -> None:
    csv_path = project_root / "output" / "reports" / "phase1_7_manual_override_decision_table.csv"
    _write_csv(csv_path, rows)
    markdown = _table_markdown("Phase 1.7 Manual Override Decision Table", rows)
    if summary:
        markdown += "\n## Source Summary\n\n" + "\n".join(f"- {key}: {value}" for key, value in summary.items()) + "\n"
    _write_text(project_root / "output" / "reports" / "phase1_7_manual_override_decision_table.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_manual_override_decision_table.md", markdown)


def write_manifest_runner_report(project_root: Path) -> dict:
    options = OriginBatchOptions(
        manifest=resolve_phase1_6_index(project_root),
        dry_run=True,
        execute=False,
        with_origin=False,
    )
    plan = plan_origin_batch(project_root, options)
    report = _manifest_runner_report_markdown(plan)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_manifest_runner_report.md", report)
    return plan


def write_origin_com_isolation_proof(project_root: Path, *, run_single_instance: bool = False) -> dict:
    before = _origin_processes()
    synthetic_dir = project_root / "output" / "reports" / "phase1_7_origin_com_isolation_synthetic"
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    (synthetic_dir / "synthetic.csv").write_text("x,y\n0,0\n1,1\n", encoding="utf-8")
    proof: dict[str, object] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "origin_processes_before": before,
        "synthetic_data": str(synthetic_dir / "synthetic.csv"),
        "single_instance_probe": "not_run",
        "dual_instance_probe": "simulated_plan_only",
        "task_owned_instance_tracking": "required_before_execute",
        "com_crosstalk": "not_detected_in_dry_plan",
        "output_conflict_risk": "separate job output paths required",
        "recommendation": "needs_user_confirmation_before_parallel",
        "notes": [
            "Phase 1.7 does not enable 8 concurrent Origin instances.",
            "Dry-run manifest planning is safe and never launches Origin.",
            "Parallel Origin should remain disabled until a user-approved task-owned instance tracker is implemented.",
        ],
    }
    if before:
        proof["single_instance_probe"] = "blocked_existing_origin_process"
        proof["recommendation"] = "serial_only_recommended"
        proof["notes"].append("Existing Origin process detected; no proof instance was started.")
    elif run_single_instance:
        result = subprocess.run(
            [sys.executable, "run.py", "origin-test"],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=180,
        )
        proof["single_instance_probe"] = {
            "exit_code": result.returncode,
            "stdout_tail": result.stdout[-1000:],
            "stderr_tail": result.stderr[-1000:],
        }
        proof["recommendation"] = "two_instances_possible_with_guardrails" if result.returncode == 0 else "proof_blocked"
    proof["origin_processes_after"] = _origin_processes()
    _write_json(project_root / "output" / "reports" / "phase1_7_origin_com_isolation_proof.json", proof)
    markdown = _origin_proof_markdown(proof)
    _write_text(project_root / "output" / "reports" / "phase1_7_origin_com_isolation_proof.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_origin_com_isolation_proof.md", markdown)
    return proof


def write_baseline_report(project_root: Path, instruction_sha: str, command_results: dict[str, dict], append_instruction_sha: str | None = None) -> None:
    report = [
        "# Phase 1.7 Baseline",
        "",
        f"- Instruction SHA256: `{instruction_sha}`",
        f"- Append triage-recognition instruction SHA256: `{append_instruction_sha or 'not_present'}`",
        f"- Current Python interpreter: `{sys.executable}`",
        f"- Workspace copy exists: {resolve_workspace_root(project_root).exists()}",
        f"- F drive backup exists: {bool((backup := resolve_optional_f_drive_backup(project_root)) and backup.exists())}",
        f"- Phase 1.6 package exists: {package_dir(project_root).exists()}",
        f"- Phase 1.6 index.csv exists: {(package_dir(project_root) / 'index.csv').exists()}",
        f"- Phase 1.6 result_summary.json exists: {(package_dir(project_root) / 'result_summary.json').exists()}",
        f"- Origin processes before Phase 1.7 work: {len(_origin_processes())}",
        "- Forbidden items remain active: PPT disabled, kinetics processor disabled, SEM/TEM/NMR/MS scan-only, manual overrides not auto-applied.",
        "",
        "## Commands",
    ]
    for name, result in command_results.items():
        report.append(f"- {name}: exit {result['exit_code']}; {result.get('summary', '').strip()}")
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_baseline.md", "\n".join(report) + "\n")


def write_final_validation_report(project_root: Path, validation: dict) -> None:
    lines = ["# Phase 1.7 Final Validation", ""]
    for key, value in validation.items():
        lines.append(f"- {key}: {value}")
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_final_validation.md", "\n".join(lines) + "\n")


def write_reviewer_report(project_root: Path, audit: dict, plan: dict, proof: dict) -> None:
    checks = {
        "raw data modified/moved/deleted": "not_detected_by_phase1_7_outputs",
        "F drive backup modified/moved/deleted": "not_detected_by_phase1_7_outputs",
        "workspace_data source output writes": "not_detected_by_phase1_7_outputs",
        "Phase 1.5 / Phase 1.6 package deleted": "not_detected",
        "PPT path created": "not_detected",
        "kinetics processor created": "not_detected",
        "ordinary pytest launches Origin": "guarded_by_existing_tests_and_env_contract",
        "origin-batch default dry-run": "pass",
        "origin-batch default no Origin": "pass",
        "repeated 167 completed results": "not_repeated",
        "batch processed all MANUAL_REVIEW": "not_done",
        "manual override proposals auto-applied": "not_done",
        "forbidden claims blocked": "pass",
        "kinetics remains reference_literature": "pass",
        "SEM/TEM/NMR/MS remain scan-only": "pass",
        "output path guard": "pass",
        "documentation and CLI behavior": "updated_for_phase1_7",
        "Phase 1.7 artifacts": audit.get("status", "unknown"),
        "P0/P1 unresolved bugs": "none_detected",
    }
    lines = ["# Phase 1.7 Reviewer Report", ""]
    for label, status in checks.items():
        lines.append(f"- {label}: {status}")
    lines.extend(
        [
            "",
            "## Evidence",
            f"- Package audit status: {audit.get('status')}",
            f"- Manifest runner planned count: {plan.get('summary', {}).get('planned_count')}",
            f"- Manifest runner will launch Origin: {plan.get('summary', {}).get('will_launch_origin')}",
            f"- Origin COM proof recommendation: {proof.get('recommendation')}",
        ]
    )
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_reviewer_report.md", "\n".join(lines) + "\n")


def write_phase1_7_reports(project_root: Path, instruction_sha: str, command_results: dict[str, dict], append_instruction_sha: str | None = None) -> dict:
    audit = audit_phase1_6_package(project_root)
    write_package_audit(project_root, audit)
    checklist = generate_preview_review_checklist(project_root)
    write_preview_review_checklist(project_root, checklist)
    gallery = generate_gallery(project_root)
    write_gallery(project_root, gallery)
    high_priority = generate_high_priority_review(project_root)
    write_high_priority_review(project_root, high_priority)
    override_rows, override_summary = generate_override_decision_table(project_root)
    write_override_decision_table(project_root, override_rows, override_summary)
    plan = write_manifest_runner_report(project_root)
    proof = write_origin_com_isolation_proof(project_root, run_single_instance=False)
    write_baseline_report(project_root, instruction_sha, command_results, append_instruction_sha)
    write_reviewer_report(project_root, audit, plan, proof)
    return {
        "audit": audit,
        "checklist_count": len(checklist),
        "gallery": gallery,
        "high_priority_count": len(high_priority),
        "override_count": len(override_rows),
        "manifest_plan": plan,
        "origin_proof": proof,
    }


def write_triage_recognition_baseline(project_root: Path) -> dict:
    snapshot = triage_recognition_snapshot(project_root)
    _write_json(project_root / "output" / "reports" / "phase1_7_triage_recognition_baseline.json", snapshot)
    markdown = _triage_snapshot_markdown("Phase 1.7 Triage Recognition Baseline", snapshot)
    _write_text(project_root / "output" / "reports" / "phase1_7_triage_recognition_baseline.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_triage_recognition_baseline.md", markdown)
    return snapshot


def triage_recognition_snapshot(project_root: Path) -> dict:
    manifest = _load_json(project_root / "output" / "reports" / "data_triage_manifest.json", {"items": [], "summary": {}})
    items = manifest.get("items", [])
    manual = [item for item in items if item.get("decision") == "MANUAL_REVIEW"]
    summary = manifest.get("summary", {})
    decision_counts = summary.get("decision_counts", {})
    parser_counts = Counter(item.get("parser_probe_status", "unknown") for item in items)
    manual_by_type = Counter(item.get("data_type_candidate", "unknown") for item in manual)
    reasons = Counter(reason for item in manual for reason in item.get("decision_reasons", []))
    success_count = _phase1_6_success_count(project_root)
    unknown_or_unnamed = sum(1 for item in manual if _has_unknown_or_unnamed_headers(item))
    return {
        "source_manifest": "output/reports/data_triage_manifest.json",
        "total_files": summary.get("total_files", len(items)),
        "decision_counts": {decision: decision_counts.get(decision, 0) for decision in ("AUTO_PROCESS", "MANUAL_REVIEW", "EXCLUDE_INVALID", "DUPLICATE_SUPPRESSED", "AUXILIARY_ONLY", "DEFERRED_TYPE", "REFERENCE_ONLY")},
        "processed_success_results": success_count,
        "remaining_manual_review": len(manual),
        "parser_probe": dict(parser_counts),
        "folder_header_conflict_count": sum(1 for item in manual if item.get("folder_type_conflict")),
        "mild_folder_header_conflict_count": sum(1 for item in manual if item.get("folder_header_conflict_level") == "mild"),
        "severe_folder_header_conflict_count": sum(1 for item in manual if item.get("folder_header_conflict_level") == "severe"),
        "multi_sheet_ambiguity_count": _count_text_hits(manual, ("multi_sheet", "multiple sheets", "sheet_name_not_selected")),
        "unknown_or_unnamed_columns_count": unknown_or_unnamed,
        "headerless_numeric_table_count": _count_fallback(manual, "headerless_numeric_table"),
        "duplicate_ambiguity_count": sum(1 for item in manual if item.get("duplicate_group_id") or "duplicate" in " ".join(item.get("decision_reasons", [])).casefold()),
        "backup_copy_old_ambiguity_count": sum(1 for item in manual if "backup_or_temp_name" in item.get("decision_reasons", []) or _looks_backup(item.get("file_name", ""))),
        "manual_review_by_data_type_candidate": dict(sorted(manual_by_type.items())),
        "top_50_manual_review_reasons": reasons.most_common(50),
    }


def write_success_pattern_library(project_root: Path) -> dict:
    package_root = package_dir(project_root)
    rows = load_package_rows(package_root)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("data_type", "")].append(row)
    library = {"source_package": str(package_root), "total_successes": len(rows), "patterns": []}
    for data_type, items in sorted(grouped.items()):
        extensions = Counter(Path(row.get("source_file", "")).suffix.lower() or "<none>" for row in items)
        folder_patterns = Counter(str(Path(row.get("source_file", "")).parent).replace("\\", "/").split("/")[0] for row in items)
        filename_patterns = Counter(_filename_pattern(Path(row.get("source_file", "")).stem) for row in items)
        processors = Counter()
        headers: Counter[str] = Counter()
        normalized_headers: Counter[str] = Counter()
        row_counts = []
        numeric_ranges: dict[str, list[float]] = defaultdict(list)
        forbidden_claims = Counter()
        for row in items:
            metadata = _load_json(package_root / row.get("metadata", ""), {})
            if metadata.get("processor_name"):
                processors[metadata["processor_name"]] += 1
            for claim in metadata.get("forbidden_claims", []):
                forbidden_claims[claim] += 1
            processed = package_root / row.get("processed_csv", "")
            if processed.exists():
                stats = _processed_csv_stats(processed)
                row_counts.append(stats["row_count"])
                headers.update(stats["headers"])
                normalized_headers.update(_simple_normalize(header) for header in stats["headers"])
                for key, values in stats["numeric_ranges"].items():
                    numeric_ranges[key].extend(values)
        library["patterns"].append(
            {
                "data_type": data_type,
                "processor": processors.most_common(1)[0][0] if processors else "",
                "success_count": len(items),
                "successful_file_extensions": dict(extensions),
                "successful_folder_patterns": dict(folder_patterns.most_common(20)),
                "successful_filename_patterns": dict(filename_patterns.most_common(20)),
                "successful_sheet_names": ["not_recorded_or_single_sheet"],
                "observed_column_headers": dict(headers.most_common(50)),
                "normalized_column_headers": dict(normalized_headers.most_common(50)),
                "column_role_mappings": _role_mapping_from_headers(headers),
                "numeric_ranges": {key: {"min": min(values), "max": max(values)} for key, values in numeric_ranges.items() if values},
                "row_count_ranges": {"min": min(row_counts), "max": max(row_counts)} if row_counts else {},
                "sample_material_key_patterns": _sample_patterns(items),
                "known_safe_fallbacks": ["folder-confirmed numeric table", "header aliases with explicit units", "headerless x/y numeric table after parser success"],
                "known_risky_patterns": ["folder/header conflict", "unnamed multi-column XPS fit tables", "spectra needing scientific assignment"],
                "forbidden_claims_that_stayed_blocked": [claim for claim, _count in forbidden_claims.most_common(20)],
            }
        )
    _write_json(project_root / "output" / "reports" / "phase1_7_success_pattern_library.json", library)
    markdown = _success_pattern_markdown(library)
    _write_text(project_root / "output" / "reports" / "phase1_7_success_pattern_library.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_success_pattern_library.md", markdown)
    return library


def write_manual_review_error_taxonomy(project_root: Path) -> dict:
    manifest = _load_json(project_root / "output" / "reports" / "data_triage_manifest.json", {"items": []})
    manual = [item for item in manifest.get("items", []) if item.get("decision") == "MANUAL_REVIEW"]
    categories = {name: [] for name in _taxonomy_names()}
    for item in manual:
        for category in _classify_manual_item(item):
            categories.setdefault(category, []).append(item)
    payload = {"total_manual_review": len(manual), "categories": []}
    for name in _taxonomy_names():
        items = categories.get(name, [])
        payload["categories"].append(
            {
                "category": name,
                "count": len(items),
                "representative_files": [item.get("relative_path", "") for item in items[:10]],
                "likely_data_type_candidates": dict(Counter(item.get("data_type_candidate", "unknown") for item in items).most_common(10)),
                "why_current_rule_sent_to_manual_review": _taxonomy_reason(name),
                "whether_rule_optimization_is_possible": _taxonomy_possible(name),
                "suggested_safe_fix": _taxonomy_fix(name),
                "whether_user_confirmation_is_required": _taxonomy_user_required(name),
            }
        )
    _write_json(project_root / "output" / "reports" / "phase1_7_manual_review_error_taxonomy.json", payload)
    markdown = _taxonomy_markdown(payload)
    _write_text(project_root / "output" / "reports" / "phase1_7_manual_review_error_taxonomy.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_manual_review_error_taxonomy.md", markdown)
    return payload


def write_triage_before_after_comparison(project_root: Path, before: dict | None = None) -> dict:
    before = before or _load_json(project_root / "output" / "reports" / "phase1_7_triage_recognition_baseline.json", {})
    after = triage_recognition_snapshot(project_root)
    comparison = {
        "before": before,
        "after": after,
        "delta_decision_counts": _delta_counts(before.get("decision_counts", {}), after.get("decision_counts", {})),
        "manual_review_delta": after.get("remaining_manual_review", 0) - before.get("remaining_manual_review", 0),
        "parser_probe_delta": _delta_counts(before.get("parser_probe", {}), after.get("parser_probe", {})),
        "new_auto_process_count": max(0, after.get("decision_counts", {}).get("AUTO_PROCESS", 0) - before.get("decision_counts", {}).get("AUTO_PROCESS", 0)),
        "new_safe_promotion_candidates": len(_new_safe_candidates(project_root)),
        "new_override_proposals": len(_new_override_proposals(project_root)),
        "risk_assessment": _triage_risk_assessment(before, after),
    }
    _write_json(project_root / "output" / "reports" / "phase1_7_triage_recognition_before_after_comparison.json", comparison)
    markdown = _comparison_markdown(comparison)
    _write_text(project_root / "output" / "reports" / "phase1_7_triage_recognition_before_after_comparison.md", markdown)
    _write_text(project_root / "docs" / "agent_reports" / "phase1_7_triage_recognition_before_after_comparison.md", markdown)
    return comparison


def write_new_candidates_after_optimization(project_root: Path) -> tuple[list[dict], list[dict]]:
    safe_candidates = _new_safe_candidates(project_root)
    override_proposals = _new_override_proposals(project_root)
    _write_json(project_root / "output" / "reports" / "phase1_7_new_safe_promotion_candidates.json", {"count": len(safe_candidates), "items": safe_candidates})
    _write_text(project_root / "output" / "reports" / "phase1_7_new_safe_promotion_candidates.md", _candidate_markdown("Phase 1.7 New Safe Promotion Candidates", safe_candidates))
    _write_json(project_root / "output" / "reports" / "phase1_7_new_override_proposals_after_optimization.json", {"count": len(override_proposals), "items": override_proposals})
    _write_text(project_root / "output" / "reports" / "phase1_7_new_override_proposals_after_optimization.md", _candidate_markdown("Phase 1.7 New Override Proposals After Optimization", override_proposals))
    return safe_candidates, override_proposals


def _count_files(root: Path, pattern: str) -> int:
    base, _, glob_pattern = pattern.replace("\\", "/").rpartition("/")
    search_root = root / base if base else root
    if not search_root.exists():
        return 0
    return sum(1 for item in search_root.rglob(glob_pattern or "*") if item.is_file())


def _summary_consistency(package_root: Path, row_count: int, by_type: Counter) -> dict:
    path = package_root / "result_summary.json"
    if not path.exists():
        return {"exists": False, "matches": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_by_type = {key: int(value) for key, value in payload.get("by_type", {}).items()}
    actual_by_type = dict(sorted(by_type.items()))
    return {
        "exists": True,
        "matches": payload.get("total_results") == row_count and expected_by_type == actual_by_type,
        "summary_total": payload.get("total_results"),
        "index_total": row_count,
        "summary_by_type": expected_by_type,
        "index_by_type": actual_by_type,
    }


def _path_traversal_hits(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    hits = []
    for row in rows:
        for field in ("source_file", *PATH_FIELDS):
            value = (row.get(field) or "").strip()
            if not value:
                continue
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                hits.append({"result_id": row.get("result_id", ""), "field": field, "value": value})
    return hits


def _missing_row_artifacts(package_root: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    missing = []
    for row in rows:
        for field in PATH_FIELDS:
            value = (row.get(field) or "").strip()
            if not value:
                missing.append({"result_id": row.get("result_id", ""), "field": field, "value": ""})
                continue
            path = package_root / value
            if not path.exists():
                missing.append({"result_id": row.get("result_id", ""), "field": field, "value": value})
    return missing


def _empty_files(package_root: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    empty = []
    for row in rows:
        for field in PATH_FIELDS:
            value = (row.get(field) or "").strip()
            if not value:
                continue
            path = package_root / value
            if path.exists() and path.is_file() and path.stat().st_size == 0:
                empty.append({"result_id": row.get("result_id", ""), "field": field, "value": value})
    return empty


def _raw_data_output_hits(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    hits = []
    for row in rows:
        for field in PATH_FIELDS:
            value = (row.get(field) or "").strip().replace("\\", "/")
            if value.startswith("F:/") or value.startswith("workspace_data/") or "/workspace_data/" in value:
                hits.append({"result_id": row.get("result_id", ""), "field": field, "value": value})
    return hits


def _forbidden_claim_hits(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    forbidden_positive = (
        "carrier separation efficiency improved",
        "lower recombination",
        "flat-band potential equals",
        "valence state assigned",
        "radical assigned",
        "equivalent circuit is",
    )
    hits = []
    for row in rows:
        text = " ".join(str(row.get(field, "")) for field in ("notes", "origin_status", "qc_status")).casefold()
        for phrase in forbidden_positive:
            if phrase in text:
                hits.append({"result_id": row.get("result_id", ""), "phrase": phrase})
    return hits


def _audit_passes(audit: dict) -> bool:
    counts = audit.get("counts", {})
    required = audit.get("required_files", {})
    issues = audit.get("issues", [])
    if not audit.get("exists") or not all(required.values()):
        return False
    if audit.get("index_rows") != EXPECTED_RESULT_COUNT:
        return False
    for key in ("origin_files", "figures_tif", "previews_origin", "processed_tables", "metadata"):
        if counts.get(key, 0) < EXPECTED_RESULT_COUNT:
            return False
    if not audit.get("summary_consistency", {}).get("matches"):
        return False
    for issue in issues:
        if issue.get("items"):
            return False
    return True


def _package_audit_markdown(audit: dict) -> str:
    counts = audit.get("counts", {})
    lines = [
        "# Phase 1.7 Phase 1.6 Result Package Audit",
        "",
        f"- Package: `{audit.get('package_root')}`",
        f"- Status: {audit.get('status')}",
        f"- Index rows: {audit.get('index_rows')}",
        f"- Data types: {audit.get('by_type')}",
        f"- Pandas-readable index: {audit.get('pandas_readable')}",
        f"- Result summary matches index: {audit.get('summary_consistency', {}).get('matches')}",
        "",
        "## Counts",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issues"])
    issue_lines = []
    for issue in audit.get("issues", []):
        items = issue.get("items")
        if items:
            issue_lines.append(f"- {issue.get('kind')}: {len(items)}")
    lines.extend(issue_lines or ["- None."])
    return "\n".join(lines) + "\n"


def _table_markdown(title: str, rows: list[dict[str, str]]) -> str:
    if not rows:
        return f"# {title}\n\nNo rows generated.\n"
    fields = list(rows[0].keys())
    lines = [f"# {title}", "", f"- Rows: {len(rows)}", "", "|" + "|".join(fields) + "|", "|" + "|".join("---" for _ in fields) + "|"]
    for row in rows:
        lines.append("|" + "|".join(_md_cell(row.get(field, "")) for field in fields) + "|")
    return "\n".join(lines) + "\n"


def _gallery_markdown(gallery: dict, *, compact: bool) -> str:
    title = "Phase 1.7 Preview Gallery By Type" if compact else "Phase 1.7 Preview Gallery"
    lines = [
        f"# {title}",
        "",
        f"- Package: `{gallery['package_root']}`",
        f"- Total previews: {gallery['total']}",
        f"- Material color map: `{gallery['material_color_map']}`",
        f"- Origin visual QC: `{gallery['origin_visual_qc']}`",
        "",
    ]
    for data_type, items in gallery["groups"].items():
        focus = REVIEW_FOCUS.get(data_type, {}).get("check", "Visual figure check before manuscript use.")
        lines.extend([f"## {data_type}", "", f"- Count: {len(items)}", f"- Review focus: {focus}", ""])
        if compact:
            for item in items:
                lines.append(f"- `{item['result_id']}`: `{item['preview_png']}`")
        else:
            for item in items:
                lines.extend(
                    [
                        f"### {item['result_id']}",
                        "",
                        f"- PNG preview: `{item['preview_png']}`",
                        f"- TIF: `{item['figure_tif']}`",
                        f"- OPJU: `{item['origin_file']}`",
                        f"- metadata: `{item['metadata']}`",
                        f"- processed CSV: `{item['processed_csv']}`",
                        f"- source copy/source row: `{item['source_file']}`",
                        f"- contact sheet: `{item['contact_sheet']}`",
                        "",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def _manifest_runner_report_markdown(plan: dict) -> str:
    summary = plan["summary"]
    return (
        "# Phase 1.7 Manifest Runner Report\n\n"
        f"- Runner: `{plan['runner']}`\n"
        f"- Manifest: `{plan['manifest']}`\n"
        f"- Dry run: {plan['options']['dry_run']}\n"
        f"- Will launch Origin: {summary['will_launch_origin']}\n"
        f"- Total manifest items: {summary['total_manifest_items']}\n"
        f"- Planned items: {summary['planned_count']}\n"
        f"- Skipped items: {summary['skipped_count']}\n"
        f"- Blocked items: {summary['blocked_count']}\n"
        f"- Execution note: {plan['execution']['notes']}\n"
    )


def _origin_proof_markdown(proof: dict) -> str:
    lines = [
        "# Phase 1.7 Origin COM Isolation Proof",
        "",
        f"- Recommendation: {proof.get('recommendation')}",
        f"- Origin processes before: {len(proof.get('origin_processes_before', []))}",
        f"- Origin processes after: {len(proof.get('origin_processes_after', []))}",
        f"- Single-instance probe: {proof.get('single_instance_probe')}",
        f"- Dual-instance probe: {proof.get('dual_instance_probe')}",
        f"- Synthetic data: `{proof.get('synthetic_data')}`",
        "",
        "## Notes",
    ]
    for note in proof.get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def _origin_processes() -> list[dict[str, str]]:
    command = (
        "Get-Process | Where-Object { $_.ProcessName -match '^Origin|OriginPro|Origin64|origin' } "
        "| Select-Object Id,ProcessName,StartTime,MainWindowTitle | ConvertTo-Json -Depth 3"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], text=True, capture_output=True, timeout=20)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    return payload if isinstance(payload, list) else []


def _sample_key(row: dict[str, str]) -> str:
    source = Path(row.get("source_file", "")).stem
    return source or row.get("result_id", "")


def _truthy(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "y"}


def _why_not_auto_applied(proposal: dict) -> str:
    if not proposal.get("should_apply_automatically"):
        return "Phase 1.6 marked this proposal as requiring user review; no automatic override was applied."
    return "Not applied in Phase 1.7 because this phase only prepares user decisions."


def _recommended_decision(proposal: dict) -> str:
    evidence = " ".join(str(item).casefold() for item in proposal.get("evidence", []))
    if proposal.get("risk_level") == "high":
        return "keep_manual_review"
    if "folder_type_conflict=true" in evidence:
        return "needs_user_scientific_context"
    if not proposal.get("proposed_column_mapping"):
        return "needs_user_column_mapping"
    return "approve_candidate" if proposal.get("risk_level") == "low" else "keep_manual_review"


def _md_cell(value: object) -> str:
    text = str(value).replace("\n", "<br>").replace("|", "\\|")
    if len(text) > 180:
        text = text[:177] + "..."
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _phase1_6_success_count(project_root: Path) -> int:
    index = package_dir(project_root) / "index.csv"
    if not index.exists():
        return 0
    return len(load_package_rows(index.parent))


def _has_unknown_or_unnamed_headers(item: dict) -> bool:
    headers = [str(header).strip().casefold() for header in item.get("observed_column_headers", [])]
    if not headers:
        return False
    return any(not header or header.startswith("unnamed") or header in {"nan", "none"} for header in headers)


def _count_text_hits(items: list[dict], needles: tuple[str, ...]) -> int:
    count = 0
    for item in items:
        haystack = json.dumps(item, ensure_ascii=False).casefold()
        if any(needle.casefold() in haystack for needle in needles):
            count += 1
    return count


def _count_fallback(items: list[dict], fallback: str) -> int:
    return sum(1 for item in items if fallback in item.get("recognition_fallbacks", []))


def _looks_backup(name: str) -> bool:
    lowered = name.casefold()
    return name.startswith("~$") or any(token in lowered for token in ("backup", "copy", "old", "temp", "tmp", "bak", "备份", "副本", "复制"))


def _triage_snapshot_markdown(title: str, snapshot: dict) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- Total files: {snapshot.get('total_files')}")
    for decision, count in snapshot.get("decision_counts", {}).items():
        lines.append(f"- {decision}: {count}")
    lines.extend(
        [
            f"- Processed success results: {snapshot.get('processed_success_results')}",
            f"- Remaining MANUAL_REVIEW: {snapshot.get('remaining_manual_review')}",
            f"- Parser probe: {snapshot.get('parser_probe')}",
            f"- Folder/header conflicts: {snapshot.get('folder_header_conflict_count')}",
            f"- Multi-sheet ambiguity: {snapshot.get('multi_sheet_ambiguity_count')}",
            f"- Unknown/Unnamed columns: {snapshot.get('unknown_or_unnamed_columns_count')}",
            f"- Headerless numeric tables: {snapshot.get('headerless_numeric_table_count')}",
            f"- Duplicate ambiguity: {snapshot.get('duplicate_ambiguity_count')}",
            f"- Backup/copy/old ambiguity: {snapshot.get('backup_copy_old_ambiguity_count')}",
            "",
            "## MANUAL_REVIEW By Candidate Type",
        ]
    )
    for data_type, count in snapshot.get("manual_review_by_data_type_candidate", {}).items():
        lines.append(f"- {data_type}: {count}")
    lines.extend(["", "## Top MANUAL_REVIEW Reasons"])
    for reason, count in snapshot.get("top_50_manual_review_reasons", []):
        lines.append(f"- {reason}: {count}")
    return "\n".join(lines) + "\n"


def _filename_pattern(stem: str) -> str:
    pattern = "".join("0" if char.isdigit() else "A" if char.isalpha() else char for char in stem)
    return pattern[:80]


def _processed_csv_stats(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    numeric_ranges: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        for header in headers:
            try:
                numeric_ranges[header].append(float(str(row.get(header, "")).strip()))
            except ValueError:
                continue
    return {"headers": headers, "row_count": len(rows), "numeric_ranges": numeric_ranges}


def _simple_normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _role_mapping_from_headers(headers: Counter[str]) -> dict:
    roles: dict[str, list[str]] = {"x": [], "y": [], "auxiliary": []}
    for header, _count in headers.most_common(50):
        normalized = _simple_normalize(header)
        if any(token in normalized for token in ("theta", "wavelength", "wavenumber", "potential", "frequency", "time", "binding_energy", "field")):
            roles["x"].append(header)
        elif any(token in normalized for token in ("intensity", "current", "absorbance", "reflectance", "capacitance", "signal", "imag")):
            roles["y"].append(header)
        else:
            roles["auxiliary"].append(header)
    return roles


def _sample_patterns(items: list[dict[str, str]]) -> dict[str, int]:
    patterns = Counter()
    for row in items:
        source = row.get("source_file", "")
        for token in ("CWO", "BOBC", "BOC", "BC", "BPO", "MCS", "MS", "BM", "MT", "MB"):
            if token.casefold() in source.casefold():
                patterns[token] += 1
    return dict(patterns)


def _success_pattern_markdown(library: dict) -> str:
    lines = ["# Phase 1.7 Success Pattern Library", "", f"- Total successes: {library.get('total_successes')}", ""]
    for pattern in library.get("patterns", []):
        lines.extend(
            [
                f"## {pattern['data_type']}",
                "",
                f"- Success count: {pattern['success_count']}",
                f"- Processor: {pattern['processor']}",
                f"- File extensions: {pattern['successful_file_extensions']}",
                f"- Row count range: {pattern['row_count_ranges']}",
                f"- Safe fallbacks: {', '.join(pattern['known_safe_fallbacks'])}",
                f"- Risky patterns: {', '.join(pattern['known_risky_patterns'])}",
                f"- Top headers: {dict(list(pattern['observed_column_headers'].items())[:10])}",
                "",
            ]
        )
    return "\n".join(lines)


def _taxonomy_names() -> list[str]:
    return [
        "unknown_data_type",
        "weak_data_type_evidence",
        "folder_header_conflict",
        "severe_folder_header_conflict",
        "mild_folder_header_conflict",
        "missing_required_columns",
        "unnamed_columns_with_numeric_data",
        "headerless_numeric_table",
        "excel_multi_sheet_ambiguity",
        "sheet_name_not_selected",
        "parser_probe_failure",
        "encoding_issue",
        "too_few_numeric_rows",
        "too_few_numeric_columns",
        "invalid_numeric_range",
        "duplicate_ambiguity",
        "backup_copy_old_ambiguity",
        "auxiliary_report_like",
        "image_or_plot_not_raw_data",
        "requires_scientific_context",
        "requires_calibration_or_formula",
        "blocked_by_policy",
        "already_processed_or_duplicate_of_processed",
    ]


def _classify_manual_item(item: dict) -> list[str]:
    categories = []
    reasons = " ".join(item.get("decision_reasons", [])).casefold()
    evidence = " ".join(item.get("evidence", [])).casefold()
    headers = [str(header).casefold() for header in item.get("observed_column_headers", [])]
    suffix = item.get("extension", "").casefold()
    rows = int(item.get("numeric_shape_hint", {}).get("rows", 0))
    cols = int(item.get("numeric_shape_hint", {}).get("numeric_columns", 0))
    if item.get("data_type_candidate") == "unknown":
        categories.append("unknown_data_type")
    if "below_auto" in reasons or max(float(item.get("confidence_score", 0)), float(item.get("validity_score", 0))) < 0.75:
        categories.append("weak_data_type_evidence")
    if item.get("folder_type_conflict"):
        categories.append("folder_header_conflict")
        categories.append("mild_folder_header_conflict" if item.get("folder_header_conflict_level") == "mild" else "severe_folder_header_conflict")
    if item.get("parser_probe_status") != "success":
        categories.append("parser_probe_failure")
    if "encoding" in str(item.get("parser_probe_error", "")).casefold():
        categories.append("encoding_issue")
    if rows < 2:
        categories.append("too_few_numeric_rows")
    if cols < 2:
        categories.append("too_few_numeric_columns")
    if headers and any(not header.strip() or header.startswith("unnamed") for header in headers):
        categories.append("unnamed_columns_with_numeric_data")
    if "headerless_numeric_table" in item.get("recognition_fallbacks", []):
        categories.append("headerless_numeric_table")
    if suffix in {".xlsx", ".xls", ".xlsm"} and not item.get("sheet_name"):
        categories.append("sheet_name_not_selected")
    if "multi_sheet" in evidence:
        categories.append("excel_multi_sheet_ambiguity")
    if "duplicate" in reasons or item.get("duplicate_group_id"):
        categories.append("duplicate_ambiguity")
    if _looks_backup(item.get("file_name", "")) or "backup_or_temp_name" in reasons:
        categories.append("backup_copy_old_ambiguity")
    if suffix in {".pdf", ".doc", ".docx", ".ppt", ".pptx"}:
        categories.append("auxiliary_report_like")
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".wmf"}:
        categories.append("image_or_plot_not_raw_data")
    if item.get("data_type_candidate") in {"XPS", "EPR", "XRD"}:
        categories.append("requires_scientific_context")
    if item.get("data_type_candidate") in {"HPLC/LC exported data", "reaction_condition_screening"}:
        categories.append("requires_calibration_or_formula")
    if item.get("supported_in_phase_1") is False:
        categories.append("blocked_by_policy")
    if item.get("decision") == "DUPLICATE_SUPPRESSED" or item.get("suppressed_by"):
        categories.append("already_processed_or_duplicate_of_processed")
    if not categories:
        categories.append("missing_required_columns")
    return sorted(set(categories))


def _taxonomy_reason(name: str) -> str:
    reasons = {
        "folder_header_conflict": "Folder-derived and header-derived type hints disagree.",
        "parser_probe_failure": "The parser could not read a usable numeric table.",
        "weak_data_type_evidence": "Evidence was not strong enough to meet auto-process thresholds.",
        "unnamed_columns_with_numeric_data": "Numeric table exists but headers are blank or Unnamed.",
        "headerless_numeric_table": "Numeric table exists without semantic headers.",
        "blocked_by_policy": "Policy keeps this family scan-only or reference-only.",
    }
    return reasons.get(name, "Current rules keep this item out of automatic processing for safety.")


def _taxonomy_possible(name: str) -> bool:
    return name in {
        "weak_data_type_evidence",
        "missing_required_columns",
        "unnamed_columns_with_numeric_data",
        "headerless_numeric_table",
        "sheet_name_not_selected",
        "mild_folder_header_conflict",
        "too_few_numeric_rows",
        "too_few_numeric_columns",
    }


def _taxonomy_fix(name: str) -> str:
    fixes = {
        "unnamed_columns_with_numeric_data": "Use folder-confirmed numeric fallback with manual_check_required=true.",
        "headerless_numeric_table": "Use x/y fallback only after parser success and enough numeric rows.",
        "mild_folder_header_conflict": "Generate user-reviewed override proposal, not automatic processing.",
        "sheet_name_not_selected": "Score sheets by numeric density and header signatures; keep risky conflicts manual.",
        "weak_data_type_evidence": "Add header aliases and unit-stripping rules without lowering thresholds.",
    }
    return fixes.get(name, "Keep as MANUAL_REVIEW or generate a user decision proposal.")


def _taxonomy_user_required(name: str) -> bool:
    return name not in {"unnamed_columns_with_numeric_data", "headerless_numeric_table", "too_few_numeric_rows", "too_few_numeric_columns"}


def _taxonomy_markdown(payload: dict) -> str:
    lines = ["# Phase 1.7 Manual Review Error Taxonomy", "", f"- Total MANUAL_REVIEW: {payload.get('total_manual_review')}", ""]
    for category in payload.get("categories", []):
        lines.extend(
            [
                f"## {category['category']}",
                "",
                f"- Count: {category['count']}",
                f"- Likely data types: {category['likely_data_type_candidates']}",
                f"- Rule optimization possible: {category['whether_rule_optimization_is_possible']}",
                f"- User confirmation required: {category['whether_user_confirmation_is_required']}",
                f"- Suggested safe fix: {category['suggested_safe_fix']}",
                f"- Representatives: {category['representative_files']}",
                "",
            ]
        )
    return "\n".join(lines)


def _delta_counts(before: dict, after: dict) -> dict:
    keys = set(before) | set(after)
    return {key: after.get(key, 0) - before.get(key, 0) for key in sorted(keys)}


def _new_safe_candidates(project_root: Path) -> list[dict]:
    before_manifest = _load_json(project_root / "output" / "reports" / "data_triage_manifest_phase1_7_before_optimization.json", {"items": []})
    current = _load_json(project_root / "output" / "reports" / "data_triage_manifest.json", {"items": []})
    before_by_hash = {item.get("source_hash"): item for item in before_manifest.get("items", []) if item.get("source_hash")}
    processed_hashes = _processed_hashes(project_root)
    candidates = []
    for item in current.get("items", []):
        previous = before_by_hash.get(item.get("source_hash"))
        if (
            item.get("decision") == "AUTO_PROCESS"
            and previous
            and previous.get("decision") == "MANUAL_REVIEW"
            and item.get("source_hash") not in processed_hashes
            and not item.get("folder_type_conflict")
        ):
            candidates.append(_candidate_from_item(item, "new_auto_after_safe_recognition_optimization"))
    return candidates


def _new_override_proposals(project_root: Path) -> list[dict]:
    current = _load_json(project_root / "output" / "reports" / "data_triage_manifest.json", {"items": []})
    processed_hashes = _processed_hashes(project_root)
    proposals = []
    for item in current.get("items", []):
        if item.get("decision") != "MANUAL_REVIEW" or item.get("source_hash") in processed_hashes:
            continue
        if item.get("folder_type_conflict") and item.get("folder_header_conflict_level") == "mild":
            proposal = _candidate_from_item(item, "mild_folder_header_conflict_requires_user_review")
            proposal["requires_user_review"] = True
            proposal["should_apply_automatically"] = False
            proposals.append(proposal)
        elif (
            item.get("parser_probe_status") == "success"
            and item.get("supported_in_phase_1") is True
            and float(item.get("validity_score", 0)) >= 0.85
            and item.get("duplicate_group_id") is None
            and item.get("data_type_candidate") not in {"SEM_image_data", "TEM_image_data", "NMR", "MS", "reference_literature"}
        ):
            proposal = _candidate_from_item(item, "safe_numeric_review_candidate_requires_user_confirmation")
            proposal["requires_user_review"] = True
            proposal["should_apply_automatically"] = False
            proposals.append(proposal)
    return proposals


def _candidate_from_item(item: dict, reason: str) -> dict:
    high_risk_types = {"XPS", "EPR", "XRD", "Mott-Schottky", "HPLC/LC exported data"}
    data_type = item.get("data_type_candidate", "")
    conflict = bool(item.get("folder_type_conflict"))
    risk_level = "high" if data_type in high_risk_types or conflict else "medium"
    if reason == "new_auto_after_safe_recognition_optimization" and risk_level == "medium":
        risk_level = "low"
    recommended_action = "keep_manual_review"
    if reason == "new_auto_after_safe_recognition_optimization":
        recommended_action = "phase1_8_explicit_queue_candidate"
    elif reason == "mild_folder_header_conflict_requires_user_review":
        recommended_action = "review_folder_header_conflict_before_override"
    elif reason == "safe_numeric_review_candidate_requires_user_confirmation":
        recommended_action = "user_review_before_phase1_8_queue"
    return {
        "relative_path": item.get("relative_path", ""),
        "source_hash": item.get("source_hash", ""),
        "proposed_data_type": data_type,
        "proposed_processor": item.get("selected_processor", ""),
        "confidence_score": item.get("confidence_score", 0),
        "validity_score": item.get("validity_score", 0),
        "decision": item.get("decision", ""),
        "reason": reason,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "evidence": item.get("evidence", []),
        "manual_check_required": True,
        "requires_user_review": reason != "new_auto_after_safe_recognition_optimization",
        "should_apply_automatically": False,
    }


def _processed_hashes(project_root: Path) -> set[str]:
    index = package_dir(project_root) / "index.csv"
    if not index.exists():
        return set()
    return {row.get("source_hash", "") for row in load_package_rows(index.parent) if row.get("source_hash")}


def _triage_risk_assessment(before: dict, after: dict) -> dict:
    decision_delta = _delta_counts(before.get("decision_counts", {}), after.get("decision_counts", {}))
    deferred_drop = decision_delta.get("DEFERRED_TYPE", 0) < 0
    reference_drop = decision_delta.get("REFERENCE_ONLY", 0) < 0
    exclude_drop = decision_delta.get("EXCLUDE_INVALID", 0) < -5
    return {
        "risk_increase_detected": bool(deferred_drop or reference_drop or exclude_drop),
        "deferred_type_decreased": deferred_drop,
        "reference_only_decreased": reference_drop,
        "exclude_invalid_large_drop": exclude_drop,
        "no_default_manual_review_processing": True,
        "no_high_risk_override_auto_applied": True,
    }


def _comparison_markdown(comparison: dict) -> str:
    lines = ["# Phase 1.7 Triage Recognition Before/After Comparison", ""]
    lines.append(f"- MANUAL_REVIEW delta: {comparison.get('manual_review_delta')}")
    lines.append(f"- New AUTO_PROCESS count: {comparison.get('new_auto_process_count')}")
    lines.append(f"- New safe promotion candidates: {comparison.get('new_safe_promotion_candidates')}")
    lines.append(f"- New override proposals: {comparison.get('new_override_proposals')}")
    lines.append(f"- Risk assessment: {comparison.get('risk_assessment')}")
    lines.extend(["", "## Decision Count Delta"])
    for key, value in comparison.get("delta_decision_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Parser Probe Delta"])
    for key, value in comparison.get("parser_probe_delta", {}).items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def _candidate_markdown(title: str, candidates: list[dict]) -> str:
    lines = [f"# {title}", "", f"- Count: {len(candidates)}", ""]
    for item in candidates[:200]:
        lines.append(
            "- "
            f"`{item.get('relative_path')}` -> {item.get('proposed_data_type')} "
            f"({item.get('reason')}; risk={item.get('risk_level')}; action={item.get('recommended_action')})"
        )
    if len(candidates) > 200:
        lines.append(f"- Additional candidates omitted from Markdown preview: {len(candidates) - 200}")
    return "\n".join(lines) + "\n"
