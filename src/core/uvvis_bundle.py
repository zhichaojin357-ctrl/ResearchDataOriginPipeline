"""Combine verified DRS/Tauc products and draw current-data gap candidates.

Readers, signal conversion, native graph creation and style acceptance remain
owned by the existing template pipeline. This module only fits explicit
intervals and packages its two accepted graphs into one editable project.
"""
from __future__ import annotations

import csv
import json
import math
import shutil
import tempfile
from pathlib import Path

from src.core.file_utils import prepare_safe_output_file_targets
from src.core.origin_runtime import neutral_origin_runtime_root, copy_runtime_artifact
from src.core.origin_style_assets import read_graph_data_snapshot
from src.core.template_numeric import _linear_fit
from src.core.table_reader import read_table, coerce_numeric_rows
from src.core.template_product_common import build_default_root_map, _resolve_pairing_path
from src.processors.calculations import uvvis_transmittance_percent_processed_table
from src.core.template_product_builder import (
    _export_native_tif_with_physical_validation, _strict_style_readback,
)
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_mimic import read_graph_style_snapshot
from src.origin.text_format import origin_bold_text


def fit_tauc_intervals(csv_path: Path, labels: list[str], intervals: dict[str, list[float]]) -> list[dict]:
    """Fit the supplied edge intervals, without picking a model or clipping data."""
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or len(rows[0]) != 2 * len(labels) or set(intervals) != set(labels):
        raise ValueError("Tauc data/labels/explicit fit intervals do not match")
    results = []
    for index, label in enumerate(labels):
        bounds = intervals[label]
        if len(bounds) != 2 or not all(math.isfinite(v) for v in bounds) or bounds[0] >= bounds[1]:
            raise ValueError(f"Invalid Tauc interval for {label}")
        points = []
        for row in rows[1:]:
            x, y = row[2 * index:2 * index + 2]
            if not x and not y:
                continue
            x, y = float(x), float(y)
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Nonfinite Tauc input")
            if bounds[0] <= x <= bounds[1]:
                points.append((x, y))
        if len(points) < 5:
            raise ValueError(f"Tauc interval for {label} has fewer than five points")
        fit = _linear_fit([x for x, y in points], [y for x, y in points])
        if not fit or fit["slope"] <= 0 or fit["r_squared"] < 0.98:
            raise ValueError(f"Tauc interval for {label} is not a positive linear edge (R2 >= 0.98)")
        gap = -fit["intercept"] / fit["slope"]
        if not 0 < gap < bounds[0]:
            raise ValueError(f"Tauc intercept for {label} is not below the fitted positive-energy interval")
        results.append({"sample": label, **fit, "Eg_candidate_eV": gap,
                        "requested_interval_eV": bounds, "used_interval_eV": [min(x for x,y in points), max(x for x,y in points)],
                        "point_count": len(points), "manual_check_required": True})
    return results


def _require(result: object, context: str) -> None:
    ok = result.get("ok") if isinstance(result, dict) else getattr(result, "ok", False)
    if not ok:
        message = result.get("message", "") if isinstance(result, dict) else getattr(result, "message", "")
        raise RuntimeError(f"{context}: {message}")


def _graph_signature(snapshot: dict) -> list[tuple]:
    if snapshot.get("status") != "ready":
        raise RuntimeError("Graph X/Y readback is unavailable")
    return [(p.get("x_values"), p.get("y_values"), p.get("plot_row_from"), p.get("plot_row_to"))
            for p in snapshot.get("plots", [])]


def _csv_signature(path: Path) -> list[tuple]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    signatures = []
    for column in range(0, len(rows[0]), 2):
        pairs = [(float(row[column]), float(row[column + 1])) for row in rows[1:] if row[column] and row[column + 1]]
        signatures.append(([x for x,y in pairs], [y for x,y in pairs], 1, len(pairs)))
    return signatures


def _bundle_plot_style_contracts(labels: list[str], overrides: dict | None) -> list[dict]:
    if overrides is None:
        return []
    if not isinstance(overrides, dict) or any(label not in overrides for label in labels):
        raise ValueError("bundle_plot_styles must specify each current sample")
    contracts = []
    for label in labels:
        style = overrides[label]
        rgb = style.get("rgb") if isinstance(style, dict) else None
        dash = style.get("line_style", 0) if isinstance(style, dict) else None
        if not isinstance(rgb, list) or len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb):
            raise ValueError(f"Invalid bundle RGB color for {label}")
        if type(dash) is not int or dash not in (0, 1, 2):
            raise ValueError(f"Invalid bundle line style for {label}")
        contracts.append({"sample": label, "rgb": rgb, "line_style": dash,
                          "color_code": 0x01000000 + rgb[0] + rgb[1] * 256 + rgb[2] * 65536})
    return contracts


