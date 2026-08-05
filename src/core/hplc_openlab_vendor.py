from __future__ import annotations

import json
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

from src.core.file_utils import file_sha256


VENDOR_RESULT_ORIGIN = "agilent_processing_server_reprocessed_rx"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BUNDLED_RUNTIME_ROOT = _PROJECT_ROOT / "vendor" / "agilent_openlab_processing" / "2.5"
_BUNDLED_RUNTIME_MANIFEST = _BUNDLED_RUNTIME_ROOT / "manifest.json"
_LOCAL_RUNTIME_CACHE = _PROJECT_ROOT / ".local_vendor_runtime"
_REQUIRED_RUNTIME_FILES = (
    "Agilent.Chromatography.DataAnalysis.Processing.ProcessingServer.exe",
    "Agilent.Chromatography.DataAnalysis.Processing.ProcessingServices.dll",
    "Agilent.Chromatography.DataAnalysis.Services.dll",
    "Agilent.OpenLab.CDSShared.ProcessingClients.dll",
    "Agilent.Acaml.Core.dll",
    "Agilent.Acaml21.Utilities.dll",
)
_VENDOR_EQUIVALENCE_NUMERIC_FIELDS = (
    "retention_time_min",
    "begin_time_min",
    "end_time_min",
    "width_base_min",
    "area",
    "area_percent",
    "height",
    "height_percent",
    "symmetry",
    "baseline_start",
    "baseline_end",
)
_VENDOR_EQUIVALENCE_VALUE_FIELDS = (
    "baseline_model",
    "baseline_code",
    "peak_type",
    "area_unit",
    "height_unit",
    "purity_passed",
    "ms_purity_passed",
)


@dataclass(frozen=True)
class BundledOpenLabVendorAssets:
    runtime_root: Path
    runtime_bin: Path
    bridge_exe: Path
    processing_method: Path
    archive_path: Path
    archive_sha256: str
    manifest: dict[str, Any]


