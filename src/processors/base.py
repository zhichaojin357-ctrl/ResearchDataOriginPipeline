from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from src.core.epr_jeol import decode_jeol_cacqu_rows, looks_like_jeol_cwesr_file
from src.core.metadata import write_metadata
from src.core.project import claim_policy_path, load_json_compatible_yaml, output_dir
from src.core.table_reader import coerce_numeric_rows, read_table
from src.origin.adapter import export_plot
from src.processors.calculations import build_processed_table, bet_numeric, condition_screening_numeric, epr_numeric, type_specific_results
from src.processors.profiles import SUPPORTED_PROCESSOR_PROFILES


MANUAL_CHECK_ITEMS = {
    "XRD": ["candidate peaks only; no phase or crystal-plane assignment"],
    "UV-vis DRS": ["Eg_candidate and linear interval require confirmation"],
    "EIS": ["no equivalent-circuit fitting or mechanism conclusion"],
    "XPS": ["peak positions/areas are candidates; no valence assignment"],
    "EPR": ["no radical species assignment"],
    "Mott-Schottky": ["flat-band candidate is not CB/VB"],
}


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "dataset"


def process_table_dataset(
    project_root: Path,
    classification: dict,
    source_file: Path,
    *,
    no_origin: bool = True,
    force: bool = True,
    triage: dict | None = None,
    output_root: Path | None = None,
) -> dict:
    data_type = classification["inferred_data_type"]
    processor_name = classification["selected_processor"]
    if (
        classification.get("supported_in_phase_1") is False
        or processor_name == "none"
        or data_type == "reference_literature"
    ):
        raise ValueError(f"{data_type} is scan-only and must not be processed as experimental data.")

    rows, input_warnings = _read_processor_rows(source_file, data_type)
    numeric = coerce_numeric_rows(rows)
    if not numeric and data_type == "reaction_condition_screening":
        numeric = condition_screening_numeric(rows)
    if data_type == "BET":
        numeric = bet_numeric(rows, numeric)
    if data_type == "EPR":
        numeric = epr_numeric(rows, numeric)

    source_slug = safe_name(source_file.stem)
    dataset_suffix = _queue_dataset_suffix(triage)
    output_slug = f"{source_slug}_{dataset_suffix}" if dataset_suffix else source_slug
    dataset_id = f"{safe_name(data_type)}_{output_slug}"
    profile = SUPPORTED_PROCESSOR_PROFILES.get(data_type)
    processed_dir = output_dir(project_root, "processed_data", safe_name(data_type), output_root=output_root)
    metadata_dir = output_dir(project_root, "metadata", safe_name(data_type), output_root=output_root)
    processed_csv = processed_dir / f"{output_slug}_processed.csv"
    if processed_csv.exists() and not force:
        raise FileExistsError(f"Output already exists; rerun with --force to overwrite: {processed_csv}")

    warnings = list(input_warnings)
    key_results = {}
    processed_headers: list[str] = []
    if data_type == "HPLC/LC exported data":
        key_results = type_specific_results(data_type, numeric, rows)

    if data_type == "HPLC/LC exported data" and key_results.get("lc_export_mode") == "ambiguous":
        headers, processed_rows = build_processed_table(data_type, numeric, rows)
        processed_headers = headers
        with processed_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(processed_rows)
        warnings.append("HPLC/LC exported table is ambiguous; manual review required before plot or quantification.")
        origin_result = None
        status = "manual_review"
    elif not numeric:
        warnings.append("No two-column numeric data could be read.")
        processed_csv.write_text("x,y\n", encoding="utf-8")
        origin_result = None
        status = "fail"
    else:
        numeric = sorted(numeric, key=lambda item: item[0], reverse=data_type in {"XPS", "FTIR"})
        headers, processed_rows = build_processed_table(data_type, numeric, rows)
        processed_headers = headers
        with processed_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(processed_rows)
        y_values = [value for _, value in numeric]
        key_results = {
            "point_count": len(numeric),
            "x_min": min(x for x, _ in numeric),
            "x_max": max(x for x, _ in numeric),
            "y_min": min(y_values),
            "y_max": max(y_values),
        }
        if data_type == "HPLC/LC exported data":
            key_results.update(type_specific_results(data_type, numeric, rows))
        else:
            key_results.update(type_specific_results(data_type, numeric, rows))
        if data_type == "UV-vis DRS":
            warnings.append("Eg candidate requires configured Tauc interval selection.")
        if data_type == "HPLC/LC exported data" and key_results.get("lc_quantification_blocked_reason"):
            warnings.append(str(key_results["lc_quantification_blocked_reason"]))
        x_title, y_title = _origin_axis_titles(headers, data_type)
        if no_origin:
            origin_result = None
            status = "processed_no_origin"
            warnings.append("Origin export skipped by --no-origin.")
        else:
            origin_result = export_plot(
                project_root,
                dataset_id,
                processed_csv,
                x_title,
                y_title,
                data_type=data_type,
                source_file=source_file,
                output_root=output_root,
            )
            status = "success" if origin_result.ok else "fail"
            if not origin_result.ok:
                warnings.append(origin_result.message)

    metadata_path = metadata_dir / output_slug / "metadata.json"
    manual_check_items = list(
        profile["manual_check_items"]
        if profile
        else MANUAL_CHECK_ITEMS.get(data_type, ("manual_check_required by Phase 1 policy",))
    )
    forbidden_claims = _forbidden_claims(project_root, data_type, profile)
    plot_type = _metadata_plot_type(data_type, key_results, profile)
    return write_metadata(
        project_root=project_root,
        path=metadata_path,
        dataset_id=dataset_id,
        data_type=data_type,
        source_file=source_file,
        processor_name=processor_name,
        processing_status=status,
        plot_type=plot_type,
        origin_file=origin_result.origin_file if origin_result else None,
        figure_tif=origin_result.figure_tif if origin_result else None,
        processed_data=processed_csv,
        preview_png=origin_result.preview_png if origin_result else None,
        manual_check_items=manual_check_items,
        forbidden_claims=forbidden_claims,
        warnings=warnings,
        key_results=key_results,
        triage=triage,
        parameters={"algorithm_provenance": _algorithm_provenance(data_type, processor_name, processed_headers, key_results)},
        output_root=output_root,
    )


