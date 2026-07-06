from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from src.core.metadata import file_hash
from src.core.template_product_common import extract_xrd_raw_data_rows
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.plot_labels import XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE
from src.core.runtime_paths import create_run_output_layout, resolve_origin_helper, resolve_output_root
from src.origin.adapter import check_origin_available, write_origin_error, write_origin_success
from src.origin.operations import quote_labtalk
from src.origin.plot_policy import GRAPH4_FIXED_STYLE, get_plot_policy
from src.origin.text_format import origin_bold_text


BICU_LABEL = "BiCu-10"
BOBC_LABEL = r"BiOBr\-(0.5)Cl\-(0.5)"
CWO_LABEL = r"CuWO\-(4)"
CWO_CARD_LABEL = r"CuWO\-(4) JCPDS card No.04-009-6293"
XRD_OVERLAY_COLORS = (23709421, 33518174, 16814848, 22106449)
XRD_SAMPLE_LEGEND_LEFT = 3569
XRD_SAMPLE_LEGEND_TOP = 650
XRD_SAMPLE_LEGEND_TEXT_LEFT = 4110
XRD_SAMPLE_LEGEND_ROW_STEP = 236
XRD_SAMPLE_LEGEND_WIDTH = 1900
XRD_SAMPLE_LEGEND_FONT = 67
XRD_SAMPLE_LEGEND_FONT_SIZE = 26
XRD_SAMPLE_LEGEND_COLOR = 1
DEFAULT_XRD_REFERENCE_OPJU = Path("templates") / "origin_styles" / "reference_opju" / "XRD.opju"


@dataclass(frozen=True)
class XrdOverlayOptions:
    bicu_source: Path
    bobc_source: Path
    cwo_source: Path
    cwo_card: Path
    reference_opju: Path = DEFAULT_XRD_REFERENCE_OPJU
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    force: bool = True


@dataclass(frozen=True)
class XrdOverlayTable:
    headers: list[str]
    rows: list[list[float | None]]
    legend_labels: list[str]
    origin_ocolors: list[int]
    metadata: dict[str, object]


@dataclass(frozen=True)
class XrdOverlayArtifacts:
    processed_data: Path
    metadata: Path
    report: Path
    origin_file: Path
    figure_tif: Path
    preview_png: Path
    job_script: Path


def build_xrd_overlay_table(
    bicu_source: Path,
    bobc_source: Path,
    cwo_source: Path,
    cwo_card: Path,
) -> XrdOverlayTable:
    series = [
        (BICU_LABEL, extract_xrd_raw_data_rows(bicu_source), 3.3),
        (BOBC_LABEL, extract_xrd_raw_data_rows(bobc_source), 2.2),
        (CWO_LABEL, extract_xrd_raw_data_rows(cwo_source), 1.1),
    ]
    numeric_series = [_numeric_xy_points(rows) for _label, rows, _offset in series]
    grid = sorted({x for points in numeric_series for x, _y in points})
    if len(grid) < 2 or any(not points for points in numeric_series):
        raise ValueError("XRD overlay requires at least two numeric points in every sample source.")

    card_peaks = parse_xrd_reference_card_peaks(cwo_card)
    card_values = _reference_stick_values(grid, card_peaks)
    rows: list[list[float | None]] = []
    for row_index, x_value in enumerate(grid):
        row: list[float | None] = [x_value]
        for points, (_label, _rows, offset) in zip(numeric_series, series):
            row.append(_normalized_offset_y(points, x_value, offset))
        row.append(card_values[row_index])
        rows.append(row)

    metadata = {
        "series_order": [BICU_LABEL, BOBC_LABEL, CWO_LABEL],
        "series_plain_labels": ["BiCu-10", "BiOBr0.5Cl0.5", "CuWO4"],
        "series_rich_labels": [BICU_LABEL, BOBC_LABEL, CWO_LABEL],
        "origin_ocolors": list(XRD_OVERLAY_COLORS),
        "offsets": [3.3, 2.2, 1.1, 0.0],
        "reference_card": {
            "label": CWO_CARD_LABEL,
            "peak_count": len(card_peaks),
            "max_stick_height": max(card_values) if card_values else 0.0,
        },
        "normalization": "Each sample trace is max-normalized and vertically offset for visual XRD comparison only.",
    }
    return XrdOverlayTable(
        headers=["two_theta_deg", BICU_LABEL, BOBC_LABEL, CWO_LABEL, CWO_CARD_LABEL],
        rows=rows,
        legend_labels=[BICU_LABEL, BOBC_LABEL, CWO_LABEL, CWO_CARD_LABEL],
        origin_ocolors=list(XRD_OVERLAY_COLORS),
        metadata=metadata,
    )


