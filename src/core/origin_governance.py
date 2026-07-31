from __future__ import annotations

import csv
import importlib
import importlib.metadata as metadata
import importlib.util
import io
import json
import warnings
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.file_utils import file_sha256 as _sha256_file
from src.core.output_sanitizer import render_output_path
from src.core.project import default_output_root, ensure_dir as _ensure_dir
from src.core.runtime_paths import resolve_locked_result_package
from src.origin.plot_policy import GRAPH4_FIXED_STYLE, get_plot_policy


DEFAULT_ORIGIN_SKILL_DIR = Path(".agents") / "skills" / "originpro-graph-export"
DEFAULT_LOCKED_RESULT_PACKAGE = Path("locked_origin_results_20260531_041538")

STYLE_PROFILE = "Origin Graph4 cached style"

REQUIRED_JOURNAL_INDEX_COLUMNS = {
    "result_id",
    "data_type",
    "source_hash",
    "processed_csv",
    "metadata",
    "origin_file",
    "figure_tif",
    "preview_png",
    "qc_status",
    "manual_check_required",
    "plotting_skill_sha256",
    "plot_style_profile",
    "y_tick_policy",
    "plot_primitive",
    "y_axis_visible",
    "y_ticks_visible",
    "y_tick_values_visible",
    "marker_policy",
    "plot_policy_reason",
    "material_color_key",
}

PACKAGE_SPECS = [
    {"package": "pybaselines", "module": "pybaselines", "tier": "core", "data_types": ["Raman", "PL", "FTIR", "UV-vis DRS", "EPR"], "license_policy": "permissive", "use": "baseline correction candidate"},
    {"package": "scipy", "module": "scipy", "tier": "core", "data_types": ["spectra", "all numeric"], "license_policy": "permissive", "use": "find_peaks and numeric routines"},
    {"package": "vgd-reader", "module": "vgd_reader", "tier": "optional_adapter", "data_types": ["XPS"], "license_policy": "permissive", "use": "VGD reader probe"},
    {"package": "pygaps", "module": "pygaps", "tier": "optional_adapter", "data_types": ["BET"], "license_policy": "permissive", "use": "PointIsotherm candidate provenance only; no BET fit/model conclusion"},
    {"package": "nmrglue", "module": "nmrglue", "tier": "diagnostic_only", "data_types": ["NMR"], "license_policy": "permissive", "use": "scan-only NMR adapter probe; no maintained NMR processor"},
    {"package": "tifffile", "module": "tifffile", "tier": "diagnostic_only", "data_types": ["SEM", "TEM"], "license_policy": "permissive", "use": "scan-only image metadata probe"},
    {"package": "pillow", "module": "PIL", "tier": "core", "data_types": ["SEM", "TEM", "QC"], "license_policy": "permissive", "use": "image preview and DPI inspection"},
    {"package": "scikit-image", "module": "skimage", "tier": "future_reference", "data_types": ["SEM", "TEM"], "license_policy": "future_candidate_unused", "use": "future image-QC candidate only; current adapter uses Pillow/tifffile"},
    {"package": "ixdat", "module": "ixdat", "tier": "diagnostic_only", "data_types": ["photocurrent", "electrochemistry"], "license_policy": "permissive", "use": "electrochemical import adapter probe; not used by the maintained table processor"},
    {"package": "impedance", "module": "impedance", "tier": "diagnostic_only", "data_types": ["EIS"], "license_policy": "MIT", "use": "explicit diagnostic fit API only; the formal EIS processor never fits"},
    {"package": "rainbow-api", "module": "rainbow", "tier": "optional_adapter", "data_types": ["HPLC/LC OpenLab raw data"], "license_policy": "LGPL_command_specific_boundary", "use": "required decoder for the selected OpenLab raw-data command"},
    {"package": "mocca2", "module": "mocca2", "tier": "diagnostic_only", "data_types": ["HPLC/LC exported data"], "license_policy": "permissive", "use": "adapter probe only; no maintained production call site"},
    {"package": "pymzml", "module": "pymzml", "tier": "diagnostic_only", "data_types": ["MS"], "license_policy": "permissive", "use": "scan-only MS adapter probe; no maintained MS processor"},
    {"package": "pyteomics", "module": "pyteomics", "tier": "diagnostic_only", "data_types": ["MS"], "license_policy": "permissive", "use": "scan-only MS adapter probe; no maintained MS processor"},
    {"package": "cwepr", "module": "cwepr", "tier": "optional_adapter", "data_types": ["EPR"], "license_policy": "BSD", "use": "cw-EPR candidate metrics; no radical assignment"},
    {"package": "eprpy", "module": "eprpy", "tier": "optional_adapter", "data_types": ["EPR"], "license_policy": "MIT", "use": "EPR candidate metrics fallback; no radical assignment"},
    {"package": "lmfitxps", "module": "lmfitxps", "tier": "optional_adapter", "data_types": ["XPS"], "license_policy": "MIT_with_internal_license_review", "use": "existing fitted-curve summary only; no automatic fitting or valence assignment"},
    {"package": "galvani", "module": "galvani", "tier": "reference_only", "data_types": ["electrochemistry"], "license_policy": "GPL_reference_only", "use": "Bio-Logic reader reference only"},
    {"package": "eclabfiles", "module": "eclabfiles", "tier": "reference_only", "data_types": ["electrochemistry"], "license_policy": "GPL_reference_only", "use": "EC-Lab reader reference only"},
    {"package": "hplc-py", "module": "hplc", "tier": "reference_only", "data_types": ["HPLC/LC exported data"], "license_policy": "reference_only_gpl", "use": "raw HPLC reader reference only; exported-table flow does not require it"},
    {"package": "pyopenms", "module": "pyopenms", "tier": "reference_only", "data_types": ["MS"], "license_policy": "heavy_optional_reference", "use": "full MS toolkit reference only"},
    {"package": "matchms", "module": "matchms", "tier": "blocked", "data_types": ["MS"], "license_policy": "blocked_core_dependency_change", "use": "blocked from the automatic dependency set because it would change core numpy/scipy versions"},
    {"package": "pyimpspec", "module": "pyimpspec", "tier": "reference_only", "data_types": ["EIS"], "license_policy": "GPL_reference_only", "use": "EIS expert analysis reference only"},
]


