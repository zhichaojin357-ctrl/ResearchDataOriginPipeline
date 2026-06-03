from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.core.project import report_path


CORE = {
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy",
    "openpyxl": "openpyxl",
    "yaml": "yaml",
    "pybaselines": "pybaselines",
    "originpro": "originpro",
    "win32com": "win32com",
}

OPTIONAL = {
    "impedance": "impedance",
    "ixdat": "ixdat",
    "galvani": "galvani",
    "eclabfiles": "eclabfiles",
    "pygaps": "pygaps",
    "nmrglue": "nmrglue",
    "tifffile": "tifffile",
    "pillow": "PIL",
    "scikit-image": "skimage",
    "lmfitxps": "lmfitxps",
    "vgd-reader": "vgd_reader",
    "ramanspy": "ramanspy",
    "rampy": "rampy",
    "spectrochempy": "spectrochempy",
    "hplc": "hplc",
    "rainbow": "rainbow",
    "mocca2": "mocca2",
    "pymzml": "pymzml",
    "pyteomics": "pyteomics",
    "cwepr": "cwepr",
    "EPRpy": "eprpy",
}


def dependency_audit(project_root: Path) -> tuple[int, dict]:
    core = {name: _availability(module, severity="fail") for name, module in CORE.items()}
    optional = {name: _availability(module, severity="warning") for name, module in OPTIONAL.items()}
    missing_core = [name for name, item in core.items() if not item["available"]]
    missing_optional = [name for name, item in optional.items() if not item["available"]]
    result = {
        "core": core,
        "optional": optional,
        "summary": {
            "status": "fail" if missing_core else "pass",
            "missing_core": missing_core,
            "missing_optional": missing_optional,
        },
    }
    report_path(project_root, "dependency_audit.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    lines = ["# Dependency Audit", "", "## Core"]
    for name, item in result["core"].items():
        consequence = item["severity"] if not item["available"] else "ok"
        lines.append(f"- `{name}`: {'available' if item['available'] else 'missing'} ({consequence})")
    lines.extend(["", "## Optional"])
    for name, item in result["optional"].items():
        consequence = item["severity"] if not item["available"] else "ok"
        lines.append(f"- `{name}`: {'available' if item['available'] else 'missing optional'} ({consequence})")
    if missing_core:
        lines.extend(["", "## Failure", f"Missing core dependencies: {', '.join(missing_core)}"])
    report_path(project_root, "dependency_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (1 if missing_core else 0), result


def _availability(module: str, severity: str) -> dict:
    available = importlib.util.find_spec(module) is not None
    return {
        "module": module,
        "available": available,
        "severity": severity,
        "status": "available" if available else "missing",
    }
