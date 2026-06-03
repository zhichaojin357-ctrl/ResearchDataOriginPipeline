from __future__ import annotations

from dataclasses import dataclass, field
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.project import load_project_config
from src.core.runtime_paths import resolve_origin_helper, resolve_project_path
from src.origin.adapter import check_origin_available, write_origin_error


ELEMENT_REGION_RE = re.compile(r"(?P<element>[A-Z][a-z]?)(?P<orbital>\d+[spdf])", re.IGNORECASE)


@dataclass(frozen=True)
class XpsFitRecord:
    sample: str
    element: str
    region: str
    source_file: Path
    sheet_name: str
    raw_label: str
    background_label: str | None
    envelope_label: str | None
    residual_label: str | None
    component_labels: list[str]
    data: list[dict[str, float | str | None]]


@dataclass(frozen=True)
class XpsComparison:
    name: str
    element: str
    sample_a: str
    sample_b: str
    record_a: XpsFitRecord
    record_b: XpsFitRecord
    optional: bool = False


@dataclass(frozen=True)
class XpsHeterojunctionOptions:
    output_dir: Path
    with_origin: bool = False
    include_optional_three_sample_oxygen: bool = False
    force: bool = True


@dataclass(frozen=True)
class XpsComparisonPlan:
    comparisons: list[XpsComparison] = field(default_factory=list)
    manual_review: list[dict[str, Any]] = field(default_factory=list)


TASK_SUBDIRS = (
    "origin_projects",
    "figures_tif",
    "processed_tables",
    "metadata",
    "reports",
)
MAX_COMPONENTS_PER_SAMPLE_FOR_PLOT = 4
MAX_CU_COMPONENTS_PER_SAMPLE_FOR_PLOT = 5
MAX_PEAK_LABELS_PER_SAMPLE = 2
COMPONENT_GRADIENT_LEVELS = 16
XPS_STACKED_PALETTE = (16777216, 28471808, 8421504, 16818150, 16777216, 24354304, 8421504, 27752908)
COMPONENT_COLORS = ("#7CB7D8", "#D99AD8", "#F2B885", "#9DCB8E", "#B7A1DE", "#E89E9E")
SAMPLE_DISPLAY_NAMES = {
    "BOBC": "BiOBr₀.₅Cl₀.₅",
    "CWO": "CuWO₄",
    "BC": "BiCu-10",
}
LEGACY_XPS_INPUT_DIRS = {
    "BOBC": Path("F:/课题/LL/检测/XPS/BOBC拟合后"),
    "CWO": Path("F:/课题/LL/检测/XPS/CWO拟合后"),
    "BC": Path("F:/课题/LL/检测/XPS/BC拟合后"),
}
LEGACY_BC_CANDIDATES = (
    Path("F:/课题/LL/检测/XPS/26010989730/BC-11/bc拟合后的数据.xlsx"),
    Path("F:/课题/LL/检测/XPS/26010989730/bc拟合后的数据.xlsx"),
)


def discover_default_xps_sample_files(
    project_root: Path | None = None,
    *,
    include_bc_candidate: bool = True,
) -> tuple[dict[str, list[Path]], list[dict[str, Any]]]:
    sample_files: dict[str, list[Path]] = {}
    notes: list[dict[str, Any]] = []
    input_dirs = _configured_xps_input_dirs(project_root)
    for sample, folder in input_dirs.items():
        files = _excel_files_in_folder(folder)
        sample_files[sample] = files
        if not files:
            notes.append({"sample": sample, "folder": str(folder), "reason": "no_excel_files_in_official_folder"})
    if include_bc_candidate and not sample_files.get("BC"):
        candidate = next((path for path in _configured_bc_candidates(project_root) if path.exists()), None)
        if candidate:
            sample_files["BC"] = [candidate]
            notes.append(
                {
                    "sample": "BC",
                    "source_file": str(candidate),
                    "reason": "bc_excel_candidate_used_because_official_folder_has_only_data_grid",
                }
            )
    return sample_files, notes


def _configured_xps_input_dirs(project_root: Path | None) -> dict[str, Path]:
    config = _xps_config(project_root)
    env_keys = {
        "BOBC": "RESEARCHDATAORIGINPIPELINE_XPS_BOBC_DIR",
        "CWO": "RESEARCHDATAORIGINPIPELINE_XPS_CWO_DIR",
        "BC": "RESEARCHDATAORIGINPIPELINE_XPS_BC_DIR",
    }
    config_keys = {
        "BOBC": "bobc_input_dir",
        "CWO": "cwo_input_dir",
        "BC": "bc_input_dir",
    }
    resolved: dict[str, Path] = {}
    for sample, legacy in LEGACY_XPS_INPUT_DIRS.items():
        value = os.environ.get(env_keys[sample]) or str(config.get(config_keys[sample], "")).strip()
        resolved[sample] = _resolve_optional_project_path(project_root, value) if value else legacy
    return resolved


def _configured_bc_candidates(project_root: Path | None) -> tuple[Path, ...]:
    config = _xps_config(project_root)
    raw = os.environ.get("RESEARCHDATAORIGINPIPELINE_XPS_BC_CANDIDATES") or str(config.get("bc_candidate_files", "")).strip()
    if raw:
        paths = [item.strip() for item in raw.replace("|", ";").split(";") if item.strip()]
        return tuple(_resolve_optional_project_path(project_root, item) for item in paths)
    return LEGACY_BC_CANDIDATES


def _xps_config(project_root: Path | None) -> dict[str, Any]:
    if project_root is None:
        return {}
    config = load_project_config(project_root, Path("config/default.yaml"))
    section = config.get("xps_heterojunction", {})
    return section if isinstance(section, dict) else {}


def _resolve_optional_project_path(project_root: Path | None, value: str | Path) -> Path:
    if project_root is None:
        return Path(value)
    return resolve_project_path(project_root, value)


def load_xps_fit_workbooks(sample_files: dict[str, list[Path]]) -> tuple[list[XpsFitRecord], list[dict[str, Any]]]:
    records: list[XpsFitRecord] = []
    manual_review: list[dict[str, Any]] = []
    for sample, files in sample_files.items():
        if not files:
            manual_review.append({"sample": sample, "reason": "no_excel_files_in_configured_input"})
            continue
        for source_file in files:
            if not source_file.exists():
                manual_review.append({"sample": sample, "source_file": str(source_file), "reason": "source_file_missing"})
                continue
            try:
                workbook = pd.ExcelFile(source_file)
            except Exception as exc:
                manual_review.append({"sample": sample, "source_file": str(source_file), "reason": "workbook_open_failed", "error": str(exc)})
                continue
            for sheet_name in workbook.sheet_names:
                region = _region_from_sheet(sheet_name)
                if not region:
                    continue
                try:
                    frame = pd.read_excel(source_file, sheet_name=sheet_name, header=None)
                    record = _extract_sheet_record(sample, source_file, sheet_name, region, frame)
                except Exception as exc:
                    manual_review.append(
                        {
                            "sample": sample,
                            "source_file": str(source_file),
                            "sheet_name": sheet_name,
                            "reason": "sheet_parse_failed",
                            "error": str(exc),
                        }
                    )
                    continue
                if record is None:
                    manual_review.append(
                        {
                            "sample": sample,
                            "source_file": str(source_file),
                            "sheet_name": sheet_name,
                            "reason": "fit_columns_not_recognized",
                        }
                    )
                    continue
                records.append(record)
    return records, manual_review


def build_comparison_plan(
    records: list[XpsFitRecord],
    manual_review: list[dict[str, Any]],
    options: XpsHeterojunctionOptions,
) -> XpsComparisonPlan:
    selected = _select_best_records(records)
    review = list(manual_review)
    comparisons: list[XpsComparison] = []

    bobc_elements = {element for sample, element in selected if sample == "BOBC"}
    cwo_elements = {element for sample, element in selected if sample == "CWO"}
    bc_elements = {element for sample, element in selected if sample == "BC"}

    for element in sorted(bobc_elements):
        if element in bc_elements:
            comparisons.append(_comparison(element, "BOBC", "BC", selected))
        else:
            review.append({"sample": "BC", "element": element, "reason": "missing_bc_counterpart", "comparison": f"BOBC vs BC {element}"})

    for element in sorted(cwo_elements):
        if element in bc_elements:
            comparisons.append(_comparison(element, "CWO", "BC", selected))
        else:
            review.append({"sample": "BC", "element": element, "reason": "missing_bc_counterpart", "comparison": f"CWO vs BC {element}"})

    if not options.include_optional_three_sample_oxygen:
        comparisons = [item for item in comparisons if item.name != "XPS_O_BOBC_CWO_BC_stacked"]

    return XpsComparisonPlan(comparisons=comparisons, manual_review=review)


