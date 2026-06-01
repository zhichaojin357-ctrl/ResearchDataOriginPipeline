from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from src.core.origin_batch import OriginBatchOptions, plan_origin_batch, run_origin_batch
from src.core.phase1_7 import (
    generate_gallery,
    generate_override_decision_table,
    generate_preview_review_checklist,
)


def test_phase1_6_package_index_can_be_read_when_available(project_root: Path):
    manifest = project_root / "output" / "phase1_6_origin_results_20260531_041538" / "index.csv"
    if not manifest.exists():
        pytest.skip("real Phase 1.6 package is not available in this checkout")
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 167
    assert {row["data_type"] for row in rows} >= {"EIS", "XPS", "Mott-Schottky"}


def test_preview_review_checklist_can_be_generated_when_package_available(project_root: Path):
    manifest = project_root / "output" / "phase1_6_origin_results_20260531_041538" / "index.csv"
    if not manifest.exists():
        pytest.skip("real Phase 1.6 package is not available in this checkout")
    checklist = generate_preview_review_checklist(project_root)
    assert len(checklist) == 167
    high_risk = [row for row in checklist if row["data_type"] in {"XPS", "EPR", "Mott-Schottky"}]
    assert high_risk
    assert all(row["manual_check_required"] == "true" for row in high_risk)


def test_gallery_index_can_be_generated_when_package_available(project_root: Path):
    manifest = project_root / "output" / "phase1_6_origin_results_20260531_041538" / "index.csv"
    if not manifest.exists():
        pytest.skip("real Phase 1.6 package is not available in this checkout")
    gallery = generate_gallery(project_root)
    assert gallery["total"] == 167
    assert gallery["by_type"]["XPS"] == 9


def test_manual_override_decision_table_can_be_generated(project_root: Path):
    rows, summary = generate_override_decision_table(project_root)
    assert "proposal_count" in summary
    assert rows
    assert all(not row["user_decision"] for row in rows)
    assert {row["recommended_decision"] for row in rows} <= {
        "approve_candidate",
        "reject_candidate",
        "needs_user_column_mapping",
        "needs_user_sample_identity",
        "needs_user_scientific_context",
        "keep_manual_review",
        "do_not_process",
    }


def test_manifest_runner_dry_run_skips_completed_items_and_does_not_launch_origin(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=True)
    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv"))
    assert plan["summary"]["planned_count"] == 0
    assert plan["summary"]["skipped_count"] == 1
    assert plan["summary"]["will_launch_origin"] is False
    assert plan["skipped_items"][0]["reason"] == "already_complete"


def test_manifest_runner_uses_package_source_copy_hash_when_manifest_lacks_source_copy(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=True)
    rows = list(csv.DictReader((package / "index.csv").open(encoding="utf-8")))
    for row in rows:
        row.pop("source_copy", None)
        row["source_file"] = "source/path/that/no/longer/exists.txt"
    _rewrite_manifest(package / "index.csv", rows)

    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv"))

    assert plan["summary"]["blocked_count"] == 0
    assert plan["summary"]["skipped_count"] == 1
    assert plan["skipped_items"][0]["reason"] == "already_complete"


def test_manifest_runner_only_type_filters_items(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=False, data_type="XPS")
    _append_manifest_row(package / "index.csv", package, project_root, data_type="EIS", result_id="EIS_done")
    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv", only_type="XPS"))
    assert plan["summary"]["planned_count"] == 1
    assert plan["planned_items"][0]["data_type"] == "XPS"
    assert any(item["reason"] == "only_type_filter" for item in plan["skipped_items"])


def test_manifest_runner_only_missing_plans_missing_origin_outputs(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=False)
    (package / "origin_files" / "XPS" / "item.opju").unlink()
    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv", only_missing=True))
    assert plan["summary"]["planned_count"] == 1
    assert "origin_file" in plan["planned_items"][0]["missing_origin_outputs"]


def test_manifest_runner_rejects_path_traversal(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=False)
    rows = list(csv.DictReader((package / "index.csv").open(encoding="utf-8")))
    rows[0]["preview_png"] = "../outside.png"
    _rewrite_manifest(package / "index.csv", rows)
    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv"))
    assert plan["summary"]["blocked_count"] == 1
    assert plan["blocked_items"][0]["reason"] == "path_traversal_or_absolute_artifact_path"


def test_manifest_runner_handles_missing_required_file(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=False)
    (package / "metadata" / "XPS" / "item_metadata.json").unlink()
    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv"))
    assert plan["summary"]["blocked_count"] == 1
    assert plan["blocked_items"][0]["reason"] == "required_input_artifact_missing"


def test_manifest_runner_blocks_hash_mismatch(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=False, source_hash="0" * 64)
    plan = plan_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv"))
    assert plan["summary"]["blocked_count"] == 1
    assert plan["blocked_items"][0]["reason"] == "source_hash_mismatch"


def test_manifest_runner_writes_default_reports(tmp_path: Path, project_root: Path):
    package = _make_manifest_package(tmp_path, project_root, complete=True)
    report_json = project_root / "output" / "reports" / "_test_phase1_7_manifest_runner_plan.json"
    report_md = project_root / "output" / "reports" / "_test_phase1_7_manifest_runner_plan.md"
    code = run_origin_batch(project_root, OriginBatchOptions(manifest=package / "index.csv", report_json=report_json, report_md=report_md))
    assert code == 0
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["summary"]["will_launch_origin"] is False


def test_origin_batch_help_documents_dry_run_default(project_root: Path):
    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--help"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0
    assert "--manifest" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--with-origin" in result.stdout


