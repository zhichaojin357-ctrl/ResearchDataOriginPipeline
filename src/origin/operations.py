from __future__ import annotations

import csv
import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.origin.plot_policy import GRAPH4_FIXED_STYLE, Graph4FixedStyle
from src.origin.text_format import origin_bold_text, origin_chemical_subscripts


PLOT_TYPES = {
    "line": 200,
    "scatter": 201,
    "line+symbol": 202,
    "column": 203,
    "bar": 204,
    "area": 205,
    "histogram": 206,
    "box": 207,
    "contour": 208,
    "3d_scatter": 209,
    "3d_surface": 210,
    "pie": 212,
    "bubble": 228,
}

EXPORT_FORMATS = {
    "png": "png",
    "jpg": "jpg",
    "jpeg": "jpg",
    "tif": "tif",
    "tiff": "tif",
    "bmp": "bmp",
    "emf": "emf",
    "eps": "eps",
    "pdf": "pdf",
    "svg": "svg",
}

COLOR_MAP = {
    "black": 1,
    "red": 2,
    "green": 3,
    "blue": 4,
    "cyan": 5,
    "magenta": 6,
    "yellow": 7,
    "orange": 19,
    "purple": 13,
    "gray": 8,
    "grey": 8,
}

SYMBOL_SHAPES = {
    1: 2,
    2: 3,
    3: 1,
    4: 4,
    5: 5,
    6: 6,
}


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


def connect_origin(entrypoint: str = "Origin.Application", *, visible: bool = False, isolated: bool = True) -> "OriginOperations":
    """Connect to Origin through COM and wrap it in the stable operations adapter."""
    import win32com.client

    if isolated and hasattr(win32com.client, "DispatchEx"):
        app = win32com.client.DispatchEx(entrypoint)
    else:
        app = win32com.client.Dispatch(entrypoint)
    try:
        app.Visible = 1 if visible else 0
    except Exception:
        pass
    return OriginOperations(app)


