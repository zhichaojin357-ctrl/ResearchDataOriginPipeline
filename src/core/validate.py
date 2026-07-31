from __future__ import annotations

import csv
import json
import os
import stat
from pathlib import Path
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
    registry_path,
    report_path,
)
from src.core.runtime_paths import resolve_workspace_root
from src.core.runtime_paths import resolve_output_root
from src.origin.adapter import ORIGIN_DISABLE_ENV_VARS, check_origin_available
from src.origin.plot_policy import all_plot_policies, validate_graph4_style_config
from src.origin.style_registry import validate_origin_style_asset_integrity


def validate(project_root: Path) -> int:
    output_root = resolve_output_root(project_root)
    ensure_output_structure(project_root, output_root=output_root)
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
        name for name in REQUIRED_OUTPUT_DIRS if not (output_root / name).is_dir()
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
    supported_entries = [entry for entry in registry["entries"] if entry["supported_in_pipeline"]]
    lines.append(f"- Pipeline-supported entries: {len(supported_entries)}")
    registry_summary_failures = _processor_registry_summary_failures(registry)
    lines.append(
        f"- Processor registry supported summary: "
        f"{'pass' if not registry_summary_failures else 'fail'}"
    )
    if registry_summary_failures:
        for failure in registry_summary_failures:
            lines.append(f"  - {failure}")
        failures.append("processor registry supported summary drift")
    required_registry_fields = set(registry.get("required_fields", [])) | {
        "folder_name",
        "inferred_data_type",
        "supported_in_pipeline",
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
        matches = [
            entry
            for entry in registry["entries"]
            if entry.get("inferred_data_type") == inferred_type
            and (not expected.get("folder_name") or entry.get("folder_name") == expected["folder_name"])
        ]
        if not matches:
            deferred_failures.append(f"{expected.get('folder_name', inferred_type)} missing")
            continue
        entry = matches[0]
        deferred_seen.append(f"{entry.get('folder_name')}={inferred_type}")
        if entry.get("supported_in_pipeline") is not False:
            deferred_failures.append(f"{entry.get('folder_name')} supported_in_pipeline must be false")
        if entry.get("special_handling") != "scan_only":
            deferred_failures.append(f"{entry.get('folder_name')} special_handling must be scan_only")
        if entry.get("selected_processor") != "none":
            deferred_failures.append(f"{entry.get('folder_name')} {inferred_type} selected_processor must be none")
    lines.append(f"- Deferred/reference registry semantics: {'pass' if not deferred_failures else 'fail'}")
    if deferred_seen:
        lines.append("  - " + ", ".join(deferred_seen))
    if deferred_failures:
        for failure in deferred_failures:
            lines.append(f"  - {failure}")
        failures.append("deferred/reference registry semantics invalid")

    forbidden = ["src/ppt", "templates/ppt", "ppt_layout.yaml", "slide_plan.json", "presentation.pptx"]
    found = [path for path in forbidden if (project_root / path).exists()]
    lines.append(f"- PPT forbidden paths: {'pass' if not found else 'fail'}")
    if found:
        failures.append("PPT forbidden paths exist")

    presentation_artifacts = []
    scan_roots = [project_root]
    allowed_source_roots = _allowed_source_artifact_roots(project_root)
    if output_root.resolve() != project_root.resolve() and not _is_under_or_equal(output_root.resolve(), project_root.resolve()):
        scan_roots.append(output_root)
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        presentation_artifacts.extend(
            path
            for path in _iter_files_without_link_descent(scan_root)
            if not _is_allowed_source_artifact(path, allowed_source_roots)
            and (
                path.suffix.lower() in {".ppt", ".pptx"}
                or path.name == "slide_plan.json"
                or path.name == "ppt_layout.yaml"
                or path.name == "presentation.pptx"
            )
        )
    lines.append(f"- Forbidden presentation artifacts: {'pass' if not presentation_artifacts else 'fail'}")
    if presentation_artifacts:
        rendered = ", ".join(render_output_path(path, project_root=project_root, output_root=output_root) or str(path) for path in presentation_artifacts)
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
        "legend has no frame or fill": "legend_border: 0" in text and "legend_frame: 0" in text and "legend_fill: 0" in text,
        "chemical formula subscripts": "chemical_formula_subscripts: true" in text,
        "line width 3": "line_width: 3" in text and "axis_line_width: 3" in text,
        "axis title size 36": "axis_title_size: 36" in text,
        "X tick label size 28": "x_tick_label_size: 28" in text,
        "Y tick label size 36": "y_tick_label_size: 36" in text,
        "legend font size 26": "legend_font_size: 26" in text,
        "annotation font size 26": "annotation_font_size: 26" in text,
        "bold font enabled": "font_bold: true" in text,
    }
    for label, passed in origin_contract_checks.items():
        lines.append(f"- Origin contract {label}: {'pass' if passed else 'fail'}")
    failed_origin_contracts = [label for label, passed in origin_contract_checks.items() if not passed]
    try:
        validate_graph4_style_config(plot_style)
        lines.append("- Origin Graph4 fixed style values: pass")
    except ValueError as exc:
        lines.append(f"- Origin Graph4 fixed style values: fail ({exc})")
        failed_origin_contracts.append("Graph4 fixed style values")
    if failed_origin_contracts:
        failures.append("Origin plotting contract invalid: " + ", ".join(failed_origin_contracts))

    style_integrity = validate_origin_style_asset_integrity(project_root)
    lines.append(
        f"- Origin style asset integrity: {'pass' if style_integrity['ok'] else 'fail'} "
        f"(schema v{style_integrity['schema_version']}, assets={style_integrity['asset_count']})"
    )
    for warning in style_integrity.get("warnings", [])[:5]:
        lines.append(f"  - warning: {warning}")
    style_failures = [str(value) for value in style_integrity.get("failures", [])]
    if style_failures:
        for failure in style_failures[:10]:
            lines.append(f"  - {failure}")
        if len(style_failures) > 10:
            lines.append(f"  - ... {len(style_failures) - 10} more")
        failures.append("Origin style asset integrity invalid")

    origin_governance_files = {
        "snapshot_md": output_root / "reports" / "origin_plotting_skill_snapshot.md",
        "snapshot_json": output_root / "reports" / "origin_plotting_skill_snapshot.json",
        "journal_index": output_root / "reports" / "journal_ready_index.csv",
    }
    generated_origin_governance_files = {
        name: path
        for name, path in origin_governance_files.items()
        if name != "snapshot_md"
    }
    if any(path.exists() for path in generated_origin_governance_files.values()):
        missing_origin_governance = [name for name, path in origin_governance_files.items() if not path.exists()]
        lines.append(f"- Origin governance plotting governance files: {'pass' if not missing_origin_governance else 'fail'}")
        if missing_origin_governance:
            failures.append("missing Origin governance plotting governance files: " + ", ".join(missing_origin_governance))
        else:
            snapshot = json.loads(origin_governance_files["snapshot_json"].read_text(encoding="utf-8"))
            skill_hash = snapshot.get("skill_sha256")
            snapshot_text = origin_governance_files["snapshot_md"].read_text(encoding="utf-8")
            hash_ok = bool(skill_hash) and skill_hash in snapshot_text
            lines.append(f"- Origin governance plotting skill SHA256 recorded: {'pass' if hash_ok else 'fail'}")
            if not hash_ok:
                failures.append("Origin governance plotting skill SHA256 not recorded consistently")
            with origin_governance_files["journal_index"].open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                headers = set(reader.fieldnames or [])
                rows = list(reader)
            missing_columns = sorted(REQUIRED_JOURNAL_INDEX_COLUMNS - headers)
            lines.append(f"- Origin governance journal-ready index columns: {'pass' if not missing_columns else 'fail'}")
            if missing_columns:
                failures.append("Origin governance journal-ready index missing columns: " + ", ".join(missing_columns))
            if rows:
                skill_column_ok = all(row.get("plotting_skill_sha256") == skill_hash for row in rows)
                lines.append(f"- Origin governance journal-ready index skill hash: {'pass' if skill_column_ok else 'fail'}")
                if not skill_column_ok:
                    failures.append("Origin governance journal-ready index contains inconsistent plotting skill hashes")
                policy_field_failures = _origin_governance_journal_policy_field_failures(rows)
                lines.append(
                    f"- Origin governance journal-ready index policy values: "
                    f"{'pass' if not policy_field_failures else 'fail'}"
                )
                if policy_field_failures:
                    for failure in policy_field_failures[:10]:
                        lines.append(f"  - {failure}")
                    if len(policy_field_failures) > 10:
                        lines.append(f"  - ... {len(policy_field_failures) - 10} more")
                    failures.append("Origin governance journal-ready index policy values invalid")
    else:
        lines.append("- Origin governance plotting governance files: not checked (no generated output artifacts)")
    lines.append("- max_threads = 5")
    lines.append("- max_depth = 1")
    lines.append(f"- Claim policy forbidden claims: {len(claim.get('forbidden_claims', []))}")

    if failures:
        lines.extend(["", "## Failures", *[f"- {failure}" for failure in failures]])
    report_path(project_root, "validation_report.md", output_root=output_root).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failures else 0


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
