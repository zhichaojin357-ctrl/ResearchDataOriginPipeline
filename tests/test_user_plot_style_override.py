from __future__ import annotations

from pathlib import Path

from src.origin.style_mimic import OpjuStyleSnapshot
from src.origin.user_style import (
    apply_resolved_style_overrides,
    load_user_plot_style,
    resolve_user_plot_style,
)


def test_user_style_override_precedence_data_type_global_exemplar_default(tmp_path: Path) -> None:
    config_path = tmp_path / "style.yaml"
    config_path.write_text(
        """
global:
  line_width_pt: 3.0
  axis_title_font_size: 28
  tick_label_font_size: 24
  legend_font_size: 22
  export_dpi: 600
eis:
  marker_size: 8
  axis_title_font_size: 30
xps:
  axis_title_font_size: 24
  tick_label_font_size: 20
""".strip()
        + "\n",
        encoding="utf-8",
    )
    exemplar = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        audit_numeric_values={"xb.fsize": 36, "legend.fsize": 18},
        layout_values={"layer.x.label.pt": 26, "layer.x.thickness": 3},
        plot_line_widths=[15.0, 20.0],
    )

    style = resolve_user_plot_style("EIS", exemplar=exemplar, user_config=load_user_plot_style(tmp_path, config_path))

    assert style.line_width_pt == 3.0
    assert style.axis_title_font_size == 30
    assert style.tick_label_font_size == 24
    assert style.legend_font_size == 22
    assert style.marker_size == 8
    assert style.axis_line_width_pt == 3


def test_user_style_override_maps_xps_group_to_xps_key() -> None:
    style = resolve_user_plot_style(
        "XPS_non_in_situ",
        user_config={"global": {"axis_title_font_size": 28}, "xps": {"tick_label_font_size": 20}},
    )

    assert style.axis_title_font_size == 28
    assert style.tick_label_font_size == 20


def test_split_uvvis_products_keep_legacy_style_fallback_with_dedicated_override() -> None:
    config = {
        "uv_vis_drs_tauc": {"line_width_pt": 2.5, "axis_title_font_size": 31},
        "uv_vis_drs": {"axis_title_font_size": 33},
    }

    drs = resolve_user_plot_style("UV-vis DRS", user_config=config)
    tauc = resolve_user_plot_style("Tauc", user_config=config)

    assert drs.line_width_pt == 2.5
    assert drs.axis_title_font_size == 33
    assert tauc.line_width_pt == 2.5
    assert tauc.axis_title_font_size == 31


def test_exemplar_origin_line_width_units_convert_to_points() -> None:
    exemplar = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        plot_line_widths=[1500.0, 1500.0, 1500.0],
    )

    style = resolve_user_plot_style("XRD", exemplar=exemplar, user_config={})

    assert style.line_width_pt == 3.0


def test_apply_resolved_style_overrides_emits_line_width_and_bold_axis_policy() -> None:
    fake = _FakeOps()
    style = resolve_user_plot_style("XRD", user_config={"global": {"line_width_pt": 3.0, "font_bold": True}})

    apply_resolved_style_overrides(fake, "Graph1", style)

    joined = "\n".join(fake.scripts)
    assert "set %C -wp 3" in joined
    assert "xb.bold=1" in joined
    assert "yl.bold=1" in joined
    assert "legend.background=0" in joined
    assert "legend.lineWidth=0" in joined


def test_default_style_preserves_independent_graph4_x_and_y_tick_font_sizes() -> None:
    style = resolve_user_plot_style("XRD", user_config={})

    assert style.x_tick_label_font_size == 28
    assert style.y_tick_label_font_size == 36

    fake = _FakeOps()
    apply_resolved_style_overrides(fake, "Graph4", style)
    joined = "\n".join(fake.scripts)
    assert "layer.x.label.pt=28" in joined
    assert "layer.y.label.pt=36" in joined


def test_legacy_shared_tick_font_size_config_applies_to_both_axes() -> None:
    style = resolve_user_plot_style("XPS", user_config={"global": {"tick_label_font_size": 20}})

    assert style.tick_label_font_size == 20
    assert style.x_tick_label_font_size == 20
    assert style.y_tick_label_font_size == 20


def test_explicit_axis_tick_font_sizes_override_legacy_shared_value() -> None:
    style = resolve_user_plot_style(
        "XRD",
        user_config={
            "global": {
                "tick_label_font_size": 20,
                "x_tick_label_font_size": 29,
                "y_tick_label_font_size": 37,
            }
        },
    )

    assert style.x_tick_label_font_size == 29
    assert style.y_tick_label_font_size == 37


def test_apply_resolved_style_overrides_targets_the_named_graph_for_every_script() -> None:
    fake = _FakeOps()
    style = resolve_user_plot_style("EIS", user_config={"global": {"line_width_pt": 3.0, "font_bold": True}})

    apply_resolved_style_overrides(fake, "Graph_Target", style)

    assert fake.scripts
    assert all('win -a "Graph_Target"' in script for script in fake.scripts)


class _FakeOps:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def run_labtalk(self, script: str):
        self.scripts.append(script)
        return object()
