from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from src.origin.style_mimic import OpjuStyleSnapshot


DEFAULT_USER_STYLE: dict[str, object] = {
    "font_family": "Arial",
    "line_width_pt": 3.0,
    "axis_line_width_pt": 2.0,
    "tick_width_pt": 1.5,
    "axis_title_font_size": 36,
    "tick_label_font_size": 28,
    "x_tick_label_font_size": 28,
    "y_tick_label_font_size": 36,
    "legend_font_size": 22,
    "title_font_size": 28,
    "marker_size": 6,
    "font_bold": True,
    "legend_no_frame": True,
    "export_dpi": 600,
}


@dataclass(frozen=True)
class ResolvedPlotStyle:
    font_family: str = "Arial"
    line_width_pt: float = 3.0
    axis_line_width_pt: float = 2.0
    tick_width_pt: float = 1.5
    axis_title_font_size: int = 36
    tick_label_font_size: int = 28
    x_tick_label_font_size: int = 28
    y_tick_label_font_size: int = 36
    legend_font_size: int = 22
    title_font_size: int = 28
    marker_size: int = 6
    font_bold: bool = True
    legend_no_frame: bool = True
    export_dpi: int = 600

    def __post_init__(self) -> None:
        # Keep direct construction with the legacy shared field compatible.
        if self.tick_label_font_size != 28 and self.x_tick_label_font_size == 28 and self.y_tick_label_font_size == 36:
            object.__setattr__(self, "x_tick_label_font_size", self.tick_label_font_size)
            object.__setattr__(self, "y_tick_label_font_size", self.tick_label_font_size)

    def to_dict(self) -> dict[str, object]:
        return {
            "font_family": self.font_family,
            "line_width_pt": self.line_width_pt,
            "axis_line_width_pt": self.axis_line_width_pt,
            "tick_width_pt": self.tick_width_pt,
            "axis_title_font_size": self.axis_title_font_size,
            "tick_label_font_size": self.tick_label_font_size,
            "x_tick_label_font_size": self.x_tick_label_font_size,
            "y_tick_label_font_size": self.y_tick_label_font_size,
            "legend_font_size": self.legend_font_size,
            "title_font_size": self.title_font_size,
            "marker_size": self.marker_size,
            "font_bold": self.font_bold,
            "legend_no_frame": self.legend_no_frame,
            "export_dpi": self.export_dpi,
        }


