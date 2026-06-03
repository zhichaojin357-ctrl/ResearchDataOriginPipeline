from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from src.core.epr_jeol import read_xy_xlsx
from src.core.project import output_dir, report_path
from src.core.runtime_paths import resolve_workspace_root
from src.origin.adapter import export_plot


DEFAULT_EPR_GROUPS = {
    "OH": (
        ("BC", "BC-OH-light2.xlsx"),
        ("CWO", "CWO-OH-light2.xlsx"),
        ("BOBC", "BOBC-OH-light1.xlsx"),
    ),
    "O3": (
        ("BC", "BC-O3-light5.xlsx"),
        ("CWO", "CWO-O3-light1.xlsx"),
        ("BOBC", "BOBC-O3-light2.xlsx"),
    ),
}


@dataclass(frozen=True)
class EprOverlayOptions:
    reference_dir: Path | None = None
    group: str = "all"
    with_origin: bool = False
    force: bool = True
    normalize: bool = False
    smooth_window: int = 0
    background: str | None = None
    report_json: Path | None = None
    report_md: Path | None = None


def run_epr_overlay(project_root: Path, options: EprOverlayOptions) -> int:
    reference_dir = options.reference_dir or _default_reference_dir(project_root)
    if not reference_dir.is_dir():
        raise FileNotFoundError(f"EPR verified Excel reference directory not found: {reference_dir}")

    selected_groups = _selected_groups(options.group)
    rows = []
    for group_name in selected_groups:
        result = build_epr_condition_overlay(
            project_root,
            reference_dir,
            group_name,
            with_origin=options.with_origin,
            force=options.force,
            normalize=options.normalize,
            smooth_window=options.smooth_window,
            background=options.background,
        )
        rows.append(result)

    payload = {
        "command": "epr-overlay",
        "reference_dir": str(reference_dir),
        "normalization": "max_abs_per_trace" if options.normalize else "none; amplitudes preserved",
        "baseline_correction": "edge-region median baseline subtraction",
        "smoothing": f"moving_average_window_{options.smooth_window}" if options.smooth_window else "none by default",
        "background_subtraction": options.background or "none unless explicit dark/background mapping is supplied",
        "offset_rule": "median peak-to-peak range * 0.85 rounded to a readable step; BC top, CWO middle, BOBC bottom",
        "forbidden_claims": ["no automatic radical assignment", "no automatic mechanism claim"],
        "items": rows,
    }
    output_json = options.report_json or report_path(project_root, "epr_overlay_report.json")
    output_md = options.report_md or report_path(project_root, "epr_overlay_report.md")
    _write_json(project_root, output_json, payload)
    _write_md(project_root, output_md, payload)
    return 0 if all(item["status"] in {"table_only", "success"} for item in rows) else 2