def parse_xrd_reference_card_peaks(path: Path) -> list[tuple[float, float]]:
    peaks: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        two_theta = _to_float(parts[0])
        intensity = _to_float(parts[2])
        if two_theta is None or intensity is None:
            continue
        if 5.0 <= two_theta <= 90.0 and intensity > 0:
            peaks.append((two_theta, intensity))
    return peaks


def run_xrd_overlay(project_root: Path, options: XrdOverlayOptions) -> dict[str, object]:
    project_root = project_root.resolve()
    options = replace(options, reference_opju=_resolve_reference_opju(project_root, options.reference_opju))
    _validate_inputs(options)
    output_root = resolve_output_root(project_root, explicit=options.output_root)
    input_paths = [options.bicu_source, options.bobc_source, options.cwo_source, options.cwo_card]
    if options.with_origin or options.reference_opju.exists():
        input_paths.append(options.reference_opju)
    layout = create_run_output_layout(
        project_root,
        scope="xrd_bobc_shuire_cwo_overlay",
        command="xrd-overlay",
        mode="with_origin" if options.with_origin else "no_origin",
        input_paths=input_paths,
        timestamp=options.timestamp,
        no_origin=not options.with_origin,
        dry_run=not options.with_origin,
        output_base=output_root / "runs",
    )
    artifacts = XrdOverlayArtifacts(
        processed_data=layout.processed_data / "XRD_BiCu_BiOBr_CuWO4_overlay.csv",
        metadata=layout.metadata / "XRD_BiCu_BiOBr_CuWO4_overlay" / "metadata.json",
        report=layout.reports / "xrd_overlay_report.md",
        origin_file=layout.origin_files / "XRD_BiCu_BiOBr_CuWO4_overlay.opju",
        figure_tif=layout.figures_tif / "XRD_BiCu_BiOBr_CuWO4_overlay.tif",
        preview_png=layout.figures_preview / "XRD_BiCu_BiOBr_CuWO4_overlay.png",
        job_script=layout.logs / "origin_jobs" / "XRD_BiCu_BiOBr_CuWO4_overlay.ps1",
    )
    table = build_xrd_overlay_table(options.bicu_source, options.bobc_source, options.cwo_source, options.cwo_card)
    _write_csv(artifacts.processed_data, table.headers, table.rows)
    export_status: dict[str, object] = {"ok": False, "message": "Origin export skipped by --dry-run/--no-origin."}
    if options.with_origin:
        export_status = _export_xrd_overlay_with_origin(project_root, options, table, artifacts)
    metadata = _write_metadata(project_root, layout.root, options, table, artifacts, export_status)
    report = _write_report(project_root, layout.root, options, table, artifacts, export_status)
    return {
        "run_root": _relative(project_root, layout.root),
        "processed_data": _relative(project_root, artifacts.processed_data),
        "metadata": _relative(project_root, metadata),
        "report": _relative(project_root, report),
        "origin_file": _relative(project_root, artifacts.origin_file),
        "figure_tif": _relative(project_root, artifacts.figure_tif),
        "preview_png": _relative(project_root, artifacts.preview_png),
        "will_launch_origin": bool(options.with_origin),
        "origin_status": export_status,
    }


