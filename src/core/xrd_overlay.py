from __future__ import annotations

import csv
import json
import math
import subprocess
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from src.core.metadata import file_hash
from src.core.file_utils import ensure_safe_output_file_target
from src.core.template_product_common import extract_xrd_raw_data_rows
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.origin_runtime import copy_runtime_artifact as _copy_runtime_artifact
from src.core.origin_runtime import neutral_origin_runtime_root as _neutral_origin_runtime_root
from src.core.plot_labels import XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE
from src.core.project import ensure_output_path_separate_from_inputs
from src.core.runtime_paths import create_run_output_layout, resolve_output_root
from src.core.xrd_helpers import interpolated_y as _interpolated_y
from src.core.xrd_helpers import relative_path as _relative
from src.core.xrd_helpers import to_finite_float as _to_float
from src.origin.adapter import (
    check_origin_available,
    reexport_tif_from_reopened_opju,
    write_origin_error,
    write_origin_success,
)
from src.origin.operations import quote_labtalk
from src.origin.plot_policy import GRAPH4_FIXED_STYLE
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
    force: bool = False


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
    input_paths = [
        options.bicu_source,
        options.bobc_source,
        options.cwo_source,
        options.cwo_card,
    ]
    if options.with_origin or options.reference_opju.is_file():
        input_paths.append(options.reference_opju)
    ensure_output_path_separate_from_inputs(project_root, output_root, input_paths)
    table = build_xrd_overlay_table(
        options.bicu_source,
        options.bobc_source,
        options.cwo_source,
        options.cwo_card,
    )
    protected_input_hashes = tuple(
        (path, file_hash(path))
        for path in input_paths
    )
    run_timestamp = options.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = output_root / "runs" / f"{run_timestamp}_xrd_bobc_shuire_cwo_overlay"
    planned_artifacts = _xrd_overlay_artifacts(run_root)
    planned_output_files = [
        run_root / "run_manifest.json",
        planned_artifacts.processed_data,
        planned_artifacts.metadata,
        planned_artifacts.report,
    ]
    if options.with_origin:
        planned_output_files.extend(
            (
                planned_artifacts.origin_file,
                planned_artifacts.figure_tif,
                planned_artifacts.preview_png,
                run_root / "reports" / "origin_errors.md",
            )
        )
        origin_ok, origin_message = check_origin_available()
        if (
            not origin_ok
            and options.force
            and any(path.exists() for path in planned_output_files)
        ):
            raise RuntimeError(
                "Origin is unavailable before XRD output preflight: "
                + origin_message
            )
        pre_existing_pids = _xrd_origin_process_ids() if origin_ok else set()
        if pre_existing_pids:
            rendered = ", ".join(
                str(pid) for pid in sorted(pre_existing_pids)
            )
            raise RuntimeError(
                "Origin is already running before XRD output preflight; "
                "refusing to replace any existing product or attach to the "
                f"existing session (PIDs: {rendered})."
            )
    _preflight_xrd_outputs(
        tuple(planned_output_files),
        output_root=output_root,
        force=options.force,
    )
    for path, digest in protected_input_hashes:
        if not path.is_file() or file_hash(path) != digest:
            raise RuntimeError(
                f"Protected XRD input changed during output preflight: {path}"
            )
    layout = create_run_output_layout(
        project_root,
        scope="xrd_bobc_shuire_cwo_overlay",
        command="xrd-overlay",
        mode="with_origin" if options.with_origin else "no_origin",
        input_paths=input_paths,
        timestamp=run_timestamp,
        no_origin=not options.with_origin,
        dry_run=not options.with_origin,
        output_base=output_root / "runs",
    )
    artifacts = _xrd_overlay_artifacts(layout.root)
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
    _remove_stale_outputs(artifacts, force=options.force)
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
    artifacts.origin_file.parent.mkdir(parents=True, exist_ok=True)
    artifacts.preview_png.parent.mkdir(parents=True, exist_ok=True)
    artifacts.figure_tif.parent.mkdir(parents=True, exist_ok=True)
    neutral_root = _neutral_origin_runtime_root()
    with tempfile.TemporaryDirectory(prefix="rdop_xrd_", dir=neutral_root) as runtime_text:
        runtime = Path(runtime_text)
        runtime_origin = runtime / artifacts.origin_file.name
        runtime_png = runtime / artifacts.preview_png.name
        shutil.copy2(options.reference_opju, runtime_origin)

        with _isolated_xrd_originpro_session() as op:
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
            op.save(str(runtime_origin))

        if not runtime_png.exists():
            raise RuntimeError("Origin did not export the PNG preview")
        if not runtime_origin.exists():
            raise RuntimeError("Origin did not save the OPJU project")
        runtime_tif = runtime / artifacts.figure_tif.name
        resolution = reexport_tif_from_reopened_opju(
            runtime_origin,
            "Graph4",
            runtime_tif,
            dpi=600,
        )
        _copy_runtime_artifact(runtime_origin, artifacts.origin_file)
        _copy_runtime_artifact(runtime_png, artifacts.preview_png)
        _copy_runtime_artifact(runtime_tif, artifacts.figure_tif)
    return {
        "ok": True,
        "message": "Graph4 template data replaced and TIF natively exported at validated 600 dpi.",
        "neutral_runtime": True,
        "tif_resolution": {
            key: value
            for key, value in resolution.as_dict().items()
            if key != "path"
        },
    }


