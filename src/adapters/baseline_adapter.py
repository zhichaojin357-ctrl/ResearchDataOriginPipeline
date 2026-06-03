from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "pybaselines"
MODULE = "pybaselines"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["Raman", "PL", "FTIR", "UV-vis DRS", "EPR", "XPS"],
        "methods": ["asls"],
        "outputs": ["raw_signal", "baseline", "corrected_signal", "metadata_provenance"],
        "forbidden_claims": ["no peak assignment", "no chemical-bond assignment", "no radical assignment"],
    }


def process_or_analyze(
    x_values: Sequence[float],
    y_values: Sequence[float],
    *,
    method: str = "asls",
    lam: float = 1e5,
    p: float = 0.01,
) -> dict[str, Any]:
    module, error = import_optional(MODULE)
    parameters = {"method": method, "lam": lam, "p": p}
    if module is None:
        return {
            "ok": False,
            "fallback_reason": f"{PACKAGE} unavailable: {error}",
            "raw_signal": list(y_values),
            "baseline": [],
            "corrected_signal": [],
            "metadata_provenance": metadata_provenance(
                adapter="baseline_adapter",
                package=PACKAGE,
                module=MODULE,
                version=None,
                method=method,
                parameters=parameters,
                fallback_reason=f"{PACKAGE} unavailable",
            ),
        }
    try:
        baseline_cls = getattr(module, "Baseline")
        baseline, _params = baseline_cls(list(x_values)).asls(list(y_values), lam=lam, p=p)
        baseline_values = [float(value) for value in baseline]
        corrected = [float(y - base) for y, base in zip(y_values, baseline_values)]
        return {
            "ok": True,
            "fallback_reason": None,
            "raw_signal": [float(value) for value in y_values],
            "baseline": baseline_values,
            "corrected_signal": corrected,
            "metadata_provenance": metadata_provenance(
                adapter="baseline_adapter",
                package=PACKAGE,
                module=MODULE,
                version=version_for(PACKAGE, MODULE),
                method=method,
                parameters=parameters,
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "fallback_reason": f"{PACKAGE} baseline failed: {exc}",
            "raw_signal": list(y_values),
            "baseline": [],
            "corrected_signal": [],
            "metadata_provenance": metadata_provenance(
                adapter="baseline_adapter",
                package=PACKAGE,
                module=MODULE,
                version=version_for(PACKAGE, MODULE),
                method=method,
                parameters=parameters,
                fallback_reason=str(exc),
            ),
        }


def smoke_test() -> dict[str, object]:
    x_values = [float(index) for index in range(20)]
    y_values = [0.1 * index + (1.0 if index in {8, 9, 10} else 0.0) for index in range(20)]
    result = process_or_analyze(x_values, y_values)
    return {"ok": bool(result["ok"]) and len(result.get("baseline", [])) == len(y_values), "result": result}
