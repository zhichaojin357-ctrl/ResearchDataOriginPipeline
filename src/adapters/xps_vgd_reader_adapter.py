from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "vgd-reader"
MODULE = "vgd_reader"

_vgd_reader_module, _vgd_reader_error = import_optional(MODULE)
read_vgd = getattr(_vgd_reader_module, "read_vgd", None)


@dataclass(frozen=True)
class VgdRowsResult:
    rows: list[dict[str, str]]
    warnings: list[str]
    metadata_provenance: dict[str, Any]


def is_available() -> bool:
    return is_module_available(MODULE)


def version_info() -> dict[str, object]:
    return {"package": PACKAGE, "module": MODULE, "available": is_available(), "version": version_for(PACKAGE, MODULE)}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["XPS"],
        "methods": ["Thermo VGD reader", "spectrum table extraction"],
        "outputs": ["binding_energy", "intensity", "core_level"],
        "forbidden_claims": ["no valence assignment", "no peak identity assignment", "no heterojunction mechanism"],
    }


def read_vgd_rows(path: str | Path) -> VgdRowsResult:
    fallback_reason = None
    if read_vgd is None:
        fallback_reason = f"{PACKAGE} unavailable: {_vgd_reader_error}"
        return VgdRowsResult(
            rows=[],
            warnings=[fallback_reason],
            metadata_provenance=_provenance(fallback_reason=fallback_reason),
        )

    vgd = read_vgd(str(path))
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    spectra = list(getattr(vgd, "spectra", []) or [])
    for spectrum in spectra:
        core_level = str(getattr(spectrum, "core_level", "") or "")
        binding_energy = _to_list(getattr(spectrum, "binding_energy", []))
        corrected = _to_list(getattr(spectrum, "corrected_intensity", []))
        raw = _to_list(getattr(spectrum, "intensity", []))
        intensity = corrected if corrected else raw
        point_count = min(len(binding_energy), len(intensity))
        for index in range(point_count):
            row = {
                "binding energy": str(float(binding_energy[index])),
                "intensity": str(float(intensity[index])),
                "core_level": core_level,
            }
            if raw and index < len(raw):
                row["raw_intensity_optional"] = str(float(raw[index]))
            rows.append(row)
        pass_energy = getattr(spectrum, "pass_energy", None)
        if pass_energy is not None:
            warnings.append(f"VGD spectrum pass energy requires manual review: {pass_energy}")

    return VgdRowsResult(
        rows=rows,
        warnings=warnings,
        metadata_provenance=_provenance(parameters={"spectrum_count": len(spectra), "point_count": len(rows)}),
    )


def process_or_analyze(path: str | Path) -> dict[str, object]:
    result = read_vgd_rows(path)
    return {
        "ok": bool(result.rows),
        "row_count": len(result.rows),
        "warnings": result.warnings,
        "manual_check_required": True,
        "metadata_provenance": result.metadata_provenance,
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "result": {"available": is_available(), "version_info": version_info()}}


def _provenance(
    *,
    parameters: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    return metadata_provenance(
        adapter="xps_vgd_reader_adapter",
        package=PACKAGE,
        module=MODULE,
        version=version_for(PACKAGE, MODULE),
        method="vgd_spectrum_table_extraction_no_peak_assignment",
        parameters=parameters,
        fallback_reason=fallback_reason,
    )


def _to_list(values: object) -> list[object]:
    if values is None:
        return []
    try:
        return list(values)  # type: ignore[arg-type]
    except TypeError:
        return []
