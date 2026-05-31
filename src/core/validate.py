from __future__ import annotations

from pathlib import Path

from src.core.deps import dependency_audit
from src.core.project import (
    REQUIRED_OUTPUT_DIRS,
    claim_policy_path,
    ensure_output_structure,
    load_json_compatible_yaml,
    registry_path,
    report_path,
)
from src.origin.adapter import ORIGIN_DISABLE_ENV_VARS, check_origin_available


def validate(project_root: Path) -> int:
    ensure_output_structure(project_root)
    failures = []
    lines = ["# Validation Report", ""]

    dep_code, _ = dependency_audit(project_root)
    lines.append(f"- Dependency audit: {'pass' if dep_code == 0 else 'fail'}")
    if dep_code:
        failures.append("missing core dependencies")

    origin_ok, origin_message = check_origin_available()
    origin_disabled = any(f"{env_var}=1" in origin_message for env_var in ORIGIN_DISABLE_ENV_VARS)
    origin_status = "pass" if origin_ok else "skip" if origin_disabled else "fail"
    lines.append(f"- Origin callability: {origin_status} ({origin_message})")
    if not origin_ok and not origin_disabled:
        failures.append("Origin unavailable")

    missing_output_dirs = [
        name for name in REQUIRED_OUTPUT_DIRS if not (project_root / "output" / name).is_dir()
    ]
    lines.append(f"- Required output directories: {'pass' if not missing_output_dirs else 'fail'}")
    if missing_output_dirs:
        failures.append("missing output directories: " + ", ".join(missing_output_dirs))

    registry = load_json_compatible_yaml(registry_path(project_root))
    claim = load_json_compatible_yaml(claim_policy_path(project_root))
    required_config_files = [
        "default.yaml",
        "processor_registry.yaml",
        "claim_policy.yaml",
        "plot_style.yaml",
        "sample_registry.yaml",
        "manual_overrides.yaml",
    ]
    missing_config = [name for name in required_config_files if not (project_root / "config" / name).exists()]
    lines.append(f"- Required config files: {'pass' if not missing_config else 'fail'}")
    if missing_config:
        failures.append("missing required config files: " + ", ".join(missing_config))

    lines.append(f"- Processor registry entries: {len(registry['entries'])}")
    supported_entries = [entry for entry in registry["entries"] if entry["supported_in_phase_1"]]
    lines.append(f"- Phase 1 supported entries: {len(supported_entries)}")
    if len(supported_entries) != 14:
        failures.append("supported registry count is not 14")
    required_registry_fields = set(registry.get("required_fields", [])) | {
        "folder_name",
        "inferred_data_type",
        "supported_in_phase_1",
        "selected_processor",
        "special_handling",
    }
    incomplete_registry_entries = [
        entry.get("folder_name", "<unknown>")
        for entry in registry["entries"]
        if not required_registry_fields.issubset(entry)
    ]
    lines.append(f"- Processor registry required fields: {'pass' if not incomplete_registry_entries else 'fail'}")
    if incomplete_registry_entries:
        failures.append("registry entries missing required fields")

    kinetics = [entry for entry in registry["entries"] if entry["folder_name"] == "动力学"]
    if not kinetics or kinetics[0]["inferred_data_type"] != "reference_literature":
        failures.append("动力学 is not reference_literature")
    else:
        lines.append("- 动力学: reference_literature scan_only selected_processor none")

    for name in ["SEM", "TEM", "核磁", "质谱"]:
        entry = [item for item in registry["entries"] if item["folder_name"] == name]
        if not entry or entry[0]["special_handling"] != "scan_only" or entry[0]["supported_in_phase_1"]:
            failures.append(f"{name} is not deferred scan_only")
    lines.append("- SEM/TEM/核磁/质谱: deferred scan_only")

    forbidden = ["src/ppt", "templates/ppt", "ppt_layout.yaml", "slide_plan.json", "presentation.pptx"]
    found = [path for path in forbidden if (project_root / path).exists()]
    lines.append(f"- PPT forbidden paths: {'pass' if not found else 'fail'}")
    if found:
        failures.append("PPT forbidden paths exist")

    presentation_artifacts = [
        path
        for path in project_root.rglob("*")
        if path.is_file()
        and not _is_allowed_source_artifact(project_root, path)
        and (
            path.suffix.lower() in {".ppt", ".pptx"}
            or path.name == "slide_plan.json"
            or path.name == "ppt_layout.yaml"
            or path.name == "presentation.pptx"
        )
    ]
    lines.append(f"- Forbidden presentation artifacts: {'pass' if not presentation_artifacts else 'fail'}")
    if presentation_artifacts:
        rendered = ", ".join(str(path.relative_to(project_root)) for path in presentation_artifacts)
        lines.append(f"  - {rendered}")
        failures.append("forbidden presentation artifacts exist")

    kinetics_files = [
        path
        for path in (project_root / "src").rglob("*")
        if path.is_file()
        and any(
            component.lower() in {"kinetics", "kinetic", "kinetics_processor", "kinetic_processor"}
            or component.lower().startswith(("kinetics_", "kinetic_"))
            for component in path.relative_to(project_root).parts
        )
    ]
    lines.append(f"- Kinetics processor paths: {'pass' if not kinetics_files else 'fail'}")
    if kinetics_files:
        rendered = ", ".join(str(path.relative_to(project_root)) for path in kinetics_files)
        lines.append(f"  - {rendered}")
        failures.append("kinetics processor path exists")

    plot_style = project_root / "config" / "plot_style.yaml"
    text = plot_style.read_text(encoding="utf-8")
    tif_config_pass = 'format: "tif"' in text and "dpi: 600" in text
    lines.append(f"- TIF export config: {'pass' if tif_config_pass else 'fail'}")
    if not tif_config_pass:
        failures.append("TIF export config invalid")
    origin_contract_checks = {
        "Graph4 reference page": 'default_graph_page: "Graph4"' in text,
        "Origin.Application automation": 'automation_entrypoint: "Origin.Application"' in text,
        "avoid Origin.ApplicationSI": 'avoid_entrypoint: "Origin.ApplicationSI"' in text,
        "PNG preview inspection": "Export PNG preview and visually inspect" in text,
        "explicit bold legend rows": "explicit legend rows" in text,
        "line width 3": "line_width: 3" in text and "axis_line_width: 3" in text,
    }
    for label, passed in origin_contract_checks.items():
        lines.append(f"- Origin contract {label}: {'pass' if passed else 'fail'}")
    failed_origin_contracts = [label for label, passed in origin_contract_checks.items() if not passed]
    if failed_origin_contracts:
        failures.append("Origin plotting contract invalid: " + ", ".join(failed_origin_contracts))
    lines.append("- max_threads = 5")
    lines.append("- max_depth = 1")
    lines.append(f"- Claim policy forbidden claims: {len(claim.get('forbidden_claims', []))}")

    if failures:
        lines.extend(["", "## Failures", *[f"- {failure}" for failure in failures]])
    report_path(project_root, "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failures else 0


def _is_allowed_source_artifact(project_root: Path, path: Path) -> bool:
    allowed_roots = [
        project_root / "workspace_data",
        project_root / "input" / "raw_data",
    ]
    resolved = path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
