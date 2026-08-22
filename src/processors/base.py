from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.epr_jeol import decode_jeol_cacqu_rows, looks_like_jeol_cwesr_file
from src.core.file_utils import (
    lexical_absolute_path,
    prepare_safe_output_file_targets,
)
from src.core.metadata import write_metadata
from src.core.plot_labels import XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE
from src.core.project import (
    claim_policy_path,
    ensure_output_path_separate_from_inputs,
    ensure_write_path_allowed,
    load_json_compatible_yaml,
)
from src.core.runtime_paths import resolve_output_root
from src.core.table_reader import coerce_numeric_rows, read_table
from src.origin.adapter import export_plot, plan_origin_plot_output_paths
from src.processors.calculations import build_processed_table, bet_numeric, condition_screening_numeric, epr_numeric, type_specific_results
from src.processors.eis import (
    eis_measured_plot_rows,
    read_eis_measurements,
)
from src.processors.profiles import SUPPORTED_PROCESSOR_PROFILES

if TYPE_CHECKING:
    from src.core.xrd_jade import XrdPhaseMatchOptions


MANUAL_CHECK_ITEMS = {
    "XRD": ["candidate peaks only; no phase or crystal-plane assignment"],
    "UV-vis DRS": ["Eg_candidate and linear interval require confirmation"],
    "EIS": ["equivalent-circuit selection and fitting are manual; the default processor reports measured data only"],
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
    force: bool = False,
    triage: dict | None = None,
    output_root: Path | None = None,
    xrd_phase_options: XrdPhaseMatchOptions | None = None,
) -> dict:
    data_type = classification["inferred_data_type"]
    processor_name = classification["selected_processor"]
    if xrd_phase_options is not None and data_type != "XRD":
        raise ValueError("xrd_phase_options can only be used with XRD data")
    if (
        classification.get("supported_in_pipeline") is False
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
    effective_output_root = output_root or resolve_output_root(project_root)
    if not effective_output_root.is_absolute():
        effective_output_root = project_root / effective_output_root
    effective_output_root = lexical_absolute_path(effective_output_root)
    ensure_write_path_allowed(
        project_root,
        effective_output_root,
        output_root=effective_output_root,
    )
    ensure_output_path_separate_from_inputs(
        project_root,
        effective_output_root,
        [source_file],
    )
    processed_dir = effective_output_root / "processed_data" / safe_name(data_type)
    metadata_dir = effective_output_root / "metadata" / safe_name(data_type)
    processed_csv = processed_dir / f"{output_slug}_processed.csv"
    metadata_path = metadata_dir / output_slug / "metadata.json"
    xrd_match_path = metadata_path.parent / "card_match_candidates.json" if xrd_phase_options is not None else None
    planned_outputs = [processed_csv, metadata_path]
    if xrd_match_path is not None:
        planned_outputs.append(xrd_match_path)
    if not no_origin:
        origin_paths = plan_origin_plot_output_paths(
            project_root,
            dataset_id,
            output_root=effective_output_root,
        )
        planned_outputs.extend(
            (
                origin_paths.plot_csv,
                origin_paths.job_script,
                origin_paths.origin_file,
                origin_paths.figure_tif,
                origin_paths.preview_png,
            )
        )
    prepare_safe_output_file_targets(
        planned_outputs,
        output_root=effective_output_root,
        force=force,
        context=f"{data_type} dataset",
    )
    processed_dir.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    warnings = list(input_warnings)
    key_results = {}
    xrd_phase_result: dict[str, object] | None = None
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
    elif data_type == "EIS":
        headers, processed_rows, eis_results = _build_eis_measured_product(source_file)
        processed_headers = headers
        with processed_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(processed_rows)
        key_results = dict(type_specific_results(data_type, numeric, rows))
        key_results.update(eis_results)
        warnings.extend(eis_results.get("eis_measurement", {}).get("warnings", []))
        warnings.append(
            "Equivalent-circuit fitting was not run: automatic circuit selection and fitting are blocked by claim policy."
        )
        warnings.append(
            "All parsed measured EIS points were retained in source order; no automatic semicircle-main-branch selection was applied."
        )
        x_title, y_title = _origin_axis_titles(
            headers,
            data_type,
            _source_headers(rows),
            epr_field_unit=key_results.get("magnetic_field_unit"),
        )
        if no_origin:
            origin_result = None
            status = "processed_no_origin"
            warnings.append("Origin export skipped by --no-origin.")
        else:
            try:
                origin_result = export_plot(
                    project_root,
                    dataset_id,
                    processed_csv,
                    x_title,
                    y_title,
                    data_type=data_type,
                    source_file=source_file,
                    output_root=effective_output_root,
                    force=force,
                )
            except Exception as exc:
                origin_result = None
                status = "fail"
                warnings.append(f"Origin export failed: {exc}")
            else:
                status = "success" if origin_result.ok else "fail"
                if not origin_result.ok:
                    warnings.append(origin_result.message)
    elif not numeric:
        warnings.append("No two-column numeric data could be read.")
        processed_csv.write_text("x,y\n", encoding="utf-8")
        origin_result = None
        status = "fail"
    else:
        numeric = sorted(numeric, key=lambda item: item[0], reverse=data_type in {"XPS", "FTIR"})
        xrd_peak_parameters = (
            (
                xrd_phase_options.peak_prominence_normalized,
                xrd_phase_options.minimum_peak_distance_deg,
            )
            if data_type == "XRD" and xrd_phase_options is not None
            else None
        )
        headers, processed_rows = build_processed_table(
            data_type,
            numeric,
            rows,
            xrd_peak_parameters=xrd_peak_parameters,
        )
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
        key_results.update(
            type_specific_results(
                data_type,
                numeric,
                rows,
                xrd_peak_parameters=xrd_peak_parameters,
            )
        )
        if data_type == "XRD" and xrd_phase_options is not None:
            from src.core.xrd_jade import match_xrd_phases

            assert xrd_match_path is not None
            xrd_phase_result = match_xrd_phases(numeric, xrd_phase_options)
            xrd_match_path.write_text(
                json.dumps(xrd_phase_result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            warnings.extend(str(item) for item in xrd_phase_result.get("warnings", []))
            matches = list(xrd_phase_result.get("matches", []))
            key_results["xrd_phase_matching"] = {
                "status": xrd_phase_result.get("status"),
                "candidate_count": xrd_phase_result.get("candidate_count"),
                "database": xrd_phase_result.get("database"),
                "peak_detection": xrd_phase_result.get("peak_detection"),
                "parameters": xrd_phase_result.get("parameters"),
                "top_candidates": [
                    {
                        key: item.get(key)
                        for key in (
                            "card_id",
                            "formula",
                            "database_name",
                            "matched_peak_count",
                            "match_score_candidate",
                            "confidence_candidate",
                        )
                    }
                    for item in matches[:5]
                    if isinstance(item, dict)
                ],
                "candidate_output": xrd_match_path,
                "manual_check_required": True,
            }
        if data_type == "UV-vis DRS":
            warnings.append("Eg candidate requires configured Tauc interval selection.")
        if (
            data_type in {"photocurrent", "photocurrent_response"}
            and key_results.get("photocurrent_input_current_unit") == "unknown"
        ):
            warnings.append(
                "Photocurrent current unit was not recognized from the column header; values were assumed A and converted to uA."
            )
        if data_type == "HPLC/LC exported data" and key_results.get("lc_quantification_blocked_reason"):
            warnings.append(str(key_results["lc_quantification_blocked_reason"]))
        x_title, y_title = _origin_axis_titles(
            headers,
            data_type,
            _source_headers(rows),
            epr_field_unit=key_results.get("magnetic_field_unit"),
        )
        if no_origin:
            origin_result = None
            status = "processed_no_origin"
            warnings.append("Origin export skipped by --no-origin.")
        else:
            try:
                origin_result = export_plot(
                    project_root,
                    dataset_id,
                    processed_csv,
                    x_title,
                    y_title,
                    data_type=data_type,
                    source_file=source_file,
                    output_root=effective_output_root,
                    force=force,
                )
            except Exception as exc:
                origin_result = None
                status = "fail"
                warnings.append(f"Origin export failed: {exc}")
            else:
                status = "success" if origin_result.ok else "fail"
                if not origin_result.ok:
                    warnings.append(origin_result.message)

    manual_check_items = list(
        profile["manual_check_items"]
        if profile
        else MANUAL_CHECK_ITEMS.get(data_type, ("manual_check_required by pipeline policy",))
    )
    if xrd_phase_result is not None:
        manual_check_items.extend(str(item) for item in xrd_phase_result.get("manual_check_items", []))
    if data_type == "EIS":
        manual_check_items.append(
            "Select any equivalent circuit, fitting interval, and excluded points manually; the default processor did not run a fit."
        )
    if (
        data_type in {"photocurrent", "photocurrent_response"}
        and key_results.get("photocurrent_input_current_unit") == "unknown"
    ):
        manual_check_items.append("Confirm the photocurrent input current unit; processing assumed A before conversion to uA.")
    forbidden_claims = _forbidden_claims(project_root, data_type, profile)
    if xrd_phase_result is not None:
        for claim in xrd_phase_result.get("forbidden_claims", []):
            rendered = str(claim)
            if rendered not in forbidden_claims:
                forbidden_claims.append(rendered)
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
        parameters={
            "algorithm_provenance": _algorithm_provenance(data_type, processor_name, processed_headers, key_results),
            **(
                {
                    "xrd_phase_matching": {
                        "database_stem": xrd_phase_options.database_stem,
                        "peak_prominence_normalized": xrd_phase_options.peak_prominence_normalized,
                        "minimum_peak_distance_deg": xrd_phase_options.minimum_peak_distance_deg,
                        "card_tolerance_deg": xrd_phase_options.card_tolerance_deg,
                        "minimum_card_relative_intensity": xrd_phase_options.minimum_card_relative_intensity,
                        "wavelength_angstrom": xrd_phase_options.wavelength_angstrom,
                    }
                }
                if xrd_phase_options is not None
                else {}
            ),
        },
        output_root=effective_output_root,
    )


def _build_eis_measured_product(source_file: Path) -> tuple[list[str], list[list[float | None]], dict[str, object]]:
    measurement = read_eis_measurements(source_file)
    headers = [
        "real_impedance_ohm",
        "neg_imag_impedance_ohm",
        "frequency_hz",
        "impedance_magnitude_ohm",
        "phase_deg",
    ]
    rows = eis_measured_plot_rows(measurement.points)
    measurement_metadata = measurement.to_metadata()
    fit_metadata = {
        "status": "not_run",
        "reason": "blocked_by_policy",
        "manual_check_required": True,
    }
    key_results = {
        "point_count": len(measurement.points),
        "nyquist_points": len(measurement.points),
        "bode_points": len([point for point in measurement.points if point.frequency_hz is not None]),
        "max_negative_imaginary_impedance": max(
            (point.minus_z_imag_ohm for point in measurement.points),
            default=None,
        ),
        "eis_measurement": measurement_metadata,
        "eis_fit": fit_metadata,
    }
    return headers, rows, key_results


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


def _origin_axis_titles(
    headers: list[str],
    data_type: str = "",
    source_headers: list[str] | None = None,
    *,
    epr_field_unit: object = None,
) -> tuple[str, str]:
    normalized = [header.strip().lower() for header in headers]
    if normalized[:2] == ["relative_pressure_p_p0", "adsorbed_volume"]:
        return "Relative Pressure (P/P0)", "Quantity Adsorbed (cm3/g STP)"
    if normalized[:2] == ["time_s", "photocurrent_ua"]:
        return "Time (s)", "Photocurrent (uA)"
    if data_type == "HPLC/LC exported data" and normalized[:2] == ["retention_time_min", "signal"]:
        return "Retention time (min)", "Detector response"
    if data_type == "reaction_condition_screening" and normalized[:2] == ["condition", "response_value"]:
        return "Condition", _reaction_response_axis_title(source_headers or [])
    epr_x_title = (
        f"Magnetic Field ({epr_field_unit})"
        if epr_field_unit in {"G", "mT"}
        else "Magnetic Field"
    )
    axis_by_type = {
        "Raman": ("Raman Shift (cm-1)", "Intensity (a.u.)"),
        "FTIR": ("Wavenumber (cm-1)", "Intensity (a.u.)"),
        "PL": ("Wavelength (nm)", "Intensity (a.u.)"),
        "EPR": (epr_x_title, "Intensity (a.u.)"),
        "XRD": (XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE),
    }
    if data_type in axis_by_type and normalized[:2] in (
        ["x", "intensity"],
        ["magnetic_field", "intensity"],
        ["two_theta_deg", "intensity"],
    ):
        return axis_by_type[data_type]
    if data_type == "EIS" and (
        {"real_impedance_ohm", "neg_imag_impedance_ohm"}.issubset(normalized)
        or {"real_impedance", "neg_imag_impedance"}.issubset(normalized)
    ):
        return "Z' (ohm)", "-Z'' (ohm)"
    if data_type == "EIS" and normalized[:4] == [
        "cleaned_z_real_ohm",
        "cleaned_minus_z_imag_ohm",
        "fit_z_real_ohm",
        "draft_fit_minus_z_imag_ohm",
    ]:
        return "Z' (ohm)", "-Z'' (ohm)"
    if len(headers) >= 2:
        return headers[0], headers[1]
    if len(headers) == 1:
        return headers[0], "signal"
    return "x", "y"


def _source_headers(rows: list[dict[str, str]]) -> list[str]:
    return list(rows[0]) if rows else []


def _reaction_response_axis_title(source_headers: list[str]) -> str:
    response_titles = {
        "yield": "Yield",
        "conversion": "Conversion",
        "selectivity": "Selectivity",
        "rate": "Rate",
        "response": "Response",
        "value": "Response",
    }
    for header in source_headers:
        words = set(re.findall(r"[a-z]+|%", header.casefold().replace("_", " ")))
        for token, title in response_titles.items():
            if token not in words:
                continue
            if "%" in words or "percent" in words:
                return f"{title} (%)"
            return title
    return "Response"


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
    if data_type == "EIS":
        candidate_methods.append("measured_nyquist_bode_coordinates_no_equivalent_circuit_fit")
    if data_type == "BET":
        candidate_methods.append("bet_exported_summary_or_isotherm_candidate")
        if key_results.get("adapter_results", {}).get("BET"):
            candidate_methods.append("pygaps_pointisotherm_candidate_no_bet_fit")
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
    if data_type == "EIS":
        provenance["equivalent_circuit_fit_policy"] = "not_run_blocked_by_policy"
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


def process_supported(project_root: Path, manifest: dict, *, no_origin: bool = True, force: bool = False, output_root: Path | None = None) -> list[dict]:
    results = []
    for classification in manifest["classifications"]:
        if not classification["supported_in_pipeline"]:
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
