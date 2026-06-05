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


def test_apply_resolved_style_overrides_emits_line_width_and_bold_axis_policy() -> None:
    fake = _FakeOps()
    style = resolve_user_plot_style("XRD", user_config={"global": {"line_width_pt": 3.0, "font_bold": True}})

    apply_resolved_style_overrides(fake, "Graph1", style)

    joined = "\n".join(fake.scripts)
    assert "set %C -w 30" in joined
    assert "xb.bold=1" in joined
    assert "yl.bold=1" in joined


class _FakeOps:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def run_labtalk(self, script: str):
        self.scripts.append(script)
        return object()