def run_xps_heterojunction_stacked(
    project_root: Path,
    sample_files: dict[str, list[Path]],
    options: XpsHeterojunctionOptions,
    pre_manual_review: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    output_dir = _safe_task_output_dir(project_root, options.output_dir)
    dirs = {name: output_dir / name for name in TASK_SUBDIRS}
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    records, manual_review = load_xps_fit_workbooks(sample_files)
    manual_review = [*(pre_manual_review or []), *manual_review]
    plan = build_comparison_plan(records, manual_review, options)
    figure_rows: list[dict[str, Any]] = []

    for comparison in plan.comparisons:
        processed_csv = dirs["processed_tables"] / f"{comparison.name}.csv"
        plot_csv = dirs["processed_tables"] / f"{comparison.name}_origin_plot.csv"
        peak_details = _comparison_peak_details(comparison)
        peak_table = dirs["processed_tables"] / f"{comparison.name}_peak_annotations.csv"
        peaks = [float(item["binding_energy_eV"]) for item in peak_details]
        _write_comparison_tables(comparison, processed_csv, plot_csv)
        _write_peak_annotation_table(peak_table, peak_details)
        origin_artifacts = {"ok": False, "origin_file": None, "figure_tif": None, "preview_png": None, "message": ""}
        if options.with_origin:
            origin_artifacts = _export_origin_for_comparison(project_root, comparison, plot_csv, dirs, peak_details)
        metadata = {
            "dataset_id": comparison.name,
            "data_type": "XPS",
            "comparison": f"{comparison.sample_a} vs {comparison.sample_b}",
            "element": comparison.element,
            "source_files": [str(comparison.record_a.source_file), str(comparison.record_b.source_file)],
            "sheets": [comparison.record_a.sheet_name, comparison.record_b.sheet_name],
            "processed_data": str(processed_csv),
            "origin_plot_input": str(plot_csv),
            "peak_annotation_table": str(peak_table),
            "manual_check_required": True,
            "manual_check_items": [
                "confirm XPS binding-energy calibration, fitted peak positions, and component assignments",
                "non-in-situ fitted XPS comparison only; no valence or mechanism conclusion generated",
            ],
            "forbidden_claims": [
                "do not assign valence states automatically",
                "do not infer electron-transfer direction or heterojunction mechanism",
                "do not claim proof of S-scheme mechanism",
            ],
            "peak_annotations": peak_details,
            "peak_annotations_eV": peaks,
            "origin_file": str(origin_artifacts["origin_file"]) if origin_artifacts.get("origin_file") else None,
            "figure_tif": str(origin_artifacts["figure_tif"]) if origin_artifacts.get("figure_tif") else None,
            "preview_png": str(origin_artifacts["preview_png"]) if origin_artifacts.get("preview_png") else None,
            "processing_status": "planned_no_origin" if not options.with_origin else ("success" if origin_artifacts.get("ok") else "origin_failed"),
            "origin_message": origin_artifacts.get("message", ""),
        }
        metadata_path = dirs["metadata"] / f"{comparison.name}_metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        figure_rows.append(
            {
                "name": comparison.name,
                "element": comparison.element,
                "comparison": f"{comparison.sample_a} vs {comparison.sample_b}",
                "sample_a_file": str(comparison.record_a.source_file),
                "sample_b_file": str(comparison.record_b.source_file),
                "processed_csv": str(processed_csv),
                "origin_plot_csv": str(plot_csv),
                "peak_annotation_csv": str(peak_table),
                "metadata": str(metadata_path),
                "origin_file": str(origin_artifacts["origin_file"]) if origin_artifacts.get("origin_file") else "",
                "figure_tif": str(origin_artifacts["figure_tif"]) if origin_artifacts.get("figure_tif") else "",
                "preview_png": str(origin_artifacts["preview_png"]) if origin_artifacts.get("preview_png") else "",
                "peak_annotations_eV": "; ".join(f"{peak:.2f}" for peak in peaks),
                "peak_annotation_labels": "; ".join(_format_peak_detail(item) for item in peak_details),
                "status": metadata["processing_status"],
            }
        )

    _write_manual_review(dirs["reports"] / "manual_review.csv", plan.manual_review)
    _write_summary_reports(dirs["reports"], sample_files, records, plan, figure_rows, options)

    result = {
        "output_dir": str(output_dir),
        "comparison_count": len(plan.comparisons),
        "manual_review_count": len(plan.manual_review),
        "will_launch_origin": bool(options.with_origin),
        "figures": figure_rows,
        "manual_review": plan.manual_review,
    }
    (dirs["reports"] / "xps_heterojunction_stacked_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _comparison(element: str, source_sample: str, composite_sample: str, selected: dict[tuple[str, str], XpsFitRecord]) -> XpsComparison:
    return XpsComparison(
        name=f"XPS_{element}_{source_sample}_vs_{composite_sample}_stacked",
        element=element,
        sample_a=source_sample,
        sample_b=composite_sample,
        record_a=selected[(source_sample, element)],
        record_b=selected[(composite_sample, element)],
    )


def _write_comparison_tables(comparison: XpsComparison, processed_csv: Path, plot_csv: Path) -> None:
    processed_csv.parent.mkdir(parents=True, exist_ok=True)
    plot_csv.parent.mkdir(parents=True, exist_ok=True)
    with processed_csv.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "sample",
            "binding_energy_eV",
            "raw_intensity",
            "background",
            "envelope",
            "residual",
            "component_label",
            "component_intensity",
            "source_file",
            "sheet_name",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in (comparison.record_a, comparison.record_b):
            for row in record.data:
                base = {
                    "sample": record.sample,
                    "binding_energy_eV": row.get("binding_energy_eV"),
                    "raw_intensity": row.get("raw_intensity"),
                    "background": row.get("background"),
                    "envelope": row.get("envelope"),
                    "residual": row.get("residual"),
                    "source_file": str(record.source_file),
                    "sheet_name": record.sheet_name,
                }
                component_keys = [_component_key(label) for label in record.component_labels]
                if not component_keys:
                    writer.writerow({**base, "component_label": "", "component_intensity": ""})
                for label, key in zip(record.component_labels, component_keys):
                    writer.writerow({**base, "component_label": label, "component_intensity": row.get(key)})

    headers, rows = _stacked_plot_rows(comparison)
    with plot_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _export_origin_for_comparison(
    project_root: Path,
    comparison: XpsComparison,
    plot_csv: Path,
    output_dirs: dict[str, Path],
    peak_details: list[dict[str, Any]],
) -> dict[str, Any]:
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, f"{comparison.name}: {message}")
        return {"ok": False, "origin_file": None, "figure_tif": None, "preview_png": None, "message": f"Origin unavailable: {message}"}
    origin_file = output_dirs["origin_projects"] / f"{comparison.name}.opju"
    figure_tif = output_dirs["figures_tif"] / f"{comparison.name}.tif"
    job_dir = output_dirs["origin_projects"] / "origin_jobs"
    job_dir.mkdir(parents=True, exist_ok=True)
    preview_png = job_dir / f"{comparison.name}.png"
    page_name = _safe_origin_page_name(comparison.name)
    job_script = job_dir / f"{comparison.name}_origin_xps_renderer.py"
    for artifact in (origin_file, figure_tif):
        if artifact.exists():
            artifact.unlink()
    script = _build_direct_origin_xps_script(comparison, plot_csv, origin_file, preview_png, figure_tif, page_name, peak_details)
    job_script.write_text(script, encoding="utf-8")
    completed = None
    for attempt in range(3):
        try:
            completed = subprocess.run(
                [sys.executable, str(job_script)],
                text=True,
                capture_output=True,
                timeout=600,
            )
        except Exception as exc:
            write_origin_error(project_root, f"{comparison.name}: {exc}")
            return {"ok": False, "origin_file": None, "figure_tif": None, "preview_png": None, "message": str(exc)}
        if completed.returncode == 0:
            break
        try:
            _wait_for_no_origin_process(timeout_seconds=30.0)
        except RuntimeError:
            _stop_headless_origin_processes()
            _wait_for_no_origin_process(timeout_seconds=30.0)
        time.sleep(1.0 + attempt)
    if completed is None or completed.returncode:
        details = (completed.stderr or completed.stdout or "Origin XPS renderer failed").strip()
        write_origin_error(project_root, f"{comparison.name}: {details}")
        return {"ok": False, "origin_file": None, "figure_tif": None, "preview_png": None, "message": details}
    missing = [path for path in (origin_file, figure_tif) if not path.exists() or path.stat().st_size == 0]
    if missing:
        message = "Missing or empty Origin artifacts: " + ", ".join(str(path) for path in missing)
        write_origin_error(project_root, f"{comparison.name}: {message}")
        return {"ok": False, "origin_file": origin_file if origin_file.exists() else None, "figure_tif": figure_tif if figure_tif.exists() else None, "preview_png": preview_png if preview_png.exists() else None, "message": message}
    return {"ok": True, "origin_file": origin_file, "figure_tif": figure_tif, "preview_png": None, "message": "Origin COM export succeeded"}


