from __future__ import annotations

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for


def is_available() -> bool:
    return any(is_module_available(module) for module in ("hplc", "rainbow", "mocca2"))


def version_info() -> dict[str, object]:
    return {
        "hplc-py": {"available": is_module_available("hplc"), "version": version_for("hplc-py", "hplc"), "policy": "reference_only_gpl"},
        "rainbow-api": {"available": is_module_available("rainbow"), "version": version_for("rainbow-api", "rainbow"), "policy": "optional_lgpl_boundary"},
        "MOCCA2": {"available": is_module_available("mocca2"), "version": version_for("MOCCA2", "mocca2"), "policy": "optional_mit"},
    }


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["HPLC/LC exported data"],
        "methods": ["chromatography import probe", "candidate peak helper only"],
        "forbidden_claims": ["no product identification", "no conversion without calibration"],
    }


def process_or_analyze() -> dict[str, object]:
    imported = {}
    for module in ("hplc", "rainbow", "mocca2"):
        mod, error = import_optional(module)
        imported[module] = {"ok": mod is not None, "error": error}
    return {
        "ok": any(item["ok"] for item in imported.values()),
        "imports": imported,
        "manual_check_required": True,
        "metadata_provenance": metadata_provenance(
            adapter="hplc_adapter",
            package="hplc-py/rainbow-api/MOCCA2",
            module="hplc/rainbow/mocca2",
            version=str(version_info()),
            method="import_probe_no_product_assignment",
        ),
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "result": process_or_analyze()}