def _read_processor_rows(source_file: Path, data_type: str) -> tuple[list[dict[str, str]], list[str]]:
    if data_type == "EPR" and looks_like_jeol_cwesr_file(source_file):
        return decode_jeol_cacqu_rows(source_file), [
            "Decoded JEOL JES-FA/JES-X3 cAcqu EPR raw file to field-intensity table; radical assignment remains blocked.",
        ]
    if data_type == "XPS" and source_file.suffix.casefold() in {".vgd", ".vgp"}:
        from src.adapters import xps_vgd_reader_adapter

        result = xps_vgd_reader_adapter.read_vgd_rows(source_file)
        if result.rows:
            return result.rows, [
                "Read Thermo VGD XPS spectrum through vgd-reader; peak assignment and valence interpretation remain blocked.",
                *result.warnings,
            ]
    return read_table(source_file), []


def _forbidden_claims(project_root: Path, data_type: str, profile: dict | None) -> list[str]:
    claims: list[str] = []
    if profile:
        claims.extend(str(item) for item in profile["forbidden_claims"])
    try:
        policy = load_json_compatible_yaml(claim_policy_path(project_root))
    except FileNotFoundError:
        policy = load_json_compatible_yaml(claim_policy_path(Path(__file__).resolve().parents[2]))
    claims.extend(str(item) for item in policy.get("forbidden_claims", []))
    type_policy = policy.get("type_specific", {}).get(data_type, {})
    claims.extend(str(item) for item in type_policy.get("forbidden", []))
    deduped = []
    seen = set()
    for claim in claims:
        if claim not in seen:
            seen.add(claim)
            deduped.append(claim)
    return deduped


def _origin_axis_titles(headers: list[str], data_type: str = "") -> tuple[str, str]:
    normalized = [header.strip().lower() for header in headers]
    if normalized[:2] == ["relative_pressure_p_p0", "adsorbed_volume"]:
        return "Relative Pressure (P/P0)", "Quantity Adsorbed (cm3/g STP)"
    if normalized[:2] == ["time_s", "photocurrent_ua"]:
        return "Time (s)", "Photocurrent (uA)"
    axis_by_type = {
        "Raman": ("Raman Shift (cm-1)", "Intensity (a.u.)"),
        "FTIR": ("Wavenumber (cm-1)", "Intensity (a.u.)"),
        "PL": ("Wavelength (nm)", "Intensity (a.u.)"),
        "EPR": ("Magnetic Field (G)", "Intensity (a.u.)"),
        "XRD": ("2theta (degree)", "Intensity (a.u.)"),
    }
    if data_type in axis_by_type and normalized[:2] in (["x", "intensity"], ["magnetic_field", "intensity"]):
        return axis_by_type[data_type]
    if len(headers) >= 2:
        return headers[0], headers[1]
    if len(headers) == 1:
        return headers[0], "signal"
    return "x", "y"