def load_user_plot_style(project_root: Path, explicit_path: Path | None = None) -> dict[str, Any]:
    path = explicit_path or project_root / "config" / "user_plot_style.yaml"
    if explicit_path is None and not path.exists():
        return {}
    if not path.exists():
        raise FileNotFoundError(f"user plot style file not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"user plot style must be a mapping: {path}")
    return dict(loaded)


def resolve_user_plot_style(
    product_key: str,
    *,
    exemplar: OpjuStyleSnapshot | dict[str, Any] | None = None,
    user_config: dict[str, Any] | None = None,
) -> ResolvedPlotStyle:
    values: dict[str, object] = dict(DEFAULT_USER_STYLE)
    if _style_key(product_key) == "eis":
        values.update({"marker_size": 8})
    _merge_style_values(values, _style_from_exemplar(exemplar))
    config = user_config or {}
    global_values = config.get("global") if isinstance(config.get("global"), dict) else {}
    _merge_style_values(values, global_values)
    type_values = config.get(_style_key(product_key)) if isinstance(config.get(_style_key(product_key)), dict) else {}
    _merge_style_values(values, type_values)
    return _coerce_style(values)


def apply_resolved_style_overrides(operations: object, graph_name: str, style: ResolvedPlotStyle) -> None:
    graph_activation = f'win -a "{graph_name}"; '
    operations.run_labtalk(
        graph_activation +
        f"layer.x.thickness={style.axis_line_width_pt}; layer.y.thickness={style.axis_line_width_pt}; "
        f"layer.x.label.pt={style.x_tick_label_font_size}; layer.y.label.pt={style.y_tick_label_font_size}; "
        f"xb.font$=\"{style.font_family}\"; yl.font$=\"{style.font_family}\"; legend.font$=\"{style.font_family}\"; "
        f"xb.fsize={style.axis_title_font_size}; yl.fsize={style.axis_title_font_size}; "
        f"legend.fsize={style.legend_font_size}; title.fsize={style.title_font_size};"
    )
    if style.font_bold:
        operations.run_labtalk(graph_activation + "xb.bold=1; yl.bold=1; layer.x.label.bold=1; layer.y.label.bold=1; legend.bold=1;")
    if style.legend_no_frame:
        operations.run_labtalk(
            graph_activation
            + "legend.background=0; legend.border=0; legend.frame=0; legend.fill=0; "
            + "legend.fillColor=0; legend.borderColor=0; legend.lineWidth=0;"
        )
    operations.run_labtalk(graph_activation + f"doc -e DY {{set %C -wp {float(style.line_width_pt):g}; set %C -z {style.marker_size};}}")


def _style_from_exemplar(exemplar: OpjuStyleSnapshot | dict[str, Any] | None) -> dict[str, object]:
    if exemplar is None:
        return {}
    numeric = exemplar.audit_numeric_values if isinstance(exemplar, OpjuStyleSnapshot) else exemplar.get("audit_numeric_values", {})
    layout = exemplar.layout_values if isinstance(exemplar, OpjuStyleSnapshot) else exemplar.get("layout_values", {})
    widths = exemplar.plot_line_widths if isinstance(exemplar, OpjuStyleSnapshot) else exemplar.get("plot_line_widths", [])
    values: dict[str, object] = {}
    line_width = _median_number(widths)
    if line_width is not None:
        values["line_width_pt"] = line_width / 500.0 if line_width > 100 else line_width
    axis_width = _first_number(layout, "layer.x.thickness", "layer.y.thickness")
    if axis_width is not None:
        values["axis_line_width_pt"] = axis_width
    axis_title = _first_number(numeric, "xb.fsize", "yl.fsize")
    if axis_title is not None:
        values["axis_title_font_size"] = int(round(axis_title))
    x_tick_label = _first_number(layout, "layer.x.label.pt")
    y_tick_label = _first_number(layout, "layer.y.label.pt")
    if x_tick_label is not None and y_tick_label is None:
        values["tick_label_font_size"] = int(round(x_tick_label))
    elif y_tick_label is not None and x_tick_label is None:
        values["tick_label_font_size"] = int(round(y_tick_label))
    else:
        if x_tick_label is not None:
            values["tick_label_font_size"] = int(round(x_tick_label))
            values["x_tick_label_font_size"] = int(round(x_tick_label))
        if y_tick_label is not None:
            values["y_tick_label_font_size"] = int(round(y_tick_label))
    legend = _first_number(numeric, "legend.fsize")
    if legend is not None:
        values["legend_font_size"] = int(round(legend))
    return values


def _merge_style_values(target: dict[str, object], updates: dict[str, object]) -> None:
    if "tick_label_font_size" in updates:
        shared = updates["tick_label_font_size"]
        target["x_tick_label_font_size"] = shared
        target["y_tick_label_font_size"] = shared
    target.update(updates)


def _coerce_style(values: dict[str, object]) -> ResolvedPlotStyle:
    style = ResolvedPlotStyle()
    for field_name, default in style.to_dict().items():
        raw = values.get(field_name, default)
        if isinstance(default, bool):
            style = replace(style, **{field_name: _to_bool(raw)})
        elif isinstance(default, str):
            style = replace(style, **{field_name: str(raw)})
        elif isinstance(default, int):
            style = replace(style, **{field_name: int(round(float(raw)))})
        else:
            style = replace(style, **{field_name: float(raw)})
    return style


def _style_key(product_key: str) -> str:
    lowered = product_key.casefold()
    if lowered.startswith("xps"):
        return "xps"
    if "uv" in lowered:
        return "uv_vis_drs_tauc"
    return (
        lowered.replace("/", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("__", "_")
        .strip("_")
    )


def _first_number(mapping: object, *keys: str) -> float | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        try:
            return float(mapping[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _median_number(values: object) -> float | None:
    if not isinstance(values, list) or not values:
        return None
    numbers = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not numbers:
        return None
    return numbers[len(numbers) // 2]


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}
