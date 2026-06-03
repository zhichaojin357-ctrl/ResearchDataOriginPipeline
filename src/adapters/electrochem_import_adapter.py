from __future__ import annotations

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for


def is_available() -> bool:
    return any(is_module_available(module) for module in ("ixdat", "galvani", "eclabfiles"))


def version_info() -> dict[str, object]:
    return {
        "ixdat": {"available": is_module_available("ixdat"), "version": version_for("ixdat", "ixdat")},
        "galvani": {"available": is_module_available("galvani"), "version": version_for("galvani", "galvani"), "policy": "reference_only_gpl"},
        "eclabfiles": {"available": is_module_available("eclabfiles"), "version": version_for("eclabfiles", "eclabfiles"), "policy": "reference_only_license_unknown"},
    }


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["photocurrent", "photocurrent_response", "EIS"],
        "methods": ["electrochemistry import probe only"],
        "forbidden_claims": ["no carrier-separation conclusion", "no mechanism conclusion"],
        "core_flow_policy": "ixdat optional; galvani/eclabfiles reference only",
    }


def process_or_analyze() -> dict[str, object]:
    imported = {}
    for module in ("ixdat", "galvani", "eclabfiles"):
        mod, error = import_optional(module)
        imported[module] = {"ok": mod is not None, "error": error}
    return {
        "ok": any(item["ok"] for item in imported.values()),
        "imports": imported,
        "metadata_provenance": metadata_provenance(
            adapter="electrochem_import_adapter",
            package="ixdat/galvani/eclabfiles",
            module="ixdat/galvani/eclabfiles",
            version=str(version_info()),
            method="import_probe_only",
        ),
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "result": process_or_analyze()}