def test_origin_batch_cli_reports_missing_manifest_headers_without_traceback(tmp_path: Path, project_root: Path):
    manifest = tmp_path / "bad_manifest.csv"
    manifest.write_text(
        "result_id,data_type,processed_csv,metadata,origin_file,figure_tif,preview_png,origin_status,qc_status\n"
        "item,EIS,processed.csv,metadata.json,item.opju,item.tif,item.png,success,QC_PASS\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "manifest CSV missing required headers" in result.stderr
    assert "source_hash" in result.stderr
    assert "Traceback" not in result.stderr


def test_origin_batch_cli_reports_duplicate_manifest_headers_without_traceback(tmp_path: Path, project_root: Path):
    manifest = tmp_path / "duplicate_manifest.csv"
    manifest.write_text(
        "result_id,result_id,data_type,source_file,source_hash,processed_csv,metadata,origin_file,figure_tif,preview_png,origin_status,qc_status\n"
        "item,item2,EIS,source.csv,hash,processed.csv,metadata.json,item.opju,item.tif,item.png,success,QC_PASS\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "manifest CSV duplicate header" in result.stderr
    assert "result_id" in result.stderr
    assert "Traceback" not in result.stderr


def test_origin_batch_cli_reports_missing_source_locator_header_without_traceback(tmp_path: Path, project_root: Path):
    manifest = tmp_path / "missing_source_locator_manifest.csv"
    manifest.write_text(
        "result_id,data_type,source_hash,processed_csv,metadata,origin_file,figure_tif,preview_png,origin_status,qc_status\n"
        "item,EIS,hash,processed.csv,metadata.json,item.opju,item.tif,item.png,success,QC_PASS\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "manifest CSV must include one source locator header" in result.stderr
    assert "Traceback" not in result.stderr


def test_origin_batch_cli_reports_extra_manifest_columns_without_traceback(tmp_path: Path, project_root: Path):
    manifest = tmp_path / "extra_columns_manifest.csv"
    manifest.write_text(
        "result_id,data_type,source_file,source_hash,processed_csv,metadata,origin_file,figure_tif,preview_png,origin_status,qc_status\n"
        "item,EIS,source.csv,hash,processed.csv,metadata.json,item.opju,item.tif,item.png,success,QC_PASS,extra\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "manifest CSV row 2 has 12 columns; expected 11" in result.stderr
    assert "Traceback" not in result.stderr


def test_origin_batch_cli_reports_short_manifest_rows_without_traceback(tmp_path: Path, project_root: Path):
    manifest = tmp_path / "short_row_manifest.csv"
    manifest.write_text(
        "result_id,data_type,source_file,source_hash,processed_csv,metadata,origin_file,figure_tif,preview_png,origin_status,qc_status\n"
        "item,EIS,source.csv,hash,processed.csv,metadata.json,item.opju,item.tif,item.png,success\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["D:\\Python\\python.exe", "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "manifest CSV row 2 has 10 columns; expected 11" in result.stderr
    assert "Traceback" not in result.stderr


def _make_manifest_package(
    tmp_path: Path,
    project_root: Path,
    *,
    complete: bool,
    data_type: str = "XPS",
    source_hash: str | None = None,
) -> Path:
    package = tmp_path / "pkg"
    for relative in (
        "processed_tables/XPS",
        "metadata/XPS",
        "origin_files/XPS",
        "figures_tif/XPS",
        "previews/origin/XPS",
        "previews/no_origin/XPS",
        "contact_sheets/origin",
    ):
        (package / relative).mkdir(parents=True, exist_ok=True)
    _write(package / "processed_tables" / "XPS" / "item.csv", "x,y\n1,2\n")
    _write(package / "metadata" / "XPS" / "item_metadata.json", "{}\n")
    _write(package / "origin_files" / "XPS" / "item.opju", "opju")
    _write(package / "figures_tif" / "XPS" / "item.tif", "tif")
    _write(package / "previews" / "origin" / "XPS" / "item.png", "png")
    _write(package / "previews" / "no_origin" / "XPS" / "item.png", "png")
    _write(package / "contact_sheets" / "origin" / "XPS_origin_contact_sheet.png", "png")
    source = package / "selected_source_data" / "source.txt"
    _write(source, "fixture source\n")
    expected_hash = source_hash or _sha256(source)
    _write_manifest(package / "index.csv", package, project_root, data_type=data_type, origin_status="success" if complete else "pending", qc_status="QC_PASS" if complete else "NOT_CHECKED", source_hash=expected_hash)
    return package


def _append_manifest_row(path: Path, package: Path, project_root: Path, *, data_type: str, result_id: str) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    row = dict(rows[0])
    row["result_id"] = result_id
    row["data_type"] = data_type
    rows.append(row)
    _rewrite_manifest(path, rows)


def _write_manifest(path: Path, package: Path, project_root: Path, *, data_type: str, origin_status: str, qc_status: str, source_hash: str) -> None:
    row = {
        "result_id": "XPS_item",
        "queue_id": "queue",
        "data_type": data_type,
        "source_file": "phase1_7_manifest_fixture/source.txt",
        "source_copy": "selected_source_data/source.txt",
        "source_hash": source_hash,
        "processed_csv": "processed_tables/XPS/item.csv",
        "metadata": "metadata/XPS/item_metadata.json",
        "origin_file": "origin_files/XPS/item.opju",
        "figure_tif": "figures_tif/XPS/item.tif",
        "preview_png": "previews/origin/XPS/item.png",
        "original_no_origin_preview": "previews/no_origin/XPS/item.png",
        "contact_sheet": "contact_sheets/origin/XPS_origin_contact_sheet.png",
        "origin_status": origin_status,
        "qc_status": qc_status,
        "manual_check_required": "True",
        "forbidden_claims": "do not automatically assign XPS valence states",
        "notes": "test package",
    }
    _rewrite_manifest(path, [row])


def _rewrite_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