def _bundle_plot_styles(ops: object, graph: str, contracts: list[dict], *, apply: bool) -> list[dict]:
    if not contracts:
        return []
    _require(ops.run_labtalk(f'win -a "{graph}";'), "Activate user palette graph")
    names = ops._plot_names(graph)
    if len(names) != len(contracts):
        raise RuntimeError("User palette and graph series counts differ")
    readback = []
    for index, (name, contract) in enumerate(zip(names, contracts), 1):
        red, green, blue = contract["rgb"]
        color = f"color({red},{green},{blue})"
        if apply:
            _require(ops.run_labtalk(f'set {name} -cse {color}; set {name} -cl {color}; set {name} -d {contract["line_style"]};'), "Apply current sample colors")
        actual = {}
        for option, expected in (("cl", contract["color_code"]), ("d", contract["line_style"])):
            variable = f"__uv_bundle_{index}_{option}"
            _require(ops.run_labtalk(f"get {name} -{option} {variable};"), "Query saved sample color/style")
            value = ops.get_labtalk_variable(variable)
            _require(value, "Read saved sample color/style")
            actual[option] = float(value.payload["value"])
            if not math.isclose(actual[option], expected, rel_tol=0, abs_tol=1e-6):
                raise RuntimeError(f'Palette readback mismatch for {contract["sample"]}: {option}')
        readback.append({**contract, "readback": actual})
    return readback


def _write_bundle_transmission_conversion(ops: object, project_root: Path, entry: dict, runtime: Path) -> list[dict]:
    if entry.get("transmittance_conversion") != "percent_to_absorbance_log10":
        return []
    roots = build_default_root_map(project_root)
    source_root = roots[entry["selected_data_root_label"]]
    audits = []
    for index, (relative, label) in enumerate(zip(entry["selected_data_relative_paths"], entry["legend_entries"]), 1):
        source = _resolve_pairing_path(source_root, relative)
        rows = read_table(source)
        headers, values = uvvis_transmittance_percent_processed_table(coerce_numeric_rows(rows), rows)
        book = f"Transmission{index}"
        _write_verified_bundle_worksheet(ops, book, list(map(list, zip(*values))), headers)
        target = runtime / f"Transmission_conversion_{index}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(values)
        audits.append({"sample": label, "source_file": source.name, "csv": target.name, "workbook": book, "sheet": "Sheet1",
                       "points": len(values), "above_100_percent": sum(row[1] > 100 for row in values),
                       "negative_absorbance_points": sum(row[3] < 0 for row in values),
                       "formula": "A=-log10(T_percent/100); Tauc=(A*1239.7/wavelength_nm)^2"})
    return audits


def _verify_bundle_worksheet(ops: object, book: str, columns: list[list[float]]) -> None:
    readback = ops.get_worksheet_data(book, "Sheet1")
    _require(readback, f"Read retained worksheet {book}")
    actual = readback.payload["columns"]
    if len(actual) != len(columns) or any(
        len(saved) != len(expected) or any(
            not math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)
            for a, b in zip(saved, expected)
        ) for saved, expected in zip(actual, columns)
    ):
        raise RuntimeError(f"Retained worksheet values do not match: {book}")


def _write_verified_bundle_worksheet(ops: object, book: str, columns: list[list[float]], headers: list[str]) -> None:
    # Use Origin's native initial sheet: a successful PutWorksheet call does
    # not prove that an unverified requested sheet rename actually existed.
    _require(ops.create_worksheet(book), "Create retained data worksheet")
    _require(ops.set_worksheet_data(book, "Sheet1", columns, headers), "Write retained data worksheet")
    _verify_bundle_worksheet(ops, book, columns)