def _algorithm_provenance(data_type: str, processor_name: str, headers: list[str], key_results: dict) -> dict:
    candidate_methods = []
    if "peak_position_candidates" in key_results:
        candidate_methods.append("local_neighbor_peak_candidates")
    if "valley_position_candidates" in key_results:
        candidate_methods.append("local_neighbor_valley_candidates")
    if "integral_area_candidate" in key_results or "area_candidate" in key_results:
        candidate_methods.append("trapezoid_area_candidate")
    if "linear_region_candidates" in key_results:
        candidate_methods.append("linear_region_candidate")
    if "xps_component_area_candidates" in key_results:
        candidate_methods.append("xps_component_trapezoid_area_candidate")
    if data_type in {"photocurrent", "photocurrent_response"}:
        candidate_methods.append("current_cycle_candidate_metrics")
    if data_type == "BET":
        candidate_methods.append("bet_exported_summary_or_isotherm_candidate")
    if data_type == "EPR":
        if key_results.get("adapter_results", {}).get("EPR"):
            candidate_methods.append("epr_adapter_field_intensity_candidate_metrics")
        else:
            candidate_methods.append("field_intensity_extrema_candidate")
    if data_type == "XPS" and key_results.get("adapter_results", {}).get("XPS"):
        candidate_methods.append("xps_lmfitxps_existing_curve_summary")
    if data_type == "HPLC/LC exported data":
        candidate_methods.append("lc_exported_table_contract_classification")
        if key_results.get("lc_calibration_candidate"):
            candidate_methods.append("lc_calibration_linear_fit_candidate")
        if key_results.get("lc_candidate_peaks"):
            candidate_methods.append("lc_peak_table_candidate_rows")

    provenance = {
        "processor_name": processor_name,
        "calculation_module": "src.processors.calculations",
        "processed_headers": headers,
        "candidate_methods": candidate_methods,
        "adapter_layer": "src.adapters",
        "adapter_policy": "lazy optional adapters with fallback; candidate metrics only",
        "interpretation_policy": "candidate metrics only; scientific interpretation requires manual review",
    }
    adapters = []
    if "peak_position_candidates" in key_results:
        adapters.append("src.adapters.peak_detection_adapter")
    if key_results.get("pybaselines_baseline_correction_available"):
        adapters.append("src.adapters.baseline_adapter")
    if data_type == "EIS":
        adapters.append("src.adapters.eis_impedance_adapter")
    if data_type == "BET":
        adapters.append("src.adapters.bet_pygaps_adapter")
    if data_type == "EPR":
        adapters.append("src.adapters.epr_adapter")
    if data_type == "XPS":
        adapters.append("src.adapters.xps_lmfitxps_adapter")
        adapters.append("src.adapters.xps_vgd_reader_adapter")
    if adapters:
        provenance["candidate_adapters"] = adapters
    if key_results.get("adapter_results"):
        provenance["adapter_results"] = key_results["adapter_results"]
    if "linear_fit_point_count" in key_results:
        provenance["fit_point_count"] = key_results["linear_fit_point_count"]
        provenance["fit_method"] = "ordinary_least_squares_candidate"
    if key_results.get("linear_region_candidates"):
        provenance["fit_regions"] = key_results["linear_region_candidates"]
    return provenance


def _metadata_plot_type(data_type: str, key_results: dict, profile: dict | None) -> str:
    if data_type == "HPLC/LC exported data":
        intent = key_results.get("lc_plot_intent")
        if isinstance(intent, dict):
            if intent.get("candidate") is False:
                return "manual_review"
            plot_type = intent.get("plot_type")
            if plot_type:
                return str(plot_type)
    return str(profile["plot_type_hints"][0] if profile else "line")


def _queue_dataset_suffix(triage: dict | None) -> str:
    if not triage:
        return ""
    queue_id = str(triage.get("queue_id") or "").strip()
    if not queue_id:
        return ""
    digest = hashlib.sha256(queue_id.encode("utf-8")).hexdigest()[:12]
    return safe_name(f"q_{digest}")


def process_supported(project_root: Path, manifest: dict, *, no_origin: bool = True, force: bool = True, output_root: Path | None = None) -> list[dict]:
    results = []
    for classification in manifest["classifications"]:
        if not classification["supported_in_phase_1"]:
            continue
        for file_name in classification["files"]:
            results.append(
                process_table_dataset(
                    project_root,
                    classification,
                    Path(file_name),
                    no_origin=no_origin,
                    force=force,
                    output_root=output_root,
                )
            )
    return results