def _display_sample_name(sample: str) -> str:
    return SAMPLE_DISPLAY_NAMES.get(sample, sample)


def _record_binding_energy_bounds(record: XpsFitRecord) -> tuple[float, float] | None:
    values: list[float] = []
    for row in record.data:
        binding = _to_float(row.get("binding_energy_eV"))
        if binding is None:
            continue
        has_signal = any(_to_float(row.get(key)) is not None for key in ("raw_intensity", "background", "envelope"))
        if has_signal:
            values.append(binding)
    if not values:
        return None
    return min(values), max(values)


def _record_binding_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    deltas = [b - a for a, b in zip(values, values[1:])]
    deltas = [abs(value) for value in deltas if value]
    if not deltas:
        return 0.0
    deltas.sort()
    return deltas[len(deltas) // 2]


def _record_signal_regions(record: XpsFitRecord) -> list[tuple[float, float]]:
    raw_values = [row["raw_intensity"] for row in record.data if isinstance(row.get("raw_intensity"), (int, float))]
    if not raw_values:
        return []
    raw_min = min(raw_values)
    raw_max = max(raw_values)
    raw_span = raw_max - raw_min
    floor = max(raw_span * 0.0025, 1e-6)

    candidate_bindings: list[float] = []
    for row in record.data:
        binding = _to_float(row.get("binding_energy_eV"))
        raw = _to_float(row.get("raw_intensity"))
        if binding is None or raw is None:
            continue
        background = _to_float(row.get("background"))
        envelope = _to_float(row.get("envelope"))
        if (
            background is not None
            and envelope is not None
            and raw <= raw_min + floor
            and abs(raw - background) <= floor
            and abs(raw - envelope) <= floor
        ):
            continue
        candidate_bindings.append(binding)
    if len(candidate_bindings) < 2:
        return []

    candidate_bindings.sort()
    step = _record_binding_step(candidate_bindings)
    if step <= 0:
        return [(min(candidate_bindings), max(candidate_bindings))]

    intervals: list[tuple[float, float]] = []
    gap = max(step * 1.8, 1e-6)
    start = candidate_bindings[0]
    previous = candidate_bindings[0]
    for value in candidate_bindings[1:]:
        if value - previous > gap:
            intervals.append((start, previous))
            start = value
        previous = value
    intervals.append((start, previous))
    return intervals


def _comparison_x_axis_range(comparison: XpsComparison, fallback_x_values: list[float]) -> tuple[float, float]:
    bounds = [_record_binding_energy_bounds(record) for record in (comparison.record_a, comparison.record_b)]
    signal_regions = [_record_signal_regions(record) for record in (comparison.record_a, comparison.record_b)]
    if all(signal_regions):
        overlaps: list[tuple[float, float]] = []
        for region_a in signal_regions[0]:
            for region_b in signal_regions[1]:
                overlap_min = max(region_a[0], region_b[0])
                overlap_max = min(region_a[1], region_b[1])
                if overlap_min < overlap_max:
                    overlaps.append((overlap_min, overlap_max))
        if overlaps:
            overlap_min, overlap_max = max(overlaps, key=lambda item: item[1] - item[0])
            return overlap_max, overlap_min

    if any(item is None for item in bounds):
        x_min = min(fallback_x_values)
        x_max = max(fallback_x_values)
        return x_max, x_min
    data_min = max(item[0] for item in bounds)
    data_max = min(item[1] for item in bounds)
    if data_min >= data_max:
        x_min = min(fallback_x_values)
        x_max = max(fallback_x_values)
        return x_max, x_min
    return data_max, data_min


def _build_direct_origin_xps_script(
    comparison: XpsComparison,
    plot_csv: Path,
    origin_file: Path,
    preview_png: Path,
    figure_tif: Path,
    page_name: str,
    peak_details: list[dict[str, Any]],
) -> str:
    header = _csv_header(plot_csv)
    x_values = _csv_x_values(plot_csv)
    x_from, x_to = _comparison_x_axis_range(comparison, x_values)
    x_span = abs(x_from - x_to)
    y_min, y_max = _csv_display_y_range(plot_csv, header)
    y_pad = max((y_max - y_min) * 0.28, 0.28)
    payload = {
        "plot_csv": str(plot_csv),
        "origin_file": str(origin_file),
        "preview_png": str(preview_png),
        "figure_tif": str(figure_tif),
        "page_name": page_name,
        "worksheet_name": _safe_origin_page_name(f"{comparison.name}_Data"),
        "series_labels": header[1:],
        "x_from": x_from,
        "x_to": x_to,
        "x_step": _nice_step(x_span),
        "y_from": y_min - y_pad,
        "y_to": y_max + y_pad,
        "peaks": peak_details,
        "component_colors": COMPONENT_COLORS,
        "gradient_levels": COMPONENT_GRADIENT_LEVELS,
        "sample_name_map": {sample: _display_sample_name(sample) for sample in (comparison.sample_a, comparison.sample_b)},
    }
    return f"""from __future__ import annotations

import csv
import json
import re
import sys

import originpro as op
from originpro.utils import ocolor

payload = json.loads({json.dumps(json.dumps(payload, ensure_ascii=False))})


def to_float(value):
    if value == "" or value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_columns(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        cols = [[] for _ in headers]
        for row in reader:
            for index in range(len(headers)):
                cols[index].append(to_float(row[index]) if index < len(row) else None)
    return headers, cols


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def blend_to_white(hex_color, fraction):
    r, g, b = hex_to_rgb(hex_color)
    return tuple(int(255 - (255 - channel) * fraction) for channel in (r, g, b))


def color_cmd(rgb):
    return "color(%d,%d,%d)" % rgb


def sample_from_label(label):
    return label.split(" ", 1)[0] if " " in label else label


def set_label_style(label, size, color=1):
    if label is None:
        return
    label.set_int("font", 67)
    label.set_float("fsize", size)
    label.set_int("bold", 1)
    label.set_int("color", color)


op.set_show(False)
try:
    headers, columns = read_columns(payload["plot_csv"])
    op.new()
    wks = op.new_sheet("w", payload["worksheet_name"])
    wks.cols = len(headers)
    for index, (label, values) in enumerate(zip(headers, columns)):
        axis = "X" if index == 0 else "Y"
        wks.from_list(index, values, lname=label, axis=axis)

    graph = op.new_graph(payload["page_name"])
    graph.name = payload["page_name"]
    layer = graph[0]
    plots = []
    for col_index, series_label in enumerate(headers[1:], start=1):
        plot = layer.add_plot(wks, coly=col_index, colx=0, type="line")
        plots.append(plot)
        lower = series_label.lower()
        if " fill upper " in lower:
            level_text = series_label.rsplit("fill upper", 1)[1].strip()
            level = int(level_text) if level_text.isdigit() else 1
            component_match = re.search(r"component (\\d+)", series_label)
            component_index = int(component_match.group(1)) if component_match else 1
            color_match = re.search(r"color (\\d+)", series_label)
            color_index = int(color_match.group(1)) if color_match else component_index
            base = payload["component_colors"][(color_index - 1) % len(payload["component_colors"])]
            fraction = max(0.14, level / payload["gradient_levels"])
            rgb = blend_to_white(base, fraction)
            color_value = ocolor(rgb)
            plot.set_cmd("-lw 0", "-c " + color_cmd(rgb))
            plot.set_fill_area(above=color_value, type=9, below=color_value)
        elif " fill lower " in lower:
            plot.set_cmd("-lw 0", "-c color(255,255,255)")
        elif " component " in lower and " line" in lower:
            component_match = re.search(r"component (\\d+)", series_label)
            component_index = int(component_match.group(1)) if component_match else 1
            color_match = re.search(r"color (\\d+)", series_label)
            color_index = int(color_match.group(1)) if color_match else component_index
            plot.color = payload["component_colors"][(color_index - 1) % len(payload["component_colors"])]
            plot.set_cmd("-lw 1.1")
        elif " measured" in lower:
            plot.color = "#B7B7B7"
            plot.set_cmd("-lw 1.0")
        elif "backgnd" in lower or "background" in lower:
            plot.color = "#8E8E8E"
            plot.set_cmd("-lw 1.1")
        elif "envelope" in lower:
            plot.color = "#000000"
            plot.set_cmd("-lw 2.4")

    layer.rescale()
    for prop, value in (
        ("x.from", payload["x_from"]),
        ("x.to", payload["x_to"]),
        ("x.inc", payload["x_step"]),
        ("y.from", payload["y_from"]),
        ("y.to", payload["y_to"]),
        ("y.ticks", 0),
        ("y.showLabels", 0),
    ):
        try:
            if isinstance(value, int):
                layer.set_int(prop, value)
            else:
                layer.set_float(prop, value)
        except Exception:
            pass

    for axis_obj_name, text in (("XB", r"\\b(Binding Energy / eV)"), ("YL", r"\\b(Intensity / a.u.)")):
        label = layer.label(axis_obj_name)
        if label is not None:
            label.text = text
            set_label_style(label, 36)
    layer.tickstyle = 1
    op.lt_exec("layer.x.label.pt=36; layer.x.label.bold=1; layer.y.label.pt=36; layer.y.label.bold=1; YL.X+=4; layer.x.tick.label.pt=30; layer.x.tick.label.bold=1; layer.x.tickthickness=3; layer.x.thickness=3; layer.y.showLabels=0; layer.y.ticks=0; layer.y.ticklength=0; layer.y.mticklength=0; layer.y.thickness=3; layer.y2.ticks=0; layer.y2.showLabels=0; layer.y2.showAxes=0; layer.x2.showAxes=0; layer.x2.ticks=0; layer.x2.showLabels=0;")

    legend = layer.label("Legend")
    if legend is not None:
        try:
            legend.remove()
        except Exception:
            pass

    x_min, x_max = min(payload["x_from"], payload["x_to"]), max(payload["x_from"], payload["x_to"])
    y_min, y_max = min(payload["y_from"], payload["y_to"]), max(payload["y_from"], payload["y_to"])
    y_span = y_max - y_min
    sample_order = []
    for series_label in payload["series_labels"]:
        sample = sample_from_label(series_label)
        if sample not in sample_order:
            sample_order.append(sample)
    sample_name_map = payload.get("sample_name_map", {{}})
    for sample_index, sample in enumerate(sample_order[:2]):
        y_label = sample_index * 1.45 + 0.18
        sample_label = layer.add_label(sample_name_map.get(sample, sample), x_max - (x_max - x_min) * 0.06, y_label)
        if sample_label is not None:
            sample_label.set_int("attach", 0)
            sample_label.set_float("x1", x_max - (x_max - x_min) * 0.06)
            sample_label.set_float("y1", y_label)
            set_label_style(sample_label, 19)

    peaks_by_sample = {{sample: [] for sample in sample_order}}
    for peak in payload["peaks"]:
        peaks_by_sample.setdefault(str(peak.get("sample") or ""), []).append(peak)
    label_x_span = x_max - x_min
    for sample_index, sample in enumerate(sample_order[:2]):
        sample_peaks = sorted(peaks_by_sample.get(sample, []), key=lambda item: float(item["binding_energy_eV"]), reverse=True)
        label_y = min(sample_index * 1.45 + 1.30, y_max - y_span * 0.08)
        for peak_index, peak in enumerate(sample_peaks):
            x = float(peak["binding_energy_eV"])
            x_shift = label_x_span * (0.055 if peak_index % 2 == 0 else -0.01)
            label_x = max(x_min + label_x_span * 0.20, min(x + x_shift, x_max - label_x_span * 0.20))
            y = max(y_min + y_span * 0.12, label_y + peak_index * y_span * 0.035)
            assignment = str(peak.get("peak_assignment") or "").strip()
            text = ((assignment + "\\n") if assignment else "") + ("%.2f eV" % x)
            label = layer.add_label(text, label_x, y)
            if label is not None:
                label.set_int("attach", 0)
                label.set_float("x1", label_x)
                label.set_float("y1", y)
                set_label_style(label, 16, 1)
    op.lt_exec("page.width=6432; page.height=4923; layer.left=17.89; layer.top=11.6; layer.width=68.19; layer.height=71.81;")
    if not op.save(payload["origin_file"]):
        raise RuntimeError("failed to save Origin project")
    exported_png = graph.save_fig(payload["preview_png"], type="png", replace=True, width=2400)
    if not exported_png:
        raise RuntimeError("failed to export PNG")
    exported_tif = graph.save_fig(payload["figure_tif"], type="tif", replace=True, width=3600)
    if not exported_tif:
        raise RuntimeError("failed to export TIF")
finally:
    op.exit()
"""


def _build_xps_origin_script(
    comparison: XpsComparison,
    plot_csv: Path,
    origin_file: Path,
    preview_dir: Path,
    page_name: str,
    project_root: Path | None = None,
) -> str:
    header = _csv_header(plot_csv)
    x_values = _csv_x_values(plot_csv)
    x_from = max(x_values)
    x_to = min(x_values)
    x_step = _nice_step(abs(x_from - x_to))
    y_min, y_max = _csv_y_range(plot_csv)
    y_pad = (y_max - y_min) * 0.08 if y_max > y_min else 1.0
    group = (
        "@{\n"
        f"  DataFile = {_ps_quote(plot_csv)}\n"
        f"  PageName = {_ps_quote(page_name)}\n"
        f"  ColumnCount = {len(header)}\n"
        f"  Labels = {_ps_array(tuple(header[1:]))}\n"
        f"  Palette = {_ps_int_array(XPS_STACKED_PALETTE)}\n"
        "  PlotType = '200'\n"
        "  XTitle = 'Binding Energy / eV'\n"
        "  YTitle = 'Intensity / a.u.'\n"
        f"  XFrom = {x_from}\n"
        f"  XTo = {x_to}\n"
        f"  XStep = {x_step}\n"
        f"  YFrom = {y_min - y_pad}\n"
        f"  YTo = {y_max + y_pad}\n"
        "}"
    )
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$groups = @({group})",
            f"& {_ps_quote(resolve_origin_helper(project_root or Path.cwd()))} -ReferenceGraph 'Graph4' -OutputOpju {_ps_quote(origin_file)} -ExportDir {_ps_quote(preview_dir)} -Groups $groups -Headless -CloseOrigin",
            f"if (-not (Test-Path -LiteralPath {_ps_quote(origin_file)})) {{ throw 'OPJU was not exported.' }}",
            f"if (-not (Test-Path -LiteralPath {_ps_quote(preview_dir / (page_name + '.png'))})) {{ throw 'PNG preview was not exported.' }}",
        ]
    ) + "\n"


