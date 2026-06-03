from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.project import _parse_simple_yaml


SUPPORTED_PLOT_PRIMITIVES = {
    "line",
    "scatter",
    "line+symbol",
    "column",
    "bar",
    "grouped_column",
    "stacked_column",
    "box",
    "lollipop",
    "chromatogram",
    "stick_spectrum",
    "heatmap",
    "contour",
    "semilog_decay",
    "bode",
    "dual_axis",
    "multi_layer",
    "fitted_component_overlay",
    "reference_card_stick_layer",
    "image_panel",
    "eds_map",
    "calibration_scatter",
    "energy_level_schematic",
}

ORIGIN_PLOT_CODES = {
    "line": "200",
    "scatter": "201",
    "line+symbol": "202",
    "column": "203",
    "bar": "204",
    "area": "205",
    "histogram": "206",
    "box": "207",
    "contour": "208",
    "pie": "212",
    "bubble": "228",
    "fitted_component_overlay": "200",
    "chromatogram": "200",
    "stick_spectrum": "200",
    "bode": "202",
    "semilog_decay": "200",
    "dual_axis": "202",
    "multi_layer": "200",
    "reference_card_stick_layer": "200",
    "image_panel": "200",
    "eds_map": "200",
    "calibration_scatter": "202",
    "energy_level_schematic": "200",
    "lollipop": "202",
    "grouped_column": "203",
    "stacked_column": "203",
    "heatmap": "208",
}


@dataclass(frozen=True)
class Graph4FixedStyle:
    page_width: int = 6432
    page_height: int = 4923
    layer_left: float = 17.89
    layer_top: float = 11.6
    layer_width: float = 68.19
    layer_height: float = 71.81
    axis_title_size: int = 36
    x_tick_label_size: int = 28
    y_tick_label_size: int = 36
    legend_font_size: int = 26
    annotation_font_size: int = 26
    axis_line_width: int = 3
    line_width: int = 3
    font_family: str = "Arial"
    font_bold: bool = True


@dataclass(frozen=True)
class PlotPolicy:
    data_type: str
    plot_primitive: str
    origin_plot_code: str
    marker_policy: str
    y_axis_visible: bool
    y_ticks_visible: bool
    y_tick_values_visible: bool
    x_tick_values_visible: bool
    allow_fit_overlay: bool
    fit_overlay_condition: str
    forbidden_claims: tuple[str, ...]
    plot_policy_reason: str


GRAPH4_FIXED_STYLE = Graph4FixedStyle()


