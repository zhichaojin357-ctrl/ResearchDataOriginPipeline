"""Pure, route-specific Origin plot-style comparisons.

Topology and role selection remain explicit in each validator; only the
field comparison shared by those contracts is factored out.
"""
from __future__ import annotations

REVIEWED_TEMPLATE_VISIBLE_PLOTS = {
    "EIS": (3, 4, 5),
    "Mott-Schottky": (1, 2, 3),
}


def _style_field_mismatches(
    reference_style: dict[str, object],
    current_style: dict[str, object],
    fields: tuple[str, ...],
) -> list[str]:
    return [field for field in fields if reference_style.get(field) != current_style.get(field)]


def _validate_raman_reopened_plot_styles(
    reference_data: dict[str, object] | None,
    current_data: dict[str, object],
) -> dict[str, object]:
    """Audit Raman plot styles per layer, avoiding flattened layer-1 readback."""

    if not isinstance(reference_data, dict) or str(reference_data.get("status") or "") != "ready":
        return {
            "ok": False,
            "status": "blocked",
            "message": "Reviewed Raman per-layer data snapshot is unavailable.",
        }
    reference_plots = {
        (int(plot.get("layer_index") or 0), int(plot.get("plot_index") or 0)): dict(plot)
        for plot in reference_data.get("plots", [])
        if isinstance(plot, dict)
    }
    current_plots = {
        (int(plot.get("layer_index") or 0), int(plot.get("plot_index") or 0)): dict(plot)
        for plot in current_data.get("plots", [])
        if isinstance(plot, dict)
    }
    reasons: list[str] = []
    expected_keys = {(1, 1), (1, 2), (2, 1)}
    if set(reference_plots) != expected_keys:
        reasons.append("reviewed Raman snapshot does not contain the expected 2-layer/3-plot structure")
    if set(current_plots) != expected_keys:
        reasons.append("reopened Raman graph does not contain the expected 2-layer/3-plot structure")
    style_fields = (
        "color",
        "line_color",
        "line_width_origin_units",
        "line_width_pt",
        "line_style",
        "symbol_shape",
        "symbol_size",
    )
    compared: list[dict[str, object]] = []
    for key in sorted(expected_keys):
        reference_plot = reference_plots.get(key)
        current_plot = current_plots.get(key)
        if reference_plot is None or current_plot is None:
            continue
        reference_style = dict(reference_plot.get("style") or {})
        current_style = dict(current_plot.get("style") or {})
        mismatches = _style_field_mismatches(reference_style, current_style, style_fields)
        if mismatches:
            reasons.append(
                f"Raman layer {key[0]} plot {key[1]} style differs: {', '.join(mismatches)}"
            )
        compared.append(
            {
                "layer_index": key[0],
                "plot_index": key[1],
                "reference_style": {
                    field: reference_style.get(field) for field in style_fields
                },
                "current_style": {
                    field: current_style.get(field) for field in style_fields
                },
                "matches": not mismatches,
            }
        )
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            "Reopened Raman graph preserves all reviewed per-layer curve styles."
            if not reasons
            else "; ".join(reasons)
        ),
        "plots": compared,
        "reasons": reasons,
    }