@dataclass(frozen=True)
class OriginGovernanceOutputs:
    skill_sha256: str
    snapshot_md: Path
    snapshot_json: Path
    journal_index_csv: Path
    journal_index_md: Path
    structure_report: Path
    cleanup_report: Path


def run_origin_governance(
    project_root: Path,
    *,
    skill_dir: Path | None = None,
    package_dir: Path | None = None,
) -> OriginGovernanceOutputs:
    skill_dir = _resolve_project_path(project_root, skill_dir or DEFAULT_ORIGIN_SKILL_DIR)
    package_dir = _resolve_project_path(project_root, package_dir) if package_dir else resolve_locked_result_package(project_root)

    skill_payload = write_origin_plotting_skill_snapshot(project_root, skill_dir)
    journal_csv, journal_md = write_journal_ready_index(project_root, package_dir, skill_payload)
    write_directory_indexes(project_root)
    package_report = write_package_integration_report(project_root)
    coverage_json, coverage_md = write_data_type_coverage_matrix(project_root, package_report)
    write_manual_review_required_final(project_root)
    write_journal_figure_qc(project_root, package_dir, skill_payload)
    structure_report = write_structure_report(project_root)
    cleanup_report = write_cleanup_report(project_root)
    write_agent_summary(project_root, skill_payload, package_dir, journal_csv)
    update_dashboard(project_root, journal_csv)

    return OriginGovernanceOutputs(
        skill_sha256=skill_payload["skill_sha256"],
        snapshot_md=default_output_root(project_root) / "reports" / "origin_plotting_skill_snapshot.md",
        snapshot_json=default_output_root(project_root) / "reports" / "origin_plotting_skill_snapshot.json",
        journal_index_csv=journal_csv,
        journal_index_md=journal_md,
        structure_report=structure_report,
        cleanup_report=cleanup_report,
    )


