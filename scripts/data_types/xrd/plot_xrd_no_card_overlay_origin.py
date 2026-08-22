from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import win32com.client

from src.core.file_utils import (  # noqa: E402
    ensure_safe_output_file_target,
    file_sha256,
    is_under_or_equal,
    lexical_absolute_path,
    prepare_safe_output_file_targets,
)
from src.core.runtime_paths import resolve_output_root  # noqa: E402
from src.origin.adapter import reexport_tif_from_reopened_opju  # noqa: E402
from src.origin.operations import OriginOperations  # noqa: E402

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
FIXED_CURVE_COUNT = 9
STYLE_ROOT = PROJECT_ROOT / "templates" / "origin_styles"
FIXED_TEMPLATE = STYLE_ROOT / "graph_templates" / "XRD_no_card.otpu"
ADAPTIVE_THEME = STYLE_ROOT / "format_themes" / "XRD_no_card.oth"


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
    lexical_output_dir = lexical_absolute_path(output_dir)
    if not is_under_or_equal(lexical_output_dir, resolved_output_root):
        raise ValueError(f"--output-dir must stay under the configured output root: {output_dir}")
    ensure_safe_output_file_target(
        lexical_output_dir / ".rdop_output_preflight",
        output_root=resolved_output_root,
    )
    return lexical_output_dir


def validate_output_stem(output_stem: str) -> str:
    value = str(output_stem)
    if (
        not value
        or value != value.strip()
        or value in {".", ".."}
        or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
        or value.endswith((".", " "))
    ):
        raise ValueError(
            "--output-stem must be one non-empty safe Windows filename component."
        )
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
    if value.split(".", 1)[0].casefold() in reserved:
        raise ValueError("--output-stem may not use a reserved Windows device name.")
    return value


def paths_alias(left: Path, right: Path) -> bool:
    lexical_left = lexical_absolute_path(left)
    lexical_right = lexical_absolute_path(right)
    if os.path.normcase(os.fspath(lexical_left)) == os.path.normcase(
        os.fspath(lexical_right)
    ):
        return True
    if (
        os.path.lexists(os.fspath(lexical_left))
        and os.path.lexists(os.fspath(lexical_right))
    ):
        try:
            return os.path.samefile(lexical_left, lexical_right)
        except OSError:
            return False
    return False


def existing_origin_process_ids() -> tuple[int, ...]:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process -Name Origin* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    if completed.returncode:
        raise RuntimeError("Could not verify whether Origin is already running.")
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return tuple(sorted(set(pids)))


def preflight_output_targets(
    *,
    output_dir: Path,
    targets: tuple[Path, ...],
    sources: tuple[Path, ...],
    force: bool,
) -> None:
    safe_targets = tuple(
        ensure_safe_output_file_target(path, output_root=output_dir)
        for path in targets
    )
    for index, left in enumerate(safe_targets):
        for right in safe_targets[index + 1 :]:
            if paths_alias(left, right):
                raise ValueError(
                    f"Output targets must be mutually distinct: {left.name}, {right.name}"
                )
    for source in sources:
        resolved = source.resolve()
        if is_under_or_equal(resolved, output_dir):
            raise ValueError(
                "Input CSV and reference OPJU must be outside --output-dir so output cleanup cannot modify them."
            )
        for target in safe_targets:
            if paths_alias(target, source):
                raise ValueError(
                    f"Output target aliases a protected input: {target.name}"
                )
    collisions = [
        path
        for path in safe_targets
        if os.path.lexists(os.fspath(path))
    ]
    directories = [path for path in collisions if path.is_dir()]
    if directories:
        names = ", ".join(path.name for path in directories)
        raise IsADirectoryError(f"Output target(s) collide with directories: {names}")
    if collisions and not force:
        names = ", ".join(path.name for path in collisions)
        raise FileExistsError(
            f"Output target(s) already exist: {names}; rerun with --force or choose a new output stem."
        )