_POLICIES: dict[str, PlotPolicy] = {
    "XRD": PlotPolicy(
        "XRD",
        "line",
        "200",
        "none",
        True,
        True,
        False,
        True,
        False,
        "reference-card sticks only when current standard-card data are supplied",
        ("no automatic phase assignment", "no automatic crystal-plane assignment"),
        "arbitrary-unit XRD exemplars use raw-pattern line overlays by default; no reference-card stick layer is drawn unless explicit current standard-card data are supplied",
    ),
    "Raman": PlotPolicy(
        "Raman",
        "line",
        "200",
        "none",
        True,
        True,
        False,
        True,
        False,
        "baseline/corrected traces only when provenance is recorded",
        ("no automatic vibrational-mode assignment", "no automatic defect assignment"),
        "dense arbitrary-unit Raman spectra use line overlays and hide Y numeric labels when normalized or offset",
    ),
    "FTIR": PlotPolicy(
        "FTIR",
        "line",
        "200",
        "none",
        True,
        True,
        False,
        True,
        False,
        "band markers only when supplied or flagged as candidates",
        ("no automatic bond assignment",),
        "local DPT spectra are dense line traces; stacked arbitrary-unit displays hide Y numeric labels",
    ),
    "PL": PlotPolicy(
        "PL",
        "line",
        "200",
        "none",
        True,
        True,
        False,
        True,
        False,
        "fit/integration only with current provenance",
        ("no automatic recombination conclusion", "no automatic defect-state assignment"),
        "emission/excitation spectra are arbitrary-unit line traces; offset overlays hide Y numeric labels",
    ),
    "TRPL": PlotPolicy(
        "TRPL",
        "semilog_decay",
        "200",
        "markers_optional_for_sparse_points",
        True,
        True,
        True,
        True,
        True,
        "decay fit only when fit parameters are supplied or calculated in current workflow",
        ("no automatic lifetime interpretation without fit provenance",),
        "TRPL decay scale is quantitative unless deliberately offset",
    ),
    "UV-vis DRS": PlotPolicy(
        "UV-vis DRS",
        "line",
        "200",
        "none",
        True,
        True,
        True,
        True,
        False,
        "Tauc guide only in Tauc-specific policy",
        ("no automatic band-gap confirmation",),
        "reflectance/absorbance/F(R) spectra are quantitative unless explicitly offset",
    ),
    "Tauc": PlotPolicy(
        "Tauc",
        "line+symbol",
        "202",
        "markers_required",
        True,
        True,
        True,
        True,
        True,
        "linear guide only with interval provenance",
        ("no automatic band-gap confirmation",),
        "Tauc intercept is quantitative, so X and Y numeric labels must be visible",
    ),
    "EIS": PlotPolicy(
        "EIS",
        "line+symbol",
        "202",
        "markers_preferred",
        True,
        True,
        True,
        True,
        True,
        "supplied fit curves only; no automatic circuit fit conclusion",
        ("no automatic equivalent-circuit interpretation",),
        "Nyquist plots require visible measured points and quantitative axes",
    ),
    "EIS Bode": PlotPolicy(
        "EIS Bode",
        "bode",
        "202",
        "markers_preferred",
        True,
        True,
        True,
        True,
        True,
        "right phase axis only when phase is plotted",
        ("no automatic equivalent-circuit interpretation",),
        "Bode plots use log-frequency with quantitative magnitude/phase axes",
    ),
    "photocurrent": PlotPolicy(
        "photocurrent",
        "line",
        "200",
        "none",
        True,
        True,
        True,
        True,
        False,
        "light-cycle markers only when timing evidence is present",
        ("no automatic carrier-separation conclusion",),
        "current-time data are quantitative and must keep Y numeric labels",
    ),
    "photocurrent_response": PlotPolicy(
        "photocurrent_response",
        "line",
        "200",
        "none",
        True,
        True,
        True,
        True,
        False,
        "light-cycle markers only when timing evidence is present",
        ("no automatic carrier-separation conclusion",),
        "photocurrent response data are quantitative and must keep Y numeric labels",
    ),
    "Mott-Schottky": PlotPolicy(
        "Mott-Schottky",
        "line+symbol",
        "202",
        "markers_preferred",
        True,
        True,
        True,
        True,
        True,
        "candidate linear guide only with fit interval provenance",
        ("no automatic CB/VB conversion", "no automatic band-edge conclusion"),
        "1/C^2-potential plots are quantitative and never hide Y numeric labels",
    ),
    "BET": PlotPolicy(
        "BET",
        "line+symbol",
        "202",
        "symbols_required_for_branches",
        True,
        True,
        True,
        True,
        False,
        "BET fit only when exported values or validated pyGAPS provenance exist",
        ("no automatic pore-structure conclusion",),
        "adsorption/desorption isotherms are quantitative line+symbol branch plots",
    ),
    "BET pore distribution": PlotPolicy(
        "BET pore distribution",
        "line+symbol",
        "202",
        "markers_optional",
        True,
        True,
        True,
        True,
        False,
        "none",
        ("no automatic pore-size conclusion",),
        "pore-size distributions use quantitative axes",
    ),
    "EPR": PlotPolicy(
        "EPR",
        "line",
        "200",
        "none",
        True,
        False,
        False,
        True,
        False,
        "peak-to-peak or g candidate only with provenance",
        ("no automatic radical assignment",),
        "EPR condition overlays are arbitrary-unit spectra; keep the Y axis title/line but hide Y ticks and numeric labels for clean offset comparisons",
    ),
    "EPR overlay": PlotPolicy(
        "EPR overlay",
        "line",
        "200",
        "direct_labels_preferred",
        True,
        False,
        False,
        True,
        False,
        "condition-group overlay only; baseline centering and vertical offsets must be recorded",
        ("no automatic radical assignment",),
        "EPR overlay outputs use direct curve labels and no Y-axis ticks or numeric labels for offset BC/CWO/BOBC comparisons",
    ),
    "XPS": PlotPolicy(
        "XPS",
        "line",
        "200",
        "none",
        True,
        True,
        False,
        True,
        True,
        "components/envelope/background only when fit columns are supplied",
        ("no automatic valence assignment", "no automatic species assignment", "no automatic mechanism claim"),
        "XPS spectra commonly use arbitrary-unit offset/baseline-shifted displays",
    ),
    "XPS fitted": PlotPolicy(
        "XPS fitted",
        "fitted_component_overlay",
        "200",
        "none",
        True,
        True,
        False,
        True,
        True,
        "raw/background/envelope/components/residual only from supplied fitted tables",
        ("no automatic valence assignment", "no automatic species assignment"),
        "fitted XPS overlays distinguish roles by line style and normally hide arbitrary Y numeric labels",
    ),
    "VBXPS": PlotPolicy(
        "VBXPS",
        "line",
        "200",
        "none",
        True,
        True,
        False,
        True,
        True,
        "leading-edge guide only with intercept provenance",
        ("no automatic VB position",),
        "VBXPS is an arbitrary-unit spectrum unless intercept analysis is supplied",
    ),
    "reaction_condition_screening": PlotPolicy(
        "reaction_condition_screening",
        "column",
        "203",
        "error_bars_when_available",
        True,
        True,
        True,
        True,
        False,
        "none",
        ("no automatic best-condition conclusion", "no automatic mechanism claim"),
        "discrete condition screening uses categorical bars with quantitative Y values",
    ),
    "cycling_test": PlotPolicy(
        "cycling_test",
        "line+symbol",
        "202",
        "markers_preferred",
        True,
        True,
        True,
        True,
        False,
        "none",
        ("no automatic stability mechanism claim",),
        "cycle-number trends use visible points and quantitative Y values",
    ),
    "radical_trapping": PlotPolicy(
        "radical_trapping",
        "column",
        "203",
        "error_bars_when_available",
        True,
        True,
        True,
        True,
        False,
        "none",
        ("no automatic radical mechanism claim",),
        "quenching comparisons are categorical quantitative plots",
    ),
    "calibration_curve": PlotPolicy(
        "calibration_curve",
        "calibration_scatter",
        "202",
        "markers_required",
        True,
        True,
        True,
        True,
        True,
        "fit raw standards in Origin; fitted line hidden unless requested",
        ("no calibration claim without raw standard points",),
        "calibration uses raw standard points and quantitative axes",
    ),
    "HPLC/LC exported data": PlotPolicy(
        "HPLC/LC exported data",
        "chromatogram",
        "200",
        "none",
        True,
        True,
        True,
        True,
        False,
        "peak markers only with supplied peak table",
        ("no automatic product identity", "no automatic conversion/selectivity without calibration"),
        "chromatograms use quantitative retention time and detector response",
    ),
    "HPLC/LC peak summary": PlotPolicy(
        "HPLC/LC peak summary",
        "lollipop",
        "202",
        "markers_required",
        True,
        True,
        True,
        True,
        False,
        "none",
        ("no automatic product identity",),
        "peak summaries compare quantitative area or height values",
    ),
    "SEM_image_panel": PlotPolicy(
        "SEM_image_panel",
        "image_panel",
        "200",
        "not_applicable",
        False,
        False,
        False,
        False,
        False,
        "none",
        ("no automatic morphology conclusion",),
        "microscopy panels use scale bars instead of graph axes",
    ),
    "TEM_image_panel": PlotPolicy(
        "TEM_image_panel",
        "image_panel",
        "200",
        "not_applicable",
        False,
        False,
        False,
        False,
        False,
        "none",
        ("no automatic lattice/plane conclusion",),
        "microscopy panels use scale bars instead of graph axes",
    ),
    "EDS_map": PlotPolicy(
        "EDS_map",
        "eds_map",
        "200",
        "not_applicable",
        False,
        False,
        False,
        False,
        False,
        "none",
        ("no automatic elemental quantification conclusion",),
        "EDS maps use image panels and element labels, not graph axes",
    ),
    "NMR exported spectrum": PlotPolicy(
        "NMR exported spectrum",
        "line",
        "200",
        "none",
        True,
        True,
        True,
        True,
        False,
        "peak labels only from supplied peaklist",
        ("no automatic structure assignment",),
        "exported NMR spectra are quantitative display axes unless offset stacked",
    ),
    "MS spectrum": PlotPolicy(
        "MS spectrum",
        "stick_spectrum",
        "200",
        "sticks_required",
        True,
        True,
        True,
        True,
        False,
        "none",
        ("no automatic product identity",),
        "centroid MS spectra are stick spectra with quantitative axes",
    ),
    "energy_level_diagram": PlotPolicy(
        "energy_level_diagram",
        "energy_level_schematic",
        "200",
        "not_applicable",
        False,
        False,
        False,
        False,
        False,
        "none",
        ("no automatic mechanism arrows",),
        "schematic energy diagrams show numeric ticks only when quantitative values are supplied",
    ),
}

