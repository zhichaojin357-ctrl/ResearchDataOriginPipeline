from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.origin.operations import quote_labtalk


STYLE_LAYOUT_FIELDS = (
    "page.width",
    "page.height",
    "page.kar",
    "layer.left",
    "layer.top",
    "layer.width",
    "layer.height",
    "layer.x.from",
    "layer.x.to",
    "layer.y.from",
    "layer.y.to",
    "layer.x.thickness",
    "layer.y.thickness",
    "layer.x.ticks",
    "layer.y.ticks",
    "layer.x.majorLen",
    "layer.y.majorLen",
    "layer.x.minor",
    "layer.y.minor",
    "layer.x.label.pt",
    "layer.y.label.pt",
    "layer.x.label.show",
    "layer.y.label.show",
    "layer.x.showLabels",
    "layer.y.showLabels",
    "layer.x.label.bold",
    "layer.y.label.bold",
    "layer.x.label.offset",
    "layer.y.label.offset",
    "xb.show",
    "yl.show",
    "xb.fsize",
    "yl.fsize",
    "xb.bold",
    "yl.bold",
    "xb.x",
    "xb.y",
    "yl.x",
    "yl.y",
    "legend.show",
    "legend.x",
    "legend.y",
    "legend.background",
    "legend.border",
    "legend.frame",
    "legend.fill",
    "legend.fillColor",
    "legend.borderColor",
    "legend.lineWidth",
    "legend.fsize",
    "legend.bold",
    "title.show",
    "title.x",
    "title.y",
    "title.fsize",
    "title.bold",
)

STYLE_AUDIT_NUMERIC_FIELDS = (
    "page.nlayers",
    "layer.x.ticks",
    "layer.y.ticks",
    "layer.x.label.show",
    "layer.y.label.show",
    "layer.x.showLabels",
    "layer.y.showLabels",
    "xb.show",
    "yl.show",
    "xb.fsize",
    "yl.fsize",
    "xb.bold",
    "yl.bold",
    "legend.show",
    "legend.x",
    "legend.y",
    "legend.background",
    "legend.border",
    "legend.frame",
    "legend.fill",
    "legend.fillColor",
    "legend.borderColor",
    "legend.lineWidth",
    "legend.fsize",
    "legend.bold",
    "title.show",
    "title.fsize",
    "title.bold",
)

STYLE_AUDIT_STRING_FIELDS = (
    "xb.font$",
    "yl.font$",
    "xb.text$",
    "yl.text$",
    "legend.font$",
    "legend.text$",
    "title.font$",
)

FORBIDDEN_EXEMPLAR_TEXT_CATEGORIES = (
    "peak assignments",
    "crystal-plane labels",
    "phase labels",
    "XPS valence labels",
    "mechanism arrows or text",
    "EPR radical labels",
    "product identity labels",
    "conversion/selectivity/yield text",
)


@dataclass(frozen=True)
class OpjuStyleSnapshot:
    source_opju: str
    status: str
    graph_page: str | None = None
    graph_pages: list[str] = field(default_factory=list)
    layout_values: dict[str, float] = field(default_factory=dict)
    audit_numeric_values: dict[str, float] = field(default_factory=dict)
    audit_string_values: dict[str, str] = field(default_factory=dict)
    layer_count: int = 0
    plot_count: int = 0
    plot_line_widths: list[float] = field(default_factory=list)
    plot_colors: list[float] = field(default_factory=list)
    marker_shapes: list[float] = field(default_factory=list)
    marker_sizes: list[float] = field(default_factory=list)
    graph_object_positions: dict[str, dict[str, float]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    copied_visible_text: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_opju": self.source_opju,
            "status": self.status,
            "graph_page": self.graph_page,
            "graph_pages": list(self.graph_pages),
            "layout_values": dict(self.layout_values),
            "audit_numeric_values": dict(self.audit_numeric_values),
            "audit_string_values": dict(self.audit_string_values),
            "layer_count": self.layer_count,
            "plot_count": self.plot_count,
            "plot_line_widths": list(self.plot_line_widths),
            "plot_colors": list(self.plot_colors),
            "marker_shapes": list(self.marker_shapes),
            "marker_sizes": list(self.marker_sizes),
            "graph_object_positions": {
                name: dict(values) for name, values in self.graph_object_positions.items()
            },
            "warnings": list(self.warnings),
            "copied_visible_text": self.copied_visible_text,
            "forbidden_visible_text_categories": list(FORBIDDEN_EXEMPLAR_TEXT_CATEGORIES),
        }