def _export_xrd_overlay_with_origin(
    project_root: Path,
    options: XrdOverlayOptions,
    table: XrdOverlayTable,
    artifacts: XrdOverlayArtifacts,
) -> dict[str, object]:
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, f"xrd-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": f"Origin unavailable: {message}"}
    _remove_stale_outputs(artifacts)
    try:
        tif_status = _replace_graph4_template_data_with_originpro(options, artifacts)
    except Exception as exc:
        write_origin_error(project_root, f"xrd-overlay: {exc}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": str(exc)}
    missing = [
        name
        for name, path in (("origin_file", artifacts.origin_file), ("figure_tif", artifacts.figure_tif), ("preview_png", artifacts.preview_png))
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        message = "Origin export missing required artifacts: " + ", ".join(missing)
        write_origin_error(project_root, f"xrd-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": message, "tif_status": tif_status}
    write_origin_success(project_root, output_root=artifacts.origin_file.parents[1])
    return {
        "ok": True,
        "message": "Origin export succeeded by replacing current data into the Graph4 reference OPJU.",
        "tif_status": tif_status,
    }


def _replace_graph4_template_data_with_originpro(options: XrdOverlayOptions, artifacts: XrdOverlayArtifacts) -> dict[str, object]:
    try:
        import originpro as op
    except Exception as exc:
        raise RuntimeError(f"originpro unavailable for OPJU template replacement: {exc}") from exc

    artifacts.origin_file.parent.mkdir(parents=True, exist_ok=True)
    artifacts.preview_png.parent.mkdir(parents=True, exist_ok=True)
    artifacts.figure_tif.parent.mkdir(parents=True, exist_ok=True)
    neutral_root = _neutral_origin_runtime_root()
    with tempfile.TemporaryDirectory(prefix="rdop_xrd_", dir=neutral_root) as runtime_text:
        runtime = Path(runtime_text)
        runtime_origin = runtime / artifacts.origin_file.name
        runtime_png = runtime / artifacts.preview_png.name
        runtime_tif = runtime / artifacts.figure_tif.name
        shutil.copy2(options.reference_opju, runtime_origin)

        try:
            op.set_show(False)
            if not op.open(str(runtime_origin), readonly=False, asksave=False):
                raise RuntimeError("failed to open copied Graph4 reference OPJU")
            graph = op.find_graph("Graph4")
            if graph is None:
                raise RuntimeError("Graph4 was not found in the copied reference OPJU")
            if len(graph) < 3:
                raise RuntimeError("Graph4 does not contain the expected sample, card, and top-curve layers")

            book2 = op.find_book("w", "Book2")
            book3 = op.find_book("w", "Book3")
            if book2 is None or book3 is None:
                raise RuntimeError("Graph4 source workbooks Book2 and Book3 were not found")
            sheet2 = book2[0]
            sheet3 = book3[0]

            cwo_points = _numeric_xy_points(extract_xrd_raw_data_rows(options.cwo_source))
            bobc_points = _numeric_xy_points(extract_xrd_raw_data_rows(options.bobc_source))
            bicu_points = _numeric_xy_points(extract_xrd_raw_data_rows(options.bicu_source))
            if not cwo_points or not bobc_points or not bicu_points:
                raise RuntimeError("one or more XRD sources contain no numeric two-theta/intensity rows")

            _write_scaled_xy_to_template_columns(sheet2, 0, 1, cwo_points, CWO_LABEL, "CuWO4")
            _write_scaled_xy_to_template_columns(sheet2, 2, 3, bobc_points, BOBC_LABEL, "BiOBr0.5Cl0.5")
            _write_scaled_xy_to_template_columns(sheet3, 4, 5, bicu_points, BICU_LABEL, "BiCu-10", y_shift=-2500.0)
            _write_card_to_template_columns(sheet2, 6, 7, parse_xrd_reference_card_peaks(options.cwo_card))

            _remove_template_bicu30_plot(graph)
            _set_template_text_objects(graph)
            op.lt_exec(_xrd_axis_title_labtalk("Graph4"))
            _enforce_template_plot_colors(graph)

            graph.save_fig(str(runtime_png), type="png", replace=True, width=GRAPH4_FIXED_STYLE.page_width)
            graph.save_fig(str(runtime_tif), type="tif", replace=True, width=GRAPH4_FIXED_STYLE.page_width)
            op.save(str(runtime_origin))
        finally:
            try:
                op.exit()
            except Exception:
                pass

        if not runtime_png.exists():
            raise RuntimeError("Origin did not export the PNG preview")
        if not runtime_tif.exists():
            raise RuntimeError("Origin did not export the TIF figure")
        if not runtime_origin.exists():
            raise RuntimeError("Origin did not save the OPJU project")
        _ensure_tif_600_dpi(runtime_tif)
        _copy_runtime_artifact(runtime_origin, artifacts.origin_file)
        _copy_runtime_artifact(runtime_png, artifacts.preview_png)
        _copy_runtime_artifact(runtime_tif, artifacts.figure_tif)
    return {
        "ok": True,
        "message": "Graph4 template data replaced and TIF exported at 600 dpi.",
        "neutral_runtime": True,
    }


def _write_scaled_xy_to_template_columns(
    sheet: object,
    x_col: int,
    y_col: int,
    points: list[tuple[float, float]],
    rich_label: str,
    plain_label: str,
    y_shift: float = 0.0,
) -> None:
    old_y = [_to_float(value) for value in sheet.to_list(y_col)]
    scaled = [value + y_shift for value in _scale_to_template_y_range([y for _x, y in points], [value for value in old_y if value is not None])]
    sheet.from_list(x_col, [x for x, _y in points], comments=plain_label, axis="X")
    sheet.from_list(y_col, scaled, comments=plain_label, axis="Y")
    sheet.set_label(x_col, "Angle", "L")
    sheet.set_label(y_col, "PSD", "L")
    sheet.set_label(x_col, plain_label, "C")
    sheet.set_label(y_col, rich_label, "C")


def _write_card_to_template_columns(sheet: object, x_col: int, y_col: int, peaks: list[tuple[float, float]]) -> None:
    if not peaks:
        raise RuntimeError("CuWO4 reference card contains no numeric peak rows")
    old_y = [_to_float(value) for value in sheet.to_list(y_col)]
    target_max = max((value for value in old_y if value is not None), default=500.0)
    max_intensity = max(intensity for _x, intensity in peaks)
    sheet.from_list(x_col, [two_theta for two_theta, _intensity in peaks], comments="CuWO4 JCPDS card No.04-009-6293", axis="X")
    sheet.from_list(y_col, [target_max * intensity / max_intensity for _two_theta, intensity in peaks], comments=CWO_CARD_LABEL, axis="Y")
    sheet.set_label(x_col, "2theta", "L")
    sheet.set_label(y_col, "Intensity", "L")


def _scale_to_template_y_range(values: list[float], template_values: list[float]) -> list[float]:
    if not values:
        return []
    source_min = min(values)
    source_max = max(values)
    target_min = min(template_values) if template_values else 0.0
    target_max = max(template_values) if template_values else 1.0
    if source_max == source_min:
        midpoint = (target_min + target_max) / 2.0
        return [midpoint for _value in values]
    scale = (target_max - target_min) / (source_max - source_min)
    return [target_min + (value - source_min) * scale for value in values]


def _remove_template_bicu30_plot(graph: object) -> None:
    layer = graph[0]
    plots = layer.plot_list()
    while len(plots) > 2:
        plots[-1].remove()
        plots = layer.plot_list()


def _set_template_text_objects(graph: object) -> None:
    layer1_objects = graph[0].obj.GraphObjects
    legend = layer1_objects["Legend"]
    if legend is not None:
        legend.Text = "\\l(2)\\b( BiOBr\\-(0.5)Cl\\-(0.5))\r\n\\l(1)\\b( CuWO\\-(4))"
        legend.Left = XRD_SAMPLE_LEGEND_LEFT
        legend.Top = XRD_SAMPLE_LEGEND_TOP + XRD_SAMPLE_LEGEND_ROW_STEP
        legend.Width = XRD_SAMPLE_LEGEND_WIDTH
        legend.Height = XRD_SAMPLE_LEGEND_ROW_STEP * 2
        _set_graph_object_format(legend)
        legend.SetNumProp("border", 0)
        legend.SetNumProp("frame", 0)
        legend.SetNumProp("fill", 0)
        legend.SetNumProp("fillarea", 0)
    top_text = layer1_objects["Text"]
    if top_text is not None:
        top_text.Text = "\\b(BiCu-10)"
        top_text.Left = XRD_SAMPLE_LEGEND_TEXT_LEFT
        top_text.Top = XRD_SAMPLE_LEGEND_TOP
        top_text.Width = XRD_SAMPLE_LEGEND_WIDTH
        top_text.Height = XRD_SAMPLE_LEGEND_ROW_STEP
        _set_graph_object_format(top_text)
    card_text = graph[1].obj.GraphObjects["Text"]
    if card_text is not None:
        card_text.Text = "\\b(\\c17585584(CuWO)\\-(\\c17585584(4))\\c17585584( JCPDS card No.04-009-6293))"


def _xrd_axis_title_labtalk(graph_name: str) -> str:
    x_title = _quote_origin_rich_text(origin_bold_text(XRD_X_AXIS_TITLE))
    y_title = _quote_origin_rich_text(origin_bold_text(XRD_Y_AXIS_TITLE))
    graph = quote_labtalk(graph_name)
    return f'win -a "{graph}"; xb.text$="{x_title}"; yl.text$="{y_title}"; xb.show=1; yl.show=1;'


def _quote_origin_rich_text(value: object) -> str:
    return str(value).replace('"', '\\"')


def _set_graph_object_format(
    graph_object: object,
    *,
    font: int = XRD_SAMPLE_LEGEND_FONT,
    size: int = XRD_SAMPLE_LEGEND_FONT_SIZE,
    color: int = XRD_SAMPLE_LEGEND_COLOR,
) -> None:
    for prop, value in (("font", font), ("fsize", size), ("bold", 1), ("color", color)):
        try:
            graph_object.SetNumProp(prop, value)
        except Exception:
            pass


def _enforce_template_plot_colors(graph: object) -> None:
    layer1_plots = graph[0].plot_list()
    if len(layer1_plots) >= 1:
        layer1_plots[0].set_int("color", 16814848)
        layer1_plots[0].set_int("line.width", 3)
    if len(layer1_plots) >= 2:
        layer1_plots[1].set_int("color", 33518174)
        layer1_plots[1].set_int("line.width", 3)
    card_plots = graph[1].plot_list()
    if card_plots:
        card_plots[0].set_int("color", 22106449)
    top_plots = graph[2].plot_list()
    if top_plots:
        top_plots[0].set_int("color", 23709421)
        top_plots[0].set_int("line.width", 3)


def _origin_job_script(
    project_root: Path,
    options: XrdOverlayOptions,
    table: XrdOverlayTable,
    artifacts: XrdOverlayArtifacts,
) -> str:
    helper = resolve_origin_helper(project_root)
    policy = get_plot_policy("XRD")
    group = (
        "@{\n"
        f"  DataFile = {_ps_quote(artifacts.processed_data)}\n"
        "  PageName = 'XRD_BiCu_BiOBr_CuWO4_overlay'\n"
        f"  ColumnCount = {len(table.headers)}\n"
        f"  Labels = {_ps_array(table.legend_labels)}\n"
        f"  Palette = {_ps_int_array(table.origin_ocolors)}\n"
        "  PlotType = '200'\n"
        "  PlotPrimitive = 'line'\n"
        "  MarkerMode = 'none'\n"
        f"  FitOverlayMode = {_ps_quote(policy.fit_overlay_condition)}\n"
        "  ShowYAxis = $true\n"
        "  ShowYTicks = $false\n"
        "  ShowYTickValues = $false\n"
        "  ShowXTickValues = $true\n"
        f"  XTitle = {_ps_quote(XRD_X_AXIS_TITLE)}\n"
        f"  YTitle = {_ps_quote(XRD_Y_AXIS_TITLE)}\n"
        "}"
    )
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$groups = @({group})",
        f"& {_ps_quote(helper)} -ReferenceOpju {_ps_quote(options.reference_opju)} -ReferenceGraph 'Graph4' "
        f"-OutputOpju {_ps_quote(artifacts.origin_file)} -ExportDir {_ps_quote(artifacts.preview_png.parent)} "
        "-Groups $groups -Headless -CloseOrigin",
        f"if (-not (Test-Path -LiteralPath {_ps_quote(artifacts.preview_png)})) {{ throw 'PNG preview was not exported.' }}",
    ]
    return "\n".join(lines) + "\n"