def build_epr_condition_overlay(
    project_root: Path,
    reference_dir: Path,
    group_name: str,
    *,
    with_origin: bool = False,
    force: bool = True,
    normalize: bool = False,
    smooth_window: int = 0,
    background: str | None = None,
) -> dict:
    entries = DEFAULT_EPR_GROUPS[group_name]
    background_map = _background_map(background, group_name)
    traces = []
    for label, file_name in entries:
        path = reference_dir / file_name
        if not path.is_file():
            raise FileNotFoundError(f"EPR overlay input missing for {group_name}: {path}")
        x_values, y_values = read_xy_xlsx(path)
        if len(x_values) < 2:
            raise ValueError(f"EPR overlay input needs at least two points, got {len(x_values)} rows in {path}")
        raw_values = list(y_values)
        background_subtracted = None
        if label in background_map:
            background_path = reference_dir / background_map[label]
            if not background_path.is_file():
                raise FileNotFoundError(f"EPR background file missing for {label}: {background_path}")
            background_x, background_y = read_xy_xlsx(background_path)
            _validate_common_x([x_values, background_x])
            y_values = [value - bg for value, bg in zip(y_values, background_y)]
            background_subtracted = list(y_values)
        centered, baseline = _baseline_correct(y_values)
        if smooth_window:
            centered = _moving_average(centered, smooth_window)
        if normalize:
            centered = _max_abs_normalize(centered)
        traces.append(
            {
                "label": label,
                "file_label": Path(file_name).stem,
                "path": path,
                "x": x_values,
                "centered": centered,
                "raw": raw_values,
                "baseline": baseline,
                "background_subtracted": background_subtracted,
                "background_file": background_map.get(label),
            }
        )

    _validate_common_x([trace["x"] for trace in traces])
    step = _offset_step([trace["centered"] for trace in traces])
    offsets = {trace["label"]: (len(traces) - index - 1) * step for index, trace in enumerate(traces)}

    data_dir = output_dir(project_root, "processed_data", "EPR")
    data_dir.mkdir(parents=True, exist_ok=True)
    slug = f"epr_{group_name.lower()}_overlay"
    plot_csv = data_dir / f"{slug}_processed.csv"
    detail_csv = data_dir / f"{slug}_detail.csv"
    if (plot_csv.exists() or detail_csv.exists()) and not force:
        raise FileExistsError(f"EPR overlay output exists; rerun with --force: {plot_csv}")

    header = ["magnetic_field", *[trace["label"] for trace in traces]]
    detail_header = ["magnetic_field"]
    for trace in traces:
        label = trace["label"]
        detail_header.extend([f"{label}_raw", f"{label}_baseline", f"{label}_baseline_corrected", f"{label}_offset"])
        if trace["background_subtracted"] is not None:
            detail_header.append(f"{label}_background_subtracted_optional")

    with plot_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row_index, field in enumerate(traces[0]["x"]):
            writer.writerow([field, *[trace["centered"][row_index] + offsets[trace["label"]] for trace in traces]])

    with detail_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(detail_header)
        for row_index, field in enumerate(traces[0]["x"]):
            row = [field]
            for trace in traces:
                row.extend([
                    trace["raw"][row_index],
                    trace["baseline"],
                    trace["centered"][row_index],
                    trace["centered"][row_index] + offsets[trace["label"]],
                ])
                if trace["background_subtracted"] is not None:
                    row.append(trace["background_subtracted"][row_index])
            writer.writerow(row)

    origin_result = None
    status = "table_only"
    if with_origin:
        origin_result = export_plot(
            project_root,
            f"EPR_{group_name}_overlay",
            plot_csv,
            "Magnetic Field (G)",
            "Intensity (a.u.)",
            data_type="EPR overlay",
            source_file=reference_dir,
        )
        status = "success" if origin_result.ok else "fail"

    return {
        "group": group_name,
        "status": status,
        "input_files": [str(trace["path"]) for trace in traces],
        "labels": [trace["label"] for trace in traces],
        "file_labels": [trace["file_label"] for trace in traces],
        "point_count": len(traces[0]["x"]),
        "x_min": min(traces[0]["x"]),
        "x_max": max(traces[0]["x"]),
        "offset_step": step,
        "offsets": offsets,
        "baseline_correction": "edge-region median baseline subtraction",
        "baseline_values": {trace["label"]: trace["baseline"] for trace in traces},
        "smoothing": f"moving_average_window_{smooth_window}" if smooth_window else "none",
        "normalization": "max_abs_per_trace" if normalize else "none",
        "background_subtraction": background or "none",
        "background_files": {trace["label"]: trace["background_file"] for trace in traces if trace["background_file"]},
        "processed_csv": str(plot_csv),
        "detail_csv": str(detail_csv),
        "origin_file": str(origin_result.origin_file) if origin_result and origin_result.origin_file else None,
        "figure_tif": str(origin_result.figure_tif) if origin_result and origin_result.figure_tif else None,
        "preview_png": str(origin_result.preview_png) if origin_result and origin_result.preview_png else None,
        "origin_message": origin_result.message if origin_result else "Origin export not requested",
    }