_ALIASES = {
    "SEM": "SEM_image_panel",
    "TEM": "TEM_image_panel",
    "EDS": "EDS_map",
    "Valence Band XPS": "VBXPS",
    "reaction screening": "reaction_condition_screening",
    "photocurrent response": "photocurrent_response",
    "HPLC": "HPLC/LC exported data",
    "LC": "HPLC/LC exported data",
    "NMR": "NMR exported spectrum",
    "MS": "MS spectrum",
}


def get_plot_policy(data_type: str) -> PlotPolicy:
    key = _ALIASES.get(data_type, data_type)
    if key in _POLICIES:
        return _POLICIES[key]
    return PlotPolicy(
        data_type=data_type,
        plot_primitive="line",
        origin_plot_code="200",
        marker_policy="review_required",
        y_axis_visible=True,
        y_ticks_visible=True,
        y_tick_values_visible=True,
        x_tick_values_visible=True,
        allow_fit_overlay=False,
        fit_overlay_condition="review required for unclassified plot family",
        forbidden_claims=("no automatic scientific interpretation",),
        plot_policy_reason="unclassified data type; default to quantitative line plot with all tick values visible",
    )


def all_plot_policies() -> dict[str, PlotPolicy]:
    return dict(_POLICIES)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def validate_graph4_style_config(path: Path) -> Graph4FixedStyle:
    if not path.exists():
        return GRAPH4_FIXED_STYLE
    config = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    expected = {
        "line_width": GRAPH4_FIXED_STYLE.line_width,
        "axis_line_width": GRAPH4_FIXED_STYLE.axis_line_width,
        "axis_title_size": GRAPH4_FIXED_STYLE.axis_title_size,
        "x_tick_label_size": GRAPH4_FIXED_STYLE.x_tick_label_size,
        "y_tick_label_size": GRAPH4_FIXED_STYLE.y_tick_label_size,
        "legend_font_size": GRAPH4_FIXED_STYLE.legend_font_size,
        "annotation_font_size": GRAPH4_FIXED_STYLE.annotation_font_size,
    }
    for key, expected_value in expected.items():
        if key not in config:
            continue
        actual = float(config[key])
        if abs(actual - float(expected_value)) > 0.01:
            raise ValueError(f"Origin Graph4 contract requires {key} to be {expected_value}, got {config[key]}.")
    if "font_bold" in config and not _bool_value(config["font_bold"]):
        raise ValueError("Origin Graph4 contract requires font_bold to be true.")
    return GRAPH4_FIXED_STYLE
