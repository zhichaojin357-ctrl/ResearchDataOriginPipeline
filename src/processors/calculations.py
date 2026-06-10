from __future__ import annotations

import re
from math import isfinite
from math import sqrt


def type_specific_results(
    data_type: str,
    numeric: list[tuple[float, float]],
    rows: list[dict[str, str]],
) -> dict:
    y_values = [y for _, y in numeric]
    if data_type == "XRD":
        return {"peak_position_candidates": local_peak_positions(numeric)}
    if data_type == "UV-vis DRS":
        return uvvis_results(numeric, rows)
    if data_type == "EIS":
        return eis_results(numeric, rows)
    if data_type in {"PL", "FTIR", "Raman"}:
        result = {
            "peak_position_candidates": local_peak_positions(numeric),
            "peak_intensity_candidate": max(y_values) if y_values else None,
            "integral_area_candidate": trapezoid_area(numeric),
            **spectral_auxiliary_results(rows),
            **spectral_package_results(numeric),
        }
        if data_type == "FTIR":
            result["valley_position_candidates"] = local_valley_positions(numeric)
        return result
    if data_type in {"photocurrent", "photocurrent_response"}:
        tail = y_values[-3:] if len(y_values) >= 3 else y_values
        return {
            "peak_current_candidate": max(y_values) if y_values else None,
            "steady_current_candidate": sum(tail) / len(tail) if tail else None,
            **photocurrent_results(rows, y_values),
        }
    if data_type == "XPS":
        return {
            "peak_position_candidates": local_peak_positions(numeric),
            "area_candidate": trapezoid_area(numeric),
            "binding_energy_display": "descending",
            **xps_export_results(rows),
        }
    if data_type == "HPLC/LC exported data":
        return lc_results(numeric, rows)
    if data_type == "reaction_condition_screening":
        records = condition_screening_records(rows)
        values = [record[1] for record in records] if records else y_values
        return {"best_condition_value_candidate": max(values) if values else None}
    if data_type == "BET":
        isotherm = bet_isotherm_rows(rows)
        pore_distribution = bet_pore_distribution_rows(rows)
        summary = bet_summary_results(rows)
        result = {**summary}
        if isotherm:
            adapter = bet_package_results(isotherm)
            result["isotherm_points"] = int(adapter.get("isotherm_point_count") or len(isotherm))
            result["bet_table_kind_candidate"] = "isotherm"
            if adapter.get("pygaps_pointisotherm_constructed"):
                result["pygaps_relative_pressure_range"] = adapter.get("relative_pressure_range", [])
                result["pygaps_loading_range"] = adapter.get("loading_range", [])
                result["adapter_results"] = {"BET": adapter}
        elif pore_distribution:
            result["pore_distribution_points"] = len(pore_distribution)
            result["bet_table_kind_candidate"] = "pore_distribution"
        elif summary:
            result["bet_table_kind_candidate"] = "summary_only"
        if pore_distribution:
            result["pore_distribution_points"] = len(pore_distribution)
        return result
    if data_type == "EPR":
        result = {
            "peak_position_candidates": local_peak_positions(numeric),
            "peak_intensity_candidate": max(y_values) if y_values else None,
        }
        adapter = epr_package_results(numeric, rows)
        if adapter.get("ok"):
            result.update(
                {
                    key: value
                    for key, value in adapter.items()
                    if key
                    in {
                        "peak_to_peak_intensity_candidate",
                        "minimum_intensity_field",
                        "maximum_intensity_field",
                        "g_candidate_at_max_intensity",
                    }
                }
            )
            result["adapter_results"] = {"EPR": adapter}
        else:
            result.update(
                {
                    "peak_to_peak_intensity_candidate": (max(y_values) - min(y_values)) if y_values else None,
                    **epr_extrema_results(numeric, rows),
                }
            )
        return result
    if data_type == "Mott-Schottky":
        mott_numeric = mott_schottky_numeric(rows, numeric)
        linear = mott_schottky_linear_results(mott_numeric)
        flat_band = linear.get("linear_x_intercept_candidate", x_at_min_abs_y(mott_numeric))
        result = {
            "flat_band_potential_candidate": flat_band,
            **linear,
        }
        frequency_groups = mott_schottky_frequency_groups(rows)
        if frequency_groups:
            result["mott_schottky_frequency_groups"] = frequency_groups
        return result
    return {}


