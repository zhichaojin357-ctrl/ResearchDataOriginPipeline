from __future__ import annotations

import csv
import hashlib
import importlib
import importlib.metadata as metadata
import io
import json
import warnings
from collections import Counter, defaultdict
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.output_sanitizer import render_output_path
from src.origin.plot_policy import GRAPH4_FIXED_STYLE, get_plot_policy


DEFAULT_ORIGIN_SKILL_DIR = Path(".agents") / "skills" / "originpro-graph-export"
DEFAULT_PHASE1_6_PACKAGE = Path("output/phase1_6_origin_results_20260531_041538")

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
    {"package": "pybaselines", "module": "pybaselines", "tier": "core_optional", "data_types": ["Raman", "PL", "FTIR", "UV-vis DRS", "EPR"], "license_policy": "permissive", "use": "baseline correction candidate"},
    {"package": "scipy", "module": "scipy", "tier": "core", "data_types": ["spectra", "all numeric"], "license_policy": "permissive", "use": "find_peaks and numeric routines"},
    {"package": "vgd-reader", "module": "vgd_reader", "tier": "optional_adapter", "data_types": ["XPS"], "license_policy": "permissive", "use": "VGD reader probe"},
    {"package": "pygaps", "module": "pygaps", "tier": "optional_adapter", "data_types": ["BET"], "license_policy": "permissive", "use": "PointIsotherm candidate provenance only; no BET fit/model conclusion"},
    {"package": "nmrglue", "module": "nmrglue", "tier": "optional_adapter", "data_types": ["NMR"], "license_policy": "permissive", "use": "Bruker processed data reader"},
    {"package": "tifffile", "module": "tifffile", "tier": "core_optional", "data_types": ["SEM", "TEM"], "license_policy": "permissive", "use": "image metadata and preview"},
    {"package": "pillow", "module": "PIL", "tier": "core_optional", "data_types": ["SEM", "TEM", "QC"], "license_policy": "permissive", "use": "image preview and DPI inspection"},
    {"package": "scikit-image", "module": "skimage", "tier": "optional_adapter", "data_types": ["SEM", "TEM"], "license_policy": "permissive", "use": "image metadata/QC only"},
    {"package": "ixdat", "module": "ixdat", "tier": "optional_adapter", "data_types": ["photocurrent", "electrochemistry"], "license_policy": "permissive", "use": "electrochemical import abstraction"},
    {"package": "impedance", "module": "impedance", "tier": "optional_adapter", "data_types": ["EIS"], "license_policy": "MIT", "use": "CustomCircuit draft fit candidate; no circuit conclusion"},
    {"package": "rainbow-api", "module": "rainbow", "tier": "optional_adapter", "data_types": ["HPLC/LC exported data"], "license_policy": "LGPL_optional_boundary", "use": "chromatography raw reader probe"},
    {"package": "mocca2", "module": "mocca2", "tier": "optional_adapter", "data_types": ["HPLC/LC exported data"], "license_policy": "permissive", "use": "baseline/peak candidate helper; no product assignment"},
    {"package": "pymzml", "module": "pymzml", "tier": "optional_adapter", "data_types": ["MS"], "license_policy": "permissive", "use": "mzML reader"},
    {"package": "pyteomics", "module": "pyteomics", "tier": "optional_adapter", "data_types": ["MS"], "license_policy": "permissive", "use": "mzML/mzXML/MGF/msp reader helpers"},
    {"package": "cwepr", "module": "cwepr", "tier": "optional_adapter", "data_types": ["EPR"], "license_policy": "BSD", "use": "cw-EPR candidate metrics; no radical assignment"},
    {"package": "eprpy", "module": "eprpy", "tier": "optional_adapter", "data_types": ["EPR"], "license_policy": "MIT", "use": "EPR candidate metrics fallback; no radical assignment"},
    {"package": "lmfitxps", "module": "lmfitxps", "tier": "optional_adapter", "data_types": ["XPS"], "license_policy": "MIT_with_internal_license_review", "use": "existing fitted-curve summary only; no automatic fitting or valence assignment"},
    {"package": "galvani", "module": "galvani", "tier": "reference_only", "data_types": ["electrochemistry"], "license_policy": "GPL_reference_only", "use": "Bio-Logic reader reference only"},
    {"package": "eclabfiles", "module": "eclabfiles", "tier": "reference_only", "data_types": ["electrochemistry"], "license_policy": "GPL_reference_only", "use": "EC-Lab reader reference only"},
    {"package": "pyopenms", "module": "pyopenms", "tier": "reference_only", "data_types": ["MS"], "license_policy": "heavy_optional_reference", "use": "full MS toolkit reference only"},
    {"package": "matchms", "module": "matchms", "tier": "reference_only", "data_types": ["MS"], "license_policy": "optional_reference", "use": "MS similarity reference only"},
    {"package": "pyimpspec", "module": "pyimpspec", "tier": "reference_only", "data_types": ["EIS"], "license_policy": "GPL_reference_only", "use": "EIS expert analysis reference only"},
]