def _draw_tauc_candidates(ops: object, graph: str, fits: list[dict], ymax: float) -> None:
    from src.core.template_format_executor import _set_origin_graph_object_text, _style_graph_object

    for index, fit in enumerate(fits, 1):
        gap = fit["Eg_candidate_eV"]
        end = fit["used_interval_eV"][1] + 0.10
        yend = fit["slope"] * end + fit["intercept"]
        line, text = f"TaucFit{index}", f"TaucGap{index}"
        _require(ops.run_labtalk(
            f'win -a "{graph}"; draw -n {line} -w 3 -d 1 -l {{{gap:.16g},0,{end:.16g},{yend:.16g}}}; '
            f'{line}.color=color(0,0,0); label -n {text} "x"; '
            f'{text}.attach=2; {text}.x=2.07; {text}.y={ymax * (0.73 - 0.13 * (index - 1)):.16g};'
        ), "Draw Tauc tangent and intercept label")
        label = origin_bold_text(f'{fit["sample"]}: E\\-(g) = {gap:.2f} eV')
        if not _set_origin_graph_object_text(ops, graph, text, label):
            raise RuntimeError("Tauc intercept label write failed")
        if not _style_graph_object(ops, graph, text, font_name="Arial", font_size=26, color=1):
            raise RuntimeError("Tauc intercept label style failed")


def _position_bundle_axis_titles(ops: object, graph: str, snapshot: dict) -> None:
    """Position existing native axis titles on the page after a scale change."""
    from src.core.template_format_executor import _find_origin_graph_object

    geometry = snapshot["layout_values"]
    width, height = geometry["page.width"], geometry["page.height"]
    layer = ops.app.FindGraphLayer(f"[{graph}]Layer1")
    _require(ops.run_labtalk(f'win -a "{graph}"; xb.attach=1; yl.attach=1; xb.show=1; yl.show=1; doc -uw;'), "Attach native titles to page")
    xb = _find_origin_graph_object(layer, "XB")
    yl = _find_origin_graph_object(layer, "YL")
    if xb is None or yl is None:
        raise RuntimeError("Native axis titles are unavailable")
    # Special axis-title COM wrappers may not expose an Attach setter;
    # the checked LabTalk write above is authoritative.
    center_x = width * (geometry["layer.left"] + geometry["layer.width"] / 2) / 100
    center_y = height * (geometry["layer.top"] + geometry["layer.height"] / 2) / 100
    bottom = height * (geometry["layer.top"] + geometry["layer.height"]) / 100
    xb.Left = int(center_x - float(xb.Width) / 2)
    xb.Top = int(min(height - float(xb.Height) - 40, bottom + height * 0.085))
    yl.Left = int(width * 0.05)
    yl.Top = int(center_y - float(yl.Height) / 2)
    for obj in (xb, yl):
        if min(float(obj.Left), float(obj.Top)) < 0 or float(obj.Left) + float(obj.Width) > width or float(obj.Top) + float(obj.Height) > height:
            raise RuntimeError("Native axis title lies outside the fixed page")