def quote_labtalk(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def quote_origin_text(value: object) -> str:
    return quote_labtalk(origin_chemical_subscripts(value))


def to_origin_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def safe_origin_name(value: str, default: str = "Page") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not cleaned:
        cleaned = default
    if cleaned[0].isdigit():
        cleaned = f"{default}_{cleaned}"
    return cleaned[:24]


def normalize_export_path(file_path: str | Path, export_format: str = "png") -> tuple[Path, str]:
    output = Path(file_path)
    requested_format = (export_format or "png").strip().lower().lstrip(".")
    suffix_format = output.suffix.lower().lstrip(".")
    resolved_format = EXPORT_FORMATS.get(suffix_format) or EXPORT_FORMATS.get(requested_format)
    if resolved_format is None:
        supported = ", ".join(sorted(EXPORT_FORMATS))
        raise ValueError(f"Unsupported export format {export_format!r}. Supported: {supported}")
    if not output.suffix or EXPORT_FORMATS.get(suffix_format) != resolved_format:
        output = output.with_suffix(f".{resolved_format}")
    return output, resolved_format


def _parse_csv(path: Path, delimiter: str = ",") -> tuple[list[str], list[list[float]]]:
    actual_delimiter = "\t" if delimiter in {"\\t", "\t"} else delimiter
    if len(actual_delimiter) != 1:
        raise ValueError(f"delimiter must be a single character, got {delimiter!r}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.reader(handle, delimiter=actual_delimiter) if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError(f"no data rows found in {path}")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("ragged CSV rows are not supported")
    header: list[str] = []
    data_rows = rows
    try:
        [[float(cell) if cell.strip() else math.nan for cell in row] for row in rows]
    except ValueError:
        header = [cell.strip() for cell in rows[0]]
        data_rows = rows[1:]
    if not data_rows:
        raise ValueError(f"no numeric data rows found in {path}")
    numeric_rows = [[float(cell) if cell.strip() else math.nan for cell in row] for row in data_rows]
    columns = [[row[index] for row in numeric_rows] for index in range(width)]
    return header, columns


def _wait_for_file(path: Path, timeout_seconds: float = 8.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.25)
    return path.exists() and path.stat().st_size > 0


class OriginOperations:
    """Stable, named Origin operation functions backed by Origin COM."""

    def __init__(self, app: Any):
        self.app = app

    def close(self) -> OperationResult:
        try:
            self.app.Exit()
        except Exception as exc:
            return OperationResult(False, f"Origin close failed: {exc}")
        return OperationResult(True, "Origin closed")

    def run_labtalk(self, script: str) -> OperationResult:
        ok = bool(self.app.Execute(script))
        return OperationResult(ok, "LabTalk executed" if ok else "LabTalk returned failure", {"script": script})

    def get_labtalk_variable(self, name: str) -> OperationResult:
        if name.endswith("$"):
            value = self.app.LTStr(name)
        else:
            value = self.app.LTVar(name)
        return OperationResult(True, f"Read LabTalk variable {name}", {"name": name, "value": value})

    def new_project(self) -> OperationResult:
        self.app.NewProject()
        return OperationResult(True, "New Origin project created")

    def save_project(self, file_path: str | Path = "") -> OperationResult:
        target = str(file_path) if file_path else ""
        self.app.Save(target)
        return OperationResult(True, "Project saved", {"file_path": target})

    def load_project(self, file_path: str | Path) -> OperationResult:
        path = Path(file_path)
        if not path.exists():
            return OperationResult(False, f"Origin project file not found: {path}")
        self.app.Load(str(path))
        return OperationResult(True, "Project loaded", {"file_path": str(path)})

    def create_worksheet(self, book_name: str, sheet_name: str = "Sheet1") -> OperationResult:
        book = self.app.CreatePage(2, safe_origin_name(book_name, "Book"), "origin")
        if sheet_name != "Sheet1":
            self.run_labtalk(f'win -a "{quote_labtalk(book)}"; wks.name$ = "{quote_labtalk(sheet_name)}";')
        return OperationResult(True, "Worksheet created", {"book_name": book, "sheet_name": sheet_name})

    def set_worksheet_data(
        self,
        book_name: str,
        sheet_name: str,
        columns: Iterable[Iterable[float]],
        column_names: Iterable[str] | None = None,
    ) -> OperationResult:
        target = f"[{book_name}]{sheet_name}"
        data_columns = [[float(value) for value in column] for column in columns]
        if not data_columns:
            return OperationResult(False, "No columns provided")
        for index, column in enumerate(data_columns):
            self.app.PutWorksheet(target, column, 0, index)
        names = list(column_names or [])
        if names:
            self.run_labtalk(f'win -a "{quote_labtalk(book_name)}";')
            for index, name in enumerate(names, start=1):
                self.run_labtalk(f'wks.col{index}.lname$ = "{quote_labtalk(name)}";')
        return OperationResult(
            True,
            "Worksheet data written",
            {"target": target, "columns": len(data_columns), "rows": len(data_columns[0])},
        )

    def get_worksheet_data(self, book_name: str, sheet_name: str) -> OperationResult:
        target = f"[{book_name}]{sheet_name}"
        data = self.app.GetWorksheet(target)
        if data is None:
            return OperationResult(False, f"Worksheet not found: {target}")
        rows = list(data)
        if not rows:
            return OperationResult(True, "Worksheet data read", {"columns": []})
        column_count = len(rows[0])
        columns = [[row[index] for row in rows] for index in range(column_count)]
        return OperationResult(True, "Worksheet data read", {"target": target, "columns": columns})

    def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
        layer = self.app.FindGraphLayer(f"[{graph_name}]Layer{int(layer_index)}")
        if not layer:
            return OperationResult(False, f"Graph layer not found: [{graph_name}]Layer{int(layer_index)}")
        data_plots = layer.DataPlots
        names = [str(data_plots.Item(index).Name) for index in range(data_plots.Count)]
        return OperationResult(
            True,
            "Graph plot dataset names read",
            {"graph_name": graph_name, "layer_index": int(layer_index), "plot_dataset_names": names},
        )

    def replace_template_workbook_columns(self, workbook_columns: dict[str, dict[int, Iterable[float]]]) -> OperationResult:
        updated: list[dict[str, object]] = []
        for book_name, columns in workbook_columns.items():
            if not book_name or not columns:
                continue
            target = f"[{book_name}]Sheet1"
            for column_index, values in sorted(columns.items()):
                column_values = [float(value) for value in values]
                self.app.PutWorksheet(target, column_values, 0, int(column_index))
                updated.append(
                    {
                        "book_name": str(book_name),
                        "column_index": int(column_index),
                        "rows": len(column_values),
                    }
                )
        if not updated:
            return OperationResult(False, "No template workbook columns were provided")
        return OperationResult(True, "Template workbook columns replaced", {"updated_columns": updated})

    def import_csv_to_worksheet(self, file_path: str | Path, book_name: str = "", delimiter: str = ",") -> OperationResult:
        path = Path(file_path)
        if not path.exists():
            return OperationResult(False, f"CSV file not found: {path}")
        header, columns = _parse_csv(path, delimiter)
        created = self.create_worksheet(book_name or path.stem)
        if not created.ok:
            return created
        actual_book = str(created.payload["book_name"])
        written = self.set_worksheet_data(actual_book, "Sheet1", columns, header or None)
        if not written.ok:
            return written
        return OperationResult(True, "CSV imported", {"book_name": actual_book, "columns": len(columns), "rows": len(columns[0])})

    def list_worksheets(self) -> OperationResult:
        self.run_labtalk(
            'string __rdop_pages$ = ""; '
            'doc -e W { __rdop_pages$ = __rdop_pages$ + page.name$ + "|workbook;"; }; '
            'doc -e P { __rdop_pages$ = __rdop_pages$ + page.name$ + "|graph;"; };'
        )
        raw = str(self.app.LTStr("__rdop_pages$"))
        pages = []
        for entry in raw.split(";"):
            if not entry:
                continue
            name, _, page_type = entry.partition("|")
            if name and page_type:
                pages.append({"name": name, "type": page_type})
        return OperationResult(True, "Pages listed", {"pages": pages})

    def create_graph(
        self,
        graph_name: str,
        data_book: str,
        data_sheet: str,
        x_col: int,
        y_col: int,
        plot_type: str = "line",
        y_error_col: int = 0,
        title: str = "",
    ) -> OperationResult:
        ptype = PLOT_TYPES.get(plot_type)
        if ptype is None:
            return OperationResult(False, f"Unsupported plot type: {plot_type}")
        graph = self.app.CreatePage(3, safe_origin_name(graph_name, "Graph"), "origin")
        data_ref = f"[{data_book}]{data_sheet}!({x_col},{y_col})"
        if y_error_col > 0:
            data_ref = f"[{data_book}]{data_sheet}!({x_col},{y_col},{y_error_col})"
        self.run_labtalk(f"plotxy iy:={data_ref} plot:={ptype} ogl:=[{graph}]Layer1;")
        if title:
            self.run_labtalk(f'label -n title -s "{quote_origin_text(title)}"; title.x = 50; title.y = 95;')
        return OperationResult(True, "Graph created", {"graph_name": graph, "plot_type": plot_type})

    def add_plot_to_graph(
        self,
        graph_name: str,
        data_book: str,
        data_sheet: str,
        x_col: int,
        y_col: int,
        plot_type: str = "line",
        y_error_col: int = 0,
    ) -> OperationResult:
        ptype = PLOT_TYPES.get(plot_type)
        if ptype is None:
            return OperationResult(False, f"Unsupported plot type: {plot_type}")
        data_ref = f"[{data_book}]{data_sheet}!({x_col},{y_col})"
        if y_error_col > 0:
            data_ref = f"[{data_book}]{data_sheet}!({x_col},{y_col},{y_error_col})"
        self.run_labtalk(f"plotxy iy:={data_ref} plot:={ptype} ogl:=[{graph_name}]Layer1;")
        return OperationResult(True, "Plot added", {"graph_name": graph_name, "plot_type": plot_type})

    def set_axis_labels(self, graph_name: str, x_label: str = "", y_label: str = "", title: str = "") -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if x_label:
            self.run_labtalk(f'xb.text$ = "{quote_origin_text(x_label)}";')
        if y_label:
            self.run_labtalk(f'yl.text$ = "{quote_origin_text(y_label)}";')
        if title:
            self.run_labtalk(f'label -n title -s "{quote_origin_text(title)}"; title.x = 50; title.y = 95;')
        return OperationResult(True, "Axis labels updated", {"graph_name": graph_name})

    def set_axis_range(
        self,
        graph_name: str,
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        commands = []
        if x_min is not None:
            commands.append(f"layer.x.from = {x_min};")
        if x_max is not None:
            commands.append(f"layer.x.to = {x_max};")
        if y_min is not None:
            commands.append(f"layer.y.from = {y_min};")
        if y_max is not None:
            commands.append(f"layer.y.to = {y_max};")
        if commands:
            self.run_labtalk(" ".join(commands))
        return OperationResult(True, "Axis range updated", {"graph_name": graph_name})

    def export_graph(
        self,
        graph_name: str,
        file_path: str | Path,
        export_format: str = "tif",
        dpi: int = 600,
        timeout_seconds: float = 8.0,
    ) -> OperationResult:
        try:
            output_path, resolved_format = normalize_export_path(file_path, export_format)
        except ValueError as exc:
            return OperationResult(False, str(exc))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        folder = quote_labtalk(to_origin_path(output_path.parent))
        filename = quote_labtalk(output_path.stem)
        graph = quote_labtalk(graph_name)
        self.run_labtalk(f'win -a "{graph}";')
        ok = self.run_labtalk(
            f'expGraph type:={resolved_format} path:="{folder}" filename:="{filename}" overwrite:=replace;'
        )
        if not ok.ok:
            return OperationResult(False, f"Origin expGraph failed for {graph_name}")
        if not _wait_for_file(output_path, timeout_seconds):
            return OperationResult(False, f"No exported file produced at {output_path}", {"file_path": str(output_path)})
        return OperationResult(True, "Graph exported", {"graph_name": graph_name, "file_path": str(output_path)})

    def export_all_graphs(self, output_dir: str | Path, export_format: str = "tif", dpi: int = 600) -> OperationResult:
        pages = self.list_worksheets()
        graph_pages = [item["name"] for item in pages.payload.get("pages", []) if item.get("type") == "graph"]
        exported = []
        failures = []
        for graph_name in graph_pages:
            result = self.export_graph(str(graph_name), Path(output_dir) / f"{graph_name}.{export_format}", export_format, dpi)
            if result.ok:
                exported.append(result.payload["file_path"])
            else:
                failures.append({"graph_name": graph_name, "message": result.message})
        return OperationResult(
            not failures,
            "All graphs exported" if not failures else "Some graph exports failed",
            {"exported": exported, "failures": failures},
        )

    def _plot_names(self, graph_name: str) -> list[str]:
        layer = self.app.FindGraphLayer(f"[{graph_name}]Layer1")
        if not layer:
            return []
        data_plots = layer.DataPlots
        return [data_plots.Item(index).Name for index in range(data_plots.Count)]

    def set_plot_style(
        self,
        graph_name: str,
        plot_index: int = 1,
        line_width: float = 1.5,
        symbol_size: int = 8,
        symbol_shape: int = 0,
        color: str = "",
    ) -> OperationResult:
        plot_names = self._plot_names(graph_name)
        index = plot_index - 1
        if index < 0 or index >= len(plot_names):
            return OperationResult(False, f"Plot index {plot_index} not found", {"available_plots": plot_names})
        plot_name = plot_names[index]
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if color:
            color_code = COLOR_MAP.get(color.lower())
            if color_code is None:
                return OperationResult(False, f"Unsupported color: {color}")
            self.run_labtalk(f"set {plot_name} -c {color_code};")
        self.run_labtalk(f"set {plot_name} -wp {float(line_width):g};")
        self.run_labtalk(f"set {plot_name} -k {symbol_shape or SYMBOL_SHAPES.get(plot_index, 2)};")
        self.run_labtalk(f"set {plot_name} -z {symbol_size};")
        self.run_labtalk(f"set {plot_name} -l 1;")
        return OperationResult(True, "Plot style updated", {"plot_name": plot_name})

    def set_graph_font(
        self,
        graph_name: str,
        font_name: str = "Arial",
        axis_title_size: int = 36,
        target: str = "all",
        x_tick_label_size: int = 28,
        y_tick_label_size: int = 36,
        legend_font_size: int = 26,
        annotation_font_size: int = 26,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if target in {"all", "axes"}:
            self.run_labtalk(f'xb.font$ = "{quote_labtalk(font_name)}"; xb.fsize = {axis_title_size}; xb.bold = 1;')
            self.run_labtalk(f'yl.font$ = "{quote_labtalk(font_name)}"; yl.fsize = {axis_title_size}; yl.bold = 1;')
        if target in {"all", "tick"}:
            self.run_labtalk(f"layer.x.label.pt = {x_tick_label_size}; layer.y.label.pt = {y_tick_label_size};")
            self.run_labtalk("layer.x.label.bold = 1; layer.y.label.bold = 1;")
        if target in {"all", "legend"}:
            self.run_labtalk(
                f'legend.font$ = "{quote_labtalk(font_name)}"; '
                f"legend.font = font({quote_labtalk(font_name)}); "
                f"legend.fsize = {legend_font_size}; "
                "legend.bold = 1; legend.color = color(black);"
            )
            self._disable_legend_box()
        if target in {"all", "annotation"}:
            self.run_labtalk(f'doc -e O {{if(object.type==4) {{object.font$="{quote_labtalk(font_name)}"; object.fsize={annotation_font_size}; object.bold=1;}}}}')
        if target == "title":
            self.run_labtalk(f'title.font$ = "{quote_labtalk(font_name)}"; title.fsize = {axis_title_size}; title.bold = 1;')
        return OperationResult(True, "Graph font updated", {"graph_name": graph_name, "target": target})

    def set_y_tick_values_visible(self, graph_name: str, visible: bool) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        value = 1 if visible else 0
        self.run_labtalk(f"layer.y.label.show = {value}; layer.y.showLabels = {value};")
        return OperationResult(True, "Y tick value visibility updated", {"graph_name": graph_name, "visible": visible})

    def set_axis_and_tick_visibility(
        self,
        graph_name: str,
        y_axis: bool = True,
        y_ticks: bool = True,
        y_tick_values: bool = True,
        x_tick_values: bool = True,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(f"layer.y.show = {1 if y_axis else 0};")
        self.run_labtalk(f"layer.y.ticks = {1 if y_ticks else 0};")
        y_label_value = 1 if y_tick_values else 0
        x_label_value = 1 if x_tick_values else 0
        self.run_labtalk(f"layer.y.label.show = {y_label_value}; layer.y.showLabels = {y_label_value};")
        self.run_labtalk(f"layer.x.label.show = {x_label_value}; layer.x.showLabels = {x_label_value};")
        return OperationResult(
            True,
            "Axis and tick visibility updated",
            {
                "graph_name": graph_name,
                "y_axis": y_axis,
                "y_ticks": y_ticks,
                "y_tick_values": y_tick_values,
                "x_tick_values": x_tick_values,
            },
        )

    def apply_graph4_fixed_style(self, graph_name: str, style_policy: Graph4FixedStyle = GRAPH4_FIXED_STYLE) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(
            "page.kar=0; "
            f"page.width={style_policy.page_width}; page.height={style_policy.page_height}; "
            "page.customwidth=1; page.customheight=1;"
        )
        self.run_labtalk(
            f"layer.left={style_policy.layer_left}; layer.top={style_policy.layer_top}; "
            f"layer.width={style_policy.layer_width}; layer.height={style_policy.layer_height};"
        )
        self.run_labtalk(
            f"layer.x.thickness = {style_policy.axis_line_width}; "
            f"layer.y.thickness = {style_policy.axis_line_width};"
        )
        self.set_graph_font(
            graph_name,
            style_policy.font_family,
            axis_title_size=style_policy.axis_title_size,
            x_tick_label_size=style_policy.x_tick_label_size,
            y_tick_label_size=style_policy.y_tick_label_size,
            legend_font_size=style_policy.legend_font_size,
            annotation_font_size=style_policy.annotation_font_size,
        )
        self._disable_legend_box()
        self.run_labtalk(f"doc -e DY {{set %C -lw {style_policy.line_width};}}")
        return OperationResult(True, "Graph4 fixed style applied", {"graph_name": graph_name})

    def set_legend(
        self,
        graph_name: str,
        visible: bool = True,
        position: str = "top-right",
        entries: Iterable[str] | None = None,
    ) -> OperationResult:
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        if not visible:
            self.run_labtalk("legend.show = 0;")
            return OperationResult(True, "Legend hidden", {"graph_name": graph_name})
        self.run_labtalk("legend -r;")
        if entries:
            legend_text = _legend_text_from_entries(list(entries))
            if legend_text:
                self.run_labtalk(f"legend.text$ = {legend_text};")
        self.run_labtalk("legend.bold = 1; legend.color = color(black);")
        self._disable_legend_box()
        fractions = {
            "top-left": (0.05, 0.85),
            "top-right": (0.65, 0.85),
            "bottom-left": (0.05, 0.15),
            "bottom-right": (0.65, 0.15),
        }
        if position in fractions:
            x_fraction, y_fraction = fractions[position]
            self.run_labtalk(
                f"legend.x = layer.x.from + {x_fraction} * (layer.x.to - layer.x.from); "
                f"legend.y = layer.y.from + {y_fraction} * (layer.y.to - layer.y.from);"
            )
        return OperationResult(True, "Legend updated", {"graph_name": graph_name, "position": position})

    def set_tick_style(
        self,
        graph_name: str,
        tick_direction: str = "in",
        major_length: int = 8,
        minor_count: int = 4,
        show_minor: bool = True,
    ) -> OperationResult:
        direction = {"in": 1, "out": 2, "both": 3}.get(tick_direction, 1)
        minor = minor_count if show_minor else 0
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(
            f"layer.x.ticks = {direction}; layer.y.ticks = {direction}; "
            f"layer.x.minor = {minor}; layer.y.minor = {minor}; "
            f"layer.x.majorLen = {major_length}; layer.y.majorLen = {major_length};"
        )
        return OperationResult(True, "Tick style updated", {"graph_name": graph_name})

    def apply_publication_style(
        self,
        graph_name: str,
        x_label: str = "",
        y_label: str = "",
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
        legend_entries: Iterable[str] | None = None,
        legend_position: str = "top-right",
        font_name: str = "Arial",
        axis_title_size: int = 36,
        line_width: float = 3.0,
        x_tick_label_size: int = 28,
        y_tick_label_size: int = 36,
        legend_font_size: int = 26,
        annotation_font_size: int = 26,
        axis_line_width: int = 3,
    ) -> OperationResult:
        self.set_axis_labels(graph_name, x_label, y_label)
        self.set_axis_range(graph_name, x_min, x_max, y_min, y_max)
        self.set_graph_font(
            graph_name,
            font_name,
            axis_title_size,
            "all",
            x_tick_label_size,
            y_tick_label_size,
            legend_font_size,
            annotation_font_size,
        )
        self.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
        self.run_labtalk(f"layer.x.thickness = {axis_line_width}; layer.y.thickness = {axis_line_width};")
        self.set_tick_style(graph_name)
        self.set_legend(graph_name, True, legend_position, legend_entries)
        self._disable_legend_box()
        for index, color in enumerate(("blue", "red", "green", "orange", "purple", "cyan"), start=1):
            result = self.set_plot_style(graph_name, index, line_width=line_width, color=color)
            if not result.ok and index == 1:
                break
        return OperationResult(True, "Publication-style operation bundle applied", {"graph_name": graph_name})

    def _disable_legend_box(self) -> None:
        self.run_labtalk(
            "legend.background = 0; legend.border = 0; legend.frame = 0; legend.fill = 0; "
            "legend.fillColor = 0; legend.borderColor = 0; legend.lineWidth = 0;"
        )


def _legend_text_from_entries(entries: list[str]) -> str:
    lines = []
    for index, entry in enumerate(entries, start=1):
        text = _legend_entry_text(entry)
        if text:
            lines.append(f"\\l({index}) {text}")
    return "\n".join(lines)


def _legend_entry_text(entry: object) -> str:
    text = origin_bold_text(entry)
    return str(text).replace(";", ",").replace("\r", " ").replace("\n", " ").strip()