@dataclass(frozen=True)
class Phase19Outputs:
    skill_sha256: str
    snapshot_md: Path
    snapshot_json: Path
    journal_index_csv: Path
    journal_index_md: Path
    structure_report: Path
    cleanup_report: Path


def run_phase1_9_governance(
    project_root: Path,
    *,
    skill_dir: Path | None = None,
    package_dir: Path | None = None,
) -> Phase19Outputs:
    skill_dir = _resolve_project_path(project_root, skill_dir or DEFAULT_ORIGIN_SKILL_DIR)
    package_dir = _resolve_project_path(project_root, package_dir or DEFAULT_PHASE1_6_PACKAGE)

    skill_payload = write_origin_plotting_skill_snapshot(project_root, skill_dir)
    journal_csv, journal_md = write_journal_ready_index(project_root, package_dir, skill_payload)
    write_method_card_index(project_root, skill_payload)
    write_directory_indexes(project_root)
    package_report = write_package_integration_report(project_root)
    coverage_json, coverage_md = write_data_type_coverage_matrix(project_root, package_report)
    write_manual_review_required_final(project_root)
    write_journal_figure_qc(project_root, package_dir, skill_payload)
    structure_report = write_structure_report(project_root)
    cleanup_report = write_cleanup_report(project_root)
    write_agent_summary(project_root, skill_payload, package_dir, journal_csv)
    update_dashboard(project_root, journal_csv)

    return Phase19Outputs(
        skill_sha256=skill_payload["skill_sha256"],
        snapshot_md=project_root / "docs" / "agent_reports" / "phase1_9_origin_plotting_skill_snapshot.md",
        snapshot_json=project_root / "output" / "reports" / "phase1_9_origin_plotting_skill_snapshot.json",
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

    reports = _ensure_dir(project_root / "output" / "reports")
    docs = _ensure_dir(project_root / "docs" / "agent_reports")
    json_path = reports / "phase1_9_origin_plotting_skill_snapshot.json"
    md_path = docs / "phase1_9_origin_plotting_skill_snapshot.md"
    report_md_path = reports / "phase1_9_origin_plotting_skill_snapshot.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# Phase 1.9 Origin Plotting Skill Snapshot",
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
    report_md_path.write_text(text, encoding="utf-8")
    return payload


def write_journal_ready_index(project_root: Path, package_dir: Path, skill_payload: dict) -> tuple[Path, Path]:
    index_csv = package_dir / "index.csv"
    if not index_csv.exists():
        raise FileNotFoundError(f"Phase 1.6 package index is missing: {index_csv}")

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
                "skill_rule_reference": "phase1_9_origin_plotting_skill_snapshot.md",
            }
        )
        enriched_rows.append(enriched)

    reports = _ensure_dir(project_root / "output" / "reports")
    docs = _ensure_dir(project_root / "docs" / "agent_reports")
    out_csv = reports / "phase1_9_journal_ready_index.csv"
    out_md = reports / "phase1_9_journal_ready_index.md"
    docs_md = docs / "phase1_9_journal_ready_index.md"
    _write_csv(out_csv, enriched_rows)

    counts = Counter(row.get("data_type", "<missing>") for row in enriched_rows)
    qc_counts = Counter(row.get("qc_status", "<missing>") for row in enriched_rows)
    md = [
        "# Phase 1.9 Journal-ready Index",
        "",
        f"- Source package: `{package_dir}`",
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
    docs_md.write_text(text, encoding="utf-8")
    return out_csv, out_md


def write_package_integration_report(project_root: Path) -> dict:
    results = []
    for spec in PACKAGE_SPECS:
        result = dict(spec)
        result.update(_package_import_status(spec["package"], spec["module"]))
        result["core_flow_allowed"] = result["tier"] in {"core", "core_optional"} and result["import_status"] == "ok"
        if result["tier"] == "optional_adapter":
            result["core_flow_allowed"] = False
            result["adapter_policy"] = "available only behind explicit optional adapter and manual-review guard"
        elif result["tier"] == "reference_only":
            result["adapter_policy"] = "do not import in automatic processing; reference/report only"
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
    reports = _ensure_dir(project_root / "output" / "reports")
    docs = _ensure_dir(project_root / "docs" / "agent_reports")
    json_path = reports / "phase1_9_package_integration_report.json"
    md_path = docs / "phase1_9_package_integration_report.md"
    report_md = reports / "phase1_9_package_integration_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phase 1.9 Package Integration Report",
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
    report_md.write_text(text, encoding="utf-8")
    return payload


def write_data_type_coverage_matrix(project_root: Path, package_report: dict) -> tuple[Path, Path]:
    installed = {item["package"]: item for item in package_report["installed_or_detected"] if item["import_status"] == "ok"}
    rows = [
        {"data_type": "photocurrent/photoelectrochemistry", "reader": "table/CHI TXT + optional ixdat", "algorithm": "time-current, light marker, current density candidate", "external_packages": _available_names(installed, ["ixdat", "scipy"]), "auto_conclusions": "blocked"},
        {"data_type": "BET", "reader": "CSV/XLS/XLSX exported tables + optional pyGAPS", "algorithm": "exported isotherm/summary parser plus optional pyGAPS PointIsotherm provenance; no BET fit", "external_packages": _available_names(installed, ["pygaps"]), "auto_conclusions": "blocked"},
        {"data_type": "EPR", "reader": "JEOL decoder + optional cwepr/eprpy", "algorithm": "adapter field-intensity, peak-to-peak, g candidate", "external_packages": _available_names(installed, ["cwepr", "eprpy"]), "auto_conclusions": "radical assignment blocked"},
        {"data_type": "PL/FTIR/Raman/UV-vis", "reader": "tables", "algorithm": "pybaselines ASLS candidate, scipy peaks, raw/corrected columns", "external_packages": _available_names(installed, ["pybaselines", "scipy"]), "auto_conclusions": "defect/recombination/bond assignment blocked"},
        {"data_type": "SEM/TEM", "reader": "image metadata/probe only", "algorithm": "thumbnail/QC metadata only", "external_packages": _available_names(installed, ["pillow", "tifffile", "scikit-image"]), "auto_conclusions": "morphology/lattice interpretation blocked"},
        {"data_type": "XPS", "reader": "tables + optional vgd-reader/lmfitxps", "algorithm": "adapter raw/background/envelope/component/residual handling; no auto fitting", "external_packages": _available_names(installed, ["vgd-reader", "lmfitxps"]), "auto_conclusions": "valence assignment blocked"},
        {"data_type": "XRD", "reader": "CSV/TXT/XLSX tables; raw/dql probe only", "algorithm": "peak candidates only", "external_packages": _available_names(installed, ["scipy"]), "auto_conclusions": "phase/plane assignment blocked"},
        {"data_type": "NMR", "reader": "optional nmrglue for Bruker processed data", "algorithm": "spectrum/peaklist index only", "external_packages": _available_names(installed, ["nmrglue"]), "auto_conclusions": "structure interpretation blocked"},
        {"data_type": "MS", "reader": "mzML/mzXML/MGF/msp standard formats", "algorithm": "spectrum index only", "external_packages": _available_names(installed, ["pymzml", "pyteomics"]), "auto_conclusions": "product assignment blocked"},
        {"data_type": "EIS/LEVM", "reader": "standard tables; LEVM lst parser planned", "algorithm": "Nyquist/Bode candidates; impedance adapter draft fit for visualization", "external_packages": _available_names(installed, ["scipy", "impedance"]), "auto_conclusions": "equivalent-circuit conclusion blocked"},
    ]
    reports = _ensure_dir(project_root / "output" / "reports")
    json_path = reports / "phase1_9_data_type_coverage_matrix.json"
    md_path = reports / "phase1_9_data_type_coverage_matrix.md"
    json_path.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 1.9 Data Type Coverage Matrix",
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
    (project_root / "docs" / "agent_reports" / "phase1_9_algorithm_upgrade_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return json_path, md_path


def write_manual_review_required_final(project_root: Path) -> Path:
    source_csv = project_root / "output" / "reports" / "phase1_8_manual_review_required_filtered.csv"
    out = project_root / "output" / "reports" / "phase1_9_manual_review_required_final.xlsx"
    if not source_csv.exists():
        return out
    rows = _read_csv(source_csv)
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "需人工复核"
    headers = ["序号", "数据类型候选", "文件路径", "原因", "建议操作", "哈希"]
    sheet.append(headers)
    for index, row in enumerate(rows, 1):
        sheet.append(
            [
                index,
                row.get("data_type_candidate") or row.get("data_type") or "",
                row.get("relative_path") or row.get("target_file") or row.get("source_file") or "",
                row.get("reason") or row.get("manual_review_reason") or row.get("why_not_auto_applied") or "",
                row.get("recommended_action") or row.get("suggested_user_action") or "人工确认后再处理",
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
    reports = _ensure_dir(project_root / "output" / "reports")
    json_path = reports / "phase1_9_journal_figure_qc.json"
    md_path = reports / "phase1_9_journal_figure_qc.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 1.9 Journal Figure QC",
        "",
        f"- Plotting skill SHA256: `{skill_payload['skill_sha256']}`",
        f"- Total figures checked: {len(qc_rows)}",
    ]
    for status, count in sorted(summary.items()):
        lines.append(f"- {status}: {count}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def write_method_card_index(project_root: Path, skill_payload: dict) -> Path:
    method_dir = project_root / "docs" / "method_cards"
    if not method_dir.exists():
        return method_dir / "README.md"
    cards = sorted(path for path in method_dir.glob("*.md") if path.name.lower() != "readme.md")
    lines = [
        "# Method Cards",
        "",
        "Each method card describes the data source, reader or adapter, processing algorithm, review items, and forbidden claims for one data type.",
        "",
        f"Current Origin plotting skill SHA256: `{skill_payload['skill_sha256']}`",
        "",
        "| Data type | Method card |",
        "| --- | --- |",
    ]
    for card in cards:
        lines.append(f"| {card.stem} | [{card.name}]({card.name}) |")
    lines.append("")
    readme = method_dir / "README.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme


def write_directory_indexes(project_root: Path) -> list[Path]:
    outputs = []
    outputs.append(_write_phase_report_index(project_root))
    outputs.append(_write_output_report_index(project_root))
    outputs.append(
        _write_simple_index(
            project_root / "scripts" / "README.md",
            "Scripts",
            "Operational scripts are kept here. Deprecated scripts should move to `scripts/archive/` only after no CLI or documentation entrypoint references them.",
        )
    )
    outputs.append(
        _write_simple_index(
            project_root / "examples" / "README.md",
            "Examples",
            "Small examples and usage notes for the pipeline. Raw project data is not stored here.",
        )
    )
    outputs.append(
        _write_simple_index(
            project_root / "golden_examples" / "README.md",
            "Golden Examples",
            "Golden fixtures and reference outputs used for behavior checks.",
        )
    )
    outputs.append(
        _write_simple_index(
            project_root / "templates" / "README.md",
            "Templates",
            "Template assets used by processing and plotting adapters.",
        )
    )
    return outputs


def write_structure_report(project_root: Path) -> Path:
    report = project_root / "docs" / "agent_reports" / "phase1_9_project_structure_report.md"
    lines = [
        "# Phase 1.9 Project Structure Report",
        "",
        "- Root entry docs kept at `README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, and `AGENT_HANDOFF.md`.",
        "- `docs/agent_reports/README.md` now indexes phase reports.",
        "- `output/reports/README.md` now indexes generated reports.",
        "- `scripts/`, `examples/`, `golden_examples/`, and `templates/` have lightweight README entrypoints.",
        "- No raw data directories were reorganized.",
        "- Phase 1.5 and Phase 1.6 result packages were not moved, renamed, or deleted.",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    (project_root / "output" / "reports" / "phase1_9_project_structure_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return report


def write_cleanup_report(project_root: Path) -> Path:
    candidates = []
    for rel in [".pytest_cache", "scripts/__pycache__"]:
        path = project_root / rel
        if path.exists():
            candidates.append(rel)
    for path in sorted((project_root / "src").rglob("__pycache__")) if (project_root / "src").exists() else []:
        candidates.append(str(path.relative_to(project_root)).replace("\\", "/"))

    reports = _ensure_dir(project_root / "output" / "reports")
    docs = _ensure_dir(project_root / "docs" / "agent_reports")
    pending = reports / "pending_cleanup_candidates.md"
    cleanup = docs / "phase1_9_cleanup_and_structure_report.md"
    cleanup_out = reports / "phase1_9_cleanup_and_structure_report.md"

    pending_lines = [
        "# Pending Cleanup Candidates",
        "",
        "These files are safe-looking cache or scratch candidates, but Phase 1.9 did not delete them automatically because tests may recreate caches.",
        "",
    ]
    if candidates:
        pending_lines.extend(f"- `{candidate}`" for candidate in sorted(set(candidates)))
    else:
        pending_lines.append("- No pending cleanup candidates found.")
    pending_lines.append("")
    pending.write_text("\n".join(pending_lines), encoding="utf-8")

    lines = [
        "# Phase 1.9 Cleanup and Structure Report",
        "",
        "- Automatic deletion performed: none.",
        "- Cleanup policy: uncertain files are recorded, not deleted.",
        "- Raw data tree touched: no.",
        "- F-drive backup touched: no.",
        "- Phase 1.5/1.6 formal results touched: no.",
        f"- Pending cleanup candidate list: `{pending.relative_to(project_root)}`",
        "",
    ]
    cleanup.write_text("\n".join(lines), encoding="utf-8")
    cleanup_out.write_text("\n".join(lines), encoding="utf-8")
    return cleanup


def write_agent_summary(project_root: Path, skill_payload: dict, package_dir: Path, journal_csv: Path) -> Path:
    summary = project_root / "docs" / "agent_reports" / "phase1_9_summary.md"
    lines = [
        "# Phase 1.9 Summary",
        "",
        f"- Origin plotting skill snapshot SHA256: `{skill_payload['skill_sha256']}`",
        f"- Phase 1.6 package audited for journal index: `{render_output_path(package_dir, project_root=project_root)}`",
        f"- Journal-ready index: `{journal_csv.relative_to(project_root)}`",
        "- Project structure index files refreshed.",
        "- Raw data and formal result packages were not moved or deleted.",
        "- No real Origin processing was launched.",
        "",
    ]
    summary.write_text("\n".join(lines), encoding="utf-8")
    return summary


def update_dashboard(project_root: Path, journal_csv: Path) -> Path:
    dashboard = _ensure_dir(project_root / "output" / "review_dashboard") / "phase1_9_origin_plotting_governance.md"
    lines = [
        "# Phase 1.9 Origin Plotting Governance",
        "",
        "- Plotting style source: `.agents/skills/originpro-graph-export/SKILL.md`.",
        "- Graph profile: cached Graph4.",
        "- Journal-ready index:",
        f"  `{journal_csv.relative_to(project_root)}`",
        "- Review the Phase 1.6 PNG/TIF/OPJU outputs against the skill snapshot before manuscript use.",
        "",
    ]
    dashboard.write_text("\n".join(lines), encoding="utf-8")
    index = project_root / "output" / "review_dashboard" / "index.md"
    if index.exists():
        text = index.read_text(encoding="utf-8")
        link = "- [Phase 1.9 Origin plotting governance](phase1_9_origin_plotting_governance.md)"
        if link not in text:
            index.write_text(text.rstrip() + "\n" + link + "\n", encoding="utf-8")
    return dashboard


def _write_phase_report_index(project_root: Path) -> Path:
    report_dir = _ensure_dir(project_root / "docs" / "agent_reports")
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(report_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        phase = path.stem.split("_", 2)
        key = "_".join(phase[:2]) if len(phase) >= 2 and phase[0] == "phase1" else "other"
        groups[key].append(path)
    lines = ["# Agent Reports", "", "Reports are grouped by phase for navigation; files remain in place.", ""]
    for phase, paths in sorted(groups.items()):
        lines.append(f"## {phase}")
        lines.append("")
        for path in paths:
            lines.append(f"- [{path.name}]({path.name})")
        lines.append("")
    out = report_dir / "README.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _write_output_report_index(project_root: Path) -> Path:
    report_dir = _ensure_dir(project_root / "output" / "reports")
    phase_counts = Counter()
    for path in report_dir.glob("*"):
        if path.is_file():
            stem = path.stem
            key = "_".join(stem.split("_", 2)[:2]) if stem.startswith("phase1_") else "other"
            phase_counts[key] += 1
    lines = [
        "# Output Reports",
        "",
        "Generated reports are retained here. Phase 1.9 adds this index so historical reports can be found without moving formal outputs.",
        "",
        "## Counts",
        "",
    ]
    for phase, count in sorted(phase_counts.items()):
        lines.append(f"- {phase}: {count}")
    lines.extend(
        [
            "",
            "## Phase 1.9 Key Files",
            "",
            "- `phase1_9_origin_plotting_skill_snapshot.json`",
            "- `phase1_9_journal_ready_index.csv`",
            "- `phase1_9_cleanup_and_structure_report.md`",
            "- `pending_cleanup_candidates.md`",
            "",
        ]
    )
    out = report_dir / "README.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _write_simple_index(path: Path, title: str, description: str) -> Path:
    _ensure_dir(path.parent)
    entries = []
    for child in sorted(path.parent.iterdir()):
        if child.name.lower() == "readme.md":
            continue
        entries.append(child.name + ("/" if child.is_dir() else ""))
    lines = [f"# {title}", "", description, "", "## Contents", ""]
    if entries:
        lines.extend(f"- `{entry}`" for entry in entries)
    else:
        lines.append("- No entries.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _load_material_color_lookup(project_root: Path) -> dict[str, str]:
    path = project_root / "output" / "reports" / "phase1_6_material_color_map.json"
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


def _package_import_status(package: str, module: str) -> dict:
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_project_path(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path
