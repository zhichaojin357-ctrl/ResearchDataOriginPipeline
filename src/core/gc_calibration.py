"""Explicit, selected GC standard tables; no subset search or raw-GC decoding."""
from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path

from src.core.file_utils import ensure_safe_output_file_target, is_under_or_equal
from src.core.project import ensure_output_path_separate_from_inputs, load_json_compatible_yaml, registry_path
from src.core.runtime_paths import resolve_output_root
from src.processors.calculations import linear_regression, linear_r_squared
from src.processors.profiles import SUPPORTED_PROCESSOR_PROFILES


DATA_TYPE = "GC calibration exported data"


def read_selected_gc_calibrations(source: Path, sheet_name: str) -> list[dict]:
    """Read horizontal concentration/area blocks with an analyte above each header.

    Sheet selection is mandatory: never choose a high-R2 subset automatically.
    All nonblank records in each declared block must be finite numeric pairs.
    """
    import openpyxl

    if source.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("GC selected calibration reader requires XLSX/XLSM")
    with source.open("rb") as handle:
        if handle.read(4) != b"PK\x03\x04":
            raise ValueError("Input is not an OOXML workbook")
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        if sheet_name not in workbook.sheetnames:
            raise ValueError(f"Selected sheet does not exist: {sheet_name}")
        grid = list(workbook[sheet_name].iter_rows(values_only=True))
        curves = []
        for row_index, row in enumerate(grid):
            for column, value in enumerate(row[:-1]):
                label = str(value or "").strip()
                if label not in {"浓度 (mM)", "Concentration (mM)"}:
                    continue
                if str(row[column + 1] or "").strip() not in {"实测峰面积", "峰面积", "Peak area"}:
                    continue
                name = str(grid[row_index - 1][column] or "").strip() if row_index else ""
                if not name and column:
                    name = str(row[column - 1] or "").strip()
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 _+().-]*", name):
                    raise ValueError("Each GC block needs an English analyte name above its header")
                points = []
                for data_index in range(row_index + 1, len(grid)):
                    record = grid[data_index]
                    x = record[column] if column < len(record) else None
                    y = record[column + 1] if column + 1 < len(record) else None
                    if x is None and y is None:
                        break
                    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y)):
                        raise ValueError(f"Non-numeric or incomplete GC point: {name}, row {data_index + 1}")
                    if x < 0 or y < 0:
                        raise ValueError(f"Negative source concentration/area: {name}, row {data_index + 1}")
                    points.append({"concentration_mM": float(x), "peak_area": float(y),
                                   "source_row": data_index + 1,
                                   "concentration_cell": f"{openpyxl.utils.get_column_letter(column + 1)}{data_index + 1}",
                                   "area_cell": f"{openpyxl.utils.get_column_letter(column + 2)}{data_index + 1}"})
                xy = [(p["concentration_mM"], p["peak_area"]) for p in points]
                if len(xy) < 3 or len({p[0] for p in xy}) < 3 or len({p[1] for p in xy}) < 2:
                    raise ValueError(f"GC calibration needs >=3 distinct concentrations and varying response: {name}")
                slope, intercept = linear_regression(xy)
                r2 = linear_r_squared(xy, slope, intercept)
                for point in points:
                    predicted = slope * point["concentration_mM"] + intercept
                    point["predicted_area"] = predicted
                    point["residual_area"] = point["peak_area"] - predicted
                    point["residual_percent_of_prediction"] = 100 * point["residual_area"] / predicted if predicted else None
                    point["back_calculated_concentration_mM"] = (point["peak_area"] - intercept) / slope if slope else None
                curves.append({"analyte": name, "points": points, "slope_candidate": slope,
                               "intercept_candidate": intercept, "r_squared": r2, "point_count": len(xy)})
        if not curves or len({c["analyte"] for c in curves}) != len(curves):
            raise ValueError("No calibration blocks found, or duplicate analyte names")
        return curves
    finally:
        workbook.close()