def extract_style_snapshot(operations: object, reference_opju: Path) -> OpjuStyleSnapshot:
    load_result = operations.load_project(reference_opju)
    if not getattr(load_result, "ok", False):
        return OpjuStyleSnapshot(reference_opju.name, "load_failed", warnings=[str(getattr(load_result, "message", ""))])

    pages_result = operations.list_worksheets()
    graph_pages = [
        str(item["name"])
        for item in getattr(pages_result, "payload", {}).get("pages", [])
        if item.get("type") == "graph"
    ]
    if not graph_pages:
        return OpjuStyleSnapshot(reference_opju.name, "no_graph_pages", warnings=["No graph pages were available in the copied exemplar."])

    snapshots = [
        read_graph_style_snapshot(
            operations,
            graph_page,
            source_label=reference_opju.name,
            graph_pages=graph_pages,
        )
        for graph_page in graph_pages
    ]
    return max(snapshots, key=_graph_page_selection_score)


def read_graph_style_snapshot(
    operations: object,
    graph_page: str,
    *,
    source_label: str = "",
    graph_pages: list[str] | None = None,
) -> OpjuStyleSnapshot:
    activated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_page)}";')
    if not getattr(activated, "ok", False):
        return OpjuStyleSnapshot(
            source_opju=source_label,
            status="graph_activation_failed",
            graph_page=graph_page,
            graph_pages=list(graph_pages or []),
            warnings=[f"Requested graph page could not be activated: {graph_page}"],
        )
    layout_values = _read_numeric_fields(operations, STYLE_LAYOUT_FIELDS)
    audit_numeric_values = _read_numeric_fields(operations, STYLE_AUDIT_NUMERIC_FIELDS)
    audit_string_values = _read_string_fields(operations, STYLE_AUDIT_STRING_FIELDS)
    layer_count = int(audit_numeric_values.get("page.nlayers", 0))
    plot_names = _plot_names(operations, graph_page)
    plot_line_widths = _read_plot_properties(operations, plot_names, "-w")
    plot_colors = _read_plot_properties(operations, plot_names, "-c")
    marker_shapes = _read_plot_properties(operations, plot_names, "-k")
    marker_sizes = _read_plot_properties(operations, plot_names, "-z")
    return OpjuStyleSnapshot(
        source_opju=source_label,
        status="extracted",
        graph_page=graph_page,
        graph_pages=list(graph_pages or [graph_page]),
        layout_values=layout_values,
        audit_numeric_values=audit_numeric_values,
        audit_string_values=audit_string_values,
        layer_count=layer_count,
        plot_count=len(plot_names),
        plot_line_widths=plot_line_widths,
        plot_colors=plot_colors,
        marker_shapes=marker_shapes,
        marker_sizes=marker_sizes,
        graph_object_positions=_read_graph_object_positions(operations),
        warnings=[
            "Visible scientific annotations are not copied from the exemplar.",
            "Series line width is later overridden by the product policy when required.",
        ],
    )


def apply_style_snapshot(
    operations: object,
    graph_name: str,
    snapshot: OpjuStyleSnapshot | dict[str, Any],
    *,
    apply_default_font: bool = True,
) -> bool:
    layout_values = snapshot.layout_values if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("layout_values", {})
    audit_numeric = snapshot.audit_numeric_values if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("audit_numeric_values", {})
    if not isinstance(layout_values, dict) or not layout_values:
        return False
    commands = []
    for key, value in layout_values.items():
        number = _to_float(value)
        if number is not None and math.isfinite(number):
            commands.append(f"{key}={number};")
    if isinstance(audit_numeric, dict):
        for key in ("layer.x.label.show", "layer.y.label.show", "layer.x.showLabels", "layer.y.showLabels"):
            if key in layout_values:
                continue
            number = _to_float(audit_numeric.get(key))
            if number is not None and math.isfinite(number):
                commands.append(f"{key}={number};")
    if not commands:
        return False
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    operations.run_labtalk("page.kar=0; page.customwidth=1; page.customheight=1; " + " ".join(commands))
    _apply_plot_style_snapshot(operations, graph_name, snapshot)
    if apply_default_font and hasattr(operations, "set_graph_font"):
        operations.set_graph_font(graph_name)
    return True