def _export_tif_from_opju(origin_file: Path, page_name: str, figure_tif: Path) -> None:
    figure_tif.parent.mkdir(parents=True, exist_ok=True)
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$app = New-Object -ComObject Origin.Application",
            "$app.Visible = 0",
            f"if (-not $app.Load({_ps_quote(str(origin_file).replace(chr(92), '/'))})) {{ throw 'Failed to load OPJU for TIF export.' }}",
            (
                "$app.Execute("
                + _ps_quote(
                    f"win -a {page_name}; expGraph type:=tif path:=\"{str(figure_tif.parent).replace(chr(92), '/')}\" filename:=\"{figure_tif.stem}\" overwrite:=replace;"
                )
                + ") | Out-Null"
            ),
            "$app.Exit() | Out-Null",
        ]
    ) + "\n"
    script_path = origin_file.parent / "origin_jobs" / f"{figure_tif.stem}_export_tif.ps1"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8-sig")
    completed = None
    for attempt in range(3):
        _wait_for_no_origin_process()
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            text=True,
            capture_output=True,
            timeout=180,
        )
        _wait_for_no_origin_process()
        if completed.returncode == 0 and figure_tif.exists() and figure_tif.stat().st_size > 0:
            break
        time.sleep(2.0 + attempt)
    if completed is None or completed.returncode:
        details = (completed.stderr or completed.stdout or "Origin TIF export failed").strip()
        raise RuntimeError(details)
    if not figure_tif.exists() or figure_tif.stat().st_size == 0:
        raise RuntimeError(f"Origin did not export TIF: {figure_tif}")