def resolve_bundled_openlab_vendor_assets() -> BundledOpenLabVendorAssets:
    """Verify and materialize the project-bundled OpenLab processing runtime.

    The checked-in runtime is one ZIP object plus a per-file SHA-256 manifest.
    Extraction is confined to the ignored project-local runtime cache.  Every
    archive member is allow-listed and hash-verified before the cache is used.
    """
    manifest = _read_bundled_runtime_manifest(_BUNDLED_RUNTIME_MANIFEST)
    archive_record = dict(manifest["archive"])
    archive_path = (_BUNDLED_RUNTIME_ROOT / str(archive_record["path"])).resolve()
    archive_sha256 = str(archive_record["sha256"])
    if not archive_path.is_file():
        raise FileNotFoundError(f"Bundled Agilent runtime archive is missing: {archive_path}")
    if archive_path.stat().st_size != int(archive_record["size_bytes"]):
        raise RuntimeError("Bundled Agilent runtime archive size does not match manifest")
    if file_sha256(archive_path) != archive_sha256:
        raise RuntimeError("Bundled Agilent runtime archive SHA-256 does not match manifest")

    cache_root = _LOCAL_RUNTIME_CACHE.resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    runtime_root = cache_root / f"agilent_openlab_processing_2_5_{archive_sha256[:12]}"
    if runtime_root.exists():
        _validate_extracted_runtime(runtime_root, manifest)
    else:
        staging = Path(tempfile.mkdtemp(prefix=".agilent-openlab-extract-", dir=cache_root)).resolve()
        try:
            _extract_bundled_runtime(archive_path, staging, manifest)
            try:
                os.replace(staging, runtime_root)
            except FileExistsError:
                _validate_extracted_runtime(runtime_root, manifest)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    _validate_extracted_runtime(runtime_root, manifest)
    (runtime_root / ".bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    entrypoints = dict(manifest["entrypoints"])
    runtime_bin = runtime_root / "Bin"
    bridge_exe = runtime_root / Path(str(entrypoints["bridge"]))
    processing_method = runtime_root / Path(str(entrypoints["default_processing_method"]))
    return BundledOpenLabVendorAssets(
        runtime_root=runtime_root,
        runtime_bin=runtime_bin,
        bridge_exe=bridge_exe,
        processing_method=processing_method,
        archive_path=archive_path,
        archive_sha256=archive_sha256,
        manifest=manifest,
    )


def _read_bundled_runtime_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Bundled Agilent runtime manifest is unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        raise RuntimeError("Bundled Agilent runtime manifest has an unsupported schema")
    payload = manifest.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise RuntimeError("Bundled Agilent runtime manifest has no payload file list")
    return manifest


def _runtime_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    casefolded: set[str] = set()
    for raw in manifest["payload"]["files"]:
        if not isinstance(raw, dict):
            raise RuntimeError("Bundled Agilent runtime manifest contains an invalid file record")
        rendered = str(raw.get("path") or "")
        relative = PurePosixPath(rendered)
        if (
            "\\" in rendered
            or ":" in rendered
            or relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
        ):
            raise RuntimeError(f"Unsafe path in bundled Agilent runtime manifest: {relative}")
        normalized = relative.as_posix()
        folded = normalized.casefold()
        if folded in casefolded:
            raise RuntimeError(f"Case-insensitive duplicate in bundled Agilent manifest: {normalized}")
        casefolded.add(folded)
        records[normalized] = raw
    if len(records) != int(manifest["payload"]["file_count"]):
        raise RuntimeError("Bundled Agilent runtime manifest file count is inconsistent")
    return records


def _extract_bundled_runtime(
    archive_path: Path,
    target_root: Path,
    manifest: dict[str, Any],
) -> None:
    records = _runtime_records(manifest)
    seen: set[str] = set()
    with zipfile.ZipFile(archive_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = PurePosixPath(member.filename)
            if (
                "\\" in member.filename
                or ":" in member.filename
                or relative.is_absolute()
                or ".." in relative.parts
                or not relative.parts
            ):
                raise RuntimeError(f"Unsafe path in bundled Agilent archive: {member.filename}")
            normalized = relative.as_posix()
            folded = normalized.casefold()
            if folded in seen:
                raise RuntimeError(f"Duplicate path in bundled Agilent archive: {normalized}")
            seen.add(folded)
            record = records.get(normalized)
            if record is None:
                raise RuntimeError(f"Unmanifested file in bundled Agilent archive: {normalized}")
            unix_type = (member.external_attr >> 16) & 0o170000
            if unix_type not in (0, 0o100000):
                raise RuntimeError(f"Non-regular file in bundled Agilent archive: {normalized}")
            if member.file_size != int(record["size_bytes"]):
                raise RuntimeError(f"Bundled Agilent member size mismatch: {normalized}")
            destination = (target_root / Path(*relative.parts)).resolve()
            try:
                destination.relative_to(target_root)
            except ValueError as exc:
                raise RuntimeError(f"Bundled Agilent member escapes extraction root: {normalized}") from exc
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(member, "r") as source, destination.open("xb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != str(record["sha256"]):
                raise RuntimeError(f"Bundled Agilent member SHA-256 mismatch: {normalized}")
    expected = {path.casefold() for path in records}
    if seen != expected:
        raise RuntimeError("Bundled Agilent archive did not contain the complete manifest payload")


def _validate_extracted_runtime(runtime_root: Path, manifest: dict[str, Any]) -> None:
    runtime_root = runtime_root.resolve()
    records = _runtime_records(manifest)
    actual: set[str] = set()
    for path in runtime_root.rglob("*"):
        _assert_not_reparse_point(path)
        if not path.is_file() or path.name == ".bundle_manifest.json":
            continue
        relative = path.relative_to(runtime_root).as_posix()
        record = records.get(relative)
        if record is None:
            raise RuntimeError(f"Unexpected file in extracted Agilent runtime: {relative}")
        if path.stat().st_size != int(record["size_bytes"]):
            raise RuntimeError(f"Extracted Agilent runtime size mismatch: {relative}")
        if file_sha256(path) != str(record["sha256"]):
            raise RuntimeError(f"Extracted Agilent runtime SHA-256 mismatch: {relative}")
        actual.add(relative.casefold())
    if actual != {path.casefold() for path in records}:
        raise RuntimeError("Extracted Agilent runtime is incomplete")


def _runtime_bundle_provenance(runtime_bin: Path) -> dict[str, Any] | None:
    manifest_path = runtime_bin.parent / ".bundle_manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = _read_bundled_runtime_manifest(manifest_path)
    return {
        "runtime_id": manifest["runtime_id"],
        "archive_sha256": manifest["archive"]["sha256"],
        "payload_file_count": manifest["payload"]["file_count"],
        "payload_size_bytes": manifest["payload"]["size_bytes"],
        "project_bundled": True,
    }


@dataclass(frozen=True)
class OpenLabVendorReprocessResult:
    effective_input_root: Path
    manifest: dict[str, Any]
    log_text: str
    injection_provenance: dict[str, dict[str, Any]]


def reprocess_openlab_with_vendor_method(
    *,
    source_root: Path,
    staged_input_root: Path,
    dataset: dict[str, Any],
    runtime_bin: Path,
    bridge_exe: Path,
    processing_method: Path,
    timeout_seconds: int,
) -> OpenLabVendorReprocessResult:
    """Reprocess selected injections with Agilent's local Processing Server.

    All result sets are copied before any vendor component is invoked.  The
    original result-set tree is hashed before and after the run and is never
    passed to the bridge as a writable work area.
    """
    source_root = source_root.resolve()
    staged_input_root = staged_input_root.resolve()
    runtime_bin = runtime_bin.resolve()
    bridge_exe = bridge_exe.resolve()
    processing_method = processing_method.resolve()
    _validate_vendor_inputs(
        source_root=source_root,
        staged_input_root=staged_input_root,
        runtime_bin=runtime_bin,
        bridge_exe=bridge_exe,
        processing_method=processing_method,
        timeout_seconds=timeout_seconds,
    )

    selected = list(dataset.get("injections") or [])
    if not selected:
        raise ValueError("Vendor reprocessing requires at least one selected injection")
    groups = _group_selected_injections(source_root, selected)
    source_snapshot = _snapshot_result_sets(source_root, groups)
    effective_input_root = (
        staged_input_root / source_root.parent.name / source_root.name
        if source_root.suffix.casefold() == ".rslt"
        else staged_input_root
    )

    started_at = datetime.now().astimezone()
    method_sha256 = file_sha256(processing_method)
    bridge_sha256 = file_sha256(bridge_exe)
    runtime_files = {
        name: {
            "sha256": file_sha256(runtime_bin / name),
            "size_bytes": (runtime_bin / name).stat().st_size,
        }
        for name in _REQUIRED_RUNTIME_FILES
    }
    result_set_reports: list[dict[str, Any]] = []
    injection_provenance: dict[str, dict[str, Any]] = {}
    log_parts: list[str] = []

    try:
        for relative_result_set, members in groups.items():
            source_result_set = (source_root / relative_result_set).resolve()
            staged_result_set = (effective_input_root / relative_result_set).resolve()
            _copy_result_set(source_result_set, staged_result_set)
            method_target = staged_result_set / processing_method.name
            shutil.copy2(processing_method, method_target)
            if file_sha256(method_target) != method_sha256:
                raise RuntimeError(f"Staged OpenLab method hash mismatch: {relative_result_set}")

            acaml_path = _select_result_acaml(staged_result_set, members)
            jobs_path = staged_result_set / ".openlab_vendor_jobs.tsv"
            report_path = staged_result_set / ".openlab_vendor_report.json"
            derived_paths: list[Path] = []
            job_lines: list[str] = []
            before_rx_hashes: dict[str, str | None] = {}
            try:
                for position, injection in enumerate(members, start=1):
                    raw_file = _safe_leaf(str(injection.get("raw_file") or ""), "raw file")
                    injection_guid = str(injection.get("injection_guid") or "").strip()
                    if not injection_guid:
                        raise ValueError(f"Missing InjectionId for {injection.get('source_relative')}")
                    derived_name = f".openlab_vendor_{position:03d}_{injection_guid[:8]}.acaml"
                    derived_path = staged_result_set / derived_name
                    details = _write_single_injection_acaml(
                        source=acaml_path,
                        target=derived_path,
                        raw_file=raw_file,
                        injection_guid=injection_guid,
                        method_name=processing_method.stem,
                    )
                    derived_paths.append(derived_path)
                    rx_path = staged_result_set / Path(raw_file).with_suffix(".rx").name
                    before_rx_hashes[raw_file] = file_sha256(rx_path) if rx_path.is_file() else None
                    job_lines.append(f"{derived_name}\t{injection_guid}\t{raw_file}")
                    source_relative = str(injection.get("source_relative") or "")
                    injection_provenance[source_relative] = {
                        "vendor_result_origin": VENDOR_RESULT_ORIGIN,
                        "vendor_reprocess_status": "planned",
                        "injection_guid": injection_guid,
                        "raw_file": raw_file,
                        "batch_folder": str(injection.get("batch_folder") or ""),
                        "result_set_folder": str(injection.get("result_set_folder") or ""),
                        "processing_method": processing_method.stem,
                        "processing_method_name": processing_method.name,
                        "processing_method_sha256": method_sha256,
                        "original_rx_sha256": before_rx_hashes[raw_file],
                        "single_acaml_structure": details,
                    }

                jobs_path.write_text("\n".join(job_lines) + "\n", encoding="utf-8")
                completed = _run_bridge(
                    runtime_bin=runtime_bin,
                    bridge_exe=bridge_exe,
                    work_area=staged_result_set,
                    method_name=method_target.name,
                    jobs_name=jobs_path.name,
                    report_path=report_path,
                    timeout_seconds=timeout_seconds,
                )
                log_parts.append(
                    _redact_stage_paths(
                        f"[{relative_result_set.as_posix()}]\n"
                        f"stdout:\n{completed.stdout}\n"
                        f"stderr:\n{completed.stderr}\n",
                        staged_input_root,
                    )
                )
                report = _read_bridge_report(report_path)
                report["result_set_relative"] = relative_result_set.as_posix()
                result_set_reports.append(report)

                report_jobs = list(report.get("jobs") or [])
                report_by_raw = {
                    str(item.get("raw_file") or item.get("raw_dx_relative") or ""): item
                    for item in report_jobs
                }
                for injection in members:
                    raw_file = str(injection["raw_file"])
                    source_relative = str(injection["source_relative"])
                    bridge_job = report_by_raw.get(raw_file)
                    if bridge_job is None:
                        raise RuntimeError(f"Bridge report omitted injection: {source_relative}")
                    job_success = bridge_job.get("success")
                    if job_success is None:
                        job_success = str(bridge_job.get("status") or "").casefold() == "succeeded"
                    if not bool(job_success):
                        raise RuntimeError(f"Agilent vendor processing failed: {source_relative}")
                    rx_path = staged_result_set / Path(raw_file).with_suffix(".rx").name
                    if not rx_path.is_file() or rx_path.stat().st_size == 0:
                        raise RuntimeError(f"Agilent vendor processing did not create .rx: {source_relative}")
                    provenance = injection_provenance[source_relative]
                    provenance.update(
                        {
                            "vendor_reprocess_status": "success",
                            "reprocessed_rx_sha256": file_sha256(rx_path),
                            "bridge_warning_messages": list(bridge_job.get("warnings") or []),
                            "bridge_load_error_messages": list(bridge_job.get("load_errors") or []),
                            "bridge_failure_messages": list(bridge_job.get("failures") or []),
                        }
                    )
            finally:
                for temporary in [*derived_paths, jobs_path, report_path]:
                    if temporary.is_file() and temporary.parent == staged_result_set:
                        temporary.unlink()

        source_after = _snapshot_result_sets(source_root, groups)
        if source_after != source_snapshot:
            raise RuntimeError("Original OpenLab input changed during vendor reprocessing")
    except Exception:
        source_after = _snapshot_result_sets(source_root, groups)
        if source_after != source_snapshot:
            raise RuntimeError("Original OpenLab input changed during failed vendor reprocessing")
        raise

    finished_at = datetime.now().astimezone()
    manifest = {
        "schema_version": "1.0",
        "engine": "Agilent OpenLab Data Analysis Processing Server",
        "operation": "ModifyAndReprocessSingleRun",
        "vendor_code_executed": True,
        "runtime_bundle": _runtime_bundle_provenance(runtime_bin),
        "staged_copy_only": True,
        "source_input_unchanged": True,
        "requested_result_set_count": len(groups),
        "completed_result_set_count": len(result_set_reports),
        "requested_injection_count": len(selected),
        "completed_injection_count": sum(
            1 for item in injection_provenance.values() if item["vendor_reprocess_status"] == "success"
        ),
        "processing_method": {
            "name": processing_method.name,
            "sha256": method_sha256,
            "size_bytes": processing_method.stat().st_size,
        },
        "bridge": {"name": bridge_exe.name, "sha256": bridge_sha256},
        "runtime_files": runtime_files,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "result_sets": result_set_reports,
    }
    return OpenLabVendorReprocessResult(
        effective_input_root=effective_input_root,
        manifest=manifest,
        log_text="\n".join(log_parts),
        injection_provenance=injection_provenance,
    )


def apply_vendor_reprocess_provenance(
    dataset: dict[str, Any],
    result: OpenLabVendorReprocessResult,
    *,
    source_root_name: str,
) -> dict[str, Any]:
    dataset["source_root_name"] = source_root_name
    dataset["library_provenance"]["vendor_reprocessing"] = result.manifest
    dataset["scientific_boundary"]["peak_source"] = (
        "Agilent OpenLab Processing Server reprocessed .rx using the selected complete PMX method"
    )
    missing: list[str] = []
    for injection in dataset.get("injections") or []:
        source_relative = str(injection.get("source_relative") or "")
        provenance = result.injection_provenance.get(source_relative)
        if provenance is None:
            missing.append(source_relative)
            continue
        injection.update(provenance)
    if missing:
        raise RuntimeError(f"Vendor provenance could not be joined to {len(missing)} injection(s)")
    return dataset


def compare_vendor_peak_datasets(
    reference: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Compare two parsed RX peak sets after chronological ordinal normalization."""

    reference_rows = _vendor_comparison_rows(reference)
    candidate_rows = _vendor_comparison_rows(candidate)
    reference_keys = set(reference_rows)
    candidate_keys = set(candidate_rows)
    common_keys = sorted(reference_keys & candidate_keys)
    missing = sorted(reference_keys - candidate_keys)
    extra = sorted(candidate_keys - reference_keys)
    field_mismatches: list[dict[str, Any]] = []
    maximum_absolute_difference: dict[str, float] = {
        field: 0.0 for field in _VENDOR_EQUIVALENCE_NUMERIC_FIELDS
    }

    for key in common_keys:
        expected = reference_rows[key]
        actual = candidate_rows[key]
        for field in _VENDOR_EQUIVALENCE_NUMERIC_FIELDS:
            expected_value = expected.get(field)
            actual_value = actual.get(field)
            if expected_value is None or actual_value is None:
                equal = expected_value is None and actual_value is None
                difference = None
            else:
                difference = abs(float(expected_value) - float(actual_value))
                maximum_absolute_difference[field] = max(
                    maximum_absolute_difference[field], difference
                )
                equal = expected_value == actual_value
            if not equal and len(field_mismatches) < 100:
                field_mismatches.append(
                    {
                        "peak_key": list(key),
                        "field": field,
                        "reference": expected_value,
                        "candidate": actual_value,
                        "absolute_difference": difference,
                    }
                )
        for field in _VENDOR_EQUIVALENCE_VALUE_FIELDS:
            if expected.get(field) != actual.get(field) and len(field_mismatches) < 100:
                field_mismatches.append(
                    {
                        "peak_key": list(key),
                        "field": field,
                        "reference": expected.get(field),
                        "candidate": actual.get(field),
                        "absolute_difference": None,
                    }
                )

    exact = not missing and not extra and not field_mismatches
    return {
        "reference_peak_count": len(reference_rows),
        "candidate_peak_count": len(candidate_rows),
        "common_peak_count": len(common_keys),
        "peak_identity_exact": not missing and not extra,
        "all_compared_fields_bit_exact": exact,
        "maximum_absolute_difference": maximum_absolute_difference,
        "missing_peak_keys": [list(key) for key in missing[:100]],
        "extra_peak_keys": [list(key) for key in extra[:100]],
        "field_mismatches": field_mismatches,
    }


def _vendor_comparison_rows(dataset: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    injection_sources = {
        str(item.get("injection_id") or ""): str(item.get("source_relative") or "")
        for item in dataset.get("injections") or []
    }
    rows: dict[tuple[str, str, int], dict[str, Any]] = {}
    for peak in dataset.get("peaks") or []:
        injection_id = str(peak.get("injection_id") or "")
        source_relative = injection_sources.get(injection_id, "")
        signal_name = str(peak.get("signal_name") or "")
        ordinal = int(peak.get("peak_ordinal") or 0)
        key = (source_relative, signal_name, ordinal)
        if not source_relative or ordinal <= 0:
            raise ValueError(f"Vendor peak is missing comparison identity: {key}")
        if key in rows:
            raise ValueError(f"Duplicate vendor peak comparison identity: {key}")
        rows[key] = peak
    return rows


def _validate_vendor_inputs(
    *,
    source_root: Path,
    staged_input_root: Path,
    runtime_bin: Path,
    bridge_exe: Path,
    processing_method: Path,
    timeout_seconds: int,
) -> None:
    if not source_root.is_dir():
        raise NotADirectoryError(f"OpenLab source root does not exist: {source_root}")
    if staged_input_root.exists():
        raise FileExistsError(f"Vendor staging root already exists: {staged_input_root}")
    if (
        source_root == staged_input_root
        or source_root in staged_input_root.parents
        or staged_input_root in source_root.parents
    ):
        raise ValueError("Vendor staging root must be separate from the OpenLab source root")
    if not runtime_bin.is_dir():
        raise NotADirectoryError(f"Agilent runtime Bin does not exist: {runtime_bin}")
    for name in _REQUIRED_RUNTIME_FILES:
        if not (runtime_bin / name).is_file():
            raise FileNotFoundError(f"Agilent runtime is missing required file: {name}")
    if not bridge_exe.is_file():
        raise FileNotFoundError(f"OpenLab vendor bridge does not exist: {bridge_exe}")
    if bridge_exe.parent != runtime_bin:
        raise ValueError("OpenLab vendor bridge must be located in the selected runtime Bin")
    if not processing_method.is_file() or processing_method.suffix.casefold() != ".pmx":
        raise FileNotFoundError(f"Selected Agilent processing method is not a .pmx file: {processing_method}")
    if timeout_seconds <= 0:
        raise ValueError("Vendor processing timeout must be greater than zero")


def _group_selected_injections(
    source_root: Path,
    selected: list[dict[str, Any]],
) -> dict[Path, list[dict[str, Any]]]:
    groups: dict[Path, list[dict[str, Any]]] = {}
    for injection in selected:
        relative = Path(str(injection.get("source_relative") or ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.name:
            raise ValueError(f"Unsafe OpenLab source-relative path: {relative}")
        result_set_relative = relative.parent
        result_set = (source_root / result_set_relative).resolve()
        try:
            result_set.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(f"OpenLab result set escapes source root: {relative}") from exc
        groups.setdefault(result_set_relative, []).append(injection)
    for members in groups.values():
        members.sort(key=lambda item: (int(item.get("sequence_order") or 0), str(item["raw_file"])))
    return groups


def _snapshot_result_sets(source_root: Path, groups: dict[Path, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for relative in groups:
        directory = (source_root / relative).resolve()
        _assert_not_reparse_point(directory)
        for path in sorted(directory.rglob("*"), key=lambda item: str(item).casefold()):
            _assert_not_reparse_point(path)
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"Unsupported OpenLab result-set entry: {path}")
            key = path.relative_to(source_root).as_posix()
            snapshot[key] = {"size_bytes": path.stat().st_size, "sha256": file_sha256(path)}
    return snapshot


def _copy_result_set(source: Path, target: Path) -> None:
    _assert_not_reparse_point(source)
    if target.exists():
        raise FileExistsError(f"Staged OpenLab result set already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, copy_function=shutil.copy2, symlinks=False)
    for path in target.rglob("*"):
        _assert_not_reparse_point(path)
    for source_file in source.rglob("*"):
        if not source_file.is_file():
            continue
        target_file = target / source_file.relative_to(source)
        if os.path.samestat(source_file.stat(), target_file.stat()):
            raise RuntimeError(f"Vendor staging created a hard link instead of a copy: {source_file}")


def _assert_not_reparse_point(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Refusing OpenLab reparse point or symlink: {path}")
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if attributes & reparse_flag:
        raise ValueError(f"Refusing OpenLab reparse point or symlink: {path}")


def _select_result_acaml(result_set: Path, members: list[dict[str, Any]]) -> Path:
    names = [str(item.get("result_name") or "").strip() for item in members]
    for name in names:
        candidate = result_set / f"{name}.acaml"
        if name and candidate.is_file():
            return candidate
    candidates = sorted(
        (path for path in result_set.glob("*.acaml") if not path.name.startswith(".openlab_vendor_")),
        key=lambda path: path.name.casefold(),
    )
    if len(candidates) != 1:
        raise ValueError(f"Expected one source ACAML in {result_set}, found {len(candidates)}")
    return candidates[0]


def _write_single_injection_acaml(
    *,
    source: Path,
    target: Path,
    raw_file: str,
    injection_guid: str,
    method_name: str,
) -> dict[str, Any]:
    tree = ET.parse(source)
    root = tree.getroot()
    metadata_parent = _first_local(root, "ArrayOfInjectionMetaData")
    metadata = [item for item in list(metadata_parent) if _local_name(item.tag) == "InjectionMetaData"]
    chosen = [item for item in metadata if str(item.get("RawDataFileName") or "") == raw_file]
    if len(chosen) != 1:
        raise ValueError(f"Expected one InjectionMetaData row for {raw_file}, found {len(chosen)}")
    selected_metadata = chosen[0]
    actual_guid = str(selected_metadata.get("InjectionId") or "")
    if actual_guid.casefold() != injection_guid.casefold():
        raise ValueError(f"InjectionId mismatch for {raw_file}: {actual_guid} != {injection_guid}")
    setup_id = str(selected_metadata.get("SampleSetupId") or "")
    if not setup_id:
        raise ValueError(f"SampleSetupId is missing for {raw_file}")
    selected_metadata.set("DaMethodName", method_name)
    for item in metadata:
        if item is not selected_metadata:
            metadata_parent.remove(item)

    content = _first_local(root, "Content")
    sections = {_local_name(item.tag): item for item in list(content)}
    samples = sections.get("Samples")
    contexts = sections.get("SampleContexts")
    injections = sections.get("Injections")
    if samples is None or contexts is None or injections is None:
        raise ValueError(f"ACAML is missing sample/injection sections: {source.name}")

    selected_sample_meas_id = ""
    for item in list(samples):
        local = _local_name(item.tag)
        keep = True
        if local == "Setup":
            keep = str(item.get("id") or "").casefold() == setup_id.casefold()
        elif local == "MeasData":
            reference = next(
                (
                    str(child.get("id") or "")
                    for child in list(item)
                    if _local_name(child.tag) == "InjectionMeasData_ID"
                ),
                "",
            )
            keep = reference.casefold() == injection_guid.casefold()
            if keep:
                selected_sample_meas_id = str(item.get("id") or "")
        if not keep:
            samples.remove(item)
    if not selected_sample_meas_id:
        raise ValueError(f"Sample MeasData is missing for {raw_file}")

    for context in list(contexts):
        local = _local_name(context.tag)
        if local == "Setup":
            for reference in list(context):
                if (
                    _local_name(reference.tag) == "SampleSetup_ID"
                    and str(reference.get("id") or "").casefold() != setup_id.casefold()
                ):
                    context.remove(reference)
        elif local == "MeasData":
            for reference in list(context):
                if (
                    _local_name(reference.tag) == "SampleMeasData_ID"
                    and str(reference.get("id") or "").casefold() != selected_sample_meas_id.casefold()
                ):
                    context.remove(reference)

    for item in list(injections):
        if (
            _local_name(item.tag) == "MeasData"
            and str(item.get("id") or "").casefold() != injection_guid.casefold()
        ):
            injections.remove(item)

    target.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return {
        "injection_metadata_count": 1,
        "sample_setup_id": setup_id,
        "sample_meas_data_id": selected_sample_meas_id,
        "injection_meas_data_count": sum(
            1 for item in list(injections) if _local_name(item.tag) == "MeasData"
        ),
    }


def _run_bridge(
    *,
    runtime_bin: Path,
    bridge_exe: Path,
    work_area: Path,
    method_name: str,
    jobs_name: str,
    report_path: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(bridge_exe),
        str(work_area),
        method_name,
        jobs_name,
        report_path.name,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            cwd=runtime_bin,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Agilent vendor processing timed out for {work_area.name}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        report_detail = ""
        if report_path.is_file():
            try:
                report_detail = report_path.read_text(encoding="utf-8-sig").strip()
            except OSError:
                report_detail = ""
        detail = "\n".join(part for part in (message, report_detail) if part)
        raise RuntimeError(
            f"Agilent vendor bridge failed for {work_area.name} with exit code "
            f"{completed.returncode}: {detail[-4000:]}"
        )
    return completed


def _read_bridge_report(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Agilent vendor bridge did not create its JSON report")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Agilent vendor bridge report is unreadable") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise RuntimeError("Agilent vendor bridge report has an invalid schema")
    return payload


def _redact_stage_paths(text: str, staged_input_root: Path) -> str:
    rendered = str(staged_input_root)
    return text.replace(rendered, "<vendor-staged-input>").replace(rendered.replace("\\", "/"), "<vendor-staged-input>")


def _safe_leaf(value: str, label: str) -> str:
    candidate = Path(value)
    if not value or candidate.name != value or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Unsafe {label}: {value}")
    return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_local(root: ET.Element, name: str) -> ET.Element:
    item = next((element for element in root.iter() if _local_name(element.tag) == name), None)
    if item is None:
        raise ValueError(f"ACAML is missing {name}")
    return item
