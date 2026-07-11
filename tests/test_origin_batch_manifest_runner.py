from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.core.origin_batch import OriginBatchOptions, plan_origin_batch, run_origin_batch
from src.core.project import default_output_root


def test_locked_result_package_index_can_be_read_when_available(project_root: Path):
    manifest = default_output_root(project_root) / "locked_origin_results_20260531_041538" / "index.csv"
    if not manifest.exists():
        pytest.skip("real locked result package is not available in this checkout")
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 167
    assert {row["data_type"] for row in rows} >= {"EIS", "XPS", "Mott-Schottky"}


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
    test_project = tmp_path / "project"
    package = _make_manifest_package(tmp_path, test_project, complete=True)
    reports_dir = default_output_root(test_project) / "reports"
    reports_dir.mkdir(parents=True)
    report_json = reports_dir / "manifest_runner_plan.json"
    report_md = reports_dir / "manifest_runner_plan.md"
    code = run_origin_batch(test_project, OriginBatchOptions(manifest=package / "index.csv", report_json=report_json, report_md=report_md))
    assert code == 0
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["summary"]["will_launch_origin"] is False
    rendered = json.dumps(payload, ensure_ascii=False)
    assert str(tmp_path) not in rendered
    assert "external/" in payload["manifest"]


def test_manifest_runner_execute_with_origin_exports_planned_items(tmp_path: Path, monkeypatch):
    test_project = tmp_path / "project"
    package = _make_manifest_package(tmp_path, test_project, complete=False)
    for relative in ("origin_files/XPS/item.opju", "figures_tif/XPS/item.tif", "previews/origin/XPS/item.png"):
        (package / relative).unlink()
    calls: list[dict[str, object]] = []

    class FakeOriginResult:
        ok = True
        message = "fake origin export"

        def __init__(self, origin_file: Path, figure_tif: Path, preview_png: Path) -> None:
            self.origin_file = origin_file
            self.figure_tif = figure_tif
            self.preview_png = preview_png

    def fake_export_plot(project: Path, dataset_id: str, processed_csv: Path, x_title: str, y_title: str, **kwargs: object):
        assert project == test_project
        assert processed_csv == package / "processed_tables" / "XPS" / "item.csv"
        assert kwargs["data_type"] == "XPS"
        calls.append({"dataset_id": dataset_id, "x_title": x_title, "y_title": y_title, "output_root": kwargs.get("output_root")})
        scratch = package / "origin_files" / f"{dataset_id}.opju"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        tif = package / "figures_tif" / f"{dataset_id}.tif"
        png = package / "figures_preview" / f"{dataset_id}.png"
        for path, content in ((scratch, b"opju"), (png, b"png")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        from PIL import Image

        tif.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 3), "white").save(tif, format="TIFF", dpi=(300, 300))
        return FakeOriginResult(scratch, tif, png)

    monkeypatch.setattr("src.core.origin_batch.export_plot", fake_export_plot)

    code = run_origin_batch(test_project, OriginBatchOptions(manifest=package / "index.csv", execute=True, with_origin=True))

    assert code == 0
    assert calls and calls[0]["dataset_id"] == "XPS_item"
    assert (package / "origin_files" / "XPS" / "item.opju").read_bytes() == b"opju"
    from PIL import Image

    with Image.open(package / "figures_tif" / "XPS" / "item.tif") as image:
        assert tuple(round(float(value)) for value in image.info.get("dpi", (0, 0))) == (600, 600)
    assert (package / "previews" / "origin" / "XPS" / "item.png").read_bytes() == b"png"
    report = json.loads((default_output_root(test_project) / "reports" / "origin_batch_plan.json").read_text(encoding="utf-8"))
    assert report["summary"]["exported_count"] == 1
    assert report["summary"]["failure_count"] == 0
    assert report["execution"]["reason"] == "executed_with_origin"


def test_manifest_runner_clears_old_targets_and_missing_export_sources_cannot_succeed(tmp_path: Path, monkeypatch) -> None:
    test_project = tmp_path / "project"
    package = _make_manifest_package(tmp_path, test_project, complete=False)
    targets = [
        package / "origin_files" / "XPS" / "item.opju",
        package / "figures_tif" / "XPS" / "item.tif",
        package / "previews" / "origin" / "XPS" / "item.png",
    ]
    assert all(path.is_file() for path in targets)

    class MissingSourceResult:
        ok = True
        message = "reported success without files"
        origin_file = tmp_path / "missing" / "result.opju"
        figure_tif = tmp_path / "missing" / "result.tif"
        preview_png = tmp_path / "missing" / "result.png"

    monkeypatch.setattr("src.core.origin_batch.export_plot", lambda *_args, **_kwargs: MissingSourceResult())

    code = run_origin_batch(
        test_project,
        OriginBatchOptions(manifest=package / "index.csv", execute=True, with_origin=True),
    )

    assert code == 1
    assert all(not path.exists() for path in targets)
    report = json.loads((default_output_root(test_project) / "reports" / "origin_batch_plan.json").read_text(encoding="utf-8"))
    assert report["summary"]["exported_count"] == 0
    assert report["summary"]["failure_count"] == 1
    assert "did not produce manifest outputs" in report["execution"]["failures"][0]["message"]


def test_origin_batch_help_documents_dry_run_default(project_root: Path):
    result = subprocess.run(
        [sys.executable, "run.py", "origin-batch", "--help"],
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
        [sys.executable, "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
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
        [sys.executable, "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
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
        [sys.executable, "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
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
        [sys.executable, "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
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
        [sys.executable, "run.py", "origin-batch", "--manifest", str(manifest), "--dry-run"],
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
        "source_file": "origin_batch_manifest_fixture/source.txt",
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