def _annotate_origin_graph(
    origin_file: Path,
    page_name: str,
    preview_png: Path,
    figure_tif: Path,
    peak_details: list[dict[str, Any]],
    series_labels: list[str],
) -> None:
    if not peak_details:
        return
    _wait_for_no_origin_process()
    preview_png.parent.mkdir(parents=True, exist_ok=True)
    figure_tif.parent.mkdir(parents=True, exist_ok=True)
    script_path = origin_file.parent / "origin_jobs" / f"{preview_png.stem}_annotate.py"
    sample_name_map: dict[str, str] = {}
    for series_label in series_labels:
        sample = series_label.split(" ", 1)[0] if " " in series_label else series_label
        if sample not in sample_name_map:
            sample_name_map[sample] = _display_sample_name(sample)
    payload = {
        "origin_file": str(origin_file),
        "page_name": page_name,
        "preview_png": str(preview_png),
        "figure_tif": str(figure_tif),
        "peaks": peak_details,
        "series_labels": series_labels,
        "sample_name_map": sample_name_map,
    }
    script = f"""from __future__ import annotations

import json
import originpro as op
from originpro.utils import ocolor

payload = json.loads({json.dumps(json.dumps(payload, ensure_ascii=False))})

BASE_COLORS = {json.dumps(COMPONENT_COLORS)}

def _hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def _blend_to_white(hex_color, fraction):
    r, g, b = _hex_to_rgb(hex_color)
    return tuple(int(255 - (255 - channel) * fraction) for channel in (r, g, b))

def _color_cmd(rgb):
    return "color(%d,%d,%d)" % rgb

def _sample_from_label(label):
    return label.split(" ", 1)[0] if " " in label else label

op.set_show(False)
try:
    if not op.open(payload["origin_file"]):
        raise RuntimeError("failed to open Origin project")
    graph = op.find_graph(payload["page_name"])
    if graph is None:
        raise RuntimeError("graph page not found: " + payload["page_name"])
    layer = graph[0]
    x_from = layer.get_float("x.from")
    x_to = layer.get_float("x.to")
    x_min, x_max = min(x_from, x_to), max(x_from, x_to)
    y_from = layer.get_float("y.from")
    y_to = layer.get_float("y.to")
    y_min, y_max = min(y_from, y_to), max(y_from, y_to)
    y_span = y_max - y_min
    plots = layer.plot_list()
    for index, (plot, series_label) in enumerate(zip(plots, payload["series_labels"]), start=1):
        lower = series_label.lower()
        if " fill upper " in lower:
            parts = series_label.rsplit("fill upper", 1)
            level = int(parts[1].strip()) if len(parts) == 2 else 1
            component_match = __import__("re").search(r"component (\\d+)", series_label)
            component_index = int(component_match.group(1)) if component_match else 1
            base = BASE_COLORS[(component_index - 1) % len(BASE_COLORS)]
            fraction = max(0.16, level / {COMPONENT_GRADIENT_LEVELS})
            rgb = _blend_to_white(base, fraction)
            color_value = ocolor(rgb)
            plot.set_cmd("-lw 0", "-c " + _color_cmd(rgb))
            plot.set_fill_area(above=color_value, type=9, below=color_value)
        elif " fill lower " in lower:
            plot.set_cmd("-lw 0", "-c color(255,255,255)")
        elif " component " in lower and " line" in lower:
            component_match = __import__("re").search(r"component (\\d+)", series_label)
            component_index = int(component_match.group(1)) if component_match else 1
            plot.color = BASE_COLORS[(component_index - 1) % len(BASE_COLORS)]
            plot.set_cmd("-lw 1.2")
        elif " measured" in lower:
            plot.color = "#B8B8B8"
            plot.set_cmd("-lw 1.0")
        elif "backgnd" in lower or "background" in lower:
            plot.color = "#8A8A8A"
            plot.set_cmd("-lw 1.1")
        elif "envelope" in lower:
            plot.color = "#000000"
            plot.set_cmd("-lw 2.2")
    for prop, value in (
        ("x2.showAxes", 0),
        ("x2.ticks", 0),
        ("x2.showLabels", 0),
        ("y.ticks", 0),
        ("y.label.show", 0),
        ("y2.showAxes", 0),
        ("y2.ticks", 0),
        ("y2.showLabels", 0),
    ):
        try:
            layer.set_int(prop, value)
        except Exception:
            pass
    op.lt_exec("layer.x.tick.label.bold=1; layer.x.tick.label.pt=30; layer.x.tickthickness=3; layer.x.thickness=3;")
    layer.tickstyle = 1
    legend = layer.label("Legend")
    if legend is not None:
        try:
            legend.remove()
        except Exception:
            pass
    sample_order = []
    for series_label in payload["series_labels"]:
        sample = _sample_from_label(series_label)
        if sample not in sample_order:
            sample_order.append(sample)
    for sample_index, sample in enumerate(sample_order[:2]):
        y_label = sample_index * 1.45 + 0.28
        sample_label = layer.add_label(payload["sample_name_map"].get(sample, sample), x_max - (x_max - x_min) * 0.08, y_label)
        if sample_label is not None:
            sample_label.set_int("attach", 0)
            sample_label.set_int("font", 67)
            sample_label.set_float("fsize", 16)
            sample_label.set_int("bold", 1)
            sample_label.set_int("color", 1)
    for index, peak in enumerate(payload["peaks"]):
        x = float(peak["binding_energy_eV"])
        y = float(peak.get("normalized_y", y_min + y_span * 0.5))
        y = max(y_min + y_span * 0.08, min(y, y_max - y_span * 0.08))
        assignment = str(peak.get("peak_assignment") or "").strip()
        text = (assignment + "\\n" if assignment else "") + ("%.2f eV" % x)
        label = layer.add_label(text, x, y)
        if label is None:
            continue
        label.set_int("attach", 0)
        label.set_int("font", 67)
        label.set_float("fsize", 13)
        label.set_int("bold", 1)
        label.set_int("color", 8421504)
        label.set_float("x1", max(x_min, min(x, x_max)))
        label.set_float("y1", y)
    op.save(payload["origin_file"])
    exported = graph.save_fig(payload["preview_png"], type="png", replace=True, width=2400)
    if not exported:
        raise RuntimeError("failed to export annotated PNG")
    exported_tif = graph.save_fig(payload["figure_tif"], type="tif", replace=True, width=3600)
    if not exported_tif:
        raise RuntimeError("failed to export annotated TIF")
finally:
    op.exit()
"""
    script_path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        text=True,
        capture_output=True,
        timeout=240,
    )
    try:
        _wait_for_no_origin_process()
    except RuntimeError:
        _stop_headless_origin_processes()
        try:
            _wait_for_no_origin_process(timeout_seconds=30.0)
        except RuntimeError:
            pass
    if completed.returncode:
        details = (completed.stderr or completed.stdout or "Origin annotation script failed").strip()
        raise RuntimeError(details)
    if not preview_png.exists() or preview_png.stat().st_size == 0:
        raise RuntimeError(f"Origin did not export annotated PNG: {preview_png}")
    if not figure_tif.exists() or figure_tif.stat().st_size == 0:
        raise RuntimeError(f"Origin did not export annotated TIF: {figure_tif}")