def _validate_xps_in_situ_reopened_plot_styles(
    reference_data: dict[str, object] | None,
    current_data: dict[str, object],
) -> dict[str, object]:
    """Audit all native XPS lines, fills, and zero-width helper curves after reopen."""

    if not isinstance(reference_data, dict) or str(reference_data.get("status") or "") != "ready":
        return {
            "ok": False,
            "status": "blocked",
            "message": "Reviewed XPS in-situ per-plot data snapshot is unavailable.",
        }
    reference_plots = {
        (int(plot.get("layer_index") or 0), int(plot.get("plot_index") or 0)): dict(plot)
        for plot in reference_data.get("plots", [])
        if isinstance(plot, dict)
    }
    current_plots = {
        (int(plot.get("layer_index") or 0), int(plot.get("plot_index") or 0)): dict(plot)
        for plot in current_data.get("plots", [])
        if isinstance(plot, dict)
    }
    expected_keys = {(1, index) for index in range(1, 22)}
    reasons: list[str] = []
    if set(reference_plots) != expected_keys:
        reasons.append("reviewed XPS in-situ snapshot does not contain the expected 1-layer/21-plot structure")
    if set(current_plots) != expected_keys:
        reasons.append("reopened XPS in-situ graph does not contain the expected 1-layer/21-plot structure")
    style_fields = (
        "color",
        "line_color",
        "line_width_origin_units",
        "line_width_pt",
        "line_style",
        "symbol_shape",
        "symbol_size",
        "fill_area",
        "fill_color",
        "border_color",
        "border_width",
    )
    compared: list[dict[str, object]] = []
    for key in sorted(expected_keys):
        reference_plot = reference_plots.get(key)
        current_plot = current_plots.get(key)
        if reference_plot is None or current_plot is None:
            continue
        reference_style = dict(reference_plot.get("style") or {})
        current_style = dict(current_plot.get("style") or {})
        mismatches = _style_field_mismatches(reference_style, current_style, style_fields)
        if mismatches:
            reasons.append(
                f"XPS in-situ plot {key[1]} style differs: {', '.join(mismatches)}"
            )
        compared.append(
            {
                "layer_index": key[0],
                "plot_index": key[1],
                "reference_style": {
                    field: reference_style.get(field) for field in style_fields
                },
                "current_style": {
                    field: current_style.get(field) for field in style_fields
                },
                "matches": not mismatches,
            }
        )
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            "Reopened XPS in-situ graph preserves all 21 reviewed native line/fill/helper styles."
            if not reasons
            else "; ".join(reasons)
        ),
        "plots": compared,
        "reasons": reasons,
    }