def style_mode_for_curve_count(curve_count: int) -> tuple[str, Path]:
    """Choose the detached project asset without consulting a reference OPJU."""

    if int(curve_count) == FIXED_CURVE_COUNT:
        if not FIXED_TEMPLATE.is_file():
            raise FileNotFoundError(f"verified fixed XRD no-card OTPU is missing: {FIXED_TEMPLATE}")
        return "fixed_otpu", FIXED_TEMPLATE
    if not ADAPTIVE_THEME.is_file():
        raise FileNotFoundError(f"adaptive XRD no-card OTH is missing: {ADAPTIVE_THEME}")
    return "adaptive_oth_json", ADAPTIVE_THEME


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


ADAPTIVE_STYLE = {
    "page_width": 6432.0,
    "page_height": 4923.0,
    "layer_left": 17.89,
    "layer_top": 11.6,
    "layer_width": 68.19,
    "layer_height": 71.81,
    "axis_thickness": 3.0,
}


def _y_axis_limits(data: pd.DataFrame) -> tuple[float, float]:
    y_columns = list(data.columns[1:])
    y_min = min(float(data[col].min()) for col in y_columns)
    y_max = max(float(data[col].max()) for col in y_columns)
    y_padding = max(0.25, (y_max - y_min) * 0.04)
    return (
        math.floor((y_min - y_padding) * 10) / 10,
        math.ceil((y_max + y_padding) * 10) / 10,
    )


def rebuild_direct_labels(
    app: object,
    graph_name: str,
    data: pd.DataFrame,
    font_code: int,
    labels: list[str],
) -> None:
    """Replace all template DL labels with labels for the current worksheet data."""

    y_columns = list(data.columns[1:])
    labtalk(app, f'win -a "{quote(graph_name)}"; layer -s 1;')
    # The fixed template contains DL1..DL9.  Delete that full contract first,
    # and delete any stale higher-index labels left by an earlier product.
    for index in range(1, max(FIXED_CURVE_COUNT, len(labels)) + 1):
        labtalk(app, f"label -r DL{index};", required=False)
    label_y_positions = []
    for column in y_columns:
        y_low = float(data[column].min())
        y_high = float(data[column].max())
        label_y_positions.append(y_low + (y_high - y_low) * 0.45)
    max_label_len = max((len(label) for label in labels), default=0)
    label_x = max(52.0, LABEL_X - max(0, max_label_len - 6) * 1.8)
    for index, (label, y_value) in enumerate(zip(labels, label_y_positions), start=1):
        name = f"DL{index}"
        labtalk(app, f'label -n {name} "\\b({quote(label)})";')
        labtalk(
            app,
            f"{name}.x={label_x}; {name}.y={y_value}; {name}.font={font_code}; "
            f"{name}.fsize=26; {name}.bold=1; {name}.color=1;",
            required=False,
        )


def apply_adaptive_style(
    app: object,
    graph_name: str,
    data: pd.DataFrame,
    font_code: int,
    labels: list[str],
) -> None:
    y_columns = list(data.columns[1:])
    y_from, y_to = _y_axis_limits(data)

    labtalk(app, f'win -a "{quote(graph_name)}"; layer -s 1;')
    labtalk(
        app,
        "page.kar=0; page.customwidth=1; page.customheight=1; "
        f"page.width={ADAPTIVE_STYLE['page_width']}; page.height={ADAPTIVE_STYLE['page_height']};",
    )
    labtalk(
        app,
        f"layer.left={ADAPTIVE_STYLE['layer_left']}; layer.top={ADAPTIVE_STYLE['layer_top']}; "
        f"layer.width={ADAPTIVE_STYLE['layer_width']}; layer.height={ADAPTIVE_STYLE['layer_height']};",
    )
    labtalk(app, f"layer.x.from=5; layer.x.to=80; layer.x.inc=10; layer.y.from={y_from}; layer.y.to={y_to};")
    labtalk(app, f"layer.x.thickness={ADAPTIVE_STYLE['axis_thickness']}; layer.y.thickness={ADAPTIVE_STYLE['axis_thickness']};")
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

    rebuild_direct_labels(app, graph_name, data, font_code, labels)


