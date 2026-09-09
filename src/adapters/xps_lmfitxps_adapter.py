from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "lmfitxps"
MODULE = "lmfitxps"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["XPS"],
        "methods": ["import smoke", "existing component curve summarization"],
        "outputs": ["component_count", "residual_excluded"],
        "forbidden_claims": ["no valence assignment", "no electron-transfer direction", "no heterojunction mechanism"],
        "default_fitting": "disabled",
    }


def process_or_analyze(curves: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    return summarize_curve_labels(curves)


def summarize_curve_labels(curve_labels: Iterable[str]) -> dict[str, Any]:
    """Summarize already identified curve labels; no fit needs signal arrays."""
    module, error = import_optional(MODULE)
    labels = [str(label) for label in curve_labels]
    components = [label for label in labels if not _is_non_component_curve(label)]
    residuals = [label for label in labels if "residual" in label.casefold()]
    fallback_reason = None if module is not None else f"{PACKAGE} unavailable: {error}"
    return {
        "ok": bool(labels),
        "component_count": len(components),
        "component_labels": components,
        "residual_labels_excluded": residuals,
        "manual_check_required": True,
        "fallback_reason": fallback_reason,
        "metadata_provenance": metadata_provenance(
            adapter="xps_lmfitxps_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, MODULE),
            method="existing_curve_summary_no_fit",
            fallback_reason=fallback_reason,
        ),
    }


def smoke_test() -> dict[str, object]:
    result = process_or_analyze({"raw_intensity": [1, 2], "Backgnd.": [0, 0], "Envelope": [1, 1], "Residuals": [0.1, -0.1], "C1s A": [0.5, 0.7]})
    return {"ok": result["ok"] and result["component_count"] == 1 and result["residual_labels_excluded"], "result": result}


def _is_non_component_curve(label: str) -> bool:
    normalized = label.casefold().replace(" ", "").replace("_", "")
    return normalized in {
        "raw",
        "rawintensity",
        "counts",
        "intensity",
        "background",
        "backgnd.",
        "backgnd",
        "envelope",
        "fit",
        "residuals",
        "residual",
    }
