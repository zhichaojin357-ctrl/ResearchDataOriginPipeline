from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from io import BytesIO
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

from src.core.agilent_dx import (
    DX_DECODER_NAME,
    DX_DECODER_VERSION,
    decode_agilent_dx,
    read_agilent_dx_metadata,
)
from src.core.file_utils import (
    apply_safe_owned_directory_removal,
    ensure_safe_output_file_target,
    file_sha256,
    lexical_absolute_path,
    plan_safe_owned_directory_removal,
)
from src.core.hplc_analysis import attach_hplc_analysis
from src.core.hplc_openlab_vendor import (
    OpenLabVendorReprocessResult,
    apply_vendor_reprocess_provenance,
    reprocess_openlab_with_vendor_method,
    resolve_bundled_openlab_vendor_assets,
)
from src.core.project import (
    ensure_output_path_separate_from_inputs,
    ensure_output_path_within_root,
    ensure_write_path_allowed,
)


OPENLAB_DATA_TYPE = "HPLC/LC OpenLab raw data"
PROCESSOR_NAME = "hplc_openlab_raw_exporter"
IDENTITY_BOUNDARY = "unassigned_manual_mapping_required"
_WAVELENGTH = re.compile(r"Wavelength\s*=\s*(?P<value>[0-9]+(?:\.[0-9]+)?)\s*nm", re.IGNORECASE)
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


@dataclass(frozen=True)
class HplcOpenLabExportOptions:
    input_root: Path
    since: date
    output_root: Path
    node_exe: Path
    builder_workdir: Path
    output_name: str | None = None
    force: bool = False
    vendor_reprocess: bool = False
    vendor_runtime_bin: Path | None = None
    vendor_bridge_exe: Path | None = None
    vendor_processing_method: Path | None = None
    vendor_timeout_seconds: int = 600


@dataclass(frozen=True)
class _HplcOutputPlan:
    file_targets: tuple[Path, ...]
    directory_targets: tuple[Path, ...]


class _HplcRollbackError(RuntimeError):
    """Raised when a failed package commit could not be rolled back completely."""


def _resolved_vendor_options(options: HplcOpenLabExportOptions) -> tuple[Path, Path, Path] | None:
    supplied = (
        options.vendor_runtime_bin,
        options.vendor_bridge_exe,
        options.vendor_processing_method,
    )
    if not options.vendor_reprocess:
        if any(value is not None for value in supplied):
            raise ValueError(
                "Agilent vendor runtime, bridge, and method options require --vendor-reprocess"
            )
        return None
    if options.vendor_timeout_seconds <= 0:
        raise ValueError("--vendor-timeout-seconds must be greater than zero")
    if not any(value is not None for value in supplied):
        bundled = resolve_bundled_openlab_vendor_assets()
        return bundled.runtime_bin, bundled.bridge_exe, bundled.processing_method
    if any(value is None for value in supplied):
        raise ValueError(
            "Vendor runtime overrides must provide --vendor-runtime-bin, "
            "--vendor-bridge-exe, and --vendor-processing-method together"
        )
    runtime_bin, bridge_exe, processing_method = supplied
    assert runtime_bin is not None and bridge_exe is not None and processing_method is not None
    return runtime_bin.resolve(), bridge_exe.resolve(), processing_method.resolve()