def apply_fixed_template_bindings(
    app: object,
    graph_name: str,
    data: pd.DataFrame,
    font_code: int,
    labels: list[str],
) -> None:
    """Keep OTPU-owned formatting, replacing only data-dependent values."""

    y_from, y_to = _y_axis_limits(data)
    labtalk(app, f'win -a "{quote(graph_name)}"; layer -s 1;')
    labtalk(app, f"layer.x.from=5; layer.x.to=80; layer.x.inc=10; layer.y.from={y_from}; layer.y.to={y_to};")
    remove_legend(app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name))
    rebuild_direct_labels(app, graph_name, data, font_code, labels)


def _clear_template_plot_bindings(app: object, graph_name: str) -> None:
    """Remove only inherited plot bindings; template axes and text remain native."""

    layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
    if layer is None:
        raise RuntimeError(f"graph layer not found: {graph_name}")
    # COM plot collections can be 0- or 1-based depending on Origin build.
    # Destroy by object until none remain, never replacing the graph page.
    while int(layer.DataPlots.Count) > 0:
        destroyed = False
        for index in (int(layer.DataPlots.Count) - 1, int(layer.DataPlots.Count)):
            try:
                layer.DataPlots.Item(index).Destroy()
                destroyed = True
                break
            except Exception:
                continue
        if not destroyed:
            raise RuntimeError("could not remove inherited XRD no-card template plot bindings")


def create_graph(
    app: object,
    book_name: str,
    data: pd.DataFrame,
    page_name: str,
    *,
    fixed_template: Path | None = None,
) -> str:
    graph_name = app.CreatePage(
        3,
        page_name,
        str(fixed_template.resolve()) if fixed_template is not None else "origin",
    )
    if fixed_template is not None:
        _clear_template_plot_bindings(app, graph_name)
    for y_col in range(2, len(data.columns) + 1):
        labtalk(app, f"plotxy iy:=[{book_name}]Sheet1!(1,{y_col}) plot:=200 ogl:=[{graph_name}]Layer1;")
    return graph_name


