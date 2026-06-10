from __future__ import annotations

from collections.abc import Sequence
from math import isfinite
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
        "outputs": ["isotherm_point_count", "relative_pressure_range", "loading_range"],
        "forbidden_claims": ["no automatic BET model validation", "no pore structure conclusion"],
    }


def process_or_analyze(relative_pressure: Sequence[float], loading: Sequence[float]) -> dict[str, Any]:
    module, error = import_optional(MODULE)
    count = min(len(relative_pressure), len(loading))
    pairs = []
    for index in range(count):
        try:
            pressure = float(relative_pressure[index])
            amount = float(loading[index])
        except (TypeError, ValueError):
            continue
        if isfinite(pressure) and isfinite(amount):
            pairs.append((pressure, amount))
    p_values = [item[0] for item in pairs]
    q_values = [item[1] for item in pairs]
    fallback_reason = None if module is not None else f"{PACKAGE} unavailable: {error}"
    pointisotherm_constructed = False
    pointisotherm_error = None
    pointisotherm_points = 0
    if module is not None and pairs:
        try:
            isotherm = module.PointIsotherm(
                pressure=p_values,
                loading=q_values,
                material="candidate",
                adsorbate="N2",
                temperature=77,
                pressure_mode="relative",
                pressure_unit="bar",
                loading_basis="molar",
                loading_unit="mmol",
                material_basis="mass",
                material_unit="g",
                temperature_unit="K",
                branch="ads",
            )
            pointisotherm_points = len(isotherm.data())
            pointisotherm_constructed = pointisotherm_points == len(pairs)
        except Exception as exc:
            pointisotherm_error = str(exc)
            fallback_reason = f"{PACKAGE} PointIsotherm candidate construction failed: {exc}"
    result = {
        "ok": bool(pairs),
        "isotherm_point_count": len(pairs),
        "relative_pressure_range": [min(p_values), max(p_values)] if p_values else [],
        "loading_range": [min(q_values), max(q_values)] if q_values else [],
        "pygaps_pointisotherm_constructed": pointisotherm_constructed,
        "pygaps_pointisotherm_points": pointisotherm_points,
        "pygaps_pointisotherm_error": pointisotherm_error,
        "manual_check_required": True,
        "fallback_reason": fallback_reason,
        "metadata_provenance": metadata_provenance(
            adapter="bet_pygaps_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, MODULE),
            method="pygaps_pointisotherm_candidate_no_bet_fit",
            parameters={
                "pressure_mode": "relative",
                "adsorbate": "N2",
                "temperature_K": 77,
                "unit_assumption_policy": "explicit units only for pyGAPS object construction; no BET fit or pore conclusion",
            },
            fallback_reason=fallback_reason,
        ),
    }
    if module is not None and pairs:
        result["pygaps_import_ok"] = True
    return result


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([0.05, 0.1, 0.2], [1.0, 2.0, 3.0])
    return {"ok": result["ok"], "result": result}
