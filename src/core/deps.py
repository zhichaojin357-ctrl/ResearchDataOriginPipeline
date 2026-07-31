from __future__ import annotations

import importlib
import importlib.metadata as package_metadata
import importlib.util
import json
import sys
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
    "pillow": "PIL",
}

OPTIONAL = {
    "impedance": "impedance",
    "ixdat": "ixdat",
    "pygaps": "pygaps",
    "nmrglue": "nmrglue",
    "tifffile": "tifffile",
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

DISTRIBUTION_NAMES = {
    "yaml": "PyYAML",
    "win32com": "pywin32",
    "pillow": "Pillow",
    "pygaps": "pyGAPS",
    "vgd-reader": "vgd-reader",
    "rainbow": "rainbow-api",
    "mocca2": "MOCCA2",
    "pymzml": "pymzML",
    "EPRpy": "EPRpy",
    "hplc-py": "hplc-py",
    "scikit-image": "scikit-image",
}


def dependency_audit(project_root: Path) -> tuple[int, dict]:
    core = {
        name: _availability(
            module,
            severity="fail",
            verify_import=True,
            distribution=DISTRIBUTION_NAMES.get(name, name),
        )
        for name, module in CORE.items()
    }
    optional = {
        name: _availability(
            module,
            severity="warning",
            distribution=DISTRIBUTION_NAMES.get(name, name),
        )
        for name, module in OPTIONAL.items()
    }
    reference_only = {
        name: _availability(
            module,
            severity="reference_only",
            distribution=DISTRIBUTION_NAMES.get(name, name),
        )
        for name, module in REFERENCE_ONLY.items()
    }
    blocked = {
        name: {
            "module": item["module"],
            "available": importlib.util.find_spec(item["module"]) is not None,
            "severity": "blocked",
            "status": "blocked",
            "reason": item["reason"],
            **_distribution_info(DISTRIBUTION_NAMES.get(name, name)),
        }
        for name, item in BLOCKED.items()
    }
    missing_core = [name for name, item in core.items() if not item["available"]]
    core_import_errors = [name for name, item in core.items() if item["status"] == "import_error"]
    missing_optional = [name for name, item in optional.items() if not item["available"]]
    missing_reference_only = [name for name, item in reference_only.items() if not item["available"]]
    metadata_errors = {
        section: {
            name: str(item["metadata_error"])
            for name, item in entries.items()
            if item.get("metadata_error")
        }
        for section, entries in (
            ("core", core),
            ("optional", optional),
            ("reference_only", reference_only),
            ("blocked", blocked),
        )
    }
    metadata_errors = {
        section: errors for section, errors in metadata_errors.items() if errors
    }
    result = {
        "runtime": {
            "executable": str(Path(sys.executable).resolve()),
            "python_version": sys.version.split()[0],
            "implementation": sys.implementation.name,
        },
        "core": core,
        "optional": optional,
        "reference_only": reference_only,
        "blocked": blocked,
        "summary": {
            "status": "fail" if missing_core else "pass",
            "missing_core": missing_core,
            "core_import_errors": core_import_errors,
            "missing_optional": missing_optional,
            "missing_reference_only": missing_reference_only,
            "blocked": sorted(blocked),
            "metadata_errors": metadata_errors,
        },
    }
    report_path(project_root, "dependency_audit.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Dependency Audit",
        "",
        "## Runtime",
        f"- Python executable: `{result['runtime']['executable']}`",
        f"- Python version: `{result['runtime']['python_version']}` ({result['runtime']['implementation']})",
        "",
        "## Core",
    ]
    for name, item in result["core"].items():
        if item["status"] == "import_error":
            lines.append(f"- `{name}`: import_error ({item['import_error']})")
        else:
            consequence = item["severity"] if not item["available"] else "ok"
            lines.append(
                f"- `{name}`: {'available' if item['available'] else 'missing'} ({consequence}); "
                f"version={item['version'] or 'unknown'}; license={item['license'] or 'unknown'}"
            )
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
    if metadata_errors:
        lines.extend(["", "## Package Metadata Warnings"])
        for section, errors in metadata_errors.items():
            for name, error in errors.items():
                lines.append(
                    f"- `{section}.{name}`: version/license metadata unavailable "
                    f"({error}); import availability was checked independently"
                )
    if missing_core:
        lines.extend(["", "## Failure", f"Missing core dependencies: {', '.join(missing_core)}"])
    report_path(project_root, "dependency_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (1 if missing_core else 0), result


def _availability(
    module: str,
    severity: str,
    *,
    verify_import: bool = False,
    distribution: str | None = None,
) -> dict:
    distribution_name = distribution or module
    distribution_info = _distribution_info(distribution_name)
    try:
        available = importlib.util.find_spec(module) is not None
    except Exception as exc:
        return {
            "module": module,
            "distribution": distribution_name,
            "available": False,
            "severity": severity,
            "status": "import_error",
            "import_error": f"{type(exc).__name__}: {exc}",
            **distribution_info,
        }
    if not available:
        return {
            "module": module,
            "distribution": distribution_name,
            "available": False,
            "severity": severity,
            "status": "missing",
            "import_error": None,
            **distribution_info,
        }
    if verify_import:
        try:
            importlib.import_module(module)
        except Exception as exc:
            return {
                "module": module,
                "distribution": distribution_name,
                "available": False,
                "severity": severity,
                "status": "import_error",
                "import_error": f"{type(exc).__name__}: {exc}",
                **distribution_info,
            }
    return {
        "module": module,
        "distribution": distribution_name,
        "available": True,
        "severity": severity,
        "status": "available",
        "import_error": None,
        **distribution_info,
    }


def _distribution_info(distribution: str) -> dict[str, str | None]:
    try:
        metadata = package_metadata.metadata(distribution)
        version = package_metadata.version(distribution)
    except package_metadata.PackageNotFoundError:
        return {"version": None, "license": "", "metadata_error": None}
    except Exception as exc:
        # A malformed, partially removed, or unreadable dist-info directory must
        # not abort the whole project validation. Module discovery/import below
        # remains the authoritative availability check.
        return {
            "version": None,
            "license": "",
            "metadata_error": f"{type(exc).__name__}: {exc}",
        }
    license_text = str(metadata.get("License-Expression") or metadata.get("License") or "").strip()
    if not license_text:
        classifiers = [
            classifier.removeprefix("License :: ").strip()
            for classifier in metadata.get_all("Classifier", [])
            if classifier.startswith("License :: ")
        ]
        license_text = "; ".join(classifiers)
    return {
        "version": version,
        "license": license_text[:240],
        "metadata_error": None,
    }
