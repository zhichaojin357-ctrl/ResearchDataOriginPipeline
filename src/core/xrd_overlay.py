from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from src.core.metadata import file_hash
from src.core.file_utils import ensure_safe_output_file_target
from src.core.image_artifacts import expected_raster_pixels, validate_tif_physical_resolution
from src.core.template_product_common import extract_xrd_raw_data_rows
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.plot_labels import XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE
from src.core.project import ensure_output_path_separate_from_inputs
from src.core.runtime_paths import create_run_output_layout, resolve_output_root
from src.core.xrd_helpers import interpolated_y as _interpolated_y
from src.core.xrd_helpers import relative_path as _relative
from src.core.xrd_helpers import to_finite_float as _to_float
from src.origin.adapter import (
    check_origin_available,
    write_origin_error,
    write_origin_success,
)
from src.origin.operations import OriginOperations, connect_origin, origin_process_ids, quote_labtalk
from src.origin.text_format import origin_bold_text
from src.origin.xrd_annotations import apply_xrd_standard_card_annotations


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
DEFAULT_XRD_GRAPH_TEMPLATE = Path("templates") / "origin_styles" / "graph_templates" / "XRD.otpu"

# This is the reviewed native-XRD binding for the current three-sample CLI.
# It deliberately contains no source OPJU ranges: a fresh project owns two
# real worksheets and all graphs are plotted from the table generated here.
XRD_FRESH_PLOT_FORMAT_CONTRACTS = (
    {"layer_index": 1, "plot_index": 1, "color": 16814848, "line_color": 16814848, "line_width": 1500, "line_style": 0, "connect": 1, "vertical_drop_lines": 0},
    {"layer_index": 1, "plot_index": 2, "color": 33518174, "line_color": 33518174, "line_width": 1500, "line_style": 0, "connect": 1, "vertical_drop_lines": 0},
    {"layer_index": 2, "plot_index": 1, "color": 22106449, "line_color": 22106449, "line_width": 250, "line_style": 0, "connect": 0, "vertical_drop_lines": 1, "vertical_drop_line_color": 17585584, "vertical_drop_line_style": 0, "vertical_drop_line_width": 3},
    {"layer_index": 3, "plot_index": 1, "color": 23709421, "line_color": 23709421, "line_width": 1500, "line_style": 0, "connect": 1, "vertical_drop_lines": 0},
)