def _wait_for_no_origin_process(timeout_seconds: float = 90.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Process -Name Origin* -ErrorAction SilentlyContinue"],
            text=True,
            capture_output=True,
            timeout=10,
        )
        if not result.stdout.strip():
            return
        time.sleep(0.5)
    raise RuntimeError("Origin remained running after export.")


def _stop_headless_origin_processes() -> None:
    command = (
        "Get-Process -Name Origin* -ErrorAction SilentlyContinue | "
        "Where-Object { -not $_.MainWindowTitle } | "
        "Stop-Process -Force"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        text=True,
        capture_output=True,
        timeout=30,
    )


def _stacked_plot_rows(comparison: XpsComparison) -> tuple[list[str], list[list[float | None]]]:
    records = [comparison.record_a, comparison.record_b]
    scales = [_normalization_scale(record) for record in records]
    offsets = [index * 1.45 for index, _record in enumerate(records)]
    max_rows = max(len(record.data) for record in records)
    x_values = [float(row["binding_energy_eV"]) for row in records[0].data]
    headers = ["binding_energy_eV"]
    component_specs_by_record = _plot_component_specs_by_record(records)
    for record, component_specs in zip(records, component_specs_by_record):
        for component_index, spec in enumerate(component_specs, start=1):
            label = spec["label"]
            color_index = int(spec["color_index"])
            for level in range(COMPONENT_GRADIENT_LEVELS, 0, -1):
                headers.extend(
                    [
                        f"{record.sample} component {component_index} color {color_index} {label} fill upper {level}",
                        f"{record.sample} component {component_index} color {color_index} {label} fill lower {level}",
                    ]
                )
            headers.append(f"{record.sample} component {component_index} color {color_index} {label} line")
        headers.extend([f"{record.sample} measured", f"{record.sample} Backgnd.", f"{record.sample} Envelope"])
    rows: list[list[float | None]] = []
    for index in range(max_rows):
        x_value = x_values[index] if index < len(x_values) else None
        out: list[float | None] = [x_value]
        for record, offset, scale, component_specs in zip(records, offsets, scales, component_specs_by_record):
            source_row = record.data[index] if index < len(record.data) else {}
            background = _to_float(source_row.get("background"))
            for spec in component_specs:
                label = spec["label"]
                component_top = _to_float(source_row.get(_component_key(label)))
                if background is None or component_top is None:
                    out.extend([None] * ((COMPONENT_GRADIENT_LEVELS * 2) + 1))
                    continue
                for level in range(COMPONENT_GRADIENT_LEVELS - 1, -1, -1):
                    upper_fraction = (level + 1) / COMPONENT_GRADIENT_LEVELS
                    lower_fraction = level / COMPONENT_GRADIENT_LEVELS
                    upper = background + (component_top - background) * upper_fraction
                    lower = background + (component_top - background) * lower_fraction
                    out.extend(
                        [
                            _normalized_offset_value(upper, scale, offset),
                            _normalized_offset_value(lower, scale, offset),
                        ]
                    )
                out.append(_normalized_offset_value(component_top, scale, offset))
            out.extend(
                [
                    _normalized_offset_value(source_row.get("raw_intensity"), scale, offset),
                    _normalized_offset_value(source_row.get("background"), scale, offset),
                    _normalized_offset_value(source_row.get("envelope"), scale, offset),
                ]
            )
        rows.append(out)
    return headers, rows


def _normalization_scale(record: XpsFitRecord) -> tuple[float, float]:
    values = [float(row["raw_intensity"]) for row in record.data if isinstance(row.get("raw_intensity"), (int, float))]
    if not values:
        return 0.0, 1.0
    minimum = min(values)
    span = max(values) - minimum
    return minimum, span if span else 1.0


def _normalized_offset_value(value: object, scale: tuple[float, float], offset: float) -> float | None:
    numeric = _to_float(value)
    if numeric is None:
        return None
    minimum, span = scale
    return ((numeric - minimum) / span) + offset


def _component_limit(record: XpsFitRecord) -> int:
    if record.region.casefold() == "cu2p":
        return MAX_CU_COMPONENTS_PER_SAMPLE_FOR_PLOT
    return MAX_COMPONENTS_PER_SAMPLE_FOR_PLOT


def _plot_component_specs_by_record(records: list[XpsFitRecord]) -> list[list[dict[str, int | str]]]:
    specs_by_record: list[list[dict[str, int | str]]] = []
    binding_keys: list[int] = []
    for record in records:
        specs: list[dict[str, int | str]] = []
        for label in _major_component_labels(record, _component_limit(record)):
            binding_key = _component_peak_binding_key(record, label)
            specs.append({"label": label, "binding_key": binding_key})
            if binding_key not in binding_keys:
                binding_keys.append(binding_key)
        specs_by_record.append(specs)
    color_sequence = _component_color_sequence(len(binding_keys))
    color_by_binding = {
        binding_key: color_sequence[index]
        for index, binding_key in enumerate(sorted(binding_keys, reverse=True))
    }
    for specs in specs_by_record:
        for spec in specs:
            spec["color_index"] = color_by_binding[int(spec["binding_key"])]
    return specs_by_record


def _component_peak_binding_key(record: XpsFitRecord, label: str) -> int:
    key = _component_key(label)
    numeric = [
        (float(row["binding_energy_eV"]), float(row[key]))
        for row in record.data
        if isinstance(row.get("binding_energy_eV"), (int, float)) and isinstance(row.get(key), (int, float))
    ]
    peak = _highest_local_peak(numeric)
    if peak is None and numeric:
        peak = max(numeric, key=lambda item: item[1])
    if peak is None:
        return 0
    return int(float(peak[0]))


def _component_color_sequence(count: int) -> list[int]:
    preferred = [2, 3, 4, 5, 1, 6]
    if count <= len(preferred):
        return preferred[:count]
    return [*preferred, *range(len(preferred) + 1, count + 1)]


def _major_component_labels(record: XpsFitRecord, limit: int) -> list[str]:
    ranked: list[tuple[float, float, str]] = []
    for label in record.component_labels:
        key = _component_key(label)
        numeric = [
            (float(row["binding_energy_eV"]), float(row[key]))
            for row in record.data
            if isinstance(row.get("binding_energy_eV"), (int, float)) and isinstance(row.get(key), (int, float))
        ]
        if numeric:
            peak = _highest_local_peak(numeric) or max(numeric, key=lambda item: item[1])
            ranked.append((float(peak[1]), float(peak[0]), label))
    selected = sorted(ranked, key=lambda item: item[0], reverse=True)[:limit]
    return [label for _height, _peak_binding, label in sorted(selected, key=lambda item: item[1], reverse=True)]