@contextmanager
def _isolated_xrd_originpro_session():
    """Yield originpro only when no user Origin session is already running."""

    pre_existing_pids = _xrd_origin_process_ids()
    if pre_existing_pids:
        rendered = ", ".join(str(pid) for pid in sorted(pre_existing_pids))
        raise RuntimeError(
            "Origin is already running before XRD overlay export; refusing to "
            f"attach to or close an existing session (PIDs: {rendered})."
        )
    try:
        import originpro as op
    except Exception as exc:
        raise RuntimeError(
            f"originpro unavailable for OPJU template replacement: {exc}"
        ) from exc

    try:
        yield op
    finally:
        exit_error = ""
        try:
            op.exit()
        except Exception as exc:
            exit_error = f"{type(exc).__name__}: {exc}"
        try:
            remaining_pids = _wait_for_xrd_origin_exit(
                pre_existing_pids,
                timeout_seconds=30.0,
            )
        except Exception as exc:
            raise RuntimeError(
                "Origin lifecycle verification failed after XRD overlay export: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if exit_error or remaining_pids:
            details: list[str] = []
            if exit_error:
                details.append(f"originpro exit raised {exit_error}")
            if remaining_pids:
                details.append(
                    "new Origin process remained after the bounded exit wait "
                    f"(PIDs: {', '.join(str(pid) for pid in sorted(remaining_pids))})"
                )
            raise RuntimeError(
                "Origin lifecycle finalization failed after XRD overlay export; "
                "the product must not be accepted: "
                + "; ".join(details)
            )


def _xrd_origin_process_ids() -> set[int]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process -Name Origin* -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty Id",
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    if completed.returncode:
        raise RuntimeError(
            "Could not inspect existing Origin processes safely: "
            + (completed.stderr or completed.stdout or "PowerShell query failed").strip()
        )
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        try:
            pids.add(int(line.strip()))
        except ValueError:
            continue
    return pids


def _wait_for_xrd_origin_exit(
    pre_existing_pids: set[int],
    *,
    timeout_seconds: float,
) -> set[int]:
    deadline = time.time() + max(0.0, timeout_seconds)
    while True:
        remaining = _xrd_origin_process_ids() - pre_existing_pids
        if not remaining:
            return set()
        if time.time() >= deadline:
            return remaining
        time.sleep(0.5)


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


def _write_metadata(
    project_root: Path,
    run_root: Path,
    options: XrdOverlayOptions,
    table: XrdOverlayTable,
    artifacts: XrdOverlayArtifacts,
    export_status: dict[str, object],
) -> Path:
    processing_status = _xrd_processing_status(options, export_status)
    payload = {
        "dataset_id": "XRD_BiCu_BiOBr_CuWO4_overlay",
        "run_root": _relative(run_root, run_root),
        "data_type": "XRD",
        "processor_name": "xrd_overlay_processor",
        "processing_status": processing_status,
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
    processing_status = _xrd_processing_status(options, export_status)
    lines = [
        "# XRD Overlay Report",
        "",
        f"- Status: {processing_status}",
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


def _xrd_processing_status(
    options: XrdOverlayOptions,
    export_status: dict[str, object],
) -> str:
    if export_status.get("ok"):
        return "success"
    return "fail" if options.with_origin else "processed_no_origin"


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


def _xrd_overlay_artifacts(run_root: Path) -> XrdOverlayArtifacts:
    return XrdOverlayArtifacts(
        processed_data=run_root / "processed_data" / "XRD_BiCu_BiOBr_CuWO4_overlay.csv",
        metadata=run_root / "metadata" / "XRD_BiCu_BiOBr_CuWO4_overlay" / "metadata.json",
        report=run_root / "reports" / "xrd_overlay_report.md",
        origin_file=run_root / "origin_files" / "XRD_BiCu_BiOBr_CuWO4_overlay.opju",
        figure_tif=run_root / "figures_tif" / "XRD_BiCu_BiOBr_CuWO4_overlay.tif",
        preview_png=run_root / "figures_preview" / "XRD_BiCu_BiOBr_CuWO4_overlay.png",
        job_script=run_root / "logs" / "origin_jobs" / "XRD_BiCu_BiOBr_CuWO4_overlay.ps1",
    )


def _preflight_xrd_outputs(
    paths: tuple[Path, ...],
    *,
    output_root: Path,
    force: bool,
) -> None:
    safe_paths = tuple(
        dict.fromkeys(
            ensure_safe_output_file_target(path, output_root=output_root)
            for path in paths
        )
    )
    existing = [path for path in safe_paths if path.exists()]
    if existing and not force:
        rendered = ", ".join(str(path) for path in existing[:8])
        raise FileExistsError(
            "One or more planned XRD overlay outputs already exist; rerun with force=True to overwrite: "
            f"{rendered}"
        )
    directories = [path for path in existing if path.is_dir() and not path.is_symlink()]
    if directories:
        rendered = ", ".join(str(path) for path in directories[:8])
        raise IsADirectoryError(f"Planned XRD file output collides with a directory: {rendered}")
    for path in existing:
        path.unlink()


def _remove_stale_outputs(artifacts: XrdOverlayArtifacts, *, force: bool) -> None:
    _preflight_xrd_outputs(
        (artifacts.origin_file, artifacts.figure_tif, artifacts.preview_png),
        output_root=artifacts.origin_file.parents[1],
        force=force,
    )


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
