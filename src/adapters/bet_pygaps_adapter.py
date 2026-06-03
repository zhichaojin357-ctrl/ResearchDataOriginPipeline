from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "pygaps"
MODULE = "pygaps"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["BET"],
        "methods": ["PointIsotherm candidate construction when compatible"],
        "outputs": ["isotherm_point_count", "relative_pressure_range"],
        "forbidden_claims": ["no automatic BET model validation", "no pore structure conclusion"],
    }


def process_or_analyze(relative_pressure: Sequence[float], loading: Sequence[float]) -> dict[str, Any]:
    module, error = import_optional(MODULE)
    count = min(len(relative_pressure), len(loading))
    p_values = [float(value) for value in relative_pressure[:count]]
    q_values = [float(value) for value in loading[:count]]
    fallback_reason = None if module is not None else f"{PACKAGE} unavailable: {error}"
    result = {
        "ok": count > 0,
        "isotherm_point_count": count,
        "relative_pressure_range": [min(p_values), max(p_values)] if p_values else [],
        "loading_range": [min(q_values), max(q_values)] if q_values else [],
        "manual_check_required": True,
        "fallback_reason": fallback_reason,
        "metadata_provenance": metadata_provenance(
            adapter="bet_pygaps_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, MODULE),
            method="isotherm_candidate_summary_no_fit",
            fallback_reason=fallback_reason,
        ),
    }
    if module is not None and count:
        result["pygaps_import_ok"] = True
    return result


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([0.05, 0.1, 0.2], [1.0, 2.0, 3.0])
    return {"ok": result["ok"], "result": result}
