from __future__ import annotations

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "pyimpspec"
MODULE = "pyimpspec"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["EIS"],
        "methods": ["import smoke", "reference-only optional EIS expert routines"],
        "outputs": ["availability", "provenance"],
        "forbidden_claims": ["no automatic equivalent-circuit conclusion"],
        "core_flow_policy": "reference_only_not_default",
    }


def process_or_analyze() -> dict[str, object]:
    module, error = import_optional(MODULE)
    return {
        "ok": module is not None,
        "fallback_reason": None if module is not None else f"{PACKAGE} unavailable: {error}",
        "metadata_provenance": metadata_provenance(
            adapter="eis_pyimpspec_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, MODULE),
            method="reference_only_import_smoke",
            fallback_reason=None if module is not None else error,
        ),
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "result": process_or_analyze()}