def _validate_xps_non_in_situ_reopened_plot_styles(
    reference_data: dict[str, object] | None,
    current_data: dict[str, object],
) -> dict[str, object]:
    """Audit the reviewed nine-role native XPS style cycle after save/reopen."""

    if not isinstance(reference_data, dict) or str(reference_data.get("status") or "") != "ready":
        return {
            "ok": False,
            "status": "blocked",
            "message": "Reviewed XPS non-in-situ per-plot data snapshot is unavailable.",
        }
    reference_plots = sorted(
        [dict(value) for value in reference_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    current_plots = sorted(
        [dict(value) for value in current_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    reasons: list[str] = []
    if len(reference_plots) != 18:
        reasons.append("reviewed XPS non-in-situ snapshot does not contain 18 plots")
    if len(current_plots) != 18 or any(
        int(plot.get("layer_index") or 0) != 1
        or int(plot.get("plot_index") or 0) != plot_index
        for plot_index, plot in enumerate(current_plots, start=1)
    ):
        reasons.append("reopened XPS non-in-situ graph does not contain the expected one-layer 18-plot sequence")
    style_fields = (
        "color",
        "line_color",
        "line_width_origin_units",
        "line_width_pt",
        "line_style",
        "symbol_shape",
        "symbol_size",
        "fill_enabled",
        "fill_mode",
        "fill_above_color",
        "fill_below_color",
        "fill_above_pattern_color",
        "fill_below_pattern_color",
        "fill_above_pattern",
        "fill_below_pattern",
        "fill_transparency",
    )
    compared: list[dict[str, object]] = []
    if len(reference_plots) == 18 and len(current_plots) == 18:
        expected_native_formats = _xps_non_in_situ_adaptive_plot_format_contracts(18)
        for plot_index, (reference_plot, current_plot) in enumerate(
            zip(reference_plots, current_plots),
            start=1,
        ):
            reference_style = dict(reference_plot.get("style") or {})
            current_style = dict(current_plot.get("style") or {})
            fields = tuple(field for field in style_fields if field in reference_style)
            mismatches = [
                field
                for field in fields
                if reference_style.get(field) != current_style.get(field)
            ]
            expected_native = expected_native_formats[plot_index - 1]
            mismatches.extend(
                field
                for field in (
                    "fill_enabled",
                    "fill_mode",
                    "fill_above_color",
                    "fill_below_color",
                )
                if current_style.get(field) != float(expected_native[field])
                and field not in mismatches
            )
            if mismatches:
                reasons.append(
                    f"XPS non-in-situ plot {plot_index} style differs: {', '.join(mismatches)}"
                )
            compared.append(
                {
                    "plot_index": plot_index,
                    "role_index": (plot_index - 1) % 9 + 1,
                    "matches": not mismatches,
                    "mismatches": mismatches,
                }
            )
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            "Reopened XPS non-in-situ graph preserves the reviewed native nine-role line/fill style cycle."
            if not reasons
            else "; ".join(reasons)
        ),
        "plots": compared,
        "reasons": reasons,
    }


def _validate_adaptive_xps_in_situ_reopened_plot_styles(
    reference_data: dict[str, object],
    current_data: dict[str, object],
    *,
    expected_plot_count: int,
) -> dict[str, object]:
    """Validate each adaptive XPS plot against its seven-role native style cycle."""

    if (
        not isinstance(reference_data, dict)
        or str(reference_data.get("status") or "") != "ready"
        or expected_plot_count <= 0
        or expected_plot_count % 7 != 0
    ):
        return {
            "ok": False,
            "status": "blocked",
            "message": "Adaptive XPS in-situ style validation lacks a complete reviewed role cycle.",
        }
    reference_plots = sorted(
        [dict(value) for value in reference_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    current_plots = sorted(
        [dict(value) for value in current_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    reasons: list[str] = []
    if len(reference_plots) != 21:
        reasons.append("reviewed XPS in-situ snapshot does not contain 21 plots")
    if len(current_plots) != expected_plot_count or any(
        int(plot.get("layer_index") or 0) != 1
        or int(plot.get("plot_index") or 0) != plot_index
        for plot_index, plot in enumerate(current_plots, start=1)
    ):
        reasons.append(
            "adaptive XPS in-situ reopened graph does not contain the expected one-layer plot sequence"
        )
    style_fields = (
        "color",
        "line_color",
        "line_width_origin_units",
        "line_width_pt",
        "line_style",
        "symbol_shape",
        "symbol_size",
        "fill_area",
        "fill_color",
        "border_color",
        "border_width",
    )
    compared: list[dict[str, object]] = []
    if len(reference_plots) == 21 and len(current_plots) == expected_plot_count:
        for plot_index, current_plot in enumerate(current_plots, start=1):
            reference_plot = reference_plots[(plot_index - 1) % 7]
            reference_style = dict(reference_plot.get("style") or {})
            current_style = dict(current_plot.get("style") or {})
            mismatches = _style_field_mismatches(reference_style, current_style, style_fields)
            if mismatches:
                reasons.append(
                    f"adaptive XPS plot {plot_index} role style differs: {', '.join(mismatches)}"
                )
            compared.append(
                {
                    "plot_index": plot_index,
                    "role_index": (plot_index - 1) % 7 + 1,
                    "matches": not mismatches,
                    "mismatches": mismatches,
                }
            )
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            "Adaptive XPS in-situ graph preserves the reviewed seven-role native style cycle."
            if not reasons
            else "; ".join(reasons)
        ),
        "expected_plot_count": expected_plot_count,
        "current_plot_count": len(current_plots),
        "plots": compared,
        "reasons": reasons,
    }


def _validate_adaptive_xps_non_in_situ_reopened_plot_styles(
    reference_data: dict[str, object],
    current_data: dict[str, object],
    *,
    expected_plot_count: int,
) -> dict[str, object]:
    """Validate every adaptive non-in-situ XPS plot against its nine-role cycle."""

    if (
        not isinstance(reference_data, dict)
        or str(reference_data.get("status") or "") != "ready"
        or expected_plot_count <= 0
        or expected_plot_count % 9 != 0
    ):
        return {
            "ok": False,
            "status": "blocked",
            "message": "Adaptive XPS non-in-situ style validation lacks a complete reviewed role cycle.",
        }
    reference_plots = sorted(
        [dict(value) for value in reference_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    current_plots = sorted(
        [dict(value) for value in current_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    reasons: list[str] = []
    if len(reference_plots) != 18:
        reasons.append("reviewed XPS non-in-situ snapshot does not contain 18 plots")
    if len(current_plots) != expected_plot_count or any(
        int(plot.get("layer_index") or 0) != 1
        or int(plot.get("plot_index") or 0) != plot_index
        for plot_index, plot in enumerate(current_plots, start=1)
    ):
        reasons.append(
            "adaptive XPS non-in-situ reopened graph does not contain the expected one-layer plot sequence"
        )
    style_fields = (
        "color",
        "line_color",
        "line_width_origin_units",
        "line_width_pt",
        "line_style",
        "symbol_shape",
        "symbol_size",
        "fill_enabled",
        "fill_mode",
        "fill_above_color",
        "fill_below_color",
        "fill_above_pattern_color",
        "fill_below_pattern_color",
        "fill_above_pattern",
        "fill_below_pattern",
        "fill_transparency",
    )
    compared: list[dict[str, object]] = []
    if len(reference_plots) == 18 and len(current_plots) == expected_plot_count:
        expected_native_formats = _xps_non_in_situ_adaptive_plot_format_contracts(
            expected_plot_count
        )
        for plot_index, current_plot in enumerate(current_plots, start=1):
            reference_plot = reference_plots[(plot_index - 1) % 9]
            reference_style = dict(reference_plot.get("style") or {})
            current_style = dict(current_plot.get("style") or {})
            fields = tuple(field for field in style_fields if field in reference_style)
            mismatches = [
                field
                for field in fields
                if reference_style.get(field) != current_style.get(field)
            ]
            expected_native = expected_native_formats[plot_index - 1]
            mismatches.extend(
                field
                for field in (
                    "fill_enabled",
                    "fill_mode",
                    "fill_above_color",
                    "fill_below_color",
                )
                if current_style.get(field) != float(expected_native[field])
                and field not in mismatches
            )
            if mismatches:
                reasons.append(
                    f"adaptive XPS non-in-situ plot {plot_index} role style differs: {', '.join(mismatches)}"
                )
            compared.append(
                {
                    "plot_index": plot_index,
                    "role_index": (plot_index - 1) % 9 + 1,
                    "matches": not mismatches,
                    "mismatches": mismatches,
                }
            )
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            "Adaptive XPS non-in-situ graph preserves the reviewed nine-role native style cycle."
            if not reasons
            else "; ".join(reasons)
        ),
        "expected_plot_count": expected_plot_count,
        "current_plot_count": len(current_plots),
        "plots": compared,
        "reasons": reasons,
    }


def _validate_adaptive_reopened_plot_style_cycle(
    reference_data: dict[str, object],
    current_data: dict[str, object],
    *,
    product_key: str,
    reference_plot_count: int,
    expected_plot_count: int,
) -> dict[str, object]:
    """Validate a reviewed native plot-style cycle after save/reopen."""

    reference_plots = sorted(
        [dict(value) for value in reference_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    current_plots = sorted(
        [dict(value) for value in current_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        ),
    )
    reasons: list[str] = []
    if (
        str(reference_data.get("status") or "") != "ready"
        or len(reference_plots) != reference_plot_count
    ):
        reasons.append(
            f"reviewed {product_key} snapshot does not contain the complete "
            f"{reference_plot_count}-plot style cycle"
        )
    if expected_plot_count <= 0 or len(current_plots) != expected_plot_count or any(
        int(plot.get("layer_index") or 0) != 1
        or int(plot.get("plot_index") or 0) != plot_index
        for plot_index, plot in enumerate(current_plots, start=1)
    ):
        reasons.append(
            f"adaptive {product_key} graph does not contain the expected one-layer current plot sequence"
        )
    style_fields = (
        "color",
        "line_color",
        "line_width_origin_units",
        "line_width_pt",
        "line_style",
        "symbol_shape",
        "symbol_size",
    )
    compared: list[dict[str, object]] = []
    if (
        len(reference_plots) == reference_plot_count
        and len(current_plots) == expected_plot_count
    ):
        for plot_index, current_plot in enumerate(current_plots, start=1):
            reference_plot = reference_plots[
                (plot_index - 1) % reference_plot_count
            ]
            reference_style = dict(reference_plot.get("style") or {})
            current_style = dict(current_plot.get("style") or {})
            mismatches = _style_field_mismatches(reference_style, current_style, style_fields)
            if mismatches:
                reasons.append(
                    f"adaptive {product_key} plot {plot_index} style differs: "
                    f"{', '.join(mismatches)}"
                )
            compared.append(
                {
                    "plot_index": plot_index,
                    "style_cycle_index": (plot_index - 1) % reference_plot_count + 1,
                    "matches": not mismatches,
                    "mismatches": mismatches,
                    "expected_style": {
                        field: reference_style.get(field) for field in style_fields
                    },
                    "current_style": {
                        field: current_style.get(field) for field in style_fields
                    },
                }
            )
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            f"Adaptive {product_key} graph preserves the reviewed native plot-style cycle."
            if not reasons
            else "; ".join(reasons)
        ),
        "expected_plot_count": expected_plot_count,
        "current_plot_count": len(current_plots),
        "plots": compared,
        "reasons": reasons,
    }


def _validate_adaptive_epr_reopened_plot_styles(
    reference_data: dict[str, object],
    current_data: dict[str, object],
    *,
    expected_plot_count: int,
) -> dict[str, object]:
    return _validate_adaptive_reopened_plot_style_cycle(
        reference_data,
        current_data,
        product_key="EPR",
        reference_plot_count=3,
        expected_plot_count=expected_plot_count,
    )


def _validate_adaptive_eis_reopened_plot_styles(
    reference_data: dict[str, object],
    current_data: dict[str, object],
    *,
    expected_plot_count: int,
) -> dict[str, object]:
    return _validate_adaptive_reopened_plot_style_cycle(
        _adaptive_eis_style_cycle_snapshot(reference_data),
        current_data,
        product_key="EIS",
        reference_plot_count=len(REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]),
        expected_plot_count=expected_plot_count,
    )


def _adaptive_eis_style_cycle_snapshot(
    data_snapshot: dict[str, object],
) -> dict[str, object]:
    """Return the three reviewed visible EIS marker styles in display order."""
    raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
    plots = [dict(value) for value in raw_plots if isinstance(value, dict)] if isinstance(raw_plots, list) else []
    by_index = {
        int(plot.get("plot_index") or 0): plot
        for plot in plots
        if int(plot.get("layer_index") or 0) == 1
    }
    visible = [
        by_index[index]
        for index in REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]
        if index in by_index
    ]
    if len(visible) != len(REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]):
        return {
            **dict(data_snapshot or {}),
            "status": "invalid",
            "plot_count": 0,
            "plots": [],
        }
    return {
        **data_snapshot,
        "status": "ready",
        "plot_count": len(visible),
        "plots": visible,
    }


def _xps_non_in_situ_adaptive_plot_format_contracts(
    plot_count: int,
) -> list[dict[str, object]]:
    role_cycle = (
        (1, 9, 30972633, 30972633),
        (0, 0, 1, 2),
        (0, 0, 1, 2),
        (1, 9, 25540850, 25540850),
        (0, 0, 1, 2),
        (0, 0, 1, 2),
        (0, 0, 1, 2),
        (0, 0, 1, 2),
        (0, 0, 1, 2),
    )
    return [
        {
            "layer_index": 1,
            "plot_index": plot_index,
            "fill_enabled": role[0],
            "fill_mode": role[1],
            "fill_above_color": role[2],
            "fill_below_color": role[3],
        }
        for plot_index in range(1, plot_count + 1)
        for role in (role_cycle[(plot_index - 1) % len(role_cycle)],)
    ]