def _export_tif_with_originpro(artifacts: XrdOverlayArtifacts) -> dict[str, object]:
    try:
        import originpro as op
    except Exception as exc:
        return {"ok": False, "message": f"originpro unavailable for TIF export: {exc}"}
    try:
        op.set_show(False)
        if not op.open(str(artifacts.origin_file), readonly=False, asksave=False):
            return {"ok": False, "message": "Failed to open generated OPJU for TIF export."}
        graph = op.find_graph("XRD_BiCu_BiOBr_CuWO4_overlay")
        if graph is None:
            return {"ok": False, "message": "Generated OPJU did not contain expected graph page."}
        artifacts.figure_tif.parent.mkdir(parents=True, exist_ok=True)
        result = graph.save_fig(str(artifacts.figure_tif), type="tif", replace=True, width=GRAPH4_FIXED_STYLE.page_width)
        if not result or not artifacts.figure_tif.exists():
            return {"ok": False, "message": "originpro did not create the TIF output."}
        _ensure_tif_600_dpi(artifacts.figure_tif)
        return {"ok": True, "message": "TIF exported at 600 dpi."}
    finally:
        try:
            op.exit()
        except Exception:
            pass


def _write_metadata(
    project_root: Path,
    run_root: Path,
    options: XrdOverlayOptions,
    table: XrdOverlayTable,
    artifacts: XrdOverlayArtifacts,
    export_status: dict[str, object],
) -> Path:
    payload = {
        "dataset_id": "XRD_BiCu_BiOBr_CuWO4_overlay",
        "run_root": _relative(run_root, run_root),
        "data_type": "XRD",
        "processor_name": "xrd_overlay_processor",
        "processing_status": "success" if export_status.get("ok") else ("fail" if options.with_origin else "processed_no_origin"),
        "source_files": [
            _output_display_path(project_root, run_root, options.bicu_source),
            _output_display_path(project_root, run_root, options.bobc_source),
            _output_display_path(project_root, run_root, options.cwo_source),
        ],
        "source_hashes": {
            "BiCu-10": file_hash(options.bicu_source),
            "BiOBr0.5Cl0.5": file_hash(options.bobc_source),
            "CuWO4": file_hash(options.cwo_source),
            "CuWO4_reference_card": file_hash(options.cwo_card),
        },
        "processed_data": _relative(run_root, artifacts.processed_data),
        "origin_file": _relative(run_root, artifacts.origin_file) if artifacts.origin_file.exists() else None,
        "figure_tif": _relative(run_root, artifacts.figure_tif) if artifacts.figure_tif.exists() else None,
        "preview_png": _relative(run_root, artifacts.preview_png) if artifacts.preview_png.exists() else None,
        "origin_reference_opju": _output_display_path(project_root, run_root, options.reference_opju),
        "origin_status": _sanitize_output_value(run_root, export_status),
        "plot_type": "normalized offset XRD overlay with CuWO4 reference-card sticks",
        "manual_check_required": True,
        "manual_check_items": [
            "confirm XRD peak positions, offsets, normalization, and reference-card identity",
            "reference-card sticks are for manual review only; no phase or crystal-plane assignment is made",
            "inspect PNG preview for Graph4 style, full chemical formula subscripts, requested order, and no template residue",
        ],
        "forbidden_claims": [
            "do not assign phase automatically",
            "do not label crystal planes automatically",
            "do not claim impurity-free automatically",
            "do not infer heterojunction type or electron transfer direction from this plot",
        ],
        "parameters": table.metadata,
    }
    artifacts.metadata.parent.mkdir(parents=True, exist_ok=True)
    artifacts.metadata.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifacts.metadata


