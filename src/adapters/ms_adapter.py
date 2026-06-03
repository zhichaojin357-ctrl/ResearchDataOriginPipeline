from __future__ import annotations

from pathlib import Path

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for


def is_available() -> bool:
    return any(is_module_available(module) for module in ("pymzml", "pyteomics"))


def version_info() -> dict[str, object]:
    return {
        "pymzML": {"available": is_module_available("pymzml"), "version": version_for("pymzML", "pymzml")},
        "pyteomics": {"available": is_module_available("pyteomics"), "version": version_for("pyteomics", "pyteomics")},
        "matchms": {"available": is_module_available("matchms"), "version": version_for("matchms", "matchms"), "policy": "blocked_core_dependency_change"},
    }


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["MS"],
        "methods": ["standard-format import probe for mzML/mzXML/MGF/msp"],
        "outputs": ["format_family", "import_probe"],
        "forbidden_claims": ["no product identification", "no structure assignment"],
        "core_flow_policy": "scan_only",
    }


def process_or_analyze(path: Path) -> dict[str, object]:
    suffix = path.suffix.casefold()
    family = {
        ".mzml": "mzML",
        ".mzxml": "mzXML",
        ".mgf": "MGF",
        ".msp": "MSP",
    }.get(suffix, "unsupported_or_vendor_specific")
    imports = {}
    for module in ("pymzml", "pyteomics"):
        mod, error = import_optional(module)
        imports[module] = {"ok": mod is not None, "error": error}
    return {
        "ok": family != "unsupported_or_vendor_specific" and any(item["ok"] for item in imports.values()),
        "format_family": family,
        "imports": imports,
        "manual_check_required": True,
        "metadata_provenance": metadata_provenance(
            adapter="ms_adapter",
            package="pymzML/pyteomics",
            module="pymzml/pyteomics",
            version=str(version_info()),
            method="standard_format_probe_no_product_assignment",
        ),
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "version_info": version_info()}