def build_processed_table(
    data_type: str,
    numeric: list[tuple[float, float]],
    rows: list[dict[str, str]],
) -> tuple[list[str], list[list[float | str | None]]]:
    if data_type == "XRD":
        peaks = set(local_peak_positions(numeric))
        max_y = max((y for _, y in numeric), default=None)
        output = []
        for two_theta, intensity in numeric:
            normalized = intensity / max_y if max_y else None
            output.append([two_theta, intensity, normalized, 1 if two_theta in peaks else 0])
        return ["two_theta_deg", "intensity", "normalized_intensity", "peak_candidate_flag"], output

    if data_type == "UV-vis DRS":
        return uvvis_processed_table(numeric, rows)

    if data_type == "EIS":
        output = []
        for row in rows:
            frequency = first_numeric(row, ["frequency", "freq", "hz"])
            real = first_numeric(row, ["re(z)", "real", "zreal", "z'", "z’", "z′", "zre"])
            neg_imag = first_numeric(row, ["-im", "-im(z)", "negative imaginary", "-z\"", "-z''", "-z”", "zimag"])
            if neg_imag is None:
                imag = first_numeric(row, ["im(z)", "imaginary", "z\"", "z''", "z”", "zimag"])
                neg_imag = abs(imag) if imag is not None else None
            magnitude = first_numeric(row, ["|z|", "zmod", "modulus", "magnitude"])
            phase = first_numeric(row, ["phase"])
            if frequency is not None and real is not None and neg_imag is not None:
                if magnitude is None:
                    magnitude = sqrt(real * real + neg_imag * neg_imag)
                output.append([frequency, real, neg_imag, magnitude, phase])
        if output:
            return ["frequency", "real_impedance", "neg_imag_impedance", "impedance_magnitude", "phase"], output

    if data_type in {"PL", "FTIR", "Raman"}:
        max_y = max((y for _, y in numeric), default=None)
        valleys = set(local_valley_positions(numeric))
        auxiliary_columns = spectral_auxiliary_columns(rows)
        auxiliary_headers = [f"{safe_column_name(key)}_optional" for key in auxiliary_columns]
        baseline_records = spectral_package_baseline_records(numeric)
        baseline_headers = ["pybaselines_baseline_optional", "pybaselines_corrected_intensity_optional"] if baseline_records else []
        output = []
        for index, (x_value, y_value) in enumerate(numeric):
            normalized = y_value / max_y if max_y else None
            optional_values = spectral_auxiliary_values(rows, auxiliary_columns, index)
            baseline_values: list[float | None] = []
            if baseline_records:
                baseline_values = [baseline_records[index][0], baseline_records[index][1]]
            if data_type == "FTIR":
                output.append([x_value, y_value, normalized, 1 if x_value in valleys else 0, *optional_values, *baseline_values])
            else:
                output.append([x_value, y_value, normalized, *optional_values, *baseline_values])
        if data_type == "FTIR":
            return ["x", "intensity", "normalized_intensity", "valley_candidate_flag", *auxiliary_headers, *baseline_headers], output
        return ["x", "intensity", "normalized_intensity", *auxiliary_headers, *baseline_headers], output

    if data_type in {"photocurrent", "photocurrent_response"}:
        return photocurrent_processed_table(numeric, rows)

    if data_type == "XPS":
        return xps_processed_table(numeric, rows)

    if data_type == "reaction_condition_screening":
        records = condition_screening_records(rows)
        if records:
            best = max((value for _, value in records), default=None)
            return (
                ["condition", "response_value", "best_condition_candidate_flag"],
                [[condition, value, 1 if best is not None and value == best else 0] for condition, value in records],
            )
        best = max((y for _, y in numeric), default=None)
        return (
            ["condition", "response_value", "best_condition_candidate_flag"],
            [[condition, value, 1 if best is not None and value == best else 0] for condition, value in numeric],
        )

    if data_type == "HPLC/LC exported data":
        return lc_processed_table(rows)

    if data_type == "BET":
        return bet_processed_table(rows)

    if data_type == "EPR":
        max_abs = max((abs(y) for _, y in numeric), default=None)
        output = []
        for field, intensity in numeric:
            normalized = intensity / max_abs if max_abs else None
            frequency = epr_frequency_for_field(rows, field)
            output.append([field, intensity, normalized, epr_g_candidate(field, frequency)])
        if any(row[3] is not None for row in output):
            return ["magnetic_field", "intensity", "normalized_intensity", "g_candidate_optional"], output
        return ["magnetic_field", "intensity", "normalized_intensity"], [row[:3] for row in output]

    if data_type == "Mott-Schottky":
        row_output = mott_schottky_processed_rows(rows)
        if row_output:
            if any(record[2] is not None for record in row_output):
                return ["potential", "one_over_c_squared", "frequency_optional"], row_output
            return ["potential", "one_over_c_squared"], [record[:2] for record in row_output]
        if rows:
            return ["potential", "one_over_c_squared"], []
        output = [[potential, one_over_c2] for potential, one_over_c2 in mott_schottky_numeric(rows, numeric)]
        return ["potential", "one_over_c_squared"], output

    return ["x", "y"], [[x_value, y_value] for x_value, y_value in numeric]


def uvvis_results(numeric: list[tuple[float, float]], rows: list[dict[str, str]]) -> dict:
    signal = uvvis_signal_type(rows)
    converted = []
    photon_energies = []
    for wavelength_nm, reflectance in numeric:
        if wavelength_nm <= 0:
            continue
        photon_energy = 1239.7 / wavelength_nm
        value = reflectance
        if signal == "absorbance":
            tauc_y = (value * photon_energy) ** 2
            if isfinite(tauc_y):
                converted.append((wavelength_nm, value))
                photon_energies.append(photon_energy)
            continue
        reflectance_fraction = value / 100.0 if value > 1 else value
        if reflectance_fraction <= 0:
            continue
        kubelka_munk = ((1 - reflectance_fraction) ** 2) / (2 * reflectance_fraction)
        if isfinite(kubelka_munk):
            converted.append((wavelength_nm, kubelka_munk))
            photon_energies.append(photon_energy)
    return {
        "uvvis_input_signal": signal,
        "kubelka_munk_points": len(converted),
        "photon_energy_range_eV": [min(photon_energies), max(photon_energies)] if photon_energies else [],
        "tauc_interval_candidate_eV": [min(photon_energies), max(photon_energies)] if len(photon_energies) >= 2 else [],
        "Eg_candidate": None,
    }


def eis_results(numeric: list[tuple[float, float]], rows: list[dict[str, str]]) -> dict:
    neg_imaginary = eis_negative_imaginary_values(rows)
    frequency = column_values(rows, ["frequency", "freq", "hz"])
    return {
        "nyquist_points": len(numeric),
        "bode_points": len(frequency) if frequency else len(numeric),
        "max_negative_imaginary_impedance": max(neg_imaginary) if neg_imaginary else None,
    }


def lc_results(numeric: list[tuple[float, float]], rows: list[dict[str, str]]) -> dict:
    mode = classify_hplc_lc_exported_table(rows)
    result = {
        "lc_export_mode": mode,
    }
    if mode == "ambiguous":
        review = build_hplc_lc_manual_review_reason(rows)
        result.update(
            {
                "lc_manual_review_required": review["manual_review_required"],
                "lc_missing_fields": review["missing_fields"],
                "lc_plot_intent": build_hplc_lc_plot_intent(mode),
            }
        )
        return result

    if mode == "calibration_curve":
        candidate = extract_hplc_lc_calibration_candidate(rows)
        result.update(
            {
                "lc_plot_intent": candidate["plot_intent"],
                "lc_calibration_candidate": {
                    key: value
                    for key, value in candidate.items()
                    if key not in {"candidate", "mode", "plot_intent", "requires_manual_mapping"}
                },
            }
        )
        return result

    result["retention_time_range"] = [numeric[0][0], numeric[-1][0]] if numeric else []
    if mode == "peak_table":
        areas = column_values(rows, ["area", "peak area"])
        candidate = extract_hplc_lc_peak_table_candidate(rows)
        result.update(
            {
                "peak_area_total_candidate": sum(areas) if areas else None,
                "lc_candidate_peaks": candidate["peaks"],
                "lc_requires_manual_calibration": True,
                "lc_quantification_boundary": "requires_manual_calibration",
                "lc_plot_intent": candidate["plot_intent"],
            }
        )
    else:
        result["lc_plot_intent"] = extract_hplc_lc_chromatogram_candidate(rows)["plot_intent"]
    blocked_reason = lc_quantification_blocked_reason(rows)
    if blocked_reason:
        result["lc_quantification_blocked_reason"] = blocked_reason
    return result


