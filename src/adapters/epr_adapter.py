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


def process_or_analyze(
    field: Sequence[float],
    intensity: Sequence[float],
    *,
    microwave_frequency_ghz: Sequence[float | None] | None = None,
) -> dict[str, object]:
    cwepr, cwepr_error = import_optional("cwepr")
    eprpy, eprpy_error = import_optional("eprpy")
    x_values = [float(value) for value in field]
    y_values = [float(value) for value in intensity]
    count = min(len(x_values), len(y_values))
    x_values = x_values[:count]
    y_values = y_values[:count]
    fallback = None if cwepr is not None or eprpy is not None else f"cw-EPR packages unavailable: {cwepr_error}; {eprpy_error}"
    result: dict[str, object] = {
        "ok": bool(y_values),
        "point_count": count,
        "peak_to_peak_intensity_candidate": max(y_values) - min(y_values) if y_values else None,
        "manual_check_required": True,
        "fallback_reason": fallback,
    }
    if y_values and x_values:
        min_index = min(range(count), key=lambda index: y_values[index])
        max_index = max(range(count), key=lambda index: y_values[index])
        result["minimum_intensity_field"] = x_values[min_index]
        result["maximum_intensity_field"] = x_values[max_index]
        frequency = _frequency_at_index(microwave_frequency_ghz, max_index)
        g_value = _g_candidate(x_values[max_index], frequency)
        if g_value is not None:
            result["g_candidate_at_max_intensity"] = g_value
    package = "cwepr" if cwepr is not None else "EPRpy" if eprpy is not None else "cwepr/EPRpy"
    module = "cwepr" if cwepr is not None else "eprpy" if eprpy is not None else "cwepr/eprpy"
    version = version_for("cwepr", "cwepr") if cwepr is not None else version_for("EPRpy", "eprpy")
    result["metadata_provenance"] = metadata_provenance(
        adapter="epr_adapter",
        package=package,
        module=module,
        version=version,
        method="field_intensity_candidate_metrics_no_radical_assignment",
        fallback_reason=fallback,
    )
    return result


def _frequency_at_index(values: Sequence[float | None] | None, index: int) -> float | None:
    if values is None or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _g_candidate(field_value: float, frequency_ghz: float | None) -> float | None:
    if frequency_ghz is None or field_value <= 0:
        return None
    field_mt = field_value / 10.0 if field_value > 1000 else field_value
    return 71.4477 * frequency_ghz / field_mt


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([330, 331, 332], [0.0, 1.5, -0.5], microwave_frequency_ghz=[9.8, 9.8, 9.8])
    return {"ok": result["ok"], "result": result}