def _write_report(
    project_root: Path,
    run_root: Path,
    options: XrdOverlayOptions,
    table: XrdOverlayTable,
    artifacts: XrdOverlayArtifacts,
    export_status: dict[str, object],
) -> Path:
    lines = [
        "# XRD Overlay Report",
        "",
        f"- Status: {'success' if export_status.get('ok') else 'processed_no_origin'}",
        f"- Processed CSV: `{_relative(run_root, artifacts.processed_data)}`",
        f"- Origin OPJU: `{_relative(run_root, artifacts.origin_file) if artifacts.origin_file.exists() else 'not exported'}`",
        f"- TIF: `{_relative(run_root, artifacts.figure_tif) if artifacts.figure_tif.exists() else 'not exported'}`",
        f"- PNG preview: `{_relative(run_root, artifacts.preview_png) if artifacts.preview_png.exists() else 'not exported'}`",
        f"- Reference OPJU: `{_output_display_path(project_root, run_root, options.reference_opju)}`",
        f"- CWO reference card: `{_output_display_path(project_root, run_root, options.cwo_card)}`",
        "",
        "## Series",
        "",
        "| order | label | role | Origin OColor |",
        "|---:|---|---|---:|",
    ]
    roles = ["top sample", "middle sample", "lower sample", "bottom reference-card sticks"]
    for index, (label, color, role) in enumerate(zip(table.legend_labels, table.origin_ocolors, roles), start=1):
        lines.append(f"| {index} | `{label}` | {role} | {color} |")
    lines.extend(
        [
            "",
            "No phase assignment, crystal-plane assignment, mechanism conclusion, or impurity conclusion is made by this output.",
        ]
    )
    artifacts.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return artifacts.report


