from __future__ import annotations

import csv
import json
import os
import stat
from pathlib import Path
from datetime import datetime
from typing import Iterator

from src.core.file_utils import is_under_or_equal as _is_under_or_equal
from src.core.output_sanitizer import render_output_path
from src.core.origin_governance import REQUIRED_JOURNAL_INDEX_COLUMNS
from src.core.deps import dependency_audit
from src.core.project import (
    REQUIRED_OUTPUT_DIRS,
    claim_policy_path,
    ensure_output_structure,
    load_json_compatible_yaml,
    read_project_yaml,
    registry_path,
    report_path,
)
from src.core.runtime_paths import resolve_workspace_root
from src.core.runtime_paths import resolve_output_root
from src.origin.adapter import ORIGIN_DISABLE_ENV_VARS, check_origin_available
from src.origin.plot_policy import GRAPH4_FIXED_STYLE, all_plot_policies
from src.origin.style_registry import validate_origin_style_asset_integrity


def validate(project_root: Path, *, scope: str = "full") -> int:
    if scope not in {"full", "runtime"}:
        raise ValueError(f"unknown validation scope: {scope}")
    output_root = resolve_output_root(project_root)
    ensure_output_structure(project_root, output_root=output_root)
    checks: list[dict] = []
    notes: list[str] = []

    def record(name: str, label: str, passed: bool, detail: str = "", *, skip: bool = False) -> None:
        checks.append({"name": name, "label": label, "status": "skip" if skip else "pass" if passed else "fail", "detail": detail})

    dep_code, _ = dependency_audit(project_root)
    record("dependencies", "Dependency audit", dep_code == 0, "missing core dependencies" if dep_code else "")
    origin_ok, origin_message = check_origin_available()
    origin_disabled = any(f"{env_var}=1" in origin_message for env_var in ORIGIN_DISABLE_ENV_VARS)
    record("origin_callability", "Origin callability", origin_ok, origin_message, skip=not origin_ok and origin_disabled)

    missing_output_dirs = [name for name in REQUIRED_OUTPUT_DIRS if not (output_root / name).is_dir()]
    record("output_directories", "Required output directories", not missing_output_dirs, ", ".join(missing_output_dirs))
    registry = load_json_compatible_yaml(registry_path(project_root))
    claim = load_json_compatible_yaml(claim_policy_path(project_root))
    required_config_files = ["default.yaml", "processor_registry.yaml", "claim_policy.yaml", "plot_style.yaml", "sample_registry.yaml", "manual_overrides.yaml"]
    missing_config = [name for name in required_config_files if not (project_root / "config" / name).exists()]
    record("config_files", "Required config files", not missing_config, ", ".join(missing_config))
    notes.append(f"Processor registry entries: {len(registry['entries'])}")
    supported_entries = [entry for entry in registry["entries"] if entry["supported_in_pipeline"]]
    notes.append(f"Pipeline-supported entries: {len(supported_entries)}")
    registry_summary_failures = _processor_registry_summary_failures(registry)
    record("registry_supported_summary", "Processor registry supported summary", not registry_summary_failures, ("processor registry supported summary drift; " + "; ".join(registry_summary_failures)) if registry_summary_failures else "")
    required_registry_fields = set(registry.get("required_fields", [])) | {
        "folder_name", "inferred_data_type", "supported_in_pipeline", "selected_processor", "special_handling",
    }
    incomplete_registry_entries = [entry.get("folder_name", "<unknown>") for entry in registry["entries"] if not required_registry_fields.issubset(entry)]
    record("registry_required_fields", "Processor registry required fields", not incomplete_registry_entries, ", ".join(incomplete_registry_entries))

    deferred_requirements = {
        "SEM_image_data": {"folder_name": "SEM"},
        "TEM_image_data": {"folder_name": "TEM"},
        "NMR": {"folder_name": "核磁"},
        "MS": {"folder_name": "质谱"},
        "reference_literature": {"folder_name": "动力学"},
    }
    deferred_failures = []
    deferred_seen = []
    for inferred_type, expected in deferred_requirements.items():
        matches = [entry for entry in registry["entries"] if entry.get("inferred_data_type") == inferred_type and entry.get("folder_name") == expected["folder_name"]]
        if not matches:
            deferred_failures.append(f"{expected['folder_name']} missing")
            continue
        entry = matches[0]
        deferred_seen.append(f"{entry.get('folder_name')}={inferred_type}")
        if entry.get("supported_in_pipeline") is not False:
            deferred_failures.append(f"{entry.get('folder_name')} supported_in_pipeline must be false")
        if entry.get("special_handling") != "scan_only":
            deferred_failures.append(f"{entry.get('folder_name')} special_handling must be scan_only")
        if entry.get("selected_processor") != "none":
            deferred_failures.append(f"{entry.get('folder_name')} {inferred_type} selected_processor must be none")
    record("deferred_registry_semantics", "Deferred/reference registry semantics", not deferred_failures, "; ".join(deferred_failures or deferred_seen))

    forbidden = ["src/ppt", "templates/ppt"]
    if scope == "full":
        forbidden.extend(["ppt_layout.yaml", "slide_plan.json", "presentation.pptx"])
    found = [path for path in forbidden if (project_root / path).exists()]
    record("ppt_forbidden_paths", "PPT forbidden paths", not found, ", ".join(found))
    if scope == "full":
        presentation_artifacts = []
        scan_roots = [project_root]
        allowed_source_roots = _allowed_source_artifact_roots(project_root)
        if not _is_under_or_equal(output_root.resolve(), project_root.resolve()):
            scan_roots.append(output_root)
        for scan_root in scan_roots:
            if scan_root.exists():
                presentation_artifacts.extend(
                    path for path in _iter_files_without_link_descent(scan_root)
                    if not _is_allowed_source_artifact(path, allowed_source_roots)
                    and (path.suffix.lower() in {".ppt", ".pptx"} or path.name in {"slide_plan.json", "ppt_layout.yaml"})
                )
        rendered = ", ".join(render_output_path(path, project_root=project_root, output_root=output_root) or str(path) for path in presentation_artifacts)
        record("presentation_artifacts", "Forbidden presentation artifacts", not presentation_artifacts, rendered)
    else:
        record("presentation_artifacts", "Forbidden presentation artifacts", False, "outside runtime scope: user and historical output files", skip=True)

    kinetics_files = [
        path for path in (project_root / "src").rglob("*") if path.is_file()
        and any(component.lower() in {"kinetics", "kinetic", "kinetics_processor", "kinetic_processor"} or component.lower().startswith(("kinetics_", "kinetic_")) for component in path.relative_to(project_root).parts)
    ]
    record("kinetics_processor_paths", "Kinetics processor paths", not kinetics_files, ", ".join(str(path.relative_to(project_root)) for path in kinetics_files))

    style = read_project_yaml(project_root / "config" / "plot_style.yaml")
    export = style.get("export", {})
    template = style.get("origin_template", {})
    record("tif_export_config", "TIF export config", export.get("format") == "tif" and export.get("dpi") == 600, "format=tif; dpi=600 required")
    origin_contract_checks = {
        "graph4_reference_page": ("Graph4 reference page", template.get("default_graph_page") == "Graph4"),
        "origin_application": ("Origin.Application automation", template.get("automation_entrypoint") == "Origin.Application"),
        "avoid_application_si": ("avoid Origin.ApplicationSI", template.get("avoid_entrypoint") == "Origin.ApplicationSI"),
        "legend_no_frame_fill": ("legend has no frame or fill", all(style.get(key) == 0 for key in ("legend_border", "legend_frame", "legend_fill"))),
        "chemical_subscripts": ("chemical formula subscripts", style.get("chemical_formula_subscripts") is True),
        "line_width": ("line width 3", style.get("line_width") == 3 and style.get("axis_line_width") == 3),
        "axis_title_size": ("axis title size 36", style.get("axis_title_size") == 36),
        "x_tick_size": ("X tick label size 28", style.get("x_tick_label_size") == 28),
        "y_tick_size": ("Y tick label size 36", style.get("y_tick_label_size") == 36),
        "legend_font_size": ("legend font size 26", style.get("legend_font_size") == 26),
        "annotation_font_size": ("annotation font size 26", style.get("annotation_font_size") == 26),
        "bold_font": ("bold font enabled", style.get("font_bold") is True),
    }
    for name, (label, passed) in origin_contract_checks.items():
        record(f"origin_contract_{name}", f"Origin contract {label}", passed)
    fixed_keys = ("line_width", "axis_line_width", "axis_title_size", "x_tick_label_size", "y_tick_label_size", "legend_font_size", "annotation_font_size")
    fixed_style_ok = all(style.get(key) == getattr(GRAPH4_FIXED_STYLE, key) for key in fixed_keys) and style.get("font_bold") is True
    record("graph4_fixed_style", "Origin Graph4 fixed style values", fixed_style_ok)
    for name, label in (("png_inspection", "PNG preview inspection"), ("explicit_legend_rows", "explicit bold legend rows")):
        record(name, f"Origin contract {label}", False, "verified on generated Origin products; instruction wording is not visual evidence", skip=True)

    style_integrity = validate_origin_style_asset_integrity(project_root)
    style_failures = [str(value) for value in style_integrity.get("failures", [])]
    detail = f"schema v{style_integrity['schema_version']}, assets={style_integrity['asset_count']}"
    if style_failures:
        detail += "; " + "; ".join(style_failures)
    record("origin_style_asset_integrity", "Origin style asset integrity", style_integrity["ok"], detail)
    notes.extend(f"Origin style asset warning: {warning}" for warning in style_integrity.get("warnings", []))

    origin_governance_files = {
        "snapshot_md": output_root / "reports" / "origin_plotting_skill_snapshot.md",
        "snapshot_json": output_root / "reports" / "origin_plotting_skill_snapshot.json",
        "journal_index": output_root / "reports" / "journal_ready_index.csv",
    }
    if scope == "runtime":
        record("origin_governance_files", "Origin governance plotting governance files", False, "outside runtime scope: historical generated artifacts", skip=True)
    elif any(path.exists() for name, path in origin_governance_files.items() if name != "snapshot_md"):
        missing_origin_governance = [name for name, path in origin_governance_files.items() if not path.exists()]
        record("origin_governance_files", "Origin governance plotting governance files", not missing_origin_governance, ", ".join(missing_origin_governance))
        if not missing_origin_governance:
            snapshot = json.loads(origin_governance_files["snapshot_json"].read_text(encoding="utf-8"))
            skill_hash = snapshot.get("skill_sha256")
            snapshot_text = origin_governance_files["snapshot_md"].read_text(encoding="utf-8")
            hash_ok = bool(skill_hash) and skill_hash in snapshot_text
            record("origin_governance_snapshot_hash", "Origin governance plotting skill SHA256 recorded", hash_ok)
            with origin_governance_files["journal_index"].open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                headers = set(reader.fieldnames or [])
                rows = list(reader)
            missing_columns = sorted(REQUIRED_JOURNAL_INDEX_COLUMNS - headers)
            record("origin_governance_index_columns", "Origin governance journal-ready index columns", not missing_columns, ", ".join(missing_columns))
            if rows:
                record("origin_governance_index_hash", "Origin governance journal-ready index skill hash", all(row.get("plotting_skill_sha256") == skill_hash for row in rows))
                policy_field_failures = _origin_governance_journal_policy_field_failures(rows)
                record("origin_governance_policy_values", "Origin governance journal-ready index policy values", not policy_field_failures, "; ".join(policy_field_failures))
    else:
        record("origin_governance_files", "Origin governance plotting governance files", False, "no generated output artifacts", skip=True)
    notes.extend(["max_threads = 5", "max_depth = 1", f"Claim policy forbidden claims: {len(claim.get('forbidden_claims', []))}"])
    failures = [check for check in checks if check["status"] == "fail"]
    report = {
        "report": "validation", "schema_version": 1, "scope": scope,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {"checks": len(checks), "failures": len(failures), "skipped": sum(check["status"] == "skip" for check in checks)},
        "checks": checks, "notes": notes, "inputs": _validation_input_fingerprints(project_root),
        "origin_visual_verified": False,
    }
    report_path(project_root, "validation_report.json", output_root=output_root).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path(project_root, "validation_report.md", output_root=output_root).write_text(_validation_markdown(report), encoding="utf-8")
    return 1 if failures else 0