def _safe_origin_page_name(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8", errors="replace")).hexdigest()[:8]
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "XPS"
    base = cleaned[: max(1, 24 - len(digest) - 1)].strip("_") or "XPS"
    return f"{base}_{digest}"[:24]


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ps_array(values: tuple[str, ...]) -> str:
    return "@(" + ", ".join(_ps_quote(value) for value in values) + ")"


def _ps_int_array(values: tuple[int, ...]) -> str:
    return "@(" + ", ".join(str(int(value)) for value in values) + ")"


def _csv_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def _csv_x_values(path: Path) -> list[float]:
    values: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if row:
                value = _to_float(row[0])
                if value is not None:
                    values.append(value)
    if not values:
        raise ValueError(f"No X values found in Origin plot CSV: {path}")
    return values


def _csv_y_range(path: Path) -> tuple[float, float]:
    values: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            for cell in row[1:]:
                value = _to_float(cell)
                if value is not None:
                    values.append(value)
    if not values:
        raise ValueError(f"No Y values found in Origin plot CSV: {path}")
    return min(values), max(values)


def _csv_display_y_range(path: Path, header: list[str]) -> tuple[float, float]:
    visible_indices = [
        index
        for index, label in enumerate(header)
        if index > 0 and (label.endswith(" measured") or label.endswith(" Envelope"))
    ]
    values: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            for index in visible_indices:
                if index < len(row):
                    value = _to_float(row[index])
                    if value is not None:
                        values.append(value)
    if not values:
        return _csv_y_range(path)
    return min(values), max(values)


def _nice_step(span: float) -> float:
    if span <= 0:
        return 1.0
    raw = span / 5.0
    magnitude = 10 ** int(f"{raw:e}".split("e")[1])
    for multiplier in (1, 2, 5, 10):
        step = multiplier * magnitude
        if step >= raw:
            return float(step)
    return float(raw)


def _comparison_peak_details(comparison: XpsComparison) -> list[dict[str, Any]]:
    if comparison.record_a.region.casefold() == "cu2p" or comparison.record_b.region.casefold() == "cu2p":
        return []
    details: list[dict[str, Any]] = []
    for sample_index, record in enumerate((comparison.record_a, comparison.record_b)):
        scale = _normalization_scale(record)
        offset = sample_index * 1.45
        component_labels = _annotation_component_labels(record, _major_component_labels(record, _component_limit(record)))
        if component_labels:
            for component_index, label in enumerate(component_labels[:MAX_PEAK_LABELS_PER_SAMPLE], start=1):
                key = _component_key(label)
                numeric = [
                    (float(row["binding_energy_eV"]), float(row[key]))
                    for row in record.data
                    if isinstance(row.get("binding_energy_eV"), (int, float)) and isinstance(row.get(key), (int, float))
                ]
                peak = _highest_local_peak(numeric)
                if peak is None:
                    continue
                binding, intensity = peak
                normalized_y = _normalized_offset_value(intensity, scale, offset)
                details.append(
                    {
                        "sample": record.sample,
                        "component_label": label,
                        "peak_assignment": _infer_peak_assignment(record.region, binding),
                        "plot_label": f"{record.sample} component {component_index}",
                        "binding_energy_eV": round(binding, 2),
                        "normalized_y": round((normalized_y or offset) + 0.23, 4),
                    }
                )
        else:
            numeric = [
                (float(row["binding_energy_eV"]), float(row.get("envelope") or row["raw_intensity"]))
                for row in record.data
                if isinstance(row.get("binding_energy_eV"), (int, float)) and isinstance(row.get("raw_intensity"), (int, float))
            ]
            for binding, intensity in _top_local_peaks(numeric, limit=2):
                normalized_y = _normalized_offset_value(intensity, scale, offset)
                details.append(
                    {
                        "sample": record.sample,
                        "component_label": "",
                        "peak_assignment": _infer_peak_assignment(record.region, binding),
                        "plot_label": f"{record.sample} peak",
                        "binding_energy_eV": round(binding, 2),
                        "normalized_y": round((normalized_y or offset) + 0.23, 4),
                    }
                )
    deduped: list[dict[str, Any]] = []
    for item in sorted(details, key=lambda value: float(value["binding_energy_eV"]), reverse=True):
        if not any(
            item["sample"] == existing["sample"] and abs(float(item["binding_energy_eV"]) - float(existing["binding_energy_eV"])) < 0.15
            for existing in deduped
        ):
            deduped.append(item)
    return deduped[: 2 * MAX_COMPONENTS_PER_SAMPLE_FOR_PLOT]


def _annotation_component_labels(record: XpsFitRecord, labels: list[str]) -> list[str]:
    ranked: list[tuple[int, float, float, str]] = []
    for label in labels:
        key = _component_key(label)
        numeric = [
            (float(row["binding_energy_eV"]), float(row[key]))
            for row in record.data
            if isinstance(row.get("binding_energy_eV"), (int, float)) and isinstance(row.get(key), (int, float))
        ]
        peak = _highest_local_peak(numeric)
        if peak is None:
            continue
        binding, height = peak
        assigned = 0 if _infer_peak_assignment(record.region, binding) else 1
        ranked.append((assigned, -height, -binding, label))
    return [label for _assigned, _height, _binding, label in sorted(ranked)]


def _highest_local_peak(numeric: list[tuple[float, float]]) -> tuple[float, float] | None:
    peaks = _top_local_peaks(numeric, limit=1)
    return peaks[0] if peaks else None


def _interpolated_background(record: XpsFitRecord, binding_energy: float) -> float | None:
    closest: tuple[float, float] | None = None
    for row in record.data:
        binding = _to_float(row.get("binding_energy_eV"))
        background = _to_float(row.get("background"))
        if binding is None or background is None:
            continue
        distance = abs(binding - binding_energy)
        if closest is None or distance < closest[0]:
            closest = (distance, background)
    return closest[1] if closest else None


def _infer_peak_assignment(region: str, binding_energy: float) -> str:
    match = re.match(r"(?P<element>[A-Z][a-z]?)(?P<n>\d+)(?P<orbital>[spdf])", region)
    if not match:
        return ""
    element = match.group("element")
    orbital = match.group("orbital").lower()
    value = float(binding_energy)
    if orbital == "s":
        return f"{element} {match.group('n')}s"
    known_windows = {
        "Bi4f": ((163.0, 166.0, "Bi 4f5/2"), (157.0, 160.5, "Bi 4f7/2")),
        "W4f": ((36.0, 39.0, "W 4f5/2"), (33.0, 36.0, "W 4f7/2")),
        "Cu2p": ((951.0, 957.5, "Cu 2p1/2"), (931.0, 936.5, "Cu 2p3/2")),
        "Br3d": ((69.2, 70.6, "Br 3d3/2"), (68.0, 69.2, "Br 3d5/2")),
        "Cl2p": ((199.4, 201.2, "Cl 2p1/2"), (197.5, 199.4, "Cl 2p3/2")),
    }
    for lower, upper, label in known_windows.get(region, ()):
        if lower <= value <= upper:
            return label
    return ""


def _top_local_peaks(numeric: list[tuple[float, float]], limit: int) -> list[tuple[float, float]]:
    candidates = []
    for index in range(1, len(numeric) - 1):
        x_value, y_value = numeric[index]
        if y_value >= numeric[index - 1][1] and y_value >= numeric[index + 1][1]:
            candidates.append((y_value, x_value))
    return [(float(x), float(y)) for y, x in sorted(candidates, reverse=True)[:limit]]


def _format_peak_detail(item: dict[str, Any]) -> str:
    label = str(item.get("peak_assignment") or item.get("component_label") or item.get("plot_label") or "peak")
    return f"{item.get('sample')} {label} {float(item['binding_energy_eV']):.2f} eV"


def _write_peak_annotation_table(path: Path, peak_details: list[dict[str, Any]]) -> None:
    fieldnames = ["sample", "component_label", "peak_assignment", "plot_label", "binding_energy_eV", "normalized_y"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: item.get(key, "") for key in fieldnames} for item in peak_details)