def run_hplc_openlab_export(project_root: Path, options: HplcOpenLabExportOptions) -> dict[str, Any]:
    """Decode Agilent OpenLab result sets and build a data-only Excel workbook."""
    input_root = options.input_root.resolve()
    if not input_root.is_dir():
        raise NotADirectoryError(f"OpenLab input root does not exist or is not a directory: {input_root}")

    output_root = lexical_absolute_path(options.output_root)
    ensure_write_path_allowed(project_root, output_root, output_root=output_root)
    ensure_output_path_separate_from_inputs(project_root, output_root, [input_root])

    builder_workdir = ensure_output_path_within_root(
        project_root,
        options.builder_workdir,
        output_root,
    )
    ensure_safe_output_file_target(builder_workdir, output_root=output_root)
    _validate_artifact_workdir(builder_workdir)
    builder_source = _validate_workbook_builder_inputs(project_root, options.node_exe)
    vendor_options = _resolved_vendor_options(options)

    output_name = options.output_name or f"agilent_hplc_openlab_{options.since:%Y%m%d}_plus.xlsx"
    if Path(output_name).name != output_name or Path(output_name).suffix.casefold() != ".xlsx":
        raise ValueError("--output-name must be one .xlsx filename without directory components")
    workbook_path = output_root / output_name
    slug = f"hplc_openlab_{options.since:%Y%m%d}_plus"
    processed_dir = output_root / "processed_data"
    metadata_dir = output_root / "metadata" / slug
    reports_dir = output_root / "reports"
    previews_dir = output_root / "workbook_previews"
    logs_dir = output_root / "logs"

    planning_dataset = extract_hplc_openlab_dataset(input_root, options.since)
    if "analysis" not in planning_dataset:
        planning_dataset = attach_hplc_analysis(planning_dataset, project_root, copy_dataset=False)
    planning_dataset["workbook_plan"] = _build_workbook_plan(planning_dataset, workbook_path)
    workbook_paths = _planned_workbook_paths(
        output_root,
        workbook_path,
        planning_dataset["workbook_plan"],
    )
    dataset_path = processed_dir / f"{slug}_dataset.json"
    verification_path = reports_dir / f"{slug}_workbook_verification.json"
    builder_log_path = logs_dir / f"{slug}_workbook_builder.log"
    metadata_path = metadata_dir / "metadata.json"
    report_path = reports_dir / f"{slug}_processing_summary.md"
    vendor_manifest_path = (
        reports_dir / f"{slug}_vendor_reprocessing.json"
        if vendor_options is not None
        else None
    )
    vendor_log_path = (
        logs_dir / f"{slug}_openlab_processing_server.log"
        if vendor_options is not None
        else None
    )
    file_targets = (
        *workbook_paths,
        dataset_path,
        verification_path,
        builder_log_path,
        metadata_path,
        report_path,
        *((vendor_manifest_path, vendor_log_path) if vendor_options is not None else ()),
    )
    preview_targets = _planned_preview_directories(
        previews_dir,
        planning_dataset["workbook_plan"],
    )
    _preflight_hplc_outputs(
        output_root,
        file_targets=file_targets,
        owned_directory_targets=preview_targets,
        force=options.force,
    )

    output_root.mkdir(parents=True, exist_ok=True)
    ensure_safe_output_file_target(output_root, output_root=output_root)

    stage_root: Path | None = None
    builder_run_dir: Path | None = None
    preserve_stage_for_recovery = False
    try:
        stage_root = lexical_absolute_path(
            Path(
                tempfile.mkdtemp(
                    prefix=f".{slug}.staging-",
                    dir=output_root,
                )
            )
        )
        ensure_safe_output_file_target(stage_root, output_root=output_root)
        stage_payload_root = stage_root / "payload"
        stage_payload_root.mkdir()

        builder_run_dir = lexical_absolute_path(
            Path(
                tempfile.mkdtemp(
                    prefix=f".{slug}.builder-",
                    dir=builder_workdir,
                )
            )
        )
        ensure_safe_output_file_target(builder_run_dir, output_root=output_root)
        staged_builder_copy = builder_run_dir / builder_source.name

        staged_workbook_paths = [
            _staged_hplc_path(path, output_root, stage_payload_root)
            for path in workbook_paths
        ]
        staged_dataset_path = _staged_hplc_path(
            dataset_path,
            output_root,
            stage_payload_root,
        )
        staged_verification_path = _staged_hplc_path(
            verification_path,
            output_root,
            stage_payload_root,
        )
        staged_builder_log_path = _staged_hplc_path(
            builder_log_path,
            output_root,
            stage_payload_root,
        )
        staged_metadata_path = _staged_hplc_path(
            metadata_path,
            output_root,
            stage_payload_root,
        )
        staged_report_path = _staged_hplc_path(
            report_path,
            output_root,
            stage_payload_root,
        )
        staged_vendor_manifest_path = (
            _staged_hplc_path(vendor_manifest_path, output_root, stage_payload_root)
            if vendor_manifest_path is not None
            else None
        )
        staged_vendor_log_path = (
            _staged_hplc_path(vendor_log_path, output_root, stage_payload_root)
            if vendor_log_path is not None
            else None
        )
        staged_preview_targets = tuple(
            _staged_hplc_path(path, output_root, stage_payload_root)
            for path in preview_targets
        )
        staged_previews_dir = _staged_hplc_path(
            previews_dir,
            output_root,
            stage_payload_root,
        )

        vendor_result: OpenLabVendorReprocessResult | None = None
        if vendor_options is not None:
            runtime_bin, bridge_exe, processing_method = vendor_options
            vendor_result = reprocess_openlab_with_vendor_method(
                source_root=input_root,
                staged_input_root=stage_root / "vendor_input",
                dataset=planning_dataset,
                runtime_bin=runtime_bin,
                bridge_exe=bridge_exe,
                processing_method=processing_method,
                timeout_seconds=options.vendor_timeout_seconds,
            )
            dataset = extract_hplc_openlab_dataset(
                vendor_result.effective_input_root,
                options.since,
            )
            dataset = apply_vendor_reprocess_provenance(
                dataset,
                vendor_result,
                source_root_name=input_root.name,
            )
            dataset = attach_hplc_analysis(dataset, project_root, copy_dataset=False)
            dataset["workbook_plan"] = _build_workbook_plan(dataset, workbook_path)
            vendor_workbook_paths = _planned_workbook_paths(
                output_root,
                workbook_path,
                dataset["workbook_plan"],
            )
            if vendor_workbook_paths != workbook_paths:
                raise RuntimeError("Vendor reprocessing changed the planned HPLC workbook layout")
            assert staged_vendor_manifest_path is not None
            assert staged_vendor_log_path is not None
            staged_vendor_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            staged_vendor_manifest_path.write_text(
                json.dumps(vendor_result.manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            staged_vendor_log_path.parent.mkdir(parents=True, exist_ok=True)
            staged_vendor_log_path.write_text(vendor_result.log_text, encoding="utf-8")
        else:
            dataset = planning_dataset

        staged_dataset_path.parent.mkdir(parents=True, exist_ok=True)
        staged_dataset_path.write_text(
            json.dumps(dataset, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        _run_workbook_builder(
            project_root=project_root,
            node_exe=options.node_exe,
            builder_workdir=builder_workdir,
            builder_copy_path=staged_builder_copy,
            dataset_path=staged_dataset_path,
            workbook_path=staged_workbook_paths[0],
            previews_dir=staged_previews_dir,
            verification_path=staged_verification_path,
            log_path=staged_builder_log_path,
        )

        metadata_payload = _metadata_payload(
            dataset,
            workbook_paths,
            output_root,
            dataset_path,
            verification_path,
        )
        staged_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        staged_metadata_path.write_text(
            json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        staged_report_path.parent.mkdir(parents=True, exist_ok=True)
        staged_report_path.write_text(
            _summary_markdown(dataset, workbook_paths, output_root),
            encoding="utf-8",
        )

        staged_preview_files = _validate_staged_hplc_package(
            stage_payload_root=stage_payload_root,
            dataset=dataset,
            workbook_paths=tuple(staged_workbook_paths),
            dataset_path=staged_dataset_path,
            verification_path=staged_verification_path,
            builder_log_path=staged_builder_log_path,
            metadata_path=staged_metadata_path,
            report_path=staged_report_path,
            vendor_manifest_path=staged_vendor_manifest_path,
            vendor_log_path=staged_vendor_log_path,
            preview_directories=staged_preview_targets,
            previews_root=staged_previews_dir,
        )
        _rewrite_staged_builder_paths(
            verification_path=staged_verification_path,
            builder_log_path=staged_builder_log_path,
            stage_payload_root=stage_payload_root,
            output_root=output_root,
        )
        _validate_builder_verification_file(
            staged_verification_path,
            expected_workbook_paths=tuple(workbook_paths),
            expected_preview_files=tuple(
                _published_hplc_path(
                    path,
                    stage_payload_root,
                    output_root,
                )
                for path in staged_preview_files
            ),
        )

        staged_file_targets = (
            *staged_workbook_paths,
            staged_dataset_path,
            staged_verification_path,
            staged_builder_log_path,
            staged_metadata_path,
            staged_report_path,
            *(
                (staged_vendor_manifest_path, staged_vendor_log_path)
                if staged_vendor_manifest_path is not None and staged_vendor_log_path is not None
                else ()
            ),
        )
        _commit_staged_hplc_package(
            output_root=output_root,
            stage_root=stage_root,
            staged_file_targets=tuple(staged_file_targets),
            final_file_targets=tuple(file_targets),
            staged_directory_targets=staged_preview_targets,
            final_directory_targets=preview_targets,
            force=options.force,
        )
    except _HplcRollbackError:
        preserve_stage_for_recovery = True
        raise
    finally:
        if builder_run_dir is not None:
            _remove_safe_owned_tree(builder_run_dir, output_root=output_root)
        if stage_root is not None and not preserve_stage_for_recovery:
            _remove_safe_owned_tree(stage_root, output_root=output_root)

    return {
        "workbook": workbook_path,
        "workbooks": workbook_paths,
        "dataset": dataset_path,
        "metadata": metadata_path,
        "report": report_path,
        "verification": verification_path,
        "preview_dir": previews_dir,
        "vendor_manifest": vendor_manifest_path,
        "vendor_log": vendor_log_path,
        "summary": dataset["summary"],
    }


def _validate_workbook_builder_inputs(project_root: Path, node_exe: Path) -> Path:
    resolved_node = node_exe.resolve()
    if not resolved_node.is_file():
        raise FileNotFoundError(f"Node.js executable does not exist: {resolved_node}")
    builder_source = project_root / "scripts" / "data_types" / "hplc_lc" / "build_openlab_workbook.mjs"
    if not builder_source.is_file():
        raise FileNotFoundError(f"OpenLab workbook builder is missing: {builder_source}")
    return builder_source.resolve()


def _safe_preview_component(value: str) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("_", str(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:90] or "sheet"


def _planned_preview_directories(
    previews_dir: Path,
    workbook_plan: dict[str, Any],
) -> tuple[Path, ...]:
    planned = [previews_dir / "00_总索引"]
    for item in workbook_plan.get("batch_workbooks", []):
        batch_id = str(item.get("batch_id") or "").strip()
        batch_folder = str(item.get("batch_folder") or "")
        if not batch_id:
            raise ValueError("Planned OpenLab batch preview is missing batch_id")
        planned.append(previews_dir / f"{batch_id}_{_safe_preview_component(batch_folder)}")
    return tuple(lexical_absolute_path(path) for path in planned)


def _preflight_hplc_outputs(
    output_root: Path,
    *,
    file_targets: tuple[Path, ...],
    owned_directory_targets: tuple[Path, ...],
    force: bool,
) -> _HplcOutputPlan:
    lexical_root = lexical_absolute_path(output_root)
    files = tuple(
        dict.fromkeys(
            ensure_safe_output_file_target(path, output_root=lexical_root)
            for path in file_targets
        )
    )
    directories = tuple(
        dict.fromkeys(
            ensure_safe_output_file_target(path, output_root=lexical_root)
            for path in owned_directory_targets
        )
    )
    existing_files = [
        path for path in files if os.path.lexists(os.fspath(path))
    ]
    directory_removal_plans = {
        path: plan_safe_owned_directory_removal(path, output_root=lexical_root)
        for path in directories
        if os.path.lexists(os.fspath(path))
    }
    existing_directories = list(directory_removal_plans)
    conflicts = [*existing_files, *existing_directories]
    if conflicts and not force:
        rendered = ", ".join(str(path) for path in conflicts[:8])
        raise FileExistsError(
            "One or more planned OpenLab outputs already exist; rerun with --force to overwrite: "
            f"{rendered}"
        )

    file_directories = [path for path in existing_files if path.is_dir() and not path.is_symlink()]
    if file_directories:
        rendered = ", ".join(str(path) for path in file_directories[:8])
        raise IsADirectoryError(f"Planned OpenLab file output collides with a directory: {rendered}")
    for path in existing_files:
        _assert_safe_regular_file(path, output_root=lexical_root)
    for plan in directory_removal_plans.values():
        for path in plan[1]:
            _assert_safe_regular_file(path, output_root=lexical_root)
    return _HplcOutputPlan(
        file_targets=files,
        directory_targets=directories,
    )


def _staged_hplc_path(
    final_path: Path,
    output_root: Path,
    stage_payload_root: Path,
) -> Path:
    safe_final = ensure_safe_output_file_target(final_path, output_root=output_root)
    relative = safe_final.relative_to(lexical_absolute_path(output_root))
    return ensure_safe_output_file_target(
        stage_payload_root / relative,
        output_root=stage_payload_root,
    )


def _published_hplc_path(
    staged_path: Path,
    stage_payload_root: Path,
    output_root: Path,
) -> Path:
    safe_staged = ensure_safe_output_file_target(
        staged_path,
        output_root=stage_payload_root,
    )
    relative = safe_staged.relative_to(lexical_absolute_path(stage_payload_root))
    return ensure_safe_output_file_target(
        output_root / relative,
        output_root=output_root,
    )


def _assert_safe_regular_file(
    path: Path,
    *,
    output_root: Path,
    require_nonempty: bool = False,
) -> Path:
    safe_path = ensure_safe_output_file_target(path, output_root=output_root)
    if not os.path.lexists(os.fspath(safe_path)):
        raise FileNotFoundError(f"Required OpenLab package file is missing: {safe_path}")
    if not safe_path.is_file():
        raise ValueError(f"OpenLab package target is not a regular file: {safe_path}")
    file_stat = safe_path.stat(follow_symlinks=False)
    if file_stat.st_nlink > 1:
        raise ValueError(
            "Refusing OpenLab package file with multiple hard links: "
            f"{safe_path} (link_count={file_stat.st_nlink})"
        )
    if require_nonempty and file_stat.st_size <= 0:
        raise RuntimeError(f"OpenLab package file is empty: {safe_path}")
    return safe_path


def _validate_xlsx_package(path: Path, *, output_root: Path) -> None:
    safe_path = _assert_safe_regular_file(
        path,
        output_root=output_root,
        require_nonempty=True,
    )
    if not zipfile.is_zipfile(safe_path):
        raise RuntimeError(f"Workbook builder produced an invalid XLSX ZIP package: {safe_path}")
    with zipfile.ZipFile(safe_path) as archive:
        members = set(archive.namelist())
    required_members = {"[Content_Types].xml", "xl/workbook.xml"}
    missing = sorted(required_members - members)
    if missing:
        raise RuntimeError(
            f"Workbook builder produced an incomplete XLSX package: {safe_path}; "
            f"missing {', '.join(missing)}"
        )


def _validate_png_preview(path: Path, *, output_root: Path) -> None:
    safe_path = _assert_safe_regular_file(
        path,
        output_root=output_root,
        require_nonempty=True,
    )
    with safe_path.open("rb") as handle:
        signature = handle.read(8)
    if signature != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"Workbook preview is not a valid PNG file: {safe_path}")


def _validate_builder_verification_file(
    verification_path: Path,
    *,
    expected_workbook_paths: tuple[Path, ...],
    expected_preview_files: tuple[Path, ...],
) -> dict[str, Any]:
    try:
        payload = json.loads(verification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Workbook verification JSON is unreadable: {verification_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Workbook verification payload must be a JSON object")
    workbooks = payload.get("workbooks")
    if not isinstance(workbooks, list):
        raise RuntimeError("Workbook verification is missing its workbooks list")
    if payload.get("workbook_count") != len(expected_workbook_paths):
        raise RuntimeError(
            "Workbook verification count does not match the planned workbook package"
        )
    if len(workbooks) != len(expected_workbook_paths):
        raise RuntimeError(
            "Workbook verification entries do not match the planned workbook package"
        )

    actual_workbook_paths: list[Path] = []
    actual_preview_files: list[Path] = []
    calculated_sheet_count = 0
    for item in workbooks:
        if not isinstance(item, dict):
            raise RuntimeError("Workbook verification contains a non-object workbook entry")
        workbook_value = str(item.get("path") or "").strip()
        if not workbook_value:
            raise RuntimeError("Workbook verification entry is missing its workbook path")
        actual_workbook_paths.append(lexical_absolute_path(Path(workbook_value)))
        sheet_count = item.get("sheet_count")
        if not isinstance(sheet_count, int) or sheet_count <= 0:
            raise RuntimeError(
                "Workbook verification contains an invalid sheet count"
            )
        calculated_sheet_count += sheet_count
        preview_values = item.get("preview_files")
        if not isinstance(preview_values, list) or not preview_values:
            raise RuntimeError(
                "Workbook verification entry is missing preview evidence"
            )
        for value in preview_values:
            rendered = str(value or "").strip()
            if not rendered:
                raise RuntimeError(
                    "Workbook verification contains an empty preview path"
                )
            actual_preview_files.append(lexical_absolute_path(Path(rendered)))

    expected_workbooks = [
        lexical_absolute_path(path) for path in expected_workbook_paths
    ]
    if actual_workbook_paths != expected_workbooks:
        raise RuntimeError(
            "Workbook verification paths do not match the planned workbook paths"
        )
    expected_previews = {
        lexical_absolute_path(path) for path in expected_preview_files
    }
    if set(actual_preview_files) != expected_previews:
        raise RuntimeError(
            "Workbook verification preview paths do not match the rendered PNG package"
        )
    if len(actual_preview_files) != len(expected_previews):
        raise RuntimeError("Workbook verification contains duplicate preview paths")
    if payload.get("preview_count") != len(expected_previews):
        raise RuntimeError(
            "Workbook verification preview count does not match rendered PNG files"
        )
    if payload.get("sheet_count") != calculated_sheet_count:
        raise RuntimeError(
            "Workbook verification sheet count does not match its workbook entries"
        )
    return payload


def _validate_staged_hplc_package(
    *,
    stage_payload_root: Path,
    dataset: dict[str, Any],
    workbook_paths: tuple[Path, ...],
    dataset_path: Path,
    verification_path: Path,
    builder_log_path: Path,
    metadata_path: Path,
    report_path: Path,
    preview_directories: tuple[Path, ...],
    previews_root: Path,
    vendor_manifest_path: Path | None = None,
    vendor_log_path: Path | None = None,
) -> tuple[Path, ...]:
    for workbook in workbook_paths:
        _validate_xlsx_package(workbook, output_root=stage_payload_root)
        if dataset.get("analysis"):
            freeze_evidence = _read_xlsx_top_row_freeze(workbook)
            expected_sheet_count = len(
                dataset.get("workbook_plan", {}).get("analysis_sheet_names", [])
            )
            if (
                not freeze_evidence["all_frozen"]
                or freeze_evidence["worksheet_count"] != expected_sheet_count
            ):
                raise RuntimeError(
                    "Analysis workbook top-row freeze or worksheet-count readback failed: "
                    f"{freeze_evidence}"
                )
    for path in (
        dataset_path,
        verification_path,
        builder_log_path,
        metadata_path,
        report_path,
    ):
        _assert_safe_regular_file(
            path,
            output_root=stage_payload_root,
            require_nonempty=True,
        )

    try:
        staged_dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Staged OpenLab dataset is unreadable: {dataset_path}") from exc
    if staged_dataset != dataset:
        raise RuntimeError("Staged OpenLab dataset changed before package commit")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Staged OpenLab metadata is unreadable: {metadata_path}") from exc
    expected_processing_status = (
        "processed_to_compact_analysis_excel_no_plot"
        if dataset.get("analysis")
        else "processed_to_split_excel_no_plot"
    )
    if metadata.get("processing_status") != expected_processing_status:
        raise RuntimeError("Staged OpenLab metadata has an invalid processing status")
    if "exit_code=0" not in builder_log_path.read_text(encoding="utf-8"):
        raise RuntimeError("Workbook builder log does not record a successful exit")
    if not report_path.read_text(encoding="utf-8").strip():
        raise RuntimeError("Staged OpenLab processing report is empty")
    if (vendor_manifest_path is None) != (vendor_log_path is None):
        raise RuntimeError("Vendor manifest and log must be staged together")
    if vendor_manifest_path is not None and vendor_log_path is not None:
        _assert_safe_regular_file(
            vendor_manifest_path,
            output_root=stage_payload_root,
            require_nonempty=True,
        )
        _assert_safe_regular_file(
            vendor_log_path,
            output_root=stage_payload_root,
            require_nonempty=True,
        )
        try:
            vendor_manifest = json.loads(vendor_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Staged OpenLab vendor manifest is unreadable") from exc
        if not vendor_manifest.get("vendor_code_executed"):
            raise RuntimeError("Staged OpenLab vendor manifest does not prove vendor execution")
        if vendor_manifest.get("completed_injection_count") != dataset["summary"][
            "selected_injection_count"
        ]:
            raise RuntimeError("Staged OpenLab vendor manifest injection count is incomplete")

    safe_previews_root = ensure_safe_output_file_target(
        previews_root,
        output_root=stage_payload_root,
    )
    if not safe_previews_root.is_dir():
        raise RuntimeError(
            f"Workbook builder did not create the preview root: {safe_previews_root}"
        )
    planned_preview_directories = {
        ensure_safe_output_file_target(path, output_root=stage_payload_root)
        for path in preview_directories
    }
    actual_root_children = {
        ensure_safe_output_file_target(path, output_root=stage_payload_root)
        for path in safe_previews_root.iterdir()
    }
    if actual_root_children != planned_preview_directories:
        raise RuntimeError(
            "Workbook builder preview directories do not match the planned package"
        )

    preview_files: list[Path] = []
    for directory in sorted(
        planned_preview_directories,
        key=lambda item: str(item).casefold(),
    ):
        plan = plan_safe_owned_directory_removal(
            directory,
            output_root=stage_payload_root,
        )
        if not plan[0].is_dir():
            raise RuntimeError(
                f"Workbook builder did not create a planned preview directory: {directory}"
            )
        if plan[2]:
            raise RuntimeError(
                f"Workbook preview directory contains unexpected nested directories: {directory}"
            )
        if not plan[1]:
            raise RuntimeError(
                f"Workbook preview directory contains no rendered PNG files: {directory}"
            )
        for preview in plan[1]:
            if preview.suffix.casefold() != ".png":
                raise RuntimeError(
                    f"Workbook preview directory contains a non-PNG file: {preview}"
                )
            _validate_png_preview(preview, output_root=stage_payload_root)
            preview_files.append(preview)

    ordered_preview_files = tuple(
        sorted(preview_files, key=lambda item: str(item).casefold())
    )
    _validate_builder_verification_file(
        verification_path,
        expected_workbook_paths=workbook_paths,
        expected_preview_files=ordered_preview_files,
    )
    return ordered_preview_files


def _rewrite_staged_builder_paths(
    *,
    verification_path: Path,
    builder_log_path: Path,
    stage_payload_root: Path,
    output_root: Path,
) -> None:
    payload = json.loads(verification_path.read_text(encoding="utf-8"))

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                rewrite(key) if isinstance(key, str) else key: rewrite(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, str):
            return _replace_staged_path_text(
                value,
                stage_payload_root=stage_payload_root,
                output_root=output_root,
            )
        return value

    verification_path.write_text(
        json.dumps(rewrite(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    builder_log_path.write_text(
        _replace_staged_path_text(
            builder_log_path.read_text(encoding="utf-8"),
            stage_payload_root=stage_payload_root,
            output_root=output_root,
        ),
        encoding="utf-8",
    )


def _replace_staged_path_text(
    value: str,
    *,
    stage_payload_root: Path,
    output_root: Path,
) -> str:
    rendered = value
    replacements = (
        (str(lexical_absolute_path(stage_payload_root)), str(lexical_absolute_path(output_root))),
        (
            lexical_absolute_path(stage_payload_root).as_posix(),
            lexical_absolute_path(output_root).as_posix(),
        ),
    )
    for old, new in replacements:
        rendered = rendered.replace(old, new)
    return rendered


def _commit_staged_hplc_package(
    *,
    output_root: Path,
    stage_root: Path,
    staged_file_targets: tuple[Path, ...],
    final_file_targets: tuple[Path, ...],
    staged_directory_targets: tuple[Path, ...],
    final_directory_targets: tuple[Path, ...],
    force: bool,
) -> None:
    if len(staged_file_targets) != len(final_file_targets):
        raise ValueError("Staged and final OpenLab file target counts do not match")
    if len(staged_directory_targets) != len(final_directory_targets):
        raise ValueError("Staged and final OpenLab directory target counts do not match")

    final_plan = _preflight_hplc_outputs(
        output_root,
        file_targets=final_file_targets,
        owned_directory_targets=final_directory_targets,
        force=force,
    )
    for path in staged_file_targets:
        _assert_safe_regular_file(
            path,
            output_root=stage_root,
            require_nonempty=True,
        )
    for directory in staged_directory_targets:
        staged_plan = plan_safe_owned_directory_removal(
            directory,
            output_root=stage_root,
        )
        if not staged_plan[0].is_dir():
            raise RuntimeError(
                f"Staged OpenLab package directory is missing: {directory}"
            )
        for path in staged_plan[1]:
            _assert_safe_regular_file(path, output_root=stage_root)

    backup_root = ensure_safe_output_file_target(
        stage_root / "rollback",
        output_root=stage_root,
    )
    moved_backups: list[tuple[str, Path, Path]] = []
    installed_targets: list[tuple[str, Path]] = []
    try:
        for final_path in final_plan.file_targets:
            if not os.path.lexists(os.fspath(final_path)):
                continue
            backup_path = ensure_safe_output_file_target(
                backup_root / "files" / final_path.relative_to(output_root),
                output_root=stage_root,
            )
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace(final_path, backup_path)
            moved_backups.append(("file", backup_path, final_path))
        for final_path in final_plan.directory_targets:
            if not os.path.lexists(os.fspath(final_path)):
                continue
            backup_path = ensure_safe_output_file_target(
                backup_root / "directories" / final_path.relative_to(output_root),
                output_root=stage_root,
            )
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace(final_path, backup_path)
            moved_backups.append(("directory", backup_path, final_path))

        for staged_path, final_path in zip(
            staged_file_targets,
            final_plan.file_targets,
            strict=True,
        ):
            if os.path.lexists(os.fspath(final_path)):
                raise RuntimeError(
                    f"OpenLab final file target changed during package commit: {final_path}"
                )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace(staged_path, final_path)
            installed_targets.append(("file", final_path))
        for staged_path, final_path in zip(
            staged_directory_targets,
            final_plan.directory_targets,
            strict=True,
        ):
            if os.path.lexists(os.fspath(final_path)):
                raise RuntimeError(
                    f"OpenLab final directory target changed during package commit: {final_path}"
                )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace(staged_path, final_path)
            installed_targets.append(("directory", final_path))
    except Exception as exc:
        rollback_errors: list[str] = []
        for kind, final_path in reversed(installed_targets):
            try:
                _remove_committed_hplc_target(
                    kind,
                    final_path,
                    output_root=output_root,
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"remove {final_path}: {rollback_exc}")
        for _kind, backup_path, final_path in reversed(moved_backups):
            try:
                if os.path.lexists(os.fspath(final_path)):
                    raise RuntimeError(
                        "unexpected target appeared before rollback restoration"
                    )
                final_path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_replace(backup_path, final_path)
            except Exception as rollback_exc:
                rollback_errors.append(f"restore {final_path}: {rollback_exc}")
        if rollback_errors:
            raise _HplcRollbackError(
                "OpenLab package commit failed and rollback was incomplete; "
                f"recovery files were preserved under {stage_root}. Details: "
                + "; ".join(rollback_errors)
            ) from exc
        raise RuntimeError(
            f"OpenLab package commit failed; the previous package was restored: {exc}"
        ) from exc


def _atomic_replace(source: Path, target: Path) -> None:
    os.replace(source, target)


def _remove_committed_hplc_target(
    kind: str,
    path: Path,
    *,
    output_root: Path,
) -> None:
    if kind == "file":
        safe_path = _assert_safe_regular_file(path, output_root=output_root)
        safe_path.unlink()
        return
    if kind != "directory":
        raise ValueError(f"Unknown OpenLab package target kind: {kind}")
    plan = plan_safe_owned_directory_removal(path, output_root=output_root)
    for child in plan[1]:
        _assert_safe_regular_file(child, output_root=output_root)
    apply_safe_owned_directory_removal(plan, output_root=output_root)


def _remove_safe_owned_tree(path: Path, *, output_root: Path) -> None:
    if not os.path.lexists(os.fspath(path)):
        return
    plan = plan_safe_owned_directory_removal(path, output_root=output_root)
    for child in plan[1]:
        _assert_safe_regular_file(child, output_root=output_root)
    apply_safe_owned_directory_removal(plan, output_root=output_root)


def extract_hplc_openlab_dataset(input_root: Path, since: date) -> dict[str, Any]:
    """Return workbook-ready raw signals, vendor peak results, and provenance."""
    dx_paths = sorted(input_root.rglob("*.dx"), key=lambda path: str(path).casefold())
    if not dx_paths:
        raise FileNotFoundError(f"No Agilent OpenLab .dx files found under: {input_root}")

    selected: list[dict[str, Any]] = []
    skipped_before_cutoff = 0
    discovery_errors: list[dict[str, str]] = []
    context_cache: dict[Path, dict[str, Any]] = {}

    for dx_path in dx_paths:
        try:
            result_set_dir = dx_path.parent.resolve()
            if result_set_dir not in context_cache:
                context_cache[result_set_dir] = _parse_result_set_context(result_set_dir)
            context = context_cache[result_set_dir]
            # Selected files are fully CRC-checked by decode_agilent_dx below.
            # The cutoff probe only needs the two required XML members, which
            # are validated as they are read.
            metadata_probe = read_agilent_dx_metadata(dx_path, verify_members=False)
            raw_metadata = dict(metadata_probe.get("metadata") or {})
            raw_file_info = context["injections_by_raw_file"].get(dx_path.name, {})
            acquisition, acquisition_source = _resolve_acquisition_datetime(
                raw_metadata=raw_metadata,
                raw_file_info=raw_file_info,
            )
        except Exception as exc:
            discovery_errors.append(
                {
                    "relative_path": _relative_text(dx_path, input_root),
                    "stage": "metadata_probe",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if acquisition.date() < since:
            skipped_before_cutoff += 1
            continue

        try:
            decoded = decode_agilent_dx(dx_path)
            injection = _build_injection_record(
                input_root=input_root,
                dx_path=dx_path,
                acquisition=acquisition,
                acquisition_source=acquisition_source,
                decoded=decoded,
                context=context,
            )
            selected.append(injection)
        except Exception as exc:
            discovery_errors.append(
                {
                    "relative_path": _relative_text(dx_path, input_root),
                    "stage": "raw_decode",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    if discovery_errors:
        rendered = "; ".join(
            f"{item['relative_path']} [{item['stage']}]: {item['error']}" for item in discovery_errors[:8]
        )
        raise RuntimeError(
            f"OpenLab export is incomplete because {len(discovery_errors)} candidate file(s) failed: {rendered}"
        )
    if not selected:
        raise ValueError(f"No OpenLab acquisitions on or after {since.isoformat()} were found")

    selected.sort(key=lambda item: (item["_acquisition_sort"], item["source_relative"].casefold()))
    result_set_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in selected:
        result_set_members[item["_result_set_key"]].append(item)
    result_set_keys = sorted(
        set(result_set_members),
        key=lambda key: result_set_members[key][0]["_acquisition_sort"],
    )
    result_set_ids = {key: f"R{index:02d}" for index, key in enumerate(result_set_keys, start=1)}
    raw_sheet_names = {key: f"Raw_{result_set_ids[key]}" for key in result_set_keys}

    peaks: list[dict[str, Any]] = []
    raw_index: list[dict[str, Any]] = []
    raw_sheets: list[dict[str, Any]] = []
    for index, injection in enumerate(selected, start=1):
        injection_id = f"I{index:03d}"
        result_set_key = injection["_result_set_key"]
        injection["injection_id"] = injection_id
        injection["result_set_id"] = result_set_ids[result_set_key]
        injection["raw_sheet"] = raw_sheet_names[result_set_key]
        for peak in injection.pop("_peaks"):
            peak.update(
                {
                    "injection_id": injection_id,
                    "result_set_id": injection["result_set_id"],
                    "result_set_folder": injection["result_set_folder"],
                    "acquisition_local": injection["acquisition_local"],
                    "batch_folder": injection["batch_folder"],
                    "sample_name": injection["sample_name"],
                    "vial_position": injection["vial_position"],
                    "raw_file": injection["raw_file"],
                    "acquisition_method": injection["acquisition_method"],
                    "processing_method": injection["processing_method"],
                }
            )
            peaks.append(peak)

    result_sets: list[dict[str, Any]] = []
    for result_set_key in result_set_keys:
        members = result_set_members[result_set_key]
        raw_sheet = raw_sheet_names[result_set_key]
        columns: list[dict[str, Any]] = []
        for injection in members:
            time_columns: list[str] = []
            signal_columns: list[str] = []
            for signal_number, signal in enumerate(injection.pop("_signals"), start=1):
                raw_key = injection["injection_id"]
                if len(injection["signal_names"]) > 1:
                    raw_key = f"{raw_key}_S{signal_number:02d}"
                time_column_index = len(columns) * 2 + 1
                signal_column_index = time_column_index + 1
                time_column = _excel_column(time_column_index)
                signal_column = _excel_column(signal_column_index)
                time_columns.append(time_column)
                signal_columns.append(signal_column)
                columns.append(
                    {
                        "signal_key": raw_key,
                        "injection_id": injection["injection_id"],
                        "signal_name": signal["name"],
                        "time_header": f"{raw_key}_Time_min",
                        "signal_header": f"{raw_key}_{signal['name']}_{signal['unit'] or 'signal'}",
                        "time": signal["time"],
                        "signal": signal["signal"],
                    }
                )
                raw_index.append(
                    {
                        "raw_sheet": raw_sheet,
                        "time_column": time_column,
                        "signal_column": signal_column,
                        "signal_key": raw_key,
                        "injection_id": injection["injection_id"],
                        "result_set_id": injection["result_set_id"],
                        "acquisition_local": injection["acquisition_local"],
                        "sample_name": injection["sample_name"],
                        "vial_position": injection["vial_position"],
                        "raw_file": injection["raw_file"],
                        "signal_name": signal["name"],
                        "detector": signal["detector"],
                        "wavelength_nm": signal["wavelength_nm"],
                        "unit": signal["unit"],
                        "point_count": signal["point_count"],
                        "time_start_min": signal["time_start_min"],
                        "time_end_min": signal["time_end_min"],
                        "source_sha256": injection["source_sha256"],
                    }
                )
            injection["time_columns"] = ",".join(time_columns)
            injection["signal_columns"] = ",".join(signal_columns)

        first = members[0]
        last = members[-1]
        result_sets.append(
            {
                "result_set_id": result_set_ids[result_set_key],
                "batch_folder": first["batch_folder"],
                "result_set_folder": first["result_set_folder"],
                "raw_sheet": raw_sheet,
                "first_acquisition_local": first["acquisition_local"],
                "last_acquisition_local": last["acquisition_local"],
                "injection_count": len(members),
                "peak_count": sum(item["vendor_peak_count"] for item in members),
                "acquisition_methods": sorted(
                    {
                        item["acquisition_method"]
                        for item in members
                        if item["acquisition_method"]
                    }
                ),
                "processing_methods": sorted(
                    {
                        item["processing_method"]
                        for item in members
                        if item["processing_method"]
                    }
                ),
                "instrument_modules": first["instrument_modules"],
            }
        )
        raw_sheets.append(
            {
                "name": raw_sheet,
                "result_set_id": result_set_ids[result_set_key],
                "batch_folder": first["batch_folder"],
                "result_set_folder": first["result_set_folder"],
                "columns": columns,
            }
        )

    for injection in selected:
        injection.pop("_acquisition_sort", None)
        injection.pop("_result_set_key", None)

    peaks.sort(key=lambda item: (item["injection_id"], item["signal_name"], item["peak_ordinal"]))
    selected_dates = sorted({item["acquisition_local"][:10] for item in selected})
    summary = {
        "cutoff_date": since.isoformat(),
        "source_dx_count": len(dx_paths),
        "skipped_before_cutoff": skipped_before_cutoff,
        "selected_injection_count": len(selected),
        "result_set_count": len(result_sets),
        "batch_count": len({item["batch_folder"] for item in selected}),
        "peak_count": len(peaks),
        "signal_count": len(raw_index),
        "signal_point_count": sum(item["point_count"] for item in raw_index),
        "selected_acquisition_dates": selected_dates,
        "decode_failure_count": 0,
        "all_times_strictly_increasing": all(item["time_monotonic"] for item in selected),
        "all_signals_finite": all(item["signal_finite"] for item in selected),
    }
    return {
        "schema_version": "1.0",
        "data_type": OPENLAB_DATA_TYPE,
        "processor_name": PROCESSOR_NAME,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_root_name": input_root.name,
        "cutoff_date": since.isoformat(),
        "library_provenance": {
            "raw_decoder": DX_DECODER_NAME,
            "raw_decoder_version": DX_DECODER_VERSION,
            "raw_decoder_implementation": "in-repository ACMD20/Signal179 decoder",
            "raw_decoder_external_runtime_required": False,
            "validation_oracle": "rainbow-api 1.3.1 (regression validation only)",
            "acquisition_time": (
                "result-set .acaml InjectionAcqDateTime converted to the local offset "
                "recorded by .dx injection.acmd RunDateTime"
            ),
            "result_parser": "project XML/OPC integration layer",
            "workbook_writer": "@oai/artifact-tool",
        },
        "scientific_boundary": {
            "manual_check_required": True,
            "peak_source": "Agilent OpenLab vendor integration results from .rx",
            "identity_assignment": IDENTITY_BOUNDARY,
            "forbidden_outputs": [
                "automatic product identification",
                "automatic retention-time identity assignment",
                "conversion without calibration and role mapping",
                "selectivity without calibration and role mapping",
                "yield without calibration and role mapping",
            ],
            "telemetry_exported": False,
            "plots_created": False,
        },
        "summary": summary,
        "result_sets": result_sets,
        "injections": selected,
        "peaks": peaks,
        "raw_index": raw_index,
        "raw_sheets": raw_sheets,
    }


def _build_injection_record(
    *,
    input_root: Path,
    dx_path: Path,
    acquisition: datetime,
    acquisition_source: str,
    decoded: Any,
    context: dict[str, Any],
) -> dict[str, Any]:
    relative = dx_path.relative_to(input_root)
    if input_root.suffix.casefold() == ".rslt" and len(relative.parts) == 1:
        batch_folder = input_root.parent.name
    else:
        batch_folder = relative.parts[0] if relative.parts else input_root.name
    result_set_folder = dx_path.parent.name
    result_set_key = _relative_text(dx_path.parent, input_root)
    raw_file_info = context["injections_by_raw_file"].get(dx_path.name, {})
    setup_info = context["sample_setups"].get(raw_file_info.get("SampleSetupId", ""), {})
    signals: list[dict[str, Any]] = []
    for datafile in decoded.datafiles:
        x = np.asarray(datafile.xlabels, dtype=float).reshape(-1)
        y = np.asarray(datafile.data, dtype=float)
        if y.ndim == 2 and y.shape[1] == 1:
            y = y[:, 0]
        else:
            y = y.reshape(-1)
        if len(x) != len(y) or len(x) < 2:
            raise ValueError(f"decoded signal has incompatible time/signal dimensions: {dx_path.name}/{datafile.name}")
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError(f"decoded signal contains non-finite values: {dx_path.name}/{datafile.name}")
        if not np.all(np.diff(x) > 0):
            raise ValueError(f"decoded signal time axis is not strictly increasing: {dx_path.name}/{datafile.name}")
        metadata = dict(datafile.metadata or {})
        description = str(metadata.get("description") or "")
        wavelength_match = _WAVELENGTH.search(description)
        interval_seconds = float(np.median(np.diff(x)) * 60.0)
        signals.append(
            {
                "name": str(datafile.name),
                "detector": str(datafile.detector or metadata.get("device") or ""),
                "description": description,
                "wavelength_nm": float(wavelength_match.group("value")) if wavelength_match else None,
                "unit": str(metadata.get("unit") or ""),
                "point_count": int(len(x)),
                "time_start_min": float(x[0]),
                "time_end_min": float(x[-1]),
                "sampling_interval_s": interval_seconds,
                "signal_min": float(np.min(y)),
                "signal_max": float(np.max(y)),
                "time": x.tolist(),
                "signal": y.tolist(),
            }
        )
    if not signals:
        raise ValueError(f"no detector signal decoded from {dx_path}")

    rx_result = _parse_optional_rx_result(dx_path.with_suffix(".rx"), context)
    peak_areas = [peak["area"] for peak in rx_result["peaks"] if peak["area"] is not None]
    peak_area_percents = [
        peak["area_percent"] for peak in rx_result["peaks"] if peak["area_percent"] is not None
    ]
    raw_metadata = dict(decoded.metadata or {})
    sample_name = str(raw_metadata.get("sample") or raw_file_info.get("SampleName") or "")
    vial_position = str(raw_metadata.get("vialpos") or raw_file_info.get("VialNumber") or "")
    acquisition_method = str(raw_metadata.get("method") or raw_file_info.get("AcqMethodName") or "")
    order = _as_int(raw_file_info.get("SampleOrderNumber"))

    return {
        "_acquisition_sort": acquisition,
        "_result_set_key": result_set_key,
        "_signals": signals,
        "_peaks": rx_result["peaks"],
        "batch_folder": batch_folder,
        "result_set_folder": result_set_folder,
        "sequence_order": order,
        "acquisition_local": acquisition.replace(tzinfo=None).isoformat(timespec="seconds"),
        "acquisition_date": acquisition.date().isoformat(),
        "acquisition_time_source": acquisition_source,
        "sample_name": sample_name,
        "vial_position": vial_position,
        "raw_file": dx_path.name,
        "injection_guid": str(raw_file_info.get("InjectionId") or ""),
        "source_relative": _relative_text(dx_path, input_root),
        "source_size_bytes": dx_path.stat().st_size,
        "source_sha256": file_sha256(dx_path),
        "acquisition_method": acquisition_method,
        "processing_method": context["processing_method"],
        "sequence_name": context.get("sequence_name", ""),
        "sequence_file": context.get("sequence_file", ""),
        "result_name": context.get("result_name", ""),
        "injection_volume_ul": setup_info.get("injection_volume_ul"),
        "instrument_modules": context["instrument_modules"],
        "signal_names": [signal["name"] for signal in signals],
        "signal_descriptions": [signal["description"] for signal in signals],
        "detectors": [signal["detector"] for signal in signals],
        "wavelengths_nm": [signal["wavelength_nm"] for signal in signals],
        "units": [signal["unit"] for signal in signals],
        "signal_point_count": sum(signal["point_count"] for signal in signals),
        "time_start_min": min(signal["time_start_min"] for signal in signals),
        "time_end_min": max(signal["time_end_min"] for signal in signals),
        "sampling_interval_s": min(signal["sampling_interval_s"] for signal in signals),
        "signal_min": min(signal["signal_min"] for signal in signals),
        "signal_max": max(signal["signal_max"] for signal in signals),
        "vendor_peak_count": len(rx_result["peaks"]),
        "vendor_peak_area_total": float(sum(peak_areas)) if peak_areas else 0.0,
        "vendor_area_percent_sum": float(sum(peak_area_percents)) if peak_area_percents else 0.0,
        "openlab_processing_state": rx_result["state"],
        "openlab_processing_warning": rx_result["warning"],
        "decode_status": "OK",
        "time_monotonic": True,
        "signal_finite": True,
        "manual_check_required": True,
    }


def _parse_result_set_context(result_set_dir: Path) -> dict[str, Any]:
    acaml_files = sorted(result_set_dir.glob("*.acaml"))
    if not acaml_files:
        return {
            "processing_method": "",
            "sequence_name": "",
            "sequence_file": "",
            "result_name": "",
            "instrument_modules": "",
            "injections_by_raw_file": {},
            "sample_setups": {},
            "signals": {},
        }
    root = ET.parse(acaml_files[0]).getroot()

    sequence_name = ""
    sequence_file = ""
    result_name = ""
    sample_contexts = _first_descendant(root, "SampleContexts")
    if sample_contexts is not None:
        setup_context = next(iter(_direct_local(sample_contexts, "Setup")), None)
        result_context = next(iter(_direct_local(sample_contexts, "MeasData")), None)
        if setup_context is not None:
            ident = next(iter(_direct_local(setup_context, "IdentParam")), None)
            if ident is not None:
                sequence_name = _text_of_direct(ident, "Name")
            binary = next(iter(_direct_local(setup_context, "BinaryData")), None)
            if binary is not None:
                for data_item in _direct_local(binary, "DataItem"):
                    candidate = _text_of_direct(data_item, "Name")
                    if candidate.casefold().endswith(".sqx"):
                        sequence_file = candidate
                        break
        if result_context is not None:
            ident = next(iter(_direct_local(result_context, "IdentParam")), None)
            if ident is not None:
                result_name = _text_of_direct(ident, "Name")

    injections_by_raw_file: dict[str, dict[str, Any]] = {}
    for element in _iter_local(root, "InjectionMetaData"):
        info = dict(element.attrib)
        order = _first_descendant(element, "SampleOrderNumber")
        if order is not None:
            info["SampleOrderNumber"] = order.get("val")
        raw_file = info.get("RawDataFileName")
        if raw_file:
            injections_by_raw_file[str(raw_file)] = info

    sample_setups: dict[str, dict[str, Any]] = {}
    for setup in _iter_local(root, "Setup"):
        setup_id = setup.get("id")
        if not setup_id:
            continue
        volume = _first_descendant(setup, "InjectionVolume")
        sample_setups[setup_id] = {
            "injection_volume_ul": _float_attr(volume, "val"),
            "vial_position": _text_of_first(setup, "VialNumber"),
            "sample_name": _text_of_first(setup, "Name"),
        }

    signals: dict[str, dict[str, Any]] = {}
    for signal in _iter_local(root, "Signal"):
        signal_id = signal.get("id")
        if not signal_id:
            continue
        signals[signal_id] = {
            "name": _text_of_direct(signal, "Name"),
            "description": _text_of_direct(signal, "Description"),
            "type": _text_of_direct(signal, "Type"),
            "trace_id": _text_of_direct(signal, "TraceID"),
            "detector": _text_of_direct(signal, "DetectorName"),
        }

    method_names = [
        _text_of_direct(method, "Name")
        for method in _iter_local(root, "Method")
        if _text_of_direct(method, "Name")
    ]
    module_parts: list[str] = []
    for module in _iter_local(root, "Module"):
        module_type = _text_of_direct(module, "Type")
        part_no = _text_of_direct(module, "PartNo")
        serial = _text_of_direct(module, "SerialNo")
        name = _text_of_direct(module, "Name")
        rendered = "/".join(part for part in (module_type or name, part_no, serial) if part)
        if rendered:
            module_parts.append(rendered)

    return {
        "processing_method": method_names[0] if method_names else "",
        "sequence_name": sequence_name,
        "sequence_file": sequence_file,
        "result_name": result_name,
        "instrument_modules": "; ".join(dict.fromkeys(module_parts)),
        "injections_by_raw_file": injections_by_raw_file,
        "sample_setups": sample_setups,
        "signals": signals,
    }


def _parse_rx_result(rx_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    if not rx_path.is_file():
        return {"peaks": [], "state": "missing_rx", "warning": "配套 .rx 结果文件缺失"}
    with zipfile.ZipFile(rx_path) as archive:
        try:
            xml_bytes = archive.read("Base/InjectionACAML")
        except KeyError as exc:
            raise ValueError(f"{rx_path.name} does not contain Base/InjectionACAML") from exc
    root = ET.fromstring(xml_bytes)
    result = next(iter(_iter_local(root, "Result")), None)
    if result is None:
        return {"peaks": [], "state": "missing_result", "warning": "配套 .rx 中没有 Result 节点"}

    peaks: list[dict[str, Any]] = []
    signal_peak_groups: dict[tuple[str, str | int], list[dict[str, Any]]] = {}
    for signal_result_index, signal_result in enumerate(
        _direct_local(result, "SignalResult")
    ):
        signal_ref = _first_descendant(signal_result, "Signal_ID")
        signal_id = signal_ref.get("id") if signal_ref is not None else ""
        signal_info = context["signals"].get(signal_id, {})
        signal_type = str(signal_info.get("type") or "")
        signal_peaks = list(_direct_local(signal_result, "Peak"))
        if signal_type and signal_type.casefold() != "chromatogram":
            continue
        group_key: tuple[str, str | int] = (
            ("signal_id", signal_id)
            if signal_id
            else ("signal_result", signal_result_index)
        )
        parsed_signal_peaks = signal_peak_groups.setdefault(group_key, [])
        parsed_signal_peaks.extend(
            _peak_record(peak, signal_info, 0) for peak in signal_peaks
        )

    for parsed_signal_peaks in signal_peak_groups.values():
        parsed_signal_peaks.sort(key=_vendor_peak_retention_order)
        for ordinal, peak_record in enumerate(parsed_signal_peaks, start=1):
            peak_record["peak_ordinal"] = ordinal
            peaks.append(peak_record)

    status_items: list[str] = []
    state = _text_of_first(result, "TransformationChainState") or "not_recorded"
    for item in _iter_local(result, "ProcessingStatusItem"):
        category = _text_of_direct(item, "Category")
        item_state = _text_of_direct(item, "TransformationState")
        message = _text_of_direct(item, "Message")
        status_items.append(": ".join(part for part in (category, item_state, message) if part))
    return {
        "peaks": peaks,
        "state": state,
        "warning": " | ".join(status_items),
    }


def _parse_optional_rx_result(
    rx_path: Path,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Read optional vendor results without blocking independent raw .dx decoding."""
    try:
        return _parse_rx_result(rx_path, context)
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {
            "peaks": [],
            "state": "vendor_result_unreadable",
            "warning": f"配套 .rx 厂商对照不可读：{type(exc).__name__}: {exc}",
        }


def _peak_record(peak: ET.Element, signal_info: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "signal_name": str(signal_info.get("name") or ""),
        "signal_description": str(signal_info.get("description") or ""),
        "peak_ordinal": ordinal,
        "retention_time_min": _value(peak, "RetentionTime"),
        "begin_time_min": _value(peak, "BeginTime"),
        "end_time_min": _value(peak, "EndTime"),
        "width_base_min": _value(peak, "WidthBase"),
        "area": _value(peak, "Area"),
        "area_unit": _unit(peak, "Area"),
        "area_percent": _value(peak, "AreaPercent"),
        "height": _value(peak, "Height"),
        "height_unit": _unit(peak, "Height"),
        "height_percent": _value(peak, "HeightPercent"),
        "symmetry": _value(peak, "Symmetry"),
        "peak_type": _text_of_direct(peak, "Type"),
        "baseline_code": _text_of_direct(peak, "BaselineCode").strip(),
        "baseline_start": _value(peak, "BaselineStart"),
        "baseline_end": _value(peak, "BaselineEnd"),
        "baseline_model": _text_of_direct(peak, "BaselineModel"),
        "purity_passed": _bool_text(_text_of_direct(peak, "PurityPassed")),
        "ms_purity_passed": _bool_text(_text_of_direct(peak, "MSPurityPassed")),
        "identity_assignment": IDENTITY_BOUNDARY,
        "manual_check_required": True,
    }


def _vendor_peak_retention_order(peak: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return a chronological key; Python's stable sort preserves exact XML ties."""

    def ordered_number(value: Any) -> float:
        return float(value) if value is not None else math.inf

    return (
        ordered_number(peak.get("retention_time_min")),
        ordered_number(peak.get("begin_time_min")),
        ordered_number(peak.get("end_time_min")),
        ordered_number(peak.get("area")),
    )


def _build_workbook_plan(
    dataset: dict[str, Any],
    summary_workbook_path: Path,
) -> dict[str, Any]:
    if dataset.get("analysis"):
        return {
            "summary_workbook": summary_workbook_path.name,
            "batch_directory": "",
            "batch_workbooks": [],
            "analysis_sheet_names": [
                "样品结果",
                "峰明细",
                "数据处理记录",
                "排除数据",
                "重打分组明细",
                "待人工复核",
                "分析参数",
            ],
            "excel_includes_raw_signals": False,
            "raw_signal_handling": (
                "decoded and validated in the processed audit dataset; intentionally omitted "
                "from the compact analysis workbook"
            ),
        }
    batch_names = list(
        dict.fromkeys(
            str(item.get("batch_folder") or "未命名批次")
            for item in dataset.get("injections", [])
        )
    )
    batch_directory = f"{summary_workbook_path.stem}_批次工作簿"
    batch_workbooks: list[dict[str, Any]] = []
    for index, batch_name in enumerate(batch_names, start=1):
        batch_id = f"B{index:02d}"
        filename = f"{batch_id}_{_safe_filename_component(batch_name)}.xlsx"
        result_set_ids = [
            str(item["result_set_id"])
            for item in dataset.get("result_sets", [])
            if str(item.get("batch_folder") or "") == batch_name
        ]
        injection_ids = [
            str(item["injection_id"])
            for item in dataset.get("injections", [])
            if str(item.get("batch_folder") or "") == batch_name
        ]
        batch_workbooks.append(
            {
                "batch_id": batch_id,
                "batch_folder": batch_name,
                "filename": filename,
                "relative_path": (Path(batch_directory) / filename).as_posix(),
                "result_set_ids": result_set_ids,
                "injection_ids": injection_ids,
            }
        )
    return {
        "summary_workbook": summary_workbook_path.name,
        "batch_directory": batch_directory,
        "batch_workbooks": batch_workbooks,
        "excel_includes_raw_signals": False,
        "raw_signal_handling": (
            "decoded and validated in the processed dataset; intentionally omitted "
            "from user-facing Excel workbooks"
        ),
    }


def _safe_filename_component(value: str, *, max_length: int = 80) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("_", str(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(". ")
    cleaned = cleaned[:max_length].rstrip(". ")
    return cleaned or "未命名批次"


def _planned_workbook_paths(
    output_root: Path,
    summary_workbook_path: Path,
    workbook_plan: dict[str, Any],
) -> list[Path]:
    planned = [lexical_absolute_path(summary_workbook_path)]
    for item in workbook_plan.get("batch_workbooks", []):
        relative_path = Path(str(item.get("relative_path") or ""))
        if not str(relative_path) or relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Invalid planned batch workbook path: {relative_path}")
        planned.append(lexical_absolute_path(output_root / relative_path))
    return planned


def _run_workbook_builder(
    *,
    project_root: Path,
    node_exe: Path,
    builder_workdir: Path,
    builder_copy_path: Path,
    dataset_path: Path,
    workbook_path: Path,
    previews_dir: Path,
    verification_path: Path,
    log_path: Path,
) -> None:
    builder_source = _validate_workbook_builder_inputs(project_root, node_exe)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_node = node_exe.resolve()
    builder_copy = ensure_safe_output_file_target(
        builder_copy_path,
        output_root=builder_workdir.parent,
    )
    if builder_copy.resolve() == builder_source.resolve():
        raise ValueError("OpenLab workbook builder source and output copy must be different files")
    builder_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(builder_source, builder_copy)
    command = [
        str(resolved_node),
        str(builder_copy),
        "--input",
        str(dataset_path.resolve()),
        "--output",
        str(workbook_path.resolve()),
        "--preview-dir",
        str(previews_dir.resolve()),
        "--verification",
        str(verification_path.resolve()),
    ]
    completed = subprocess.run(
        command,
        cwd=builder_workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_lines = [
        f"exit_code={completed.returncode}",
        "[stdout]",
        completed.stdout,
        "[stderr]",
        completed.stderr,
    ]
    if completed.returncode != 0:
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        raise RuntimeError(
            "Excel workbook builder failed; see log: "
            f"{log_path}. Last error: {(completed.stderr or completed.stdout)[-1200:]}"
        )
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        built_workbooks = _planned_workbook_paths(
            workbook_path.parent,
            workbook_path,
            payload["workbook_plan"],
        )
        freeze_evidence = {
            str(path.resolve()): _patch_xlsx_top_row_freeze(path)
            for path in built_workbooks
        }
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        verification["top_row_freeze"] = {
            "implementation": "controlled OOXML compatibility patch after artifact-tool export",
            "reason": "artifact-tool 2.8.6 freezeRows does not serialize worksheet panes",
            "workbooks": freeze_evidence,
        }
        verification_path.write_text(
            json.dumps(verification, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log_lines.extend(
            [
                "[top_row_freeze]",
                json.dumps(freeze_evidence, ensure_ascii=False),
            ]
        )
    except Exception as exc:
        log_lines.extend(["[top_row_freeze_error]", f"{type(exc).__name__}: {exc}"])
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        raise RuntimeError(
            "Excel workbook was exported but the required frozen top row could not be verified"
        ) from exc
    log_path.write_text("\n".join(log_lines), encoding="utf-8")


def _patch_xlsx_top_row_freeze(workbook_path: Path) -> dict[str, Any]:
    """Apply and read back a one-row freeze pane without changing workbook data."""
    workbook = workbook_path.resolve()
    if not workbook.is_file() or not zipfile.is_zipfile(workbook):
        raise RuntimeError(f"Workbook is missing or invalid before freeze patch: {workbook}")
    temporary_handle = tempfile.NamedTemporaryFile(
        prefix=f".{workbook.stem}.freeze-",
        suffix=".xlsx",
        dir=workbook.parent,
        delete=False,
    )
    temporary_path = Path(temporary_handle.name)
    temporary_handle.close()
    worksheet_names: list[str] = []
    try:
        with zipfile.ZipFile(workbook, "r") as source, zipfile.ZipFile(
            temporary_path,
            "w",
            allowZip64=True,
        ) as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", info.filename):
                    payload = _freeze_top_row_in_worksheet_xml(payload)
                    worksheet_names.append(info.filename)
                target.writestr(info, payload)
        if not worksheet_names:
            raise RuntimeError("Workbook contains no worksheet XML parts")
        os.replace(temporary_path, workbook)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    evidence = _read_xlsx_top_row_freeze(workbook)
    if evidence["worksheet_count"] != len(worksheet_names) or not evidence["all_frozen"]:
        raise RuntimeError(f"Frozen top-row readback failed: {evidence}")
    return evidence


def _freeze_top_row_in_worksheet_xml(payload: bytes) -> bytes:
    for _, namespace in ET.iterparse(BytesIO(payload), events=("start-ns",)):
        prefix, uri = namespace
        try:
            ET.register_namespace(prefix or "", uri)
        except ValueError:
            pass
    root = ET.fromstring(payload)
    namespace_uri = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""

    def qualified(local_name: str) -> str:
        return f"{{{namespace_uri}}}{local_name}" if namespace_uri else local_name

    sheet_views = root.find(qualified("sheetViews"))
    if sheet_views is None:
        sheet_views = ET.Element(qualified("sheetViews"))
        children = list(root)
        dimension = root.find(qualified("dimension"))
        insert_at = children.index(dimension) + 1 if dimension is not None else 0
        root.insert(insert_at, sheet_views)
    sheet_view = sheet_views.find(qualified("sheetView"))
    if sheet_view is None:
        sheet_view = ET.SubElement(sheet_views, qualified("sheetView"), {"workbookViewId": "0"})
    pane = sheet_view.find(qualified("pane"))
    if pane is None:
        pane = ET.Element(qualified("pane"))
        sheet_view.insert(0, pane)
    pane.attrib.clear()
    pane.attrib.update(
        {
            "ySplit": "1",
            "topLeftCell": "A2",
            "activePane": "bottomLeft",
            "state": "frozen",
        }
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _read_xlsx_top_row_freeze(workbook_path: Path) -> dict[str, Any]:
    frozen: list[str] = []
    worksheets: list[str] = []
    with zipfile.ZipFile(workbook_path, "r") as archive:
        for name in archive.namelist():
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                continue
            worksheets.append(name)
            root = ET.fromstring(archive.read(name))
            namespace_uri = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
            prefix = f"{{{namespace_uri}}}" if namespace_uri else ""
            pane = root.find(f"{prefix}sheetViews/{prefix}sheetView/{prefix}pane")
            if (
                pane is not None
                and pane.get("state") == "frozen"
                and pane.get("ySplit") == "1"
                and pane.get("topLeftCell") == "A2"
            ):
                frozen.append(name)
    return {
        "worksheet_count": len(worksheets),
        "frozen_top_row_count": len(frozen),
        "all_frozen": bool(worksheets) and len(frozen) == len(worksheets),
        "worksheet_parts": worksheets,
    }


def _validate_artifact_workdir(builder_workdir: Path) -> None:
    package_root = builder_workdir / "node_modules" / "@oai" / "artifact-tool"
    if not package_root.exists():
        raise RuntimeError(
            "Builder workdir must contain node_modules linked to the workspace dependency runtime; "
            f"missing {package_root}"
        )


def _metadata_payload(
    dataset: dict[str, Any],
    workbook_paths: list[Path],
    output_root: Path,
    dataset_path: Path,
    verification_path: Path,
) -> dict[str, Any]:
    relative_workbooks = [
        path.resolve().relative_to(output_root.resolve()).as_posix()
        for path in workbook_paths
    ]
    analysis = dataset.get("analysis") or {}
    algorithm_provenance = dict(dataset["library_provenance"])
    if analysis.get("analysis_version"):
        vendor_reprocessing = algorithm_provenance.get("vendor_reprocessing")
        algorithm_provenance["peak_integration"] = {
            "name": "Agilent OpenLab vendor integration",
            "analysis_version": analysis["analysis_version"],
            "vendor_method_required": bool(vendor_reprocessing),
            "source_priority": (
                "Agilent Processing Server complete-PMX reprocessed .rx"
                if vendor_reprocessing
                else "successful stored Agilent .rx only"
            ),
            "vendor_results_role": (
                "sole target source after explicit complete-PMX vendor reprocessing"
                if vendor_reprocessing
                else "sole target source when stored result is successful"
            ),
            "native_fallback_removed": True,
        }
    return {
        "dataset_id": f"hplc_openlab_{dataset['cutoff_date'].replace('-', '')}_plus",
        "data_type": dataset["data_type"],
        "processor_name": dataset["processor_name"],
        "processing_status": (
            "processed_to_compact_analysis_excel_no_plot"
            if dataset.get("analysis")
            else "processed_to_split_excel_no_plot"
        ),
        "source_root_name": dataset["source_root_name"],
        "cutoff_date": dataset["cutoff_date"],
        "processed_workbook": relative_workbooks[0],
        "processed_workbooks": relative_workbooks,
        "excel_output_layout": dataset["workbook_plan"],
        "processed_dataset": dataset_path.name,
        "verification_report": verification_path.name,
        "manual_check_required": True,
        "manual_check_items": [
            "目标峰使用用户提供的RT窗口候选映射，化学身份及峰积分边界仍需人工复核",
            "转化率、选择性、产率和回收率依据用户提供标曲与稀释倍数计算，属于待复核候选结果",
            "请优先复核待人工复核工作表、重打分组、同批次C₀及原厂结果可用性提示",
            "原始色谱信号已完整解码并保存在审计数据集中，但按用户要求不放入简化 Excel",
        ],
        "forbidden_claims": dataset["scientific_boundary"]["forbidden_outputs"],
        "key_results": {
            "decode": dataset["summary"],
            "analysis": analysis.get("summary", {}),
        },
        "algorithm_provenance": algorithm_provenance,
    }


def _summary_markdown(
    dataset: dict[str, Any],
    workbook_paths: list[Path],
    output_root: Path,
) -> str:
    summary = dataset["summary"]
    analysis_summary = dataset.get("analysis", {}).get("summary", {})
    vendor_reprocessing = dataset.get("library_provenance", {}).get("vendor_reprocessing")
    relative_workbooks = [
        path.resolve().relative_to(output_root.resolve()).as_posix()
        for path in workbook_paths
    ]
    return "\n".join(
        [
            "# Agilent OpenLab HPLC Raw Data Processing Summary",
            "",
            f"- Cutoff (inclusive): `{summary['cutoff_date']}`",
            f"- Selected injections: `{summary['selected_injection_count']}`",
            f"- Result sets: `{summary['result_set_count']}`",
            f"- Batches: `{summary['batch_count']}`",
            f"- Vendor peaks retained for validation: `{summary['peak_count']}`",
            f"- Agilent Processing Server reprocessed: `{'yes' if vendor_reprocessing else 'no'}`",
            f"- Raw signal points: `{summary['signal_point_count']}`",
            f"- Vendor-result unavailable injections: `{analysis_summary.get('vendor_result_unavailable_injection_count', 0)}`",
            f"- Final sample rows: `{analysis_summary.get('final_sample_row_count', 0)}`",
            f"- Manual-review items: `{analysis_summary.get('manual_review_item_count', 0)}`",
            f"- Excel workbooks: `{len(relative_workbooks)}`",
            f"- Summary workbook: `{relative_workbooks[0]}`",
            *[f"- Batch workbook: `{path}`" for path in relative_workbooks[1:]],
            "- Raw signal points in Excel: `no` (retained in the processed audit dataset)",
            "- Plots created: `no`",
            "- Candidate conversion/selectivity/yield calculations: `yes` (user-supplied RT mapping/calibration; manual review required)",
            "- Automatic final chemical or mechanistic claims: `no`",
            "",
        ]
    )


def _parse_acquisition_datetime(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("OpenLab manifest does not contain an acquisition date")
    # OpenLab serializes .NET DateTime values with variable fractional-second
    # precision.  The bundled runtime requires exactly six digits when a
    # fraction is present, so pad short values and truncate excess precision
    # while retaining the original UTC offset.
    text = re.sub(
        r"\.(\d+)(?=(?:Z|[+-]\d{2}:\d{2})?$)",
        lambda match: f".{match.group(1)[:6].ljust(6, '0')}",
        text,
    )
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    return datetime.fromisoformat(normalized)


def _resolve_acquisition_datetime(
    *,
    raw_metadata: dict[str, Any],
    raw_file_info: dict[str, Any],
) -> tuple[datetime, str]:
    """Resolve the injection-specific time and retain the .dx local UTC offset."""
    manifest_time = _parse_acquisition_datetime(raw_metadata.get("date"))
    result_set_value = str(raw_file_info.get("InjectionAcqDateTime") or "").strip()
    if not result_set_value:
        return manifest_time, "dx_injection_acmd.RunDateTime"
    injection_time = _parse_acquisition_datetime(result_set_value)
    if manifest_time.tzinfo is not None:
        if injection_time.tzinfo is None:
            injection_time = injection_time.replace(tzinfo=manifest_time.tzinfo)
        else:
            injection_time = injection_time.astimezone(manifest_time.tzinfo)
    return injection_time, "result_set_acaml.InjectionMetaData.InjectionAcqDateTime"


def _relative_text(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter_local(element: ET.Element, name: str):
    return (item for item in element.iter() if _local_name(item.tag) == name)


def _direct_local(element: ET.Element, name: str):
    return (item for item in list(element) if _local_name(item.tag) == name)


def _first_descendant(element: ET.Element, name: str) -> ET.Element | None:
    return next(iter(_iter_local(element, name)), None)


def _text_of_first(element: ET.Element, name: str) -> str:
    item = _first_descendant(element, name)
    return (item.text or "").strip() if item is not None else ""


def _text_of_direct(element: ET.Element, name: str) -> str:
    item = next(iter(_direct_local(element, name)), None)
    return (item.text or "").strip() if item is not None else ""


def _float_attr(element: ET.Element | None, attr: str) -> float | None:
    if element is None:
        return None
    return _finite_float(element.get(attr))


def _value(element: ET.Element, name: str) -> float | None:
    return _float_attr(next(iter(_direct_local(element, name)), None), "val")


def _unit(element: ET.Element, name: str) -> str:
    item = next(iter(_direct_local(element, name)), None)
    return str(item.get("unit") or "") if item is not None else ""


def _finite_float(value: object) -> float | None:
    try:
        result = float(str(value))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _as_int(value: object) -> int | None:
    number = _finite_float(value)
    return int(number) if number is not None else None


def _bool_text(value: str) -> bool | None:
    normalized = value.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _excel_column(index: int) -> str:
    if index <= 0:
        raise ValueError("Excel column index must be positive")
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