def uvvis_processed_table(
    numeric: list[tuple[float, float]],
    rows: list[dict[str, str]],
) -> tuple[list[str], list[list[float | str | None]]]:
    signal = uvvis_signal_type(rows)
    output = []
    if signal == "absorbance":
        for wavelength_nm, absorbance in numeric:
            photon_energy = 1239.7 / wavelength_nm if wavelength_nm > 0 else None
            tauc_y = (absorbance * photon_energy) ** 2 if photon_energy is not None else None
            output.append([wavelength_nm, absorbance, photon_energy, tauc_y])
        return ["wavelength_nm", "absorbance", "photon_energy_eV", "tauc_y_absorbance_direct_candidate"], output

    for wavelength_nm, reflectance in numeric:
        reflectance_fraction = reflectance / 100.0 if reflectance > 1 else reflectance
        photon_energy = 1239.7 / wavelength_nm if wavelength_nm > 0 else None
        kubelka_munk = None
        tauc_y = None
        if reflectance_fraction > 0:
            kubelka_munk = ((1 - reflectance_fraction) ** 2) / (2 * reflectance_fraction)
            if photon_energy is not None:
                tauc_y = (kubelka_munk * photon_energy) ** 2
        output.append([wavelength_nm, reflectance, reflectance_fraction, kubelka_munk, photon_energy, tauc_y])
    return ["wavelength_nm", "reflectance", "reflectance_fraction", "kubelka_munk", "photon_energy_eV", "tauc_y_direct_candidate"], output


def uvvis_signal_type(rows: list[dict[str, str]]) -> str:
    if rows and matching_key(rows[0], ["absorbance", "abs"]):
        return "absorbance"
    return "reflectance"


def photocurrent_results(rows: list[dict[str, str]], values: list[float]) -> dict:
    states = light_states(rows)
    result = {"on_off_ratio_candidate": on_off_ratio_candidate(values)}
    if states:
        on_values = [first_numeric(row, ["current"]) for row, state in zip(rows, states) if state == "on"]
        off_values = [first_numeric(row, ["current"]) for row, state in zip(rows, states) if state == "off"]
        on_values = [value for value in on_values if value is not None]
        off_values = [value for value in off_values if value is not None]
        result["light_on_points"] = len(on_values)
        result["light_off_points"] = len(off_values)
        if on_values and off_values:
            off_mean = sum(off_values) / len(off_values)
            result["on_off_ratio_candidate"] = (sum(on_values) / len(on_values)) / off_mean if off_mean > 0 else None
    return result