def _write_manual_review(path: Path, items: list[dict[str, Any]]) -> None:
    keys = sorted({key for item in items for key in item}) or ["reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(items)


def _write_summary_reports(
    reports_dir: Path,
    sample_files: dict[str, list[Path]],
    records: list[XpsFitRecord],
    plan: XpsComparisonPlan,
    figure_rows: list[dict[str, Any]],
    options: XpsHeterojunctionOptions,
) -> None:
    csv_path = reports_dir / "xps_heterojunction_stacked_summary.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "name",
            "element",
            "comparison",
            "status",
            "processed_csv",
            "origin_file",
            "figure_tif",
            "preview_png",
            "peak_annotations_eV",
            "peak_annotation_labels",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in figure_rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    lines = [
        "# XPS Heterojunction Stacked Summary",
        "",
        "Scope: non-in-situ fitted XPS heterojunction stacked comparisons; no mechanism conclusion is generated.",
        "",
        f"- Origin requested: {options.with_origin}",
        f"- Comparison count: {len(plan.comparisons)}",
        f"- Manual review count: {len(plan.manual_review)}",
        "",
        "## Drawing Method",
        "",
        "- Origin renderer: direct `originpro`/COM graph generation.",
        "- Experimental spectrum is labeled as `measured`; it is the original measured XPS intensity column exported from the fitted Excel table.",
        "- `Backgnd.` is plotted as a grey line, `Envelope` as a black solid line, and `Residuals` is not plotted.",
        "- Fitted components are filled down to `Backgnd.` using smooth layered light-to-color fills; the y-axis range is based on measured/envelope curves so abnormal background/component tails do not compress the plot.",
        "- Y-axis tick marks and y-axis numeric labels are hidden; the axis title is retained.",
        "- Cu2p comparisons keep five fitted components per sample when the Excel table provides them, and component colors are assigned by the integer part of fitted peak binding energy so upper/lower samples stay consistent even when Scan labels are ordered differently.",
        "",
        "## Scanned Excel Files",
    ]
    for sample, files in sample_files.items():
        if files:
            for path in files:
                lines.append(f"- {sample}: `{path}`")
        else:
            lines.append(f"- {sample}: no Excel file configured/found")
    lines.extend(["", "## Recognized Sheets", "", "| sample | element | region | sheet | source |", "|---|---|---|---|---|"])
    for record in records:
        lines.append(f"| {record.sample} | {record.element} | {record.region} | {record.sheet_name} | `{record.source_file}` |")
    lines.extend(
        [
            "",
            "## Generated/Planned Figures",
            "",
            "| name | comparison | peak labels | processed table | Origin project | TIF | preview |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in figure_rows:
        lines.append(
            f"| {row['name']} | {row['comparison']} | {row['peak_annotation_labels']} | "
            f"`{row['processed_csv']}` | `{row['origin_file']}` | `{row['figure_tif']}` | `{row['preview_png']}` |"
        )
    lines.extend(["", "## Manual Review"])
    if plan.manual_review:
        for item in plan.manual_review:
            lines.append(f"- `{json.dumps(item, ensure_ascii=False)}`")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "This stage only plots non-in-situ fitted XPS data for BOBC/BC and CWO/BC component comparisons.",
            "It does not automatically assign valence states, chemical states, electron-transfer direction, or S-scheme mechanism.",
        ]
    )
    (reports_dir / "xps_heterojunction_stacked_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_task_output_dir(project_root: Path, output_dir: Path) -> Path:
    resolved_project = project_root.resolve()
    resolved_output = output_dir.resolve()
    allowed = resolved_project / "output"
    try:
        resolved_output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to write XPS stacked outputs outside project output/: {output_dir}") from exc
    return output_dir


def _excel_files_in_folder(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    candidates = []
    for pattern in ("*.xlsx", "*.xls"):
        candidates.extend(path for path in folder.glob(pattern) if path.is_file() and not path.name.startswith("~$"))
    return sorted(candidates, key=lambda path: (path.suffix.lower() != ".xlsx", path.name.casefold()))


def _select_best_records(records: list[XpsFitRecord]) -> dict[tuple[str, str], XpsFitRecord]:
    selected: dict[tuple[str, str], XpsFitRecord] = {}
    for record in records:
        key = (record.sample, record.element)
        current = selected.get(key)
        if current is None or _record_rank(record) > _record_rank(current):
            selected[key] = record
    return selected


def _record_rank(record: XpsFitRecord) -> tuple[int, int, int]:
    no_suffix_bonus = 1 if not re.search(r"\s+[A-Z]$", record.sheet_name.strip()) else 0
    return (no_suffix_bonus, len(record.component_labels), len(record.data))


def _region_from_sheet(sheet_name: str) -> str | None:
    if "survey" in sheet_name.casefold() or "valence" in sheet_name.casefold():
        return None
    match = ELEMENT_REGION_RE.search(sheet_name.replace(" ", ""))
    if not match:
        return None
    element = match.group("element")
    orbital = match.group("orbital")
    return f"{element[0].upper()}{element[1:].lower()}{orbital.lower()}"


def _extract_sheet_record(
    sample: str,
    source_file: Path,
    sheet_name: str,
    region: str,
    frame: pd.DataFrame,
) -> XpsFitRecord | None:
    header_index = _find_binding_header(frame)
    if header_index is None:
        return None
    headers = [_clean_header(value, index) for index, value in enumerate(frame.iloc[header_index].tolist())]
    binding_index = _first_index(headers, ["binding energy", "bindingenergy"])
    if binding_index is None:
        return None
    background_index = _first_index(headers, ["backgnd", "background"])
    envelope_index = _first_index(headers, ["envelope", "fit"])
    residual_index = _first_index(headers, ["residual"])
    raw_index = _measured_signal_index(frame, header_index, headers, binding_index, {background_index, envelope_index, residual_index})
    named_signal_indices = [
        index
        for index, header in enumerate(headers)
        if index != binding_index
        and header
        and index not in {background_index, envelope_index, residual_index}
        and not header.lower().startswith("unnamed")
    ]
    if raw_index is None and not named_signal_indices:
        return None

    if raw_index is None:
        raw_index = named_signal_indices[0]
        component_indices = named_signal_indices[1:]
    else:
        component_indices = [index for index in named_signal_indices if index != raw_index]
    data: list[dict[str, float | str | None]] = []
    for row_index in range(header_index + 2, len(frame.index)):
        row = frame.iloc[row_index].tolist()
        binding = _to_float(row[binding_index] if binding_index < len(row) else None)
        raw = _to_float(row[raw_index] if raw_index < len(row) else None)
        if binding is None or raw is None:
            continue
        record: dict[str, float | str | None] = {
            "binding_energy_eV": binding,
            "raw_intensity": raw,
        }
        if background_index is not None:
            record["background"] = _to_float(row[background_index] if background_index < len(row) else None)
        if envelope_index is not None:
            record["envelope"] = _to_float(row[envelope_index] if envelope_index < len(row) else None)
        if residual_index is not None:
            record["residual"] = _to_float(row[residual_index] if residual_index < len(row) else None)
        for index in component_indices:
            record[_component_key(headers[index])] = _to_float(row[index] if index < len(row) else None)
        data.append(record)
    if len(data) < 2:
        return None
    element = re.match(r"[A-Z][a-z]?", region)
    return XpsFitRecord(
        sample=sample,
        element=element.group(0) if element else region,
        region=region,
        source_file=source_file,
        sheet_name=sheet_name,
        raw_label="measured" if headers[raw_index].lower().startswith("unnamed") else headers[raw_index],
        background_label=headers[background_index] if background_index is not None else None,
        envelope_label=headers[envelope_index] if envelope_index is not None else None,
        residual_label=headers[residual_index] if residual_index is not None else None,
        component_labels=[headers[index] for index in component_indices],
        data=data,
    )


def _find_binding_header(frame: pd.DataFrame) -> int | None:
    for index, row in frame.iterrows():
        cells = [_normalize_cell(value) for value in row.tolist()]
        if any("binding energy" in cell or "bindingenergy" in cell for cell in cells):
            return int(index)
    return None


def _measured_signal_index(
    frame: pd.DataFrame,
    header_index: int,
    headers: list[str],
    binding_index: int,
    special_indices: set[int | None],
) -> int | None:
    numeric_scores: list[tuple[int, int]] = []
    first_named_signal = next(
        (
            index
            for index, header in enumerate(headers)
            if index != binding_index
            and index not in special_indices
            and not header.lower().startswith("unnamed")
        ),
        len(headers),
    )
    for index, header in enumerate(headers):
        if index == binding_index or index in special_indices:
            continue
        normalized = _normalize_cell(header)
        if not header.lower().startswith("unnamed"):
            continue
        values = []
        for row_index in range(header_index + 2, len(frame.index)):
            row = frame.iloc[row_index].tolist()
            value = _to_float(row[index] if index < len(row) else None)
            if value is not None:
                values.append(value)
        if len(values) < 2:
            continue
        if max(values) - min(values) <= 0:
            continue
        proximity_bonus = 2 if index < first_named_signal else 0
        numeric_scores.append((proximity_bonus, index))
    if numeric_scores:
        return sorted(numeric_scores, key=lambda item: (-item[0], item[1]))[0][1]
    return None


def _first_index(headers: list[str], needles: list[str]) -> int | None:
    for index, header in enumerate(headers):
        normalized = _normalize_cell(header)
        if any(needle in normalized for needle in needles):
            return index
    return None


def _clean_header(value: object, index: int) -> str:
    text = "" if pd.isna(value) else str(value).replace("\ufeff", "").strip()
    return text or f"Unnamed: {index}"


def _normalize_cell(value: object) -> str:
    return re.sub(r"\s+", "", str(value).replace("\ufeff", "").casefold())


def _to_float(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _component_key(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
    return f"component_{cleaned or 'peak'}"