def _apply_plot_style_snapshot(
    operations: object,
    graph_name: str,
    snapshot: OpjuStyleSnapshot | dict[str, Any],
) -> None:
    plot_names = _plot_names(operations, graph_name)
    if not plot_names:
        return
    widths = snapshot.plot_line_widths if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("plot_line_widths", [])
    colors = snapshot.plot_colors if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("plot_colors", [])
    shapes = snapshot.marker_shapes if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("marker_shapes", [])
    sizes = snapshot.marker_sizes if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("marker_sizes", [])
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    for index, plot_name in enumerate(plot_names):
        commands: list[str] = []
        if index < len(widths):
            width = _origin_line_width_to_set_value(widths[index])
            if width is not None:
                commands.append(f"set {plot_name} -wp {width:g};")
        if index < len(colors):
            color = _to_float(colors[index])
            if color is not None and math.isfinite(color):
                commands.append(f"set {plot_name} -c {int(round(color))};")
        if index < len(shapes):
            shape = _to_float(shapes[index])
            if shape is not None and math.isfinite(shape):
                commands.append(f"set {plot_name} -k {int(round(shape))};")
        if index < len(sizes):
            size = _to_float(sizes[index])
            if size is not None and math.isfinite(size):
                commands.append(f"set {plot_name} -z {int(round(size))};")
        if commands:
            operations.run_labtalk(" ".join(commands))


def _origin_line_width_to_set_value(value: object) -> float | None:
    number = _to_float(value)
    if number is None or not math.isfinite(number):
        return None
    if number > 100:
        return max(0.1, number / 500.0)
    return number


def _read_numeric_fields(operations: object, fields: tuple[str, ...]) -> dict[str, float]:
    values: dict[str, float] = {}
    for field_name in fields:
        read = operations.get_labtalk_variable(field_name)
        value = _to_float(getattr(read, "payload", {}).get("value"))
        if value is not None and math.isfinite(value):
            values[field_name] = value
    return values


def _read_string_fields(operations: object, fields: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    for field_name in fields:
        try:
            read = operations.get_labtalk_variable(field_name)
        except Exception:
            continue
        value = getattr(read, "payload", {}).get("value")
        if value is not None and str(value).strip():
            values[field_name] = str(value)
    return values


def _plot_names(operations: object, graph_name: str) -> list[str]:
    getter = getattr(operations, "_plot_names", None)
    if getter is None:
        return []
    try:
        return [str(name) for name in getter(graph_name)]
    except Exception:
        return []


def _read_plot_properties(operations: object, plot_names: list[str], option: str) -> list[float]:
    values: list[float] = []
    for index, plot_name in enumerate(plot_names, start=1):
        variable = f"__style_mimic_{option.strip('-')}_{index}"
        operations.run_labtalk(f"get {plot_name} {option} {variable};")
        read = operations.get_labtalk_variable(variable)
        value = _to_float(getattr(read, "payload", {}).get("value"))
        if value is not None and math.isfinite(value):
            values.append(value)
    return values


def _read_graph_object_positions(operations: object) -> dict[str, dict[str, float]]:
    app = getattr(operations, "app", None)
    if app is None:
        return {}
    try:
        layer = app.ActiveLayer()
    except Exception:
        return {}
    graph_objects = getattr(layer, "GraphObjects", None)
    if graph_objects is None:
        return {}
    try:
        count = int(graph_objects.Count)
    except Exception:
        return {}
    positions: dict[str, dict[str, float]] = {}
    for index in range(count):
        try:
            obj = graph_objects.Item(index)
        except Exception:
            continue
        name = str(getattr(obj, "Name", "") or f"object_{index + 1}")
        values: dict[str, float] = {}
        for attr in ("Left", "Top", "Width", "Height"):
            try:
                number = _to_float(getattr(obj, attr))
            except Exception:
                number = None
            if number is not None:
                values[attr.casefold()] = number
        if values:
            positions[name] = values
    return positions


def _graph_page_selection_score(snapshot: OpjuStyleSnapshot) -> tuple[float, str]:
    name = str(snapshot.graph_page or "")
    normalized_name = name.casefold()
    score = 0.0
    if normalized_name.startswith("sparkline"):
        score -= 100.0
    else:
        score += 100.0
    if normalized_name.startswith("graph"):
        score += 30.0
    score += min(snapshot.plot_count, 10) * 8.0
    score += min(len(snapshot.plot_colors), 10) * 2.0
    if _has_real_axis_title(snapshot.audit_string_values.get("xb.text$", "")):
        score += 20.0
    if _has_real_axis_title(snapshot.audit_string_values.get("yl.text$", "")):
        score += 20.0
    if snapshot.audit_numeric_values.get("xb.show", 0.0) > 0:
        score += 5.0
    if snapshot.audit_numeric_values.get("yl.show", 0.0) > 0:
        score += 5.0
    if snapshot.layout_values.get("layer.width", 0.0) >= 20.0 and snapshot.layout_values.get("layer.height", 0.0) >= 20.0:
        score += 5.0
    return (score, name)


def _has_real_axis_title(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    placeholders = {"%(?x)", "%(?y)", "%(?xl)", "%(?yl)"}
    return text.casefold() not in placeholders


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
