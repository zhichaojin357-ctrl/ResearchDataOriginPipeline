"""CHI data preparation and verification around the existing Graph4 helper."""
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from src.core.file_utils import ensure_safe_output_file_target, prepare_safe_output_file_targets
from src.origin.adapter import build_origin_plot_job, _run_origin_job, _wait_for_no_origin_process
from src.origin.operations import connect_origin, quote_labtalk, to_origin_path
from src.origin.plot_policy import GRAPH4_FIXED_STYLE
from src.processors.eis import read_eis_measurements, eis_measured_plot_rows


def _require(result):
    if not result.ok:
        raise RuntimeError(result.message + ": " + str(result.payload))
    return result.payload


def _write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _slug(material):
    return re.sub(r"[^A-Za-z0-9]+", "_", material).strip("_")


def prepare_chi_origin_jobs(project_root, root, stage, plots, eis_records):
    """Keep source order and every measured point. No fitting or selection."""
    items = []
    palette = (28471808, 16818150, 24354304, 16801493, 32093270, 27752908)
    for plot in plots:
        series = plot["series"]
        xs = [[p["potential_V"] for p in s["points"]] for s in series]
        same_x = all(values == xs[0] for values in xs[1:])
        labels = tuple(f'{s["frequency_Hz"]:g} Hz' for s in series)
        if same_x:
            headers = ["potential_v", *labels]
            rows = [[x, *[s["points"][i]["one_over_Cs_squared_F-2"] for s in series]] for i, x in enumerate(xs[0])]
            pairs = tuple((1, i+2) for i in range(len(series)))
        else:
            headers = [h for label in labels for h in ("Potential_" + label, label)]
            rows = [[v for s in series for v in ((s["points"][i]["potential_V"], s["points"][i]["one_over_Cs_squared_F-2"]) if i < len(s["points"]) else (None, None))] for i in range(max(len(s["points"]) for s in series))]
            pairs = tuple((i*2+1, i*2+2) for i in range(len(series)))
        source = stage / "source_data" / ("MT_" + plot["slug"] + ".csv")
        _write_csv(source, headers, rows)
        job = build_origin_plot_job(project_root, "MT_" + plot["slug"], source,
                                   "Potential (V)", r"1/C\+(2) (10\+(9) F\+(-2))", "Mott-Schottky", output_root=stage)
        _write_csv(job.plot_csv, headers, rows)
        job = replace(job, labels=labels, column_count=len(headers), xy_column_pairs=pairs, y_tick_divisor=1e9, force=True,
                      curve_colors=tuple(palette[(int(s["frequency_Hz"])-2000)//1000] for s in series))
        items.append({"kind": "MT", "material": plot["material"], "repeat": plot["repeat"], "slug": plot["slug"],
                      "job": job, "rows": rows, "pairs": pairs, "source_series": series,
                      "project_target": root / "04_MT Origin绘图工程" / plot["material"] / (plot["slug"] + ".opju")})
    for record in eis_records:
        sources = [Path(p) for p in record["source_files"] if Path(p).suffix.lower() in {".txt", ".csv"}]
        sources.sort(key=lambda p: (p.suffix.lower() != ".txt", str(p)))
        if not sources:
            raise ValueError("EIS acquisition lacks readable export: " + record["id"])
        source = Path(record["input_directory"]) / sources[0]
        measurement = read_eis_measurements(source)
        rows = eis_measured_plot_rows(measurement.points)
        plot_rows = eis_measured_plot_rows(measurement.points, scale=1e-3)
        if len(rows) != record["row_count"]:
            raise ValueError("Existing EIS reader dropped source rows: " + record["id"])
        slug = f'EIS_{_slug(record["material"])}_{record["condition"]:g}s_r{record["repeat"]}_{record["id"]}'
        table = stage / "source_data" / (slug + ".csv")
        _write_csv(table, ["z_real_ohm", "minus_z_imag_ohm", "frequency_hz", "impedance_magnitude_ohm", "phase_deg"], rows)
        job = build_origin_plot_job(project_root, slug, table, "Z' (kΩ)", '-Z" (kΩ)', "EIS", source_file=source, output_root=stage)
        label = f'{record["material"]}, {record["condition"]:g} s, rep {record["repeat"]}'
        if any("label collision" in w for w in record.get("warnings", [])):
            label += f' ({record["id"]})'
        _write_csv(job.plot_csv, ["Zreal_kohm", "minus_Zimag_kohm"], [r[:2] for r in plot_rows])
        job = replace(job, labels=(label,), column_count=2, xy_column_pairs=((1, 2),), force=True,
                      origin_file=stage / "origin_files" / ("EIS_" + _slug(record["material"]) + ".opju"))
        items.append({"kind": "EIS", "material": record["material"], "repeat": record["repeat"], "slug": slug,
                      "record_id": record["id"], "job": job, "rows": [r[:2] for r in plot_rows], "pairs": ((1, 2),),
                      "raw_rows": rows, "reader_metadata": {**measurement.to_metadata(), "plot_unit": "kohm", "ohm_to_plot_multiplier": 1e-3},
                      "project_target": root / "08_EIS Origin绘图工程" / record["material"] / ("EIS_" + _slug(record["material"]) + ".opju")})
    return items


def _verify_graph(op, item):
    job = item["job"]
    graph = job.page_name
    _require(op.run_labtalk(f'win -a {graph};'))
    keys = ["page.width", "page.height", "layer.left", "layer.top", "layer.width", "layer.height",
            "layer.x.thickness", "layer.y.thickness", "layer.x.label.pt", "layer.y.label.pt",
            "layer.x.label.bold", "layer.y.label.bold"]
    style = {key: float(op.app.Evaluate(key)) for key in keys}
    if job.y_tick_divisor is not None:
        style["layer.y.label.divideBy"] = float(op.app.Evaluate("layer.y.label.divideBy"))
        if not math.isclose(style["layer.y.label.divideBy"], job.y_tick_divisor, rel_tol=1e-12):
            raise RuntimeError("Scientific Y-axis multiplier was not applied: " + graph)
    fixed = GRAPH4_FIXED_STYLE
    values = [fixed.page_width, fixed.page_height, fixed.layer_left, fixed.layer_top, fixed.layer_width,
              fixed.layer_height, fixed.axis_line_width, fixed.axis_line_width, fixed.x_tick_label_size,
              fixed.y_tick_label_size, 1, 1]
    for key, expected in zip(keys, values):
        if abs(style[key]-expected) > .01:
            raise RuntimeError(f"Existing-helper style mismatch: {graph}, {key}: {style[key]} != {expected}")
    layer = op.app.FindGraphLayer(graph)
    if int(layer.DataPlots.Count) != len(item["pairs"]):
        raise RuntimeError("Wrong curve count: " + graph)
    mapping = _require(op.get_graph_plot_dataset_mappings(graph))
    if mapping["mapping_failure_count"]:
        raise RuntimeError("Curve binding readback failed: " + graph)
    ranges = {k: float(op.app.Evaluate(k)) for k in ("layer.x.from", "layer.x.to", "layer.y.from", "layer.y.to")}
    for mapped, (x_col, y_col) in zip(mapping["plot_mappings"], item["pairs"]):
        x_book, x_letter = mapped["x_dataset"].rsplit("_", 1)
        y_book, y_letter = mapped["y_dataset"].rsplit("_", 1)
        if x_book != y_book or x_letter.split("@")[0] != chr(64+x_col) or y_letter.split("@")[0] != chr(64+y_col):
            raise RuntimeError("Curve X/Y columns differ from prepared input: " + graph)
        actual = _require(op.get_worksheet_data(x_book, "1"))["columns"]
        expected_points = [(r[x_col-1], r[y_col-1]) for r in item["rows"] if r[x_col-1] is not None and r[y_col-1] is not None]
        for x, y in expected_points:
            for axis, value in (("x", x), ("y", y)):
                lo, hi = sorted([ranges[f"layer.{axis}.from"], ranges[f"layer.{axis}.to"]])
                if not lo-abs(hi-lo)*1e-10 <= value <= hi+abs(hi-lo)*1e-10:
                    raise RuntimeError("A measured point is clipped by the axis range: " + graph)
        if mapped["row_from"] != 1 or mapped["row_count"] != len(expected_points):
            raise RuntimeError("Wrong plotted row range: " + graph)
        for i, (x, y) in enumerate(expected_points):
            if not math.isclose(float(actual[x_col-1][i]), x, rel_tol=1e-12, abs_tol=1e-14) or not math.isclose(float(actual[y_col-1][i]), y, rel_tol=1e-12, abs_tol=1e-14):
                raise RuntimeError("Saved plot values differ from current data: " + graph)
    objects = _require(op.read_graph_text_objects(graph, ["XB", "YL", "Legend"]))["objects"]
    for obj in objects:
        native = next(layer.GraphObjects.Item(i) for i in range(int(layer.GraphObjects.Count))
                      if str(layer.GraphObjects.Item(i).Name).casefold() == obj["name"].casefold())
        size = float(native.GetNumProp("fsize"))
        expected_size = 26 if obj["name"].casefold() == "legend" else 36
        if abs(size-expected_size) > .01:
            raise RuntimeError(f"Wrong text size on {graph}: {obj['name']}={size}")
        if obj["name"].casefold() == "legend" and any(abs(float(native.GetNumProp(k))) > .05 for k in ("background", "border", "frame", "fill")):
            raise RuntimeError("Legend has a frame or fill: " + graph)
    widths = [float(layer.DataPlots.Item(i).GetNumProp("line.width")) for i in range(int(layer.DataPlots.Count))]
    if any(abs(width-3) > .01 for width in widths):
        raise RuntimeError(f"Wrong line width on {graph}: {widths}")
    return {"style": style, "axis_ranges": ranges, "mapping": mapping, "text": objects, "line_widths_pt": widths,
            "labels": list(job.labels), "plot_count": len(item["pairs"]), "saved_reopened": True}


def render_chi_with_existing_helper(project_root, root, plots, eis_records, *, stage=None, redraw_kinds=None):
    """Stage real helper output; replace final products after PNG review."""
    from PIL import Image
    if stage is None:
        stage = Path(tempfile.mkdtemp(prefix="origin_replot_", dir=root / "07_自动化处理脚本"))
    else:
        stage = ensure_safe_output_file_target(Path(stage), output_root=root / "07_自动化处理脚本")
        if not stage.is_dir() or not stage.name.startswith("origin_replot_"):
            raise ValueError("Resume requires this package's task-owned Origin stage")
    items = prepare_chi_origin_jobs(project_root, root, stage, plots, eis_records)
    projects = defaultdict(list)
    for item in items:
        item["job"].origin_file.parent.mkdir(parents=True, exist_ok=True)
        item["job"].preview_png.parent.mkdir(parents=True, exist_ok=True)
        item["job"].figure_tif.parent.mkdir(parents=True, exist_ok=True)
        projects[item["job"].origin_file].append(item)
    for project, group in projects.items():
        if redraw_kinds is not None and group[0]["kind"] not in redraw_kinds and project.is_file():
            print("Reuse staged helper project, verify again: " + project.name, flush=True)
            continue
        print("Origin helper: " + project.name, flush=True)
        run = _run_origin_job(group[0]["job"], additional_jobs=tuple(i["job"] for i in group[1:]))
        (stage / (project.stem + "_helper.log")).write_text(run.stdout + "\n" + run.stderr, encoding="utf-8")
        if run.returncode or not project.is_file():
            raise RuntimeError("Existing Origin helper failed: " + project.name + "\n" + run.stderr[-2500:])
        if not _wait_for_no_origin_process(timeout_seconds=15):
            raise RuntimeError("Origin helper did not close its session")
    evidence, installs = [], []
    op = connect_origin(isolated=True, visible=False)
    try:
        for project, group in projects.items():
            print("Reopen/verify: " + project.name, flush=True)
            _require(op.new_project())
            _require(op.load_project(project))
            # Preserve complete editable measurement/calculation tables.
            for item in group:
                print("Verify/export: " + item["job"].page_name, flush=True)
                if item["kind"] == "MT":
                    headers = ["potential_V", "Zreal_ohm", "Zimag_ohm", "Zabs_ohm", "phase_deg", "frequency_Hz", "Cs_F", "one_over_Cs_squared_F-2"]
                    rows = [[p[k] for k in headers] for s in item["source_series"] for p in s["points"]]
                    name = "Calculations"
                else:
                    headers = ["Zreal_ohm", "minus_Zimag_ohm", "frequency_Hz", "Zabs_ohm", "phase_deg"]
                    rows, name = item["raw_rows"], "Raw" + item["record_id"]
                pages = _require(op.list_worksheets())["pages"]
                if not any(p["name"] == name for p in pages):
                    book = _require(op.create_worksheet(name, "Sheet1"))["book_name"]
                    _require(op.set_worksheet_data(book, "Sheet1", list(map(list, zip(*rows))), headers))
            _require(op.save_project(project))
            _require(op.new_project())
            _require(op.load_project(project))
            installs.append((project, group[0]["project_target"]))
            for item in group:
                proof = _verify_graph(op, item)
                job = item["job"]
                expected = (round(proof["style"]["page.width"]*.6), round(proof["style"]["page.height"]*.6))
                exports = {}
                for fmt, extension in [("png", ".png"), ("tif", ".tif"), ("svg", ".svg"), ("pdf", ".pdf")]:
                    native = stage / ("export_" + fmt) / (item["slug"] + extension)
                    native.parent.mkdir(exist_ok=True)
                    if fmt in {"png", "tif"}:
                        folder = quote_labtalk(to_origin_path(native.parent))
                        _require(op.run_labtalk(f'win -a {job.page_name}; expGraph type:={fmt} path:="{folder}" filename:="{native.stem}" overwrite:=replace sysopts:=0 tr.Margin:=2 tr1.Unit:=2 tr1.Width:={expected[0]+.5} tr2.{fmt.upper()}.dotsperinch:=600;'))
                        with Image.open(native) as image:
                            dpi = [float(v) for v in image.info.get("dpi", (0, 0))]
                            effective = [image.width*1000/proof["style"]["page.width"], image.height*1000/proof["style"]["page.height"]]
                            if image.size != expected or any(abs(v-600) > .2 for v in (*dpi, *effective)):
                                raise RuntimeError("Native 600dpi verification failed: " + str(native))
                    else:
                        _require(op.export_graph(job.page_name, native, fmt))
                    base = "05_MT高清图像" if item["kind"] == "MT" else "09_EIS高清图像"
                    target = root / base / {"png": "PNG", "tif": "TIFF", "svg": "SVG", "pdf": "PDF"}[fmt] / native.name
                    installs.append((native, target))
                    exports[fmt] = {"staged": str(native), "target": str(target.relative_to(root))}
                evidence.append({"kind": item["kind"], "material": item["material"], "repeat": item["repeat"],
                                 "graph": job.page_name, "project": str(item["project_target"].relative_to(root)),
                                 **proof, "exports": exports, "reader_metadata": item.get("reader_metadata")})
        return {"stage": str(stage), "helper": str(items[0]["job"].helper_script),
                "style_source": "existing cached Graph4 helper/config/plot_style.yaml", "graphs": evidence,
                "installs": [[str(a), str(b)] for a, b in installs], "visual_review_status": "pending"}
    finally:
        op.close()


def _install_chi_products(root, result, *, force=False):
    targets = [Path(target) for _, target in result["installs"]]
    for source, target in result["installs"]:
        if not Path(source).is_file() or not Path(source).stat().st_size:
            raise ValueError("Staged artifact missing: " + source)
        ensure_safe_output_file_target(Path(target), output_root=root)
    prepare_safe_output_file_targets(targets, output_root=root, force=force, context="CHI Origin products")
    for source, target in result["installs"]:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def install_verified_chi_redraw(root, result, *, review_note):
    if not review_note.strip():
        raise ValueError("Actual PNG review note is required")
    _install_chi_products(root, result, force=True)
    result["visual_review_status"] = "passed"
    result["visual_review_note"] = review_note


def plot_chi_mott(project_root, root, plots):
    result = render_chi_with_existing_helper(project_root, root, plots, [])
    _install_chi_products(root, result)
    return result
