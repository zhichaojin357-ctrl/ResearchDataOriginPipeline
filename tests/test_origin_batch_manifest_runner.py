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


def test_manifest_runner_rejects_unsafe_result_id_before_output_planning(
    tmp_path: Path,
    project_root: Path,
) -> None:
    package = _make_manifest_package(tmp_path, project_root, complete=False)
    rows = list(csv.DictReader((package / "index.csv").open(encoding="utf-8")))
    rows[0]["result_id"] = "../escape"
    _rewrite_manifest(package / "index.csv", rows)

    plan = plan_origin_batch(
        project_root,
        OriginBatchOptions(manifest=package / "index.csv"),
    )

    assert plan["summary"]["blocked_count"] == 1
    assert plan["blocked_items"][0]["reason"] == "unsafe_result_id"


def test_manifest_runner_report_path_cannot_alias_input_manifest(
    tmp_path: Path,
    project_root: Path,
) -> None:
    package = _make_manifest_package(tmp_path, project_root, complete=False)
    manifest = package / "index.csv"
    before = manifest.read_bytes()

    with pytest.raises(ValueError, match="report path aliases the input manifest"):
        run_origin_batch(
            project_root,
            OriginBatchOptions(
                manifest=manifest,
                report_json=manifest,
                report_md=package / "plan.md",
                output_root=package,
            ),
        )

    assert manifest.read_bytes() == before


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
    stale_plot_input = package / "logs" / "origin_jobs" / "XPS_item_plot_input.csv"
    stale_job_script = package / "logs" / "origin_jobs" / "XPS_item.ps1"
    stale_plot_input.parent.mkdir(parents=True)
    stale_plot_input.write_text("stale", encoding="utf-8")
    stale_job_script.write_text("stale", encoding="utf-8")

    class FakeOriginResult:
        ok = True
        message = "fake origin export"

        def __init__(
            self,
            origin_file: Path,
            figure_tif: Path,
            preview_png: Path,
            tif_resolution_evidence: object,
        ) -> None:
            self.origin_file = origin_file
            self.figure_tif = figure_tif
            self.preview_png = preview_png
            self.tif_resolution_evidence = tif_resolution_evidence

    class FakeTifEvidence:
        requested_dpi = 600
        page_width_origin_units = 100.0
        page_height_origin_units = 100.0

    def fake_export_plot(project: Path, dataset_id: str, processed_csv: Path, x_title: str, y_title: str, **kwargs: object):
        assert project == test_project
        assert processed_csv == package / "processed_tables" / "XPS" / "item.csv"
        assert kwargs["data_type"] == "XPS"
        assert stale_plot_input.read_text(encoding="utf-8") == "stale"
        assert stale_job_script.read_text(encoding="utf-8") == "stale"
        calls.append(
            {
                "dataset_id": dataset_id,
                "x_title": x_title,
                "y_title": y_title,
                "output_root": kwargs.get("output_root"),
                "force": kwargs.get("force"),
            }
        )
        stage_root = Path(kwargs["output_root"])
        assert stage_root.parent == package
        assert stage_root.name.startswith(".origin_batch_")
        scratch = stage_root / "origin_files" / f"{dataset_id}.opju"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        tif = stage_root / "figures_tif" / f"{dataset_id}.tif"
        png = stage_root / "figures_preview" / f"{dataset_id}.png"
        for path, content in ((scratch, b"opju"), (png, b"png")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        from PIL import Image

        tif.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (60, 60), "white").save(
            tif,
            format="TIFF",
            dpi=(600, 600),
        )
        return FakeOriginResult(scratch, tif, png, FakeTifEvidence())

    monkeypatch.setattr("src.core.origin_batch.export_plot", fake_export_plot)

    code = run_origin_batch(test_project, OriginBatchOptions(manifest=package / "index.csv", execute=True, with_origin=True))

    assert code == 0
    assert calls and calls[0]["dataset_id"] == "XPS_item"
    assert calls[0]["force"] is True
    assert (package / "origin_files" / "XPS" / "item.opju").read_bytes() == b"opju"
    assert stale_plot_input.read_text(encoding="utf-8") == "stale"
    assert stale_job_script.read_text(encoding="utf-8") == "stale"
    assert not list(package.glob(".origin_batch_*"))
    from PIL import Image

    with Image.open(package / "figures_tif" / "XPS" / "item.tif") as image:
        assert tuple(round(float(value)) for value in image.info.get("dpi", (0, 0))) == (600, 600)
    assert (package / "previews" / "origin" / "XPS" / "item.png").read_bytes() == b"png"
    report = json.loads((default_output_root(test_project) / "reports" / "origin_batch_plan.json").read_text(encoding="utf-8"))
    assert report["summary"]["exported_count"] == 1
    assert report["summary"]["failure_count"] == 0
    assert report["execution"]["reason"] == "executed_with_origin"
    assert report["execution"]["exported"][0]["tif_resolution_evidence"]["effective_dpi_x"] == 600.0