def _validate_inputs(options: XrdOverlayOptions) -> None:
    for label, path in (
        ("bicu_source", options.bicu_source),
        ("bobc_source", options.bobc_source),
        ("cwo_source", options.cwo_source),
        ("cwo_card", options.cwo_card),
    ):
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"{label} does not exist or is not a file: {path}")
    if options.with_origin and (not options.reference_opju.exists() or not options.reference_opju.is_file()):
        raise FileNotFoundError(f"reference_opju does not exist or is not a file: {options.reference_opju}")


def _resolve_reference_opju(project_root: Path, reference_opju: Path) -> Path:
    return reference_opju if reference_opju.is_absolute() else (project_root / reference_opju).resolve()


def _numeric_xy_points(rows: list[list[float]]) -> list[tuple[float, float]]:
    points: dict[float, float] = {}
    for row in rows:
        if len(row) < 2:
            continue
        x_value = _to_float(row[0])
        y_value = _to_float(row[1])
        if x_value is not None and y_value is not None and math.isfinite(x_value) and math.isfinite(y_value):
            points[float(x_value)] = float(y_value)
    return sorted(points.items(), key=lambda item: item[0])


def _normalized_offset_y(points: list[tuple[float, float]], x_value: float, offset: float) -> float | None:
    max_y = max((y for _x, y in points), default=0.0)
    y_value = _interpolated_y(points, x_value)
    if y_value is None or max_y <= 0:
        return None
    return offset + y_value / max_y