def run_gc_calibration(project_root: Path, *, source: Path, sheet_name: str,
                       output_root: Path | None = None, with_origin: bool = False,
                       selection_note: str, area_unit: str = "a.u.", plot_only: bool = False) -> dict:
    registry = load_json_compatible_yaml(registry_path(project_root))
    entry = next((e for e in registry["entries"] if e.get("inferred_data_type") == DATA_TYPE), None)
    if not entry or entry.get("supported_in_pipeline") is not True or entry.get("selected_processor") != "gc_calibration_processor":
        raise ValueError("GC calibration is not enabled in the current registry")
    if not selection_note.strip():
        raise ValueError("An explicit selection provenance note is required")
    if not re.fullmatch(r"[A-Za-z0-9 .*/()_-]+", area_unit):
        raise ValueError("Unsupported area-unit text")
    if plot_only:
        with_origin = True
    curves = read_selected_gc_calibrations(source, sheet_name)
    root = resolve_output_root(project_root, explicit=output_root)
    if is_under_or_equal(root.resolve(), project_root.resolve()) or is_under_or_equal(project_root.resolve(), root.resolve()):
        raise ValueError("GC output root must be separate from the source tree")
    ensure_output_path_separate_from_inputs(project_root, root, [source])
    run_dir = root / "gc_calibration" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ensure_safe_output_file_target(run_dir, output_root=root)
    if with_origin:
        from src.origin.operations import origin_process_ids
        if origin_process_ids():
            raise RuntimeError("Origin is already running; user work must be closed or explicitly authorized first")
    run_dir.mkdir(parents=True, exist_ok=False)
    profile = SUPPORTED_PROCESSOR_PROFILES[DATA_TYPE]
    policy = load_json_compatible_yaml(project_root / "config" / "claim_policy.yaml")
    metadata = {"source_file": str(source.resolve()), "source_sheet": sheet_name, "data_type": DATA_TYPE,
                "selected_processor": entry["selected_processor"], "selection_note": selection_note,
                "selection_performed_by_pipeline": False, "plot_only": plot_only, "fit_method": "ordinary least squares with free intercept; unweighted",
                "concentration_unit": "mM", "area_unit": area_unit, "curves": curves,
                "manual_check_required": True, "manual_checks": list(profile["manual_check_items"]),
                "forbidden_claims": list(profile["forbidden_claims"]) + policy["forbidden_claims"],
                "processing_status": "processed_no_origin", "origin_launched": False,
                "visual_review_status": "not_applicable" if not with_origin else "pending",
                "warnings": ["R-squared threshold alone does not establish validated analytical linearity.",
                             "Area unit is unspecified in source; a.u. is a display placeholder." ] if area_unit == "a.u." else []}
    for curve in ([] if plot_only else curves):
        path = run_dir / (curve["analyte"].replace(" ", "_") + "_processed.csv")
        ensure_safe_output_file_target(path, output_root=root)
        with path.open("x", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(curve["points"][0]))
            writer.writeheader()
            writer.writerows(curve["points"])
    _write_report(run_dir, metadata)
    _write_json(run_dir / "metadata.json", metadata)
    if with_origin:
        try:
            metadata["origin_launched"] = True
            metadata["origin_verification"] = _plot_calibrations(run_dir, curves, area_unit)
            metadata["processing_status"] = "origin_exported_pending_visual_review"
        except Exception as exc:
            metadata["processing_status"] = "origin_failed"
            metadata["error"] = str(exc)
            _write_json(run_dir / "metadata.json", metadata)
            raise
        _write_json(run_dir / "metadata.json", metadata)
    print(json.dumps({"run_directory": str(run_dir), "status": metadata["processing_status"]}, ensure_ascii=False))
    return metadata


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _write_report(run_dir: Path, metadata: dict) -> None:
    rows = ["# GC selected standard curves", "", metadata["selection_note"], "",
            "Source sheet: " + metadata["source_sheet"], "",
            "Unweighted ordinary least squares with a free intercept; source areas unchanged.", "",
            "| Analyte | n | Concentrations (mM) | Slope | Intercept | R² |", "|---|---:|---|---:|---:|---:|"]
    for curve in metadata["curves"]:
        concentrations = ", ".join(f'{p["concentration_mM"]:g}' for p in curve["points"])
        rows.append(f'| {curve["analyte"]} | {curve["point_count"]} | {concentrations} | {curve["slope_candidate"]:.8f} | {curve["intercept_candidate"]:.8f} | {curve["r_squared"]:.10f} |')
    rows += ["", "R² alone does not validate the calibration range. Inspect residuals, especially low standards; negative predicted areas are retained in the table.",
             "The residual column is 100 × (measured − predicted) / predicted; it is separate from the source workbook's formatted residual field.",
             "Confirm GC detector/integration units, standard preparation, peak mapping, excluded-point rationale and independent repeat measurements before quantification."]
    (run_dir / "report.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _require(result):
    if not result.ok:
        raise RuntimeError(result.message + ": " + json.dumps(result.payload, ensure_ascii=False, default=str))
    return result.payload


def _plot_calibrations(run_dir: Path, curves: list[dict], area_unit: str) -> dict:
    from PIL import Image
    from src.origin.operations import connect_origin, quote_origin_markup, quote_labtalk, to_origin_path
    from src.origin.plot_policy import GRAPH4_FIXED_STYLE

    op = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    records = []
    try:
        _require(op.new_project())
        for index, curve in enumerate(curves, 1):
            name = curve["analyte"]
            book = "Standards" + str(index)
            _require(op.create_worksheet(book))
            xs = [p["concentration_mM"] for p in curve["points"]]
            ys = [p["peak_area"] for p in curve["points"]]
            _require(op.set_worksheet_data(book, "Sheet1", [xs, ys], ["Concentration", name]))
            _require(op.run_labtalk(f'win -a {book}; wks.ncols=3; wks.col1.type=4; wks.col1.unit$="mM"; fitlr iy:=(1,2) oy:=(1,3);'))
            fit = {"slope": float(op.app.Evaluate("fitlr.b")), "intercept": float(op.app.Evaluate("fitlr.a")),
                   "r_squared": float(op.app.Evaluate("fitlr.r")) ** 2}
            for key, expected in [("slope", curve["slope_candidate"]), ("intercept", curve["intercept_candidate"]), ("r_squared", curve["r_squared"])]:
                if not math.isclose(fit[key], expected, rel_tol=1e-9, abs_tol=1e-8):
                    raise RuntimeError(f"Origin and processor fit disagree: {name}, {key}")
            graph = _require(op.create_graph("Calibration" + str(index), book, "Sheet1", 1, 2, plot_type="scatter"))["graph_name"]
            _require(op.apply_graph4_fixed_style(graph))
            ymax = math.ceil(max(ys) / 10000) * 10000
            xmax = math.ceil(max(xs) / 5) * 5 + 5
            _require(op.set_axis_range(graph, x_min=0, x_max=xmax, y_min=0, y_max=ymax))
            _require(op.set_axis_labels(graph, "Concentration (mM)", f"Peak area ({area_unit})"))
            _require(op.run_labtalk('layer.x.inc=5; layer.y.inc=10000; layer.x.ticks=2; layer.y.ticks=2; layer.x.showAxes=3; layer.y.showAxes=3; layer.x.showLabels=1; layer.y.showLabels=1; layer.y.label.dir=1; layer.y.label.rotate=0; layer.y.label.divideBy=10000; layer.y.label.pt=36; layer.x2.ticks=0; layer.y2.ticks=0; doc -e DY {set %C -c color(255,128,0); set %C -z 9; set %C -lw 3;};'))
            # Show the area scale explicitly; imported areas and fit coefficients stay unscaled.
            _require(op.set_axis_labels(graph, "Concentration (mM)", f"Peak area (10\\+(4) {area_unit})"))
            axis_text = quote_origin_markup(f'\\b(Peak area (10\\+(4) {area_unit}))')
            _require(op.run_labtalk(f'xb.text$="\\b(Concentration (mM))"; yl.text$="{axis_text}";'))
            _require(op.set_legend(graph, position="top-left", entries=[name]))
            legend_layer = op.app.FindGraphLayer(graph)
            for object_index in range(int(legend_layer.GraphObjects.Count)):
                graph_object = legend_layer.GraphObjects.Item(object_index)
                if str(graph_object.Name).lower() == "legend":
                    graph_object.Left = 1500
                    graph_object.Top = 750
            equation = f'y = {fit["slope"]:.4f}x {"+" if fit["intercept"] >= 0 else "-"} {abs(fit["intercept"]):.4f}'
            text = f'\\b({equation})\r\n\\b(R\\+(2) = {fit["r_squared"]:.7f})'
            _require(op.replace_graph_direct_labels(graph, [{"name": "statistics", "text": text,
                                                             "left": 1600, "top": 1150,
                                                             "font_size": 26}], hide_legend=False))
            records.append({"analyte": name, "book": book, "graph": graph, "origin_fit": fit})
        project = run_dir / "GC_calibrations.opju"
        _require(op.save_project(project))
        if not project.is_file() or not project.stat().st_size:
            raise RuntimeError("Origin did not save an OPJU")
        _require(op.new_project())
        _require(op.load_project(project))
        for record, curve in zip(records, curves):
            graph = record["graph"]
            _require(op.run_labtalk(f'win -a {graph};'))
            style = {key: float(op.app.Evaluate(key)) for key in ["page.width", "page.height", "layer.left", "layer.top", "layer.width", "layer.height", "layer.x.label.pt", "layer.y.label.pt", "xb.fsize", "yl.fsize", "legend.fsize"]}
            for key, expected in {"page.width": GRAPH4_FIXED_STYLE.page_width, "page.height": GRAPH4_FIXED_STYLE.page_height,
                                  "layer.left": GRAPH4_FIXED_STYLE.layer_left, "layer.top": GRAPH4_FIXED_STYLE.layer_top,
                                  "layer.width": GRAPH4_FIXED_STYLE.layer_width, "layer.height": GRAPH4_FIXED_STYLE.layer_height,
                                  "layer.x.label.pt": 28, "layer.y.label.pt": 36, "xb.fsize": 36, "yl.fsize": 36, "legend.fsize": 26}.items():
                if abs(style[key] - expected) > .01:
                    raise RuntimeError(f"Saved Origin style mismatch: {graph}, {key}: {style[key]}")
            layer = op.app.FindGraphLayer(graph)
            if int(layer.DataPlots.Count) != 1:
                raise RuntimeError("GC graph must contain exactly one measured scatter series")
            record["plot_mapping_readback"] = _require(op.get_graph_plot_dataset_mappings(graph))
            record["text_readback"] = _require(op.read_graph_text_objects(graph, ["Legend", "statistics", "XB", "YL"]))["objects"]
            data = _require(op.get_worksheet_data(record["book"], "Sheet1"))["columns"]
            for column, key in [(0, "concentration_mM"), (1, "peak_area")]:
                values = data[column]
                if len(values) != len(curve["points"]) or any(not math.isclose(float(a), p[key], rel_tol=1e-12, abs_tol=1e-12) for a, p in zip(values, curve["points"])):
                    raise RuntimeError("Saved OPJU standard values changed")
            expected = (round(style["page.width"] * .6), round(style["page.height"] * .6))
            # Origin truncates raster dimensions; render at the center of the target pixel interval.
            # This is a native vector-to-raster export, without image resizing or DPI relabeling.
            folder = quote_labtalk(to_origin_path(run_dir))
            _require(op.run_labtalk(f'expGraph type:=tif path:="{folder}" filename:="{record["analyte"]}" overwrite:=replace sysopts:=0 tr.Margin:=2 tr1.Unit:=2 tr1.Width:={expected[0] + .5} tr2.TIF.dotsperinch:=600;'))
            _require(op.export_graph(graph, run_dir / (record["analyte"] + ".png"), "png", dpi=150,
                                     pixel_width=round(style["page.width"] * .15)))
            with Image.open(run_dir / (record["analyte"] + ".tif")) as image:
                dpi = tuple(float(v) for v in image.info.get("dpi", (0, 0)))
                effective = (image.width * 1000 / style["page.width"], image.height * 1000 / style["page.height"])
                if image.size != expected or any(abs(d - 600) > .2 for d in (*dpi, *effective)):
                    raise RuntimeError(f"Native 600 dpi verification failed: {image.size}, {dpi}, expected {expected}")
                record.update({"style_readback": style, "tiff_pixels": list(image.size), "tiff_dpi": dpi, "effective_dpi": effective})
        return {"saved_reopened": True, "graphs": records, "png_visual_review": "pending"}
    finally:
        op.close()


def record_gc_visual_review(project_root: Path, run_dir: Path, *, note: str) -> None:
    """Record an operator's actual PNG review after successful native export."""
    root = resolve_output_root(project_root)
    path = ensure_safe_output_file_target(run_dir / "metadata.json", output_root=root)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("processing_status") != "origin_exported_pending_visual_review" or not note.strip():
        raise ValueError("Visual review requires successfully exported plots and a review note")
    for graph in data["origin_verification"]["graphs"]:
        for extension in ("png", "tif"):
            artifact = ensure_safe_output_file_target(run_dir / (graph["analyte"] + "." + extension), output_root=root)
            if not artifact.is_file() or not artifact.stat().st_size:
                raise ValueError("Visual review package is incomplete")
    data["processing_status"] = "origin_verified"
    data["visual_review_status"] = "passed"
    data["origin_verification"]["png_visual_review"] = "passed"
    data["visual_review_note"] = note
    _write_json(path, data)
