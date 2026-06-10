from __future__ import annotations

from collections.abc import Sequence
from math import atan2, degrees, sqrt
from typing import Any

import numpy as np

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "impedance"
MODULE = "impedance"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["EIS"],
        "methods": ["impedance import smoke", "Nyquist/Bode numeric validation"],
        "outputs": ["nyquist", "bode_magnitude", "bode_phase"],
        "forbidden_claims": ["no equivalent circuit selection", "no mechanism conclusion"],
    }


def process_or_analyze(
    frequency: Sequence[float],
    z_real: Sequence[float],
    z_imag: Sequence[float],
) -> dict[str, Any]:
    module, error = import_optional(MODULE)
    count = min(len(frequency), len(z_real), len(z_imag))
    rows = []
    for index in range(count):
        real = float(z_real[index])
        imag = float(z_imag[index])
        rows.append(
            {
                "frequency": float(frequency[index]),
                "real_impedance": real,
                "imag_impedance": imag,
                "neg_imag_impedance": -imag if imag < 0 else abs(imag),
                "impedance_magnitude": sqrt(real * real + imag * imag),
                "phase_deg": degrees(atan2(imag, real)),
            }
        )
    fallback_reason = None if module is not None else f"{PACKAGE} unavailable: {error}"
    return {
        "ok": count > 0,
        "point_count": count,
        "nyquist": [{"x": row["real_impedance"], "y": row["neg_imag_impedance"]} for row in rows],
        "bode": rows,
        "fallback_reason": fallback_reason,
        "metadata_provenance": metadata_provenance(
            adapter="eis_impedance_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, MODULE),
            method="numeric_eis_validation_no_fit",
            fallback_reason=fallback_reason,
        ),
    }


def fit_randles_cpe_candidate(
    frequency: Sequence[float],
    z_real: Sequence[float],
    minus_z_imag: Sequence[float],
    *,
    fit_points: int = 240,
) -> dict[str, Any]:
    circuits, error = import_optional("impedance.models.circuits")
    count = min(len(frequency), len(z_real), len(minus_z_imag))
    if circuits is None:
        return _blocked_fit(f"{PACKAGE} unavailable: {error}", count)
    if count < 4:
        return _blocked_fit("Fewer than 4 EIS points with frequency; impedance fit not attempted.", count)

    ordered = sorted(
        (
            (float(frequency[index]), float(z_real[index]), float(minus_z_imag[index]))
            for index in range(count)
            if float(frequency[index]) > 0
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if len(ordered) < 4:
        return _blocked_fit("Fewer than 4 positive-frequency EIS points; impedance fit not attempted.", len(ordered))

    freq = np.array([item[0] for item in ordered], dtype=float)
    real = np.array([item[1] for item in ordered], dtype=float)
    minus_imag = np.array([item[2] for item in ordered], dtype=float)
    measured = real - 1j * minus_imag
    max_impedance = max(float(np.nanmax(np.abs(real))), float(np.nanmax(np.abs(minus_imag))), 1.0)
    span = max(float(np.nanmax(real) - np.nanmin(real)), 1.0)
    peak_index = int(np.nanargmax(minus_imag))
    peak_freq = max(float(freq[peak_index]), 1e-6)
    rs_guess = max(float(np.nanmin(real)), 1e-6)
    rct_guess = max(span, 1e-6)
    q_guess = 1.0 / max(rct_guess * (2 * np.pi * peak_freq) ** 0.9, 1e-12)
    bounds = (
        [1e-12, 1e-12, 1e-12, 0.5],
        [max_impedance * 2.0, max(span * 10.0, max_impedance * 4.0), 1e3, 1.0],
    )

    try:
        circuit = circuits.CustomCircuit(
            "R0-p(R1,CPE1)",
            initial_guess=[rs_guess, rct_guess, q_guess, 0.9],
        )
        circuit.fit(
            freq,
            measured,
            bounds=bounds,
            weight_by_modulus=True,
            maxfev=5000,
        )
        rs, rct, q_value, n_value = [float(value) for value in circuit.parameters_]
        smooth_min_freq = max(float(freq.min()) * 1e-6, 1e-12)
        smooth_freq = np.logspace(np.log10(float(freq.max())), np.log10(smooth_min_freq), max(fit_points, len(freq)))
        predicted_smooth = circuit.predict(smooth_freq)
        fit_points_xy = [(float(value.real), float(-value.imag)) for value in predicted_smooth]
        predicted = circuit.predict(freq)
        modulus = np.maximum(np.abs(measured), max(float(np.median(np.abs(measured))) * 0.05, 1e-9))
        residual = np.concatenate(((predicted.real - measured.real) / modulus, ((-predicted.imag) - minus_imag) / modulus))
        residual_sse = float(np.sum(residual * residual))
    except Exception as exc:
        return _blocked_fit(f"{PACKAGE} Randles-CPE candidate fit failed: {exc}", len(ordered))

    return {
        "ok": True,
        "method": "impedance_custom_circuit_R0_p_R1_CPE1_candidate",
        "model": "Model A: Rs + (Rct || CPE)",
        "point_count": len(ordered),
        "fit_points": fit_points_xy,
        "parameters": {"Rs": rs, "Rct": rct, "Q": q_value, "n": n_value},
        "residual_sse": residual_sse,
        "semicircle_classification": "near-ideal semicircle candidate" if n_value >= 0.95 else "depressed semicircle candidate",
        "manual_check_required": True,
        "fallback_reason": None,
        "metadata_provenance": metadata_provenance(
            adapter="eis_impedance_adapter",
            package=PACKAGE,
            module="impedance.models.circuits",
            version=version_for(PACKAGE, MODULE),
            method="impedance_custom_circuit_R0_p_R1_CPE1_candidate",
            parameters={"circuit": "R0-p(R1,CPE1)", "weight_by_modulus": True},
        ),
    }


def _blocked_fit(reason: str, point_count: int) -> dict[str, Any]:
    return {
        "ok": False,
        "point_count": point_count,
        "fit_points": [],
        "parameters": {},
        "manual_check_required": True,
        "fallback_reason": reason,
        "metadata_provenance": metadata_provenance(
            adapter="eis_impedance_adapter",
            package=PACKAGE,
            module="impedance.models.circuits",
            version=version_for(PACKAGE, MODULE),
            method="impedance_custom_circuit_R0_p_R1_CPE1_candidate",
            fallback_reason=reason,
        ),
    }


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([1000, 100, 10], [10, 20, 30], [-5, -12, -8])
    return {"ok": result["ok"] and result["point_count"] == 3, "result": result}