def write_origin_plotting_skill_snapshot(project_root: Path, skill_dir: Path) -> dict:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"origin plotting skill is missing: {skill_md}")

    files = [path for path in skill_dir.rglob("*") if path.is_file()]
    file_entries = []
    for path in sorted(files):
        file_entries.append(
            {
                "relative_path": str(path.relative_to(skill_dir)).replace("\\", "/"),
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "skill_dir": render_output_path(skill_dir, project_root=project_root),
        "skill_md": render_output_path(skill_md, project_root=project_root),
        "skill_sha256": _sha256_file(skill_md),
        "files": file_entries,
        "locked_rules": {
            "style_source": ".agents/skills/originpro-graph-export/SKILL.md",
            "graph": "Graph4",
            "cache_style": True,
            "refresh_template_each_run": False,
            "origin_entrypoint": "Origin.Application",
            "avoid_entrypoint": "Origin.ApplicationSI",
            "page_width": 6432,
            "page_height": 4923,
            "layer_left": 17.89,
            "layer_top": 11.6,
            "layer_width": 68.19,
            "layer_height": 71.81,
            "axis_line_width": 3,
            "sample_line_width": 3,
            "font_family": "Arial",
            "x_tick_label_size": 28,
            "y_tick_label_size": 36,
            "x_axis_title_size": 36,
            "y_axis_title_size": 36,
            "legend_font_size": 26,
            "annotation_font_size": GRAPH4_FIXED_STYLE.annotation_font_size,
            "font_bold": GRAPH4_FIXED_STYLE.font_bold,
            "tif_dpi": 600,
            "outputs": ["OPJU", "TIF", "PNG preview"],
            "palette": "Okabe-Ito fallback unless skill or material color map overrides",
        },
    }

    reports = _ensure_dir(default_output_root(project_root) / "reports")
    json_path = reports / "origin_plotting_skill_snapshot.json"
    md_path = reports / "origin_plotting_skill_snapshot.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# Origin Plotting Skill Snapshot",
        "",
        f"- Skill path: `{render_output_path(skill_md, project_root=project_root)}`",
        f"- Skill SHA256: `{payload['skill_sha256']}`",
        f"- Generated at: `{payload['generated_at']}`",
        "- Locked source of truth: the project-local Origin graph export skill.",
        "- Origin entrypoint: `Origin.Application`.",
        "- Graph/style source: cached `Graph4` profile.",
        "- Export contract: OPJU, 600 dpi TIF, PNG preview.",
        "- Axis title size: 36 pt for X and Y titles.",
        "- Y tick policy: resolved by data type from the skill-backed project policy.",
        "",
        "## Skill File Inventory",
        "",
        "| File | SHA256 | Bytes |",
        "| --- | --- | ---: |",
    ]
    for entry in file_entries:
        md.append(f"| `{entry['relative_path']}` | `{entry['sha256']}` | {entry['bytes']} |")
    md.append("")
    text = "\n".join(md)
    md_path.write_text(text, encoding="utf-8")
    return payload


