from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import win32com.client
from PIL import Image

from src.core.file_utils import is_under_or_equal  # noqa: E402
from src.core.runtime_paths import resolve_output_root  # noqa: E402

PAGE_NAME = "XRD_no_card_overlay"
PALETTE = [
    "color(0,114,178)",
    "color(230,159,0)",
    "color(0,158,115)",
    "color(213,94,0)",
    "color(86,180,233)",
    "color(204,121,167)",
    "color(240,228,66)",
    "color(0,0,0)",
    "color(0,114,178)",
]
LABEL_X = 65.6


def quote(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def origin_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def labtalk(app: object, script: str, *, required: bool = True) -> bool:
    ok = bool(app.Execute(script))
    if required and not ok:
        raise RuntimeError(f"Origin LabTalk failed: {script}")
    return ok


def wait_for_file(path: Path, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Origin output was not created: {path}")


def ensure_output_dir_allowed(output_dir: Path, output_root: Path | None) -> Path:
    resolved_output_root = resolve_output_root(PROJECT_ROOT, explicit=output_root).resolve()
    resolved_output_dir = output_dir.resolve()
    if not is_under_or_equal(resolved_output_dir, resolved_output_root):
        raise ValueError(f"--output-dir must stay under the configured output root: {output_dir}")
    return resolved_output_dir


def ensure_tif_600_dpi(path: Path, min_width: int = 6432) -> None:
    with Image.open(path) as image:
        output = image.copy()
    if output.width < min_width:
        target_height = max(1, round(output.height * (min_width / output.width)))
        output = output.resize((min_width, target_height))
    output.save(path, format="TIFF", dpi=(600, 600), compression="tiff_lzw")


def inspect_reference_style(app: object, reference_opju: Path, graph_name: str) -> dict[str, float]:
    style = {
        "page_width": 6432.0,
        "page_height": 4923.0,
        "layer_left": 17.89,
        "layer_top": 11.6,
        "layer_width": 68.19,
        "layer_height": 71.81,
        "axis_thickness": 3.0,
    }
    if not reference_opju or not reference_opju.exists():
        return style
    runtime = Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    ref_copy = runtime / f"reference_{reference_opju.name}"
    shutil.copy2(reference_opju, ref_copy)
    if not bool(app.Load(str(ref_copy))):
        raise RuntimeError(f"failed to load copied reference OPJU: {reference_opju}")
    labtalk(app, f'win -a "{quote(graph_name)}"; layer -s 1;')
    style.update(
        {
            "page_width": float(app.Evaluate("page.width")),
            "page_height": float(app.Evaluate("page.height")),
            "layer_left": float(app.Evaluate("layer.left")),
            "layer_top": float(app.Evaluate("layer.top")),
            "layer_width": float(app.Evaluate("layer.width")),
            "layer_height": float(app.Evaluate("layer.height")),
            "axis_thickness": float(app.Evaluate("layer.x.thickness")),
        }
    )
    app.NewProject()
    return style


def write_workbook(app: object, data: pd.DataFrame) -> str:
    book_name = app.CreatePage(2, "XRD_NoCard_Data", "origin")
    target = f"[{book_name}]Sheet1"
    labtalk(app, f'win -a "{quote(book_name)}"; wks.ncols={len(data.columns)}; wks.nrows={len(data)};')
    for index, column in enumerate(data.columns, start=1):
        app.PutWorksheet(target, data[column].astype(float).tolist(), 0, index - 1)
        labtalk(app, f'wks.col{index}.lname$="{quote(column)}"; wks.col{index}.comment$="";')
    labtalk(app, "wks.col1.type=4;")
    for index in range(2, len(data.columns) + 1):
        labtalk(app, f"wks.col{index}.type=1;")
    return book_name


def set_graph_object_style(obj: object, font_code: int, size: int, color: int = 1) -> None:
    for prop, value in (("font", font_code), ("fsize", size), ("bold", 1), ("color", color)):
        try:
            obj.SetNumProp(prop, value)
        except Exception:
            pass


def get_graph_object(layer: object, name: str) -> object | None:
    try:
        return layer.GraphObjects[name]
    except Exception:
        return None


def remove_legend(layer: object) -> None:
    legend = get_graph_object(layer, "Legend")
    if legend is not None:
        try:
            legend.Destroy()
        except Exception:
            pass


def apply_style(
    app: object,
    graph_name: str,
    data: pd.DataFrame,
    style: dict[str, float],
    font_code: int,
    labels: list[str],
) -> None:
    y_columns = list(data.columns[1:])
    y_min = min(float(data[col].min()) for col in y_columns)
    y_max = max(float(data[col].max()) for col in y_columns)
    y_padding = max(0.25, (y_max - y_min) * 0.04)
    y_from = math.floor((y_min - y_padding) * 10) / 10
    y_to = math.ceil((y_max + y_padding) * 10) / 10

    labtalk(app, f'win -a "{quote(graph_name)}"; layer -s 1;')
    labtalk(
        app,
        "page.kar=0; page.customwidth=1; page.customheight=1; "
        f"page.width={style['page_width']}; page.height={style['page_height']};",
    )
    labtalk(
        app,
        f"layer.left={style['layer_left']}; layer.top={style['layer_top']}; "
        f"layer.width={style['layer_width']}; layer.height={style['layer_height']};",
    )
    labtalk(app, f"layer.x.from=5; layer.x.to=80; layer.x.inc=10; layer.y.from={y_from}; layer.y.to={y_to};")
    labtalk(app, f"layer.x.thickness={style['axis_thickness']}; layer.y.thickness={style['axis_thickness']};")
    labtalk(
        app,
        f"layer.x.label.font={font_code}; layer.y.label.font={font_code}; "
        "layer.x.label.pt=28; layer.y.label.pt=36; layer.x.label.bold=1; layer.y.label.bold=1; "
        "layer.y.label.show=0; layer.y.showLabels=0;",
    )
    labtalk(
        app,
        "layer.y.show=1; layer.y.ticks=0; layer.y.ticklength=0; layer.y.mticklength=0; "
        "layer.y2.ticks=0; layer.y2.ticklength=0; layer.y2.mticklength=0; layer.y2.showLabels=0;",
        required=False,
    )

    layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
    if layer is None:
        raise RuntimeError(f"graph layer not found: {graph_name}")

    xb = get_graph_object(layer, "XB")
    yl = get_graph_object(layer, "YL")
    if xb is not None:
        xb.Text = r"\b(2\g(q) (degree))"
        set_graph_object_style(xb, font_code, 36)
    if yl is not None:
        yl.Text = r"\b(Intensity (a.u.))"
        set_graph_object_style(yl, font_code, 36)
        try:
            yl.Left = max(65, int(yl.Left))
        except Exception:
            pass

    remove_legend(layer)
    for index in range(layer.DataPlots.Count):
        plot = layer.DataPlots.Item(index)
        plot_name = plot.Name
        color = PALETTE[index % len(PALETTE)]
        labtalk(app, f"set {plot_name} -c {color}; set {plot_name} -w 30; set {plot_name} -l 1;", required=False)
        try:
            plot.SetNumProp("line.width", 3)
            plot.SetNumProp("symbol.kind", 0)
        except Exception:
            pass

    label_y_positions = []
    for column in y_columns:
        y_low = float(data[column].min())
        y_high = float(data[column].max())
        label_y_positions.append(y_low + (y_high - y_low) * 0.45)
    max_label_len = max((len(label) for label in labels), default=0)
    label_x = max(52.0, LABEL_X - max(0, max_label_len - 6) * 1.8)
    for index, (label, y_value) in enumerate(zip(labels, label_y_positions), start=1):
        name = f"DL{index}"
        labtalk(app, f"label -r {name};", required=False)
        labtalk(app, f'label -n {name} "\\b({quote(label)})";')
        labtalk(
            app,
            f"{name}.x={label_x}; {name}.y={y_value}; {name}.font={font_code}; "
            f"{name}.fsize=26; {name}.bold=1; {name}.color=1;",
            required=False,
        )


def create_graph(app: object, book_name: str, data: pd.DataFrame, page_name: str) -> str:
    graph_name = app.CreatePage(3, page_name, "origin")
    for y_col in range(2, len(data.columns) + 1):
        labtalk(app, f"plotxy iy:=[{book_name}]Sheet1!(1,{y_col}) plot:=200 ogl:=[{graph_name}]Layer1;")
    return graph_name


def export_graph(app: object, graph_name: str, output_dir: Path, output_stem: str) -> tuple[Path, Path]:
    png = output_dir / f"{output_stem}.png"
    tif = output_dir / f"{output_stem}.tif"
    for path in (png, tif):
        if path.exists():
            path.unlink()
    labtalk(app, f'win -a "{quote(graph_name)}"; expGraph type:=png path:="{origin_path(output_dir)}" filename:="{output_stem}" overwrite:=replace;')
    labtalk(app, f'win -a "{quote(graph_name)}"; expGraph type:=tif path:="{origin_path(output_dir)}" filename:="{output_stem}" overwrite:=replace;')
    wait_for_file(png)
    wait_for_file(tif)
    ensure_tif_600_dpi(tif)
    return png, tif


def verify_output(app: object, graph_name: str, expected_plots: int, font_code: int) -> dict[str, object]:
    labtalk(app, f'win -a "{quote(graph_name)}"; layer -s 1;')
    layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
    if layer is None:
        raise RuntimeError(f"graph layer not found for verification: {graph_name}")
    if int(layer.DataPlots.Count) != expected_plots:
        raise RuntimeError(f"expected {expected_plots} plots, got {layer.DataPlots.Count}")
    checks: dict[str, object] = {
        "plot_count": int(layer.DataPlots.Count),
        "font_code": font_code,
        "x_tick_font": float(app.Evaluate("layer.x.label.font")),
        "y_tick_font": float(app.Evaluate("layer.y.label.font")),
        "y_ticks": float(app.Evaluate("layer.y.ticks")),
        "y_ticklength": float(app.Evaluate("layer.y.ticklength")),
        "x_title": "",
        "y_title": "",
        "legend_present": False,
        "direct_labels": [],
    }
    if checks["y_ticks"] != 0 or checks["y_ticklength"] != 0:
        raise RuntimeError(f"Y-axis ticks are still visible: {checks['y_ticks']}, {checks['y_ticklength']}")
    for index in range(layer.GraphObjects.Count):
        obj = layer.GraphObjects.Item(index)
        name = str(obj.Name)
        try:
            text = str(obj.Text)
        except Exception:
            text = ""
        if name == "Legend":
            checks["legend_present"] = True
            if r"\l(" in text:
                raise RuntimeError(f"legend still contains colored line samples: {text}")
        if name in {"XB", "YL"} or name.startswith("DL"):
            try:
                font = int(obj.GetNumProp("font"))
            except Exception:
                font = -1
            if font != font_code:
                raise RuntimeError(f"{name} is not Arial font code {font_code}: {font}")
        if name == "XB":
            checks["x_title"] = text
            if r"\g(q)" not in text:
                raise RuntimeError(f"X axis title is not Origin theta rich text: {text}")
        elif name == "YL":
            checks["y_title"] = text
        elif name.startswith("DL"):
            checks["direct_labels"].append(text)
    if len(checks["direct_labels"]) != expected_plots:
        raise RuntimeError(f"expected {expected_plots} direct labels, got {len(checks['direct_labels'])}")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a no-card XRD overlay in Origin using the XRD-specific COM workflow.")
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--reference-opju", type=Path, default=Path(""))
    parser.add_argument("--reference-graph", default="Graph4")
    parser.add_argument("--output-stem", default="XRD_26.7.2_no_card_final")
    parser.add_argument("--page-name", default=PAGE_NAME)
    parser.add_argument("--labels", nargs="*", help="direct labels for each Y column; defaults to CSV Y-column headers")
    args = parser.parse_args()

    data = pd.read_csv(args.input_csv)
    if len(data.columns) < 2:
        raise ValueError(f"expected one X column and at least one Y column, got {len(data.columns)} columns")
    labels = list(args.labels or [str(column) for column in data.columns[1:]])
    if len(labels) != len(data.columns) - 1:
        raise ValueError(f"expected {len(data.columns) - 1} labels for Y columns, got {len(labels)} labels")
    args.output_dir = ensure_output_dir_allowed(args.output_dir, args.output_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    opju = args.output_dir / f"{args.output_stem}.opju"
    metadata = args.output_dir / f"{args.output_stem}_metadata.json"
    report = args.output_dir / f"{args.output_stem}_report.md"
    for path in (opju, metadata, report, args.output_dir / f"{args.output_stem}.png", args.output_dir / f"{args.output_stem}.tif"):
        if path.exists():
            path.unlink()

    app = None
    try:
        app = win32com.client.DispatchEx("Origin.Application")
        try:
            app.Visible = 0
        except Exception:
            pass
        font_code = int(app.Evaluate("font(Arial)")) or 71
        style = inspect_reference_style(app, args.reference_opju, args.reference_graph)
        book_name = write_workbook(app, data)
        graph_name = create_graph(app, book_name, data, args.page_name)
        apply_style(app, graph_name, data, style, font_code, labels)
        checks = verify_output(app, graph_name, len(data.columns) - 1, font_code)
        app.Save(str(opju))
        wait_for_file(opju)
        png, tif = export_graph(app, graph_name, args.output_dir, args.output_stem)
        with Image.open(tif) as image:
            tif_dpi = image.info.get("dpi", (0, 0))
            tif_info = {
                "pixels": [int(value) for value in image.size],
                "dpi": [float(value) for value in tif_dpi],
            }
        payload = {
            "dataset_id": args.output_stem,
            "data_type": "XRD",
            "processor_name": "xrd_no_card_origin_com_script",
            "input_csv": str(args.input_csv),
            "reference_opju": str(args.reference_opju),
            "origin_file": str(opju),
            "preview_png": str(png),
            "figure_tif": str(tif),
            "plot_type": "single-page normalized offset XRD overlay without standard-card lines",
            "font": "Arial",
            "origin_font_code": font_code,
            "standard_card_added": False,
            "legend_line_samples": False,
            "direct_labels": labels,
            "checks": checks,
            "tif": tif_info,
            "manual_check_required": True,
            "manual_check_items": [
                "confirm labels, order, normalization, and offsets",
                "no phase or crystal-plane assignment is made",
            ],
        }
        metadata.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report.write_text(
            "\n".join(
                [
                    "# XRD No-Card Overlay Final",
                    "",
                    f"- Origin OPJU: `{opju}`",
                    f"- PNG preview: `{png}`",
                    f"- TIF: `{tif}`",
                    "- Font: Arial for axis titles, tick labels, and direct labels",
                    "- Standard card: not added",
                    "- Legend colored line samples: not used",
                    f"- Curves: {len(labels)}, single graph page",
                    "",
                    "No phase, crystal-plane, mechanism, heterojunction, or purity claim is generated.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"OPJU={opju}")
        print(f"PNG={png}")
        print(f"TIF={tif}")
        print(f"METADATA={metadata}")
    finally:
        if app is not None:
            try:
                app.Exit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
