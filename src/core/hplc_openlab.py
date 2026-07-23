from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

from src.core.project import (
    ensure_output_path_separate_from_inputs,
    ensure_output_path_within_root,
    ensure_write_path_allowed,
)


MIN_RAINBOW_VERSION = (1, 3, 1)
OPENLAB_DATA_TYPE = "HPLC/LC OpenLab raw data"
PROCESSOR_NAME = "hplc_openlab_raw_exporter"
IDENTITY_BOUNDARY = "unassigned_manual_mapping_required"
_DATE_PREFIX = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})")
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


def run_hplc_openlab_export(project_root: Path, options: HplcOpenLabExportOptions) -> dict[str, Any]:
    """Decode Agilent OpenLab result sets and build a data-only Excel workbook."""
    input_root = options.input_root.resolve()
    if not input_root.is_dir():
        raise NotADirectoryError(f"OpenLab input root does not exist or is not a directory: {input_root}")

    output_root = options.output_root.resolve()
    ensure_write_path_allowed(project_root, output_root, output_root=output_root)
    ensure_output_path_separate_from_inputs(project_root, output_root, [input_root])
    output_root.mkdir(parents=True, exist_ok=True)

    builder_workdir = ensure_output_path_within_root(
        project_root,
        options.builder_workdir,
        output_root,
    )
    builder_workdir.mkdir(parents=True, exist_ok=True)
    _validate_artifact_workdir(builder_workdir)

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
    for directory in (processed_dir, metadata_dir, reports_dir, previews_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    dataset = extract_hplc_openlab_dataset(input_root, options.since)
    dataset["workbook_plan"] = _build_workbook_plan(dataset, workbook_path)
    workbook_paths = _planned_workbook_paths(output_root, workbook_path, dataset["workbook_plan"])
    existing_workbooks = [path for path in workbook_paths if path.exists()]
    if existing_workbooks and not options.force:
        rendered = ", ".join(str(path) for path in existing_workbooks[:5])
        raise FileExistsError(
            "One or more planned workbooks already exist; rerun with --force to overwrite: "
            f"{rendered}"
        )
    dataset_path = processed_dir / f"{slug}_dataset.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    verification_path = reports_dir / f"{slug}_workbook_verification.json"
    builder_log_path = logs_dir / f"{slug}_workbook_builder.log"
    _run_workbook_builder(
        project_root=project_root,
        node_exe=options.node_exe,
        builder_workdir=builder_workdir,
        dataset_path=dataset_path,
        workbook_path=workbook_path,
        previews_dir=previews_dir,
        verification_path=verification_path,
        log_path=builder_log_path,
    )
    missing_workbooks = [
        path for path in workbook_paths if not path.is_file() or path.stat().st_size <= 0
    ]
    if missing_workbooks:
        raise RuntimeError(
            "Workbook builder did not create all planned non-empty .xlsx files: "
            + ", ".join(str(path) for path in missing_workbooks[:5])
        )

    metadata_payload = _metadata_payload(
        dataset,
        workbook_paths,
        output_root,
        dataset_path,
        verification_path,
    )
    metadata_path = metadata_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = reports_dir / f"{slug}_processing_summary.md"
    report_path.write_text(
        _summary_markdown(dataset, workbook_paths, output_root),
        encoding="utf-8",
    )

    return {
        "workbook": workbook_path,
        "workbooks": workbook_paths,
        "dataset": dataset_path,
        "metadata": metadata_path,
        "report": report_path,
        "verification": verification_path,
        "preview_dir": previews_dir,
        "summary": dataset["summary"],
    }


def extract_hplc_openlab_dataset(input_root: Path, since: date) -> dict[str, Any]:
    """Return workbook-ready raw signals, vendor peak results, and provenance."""
    rainbow, rainbow_version = _load_rainbow()
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
            metadata_probe = rainbow.read_metadata(str(dx_path))
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
            decoded = rainbow.read(str(dx_path))
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
    result_set_keys = sorted(
        {item["_result_set_key"] for item in selected},
        key=lambda key: min(item["_acquisition_sort"] for item in selected if item["_result_set_key"] == key),
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
        members = [item for item in selected if item["_result_set_key"] == result_set_key]
        members.sort(key=lambda item: item["_acquisition_sort"])
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
            "raw_decoder": "rainbow-api",
            "raw_decoder_version": rainbow_version,
            "raw_decoder_repository": "https://github.com/evanyeyeye/rainbow",
            "raw_decoder_license": "LGPL-3.0",
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

    rx_result = _parse_rx_result(dx_path.with_suffix(".rx"), context)
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
        "source_relative": _relative_text(dx_path, input_root),
        "source_size_bytes": dx_path.stat().st_size,
        "source_sha256": _sha256(dx_path),
        "acquisition_method": acquisition_method,
        "processing_method": context["processing_method"],
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
            "instrument_modules": "",
            "injections_by_raw_file": {},
            "sample_setups": {},
            "signals": {},
        }
    root = ET.parse(acaml_files[0]).getroot()

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
    ordinal = 0
    for signal_result in _direct_local(result, "SignalResult"):
        signal_ref = _first_descendant(signal_result, "Signal_ID")
        signal_id = signal_ref.get("id") if signal_ref is not None else ""
        signal_info = context["signals"].get(signal_id, {})
        signal_type = str(signal_info.get("type") or "")
        signal_peaks = list(_direct_local(signal_result, "Peak"))
        if signal_type and signal_type.casefold() != "chromatogram":
            continue
        for peak in signal_peaks:
            ordinal += 1
            peaks.append(_peak_record(peak, signal_info, ordinal))

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


def _load_rainbow() -> tuple[Any, str]:
    try:
        import rainbow
    except ImportError as exc:
        raise RuntimeError(
            "Agilent OpenLab .dx decoding requires rainbow-api>=1.3.1; install the optional dependency first"
        ) from exc
    version = importlib_metadata.version("rainbow-api")
    if _version_tuple(version) < MIN_RAINBOW_VERSION:
        raise RuntimeError(
            f"rainbow-api>={'.'.join(map(str, MIN_RAINBOW_VERSION))} is required for OpenLab .dx; found {version}"
        )
    return rainbow, version


def _build_workbook_plan(
    dataset: dict[str, Any],
    summary_workbook_path: Path,
) -> dict[str, Any]:
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
    planned = [summary_workbook_path.resolve()]
    for item in workbook_plan.get("batch_workbooks", []):
        relative_path = Path(str(item.get("relative_path") or ""))
        if not str(relative_path) or relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Invalid planned batch workbook path: {relative_path}")
        planned.append((output_root / relative_path).resolve())
    return planned


def _run_workbook_builder(
    *,
    project_root: Path,
    node_exe: Path,
    builder_workdir: Path,
    dataset_path: Path,
    workbook_path: Path,
    previews_dir: Path,
    verification_path: Path,
    log_path: Path,
) -> None:
    resolved_node = node_exe.resolve()
    if not resolved_node.is_file():
        raise FileNotFoundError(f"Node.js executable does not exist: {resolved_node}")
    builder_source = project_root / "scripts" / "data_types" / "hplc_lc" / "build_openlab_workbook.mjs"
    if not builder_source.is_file():
        raise FileNotFoundError(f"OpenLab workbook builder is missing: {builder_source}")
    builder_copy = builder_workdir / builder_source.name
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
    log_path.write_text(
        "\n".join(
            [
                f"exit_code={completed.returncode}",
                "[stdout]",
                completed.stdout,
                "[stderr]",
                completed.stderr,
            ]
        ),
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Excel workbook builder failed; see log: "
            f"{log_path}. Last error: {(completed.stderr or completed.stdout)[-1200:]}"
        )


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
    return {
        "dataset_id": f"hplc_openlab_{dataset['cutoff_date'].replace('-', '')}_plus",
        "data_type": dataset["data_type"],
        "processor_name": dataset["processor_name"],
        "processing_status": "processed_to_split_excel_no_plot",
        "source_root_name": dataset["source_root_name"],
        "cutoff_date": dataset["cutoff_date"],
        "processed_workbook": relative_workbooks[0],
        "processed_workbooks": relative_workbooks,
        "excel_output_layout": dataset["workbook_plan"],
        "processed_dataset": dataset_path.name,
        "verification_report": verification_path.name,
        "manual_check_required": True,
        "manual_check_items": [
            "峰表来自 OpenLab 原积分结果，峰身份仍需经标准品或用户提供的映射确认",
            "未提供标曲、响应因子和底物/产物角色映射，因此不计算转化率、选择性或产率",
            "请复核 OpenLab 处理警告、峰积分边界、检测波长和进样信息",
            "原始色谱信号已完整解码并保存在审计数据集中，但按用户要求不放入简化 Excel",
        ],
        "forbidden_claims": dataset["scientific_boundary"]["forbidden_outputs"],
        "key_results": dataset["summary"],
        "algorithm_provenance": dataset["library_provenance"],
    }


def _summary_markdown(
    dataset: dict[str, Any],
    workbook_paths: list[Path],
    output_root: Path,
) -> str:
    summary = dataset["summary"]
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
            f"- Vendor-integrated peaks: `{summary['peak_count']}`",
            f"- Raw signal points: `{summary['signal_point_count']}`",
            f"- Excel workbooks: `{len(relative_workbooks)}`",
            f"- Summary workbook: `{relative_workbooks[0]}`",
            *[f"- Batch workbook: `{path}`" for path in relative_workbooks[1:]],
            "- Raw signal points in Excel: `no` (retained in the processed audit dataset)",
            "- Plots created: `no`",
            "- Automatic chemical identity or conversion/selectivity/yield claims: `no`",
            "",
        ]
    )


def _date_from_filename(name: str) -> date | None:
    match = _DATE_PREFIX.match(name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group("date"))
    except ValueError:
        return None


def _parse_acquisition_datetime(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("OpenLab manifest does not contain an acquisition date")
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_text(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", value)[:3]]
    return tuple(parts + [0] * (3 - len(parts)))


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