def write_journal_ready_index(project_root: Path, package_dir: Path, skill_payload: dict) -> tuple[Path, Path]:
    index_csv = package_dir / "index.csv"
    if not index_csv.exists():
        raise FileNotFoundError(f"locked result package index is missing: {index_csv}")

    color_lookup = _load_material_color_lookup(project_root)
    rows = _read_csv(index_csv)
    enriched_rows = []
    for row in rows:
        data_type = row.get("data_type", "")
        result_id = row.get("result_id", "")
        material_key = color_lookup.get(result_id) or _infer_material_key(row)
        plot_policy = get_plot_policy(data_type)
        y_policy = _policy_y_tick_summary(plot_policy)
        enriched = dict(row)
        enriched.update(
            {
                "plotting_skill_sha256": skill_payload["skill_sha256"],
                "plot_style_profile": STYLE_PROFILE,
                "y_tick_policy": y_policy,
                "plot_primitive": plot_policy.plot_primitive,
                "y_axis_visible": _bool_text(plot_policy.y_axis_visible),
                "y_ticks_visible": _bool_text(plot_policy.y_ticks_visible),
                "y_tick_values_visible": _bool_text(plot_policy.y_tick_values_visible),
                "marker_policy": plot_policy.marker_policy,
                "plot_policy_reason": plot_policy.plot_policy_reason,
                "material_color_key": material_key,
                "skill_rule_reference": "origin_plotting_skill_snapshot.md",
            }
        )
        enriched_rows.append(enriched)

    reports = _ensure_dir(default_output_root(project_root) / "reports")
    out_csv = reports / "journal_ready_index.csv"
    out_md = reports / "journal_ready_index.md"
    _write_csv(out_csv, enriched_rows)

    counts = Counter(row.get("data_type", "<missing>") for row in enriched_rows)
    qc_counts = Counter(row.get("qc_status", "<missing>") for row in enriched_rows)
    md = [
        "# Journal-ready Index",
        "",
        f"- Source package: `{render_output_path(package_dir, project_root=project_root)}`",
        f"- Rows: {len(enriched_rows)}",
        f"- Plotting skill SHA256: `{skill_payload['skill_sha256']}`",
        f"- Style profile: `{STYLE_PROFILE}`",
        "",
        "## Data Types",
        "",
    ]
    for data_type, count in sorted(counts.items()):
        md.append(f"- {data_type}: {count}")
    md.extend(["", "## QC Status", ""])
    for status, count in sorted(qc_counts.items()):
        md.append(f"- {status}: {count}")
    md.extend(
        [
            "",
            "## Added Columns",
            "",
            "- `plotting_skill_sha256`",
            "- `plot_style_profile`",
            "- `y_tick_policy`",
            "- `plot_primitive`",
            "- `y_axis_visible`",
            "- `y_ticks_visible`",
            "- `y_tick_values_visible`",
            "- `marker_policy`",
            "- `plot_policy_reason`",
            "- `material_color_key`",
            "- `skill_rule_reference`",
            "",
        ]
    )
    text = "\n".join(md)
    out_md.write_text(text, encoding="utf-8")
    return out_csv, out_md


def write_package_integration_report(project_root: Path) -> dict:
    results = []
    for spec in PACKAGE_SPECS:
        result = dict(spec)
        allow_import = spec["tier"] in {"core", "optional_adapter"}
        result.update(_package_import_status(spec["package"], spec["module"], allow_import=allow_import))
        result["core_flow_allowed"] = result["tier"] == "core" and result["import_status"] == "ok"
        if result["tier"] == "optional_adapter":
            result["core_flow_allowed"] = False
            result["adapter_policy"] = "available only behind explicit optional adapter and manual-review guard"
        elif result["tier"] == "reference_only":
            result["adapter_policy"] = "do not import in automatic processing; reference/report only"
        elif result["tier"] == "blocked":
            result["adapter_policy"] = "blocked from the automatic dependency set"
        elif result["tier"] == "future_reference":
            result["adapter_policy"] = "future candidate only; not imported by current automatic processing"
        elif result["tier"] == "diagnostic_only":
            result["adapter_policy"] = "metadata probe only; do not import in the maintained automatic processing path"
        else:
            result["adapter_policy"] = "allowed for candidate calculations without scientific conclusions"
        results.append(result)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "installed_or_detected": results,
        "policy": {
            "no_third_party_source_copied": True,
            "gpl_packages_reference_only": True,
            "expert_systems_reference_only": True,
            "automatic_scientific_assignment_blocked": True,
        },
    }
    reports = _ensure_dir(default_output_root(project_root) / "reports")
    json_path = reports / "package_integration_report.json"
    md_path = reports / "package_integration_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Package Integration Report",
        "",
        "- Third-party source copied into project: no.",
        "- GPL/expert-system packages in core automatic flow: no.",
        "- Real data processing triggered by this report: no.",
        "",
        "| Package | Version | Import | Tier | License policy | Data types | Use |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        lines.append(
            f"| `{item['package']}` | {item.get('version') or ''} | {item['import_status']} | {item['tier']} | {item['license_policy']} | {', '.join(item['data_types'])} | {item['use']} |"
        )
    lines.append("")
    text = "\n".join(lines)
    md_path.write_text(text, encoding="utf-8")
    return payload


