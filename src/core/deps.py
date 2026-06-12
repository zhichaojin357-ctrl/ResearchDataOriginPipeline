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
    "pygaps": "pygaps",
    "nmrglue": "nmrglue",
    "tifffile": "tifffile",
    "pillow": "PIL",
    "lmfitxps": "lmfitxps",
    "vgd-reader": "vgd_reader",
    "ramanspy": "ramanspy",
    "rampy": "rampy",
    "spectrochempy": "spectrochempy",
    "rainbow": "rainbow",
    "mocca2": "mocca2",
    "pymzml": "pymzml",
    "pyteomics": "pyteomics",
    "cwepr": "cwepr",
    "EPRpy": "eprpy",
}

REFERENCE_ONLY = {
    "pyimpspec": "pyimpspec",
    "galvani": "galvani",
    "eclabfiles": "eclabfiles",
    "hplc-py": "hplc",
    "scikit-image": "skimage",
    "hyperspy": "hyperspy",
    "exspy": "exspy",
    "pyopenms": "pyopenms",
}

BLOCKED = {
    "matchms": {
        "module": "matchms",
        "reason": "blocked because the dry-run would change core numpy/scipy versions",
    },
}


def dependency_audit(project_root: Path) -> tuple[int, dict]:
    core = {name: _availability(module, severity="fail") for name, module in CORE.items()}
    optional = {name: _availability(module, severity="warning") for name, module in OPTIONAL.items()}
    reference_only = {name: _availability(module, severity="reference_only") for name, module in REFERENCE_ONLY.items()}
    blocked = {
        name: {
            "module": item["module"],
            "available": importlib.util.find_spec(item["module"]) is not None,
            "severity": "blocked",
            "status": "blocked",
            "reason": item["reason"],
        }
        for name, item in BLOCKED.items()
    }
    missing_core = [name for name, item in core.items() if not item["available"]]
    missing_optional = [name for name, item in optional.items() if not item["available"]]
    missing_reference_only = [name for name, item in reference_only.items() if not item["available"]]
    result = {
        "core": core,
        "optional": optional,
        "reference_only": reference_only,
        "blocked": blocked,
        "summary": {
            "status": "fail" if missing_core else "pass",
            "missing_core": missing_core,
            "missing_optional": missing_optional,
            "missing_reference_only": missing_reference_only,
            "blocked": sorted(blocked),
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
    lines.extend(["", "## Reference-Only"])
    for name, item in result["reference_only"].items():
        consequence = item["severity"] if not item["available"] else "reference-only available"
        lines.append(f"- `{name}`: {'available' if item['available'] else 'missing reference-only'} ({consequence})")
    lines.extend(["", "## Blocked"])
    for name, item in result["blocked"].items():
        lines.append(f"- `{name}`: blocked ({item['reason']})")
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
