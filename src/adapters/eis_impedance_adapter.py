from __future__ import annotations

from collections.abc import Sequence
from math import atan2, degrees, sqrt
from typing import Any

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


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([1000, 100, 10], [10, 20, 30], [-5, -12, -8])
    return {"ok": result["ok"] and result["point_count"] == 3, "result": result}