def export_preview(app: object, graph_name: str, output_dir: Path, output_stem: str) -> Path:
    png = output_dir / f"{output_stem}.png"
    if png.exists():
        png.unlink()
    labtalk(app, f'win -a "{quote(graph_name)}"; expGraph type:=png path:="{origin_path(output_dir)}" filename:="{output_stem}" overwrite:=replace;')
    wait_for_file(png)
    return png


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
    parser.add_argument(
        "--reference-opju",
        type=Path,
        default=None,
        help="audit-only compatibility parameter; never loaded for product generation",
    )
    parser.add_argument("--reference-graph", default="Graph4", help="audit-only compatibility parameter")
    parser.add_argument("--output-stem", default="XRD_26.7.2_no_card_final")
    parser.add_argument("--page-name", default=PAGE_NAME)
    parser.add_argument("--labels", nargs="*", help="direct labels for each Y column; defaults to CSV Y-column headers")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.input_csv = args.input_csv.resolve()
    if not args.input_csv.is_file():
        raise FileNotFoundError(f"input CSV does not exist: {args.input_csv}")
    if args.reference_opju is not None:
        args.reference_opju = args.reference_opju.resolve()
        if not args.reference_opju.is_file():
            raise FileNotFoundError(f"reference OPJU does not exist: {args.reference_opju}")
    data = pd.read_csv(args.input_csv)
    if len(data.columns) < 2:
        raise ValueError(f"expected one X column and at least one Y column, got {len(data.columns)} columns")
    for column in data.columns:
        try:
            numeric = pd.to_numeric(data[column], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"XRD input column is not fully numeric: {column}"
            ) from exc
        if not all(math.isfinite(float(value)) for value in numeric):
            raise ValueError(f"XRD input column contains non-finite values: {column}")
        data[column] = numeric
    labels = list(args.labels or [str(column) for column in data.columns[1:]])
    if len(labels) != len(data.columns) - 1:
        raise ValueError(f"expected {len(data.columns) - 1} labels for Y columns, got {len(labels)} labels")
    style_mode, style_asset = style_mode_for_curve_count(len(labels))
    args.output_dir = ensure_output_dir_allowed(args.output_dir, args.output_root)
    args.output_stem = validate_output_stem(args.output_stem)
    opju = args.output_dir / f"{args.output_stem}.opju"
    metadata = args.output_dir / f"{args.output_stem}_metadata.json"
    report = args.output_dir / f"{args.output_stem}_report.md"
    png_target = args.output_dir / f"{args.output_stem}.png"
    tif_target = args.output_dir / f"{args.output_stem}.tif"
    targets = (opju, metadata, report, png_target, tif_target)
    sources = (args.input_csv,) + ((args.reference_opju,) if args.reference_opju is not None else ())
    preflight_output_targets(
        output_dir=args.output_dir,
        targets=targets,
        sources=sources,
        force=bool(args.force),
    )
    running_origin = existing_origin_process_ids()
    if running_origin:
        raise RuntimeError(
            "Origin is already running; close every Origin session before running the XRD no-card helper."
        )
    prepare_safe_output_file_targets(
        targets,
        output_root=args.output_dir,
        force=bool(args.force),
        context="XRD no-card",
    )
    input_hash_before = file_sha256(args.input_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    app = None
    try:
        app = win32com.client.DispatchEx("Origin.Application")
        try:
            app.Visible = 0
        except Exception:
            pass
        # Make the fresh-project boundary explicit.  No reference OPJU is
        # opened in either style mode.
        app.NewProject()
        font_code = int(app.Evaluate("font(Arial)")) or 71
        book_name = write_workbook(app, data)
        graph_name = create_graph(
            app,
            book_name,
            data,
            args.page_name,
            fixed_template=style_asset if style_mode == "fixed_otpu" else None,
        )
        if style_mode == "fixed_otpu":
            apply_fixed_template_bindings(app, graph_name, data, font_code, labels)
        else:
            applied = OriginOperations(app).apply_graph_theme(graph_name, style_asset)
            if not applied.ok:
                raise RuntimeError(applied.message)
            apply_adaptive_style(app, graph_name, data, font_code, labels)
        checks = verify_output(app, graph_name, len(data.columns) - 1, font_code)
        app.Save(str(opju))
        wait_for_file(opju)
        png = export_preview(app, graph_name, args.output_dir, args.output_stem)
        app.Exit()
        app = None
        tif = tif_target
        resolution = reexport_tif_from_reopened_opju(
            opju,
            graph_name,
            tif,
            dpi=600,
        )
        tif_info = {
            "resolution_evidence": {
                key: value
                for key, value in resolution.as_dict().items()
                if key != "path"
            },
        }
        input_hash_after = file_sha256(args.input_csv)
        if input_hash_after != input_hash_before:
            raise RuntimeError("The input CSV changed during the Origin run; outputs are rejected.")
        payload = {
            "dataset_id": args.output_stem,
            "data_type": "XRD",
            "processor_name": "xrd_no_card_origin_com_script",
            "processing_status": "success",
            "input_csv": {
                "filename": args.input_csv.name,
                "sha256_before": input_hash_before,
                "sha256_after": input_hash_after,
            },
            "reference_opju_audit": (
                {
                    "filename": args.reference_opju.name,
                    "requested": True,
                }
                if args.reference_opju is not None
                else None
            ),
            "reference_opju_loaded": False,
            "style_mode": style_mode,
            "style_asset": str(style_asset.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "origin_file": opju.name,
            "preview_png": png.name,
            "figure_tif": tif.name,
            "overwrite_authorized": bool(args.force),
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
                    f"- Origin OPJU: `{opju.name}`",
                    f"- PNG preview: `{png.name}`",
                    f"- TIF: `{tif.name}`",
                    "- Font: Arial for axis titles, tick labels, and direct labels",
                    "- Standard card: not added",
                    "- Legend colored line samples: not used",
                    f"- Style mode: {style_mode}",
                    "- Reference OPJU: not loaded (audit parameter only)",
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