def export_uvvis_bundle(project_root: Path, result: dict, pairing_path: Path) -> dict:
    from src.core.template_format_executor import _find_origin_graph_object, _set_origin_graph_object_text

    products = {item["product_key"]: item for item in result["products"]}
    if set(products) != {"UV-vis DRS", "Tauc"} or any(p["status"] != "accepted" for p in products.values()):
        raise ValueError("UV-vis bundle requires exactly the accepted DRS and Tauc products")
    pairings = json.loads(pairing_path.read_text(encoding="utf-8"))
    pairing = next(p for p in pairings if p.get("data_type") == "Tauc")
    pairing_by_type = {p["data_type"]: p for p in pairings}
    styles_by_graph = {
        "DRS": _bundle_plot_style_contracts(pairing_by_type["UV-vis DRS"]["legend_entries"], pairing_by_type["UV-vis DRS"].get("bundle_plot_styles")),
        "Tauc": _bundle_plot_style_contracts(pairing["legend_entries"], pairing.get("bundle_plot_styles")),
    }
    if not str(pairing.get("tauc_fit_note") or "").strip():
        raise ValueError("An explicit tauc_fit_note is required for current fit provenance")
    labels = pairing.get("legend_entries", [])
    run_root = Path(result["run_root"])
    target_root = run_root / "bundle"
    paths = [target_root / n for n in ("DRS_Tauc.opju", "DRS.png", "DRS.tif", "Tauc.png", "Tauc.tif", "metadata.json", "report.md")]
    transmission_entries = pairing_by_type["UV-vis DRS"]
    if transmission_entries.get("transmittance_conversion") == "percent_to_absorbance_log10":
        paths.extend(target_root / f"Transmission_conversion_{i+1}.csv" for i in range(len(transmission_entries["legend_entries"])))
    prepare_safe_output_file_targets(paths, output_root=run_root, force=False, context="DRS/Tauc bundle")
    target_root.mkdir(parents=True, exist_ok=True)
    fit_results = fit_tauc_intervals(run_root / products["Tauc"]["processed_data"], labels, pairing.get("tauc_fit_intervals_eV", {}))
    metadata = {"status": "in_progress", "manual_check_required": True, "tauc_fits": fit_results,
                "tauc_fit_note": pairing["tauc_fit_note"], "transition_assumption": "squared_direct_candidate",
                "source_products": {k: {n: p[n] for n in ("origin_file", "processed_data", "metadata")} for k,p in products.items()},
                "selection": pairing.get("selection_provenance", {}), "graphs": {}}
    ops = None
    try:
        with tempfile.TemporaryDirectory(prefix="uvvis_bundle_", dir=neutral_origin_runtime_root(), ignore_cleanup_errors=True) as temporary:
            runtime = Path(temporary)
            ops = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
            graph_names = {}
            signatures = {}
            for key in ("UV-vis DRS", "Tauc"):
                item = products[key]
                source_meta = json.loads((run_root / item["metadata"]).read_text(encoding="utf-8"))
                graph = source_meta["origin_status"]["reopened_graph"]
                name = "DRS" if key == "UV-vis DRS" else "Tauc"
                source = runtime / f"{name}_source.opju"
                shutil.copy2(run_root / item["origin_file"], source)
                _require(ops.load_project(source) if key == "UV-vis DRS" else ops.append_project(source), "Load/append verified graph project")
                _require(ops.run_labtalk(f'win -a "{quote_labtalk(graph)}"; page.longname$="{name}";'), "Set graph display name")
                graph_names[name] = graph
                signatures[name] = _csv_signature(run_root / item["processed_data"])
                if _graph_signature(read_graph_data_snapshot(ops, graph)) != signatures[name]:
                    raise RuntimeError(f"{name} appended graph does not match its processed CSV")
                _bundle_plot_styles(ops, graph, styles_by_graph[name], apply=True)
            graph = graph_names["Tauc"]
            csv_path = run_root / products["Tauc"]["processed_data"]
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                data = list(csv.reader(handle))[1:]
            visible_y = [float(row[i + 1]) for row in data for i in range(0, 2 * len(labels), 2)
                         if row[i] and row[i+1] and 2 <= float(row[i]) <= 4]
            ymax = math.ceil(max(visible_y) * 1.12)
            _require(ops.set_axis_range(graph, x_min=2, x_max=4, y_min=0, y_max=ymax), "Tauc edge axis range")
            _require(ops.run_labtalk(
                f'win -a "{graph}"; layer.x.inc=0.5; layer.y.inc=2; '
                'layer.y.label.divideBy=1; layer.y.label.formula$=""; '
                'layer.y.label.numFormat=1; layer.y.label.decPlaces=0; '
                'layer.x.label.divideBy=1; layer.x.label.decPlaces=1;'
            ), "Tauc ticks in unscaled current-data units")
            # The supplied signal is absorbance, used as a candidate proxy.
            if not _set_origin_graph_object_text(ops, graph, "YL", r"\b(\(40)\i(Ah\f:g(ν))\(41)\+(2) (a.u.))"):
                raise RuntimeError("Tauc absorbance-proxy axis title failed")
            style = read_graph_style_snapshot(ops, graph).to_dict()
            _position_bundle_axis_titles(ops, graph, style)
            _draw_tauc_candidates(ops, graph, fit_results, ymax)
            metadata["transmission_conversion"] = _write_bundle_transmission_conversion(ops, project_root, transmission_entries, runtime)
            # Fit points and the complete original transformed spectra stay editable.
            retained_fit_columns = {}
            for index, fit in enumerate(fit_results, 1):
                book = f"TaucFit{index}"
                columns = [fit["used_interval_eV"], [fit["slope"] * x + fit["intercept"] for x in fit["used_interval_eV"]]]
                _write_verified_bundle_worksheet(ops, book, columns, ["Photon energy (eV)", f'{fit["sample"]} linear fit'])
                retained_fit_columns[book] = columns
            project = runtime / "DRS_Tauc.opju"
            _require(ops.save_project(project), "Save combined project")
            _require(ops.new_project(), "Reset before reopen")
            _require(ops.load_project(project), "Reopen combined project")
            all_pages = ops.list_worksheets()
            _require(all_pages, "List combined project")
            graphs = [p for p in all_pages.payload["pages"] if p["type"] == "graph"]
            if len(graphs) != 2:
                raise RuntimeError("Combined project must contain exactly two graph pages")
            for conversion in metadata["transmission_conversion"]:
                with (runtime / conversion["csv"]).open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.reader(handle))[1:]
                columns = [[float(value) for value in column] for column in zip(*rows)]
                _verify_bundle_worksheet(ops, conversion["workbook"], columns)
                conversion["values_unchanged_after_reopen"] = True
            for book, columns in retained_fit_columns.items():
                _verify_bundle_worksheet(ops, book, columns)
            metadata["fit_worksheets_unchanged_after_reopen"] = True
            for name, graph in graph_names.items():
                snapshot = read_graph_data_snapshot(ops, graph)
                if _graph_signature(snapshot) != signatures[name]:
                    raise RuntimeError(f"{name} data or displayed row ranges changed during bundling")
                style = read_graph_style_snapshot(ops, graph).to_dict()
                checks = _strict_style_readback(style)
                if not all(checks.values()):
                    raise RuntimeError(f"{name} saved typography failed: {checks}")
                palette_readback = _bundle_plot_styles(ops, graph, styles_by_graph[name], apply=False)
                if name == "Tauc":
                    divisor = ops.get_labtalk_variable("layer.y.label.divideBy")
                    if not divisor.ok or not math.isclose(float(divisor.payload["value"]), 1):
                        raise RuntimeError("Tauc Y tick labels must use the current unscaled ordinate")
                    layer = ops.app.FindGraphLayer(f"[{graph}]Layer1")
                    for index, fit in enumerate(fit_results, 1):
                        line = _find_origin_graph_object(layer, f"TaucFit{index}")
                        text = _find_origin_graph_object(layer, f"TaucGap{index}")
                        if line is None or text is None or f'{fit["Eg_candidate_eV"]:.2f}' not in str(text.Text):
                            raise RuntimeError("Saved Tauc tangent/intercept label is missing")
                png, tif = runtime / f"{name}.png", runtime / f"{name}.tif"
                _require(ops.export_graph(graph, png, "png", dpi=600), f"Export {name} preview")
                resolution = _export_native_tif_with_physical_validation(ops, graph, tif, dpi=600)
                _require(resolution, f"Export {name} native TIFF")
                for artifact in (png, tif):
                    copy_runtime_artifact(artifact, target_root / artifact.name)
                metadata["graphs"][name] = {"graph_page": graph, "plot_count": style["plot_count"], "values_unchanged_after_reopen": True,
                                            "style_checks": checks, "palette_readback": palette_readback, "tif_resolution_evidence": resolution["evidence"]}
            for conversion in metadata["transmission_conversion"]:
                copy_runtime_artifact(runtime / conversion["csv"], target_root / conversion["csv"])
            copy_runtime_artifact(project, target_root / project.name)
            _require(ops.close(), "Close task-owned Origin")
            ops = None
        metadata["status"] = "success"
    except Exception as exc:
        metadata.update(status="failed", message=str(exc))
        raise
    finally:
        if ops is not None:
            closed = ops.close()
            if not closed.ok:
                metadata.update(status="failed", message=closed.message)
        (target_root / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if metadata["status"] != "success":
        raise RuntimeError(metadata.get("message", "Bundle failed"))
    lines = ["# DRS / Tauc bundle", "", "One editable Origin project, two native graph pages, both with linked sample legends.",
             "", "| Sample | Interval / eV | Points | R² | Eg candidate / eV |", "|---|---|---:|---:|---:|"]
    lines += [f'| {f["sample"]} | {f["requested_interval_eV"]} | {f["point_count"]} | {f["r_squared"]:.6f} | {f["Eg_candidate_eV"]:.4f} |' for f in fit_results]
    lines += ["", pairing["tauc_fit_note"], "", "Tauc graph displays 2–4 eV; all transformed source points remain in the workbook.",
              "Tangent guides are native graph objects; fit endpoints are also retained in editable worksheets."]
    (target_root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "origin_file": str(target_root / "DRS_Tauc.opju"), "tauc_fits": fit_results}
