from __future__ import annotations

from pathlib import Path

import pytest

from src.origin.plot_policy import (
    GRAPH4_FIXED_STYLE,
    SUPPORTED_PLOT_PRIMITIVES,
    get_plot_policy,
    validate_graph4_style_config,
)


def test_plot_policy_covers_supported_data_types() -> None:
    expected = {
        "XRD",
        "Raman",
        "FTIR",
        "PL",
        "EPR",
        "XPS",
        "XPS fitted",
        "EIS",
        "EIS Bode",
        "photocurrent",
        "photocurrent_response",
        "Mott-Schottky",
        "BET",
        "BET pore distribution",
        "reaction_condition_screening",
        "cycling_test",
        "radical_trapping",
        "calibration_curve",
        "HPLC/LC exported data",
        "HPLC/LC peak summary",
        "SEM_image_panel",
        "TEM_image_panel",
        "EDS_map",
        "NMR exported spectrum",
        "MS spectrum",
        "energy_level_diagram",
    }

    for data_type in expected:
        policy = get_plot_policy(data_type)
        assert policy.plot_primitive in SUPPORTED_PLOT_PRIMITIVES
        if policy.plot_primitive in {"image_panel", "eds_map", "energy_level_schematic"}:
            assert policy.x_tick_values_visible is False
        else:
            assert policy.x_tick_values_visible is True
        assert policy.plot_policy_reason


def test_quantitative_plots_show_y_axis_ticks_and_values() -> None:
    for data_type in [
        "EIS",
        "EIS Bode",
        "photocurrent",
        "photocurrent_response",
        "Mott-Schottky",
        "BET",
        "BET pore distribution",
        "reaction_condition_screening",
        "calibration_curve",
        "HPLC/LC exported data",
    ]:
        policy = get_plot_policy(data_type)
        assert policy.y_axis_visible is True
        assert policy.y_ticks_visible is True
        assert policy.y_tick_values_visible is True


def test_offset_spectra_keep_y_axis_and_ticks_but_hide_numeric_values() -> None:
    for data_type in ["XRD", "Raman", "FTIR", "PL", "XPS", "XPS fitted"]:
        policy = get_plot_policy(data_type)
        assert policy.y_axis_visible is True
        assert policy.y_ticks_visible is True
        assert policy.y_tick_values_visible is False


def test_epr_overlays_keep_y_axis_but_hide_ticks_and_values() -> None:
    for data_type in ["EPR", "EPR overlay"]:
        policy = get_plot_policy(data_type)
        assert policy.y_axis_visible is True
        assert policy.y_ticks_visible is False
        assert policy.y_tick_values_visible is False


def test_xrd_policy_defaults_to_raw_pattern_line_not_reference_card_sticks() -> None:
    policy = get_plot_policy("XRD")

    assert policy.plot_primitive == "line"
    assert policy.origin_plot_code == "200"
    assert "reference-card stick layer" in policy.plot_policy_reason
    assert "explicit current standard-card data" in policy.plot_policy_reason
    assert "no automatic phase assignment" in policy.forbidden_claims
    assert "no automatic crystal-plane assignment" in policy.forbidden_claims


def test_image_panel_policies_hide_graph_axes() -> None:
    for data_type in ["SEM_image_panel", "TEM_image_panel", "EDS_map"]:
        policy = get_plot_policy(data_type)
        assert policy.plot_primitive == "image_panel" or policy.plot_primitive == "eds_map"
        assert policy.y_axis_visible is False
        assert policy.y_ticks_visible is False
        assert policy.y_tick_values_visible is False


def test_graph4_fixed_style_values_are_locked() -> None:
    assert GRAPH4_FIXED_STYLE.page_width == 6432
    assert GRAPH4_FIXED_STYLE.page_height == 4923
    assert GRAPH4_FIXED_STYLE.layer_left == 17.89
    assert GRAPH4_FIXED_STYLE.layer_top == 11.6
    assert GRAPH4_FIXED_STYLE.layer_width == 68.19
    assert GRAPH4_FIXED_STYLE.layer_height == 71.81
    assert GRAPH4_FIXED_STYLE.axis_title_size == 36
    assert GRAPH4_FIXED_STYLE.x_tick_label_size == 28
    assert GRAPH4_FIXED_STYLE.y_tick_label_size == 36
    assert GRAPH4_FIXED_STYLE.legend_font_size == 26
    assert GRAPH4_FIXED_STYLE.annotation_font_size == 26
    assert GRAPH4_FIXED_STYLE.axis_line_width == 3
    assert GRAPH4_FIXED_STYLE.line_width == 3
    assert GRAPH4_FIXED_STYLE.font_bold is True


def test_validate_graph4_style_config_rejects_drift(tmp_path: Path) -> None:
    plot_style = tmp_path / "plot_style.yaml"
    plot_style.write_text(
        "\n".join(
            [
                "line_width: 2",
                "axis_line_width: 3",
                "axis_title_size: 36",
                "x_tick_label_size: 28",
                "y_tick_label_size: 36",
                "legend_font_size: 26",
                "annotation_font_size: 26",
                "font_bold: true",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="line_width"):
        validate_graph4_style_config(plot_style)
