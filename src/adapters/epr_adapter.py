from __future__ import annotations

from collections.abc import Sequence

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for


def is_available() -> bool:
    return is_module_available("cwepr") or is_module_available("eprpy")


def version_info() -> dict[str, object]:
    return {
        "cwepr": {"available": is_module_available("cwepr"), "version": version_for("cwepr", "cwepr")},
        "EPRpy": {"available": is_module_available("eprpy"), "version": version_for("EPRpy", "eprpy")},
    }


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["EPR"],
        "methods": ["cw-EPR import/probe", "field-intensity candidate metrics"],
        "outputs": ["peak_to_peak_intensity_candidate"],
        "forbidden_claims": ["no radical assignment"],
    }


def process_or_analyze(field: Sequence[float], intensity: Sequence[float]) -> dict[str, object]:
    cwepr, cwepr_error = import_optional("cwepr")
    eprpy, eprpy_error = import_optional("eprpy")
    y_values = [float(value) for value in intensity]
    fallback = None if cwepr is not None or eprpy is not None else f"cw-EPR packages unavailable: {cwepr_error}; {eprpy_error}"
    return {
        "ok": bool(y_values),
        "point_count": min(len(field), len(intensity)),
        "peak_to_peak_intensity_candidate": max(y_values) - min(y_values) if y_values else None,
        "manual_check_required": True,
        "fallback_reason": fallback,
        "metadata_provenance": metadata_provenance(
            adapter="epr_adapter",
            package="cwepr/EPRpy",
            module="cwepr/eprpy",
            version=str(version_info()),
            method="field_intensity_candidate_metrics_no_radical_assignment",
            fallback_reason=fallback,
        ),
    }


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([330, 331, 332], [0.0, 1.5, -0.5])
    return {"ok": result["ok"], "result": result}