def photocurrent_processed_table(
    numeric: list[tuple[float, float]],
    rows: list[dict[str, str]],
) -> tuple[list[str], list[list[float | str | None]]]:
    states = light_states(rows)
    if not states:
        output = []
        for index, (time_value, current) in enumerate(numeric):
            output.append([time_value, current * 1_000_000, index // 2 + 1])
        return ["time_s", "photocurrent_uA", "cycle_candidate_id"], output

    output = []
    cycle = 1
    previous = states[0]
    for index, (time_value, current) in enumerate(numeric):
        state = states[index] if index < len(states) else ""
        if index and state != previous:
            cycle += 1
            previous = state
        area = first_numeric(rows[index], ["area_cm2", "area"]) if index < len(rows) else None
        density = current / area if area and area != 0 else None
        density_uA = density * 1_000_000 if density is not None else None
        output.append([time_value, current * 1_000_000, state, cycle, density_uA])
    return ["time_s", "photocurrent_uA", "light_state", "cycle_candidate_id", "current_density_uA_cm2_optional"], output


def xps_export_results(rows: list[dict[str, str]]) -> dict:
    components = xps_component_columns(rows)
    adapter = xps_package_results(rows)
    if adapter.get("ok") and adapter.get("component_labels"):
        components = [str(label) for label in adapter["component_labels"]]
    result = {
        "xps_background_preserved": bool(rows and matching_key(rows[0], ["background", "backgnd"])),
        "xps_envelope_preserved": bool(rows and matching_key(rows[0], ["envelope", "fit"])),
    }
    if components:
        result["xps_component_columns"] = components
        result["xps_component_count"] = len(components)
        component_areas = xps_component_area_candidates(rows, components)
        if component_areas:
            result["xps_component_area_candidates"] = component_areas
    if adapter.get("ok"):
        result["adapter_results"] = {"XPS": adapter}
    return result


def xps_package_results(rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {}
    from src.adapters import xps_lmfitxps_adapter

    result = xps_lmfitxps_adapter.process_or_analyze(xps_numeric_curves(rows))
    return result if result.get("ok") else {}


def xps_numeric_curves(rows: list[dict[str, str]]) -> dict[str, list[float]]:
    if not rows:
        return {}
    binding_key = matching_key(rows[0], ["binding energy", "bindingenergy"])
    curves: dict[str, list[float]] = {}
    for key in rows[0]:
        if key == binding_key:
            continue
        values = []
        for row in rows:
            value = first_numeric(row, [key])
            if value is not None:
                values.append(float(value))
        if values:
            curves[key] = values
    return curves


def xps_processed_table(
    numeric: list[tuple[float, float]],
    rows: list[dict[str, str]],
) -> tuple[list[str], list[list[float | str | None]]]:
    peaks = set(local_peak_positions(numeric))
    if not rows:
        return (
            ["binding_energy_eV", "raw_intensity", "peak_candidate_flag"],
            [[binding_energy, intensity, 1 if binding_energy in peaks else 0] for binding_energy, intensity in numeric],
        )
    binding_key = matching_key(rows[0], ["binding energy", "bindingenergy"])
    raw_key = matching_key(rows[0], ["raw intensity", "intensity", "counts"])
    background_key = matching_key(rows[0], ["background"])
    envelope_key = matching_key(rows[0], ["envelope", "fit"])
    components = xps_component_columns(rows)
    headers = ["binding_energy_eV", "raw_intensity", "peak_candidate_flag"]
    if background_key:
        headers.append("background_optional")
    if envelope_key:
        headers.append("envelope_optional")
    headers.extend(f"{safe_column_name(column)}_optional" for column in components)

    output = []
    for row in rows:
        binding = first_numeric(row, [binding_key]) if binding_key else None
        raw = first_numeric(row, [raw_key]) if raw_key else None
        if binding is None or raw is None:
            continue
        record: list[float | str | None] = [binding, raw, 1 if binding in peaks else 0]
        if background_key:
            record.append(first_numeric(row, [background_key]))
        if envelope_key:
            record.append(first_numeric(row, [envelope_key]))
        for component in components:
            record.append(first_numeric(row, [component]))
        output.append(record)
    if not output and numeric:
        return (
            ["binding_energy_eV", "raw_intensity", "peak_candidate_flag"],
            [[binding_energy, intensity, 1 if binding_energy in peaks else 0] for binding_energy, intensity in numeric],
        )
    return headers, output


def lc_processed_table(rows: list[dict[str, str]]) -> tuple[list[str], list[list[float | str | None]]]:
    mode = lc_export_mode(rows)
    if mode == "ambiguous":
        return (
            ["manual_review_reason", "missing_fields"],
            [["ambiguous_exported_table", ";".join(lc_missing_fields(rows))]],
        )
    if mode == "calibration_curve":
        output = []
        analyte_key = lc_analyte_key(rows)
        for row in rows:
            concentration = first_numeric(row, ["concentration", "standard concentration"])
            response = first_numeric(row, ["response", "peak area", "area"])
            if concentration is None or response is None:
                continue
            analyte = str(row.get(analyte_key, "")).strip() if analyte_key else ""
            output.append([concentration, response, analyte or None, True])
        return ["concentration", "response", "analyte_optional", "manual_check_required"], output

    peak_name_key = lc_peak_name_key(rows) if mode == "peak_table" else None
    output = []
    for row in rows:
        retention_time = first_numeric(row, ["retention", "rt", "time"])
        signal = first_numeric(row, ["intensity", "absorbance", "signal", "mau"])
        area = first_numeric(row, ["area", "peak area"])
        height = first_numeric(row, ["height", "peak height"])
        if retention_time is None:
            continue
        if mode == "peak_table":
            record: list[float | str | None] = [retention_time, signal, area, height]
            if peak_name_key:
                record.append(str(row.get(peak_name_key, "")).strip() or None)
            output.append(record)
        else:
            output.append([retention_time, signal])
    if mode == "peak_table":
        headers = ["retention_time_min", "signal", "peak_area_optional", "peak_height_optional"]
        if peak_name_key:
            headers.append("peak_name_optional")
        return headers, output
    return ["retention_time_min", "signal"], output


def lc_export_mode(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "ambiguous"
    if lc_has_calibration_table(rows):
        return "calibration_curve"
    if matching_key(rows[0], ["area", "peak area", "height", "peak height"]):
        return "peak_table"
    if matching_key(rows[0], ["retention", "rt", "time"]) and matching_key(rows[0], ["intensity", "absorbance", "signal", "mau"]):
        return "chromatogram"
    return "ambiguous"


def classify_hplc_lc_exported_table(table: object) -> str:
    return lc_export_mode(hplc_lc_table_rows(table))


def extract_hplc_lc_chromatogram_candidate(table: object) -> dict[str, object]:
    rows = hplc_lc_table_rows(table)
    points = hplc_lc_chromatogram_points(rows)
    return {
        "candidate": True,
        "mode": "chromatogram",
        "point_count": len(points),
        "retention_time_range": [points[0][0], points[-1][0]] if points else [],
        "x_axis": "retention_time_min",
        "y_axis": "signal",
        "manual_check_required": True,
        "forbidden_claims": hplc_lc_forbidden_candidate_claims(),
        "plot_intent": build_hplc_lc_plot_intent("chromatogram"),
    }


def extract_hplc_lc_peak_table_candidate(table: object) -> dict[str, object]:
    rows = hplc_lc_table_rows(table)
    peaks = lc_candidate_peak_rows(rows)
    areas = [float(peak["area"]) for peak in peaks if peak.get("area") is not None]
    return {
        "candidate": True,
        "mode": "peak_table",
        "peaks": peaks,
        "peak_count": len(peaks),
        "peak_area_total_candidate": sum(areas) if areas else None,
        "requires_manual_calibration": True,
        "requires_manual_mapping": True,
        "manual_check_required": True,
        "forbidden_claims": hplc_lc_forbidden_candidate_claims(),
        "plot_intent": build_hplc_lc_plot_intent("peak_table"),
    }


def extract_hplc_lc_calibration_candidate(table: object) -> dict[str, object]:
    rows = hplc_lc_table_rows(table)
    candidate = lc_calibration_candidate(rows)
    return {
        "candidate": True,
        "mode": "calibration_curve",
        **candidate,
        "requires_manual_mapping": True,
        "forbidden_claims": hplc_lc_forbidden_candidate_claims(),
        "plot_intent": build_hplc_lc_plot_intent("calibration_curve"),
    }


def build_hplc_lc_manual_review_reason(table: object) -> dict[str, object]:
    rows = hplc_lc_table_rows(table)
    return {
        "manual_review_required": True,
        "reason": "ambiguous_exported_table",
        "missing_fields": lc_missing_fields(rows),
    }


def build_hplc_lc_plot_intent(mode: str) -> dict[str, object]:
    if mode == "chromatogram":
        return {
            "candidate": True,
            "plot_type": "chromatogram",
            "x_axis": "retention_time_min",
            "y_axis": "signal",
            "manual_check_required": True,
        }
    if mode == "peak_table":
        return {
            "candidate": True,
            "plot_type": "peak_table_summary",
            "x_axis": "retention_time_min",
            "y_axis": "peak_area_optional",
            "manual_check_required": True,
        }
    if mode == "calibration_curve":
        return {
            "candidate": True,
            "plot_type": "calibration_curve",
            "x_axis": "concentration",
            "y_axis": "response",
            "manual_check_required": True,
        }
    return {
        "candidate": False,
        "reason": "ambiguous_exported_table",
    }


def hplc_lc_table_rows(table: object) -> list[dict[str, str]]:
    if table is None:
        return []
    if isinstance(table, list):
        raw_rows = table
    elif hasattr(table, "to_dict"):
        raw_rows = table.to_dict(orient="records")  # type: ignore[call-arg]
    else:
        raw_rows = list(table) if not isinstance(table, (str, bytes)) else []
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        rows.append({str(key): "" if value is None else str(value) for key, value in row.items()})
    return rows


def hplc_lc_chromatogram_points(rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    points = []
    for row in rows:
        retention_time = first_numeric(row, ["retention", "rt", "time"])
        signal = first_numeric(row, ["intensity", "absorbance", "signal", "mau"])
        if retention_time is not None and signal is not None:
            points.append((retention_time, signal))
    return points


def hplc_lc_forbidden_candidate_claims() -> list[str]:
    return [
        "no_peak_identity_assignment",
        "no_product_identity_assignment",
        "no_conversion_selectivity_yield_without_calibration_mapping",
    ]


def lc_quantification_blocked_reason(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    has_quantification_or_identity = matching_key(
        rows[0],
        ["concentration", "amount", "conversion", "selectivity", "yield", "product", "identity"],
    )
    has_calibration_evidence = matching_key(
        rows[0],
        ["calibration", "standard curve", "response factor", "external standard", "internal standard"],
    )
    if has_quantification_or_identity and not has_calibration_evidence:
        return "LC quantification/product-identity fields require calibration evidence and manual confirmation; no conversion/selectivity/product candidates were computed."
    return None


def lc_has_calibration_table(rows: list[dict[str, str]]) -> bool:
    if not rows:
        return False
    first = rows[0]
    return bool(
        matching_key(first, ["concentration", "standard concentration"])
        and matching_key(first, ["response", "peak area", "area"])
        and lc_analyte_key(rows)
    )


def lc_analyte_key(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    return matching_key(rows[0], ["analyte", "manual mapping", "compound", "standard name"])


def lc_peak_name_key(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    return matching_key(rows[0], ["peak name"])


def lc_missing_fields(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["time_or_retention_time", "signal_or_peak_area_or_calibration_response"]
    first = rows[0]
    missing = []
    if not matching_key(first, ["retention", "rt", "time"]) and not matching_key(first, ["concentration", "standard concentration"]):
        missing.append("time_or_retention_time")
    if not (
        matching_key(first, ["intensity", "absorbance", "signal", "mau"])
        or matching_key(first, ["area", "peak area", "height", "peak height", "response"])
    ):
        missing.append("signal_or_peak_area_or_calibration_response")
    if matching_key(first, ["concentration", "standard concentration"]) and not lc_analyte_key(rows):
        missing.append("analyte_or_manual_mapping")
    return missing or ["unrecognized_hplc_lc_export_shape"]


def lc_candidate_peak_rows(rows: list[dict[str, str]]) -> list[dict[str, float | str | None]]:
    peak_name_key = lc_peak_name_key(rows)
    candidates = []
    for row in rows:
        retention_time = first_numeric(row, ["retention", "rt", "time"])
        area = first_numeric(row, ["area", "peak area"])
        height = first_numeric(row, ["height", "peak height"])
        if retention_time is None:
            continue
        peak_name = str(row.get(peak_name_key, "")).strip() if peak_name_key else None
        candidates.append(
            {
                "retention_time": retention_time,
                "area": area,
                "height": height,
                "peak_name": peak_name or None,
                "identity_assignment": "unassigned_manual_mapping_required",
            }
        )
    return candidates


def lc_calibration_candidate(rows: list[dict[str, str]]) -> dict[str, float | int | str | bool | None]:
    points = []
    for row in rows:
        concentration = first_numeric(row, ["concentration", "standard concentration"])
        response = first_numeric(row, ["response", "peak area", "area"])
        if concentration is not None and response is not None:
            points.append((concentration, response))

    analyte = None
    analyte_key = lc_analyte_key(rows)
    if analyte_key:
        for row in rows:
            value = str(row.get(analyte_key, "")).strip()
            if value:
                analyte = value
                break

    candidate: dict[str, float | int | str | bool | None] = {
        "fit_method": "ordinary_least_squares_candidate",
        "point_count": len(points),
        "analyte": analyte,
        "manual_check_required": True,
    }
    if len(points) >= 2:
        slope, intercept = linear_regression(points)
        candidate.update(
            {
                "slope": slope,
                "intercept": intercept,
                "r_squared": linear_r_squared(points, slope, intercept),
            }
        )
    else:
        candidate.update({"slope": None, "intercept": None, "r_squared": None})
    return candidate


def bet_numeric(rows: list[dict[str, str]], fallback: list[tuple[float, float]]) -> list[tuple[float, float]]:
    isotherm = bet_isotherm_rows(rows)
    if isotherm:
        return [(float(row[0]), float(row[1])) for row in isotherm if row[0] is not None and row[1] is not None]
    pore_distribution = bet_pore_distribution_rows(rows)
    if pore_distribution:
        return [(float(row[0]), float(row[1])) for row in pore_distribution if row[0] is not None and row[1] is not None]
    summary = bet_summary_results(rows)
    if summary and not fallback:
        return [(float(index + 1), value) for index, value in enumerate(summary.values())]
    return fallback


def bet_summary_results(rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {}
    metric_key = matching_key(rows[0], ["metric", "parameter", "item"])
    value_key = matching_key(rows[0], ["value", "reported"])
    if metric_key and value_key:
        return bet_metric_summary_results(rows, metric_key, value_key)
    first = rows[0]
    result = {}
    surface = first_numeric(first, ["bet surface area", "surface area"])
    pore_volume = first_numeric(first, ["total pore volume", "pore volume"])
    pore_diameter = first_numeric(first, ["average pore diameter", "pore diameter"])
    if surface is not None:
        result["bet_surface_area_m2_g_candidate"] = surface
    if pore_volume is not None:
        result["pore_volume_cm3_g_candidate"] = pore_volume
    if pore_diameter is not None:
        result["average_pore_diameter_nm_candidate"] = pore_diameter
    return result


def bet_metric_summary_results(rows: list[dict[str, str]], metric_key: str, value_key: str) -> dict:
    result = {}
    for row in rows:
        metric = str(row.get(metric_key, "")).lower()
        value = to_float(row.get(value_key, ""))
        if value is None:
            continue
        if "surface" in metric and "area" in metric:
            result["bet_surface_area_m2_g_candidate"] = value
        elif "pore" in metric and "volume" in metric:
            result["pore_volume_cm3_g_candidate"] = value
        elif "pore" in metric and ("diameter" in metric or "size" in metric):
            result["average_pore_diameter_nm_candidate"] = value
    return result


def bet_processed_table(rows: list[dict[str, str]]) -> tuple[list[str], list[list[float | str | None]]]:
    isotherm = bet_isotherm_rows(rows)
    if isotherm:
        return ["relative_pressure_p_p0", "adsorbed_volume", "desorption_volume_optional"], isotherm

    pore_distribution = bet_pore_distribution_rows(rows)
    if pore_distribution:
        return ["pore_size_nm", "pore_volume_cm3_g"], pore_distribution

    summary = bet_summary_results(rows)
    if summary and not any(matching_key(row, ["relative pressure", "p/p0", "p/p"]) for row in rows):
        headers = [
            "bet_surface_area_m2_g_candidate",
            "pore_volume_cm3_g_candidate",
            "average_pore_diameter_nm_candidate",
        ]
        return headers, [[summary.get(header) for header in headers]]

    return ["bet_surface_area_m2_g_candidate", "pore_volume_cm3_g_candidate", "average_pore_diameter_nm_candidate"], []


def bet_isotherm_rows(rows: list[dict[str, str]]) -> list[list[float | str | None]]:
    vendor_isotherm = bet_vendor_isotherm_rows(rows)
    if vendor_isotherm:
        return vendor_isotherm

    output = []
    for row in rows:
        pressure = first_numeric(row, ["relative pressure", "p/p0", "p/p"])
        adsorbed = first_numeric(row, ["quantity adsorbed", "adsorbed", "adsorption"])
        desorption = first_numeric(row, ["desorption"])
        if pressure is not None and adsorbed is not None:
            output.append([pressure, adsorbed, desorption])
    return output if len(output) >= 2 else []


def bet_pore_distribution_rows(rows: list[dict[str, str]]) -> list[list[float | str | None]]:
    output: list[list[float | str | None]] = []
    for row in rows:
        pore_size = first_numeric(row, ["pore size", "pore diameter", "pore width", "diameter/nm", "width/nm"])
        pore_volume = first_numeric(
            row,
            [
                "dV/dlog",
                "dV",
                "differential pore volume",
                "pore volume distribution",
                "differential volume",
            ],
        )
        if pore_size is None or pore_volume is None:
            continue
        if pore_size > 0 and isfinite(pore_volume):
            output.append([pore_size, pore_volume])
    return output if len(output) >= 2 else []


def bet_package_results(isotherm_rows: list[list[float | str | None]]) -> dict:
    if not isotherm_rows:
        return {}
    from src.adapters import bet_pygaps_adapter

    relative_pressure = []
    loading = []
    for row in isotherm_rows:
        if len(row) < 2:
            continue
        try:
            pressure = float(row[0])
            amount = float(row[1])
        except (TypeError, ValueError):
            continue
        relative_pressure.append(pressure)
        loading.append(amount)
    if not relative_pressure:
        return {}
    result = bet_pygaps_adapter.process_or_analyze(relative_pressure, loading)
    return result if result.get("ok") else {}


def bet_vendor_isotherm_rows(rows: list[dict[str, str]]) -> list[list[float | str | None]]:
    """Extract adsorption/desorption branches from wide vendor BET report sheets.

    Some instrument exports are a single wide Excel report with repeated
    subreports. The workbook header is metadata, while the real isotherm table is
    embedded later as adjacent "Relative Pressure (P/Po)" / "Quantity Adsorbed"
    column pairs. Prefer those pairs over summary-only candidate fields.
    """
    if not rows:
        return []
    row_values = [list(row.values()) for row in rows]
    for header_index, values in enumerate(row_values):
        pair_indices = []
        for index in range(len(values) - 1):
            left = str(values[index]).casefold()
            right = str(values[index + 1]).casefold()
            if _is_bet_relative_pressure_label(left) and _is_bet_quantity_adsorbed_label(right):
                pair_indices.append((index, index + 1))
        if len(pair_indices) < 2:
            continue

        branches: list[list[tuple[float, float]]] = []
        for x_index, y_index in pair_indices:
            branch: list[tuple[float, float]] = []
            for data_values in row_values[header_index + 1 :]:
                if x_index >= len(data_values) or y_index >= len(data_values):
                    continue
                pressure = to_float(data_values[x_index])
                quantity = to_float(data_values[y_index])
                if pressure is None or quantity is None:
                    continue
                if 0 <= pressure <= 1.05 and isfinite(quantity):
                    branch.append((pressure, quantity))
            if len(branch) >= 5:
                branches.append(branch)

        if len(branches) >= 2:
            adsorption = sorted(_dedupe_points(branches[0]), key=lambda item: item[0])
            desorption = sorted(_dedupe_points(branches[1]), key=lambda item: item[0])
            if len(adsorption) < 5 or len(desorption) < 5:
                continue
            return [
                [pressure, adsorbed, _interpolated_y(desorption, pressure)]
                for pressure, adsorbed in adsorption
            ]
    return []


def _is_bet_relative_pressure_label(value: str) -> bool:
    return "relative pressure" in value or "p/po" in value or "p/p0" in value


def _is_bet_quantity_adsorbed_label(value: str) -> bool:
    return "quantity adsorbed" in value or "adsorbed" in value


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: dict[float, float] = {}
    for x_value, y_value in points:
        deduped[float(x_value)] = float(y_value)
    return [(x_value, deduped[x_value]) for x_value in deduped]


def _interpolated_y(points: list[tuple[float, float]], x_value: float) -> float | None:
    if not points:
        return None
    if x_value <= points[0][0]:
        return points[0][1]
    if x_value >= points[-1][0]:
        return points[-1][1]
    for left, right in zip(points, points[1:]):
        x0, y0 = left
        x1, y1 = right
        if x0 <= x_value <= x1:
            if x1 == x0:
                return y0
            ratio = (x_value - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return None


def epr_extrema_results(numeric: list[tuple[float, float]], rows: list[dict[str, str]]) -> dict:
    if not numeric:
        return {}
    min_field, _ = min(numeric, key=lambda item: item[1])
    max_field, _ = max(numeric, key=lambda item: item[1])
    frequency = epr_frequency_for_field(rows, max_field)
    result = {
        "minimum_intensity_field": float(min_field),
        "maximum_intensity_field": float(max_field),
    }
    g_value = epr_g_candidate(max_field, frequency)
    if g_value is not None:
        result["g_candidate_at_max_intensity"] = g_value
    return result


def epr_package_results(numeric: list[tuple[float, float]], rows: list[dict[str, str]]) -> dict:
    if not numeric:
        return {}
    from src.adapters import epr_adapter

    fields = [field for field, _ in numeric]
    intensities = [intensity for _, intensity in numeric]
    frequencies = [epr_frequency_for_field(rows, field) for field in fields]
    result = epr_adapter.process_or_analyze(
        fields,
        intensities,
        microwave_frequency_ghz=frequencies if any(value is not None for value in frequencies) else None,
    )
    return result if result.get("ok") else {}


def epr_numeric(rows: list[dict[str, str]], fallback: list[tuple[float, float]]) -> list[tuple[float, float]]:
    output = []
    for row in rows:
        field = first_numeric(row, ["magnetic field", "field"])
        intensity = first_numeric(row, ["intensity"])
        if field is not None and intensity is not None:
            output.append((field, intensity))
    return output or fallback


def epr_frequency_for_field(rows: list[dict[str, str]], field: float) -> float | None:
    for row in rows:
        row_field = first_numeric(row, ["magnetic field", "field"])
        if row_field is None or abs(row_field - field) > 1e-9:
            continue
        frequency = first_numeric(row, ["microwave frequency", "frequency ghz", "ghz"])
        if frequency is not None:
            return frequency
    return None


def epr_g_candidate(field_value: float, frequency_ghz: float | None) -> float | None:
    if frequency_ghz is None or field_value <= 0:
        return None
    # g = h * nu / (mu_B * B). For fields exported in gauss, B_mT = G / 10.
    field_mt = field_value / 10.0 if field_value > 1000 else field_value
    return 71.4477 * frequency_ghz / field_mt


def mott_schottky_linear_results(numeric: list[tuple[float, float]]) -> dict:
    if len(numeric) < 2:
        return {}
    ordered = sorted(numeric, key=lambda item: item[0])
    slope, intercept = linear_regression(ordered)
    result = {
        "linear_interval_candidate": [ordered[0][0], ordered[-1][0]],
        "linear_slope_candidate": slope,
        "linear_intercept_candidate": intercept,
        "linear_fit_point_count": len(ordered),
        "linear_region_candidates": [
            {
                "potential_interval": [ordered[0][0], ordered[-1][0]],
                "slope": slope,
                "intercept": intercept,
                "r_squared": linear_r_squared(ordered, slope, intercept),
                "fit_point_count": len(ordered),
                "fit_method": "ordinary_least_squares_candidate",
            }
        ],
    }
    if slope:
        result["linear_x_intercept_candidate"] = -intercept / slope
    return result


def mott_schottky_frequency_groups(rows: list[dict[str, str]]) -> list[dict]:
    groups: dict[float, list[tuple[float, float]]] = {}
    for row in rows:
        potential, one_over_c2 = mott_schottky_row_values(row)
        frequency = first_numeric(row, ["frequency", "freq", "hz"])
        if potential is None or one_over_c2 is None or frequency is None:
            continue
        groups.setdefault(frequency, []).append((potential, one_over_c2))

    output = []
    for frequency in sorted(groups):
        numeric = sorted(groups[frequency], key=lambda item: item[0])
        group = {
            "frequency": frequency,
            "point_count": len(numeric),
            "potential_interval": [numeric[0][0], numeric[-1][0]] if numeric else [],
        }
        if len(numeric) >= 2:
            slope, intercept = linear_regression(numeric)
            group.update(
                {
                    "linear_slope_candidate": slope,
                    "linear_intercept_candidate": intercept,
                    "r_squared": linear_r_squared(numeric, slope, intercept),
                }
            )
            if slope:
                group["linear_x_intercept_candidate"] = -intercept / slope
        output.append(group)
    return output


def linear_regression(numeric: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(numeric)
    mean_x = sum(x for x, _ in numeric) / n
    mean_y = sum(y for _, y in numeric) / n
    denominator = sum((x - mean_x) ** 2 for x, _ in numeric)
    if denominator == 0:
        return 0.0, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in numeric) / denominator
    intercept = mean_y - slope * mean_x
    return float(slope), float(intercept)


def linear_r_squared(numeric: list[tuple[float, float]], slope: float, intercept: float) -> float:
    if len(numeric) < 2:
        return 1.0
    mean_y = sum(y for _, y in numeric) / len(numeric)
    total = sum((y - mean_y) ** 2 for _, y in numeric)
    if total == 0:
        return 1.0
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in numeric)
    return float(1 - residual / total)


def condition_screening_numeric(rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    return [(float(index + 1), response) for index, (_, response) in enumerate(condition_screening_records(rows))]


def condition_screening_records(rows: list[dict[str, str]]) -> list[tuple[str, float]]:
    records = []
    for row in rows:
        response_key = matching_key(row, ["yield", "conversion", "selectivity", "response", "value", "rate"])
        if response_key is None:
            continue
        response = to_float(row.get(response_key, ""))
        if response is None:
            continue
        labels = []
        for key, value in row.items():
            if key == response_key or not str(value).strip():
                continue
            if to_float(value) is None:
                labels.append(str(value).strip())
        condition = " | ".join(labels) if labels else str(len(records) + 1)
        records.append((condition, response))
    return records


def local_peak_positions(numeric: list[tuple[float, float]]) -> list[float]:
    if len(numeric) < 3:
        return []
    scipy_positions = scipy_peak_positions(numeric)
    if scipy_positions:
        return scipy_positions
    peaks = []
    for index in range(1, len(numeric) - 1):
        previous_y = numeric[index - 1][1]
        x_value, y_value = numeric[index]
        next_y = numeric[index + 1][1]
        if y_value >= previous_y and y_value >= next_y and (y_value > previous_y or y_value > next_y):
            peaks.append(float(x_value))
    return peaks


def scipy_peak_positions(numeric: list[tuple[float, float]]) -> list[float]:
    from src.adapters import peak_detection_adapter

    x_values = [x for x, _ in numeric]
    y_values = [y for _, y in numeric]
    result = peak_detection_adapter.process_or_analyze(x_values, y_values)
    if result.get("candidate_peaks"):
        return [float(item["x"]) for item in result["candidate_peaks"]]
    try:
        from scipy.signal import find_peaks
    except Exception:
        return []
    try:
        peak_indices, _ = find_peaks(y_values)
    except Exception:
        return []
    return [float(numeric[index][0]) for index in peak_indices]


def local_valley_positions(numeric: list[tuple[float, float]]) -> list[float]:
    if len(numeric) < 3:
        return []
    valleys = []
    for index in range(1, len(numeric) - 1):
        previous_y = numeric[index - 1][1]
        x_value, y_value = numeric[index]
        next_y = numeric[index + 1][1]
        if y_value <= previous_y and y_value <= next_y and (y_value < previous_y or y_value < next_y):
            valleys.append(float(x_value))
    return valleys


def x_at_min_abs_y(numeric: list[tuple[float, float]]) -> float | None:
    if not numeric:
        return None
    return float(min(numeric, key=lambda item: abs(item[1]))[0])


def trapezoid_area(numeric: list[tuple[float, float]]) -> float | None:
    if len(numeric) < 2:
        return None
    area = 0.0
    ordered = sorted(numeric, key=lambda item: item[0])
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        area += (x1 - x0) * (y0 + y1) / 2.0
    return float(area)


def on_off_ratio_candidate(values: list[float]) -> float | None:
    if not values:
        return None
    low = min(values)
    high = max(values)
    if low <= 0:
        return None
    return float(high / low)


def mott_schottky_numeric(rows: list[dict[str, str]], fallback: list[tuple[float, float]]) -> list[tuple[float, float]]:
    output = []
    for row in rows:
        potential, one_over_c2 = mott_schottky_row_values(row)
        if potential is not None and one_over_c2 is not None:
            output.append((potential, one_over_c2))
    if rows:
        return output
    return output or fallback


def mott_schottky_processed_rows(rows: list[dict[str, str]]) -> list[list[float | None]]:
    output = []
    for row in rows:
        potential, one_over_c2 = mott_schottky_row_values(row)
        if potential is not None and one_over_c2 is not None:
            output.append([potential, one_over_c2, first_numeric(row, ["frequency", "freq", "hz"])])
    return output


def mott_schottky_row_values(row: dict[str, str]) -> tuple[float | None, float | None]:
    potential = first_numeric(row, ["potential", "voltage", "ewe", "v"])
    one_over_c2 = first_numeric(row, ["1/c2", "1/c^2", "one_over_c"])
    if one_over_c2 is None:
        capacitance_key = capacitance_matching_key(row)
        capacitance = to_float(row.get(capacitance_key, "")) if capacitance_key else None
        if capacitance and capacitance != 0:
            one_over_c2 = 1.0 / (capacitance * capacitance)
    return potential, one_over_c2


def column_values(rows: list[dict[str, str]], needles: list[str]) -> list[float]:
    values = []
    for row in rows:
        key = matching_key(row, needles)
        if key is None:
            continue
        value = to_float(row.get(key, ""))
        if value is not None:
            values.append(abs(value) if key.lower().replace(" ", "") == "im(z)" else value)
    return values


def eis_negative_imaginary_values(rows: list[dict[str, str]]) -> list[float]:
    values = []
    for row in rows:
        value = first_numeric(row, ["-im", "-im(z)", "negative imaginary", "-z\"", "-z''", "-z”", "zimag"])
        if value is None:
            value = first_numeric(row, ["im(z)", "imaginary", "z\"", "z''", "z”", "zimag"])
        if value is not None:
            values.append(abs(value))
    return values


def capacitance_matching_key(row: dict[str, str]) -> str | None:
    for key in row:
        normalized = key.lower().replace(" ", "")
        if "current" in normalized:
            continue
        if any(token in normalized for token in ["capacitance", "c/f", "c(f)", "cap/f"]):
            return key
        if normalized in {"c", "cf", "c_f"}:
            return key
    return None


def spectral_auxiliary_results(rows: list[dict[str, str]]) -> dict[str, bool]:
    columns = spectral_auxiliary_columns(rows)
    if not columns:
        return {}
    result = {}
    if any(spectral_auxiliary_kind(key) in {"baseline", "background"} for key in columns):
        result["baseline_column_preserved"] = True
    if any(spectral_auxiliary_kind(key) == "corrected" for key in columns):
        result["baseline_corrected_signal_present"] = True
    if any(spectral_auxiliary_kind(key) == "raw" for key in columns):
        result["raw_signal_present"] = True
    return result


def spectral_package_results(numeric: list[tuple[float, float]]) -> dict[str, str | bool]:
    if spectral_package_baseline_records(numeric):
        return {
            "pybaselines_baseline_correction_available": True,
            "pybaselines_method": "asls_candidate",
        }
    return {}


def spectral_package_baseline_records(numeric: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(numeric) < 3:
        return []
    from src.adapters import baseline_adapter

    x_values = [x for x, _ in numeric]
    y_values = [y for _, y in numeric]
    result = baseline_adapter.process_or_analyze(x_values, y_values, lam=1e5, p=0.01)
    baseline = result.get("baseline", [])
    corrected = result.get("corrected_signal", [])
    if not result.get("ok") or len(baseline) != len(y_values) or len(corrected) != len(y_values):
        return []
    return [(float(base), float(value)) for base, value in zip(baseline, corrected)]


def spectral_auxiliary_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    columns = []
    for key in rows[0]:
        if spectral_auxiliary_kind(key) and any(first_numeric(row, [key]) is not None for row in rows):
            columns.append(key)
    return columns


def spectral_auxiliary_kind(key: str) -> str | None:
    normalized = key.lower().replace(" ", "")
    if "corrected" in normalized and ("intensity" in normalized or "signal" in normalized or "counts" in normalized):
        return "corrected"
    if "raw" in normalized and ("intensity" in normalized or "signal" in normalized or "counts" in normalized):
        return "raw"
    if "baseline" in normalized:
        return "baseline"
    if "background" in normalized:
        return "background"
    return None


def spectral_auxiliary_values(
    rows: list[dict[str, str]],
    columns: list[str],
    index: int,
) -> list[float | str | None]:
    if not columns:
        return []
    if index >= len(rows):
        return [None for _ in columns]
    return [first_numeric(rows[index], [key]) for key in columns]


def first_numeric(row: dict[str, str], needles: list[str]) -> float | None:
    key = matching_key(row, needles)
    if key is None:
        return None
    return to_float(row.get(key, ""))


def matching_key(row: dict[str, str], needles: list[str]) -> str | None:
    for key in row:
        normalized = key.lower().replace(" ", "")
        for needle in needles:
            if needle.lower().replace(" ", "") in normalized:
                return key
    return None


def light_states(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    key = matching_key(rows[0], ["light", "on/off", "illumination"])
    if key is None:
        return []
    states = []
    for row in rows:
        value = str(row.get(key, "")).strip().lower()
        if value in {"on", "1", "true", "light"}:
            states.append("on")
        elif value in {"off", "0", "false", "dark"}:
            states.append("off")
        else:
            states.append(value or "")
    return states


def xps_component_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    excluded = {"binding", "energy", "raw", "intensity", "counts", "background", "envelope", "fit", "residual", "residuals", "difference", "error"}
    components = []
    for key in rows[0]:
        normalized = key.lower().replace(" ", "")
        if "component" in normalized and any(first_numeric(row, [key]) is not None for row in rows):
            components.append(key)
            continue
        if any(token in normalized for token in excluded):
            continue
        if any(first_numeric(row, [key]) is not None for row in rows):
            components.append(key)
    return components


def xps_component_area_candidates(rows: list[dict[str, str]], components: list[str]) -> dict[str, float]:
    if not rows or not components:
        return {}
    binding_key = matching_key(rows[0], ["binding energy", "bindingenergy"])
    if binding_key is None:
        return {}
    result = {}
    for component in components:
        numeric = []
        for row in rows:
            binding = first_numeric(row, [binding_key])
            intensity = first_numeric(row, [component])
            if binding is not None and intensity is not None:
                numeric.append((binding, intensity))
        area = trapezoid_area(numeric)
        if area is not None:
            result[component] = abs(area)
    return result


def safe_column_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_") or "component"


def to_float(value: str) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None