def _validation_markdown(report: dict) -> str:
    lines = ["# Validation Report", "", f"- Scope: {report['scope']}", "- Origin visual results: not verified", ""]
    for check in report["checks"]:
        status = "not checked" if check["status"] == "skip" else check["status"]
        suffix = f" ({check['detail']})" if check["status"] == "skip" and check["detail"] else ""
        lines.append(f"- {check['label']}: {status}{suffix}")
        if check["detail"] and check["status"] != "skip":
            lines.append(f"  - {check['detail']}")
    lines.extend(f"- {note}" for note in report["notes"])
    failures = [check for check in report["checks"] if check["status"] == "fail"]
    if failures:
        lines.extend(["", "## Failures", *[f"- {check['label'].lower()}: {check['detail']}" for check in failures]])
    return "\n".join(lines) + "\n"


def _validation_input_fingerprints(project_root: Path) -> dict[str, dict[str, int]]:
    """Track ordinary file changes; asset integrity is verified separately."""
    candidates = []
    for directory in ("src", "config", "scripts"):
        root = project_root / directory
        if root.is_dir():
            candidates.extend(path for path in _iter_files_without_link_descent(root) if path.suffix.lower() in {".py", ".yaml", ".yml", ".json", ".ps1", ".toml"})
    candidates.extend(path for path in (project_root / "requirements.txt", project_root / "pyproject.toml") if path.is_file())
    style_manifest = project_root / "templates" / "origin_styles" / "manifest.json"
    if style_manifest.is_file():
        candidates.append(style_manifest)
    inputs = {}
    for path in sorted(candidates):
        info = path.stat()
        inputs[path.relative_to(project_root).as_posix()] = {
            "mtime_ns": info.st_mtime_ns, "size_bytes": info.st_size,
        }
    return inputs