def write_data_type_coverage_matrix(project_root: Path, package_report: dict) -> tuple[Path, Path]:
    installed = {item["package"]: item for item in package_report["installed_or_detected"] if item["import_status"] == "ok"}
    rows = [
        {"data_type": "photocurrent/photoelectrochemistry", "reader": "table/CHI TXT + optional ixdat", "algorithm": "time-current, light marker, current density candidate", "external_packages": _available_names(installed, ["ixdat", "scipy"]), "auto_conclusions": "blocked"},
        {"data_type": "BET", "reader": "CSV/XLS/XLSX exported tables + optional pyGAPS", "algorithm": "exported isotherm/summary parser plus optional pyGAPS PointIsotherm provenance; no BET fit", "external_packages": _available_names(installed, ["pygaps"]), "auto_conclusions": "blocked"},
        {"data_type": "EPR", "reader": "JEOL decoder + optional cwepr/eprpy", "algorithm": "adapter field-intensity, peak-to-peak, g candidate", "external_packages": _available_names(installed, ["cwepr", "eprpy"]), "auto_conclusions": "radical assignment blocked"},
        {"data_type": "PL/FTIR/Raman/UV-vis", "reader": "tables", "algorithm": "pybaselines ASLS candidate, scipy peaks, raw/corrected columns", "external_packages": _available_names(installed, ["pybaselines", "scipy"]), "auto_conclusions": "defect/recombination/bond assignment blocked"},
        {"data_type": "SEM/TEM", "reader": "image metadata/probe only", "algorithm": "thumbnail/QC metadata only", "external_packages": _available_names(installed, ["pillow", "tifffile"]), "auto_conclusions": "morphology/lattice interpretation blocked"},
        {"data_type": "XPS", "reader": "tables + optional vgd-reader/lmfitxps", "algorithm": "adapter raw/background/envelope/component/residual handling; no auto fitting", "external_packages": _available_names(installed, ["vgd-reader", "lmfitxps"]), "auto_conclusions": "valence assignment blocked"},
        {"data_type": "XRD", "reader": "CSV/TXT/XLSX tables; raw/dql probe only", "algorithm": "peak candidates only", "external_packages": _available_names(installed, ["scipy"]), "auto_conclusions": "phase/plane assignment blocked"},
        {"data_type": "NMR", "reader": "optional nmrglue for Bruker processed data", "algorithm": "spectrum/peaklist index only", "external_packages": _available_names(installed, ["nmrglue"]), "auto_conclusions": "structure interpretation blocked"},
        {"data_type": "MS", "reader": "mzML/mzXML/MGF/msp standard formats", "algorithm": "spectrum index only", "external_packages": _available_names(installed, ["pymzml", "pyteomics"]), "auto_conclusions": "product assignment blocked"},
        {"data_type": "EIS/LEVM", "reader": "standard tables; LEVM lst parser planned", "algorithm": "measured Nyquist/Bode-ready coordinates only; no automatic branch selection or fit", "external_packages": _available_names(installed, ["scipy"]), "auto_conclusions": "equivalent-circuit fitting and conclusions blocked"},
    ]
    reports = _ensure_dir(default_output_root(project_root) / "reports")
    json_path = reports / "data_type_coverage_matrix.json"
    md_path = reports / "data_type_coverage_matrix.md"
    json_path.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Data Type Coverage Matrix",
        "",
        "| Data type | Reader | Algorithm | External packages | Auto conclusions |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['data_type']} | {row['reader']} | {row['algorithm']} | {row['external_packages']} | {row['auto_conclusions']} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def write_manual_review_required_final(project_root: Path) -> Path:
    source_csv = default_output_root(project_root) / "reports" / "manual_review_required_filtered.csv"
    out = default_output_root(project_root) / "reports" / "manual_review_required_final.xlsx"
    if not source_csv.exists():
        return out
    rows = _read_csv(source_csv)
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "manual_review"
    headers = ["index", "data_type_candidate", "file_path", "reason", "recommended_action", "source_hash"]
    sheet.append(headers)
    for index, row in enumerate(rows, 1):
        sheet.append(
            [
                index,
                row.get("data_type_candidate") or row.get("data_type") or "",
                row.get("relative_path") or row.get("target_file") or row.get("source_file") or "",
                row.get("reason") or row.get("manual_review_reason") or row.get("why_not_auto_applied") or "",
                row.get("recommended_action") or row.get("suggested_user_action") or "manual confirmation required before processing",
                row.get("source_hash") or "",
            ]
        )
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(60, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
    workbook.save(out)
    return out


def write_journal_figure_qc(project_root: Path, package_dir: Path, skill_payload: dict) -> tuple[Path, Path]:
    rows = _read_csv(package_dir / "index.csv")
    qc_rows = []
    for row in rows:
        checks = {}
        for key in ["origin_file", "figure_tif", "preview_png", "processed_csv", "metadata"]:
            path = package_dir / row.get(key, "")
            checks[f"{key}_exists"] = path.exists()
            checks[f"{key}_nonempty"] = path.exists() and path.stat().st_size > 0
        status = "QC_PASS" if all(checks.values()) and row.get("qc_status") == "QC_PASS" else "QC_WARNING"
        plot_policy = get_plot_policy(row.get("data_type", ""))
        qc_rows.append(
            {
                "result_id": row.get("result_id"),
                "data_type": row.get("data_type"),
                "qc_status": status,
                "plotting_skill_sha256": skill_payload["skill_sha256"],
                "y_tick_policy": _policy_y_tick_summary(plot_policy),
                "plot_primitive": plot_policy.plot_primitive,
                "y_axis_visible": plot_policy.y_axis_visible,
                "y_ticks_visible": plot_policy.y_ticks_visible,
                "y_tick_values_visible": plot_policy.y_tick_values_visible,
                "checks": checks,
            }
        )
    summary = Counter(item["qc_status"] for item in qc_rows)
    payload = {"summary": dict(summary), "rows": qc_rows}
    reports = _ensure_dir(default_output_root(project_root) / "reports")
    json_path = reports / "journal_figure_qc.json"
    md_path = reports / "journal_figure_qc.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Journal Figure QC",
        "",
        f"- Plotting skill SHA256: `{skill_payload['skill_sha256']}`",
        f"- Total figures checked: {len(qc_rows)}",
    ]
    for status, count in sorted(summary.items()):
        lines.append(f"- {status}: {count}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def write_directory_indexes(project_root: Path) -> list[Path]:
    outputs = []
    outputs.append(_write_output_report_index(project_root))
    return outputs


def write_structure_report(project_root: Path) -> Path:
    report = default_output_root(project_root) / "reports" / "project_structure_report.md"
    lines = [
        "# Project Structure Report",
        "",
        "- Root entry docs kept at `README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, and `AGENT_HANDOFF.md`.",
        "- `output/reports/README.md` now indexes generated reports.",
        "- No raw data directories were reorganized.",
        "- Historical result packages were not moved, renamed, or deleted.",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def write_cleanup_report(project_root: Path) -> Path:
    candidates = []
    for rel in [".pytest_cache", "scripts/__pycache__"]:
        path = project_root / rel
        if path.exists():
            candidates.append(rel)
    for path in sorted((project_root / "src").rglob("__pycache__")) if (project_root / "src").exists() else []:
        candidates.append(str(path.relative_to(project_root)).replace("\\", "/"))

    reports = _ensure_dir(default_output_root(project_root) / "reports")
    pending = reports / "pending_cleanup_candidates.md"
    cleanup = reports / "cleanup_and_structure_report.md"

    pending_lines = [
        "# Pending Cleanup Candidates",
        "",
        "These files are safe-looking cache or scratch candidates, but Origin governance did not delete them automatically because tests may recreate caches.",
        "",
    ]
    if candidates:
        pending_lines.extend(f"- `{candidate}`" for candidate in sorted(set(candidates)))
    else:
        pending_lines.append("- No pending cleanup candidates found.")
    pending_lines.append("")
    pending.write_text("\n".join(pending_lines), encoding="utf-8")

    lines = [
        "# Cleanup and Structure Report",
        "",
        "- Automatic deletion performed: none.",
        "- Cleanup policy: uncertain files are recorded, not deleted.",
        "- Raw data tree touched: no.",
        "- F-drive backup touched: no.",
        "- Historical formal results touched: no.",
        f"- Pending cleanup candidate list: `{render_output_path(pending, project_root=project_root, output_root=default_output_root(project_root))}`",
        "",
    ]
    cleanup.write_text("\n".join(lines), encoding="utf-8")
    return cleanup


def write_agent_summary(project_root: Path, skill_payload: dict, package_dir: Path, journal_csv: Path) -> Path:
    summary = default_output_root(project_root) / "reports" / "origin_governance_summary.md"
    lines = [
        "# Origin governance Summary",
        "",
        f"- Origin plotting skill snapshot SHA256: `{skill_payload['skill_sha256']}`",
        f"- locked result package audited for journal index: `{render_output_path(package_dir, project_root=project_root)}`",
        f"- Journal-ready index: `{render_output_path(journal_csv, project_root=project_root, output_root=default_output_root(project_root))}`",
        "- Project structure index files refreshed.",
        "- Raw data and formal result packages were not moved or deleted.",
        "- No real Origin processing was launched.",
        "",
    ]
    summary.write_text("\n".join(lines), encoding="utf-8")
    return summary


def update_dashboard(project_root: Path, journal_csv: Path) -> Path:
    dashboard = _ensure_dir(default_output_root(project_root) / "review_dashboard") / "origin_plotting_governance.md"
    lines = [
        "# Origin Plotting Governance",
        "",
        "- Plotting style source: `.agents/skills/originpro-graph-export/SKILL.md`.",
        "- Graph profile: cached Graph4.",
        "- Journal-ready index:",
        f"  `{render_output_path(journal_csv, project_root=project_root, output_root=default_output_root(project_root))}`",
        "- Review the locked result package PNG/TIF/OPJU outputs against the skill snapshot before manuscript use.",
        "",
    ]
    dashboard.write_text("\n".join(lines), encoding="utf-8")
    index = default_output_root(project_root) / "review_dashboard" / "index.md"
    if index.exists():
        text = index.read_text(encoding="utf-8")
        link = "- [Origin plotting governance](origin_plotting_governance.md)"
        if link not in text:
            index.write_text(text.rstrip() + "\n" + link + "\n", encoding="utf-8")
    return dashboard


def _write_output_report_index(project_root: Path) -> Path:
    report_dir = _ensure_dir(default_output_root(project_root) / "reports")
    report_counts = Counter()
    for path in report_dir.glob("*"):
        if path.is_file():
            stem = path.stem
            key = stem.split("_", 1)[0] if "_" in stem else "other"
            report_counts[key] += 1
    lines = [
        "# Output Reports",
        "",
        "Generated reports are retained here. Origin governance adds this index without moving formal outputs.",
        "",
        "## Counts",
        "",
    ]
    for group, count in sorted(report_counts.items()):
        lines.append(f"- {group}: {count}")
    lines.extend(
        [
            "",
            "## Origin governance Key Files",
            "",
            "- `origin_plotting_skill_snapshot.json`",
            "- `journal_ready_index.csv`",
            "- `cleanup_and_structure_report.md`",
            "- `pending_cleanup_candidates.md`",
            "",
        ]
    )
    out = report_dir / "README.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
def _load_material_color_lookup(project_root: Path) -> dict[str, str]:
    path = default_output_root(project_root) / "reports" / "locked_result_material_color_map.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    lookup = {}
    for item in data.get("assignments", []):
        dataset_id = item.get("dataset_id")
        material = item.get("material_key")
        color = item.get("hex") or item.get("color_name")
        if dataset_id and material:
            lookup[dataset_id] = f"{material}:{color}" if color else material
    return lookup


def _package_import_status(package: str, module: str, *, allow_import: bool = True) -> dict:
    result = {"import_status": "missing", "version": None, "license": ""}
    try:
        result["version"] = metadata.version(package)
    except metadata.PackageNotFoundError:
        pass
    try:
        pkg_metadata = metadata.metadata(package)
        license_text = pkg_metadata.get("License") or "; ".join((pkg_metadata.get_all("Classifier") or [])[:8])
        result["license"] = _short_license_text(license_text)
    except metadata.PackageNotFoundError:
        result["license"] = "not installed"
    if not allow_import:
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, AttributeError, ValueError):
            available = False
        result["import_status"] = "available_not_imported" if available else "missing"
        result["smoke_status"] = "not_run_by_policy"
        return result
    try:
        with warnings.catch_warnings(), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            warnings.filterwarnings(
                "ignore",
                message="Cython PyNumpress is not installed.*",
                category=ImportWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message="Plotly is required for plotting support.*",
                category=ImportWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message="Importing from numpy\\.matlib is deprecated.*",
                category=PendingDeprecationWarning,
            )
            importlib.import_module(module)
        result["import_status"] = "ok"
        result["smoke_status"] = _package_smoke(package)
    except Exception as exc:
        result["import_status"] = "fail"
        result["error"] = repr(exc)
        result["smoke_status"] = "not_run"
    return result


def _package_smoke(package: str) -> str:
    try:
        if package == "pybaselines":
            from pybaselines import Baseline
            Baseline([1.0, 2.0, 3.0]).asls([1.0, 2.0, 1.0])
        elif package == "scipy":
            from scipy.signal import find_peaks
            find_peaks([1.0, 3.0, 1.0])
        elif package == "tifffile":
            import numpy as np
            import tifffile
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / "smoke.tif"
                tifffile.imwrite(path, np.zeros((2, 2), dtype=np.uint8))
                tifffile.imread(path)
        elif package == "pillow":
            from PIL import Image
            Image.new("RGB", (2, 2))
        elif package == "pyteomics":
            from pyteomics import mgf
            _ = mgf
        elif package == "pymzml":
            import pymzml
            _ = pymzml.run.Reader
        return "ok"
    except Exception as exc:
        return "warning:" + repr(exc)
    return "import_only"


def _short_license_text(value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    return text[:180] + ("..." if len(text) > 180 else "")


def _available_names(installed: dict, names: list[str]) -> str:
    available = [name for name in names if name in installed]
    return ", ".join(available) if available else "none"


def _infer_material_key(row: dict[str, str]) -> str:
    haystack = " ".join([row.get("result_id", ""), row.get("source_file", ""), row.get("notes", "")]).upper()
    for token in ["BOBC", "CWO", "BICU-10", "BICU10", "BC"]:
        if token in haystack:
            return token
    return "manual_review"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _policy_y_tick_summary(policy) -> str:
    if not policy.y_axis_visible:
        return "hide_y_axis_and_ticks"
    if policy.y_ticks_visible and policy.y_tick_values_visible:
        return "show_y_axis_ticks_and_numeric_values"
    if policy.y_ticks_visible and not policy.y_tick_values_visible:
        return "show_y_axis_and_tick_marks_hide_numeric_values"
    return "show_y_axis_hide_tick_marks_and_numeric_values"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_project_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path