def _default_reference_dir(project_root: Path) -> Path:
    return resolve_workspace_root(project_root) / "EPR" / "导出后的数据"


def _selected_groups(group: str) -> list[str]:
    if group == "all":
        return list(DEFAULT_EPR_GROUPS)
    normalized = group.upper()
    if normalized not in DEFAULT_EPR_GROUPS:
        raise ValueError(f"unknown EPR overlay group: {group}; expected one of all, OH, O3")
    return [normalized]


def _baseline_correct(values: list[float]) -> tuple[list[float], float]:
    baseline = _edge_region_baseline(values)
    return [value - baseline for value in values], baseline


def _edge_region_baseline(values: list[float]) -> float:
    if len(values) < 40:
        return median(values)
    edge_count = max(20, int(len(values) * 0.05))
    return median(values[:edge_count] + values[-edge_count:])


def _max_abs_normalize(values: list[float]) -> list[float]:
    scale = max((abs(value) for value in values), default=0.0)
    if scale == 0:
        return values
    return [value / scale for value in values]


def _moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1:
        return list(values)
    if window % 2 == 0:
        raise ValueError("EPR smoothing window must be odd to preserve peak centers")
    if window > 31:
        raise ValueError("EPR smoothing window is too large for conservative plotting; use <=31")
    half = window // 2
    output = []
    for index in range(len(values)):
        start = max(0, index - half)
        end = min(len(values), index + half + 1)
        output.append(sum(values[start:end]) / (end - start))
    return output


def _background_map(background: str | None, group_name: str) -> dict[str, str]:
    if background in {None, "", "none"}:
        return {}
    if background == "matched_dark" and group_name == "OH":
        return {
            "BC": "BC-OH-dark.xlsx",
            "CWO": "CWO-OH-dark.xlsx",
        }
    if background == "matched_dark" and group_name == "O3":
        return {
            "BC": "BC-O3-dark.xlsx",
            "CWO": "CWO-O3-dark.xlsx",
        }
    raise ValueError(f"unsupported EPR background option for {group_name}: {background}")


def _offset_step(traces: list[list[float]]) -> float:
    ranges = [max(trace) - min(trace) for trace in traces if trace]
    if not ranges:
        return 100.0
    raw_step = median(ranges) * 0.85
    if raw_step <= 100:
        return round(raw_step / 10.0 + 0.499) * 10.0
    return round(raw_step / 50.0 + 0.499) * 50.0


def _validate_common_x(series: list[list[float]]) -> None:
    first = series[0]
    for values in series[1:]:
        if len(values) != len(first):
            raise ValueError("EPR overlay traces have different row counts")
        max_delta = max(abs(a - b) for a, b in zip(first, values))
        if max_delta > 0.0001:
            raise ValueError(f"EPR overlay traces have different magnetic field grids; max delta={max_delta}")


def _write_json(project_root: Path, path: Path, payload: dict) -> None:
    target = path if path.is_absolute() else project_root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_md(project_root: Path, path: Path, payload: dict) -> None:
    target = path if path.is_absolute() else project_root / path
    lines = [
        "# EPR Overlay Report",
        "",
        f"- Reference dir: `{payload['reference_dir']}`",
        f"- Baseline correction: `{payload['baseline_correction']}`",
        f"- Normalization: `{payload['normalization']}`",
        f"- Smoothing: `{payload['smoothing']}`",
        f"- Background subtraction: `{payload['background_subtraction']}`",
        f"- Offset rule: {payload['offset_rule']}",
        "- Forbidden: no radical assignment, no mechanism claim.",
        "",
        "| group | status | labels | offset step | processed CSV | preview PNG |",
        "|---|---|---|---:|---|---|",
    ]
    for item in payload["items"]:
        lines.append(
            f"| {item['group']} | {item['status']} | {', '.join(item['labels'])} | {item['offset_step']} | "
            f"`{item['processed_csv']}` | `{item.get('preview_png') or ''}` |"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