XRD_FRESH_ANNOTATION_CONTRACT = {
    "hide_layer_legends": [2, 3],
    "top_series": {
        "semantic_role": "BiCu-10_sample_pattern",
        "display_text": "BiCu-10",
        "layer_index": 1,
        "line": {"name": "RDOPXRDTopLine", "x1": 54.64294981426266, "y1": 4.28, "x2": 46.15937072503422, "y2": 4.28, "color": 23709421, "line_width": 3, "line_type": 1},
        "text": {"name": "RDOPXRDTopText", "left": 4111, "top": 587, "width": 823, "height": 251, "font": 1, "font_size": 26, "color": 1, "rich_text": "\\b(BiCu-10)"},
    },
    "reference_card": {
        "semantic_role": "CuWO4_JCPDS_04-009-6293_reference_sticks",
        "display_text": "CuWO4 JCPDS card No.04-009-6293",
        "layer_index": 2,
        "text": {"name": "RDOPXRDCardText", "left": 2680, "top": 3345, "width": 2819, "height": 226, "font": 71, "font_size": 20, "color": 1, "rich_text": "\\b(\\c17585584(CuWO)\\-(\\c17585584(4))\\c17585584( JCPDS card No.04-009-6293))"},
    },
}


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
    # ``reference_opju`` remains an audit/compatibility parameter.  It is
    # never opened, copied, or used as a graph/product base by this path.
    if options.reference_opju.is_file():
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
        graph_template = _resolve_xrd_graph_template(project_root)
        if not graph_template.is_file():
            raise FileNotFoundError(
                "The project-local fresh XRD graph template is missing: "
                f"{graph_template}"
            )
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
        pre_existing_pids = origin_process_ids() if origin_ok else set()
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
    operations: OriginOperations | None = None
    try:
        # ``connect_origin`` is deliberately fail-closed when an Origin
        # process already exists.  The normal production path therefore never
        # attaches to a possibly user-owned session.
        operations = connect_origin(entrypoint="Origin.Application", visible=False, isolated=True)
        export_status = _build_fresh_xrd_overlay_with_operations(
            project_root,
            table,
            artifacts,
            operations,
        )
    except Exception as exc:
        write_origin_error(project_root, f"xrd-overlay: {exc}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": str(exc)}
    finally:
        if operations is not None:
            closed = operations.close()
            if not closed.ok:
                write_origin_error(
                    project_root,
                    f"xrd-overlay: task-owned Origin close failed: {closed.message}",
                    output_root=artifacts.origin_file.parents[1],
                )
                return {"ok": False, "message": closed.message}
    missing = [
        name
        for name, path in (("origin_file", artifacts.origin_file), ("figure_tif", artifacts.figure_tif), ("preview_png", artifacts.preview_png))
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        message = "Origin export missing required artifacts: " + ", ".join(missing)
        write_origin_error(project_root, f"xrd-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": message, "export_status": export_status}
    write_origin_success(project_root, output_root=artifacts.origin_file.parents[1])
    return {
        "ok": True,
        "message": "Origin export succeeded from a fresh project with the project-local XRD OTPU.",
        **export_status,
    }


def _build_fresh_xrd_overlay_with_operations(
    project_root: Path,
    table: XrdOverlayTable,
    artifacts: XrdOverlayArtifacts,
    operations: OriginOperations,
) -> dict[str, object]:
    """Build the current XRD overlay in a new Origin project.

    The worksheet data are the same normalized/offset values recorded in the
    processed CSV.  No reference OPJU is loaded and no visual raster or
    synthetic curve is inserted.  The OTPU contributes only the native Origin
    graph/page/layer formatting; every plotted X/Y range is made explicit.
    """
    artifacts.origin_file.parent.mkdir(parents=True, exist_ok=True)
    artifacts.preview_png.parent.mkdir(parents=True, exist_ok=True)
    artifacts.figure_tif.parent.mkdir(parents=True, exist_ok=True)
    template_path = _resolve_xrd_graph_template(project_root)
    if not template_path.is_file():
        raise FileNotFoundError(f"XRD graph template is missing: {template_path}")

    created = operations.new_project()
    if not created.ok:
        raise RuntimeError(created.message)
    book2, book3 = _write_xrd_overlay_worksheets(operations, table)
    plotted = operations.create_graph_from_xy_pairs_template(
        "Graph4",
        template_path.resolve(),
        book2,
        _fresh_xrd_xy_ranges(book2, book3, len(table.rows)),
        plot_type="line",
        rescale=False,
        legend=False,
        group_plots=False,
        plot_format_contracts=XRD_FRESH_PLOT_FORMAT_CONTRACTS,
    )
    if not plotted.ok:
        raise RuntimeError(f"fresh XRD OTPU plotting failed: {plotted.message}")
    _verify_xrd_native_bindings(operations, "Graph4", book2, book3, len(table.rows))
    _apply_xrd_native_text_and_axes(operations, "Graph4")
    annotations = apply_xrd_standard_card_annotations(
        operations,
        "Graph4",
        XRD_FRESH_ANNOTATION_CONTRACT,
    )
    if not annotations.get("applied"):
        raise RuntimeError(
            "fresh XRD OTPU annotations failed: "
            + str(annotations.get("reason") or annotations)
        )

    saved = operations.save_project(artifacts.origin_file)
    if not saved.ok or not artifacts.origin_file.is_file():
        raise RuntimeError(f"Origin did not save fresh XRD OPJU: {saved.message}")
    reopened = operations.load_project(artifacts.origin_file)
    if not reopened.ok:
        raise RuntimeError(f"Origin did not reopen fresh XRD OPJU: {reopened.message}")
    _verify_xrd_native_bindings(operations, "Graph4", book2, book3, len(table.rows))
    png = operations.export_graph("Graph4", artifacts.preview_png, "png", dpi=600)
    tif = _export_native_xrd_tif_with_physical_validation(
        operations,
        "Graph4",
        artifacts.figure_tif,
        dpi=600,
    )
    if not png.ok or not tif.get("ok"):
        raise RuntimeError(
            "Origin native XRD export failed: "
            f"PNG={png.message}; TIF={tif.get('message', 'unknown failure')}"
        )
    return {
        "fresh_project": True,
        "graph_template": _output_display_path(project_root, artifacts.origin_file.parent, template_path),
        "reference_opju_loaded": False,
        "native_object_kinds": ["worksheet", "line_plot", "axes", "legend", "vertical_drop_lines", "text"],
        "reopened_before_export": True,
        "png_export": png.payload,
        "tif_export": tif,
        "annotation_status": annotations,
    }


def _export_native_xrd_tif_with_physical_validation(
    operations: OriginOperations,
    graph_name: str,
    target: Path,
    *,
    dpi: int,
) -> dict[str, object]:
    activated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if not activated.ok:
        return {"ok": False, "message": f"Could not activate reopened graph {graph_name!r} before TIFF export."}
    dimensions: dict[str, float] = {}
    for name in ("page.width", "page.height"):
        read = operations.get_labtalk_variable(name)
        try:
            value = float(read.payload.get("value"))
        except (TypeError, ValueError, OverflowError):
            return {"ok": False, "message": f"Reopened XRD graph returned an invalid {name}."}
        if not math.isfinite(value) or value <= 0:
            return {"ok": False, "message": f"Reopened XRD graph returned a non-positive {name}."}
        dimensions[name] = value
    expected_width, _expected_height = expected_raster_pixels(
        dimensions["page.width"],
        dimensions["page.height"],
        dpi=dpi,
    )
    identity = operations.reset_project_identity_for_export()
    if not identity.ok:
        return {"ok": False, "message": "Origin project identity reset failed before native XRD TIFF export."}
    reactivated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if not reactivated.ok:
        return {"ok": False, "message": "Could not reactivate reopened XRD graph before native TIFF export."}
    exported = operations.export_graph(
        graph_name,
        target,
        "tif",
        dpi=dpi,
        pixel_width=expected_width,
    )
    if not exported.ok:
        return {"ok": False, "message": exported.message}
    try:
        evidence = validate_tif_physical_resolution(
            target,
            page_width_origin_units=dimensions["page.width"],
            page_height_origin_units=dimensions["page.height"],
            dpi=dpi,
        ).as_dict()
    except Exception as exc:
        return {"ok": False, "message": scrub_output_text(str(exc))}
    evidence["path"] = target.name
    return {
        "ok": True,
        "message": "Origin native XRD TIFF export passed physical-resolution validation.",
        "evidence": evidence,
    }


def _write_xrd_overlay_worksheets(
    operations: OriginOperations,
    table: XrdOverlayTable,
) -> tuple[str, str]:
    """Write the exact processed-table values into the fresh Origin project."""

    if not table.rows:
        raise RuntimeError("fresh XRD plotting requires processed table rows")
    columns = list(zip(*table.rows))
    if len(columns) != 5:
        raise RuntimeError("fresh XRD processed table must contain X + three samples + card")
    x, bicu, bobc, cwo, card = (_origin_numeric_column(column) for column in columns)
    fillers = [math.nan] * len(x)

    created_book2 = operations.create_worksheet("Book2", "Sheet1")
    if not created_book2.ok:
        raise RuntimeError(created_book2.message)
    book2 = str(created_book2.payload.get("book_name") or "")
    written_book2 = operations.set_worksheet_data(
        book2,
        "Sheet1",
        [x, cwo, x, bobc, fillers, fillers, x, card],
        ["two_theta_deg", CWO_LABEL, "two_theta_deg", BOBC_LABEL, "unused", "unused", "two_theta_deg", CWO_CARD_LABEL],
    )
    if not written_book2.ok:
        raise RuntimeError(written_book2.message)

    created_book3 = operations.create_worksheet("Book3", "Sheet1")
    if not created_book3.ok:
        raise RuntimeError(created_book3.message)
    book3 = str(created_book3.payload.get("book_name") or "")
    written_book3 = operations.set_worksheet_data(
        book3,
        "Sheet1",
        [fillers, fillers, fillers, fillers, x, bicu],
        ["unused", "unused", "unused", "unused", "two_theta_deg", BICU_LABEL],
    )
    if not written_book3.ok:
        raise RuntimeError(written_book3.message)
    _verify_xrd_worksheet_roundtrip(operations, book2, book3, x, bicu, bobc, cwo, card)
    return book2, book3


def _origin_numeric_column(values: object) -> list[float]:
    column: list[float] = []
    for value in values if isinstance(values, tuple) else list(values):
        if value is None:
            column.append(math.nan)
            continue
        number = float(value)
        column.append(number if math.isfinite(number) else math.nan)
    return column


def _verify_xrd_worksheet_roundtrip(
    operations: OriginOperations,
    book2: str,
    book3: str,
    x: list[float],
    bicu: list[float],
    bobc: list[float],
    cwo: list[float],
    card: list[float],
) -> None:
    actual2 = operations.get_worksheet_data(book2, "Sheet1")
    actual3 = operations.get_worksheet_data(book3, "Sheet1")
    if not actual2.ok or not actual3.ok:
        raise RuntimeError("fresh XRD worksheet readback failed")
    columns2 = actual2.payload.get("columns")
    columns3 = actual3.payload.get("columns")
    if not isinstance(columns2, list) or not isinstance(columns3, list) or len(columns2) < 8 or len(columns3) < 6:
        raise RuntimeError("fresh XRD worksheet readback has the wrong column shape")
    expected = ((columns2[0], x), (columns2[1], cwo), (columns2[2], x), (columns2[3], bobc), (columns2[6], x), (columns2[7], card), (columns3[4], x), (columns3[5], bicu))
    if any(not _numeric_columns_match(actual, intended) for actual, intended in expected):
        raise RuntimeError("fresh XRD worksheet readback differs from the processed table")


def _numeric_columns_match(actual: object, expected: list[float]) -> bool:
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False
    for got, wanted in zip(actual, expected):
        try:
            got_number = float(got)
        except (TypeError, ValueError):
            return False
        if math.isnan(wanted):
            if not math.isnan(got_number):
                return False
        elif not math.isclose(got_number, wanted, rel_tol=1e-12, abs_tol=1e-12):
            return False
    return True


def _fresh_xrd_xy_ranges(book2: str, book3: str, row_count: int) -> tuple[dict[str, object], ...]:
    if row_count < 2:
        raise ValueError("fresh XRD graph requires at least two processed rows")
    return (
        {"book_name": book2, "sheet_index": 1, "x_col": 1, "y_col": 2, "row_from": 1, "row_to": row_count, "layer_index": 1},
        {"book_name": book2, "sheet_index": 1, "x_col": 3, "y_col": 4, "row_from": 1, "row_to": row_count, "layer_index": 1},
        {"book_name": book2, "sheet_index": 1, "x_col": 7, "y_col": 8, "row_from": 1, "row_to": row_count, "layer_index": 2},
        {"book_name": book3, "sheet_index": 1, "x_col": 5, "y_col": 6, "row_from": 1, "row_to": row_count, "layer_index": 3},
    )


def _verify_xrd_native_bindings(
    operations: OriginOperations,
    graph_name: str,
    book2: str,
    book3: str,
    row_count: int,
) -> None:
    expected = {
        1: [(book2, 1, 2), (book2, 3, 4)],
        2: [(book2, 7, 8)],
        3: [(book3, 5, 6)],
    }
    for layer_index, ranges in expected.items():
        mappings = operations.get_graph_plot_dataset_mappings(graph_name, layer_index)
        if not mappings.ok:
            raise RuntimeError(f"fresh XRD graph mapping readback failed for layer {layer_index}: {mappings.message}")
        items = mappings.payload.get("plot_mappings")
        if not isinstance(items, list) or len(items) != len(ranges):
            raise RuntimeError(f"fresh XRD graph has incorrect native plot count in layer {layer_index}")
        for item, (book, x_col, y_col) in zip(items, ranges):
            if not isinstance(item, dict) or item.get("status") != "ready" or int(item.get("row_from", 0)) != 1 or int(item.get("row_to", -1)) != row_count:
                raise RuntimeError(f"fresh XRD graph native range mapping failed in layer {layer_index}")
            x_name = str(item.get("x_dataset") or "")
            y_name = str(item.get("y_dataset") or "")
            if not (x_name.startswith(f"{book}_") and y_name.startswith(f"{book}_")):
                raise RuntimeError(f"fresh XRD graph uses a non-fresh worksheet range in layer {layer_index}")
            if not (x_name.endswith(_origin_column_letter(x_col)) and y_name.endswith(_origin_column_letter(y_col))):
                raise RuntimeError(f"fresh XRD graph worksheet columns do not match the binding contract in layer {layer_index}")


def _origin_column_letter(index: int) -> str:
    if index < 1 or index > 26:
        raise ValueError("XRD worksheet column index must be in A-Z")
    return chr(ord("A") + index - 1)


def _apply_xrd_native_text_and_axes(operations: OriginOperations, graph_name: str) -> None:
    """Apply reviewed titles and legend as editable, native Origin objects."""

    graph = quote_labtalk(graph_name)
    configured = operations.run_labtalk(
        f'win -a "{graph}"; '
        'layer -s 1; layer.x.from=5; layer.x.to=80; layer.y.from=0; layer.y.to=4.6; '
        'layer -s 2; layer.x.from=5; layer.x.to=80; layer.y.from=0; layer.y.to=4.6; '
        'layer -s 3; layer.x.from=5; layer.x.to=80; layer.y.from=0; layer.y.to=4.6; '
        'layer -s 1;'
    )
    if not configured.ok:
        raise RuntimeError("fresh XRD OTPU axis setup failed")
    layer = operations._graph_layer(graph_name, 1)
    if layer is None:
        raise RuntimeError("fresh XRD OTPU Layer1 is unavailable for the native legend")
    try:
        legend = layer.GraphObjects["Legend"]
    except Exception:
        legend = None
    if legend is None:
        raise RuntimeError("fresh XRD OTPU does not contain its native Layer1 legend holder")
    try:
        legend.Text = "\\l(2)\\b( BiOBr\\-(0.5)Cl\\-(0.5))\r\n\\l(1)\\b( CuWO\\-(4))"
        legend.Left = XRD_SAMPLE_LEGEND_LEFT
        legend.Top = XRD_SAMPLE_LEGEND_TOP + XRD_SAMPLE_LEGEND_ROW_STEP
        legend.Width = XRD_SAMPLE_LEGEND_WIDTH
        legend.Height = XRD_SAMPLE_LEGEND_ROW_STEP * 2
        legend.Show = 1
    except Exception as exc:
        raise RuntimeError(f"fresh XRD OTPU native legend setup failed: {exc}") from exc
    _set_graph_object_format(legend)
    for prop in ("border", "frame", "fill", "fillarea"):
        try:
            legend.SetNumProp(prop, 0)
        except Exception:
            pass
    # The verified OTPU already owns the native XB/YL title objects.  Reusing
    # ``label -s -xb/-yl`` here would create a second pair on some Origin
    # builds, producing visibly overlapping titles.  Preserve the template
    # objects and read their actual properties instead.
    checked = operations.run_labtalk(
        f'win -a "{graph}"; layer -s 1; '
        'string __rdop_xrd_x_title$=xb.text$; string __rdop_xrd_y_title$=yl.text$;'
    )
    if not checked.ok:
        raise RuntimeError("fresh XRD OTPU axis-title readback failed")
    x_title = str(operations.get_labtalk_variable("__rdop_xrd_x_title$").payload.get("value") or "")
    y_title = str(operations.get_labtalk_variable("__rdop_xrd_y_title$").payload.get("value") or "")
    if "θ" not in x_title or "Intensity" not in y_title:
        raise RuntimeError("fresh XRD OTPU native axis titles do not match the XRD contract")


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
        "origin_reference_opju_role": "audit_compatibility_only_not_loaded_for_fresh_plot",
        "origin_graph_template": _output_display_path(project_root, run_root, _resolve_xrd_graph_template(project_root)),
        "origin_status": _sanitize_output_value(run_root, export_status),
        "plot_type": "normalized offset XRD overlay with CuWO4 reference-card sticks",
        "manual_check_required": True,
        "manual_check_items": [
            "confirm XRD peak positions, offsets, normalization, and reference-card identity",
            "reference-card sticks are for manual review only; no phase or crystal-plane assignment is made",
            "inspect PNG preview for Graph4 style, full chemical formula subscripts, requested order, and no template residue",
        ],
        "forbidden_claims": [
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
        f"- Reference OPJU (audit compatibility only; not loaded): `{_output_display_path(project_root, run_root, options.reference_opju)}`",
        f"- Fresh Origin graph template: `{_output_display_path(project_root, run_root, _resolve_xrd_graph_template(project_root))}`",
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
            "Reference-card data are retained as traceable phase-comparison evidence. No crystal-plane, mechanism, or impurity-free conclusion is made by this output.",
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


def _resolve_reference_opju(project_root: Path, reference_opju: Path) -> Path:
    return reference_opju if reference_opju.is_absolute() else (project_root / reference_opju).resolve()


def _resolve_xrd_graph_template(project_root: Path) -> Path:
    return (project_root / DEFAULT_XRD_GRAPH_TEMPLATE).resolve()


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
