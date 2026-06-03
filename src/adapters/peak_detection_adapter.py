from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "scipy"
MODULE = "scipy.signal"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, "scipy")}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["XRD", "Raman", "PL", "FTIR", "EPR", "XPS"],
        "methods": ["scipy.signal.find_peaks"],
        "outputs": ["candidate_peaks"],
        "forbidden_claims": ["no phase assignment", "no defect assignment", "no radical assignment", "no valence assignment"],
    }


def process_or_analyze(
    x_values: Sequence[float],
    y_values: Sequence[float],
    *,
    prominence: float | None = None,
    distance: int | None = None,
) -> dict[str, Any]:
    module, error = import_optional(MODULE)
    parameters = {"prominence": prominence, "distance": distance}
    if module is None:
        indices = _local_peak_indices(y_values)
        fallback_reason = f"{PACKAGE} unavailable: {error}"
    else:
        kwargs = {key: value for key, value in parameters.items() if value is not None}
        try:
            indices, properties = module.find_peaks(list(y_values), **kwargs)
            indices = [int(index) for index in indices]
            fallback_reason = None
            properties = {key: [float(item) for item in value] for key, value in properties.items()}
        except Exception as exc:
            indices = _local_peak_indices(y_values)
            fallback_reason = f"{PACKAGE} find_peaks failed; local fallback used: {exc}"
            properties = {}
    peaks = [
        {"index": int(index), "x": float(x_values[index]), "y": float(y_values[index])}
        for index in indices
        if 0 <= int(index) < len(x_values)
    ]
    return {
        "ok": True,
        "candidate_peaks": peaks,
        "fallback_reason": fallback_reason,
        "metadata_provenance": metadata_provenance(
            adapter="peak_detection_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, "scipy"),
            method="scipy.signal.find_peaks" if fallback_reason is None else "local_neighbor_peak_candidates",
            parameters=parameters,
            fallback_reason=fallback_reason,
        ),
    }


def smoke_test() -> dict[str, object]:
    x_values = [float(index) for index in range(7)]
    y_values = [0.0, 1.0, 0.2, 2.0, 0.1, 0.7, 0.0]
    result = process_or_analyze(x_values, y_values)
    return {"ok": bool(result["candidate_peaks"]), "result": result}


def _local_peak_indices(y_values: Sequence[float]) -> list[int]:
    return [
        index
        for index in range(1, len(y_values) - 1)
        if y_values[index] > y_values[index - 1] and y_values[index] > y_values[index + 1]
    ]
