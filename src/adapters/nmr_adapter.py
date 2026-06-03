from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "nmrglue"
MODULE = "nmrglue"


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["NMR"],
        "methods": ["Bruker processed data import probe", "peaklist XML index"],
        "outputs": ["peaklist_entries", "provenance"],
        "forbidden_claims": ["no structure elucidation", "no compound identification"],
        "core_flow_policy": "scan_only",
    }


def process_or_analyze(path: Path) -> dict[str, object]:
    module, error = import_optional(MODULE)
    peaks = []
    if path.name.casefold() == "peaklist.xml" and path.exists():
        try:
            root = ET.parse(path).getroot()
            for elem in root.iter():
                attrs = {key: value for key, value in elem.attrib.items() if key}
                if attrs:
                    peaks.append(attrs)
        except Exception as exc:
            error = str(exc)
    return {
        "ok": module is not None or bool(peaks),
        "peaklist_entries": len(peaks),
        "manual_check_required": True,
        "fallback_reason": None if module is not None else f"{PACKAGE} unavailable: {error}",
        "metadata_provenance": metadata_provenance(
            adapter="nmr_adapter",
            package=PACKAGE,
            module=MODULE,
            version=version_for(PACKAGE, MODULE),
            method="scan_only_peaklist_or_import_probe",
            fallback_reason=None if module is not None else error,
        ),
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "version_info": version_info()}