def _interpolated_y(points: list[tuple[float, float]], x_value: float) -> float | None:
    if x_value < points[0][0] or x_value > points[-1][0]:
        return None
    for index, (point_x, point_y) in enumerate(points):
        if abs(point_x - x_value) <= 1e-12:
            return point_y
        if point_x > x_value and index > 0:
            prev_x, prev_y = points[index - 1]
            span = point_x - prev_x
            if span == 0:
                return point_y
            fraction = (x_value - prev_x) / span
            return prev_y + fraction * (point_y - prev_y)
    return points[-1][1]


def _reference_stick_values(grid: list[float], peaks: list[tuple[float, float]]) -> list[float]:
    if not grid or not peaks:
        return [0.0 for _x in grid]
    max_intensity = max(intensity for _x, intensity in peaks)
    values = [0.0 for _x in grid]
    low, high = min(grid), max(grid)
    for two_theta, intensity in peaks:
        if two_theta < low or two_theta > high:
            continue
        index = min(range(len(grid)), key=lambda item: abs(grid[item] - two_theta))
        values[index] = max(values[index], 0.75 * intensity / max_intensity)
    return values


def _write_csv(path: Path, headers: list[str], rows: list[list[float | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(["" if value is None else value for value in row])


def _remove_stale_outputs(artifacts: XrdOverlayArtifacts) -> None:
    for path in (artifacts.origin_file, artifacts.figure_tif, artifacts.preview_png):
        if path.exists():
            path.unlink()


def _ensure_tif_600_dpi(path: Path) -> None:
    try:
        from PIL import Image
    except Exception:
        return
    with Image.open(path) as image:
        output = image.copy()
    if output.width < GRAPH4_FIXED_STYLE.page_width:
        target_height = max(1, round(output.height * (GRAPH4_FIXED_STYLE.page_width / output.width)))
        output = output.resize((GRAPH4_FIXED_STYLE.page_width, target_height))
    output.save(path, format="TIFF", dpi=(600, 600), compression="tiff_lzw")


def _neutral_origin_runtime_root() -> Path:
    candidates: list[Path] = []
    for name in ("LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value) / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path.home() / "AppData" / "Local" / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path("C:/ResearchDataOriginPipeline/origin_runtime"))
    candidates.append(Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime")
    for candidate in candidates:
        if "codex" in str(candidate).casefold():
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    fallback = Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _copy_runtime_artifact(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    shutil.copy2(source, target)


def _to_float(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ps_array(values: list[str]) -> str:
    return "@(" + ", ".join(_ps_quote(value) for value in values) + ")"


def _ps_int_array(values: list[int]) -> str:
    return "@(" + ", ".join(str(int(value)) for value in values) + ")"


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _output_display_path(project_root: Path, run_root: Path, path: Path) -> str:
    rendered = render_output_path(path, project_root=project_root, output_root=run_root)
    return rendered or Path(path).name


def _sanitize_output_value(run_root: Path, value: object) -> object:
    if isinstance(value, dict):
        return {key: _sanitize_output_value(run_root, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_output_value(run_root, item) for item in value]
    if isinstance(value, str):
        return scrub_output_text(value, output_root=run_root)
    return value