def test_origin_batch_retry_refuses_hardlink_output_alias_to_required_input(
    tmp_path: Path,
) -> None:
    import os

    from src.core.origin_batch import _preflight_origin_output_targets

    package = tmp_path / "package"
    processed = package / "processed.csv"
    metadata = package / "metadata.json"
    origin_file = package / "result.opju"
    figure_tif = package / "result.tif"
    preview_png = package / "result.png"
    package.mkdir()
    processed.write_bytes(b"scientific input")
    metadata.write_text("{}", encoding="utf-8")
    os.link(processed, origin_file)

    with pytest.raises(ValueError, match="aliases a required input"):
        _preflight_origin_output_targets(
            {
                "processed_csv": processed,
                "metadata": metadata,
                "origin_file": origin_file,
                "figure_tif": figure_tif,
                "preview_png": preview_png,
            },
            output_root=package,
        )

    assert processed.read_bytes() == b"scientific input"
    assert origin_file.read_bytes() == b"scientific input"


def test_origin_batch_retry_refuses_generic_target_alias_to_required_input(
    tmp_path: Path,
) -> None:
    from src.core.origin_batch import _preflight_origin_output_targets

    package = tmp_path / "package"
    processed = package / "processed.csv"
    metadata = package / "metadata.json"
    package.mkdir()
    processed.write_bytes(b"scientific input")
    metadata.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="generic_retry_target_1"):
        _preflight_origin_output_targets(
            {
                "processed_csv": processed,
                "metadata": metadata,
                "origin_file": package / "result.opju",
                "figure_tif": package / "result.tif",
                "preview_png": package / "result.png",
            },
            output_root=package,
            extra_targets=(processed,),
        )

    assert processed.read_bytes() == b"scientific input"


def test_manifest_runner_preserves_old_targets_when_staged_export_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
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
    assert all(path.is_file() for path in targets)
    assert [path.read_bytes() for path in targets] == [b"opju", b"tif", b"png"]
    assert not list(package.glob(".origin_batch_*"))
    report = json.loads((default_output_root(test_project) / "reports" / "origin_batch_plan.json").read_text(encoding="utf-8"))
    assert report["summary"]["exported_count"] == 0
    assert report["summary"]["failure_count"] == 1
    assert "native TIFF resolution evidence" in report["execution"]["failures"][0]["message"]


def test_origin_batch_package_commit_failure_restores_every_previous_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import os

    from src.core.origin_batch import _publish_origin_artifact_package

    output_root = tmp_path / "package"
    source_root = tmp_path / "stage"
    output_root.mkdir()
    source_root.mkdir()
    sources = []
    targets = []
    for index, suffix in enumerate(("opju", "tif", "png"), start=1):
        source = source_root / f"new_{index}.{suffix}"
        target = output_root / f"result_{index}.{suffix}"
        source.write_bytes(f"new-{index}".encode())
        target.write_bytes(f"old-{index}".encode())
        sources.append(source)
        targets.append(target)

    real_replace = os.replace
    publish_install_count = 0
    failed_once = False

    def fail_second_publish(source: object, target: object) -> None:
        nonlocal publish_install_count, failed_once
        source_path = Path(source)
        if source_path.name.endswith(".publish"):
            publish_install_count += 1
            if publish_install_count == 2 and not failed_once:
                failed_once = True
                raise OSError("injected second-artifact commit failure")
        real_replace(source, target)

    monkeypatch.setattr("src.core.origin_batch.os.replace", fail_second_publish)

    with pytest.raises(OSError, match="injected"):
        _publish_origin_artifact_package(
            tuple(zip(sources, targets, strict=True)),
            output_root=output_root,
        )

    assert [path.read_bytes() for path in targets] == [
        b"old-1",
        b"old-2",
        b"old-3",
    ]
    assert not list(output_root.glob(".*.publish"))
    assert not list(output_root.glob(".*.rollback"))


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