def _iter_files_without_link_descent(root: Path) -> Iterator[Path]:
    """Yield files below ``root`` without traversing links or Windows junctions.

    Validation may inspect an external output tree that contains package-manager
    junctions (for example ``node_modules``). Following those links makes the
    project-wide presentation-artifact check unbounded and can scan unrelated
    caches outside the configured output root.
    """

    for current, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        directory_names[:] = [
            name
            for name in directory_names
            if not _is_link_or_junction(current_path / name)
        ]
        for name in file_names:
            yield current_path / name


def _is_link_or_junction(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction and is_junction():
            return True
        # Path.is_junction() is only available in Python 3.12+, while the
        # project supports Python 3.10. Inspect the Windows reparse attribute
        # directly so older runtimes also prune directory junctions.
        attributes = int(getattr(os.lstat(path), "st_file_attributes", 0))
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        # A directory that cannot be inspected safely is not a valid traversal
        # target for a validation scan.
        return True


def _processor_registry_summary_failures(registry: dict) -> list[str]:
    """Return explicit diagnostics when the supported summary drifts from entries."""

    failures: list[str] = []
    supported_entries = [
        entry
        for entry in registry.get("entries", [])
        if isinstance(entry, dict) and entry.get("supported_in_pipeline") is True
    ]
    supported_entry_types: list[str] = []
    for index, entry in enumerate(supported_entries):
        data_type = entry.get("inferred_data_type")
        if not isinstance(data_type, str) or not data_type.strip():
            failures.append(
                f"supported entry at entries[{index}] has no valid inferred_data_type"
            )
            continue
        supported_entry_types.append(data_type)

    declared_count = registry.get("pipeline_supported_count")
    actual_entry_count = len(supported_entries)
    if (
        not isinstance(declared_count, int)
        or isinstance(declared_count, bool)
        or declared_count != actual_entry_count
    ):
        failures.append(
            f"pipeline_supported_count={declared_count!r} but entries declare "
            f"{actual_entry_count} supported types"
        )

    declared_types = registry.get("pipeline_supported")
    if not isinstance(declared_types, list):
        failures.append(
            f"pipeline_supported must be a list; got {type(declared_types).__name__}"
        )
        return failures

    invalid_declared = [
        repr(data_type)
        for data_type in declared_types
        if not isinstance(data_type, str) or not data_type.strip()
    ]
    if invalid_declared:
        failures.append(
            "pipeline_supported contains invalid type names: "
            + ", ".join(invalid_declared)
        )

    valid_declared_types = [
        data_type
        for data_type in declared_types
        if isinstance(data_type, str) and data_type.strip()
    ]
    if (
        isinstance(declared_count, int)
        and not isinstance(declared_count, bool)
        and declared_count != len(valid_declared_types)
    ):
        failures.append(
            f"pipeline_supported_count={declared_count} but pipeline_supported "
            f"declares {len(valid_declared_types)} types"
        )
    duplicate_declared = sorted(
        {
            data_type
            for data_type in valid_declared_types
            if valid_declared_types.count(data_type) > 1
        }
    )
    if duplicate_declared:
        failures.append(
            "pipeline_supported contains duplicate types: "
            + ", ".join(duplicate_declared)
        )

    duplicate_entries = sorted(
        {
            data_type
            for data_type in supported_entry_types
            if supported_entry_types.count(data_type) > 1
        }
    )
    if duplicate_entries:
        failures.append(
            "supported entries contain duplicate inferred_data_type values: "
            + ", ".join(duplicate_entries)
        )

    declared_type_set = set(valid_declared_types)
    supported_entry_type_set = set(supported_entry_types)
    missing = sorted(supported_entry_type_set - declared_type_set)
    unexpected = sorted(declared_type_set - supported_entry_type_set)
    if missing:
        failures.append(
            "pipeline_supported missing supported entry types: " + ", ".join(missing)
        )
    if unexpected:
        failures.append(
            "pipeline_supported contains non-supported types: "
            + ", ".join(unexpected)
        )
    return failures


def _allowed_source_artifact_roots(project_root: Path) -> tuple[Path, ...]:
    allowed_roots = [
        project_root / "workspace_data",
        project_root / "input" / "raw_data",
    ]
    resolved_workspace = resolve_workspace_root(project_root)
    if resolved_workspace not in allowed_roots:
        allowed_roots.append(resolved_workspace)
    return tuple(root.resolve() for root in allowed_roots)


def _is_allowed_source_artifact(path: Path, allowed_roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _origin_governance_journal_policy_field_failures(rows: list[dict[str, str]]) -> list[str]:
    bool_fields = ["y_axis_visible", "y_ticks_visible", "y_tick_values_visible"]
    allowed_bool_values = {"true", "false"}
    allowed_marker_modes = {
        "none",
        "markers_preferred",
        "markers_required",
        "markers_optional",
        "markers_optional_for_sparse_points",
        "symbols_required_for_branches",
        "error_bars_when_available",
        "sticks_required",
        "not_applicable",
        "review_required",
    }
    allowed_marker_modes.update(policy.marker_policy for policy in all_plot_policies().values())
    failures: list[str] = []
    for index, row in enumerate(rows, start=2):
        result_id = row.get("result_id") or f"row {index}"
        for field in [
            "plot_primitive",
            "marker_policy",
            "plot_policy_reason",
            "y_axis_visible",
            "y_ticks_visible",
            "y_tick_values_visible",
        ]:
            if not str(row.get(field, "")).strip():
                failures.append(f"{result_id}: missing {field}")
        for field in bool_fields:
            value = str(row.get(field, "")).strip().casefold()
            if value and value not in allowed_bool_values:
                failures.append(f"{result_id}: {field} must be true/false, got {row.get(field)!r}")
        marker = str(row.get("marker_policy", "")).strip()
        if marker and marker not in allowed_marker_modes:
            failures.append(f"{result_id}: unsupported marker_policy {marker!r}")
    return failures
