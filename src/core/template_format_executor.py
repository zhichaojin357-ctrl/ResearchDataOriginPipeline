from __future__ import annotations

import csv
import heapq
import json
import math
import re
import shutil
import tempfile
import traceback
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import median

from src.core.file_utils import file_sha256
from src.core.template_inputs import (
    current_template_inputs,
    invalidate_processed_table,
    load_template_binding_contracts,
    template_input_scope,
)
from src.core.template_style_validation import (
    REVIEWED_TEMPLATE_VISIBLE_PLOTS,
    _adaptive_eis_style_cycle_snapshot,
    _validate_adaptive_eis_reopened_plot_styles,
    _validate_adaptive_epr_reopened_plot_styles,
    _validate_adaptive_reopened_plot_style_cycle,
    _validate_adaptive_xps_in_situ_reopened_plot_styles,
    _validate_adaptive_xps_non_in_situ_reopened_plot_styles,
    _validate_raman_reopened_plot_styles,
    _validate_xps_in_situ_reopened_plot_styles,
    _validate_xps_non_in_situ_reopened_plot_styles,
    _xps_non_in_situ_adaptive_plot_format_contracts,
)
from src.core.template_numeric import (
    _finite_float,
    _finite_numeric_value,
    _linear_fit,
    _mott_schottky_candidate_guides,
    _padded_axis_bounds,
    _paired_numeric_row_bounds,
    _photocurrent_axis_series_match,
    _photocurrent_reference_xy_series,
    _photocurrent_xy_series,
    _shared_x_contiguous_y_series,
    _shared_x_intercept_fit,
    _validate_verified_current_data,
)
from src.core.origin_style_assets import (
    compare_graph_data_snapshots,
    read_graph_data_snapshot,
)
from src.core.template_product_common import (
    ProductContext,
    XPS_IN_SITU_REVIEWED_VERTICAL_OFFSETS,
    _product_output_path,
)
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.origin_runtime import (
    cleanup_origin_runtime_directory as _cleanup_origin_runtime_directory,
)
from src.core.origin_runtime import copy_runtime_artifact as _copy_runtime_artifact
from src.core.origin_runtime import neutral_origin_runtime_root as _neutral_origin_runtime_root
from src.core.template_product_builder import (
    TemplateProductBuilderOptions,
    _csv_bounds_for_columns,
    _export_native_tif_with_physical_validation,
    _prepare_template_epr_origin_processed_workbook,
    _style_snapshot_axis_title_bold_required,
    _strict_style_readback,
    _template_xps_sample_display_label,
    _xps_peak_annotations_from_processed_data,
    is_template_xrd_reference_stick_header,
    run_template_product_builder_all_types,
    template_plot_type_for_header,
)
from src.origin.conformance import compare_style_snapshots
from src.origin.embedded_template_snapshots import embedded_template_snapshot
from src.origin.operations import avoid_native_legend_overlap, connect_origin, quote_labtalk, update_native_legend
from src.origin.style_registry import (
    origin_style_asset_read_scope,
    origin_style_file_sha256,
    read_origin_style_json,
    resolve_origin_adaptive_style_asset,
    resolve_origin_runtime_style_asset,
)
from src.origin.style_mimic import (
    _origin_color_value_for_labtalk,
    _origin_plot_color_for_labtalk,
    apply_style_snapshot,
    extract_style_snapshot,
    read_graph_style_snapshot,
)
from src.origin.template_binding import (
    validate_template_source_bindings,
)
from src.origin.template_format import (
    build_template_dataset_updates,
    build_template_format_plan,
    parse_origin_dataset_reference,
)
from src.origin.text_format import origin_bold_text
from src.origin.user_style import ResolvedPlotStyle, apply_resolved_style_overrides
from src.processors.base import safe_name


TEMPLATE_FORMAT_SCOPE = "template_format_products"
TEMPLATE_FORMAT_COMMAND = "template-format-products"
FINAL_TEMPLATE_STYLE_OVERRIDE = {
    "font_family": "Arial",
    "line_width_pt": 3.0,
    "axis_title_font_size": 36,
    "font_bold": True,
    "legend_no_frame": True,
}
XRD_STANDARD_CARD_SAMPLE_COLOR_SEQUENCE = (16814848, 33518174, 18128807, 16814848)
XRD_STANDARD_CARD_ADAPTIVE_SAMPLE_COLORS = (16814848, 33518174, 18128807, 23709421)
XRD_STANDARD_CARD_ADAPTIVE_CARD_COLOR = 22106449
XRD_STANDARD_CARD_ADAPTIVE_STICK_COLOR = 11
XRD_STANDARD_CARD_STICK_COLOR_EXPR = "color(181,91,0)"
XRD_STANDARD_CARD_STICK_WIDTH = 1500
XRD_STANDARD_CARD_STICK_WIDTH_PT = 3
VERIFIED_GRAPH_TEMPLATE_PRODUCTS = {
    "BET",
    "EIS",
    "EPR",
    "Raman",
    "PL",
    "photocurrent",
    "FTIR",
    "Mott-Schottky",
    "UV-vis DRS",
    "Tauc",
    "XPS_in_situ",
    "XPS_non_in_situ",
}

VERIFIED_FTIR_SERIES_LABELS = ("BiOBr0.5Cl0.5", "CuWO4", "BiCu-10")
VERIFIED_FTIR_RAW_TO_PLOTTED_OFFSETS = (
    0.6992644978783592,
    0.48749646393210766,
    -0.174144271570014,
)
VERIFIED_FTIR_LAST_CURVE_TRANSLATE_ANNOTATIONS = (
    0.69926449787836,
    0.48749646393211,
    -0.62347949080622,
)
VERIFIED_PHOTOCURRENT_DESTINATION_PAIRS = ((9, 10), (13, 14), (17, 18))
VERIFIED_RAMAN_DESTINATION_PAIRS = ((1, 2), (3, 4), (5, 6))
VERIFIED_MOTT_DESTINATION_PAIRS = ((5, 4), (5, 6), (7, 8), (9, 10), (11, 12))
VERIFIED_XPS_IN_SITU_BOOKS = ("Book2", "Book3", "Book4")
VERIFIED_XPS_IN_SITU_DESTINATION_Y_COLUMNS = (2, 3, 5, 4, 5, 5, 6)
VERIFIED_XPS_IN_SITU_ROLE_SUFFIXES = (
    "_measured",
    "_component_1",
    "_component_1_fill_baseline",
    "_component_2",
    "_component_2_fill_baseline",
    "_background",
    "_envelope",
)
VERIFIED_XPS_NON_IN_SITU_ROLE_SUFFIXES = (
    "_component_1_fill_upper",
    "_component_1_fill_baseline",
    "_component_1_line",
    "_component_2_fill_upper",
    "_component_2_fill_baseline",
    "_component_2_line",
    "_measured",
    "_background",
    "_envelope",
)
VERIFIED_XPS_NON_IN_SITU_DESTINATION_Y_COLUMNS = tuple(range(2, 20))
VERIFIED_XPS_NON_IN_SITU_VERTICAL_OFFSETS = (0.0, 1.35)
VERIFIED_PHOTOCURRENT_X_TITLE = "Time (s)"
VERIFIED_BET_X_TITLE = "Relative Pressure (P/Po)"
VERIFIED_BET_Y_TITLE = "Quantity Adsorbed (cm3/g STP)"
TAUC_REFERENCE_GUIDE_OBJECTS = (
    "Line",
    "Line1",
    "Line2",
    "Line3",
    "Line4",
    "Line5",
    "Arrow",
    "Arrow1",
    "Arrow2",
    "Arrow3",
    "Text",
    "Text1",
)
TAUC_REFERENCE_INTERCEPT_LABELS = ("2.28", "2.94")
BET_ADAPTIVE_Y_TITLE_OBJECT = "RDOPBETYL"
# The reviewed Graph5 Y title starts at 391/78. Adaptive numeric tick labels
# are wider than the reference integer labels, so the stable text replacement
# is shifted left just enough to preserve a visible gap without moving the
# page, layer, axes, or changing any font size.
BET_ADAPTIVE_Y_TITLE_LEFT = 300
BET_ADAPTIVE_Y_TITLE_TOP = 78


@dataclass(frozen=True)
class TemplateFormatExecutorOptions:
    pairing_path: Path
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    f_drive_template_root: Path | None = None
    xps_reference_template_root: Path | None = None
    xps_non_in_situ_template_root: Path | None = None
    user_style_path: Path | None = None
    asset_only: bool = False
    exemplar_driven: bool = False
    compact_output: bool = False
    only_type: str | None = None
    style_replay_report: Path | None = None
    origin_style_mode: str = "auto"


def build_template_product_builder_options(options: TemplateFormatExecutorOptions) -> TemplateProductBuilderOptions:
    return TemplateProductBuilderOptions(
        pairing_path=options.pairing_path,
        output_root=options.output_root,
        with_origin=options.with_origin,
        timestamp=options.timestamp,
        f_drive_template_root=None if options.asset_only else options.f_drive_template_root,
        xps_reference_template_root=None if options.asset_only else options.xps_reference_template_root,
        xps_non_in_situ_template_root=None if options.asset_only else options.xps_non_in_situ_template_root,
        user_style_path=options.user_style_path,
        run_scope=TEMPLATE_FORMAT_SCOPE,
        command_name=TEMPLATE_FORMAT_COMMAND,
        product_slug_version="template_format",
        global_style_override={} if options.exemplar_driven else FINAL_TEMPLATE_STYLE_OVERRIDE,
        eis_strict_semicircle_branch=True,
        xps_reference_templates_for_all_xps=True,
        xps_templates_from_reference_only=True,
        xps_smooth_gradient_fill=True,
        cleanup_empty_run_layout_dirs=True,
        project_style_asset_fallback=True,
        prefer_project_style_assets=not options.exemplar_driven,
        external_reference_preview_comparison=not options.exemplar_driven and not options.asset_only,
        asset_only=options.asset_only,
        exemplar_driven=options.exemplar_driven,
        compact_output=options.compact_output,
        only_type=options.only_type,
        style_replay_report=options.style_replay_report,
        origin_style_mode=options.origin_style_mode,
    )


def run_template_format_executor(project_root: Path, options: TemplateFormatExecutorOptions) -> dict[str, object]:
    if options.asset_only and options.exemplar_driven:
        raise ValueError("--asset-only and --exemplar-driven are mutually exclusive")
    _normalize_origin_style_mode(options.origin_style_mode)
    options = _with_default_xps_non_in_situ_template_root(project_root, options)
    with origin_style_asset_read_scope():
        result = run_template_product_builder_all_types(
            project_root,
            build_template_product_builder_options(options),
            origin_exporter=lambda product, style: export_template_base_product_with_origin(
                product,
                style,
                project_root=project_root,
                prefer_project_style_asset=not options.exemplar_driven,
                preserve_exemplar_style=options.exemplar_driven,
                asset_only=options.asset_only,
                origin_style_mode=options.origin_style_mode,
            ),
        )
    _write_template_format_docs(project_root, Path(str(result["run_root"])), result)
    summary = dict(result.get("summary", {}))
    summary["success_count"] = int(summary.get("accepted_count", 0))
    result["summary"] = summary
    return result


def _with_default_xps_non_in_situ_template_root(
    project_root: Path,
    options: TemplateFormatExecutorOptions,
) -> TemplateFormatExecutorOptions:
    if options.asset_only:
        return options
    if options.xps_non_in_situ_template_root is not None:
        return options
    if options.f_drive_template_root is None and options.xps_reference_template_root is None:
        return options
    default_root = (
        project_root.resolve().parent
        / "26.6.3\u7ec4\u4f1a\u6570\u636e"
        / "\u7ed3\u679c\u6c47\u603b"
        / "XPS"
        / "xps_heterojunction_stacked"
        / "origin_projects"
    )
    if default_root.exists():
        return replace(options, xps_non_in_situ_template_root=default_root)
    return options


def _normalize_origin_style_mode(value: object) -> str:
    mode = str(value or "auto").strip().casefold()
    if mode not in {"auto", "otpu", "oth-json"}:
        raise ValueError(
            "origin_style_mode must be one of: auto, otpu, oth-json"
        )
    return mode


def _style_asset_display_path(product: ProductContext, path: object) -> str:
    if path is None:
        return ""
    text = str(path).strip()
    if not text:
        return ""
    return _product_output_path(product.type_root.parent, Path(text))


def _style_execution_decision(
    product: ProductContext,
    *,
    requested_mode: str,
    selected_mode: str,
    reason_code: str,
    message: str,
    current_series_count: int,
    contract_series_count: int,
    asset: object | None,
    ok: bool = True,
    fixed_binding_match: bool = False,
    candidate_assets_allowed: bool = False,
) -> dict[str, object]:
    runtime_kind = str(getattr(asset, "runtime_asset_kind", "") or "")
    selected_path = (
        getattr(asset, "runtime_asset_path", None)
        if runtime_kind == "otpu"
        else getattr(asset, "format_theme_path", None)
    )
    return {
        "ok": ok,
        "requested_mode": requested_mode,
        "selected_mode": selected_mode,
        "style_execution_mode": (
            "exact_contract_otpu"
            if selected_mode == "otpu"
            else (
                "variable_structure_oth_json"
                if selected_mode == "oth-json"
                else "existing_template_resolution"
            )
        ),
        "reason_code": reason_code,
        "message": message,
        "current_series_count": current_series_count,
        "contract_series_count": contract_series_count,
        "series_count_matches_contract": (
            contract_series_count > 0
            and current_series_count == contract_series_count
        ),
        "selected_asset_kind": runtime_kind,
        "selected_asset_path": _style_asset_display_path(product, selected_path),
        "selected_style_snapshot_path": _style_asset_display_path(
            product,
            getattr(asset, "style_snapshot_path", None),
        ),
        "selected_data_snapshot_path": _style_asset_display_path(
            product,
            getattr(asset, "data_snapshot_path", None),
        ),
        "automatic_error_fallback": False,
        "otpu_one_to_one_allowed": bool(
            selected_mode == "otpu" and fixed_binding_match
        ),
        "fixed_binding_match": bool(fixed_binding_match),
        "candidate_assets_allowed": bool(candidate_assets_allowed),
        "adaptive_series_cardinality": bool(
            selected_mode == "oth-json"
            and contract_series_count > 0
            and current_series_count != contract_series_count
        ),
    }


def _style_execution_metadata(decision: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(decision, dict):
        return {}
    return {
        "style_execution_mode": decision.get("style_execution_mode", ""),
        "style_execution_reason_code": decision.get("reason_code", ""),
        "origin_style_mode_requested": decision.get("requested_mode", "auto"),
        "current_series_count": decision.get("current_series_count", 0),
        "contract_series_count": decision.get("contract_series_count", 0),
        "selected_style_asset_kind": decision.get("selected_asset_kind", ""),
        "selected_style_asset_path": decision.get("selected_asset_path", ""),
        "selected_style_snapshot_path": decision.get(
            "selected_style_snapshot_path", ""
        ),
        "selected_data_snapshot_path": decision.get(
            "selected_data_snapshot_path", ""
        ),
        "automatic_error_fallback": False,
        "otpu_one_to_one_allowed": bool(
            decision.get("otpu_one_to_one_allowed")
        ),
        "adaptive_series_cardinality": bool(
            decision.get("adaptive_series_cardinality")
        ),
    }


def _attach_style_execution_decision(
    result: dict[str, object],
    decision: dict[str, object] | None,
) -> dict[str, object]:
    if not isinstance(decision, dict):
        return result
    payload = dict(result)
    payload["origin_style_decision"] = dict(decision)
    processing = (
        dict(payload.get("origin_processing", {}))
        if isinstance(payload.get("origin_processing"), dict)
        else {}
    )
    processing.update(_style_execution_metadata(decision))
    payload["origin_processing"] = processing
    return payload


def _saved_theme_reference_policy(
    style_asset: object | None,
    decision: dict[str, object] | None,
    *,
    asset_only: bool,
) -> tuple[Path | None, str, bool]:
    if str((decision or {}).get("selected_mode") or "") == "oth-json":
        return None, "", False
    return (
        getattr(style_asset, "template_opju_path", None),
        str(getattr(style_asset, "graph_page", "") or ""),
        bool(asset_only),
    )


def _binding_contract_for_asset(
    product_key: str,
    asset: object | None,
) -> tuple[object | None, str]:
    contract_path = getattr(asset, "binding_contract_path", None)
    if contract_path is None:
        return None, "binding contract path is missing"
    try:
        contracts = load_template_binding_contracts(contract_path)
    except (OSError, ValueError) as exc:
        return None, str(exc)
    key = (
        str(product_key)
        .strip()
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )
    contract = contracts.get(key)
    if contract is None:
        return None, f"binding contract does not contain {product_key}"
    if not bool(getattr(contract, "ready", False)):
        return None, str(getattr(contract, "reason", "") or "binding contract is not ready")
    return contract, ""


def _adaptive_asset_complete(asset: object | None) -> tuple[bool, str]:
    if asset is None:
        return False, "adaptive OTH+JSON asset is unavailable"
    if str(getattr(asset, "runtime_asset_kind", "") or "") != "oth_json":
        return False, "adaptive style resolver did not return runtime_asset_kind=oth_json"
    required = {
        "format_theme": getattr(asset, "format_theme_path", None),
        "style_snapshot": getattr(asset, "style_snapshot_path", None),
        "data_snapshot": getattr(asset, "data_snapshot_path", None),
    }
    missing = [
        name
        for name, value in required.items()
        if value is None or not Path(value).is_file()
    ]
    if missing:
        return False, "adaptive OTH+JSON asset is incomplete: " + ", ".join(missing)
    return True, ""


def _strict_adaptive_source_validation(
    contract: object,
    headers: list[str],
    rows: list[list[object]],
    source_pairs: list[tuple[int, int]],
) -> dict[str, object]:
    schema = dict(getattr(contract, "source_schema", {}) or {})
    layout = str(schema.get("layout") or "")
    failures: list[str] = []
    if not source_pairs:
        failures.append("processed CSV has no strictly recognized plot pairs")
    if layout == "paired_xy_columns":
        x_suffix = str(schema.get("x_header_suffix") or "")
        y_suffix = str(schema.get("y_header_suffix") or "")
        if not x_suffix or not y_suffix:
            failures.append("paired-X/Y contract lacks semantic header suffixes")
        identities: list[str] = []
        for series_index, (x_index, y_index) in enumerate(source_pairs, start=1):
            if min(x_index, y_index) < 0 or max(x_index, y_index) >= len(headers):
                failures.append(f"series {series_index} references unavailable columns")
                continue
            x_header = str(headers[x_index]).strip()
            y_header = str(headers[y_index]).strip()
            x_identity = (
                x_header[: -len(x_suffix)] if x_suffix and x_header.endswith(x_suffix) else ""
            )
            y_identity = (
                y_header[: -len(y_suffix)] if y_suffix and y_header.endswith(y_suffix) else ""
            )
            if not x_identity or x_identity != y_identity:
                failures.append(
                    f"series {series_index} X/Y headers do not match the contracted suffixes and identity"
                )
            identities.append(x_identity.casefold())
        nonempty = [value for value in identities if value]
        if len(nonempty) != len(set(nonempty)):
            failures.append("processed source series identities are not unique")
    elif layout == "shared_x_y_columns":
        expected_x = str(schema.get("x_header") or "")
        if expected_x and (not headers or str(headers[0]).strip() != expected_x):
            failures.append(f"shared X header must be {expected_x!r}")
        y_suffix = str(schema.get("y_header_suffix") or "")
        y_headers = [str(headers[y_index]).strip() for _x_index, y_index in source_pairs]
        if y_suffix and any(not value.endswith(y_suffix) for value in y_headers):
            failures.append(f"shared-X Y headers must end with {y_suffix!r}")
        if any(not value for value in y_headers) or len(
            {value.casefold() for value in y_headers}
        ) != len(y_headers):
            failures.append("shared-X Y headers must be nonempty and unique")
    elif layout == "three_sample_independent_x_with_seven_roles":
        x_suffix = str(schema.get("x_header_suffix") or "")
        if x_suffix != "_binding_energy_eV":
            failures.append("XPS adaptive contract lacks the reviewed sample-local X suffix")
        if len(headers) < 8 or len(headers) % 8 != 0:
            failures.append("XPS adaptive source must contain complete 8-column sample groups")
        sample_count = len(headers) // 8
        expected_pairs: list[tuple[int, int]] = []
        identities: list[str] = []
        for sample_index in range(sample_count):
            x_index = sample_index * 8
            first = x_index + 1
            x_header = str(headers[x_index]).strip()
            identity = (
                x_header[: -len(x_suffix)]
                if x_suffix and x_header.casefold().endswith(x_suffix.casefold())
                else ""
            )
            if not identity:
                failures.append(
                    f"XPS sample group {sample_index + 1} lacks a sample-local binding-energy header"
                )
            for role_index, role_suffix in enumerate(
                VERIFIED_XPS_IN_SITU_ROLE_SUFFIXES
            ):
                y_index = first + role_index
                expected_pairs.append((x_index, y_index))
                if y_index >= len(headers):
                    continue
                y_header = str(headers[y_index]).strip()
                expected_header = identity + role_suffix
                if not identity or y_header.casefold() != expected_header.casefold():
                    failures.append(
                        f"XPS sample group {sample_index + 1} role {role_index + 1} "
                        "does not match the reviewed sample identity and role order"
                    )
            identities.append(identity.casefold())
        if source_pairs != expected_pairs:
            failures.append("XPS adaptive plot pairs do not follow the reviewed seven-role order")
        nonempty = [value for value in identities if value]
        if len(nonempty) != len(set(nonempty)):
            failures.append("XPS adaptive sample identities must be nonempty and unique")
        for sample_index in range(sample_count):
            x_index = sample_index * 8
            first = x_index + 1
            bounds = _paired_numeric_row_bounds(rows, x_index, first)
            if bounds is None:
                continue
            row_from, row_to = bounds
            component_order = _xps_in_situ_component_source_order(
                rows,
                x_index,
                first + 1,
                first + 3,
                row_from=row_from,
                row_to=row_to,
            )
            if component_order != (first + 1, first + 3):
                failures.append(
                    f"XPS sample group {sample_index + 1} components are not ordered higher-binding-energy first"
                )
            for row_index in range(row_from - 1, row_to):
                background_values = [
                    _finite_numeric_value(rows[row_index][column_index])
                    for column_index in (first + 2, first + 4, first + 5)
                ]
                if any(value is None for value in background_values) or len(
                    set(background_values)
                ) != 1:
                    failures.append(
                        f"XPS sample group {sample_index + 1} fill baselines and background differ"
                    )
                    break
    elif layout == "two_sample_shared_x_with_nine_roles":
        if str(schema.get("region_scope") or "") != "Bi 4f only":
            failures.append(
                "XPS non-in-situ adaptive contract is not explicitly scoped to the reviewed Bi 4f region"
            )
        if not headers or str(headers[0]).strip() != "binding_energy_eV":
            failures.append("XPS non-in-situ adaptive source requires shared binding_energy_eV")
        if len(headers) < 10 or (len(headers) - 1) % 9 != 0:
            failures.append("XPS non-in-situ adaptive source must contain complete nine-role sample groups")
        sample_count = max(0, (len(headers) - 1) // 9)
        expected_pairs = [(0, y_index) for y_index in range(1, len(headers))]
        if source_pairs != expected_pairs:
            failures.append("XPS non-in-situ adaptive plot pairs must use the shared X and reviewed role order")
        identities: list[str] = []
        for sample_index in range(sample_count):
            first = 1 + sample_index * 9
            identity = ""
            for role_index, role_suffix in enumerate(
                VERIFIED_XPS_NON_IN_SITU_ROLE_SUFFIXES
            ):
                y_index = first + role_index
                if y_index >= len(headers):
                    continue
                y_header = str(headers[y_index]).strip()
                current_identity = (
                    y_header[: -len(role_suffix)]
                    if y_header.casefold().endswith(role_suffix.casefold())
                    else ""
                )
                if not current_identity:
                    failures.append(
                        f"XPS non-in-situ sample group {sample_index + 1} role "
                        f"{role_index + 1} does not match {role_suffix!r}"
                    )
                elif not identity:
                    identity = current_identity
                elif current_identity.casefold() != identity.casefold():
                    failures.append(
                        f"XPS non-in-situ sample group {sample_index + 1} mixes sample identities"
                    )
            identities.append(identity.casefold())
            group_bounds = [
                _paired_numeric_row_bounds(rows, 0, first + role_index)
                for role_index in range(9)
            ]
            finite_bounds = [value for value in group_bounds if value is not None]
            if len(finite_bounds) != 9:
                failures.append(
                    f"XPS non-in-situ sample group {sample_index + 1} has an empty role curve"
                )
                continue
            if len(set(finite_bounds)) != 1:
                failures.append(
                    f"XPS non-in-situ sample group {sample_index + 1} role curves do not share row bounds"
                )
                continue
            row_from, row_to = finite_bounds[0]
            for row_index in range(row_from - 1, row_to):
                values = [
                    _finite_numeric_value(rows[row_index][column_index])
                    for column_index in range(first, first + 9)
                ]
                if any(value is None for value in values):
                    failures.append(
                        f"XPS non-in-situ sample group {sample_index + 1} has an incomplete role curve"
                    )
                    break
                component_1, baseline_1, line_1 = values[0:3]
                component_2, baseline_2, line_2 = values[3:6]
                background = values[7]
                if (
                    component_1 != line_1
                    or component_2 != line_2
                    or baseline_1 != background
                    or baseline_2 != background
                ):
                    failures.append(
                        f"XPS non-in-situ sample group {sample_index + 1} fill helpers do not match supplied components/background"
                    )
                    break
        nonempty = [value for value in identities if value]
        if len(nonempty) != len(set(nonempty)):
            failures.append("XPS non-in-situ sample identities must be nonempty and unique")
    elif (
        layout == "multi_book_xy_pairs"
        and str(getattr(contract, "product_key", "") or "").casefold() == "xrd"
    ):
        # The reviewed XRD OTPU contract owns multiple workbooks and layers.
        # The adaptive OTH+JSON route deliberately does not: it plots the
        # current shared-X CSV in one clean layer.  Its semantic contract is
        # therefore explicit here rather than pretending its columns satisfy
        # the fixed multi-book binding.
        semantic = _validate_adaptive_xrd_standard_card_headers(
            headers,
            [(x_index + 1, y_index + 1) for x_index, y_index in source_pairs],
        )
        if not semantic.get("ok"):
            failures.extend(str(value) for value in semantic.get("failures", []))
    else:
        failures.append(f"adaptive source layout is unsupported: {layout!r}")

    for series_index, (x_index, y_index) in enumerate(source_pairs, start=1):
        for row in rows:
            x_value = _finite_numeric_value(row[x_index]) if x_index < len(row) else None
            y_value = _finite_numeric_value(row[y_index]) if y_index < len(row) else None
            if layout == "shared_x_y_columns":
                if y_value is not None and x_value is None:
                    failures.append(
                        f"series {series_index} contains Y data without its shared X value"
                    )
                    break
            else:
                if (x_value is None) != (y_value is None):
                    failures.append(f"series {series_index} contains an unpaired X or Y value")
                    break
        bounds = _paired_numeric_row_bounds(rows, x_index, y_index)
        if bounds is None:
            failures.append(f"series {series_index} has no contiguous finite X/Y run")
    return {
        "ok": not failures,
        "status": "ready" if not failures else "invalid",
        "layout": layout,
        "source_series_count": len(source_pairs),
        "failures": failures,
        "message": (
            "Current CSV is semantically valid; only series cardinality differs from the fixed contract."
            if not failures
            else "; ".join(failures)
        ),
    }


def _resolve_origin_style_execution_route(
    project_root: Path,
    product: ProductContext,
    *,
    requested_mode: str,
    asset_only: bool = False,
) -> tuple[dict[str, object], object | None]:
    mode = _normalize_origin_style_mode(requested_mode)
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="processed_csv_invalid",
                message=str(exc),
                current_series_count=0,
                contract_series_count=0,
                asset=None,
                ok=False,
            ),
            None,
        )
    plot_pairs = _processed_csv_plot_pairs(product, headers)
    current_count = len(plot_pairs)
    if current_count <= 0:
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="processed_csv_binding_invalid",
                message="Processed CSV headers do not form valid plot pairs.",
                current_series_count=0,
                contract_series_count=0,
                asset=None,
                ok=False,
            ),
            None,
        )

    try:
        exact_asset = resolve_origin_runtime_style_asset(
            project_root,
            product.product_key,
        )
    except (OSError, ValueError) as exc:
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="runtime_asset_registry_invalid",
                message=str(exc),
                current_series_count=current_count,
                contract_series_count=0,
                asset=None,
                ok=False,
            ),
            None,
        )
    legacy_oth_asset = None
    if exact_asset is not None and str(
        getattr(exact_asset, "runtime_asset_kind", "") or ""
    ) != "otpu":
        if str(getattr(exact_asset, "runtime_asset_kind", "") or "") == "oth":
            legacy_oth_asset = exact_asset
        exact_asset = None

    adaptive_asset = None
    adaptive_resolved = False
    adaptive_error = ""

    def get_adaptive_asset():
        nonlocal adaptive_asset, adaptive_resolved, adaptive_error
        if not adaptive_resolved:
            adaptive_resolved = True
            try:
                adaptive_asset = resolve_origin_adaptive_style_asset(
                    project_root,
                    product.product_key,
                    allow_candidate=mode == "oth-json",
                )
            except (OSError, ValueError) as exc:
                adaptive_error = str(exc)
        return adaptive_asset

    # A matching fixed binding has no dependency on the adaptive candidate.
    if mode == "oth-json" or (mode == "auto" and exact_asset is None):
        get_adaptive_asset()
        if mode == "oth-json" and adaptive_error:
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="adaptive_asset_registry_invalid",
                    message=adaptive_error,
                    current_series_count=current_count,
                    contract_series_count=0,
                    asset=None,
                    ok=False,
                    candidate_assets_allowed=True,
                ),
                None,
            )

    contract_asset = exact_asset or adaptive_asset
    contract, contract_error = _binding_contract_for_asset(
        product.product_key,
        contract_asset,
    )
    contract_count = int(getattr(contract, "source_series_count", 0) or 0)
    xps_non_in_situ_bi4f_scope = bool(
        product.product_key != "XPS_non_in_situ"
        or re.search(r"\bBi\s*4f\b", str(product.graph_title), re.IGNORECASE)
    )

    if mode == "otpu":
        if exact_asset is None:
            decision = _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="verified_otpu_unavailable",
                message="A verified OTPU runtime asset is not available.",
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=None,
                ok=False,
            )
            return decision, None
        try:
            binding = _prepare_verified_otpu_binding(
                product,
                headers,
                rows,
                contract_path=getattr(exact_asset, "binding_contract_path", None),
            )
        except (OSError, ValueError) as exc:
            binding = {"ok": False, "message": str(exc)}
        if not bool(binding.get("ok")):
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="verified_otpu_binding_mismatch",
                    message=str(binding.get("message") or "OTPU binding failed."),
                    current_series_count=current_count,
                    contract_series_count=contract_count,
                    asset=exact_asset,
                    ok=False,
                ),
                None,
            )
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="otpu",
                reason_code="explicit_verified_otpu",
                message="Explicit OTPU mode selected the exact fixed binding.",
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=exact_asset,
                fixed_binding_match=True,
            ),
            exact_asset,
        )

    if mode == "oth-json":
        if not xps_non_in_situ_bi4f_scope:
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="xps_non_in_situ_bi4f_scope_mismatch",
                    message=(
                        "The accepted XPS non-in-situ OTH+JSON asset is reviewed for Bi 4f only; "
                        "a different XPS region requires its own reviewed style and annotation contract."
                    ),
                    current_series_count=current_count,
                    contract_series_count=contract_count,
                    asset=adaptive_asset,
                    ok=False,
                    candidate_assets_allowed=True,
                ),
                None,
            )
        complete, message = _adaptive_asset_complete(get_adaptive_asset())
        if not complete:
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="adaptive_oth_json_unavailable",
                    message=message,
                    current_series_count=current_count,
                    contract_series_count=contract_count,
                    asset=adaptive_asset,
                    ok=False,
                    candidate_assets_allowed=True,
                ),
                None,
            )
        if contract is None:
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="adaptive_binding_contract_invalid",
                    message=contract_error,
                    current_series_count=current_count,
                    contract_series_count=0,
                    asset=adaptive_asset,
                    ok=False,
                    candidate_assets_allowed=True,
                ),
                None,
            )
        explicit_source_validation = _strict_adaptive_source_validation(
            contract,
            headers,
            rows,
            [(x_col - 1, y_col - 1) for x_col, y_col in plot_pairs],
        )
        if not bool(explicit_source_validation.get("ok")):
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="adaptive_source_binding_invalid",
                    message=str(
                        explicit_source_validation.get("message")
                        or "Adaptive CSV binding is invalid."
                    ),
                    current_series_count=current_count,
                    contract_series_count=contract_count,
                    asset=adaptive_asset,
                    ok=False,
                    candidate_assets_allowed=True,
                ),
                None,
            )
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="oth-json",
                reason_code="explicit_adaptive_oth_json",
                message="Explicit OTH+JSON mode selected the adaptive style path.",
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=adaptive_asset,
                candidate_assets_allowed=True,
            ),
            adaptive_asset,
        )

    if exact_asset is None:
        complete, _message = _adaptive_asset_complete(get_adaptive_asset())
        if complete:
            if not xps_non_in_situ_bi4f_scope:
                return (
                    _style_execution_decision(
                        product,
                        requested_mode=mode,
                        selected_mode="blocked",
                        reason_code="xps_non_in_situ_bi4f_scope_mismatch",
                        message=(
                            "The accepted XPS non-in-situ adaptive asset is reviewed for Bi 4f only."
                        ),
                        current_series_count=current_count,
                        contract_series_count=contract_count,
                        asset=adaptive_asset,
                        ok=False,
                    ),
                    None,
                )
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="oth-json",
                    reason_code="accepted_adaptive_asset_without_fixed_otpu",
                    message="No fixed OTPU runtime exists; accepted adaptive OTH+JSON was selected.",
                    current_series_count=current_count,
                    contract_series_count=contract_count,
                    asset=adaptive_asset,
                ),
                adaptive_asset,
            )
        if legacy_oth_asset is not None:
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="legacy-oth",
                    reason_code="accepted_legacy_oth_runtime",
                    message="Accepted legacy OTH runtime behavior was preserved.",
                    current_series_count=current_count,
                    contract_series_count=0,
                    asset=legacy_oth_asset,
                ),
                legacy_oth_asset,
            )
        if not asset_only:
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="existing-template",
                    reason_code="no_project_runtime_asset",
                    message="No project runtime asset was selected; existing template resolution remains active.",
                    current_series_count=current_count,
                    contract_series_count=0,
                    asset=None,
                ),
                None,
            )
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="asset_only_runtime_asset_unavailable",
                message="Asset-only mode requires a verified OTPU or accepted adaptive OTH+JSON asset.",
                current_series_count=current_count,
                contract_series_count=0,
                asset=None,
                ok=False,
            ),
            None,
        )
    if contract is None:
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="fixed_binding_contract_invalid",
                message=contract_error,
                current_series_count=current_count,
                contract_series_count=0,
                asset=exact_asset,
                ok=False,
            ),
            None,
        )
    if current_count == contract_count:
        try:
            binding = _prepare_verified_otpu_binding(
                product,
                headers,
                rows,
                contract_path=getattr(exact_asset, "binding_contract_path", None),
            )
        except (OSError, ValueError) as exc:
            binding = {"ok": False, "message": str(exc)}
        if not bool(binding.get("ok")):
            if product.product_key in {"UV-vis DRS", "Tauc", "XRD"}:
                source_validation = _strict_adaptive_source_validation(
                    contract,
                    headers,
                    rows,
                    [(x_col - 1, y_col - 1) for x_col, y_col in plot_pairs],
                )
                adaptive_complete, adaptive_error = _adaptive_asset_complete(get_adaptive_asset())
                if source_validation.get("ok") and adaptive_complete:
                    return (
                        _style_execution_decision(
                            product,
                            requested_mode=mode,
                            selected_mode="oth-json",
                            reason_code=(
                                "fixed_cardinality_semantics_select_adaptive_xrd"
                                if product.product_key == "XRD"
                                else "fixed_cardinality_semantics_select_adaptive_uvvis"
                            ),
                            message=(
                                "Current XRD shared-X columns carry one final reference-card role but "
                                "do not carry the reviewed fixed multi-book/layer binding; accepted OTH+JSON was selected."
                                if product.product_key == "XRD"
                                else "Current UV-vis columns are valid spectra but do not carry the "
                                "reviewed hidden/visible fixed-template roles; accepted OTH+JSON was selected."
                            ),
                            current_series_count=current_count,
                            contract_series_count=contract_count,
                            asset=adaptive_asset,
                        ),
                        adaptive_asset,
                    )
                if source_validation.get("ok") and not adaptive_complete:
                    binding = {
                        **binding,
                        "message": str(binding.get("message") or "OTPU binding failed.")
                        + f" Adaptive route unavailable: {adaptive_error}",
                    }
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="fixed_cardinality_semantic_binding_mismatch",
                    message=str(binding.get("message") or "OTPU binding failed."),
                    current_series_count=current_count,
                    contract_series_count=contract_count,
                    asset=exact_asset,
                    ok=False,
                ),
                None,
            )
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="otpu",
                reason_code="auto_exact_fixed_binding_match",
                message="Current CSV exactly matches the fixed OTPU binding contract.",
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=exact_asset,
                fixed_binding_match=True,
            ),
            exact_asset,
        )

    source_pairs = [
        (x_col - 1, y_col - 1) for x_col, y_col in plot_pairs
    ]
    if not xps_non_in_situ_bi4f_scope:
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="xps_non_in_situ_bi4f_scope_mismatch",
                message=(
                    "The accepted XPS non-in-situ adaptive asset is reviewed for Bi 4f only."
                ),
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=adaptive_asset,
                ok=False,
            ),
            None,
        )
    source_validation = _strict_adaptive_source_validation(
        contract,
        headers,
        rows,
        source_pairs,
    )
    if not bool(source_validation.get("ok")):
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="cardinality_and_semantic_binding_mismatch",
                message=str(source_validation.get("message") or "CSV binding is invalid."),
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=exact_asset,
                ok=False,
            ),
            None,
        )
    complete, adaptive_error = _adaptive_asset_complete(get_adaptive_asset())
    if not complete:
        return (
            _style_execution_decision(
                product,
                requested_mode=mode,
                selected_mode="blocked",
                reason_code="cardinality_mismatch_without_accepted_adaptive_asset",
                message=adaptive_error,
                current_series_count=current_count,
                contract_series_count=contract_count,
                asset=exact_asset,
                ok=False,
            ),
            None,
        )
    return (
        _style_execution_decision(
            product,
            requested_mode=mode,
            selected_mode="oth-json",
            reason_code="auto_series_cardinality_mismatch_only",
            message=(
                "The current CSV is semantically valid and differs from the fixed OTPU "
                "contract only in series cardinality; accepted adaptive OTH+JSON was selected."
            ),
            current_series_count=current_count,
            contract_series_count=contract_count,
            asset=adaptive_asset,
        ),
        adaptive_asset,
    )


def apply_template_base_data_replacement(operations: object, product: ProductContext, graph_name: str) -> dict[str, object]:
    plot_names_result = _read_template_plot_dataset_names(operations, graph_name)
    if not plot_names_result["ok"]:
        return {"ok": False, "message": str(plot_names_result.get("message") or "plot dataset read failed")}
    plot_dataset_names = list(plot_names_result["plot_dataset_names"])
    headers, rows = _read_processed_csv(product.processed_data)
    headers, rows, column_mapping = _template_base_ordered_processed_table(product, headers, rows)
    updates = build_template_dataset_updates(
        plot_dataset_names,
        headers,
        rows,
        allow_partial=True,
        paired_xy_columns=product.product_key == "XRD" and _xrd_standard_card_keeps_line_sample_legend(product),
    )
    if updates.status not in {"ready", "partial"}:
        return {
            "ok": False,
            "message": "; ".join(updates.warnings) or "template dataset update plan is blocked",
            "template_dataset_updates": updates.to_dict(),
        }
    replaced = operations.replace_template_workbook_columns(updates.workbook_columns)
    if not getattr(replaced, "ok", False):
        return {
            "ok": False,
            "message": getattr(replaced, "message", "template workbook replacement failed"),
            "template_dataset_updates": updates.to_dict(),
        }
    return {
        "ok": True,
        "message": "Template workbook columns replaced from processed data.",
        "template_dataset_updates": updates.to_dict(),
        "replace_result": getattr(replaced, "payload", {}),
        "processed_headers": headers,
        "processed_column_mapping": column_mapping,
        "template_plot_layers_read": plot_names_result["layers_read"],
    }


def _template_base_ordered_processed_table(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
) -> tuple[list[str], list[list[object]], dict[str, object]]:
    if product.product_key != "EPR":
        return headers, rows, {"applied": False, "method": "csv_header_order"}
    preferred_order = ["BOBC", "CWO", "BC"]
    header_map = {str(header).strip().casefold(): index for index, header in enumerate(headers)}
    if not headers or not all(name.casefold() in header_map for name in preferred_order):
        return headers, rows, {
            "applied": False,
            "method": "csv_header_order",
            "reason": "EPR preferred template-stack headers were not all present.",
            "preferred_order": preferred_order,
        }
    indices = [0] + [header_map[name.casefold()] for name in preferred_order]
    reordered_headers = [headers[index] for index in indices]
    reordered_rows = [[row[index] if index < len(row) else "" for index in indices] for row in rows]
    return reordered_headers, reordered_rows, {
        "applied": True,
        "method": "epr_template_bottom_to_top_plot_order",
        "preferred_order": preferred_order,
        "source_headers": headers,
        "output_headers": reordered_headers,
    }


def _processed_csv_template_source_pairs(
    product: ProductContext,
    headers: list[str],
) -> list[tuple[int, int]]:
    pairs = [
        (origin_x - 1, origin_y - 1)
        for origin_x, origin_y in _processed_csv_plot_pairs(product, headers)
    ]
    if product.product_key == "XPS_in_situ":
        pairs = [
            (x_index, y_index)
            for x_index, y_index in pairs
            if not str(headers[y_index]).strip().casefold().endswith("_fill_baseline")
        ]
    return pairs


def _read_template_plot_dataset_names(operations: object, graph_name: str, *, max_layers: int = 12) -> dict[str, object]:
    names: list[str] = []
    layers_read: list[int] = []
    first_failure = ""
    for layer_index in range(1, max_layers + 1):
        result = operations.get_graph_plot_dataset_names(graph_name, layer_index=layer_index)
        if not getattr(result, "ok", False):
            if layer_index == 1:
                first_failure = getattr(result, "message", "plot dataset read failed")
            if names:
                break
            continue
        layer_names = [str(name) for name in getattr(result, "payload", {}).get("plot_dataset_names", []) if str(name).strip()]
        if not layer_names and names:
            break
        if layer_names:
            layers_read.append(layer_index)
            names.extend(layer_names)
    if not names:
        return {"ok": False, "message": first_failure or "No plot datasets were found in template graph.", "plot_dataset_names": [], "layers_read": []}
    return {"ok": True, "plot_dataset_names": names, "layers_read": layers_read}


class _OriginLifecycleFailure(RuntimeError):
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        details: list[str] = []
        if not bool(payload.get("origin_close_ok")):
            close_message = str(payload.get("origin_close_message") or "").strip()
            details.append(f"Origin close failed{': ' + close_message if close_message else ''}")
        cleanup = payload.get("runtime_cleanup")
        if isinstance(cleanup, dict) and not bool(cleanup.get("ok")):
            cleanup_status = str(cleanup.get("status") or "failed")
            cleanup_error = str(cleanup.get("error") or "").strip()
            details.append(
                f"runtime cleanup {cleanup_status}{': ' + cleanup_error if cleanup_error else ''}"
            )
        super().__init__(
            "Origin lifecycle finalization failed; product acceptance is blocked"
            + (": " + "; ".join(details) if details else "")
        )


def export_template_base_product_with_origin(
    product: ProductContext,
    style: ResolvedPlotStyle,
    *,
    project_root: Path | None = None,
    prefer_project_style_asset: bool = True,
    preserve_exemplar_style: bool = False,
    asset_only: bool = False,
    origin_style_mode: str = "auto",
) -> dict[str, object]:
    try:
        with origin_style_asset_read_scope(), template_input_scope():
            return _export_template_base_product_with_origin_impl(
                product,
                style,
                project_root=project_root,
                prefer_project_style_asset=prefer_project_style_asset,
                preserve_exemplar_style=preserve_exemplar_style,
                asset_only=asset_only,
                origin_style_mode=origin_style_mode,
            )
    except _OriginLifecycleFailure as exc:
        return {
            "ok": False,
            "message": str(exc),
            "origin_runtime_cleanup": exc.payload,
        }


def _export_template_base_product_with_origin_impl(
    product: ProductContext,
    style: ResolvedPlotStyle,
    *,
    project_root: Path | None = None,
    prefer_project_style_asset: bool = True,
    preserve_exemplar_style: bool = False,
    asset_only: bool = False,
    origin_style_mode: str = "auto",
) -> dict[str, object]:
    operations = None
    runtime_cleanup_path: Path | None = None
    try:
        if asset_only and preserve_exemplar_style:
            return {"ok": False, "message": "asset-only export cannot preserve an external exemplar"}
        if asset_only and product.external_reference_opju is not None:
            product = replace(
                product,
                external_reference_opju=None,
                external_reference_graph="",
                external_reference_source="",
            )
        style_decision: dict[str, object] | None = None
        if (
            project_root is not None
            and prefer_project_style_asset
            and not preserve_exemplar_style
        ):
            style_decision, style_asset = _resolve_origin_style_execution_route(
                project_root,
                product,
                requested_mode=origin_style_mode,
                asset_only=asset_only,
            )
            if not bool(style_decision.get("ok")):
                return {
                    "ok": False,
                    "message": str(
                        style_decision.get("message")
                        or "Origin style execution route is blocked."
                    ),
                    "origin_style_decision": style_decision,
                    "origin_processing": _style_execution_metadata(style_decision),
                }
        else:
            style_asset = None
        neutral_root = _neutral_origin_runtime_root()
        with tempfile.TemporaryDirectory(prefix="rdop_origin_", dir=neutral_root, ignore_cleanup_errors=True) as runtime_text:
            runtime = Path(runtime_text)
            runtime_cleanup_path = runtime
            reference_source = product.reference_opju_copy
            runtime_reference = runtime / reference_source.name
            plan_opju: Path | None = None
            if (
                not asset_only
                and (style_asset is None or style_asset.runtime_asset_kind not in {"otpu", "oth_json"})
                and reference_source.suffix.casefold() in {".opju", ".opj"}
                and reference_source.is_file()
            ):
                shutil.copy2(reference_source, runtime_reference)
                plan_opju = runtime_reference
            runtime_origin = runtime / product.origin_file.name
            runtime_reference_png = runtime / product.reference_preview_png.name
            runtime_preview_png = runtime / product.preview_png.name
            runtime_tif = runtime / product.figure_tif.name
            runtime_debug = runtime / "debug"
            runtime_template_debug = runtime_debug / "template_preview.png"
            runtime_generated_debug = runtime_debug / "generated_preview.png"
            operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
            if (
                style_asset is not None
                and style_asset.runtime_asset_kind == "otpu"
                and style_asset.runtime_asset_path is not None
            ):
                result = _export_verified_graph_template_product_with_origin(
                    operations,
                    product,
                    style,
                    style_asset,
                    runtime_dir=runtime,
                )
                return _attach_style_execution_decision(result, style_decision)
            embedded_snapshot = embedded_template_snapshot(product.product_key)
            embedded_available = embedded_snapshot is not None

            plan = build_template_format_plan(
                product.product_key,
                opju_path=plan_opju,
                style_package_path=style_asset.format_theme_path if style_asset else None,
                graph_page=style_asset.graph_page if style_asset else (embedded_snapshot.graph_page if embedded_snapshot is not None else ""),
                reference_preview_png=runtime_reference_png,
                product_preview_png=runtime_preview_png,
                curve_line_width_pt=style.line_width_pt,
                axis_title_bold=style.font_bold,
                embedded_snapshot_available=embedded_available and plan_opju is None and style_asset is None,
            )
            if not plan.can_execute:
                return {"ok": False, "message": "; ".join(plan.warnings), "template_format_plan": plan.to_dict()}
            if plan.mode == "saved_format_theme":
                project_reference_opju, project_reference_graph, require_project_reference = (
                    _saved_theme_reference_policy(
                        style_asset,
                        style_decision,
                        asset_only=asset_only,
                    )
                )
                result = _export_saved_format_theme_product_with_origin(
                    operations,
                    product,
                    style,
                    plan,
                    project_reference_opju=project_reference_opju,
                    project_reference_graph=project_reference_graph,
                    require_project_reference=require_project_reference,
                    runtime_dir=runtime,
                    style_snapshot_path=getattr(style_asset, "style_snapshot_path", None),
                    data_snapshot_path=getattr(style_asset, "data_snapshot_path", None),
                    style_execution_decision=style_decision,
                )
                return _attach_style_execution_decision(result, style_decision)
            if plan.mode == "embedded_template_snapshot" and embedded_snapshot is not None:
                return _export_template_snapshot_fallback_product_with_origin(
                    operations,
                    product,
                    style,
                    plan,
                    embedded_snapshot,
                    {
                        "ok": False,
                        "message": "External OPJU template was not used; script-embedded Origin template snapshot selected.",
                        "embedded_template_snapshot": True,
                    },
                    runtime_origin=runtime_origin,
                    runtime_reference_png=runtime_reference_png,
                    runtime_preview_png=runtime_preview_png,
                    runtime_tif=runtime_tif,
                    runtime_template_debug=runtime_template_debug,
                    runtime_generated_debug=runtime_generated_debug,
                    preserve_exemplar_style=preserve_exemplar_style,
                )
            if not runtime_reference.is_file():
                return {"ok": False, "message": "Template OPJU copy was not available.", "template_format_plan": plan.to_dict()}

            exemplar_snapshot = extract_style_snapshot(operations, runtime_reference)
            exemplar_style = exemplar_snapshot.to_dict()
            graph_name = str(exemplar_snapshot.graph_page or "")
            if not graph_name:
                return {
                    "ok": False,
                    "message": "No graph page was available in the template OPJU copy.",
                    "template_format_plan": plan.to_dict(),
                    "exemplar_style": exemplar_style,
                }
            plan = build_template_format_plan(
                product.product_key,
                opju_path=runtime_reference,
                graph_page=graph_name,
                reference_preview_png=runtime_reference_png,
                product_preview_png=runtime_preview_png,
                curve_line_width_pt=style.line_width_pt,
                axis_title_bold=style.font_bold,
            )
            operations.export_graph(graph_name, runtime_reference_png, "png", dpi=style.export_dpi)
            operations.export_graph(graph_name, runtime_template_debug, "png", dpi=style.export_dpi)
            operations.new_project()
            exemplar_snapshot = extract_style_snapshot(operations, runtime_reference)
            exemplar_style = exemplar_snapshot.to_dict()
            graph_name = str(exemplar_snapshot.graph_page or graph_name)
            reference_data_snapshot = (
                read_graph_data_snapshot(
                    operations,
                    graph_name,
                    source_label=runtime_reference.name,
                )
                if preserve_exemplar_style
                else {}
            )
            try:
                replacement = apply_template_base_data_replacement(
                    operations,
                    product,
                    graph_name,
                )
            except Exception as exc:
                if not preserve_exemplar_style and _can_use_template_snapshot_fallback(product):
                    replacement_failure = {
                        "ok": False,
                        "message": scrub_output_text(str(exc), output_root=product.type_root.parent),
                        "traceback": scrub_output_text(traceback.format_exc(), output_root=product.type_root.parent),
                    }
                    return _export_template_snapshot_fallback_product_with_origin(
                        operations,
                        product,
                        style,
                        plan,
                        exemplar_snapshot,
                        replacement_failure,
                        runtime_origin=runtime_origin,
                        runtime_reference_png=runtime_reference_png,
                        runtime_preview_png=runtime_preview_png,
                        runtime_tif=runtime_tif,
                        runtime_template_debug=runtime_template_debug,
                        runtime_generated_debug=runtime_generated_debug,
                        preserve_exemplar_style=preserve_exemplar_style,
                    )
                raise
            if not replacement.get("ok"):
                if not preserve_exemplar_style and _can_use_template_snapshot_fallback(product):
                    return _export_template_snapshot_fallback_product_with_origin(
                        operations,
                        product,
                        style,
                        plan,
                        exemplar_snapshot,
                        replacement,
                        runtime_origin=runtime_origin,
                        runtime_reference_png=runtime_reference_png,
                        runtime_preview_png=runtime_preview_png,
                        runtime_tif=runtime_tif,
                        runtime_template_debug=runtime_template_debug,
                        runtime_generated_debug=runtime_generated_debug,
                        preserve_exemplar_style=preserve_exemplar_style,
                    )
                return {
                    "ok": False,
                    "message": str(replacement.get("message") or "template base data replacement failed"),
                    "template_format_plan": plan.to_dict(),
                    "template_base_replacement": replacement,
                    "exemplar_style": exemplar_style,
                }

            if not preserve_exemplar_style:
                _apply_template_base_global_policies(
                    operations,
                    graph_name,
                    product,
                    style,
                    template_axis_titles=exemplar_snapshot.audit_string_values,
                )
                apply_resolved_style_overrides(operations, graph_name, style)
            if preserve_exemplar_style:
                legend_policy: dict[str, object] = {
                    "mode": "template_legend_object_preserved",
                    "applied": False,
                    "style_mutation_blocked": True,
                    "reason": "Strict exemplar mode preserves the template legend and graph objects unchanged.",
                }
            else:
                legend_entries = _plain_text_legend_entries(product, exemplar_snapshot)
                xrd_keep_line_legend = _xrd_standard_card_keeps_line_sample_legend(product)
                if xrd_keep_line_legend:
                    preserved_legend_policy = _format_preserved_line_sample_legend(operations, graph_name, style)
                    xrd_card_label_policy = _apply_xrd_standard_card_legend_and_label(
                        operations,
                        graph_name,
                        product,
                        legend_entries,
                        style,
                    )
                    legend_anchor_policy = {
                        "applied": False,
                        "reason": "xrd_standard_card_keeps_template_line_sample_legend",
                    }
                    xrd_plain_label_policy = {
                        "applied": False,
                        "reason": "xrd_standard_card_keeps_template_line_sample_legend",
                    }
                else:
                    legend_anchor_policy = {"applied": False, "reason": "native_legend_layout_deferred"}
                    if product.product_key == "XRD":
                        xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(
                            operations,
                            graph_name,
                            product,
                            legend_entries,
                            style,
                        )
                    else:
                        _update_template_native_legend(
                            operations,
                            graph_name,
                            legend_entries,
                            style,
                        )
                        xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(
                            operations,
                            graph_name,
                            product,
                            legend_entries,
                            style,
                        )
                legend_policy = _plain_text_legend_policy(
                    product,
                    entries=legend_entries,
                    anchor_policy=legend_anchor_policy,
                    xrd_plain_label_policy=xrd_plain_label_policy,
                    line_samples_removed=product.product_key == "XRD" and not xrd_keep_line_legend,
                    preserved_line_sample_policy=preserved_legend_policy if xrd_keep_line_legend else None,
                    xrd_card_label_policy=xrd_card_label_policy if xrd_keep_line_legend else None,
                    xrd_standard_card_reference_sticks_present=xrd_keep_line_legend,
                )
            legend_layout = avoid_native_legend_overlap(operations, graph_name)
            if not getattr(legend_layout, "ok", False):
                return {
                    "ok": False,
                    "message": getattr(legend_layout, "message", "native legend layout failed"),
                    "exemplar_style": exemplar_style,
                    "native_legend_layout": getattr(legend_layout, "payload", {}),
                }
            saved = operations.save_project(runtime_origin)
            if not getattr(saved, "ok", False):
                return {"ok": False, "message": getattr(saved, "message", "project save failed"), "exemplar_style": exemplar_style}

            operations.new_project()
            loaded = operations.load_project(runtime_origin)
            if not getattr(loaded, "ok", False):
                return {"ok": False, "message": getattr(loaded, "message", "saved product reload failed"), "exemplar_style": exemplar_style}
            pages = operations.list_worksheets().payload.get("pages", [])
            graph_pages = [str(item["name"]) for item in pages if item.get("type") == "graph"]
            reopened_graph = graph_name if graph_name in graph_pages else (graph_pages[0] if graph_pages else graph_name)
            product_snapshot = read_graph_style_snapshot(
                operations,
                reopened_graph,
                source_label=product.origin_file.name,
                graph_pages=graph_pages,
                prefer_custom_rgb=product.product_key == "Mott-Schottky",
            )
            product_data_snapshot = (
                read_graph_data_snapshot(
                    operations,
                    reopened_graph,
                    source_label=runtime_origin.name,
                )
                if preserve_exemplar_style
                else {}
            )
            same_data_comparison = (
                compare_graph_data_snapshots(
                    reference_data_snapshot,
                    product_data_snapshot,
                    require_explicit_plotdata_mapping=True,
                )
                if preserve_exemplar_style
                else {
                    "status": "not_evaluated",
                    "same_data": False,
                    "reasons": [
                        "Same-data exact comparison is reserved for explicit exemplar diagnostics."
                    ],
                }
            )
            conformance = compare_style_snapshots(
                exemplar_snapshot,
                product_snapshot,
                required_line_width_pt=None if preserve_exemplar_style else style.line_width_pt,
                require_axis_title_bold=not preserve_exemplar_style,
            )
            strict_readback = _strict_style_readback(product_snapshot.to_dict())
            png = operations.export_graph(reopened_graph, runtime_preview_png, "png", dpi=style.export_dpi)
            tif = _export_native_tif_with_physical_validation(
                operations,
                reopened_graph,
                runtime_tif,
                dpi=style.export_dpi,
            )
            operations.export_graph(reopened_graph, runtime_generated_debug, "png", dpi=style.export_dpi)
            metadata_warnings = [
                warning
                for warning in (
                    _strip_raster_metadata(runtime_reference_png, dpi=style.export_dpi),
                    _strip_raster_metadata(runtime_preview_png, dpi=style.export_dpi),
                )
                if warning
            ]
            missing = [
                path
                for path in (runtime_origin, runtime_reference_png, runtime_preview_png, runtime_tif)
                if not path.exists() or path.stat().st_size == 0
            ]
            if missing:
                return {
                    "ok": False,
                    "message": "missing artifacts: " + "; ".join(path.name for path in missing),
                    "template_format_plan": plan.to_dict(),
                    "template_base_replacement": replacement,
                    "exemplar_style": exemplar_style,
                    "product_style": product_snapshot.to_dict(),
                    "conformance": conformance.to_dict(),
                }
            if not getattr(png, "ok", False) or not bool(tif.get("ok")):
                return {
                    "ok": False,
                    "message": scrub_output_text(
                        f"{getattr(png, 'message', '')}; {tif.get('message', '')}",
                        output_root=product.type_root.parent,
                    ),
                    "template_format_plan": plan.to_dict(),
                    "template_base_replacement": replacement,
                    "exemplar_style": exemplar_style,
                }
            operations.new_project()
            _copy_runtime_artifact(runtime_origin, product.origin_file)
            _copy_runtime_artifact(runtime_reference_png, product.reference_preview_png)
            _copy_runtime_artifact(runtime_preview_png, product.preview_png)
            _copy_runtime_artifact(runtime_tif, product.figure_tif)
            if runtime_template_debug.exists():
                _copy_runtime_artifact(runtime_template_debug, product.type_root / "debug" / "template_preview.png")
            if runtime_generated_debug.exists():
                _copy_runtime_artifact(runtime_generated_debug, product.type_root / "debug" / "generated_preview.png")
        return {
            "ok": True,
            "message": "Origin template-base export succeeded after save/reopen/readback.",
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement,
            "exemplar_style": exemplar_style,
            "product_style": product_snapshot.to_dict(),
            "conformance": conformance.to_dict(),
            "strict_style_readback": strict_readback,
            "same_data_comparison": same_data_comparison,
            "reference_graph_data": _compact_graph_data_snapshot(reference_data_snapshot),
            "product_graph_data": _compact_graph_data_snapshot(product_data_snapshot),
            "origin_processing": {
                "required": True,
                "applied": True,
                "method": "opju_template_base_workbook_replacement",
                "processing_location": "Origin template-base workbook replacement",
                "source_opju_copy": _product_output_path(product.type_root.parent, product.reference_opju_copy),
                "graph_page": reopened_graph,
                "raster_metadata_stripped": not metadata_warnings,
                "metadata_warnings": metadata_warnings,
                "tif_resolution_evidence": tif.get("evidence", {}),
                "legend_policy": legend_policy,
                "style_contract": (
                    "preserve_exemplar_exact"
                    if preserve_exemplar_style
                    else "apply_resolved_style_policy"
                ),
            },
            "xps_component_fill": _template_base_xps_fill_intent(product, replacement),
            "reopened_graph": reopened_graph,
            "tif_resolution_evidence": tif.get("evidence", {}),
            "line_width_policy_pt": None if preserve_exemplar_style else style.line_width_pt,
            "line_width_reference_origin_units": (
                list(exemplar_snapshot.plot_line_widths)
                if preserve_exemplar_style
                else []
            ),
            "axis_title_bold_policy": None if preserve_exemplar_style else style.font_bold,
            "axis_title_bold_reference": (
                _style_snapshot_axis_title_bold_required(exemplar_snapshot.to_dict())
                if preserve_exemplar_style
                else None
            ),
            "one_to_one_pixel_comparison_eligible": bool(
                same_data_comparison.get("same_data")
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": scrub_output_text(str(exc), output_root=product.type_root.parent),
            "traceback": scrub_output_text(traceback.format_exc(), output_root=product.type_root.parent),
        }
    finally:
        close_result = None
        close_exception = ""
        if operations is not None:
            try:
                close_result = operations.close()
            except Exception as exc:
                close_exception = f"{type(exc).__name__}: {exc}"
        try:
            cleanup_result = _cleanup_origin_runtime_directory(runtime_cleanup_path)
        except Exception as exc:
            cleanup_result = {
                "ok": False,
                "status": "cleanup_raised",
                "attempts": 0,
                "runtime_directory": runtime_cleanup_path.name if runtime_cleanup_path is not None else "",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if (
            bool(close_exception)
            or (close_result is not None and not getattr(close_result, "ok", False))
            or not bool(cleanup_result.get("ok"))
        ):
            try:
                failure_payload = _record_origin_runtime_cleanup_failure(
                    product,
                    close_result=close_result,
                    close_exception=close_exception,
                    cleanup_result=cleanup_result,
                )
            except Exception as exc:
                failure_payload = {
                    "status": "failed",
                    "origin_close_ok": not bool(close_exception)
                    and (close_result is None or bool(getattr(close_result, "ok", False))),
                    "origin_close_message": scrub_output_text(
                        close_exception
                        or (getattr(close_result, "message", "") if close_result is not None else ""),
                        output_root=product.type_root.parent,
                    ),
                    "runtime_cleanup": dict(cleanup_result),
                    "diagnostic_write_error": scrub_output_text(
                        f"{type(exc).__name__}: {exc}",
                        output_root=product.type_root.parent,
                    ),
                }
            raise _OriginLifecycleFailure(failure_payload)


def _compact_graph_data_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    if not isinstance(snapshot, dict) or not snapshot:
        return {}
    plots = snapshot.get("plots")
    compact_plots = []
    if isinstance(plots, list):
        for raw in plots:
            if not isinstance(raw, dict):
                continue
            compact_plots.append(
                {
                    key: raw.get(key)
                    for key in (
                        "status",
                        "layer_index",
                        "plot_index",
                        "x_dataset",
                        "y_dataset",
                        "plot_row_from",
                        "plot_row_to",
                        "row_count",
                        "x_mapping_source",
                        "plot_row_range_source",
                        "x_data_sha256",
                        "y_data_sha256",
                        "xy_data_sha256",
                    )
                }
            )
    return {
        key: snapshot.get(key)
        for key in (
            "schema_version",
            "status",
            "source_opju",
            "graph_page",
            "layer_count_with_plots",
            "plot_count",
            "plot_values_sha256",
            "plot_mapping_sha256",
            "plot_data_sha256",
            "mapping_failure_count",
        )
    } | {"plots": compact_plots}


def _record_origin_runtime_cleanup_failure(
    product: ProductContext,
    *,
    close_result: object | None,
    close_exception: str = "",
    cleanup_result: dict[str, object],
) -> dict[str, object]:
    failure_path = product.type_root / "debug" / "origin_runtime_cleanup_failure.json"
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    close_ok = not close_exception and (
        close_result is None or bool(getattr(close_result, "ok", False))
    )
    payload = {
        "status": "failed",
        "origin_close_ok": close_ok,
        "origin_close_message": scrub_output_text(
            close_exception
            or (getattr(close_result, "message", "") if close_result is not None else ""),
            output_root=product.type_root.parent,
        ),
        "runtime_cleanup": {
            "ok": bool(cleanup_result.get("ok")),
            "status": str(cleanup_result.get("status") or ""),
            "attempts": int(cleanup_result.get("attempts") or 0),
            "runtime_directory": str(cleanup_result.get("runtime_directory") or ""),
            "error": scrub_output_text(
                str(cleanup_result.get("error") or ""),
                output_root=product.type_root.parent,
            ),
        },
        "manual_check_required": (
            "Confirm the isolated Origin process has exited."
            + (
                " Remove the retained runtime directory only after its lock is released."
                if not bool(cleanup_result.get("ok"))
                else ""
            )
        ),
    }
    failure_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def _can_use_template_snapshot_fallback(product: ProductContext) -> bool:
    return embedded_template_snapshot(product.product_key) is not None




def _export_template_snapshot_fallback_product_with_origin(
    operations: object,
    product: ProductContext,
    style: ResolvedPlotStyle,
    plan: object,
    exemplar_snapshot: object,
    replacement_failure: dict[str, object],
    *,
    runtime_origin: Path,
    runtime_reference_png: Path,
    runtime_preview_png: Path,
    runtime_tif: Path,
    runtime_template_debug: Path,
    runtime_generated_debug: Path,
    preserve_exemplar_style: bool = False,
) -> dict[str, object]:
    if not runtime_reference_png.is_file() or runtime_reference_png.stat().st_size == 0:
        return {
            "ok": False,
            "message": "Snapshot fallback requires an independent reference preview; the generated product preview cannot be reused as its own reference.",
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
            "reference_preview": {
                "required": True,
                "available": False,
                "generated_preview_reuse_blocked": True,
            },
        }
    headers, rows = _read_processed_csv(product.processed_data)
    if len(headers) < 2:
        return {
            "ok": False,
            "message": "processed CSV must contain at least one X column and one Y column",
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }

    operations.new_project()
    imported = operations.import_csv_to_worksheet(product.processed_data, book_name=f"{product.slug}_data")
    if not getattr(imported, "ok", False):
        return {
            "ok": False,
            "message": getattr(imported, "message", "CSV import failed"),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }
    book_name = str(imported.payload["book_name"])
    graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
    plot_pairs = _processed_csv_plot_pairs(product, headers)
    if not plot_pairs:
        return {
            "ok": False,
            "message": "processed CSV does not contain plottable column pairs",
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }
    first_header = headers[plot_pairs[0][1] - 1] if plot_pairs[0][1] - 1 < len(headers) else ""
    created = operations.create_graph(
        graph_name,
        book_name,
        "Sheet1",
        plot_pairs[0][0],
        plot_pairs[0][1],
        plot_type=template_plot_type_for_header(product.product_key, str(first_header), product.plot_type),
    )
    if not getattr(created, "ok", False):
        return {
            "ok": False,
            "message": getattr(created, "message", "graph creation failed"),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }
    graph_name = str(created.payload.get("graph_name") or graph_name)
    for x_col, y_col in plot_pairs[1:]:
        header = headers[y_col - 1] if y_col - 1 < len(headers) else ""
        added = operations.add_plot_to_graph(
            graph_name,
            book_name,
            "Sheet1",
            x_col,
            y_col,
            plot_type=template_plot_type_for_header(product.product_key, str(header), product.plot_type),
        )
        if not getattr(added, "ok", False):
            return {
                "ok": False,
                "message": getattr(added, "message", f"plot add failed for columns {x_col}/{y_col}"),
                "template_format_plan": plan.to_dict(),
                "template_base_replacement": replacement_failure,
                "exemplar_style": exemplar_snapshot.to_dict(),
            }

    if not apply_style_snapshot(
        operations,
        graph_name,
        exemplar_snapshot,
        apply_default_font=not preserve_exemplar_style,
    ) and hasattr(operations, "apply_graph4_fixed_style"):
        operations.apply_graph4_fixed_style(graph_name)
    if preserve_exemplar_style and hasattr(operations, "set_graph_font"):
        operations.set_graph_font(
            graph_name,
            font_name=style.font_family,
            axis_title_size=style.axis_title_font_size,
            x_tick_label_size=style.x_tick_label_font_size,
            y_tick_label_size=style.y_tick_label_font_size,
            legend_font_size=style.legend_font_size,
            annotation_font_size=style.legend_font_size,
        )
    if preserve_exemplar_style:
        _apply_exemplar_axis_title_text(operations, graph_name, exemplar_snapshot)
    elif hasattr(operations, "set_axis_labels"):
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
    if not preserve_exemplar_style:
        _apply_template_base_global_policies(
            operations,
            graph_name,
            product,
            style,
            template_axis_titles=getattr(exemplar_snapshot, "audit_string_values", {}),
        )
        apply_resolved_style_overrides(operations, graph_name, style)
    if not preserve_exemplar_style and hasattr(operations, "set_axis_and_tick_visibility"):
        operations.set_axis_and_tick_visibility(
            graph_name,
            y_axis=True,
            y_ticks=product.y_ticks,
            y_tick_values=product.y_tick_values,
        )
    data_axis_policy = _apply_embedded_snapshot_data_axis_range(operations, graph_name, product)
    legend_entries = _plain_text_legend_entries(product, exemplar_snapshot)
    xrd_keep_line_legend = _xrd_standard_card_keeps_line_sample_legend(product)
    if xrd_keep_line_legend:
        preserved_legend_policy = _format_preserved_line_sample_legend(operations, graph_name, style)
        xrd_card_label_policy = _apply_xrd_standard_card_legend_and_label(
            operations,
            graph_name,
            product,
            legend_entries,
            style,
        )
        legend_anchor_policy = {
            "applied": False,
            "reason": "xrd_standard_card_keeps_template_line_sample_legend",
        }
        xrd_plain_label_policy = {
            "applied": False,
            "reason": "xrd_standard_card_keeps_template_line_sample_legend",
        }
    else:
        legend_anchor_policy = {"applied": False, "reason": "native_legend_layout_deferred"}
        if product.product_key == "XRD":
            xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(
                operations,
                graph_name,
                product,
                legend_entries,
                style,
            )
        else:
            _update_template_native_legend(
                operations,
                graph_name,
                legend_entries,
                style,
            )
            xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(operations, graph_name, product, legend_entries, style)
    plot_sequence = _apply_external_reference_plot_sequence(
        operations,
        graph_name,
        exemplar_snapshot.to_dict(),
        product=product,
    )
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; title.show=0;')

    legend_layout = avoid_native_legend_overlap(operations, graph_name)
    if not getattr(legend_layout, "ok", False):
        return {
            "ok": False,
            "message": getattr(legend_layout, "message", "native legend layout failed"),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
            "native_legend_layout": getattr(legend_layout, "payload", {}),
        }
    saved = operations.save_project(runtime_origin)
    if not getattr(saved, "ok", False):
        return {
            "ok": False,
            "message": getattr(saved, "message", "project save failed"),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }

    operations.new_project()
    loaded = operations.load_project(runtime_origin)
    if not getattr(loaded, "ok", False):
        return {
            "ok": False,
            "message": getattr(loaded, "message", "saved product reload failed"),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }
    pages = operations.list_worksheets().payload.get("pages", [])
    graph_pages = [str(item["name"]) for item in pages if item.get("type") == "graph"]
    reopened_graph = graph_name if graph_name in graph_pages else (graph_pages[0] if graph_pages else graph_name)
    product_snapshot = read_graph_style_snapshot(
        operations,
        reopened_graph,
        source_label=product.origin_file.name,
        graph_pages=graph_pages,
        prefer_custom_rgb=product.product_key == "Mott-Schottky",
    )
    conformance = compare_style_snapshots(exemplar_snapshot, product_snapshot, required_line_width_pt=style.line_width_pt)
    strict_readback = _strict_style_readback(product_snapshot.to_dict())
    png = operations.export_graph(reopened_graph, runtime_preview_png, "png", dpi=style.export_dpi)
    tif = _export_native_tif_with_physical_validation(
        operations,
        reopened_graph,
        runtime_tif,
        dpi=style.export_dpi,
    )
    operations.export_graph(reopened_graph, runtime_generated_debug, "png", dpi=style.export_dpi)
    if not runtime_template_debug.exists() and runtime_reference_png.exists():
        runtime_template_debug.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_reference_png, runtime_template_debug)
    metadata_warnings = [
        warning
        for warning in (
            _strip_raster_metadata(runtime_reference_png, dpi=style.export_dpi),
            _strip_raster_metadata(runtime_preview_png, dpi=style.export_dpi),
        )
        if warning
    ]
    missing = [
        path
        for path in (runtime_origin, runtime_reference_png, runtime_preview_png, runtime_tif)
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        return {
            "ok": False,
            "message": "missing artifacts: " + "; ".join(path.name for path in missing),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
            "product_style": product_snapshot.to_dict(),
            "conformance": conformance.to_dict(),
        }
    if not getattr(png, "ok", False) or not bool(tif.get("ok")):
        return {
            "ok": False,
            "message": scrub_output_text(
                f"{getattr(png, 'message', '')}; {tif.get('message', '')}",
                output_root=product.type_root.parent,
            ),
            "template_format_plan": plan.to_dict(),
            "template_base_replacement": replacement_failure,
            "exemplar_style": exemplar_snapshot.to_dict(),
        }

    operations.new_project()
    _copy_runtime_artifact(runtime_origin, product.origin_file)
    _copy_runtime_artifact(runtime_reference_png, product.reference_preview_png)
    _copy_runtime_artifact(runtime_preview_png, product.preview_png)
    _copy_runtime_artifact(runtime_tif, product.figure_tif)
    if runtime_template_debug.exists():
        _copy_runtime_artifact(runtime_template_debug, product.type_root / "debug" / "template_preview.png")
    if runtime_generated_debug.exists():
        _copy_runtime_artifact(runtime_generated_debug, product.type_root / "debug" / "generated_preview.png")
    return {
        "ok": True,
        "message": "Origin snapshot fallback export succeeded after template workbook replacement failed.",
        "template_format_plan": plan.to_dict(),
        "template_base_replacement": {
            **replacement_failure,
            "fallback_applied": True,
        },
        "exemplar_style": exemplar_snapshot.to_dict(),
        "product_style": product_snapshot.to_dict(),
        "conformance": conformance.to_dict(),
        "strict_style_readback": strict_readback,
        "origin_processing": {
            "required": True,
            "applied": True,
            "method": "embedded_template_snapshot_graph"
            if replacement_failure.get("embedded_template_snapshot")
            else "opju_template_snapshot_fallback_graph",
            "processing_location": "Origin clean graph rebuilt from processed CSV using script-embedded template snapshot"
            if replacement_failure.get("embedded_template_snapshot")
            else "Origin clean graph rebuilt from processed CSV after template workbook replacement failed",
            "source_opju_copy": _product_output_path(product.type_root.parent, product.reference_opju_copy),
            "graph_page": reopened_graph,
            "fallback_reason": str(replacement_failure.get("message") or "template workbook replacement failed"),
            "plot_pairs": [{"x_col": x_col, "y_col": y_col} for x_col, y_col in plot_pairs],
            "plot_sequence": plot_sequence,
            "axis_range_policy": data_axis_policy,
            "raster_metadata_stripped": not metadata_warnings,
            "metadata_warnings": metadata_warnings,
            "tif_resolution_evidence": tif.get("evidence", {}),
            "legend_policy": _plain_text_legend_policy(
                product,
                entries=legend_entries,
                anchor_policy=legend_anchor_policy,
                xrd_plain_label_policy=xrd_plain_label_policy,
                line_samples_removed=product.product_key == "XRD" and not xrd_keep_line_legend,
                preserved_line_sample_policy=preserved_legend_policy if xrd_keep_line_legend else None,
                xrd_card_label_policy=xrd_card_label_policy if xrd_keep_line_legend else None,
                xrd_standard_card_reference_sticks_present=xrd_keep_line_legend,
            ),
        },
        "xps_component_fill": _template_base_xps_fill_intent(product, {"ok": True, "template_dataset_updates": {}}),
        "reopened_graph": reopened_graph,
        "tif_resolution_evidence": tif.get("evidence", {}),
        "line_width_policy_pt": style.line_width_pt,
        "axis_title_bold_policy": style.font_bold,
    }


def _export_verified_graph_template_product_with_origin(
    operations: object,
    product: ProductContext,
    style: ResolvedPlotStyle,
    style_asset: object,
    *,
    runtime_dir: Path,
) -> dict[str, object]:
    template_path = Path(str(getattr(style_asset, "runtime_asset_path", "") or ""))
    template_sha256 = str(getattr(style_asset, "runtime_asset_sha256", "") or "")
    if (
        product.product_key not in VERIFIED_GRAPH_TEMPLATE_PRODUCTS
        or str(getattr(style_asset, "runtime_asset_kind", "")) != "otpu"
        or not template_path.is_file()
        or template_path.suffix.casefold() != ".otpu"
    ):
        return {
            "ok": False,
            "message": "Verified graph-template export received an unsupported or missing runtime asset.",
        }
    if origin_style_file_sha256(template_path) != template_sha256:
        return {
            "ok": False,
            "message": "Verified graph-template asset hash changed before Origin execution.",
        }
    headers, rows = _read_processed_csv(product.processed_data)
    binding = _prepare_verified_otpu_binding(
        product,
        headers,
        rows,
        contract_path=getattr(style_asset, "binding_contract_path", None),
    )
    plan_payload = {
        "data_type": product.product_key,
        "status": "ready" if binding.get("ok") else "blocked",
        "mode": "verified_graph_template",
        "graph_page": binding.get("graph_page") or getattr(style_asset, "graph_page", ""),
        "style_package_path": _product_output_path(
            product.type_root.parent,
            template_path,
        ),
        "can_execute": bool(binding.get("ok")),
        "one_to_one_claim_allowed": False,
        "warnings": [] if binding.get("ok") else [binding.get("message")],
    }
    if not binding.get("ok"):
        return {
            "ok": False,
            "message": str(
                binding.get("message")
                or f"{product.product_key} OTPU binding is blocked."
            ),
            "template_format_plan": plan_payload,
            "template_binding": binding,
        }

    runtime = Path(runtime_dir)
    runtime_template = runtime / template_path.name
    runtime_origin = runtime / product.origin_file.name
    runtime_png = runtime / product.preview_png.name
    runtime_tif = runtime / product.figure_tif.name
    shutil.copy2(template_path, runtime_template)
    reference_style_path = getattr(style_asset, "style_snapshot_path", None)
    reference_style = _load_json_object(reference_style_path)
    if not isinstance(reference_style, dict) or reference_style.get("status") != "extracted":
        return {
            "ok": False,
            "message": (
                f"Verified {product.product_key} OTPU export requires its saved style snapshot."
            ),
            "template_format_plan": plan_payload,
        }
    reference_data_path = getattr(style_asset, "data_snapshot_path", None)
    reference_data = _load_json_object(reference_data_path)
    if product.product_key in {"Raman", "photocurrent", "Mott-Schottky", "UV-vis DRS", "Tauc", "XPS_in_situ", "XPS_non_in_situ"} and (
        not isinstance(reference_data, dict)
        or str(reference_data.get("status") or "") != "ready"
    ):
        return {
            "ok": False,
            "message": (
                f"Verified {product.product_key} OTPU export requires its saved data snapshot."
            ),
            "template_format_plan": plan_payload,
        }
    reference_axis_titles: dict[str, object] | None = None
    if product.product_key == "photocurrent":
        reference_axis_titles = _validate_photocurrent_axis_titles(
            reference_style,
            headers,
        )
        if not reference_axis_titles.get("ok"):
            return {
                "ok": False,
                "message": str(reference_axis_titles["message"]),
                "template_format_plan": plan_payload,
                "photocurrent_axis_titles": reference_axis_titles,
            }
    runtime_theme: Path | None = None
    if product.product_key in {"EIS", "EPR", "PL", "photocurrent"}:
        theme_path = Path(str(getattr(style_asset, "format_theme_path", "") or ""))
        if not theme_path.is_file() or theme_path.suffix.casefold() != ".oth":
            return {
                "ok": False,
                "message": f"Verified {product.product_key} OTPU export requires its reviewed OTH asset.",
                "template_format_plan": plan_payload,
            }
        runtime_theme = runtime / theme_path.name
        shutil.copy2(theme_path, runtime_theme)
    runtime_reference = {
        "ok": True,
        "reference_kind": "validated_project_style_snapshot",
        "style_snapshot_path": _product_output_path(
            product.type_root.parent,
            Path(reference_style_path),
        ),
        "reference_opju_loaded": False,
        "used_as_product_base": False,
    }

    reset = operations.new_project()
    if not getattr(reset, "ok", False):
        return {
            "ok": False,
            "message": getattr(reset, "message", "Could not start a fresh Origin project."),
            "template_format_plan": plan_payload,
        }
    workbook = _populate_verified_otpu_workbook(
        operations,
        product,
        headers,
        rows,
        binding,
    )
    if not workbook.get("ok"):
        return {
            "ok": False,
            "message": str(
                workbook.get("message")
                or f"Processed {product.product_key} workbook preparation failed."
            ),
            "template_format_plan": plan_payload,
            "template_binding": binding,
        }
    # EPR writes through the shared Origin processor; XPS writes through
    # _write_processed_csv below.  Later readback must use the transformed data.
    if product.product_key == "EPR":
        invalidate_processed_table(product.processed_data)
    _validation_headers, validation_rows = _read_processed_csv(product.processed_data)
    book_name = str(workbook["book_name"])
    created = operations.create_graph_from_xy_pairs_template(
        str(binding["graph_page"]),
        runtime_template,
        book_name,
        list(binding["xy_ranges"]),
        plot_type=str(binding["plot_type"]),
        rescale=False,
        legend=False,
        group_plots=bool(binding.get("group_plots", False)),
        plot_format_contracts=list(binding.get("plot_format_contracts") or []),
    )
    if not getattr(created, "ok", False):
        return {
            "ok": False,
            "message": getattr(
                created,
                "message",
                f"Verified {product.product_key} OTPU plot failed.",
            ),
            "template_format_plan": plan_payload,
        }
    graph_name = str(created.payload.get("graph_name") or binding["graph_page"])
    page_mask_override = binding.get("page_mask_override")
    if page_mask_override is not None:
        mask_display = operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; page.mask={int(page_mask_override)};'
        )
        if not getattr(mask_display, "ok", False):
            return {
                "ok": False,
                "message": f"Verified {product.product_key} masked-point display policy failed.",
                "template_format_plan": plan_payload,
            }
    post_plot_style = _apply_verified_otpu_post_plot_style(
        operations,
        product,
        graph_name,
        reference_style,
        style,
        runtime_theme=runtime_theme,
        reference_data=reference_data,
    )
    if not post_plot_style.get("ok"):
        return {
            "ok": False,
            "message": str(
                post_plot_style.get("message")
                or f"Verified {product.product_key} detached style replay failed."
            ),
            "template_format_plan": plan_payload,
            "template_binding": binding,
            "post_plot_style": post_plot_style,
        }
    render_refresh = _refresh_graph_for_export(operations, graph_name)
    legend_layout = avoid_native_legend_overlap(operations, graph_name)
    if not getattr(legend_layout, "ok", False):
        return {
            "ok": False,
            "message": getattr(legend_layout, "message", "native legend layout failed"),
            "template_format_plan": plan_payload,
            "native_legend_layout": getattr(legend_layout, "payload", {}),
        }
    saved = operations.save_project(runtime_origin)
    if not getattr(saved, "ok", False) or not runtime_origin.is_file():
        return {
            "ok": False,
            "message": getattr(
                saved,
                "message",
                f"Verified {product.product_key} OPJU save failed.",
            ),
            "template_format_plan": plan_payload,
        }
    operations.new_project()
    reopened = operations.load_project(runtime_origin)
    if not getattr(reopened, "ok", False):
        return {
            "ok": False,
            "message": getattr(
                reopened,
                "message",
                f"Verified {product.product_key} OPJU reopen failed.",
            ),
            "template_format_plan": plan_payload,
        }
    pages_result = operations.list_worksheets()
    pages = getattr(pages_result, "payload", {}).get("pages", [])
    graph_pages = [
        str(page.get("name"))
        for page in pages
        if isinstance(page, dict) and page.get("type") == "graph"
    ]
    if graph_pages.count(graph_name) != 1:
        return {
            "ok": False,
            "message": (
                f"Saved {product.product_key} graph page {graph_name!r} was not uniquely "
                "present after reopen."
            ),
            "template_format_plan": plan_payload,
            "available_graph_pages": graph_pages,
        }
    product_snapshot = read_graph_style_snapshot(
        operations,
        graph_name,
        source_label=product.origin_file.name,
        graph_pages=graph_pages,
        prefer_custom_rgb=product.product_key == "Mott-Schottky",
    )
    product_style = product_snapshot.to_dict()
    tauc_guide_cleanup_validation: dict[str, object] = {
        "ok": True,
        "status": "not_required",
    }
    if (
        product.product_key == "Tauc"
        and not bool(post_plot_style.get("reference_fit_guides_preserved"))
    ):
        tauc_guide_cleanup_validation = _validate_tauc_reference_guides_removed(
            operations,
            graph_name,
            product_style,
        )
        if not tauc_guide_cleanup_validation.get("ok"):
            return {
                "ok": False,
                "message": "Changed-data Tauc reference guides remained after save/reopen.",
                "template_format_plan": plan_payload,
                "product_style": product_style,
                "tauc_guide_cleanup_validation": tauc_guide_cleanup_validation,
            }
    product_axis_titles: dict[str, object] | None = None
    if product.product_key == "photocurrent":
        product_axis_titles = _validate_photocurrent_axis_titles(
            product_style,
            headers,
        )
        if not product_axis_titles.get("ok"):
            return {
                "ok": False,
                "message": str(product_axis_titles["message"]),
                "template_format_plan": plan_payload,
                "photocurrent_axis_titles": product_axis_titles,
            }
    strict_readback = _strict_style_readback(product_style)
    conformance = compare_style_snapshots(
        _verified_otpu_conformance_reference(product.product_key, reference_style, product_style),
        product_snapshot,
        required_line_width_pt=_verified_otpu_required_line_width_pt(
            product.product_key,
            style,
        ),
        require_axis_title_bold=_verified_otpu_axis_title_bold_policy(
            product.product_key,
            reference_style,
        ),
    ).to_dict()
    conformance["reference_source"] = runtime_reference["reference_kind"]
    if (
        product.product_key in {"Raman", "Mott-Schottky", "UV-vis DRS", "Tauc", "XPS_in_situ", "XPS_non_in_situ"}
        and str(conformance.get("status") or "").casefold() == "fail"
    ):
        return {
            "ok": False,
            "message": (
                f"Verified {product.product_key} style conformance failed after save/reopen."
            ),
            "template_format_plan": plan_payload,
            "conformance": conformance,
            "product_style": product_style,
        }
    current_data_snapshot = read_graph_data_snapshot(
        operations,
        graph_name,
        source_label=product.origin_file.name,
    )
    current_data_validation = _validate_verified_current_data(
        product.product_key,
        validation_rows,
        list(binding["xy_ranges"]),
        current_data_snapshot,
    )
    if not current_data_validation.get("ok"):
        return {
            "ok": False,
            "message": str(
                current_data_validation.get("message")
                or f"Reopened {product.product_key} graph data did not match the processed CSV."
            ),
            "template_format_plan": plan_payload,
            "current_data_validation": current_data_validation,
        }
    raman_plot_style_validation = (
        _validate_raman_reopened_plot_styles(reference_data, current_data_snapshot)
        if product.product_key == "Raman"
        else {"ok": True, "status": "not_required"}
    )
    if not raman_plot_style_validation.get("ok"):
        return {
            "ok": False,
            "message": str(
                raman_plot_style_validation.get("message")
                or "Reopened Raman per-layer plot styles differ from the reviewed snapshot."
            ),
            "template_format_plan": plan_payload,
            "raman_plot_style_validation": raman_plot_style_validation,
        }
    xps_plot_style_validation = (
        _validate_xps_in_situ_reopened_plot_styles(reference_data, current_data_snapshot)
        if product.product_key == "XPS_in_situ"
        else _validate_xps_non_in_situ_reopened_plot_styles(
            reference_data,
            current_data_snapshot,
        )
        if product.product_key == "XPS_non_in_situ"
        else {"ok": True, "status": "not_required"}
    )
    if not xps_plot_style_validation.get("ok"):
        return {
            "ok": False,
            "message": str(
                xps_plot_style_validation.get("message")
                or "Reopened XPS plot styles differ from the reviewed snapshot."
            ),
            "template_format_plan": plan_payload,
            "xps_plot_style_validation": xps_plot_style_validation,
        }
    png = operations.export_graph(graph_name, runtime_png, "png", dpi=style.export_dpi)
    tif = _export_native_tif_with_physical_validation(
        operations,
        graph_name,
        runtime_tif,
        dpi=style.export_dpi,
    )
    metadata_warning = (
        _strip_raster_metadata(runtime_png, dpi=style.export_dpi)
        if runtime_png.exists()
        else ""
    )
    if (
        not getattr(png, "ok", False)
        or not bool(tif.get("ok"))
        or any(
            not path.is_file() or path.stat().st_size == 0
            for path in (runtime_origin, runtime_png, runtime_tif)
        )
    ):
        return {
            "ok": False,
            "message": f"Verified {product.product_key} Origin artifact export failed.",
            "template_format_plan": plan_payload,
            "tif_resolution_evidence": tif.get("evidence", {}),
        }
    if file_sha256(template_path) != template_sha256:
        return {
            "ok": False,
            "message": (
                f"Verified {product.product_key} OTPU source changed during Origin execution."
            ),
            "template_format_plan": plan_payload,
        }
    operations.new_project()
    _copy_runtime_artifact(runtime_origin, product.origin_file)
    _copy_runtime_artifact(runtime_png, product.preview_png)
    _copy_runtime_artifact(runtime_tif, product.figure_tif)
    return {
        "ok": True,
        "message": (
            f"Origin verified-OTPU {product.product_key} export succeeded without loading "
            "a reference OPJU."
        ),
        "template_format_plan": plan_payload,
        "origin_processing": {
            "required": True,
            "applied": True,
            "method": "fresh_graph_verified_otpu_explicit_xy",
            "processing_location": "Origin fresh project with verified project-local OTPU and explicit current-data X/Y ranges",
            "style_contract": _verified_otpu_style_contract(product.product_key),
            "runtime_asset_kind": "otpu",
            "runtime_asset_path": _product_output_path(
                product.type_root.parent,
                template_path,
            ),
            "runtime_asset_sha256": template_sha256,
            "graph_page": graph_name,
            "neutral_runtime": True,
            "reference_opju_used_as_product_base": False,
            "reference_opju_loaded": False,
            "current_data_validation": current_data_validation,
            "raman_plot_style_validation": raman_plot_style_validation,
            "xps_plot_style_validation": xps_plot_style_validation,
            "template_binding": binding,
            "workbook_preparation": workbook,
            "post_plot_style": post_plot_style,
            "tauc_guide_cleanup_validation": tauc_guide_cleanup_validation,
            "photocurrent_axis_titles": product_axis_titles,
            "render_refresh": render_refresh,
            "raster_metadata_stripped": not bool(metadata_warning),
            "metadata_warnings": [metadata_warning] if metadata_warning else [],
            "tif_resolution_evidence": tif.get("evidence", {}),
        },
        "external_reference_preview": runtime_reference,
        "exemplar_style": reference_style,
        "product_style": product_style,
        "strict_style_readback": strict_readback,
        "conformance": conformance,
        "current_data_snapshot": current_data_snapshot,
        "current_data_validation": current_data_validation,
        "raman_plot_style_validation": raman_plot_style_validation,
        "xps_plot_style_validation": xps_plot_style_validation,
        "reopened_graph": graph_name,
        "tif_resolution_evidence": tif.get("evidence", {}),
        "line_width_policy_pt": _verified_otpu_required_line_width_pt(
            product.product_key,
            style,
        ),
        "axis_title_bold_policy": _verified_otpu_axis_title_bold_policy(
            product.product_key,
            reference_style,
        ),
        "photocurrent_axis_titles": product_axis_titles,
        "xps_component_fill": {
            "required": product.product_key in {"XPS_in_situ", "XPS_non_in_situ"},
            "applied": product.product_key in {"XPS_in_situ", "XPS_non_in_situ"} and bool(xps_plot_style_validation.get("ok")),
            "method": (
                "verified_otpu_native_component_fill_with_shared_background_helpers"
                if product.product_key in {"XPS_in_situ", "XPS_non_in_situ"}
                else "not_required"
            ),
        },
    }


def _prepare_verified_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    cache = current_template_inputs()
    cache_key = (id(product), str(contract_path or ""))
    if cache is not None and cache_key in cache.bindings:
        return cache.bindings[cache_key]
    preparers = {
        "BET": _prepare_verified_bet_otpu_binding,
        "EIS": _prepare_verified_eis_otpu_binding,
        "EPR": _prepare_verified_epr_otpu_binding,
        "Raman": _prepare_verified_raman_otpu_binding,
        "PL": _prepare_verified_pl_otpu_binding,
        "photocurrent": _prepare_verified_photocurrent_otpu_binding,
        "FTIR": _prepare_verified_ftir_otpu_binding,
        "Mott-Schottky": _prepare_verified_mott_otpu_binding,
        "UV-vis DRS": _prepare_verified_uvvis_otpu_binding,
        "Tauc": _prepare_verified_uvvis_otpu_binding,
        "XPS_in_situ": _prepare_verified_xps_in_situ_otpu_binding,
        "XPS_non_in_situ": _prepare_verified_xps_non_in_situ_otpu_binding,
    }
    prepare = preparers.get(product.product_key)
    if prepare is None:
        return {
            "ok": False,
            "message": (
                f"Verified OTPU runtime dispatch is not implemented for {product.product_key}."
            ),
        }
    result = prepare(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )
    if cache is not None:
        cache.bindings[cache_key] = result
    return result


def _verified_otpu_conformance_reference(
    product_key: str,
    reference_style: dict[str, object],
    product_style: dict[str, object],
) -> dict[str, object]:
    if product_key in {"BET", "photocurrent", "UV-vis DRS", "Tauc"}:
        adjusted = dict(reference_style)
        data_dependent_fields = {
            "layer.x.from",
            "layer.x.to",
            "layer.y.from",
            "layer.y.to",
            "xb.x",
            "xb.y",
            "yl.x",
            "yl.y",
            "legend.x",
            "legend.y",
        }
        for section in ("layout_values", "audit_numeric_values"):
            expected = dict(reference_style.get(section) or {})
            actual = dict(product_style.get(section) or {})
            expected.update(
                {
                    field: actual[field]
                    for field in data_dependent_fields
                    if field in actual
                }
            )
            adjusted[section] = expected
        expected_strings = dict(reference_style.get("audit_string_values") or {})
        actual_strings = dict(product_style.get("audit_string_values") or {})
        # Axis titles remain fixed reviewed content.  Axis ranges/coordinates
        # and the legend text are current-data dependent for adaptive products.
        if "legend.text$" in actual_strings:
            expected_strings["legend.text$"] = actual_strings["legend.text$"]
        if product_key in {"UV-vis DRS", "Tauc"}:
            for field in ("xb.text$", "yl.text$"):
                if field in actual_strings:
                    expected_strings[field] = actual_strings[field]
        adjusted["audit_string_values"] = expected_strings
        return adjusted
    if product_key in {"PL", "Raman", "Mott-Schottky"}:
        adjusted = dict(reference_style)
        expected_strings = dict(reference_style.get("audit_string_values") or {})
        actual_strings = dict(product_style.get("audit_string_values") or {})
        if "legend.text$" in actual_strings:
            expected_strings["legend.text$"] = actual_strings["legend.text$"]
        adjusted["audit_string_values"] = expected_strings
        return adjusted
    if product_key not in {"EIS", "EPR"}:
        return reference_style
    adjusted = dict(reference_style)
    if product_key == "EIS":
        fields = {
            "layer.x.from", "layer.x.to", "layer.y.from", "layer.y.to",
            "legend.x", "legend.y", "legend.show",
            # Origin automatically moves titles away from tick-label extents when
            # current data require a different numeric tick format.  Preserve the
            # centered/template text styling, then audit visibility and overlap
            # separately instead of treating these perpendicular offsets as fixed.
            "xb.y", "yl.x",
        }
    else:
        # EPR only permits the current magnetic-field range and the resulting
        # horizontal-axis title coordinate to differ from its exact template.
        fields = {"layer.x.from", "layer.x.to", "xb.x", "xb.y"}
    for section in ("layout_values", "audit_numeric_values"):
        expected = dict(reference_style.get(section) or {})
        actual = dict(product_style.get(section) or {})
        expected.update({field: actual[field] for field in fields if field in actual})
        adjusted[section] = expected
    return adjusted


def _verified_otpu_style_contract(product_key: str) -> str:
    return (
        "preserve_exemplar_exact"
        if product_key in {"EIS", "Raman", "photocurrent", "FTIR"}
        else "verified_detached_otpu"
    )


def _verified_otpu_required_line_width_pt(
    product_key: str,
    style: ResolvedPlotStyle,
) -> float | None:
    # EIS preserves a template-specific width. The reviewed photocurrent Graph2
    # and FTIR assets are explicitly audited at the current 3 pt product policy.
    # Raman's reviewed graph spans two layers. The flattened page-level style
    # snapshot cannot read the third plot width reliably; its per-layer data
    # snapshot is validated explicitly after reopen instead.
    return None if product_key in {"EIS", "Raman", "Mott-Schottky", "XPS_in_situ", "XPS_non_in_situ", "XRD"} else style.line_width_pt


def _verified_otpu_axis_title_bold_policy(
    product_key: str,
    reference_style: dict[str, object],
) -> bool:
    if product_key in {"photocurrent", "FTIR"}:
        return _style_snapshot_axis_title_bold_required(reference_style)
    return True


def _xps_in_situ_component_source_order(
    rows: list[list[object]],
    x_index: int,
    first_component_index: int,
    second_component_index: int,
    *,
    row_from: int,
    row_to: int,
) -> tuple[int, int] | None:
    peak_binding_energies: list[tuple[float, int]] = []
    for source_index in (first_component_index, second_component_index):
        points: list[tuple[float, float]] = []
        for row in rows[row_from - 1 : row_to]:
            x_value = _finite_numeric_value(
                row[x_index] if x_index < len(row) else None
            )
            y_value = _finite_numeric_value(
                row[source_index] if source_index < len(row) else None
            )
            if x_value is not None and y_value is not None:
                points.append((x_value, y_value))
        if not points:
            return None
        peak_x, _peak_y = max(points, key=lambda point: point[1])
        peak_binding_energies.append((peak_x, source_index))
    if peak_binding_energies[0][0] == peak_binding_energies[1][0]:
        return None
    ordered = sorted(peak_binding_energies, reverse=True)
    return ordered[0][1], ordered[1][1]


def _prepare_verified_xps_in_situ_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "XPS_in_situ":
        return {
            "ok": False,
            "message": "Verified XPS in-situ binding received a different product type.",
        }
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("xps_in_situ")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed XPS in-situ template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    expected_indices = list(range(24))
    if (
        str(source_schema.get("layout") or "")
        != "three_sample_independent_x_with_seven_roles"
        or str(source_schema.get("x_header_suffix") or "") != "_binding_energy_eV"
        or source_schema.get("source_csv_indices") != expected_indices
        or str(source_schema.get("worksheet_layout") or "")
        != "three_workbooks_shared_x_six_destination_columns"
        or list(source_schema.get("reviewed_vertical_offsets") or [])
        != list(XPS_IN_SITU_REVIEWED_VERTICAL_OFFSETS)
        or str(source_schema.get("component_order") or "")
        != "higher_binding_energy_peak_first"
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": "XPS in-situ contract must use the reviewed 24-column independent-X, three-workbook layout.",
        }
    if len(headers) != 24:
        return {
            "ok": False,
            "message": "XPS in-situ processed CSV must contain three sample-local binding-energy columns plus 21 fitted-role columns.",
        }
    if re.search(
        r"\bBi\s*4f\b",
        str(product.graph_title),
        re.IGNORECASE,
    ) is None:
        return {
            "ok": False,
            "message": "The reviewed Bi 4f fixed template cannot be used for a non-Bi XPS region.",
        }

    sample_identities: list[str] = []
    for sample_index in range(3):
        x_index = sample_index * 8
        first = x_index + 1
        x_header = str(headers[x_index]).strip()
        x_suffix = "_binding_energy_eV"
        if not x_header.casefold().endswith(x_suffix.casefold()):
            return {
                "ok": False,
                "message": f"XPS in-situ sample group {sample_index + 1} lacks its sample-local binding-energy column.",
            }
        x_identity = x_header[: -len(x_suffix)]
        identities: list[str] = []
        for header, suffix in zip(
            headers[first : first + 7],
            VERIFIED_XPS_IN_SITU_ROLE_SUFFIXES,
        ):
            text = str(header).strip()
            if not text.casefold().endswith(suffix.casefold()):
                return {
                    "ok": False,
                    "message": (
                        f"XPS in-situ sample group {sample_index + 1} does not follow the reviewed "
                        f"seven-role order at {text!r}; expected suffix {suffix!r}."
                    ),
                }
            identities.append(text[: -len(suffix)])
        if (
            not x_identity
            or any(not identity for identity in identities)
            or {identity.casefold() for identity in identities} != {x_identity.casefold()}
        ):
            return {
                "ok": False,
                "message": f"XPS in-situ sample group {sample_index + 1} mixes different sample identities.",
            }
        sample_identities.append(x_identity)
    if len({identity.casefold() for identity in sample_identities}) != 3:
        return {
            "ok": False,
            "message": "XPS in-situ requires three nonempty unique current sample identities.",
        }

    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [
        (f"{book_name}_A", f"{book_name}_{chr(64 + y_col)}")
        for book_name in VERIFIED_XPS_IN_SITU_BOOKS
        for y_col in VERIFIED_XPS_IN_SITU_DESTINATION_Y_COLUMNS
    ]
    actual_datasets = [
        (str(plot.x_dataset), str(plot.y_dataset)) for plot in contracted_plots
    ]
    if (
        len(contracted_plots) != 21
        or contract.source_series_count != 21
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != list(range(1, 22))
        or [plot.source_series_index for plot in contracted_plots] != list(range(1, 22))
        or actual_datasets != expected_datasets
    ):
        return {
            "ok": False,
            "message": "XPS in-situ contract must contain the reviewed ordered Book2/Book3/Book4 21-plot topology.",
        }

    bounds_by_sample: list[tuple[int, int]] = []
    for sample_index in range(3):
        x_index = sample_index * 8
        first = x_index + 1
        group_bounds: list[tuple[int, int]] = []
        for source_y_index in range(first, first + 7):
            bounds = _paired_numeric_row_bounds(rows, x_index, source_y_index)
            if bounds is None:
                return {
                    "ok": False,
                    "message": (
                        f"XPS in-situ sample group {sample_index + 1} role column "
                        f"{source_y_index + 1} must contain one contiguous finite sample-local X/Y run."
                    ),
                }
            group_bounds.append(bounds)
        if len(set(group_bounds)) != 1:
            return {
                "ok": False,
                "message": f"XPS in-situ sample group {sample_index + 1} fitted roles do not share row bounds.",
            }
        bounds_by_sample.append(group_bounds[0])

    for sample_index in range(3):
        first = sample_index * 8 + 1
        row_from, row_to = bounds_by_sample[sample_index]
        shared_background_columns = (first + 2, first + 4, first + 5)
        for row_index in range(row_from - 1, row_to):
            values = [
                _finite_numeric_value(rows[row_index][column_index])
                for column_index in shared_background_columns
            ]
            if any(value is None for value in values) or len(set(values)) != 1:
                return {
                    "ok": False,
                    "message": (
                        f"XPS in-situ sample group {sample_index + 1} requires component baselines "
                        "and background to be the same supplied curve before sharing destination column E."
                    ),
                }

    runtime_sources_by_sample: list[list[int]] = []
    for sample_index in range(3):
        x_index = sample_index * 8
        first = x_index + 1
        row_from, row_to = bounds_by_sample[sample_index]
        component_order = _xps_in_situ_component_source_order(
            rows,
            x_index,
            first + 1,
            first + 3,
            row_from=row_from,
            row_to=row_to,
        )
        if component_order is None:
            return {
                "ok": False,
                "message": (
                    f"XPS in-situ sample group {sample_index + 1} component peak order is ambiguous; "
                    "the fixed Bi 4f template requires distinct higher/lower-binding-energy components."
                ),
            }
        high_binding_component, low_binding_component = component_order
        runtime_sources_by_sample.append(
            [
                first,
                high_binding_component,
                first + 2,
                low_binding_component,
                first + 4,
                first + 5,
                first + 6,
            ]
        )

    xy_ranges: list[dict[str, object]] = []
    for flat_index, (plot, y_col, source_y_index) in enumerate(zip(
        contracted_plots,
        VERIFIED_XPS_IN_SITU_DESTINATION_Y_COLUMNS * 3,
        (source for sources in runtime_sources_by_sample for source in sources),
    )):
        sample_index = flat_index // 7
        book_name = VERIFIED_XPS_IN_SITU_BOOKS[sample_index]
        x_index = sample_index * 8
        row_from, row_to = bounds_by_sample[sample_index]
        xy_ranges.append(
            {
                "book_name": book_name,
                "sheet_index": 1,
                "layer_index": 1,
                "x_col": 1,
                "y_col": y_col,
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": x_index,
                "source_y_index": source_y_index,
            }
        )
    workbooks = []
    for sample_index, book_name in enumerate(VERIFIED_XPS_IN_SITU_BOOKS):
        x_index = sample_index * 8
        first = x_index + 1
        high_binding_component = runtime_sources_by_sample[sample_index][1]
        low_binding_component = runtime_sources_by_sample[sample_index][3]
        workbooks.append(
            {
                "book_name": book_name,
                "sheet_name": "Sheet1",
                "sample_identity": sample_identities[sample_index],
                "source_indices": [
                    x_index,
                    first,
                    high_binding_component,
                    low_binding_component,
                    first + 5,
                    first + 6,
                ],
                "normalization_source_index": first,
                "reviewed_vertical_offset": XPS_IN_SITU_REVIEWED_VERTICAL_OFFSETS[sample_index],
            }
        )
    return {
        "ok": True,
        "message": "Processed XPS in-situ columns match the reviewed 21-role OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": VERIFIED_XPS_IN_SITU_BOOKS[0],
        "plot_type": "line",
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "workbooks": workbooks,
        "sample_identities": sample_identities,
        "source_binding": {
            "ok": True,
            "status": "ready",
            "layout": "three_sample_independent_x_with_seven_roles",
            "source_series_count": 21,
            "row_bounds_by_sample": [list(value) for value in bounds_by_sample],
        },
        "contract": contract.to_dict(),
    }


def _prepare_verified_xps_non_in_situ_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "XPS_non_in_situ":
        return {
            "ok": False,
            "message": "Verified XPS non-in-situ binding received a different product type.",
        }
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("xps_non_in_situ")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed XPS non-in-situ template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    raw_plot_formats = source_schema.get("plot_format_contracts")
    plot_format_contracts = (
        [dict(value) for value in raw_plot_formats if isinstance(value, dict)]
        if isinstance(raw_plot_formats, list)
        else []
    )
    if (
        str(source_schema.get("status") or "") != "ready"
        or str(source_schema.get("layout") or "")
        != "two_sample_shared_x_with_nine_roles"
        or str(source_schema.get("x_header") or "") != "binding_energy_eV"
        or str(source_schema.get("region_scope") or "") != "Bi 4f only"
        or source_schema.get("source_csv_indices") != list(range(19))
        or str(source_schema.get("worksheet_layout") or "")
        != "one_workbook_shared_x_eighteen_destination_columns"
        or list(source_schema.get("reviewed_vertical_offsets") or [])
        != list(VERIFIED_XPS_NON_IN_SITU_VERTICAL_OFFSETS)
        or str(source_schema.get("component_order") or "")
        != "source_workbook_order"
        or str(source_schema.get("plot_type") or "") != "line"
        or bool(source_schema.get("group_plots", True))
        or len(plot_format_contracts) != 18
    ):
        return {
            "ok": False,
            "message": "XPS non-in-situ contract must use the reviewed shared-X 19-column/18-plot layout.",
        }
    expected_fill_above = [
        30972633,
        1,
        1,
        25540850,
        1,
        1,
        1,
        1,
        1,
    ] * 2
    if any(
        int(value.get("layer_index", 0)) != 1
        or int(value.get("plot_index", 0)) != plot_index
        or int(value.get("fill_above_color", -1)) != expected_fill_above[plot_index - 1]
        for plot_index, value in enumerate(plot_format_contracts, start=1)
    ):
        return {
            "ok": False,
            "message": "XPS non-in-situ contract lacks the reviewed persistent component-fill colour sequence.",
        }
    if len(headers) != 19:
        return {
            "ok": False,
            "message": "XPS non-in-situ fixed OTPU requires shared X plus two complete nine-role sample groups.",
        }
    if re.search(
        r"\bBi\s*4f\b",
        str(product.graph_title),
        re.IGNORECASE,
    ) is None:
        return {
            "ok": False,
            "message": "The reviewed Bi 4f fixed template cannot be used for a non-Bi XPS region.",
        }
    source_pairs = [(0, source_y_index) for source_y_index in range(1, 19)]
    source_validation = _strict_adaptive_source_validation(
        contract,
        headers,
        rows,
        source_pairs,
    )
    if not source_validation.get("ok"):
        return {
            "ok": False,
            "message": str(
                source_validation.get("message")
                or "XPS non-in-situ fixed source binding is invalid."
            ),
            "source_binding": source_validation,
        }
    sample_identities = [
        str(headers[1 + sample_index * 9])[
            : -len(VERIFIED_XPS_NON_IN_SITU_ROLE_SUFFIXES[0])
        ]
        for sample_index in range(2)
    ]
    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [
        ("Book2_A", f"Book2_{chr(64 + y_col)}")
        for y_col in VERIFIED_XPS_NON_IN_SITU_DESTINATION_Y_COLUMNS
    ]
    if (
        len(contracted_plots) != 18
        or contract.source_series_count != 18
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != list(range(1, 19))
        or [plot.source_series_index for plot in contracted_plots]
        != list(range(1, 19))
        or [
            (str(plot.x_dataset), str(plot.y_dataset))
            for plot in contracted_plots
        ]
        != expected_datasets
    ):
        return {
            "ok": False,
            "message": "XPS non-in-situ contract must contain the reviewed ordered Book2 A/S 18-plot topology.",
        }
    bounds = [
        _paired_numeric_row_bounds(rows, 0, source_y_index)
        for source_y_index in range(1, 19)
    ]
    finite_bounds = [value for value in bounds if value is not None]
    if len(finite_bounds) != 18 or len(set(finite_bounds)) != 1:
        return {
            "ok": False,
            "message": "XPS non-in-situ fixed curves must share one contiguous finite row range.",
        }
    row_from, row_to = finite_bounds[0]
    xy_ranges = [
        {
            "book_name": "Book2",
            "sheet_index": 1,
            "layer_index": 1,
            "x_col": 1,
            "y_col": y_col,
            "row_from": row_from,
            "row_to": row_to,
            "source_x_index": 0,
            "source_y_index": source_y_index,
        }
        for y_col, source_y_index in zip(
            VERIFIED_XPS_NON_IN_SITU_DESTINATION_Y_COLUMNS,
            range(1, 19),
        )
    ]
    return {
        "ok": True,
        "message": "Processed XPS non-in-situ columns match the reviewed 18-role OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": "Book2",
        "plot_type": "line",
        "group_plots": False,
        "plot_format_contracts": plot_format_contracts,
        "xy_ranges": xy_ranges,
        "sample_identities": sample_identities,
        "source_binding": source_validation,
        "contract": contract.to_dict(),
    }


def _prepare_verified_bet_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "BET":
        return {
            "ok": False,
            "message": "Verified OTPU runtime dispatch is currently enabled only for BET.",
        }
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("bet")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed BET template binding contract is unavailable.",
        }
    source_pairs = _processed_csv_template_source_pairs(product, headers)
    source_validation = validate_template_source_bindings(
        contract,
        headers,
        source_pairs,
    )
    if not bool(source_validation.get("ok")):
        return {
            "ok": False,
            "message": str(
                source_validation.get("message")
                or "Processed BET source binding validation failed."
            ),
            "source_binding": source_validation,
            "contract": contract.to_dict(),
        }
    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    if any(plot.layer_index != 1 for plot in contracted_plots):
        return {
            "ok": False,
            "message": "Verified BET OTPU requires all contracted plots in layer 1.",
            "contract": contract.to_dict(),
        }

    xy_ranges: list[dict[str, int]] = []
    metadata_by_column: dict[int, dict[str, object]] = {}
    legend_entries = [str(value).strip() for value in product.legend_entries]
    source_schema = dict(contract.source_schema)
    x_suffix = str(source_schema.get("x_header_suffix") or "")
    for plot in contracted_plots:
        source_index = plot.source_series_index - 1
        x_index, y_index = source_pairs[source_index]
        row_bounds = _paired_numeric_row_bounds(rows, x_index, y_index)
        if row_bounds is None:
            return {
                "ok": False,
                "message": (
                    f"BET source series {plot.source_series_index} has no paired numeric X/Y rows."
                ),
                "source_binding": source_validation,
                "contract": contract.to_dict(),
            }
        row_from, row_to = row_bounds
        xy_ranges.append(
            {
                "x_col": x_index + 1,
                "y_col": y_index + 1,
                "row_from": row_from,
                "row_to": row_to,
            }
        )
        role_is_desorption = "desorption" in plot.semantic_role.casefold()
        x_long_name = (
            "Relative Pressure (P/Po)"
            if plot.plot_index <= 2
            else f"Relative Pressure ({'Desorption' if role_is_desorption else 'Adsorption'})"
        )
        metadata_by_column[x_index + 1] = {
            "column_index": x_index + 1,
            "long_name": x_long_name,
            "unit": "" if plot.plot_index <= 2 else "P/P0",
            "comment": "",
            "type": 4,
        }
        if plot.plot_index == 1:
            y_long_name = "Quantity Adsorbed"
        elif plot.plot_index == 2:
            y_long_name = "Quantity Desorption"
        else:
            fallback = str(headers[y_index])
            if x_suffix and fallback.endswith(str(source_schema.get("y_header_suffix") or "")):
                fallback = fallback[: -len(str(source_schema.get("y_header_suffix") or ""))]
            label = (
                legend_entries[source_index]
                if source_index < len(legend_entries) and legend_entries[source_index]
                else fallback.replace("_", " ").strip()
            )
            y_long_name = origin_bold_text(
                _bet_template_legend_label(
                    label or f"Series {plot.source_series_index}",
                    is_desorption=role_is_desorption,
                )
            )
        metadata_by_column[y_index + 1] = {
            "column_index": y_index + 1,
            "long_name": y_long_name,
            "unit": "cm3/g STP",
            "comment": "",
            "type": 1,
        }
    return {
        "ok": True,
        "message": "Processed BET columns match the reviewed OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": "Isotherm",
        "plot_type": "line+symbol",
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "column_metadata": [
            metadata_by_column[index] for index in sorted(metadata_by_column)
        ],
        "source_pairs": [list(pair) for pair in source_pairs],
        "source_binding": source_validation,
        "contract": contract.to_dict(),
    }


def _prepare_verified_eis_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "EIS":
        return {"ok": False, "message": "Verified EIS binding received a non-EIS product."}
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("eis")
    if contract is None or not contract.ready:
        return {"ok": False, "message": "The reviewed EIS binding contract is unavailable."}
    source_pairs = _processed_csv_template_source_pairs(product, headers)
    source_validation = validate_template_source_bindings(
        contract,
        headers,
        source_pairs,
    )
    if not bool(source_validation.get("ok")):
        return {
            "ok": False,
            "message": str(
                source_validation.get("message")
                or "Processed EIS source binding validation failed."
            ),
            "source_binding": source_validation,
        }
    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    if (
        len(contracted_plots) != 8
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != list(range(1, 9))
        or [plot.source_series_index for plot in contracted_plots] != list(range(1, 9))
    ):
        return {"ok": False, "message": "EIS contract must contain eight ordered layer-1 plots."}
    source_schema = dict(contract.source_schema)
    if (
        str(source_schema.get("worksheet_layout") or "")
        != "one_source_series_per_sheet"
        or bool(source_schema.get("group_plots", True))
    ):
        return {"ok": False, "message": "EIS contract must use eight ungrouped worksheets."}

    legend_entries = [str(value).strip() for value in product.legend_entries]
    visible_indices = REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]
    if len(legend_entries) == len(visible_indices):
        visible_legend_entries = legend_entries
    elif len(legend_entries) >= max(visible_indices):
        visible_legend_entries = [legend_entries[index - 1] for index in visible_indices]
    else:
        return {"ok": False, "message": "EIS requires current legend labels for slots 3-5."}
    if (
        any(not value for value in visible_legend_entries)
        or len({value.casefold() for value in visible_legend_entries})
        != len(visible_legend_entries)
    ):
        return {"ok": False, "message": "EIS slot-3-to-5 legend labels must be nonempty and unique."}

    xy_ranges: list[dict[str, int]] = []
    sheets: list[dict[str, object]] = []
    for plot in contracted_plots:
        source_index = plot.source_series_index - 1
        x_index, y_index = source_pairs[source_index]
        source_bounds = _paired_numeric_row_bounds(rows, x_index, y_index)
        if source_bounds is None:
            return {
                "ok": False,
                "message": (
                    f"EIS source series {plot.source_series_index} must contain one "
                    "contiguous run of finite X/Y rows."
                ),
            }
        source_row_from, source_row_to = source_bounds
        row_count = source_row_to - source_row_from + 1
        xy_ranges.append(
            {
                "x_col": 5,
                "y_col": 7,
                "row_from": 1,
                "row_to": row_count,
                "sheet_index": plot.source_series_index,
                "source_x_index": x_index,
                "source_y_index": y_index,
                "source_row_from": source_row_from,
                "source_row_to": source_row_to,
            }
        )
        sheets.append({
            "sheet_index": plot.source_series_index,
            "source_x_index": x_index,
            "source_y_index": y_index,
            "source_row_from": source_row_from,
            "source_row_to": source_row_to,
        })
    return {
        "ok": True,
        "message": "Processed EIS columns match the reviewed OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": "Book1",
        "plot_type": str(source_schema.get("plot_type") or "scatter"),
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "sheets": sheets,
        "visible_plot_indices": list(visible_indices),
        "visible_legend_entries": visible_legend_entries,
        "source_pairs": [list(pair) for pair in source_pairs],
        "source_binding": source_validation,
        "contract": contract.to_dict(),
    }


def _prepare_verified_epr_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "EPR":
        return {"ok": False, "message": "Verified EPR binding received a non-EPR product."}
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("epr")
    if contract is None or not contract.ready:
        return {"ok": False, "message": "The reviewed EPR template binding contract is unavailable."}
    source_schema = dict(contract.source_schema)
    if (
        str(source_schema.get("layout") or "") != "shared_x_y_columns"
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": "EPR contract must use one shared-X worksheet with ungrouped plots.",
        }
    expected_indices = [0, 1, 2, 3]
    contract_indices = source_schema.get("source_csv_indices", expected_indices)
    if not isinstance(contract_indices, list) or contract_indices != expected_indices:
        return {
            "ok": False,
            "message": "EPR contract must bind processed CSV columns 0/1,2,3.",
        }
    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    if (
        len(contracted_plots) != 3
        or contract.source_series_count != 3
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != [1, 2, 3]
        or [plot.source_series_index for plot in contracted_plots] != [1, 2, 3]
    ):
        return {"ok": False, "message": "EPR contract must contain three ordered layer-1 plots."}
    if len(headers) != 4 or any(not str(value).strip() for value in headers):
        return {
            "ok": False,
            "message": "EPR processed CSV must contain exactly one X column and three Y columns.",
        }
    if str(headers[0]).strip().casefold() != "magnetic_field":
        return {"ok": False, "message": "EPR shared X column must be magnetic_field."}
    legend_entries = [str(value).strip() for value in product.legend_entries]
    if (
        len(legend_entries) != 3
        or any(not value for value in legend_entries)
        or len({value.casefold() for value in legend_entries}) != 3
    ):
        return {"ok": False, "message": "EPR requires three nonempty unique current labels."}

    xy_ranges: list[dict[str, int]] = []
    source_bindings: list[dict[str, object]] = []
    expected_bounds: tuple[int, int] | None = None
    for plot in contracted_plots:
        source_y_index = plot.source_series_index
        bounds = _paired_numeric_row_bounds(rows, 0, source_y_index)
        if bounds is None:
            return {
                "ok": False,
                "message": f"EPR source trace {plot.source_series_index} must contain one contiguous finite X/Y run.",
            }
        if expected_bounds is None:
            expected_bounds = bounds
        elif bounds != expected_bounds:
            return {"ok": False, "message": "EPR shared-X traces must have identical finite row bounds."}
        row_from, row_to = bounds
        xy_ranges.append(
            {
                "x_col": 1,
                "y_col": 10 + plot.source_series_index,
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": 0,
                "source_y_index": source_y_index,
                "source_row_from": row_from,
                "source_row_to": row_to,
            }
        )
        source_bindings.append(
            {
                "source_series_index": plot.source_series_index,
                "source_x_column_index": 0,
                "source_y_column_index": source_y_index,
                "source_x_header": str(headers[0]),
                "source_y_header": str(headers[source_y_index]),
            }
        )
    return {
        "ok": True,
        "message": "Processed EPR shared-X columns match the reviewed OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": "EPR",
        "plot_type": str(source_schema.get("plot_type") or "line"),
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "source_binding": {
            "ok": True,
            "status": "ready",
            "layout": "shared_x_y_columns",
            "source_bindings": source_bindings,
        },
        "contract": contract.to_dict(),
    }


def _prepare_verified_pl_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "PL":
        return {"ok": False, "message": "Verified PL binding received a non-PL product."}
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("pl")
    if contract is None or not contract.ready:
        return {"ok": False, "message": "The reviewed PL template binding contract is unavailable."}
    source_schema = dict(contract.source_schema)
    if (
        str(source_schema.get("layout") or "") != "shared_x_y_columns"
        or bool(source_schema.get("group_plots", True))
        or source_schema.get("source_csv_indices", [0, 1, 2, 3]) != [0, 1, 2, 3]
    ):
        return {
            "ok": False,
            "message": "PL contract must use CSV columns 0/1,2,3 on one ungrouped shared-X worksheet.",
        }
    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [("A", "B"), ("A", "D"), ("A", "F")]
    actual_datasets = [
        (
            str(plot.x_dataset).rsplit("_", 1)[-1].upper(),
            str(plot.y_dataset).rsplit("_", 1)[-1].upper(),
        )
        for plot in contracted_plots
    ]
    if (
        len(contracted_plots) != 3
        or contract.source_series_count != 3
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != [1, 2, 3]
        or [plot.source_series_index for plot in contracted_plots] != [1, 2, 3]
        or actual_datasets != expected_datasets
    ):
        return {
            "ok": False,
            "message": "PL contract must contain ordered A-B, A-D, and A-F layer-1 plots.",
        }
    if (
        len(headers) != 4
        or str(headers[0]).strip().casefold() != "wavelength_nm"
        or not rows
    ):
        return {
            "ok": False,
            "message": "PL processed CSV must contain wavelength_nm and exactly three Y columns.",
        }
    legend_entries = [str(value).strip() for value in product.legend_entries]
    if (
        len(legend_entries) != 3
        or any(not value for value in legend_entries)
        or len({value.casefold() for value in legend_entries}) != 3
    ):
        return {"ok": False, "message": "PL requires three nonempty unique current labels."}
    expected_y_headers = [
        f"{safe_name(label)}_counts".casefold()
        for label in legend_entries
    ]
    if [str(value).strip().casefold() for value in headers[1:]] != expected_y_headers:
        return {
            "ok": False,
            "message": "PL Y headers must match the three current labels with the _counts suffix.",
        }

    destination_y_columns = (2, 4, 6)
    xy_ranges: list[dict[str, int]] = []
    for plot, y_col in zip(contracted_plots, destination_y_columns):
        source_y_index = plot.source_series_index
        bounds = _paired_numeric_row_bounds(rows, 0, source_y_index)
        if bounds is None:
            return {
                "ok": False,
                "message": f"PL source trace {source_y_index} must contain one contiguous finite X/Y run.",
            }
        row_from, row_to = bounds
        xy_ranges.append(
            {
                "x_col": 1,
                "y_col": y_col,
                "expected_x_col_letter": "A",
                "expected_y_col_letter": chr(64 + y_col),
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": 0,
                "source_y_index": source_y_index,
                "source_row_from": row_from,
                "source_row_to": row_to,
            }
        )
    return {
        "ok": True,
        "message": "Processed PL shared-X columns match the reviewed OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": "PL",
        "plot_type": str(source_schema.get("plot_type") or "line"),
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "contract": contract.to_dict(),
    }


def _prepare_verified_raman_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    """Bind three independent Raman X/Y pairs to the reviewed two-layer OTPU."""

    if product.product_key != "Raman":
        return {"ok": False, "message": "Verified Raman binding received a non-Raman product."}
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("raman")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed Raman template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    if (
        str(source_schema.get("status") or "") != "ready"
        or str(source_schema.get("layout") or "") != "paired_xy_columns"
        or str(source_schema.get("worksheet_layout") or "")
        != "one_sheet_three_independent_xy_pairs"
        or source_schema.get("source_csv_indices") != [0, 1, 2, 3, 4, 5]
        or str(source_schema.get("x_header_suffix") or "")
        != "_raman_shift_cm-1"
        or str(source_schema.get("y_header_suffix") or "") != "_intensity"
        or str(source_schema.get("transform") or "")
        != "independent_raman_xy_pairs_without_sorting_interpolation_smoothing_normalization_or_added_offsets"
        or str(source_schema.get("plot_type") or "") != "line"
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": (
                "Raman contract must define three independent adjacent X/Y pairs "
                "without interpolation or other numeric transformation."
            ),
        }

    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [
        ("Book2_A", "Book2_B"),
        ("Book2_E", "Book2_F"),
        ("Book2_C", "Book2_D"),
    ]
    if (
        len(contracted_plots) != 3
        or contract.source_series_count != 3
        or contract.graph_page != "Graph2"
        or [(plot.layer_index, plot.plot_index) for plot in contracted_plots]
        != [(1, 1), (1, 2), (2, 1)]
        or [plot.source_series_index for plot in contracted_plots] != [1, 3, 2]
        or [
            (str(plot.x_dataset), str(plot.y_dataset))
            for plot in contracted_plots
        ]
        != expected_datasets
    ):
        return {
            "ok": False,
            "message": (
                "Raman contract must bind Graph2 A/B, E/F, and C/D in the "
                "reviewed two-layer plot order while preserving source order 1/3/2."
            ),
        }
    if len(headers) != 6 or not rows:
        return {
            "ok": False,
            "message": "Raman processed CSV must contain exactly three adjacent X/Y pairs.",
        }
    source_pairs = _adjacent_independent_xy_pairs(
        headers,
        x_suffix="_raman_shift_cm-1",
        y_suffix="_intensity",
    )
    if source_pairs != [(1, 2), (3, 4), (5, 6)]:
        return {
            "ok": False,
            "message": "Raman processed CSV headers do not form three unique paired spectra.",
        }
    identities = [
        str(headers[index]).strip()[: -len("_raman_shift_cm-1")]
        for index in (0, 2, 4)
    ]
    labels = [str(value).strip() for value in product.legend_entries]
    if (
        len(labels) != 3
        or any(not value for value in labels)
        or [safe_name(value).casefold() for value in labels]
        != [value.casefold() for value in identities]
    ):
        return {
            "ok": False,
            "message": "Raman current labels must match the three processed paired-spectrum identities.",
        }

    xy_ranges: list[dict[str, object]] = []
    reference_books: set[str] = set()
    reference_sheets: set[int] = set()
    for plot in contracted_plots:
        x_reference = parse_origin_dataset_reference(str(plot.x_dataset))
        y_reference = parse_origin_dataset_reference(str(plot.y_dataset))
        if (
            x_reference is None
            or y_reference is None
            or x_reference.book_name != y_reference.book_name
            or x_reference.sheet_index != y_reference.sheet_index
        ):
            return {
                "ok": False,
                "message": "Raman contract contains an invalid same-sheet Origin X/Y mapping.",
            }
        reference_books.add(x_reference.book_name)
        reference_sheets.add(x_reference.sheet_index)
        source_x_index = (int(plot.source_series_index) - 1) * 2
        source_y_index = source_x_index + 1
        bounds = _paired_numeric_row_bounds(rows, source_x_index, source_y_index)
        if bounds is None or bounds[0] != 1:
            return {
                "ok": False,
                "message": (
                    f"Raman source series {plot.source_series_index} must contain one "
                    "contiguous finite X/Y run followed only by a blank tail."
                ),
            }
        row_from, row_to = bounds
        xy_ranges.append(
            {
                "book_name": x_reference.book_name,
                "sheet_index": x_reference.sheet_index,
                "layer_index": int(plot.layer_index),
                "x_col": x_reference.column_index + 1,
                "y_col": y_reference.column_index + 1,
                "expected_x_col_letter": chr(65 + x_reference.column_index),
                "expected_y_col_letter": chr(65 + y_reference.column_index),
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": source_x_index,
                "source_y_index": source_y_index,
                "source_row_from": row_from,
                "source_row_to": row_to,
            }
        )
    if reference_books != {"Book2"} or reference_sheets != {1}:
        return {
            "ok": False,
            "message": "Raman fixed template requires reviewed workbook Book2 sheet 1.",
        }
    return {
        "ok": True,
        "message": (
            "Processed Raman independent X/Y pairs match the reviewed two-layer OTPU binding contract."
        ),
        "graph_page": contract.graph_page,
        "book_name": "Book2",
        "plot_type": "line",
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "contract": contract.to_dict(),
    }


def _prepare_verified_mott_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "Mott-Schottky":
        return {
            "ok": False,
            "message": "Verified Mott-Schottky binding received a different product.",
        }
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("mott_schottky")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed Mott-Schottky template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    expected_source_indices = [0, 1, 2, 3, 4, 5]
    if (
        str(source_schema.get("layout") or "") != "shared_x_y_columns"
        or str(source_schema.get("x_header") or "") != "potential_v"
        or str(source_schema.get("y_header_suffix") or "")
        != "_one_over_c_squared"
        or source_schema.get("source_csv_indices") != expected_source_indices
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": (
                "Mott-Schottky contract must bind potential_v plus five Y columns "
                "as one ungrouped shared-X source table."
            ),
        }

    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [("E", "D"), ("E", "F"), ("G", "H"), ("I", "J"), ("K", "L")]
    actual_datasets = [
        (
            str(plot.x_dataset).rsplit("_", 1)[-1].upper(),
            str(plot.y_dataset).rsplit("_", 1)[-1].upper(),
        )
        for plot in contracted_plots
    ]
    if (
        len(contracted_plots) != 5
        or contract.source_series_count != 5
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != [1, 2, 3, 4, 5]
        or [plot.source_series_index for plot in contracted_plots] != [1, 2, 3, 4, 5]
        or actual_datasets != expected_datasets
    ):
        return {
            "ok": False,
            "message": (
                "Mott-Schottky contract must contain ordered layer-1 E-D, E-F, "
                "G-H, I-J, and K-L plots."
            ),
        }
    if len(headers) != 6 or not rows or str(headers[0]).strip() != "potential_v":
        return {
            "ok": False,
            "message": (
                "Mott-Schottky processed CSV must contain potential_v and exactly five Y columns."
            ),
        }
    y_headers = [str(value).strip() for value in headers[1:]]
    y_suffix = "_one_over_c_squared"
    identities = [
        value[: -len(y_suffix)] if value.endswith(y_suffix) else ""
        for value in y_headers
    ]
    if (
        any(not value for value in identities)
        or len({value.casefold() for value in identities}) != 5
    ):
        return {
            "ok": False,
            "message": (
                "Mott-Schottky Y headers must have five unique identities and the "
                "_one_over_c_squared suffix."
            ),
        }
    legend_entries = [str(value).strip() for value in product.legend_entries]
    if len(legend_entries) != 5 or any(not value for value in legend_entries):
        return {
            "ok": False,
            "message": (
                "Mott-Schottky fixed template requires one current legend label "
                "for each of its five bound source series."
            ),
        }

    reference_books: set[str] = set()
    reference_sheets: set[int] = set()
    for plot in contracted_plots:
        for dataset in (plot.x_dataset, plot.y_dataset):
            parsed = parse_origin_dataset_reference(dataset)
            if parsed is None:
                return {
                    "ok": False,
                    "message": (
                        "Mott-Schottky contract contains an unparseable Origin "
                        f"dataset reference: {dataset}"
                    ),
                }
            reference_books.add(parsed.book_name)
            reference_sheets.add(parsed.sheet_index)
    if len(reference_books) != 1 or reference_sheets != {1}:
        return {
            "ok": False,
            "message": (
                "Mott-Schottky fixed template requires one reviewed workbook "
                "and worksheet identity across all plots."
            ),
        }
    reference_book_name = next(iter(reference_books))

    xy_ranges: list[dict[str, object]] = []
    for fixed_index, (plot, (x_col, y_col)) in enumerate(zip(
        contracted_plots,
        VERIFIED_MOTT_DESTINATION_PAIRS,
    ), start=1):
        source_y_index = int(plot.source_series_index)
        bounds = _paired_numeric_row_bounds(rows, 0, source_y_index)
        if bounds is None:
            return {
                "ok": False,
                "message": (
                    f"Mott-Schottky source trace {source_y_index} must contain one "
                    "contiguous finite potential/Y run."
                ),
            }
        row_from, row_to = bounds
        expected_masked_rows = (
            [
                row_index
                for row_index in range(row_from, row_to + 1)
                if (x_value := _finite_numeric_value(rows[row_index - 1][0])) is not None
                and x_value < -1.0e-8
            ]
            if fixed_index <= 4
            else []
        )
        xy_ranges.append(
            {
                "x_col": x_col,
                "y_col": y_col,
                "book_name": reference_book_name,
                "sheet_index": 1,
                "layer_index": int(plot.layer_index),
                "expected_x_col_letter": chr(64 + x_col),
                "expected_y_col_letter": chr(64 + y_col),
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": 0,
                "source_y_index": source_y_index,
                "source_row_from": row_from,
                "source_row_to": row_to,
                "expected_y_masked_rows": expected_masked_rows,
            }
        )
    raw_plot_formats = source_schema.get("plot_format_contracts")
    plot_format_contracts = (
        [dict(value) for value in raw_plot_formats if isinstance(value, dict)]
        if isinstance(raw_plot_formats, list)
        else []
    )
    if len(plot_format_contracts) != 5 or any(
        int(value.get("connect", -1)) != 0 for value in plot_format_contracts
    ):
        return {
            "ok": False,
            "message": "Mott-Schottky contract must explicitly set connect=0 for all five plots.",
        }
    return {
        "ok": True,
        "message": (
            "Processed Mott-Schottky shared-X columns match the reviewed OTPU binding contract."
        ),
        "graph_page": contract.graph_page,
        "book_name": reference_book_name,
        "plot_type": str(source_schema.get("plot_type") or "line+symbol"),
        "group_plots": False,
        "page_mask_override": int(source_schema.get("page_mask_override", 0)),
        "plot_format_contracts": plot_format_contracts,
        "xy_ranges": xy_ranges,
        "contract": contract.to_dict(),
    }


def _validate_bet_axis_titles(
    snapshot: dict[str, object],
    headers: list[str],
) -> dict[str, object]:
    """Reject dynamic or worksheet-internal BET titles after save/reopen."""

    audit_strings = snapshot.get("audit_string_values")
    if not isinstance(audit_strings, dict):
        return {
            "ok": False,
            "message": "BET style readback does not contain axis-title text.",
            "x_title": "",
            "y_title": "",
        }
    x_title = str(audit_strings.get("xb.text$") or "").strip()
    y_title = str(audit_strings.get("yl.text$") or "").strip()
    folded_headers = {
        str(value).strip().casefold()
        for value in headers
        if str(value).strip()
    }
    internal_title = (
        x_title.casefold() in folded_headers
        or y_title.casefold() in folded_headers
        or any(
            fragment in value.casefold()
            for value in (x_title, y_title)
            for fragment in (
                "_relative_pressure_p_p0",
                "_quantity_adsorbed_cm3_g_stp",
            )
        )
    )
    dynamic_title = any("%(" in value or "%[" in value for value in (x_title, y_title))
    x_title_ok = VERIFIED_BET_X_TITLE.casefold() in x_title.casefold()
    y_title_ok = VERIFIED_BET_Y_TITLE.casefold() in y_title.casefold()
    reasons: list[str] = []
    if internal_title:
        reasons.append("an internal processed-data header was used as an axis title")
    if dynamic_title:
        reasons.append("a dynamic worksheet-title placeholder remains")
    if not x_title_ok:
        reasons.append(f"X title is not {VERIFIED_BET_X_TITLE!r}")
    if not y_title_ok:
        reasons.append(f"Y title is not {VERIFIED_BET_Y_TITLE!r}")
    return {
        "ok": not reasons,
        "message": (
            "BET axis titles match the reviewed Graph5 scientific titles."
            if not reasons
            else "BET axis-title hard gate failed: " + "; ".join(reasons)
        ),
        "x_title": x_title,
        "y_title": y_title,
        "internal_header_rejected": not internal_title,
        "dynamic_placeholder_rejected": not dynamic_title,
    }


def _validate_photocurrent_axis_titles(
    snapshot: dict[str, object],
    headers: list[str],
) -> dict[str, object]:
    """Require the reviewed scientific titles, never worksheet-derived text."""
    audit_strings = snapshot.get("audit_string_values")
    if not isinstance(audit_strings, dict):
        return {
            "ok": False,
            "message": "Photocurrent style readback does not contain axis-title text.",
            "x_title": "",
            "y_title": "",
        }
    x_title = str(audit_strings.get("xb.text$") or "").strip()
    y_title = str(audit_strings.get("yl.text$") or "").strip()
    normalized_headers = {
        str(value).strip().casefold()
        for value in headers
        if str(value).strip()
    }
    title_values = {x_title.casefold(), y_title.casefold()}
    internal_title = bool(title_values & normalized_headers) or any(
        fragment in value.casefold()
        for value in (x_title, y_title)
        for fragment in ("_time_s", "_current_a")
    )
    dynamic_title = any("%(" in value or "%[" in value for value in (x_title, y_title))
    placeholder_title = x_title.casefold() in {"a", "b"} or y_title.casefold() in {
        "a",
        "b",
    }
    x_title_ok = VERIFIED_PHOTOCURRENT_X_TITLE.casefold() in x_title.casefold()
    y_folded = y_title.casefold()
    y_unit_ok = any(
        marker in y_folded
        for marker in ("μa", "μ a", "a\\(41)", "microampere", "microamp")
    )
    y_title_ok = (
        "photocurrent" in y_folded
        and ("μ" in y_title or "micro" in y_folded)
        and y_unit_ok
    )
    reasons: list[str] = []
    if internal_title:
        reasons.append("an internal processed-data header was used as an axis title")
    if dynamic_title:
        reasons.append("a dynamic worksheet-title placeholder remains")
    if placeholder_title:
        reasons.append("the placeholder title A or B remains")
    if not x_title_ok:
        reasons.append(f"X title is not {VERIFIED_PHOTOCURRENT_X_TITLE!r}")
    if not y_title_ok:
        reasons.append("Y title is not the reviewed Photocurrent (μA) title")
    return {
        "ok": not reasons,
        "message": (
            "Photocurrent axis titles match the reviewed scientific title snapshot."
            if not reasons
            else "Photocurrent axis-title hard gate failed: " + "; ".join(reasons)
        ),
        "x_title": x_title,
        "y_title": y_title,
        "internal_header_rejected": not internal_title,
        "dynamic_placeholder_rejected": not dynamic_title,
        "a_b_placeholder_rejected": not placeholder_title,
    }


def _prepare_verified_photocurrent_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "photocurrent":
        return {
            "ok": False,
            "message": "Verified photocurrent binding received a non-photocurrent product.",
        }
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("photocurrent")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed photocurrent template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    if (
        str(source_schema.get("status") or "") != "ready"
        or str(source_schema.get("layout") or "") != "paired_xy_columns"
        or str(source_schema.get("worksheet_layout") or "")
        != "one_sheet_three_independent_xy_pairs_at_i_j_m_n_q_r"
        or source_schema.get("source_csv_indices") != [0, 1, 2, 3, 4, 5]
        or str(source_schema.get("x_header_suffix") or "") != "_time_s"
        or str(source_schema.get("y_header_suffix") or "") != "_current_a"
        or str(source_schema.get("transform") or "")
        != "independent_photocurrent_xy_pairs_without_interpolation_smoothing_or_normalization"
        or str(source_schema.get("plot_type") or "") != "line"
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": (
                "Photocurrent contract must use six adjacent independent X/Y columns "
                "as three ungrouped plots sourced from I/J, M/N, and Q/R."
            ),
        }

    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [
        ("Book1_I", "Book1_J"),
        ("Book1_M", "Book1_N"),
        ("Book1_Q", "Book1_R"),
    ]
    actual_datasets = [
        (str(plot.x_dataset), str(plot.y_dataset))
        for plot in contracted_plots
    ]
    if (
        len(contracted_plots) != 3
        or contract.source_series_count != 3
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != [1, 2, 3]
        or [plot.source_series_index for plot in contracted_plots] != [1, 2, 3]
        or actual_datasets != expected_datasets
    ):
        return {
            "ok": False,
            "message": (
                "Photocurrent contract must contain ordered Book1 I/J, M/N, and Q/R "
                "layer-1 plots."
            ),
        }

    legend_entries = [str(value).strip() for value in product.legend_entries]
    if (
        len(legend_entries) != 3
        or any(not value for value in legend_entries)
        or len({value.casefold() for value in legend_entries}) != 3
    ):
        return {
            "ok": False,
            "message": "Photocurrent requires three nonempty unique current labels.",
        }
    safe_labels = [safe_name(label) for label in legend_entries]
    if any(not value for value in safe_labels) or len(
        {value.casefold() for value in safe_labels}
    ) != 3:
        return {
            "ok": False,
            "message": (
                "Photocurrent current labels must remain unique after safe CSV header "
                "normalization."
            ),
        }
    expected_headers = [
        header
        for label in safe_labels
        for header in (
            f"{label}_time_s",
            f"{label}_current_a",
        )
    ]
    if (
        len(headers) != 6
        or [str(value).strip() for value in headers] != expected_headers
        or not rows
        or any(len(row) != 6 for row in rows)
    ):
        return {
            "ok": False,
            "message": (
                "Photocurrent processed CSV must contain exactly the six contracted "
                "current-label X/Y columns."
            ),
        }

    xy_ranges: list[dict[str, int]] = []
    for pair_index, (x_index, y_index) in enumerate(((0, 1), (2, 3), (4, 5))):
        for row in rows:
            x_value = _finite_numeric_value(row[x_index])
            y_value = _finite_numeric_value(row[y_index])
            if (x_value is None) != (y_value is None):
                return {
                    "ok": False,
                    "message": (
                        f"Photocurrent source pair {pair_index + 1} contains an "
                        "unpaired X or Y value."
                    ),
                }
        bounds = _paired_numeric_row_bounds(rows, x_index, y_index)
        if bounds is None or bounds[0] != 1:
            return {
                "ok": False,
                "message": (
                    f"Photocurrent source pair {pair_index + 1} must contain one "
                    "contiguous finite run followed only by blank tail rows."
                ),
            }
        row_from, row_to = bounds
        x_col, y_col = VERIFIED_PHOTOCURRENT_DESTINATION_PAIRS[pair_index]
        xy_ranges.append(
            {
                "x_col": x_col,
                "y_col": y_col,
                "expected_x_col_letter": chr(64 + x_col),
                "expected_y_col_letter": chr(64 + y_col),
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": x_index,
                "source_y_index": y_index,
                "source_row_from": row_from,
                "source_row_to": row_to,
            }
        )
    return {
        "ok": True,
        "message": (
            "Processed photocurrent independent X/Y pairs match the reviewed OTPU "
            "I/J, M/N, and Q/R binding contract with current per-pair row bounds."
        ),
        "graph_page": contract.graph_page,
        "book_name": "Book1",
        "plot_type": str(source_schema.get("plot_type") or "line"),
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "contract": contract.to_dict(),
    }


def _prepare_verified_ftir_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    if product.product_key != "FTIR":
        return {"ok": False, "message": "Verified FTIR binding received a non-FTIR product."}
    contracts = load_template_binding_contracts(contract_path)
    contract = contracts.get("ftir")
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": "The reviewed FTIR template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    raw_offsets = source_schema.get("raw_to_plotted_vertical_offsets")
    annotation_offsets = source_schema.get("last_origin_curve_translate_annotations")
    contract_labels = source_schema.get("source_series_labels")
    raw_offsets_match = (
        isinstance(raw_offsets, list)
        and tuple(raw_offsets) == VERIFIED_FTIR_RAW_TO_PLOTTED_OFFSETS
    )
    if (
        str(source_schema.get("status") or "") != "ready"
        or str(source_schema.get("layout") or "") != "paired_xy_columns"
        or str(source_schema.get("worksheet_layout") or "")
        != "one_sheet_three_independent_xy_pairs_with_reserved_cd"
        or source_schema.get("source_csv_indices") != [0, 1, 2, 3, 4, 5]
        or str(source_schema.get("x_header_suffix") or "") != "_wavenumber_cm-1"
        or str(source_schema.get("y_header_suffix") or "") != "_transmittance"
        or str(source_schema.get("transform") or "")
        != "independent_ftir_xy_pairs_with_explicit_reference_vertical_offsets_without_interpolation_smoothing_or_normalization"
        or not raw_offsets_match
    ):
        return {
            "ok": False,
            "message": (
                "FTIR contract must define the reviewed independent paired-XY layout "
                "and exact raw-to-plotted net offsets."
            ),
        }
    if (
        not isinstance(annotation_offsets, list)
        or tuple(annotation_offsets) != VERIFIED_FTIR_LAST_CURVE_TRANSLATE_ANNOTATIONS
        or not isinstance(contract_labels, list)
        or tuple(str(value) for value in contract_labels) != VERIFIED_FTIR_SERIES_LABELS
        or str(source_schema.get("plot_type") or "") != "line"
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": (
                "FTIR contract must preserve the reviewed curve-translate annotations, "
                "fixed series labels, and ungrouped line policy."
            ),
        }

    contracted_plots = sorted(
        contract.plots,
        key=lambda plot: (plot.layer_index, plot.plot_index),
    )
    expected_datasets = [
        ("Book2_A", "Book2_B"),
        ("Book2_E", "Book2_F"),
        ("Book2_G", "Book2_H"),
    ]
    actual_datasets = [
        (str(plot.x_dataset), str(plot.y_dataset))
        for plot in contracted_plots
    ]
    if (
        len(contracted_plots) != 3
        or contract.source_series_count != 3
        or contract.graph_page != "Graph3"
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots] != [1, 2, 3]
        or [plot.source_series_index for plot in contracted_plots] != [1, 2, 3]
        or actual_datasets != expected_datasets
    ):
        return {
            "ok": False,
            "message": "FTIR contract must contain ordered Book2 A/B, E/F, and G/H Graph3 plots.",
        }

    labels = tuple(str(value).strip() for value in product.legend_entries)
    if labels != VERIFIED_FTIR_SERIES_LABELS:
        return {
            "ok": False,
            "message": "FTIR current labels must exactly match the reviewed three-series order.",
        }
    expected_headers = [
        header
        for label in labels
        for header in (
            f"{safe_name(label)}_wavenumber_cm-1",
            f"{safe_name(label)}_transmittance",
        )
    ]
    if (
        len(headers) != 6
        or [str(value).strip() for value in headers] != expected_headers
        or not rows
        or any(len(row) != 6 for row in rows)
    ):
        return {
            "ok": False,
            "message": "FTIR processed CSV must contain exactly the six contracted final plotted X/Y columns.",
        }

    destination_pairs = ((1, 2), (5, 6), (7, 8))
    xy_ranges: list[dict[str, int]] = []
    for pair_index, ((source_x, source_y), (x_col, y_col)) in enumerate(
        zip(((0, 1), (2, 3), (4, 5)), destination_pairs),
        start=1,
    ):
        for row in rows:
            x_value = _finite_numeric_value(row[source_x])
            y_value = _finite_numeric_value(row[source_y])
            if (x_value is None) != (y_value is None):
                return {
                    "ok": False,
                    "message": f"FTIR source pair {pair_index} contains an unpaired X or Y value.",
                }
        bounds = _paired_numeric_row_bounds(rows, source_x, source_y)
        if bounds is None or bounds[0] != 1:
            return {
                "ok": False,
                "message": (
                    f"FTIR source pair {pair_index} must contain one contiguous finite run "
                    "followed only by blank tail rows."
                ),
            }
        row_from, row_to = bounds
        xy_ranges.append(
            {
                "x_col": x_col,
                "y_col": y_col,
                "expected_x_col_letter": chr(64 + x_col),
                "expected_y_col_letter": chr(64 + y_col),
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": source_x,
                "source_y_index": source_y,
                "source_row_from": row_from,
                "source_row_to": row_to,
            }
        )
    return {
        "ok": True,
        "message": "Processed FTIR final plotted X/Y pairs match the reviewed OTPU binding contract.",
        "graph_page": "Graph3",
        "book_name": "Book2",
        "plot_type": "line",
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "raw_to_plotted_vertical_offsets": list(VERIFIED_FTIR_RAW_TO_PLOTTED_OFFSETS),
        "last_origin_curve_translate_annotations": list(
            VERIFIED_FTIR_LAST_CURVE_TRANSLATE_ANNOTATIONS
        ),
        "reserved_columns": [3, 4],
        "contract": contract.to_dict(),
    }


def _prepare_verified_uvvis_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
    """Bind explicit DRS or Tauc pairs to the reviewed detached graph page."""

    if product.product_key not in {"UV-vis DRS", "Tauc"}:
        return {"ok": False, "message": "UV-vis OTPU binding received a different product."}
    contracts = load_template_binding_contracts(contract_path)
    contract_key = "uv_vis_drs" if product.product_key == "UV-vis DRS" else "tauc"
    contract = contracts.get(contract_key)
    if contract is None or not contract.ready:
        return {
            "ok": False,
            "message": f"The reviewed {product.product_key} template binding contract is unavailable.",
        }
    source_schema = dict(contract.source_schema)
    expected_x_suffix = "_wavelength_nm" if product.product_key == "UV-vis DRS" else "_photon_energy_eV"
    expected_y_suffix = "_drs_signal" if product.product_key == "UV-vis DRS" else "_tauc_y_direct_candidate"
    if (
        str(source_schema.get("status") or "") != "ready"
        or str(source_schema.get("layout") or "") != "paired_xy_columns"
        or str(source_schema.get("x_header_suffix") or "") != expected_x_suffix
        or str(source_schema.get("y_header_suffix") or "") != expected_y_suffix
        or str(source_schema.get("plot_type") or "") != "line"
        or bool(source_schema.get("group_plots", True))
    ):
        return {
            "ok": False,
            "message": (
                f"{product.product_key} contract must define ungrouped adjacent X/Y pairs "
                "using the current processor-output header suffixes."
            ),
        }
    source_pairs = _adjacent_independent_xy_pairs(
        headers,
        x_suffix=expected_x_suffix,
        y_suffix=expected_y_suffix,
    )
    if len(source_pairs) != contract.source_series_count or not rows:
        return {
            "ok": False,
            "message": (
                f"{product.product_key} processed CSV must contain exactly "
                f"{contract.source_series_count} contracted adjacent X/Y pairs."
            ),
        }
    contracted_plots = sorted(contract.plots, key=lambda plot: (plot.layer_index, plot.plot_index))
    if (
        len(contracted_plots) != contract.source_series_count
        or any(plot.layer_index != 1 for plot in contracted_plots)
        or [plot.plot_index for plot in contracted_plots]
        != list(range(1, contract.source_series_count + 1))
        or sorted(plot.source_series_index for plot in contracted_plots)
        != list(range(1, contract.source_series_count + 1))
    ):
        return {
            "ok": False,
            "message": f"{product.product_key} contract plot/source indices are incomplete or ambiguous.",
        }
    identities = [
        str(headers[x_index - 1]).strip()[: -len(expected_x_suffix)]
        for x_index, _y_index in source_pairs
    ]
    labels = [str(value).strip() for value in product.legend_entries]
    expected_identities = [
        str(value).strip()
        for value in source_schema.get("source_identities", [])
    ]
    expected_labels = [
        str(value).strip()
        for value in source_schema.get("source_legend_entries", [])
    ]
    if (
        len(expected_identities) != contract.source_series_count
        or len(expected_labels) != contract.source_series_count
        or [value.casefold() for value in identities]
        != [value.casefold() for value in expected_identities]
        or len(labels) != len(expected_labels)
        or [value.casefold() for value in labels]
        != [value.casefold() for value in expected_labels]
    ):
        return {
            "ok": False,
            "message": (
                f"{product.product_key} fixed OTPU requires the reviewed hidden/visible source roles "
                "and legend sequence; ordinary current spectra must use adaptive OTH+JSON."
            ),
        }

    reference_books: set[str] = set()
    reference_sheets: set[int] = set()
    xy_ranges: list[dict[str, object]] = []
    for plot in contracted_plots:
        x_reference = parse_origin_dataset_reference(str(plot.x_dataset))
        y_reference = parse_origin_dataset_reference(str(plot.y_dataset))
        if (
            x_reference is None
            or y_reference is None
            or x_reference.book_name != y_reference.book_name
            or x_reference.sheet_index != y_reference.sheet_index
        ):
            return {
                "ok": False,
                "message": f"{product.product_key} contract contains an invalid same-sheet X/Y mapping.",
            }
        reference_books.add(x_reference.book_name)
        reference_sheets.add(x_reference.sheet_index)
        source_x_index, source_y_index = source_pairs[plot.source_series_index - 1]
        source_x_index -= 1
        source_y_index -= 1
        bounds = _paired_numeric_row_bounds(rows, source_x_index, source_y_index)
        if bounds is None or bounds[0] != 1:
            return {
                "ok": False,
                "message": (
                    f"{product.product_key} source series {plot.source_series_index} must contain "
                    "one contiguous finite X/Y run followed only by a blank tail."
                ),
            }
        row_from, row_to = bounds
        xy_ranges.append(
            {
                "book_name": x_reference.book_name,
                "sheet_index": x_reference.sheet_index,
                "layer_index": int(plot.layer_index),
                "x_col": x_reference.column_index + 1,
                "y_col": y_reference.column_index + 1,
                "expected_x_col_letter": chr(65 + x_reference.column_index),
                "expected_y_col_letter": chr(65 + y_reference.column_index),
                "row_from": row_from,
                "row_to": row_to,
                "source_x_index": source_x_index,
                "source_y_index": source_y_index,
                "source_row_from": row_from,
                "source_row_to": row_to,
            }
        )
    if len(reference_books) != 1 or reference_sheets != {1}:
        return {
            "ok": False,
            "message": f"{product.product_key} fixed template requires one reviewed workbook and worksheet.",
        }
    return {
        "ok": True,
        "message": f"Processed {product.product_key} X/Y pairs match the reviewed OTPU binding contract.",
        "graph_page": contract.graph_page,
        "book_name": next(iter(reference_books)),
        "plot_type": "line",
        "group_plots": False,
        "xy_ranges": xy_ranges,
        "contract": contract.to_dict(),
    }


def _transform_verified_xps_in_situ_rows(
    headers: list[str],
    rows: list[list[object]],
    binding: dict[str, object],
) -> dict[str, object]:
    raw_workbooks = binding.get("workbooks")
    source_binding = binding.get("source_binding")
    if (
        len(headers) != 24
        or not isinstance(raw_workbooks, list)
        or len(raw_workbooks) != 3
        or not isinstance(source_binding, dict)
    ):
        return {
            "ok": False,
            "message": "XPS in-situ reviewed normalization received an incomplete fixed binding.",
        }
    raw_bounds = source_binding.get("row_bounds_by_sample")
    if not isinstance(raw_bounds, list) or len(raw_bounds) != 3:
        return {
            "ok": False,
            "message": "XPS in-situ reviewed normalization received invalid finite row bounds.",
        }
    transformed_rows = [list(row) for row in rows]
    transformations: list[dict[str, object]] = []
    for sample_index, raw_workbook in enumerate(raw_workbooks):
        if not isinstance(raw_workbook, dict):
            return {"ok": False, "message": "XPS in-situ normalization binding is malformed."}
        measured_index = int(raw_workbook.get("normalization_source_index") or 0)
        target_offset = _finite_numeric_value(raw_workbook.get("reviewed_vertical_offset"))
        expected_offset = XPS_IN_SITU_REVIEWED_VERTICAL_OFFSETS[sample_index]
        first_role_index = sample_index * 8 + 1
        if measured_index != first_role_index or target_offset != expected_offset:
            return {
                "ok": False,
                "message": "XPS in-situ normalization binding does not match the reviewed sample offsets.",
            }
        sample_bounds = raw_bounds[sample_index]
        if not isinstance(sample_bounds, list) or len(sample_bounds) != 2:
            return {
                "ok": False,
                "message": "XPS in-situ normalization binding has malformed sample row bounds.",
            }
        row_from, row_to = (int(sample_bounds[0]), int(sample_bounds[1]))
        if row_from < 1 or row_to < row_from or row_to > len(rows):
            return {
                "ok": False,
                "message": "XPS in-situ reviewed normalization received invalid sample row bounds.",
            }
        measured_values = [
            _finite_numeric_value(rows[row_index][measured_index])
            for row_index in range(row_from - 1, row_to)
        ]
        if any(value is None for value in measured_values):
            return {
                "ok": False,
                "message": f"XPS in-situ sample group {sample_index + 1} measured curve is incomplete.",
            }
        finite_measured = [float(value) for value in measured_values if value is not None]
        minimum = min(finite_measured)
        span = max(finite_measured) - minimum
        if not math.isfinite(span) or span <= 0:
            return {
                "ok": False,
                "message": f"XPS in-situ sample group {sample_index + 1} measured curve has no finite intensity span.",
            }
        if minimum == expected_offset and math.isclose(
            span,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            transformations.append(
                {
                    "sample_identity": str(raw_workbook.get("sample_identity") or ""),
                    "source_measured_index": measured_index,
                    "source_minimum": minimum,
                    "source_span": span,
                    "reviewed_vertical_offset": expected_offset,
                    "method": "already_normalized_with_reviewed_offset",
                }
            )
            continue
        for row_index in range(row_from - 1, row_to):
            for source_index in range(first_role_index, first_role_index + 7):
                value = _finite_numeric_value(rows[row_index][source_index])
                if value is None:
                    return {
                        "ok": False,
                        "message": (
                            f"XPS in-situ sample group {sample_index + 1} role column "
                            f"{source_index + 1} is incomplete within the reviewed row range."
                        ),
                    }
                transformed_rows[row_index][source_index] = (
                    (value - minimum) / span + expected_offset
                )
        transformations.append(
            {
                "sample_identity": str(raw_workbook.get("sample_identity") or ""),
                "source_measured_index": measured_index,
                "source_minimum": minimum,
                "source_span": span,
                "reviewed_vertical_offset": expected_offset,
                "method": "minmax_normalized_with_reviewed_offset",
            }
        )
    return {
        "ok": True,
        "message": "XPS in-situ curves were min-max normalized with reviewed vertical offsets without interpolation, smoothing, or refitting.",
        "rows": transformed_rows,
        "transformations": transformations,
    }


def _populate_verified_otpu_workbook(
    operations: object,
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    binding: dict[str, object],
) -> dict[str, object]:
    if product.product_key == "XPS_in_situ":
        raw_workbooks = binding.get("workbooks")
        if not isinstance(raw_workbooks, list) or len(raw_workbooks) != 3:
            return {
                "ok": False,
                "message": "XPS in-situ workbook adapter requires exactly three reviewed workbooks.",
            }
        transformed = _transform_verified_xps_in_situ_rows(headers, rows, binding)
        if not transformed.get("ok"):
            return transformed
        # The transform already owns a new table; writing it and constructing
        # Origin columns do not mutate those rows.
        transformed_rows = transformed["rows"]
        if len(transformed_rows) != len(rows):
            return {
                "ok": False,
                "message": "XPS in-situ reviewed normalization did not preserve the source row count.",
            }
        _write_processed_csv(product.processed_data, headers, transformed_rows)
        created_books: list[str] = []
        for raw_workbook in raw_workbooks:
            if not isinstance(raw_workbook, dict):
                return {"ok": False, "message": "XPS in-situ workbook binding is malformed."}
            requested_book = str(raw_workbook.get("book_name") or "")
            sheet_name = str(raw_workbook.get("sheet_name") or "Sheet1")
            source_indices = raw_workbook.get("source_indices")
            if (
                requested_book not in VERIFIED_XPS_IN_SITU_BOOKS
                or not isinstance(source_indices, list)
                or len(source_indices) != 6
            ):
                return {
                    "ok": False,
                    "message": "XPS in-situ workbook binding lacks its reviewed six destination roles.",
                }
            created = operations.create_worksheet(requested_book, sheet_name)
            if not getattr(created, "ok", False):
                return _verified_otpu_failure(
                    created,
                    f"XPS in-situ workbook {requested_book} creation failed.",
                )
            actual_book = str(getattr(created, "payload", {}).get("book_name") or "")
            actual_sheet = str(
                getattr(created, "payload", {}).get("sheet_name") or sheet_name
            )
            if actual_book != requested_book:
                return {
                    "ok": False,
                    "message": (
                        f"Origin did not preserve reviewed XPS workbook identity {requested_book}; "
                        f"actual name was {actual_book or '<empty>'}."
                    ),
                }
            columns: list[list[float]] = []
            for raw_source_index in source_indices:
                source_index = int(raw_source_index)
                columns.append(
                    [
                        float(value)
                        if source_index < len(row)
                        and (value := _finite_numeric_value(row[source_index])) is not None
                        else math.nan
                        for row in transformed_rows
                    ]
                )
            written = operations.set_worksheet_data(
                actual_book,
                actual_sheet,
                columns,
            )
            if not getattr(written, "ok", False):
                return _verified_otpu_failure(
                    written,
                    f"XPS in-situ workbook {requested_book} data write failed.",
                )
            metadata = [
                {
                    "column_index": destination_index,
                    "long_name": headers[int(source_index)],
                    "unit": "eV" if destination_index == 1 else "a.u.",
                    "comment": str(raw_workbook.get("sample_identity") or ""),
                    "type": 4 if destination_index == 1 else 1,
                }
                for destination_index, source_index in enumerate(source_indices, start=1)
            ]
            metadata_write = operations.set_worksheet_column_metadata(
                actual_book,
                metadata,
            )
            if not getattr(metadata_write, "ok", False):
                return _verified_otpu_failure(
                    metadata_write,
                    f"XPS in-situ workbook {requested_book} metadata write failed.",
                )
            created_books.append(actual_book)
        return {
            "ok": True,
            "method": "xps_in_situ_three_native_shared_x_six_column_workbooks",
            "book_name": created_books[0],
            "book_names": created_books,
            "sheet_count": 3,
            "destination_columns_per_book": 6,
            "origin_processing": {
                "required": True,
                "applied": True,
                "processing_location": "Current-data normalization before native Origin workbook/graph creation",
                "processing_kind": "xps_minmax_normalize_reviewed_vertical_stack_high_binding_component_first",
                "reviewed_vertical_offsets": list(XPS_IN_SITU_REVIEWED_VERTICAL_OFFSETS),
                "component_order": "higher_binding_energy_peak_first",
                "interpolation": "not_applied",
                "smoothing": "not_applied",
                "refitting": "not_applied",
            },
        }

    if product.product_key == "XPS_non_in_situ":
        imported = operations.import_csv_to_worksheet(
            product.processed_data,
            book_name=str(binding["book_name"]),
        )
        if not getattr(imported, "ok", False):
            return _verified_otpu_failure(
                imported,
                "Processed XPS non-in-situ CSV import failed.",
            )
        book_name = str(getattr(imported, "payload", {}).get("book_name") or "")
        if book_name != str(binding["book_name"]):
            return {
                "ok": False,
                "message": (
                    "Origin did not preserve the reviewed XPS non-in-situ workbook identity: "
                    f"expected {binding['book_name']}, actual {book_name or '<empty>'}."
                ),
            }
        metadata_write = operations.set_worksheet_column_metadata(
            book_name,
            [
                {
                    "column_index": column_index,
                    "long_name": header,
                    "unit": "eV" if column_index == 1 else "a.u.",
                    "comment": "",
                    "type": 4 if column_index == 1 else 1,
                }
                for column_index, header in enumerate(headers, start=1)
            ],
        )
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(
                metadata_write,
                "XPS non-in-situ worksheet metadata write failed.",
            )
        return {
            "ok": True,
            "method": "xps_non_in_situ_shared_x_eighteen_role_native_workbook",
            "book_name": book_name,
            "sheet_count": 1,
            "destination_column_count": 19,
            "origin_processing": {
                "required": True,
                "applied": True,
                "processing_location": "Processed current-data CSV before native Origin graph creation",
                "processing_kind": "xps_common_raw_intensity_scale_with_reviewed_vertical_offsets",
                "reviewed_vertical_offsets": list(
                    VERIFIED_XPS_NON_IN_SITU_VERTICAL_OFFSETS
                ),
                "component_order": "source_workbook_order",
                "interpolation": "not_applied",
                "smoothing": "not_applied",
                "refitting": "not_applied",
            },
        }

    if product.product_key == "BET":
        imported = operations.import_csv_to_worksheet(
            product.processed_data,
            book_name=str(binding["book_name"]),
        )
        if not getattr(imported, "ok", False):
            return _verified_otpu_failure(imported, "Processed BET CSV import failed.")
        book_name = str(getattr(imported, "payload", {}).get("book_name") or "")
        metadata_write = operations.set_worksheet_column_metadata(
            book_name,
            list(binding["column_metadata"]),
        )
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(metadata_write, "BET worksheet metadata write failed.")
        return {
            "ok": True,
            "method": "processed_csv_single_sheet_import",
            "book_name": book_name,
            "sheet_count": 1,
        }

    if product.product_key in {"UV-vis DRS", "Tauc"}:
        created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(created, f"{product.product_key} workbook creation failed.")
        book_name = str(getattr(created, "payload", {}).get("book_name") or "")
        sheet_name = str(getattr(created, "payload", {}).get("sheet_name") or "Sheet1")
        if book_name != str(binding["book_name"]):
            return {
                "ok": False,
                "message": (
                    f"Origin did not preserve the reviewed {product.product_key} workbook identity: "
                    f"expected {binding['book_name']}, actual {book_name or '<empty>'}."
                ),
            }
        xy_ranges = [dict(value) for value in binding.get("xy_ranges", []) if isinstance(value, dict)]
        destination_count = max(
            (max(int(value["x_col"]), int(value["y_col"])) for value in xy_ranges),
            default=0,
        )
        if destination_count <= 0:
            return {"ok": False, "message": f"{product.product_key} destination columns are unavailable."}
        columns = [[math.nan] * len(rows) for _index in range(destination_count)]
        metadata: list[dict[str, object]] = []
        for plot_index, value in enumerate(xy_ranges, start=1):
            x_col = int(value["x_col"])
            y_col = int(value["y_col"])
            source_x_index = int(value["source_x_index"])
            source_y_index = int(value["source_y_index"])
            columns[x_col - 1] = [
                float(current)
                if source_x_index < len(row)
                and (current := _finite_numeric_value(row[source_x_index])) is not None
                else math.nan
                for row in rows
            ]
            columns[y_col - 1] = [
                float(current)
                if source_y_index < len(row)
                and (current := _finite_numeric_value(row[source_y_index])) is not None
                else math.nan
                for row in rows
            ]
            metadata.extend(
                (
                    {
                        "column_index": x_col,
                        "long_name": headers[source_x_index],
                        "unit": "nm" if product.product_key == "UV-vis DRS" else "eV",
                        "comment": "",
                        "type": 4,
                    },
                    {
                        "column_index": y_col,
                        "long_name": headers[source_y_index],
                        "unit": "a.u.",
                        "comment": "",
                        "type": 1,
                    },
                )
            )
        written = operations.set_worksheet_data(book_name, sheet_name, columns)
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(written, f"{product.product_key} worksheet data write failed.")
        metadata_write = operations.set_worksheet_column_metadata(book_name, metadata)
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(metadata_write, f"{product.product_key} worksheet metadata write failed.")
        return {
            "ok": True,
            "method": "uvvis_explicit_processor_xy_pairs_to_reviewed_sparse_columns",
            "book_name": book_name,
            "sheet_count": 1,
            "destination_column_count": destination_count,
        }

    if product.product_key == "EPR":
        processed = _prepare_template_epr_origin_processed_workbook(operations, product)
        if not processed.get("ok"):
            return {
                "ok": False,
                "message": str(processed.get("message") or "EPR Origin processing failed."),
            }
        processed_headers = [str(value) for value in processed.get("headers", [])]
        if processed_headers != ["magnetic_field", *[str(value).strip() for value in product.legend_entries]]:
            return {
                "ok": False,
                "message": "EPR Origin processing did not produce the contracted current-label CSV.",
            }
        return {
            "ok": True,
            "method": "shared_epr_origin_baseline_aav7_offset_transform",
            "book_name": str(processed["book_name"]),
            "sheet_count": 1,
            "origin_processing": dict(processed["origin_processing"]),
        }

    if product.product_key == "PL":
        created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(created, "PL workbook creation failed.")
        book_name = str(getattr(created, "payload", {}).get("book_name") or "")
        sheet_name = str(getattr(created, "payload", {}).get("sheet_name") or "Sheet1")
        if not book_name:
            return {"ok": False, "message": "Origin did not return the PL workbook name."}
        columns = [[math.nan] * len(rows) for _index in range(6)]
        columns[0] = [
            float(value) if (value := _finite_numeric_value(row[0])) is not None else math.nan
            for row in rows
        ]
        for source_index, destination_index in zip((1, 2, 3), (1, 3, 5)):
            columns[destination_index] = [
                float(value)
                if source_index < len(row)
                and (value := _finite_numeric_value(row[source_index])) is not None
                else math.nan
                for row in rows
            ]
        written = operations.set_worksheet_data(book_name, sheet_name, columns)
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(written, "PL worksheet data write failed.")
        metadata_write = operations.set_worksheet_column_metadata(
            book_name,
            [
                {"column_index": 1, "long_name": headers[0], "unit": "nm", "comment": "", "type": 4},
                {"column_index": 2, "long_name": headers[1], "unit": "counts", "comment": "", "type": 1},
                {"column_index": 4, "long_name": headers[2], "unit": "counts", "comment": "", "type": 1},
                {"column_index": 6, "long_name": headers[3], "unit": "counts", "comment": "", "type": 1},
            ],
        )
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(metadata_write, "PL worksheet metadata write failed.")
        return {
            "ok": True,
            "method": "pl_shared_x_explicit_a_b_d_f_copy",
            "book_name": book_name,
            "sheet_count": 1,
        }

    if product.product_key == "Raman":
        created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(created, "Raman workbook creation failed.")
        book_name = str(getattr(created, "payload", {}).get("book_name") or "")
        sheet_name = str(getattr(created, "payload", {}).get("sheet_name") or "Sheet1")
        if book_name != "Book2":
            return {
                "ok": False,
                "message": (
                    "Origin did not preserve the reviewed Raman workbook identity: "
                    f"expected Book2, actual {book_name or '<empty>'}."
                ),
            }
        columns = [
            [
                float(value)
                if source_index < len(row)
                and (value := _finite_numeric_value(row[source_index])) is not None
                else math.nan
                for row in rows
            ]
            for source_index in range(6)
        ]
        written = operations.set_worksheet_data(book_name, sheet_name, columns)
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(written, "Raman worksheet data write failed.")
        metadata = [
            {
                "column_index": column_index,
                "long_name": headers[column_index - 1],
                "unit": "cm^-1" if column_index % 2 else "a.u.",
                "comment": "",
                "type": 4 if column_index % 2 else 1,
            }
            for column_index in range(1, 7)
        ]
        metadata_write = operations.set_worksheet_column_metadata(book_name, metadata)
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(metadata_write, "Raman worksheet metadata write failed.")
        return {
            "ok": True,
            "method": "raman_independent_a_b_c_d_e_f_copy_without_numeric_transform",
            "book_name": book_name,
            "sheet_count": 1,
            "destination_pairs": [
                {"x_col": x_col, "y_col": y_col}
                for x_col, y_col in VERIFIED_RAMAN_DESTINATION_PAIRS
            ],
        }

    if product.product_key == "FTIR":
        created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(created, "FTIR workbook creation failed.")
        book_name = str(getattr(created, "payload", {}).get("book_name") or "")
        sheet_name = str(getattr(created, "payload", {}).get("sheet_name") or "Sheet1")
        if not book_name:
            return {"ok": False, "message": "Origin did not return the FTIR workbook name."}
        columns = [[math.nan] * len(rows) for _index in range(8)]
        for source_index, destination_index in zip(
            range(6),
            (0, 1, 4, 5, 6, 7),
        ):
            columns[destination_index] = [
                float(value)
                if source_index < len(row)
                and (value := _finite_numeric_value(row[source_index])) is not None
                else math.nan
                for row in rows
            ]
        written = operations.set_worksheet_data(book_name, sheet_name, columns)
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(written, "FTIR worksheet data write failed.")
        annotation_offsets = list(binding["last_origin_curve_translate_annotations"])
        comments = {
            column_index: (
                f"curve translate:\r\n{column_letter} is moved vertically by {offset}"
            )
            for column_index, column_letter, offset in zip(
                (2, 6, 8),
                ("B", "F", "H"),
                annotation_offsets,
            )
        }
        metadata = []
        for column_index in (1, 2, 5, 6, 7, 8):
            column_type = 4 if column_index in {1, 5, 7} else 1
            metadata.append(
                {
                    "column_index": column_index,
                    "long_name": "",
                    "unit": "",
                    "comment": comments.get(column_index, ""),
                    "type": column_type,
                }
            )
        metadata_write = operations.set_worksheet_column_metadata(book_name, metadata)
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(metadata_write, "FTIR worksheet metadata write failed.")
        return {
            "ok": True,
            "method": "ftir_independent_a_b_e_f_g_h_copy_with_reserved_c_d",
            "book_name": book_name,
            "sheet_count": 1,
            "reserved_columns": [3, 4],
            "raw_to_plotted_vertical_offsets": list(
                binding["raw_to_plotted_vertical_offsets"]
            ),
            "last_origin_curve_translate_annotations": annotation_offsets,
        }

    if product.product_key == "Mott-Schottky":
        created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(
                created,
                "Mott-Schottky workbook creation failed.",
            )
        book_name = str(getattr(created, "payload", {}).get("book_name") or "")
        sheet_name = str(
            getattr(created, "payload", {}).get("sheet_name") or "Sheet1"
        )
        if not book_name:
            return {
                "ok": False,
                "message": "Origin did not return the Mott-Schottky workbook name.",
            }
        if book_name != str(binding["book_name"]):
            return {
                "ok": False,
                "message": (
                    "Origin did not preserve the reviewed Mott-Schottky workbook "
                    f"identity: expected {binding['book_name']}, actual {book_name}."
                ),
            }
        columns = [[math.nan] * len(rows) for _index in range(12)]
        shared_x = [
            float(value)
            if (value := _finite_numeric_value(row[0])) is not None
            else math.nan
            for row in rows
        ]
        for destination_x in sorted(
            {pair[0] for pair in VERIFIED_MOTT_DESTINATION_PAIRS}
        ):
            columns[destination_x - 1] = list(shared_x)
        for source_y, (_destination_x, destination_y) in enumerate(
            VERIFIED_MOTT_DESTINATION_PAIRS,
            start=1,
        ):
            columns[destination_y - 1] = [
                float(value)
                if source_y < len(row)
                and (value := _finite_numeric_value(row[source_y])) is not None
                else math.nan
                for row in rows
            ]
        written = operations.set_worksheet_data(
            book_name,
            sheet_name,
            columns,
        )
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(
                written,
                "Mott-Schottky worksheet data write failed.",
            )
        metadata: list[dict[str, object]] = []
        x_headers_written: set[int] = set()
        for source_y, (x_col, y_col) in enumerate(
            VERIFIED_MOTT_DESTINATION_PAIRS,
            start=1,
        ):
            if x_col not in x_headers_written:
                metadata.append(
                    {
                        "column_index": x_col,
                        "long_name": headers[0],
                        "unit": "V",
                        "comment": "",
                        "type": 4,
                    }
                )
                x_headers_written.add(x_col)
            metadata.append(
                {
                    "column_index": y_col,
                    "long_name": headers[source_y],
                    "unit": "10^8 cm^4 F^-2",
                    "comment": "",
                    "type": 1,
                }
            )
        metadata_write = operations.set_worksheet_column_metadata(book_name, metadata)
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(
                metadata_write,
                "Mott-Schottky worksheet metadata write failed.",
            )
        masked_rows = [
            row_index
            for row_index, value in enumerate(shared_x, start=1)
            if math.isfinite(value) and value < -1.0e-8
        ]
        mask_columns: list[int] = []
        for _x_col, y_col in VERIFIED_MOTT_DESTINATION_PAIRS[:4]:
            mask_write = operations.set_worksheet_column_mask_rows(
                book_name,
                y_col,
                masked_rows,
            )
            if not getattr(mask_write, "ok", False):
                return _verified_otpu_failure(
                    mask_write,
                    "Mott-Schottky worksheet mask-state write failed.",
                )
            mask_columns.append(y_col)
        return {
            "ok": True,
            "method": "mott_shared_x_to_reviewed_d_to_l_columns_with_native_masks",
            "book_name": book_name,
            "sheet_count": 1,
            "destination_pairs": [
                {"x_col": x_col, "y_col": y_col}
                for x_col, y_col in VERIFIED_MOTT_DESTINATION_PAIRS
            ],
            "masked_rows": masked_rows,
            "masked_y_columns": mask_columns,
        }

    if product.product_key == "photocurrent":
        created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(created, "Photocurrent workbook creation failed.")
        book_name = str(getattr(created, "payload", {}).get("book_name") or "")
        sheet_name = str(getattr(created, "payload", {}).get("sheet_name") or "Sheet1")
        if not book_name:
            return {
                "ok": False,
                "message": "Origin did not return the photocurrent workbook name.",
            }
        # The reviewed Graph2 OTPU binds the three plots to Book1 I/J, M/N,
        # and Q/R.  Keep the intervening columns blank and copy each current
        # source pair verbatim; plot row ranges come from the per-pair binding,
        # so different positive row counts are preserved without padding data.
        columns = [[math.nan] * len(rows) for _index in range(18)]
        for (source_x, source_y), (destination_x, destination_y) in zip(
            ((0, 1), (2, 3), (4, 5)),
            VERIFIED_PHOTOCURRENT_DESTINATION_PAIRS,
        ):
            for source_index, destination_column in (
                (source_x, destination_x),
                (source_y, destination_y),
            ):
                columns[destination_column - 1] = [
                    float(value)
                    if source_index < len(row)
                    and (value := _finite_numeric_value(row[source_index])) is not None
                    else math.nan
                    for row in rows
                ]
        written = operations.set_worksheet_data(
            book_name,
            sheet_name,
            columns,
        )
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(
                written,
                "Photocurrent worksheet data write failed.",
            )
        metadata = []
        for label, (x_col, y_col) in zip(
            product.legend_entries,
            VERIFIED_PHOTOCURRENT_DESTINATION_PAIRS,
        ):
            metadata.extend(
                (
                    {
                        "column_index": x_col,
                        "long_name": "",
                        "unit": "",
                        "comment": "",
                        "type": 4,
                    },
                    {
                        "column_index": y_col,
                        "long_name": "",
                        "unit": "",
                        "comment": str(label).strip(),
                        "type": 1,
                    },
                )
            )
        metadata_write = operations.set_worksheet_column_metadata(
            book_name,
            metadata,
        )
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(
                metadata_write,
                "Photocurrent worksheet metadata write failed.",
            )
        return {
            "ok": True,
            "method": "photocurrent_independent_i_j_m_n_q_r_copy",
            "book_name": book_name,
            "sheet_count": 1,
            "destination_pairs": [
                {"x_col": x_col, "y_col": y_col}
                for x_col, y_col in VERIFIED_PHOTOCURRENT_DESTINATION_PAIRS
            ],
        }

    if product.product_key != "EIS":
        return {"ok": False, "message": f"No OTPU workbook adapter for {product.product_key}."}
    sheets = binding.get("sheets")
    if not isinstance(sheets, list) or len(sheets) != 8:
        return {"ok": False, "message": "EIS workbook requires exactly eight sheets."}
    created = operations.create_worksheet(str(binding["book_name"]), "Sheet1")
    if not getattr(created, "ok", False):
        return _verified_otpu_failure(created, "EIS workbook creation failed.")
    book_name = str(getattr(created, "payload", {}).get("book_name") or "")
    if not book_name:
        return {"ok": False, "message": "Origin did not return the EIS workbook name."}

    for sheet_offset, raw_sheet in enumerate(sheets):
        sheet = dict(raw_sheet)
        sheet_index = int(sheet["sheet_index"])
        requested_sheet_name = f"Sheet{sheet_index}"
        if sheet_offset == 0:
            sheet_name = str(
                getattr(created, "payload", {}).get("sheet_name")
                or requested_sheet_name
            )
        else:
            added = operations.add_worksheet(book_name, requested_sheet_name)
            if not getattr(added, "ok", False):
                return _verified_otpu_failure(added, f"EIS sheet {sheet_index} creation failed.")
            sheet_name = str(
                getattr(added, "payload", {}).get("sheet_name")
                or requested_sheet_name
            )
        x_index = int(sheet["source_x_index"])
        y_index = int(sheet["source_y_index"])
        source_row_from = int(sheet["source_row_from"])
        source_row_to = int(sheet["source_row_to"])
        selected = rows[source_row_from - 1 : source_row_to]
        x_values = [float(row[x_index]) for row in selected]
        y_values = [float(row[y_index]) for row in selected]
        blank = [math.nan] * len(x_values)
        columns = [list(blank) for _index in range(7)]
        columns[4] = x_values
        columns[6] = y_values
        written = operations.set_worksheet_data(
            book_name,
            sheet_name,
            columns,
        )
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(written, f"EIS sheet {sheet_index} data write failed.")
        metadata_write = operations.set_worksheet_column_metadata(
            book_name,
            [
                {"column_index": 5, "long_name": headers[x_index], "unit": "kOhm", "comment": "", "type": 4},
                {"column_index": 7, "long_name": headers[y_index], "unit": "kOhm", "comment": "", "type": 1},
            ],
            sheet_index=sheet_index,
        )
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(metadata_write, f"EIS sheet {sheet_index} metadata failed.")
    return {
        "ok": True,
        "method": "eis_eight_sheet_explicit_e_g_copy",
        "book_name": book_name,
        "sheet_count": 8,
    }


def _verified_otpu_failure(result: object, fallback: str) -> dict[str, object]:
    return {"ok": False, "message": getattr(result, "message", fallback)}


def _uvvis_current_data_matches_reference(
    product: ProductContext,
    reference_data: dict[str, object] | None,
) -> dict[str, object]:
    if not isinstance(reference_data, dict) or str(reference_data.get("status") or "") != "ready":
        return {"matches": False, "reason": "reference_data_snapshot_unavailable"}
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"matches": False, "reason": f"processed_data_unavailable: {exc}"}
    pairs = _processed_csv_plot_pairs(product, headers)
    plots = sorted(
        [dict(value) for value in reference_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (int(value.get("layer_index") or 0), int(value.get("plot_index") or 0)),
    )
    if len(pairs) != len(plots):
        return {
            "matches": False,
            "reason": "series_count_differs",
            "current_series_count": len(pairs),
            "reference_series_count": len(plots),
        }
    for series_index, ((x_col, y_col), plot) in enumerate(zip(pairs, plots), start=1):
        current_x: list[float] = []
        current_y: list[float] = []
        for row in rows:
            x_value = _finite_numeric_value(row[x_col - 1] if x_col - 1 < len(row) else None)
            y_value = _finite_numeric_value(row[y_col - 1] if y_col - 1 < len(row) else None)
            if x_value is None and y_value is None:
                continue
            if x_value is None or y_value is None:
                return {"matches": False, "reason": f"series_{series_index}_has_unpaired_values"}
            current_x.append(x_value)
            current_y.append(y_value)
        reference_x = [float(value) for value in list(plot.get("x_values") or [])]
        reference_y = [float(value) for value in list(plot.get("y_values") or [])]
        if current_x != reference_x or current_y != reference_y:
            return {"matches": False, "reason": f"series_{series_index}_values_differ"}
    return {
        "matches": True,
        "reason": "all_current_xy_values_match_reference_snapshot",
        "series_count": len(pairs),
    }


def _xps_in_situ_current_data_matches_reference(
    product: ProductContext,
    reference_data: dict[str, object] | None,
) -> dict[str, object]:
    """Return true only when all 21 current XPS curves exactly match the review snapshot."""

    if not isinstance(reference_data, dict) or str(reference_data.get("status") or "") != "ready":
        return {"matches": False, "reason": "reference_data_snapshot_unavailable"}
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"matches": False, "reason": f"processed_data_unavailable: {exc}"}
    if len(headers) != 24:
        return {
            "matches": False,
            "reason": "processed_column_count_differs",
            "current_column_count": len(headers),
            "reference_column_count": 24,
        }
    plots = sorted(
        [dict(value) for value in reference_data.get("plots", []) if isinstance(value, dict)],
        key=lambda value: (int(value.get("layer_index") or 0), int(value.get("plot_index") or 0)),
    )
    expected_keys = [(1, index) for index in range(1, 22)]
    actual_keys = [
        (int(plot.get("layer_index") or 0), int(plot.get("plot_index") or 0))
        for plot in plots
    ]
    if actual_keys != expected_keys:
        return {
            "matches": False,
            "reason": "reference_plot_topology_differs",
            "reference_plot_count": len(plots),
        }
    runtime_pairs: list[tuple[int, int]] = []
    for sample_index in range(3):
        x_index = sample_index * 8
        first = x_index + 1
        bounds = _paired_numeric_row_bounds(rows, x_index, first)
        if bounds is None:
            return {
                "matches": False,
                "reason": f"sample_{sample_index + 1}_row_bounds_unavailable",
            }
        row_from, row_to = bounds
        component_order = _xps_in_situ_component_source_order(
            rows,
            x_index,
            first + 1,
            first + 3,
            row_from=row_from,
            row_to=row_to,
        )
        if component_order is None:
            return {
                "matches": False,
                "reason": f"sample_{sample_index + 1}_component_order_ambiguous",
            }
        high_binding_component, low_binding_component = component_order
        runtime_pairs.extend(
            (x_index, source_y_index)
            for source_y_index in (
                first,
                high_binding_component,
                first + 2,
                low_binding_component,
                first + 4,
                first + 5,
                first + 6,
            )
        )
    for plot_index, ((source_x_index, source_y_index), plot) in enumerate(
        zip(runtime_pairs, plots),
        start=1,
    ):
        current_x: list[float] = []
        current_y: list[float] = []
        for row in rows:
            x_value = _finite_numeric_value(
                row[source_x_index] if source_x_index < len(row) else None
            )
            y_value = _finite_numeric_value(
                row[source_y_index] if source_y_index < len(row) else None
            )
            if x_value is None and y_value is None:
                continue
            if x_value is None or y_value is None:
                return {
                    "matches": False,
                    "reason": f"plot_{plot_index}_has_unpaired_values",
                }
            current_x.append(x_value)
            current_y.append(y_value)
        reference_x = [float(value) for value in list(plot.get("x_values") or [])]
        reference_y = [float(value) for value in list(plot.get("y_values") or [])]
        if current_x != reference_x or current_y != reference_y:
            return {
                "matches": False,
                "reason": f"plot_{plot_index}_values_differ",
            }
    return {
        "matches": True,
        "reason": "all_21_current_xy_values_match_reference_snapshot",
        "series_count": 21,
    }


def _update_verified_xps_in_situ_annotations(
    operations: object,
    graph_name: str,
    product: ProductContext,
) -> dict[str, object]:
    return _update_verified_xps_native_annotations(
        operations,
        graph_name,
        product,
        expected_sample_count=3,
        sample_objects=("Text1", "Text4", "Text7"),
        peak_objects=(("Text2", "Text3"), ("Text5", "Text6"), ("Text8", "Text9")),
        route_name="xps_in_situ",
    )


def _update_verified_xps_non_in_situ_annotations(
    operations: object,
    graph_name: str,
    product: ProductContext,
) -> dict[str, object]:
    return _update_verified_xps_native_annotations(
        operations,
        graph_name,
        product,
        expected_sample_count=2,
        sample_objects=("Text", "Text1"),
        peak_objects=(("Text2", "Text3"), ("Text4", "Text5")),
        route_name="xps_non_in_situ",
    )


def _update_verified_xps_native_annotations(
    operations: object,
    graph_name: str,
    product: ProductContext,
    *,
    expected_sample_count: int,
    sample_objects: tuple[str, ...],
    peak_objects: tuple[tuple[str, str], ...],
    route_name: str,
) -> dict[str, object]:
    """Populate reviewed native XPS text objects from current candidate data."""

    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"processed_data_unavailable: {exc}"}
    source_samples = [
        str(header).strip()[: -len("_measured")]
        for header in headers
        if str(header).strip().casefold().endswith("_measured")
    ]
    labels = [_template_xps_sample_display_label(value) for value in source_samples]
    if (
        len(labels) != expected_sample_count
        or len(sample_objects) != expected_sample_count
        or len(peak_objects) != expected_sample_count
        or any(not label for label in labels)
        or len({label.casefold() for label in labels}) != expected_sample_count
    ):
        return {
            "applied": False,
            "reason": f"{route_name}_requires_{expected_sample_count}_nonempty_unique_current_sample_labels",
            "labels": labels,
        }
    try:
        annotations = _xps_peak_annotations_from_processed_data(
            product.processed_data,
            product_title=product.graph_title,
        )
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"xps_peak_candidates_unavailable: {exc}"}
    annotations_by_sample: dict[str, list[dict[str, object]]] = {}
    for annotation in annotations:
        annotations_by_sample.setdefault(str(annotation.get("sample") or ""), []).append(
            dict(annotation)
        )
    if any(
        len(annotations_by_sample.get(sample, [])) != 2 for sample in source_samples
    ):
        return {
            "applied": False,
            "reason": f"{route_name}_requires_exactly_two_current_component_peak_candidates_per_sample",
            "sample_component_counts": {
                sample: len(annotations_by_sample.get(sample, [])) for sample in source_samples
            },
        }
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "no_origin_app"}
    try:
        layer = (
            app.FindGraphLayer(f"[{graph_name}]Layer1")
            or app.FindGraphLayer(f"[{graph_name}]1")
            or app.FindGraphLayer(graph_name)
        )
    except Exception:
        layer = None
    if not layer:
        return {"applied": False, "reason": "graph_layer_unavailable"}

    text_by_object: dict[str, str] = {}
    for sample_index, (source_sample, display_label) in enumerate(
        zip(source_samples, labels),
    ):
        text_by_object[sample_objects[sample_index]] = origin_bold_text(
            _reviewed_template_legend_rich_text(display_label)
        )
        candidates = sorted(
            annotations_by_sample[source_sample],
            key=lambda value: float(value["x"]),
            reverse=True,
        )
        for object_name, candidate in zip(peak_objects[sample_index], candidates):
            candidate_text = str(candidate.get("text") or "").strip()
            energy_text = f"{float(candidate['x']):.2f} eV"
            prefix = (
                candidate_text[: -len(energy_text)].strip()
                if candidate_text.endswith(energy_text)
                else candidate_text
            )
            if not prefix:
                prefix = str(candidate.get("region") or "Peak").strip() or "Peak"
            text_by_object[object_name] = (
                f"{origin_bold_text(prefix)}\r\n{origin_bold_text(energy_text)}"
            )

    readback: dict[str, str] = {}
    for object_name, expected_text in text_by_object.items():
        graph_object = _find_unique_origin_graph_object(layer, object_name)
        if graph_object is None:
            return {
                "applied": False,
                "reason": "required_xps_annotation_missing_or_not_unique",
                "object_name": object_name,
            }
        try:
            graph_object.Text = expected_text
            actual_text = str(getattr(graph_object, "Text", "") or "")
        except Exception:
            return {
                "applied": False,
                "reason": "xps_annotation_write_or_readback_failed",
                "object_name": object_name,
            }
        if actual_text != expected_text:
            return {
                "applied": False,
                "reason": "xps_annotation_readback_mismatch",
                "object_name": object_name,
                "expected": expected_text,
                "actual": actual_text,
            }
        readback[object_name] = actual_text
    return {
        "applied": True,
        "method": "reviewed_native_text_objects_with_current_sample_and_component_maximum_candidates",
        "sample_labels": labels,
        "peak_candidate_count": len(annotations),
        "objects": readback,
        "manual_check_required": True,
        "claim_policy": "Peak positions are current-data candidates; no chemical-state or valence assignment is asserted.",
    }


def _update_verified_uvvis_fixed_legend(
    operations: object,
    graph_name: str,
    product: ProductContext,
) -> dict[str, object]:
    labels = [str(value).strip() for value in product.legend_entries]
    visible_indices = (4, 5, 6) if product.product_key == "UV-vis DRS" else (2, 3)
    if len(labels) < max(visible_indices) or any(not labels[index - 1] for index in visible_indices):
        return {
            "applied": False,
            "reason": "visible_plot_labels_unavailable",
            "visible_plot_indices": list(visible_indices),
            "label_count": len(labels),
        }
    written = update_native_legend(
        operations, graph_name,
        [labels[index - 1] for index in visible_indices],
        plot_indices=visible_indices,
    ).ok
    return {
        "applied": bool(written),
        "method": "current_labels_for_reviewed_visible_plot_indices",
        "visible_plot_indices": list(visible_indices),
        "entries": [labels[index - 1] for index in visible_indices],
    }


def _apply_verified_uvvis_fixed_visibility(
    operations: object,
    graph_name: str,
    reference_style: dict[str, object],
) -> dict[str, object]:
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    raw_visibility = reference_style.get("plot_visibility")
    visibility = list(raw_visibility) if isinstance(raw_visibility, list) else []
    if not plot_names or len(visibility) != len(plot_names):
        return {
            "applied": False,
            "reason": "reference_visibility_or_current_plot_count_mismatch",
            "plot_count": len(plot_names),
            "visibility_count": len(visibility),
        }
    commands: list[str] = []
    applied_visibility: list[int] = []
    for index, value in enumerate(visibility, start=1):
        numeric = _finite_numeric_value(value)
        show = 1 if numeric is not None and numeric > 0.5 else 0
        command = (
            f'win -a "{quote_labtalk(graph_name)}"; '
            f"layer.plot{index}.show={show};"
        )
        result = operations.run_labtalk(command)
        if not getattr(result, "ok", False):
            return {
                "applied": False,
                "reason": "reference_plot_visibility_restore_failed",
                "plot_index": index,
                "commands": commands,
            }
        commands.append(command)
        applied_visibility.append(show)
    return {
        "applied": True,
        "method": "reviewed_fixed_plot_visibility",
        "plot_visibility": applied_visibility,
        "commands": commands,
    }


def _apply_uvvis_current_axis_titles(
    operations: object,
    graph_name: str,
    x_label: str,
    y_label: str,
) -> dict[str, object]:
    labels = operations.set_axis_labels(graph_name, x_label, y_label, "")
    if not getattr(labels, "ok", False):
        return {"applied": False, "reason": "set_axis_labels_failed"}
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "origin_app_unavailable"}
    try:
        layer = (
            app.FindGraphLayer(f"[{graph_name}]Layer1")
            or app.FindGraphLayer(f"[{graph_name}]1")
            or app.FindGraphLayer(graph_name)
        )
    except Exception:
        layer = None
    if not layer:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    readback: dict[str, dict[str, object]] = {}
    for object_name, plain_text in (("XB", x_label), ("YL", y_label)):
        graph_object = _find_origin_graph_object(layer, object_name)
        if graph_object is None:
            return {
                "applied": False,
                "reason": "axis_title_object_unavailable",
                "object_name": object_name,
            }
        rich_text = _uvvis_axis_title_rich_text(plain_text)
        try:
            graph_object.Text = rich_text
            graph_object.SetNumProp("bold", 1)
            graph_object.SetNumProp("show", 1)
        except Exception as exc:
            return {
                "applied": False,
                "reason": "axis_title_com_write_failed",
                "object_name": object_name,
                "error": f"{type(exc).__name__}: {exc}",
            }
        try:
            actual_text = str(getattr(graph_object, "Text", "") or "")
        except Exception:
            actual_text = ""
        try:
            actual_bold = _finite_float(graph_object.GetNumProp("bold"))
        except Exception:
            actual_bold = None
        if actual_bold is not None and actual_bold != 0.0 and abs(actual_bold) < 1e-250:
            # Origin returns a tiny finite missing-value sentinel for some
            # graph-object properties instead of raising or returning None.
            actual_bold = None
        elif actual_bold is not None and not (
            math.isclose(actual_bold, 0.0, abs_tol=1e-9)
            or math.isclose(actual_bold, 1.0, abs_tol=1e-9)
        ):
            actual_bold = None
        if actual_bold is not None and not math.isclose(actual_bold, 1.0, abs_tol=1e-9):
            return {
                "applied": False,
                "reason": "axis_title_immediate_bold_readback_mismatch",
                "object_name": object_name,
                "actual_text": actual_text,
                "actual_bold": actual_bold,
            }
        readback[object_name] = {
            "text": actual_text,
            "bold": actual_bold,
            "immediate_readback_available": bool(actual_text) and actual_bold is not None,
        }
    return {
        "applied": True,
        "method": "origin_native_axis_title_objects_with_save_reopen_hard_gate",
        "readback": readback,
    }


def _uvvis_axis_title_rich_text(value: str) -> str:
    compact = re.sub(r"\s+", "", str(value))
    if compact == "hν(eV)":
        return r"\b(\i(h\f:g(ν) )(eV))"
    if compact == "(αhν)^2":
        return r"\b(\(40)\i(\f:g(α)h\f:g(ν))\(41)\+(2))"
    if compact == "(F(R)hν)^2":
        return r"\b(\(40)\i(F\(40)R\(41)h\f:g(ν))\(41)\+(2))"
    return origin_bold_text(value)


def _position_adaptive_xrd_axis_titles(
    operations: object,
    graph_name: str,
    x_label: str,
    y_label: str,
    style_snapshot: dict[str, object],
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    """Place native XRD axis-title objects from reviewed page/layer geometry."""

    layout = style_snapshot.get("layout_values") if isinstance(style_snapshot, dict) else None
    required = {
        key: _snapshot_axis_value(layout, key)
        for key in (
            "page.width",
            "page.height",
            "layer.left",
            "layer.top",
            "layer.width",
            "layer.height",
        )
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        return {
            "applied": False,
            "reason": "reviewed_page_layer_geometry_unavailable",
            "missing": missing,
        }
    page_width = float(required["page.width"])
    page_height = float(required["page.height"])
    layer_left = float(required["layer.left"])
    layer_top = float(required["layer.top"])
    layer_width = float(required["layer.width"])
    layer_height = float(required["layer.height"])
    if page_width <= 0 or page_height <= 0 or layer_width <= 0 or layer_height <= 0:
        return {"applied": False, "reason": "reviewed_page_layer_geometry_invalid"}

    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "origin_app_unavailable"}
    try:
        layer = (
            app.FindGraphLayer(f"[{graph_name}]Layer1")
            or app.FindGraphLayer(f"[{graph_name}]1")
            or app.FindGraphLayer(graph_name)
        )
    except Exception as exc:
        return {
            "applied": False,
            "reason": "graph_layer_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not layer:
        return {"applied": False, "reason": "graph_layer_unavailable"}

    objects: dict[str, object] = {}
    for object_name in ("XB", "YL"):
        graph_object = _find_origin_graph_object(layer, object_name)
        if graph_object is None:
            return {
                "applied": False,
                "reason": "axis_title_object_unavailable",
                "object_name": object_name,
            }
        objects[object_name] = graph_object

    attach_result = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; xb.attach=1; yl.attach=1;'
    )
    if not getattr(attach_result, "ok", False):
        return {"applied": False, "reason": "axis_title_page_attachment_failed"}
    for graph_object in objects.values():
        try:
            graph_object.Attach = 1
        except Exception:
            # LabTalk is the authoritative write for special Origin axis-title
            # objects; some COM wrappers do not expose Attach directly.
            pass

    font_code = _origin_font_code(app, style.font_family)
    for object_name, plain_text in (("XB", x_label), ("YL", y_label)):
        graph_object = objects[object_name]
        try:
            graph_object.Text = origin_bold_text(plain_text)
            for prop, value in (
                ("font", font_code),
                ("fsize", int(style.axis_title_font_size)),
                ("bold", 1 if style.font_bold else 0),
                ("color", 1),
                ("show", 1),
                ("background", 0),
                ("border", 0),
                ("frame", 0),
                ("fill", 0),
            ):
                graph_object.SetNumProp(prop, value)
        except Exception as exc:
            return {
                "applied": False,
                "reason": "axis_title_native_style_write_failed",
                "object_name": object_name,
                "error": f"{type(exc).__name__}: {exc}",
            }

    show_result = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; xb.show=1; yl.show=1; doc -uw;'
    )
    if not getattr(show_result, "ok", False):
        return {"applied": False, "reason": "axis_title_native_refresh_failed"}

    try:
        xb_width = float(getattr(objects["XB"], "Width"))
        xb_height = float(getattr(objects["XB"], "Height"))
        yl_width = float(getattr(objects["YL"], "Width"))
        yl_height = float(getattr(objects["YL"], "Height"))
    except Exception as exc:
        return {
            "applied": False,
            "reason": "axis_title_native_size_readback_failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
    if min(xb_width, xb_height, yl_width, yl_height) <= 0:
        return {"applied": False, "reason": "axis_title_native_size_invalid"}

    layer_center_x = page_width * (layer_left + layer_width / 2.0) / 100.0
    layer_center_y = page_height * (layer_top + layer_height / 2.0) / 100.0
    positions = {
        "XB": {
            "left": int(round(layer_center_x - xb_width / 2.0)),
            "top": int(round(page_height * (layer_top + layer_height + 7.7) / 100.0)),
            "width": int(round(xb_width)),
            "height": int(round(xb_height)),
        },
        "YL": {
            "left": int(round(page_width * layer_left / 100.0 - yl_width - page_width * 0.017)),
            "top": int(round(layer_center_y - yl_height / 2.0)),
            "width": int(round(yl_width)),
            "height": int(round(yl_height)),
        },
    }
    try:
        for object_name, geometry in positions.items():
            graph_object = objects[object_name]
            graph_object.Left = geometry["left"]
            graph_object.Top = geometry["top"]
    except Exception as exc:
        return {
            "applied": False,
            "reason": "axis_title_native_position_write_failed",
            "error": f"{type(exc).__name__}: {exc}",
        }

    position_refresh = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; doc -uw;'
    )
    if not getattr(position_refresh, "ok", False):
        return {"applied": False, "reason": "axis_title_position_refresh_failed"}

    actual_positions: dict[str, dict[str, int]] = {}
    failures: list[str] = []
    for object_name, graph_object in objects.items():
        try:
            geometry = {
                "left": int(round(float(getattr(graph_object, "Left")))),
                "top": int(round(float(getattr(graph_object, "Top")))),
                "width": int(round(float(getattr(graph_object, "Width")))),
                "height": int(round(float(getattr(graph_object, "Height")))),
            }
        except Exception as exc:
            failures.append(f"{object_name}: geometry readback failed ({type(exc).__name__})")
            continue
        actual_positions[object_name] = geometry
        if geometry["left"] < 0 or geometry["top"] < 0:
            failures.append(f"{object_name}: negative page coordinate")
        if geometry["left"] + geometry["width"] > page_width + 1:
            failures.append(f"{object_name}: exceeds page width")
        if geometry["top"] + geometry["height"] > page_height + 1:
            failures.append(f"{object_name}: exceeds page height")
    return {
        "applied": not failures,
        "method": "origin_native_axis_title_page_geometry_from_reviewed_layout",
        "attachment": "page",
        "page_width": page_width,
        "page_height": page_height,
        "positions": actual_positions,
        "failures": failures,
    }


def _validate_xrd_axis_title_page_bounds(product_style: dict[str, object]) -> dict[str, object]:
    layout = product_style.get("layout_values") if isinstance(product_style, dict) else None
    page_width = _snapshot_axis_value(layout, "page.width")
    page_height = _snapshot_axis_value(layout, "page.height")
    positions = product_style.get("graph_object_positions") if isinstance(product_style, dict) else None
    if page_width is None or page_height is None or page_width <= 0 or page_height <= 0:
        return {"ok": False, "status": "mismatch", "reason": "page_geometry_unavailable"}
    if not isinstance(positions, dict):
        return {"ok": False, "status": "mismatch", "reason": "graph_object_positions_unavailable"}
    by_name = {str(name).casefold(): value for name, value in positions.items()}
    checked: dict[str, dict[str, float]] = {}
    failures: list[str] = []
    for object_name in ("XB", "YL"):
        raw = by_name.get(object_name.casefold())
        if not isinstance(raw, dict):
            failures.append(f"{object_name}: missing after save/reopen")
            continue
        geometry = {key: _finite_float(raw.get(key)) for key in ("left", "top", "width", "height")}
        if any(value is None for value in geometry.values()):
            failures.append(f"{object_name}: incomplete geometry after save/reopen")
            continue
        numeric = {key: float(value) for key, value in geometry.items() if value is not None}
        checked[object_name] = numeric
        if numeric["left"] < 0 or numeric["top"] < 0:
            failures.append(f"{object_name}: outside page at negative coordinate")
        if numeric["width"] <= 0 or numeric["height"] <= 0:
            failures.append(f"{object_name}: invalid size")
        if numeric["left"] + numeric["width"] > page_width + 1:
            failures.append(f"{object_name}: outside page width")
        if numeric["top"] + numeric["height"] > page_height + 1:
            failures.append(f"{object_name}: outside page height")
    return {
        "ok": not failures,
        "status": "matched" if not failures else "mismatch",
        "message": (
            "Adaptive native axis-title objects remain inside the page after save/reopen."
            if not failures
            else "; ".join(failures)
        ),
        "page_width": page_width,
        "page_height": page_height,
        "objects": checked,
    }


def _remove_tauc_reference_candidate_guides(
    operations: object,
    graph_name: str,
) -> dict[str, object]:
    command = f'win -a "{quote_labtalk(graph_name)}"; ' + " ".join(
        f"label -r {name};" for name in TAUC_REFERENCE_GUIDE_OBJECTS
    )
    result = operations.run_labtalk(command)
    return {
        "applied": bool(getattr(result, "ok", False)),
        "method": "remove_reference_data_dependent_fit_guides_and_intercept_labels",
        "removed_objects": list(TAUC_REFERENCE_GUIDE_OBJECTS),
        "removed_intercept_labels": list(TAUC_REFERENCE_INTERCEPT_LABELS),
        "manual_check_required": True,
        "visible_claim": "none",
    }


def _validate_tauc_reference_guides_removed(
    operations: object,
    graph_name: str,
    product_style: dict[str, object],
) -> dict[str, object]:
    positions = product_style.get("graph_object_positions")
    position_names = (
        {str(name).casefold() for name in positions}
        if isinstance(positions, dict)
        else set()
    )
    present_names = [
        name
        for name in TAUC_REFERENCE_GUIDE_OBJECTS
        if name.casefold() in position_names
    ]
    present_intercept_labels: list[str] = []
    app = getattr(operations, "app", None)
    layer = None
    if app is not None:
        try:
            layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
        except Exception:
            layer = None
    if layer:
        for name in TAUC_REFERENCE_GUIDE_OBJECTS:
            if _find_origin_graph_object(layer, name) is not None and name not in present_names:
                present_names.append(name)
        collection = getattr(layer, "GraphObjects", None)
        if collection is not None:
            try:
                count = int(getattr(collection, "Count", 0))
            except Exception:
                count = 0
            objects: list[object] = []
            for base in (0, 1):
                attempt: list[object] = []
                for index in range(count):
                    try:
                        attempt.append(collection.Item(index + base))
                    except Exception:
                        continue
                if len(attempt) == count:
                    objects = attempt
                    break
            for graph_object in objects:
                text = str(getattr(graph_object, "Text", "") or "")
                for label in TAUC_REFERENCE_INTERCEPT_LABELS:
                    if label in text and label not in present_intercept_labels:
                        present_intercept_labels.append(label)
    return {
        "ok": not present_names and not present_intercept_labels,
        "status": "pass" if not present_names and not present_intercept_labels else "fail",
        "checked_objects": list(TAUC_REFERENCE_GUIDE_OBJECTS),
        "present_objects": present_names,
        "checked_intercept_labels": list(TAUC_REFERENCE_INTERCEPT_LABELS),
        "present_intercept_labels": present_intercept_labels,
    }


def _apply_verified_otpu_post_plot_style(
    operations: object,
    product: ProductContext,
    graph_name: str,
    reference_style: dict[str, object],
    style: ResolvedPlotStyle,
    *,
    runtime_theme: Path | None,
    reference_data: dict[str, object] | None = None,
) -> dict[str, object]:
    if product.product_key == "XPS_in_situ":
        if runtime_theme is not None:
            return {
                "ok": False,
                "message": "Verified XPS in-situ OTPU runtime must not apply an OTH asset.",
            }
        same_data = _xps_in_situ_current_data_matches_reference(product, reference_data)
        if same_data.get("matches"):
            return {
                "ok": True,
                "method": "otpu_native_style_exact_same_data_with_native_xps_annotations",
                "same_data_reference_match": same_data,
                "format_theme_applied": False,
                "reference_annotations_preserved": True,
                "manual_check_required": True,
            }
        annotation_policy = _update_verified_xps_in_situ_annotations(
            operations,
            graph_name,
            product,
        )
        if not annotation_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified XPS in-situ current sample/peak annotation replacement failed.",
                "same_data_reference_match": same_data,
                "annotation_policy": annotation_policy,
            }
        return {
            "ok": True,
            "method": "otpu_native_style_with_current_sample_and_peak_candidate_annotations",
            "same_data_reference_match": same_data,
            "annotation_policy": annotation_policy,
            "format_theme_applied": False,
            "reference_annotations_preserved": False,
            "manual_check_required": True,
        }
    if product.product_key == "XPS_non_in_situ":
        if runtime_theme is not None:
            return {
                "ok": False,
                "message": "Verified XPS non-in-situ OTPU runtime must not apply an OTH asset.",
            }
        same_data = _uvvis_current_data_matches_reference(product, reference_data)
        if same_data.get("matches"):
            return {
                "ok": True,
                "method": "otpu_native_style_exact_same_data_with_native_xps_annotations",
                "same_data_reference_match": same_data,
                "format_theme_applied": False,
                "reference_annotations_preserved": True,
                "manual_check_required": True,
            }
        annotation_policy = _update_verified_xps_non_in_situ_annotations(
            operations,
            graph_name,
            product,
        )
        if not annotation_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified XPS non-in-situ current sample/peak annotation replacement failed.",
                "same_data_reference_match": same_data,
                "annotation_policy": annotation_policy,
            }
        return {
            "ok": True,
            "method": "otpu_native_style_with_current_sample_and_peak_candidate_annotations",
            "same_data_reference_match": same_data,
            "annotation_policy": annotation_policy,
            "format_theme_applied": False,
            "reference_annotations_preserved": False,
            "manual_check_required": True,
        }
    if product.product_key == "BET":
        return {"ok": True, "method": "otpu_native_style_only"}
    if product.product_key in {"UV-vis DRS", "Tauc"}:
        same_data = _uvvis_current_data_matches_reference(product, reference_data)
        plot_style_policy = _apply_reviewed_template_plot_styles(
            operations,
            graph_name,
            reference_data or {},
        )
        if not plot_style_policy.get("applied"):
            return {
                "ok": False,
                "message": f"Verified {product.product_key} per-plot style restore failed.",
                "plot_style_policy": plot_style_policy,
            }
        visibility_policy = _apply_verified_uvvis_fixed_visibility(
            operations,
            graph_name,
            reference_style,
        )
        if not visibility_policy.get("applied"):
            return {
                "ok": False,
                "message": f"Verified {product.product_key} reference visibility restore failed.",
                "visibility_policy": visibility_policy,
            }
        if same_data.get("matches"):
            legend_restored = _update_verified_uvvis_fixed_legend(
                operations, graph_name, product,
            ).get("applied", False)
            if not legend_restored:
                return {
                    "ok": False,
                    "message": f"Verified {product.product_key} reference legend restore failed.",
                    "visibility_policy": visibility_policy,
                }
            return {
                "ok": True,
                "method": "otpu_native_style_exact_same_data_with_reviewed_visibility_and_legend",
                "same_data_reference_match": same_data,
                "plot_style_policy": plot_style_policy,
                "visibility_policy": visibility_policy,
                "legend_policy": {
                    "applied": True,
                    "method": "reviewed_reference_legend_text",
                },
                "reference_fit_guides_preserved": product.product_key == "Tauc",
            }
        legend_policy = _update_verified_uvvis_fixed_legend(
            operations,
            graph_name,
            product,
        )
        if not legend_policy.get("applied"):
            return {
                "ok": False,
                "message": f"Verified {product.product_key} current-label legend replacement failed.",
                "legend_policy": legend_policy,
            }
        axis_title_policy = _apply_uvvis_current_axis_titles(
            operations,
            graph_name,
            product.x_label,
            product.y_label,
        )
        if not axis_title_policy.get("applied"):
            return {
                "ok": False,
                "message": f"Verified {product.product_key} current scientific axis titles failed.",
                "axis_title_policy": axis_title_policy,
            }
        axis_range_policy = _apply_embedded_snapshot_data_axis_range(
            operations,
            graph_name,
            product,
        )
        if not axis_range_policy.get("applied"):
            return {
                "ok": False,
                "message": f"Verified {product.product_key} current-data axis range failed.",
                "axis_range_policy": axis_range_policy,
            }
        guide_policy = (
            _remove_tauc_reference_candidate_guides(operations, graph_name)
            if product.product_key == "Tauc"
            else {"applied": False, "reason": "not_tauc"}
        )
        if product.product_key == "Tauc" and not guide_policy.get("applied"):
            return {
                "ok": False,
                "message": "Old Tauc fit guides or intercept labels could not be removed for changed data.",
                "guide_policy": guide_policy,
            }
        return {
            "ok": True,
            "method": "otpu_native_style_with_current_labels_axes_and_claim_cleanup",
            "same_data_reference_match": same_data,
            "plot_style_policy": plot_style_policy,
            "visibility_policy": visibility_policy,
            "legend_policy": legend_policy,
            "axis_title_policy": axis_title_policy,
            "axis_range_policy": axis_range_policy,
            "guide_policy": guide_policy,
            "reference_fit_guides_preserved": False,
            "manual_check_required": product.product_key == "Tauc",
        }
    if product.product_key == "Raman":
        if runtime_theme is not None:
            return {
                "ok": False,
                "message": "Verified Raman OTPU runtime must not apply an OTH asset.",
            }
        snapshot_applied = apply_style_snapshot(
            operations,
            graph_name,
            reference_style,
            apply_default_font=False,
            apply_axis_titles=True,
        )
        if not snapshot_applied:
            return {
                "ok": False,
                "message": "Verified Raman style snapshot application failed.",
            }
        label_policy = _update_verified_raman_label_objects(
            operations,
            graph_name,
            product.legend_entries,
        )
        if not label_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified Raman current-label object replacement failed.",
                "label_policy": label_policy,
            }
        return {
            "ok": True,
            "method": "otpu_then_snapshot_then_current_distributed_labels",
            "format_theme_applied": False,
            "style_snapshot_applied": True,
            "apply_default_font": False,
            "apply_axis_titles": True,
            "label_policy": label_policy,
        }
    if product.product_key == "FTIR":
        if runtime_theme is not None:
            return {
                "ok": False,
                "message": "Verified FTIR runtime must not apply an OTH asset.",
            }
        legend_policy = _update_verified_ftir_legend(
            operations,
            graph_name,
            product.legend_entries,
        )
        if not legend_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified FTIR exact reference legend replacement failed.",
                "legend_policy": legend_policy,
            }
        return {
            "ok": True,
            "method": "otpu_native_style_then_exact_reference_legend",
            "format_theme_applied": False,
            "style_snapshot_applied": False,
            "legend_policy": legend_policy,
        }
    if product.product_key == "Mott-Schottky":
        if runtime_theme is not None:
            return {
                "ok": False,
                "message": "Verified Mott-Schottky OTPU runtime must not apply an OTH asset.",
            }
        if (
            not isinstance(reference_data, dict)
            or str(reference_data.get("status") or "") != "ready"
        ):
            return {
                "ok": False,
                "message": "Verified Mott-Schottky plot styles require the reviewed data snapshot.",
            }
        snapshot_applied = apply_style_snapshot(
            operations,
            graph_name,
            reference_style,
            apply_default_font=False,
            apply_axis_titles=True,
            preserve_custom_rgb=True,
        )
        if not snapshot_applied:
            return {
                "ok": False,
                "message": "Verified Mott-Schottky style snapshot application failed.",
            }
        reviewed_policy = _apply_reviewed_template_plot_policy(
            operations,
            graph_name,
            product,
            reference_style,
            style,
            data_snapshot=reference_data,
            restore_plot_styles=False,
        )
        if not reviewed_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified Mott-Schottky plot visibility, styles, legend, or guides failed.",
                "reviewed_plot_policy": reviewed_policy,
            }
        guide_policy = reviewed_policy.get("mott_schottky_candidate_guides")
        if not isinstance(guide_policy, dict) or not guide_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified Mott-Schottky candidate guide construction failed.",
                "reviewed_plot_policy": reviewed_policy,
            }
        legend_anchor_policy = _apply_saved_template_legend_anchor(
            operations,
            graph_name,
            reference_style,
            regenerate=False,
        )
        if not legend_anchor_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified Mott-Schottky template legend anchor could not be restored.",
                "reviewed_plot_policy": reviewed_policy,
                "legend_anchor_policy": legend_anchor_policy,
            }
        return {
            "ok": True,
            "method": "otpu_then_snapshot_then_reviewed_native_plot_policy_and_candidate_guides",
            "format_theme_applied": False,
            "style_snapshot_applied": True,
            "apply_default_font": False,
            "apply_axis_titles": True,
            "reviewed_plot_policy": reviewed_policy,
            "legend_anchor_policy": legend_anchor_policy,
        }
    if product.product_key == "photocurrent":
        if runtime_theme is None or not runtime_theme.is_file():
            return {
                "ok": False,
                "message": "Verified photocurrent runtime requires its reviewed OTH asset.",
            }
        theme = operations.apply_graph_theme(graph_name, runtime_theme)
        if not getattr(theme, "ok", False):
            return _verified_otpu_failure(
                theme,
                "Verified photocurrent OTH application failed.",
            )
        snapshot_applied = apply_style_snapshot(
            operations,
            graph_name,
            reference_style,
            apply_default_font=False,
            apply_axis_titles=True,
        )
        if not snapshot_applied:
            return {
                "ok": False,
                "message": "Verified photocurrent style snapshot application failed.",
            }
        axis_range_policy = _apply_embedded_snapshot_data_axis_range(
            operations,
            graph_name,
            product,
            reference_style_snapshot=reference_style,
            reference_data_snapshot=reference_data,
        )
        if not axis_range_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified photocurrent current-data axis range application failed.",
                "axis_range_policy": axis_range_policy,
            }
        legend_anchor_policy = _apply_saved_template_legend_anchor(
            operations,
            graph_name,
            reference_style,
        )
        if not legend_anchor_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified photocurrent proportional legend anchoring failed.",
                "legend_anchor_policy": legend_anchor_policy,
            }
        legend_policy = _update_verified_photocurrent_legend(
            operations,
            graph_name,
            product.legend_entries,
        )
        if not legend_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified photocurrent current-sample legend replacement failed.",
                "legend_policy": legend_policy,
            }
        return {
            "ok": True,
            "method": "otpu_then_oth_then_snapshot_then_current_legend",
            "format_theme_applied": True,
            "style_snapshot_applied": True,
            "apply_default_font": False,
            "apply_axis_titles": True,
            "axis_range_policy": axis_range_policy,
            "legend_anchor_policy": legend_anchor_policy,
            "legend_policy": legend_policy,
        }
    if product.product_key in {"EPR", "PL"}:
        if runtime_theme is None or not runtime_theme.is_file():
            return {
                "ok": False,
                "message": f"Verified {product.product_key} OTH runtime copy is unavailable.",
            }
        theme = operations.apply_graph_theme(graph_name, runtime_theme)
        if not getattr(theme, "ok", False):
            return _verified_otpu_failure(
                theme,
                f"Verified {product.product_key} OTH application failed.",
            )
        snapshot_applied = apply_style_snapshot(
            operations,
            graph_name,
            reference_style,
            apply_default_font=False,
            apply_axis_titles=True,
        )
        if not snapshot_applied:
            return {
                "ok": False,
                "message": f"Verified {product.product_key} snapshot failed after OTH.",
            }
        if product.product_key == "PL":
            legend_policy = _update_verified_pl_legend(
                operations,
                graph_name,
                product.legend_entries,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Verified PL current legend replacement failed.",
                    "legend_policy": legend_policy,
                }
            return {
                "ok": True,
                "method": "otpu_then_oth_then_snapshot_then_current_legend",
                "format_theme_applied": True,
                "style_snapshot_applied": True,
                "apply_default_font": False,
                "apply_axis_titles": True,
                "legend_policy": legend_policy,
            }
        axis_range_policy = _apply_embedded_snapshot_data_axis_range(
            operations,
            graph_name,
            product,
        )
        if not axis_range_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified EPR current magnetic-field range could not be applied.",
                "axis_range_policy": axis_range_policy,
            }
        label_policy = _update_verified_epr_label_objects(
            operations,
            graph_name,
            product.legend_entries,
        )
        if not label_policy.get("applied"):
            return {
                "ok": False,
                "message": "Verified EPR current DL1/DL2/DL3 labels failed.",
                "label_policy": label_policy,
            }
        return {
            "ok": True,
            "method": "otpu_then_oth_then_snapshot_then_current_data_axis_and_dl_labels",
            "format_theme_applied": True,
            "style_snapshot_applied": True,
            "apply_default_font": False,
            "apply_axis_titles": True,
            "axis_range_policy": axis_range_policy,
            "label_policy": label_policy,
        }
    if product.product_key != "EIS":
        return {"ok": False, "message": f"No OTPU style adapter for {product.product_key}."}
    if runtime_theme is None or not runtime_theme.is_file():
        return {"ok": False, "message": "Verified EIS OTH runtime copy is unavailable."}

    theme = operations.apply_graph_theme(graph_name, runtime_theme)
    if not getattr(theme, "ok", False):
        return _verified_otpu_failure(theme, "Verified EIS OTH application failed.")
    snapshot_applied = apply_style_snapshot(
        operations,
        graph_name,
        reference_style,
        apply_default_font=False,
        apply_axis_titles=True,
    )
    if not snapshot_applied:
        return {"ok": False, "message": "Verified EIS snapshot failed after OTH."}
    axis_range_policy = _apply_embedded_snapshot_data_axis_range(
        operations,
        graph_name,
        product,
    )
    if not axis_range_policy.get("applied"):
        return {
            "ok": False,
            "message": "Verified EIS current-data axis range could not be applied.",
            "axis_range_policy": axis_range_policy,
        }
    legend_anchor_policy = _apply_saved_template_legend_anchor(
        operations,
        graph_name,
        reference_style,
    )
    if not legend_anchor_policy.get("applied"):
        return {
            "ok": False,
            "message": "Verified EIS template legend anchor could not be restored.",
            "legend_anchor_policy": legend_anchor_policy,
        }
    anchor_refresh = _refresh_graph_for_export(operations, graph_name)
    legend_policy = _finalize_reviewed_template_legend(
        operations,
        graph_name,
        product,
        reference_style,
        style,
    )
    if not legend_policy.get("applied"):
        return {
            "ok": False,
            "message": "Verified EIS current legend for slots 3-5 failed.",
            "legend_policy": legend_policy,
        }
    return {
        "ok": True,
        "method": "otpu_then_oth_then_snapshot_then_current_data_axis_and_legend",
        "format_theme_applied": True,
        "style_snapshot_applied": True,
        "apply_default_font": False,
        "apply_axis_titles": True,
        "axis_range_policy": axis_range_policy,
        "legend_anchor_policy": legend_anchor_policy,
        "legend_anchor_refresh": anchor_refresh,
        "legend_policy": legend_policy,
    }


def _bet_template_legend_label(label: str, *, is_desorption: bool) -> str:
    """Keep the reviewed BET legend grammar while substituting the sample name."""
    value = str(label).strip()
    material = re.sub(
        r"(?:[\s_]*\(?(?:adsorption|desorption)\)?)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip(" _")
    if not material:
        material = value or "Series"
    branch = "Desorption" if is_desorption else "Adsorption"
    return f"{material} ({branch})"


def _apply_mott_schottky_source_masks(
    operations: object,
    book_name: str,
    rows: list[list[object]],
    plot_pairs: list[tuple[int, int]],
) -> dict[str, object]:
    mask_writer = getattr(operations, "set_worksheet_column_mask_rows", None)
    if not callable(mask_writer):
        return {"applied": False, "reason": "worksheet_mask_operation_unavailable"}
    if not plot_pairs:
        return {"applied": False, "reason": "mott_plot_pairs_unavailable"}
    applied: list[dict[str, object]] = []
    for series_index, (x_col, y_col) in enumerate(plot_pairs, start=1):
        masked_rows = [
            row_index
            for row_index, row in enumerate(rows, start=1)
            if x_col - 1 < len(row)
            and y_col - 1 < len(row)
            and (x_value := _finite_numeric_value(row[x_col - 1])) is not None
            and _finite_numeric_value(row[y_col - 1]) is not None
            and x_value < -1.0e-8
        ]
        written = mask_writer(book_name, y_col, masked_rows)
        if not getattr(written, "ok", False):
            return {
                "applied": False,
                "reason": "worksheet_mask_write_failed",
                "series_index": series_index,
                "y_column": y_col,
                "message": getattr(written, "message", "mask write failed"),
            }
        applied.append(
            {
                "series_index": series_index,
                "x_column": x_col,
                "y_column": y_col,
                "masked_rows": masked_rows,
            }
        )
    return {
        "applied": True,
        "method": "origin_native_y_column_masks_for_negative_potential_rows",
        "zero_tolerance_v": 1.0e-8,
        "series": applied,
    }


def _validate_adaptive_epr_direct_labels(
    operations: object,
    graph_name: str,
    product: ProductContext,
    product_style: dict[str, object],
) -> dict[str, object]:
    entries = _plain_text_legend_entries(product)
    names = [f"DL{index}" for index in range(1, len(entries) + 1)]
    reader = getattr(operations, "read_graph_text_objects", None)
    if not entries or not callable(reader):
        return {
            "ok": False,
            "status": "blocked",
            "message": "Adaptive EPR current labels or native object readback are unavailable.",
        }
    readback = reader(graph_name, names)
    if not getattr(readback, "ok", False):
        return {
            "ok": False,
            "status": "mismatch",
            "message": getattr(readback, "message", "EPR native label readback failed"),
        }
    objects = [
        dict(value)
        for value in getattr(readback, "payload", {}).get("objects", [])
        if isinstance(value, dict)
    ]
    expected_text = {
        name: origin_bold_text(entry)
        for name, entry in zip(names, entries)
    }
    failures: list[str] = []
    actual_text = {str(value.get("name") or ""): str(value.get("text") or "") for value in objects}
    if actual_text != expected_text:
        failures.append("native direct-label text does not match the current EPR input labels")

    layout = product_style.get("layout_values") if isinstance(product_style, dict) else None
    page_width = _snapshot_axis_value(layout, "page.width")
    page_height = _snapshot_axis_value(layout, "page.height")
    positions = product_style.get("graph_object_positions")
    position_names = {
        str(name)
        for name in positions
        if isinstance(positions, dict) and re.fullmatch(r"DL\d+", str(name), flags=re.IGNORECASE)
    }
    if {name.casefold() for name in position_names} != {name.casefold() for name in names}:
        failures.append("stale or missing EPR direct-label objects remain after save/reopen")
    if page_width is None or page_height is None or page_width <= 0 or page_height <= 0:
        failures.append("page bounds are unavailable for EPR label validation")
    else:
        for value in objects:
            geometry = {
                key: _finite_float(value.get(key))
                for key in ("left", "top", "width", "height")
            }
            name = str(value.get("name") or "")
            if any(number is None for number in geometry.values()):
                failures.append(f"{name}: incomplete page geometry")
                continue
            left = float(geometry["left"])
            top = float(geometry["top"])
            width = float(geometry["width"])
            height = float(geometry["height"])
            if left < 0 or top < 0 or width <= 0 or height <= 0:
                failures.append(f"{name}: invalid page geometry")
            elif left + width > page_width + 1 or top + height > page_height + 1:
                failures.append(f"{name}: outside the Origin page")
    legend_show = _snapshot_axis_value(layout, "legend.show")
    if legend_show is None or abs(legend_show) > 1e-9:
        failures.append("EPR legend is visible even though native direct labels own the sample names")
    return {
        "ok": not failures,
        "status": "matched" if not failures else "mismatch",
        "message": (
            "Adaptive EPR native direct labels contain only current sample names and remain inside the page."
            if not failures
            else "; ".join(failures)
        ),
        "entries": entries,
        "object_names": names,
        "objects": objects,
        "failures": failures,
    }


def _validate_adaptive_epr_axis_bounds(
    product_style: dict[str, object],
    rows: list[list[object]],
    plot_pairs: list[tuple[int, int]],
    reference_style_snapshot: dict[str, object],
) -> dict[str, object]:
    series = _photocurrent_xy_series(rows, plot_pairs)
    layout = product_style.get("layout_values") if isinstance(product_style, dict) else None
    x_from = _snapshot_axis_value(layout, "layer.x.from")
    x_to = _snapshot_axis_value(layout, "layer.x.to")
    y_from = _snapshot_axis_value(layout, "layer.y.from")
    y_to = _snapshot_axis_value(layout, "layer.y.to")
    failures: list[str] = []
    if len(series) != len(plot_pairs) or not series:
        failures.append("current EPR X/Y series are unavailable")
    if None in {x_from, x_to, y_from, y_to}:
        failures.append("reopened EPR axis bounds are unavailable")
    if not failures:
        x_values = [value for values, _ in series for value in values]
        y_values = [value for _, values in series for value in values]
        x_low, x_high = sorted((float(x_from), float(x_to)))
        y_low, y_high = sorted((float(y_from), float(y_to)))
        x_tolerance = max((x_high - x_low) * 1e-9, 1e-12)
        y_tolerance = max((y_high - y_low) * 1e-9, 1e-9)
        if min(x_values) < x_low - x_tolerance or max(x_values) > x_high + x_tolerance:
            failures.append("current EPR magnetic-field data are clipped by the reopened X axis")
        if min(y_values) < y_low - y_tolerance or max(y_values) > y_high + y_tolerance:
            failures.append("current EPR processed traces are clipped by the reopened Y axis")
    if _snapshot_axis_value(layout, "layer.y.showLabels") != 0.0:
        failures.append("reviewed EPR hidden Y tick-value style changed")
    if _snapshot_axis_value(layout, "layer.x.showLabels") != 1.0:
        failures.append("reviewed EPR visible X tick-value style changed")
    page_bounds = _validate_xrd_axis_title_page_bounds(product_style)
    if not page_bounds.get("ok"):
        failures.append(str(page_bounds.get("message") or "EPR axis titles are outside the page"))
    reference_positions = reference_style_snapshot.get("graph_object_positions")
    current_positions = product_style.get("graph_object_positions")
    for object_name in ("XB", "YL"):
        expected = reference_positions.get(object_name) if isinstance(reference_positions, dict) else None
        actual = current_positions.get(object_name) if isinstance(current_positions, dict) else None
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            failures.append(f"reviewed EPR axis-title geometry is unavailable: {object_name}")
            continue
        mismatches = [
            field
            for field in ("left", "top", "width", "height")
            if _finite_float(expected.get(field)) is None
            or _finite_float(actual.get(field)) is None
            or not math.isclose(
                float(actual[field]),
                float(expected[field]),
                rel_tol=0.0,
                abs_tol=1.0,
            )
        ]
        if mismatches:
            failures.append(
                f"reviewed EPR axis-title page geometry changed for {object_name}: {', '.join(mismatches)}"
            )
    return {
        "ok": not failures,
        "status": "matched" if not failures else "mismatch",
        "message": (
            "Adaptive EPR axes contain every current processed point and preserve tick-label visibility."
            if not failures
            else "; ".join(failures)
        ),
        "axis_bounds": {
            "x_from": x_from,
            "x_to": x_to,
            "y_from": y_from,
            "y_to": y_to,
        },
        "axis_title_page_bounds": page_bounds,
        "failures": failures,
    }


def _validate_verified_bet_current_data(
    rows: list[list[object]],
    xy_ranges: list[dict[str, int]],
    graph_snapshot: dict[str, object],
) -> dict[str, object]:
    return _validate_verified_current_data("BET", rows, xy_ranges, graph_snapshot)


def _populate_adaptive_xps_in_situ_workbooks(
    operations: object,
    headers: list[str],
    rows: list[list[object]],
) -> dict[str, object]:
    if len(headers) < 8 or len(headers) % 8 != 0:
        return {"ok": False, "message": "Adaptive XPS source lacks complete sample groups."}
    sample_count = len(headers) // 8
    created_books: list[str] = []
    plot_sources: list[dict[str, object]] = []
    for sample_index in range(sample_count):
        x_index = sample_index * 8
        first = x_index + 1
        bounds = _paired_numeric_row_bounds(rows, x_index, first)
        if bounds is None:
            return {
                "ok": False,
                "message": f"Adaptive XPS sample group {sample_index + 1} has no finite X/Y range.",
            }
        row_from, row_to = bounds
        requested_book = f"Book{sample_index + 2}"
        sheet_name = "Sheet1"
        source_indices = [
            x_index,
            first,
            first + 1,
            first + 3,
            first + 5,
            first + 6,
        ]
        created = operations.create_worksheet(requested_book, sheet_name)
        if not getattr(created, "ok", False):
            return _verified_otpu_failure(
                created,
                f"Adaptive XPS workbook {requested_book} creation failed.",
            )
        actual_book = str(getattr(created, "payload", {}).get("book_name") or "")
        actual_sheet = str(
            getattr(created, "payload", {}).get("sheet_name") or sheet_name
        )
        if actual_book != requested_book:
            return {
                "ok": False,
                "message": f"Origin did not preserve adaptive XPS workbook identity {requested_book}.",
            }
        columns = [
            [
                float(value)
                if source_index < len(row)
                and (value := _finite_numeric_value(row[source_index])) is not None
                else math.nan
                for row in rows
            ]
            for source_index in source_indices
        ]
        written = operations.set_worksheet_data(actual_book, actual_sheet, columns)
        if not getattr(written, "ok", False):
            return _verified_otpu_failure(
                written,
                f"Adaptive XPS workbook {requested_book} data write failed.",
            )
        sample_identity = str(headers[x_index])[: -len("_binding_energy_eV")]
        metadata = [
            {
                "column_index": destination_index,
                "long_name": headers[source_index],
                "unit": "eV" if destination_index == 1 else "a.u.",
                "comment": sample_identity,
                "type": 4 if destination_index == 1 else 1,
            }
            for destination_index, source_index in enumerate(source_indices, start=1)
        ]
        metadata_write = operations.set_worksheet_column_metadata(actual_book, metadata)
        if not getattr(metadata_write, "ok", False):
            return _verified_otpu_failure(
                metadata_write,
                f"Adaptive XPS workbook {requested_book} metadata write failed.",
            )
        for y_column in VERIFIED_XPS_IN_SITU_DESTINATION_Y_COLUMNS:
            plot_sources.append(
                {
                    "book_name": actual_book,
                    "sheet_name": actual_sheet,
                    "x_col": 1,
                    "y_col": y_column,
                    "row_from": row_from,
                    "row_to": row_to,
                }
            )
        created_books.append(actual_book)
    return {
        "ok": True,
        "method": "xps_in_situ_adaptive_native_workbook_per_sample_with_shared_fill_baseline",
        "book_name": created_books[0],
        "book_names": created_books,
        "sheet_count": sample_count,
        "destination_columns_per_book": 6,
        "plot_sources": plot_sources,
    }


def _export_saved_format_theme_product_with_origin(
    operations: object,
    product: ProductContext,
    style: ResolvedPlotStyle,
    plan: object,
    *,
    project_reference_opju: Path | None = None,
    project_reference_graph: str = "",
    require_project_reference: bool = False,
    runtime_dir: Path | None = None,
    style_snapshot_path: str | Path | None = None,
    data_snapshot_path: str | Path | None = None,
    style_execution_decision: dict[str, object] | None = None,
) -> dict[str, object]:
    theme_path = Path(str(getattr(plan, "style_package_path", "") or ""))
    if not theme_path.is_file():
        return {"ok": False, "message": f"Saved Origin format theme not found: {theme_path}", "template_format_plan": plan.to_dict()}
    headers, rows = _read_processed_csv(product.processed_data)
    if len(headers) < 2:
        return {"ok": False, "message": "processed CSV must contain at least one X column and one Y column", "template_format_plan": plan.to_dict()}
    runtime_context = (
        nullcontext(str(runtime_dir))
        if runtime_dir is not None
        else tempfile.TemporaryDirectory(
            prefix="rdop_origin_",
            dir=_neutral_origin_runtime_root(),
            ignore_cleanup_errors=True,
        )
    )
    with runtime_context as runtime_text:
        runtime = Path(runtime_text)
        runtime_theme = runtime / theme_path.name
        shutil.copy2(theme_path, runtime_theme)
        runtime_origin = runtime / product.origin_file.name
        runtime_reference_png = runtime / product.reference_preview_png.name
        runtime_png = runtime / product.preview_png.name
        runtime_tif = runtime / product.figure_tif.name

        external_reference_preview = _export_external_reference_preview_if_requested(
            operations,
            product,
            runtime,
            runtime_reference_png,
            style,
            project_reference_opju=project_reference_opju,
            project_reference_graph=project_reference_graph,
        )
        if not external_reference_preview.get("ok", True):
            return {
                "ok": False,
                "message": str(external_reference_preview.get("message") or "external reference preview export failed"),
                "template_format_plan": plan.to_dict(),
                "external_reference_preview": external_reference_preview,
            }
        if require_project_reference and external_reference_preview.get("reference_kind") != "project_local_reference_opju":
            return {
                "ok": False,
                "message": "Asset-only export requires an independently loaded project-local reference OPJU preview.",
                "template_format_plan": plan.to_dict(),
                "external_reference_preview": external_reference_preview,
                "asset_only": True,
            }

        plot_pairs = _processed_csv_plot_pairs(product, headers)
        if not plot_pairs:
            return {"ok": False, "message": "processed CSV does not contain plottable column pairs", "template_format_plan": plan.to_dict()}
        selected_oth_json = str(
            (style_execution_decision or {}).get("selected_mode") or ""
        ) == "oth-json"
        xrd_adaptive_source_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key == "XRD":
            xrd_adaptive_source_validation = _validate_adaptive_xrd_standard_card_headers(
                headers,
                plot_pairs,
            )
            if not xrd_adaptive_source_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(xrd_adaptive_source_validation.get("message")),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_xrd_source_validation": xrd_adaptive_source_validation,
                }
        operations.new_project()
        adaptive_epr_processing: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key == "EPR":
            adaptive_epr_processing = _prepare_template_epr_origin_processed_workbook(
                operations,
                product,
            )
            if not adaptive_epr_processing.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_epr_processing.get("message")
                        or "Adaptive EPR Origin preprocessing failed."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_processing": adaptive_epr_processing,
                }
            invalidate_processed_table(product.processed_data)
            try:
                headers, rows = _read_processed_csv(product.processed_data)
            except (OSError, ValueError) as exc:
                return {
                    "ok": False,
                    "message": f"Adaptive EPR processed CSV could not be read: {exc}",
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_processing": adaptive_epr_processing,
                }
            plot_pairs = _processed_csv_plot_pairs(product, headers)
            if not plot_pairs:
                return {
                    "ok": False,
                    "message": "Adaptive EPR Origin preprocessing produced no valid shared-X curves.",
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_processing": adaptive_epr_processing,
                }
            reset_after_processing = operations.new_project()
            if not getattr(reset_after_processing, "ok", False):
                return {
                    "ok": False,
                    "message": getattr(
                        reset_after_processing,
                        "message",
                        "Origin reset after adaptive EPR preprocessing failed",
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_processing": adaptive_epr_processing,
                }
        adaptive_xps_workbooks: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key == "XPS_in_situ":
            adaptive_xps_workbooks = _populate_adaptive_xps_in_situ_workbooks(
                operations,
                headers,
                rows,
            )
            if not adaptive_xps_workbooks.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_xps_workbooks.get("message")
                        or "Adaptive XPS native workbook preparation failed."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_xps_workbooks": adaptive_xps_workbooks,
                }
            book_name = str(adaptive_xps_workbooks["book_name"])
        else:
            imported = operations.import_csv_to_worksheet(
                product.processed_data,
                book_name=f"{product.slug}_data",
            )
            if not getattr(imported, "ok", False):
                return {"ok": False, "message": getattr(imported, "message", "CSV import failed"), "template_format_plan": plan.to_dict()}
            book_name = str(imported.payload["book_name"])
        graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
        adaptive_plot_bounds: dict[tuple[int, int], tuple[int, int]] = {}
        if selected_oth_json and product.product_key in {
            "EIS",
            "EPR",
            "PL",
            "Raman",
            "UV-vis DRS",
            "Tauc",
            "XPS_in_situ",
            "XPS_non_in_situ",
        }:
            for x_col, y_col in plot_pairs:
                bounds = _paired_numeric_row_bounds(rows, x_col - 1, y_col - 1)
                if bounds is None or (
                    product.product_key != "PL" and bounds[0] != 1
                ):
                    return {
                        "ok": False,
                        "message": (
                            f"Adaptive {product.product_key} requires one contiguous finite X/Y run "
                            "per spectrum followed only by blank tail rows."
                        ),
                        "template_format_plan": plan.to_dict(),
                    }
                adaptive_plot_bounds[(x_col, y_col)] = bounds
        mott_mask_policy = (
            _apply_mott_schottky_source_masks(
                operations,
                book_name,
                rows,
                plot_pairs,
            )
            if product.product_key == "Mott-Schottky"
            else {"applied": False, "reason": "not_required_for_product"}
        )
        if product.product_key == "Mott-Schottky" and not mott_mask_policy.get("applied"):
            return {
                "ok": False,
                "message": "Mott-Schottky native worksheet mask policy failed.",
                "template_format_plan": plan.to_dict(),
                "mott_schottky_mask_policy": mott_mask_policy,
            }
        origin_plot_sources = (
            [dict(value) for value in adaptive_xps_workbooks.get("plot_sources", []) if isinstance(value, dict)]
            if selected_oth_json and product.product_key == "XPS_in_situ"
            else [
                {
                    "book_name": book_name,
                    "sheet_name": "Sheet1",
                    "x_col": x_col,
                    "y_col": y_col,
                    "row_from": adaptive_plot_bounds.get((x_col, y_col), (0, 0))[0],
                    "row_to": adaptive_plot_bounds.get((x_col, y_col), (0, 0))[1],
                }
                for x_col, y_col in plot_pairs
            ]
        )
        if len(origin_plot_sources) != len(plot_pairs):
            return {
                "ok": False,
                "message": "Origin plot-source topology does not match current processed X/Y pairs.",
                "template_format_plan": plan.to_dict(),
            }
        first_source = origin_plot_sources[0]
        first_header = headers[plot_pairs[0][1] - 1] if plot_pairs[0][1] - 1 < len(headers) else ""
        first_row_kwargs = (
            {
                "row_from": int(first_source["row_from"]),
                "row_to": int(first_source["row_to"]),
            }
            if int(first_source.get("row_from") or 0) > 0
            else {}
        )
        created = operations.create_graph(
            graph_name,
            str(first_source["book_name"]),
            str(first_source["sheet_name"]),
            int(first_source["x_col"]),
            int(first_source["y_col"]),
            plot_type=template_plot_type_for_header(product.product_key, str(first_header), product.plot_type),
            **first_row_kwargs,
        )
        if not getattr(created, "ok", False):
            return {"ok": False, "message": getattr(created, "message", "graph creation failed"), "template_format_plan": plan.to_dict()}
        graph_name = str(created.payload.get("graph_name") or graph_name)
        if product.product_key == "Mott-Schottky":
            mask_display = operations.run_labtalk(
                f'win -a "{quote_labtalk(graph_name)}"; page.mask=0;'
            )
            if not getattr(mask_display, "ok", False):
                return {
                    "ok": False,
                    "message": "Mott-Schottky masked-point display policy failed.",
                    "template_format_plan": plan.to_dict(),
                }
        for (x_col, y_col), origin_source in zip(
            plot_pairs[1:],
            origin_plot_sources[1:],
        ):
            header = headers[y_col - 1] if y_col - 1 < len(headers) else ""
            row_kwargs = (
                {
                    "row_from": int(origin_source["row_from"]),
                    "row_to": int(origin_source["row_to"]),
                }
                if int(origin_source.get("row_from") or 0) > 0
                else {}
            )
            added = operations.add_plot_to_graph(
                graph_name,
                str(origin_source["book_name"]),
                str(origin_source["sheet_name"]),
                int(origin_source["x_col"]),
                int(origin_source["y_col"]),
                plot_type=template_plot_type_for_header(product.product_key, str(header), product.plot_type),
                **row_kwargs,
            )
            if not getattr(added, "ok", False):
                return {"ok": False, "message": getattr(added, "message", f"plot add failed for columns {x_col}/{y_col}"), "template_format_plan": plan.to_dict()}
        applied = operations.apply_graph_theme(graph_name, runtime_theme)
        if not getattr(applied, "ok", False):
            return {"ok": False, "message": getattr(applied, "message", "format theme apply failed"), "template_format_plan": plan.to_dict()}
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
        _apply_template_base_global_policies(operations, graph_name, product, style)
        data_axis_policy = (
            {"applied": False, "reason": "deferred_until_saved_snapshots_are_applied"}
            if product.product_key in {"EIS", "EPR", "PL", "photocurrent", "UV-vis DRS", "Tauc", "XPS_non_in_situ", "XRD"}
            else _apply_embedded_snapshot_data_axis_range(operations, graph_name, product)
        )
        saved_style_snapshot = _load_saved_style_snapshot(
            theme_path,
            explicit_path=style_snapshot_path,
        )
        saved_data_snapshot = _load_saved_data_snapshot(
            theme_path,
            explicit_path=data_snapshot_path,
        )
        photocurrent_source_axis_titles: dict[str, object] | None = None
        if selected_oth_json and product.product_key == "photocurrent":
            photocurrent_source_axis_titles = _validate_photocurrent_axis_titles(
                saved_style_snapshot,
                headers,
            )
            if not photocurrent_source_axis_titles.get("ok"):
                return {
                    "ok": False,
                    "message": str(photocurrent_source_axis_titles["message"]),
                    "template_format_plan": plan.to_dict(),
                    "photocurrent_axis_titles": photocurrent_source_axis_titles,
                }
        adaptive_cardinality = bool(
            (style_execution_decision or {}).get("adaptive_series_cardinality")
        )
        adaptive_uvvis = bool(
            selected_oth_json and product.product_key in {"UV-vis DRS", "Tauc"}
        )
        adaptive_xrd = bool(selected_oth_json and product.product_key == "XRD")
        adaptive_epr = bool(selected_oth_json and product.product_key == "EPR")
        adaptive_eis = bool(selected_oth_json and product.product_key == "EIS")
        adaptive_snapshot_style_applied = bool(
            selected_oth_json
            and saved_style_snapshot
            and apply_style_snapshot(
                operations,
                graph_name,
                saved_style_snapshot,
                apply_default_font=False,
                apply_axis_titles=True,
                preserve_custom_rgb=product.product_key in {"EIS", "Mott-Schottky", "EPR", "PL"},
            )
        )
        plot_sequence = (
            {
                "applied": False,
                "reason": "adaptive_xrd_semantic_styles_replace_fixed_plot_sequence",
            }
            if adaptive_xrd or adaptive_eis
            else _apply_external_reference_plot_sequence(
                operations,
                graph_name,
                saved_style_snapshot
                or (
                    external_reference_preview.get("style_snapshot")
                    if isinstance(external_reference_preview, dict)
                    else {}
                ),
                product=product,
            )
        )
        adaptive_plot_style_policy = (
            _apply_adaptive_xrd_standard_card_plot_styles(
                operations,
                graph_name,
                headers,
            )
            if adaptive_xrd
            else _apply_adaptive_oth_json_plot_styles(
                operations,
                graph_name,
                saved_data_snapshot,
                cycle_styles=adaptive_cardinality or adaptive_uvvis or adaptive_eis,
                preserve_custom_rgb=product.product_key in {
                    "EIS",
                    "Mott-Schottky",
                    "XPS_non_in_situ",
                    "EPR",
                    "PL",
                },
                product_key=product.product_key,
            )
            if selected_oth_json
            else {"applied": False, "reason": "not_oth_json_mode"}
        )
        if (
            selected_oth_json
            and product.product_key in {"EIS", "EPR", "PL", "XPS_in_situ", "XPS_non_in_situ"}
            and not adaptive_plot_style_policy.get("applied")
        ):
            return {
                "ok": False,
                "message": f"Adaptive {product.product_key} per-plot native style restoration failed.",
                "template_format_plan": plan.to_dict(),
                "adaptive_plot_style_policy": adaptive_plot_style_policy,
            }
        reviewed_plot_policy = (
            {"applied": False, "reason": "adaptive_route_uses_all_current_plots"}
            if adaptive_cardinality or adaptive_uvvis or adaptive_xrd or adaptive_epr or adaptive_eis
            else _apply_reviewed_template_plot_policy(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                style,
                data_snapshot=saved_data_snapshot,
            )
        )
        if adaptive_xrd:
            data_axis_policy = _apply_embedded_snapshot_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive XRD current-data axis range restoration failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            axis_title_result = _position_adaptive_xrd_axis_titles(
                operations,
                graph_name,
                product.x_label,
                product.y_label,
                saved_style_snapshot,
                style,
            )
            if not axis_title_result.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive XRD current axis-title restoration failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_title_policy": axis_title_result,
                }
            data_axis_policy["axis_title_policy"] = axis_title_result
        adaptive_mott_guide_policy = {
            "applied": False,
            "reason": "not_required_for_product_or_cardinality",
        }
        if (
            selected_oth_json
            and product.product_key == "Mott-Schottky"
            and adaptive_cardinality
        ):
            adaptive_mott_guide_policy = _apply_mott_schottky_candidate_guides(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                series_count=len(plot_pairs),
            )
            if not adaptive_mott_guide_policy.get("applied"):
                if (
                    adaptive_mott_guide_policy.get("reason")
                    == "no_defensible_common_linear_window"
                ):
                    adaptive_mott_guide_policy = {
                        **adaptive_mott_guide_policy,
                        "status": "omitted",
                        "guides_omitted": True,
                        "manual_check_required": True,
                        "visible_claim": "none",
                        "message": (
                            "No common linear-window candidate passed the quality gate; "
                            "the native current-data curves are retained without fit guides."
                        ),
                    }
                else:
                    return {
                        "ok": False,
                        "message": "Adaptive Mott-Schottky candidate guide construction failed.",
                        "template_format_plan": plan.to_dict(),
                        "mott_schottky_candidate_guides": adaptive_mott_guide_policy,
                    }
        if product.product_key == "XPS_in_situ" and selected_oth_json:
            legend_policy = _apply_adaptive_xps_in_situ_text_policy(
                operations,
                graph_name,
                product,
                style,
                saved_style_snapshot,
                saved_data_snapshot,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive XPS in-situ current annotation/legend policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif product.product_key == "XPS_non_in_situ" and selected_oth_json:
            data_axis_policy = _apply_xps_non_in_situ_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
                reference_data_snapshot=saved_data_snapshot,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive XPS non-in-situ current-data axis range failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            legend_policy = _apply_adaptive_xps_non_in_situ_text_policy(
                operations,
                graph_name,
                product,
                style,
                saved_style_snapshot,
                saved_data_snapshot,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive XPS non-in-situ current annotation/legend policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif adaptive_eis:
            data_axis_policy = _apply_embedded_snapshot_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
                reference_data_snapshot=saved_data_snapshot,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive EIS current-data axis range failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            legend_anchor_policy = _apply_saved_template_legend_anchor(
                operations,
                graph_name,
                saved_style_snapshot,
            )
            if not legend_anchor_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive EIS reviewed legend anchor restoration failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_anchor_policy": legend_anchor_policy,
                }
            current_entries = [
                str(value).strip() for value in product.legend_entries
                if str(value).strip()
            ]
            legend_policy = _update_eis_native_legend(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                style,
                visible_plot_indices=tuple(range(1, len(plot_pairs) + 1)),
                legend_entries=current_entries,
                force_current_visibility=True,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive EIS current native legend/visibility policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
            legend_policy["anchor_policy"] = legend_anchor_policy
        elif adaptive_epr:
            data_axis_policy = _apply_adaptive_epr_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
                style=style,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive EPR current-data axis range failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            legend_policy = _apply_adaptive_epr_direct_labels(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                rows,
                plot_pairs,
                data_axis_policy,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive EPR native direct-label policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif product.product_key == "FTIR" and selected_oth_json:
            legend_policy = _apply_adaptive_ftir_oth_json_text_policy(
                operations,
                graph_name,
                product,
                style,
                saved_style_snapshot,
            )
        elif product.product_key == "BET" and selected_oth_json:
            data_axis_policy = _apply_embedded_snapshot_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
                reference_data_snapshot=saved_data_snapshot,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive BET current-data axis range application failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            legend_policy = _apply_adaptive_bet_oth_json_text_policy(
                operations,
                graph_name,
                product,
                style,
                saved_style_snapshot,
                axis_range_changed=bool(data_axis_policy.get("range_changed")),
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive BET final axis-title/legend policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif product.product_key == "photocurrent" and selected_oth_json:
            data_axis_policy = _apply_embedded_snapshot_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
                reference_data_snapshot=saved_data_snapshot,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive photocurrent current-data axis range application failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            legend_policy = _apply_adaptive_photocurrent_oth_json_text_policy(
                operations,
                graph_name,
                product,
                style,
                saved_style_snapshot,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive photocurrent final axis-title/legend policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif product.product_key == "PL" and selected_oth_json:
            data_axis_policy = _apply_embedded_snapshot_data_axis_range(
                operations,
                graph_name,
                product,
                reference_style_snapshot=saved_style_snapshot,
                reference_data_snapshot=saved_data_snapshot,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive PL current-data axis range application failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            legend_policy = _update_verified_pl_legend(
                operations,
                graph_name,
                product.legend_entries,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive PL current-sample legend replacement failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif adaptive_xrd:
            legend_policy = _apply_xrd_standard_card_legend_and_label(
                operations,
                graph_name,
                product,
                _plain_text_legend_entries(product),
                style,
                apply_reference_plot_style=False,
            )
            if not legend_policy.get("applied"):
                return {
                    "ok": False,
                    "message": "Adaptive XRD standard-card legend/label policy failed.",
                    "template_format_plan": plan.to_dict(),
                    "legend_policy": legend_policy,
                }
        elif adaptive_cardinality or adaptive_uvvis:
            legend_policy = _apply_adaptive_dynamic_legend_policy(
                operations,
                graph_name,
                product,
                style,
                saved_style_snapshot,
            )
        else:
            legend_policy = _apply_cached_style_rich_text_policies(
                operations,
                graph_name,
                product,
                style,
                snapshot=saved_style_snapshot,
            )
        uvvis_guide_policy: dict[str, object] = {
            "applied": False,
            "reason": "not_required_for_product",
        }
        uvvis_axis_title_policy: dict[str, object] = {
            "applied": False,
            "reason": "not_required_for_product",
        }
        if adaptive_uvvis:
            data_axis_policy = _apply_embedded_snapshot_data_axis_range(
                operations,
                graph_name,
                product,
            )
            if not data_axis_policy.get("applied"):
                return {
                    "ok": False,
                    "message": f"Adaptive {product.product_key} current-data axis range application failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_range_policy": data_axis_policy,
                }
            uvvis_axis_title_policy = _apply_uvvis_current_axis_titles(
                operations,
                graph_name,
                product.x_label,
                product.y_label,
            )
            if not uvvis_axis_title_policy.get("applied"):
                return {
                    "ok": False,
                    "message": f"Adaptive {product.product_key} current scientific axis titles failed.",
                    "template_format_plan": plan.to_dict(),
                    "axis_title_policy": uvvis_axis_title_policy,
                }
            if product.product_key == "Tauc":
                uvvis_guide_policy = _remove_tauc_reference_candidate_guides(
                    operations,
                    graph_name,
                )
                if not uvvis_guide_policy.get("applied"):
                    return {
                        "ok": False,
                        "message": "Adaptive Tauc old guide cleanup failed.",
                        "template_format_plan": plan.to_dict(),
                        "tauc_guide_policy": uvvis_guide_policy,
                    }
        legend_policy["adaptive_plot_style"] = adaptive_plot_style_policy
        legend_policy["adaptive_style_snapshot"] = {
            "loaded": bool(saved_style_snapshot),
            "applied": adaptive_snapshot_style_applied,
            "apply_default_font": False,
            "apply_axis_titles": True,
        }
        legend_policy["reviewed_template_plot_policy"] = reviewed_plot_policy
        legend_policy["mott_schottky_mask_policy"] = mott_mask_policy
        legend_policy["adaptive_mott_schottky_candidate_guides"] = (
            adaptive_mott_guide_policy
        )
        legend_policy["tauc_reference_guide_policy"] = uvvis_guide_policy
        legend_policy["final_reviewed_legend"] = (
            {
                "applied": False,
                "reason": "adaptive_oth_json_legend_already_finalized",
            }
            if selected_oth_json and product.product_key in {"BET", "EIS", "EPR", "FTIR", "PL", "photocurrent", "UV-vis DRS", "Tauc", "XRD"}
            else {"applied": False, "reason": "adaptive_cardinality_uses_dynamic_current_legend"}
            if adaptive_cardinality or adaptive_uvvis or adaptive_xrd
            else _finalize_reviewed_template_legend(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                style,
            )
        )
        render_refresh = _refresh_graph_for_export(operations, graph_name)
        legend_layout = avoid_native_legend_overlap(operations, graph_name)
        if not getattr(legend_layout, "ok", False):
            return {
                "ok": False,
                "message": getattr(legend_layout, "message", "native legend layout failed"),
                "template_format_plan": plan.to_dict(),
                "native_legend_layout": getattr(legend_layout, "payload", {}),
            }
        saved = operations.save_project(runtime_origin)
        if not getattr(saved, "ok", False):
            return {"ok": False, "message": getattr(saved, "message", "project save failed"), "template_format_plan": plan.to_dict()}
        reset = operations.new_project()
        if not getattr(reset, "ok", False):
            return {
                "ok": False,
                "message": getattr(reset, "message", "new project before saved product reload failed"),
                "template_format_plan": plan.to_dict(),
            }
        loaded = operations.load_project(runtime_origin)
        if not getattr(loaded, "ok", False):
            return {
                "ok": False,
                "message": scrub_output_text(
                    getattr(loaded, "message", "saved product reload failed"),
                    output_root=product.type_root.parent,
                ),
                "template_format_plan": plan.to_dict(),
            }
        pages_result = operations.list_worksheets()
        if not getattr(pages_result, "ok", False):
            return {
                "ok": False,
                "message": getattr(pages_result, "message", "saved product page listing failed"),
                "template_format_plan": plan.to_dict(),
            }
        pages = getattr(pages_result, "payload", {}).get("pages", [])
        if not isinstance(pages, list):
            return {
                "ok": False,
                "message": "Saved product page listing returned an invalid payload.",
                "template_format_plan": plan.to_dict(),
            }
        graph_pages = [
            str(item["name"])
            for item in pages
            if isinstance(item, dict) and item.get("type") == "graph" and str(item.get("name") or "").strip()
        ]
        matching_graph_pages = [page_name for page_name in graph_pages if page_name == graph_name]
        if len(matching_graph_pages) != 1:
            reason = "missing" if not matching_graph_pages else "ambiguous"
            return {
                "ok": False,
                "message": f"Expected saved graph page {graph_name!r} was {reason} after project reload.",
                "template_format_plan": plan.to_dict(),
                "expected_graph_page": graph_name,
                "available_graph_pages": graph_pages,
            }
        reopened_graph = matching_graph_pages[0]
        try:
            snapshot = read_graph_style_snapshot(
                operations,
                reopened_graph,
                source_label=product.origin_file.name,
                graph_pages=graph_pages,
                prefer_custom_rgb=product.product_key in {"EIS", "Mott-Schottky", "EPR"},
            )
            product_style = snapshot.to_dict()
        except Exception as exc:
            return {
                "ok": False,
                "message": "Saved product style readback failed after project reload: "
                + scrub_output_text(exc, output_root=product.type_root.parent),
                "template_format_plan": plan.to_dict(),
                "expected_graph_page": graph_name,
                "available_graph_pages": graph_pages,
            }
        if str(product_style.get("status") or "") != "extracted" or str(product_style.get("graph_page") or "") != reopened_graph:
            return {
                "ok": False,
                "message": "Saved product style readback did not confirm the reopened graph page.",
                "template_format_plan": plan.to_dict(),
                "expected_graph_page": graph_name,
                "available_graph_pages": graph_pages,
                "product_style": product_style,
            }
        adaptive_xrd_plot_style_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        adaptive_xrd_axis_title_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if adaptive_xrd:
            adaptive_xrd_axis_title_validation = _validate_xrd_axis_title_page_bounds(
                product_style
            )
            if not adaptive_xrd_axis_title_validation.get("ok"):
                return {
                    "ok": False,
                    "message": "Adaptive XRD axis titles moved outside the page after save/reopen.",
                    "template_format_plan": plan.to_dict(),
                    "adaptive_xrd_axis_title_validation": adaptive_xrd_axis_title_validation,
                }
            adaptive_xrd_plot_style_validation = _validate_adaptive_xrd_plot_styles(
                operations,
                reopened_graph,
                len(plot_pairs),
            )
            if not adaptive_xrd_plot_style_validation.get("ok"):
                return {
                    "ok": False,
                    "message": "Adaptive XRD native line/card styles changed after save/reopen.",
                    "template_format_plan": plan.to_dict(),
                    "adaptive_xrd_plot_style_validation": adaptive_xrd_plot_style_validation,
                }
        tauc_guide_cleanup_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key == "Tauc":
            tauc_guide_cleanup_validation = _validate_tauc_reference_guides_removed(
                operations,
                reopened_graph,
                product_style,
            )
            if not tauc_guide_cleanup_validation.get("ok"):
                return {
                    "ok": False,
                    "message": "Adaptive Tauc reference guides remained after save/reopen.",
                    "template_format_plan": plan.to_dict(),
                    "product_style": product_style,
                    "tauc_guide_cleanup_validation": tauc_guide_cleanup_validation,
                }
        current_data_snapshot: dict[str, object] = {}
        current_data_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key in {
            "BET",
            "EIS",
            "EPR",
            "PL",
            "Raman",
            "photocurrent",
            "Mott-Schottky",
            "UV-vis DRS",
            "Tauc",
            "XPS_in_situ",
            "XPS_non_in_situ",
            "XRD",
        }:
            current_data_snapshot = read_graph_data_snapshot(
                operations,
                reopened_graph,
                source_label=product.origin_file.name,
                prefer_custom_rgb=product.product_key in {
                    "EIS",
                    "Mott-Schottky",
                    "EPR",
                },
            )
            validation_ranges = _adaptive_photocurrent_validation_ranges(
                rows,
                plot_pairs,
                mask_negative_x=product.product_key == "Mott-Schottky",
                shared_x_variable_y=product.product_key == "PL",
            )
            if len(validation_ranges) != len(plot_pairs):
                return {
                    "ok": False,
                    "message": (
                        f"Adaptive {product.product_key} processed CSV does not contain strict "
                        "contiguous finite X/Y runs for every plotted pair."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "current_data_snapshot": current_data_snapshot,
                }
            current_data_validation = _validate_verified_current_data(
                product.product_key,
                rows,
                validation_ranges,
                current_data_snapshot,
            )
            if not current_data_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        current_data_validation.get("message")
                        or f"Adaptive {product.product_key} reopened graph data did not match the current CSV."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "current_data_snapshot": current_data_snapshot,
                    "current_data_validation": current_data_validation,
                }
        adaptive_xps_plot_style_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key in {"XPS_in_situ", "XPS_non_in_situ"}:
            adaptive_xps_plot_style_validation = (
                _validate_adaptive_xps_in_situ_reopened_plot_styles(
                    saved_data_snapshot,
                    current_data_snapshot,
                    expected_plot_count=len(plot_pairs),
                )
                if product.product_key == "XPS_in_situ"
                else _validate_adaptive_xps_non_in_situ_reopened_plot_styles(
                    saved_data_snapshot,
                    current_data_snapshot,
                    expected_plot_count=len(plot_pairs),
                )
            )
            if not adaptive_xps_plot_style_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_xps_plot_style_validation.get("message")
                        or "Adaptive XPS plot styles differ from the reviewed role cycle."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_xps_plot_style_validation": adaptive_xps_plot_style_validation,
                }
        adaptive_epr_plot_style_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        adaptive_pl_plot_style_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        adaptive_eis_plot_style_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        adaptive_eis_legend_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        adaptive_epr_direct_label_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        adaptive_epr_axis_validation: dict[str, object] = {
            "ok": True,
            "status": "not_required",
        }
        if selected_oth_json and product.product_key == "PL":
            adaptive_pl_plot_style_validation = (
                _validate_adaptive_reopened_plot_style_cycle(
                    saved_data_snapshot,
                    current_data_snapshot,
                    product_key="PL",
                    reference_plot_count=3,
                    expected_plot_count=len(plot_pairs),
                )
            )
            if not adaptive_pl_plot_style_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_pl_plot_style_validation.get("message")
                        or "Adaptive PL native plot styles changed after save/reopen."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_pl_plot_style_validation": adaptive_pl_plot_style_validation,
                }
        if adaptive_eis:
            adaptive_eis_plot_style_validation = _validate_adaptive_eis_reopened_plot_styles(
                saved_data_snapshot,
                current_data_snapshot,
                expected_plot_count=len(plot_pairs),
            )
            if not adaptive_eis_plot_style_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_eis_plot_style_validation.get("message")
                        or "Adaptive EIS native plot styles changed after save/reopen."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_eis_plot_style_validation": adaptive_eis_plot_style_validation,
                }
            adaptive_eis_legend_validation = _validate_reopened_adaptive_eis_legend(
                operations,
                reopened_graph,
                [str(value).strip() for value in product.legend_entries if str(value).strip()],
            )
            if not adaptive_eis_legend_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_eis_legend_validation.get("message")
                        or "Adaptive EIS native legend changed after save/reopen."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_eis_legend_validation": adaptive_eis_legend_validation,
                }
        if adaptive_epr:
            adaptive_epr_plot_style_validation = _validate_adaptive_epr_reopened_plot_styles(
                saved_data_snapshot,
                current_data_snapshot,
                expected_plot_count=len(plot_pairs),
            )
            if not adaptive_epr_plot_style_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_epr_plot_style_validation.get("message")
                        or "Adaptive EPR native plot styles changed after save/reopen."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_plot_style_validation": adaptive_epr_plot_style_validation,
                }
            adaptive_epr_direct_label_validation = _validate_adaptive_epr_direct_labels(
                operations,
                reopened_graph,
                product,
                product_style,
            )
            if not adaptive_epr_direct_label_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_epr_direct_label_validation.get("message")
                        or "Adaptive EPR native direct labels changed after save/reopen."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_direct_label_validation": adaptive_epr_direct_label_validation,
                }
            adaptive_epr_axis_validation = _validate_adaptive_epr_axis_bounds(
                product_style,
                rows,
                plot_pairs,
                saved_style_snapshot,
            )
            if not adaptive_epr_axis_validation.get("ok"):
                return {
                    "ok": False,
                    "message": str(
                        adaptive_epr_axis_validation.get("message")
                        or "Adaptive EPR current data are clipped after save/reopen."
                    ),
                    "template_format_plan": plan.to_dict(),
                    "adaptive_epr_axis_validation": adaptive_epr_axis_validation,
                }
        bet_product_axis_titles: dict[str, object] | None = None
        if selected_oth_json and product.product_key == "BET":
            bet_y_title_overlay = _read_adaptive_bet_y_title_overlay(
                operations,
                reopened_graph,
            )
            if data_axis_policy.get("range_changed"):
                if not bet_y_title_overlay.get("ok"):
                    return {
                        "ok": False,
                        "message": str(
                            bet_y_title_overlay.get("message")
                            or "Adaptive BET Y-axis title overlay validation failed after reopen."
                        ),
                        "template_format_plan": plan.to_dict(),
                        "product_style": product_style,
                        "bet_y_title_overlay": bet_y_title_overlay,
                    }
                product_style = _effective_bet_style_with_y_title_overlay(
                    product_style,
                    bet_y_title_overlay,
                )
                snapshot = replace(
                    snapshot,
                    layout_values=dict(product_style.get("layout_values") or {}),
                    audit_numeric_values=dict(
                        product_style.get("audit_numeric_values") or {}
                    ),
                    audit_string_values=dict(
                        product_style.get("audit_string_values") or {}
                    ),
                )
            bet_product_axis_titles = _validate_bet_axis_titles(
                product_style,
                headers,
            )
            bet_product_axis_titles["y_title_overlay"] = bet_y_title_overlay
            if not bet_product_axis_titles.get("ok"):
                return {
                    "ok": False,
                    "message": str(bet_product_axis_titles["message"]),
                    "template_format_plan": plan.to_dict(),
                    "product_style": product_style,
                    "bet_axis_titles": bet_product_axis_titles,
                }
        photocurrent_product_axis_titles: dict[str, object] | None = None
        if selected_oth_json and product.product_key == "photocurrent":
            photocurrent_product_axis_titles = _validate_photocurrent_axis_titles(
                product_style,
                headers,
            )
            if not photocurrent_product_axis_titles.get("ok"):
                return {
                    "ok": False,
                    "message": str(photocurrent_product_axis_titles["message"]),
                    "template_format_plan": plan.to_dict(),
                    "product_style": product_style,
                    "photocurrent_axis_titles": photocurrent_product_axis_titles,
                }
        strict_readback = _strict_style_readback(product_style)
        independent_style_snapshot = (
            external_reference_preview.get("style_snapshot")
            if isinstance(external_reference_preview.get("style_snapshot"), dict)
            else {}
        )
        reference_style_snapshot = (
            independent_style_snapshot
            if str(independent_style_snapshot.get("status") or "") == "extracted"
            else saved_style_snapshot
        )
        conformance_reference = (
            _adaptive_eis_conformance_reference(
                reference_style_snapshot,
                saved_data_snapshot,
                len(plot_pairs),
                product_style,
            )
            if adaptive_eis
            else _adaptive_epr_conformance_reference(
                reference_style_snapshot,
                saved_data_snapshot,
                len(plot_pairs),
                product_style,
            )
            if selected_oth_json and product.product_key == "EPR"
            else _adaptive_raman_conformance_reference(
                reference_style_snapshot,
                saved_data_snapshot,
                len(plot_pairs),
            )
            if selected_oth_json and product.product_key == "Raman"
            else _adaptive_xrd_standard_card_conformance_reference(
                reference_style_snapshot,
                len(plot_pairs),
                product_style,
            )
            if selected_oth_json and product.product_key == "XRD"
            else _adaptive_pl_conformance_reference(
                reference_style_snapshot,
                product_style,
            )
            if selected_oth_json and product.product_key == "PL"
            else _verified_otpu_conformance_reference(
                product.product_key,
                _adaptive_uvvis_conformance_reference(
                    product.product_key,
                    reference_style_snapshot,
                    saved_data_snapshot,
                    len(plot_pairs),
                ),
                product_style,
            )
            if selected_oth_json and product.product_key in {"UV-vis DRS", "Tauc"}
            else _verified_otpu_conformance_reference(
                product.product_key,
                reference_style_snapshot,
                product_style,
            )
            if product.product_key in {"BET", "photocurrent", "UV-vis DRS", "Tauc"}
            else reference_style_snapshot
        )
        conformance = compare_style_snapshots(
            conformance_reference,
            snapshot,
            required_line_width_pt=_verified_otpu_required_line_width_pt(
                product.product_key,
                style,
            ),
            require_axis_title_bold=_style_snapshot_axis_title_bold_required(
                reference_style_snapshot
            ),
        ).to_dict()
        adaptive_validation = _adaptive_oth_json_readback_validation(
            product,
            plot_pairs,
            product_style,
            style_execution_decision,
            conformance,
            current_data_validation=current_data_validation,
        )
        if not adaptive_validation.get("ok"):
            return {
                "ok": False,
                "message": str(
                    adaptive_validation.get("message")
                    or "Adaptive OTH+JSON readback validation failed."
                ),
                "template_format_plan": plan.to_dict(),
                "product_style": product_style,
                "conformance": conformance,
                "adaptive_oth_json_validation": adaptive_validation,
            }
        if adaptive_validation.get("series_cardinality_relaxed"):
            conformance = _adaptive_series_count_conformance(
                conformance,
                adaptive_validation,
            )
        if selected_oth_json and str(conformance.get("status") or "").casefold() == "fail":
            return {
                "ok": False,
                "message": (
                    "Adaptive OTH+JSON style conformance retained a hard failure "
                    "after the permitted series-cardinality differences were removed."
                ),
                "template_format_plan": plan.to_dict(),
                "product_style": product_style,
                "conformance": conformance,
                "adaptive_oth_json_validation": adaptive_validation,
            }
        conformance["reference_source"] = (
            external_reference_preview.get("reference_kind")
            if reference_style_snapshot is independent_style_snapshot
            else "saved_style_snapshot"
        )
        png = operations.export_graph(reopened_graph, runtime_png, "png", dpi=style.export_dpi)
        tif = _export_native_tif_with_physical_validation(
            operations,
            reopened_graph,
            runtime_tif,
            dpi=style.export_dpi,
        )
        metadata_warnings = [
            warning
            for warning in (
                _strip_raster_metadata(runtime_png, dpi=style.export_dpi),
            )
            if warning
        ]
        missing = [path for path in (runtime_origin, runtime_png, runtime_tif) if not path.exists() or path.stat().st_size == 0]
        if missing:
            return {
                "ok": False,
                "message": "missing artifacts: " + "; ".join(path.name for path in missing),
                "template_format_plan": plan.to_dict(),
            }
        if not getattr(png, "ok", False) or not bool(tif.get("ok")):
            return {
                "ok": False,
                "message": scrub_output_text(
                    f"{getattr(png, 'message', '')}; {tif.get('message', '')}",
                    output_root=product.type_root.parent,
                ),
                "template_format_plan": plan.to_dict(),
            }
        operations.new_project()
        _copy_runtime_artifact(runtime_origin, product.origin_file)
        if runtime_reference_png.exists():
            _copy_runtime_artifact(runtime_reference_png, product.reference_preview_png)
        _copy_runtime_artifact(runtime_png, product.preview_png)
        _copy_runtime_artifact(runtime_tif, product.figure_tif)
    missing = [path for path in (product.origin_file, product.preview_png, product.figure_tif) if not path.exists() or path.stat().st_size == 0]
    if missing:
        return {
            "ok": False,
            "message": "missing copied artifacts: " + "; ".join(_product_output_path(product.type_root.parent, path) for path in missing),
            "template_format_plan": plan.to_dict(),
        }
    return {
        "ok": True,
        "message": "Origin saved format-theme export succeeded after save/reopen/readback.",
        "template_format_plan": plan.to_dict(),
        "origin_processing": {
            "required": True,
            "applied": True,
            "method": "saved_format_theme_apply",
            "processing_location": "Origin clean target graph with project-local .oth format theme applied",
            "style_package_path": _product_output_path(product.type_root.parent, theme_path),
            "graph_page": reopened_graph,
            "neutral_runtime": True,
            "raster_metadata_stripped": not metadata_warnings,
            "metadata_warnings": metadata_warnings,
            "tif_resolution_evidence": tif.get("evidence", {}),
            "axis_range_policy": data_axis_policy,
            "uvvis_axis_title_policy": uvvis_axis_title_policy,
            "legend_policy": legend_policy,
            "render_refresh": render_refresh,
            "adaptive_oth_json_validation": adaptive_validation,
            "adaptive_xps_plot_style_validation": adaptive_xps_plot_style_validation,
            "adaptive_eis_plot_style_validation": adaptive_eis_plot_style_validation,
            "adaptive_eis_legend_validation": adaptive_eis_legend_validation,
            "adaptive_epr_processing": adaptive_epr_processing,
            "adaptive_epr_plot_style_validation": adaptive_epr_plot_style_validation,
            "adaptive_pl_plot_style_validation": adaptive_pl_plot_style_validation,
            "adaptive_epr_direct_label_validation": adaptive_epr_direct_label_validation,
            "adaptive_epr_axis_validation": adaptive_epr_axis_validation,
            "adaptive_xrd_plot_style_validation": adaptive_xrd_plot_style_validation,
            "adaptive_xrd_axis_title_validation": adaptive_xrd_axis_title_validation,
            "adaptive_xps_workbooks": adaptive_xps_workbooks,
            "adaptive_xrd_source_validation": xrd_adaptive_source_validation,
            "bet_axis_titles": bet_product_axis_titles,
            "photocurrent_axis_titles": photocurrent_product_axis_titles,
            "current_data_validation": current_data_validation,
            "tauc_guide_cleanup_validation": tauc_guide_cleanup_validation,
            "adaptive_json_assets": {
                "style_snapshot_loaded": bool(saved_style_snapshot),
                "style_snapshot_applied": adaptive_snapshot_style_applied,
                "data_snapshot_loaded": bool(saved_data_snapshot),
                "data_snapshot_applied": bool(
                    selected_oth_json and adaptive_plot_style_policy.get("applied")
                ),
            },
            "reference_opju_loaded": False if selected_oth_json else None,
            "reference_opju_used_as_product_base": False,
        },
        "external_reference_preview": external_reference_preview,
        "external_reference_plot_sequence": plot_sequence,
        "saved_style_snapshot": {"loaded": bool(saved_style_snapshot)},
        "exemplar_style": reference_style_snapshot,
        "product_style": product_style,
        "strict_style_readback": strict_readback,
        "conformance": conformance,
        "adaptive_oth_json_validation": adaptive_validation,
        "adaptive_xps_plot_style_validation": adaptive_xps_plot_style_validation,
        "adaptive_eis_plot_style_validation": adaptive_eis_plot_style_validation,
        "adaptive_eis_legend_validation": adaptive_eis_legend_validation,
        "adaptive_epr_processing": adaptive_epr_processing,
        "adaptive_epr_plot_style_validation": adaptive_epr_plot_style_validation,
        "adaptive_pl_plot_style_validation": adaptive_pl_plot_style_validation,
        "adaptive_epr_direct_label_validation": adaptive_epr_direct_label_validation,
        "adaptive_epr_axis_validation": adaptive_epr_axis_validation,
        "adaptive_xrd_plot_style_validation": adaptive_xrd_plot_style_validation,
        "adaptive_xrd_axis_title_validation": adaptive_xrd_axis_title_validation,
        "adaptive_xps_workbooks": adaptive_xps_workbooks,
        "adaptive_xrd_source_validation": xrd_adaptive_source_validation,
        "bet_axis_titles": bet_product_axis_titles,
        "photocurrent_axis_titles": photocurrent_product_axis_titles,
        "current_data_snapshot": current_data_snapshot,
        "current_data_validation": current_data_validation,
        "xps_component_fill": _saved_format_theme_xps_fill_intent(product),
        "reopened_graph": reopened_graph,
        "tif_resolution_evidence": tif.get("evidence", {}),
        "line_width_policy_pt": _verified_otpu_required_line_width_pt(
            product.product_key,
            style,
        ),
        "axis_title_bold_policy": style.font_bold,
    }


def _export_external_reference_preview_if_requested(
    operations: object,
    product: ProductContext,
    runtime: Path,
    runtime_reference_png: Path,
    style: ResolvedPlotStyle,
    *,
    project_reference_opju: Path | None = None,
    project_reference_graph: str = "",
) -> dict[str, object]:
    source = product.external_reference_opju
    graph_name = str(product.external_reference_graph or "").strip()
    external_selected = source is not None or bool(graph_name)
    if external_selected and (source is None or not graph_name):
        return {
            "requested": True,
            "ok": False,
            "message": "External reference selection is incomplete; both OPJU and graph page are required.",
            "reference_kind": "external_reference_opju",
        }
    if external_selected:
        reference_kind = "external_reference_opju"
        reference_source = product.external_reference_source
    else:
        source = project_reference_opju
        graph_name = str(project_reference_graph or "").strip()
        reference_kind = "project_local_reference_opju"
        reference_source = "project_origin_style_asset"
    if source is None or not graph_name:
        return {"requested": False, "ok": True, "message": "No independent reference OPJU was selected."}
    if not source.is_file():
        return {
            "requested": True,
            "ok": False,
            "message": f"Independent reference OPJU missing: {source}",
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "reference_kind": reference_kind,
        }
    source_hash_before = file_sha256(source)
    runtime_reference_opju = runtime / f"independent_reference{source.suffix.casefold()}"
    shutil.copy2(source, runtime_reference_opju)
    try:
        runtime_reference_opju.chmod(0o444)
    except OSError as exc:
        return {
            "requested": True,
            "ok": False,
            "message": f"Could not make the isolated reference OPJU copy read-only: {exc}",
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "reference_kind": reference_kind,
        }
    operations.new_project()
    loaded = operations.load_project(runtime_reference_opju)
    if not getattr(loaded, "ok", False):
        return {
            "requested": True,
            "ok": False,
            "message": scrub_output_text(
                getattr(loaded, "message", "independent reference OPJU load failed"),
                output_root=product.type_root.parent,
            ),
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "reference_kind": reference_kind,
        }
    pages_result = operations.list_worksheets()
    if not getattr(pages_result, "ok", False):
        return {
            "requested": True,
            "ok": False,
            "message": "Could not enumerate graph pages in the independent reference OPJU.",
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "reference_kind": reference_kind,
        }
    available_graph_pages = [
        str(page.get("name"))
        for page in getattr(pages_result, "payload", {}).get("pages", [])
        if isinstance(page, dict) and page.get("type") == "graph"
    ]
    if graph_name not in available_graph_pages:
        return {
            "requested": True,
            "ok": False,
            "message": (
                "Requested independent reference graph page does not exist: "
                f"{graph_name}"
            ),
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "available_graph_pages": available_graph_pages,
            "reference_kind": reference_kind,
        }
    exported = operations.export_graph(graph_name, runtime_reference_png, "png", dpi=style.export_dpi)
    snapshot_payload: dict[str, object] = {}
    try:
        snapshot_payload = read_graph_style_snapshot(
            operations,
            graph_name,
            source_label=source.name,
            prefer_custom_rgb=product.product_key == "Mott-Schottky",
        ).to_dict()
    except Exception as exc:
        snapshot_payload = {"status": "readback_failed", "message": str(exc)}
    metadata_warning = _strip_raster_metadata(runtime_reference_png, dpi=style.export_dpi) if runtime_reference_png.exists() else ""
    if not getattr(exported, "ok", False) or not runtime_reference_png.exists() or runtime_reference_png.stat().st_size == 0:
        return {
            "requested": True,
            "ok": False,
            "message": scrub_output_text(
                getattr(exported, "message", "independent reference graph export failed"),
                output_root=product.type_root.parent,
            ),
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "reference_kind": reference_kind,
        }
    if file_sha256(source) != source_hash_before:
        return {
            "requested": True,
            "ok": False,
            "message": "Independent reference source changed during isolated preview export.",
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
            "reference_kind": reference_kind,
        }
    return {
        "requested": True,
        "ok": True,
        "source_opju": _product_output_path(product.type_root.parent, source),
        "graph_page": graph_name,
        "source": reference_source,
        "reference_kind": reference_kind,
        "read_only_runtime_copy": True,
        "runtime_copy_write_protected": True,
        "used_as_product_base": False,
        "source_sha256": source_hash_before,
        "preview_png": _product_output_path(product.type_root.parent, product.reference_preview_png),
        "style_snapshot": snapshot_payload,
        "raster_metadata_stripped": not metadata_warning,
        "metadata_warning": metadata_warning,
    }


def _apply_external_reference_plot_sequence(
    operations: object,
    graph_name: str,
    snapshot: object,
    *,
    product: ProductContext | None = None,
) -> dict[str, object]:
    if not isinstance(snapshot, dict):
        return {"applied": False, "reason": "missing external reference style snapshot"}
    colors = [_to_int(value) for value in snapshot.get("plot_colors", []) if _to_int(value) is not None]
    if not colors:
        return {"applied": False, "reason": "external reference style snapshot has no plot colors"}
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    if not plot_names:
        return {"applied": False, "reason": "target graph has no readable plots"}
    skipped_reference_plots: list[int] = []
    plotted_headers: list[tuple[int, str]] = []
    if product is not None and product.product_key == "XRD":
        try:
            headers, _rows = _read_processed_csv(product.processed_data)
        except Exception:
            headers = []
        plotted_headers = _xrd_plotted_y_headers(product, headers)
        skipped_reference_plots = [
            index
            for index, (_csv_index, header) in enumerate(plotted_headers, start=1)
            if is_template_xrd_reference_stick_header(str(header))
        ]
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    applied: list[dict[str, object]] = []
    sample_color_sequence = _xrd_standard_card_sample_color_sequence(colors) if skipped_reference_plots else ()
    for index, plot_name in enumerate(plot_names, start=1):
        if index in skipped_reference_plots:
            continue
        if sample_color_sequence and index <= len(sample_color_sequence):
            color = sample_color_sequence[index - 1]
        else:
            color = colors[(index - 1) % len(colors)]
        operations.run_labtalk(f"set {plot_name} -c {color};")
        operations.run_labtalk(f"set {plot_name} -cl {color};")
        applied.append({"plot": plot_name, "color": color})
    return {
        "applied": True,
        "colors": colors,
        "sample_color_sequence": list(sample_color_sequence),
        "target_plots": len(plot_names),
        "applied_plots": applied,
        "skipped_reference_plot_indices": skipped_reference_plots,
    }


def _xrd_standard_card_sample_color_sequence(colors: list[int]) -> tuple[int, ...]:
    sequence: list[int] = []
    for index, fallback_color in enumerate(XRD_STANDARD_CARD_SAMPLE_COLOR_SEQUENCE):
        color = colors[index] if index < len(colors) and colors[index] not in (0, 1) else fallback_color
        sequence.append(color)
    return tuple(sequence)


def _validate_adaptive_xrd_standard_card_headers(
    headers: list[str],
    plot_pairs: list[tuple[int, int]],
) -> dict[str, object]:
    """Validate the one-layer shared-X XRD+card adaptive input contract."""

    failures: list[str] = []
    if not headers or str(headers[0]).strip().casefold() != "two_theta_deg":
        failures.append("adaptive XRD shared X header must be 'two_theta_deg'")
    y_headers = [str(header).strip() for header in headers[1:]]
    if not y_headers or any(not header for header in y_headers):
        failures.append("adaptive XRD requires nonempty sample and reference-card headers")
    expected_pairs = [(1, index) for index in range(2, len(headers) + 1)]
    if plot_pairs != expected_pairs:
        failures.append("adaptive XRD must plot every shared-X Y column in CSV order")
    card_indices = [
        index
        for index, header in enumerate(y_headers, start=1)
        if is_template_xrd_reference_stick_header(header)
    ]
    if len(card_indices) != 1:
        failures.append(
            "adaptive XRD requires exactly one reference-card header; "
            "use XRD_no_card when no standard card is supplied"
        )
    elif card_indices[0] != len(y_headers):
        failures.append("adaptive XRD reference-card header must be the final Y column")
    sample_headers = [
        header for header in y_headers if not is_template_xrd_reference_stick_header(header)
    ]
    if not sample_headers:
        failures.append("adaptive XRD requires at least one sample column before the card")
    if len({header.casefold() for header in sample_headers}) != len(sample_headers):
        failures.append("adaptive XRD sample headers must be unique")
    ok = not failures
    return {
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "message": (
            "Adaptive XRD has one final reference-card column and all current sample columns."
            if ok
            else "; ".join(failures)
        ),
        "failures": failures,
        "sample_headers": sample_headers,
        "reference_card_header": (
            y_headers[card_indices[0] - 1] if len(card_indices) == 1 else ""
        ),
        "reference_card_count": len(card_indices),
        "expected_plot_count": len(y_headers),
    }


def _apply_adaptive_xrd_standard_card_plot_styles(
    operations: object,
    graph_name: str,
    headers: list[str],
) -> dict[str, object]:
    """Apply native sample-line/card-drop roles to the adaptive one-layer graph."""

    validation = _validate_adaptive_xrd_standard_card_headers(
        headers,
        [(1, index) for index in range(2, len(headers) + 1)],
    )
    if not validation.get("ok"):
        return {"applied": False, "reason": validation.get("message"), "validation": validation}
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    styles = _adaptive_xrd_plot_style_specs(int(validation["expected_plot_count"]))
    if len(plot_names) != len(styles):
        return {
            "applied": False,
            "reason": "current_plot_count_does_not_match_xrd_card_role_mapping",
            "expected_plot_count": len(styles),
            "actual_plot_count": len(plot_names),
        }
    graph = quote_labtalk(graph_name)
    for plot_name, spec in zip(plot_names, styles):
        commands = " ".join(
            f"set {plot_name} -{option} {_origin_number(value)};"
            for option, value in dict(spec["style"]).items()
        )
        result = operations.run_labtalk(f'win -a "{graph}"; {commands}')
        if not getattr(result, "ok", False):
            return {
                "applied": False,
                "reason": "origin_xrd_adaptive_native_style_write_failed",
                "plot_index": spec["plot_index"],
                "plot_name": plot_name,
            }
    readback = _validate_adaptive_xrd_plot_styles(operations, graph_name, len(styles))
    return {
        **readback,
        "applied": bool(readback.get("ok")),
        "method": "adaptive_xrd_one_layer_native_sample_lines_and_reference_card_column_sticks",
    }


def _adaptive_xrd_plot_style_specs(plot_count: int) -> list[dict[str, object]]:
    sample_count = max(0, plot_count - 1)
    colors = [
        XRD_STANDARD_CARD_ADAPTIVE_SAMPLE_COLORS[
            (sample_count - index - 1) % len(XRD_STANDARD_CARD_ADAPTIVE_SAMPLE_COLORS)
        ]
        for index in range(sample_count)
    ]
    specs = [
        {
            "plot_index": index + 1,
            "role": "sample_pattern",
            "style": {"c": color, "cl": color, "w": 1500, "d": 0, "l": 1, "k": 0, "z": 9, "lh": 0, "lv": 0, "s": 1},
        }
        for index, color in enumerate(colors)
    ]
    if plot_count > 0:
        specs.append(
            {
                "plot_index": plot_count,
                "role": "reference_card_sticks",
                "style": {
                    "c": XRD_STANDARD_CARD_ADAPTIVE_CARD_COLOR,
                    "cl": XRD_STANDARD_CARD_ADAPTIVE_CARD_COLOR,
                    "w": 250,
                    "d": 0,
                    "l": 0,
                    "k": 0,
                    "z": 9,
                    "lh": 0,
                    "lv": 0,
                    "pbc": XRD_STANDARD_CARD_ADAPTIVE_STICK_COLOR,
                    "pfb": XRD_STANDARD_CARD_ADAPTIVE_STICK_COLOR,
                    "pfc": XRD_STANDARD_CARD_ADAPTIVE_STICK_COLOR,
                    "pbs": 0,
                    "pbw": 0.5,
                    "s": 1,
                },
            }
        )
    return specs


def _validate_adaptive_xrd_plot_styles(
    operations: object,
    graph_name: str,
    plot_count: int,
) -> dict[str, object]:
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    specs = _adaptive_xrd_plot_style_specs(plot_count)
    if len(plot_names) != len(specs):
        return {
            "ok": False,
            "status": "mismatch",
            "message": "adaptive XRD plot count changed before native style readback",
            "expected_plot_count": len(specs),
            "actual_plot_count": len(plot_names),
        }
    plots: list[dict[str, object]] = []
    failures: list[str] = []
    for plot_name, spec in zip(plot_names, specs):
        expected = dict(spec["style"])
        values = _read_plot_style_options(
            operations,
            plot_name,
            tuple(f"-{option}" for option in expected),
        )
        mismatches: list[str] = []
        for option, expected_value in expected.items():
            value = _finite_float(values.get(option))
            if value is None:
                mismatches.append(option)
                continue
            if not math.isclose(value, float(expected_value), rel_tol=0.0, abs_tol=1e-6):
                mismatches.append(option)
        if mismatches:
            failures.append(f"plot {spec['plot_index']}: {', '.join(mismatches)}")
        plots.append({**spec, "plot_name": plot_name, "readback": values, "mismatches": mismatches})
    return {
        "ok": not failures,
        "status": "matched" if not failures else "mismatch",
        "message": (
            "Adaptive XRD native sample-line and reference-card column-stick styles match."
            if not failures
            else "; ".join(failures)
        ),
        "plot_count": len(plots),
        "sample_count": max(0, len(plots) - 1),
        "reference_card_plot_index": len(plots),
        "plots": plots,
    }


def _adaptive_xrd_standard_card_conformance_reference(
    style_snapshot: dict[str, object],
    plot_count: int,
    product_style: dict[str, object],
) -> dict[str, object]:
    """Create the explicit one-layer semantic comparison target for adaptive XRD."""

    result = dict(style_snapshot)
    sample_count = max(0, plot_count - 1)
    specs = _adaptive_xrd_plot_style_specs(plot_count)
    sample_colors = [int(dict(spec["style"])["c"]) for spec in specs[:-1]]
    result.update(
        {
            "layer_count": 1,
            "plot_count": plot_count,
            "plot_colors": sample_colors + [XRD_STANDARD_CARD_ADAPTIVE_CARD_COLOR],
            "plot_line_colors": sample_colors + [XRD_STANDARD_CARD_ADAPTIVE_CARD_COLOR],
            "plot_line_widths": [
                XRD_STANDARD_CARD_STICK_WIDTH
            ] * sample_count + [250],
            "marker_shapes": [0] * plot_count,
            "marker_sizes": [9] * plot_count,
            "plot_visibility": [1.0] * plot_count,
        }
    )
    layout_values = dict(result.get("layout_values") or {})
    current_layout = dict(product_style.get("layout_values") or {})
    for field in (
        "layer.y.from",
        "layer.y.to",
        "xb.x",
        "xb.y",
        "yl.x",
        "yl.y",
        "legend.x",
        "legend.y",
    ):
        if field in current_layout:
            layout_values[field] = current_layout[field]
    layout_values["page.nlayers"] = 1.0
    result["layout_values"] = layout_values
    audit = dict(result.get("audit_numeric_values") or {})
    audit["page.nlayers"] = 1.0
    result["audit_numeric_values"] = audit
    return result


def _adaptive_oth_json_readback_validation(
    product: ProductContext,
    plot_pairs: list[tuple[int, int]],
    product_style: dict[str, object],
    decision: dict[str, object] | None,
    conformance: dict[str, object],
    *,
    current_data_validation: dict[str, object] | None = None,
) -> dict[str, object]:
    if str((decision or {}).get("selected_mode") or "") != "oth-json":
        return {"ok": True, "status": "not_required", "series_cardinality_relaxed": False}
    expected = len(plot_pairs)
    try:
        actual = int(product_style.get("plot_count") or 0)
    except (TypeError, ValueError):
        actual = 0
    contract_count = int((decision or {}).get("contract_series_count") or 0)
    relaxed = contract_count > 0 and expected != contract_count
    failures: list[str] = []
    if actual != expected:
        failures.append(
            f"reopened graph has {actual} curves; current CSV requires {expected}"
        )
    raw_visibility = product_style.get("plot_visibility")
    visibility = (
        [_finite_float(value) for value in raw_visibility]
        if isinstance(raw_visibility, list)
        else []
    )
    all_current_plots_visible = (
        len(visibility) == expected
        and all(value is not None and value > 0.5 for value in visibility)
    )
    requires_all_current_plots_visible = relaxed or product.product_key in {
        "EIS",
        "EPR",
        "PL",
        "UV-vis DRS",
        "Tauc",
        "XRD",
    }
    if requires_all_current_plots_visible and not all_current_plots_visible:
        failures.append(
            "not every current CSV curve is visible after adaptive save/reopen"
        )
    if not relaxed and str(conformance.get("status") or "").casefold() == "fail":
        failures.append("fixed-cardinality OTH+JSON style conformance failed")
    requires_current_data_match = product.product_key in {
        "BET",
        "EIS",
        "EPR",
        "PL",
        "Raman",
        "photocurrent",
        "Mott-Schottky",
        "UV-vis DRS",
        "Tauc",
        "XPS_in_situ",
        "XPS_non_in_situ",
        "XRD",
    }
    current_data_match = bool(
        isinstance(current_data_validation, dict)
        and current_data_validation.get("ok") is True
        and current_data_validation.get("status") == "matched"
    )
    if requires_current_data_match and not current_data_match:
        failures.append("reopened graph X/Y values do not match the current processed CSV")
    xrd_structure: dict[str, object] = {"ok": True, "status": "not_required"}
    if product.product_key == "XRD":
        try:
            layer_count = int(product_style.get("layer_count") or 0)
        except (TypeError, ValueError):
            layer_count = 0
        xrd_structure = {
            "ok": layer_count == 1 and actual == expected,
            "status": "matched" if layer_count == 1 and actual == expected else "mismatch",
            "expected_layer_count": 1,
            "actual_layer_count": layer_count,
            "expected_plot_count": expected,
            "actual_plot_count": actual,
        }
        if layer_count != 1:
            failures.append(
                f"adaptive XRD must reopen as one layer; found {layer_count}"
            )
    epr_structure: dict[str, object] = {"ok": True, "status": "not_required"}
    if product.product_key == "EPR":
        try:
            layer_count = int(product_style.get("layer_count") or 0)
        except (TypeError, ValueError):
            layer_count = 0
        epr_structure = {
            "ok": layer_count == 1 and actual == expected,
            "status": "matched" if layer_count == 1 and actual == expected else "mismatch",
            "expected_layer_count": 1,
            "actual_layer_count": layer_count,
            "expected_plot_count": expected,
            "actual_plot_count": actual,
        }
        if layer_count != 1:
            failures.append(f"adaptive EPR must reopen as one layer; found {layer_count}")
    eis_structure: dict[str, object] = {"ok": True, "status": "not_required"}
    if product.product_key == "EIS":
        try:
            layer_count = int(product_style.get("layer_count") or 0)
        except (TypeError, ValueError):
            layer_count = 0
        eis_structure = {
            "ok": layer_count == 1 and actual == expected,
            "status": "matched" if layer_count == 1 and actual == expected else "mismatch",
            "expected_layer_count": 1,
            "actual_layer_count": layer_count,
            "expected_plot_count": expected,
            "actual_plot_count": actual,
        }
        if layer_count != 1:
            failures.append(f"adaptive EIS must reopen as one layer; found {layer_count}")
    return {
        "ok": not failures,
        "product_key": product.product_key,
        "status": "accepted" if not failures else "blocked",
        "message": (
            "Adaptive OTH+JSON graph curve count matches the current CSV after save/reopen."
            if not failures
            else "; ".join(failures)
        ),
        "current_csv_pair_count": expected,
        "reopened_plot_count": actual,
        "contract_series_count": contract_count,
        "series_cardinality_relaxed": relaxed,
        "all_current_plots_visible": all_current_plots_visible,
        "all_current_plots_visible_required": requires_all_current_plots_visible,
        "one_to_one_claim_allowed": False,
        "saved_reopened": True,
        "native_tif_600dpi_required": True,
        "current_plot_values_match_csv": (
            current_data_match if requires_current_data_match else None
        ),
        "current_data_validation": dict(current_data_validation or {}),
        "xrd_adaptive_structure": xrd_structure,
        "epr_adaptive_structure": epr_structure,
        "eis_adaptive_structure": eis_structure,
    }


def _adaptive_photocurrent_validation_ranges(
    rows: list[list[object]],
    plot_pairs: list[tuple[int, int]],
    *,
    mask_negative_x: bool = False,
    shared_x_variable_y: bool = False,
) -> list[dict[str, object]]:
    series = (
        _shared_x_contiguous_y_series(rows, plot_pairs)
        if shared_x_variable_y
        else _photocurrent_xy_series(rows, plot_pairs)
    )
    if len(series) != len(plot_pairs):
        return []
    ranges: list[dict[str, object]] = []
    for (x_column, y_column), (x_values, _y_values) in zip(plot_pairs, series):
        bounds = (
            _paired_numeric_row_bounds(rows, x_column - 1, y_column - 1)
            if shared_x_variable_y
            else (1, len(x_values))
        )
        if bounds is None:
            return []
        row_from, row_to = bounds
        record: dict[str, int | list[int]] = {
            "x_col": x_column,
            "y_col": y_column,
            "row_from": row_from,
            "row_to": row_to,
            "source_x_index": x_column - 1,
            "source_y_index": y_column - 1,
            "source_row_from": row_from,
            "source_row_to": row_to,
        }
        if mask_negative_x:
            record["expected_y_masked_rows"] = [
                row_index
                for row_index, value in enumerate(x_values, start=1)
                if value < -1.0e-8
            ]
        ranges.append(record)
    return ranges


def _adaptive_series_count_conformance(
    conformance: dict[str, object],
    validation: dict[str, object],
) -> dict[str, object]:
    payload = dict(conformance)
    raw_issues = conformance.get("issues")
    issues = [dict(value) for value in raw_issues if isinstance(value, dict)] if isinstance(raw_issues, list) else []
    cardinality_fields = {
        "plot_count",
        "plot_colors",
        "plot_line_colors",
        "plot_line_widths",
        "plot_line_styles",
        "plot_symbol_shapes",
        "plot_symbol_sizes",
        "marker_shapes",
        "marker_sizes",
        "plot_visibility",
    }
    cardinality_changed = (
        int(validation.get("current_csv_pair_count") or 0)
        != int(validation.get("contract_series_count") or 0)
    )
    all_current_plots_visible = validation.get("all_current_plots_visible") is True

    def intentional_adaptive_difference(issue: dict[str, object]) -> bool:
        field = str(issue.get("field") or "")
        if field in cardinality_fields:
            return True
        if (
            field == "layer_count"
            and cardinality_changed
            and str(validation.get("product_key") or "") == "Raman"
        ):
            # The fixed Raman OTPU uses a second overlay layer for its middle
            # trace.  Variable-cardinality OTH+JSON instead builds one native
            # Origin layer containing exactly the current spectra.
            return all_current_plots_visible
        # A fixed template may intentionally hide surplus reference plots.  In
        # an adaptive graph every plot represents current input data, so those
        # plots must be visible.  Treat that indexed visibility difference as
        # part of the cardinality adaptation only after readback proves that
        # every current plot is visible; other indexed style differences remain
        # hard conformance issues.
        return (
            cardinality_changed
            and all_current_plots_visible
            and re.fullmatch(r"plot_visibility\[\d+\]", field) is not None
        )

    retained = [
        issue
        for issue in issues
        if not intentional_adaptive_difference(issue)
    ]
    payload["original_status"] = conformance.get("status", "")
    payload["original_issues"] = issues
    payload["issues"] = retained
    payload["status"] = (
        "fail"
        if any(str(item.get("severity") or "").casefold() == "fail" for item in retained)
        else "pass"
    )
    payload["adaptive_series_cardinality_relaxed"] = True
    payload["adaptive_validation"] = dict(validation)
    return payload


def _load_saved_style_snapshot(
    style_package_path: Path,
    *,
    explicit_path: str | Path | None = None,
) -> dict[str, object]:
    snapshot_path = (
        Path(explicit_path)
        if explicit_path is not None
        else style_package_path.parent.parent
        / "snapshots"
        / f"{style_package_path.stem}.json"
    )
    return _load_json_object(snapshot_path)


def _load_saved_data_snapshot(
    style_package_path: Path,
    *,
    explicit_path: str | Path | None = None,
) -> dict[str, object]:
    snapshot_path = (
        Path(explicit_path)
        if explicit_path is not None
        else style_package_path.parent.parent
        / "data_snapshots"
        / f"{style_package_path.stem}.json"
    )
    return _load_json_object(snapshot_path)


def _load_json_object(path: str | Path | None) -> dict[str, object]:
    if path is None:
        return {}
    source = Path(path)
    try:
        loaded = read_origin_style_json(source)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _refresh_graph_for_export(operations: object, graph_name: str) -> dict[str, object]:
    graph = quote_labtalk(graph_name)
    update = operations.run_labtalk(f'win -a "{graph}"; doc -uw;')
    repaint = operations.run_labtalk(f'win -a "{graph}"; draw -uwi;')
    return {
        "applied": bool(getattr(update, "ok", False)),
        "document_update": bool(getattr(update, "ok", False)),
        "immediate_repaint": bool(getattr(repaint, "ok", False)),
        "immediate_repaint_best_effort": True,
    }


def _to_int(value: object) -> int | None:
    try:
        number = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    return number


def _saved_format_theme_xps_fill_intent(product: ProductContext) -> dict[str, object]:
    required = product.product_key.startswith("XPS")
    return {
        "required": required,
        "applied": required,
        "policy": "XPS component fill/gradient formatting is applied from the project-local Origin .oth format theme to the clean target graph.",
    }


def _restore_adaptive_xps_native_graph_objects(
    operations: object,
    graph_name: str,
    style_snapshot: dict[str, object],
    *,
    expected_names: list[str],
    restore_names: set[str] | None = None,
) -> dict[str, object]:
    records = style_snapshot.get("adaptive_native_graph_objects")
    if not isinstance(records, list):
        return {"applied": False, "reason": "adaptive_native_graph_objects_missing"}
    if [str(value.get("name") or "") for value in records if isinstance(value, dict)] != expected_names:
        return {"applied": False, "reason": "adaptive_native_graph_objects_incomplete"}
    if any(not isinstance(record, dict) for record in records):
        return {"applied": False, "reason": "adaptive_native_graph_object_malformed"}
    if restore_names is not None:
        records = [record for record in records if record["name"] in restore_names]
    graph = quote_labtalk(graph_name)
    restored: list[str] = []
    for record in records:
        object_name = str(record["name"])
        operations.run_labtalk(f'win -a "{graph}"; label -r {object_name};')
        created = operations.run_labtalk(
            f'win -a "{graph}"; label -n {object_name} "x";'
        )
        if not getattr(created, "ok", False):
            return {
                "applied": False,
                "reason": "native_graph_object_creation_failed",
                "object_name": object_name,
            }
        app = getattr(operations, "app", None)
        try:
            layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
        except Exception:
            layer = None
        graph_object = _find_origin_graph_object(layer, object_name) if layer else None
        if graph_object is None:
            return {
                "applied": False,
                "reason": "native_graph_object_readback_failed",
                "object_name": object_name,
            }
        try:
            graph_object.Text = str(record.get("text") or "")
        except Exception:
            return {
                "applied": False,
                "reason": "native_graph_object_text_failed",
                "object_name": object_name,
            }
        styled = _style_graph_object(
            operations,
            graph_name,
            object_name,
            font_name=str(record.get("font_name") or "Arial"),
            font_size=int(record.get("font_size") or 16),
            color=int(record.get("color") or 1),
            left=int(record.get("left") or 0),
            top=int(record.get("top") or 0),
            width=int(record.get("width") or 0),
            height=int(record.get("height") or 0),
            bold=0,
            background=0,
            border=0,
            frame=0,
            fill=0,
        )
        if not styled:
            return {
                "applied": False,
                "reason": "native_graph_object_style_failed",
                "object_name": object_name,
            }
        restored.append(object_name)
    return {
        "applied": len(restored) == len(records),
        "method": "project_local_json_to_native_origin_graph_objects",
        "object_names": restored,
    }


def _apply_adaptive_xps_in_situ_text_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    style_snapshot: dict[str, object],
    data_snapshot: dict[str, object],
) -> dict[str, object]:
    """Keep native XPS annotations for three samples; use a native legend otherwise."""

    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"processed_data_unavailable: {exc}"}
    if len(headers) < 8 or len(headers) % 8 != 0:
        return {"applied": False, "reason": "incomplete_xps_sample_groups"}
    sample_count = len(headers) // 8
    x_suffix = "_binding_energy_eV"
    sample_labels = [
        str(headers[sample_index * 8])[: -len(x_suffix)]
        for sample_index in range(sample_count)
    ]
    graph = quote_labtalk(graph_name)
    native_objects = _restore_adaptive_xps_native_graph_objects(
        operations,
        graph_name,
        style_snapshot,
        expected_names=["Text", *(f"Text{index}" for index in range(1, 10))],
        restore_names=None if sample_count == 3 else {"Text"},
    )
    if not native_objects.get("applied"):
        return {
            "applied": False,
            "reason": "adaptive_native_graph_object_restore_failed",
            "native_graph_objects": native_objects,
        }
    if sample_count == 3:
        hidden = operations.run_labtalk(f'win -a "{graph}"; label -r Legend;')
        annotation_policy = _update_verified_xps_in_situ_annotations(
            operations,
            graph_name,
            product,
        )
        same_data = _xps_in_situ_current_data_matches_reference(
            product,
            data_snapshot,
        )
        return {
            "applied": bool(getattr(hidden, "ok", False))
            and bool(annotation_policy.get("applied")),
            "method": "native_xps_three_sample_annotations_without_legend",
            "sample_count": sample_count,
            "sample_labels": sample_labels,
            "same_data_reference_match": same_data,
            "annotation_policy": annotation_policy,
            "native_graph_objects": native_objects,
            "stale_reference_annotations_removed": False,
        }

    removed: list[str] = []
    for object_name in (f"Text{index}" for index in range(1, 10)):
        result = operations.run_labtalk(
            f'win -a "{graph}"; label -r {object_name};'
        )
        if getattr(result, "ok", False):
            removed.append(object_name)
    measured_plot_indices = [1 + sample_index * 7 for sample_index in range(sample_count)]
    legend_font_size = _reviewed_template_legend_font_size(style_snapshot, style)
    native_legend = update_native_legend(
        operations, graph_name, sample_labels, plot_indices=measured_plot_indices,
    )
    _style_graph_object(
        operations,
        graph_name,
        "Legend",
        font_name=style.font_family or "Arial",
        font_size=legend_font_size,
        color=1,
    )
    return {
        "applied": native_legend.ok,
        "native_legend": native_legend.payload,
        "native_legend_message": native_legend.message,
        "method": "native_xps_variable_sample_legend",
        "sample_count": sample_count,
        "sample_labels": sample_labels,
        "measured_plot_indices": measured_plot_indices,
        "stale_reference_annotations_removed": len(removed) == 9,
        "removed_annotation_objects": removed,
        "native_graph_objects": native_objects,
        "legend_font_size": legend_font_size,
    }


def _apply_adaptive_xps_non_in_situ_text_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    style_snapshot: dict[str, object],
    data_snapshot: dict[str, object],
) -> dict[str, object]:
    """Keep the reviewed two-sample native annotations; use a native legend otherwise."""

    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"processed_data_unavailable: {exc}"}
    if len(headers) < 10 or (len(headers) - 1) % 9 != 0:
        return {"applied": False, "reason": "incomplete_xps_non_in_situ_sample_groups"}
    sample_count = (len(headers) - 1) // 9
    sample_labels = [
        str(headers[1 + sample_index * 9])[
            : -len(VERIFIED_XPS_NON_IN_SITU_ROLE_SUFFIXES[0])
        ]
        for sample_index in range(sample_count)
    ]
    graph = quote_labtalk(graph_name)
    object_names = ["Text", "Text1", "Text2", "Text3", "Text4", "Text5"]
    native_objects = _restore_adaptive_xps_native_graph_objects(
        operations,
        graph_name,
        style_snapshot,
        expected_names=object_names,
        restore_names=None if sample_count == 2 else set(),
    )
    if not native_objects.get("applied"):
        return {
            "applied": False,
            "reason": "adaptive_native_graph_object_restore_failed",
            "native_graph_objects": native_objects,
        }
    if sample_count == 2:
        hidden = operations.run_labtalk(f'win -a "{graph}"; label -r Legend;')
        annotation_policy = _update_verified_xps_non_in_situ_annotations(
            operations,
            graph_name,
            product,
        )
        same_data = _uvvis_current_data_matches_reference(product, data_snapshot)
        return {
            "applied": bool(getattr(hidden, "ok", False))
            and bool(annotation_policy.get("applied")),
            "method": "native_xps_non_in_situ_two_sample_annotations_without_legend",
            "sample_count": sample_count,
            "sample_labels": sample_labels,
            "same_data_reference_match": same_data,
            "annotation_policy": annotation_policy,
            "native_graph_objects": native_objects,
            "stale_reference_annotations_removed": False,
        }

    removed: list[str] = []
    for object_name in object_names:
        result = operations.run_labtalk(
            f'win -a "{graph}"; label -r {object_name};'
        )
        if getattr(result, "ok", False):
            removed.append(object_name)
    measured_plot_indices = [7 + sample_index * 9 for sample_index in range(sample_count)]
    legend_font_size = _reviewed_template_legend_font_size(style_snapshot, style)
    native_legend = update_native_legend(
        operations, graph_name, sample_labels, plot_indices=measured_plot_indices,
    )
    _style_graph_object(
        operations,
        graph_name,
        "Legend",
        font_name=style.font_family or "Arial",
        font_size=legend_font_size,
        color=1,
    )
    return {
        "applied": native_legend.ok,
        "native_legend": native_legend.payload,
        "native_legend_message": native_legend.message,
        "method": "native_xps_non_in_situ_variable_sample_legend",
        "sample_count": sample_count,
        "sample_labels": sample_labels,
        "measured_plot_indices": measured_plot_indices,
        "stale_reference_annotations_removed": len(removed) == len(object_names),
        "removed_annotation_objects": removed,
        "native_graph_objects": native_objects,
        "legend_font_size": legend_font_size,
    }


def _apply_reviewed_template_plot_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    snapshot: dict[str, object],
    style: ResolvedPlotStyle,
    *,
    data_snapshot: dict[str, object] | None = None,
    restore_plot_styles: bool = True,
) -> dict[str, object]:
    visible_indices = REVIEWED_TEMPLATE_VISIBLE_PLOTS.get(product.product_key)
    if visible_indices is None:
        return {"applied": False, "reason": "not_required_for_product"}
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    if len(plot_names) < max(visible_indices):
        return {
            "applied": False,
            "reason": "insufficient_plot_count",
            "plot_count": len(plot_names),
            "required_visible_indices": list(visible_indices),
        }

    graph = quote_labtalk(graph_name)
    plot_style_policy = (
        _apply_reviewed_template_plot_styles(
            operations,
            graph_name,
            data_snapshot or {},
        )
        if restore_plot_styles
        else {
            "applied": False,
            "reason": "fixed_otpu_and_style_snapshot_preserve_native_plot_styles",
        }
    )
    visibility_commands: list[str] = []
    for index in range(1, len(plot_names) + 1):
        show = 1 if index in visible_indices else 0
        command = f'win -a "{graph}"; layer.plot{index}.show={show};'
        operations.run_labtalk(command)
        visibility_commands.append(command)

    entries = list(product.legend_entries)[: len(visible_indices)]
    if len(entries) != len(visible_indices):
        return {
            "applied": False,
            "reason": "legend_entry_count_mismatch",
            "visible_indices": list(visible_indices),
            "legend_entries": entries,
        }
    legend_font_size = _reviewed_template_legend_font_size(snapshot, style)
    legend_com_text_refreshed = update_native_legend(
        operations, graph_name, entries, plot_indices=visible_indices,
    ).ok
    _style_graph_object(
        operations,
        graph_name,
        "Legend",
        font_name=style.font_family or "Arial",
        font_size=legend_font_size,
        color=1,
    )
    if snapshot:
        _apply_exemplar_axis_title_text(operations, graph_name, snapshot)
    mott_guide_policy = (
        _apply_mott_schottky_candidate_guides(operations, graph_name, product, snapshot)
        if product.product_key == "Mott-Schottky"
        else {"applied": False, "reason": "not_required_for_product"}
    )
    return {
        "applied": legend_com_text_refreshed,
        "visible_indices": list(visible_indices),
        "hidden_indices": [index for index in range(1, len(plot_names) + 1) if index not in visible_indices],
        "legend_entries": entries,
        "legend_font_size": legend_font_size,
        "legend_line_samples_preserved": True,
        "legend_com_text_refreshed": legend_com_text_refreshed,
        "axis_titles_restored_from_style_snapshot": bool(snapshot),
        "plot_style": plot_style_policy,
        "mott_schottky_candidate_guides": mott_guide_policy,
    }


def _reviewed_template_legend_rich_text(label: object) -> str:
    text = str(label or "").strip()
    return (
        text.replace("BiOBr0.5Cl0.5", r"BiOBr\-(0.5)Cl\-(0.5)")
        .replace("CuWO4", r"CuWO\-(4)")
    )


def _ftir_native_legend_labels(entries: list[str] | tuple[str, ...]) -> list[str]:
    """Preserve reviewed inline column-label formatting for native legends."""
    reviewed = {
        "BiOBr0.5Cl0.5": r"\b(\i( )\c1(BiOBr)\-(\c1(0.5))\c1(Cl)\-(\c1(0.5)))",
        "CuWO4": r"\b(\i( )CuWO\-(4))",
        "BiCu-10": r"\b(\i( )BiCu-10)",
    }
    return [reviewed.get(str(label), origin_bold_text(label)) for label in entries]


def _refresh_reviewed_template_legend_com_text(
    operations: object,
    graph_name: str,
    product: ProductContext,
) -> bool:
    visible_indices = REVIEWED_TEMPLATE_VISIBLE_PLOTS.get(product.product_key)
    if visible_indices is None:
        return False
    entries = _plain_text_legend_entries(product)
    if len(entries) != len(visible_indices):
        return False
    return update_native_legend(
        operations, graph_name, entries, plot_indices=visible_indices,
    ).ok


def _update_eis_native_legend(
    operations: object,
    graph_name: str,
    product: ProductContext,
    snapshot: dict[str, object],
    style: ResolvedPlotStyle,
    *,
    visible_plot_indices: tuple[int, ...] | None = None,
    legend_entries: list[str] | None = None,
    force_current_visibility: bool = False,
) -> dict[str, object]:
    if product.product_key != "EIS":
        return {"applied": False, "reason": "not_required_for_product"}
    visible_indices = (
        tuple(visible_plot_indices)
        if visible_plot_indices is not None
        else REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]
    )
    entries = (
        [str(value).strip() for value in legend_entries]
        if legend_entries is not None
        else _plain_text_legend_entries(product)
    )
    if len(entries) != len(visible_indices):
        return {"applied": False, "reason": "legend_entry_count_mismatch"}
    if any(not value for value in entries) or len(
        {value.casefold() for value in entries}
    ) != len(entries):
        return {"applied": False, "reason": "legend_entries_must_be_nonempty_and_unique"}
    visibility_commands: list[str] = []
    if force_current_visibility:
        plot_names = (
            operations._plot_names(graph_name)
            if hasattr(operations, "_plot_names")
            else []
        )
        if len(plot_names) != len(visible_indices):
            return {
                "applied": False,
                "reason": "adaptive_eis_plot_and_legend_count_mismatch",
                "plot_count": len(plot_names),
                "legend_entry_count": len(entries),
            }
        for plot_index in range(1, len(plot_names) + 1):
            command = (
                f'win -a "{quote_labtalk(graph_name)}"; '
                f"layer.plot{plot_index}.show=1;"
            )
            shown = operations.run_labtalk(command)
            if not getattr(shown, "ok", False):
                return {
                    "applied": False,
                    "reason": "adaptive_eis_plot_visibility_restore_failed",
                    "plot_index": plot_index,
                }
            visibility_commands.append(command)
    updated = update_native_legend(
        operations, graph_name, entries, plot_indices=visible_indices,
    )
    font_size = _reviewed_template_legend_font_size(snapshot, style)
    if updated.ok:
        _style_graph_object(
            operations, graph_name, "Legend",
            font_name=style.font_family or "Arial", font_size=font_size, color=1,
        )
    return {
        "applied": updated.ok,
        "method": "origin_legendupdate_long_name",
        "object_name": "Legend",
        "entries": entries,
        "visible_plot_indices": list(visible_indices),
        "all_current_plots_visible": bool(force_current_visibility),
        "visibility_commands": visibility_commands,
        "font_size": font_size,
        "message": updated.message,
    }


def _validate_reopened_adaptive_eis_legend(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    app = getattr(operations, "app", None)
    reasons: list[str] = []
    actual_text = ""
    labels: list[str] = []
    visible = False
    try:
        if app is None or not entries:
            raise ValueError("Origin app or current entries are unavailable")
        layer = (app.FindGraphLayer(f"[{graph_name}]Layer1")
                 or app.FindGraphLayer(f"[{graph_name}]1")
                 or app.FindGraphLayer(graph_name))
        legend = _find_origin_graph_object(layer, "Legend")
        if legend is None:
            raise ValueError("native Origin legend is missing")
        actual_text = str(legend.Text or "")
        visible = float(legend.Show) > 0.5
        if _find_origin_graph_object(layer, "rdop_reviewed_legend") is not None:
            reasons.append("obsolete separate EIS legend overlay remains")
        symbols = [int(value) for value in re.findall(r"\\l\((\d+)\)", actual_text, flags=re.I)]
        substitutions = [int(value) for value in re.findall(r"%\((\d+)\)", actual_text)]
        expected_indices = list(range(1, len(entries) + 1))
        if symbols != expected_indices or substitutions != expected_indices:
            reasons.append("native legend curve-to-column substitutions differ")
        for index in expected_indices:
            read = operations.run_labtalk(
                f'range -wy __rdop_legend_y=[{graph_name}]1!{index}; '
                '__rdop_legend_label$=__rdop_legend_y[L]$;'
            )
            if not read.ok:
                raise ValueError("mapped Y long-name readback failed")
            labels.append(str(app.LTStr("__rdop_legend_label$") or ""))
        if labels != [origin_bold_text(entry) for entry in entries]:
            reasons.append("mapped Y labels differ from current sample names")
        if not visible:
            reasons.append("native Origin legend is hidden")
    except Exception as exc:
        reasons.append(str(exc))
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": "Native EIS legend and mapped sample labels match." if not reasons else "; ".join(reasons),
        "entries": entries,
        "actual_text": actual_text,
        "mapped_y_long_names": labels,
        "native_legend_visible": visible,
        "reasons": reasons,
    }


def _reviewed_template_legend_font_size(
    snapshot: dict[str, object],
    style: ResolvedPlotStyle,
) -> int:
    layout = snapshot.get("layout_values") if isinstance(snapshot, dict) else None
    saved_size = _snapshot_axis_value(layout, "legend.fsize")
    if saved_size is not None and saved_size > 0:
        return int(round(saved_size))
    return int(style.legend_font_size or 26)


def _finalize_reviewed_template_legend(
    operations: object,
    graph_name: str,
    product: ProductContext,
    snapshot: dict[str, object],
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    if product.product_key == "EIS":
        return _update_eis_native_legend(
            operations,
            graph_name,
            product,
            snapshot,
            style,
        )
    if product.product_key in REVIEWED_TEMPLATE_VISIBLE_PLOTS:
        return {
            "applied": _refresh_reviewed_template_legend_com_text(operations, graph_name, product),
            "method": "origin_legendupdate_long_name",
        }
    return {"applied": False, "reason": "not_required_for_product"}


def _apply_reviewed_template_plot_styles(
    operations: object,
    graph_name: str,
    data_snapshot: dict[str, object],
    *,
    cycle_styles: bool = False,
    preserve_custom_rgb: bool = False,
) -> dict[str, object]:
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    records = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
    if not plot_names:
        return {"applied": False, "reason": "target_graph_has_no_readable_plots"}
    if not isinstance(records, list) or not records or (
        not cycle_styles and len(records) < len(plot_names)
    ):
        return {
            "applied": False,
            "reason": "saved_data_snapshot_plot_styles_unavailable",
            "target_plot_count": len(plot_names),
            "snapshot_plot_count": len(records) if isinstance(records, list) else 0,
        }

    option_fields = (
        ("line_color", "-cl", True),
        ("line_width_pt", "-wp", False),
        ("line_style", "-l", True),
        ("symbol_shape", "-k", True),
        ("symbol_size", "-z", False),
        ("fill_area", "-pfb", True),
        ("fill_color", "-pfc", True),
        ("border_color", "-pbc", True),
        ("border_width", "-pbw", False),
    )
    applied: list[dict[str, object]] = []
    graph = quote_labtalk(graph_name)
    target_records = (
        [records[index % len(records)] for index in range(len(plot_names))]
        if cycle_styles
        else records
    )
    for plot_name, record in zip(plot_names, target_records):
        plot_style = record.get("style") if isinstance(record, dict) else None
        if not isinstance(plot_style, dict):
            return {
                "applied": False,
                "reason": "saved_data_snapshot_plot_style_missing",
                "plot_name": plot_name,
            }
        commands: list[str] = []
        restored: dict[str, float | int] = {}
        for field, option, integer_value in option_fields:
            value = _finite_float(plot_style.get(field))
            if value is None:
                continue
            rendered: int | float = int(round(value)) if integer_value else value
            rendered_value = (
                _origin_color_value_for_labtalk(rendered)
                if preserve_custom_rgb and field == "line_color"
                else _origin_number(rendered)
            )
            commands.append(f"set {plot_name} {option} {rendered_value};")
            restored[field] = rendered
        color = _finite_float(plot_style.get("color"))
        if color is not None:
            if preserve_custom_rgb:
                color_option, color_value = _origin_plot_color_for_labtalk(color)
            else:
                color_option, color_value = "-c", str(int(round(color)))
            if color_option == "-cse":
                # Persist the same native state used by the reviewed Origin
                # line+symbol plots: the combined colour and symbol edge are
                # the marker RGB, while the line colour remains independent.
                # The reviewed project has custom colours enabled (``-cue 1``),
                # and Origin otherwise falls back to the line colour on reopen.
                # ``-cl`` can also relink/overwrite the symbol edge, so the edge
                # colour must be restored after the line colour.
                commands.append(f"set {plot_name} -cue 1;")
                commands.append(f"set {plot_name} -c {color_value};")
                line_color = _finite_float(plot_style.get("line_color"))
                if line_color is not None:
                    commands.append(
                        f"set {plot_name} -cl "
                        f"{_origin_color_value_for_labtalk(line_color)};"
                    )
                commands.append(f"set {plot_name} -cse {color_value};")
            else:
                commands.append(f"set {plot_name} {color_option} {color_value};")
            restored["color"] = int(round(color))
        if not commands:
            return {
                "applied": False,
                "reason": "saved_data_snapshot_plot_style_empty",
                "plot_name": plot_name,
            }
        result = operations.run_labtalk(f'win -a "{graph}"; ' + " ".join(commands))
        if not getattr(result, "ok", False):
            return {
                "applied": False,
                "reason": "origin_plot_style_restore_failed",
                "plot_name": plot_name,
            }
        applied.append({"plot_name": plot_name, "style": restored})
    return {
        "applied": True,
        "method": "project_local_data_snapshot_plot_style_restore",
        "plot_count": len(applied),
        "cycled_for_variable_series_count": cycle_styles,
        "plots": applied,
    }


def _apply_adaptive_oth_json_plot_styles(
    operations: object,
    graph_name: str,
    data_snapshot: dict[str, object],
    *,
    cycle_styles: bool,
    preserve_custom_rgb: bool = False,
    product_key: str = "",
) -> dict[str, object]:
    snapshot = data_snapshot
    if product_key == "Raman":
        raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
        if isinstance(raw_plots, list):
            plots = [dict(value) for value in raw_plots if isinstance(value, dict)]
            plots.sort(
                key=lambda value: (
                    str(value.get("book_name") or ""),
                    int(value.get("sheet_index") or 0),
                    int(value.get("x_col_index") or 0),
                )
            )
            snapshot = {**data_snapshot, "plots": plots}
    if product_key in {"UV-vis DRS", "Tauc"}:
        raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
        if isinstance(raw_plots, list):
            plots = [dict(value) for value in raw_plots if isinstance(value, dict)]
            visible_start = 3 if product_key == "UV-vis DRS" else 1
            visible_count = 3 if product_key == "UV-vis DRS" else 2
            visible_plots = plots[visible_start : visible_start + visible_count]
            if visible_plots:
                snapshot = {
                    **data_snapshot,
                    "plots": visible_plots,
                    "plot_count": len(visible_plots),
                }
    if product_key == "EIS":
        snapshot = _adaptive_eis_style_cycle_snapshot(data_snapshot)
        cycle_styles = True
    if product_key == "XPS_non_in_situ":
        raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
        if isinstance(raw_plots, list) and len(raw_plots) >= 9:
            snapshot = {
                **data_snapshot,
                "plots": [
                    dict(value)
                    for value in raw_plots[:9]
                    if isinstance(value, dict)
                ],
                "plot_count": 9,
            }
            cycle_styles = True
    restored = _apply_reviewed_template_plot_styles(
        operations,
        graph_name,
        snapshot,
        cycle_styles=cycle_styles,
        preserve_custom_rgb=preserve_custom_rgb,
    )
    if product_key != "XPS_non_in_situ" or not restored.get("applied"):
        return restored
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    native_formats = operations.apply_graph_plot_format_contracts(
        graph_name,
        _xps_non_in_situ_adaptive_plot_format_contracts(len(plot_names)),
    )
    if not getattr(native_formats, "ok", False):
        return {
            "applied": False,
            "reason": "xps_non_in_situ_native_fill_style_restore_failed",
            "plot_style_restore": restored,
            "message": getattr(native_formats, "message", "native fill restore failed"),
        }
    return {
        **restored,
        "method": "project_local_nine_role_style_cycle_with_native_origin_fill_contracts",
        "native_plot_format_readback": dict(
            getattr(native_formats, "payload", {}) or {}
        ),
    }


def _adaptive_uvvis_conformance_reference(
    product_key: str,
    style_snapshot: dict[str, object],
    data_snapshot: dict[str, object],
    series_count: int,
) -> dict[str, object]:
    raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
    if not isinstance(raw_plots, list) or series_count <= 0:
        return dict(style_snapshot)
    plots = [dict(value) for value in raw_plots if isinstance(value, dict)]
    visible_start = 3 if product_key == "UV-vis DRS" else 1
    visible_count = 3 if product_key == "UV-vis DRS" else 2
    visible_plots = plots[visible_start : visible_start + visible_count]
    if not visible_plots:
        return dict(style_snapshot)
    result = dict(style_snapshot)
    data_style_fields = {
        "plot_colors": "color",
        "plot_line_colors": "line_color",
        "plot_line_widths": "line_width_origin_units",
        "marker_shapes": "symbol_shape",
        "marker_sizes": "symbol_size",
    }
    for field, data_style_field in data_style_fields.items():
        values = [
            (plot.get("style") or {}).get(data_style_field)
            if isinstance(plot.get("style"), dict)
            else None
            for plot in visible_plots
        ]
        if any(value is None for value in values):
            continue
        result[field] = [values[index % len(values)] for index in range(series_count)]
    result["plot_visibility"] = [1.0] * series_count
    result["plot_count"] = series_count
    return result


def _adaptive_epr_conformance_reference(
    style_snapshot: dict[str, object],
    data_snapshot: dict[str, object],
    series_count: int,
    product_style: dict[str, object],
) -> dict[str, object]:
    """Compare invariant EPR style while separately gating current data geometry."""

    raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
    plots = [dict(value) for value in raw_plots if isinstance(value, dict)] if isinstance(raw_plots, list) else []
    if len(plots) != 3 or series_count <= 0:
        return dict(style_snapshot)
    plots.sort(
        key=lambda value: (
            int(value.get("layer_index") or 0),
            int(value.get("plot_index") or 0),
        )
    )
    result = dict(style_snapshot)
    style_fields = {
        "plot_colors": "color",
        "plot_line_colors": "line_color",
        "plot_line_widths": "line_width_origin_units",
        "marker_shapes": "symbol_shape",
        "marker_sizes": "symbol_size",
    }
    for field, style_field in style_fields.items():
        values = [
            (plot.get("style") or {}).get(style_field)
            if isinstance(plot.get("style"), dict)
            else None
            for plot in plots
        ]
        if any(value is None for value in values):
            continue
        result[field] = [values[index % 3] for index in range(series_count)]
    result["plot_count"] = series_count
    result["layer_count"] = 1
    result["plot_visibility"] = [1.0] * series_count

    current_layout = dict(product_style.get("layout_values") or {})
    layout = dict(result.get("layout_values") or {})
    for field in (
        "layer.x.from",
        "layer.x.to",
        "layer.y.from",
        "layer.y.to",
        "xb.x",
        "xb.y",
        "yl.x",
        "yl.y",
        "legend.x",
        "legend.y",
        "legend.fsize",
    ):
        if field in current_layout:
            layout[field] = current_layout[field]
    result["layout_values"] = layout
    audit = dict(result.get("audit_numeric_values") or {})
    for field in (
        "legend.x",
        "legend.y",
        "legend.fsize",
    ):
        if field in current_layout:
            audit[field] = current_layout[field]
    result["audit_numeric_values"] = audit
    return result


def _adaptive_eis_conformance_reference(
    style_snapshot: dict[str, object],
    data_snapshot: dict[str, object],
    series_count: int,
    product_style: dict[str, object],
) -> dict[str, object]:
    """Keep EIS geometry invariant while cycling the reviewed visible markers."""
    result = _verified_otpu_conformance_reference(
        "EIS",
        style_snapshot,
        product_style,
    )
    cycle_snapshot = _adaptive_eis_style_cycle_snapshot(data_snapshot)
    plots = [
        dict(value)
        for value in cycle_snapshot.get("plots", [])
        if isinstance(value, dict)
    ]
    if len(plots) != len(REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]) or series_count <= 0:
        return result
    style_fields = {
        "plot_colors": "color",
        "plot_line_colors": "line_color",
        "plot_line_widths": "line_width_origin_units",
        "marker_shapes": "symbol_shape",
        "marker_sizes": "symbol_size",
    }
    for field, style_field in style_fields.items():
        values = [
            (plot.get("style") or {}).get(style_field)
            if isinstance(plot.get("style"), dict)
            else None
            for plot in plots
        ]
        if any(value is None for value in values):
            continue
        result[field] = [values[index % len(values)] for index in range(series_count)]
    result["plot_count"] = series_count
    result["layer_count"] = 1
    result["plot_visibility"] = [1.0] * series_count
    expected_strings = dict(result.get("audit_string_values") or {})
    actual_strings = dict(product_style.get("audit_string_values") or {})
    if "legend.text$" in actual_strings:
        expected_strings["legend.text$"] = actual_strings["legend.text$"]
    result["audit_string_values"] = expected_strings
    return result


def _adaptive_pl_conformance_reference(
    style_snapshot: dict[str, object],
    product_style: dict[str, object],
) -> dict[str, object]:
    """Keep PL formatting invariant while allowing current-data geometry/text."""

    result = dict(style_snapshot)
    data_dependent_fields = {
        "layer.x.from",
        "layer.x.to",
        "layer.y.from",
        "layer.y.to",
        "xb.x",
        "xb.y",
        "yl.x",
        "yl.y",
        "legend.x",
        "legend.y",
    }
    for section in ("layout_values", "audit_numeric_values"):
        expected = dict(style_snapshot.get(section) or {})
        actual = dict(product_style.get(section) or {})
        expected.update(
            {
                field: actual[field]
                for field in data_dependent_fields
                if field in actual
            }
        )
        result[section] = expected
    expected_strings = dict(style_snapshot.get("audit_string_values") or {})
    actual_strings = dict(product_style.get("audit_string_values") or {})
    if "legend.text$" in actual_strings:
        expected_strings["legend.text$"] = actual_strings["legend.text$"]
    result["audit_string_values"] = expected_strings
    return result


def _adaptive_raman_conformance_reference(
    style_snapshot: dict[str, object],
    data_snapshot: dict[str, object],
    series_count: int,
) -> dict[str, object]:
    """Build the Raman adaptive style sequence in natural source-column order."""

    raw_plots = data_snapshot.get("plots") if isinstance(data_snapshot, dict) else None
    if not isinstance(raw_plots, list) or not raw_plots or series_count <= 0:
        return dict(style_snapshot)
    indexed_plots = [
        (index, value)
        for index, value in enumerate(raw_plots)
        if isinstance(value, dict)
    ]
    if len(indexed_plots) != len(raw_plots):
        return dict(style_snapshot)
    natural_plots = [
        value
        for _index, value in sorted(
            indexed_plots,
            key=lambda item: (
                str(item[1].get("book_name") or ""),
                int(item[1].get("sheet_index") or 0),
                int(item[1].get("x_col_index") or 0),
            ),
        )
    ]
    result = dict(style_snapshot)
    data_style_fields = {
        "plot_colors": "color",
        "plot_line_colors": "line_color",
        "plot_line_widths": "line_width_origin_units",
        "marker_shapes": "symbol_shape",
        "marker_sizes": "symbol_size",
    }
    for field, data_style_field in data_style_fields.items():
        natural_values = [
            (plot.get("style") or {}).get(data_style_field)
            if isinstance(plot.get("style"), dict)
            else None
            for plot in natural_plots
        ]
        if any(value is None for value in natural_values):
            continue
        result[field] = [
            natural_values[index % len(natural_values)]
            for index in range(series_count)
        ]
    visibility = style_snapshot.get("plot_visibility")
    if isinstance(visibility, list) and visibility:
        result["plot_visibility"] = [1.0] * series_count
    result["plot_count"] = series_count
    return result


def _apply_adaptive_dynamic_legend_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    snapshot: dict[str, object],
) -> dict[str, object]:
    _apply_exemplar_axis_title_text(operations, graph_name, snapshot)
    entries = _plain_text_legend_entries(product)
    plot_names = (
        operations._plot_names(graph_name)
        if hasattr(operations, "_plot_names")
        else []
    )
    if plot_names and len(plot_names) != len(entries):
        return {
            "applied": False,
            "reason": "current_plot_and_legend_entry_count_mismatch",
            "plot_count": len(plot_names),
            "legend_entry_count": len(entries),
        }
    visibility_commands: list[str] = []
    for index in range(1, len(plot_names) + 1):
        command = (
            f'win -a "{quote_labtalk(graph_name)}"; '
            f"layer.plot{index}.show=1;"
        )
        result = operations.run_labtalk(command)
        if not getattr(result, "ok", False):
            return {
                "applied": False,
                "reason": "current_plot_visibility_restore_failed",
                "plot_index": index,
            }
        visibility_commands.append(command)
    written = update_native_legend(
        operations, graph_name, entries,
        plot_indices=range(1, len(entries) + 1),
    ).ok
    font_size = _reviewed_template_legend_font_size(snapshot, style)
    preserved = _format_preserved_line_sample_legend(
        operations,
        graph_name,
        style,
        font_size=font_size,
    )
    anchor_policy = _apply_saved_template_legend_anchor(
        operations,
        graph_name,
        snapshot,
        regenerate=False,
    )
    return {
        "applied": written,
        "method": "adaptive_dynamic_rich_text_legend_all_current_plots",
        "entries": entries,
        "visible_plot_indices": list(range(1, len(entries) + 1)),
        "all_current_plots_visible": len(plot_names) == len(entries),
        "visibility_commands": visibility_commands,
        "line_samples_preserved": True,
        "font_size": font_size,
        "anchor_policy": anchor_policy,
        "preserved_line_sample_policy": preserved,
        "axis_titles_restored_from_style_snapshot": bool(snapshot),
    }


def _apply_adaptive_bet_oth_json_text_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    snapshot: dict[str, object],
    *,
    axis_range_changed: bool = False,
) -> dict[str, object]:
    """Restore reviewed BET titles and current adsorption/desorption labels."""

    x_text = origin_bold_text(VERIFIED_BET_X_TITLE)
    y_text = origin_bold_text(VERIFIED_BET_Y_TITLE)
    reset_titles = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        f'label -xb "{_quote_origin_rich_text(x_text)}"; '
        f'label -yl "{_quote_origin_rich_text(y_text)}";'
    )
    # The standard label commands recalculate the automatic title anchors.
    # Reassign through COM afterwards so Origin keeps rich-text escape codes
    # as formatting rather than displaying a literal backslash sequence.
    x_written = _set_origin_graph_object_text(
        operations,
        graph_name,
        "XB",
        x_text,
    )
    y_written = _set_origin_graph_object_text(
        operations,
        graph_name,
        "YL",
        y_text,
    )
    x_styled = _style_graph_object(
        operations,
        graph_name,
        "XB",
        font_name=style.font_family or "Arial",
        font_size=36,
        color=1,
    )
    y_styled = _style_graph_object(
        operations,
        graph_name,
        "YL",
        font_name=style.font_family or "Arial",
        font_size=36,
        color=1,
    )
    adaptive_y_title = (
        _replace_adaptive_bet_y_axis_title(
            operations,
            graph_name,
            y_text,
        )
        if axis_range_changed
        else {"applied": True, "method": "reviewed_special_yl_preserved"}
    )
    orientation = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        + (
            "xb.show=1; xb.rotate=0; yl.show=0; yl.rotate=90;"
            if axis_range_changed
            else "xb.show=1; xb.rotate=0; yl.show=1; yl.rotate=90;"
        )
    )
    entries = [
        _bet_template_legend_label(
            label,
            is_desorption="desorption" in str(label).casefold(),
        )
        for label in _plain_text_legend_entries(product)
    ]
    legend_written = update_native_legend(
        operations, graph_name, entries,
        plot_indices=range(1, len(entries) + 1),
    ).ok
    font_size = _reviewed_template_legend_font_size(snapshot, style)
    preserved = _format_preserved_line_sample_legend(
        operations,
        graph_name,
        style,
        font_size=font_size,
    )
    applied = (
        x_written
        and y_written
        and bool(getattr(reset_titles, "ok", False))
        and x_styled
        and y_styled
        and bool(adaptive_y_title.get("applied"))
        and bool(getattr(orientation, "ok", False))
        and legend_written
        and bool(preserved.get("applied"))
    )
    return {
        "applied": applied,
        "method": "adaptive_bet_fixed_reviewed_titles_current_pair_legend",
        "x_title": VERIFIED_BET_X_TITLE,
        "y_title": VERIFIED_BET_Y_TITLE,
        "axis_titles_written": x_written and y_written,
        "axis_titles_reset_with_origin_label_command": bool(
            getattr(reset_titles, "ok", False)
        ),
        "axis_title_objects_styled": x_styled and y_styled,
        "y_title_rotation_restored": bool(getattr(orientation, "ok", False)),
        "adaptive_y_title": adaptive_y_title,
        "entries": entries,
        "native_legend": True,
        "line_samples_preserved": True,
        "font_size": font_size,
        "preserved_line_sample_policy": preserved,
    }


def _replace_adaptive_bet_y_axis_title(
    operations: object,
    graph_name: str,
    rich_text: str,
) -> dict[str, object]:
    """Use a stable text object when Origin's special YL moves with tick width."""

    graph = quote_labtalk(graph_name)
    operations.run_labtalk(
        f'win -a "{graph}"; label -r {BET_ADAPTIVE_Y_TITLE_OBJECT};'
    )
    created = operations.run_labtalk(
        f'win -a "{graph}"; '
        f'label -n {BET_ADAPTIVE_Y_TITLE_OBJECT} '
        f'"{_quote_origin_rich_text(rich_text)}";'
    )
    if not getattr(created, "ok", False):
        return {"applied": False, "reason": "bet_adaptive_y_title_create_failed"}

    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "origin_application_unavailable"}
    try:
        layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(
            graph_name
        )
    except Exception:
        layer = None
    if not layer:
        return {"applied": False, "reason": "bet_graph_layer_unavailable"}
    special_title = _find_origin_graph_object(layer, "YL")
    stable_title = _find_origin_graph_object(layer, BET_ADAPTIVE_Y_TITLE_OBJECT)
    if special_title is None or stable_title is None:
        return {"applied": False, "reason": "bet_y_title_objects_unavailable"}

    try:
        stable_title.Text = rich_text
        # Attachment 0 is page-relative.  It prevents the title from moving
        # when the current data require wider or decimal Y tick labels.
        for prop, value in (
            ("attach", 0),
            ("rotate", 90),
            ("fsize", 36),
            ("color", 1),
            ("show", 1),
            ("background", 0),
            ("border", 0),
            ("frame", 0),
            ("fill", 0),
        ):
            stable_title.SetNumProp(prop, value)
        stable_title.Left = BET_ADAPTIVE_Y_TITLE_LEFT
        stable_title.Top = BET_ADAPTIVE_Y_TITLE_TOP
        stable_title.Show = 1
        special_title.Show = 0
    except Exception as exc:
        return {
            "applied": False,
            "reason": f"bet_adaptive_y_title_style_failed: {exc}",
        }
    return {
        "applied": True,
        "method": "origin_standard_page_attached_text_for_adaptive_y_title",
        "object_name": BET_ADAPTIVE_Y_TITLE_OBJECT,
        "special_axis_title_hidden": True,
        "left": BET_ADAPTIVE_Y_TITLE_LEFT,
        "top": BET_ADAPTIVE_Y_TITLE_TOP,
        "font_size": 36,
        "rotation": 90,
        "text": rich_text,
    }


def _read_adaptive_bet_y_title_overlay(
    operations: object,
    graph_name: str,
) -> dict[str, object]:
    app = getattr(operations, "app", None)
    if app is None:
        return {"ok": False, "message": "Origin application is unavailable."}
    try:
        layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(
            graph_name
        )
    except Exception:
        layer = None
    if not layer:
        return {"ok": False, "message": "BET graph layer is unavailable."}
    stable_title = _find_origin_graph_object(layer, BET_ADAPTIVE_Y_TITLE_OBJECT)
    special_title = _find_origin_graph_object(layer, "YL")
    if stable_title is None:
        return {
            "ok": False,
            "message": "Adaptive BET Y-axis title object is missing after reopen.",
        }

    def number(name: str) -> float | None:
        try:
            return float(stable_title.GetNumProp(name))
        except Exception:
            return None

    text = str(getattr(stable_title, "Text", "") or "").strip()
    show = number("show")
    rotate = number("rotate")
    font_size = number("fsize")
    attach = number("attach")
    special_show = None
    if special_title is not None:
        try:
            special_show = float(special_title.GetNumProp("show"))
        except Exception:
            try:
                special_show = float(special_title.Show)
            except Exception:
                special_show = None
    reasons: list[str] = []
    if VERIFIED_BET_Y_TITLE.casefold() not in text.casefold():
        reasons.append("reviewed BET Y title text is missing")
    if show is None or abs(show - 1.0) > 0.01:
        reasons.append("adaptive BET Y title is not visible")
    if rotate is None or abs(rotate - 90.0) > 0.01:
        reasons.append("adaptive BET Y title is not rotated 90 degrees")
    if font_size is None or abs(font_size - 36.0) > 0.01:
        reasons.append("adaptive BET Y title is not 36 pt")
    if attach is None or abs(attach) > 0.01:
        reasons.append("adaptive BET Y title is not page-attached")
    if special_show is None or abs(special_show) > 0.01:
        reasons.append("Origin special YL object is not hidden")
    return {
        "ok": not reasons,
        "message": (
            "Adaptive BET Y-axis title survived save/reopen with stable page attachment."
            if not reasons
            else "Adaptive BET Y-axis title hard gate failed: " + "; ".join(reasons)
        ),
        "object_name": BET_ADAPTIVE_Y_TITLE_OBJECT,
        "text": text,
        "show": show,
        "rotate": rotate,
        "font_size": font_size,
        "attach": attach,
        "special_axis_title_show": special_show,
        "left": getattr(stable_title, "Left", None),
        "top": getattr(stable_title, "Top", None),
        "width": getattr(stable_title, "Width", None),
        "height": getattr(stable_title, "Height", None),
    }


def _effective_bet_style_with_y_title_overlay(
    product_style: dict[str, object],
    overlay: dict[str, object],
) -> dict[str, object]:
    """Expose the validated visible replacement through the standard YL audit keys."""

    effective = dict(product_style)
    for section in ("layout_values", "audit_numeric_values"):
        values = dict(product_style.get(section) or {})
        values["yl.show"] = overlay.get("show")
        values["yl.fsize"] = overlay.get("font_size")
        values["yl.bold"] = 0.0
        effective[section] = values
    strings = dict(product_style.get("audit_string_values") or {})
    strings["yl.text$"] = overlay.get("text")
    effective["audit_string_values"] = strings
    effective["adaptive_bet_y_title_overlay"] = dict(overlay)
    return effective


def _apply_adaptive_ftir_oth_json_text_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    snapshot: dict[str, object],
) -> dict[str, object]:
    _apply_exemplar_axis_title_text(operations, graph_name, snapshot)
    headers, rows = _read_processed_csv(product.processed_data)
    pairs = _processed_csv_plot_pairs(product, headers)
    entries = [str(value).strip() for value in product.legend_entries if str(value).strip()]
    if len(entries) != len(pairs):
        entries = [
            str(headers[y_col - 1])[: -len("_transmittance")]
            for _x_col, y_col in pairs
        ]
    written = update_native_legend(
        operations, graph_name, _ftir_native_legend_labels(entries),
        plot_indices=range(1, len(entries) + 1),
    ).ok
    legend_font_size = _reviewed_template_legend_font_size(snapshot, style)
    preserved = _format_preserved_line_sample_legend(
        operations,
        graph_name,
        style,
        font_size=legend_font_size,
    )
    return {
        "applied": written,
        "method": "adaptive_ftir_dynamic_rich_text_legend_with_line_samples",
        "entries": entries,
        "native_legend": True,
        "line_samples_preserved": True,
        "font_size": legend_font_size,
        "old_sample_names_removed": True,
        "axis_titles_restored_from_style_snapshot": bool(snapshot),
        "preserved_line_sample_policy": preserved,
    }


def _apply_adaptive_photocurrent_oth_json_text_policy(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    snapshot: dict[str, object],
) -> dict[str, object]:
    """Restore the reviewed photocurrent dynamic legend without fixed plot objects."""
    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {
            "applied": False,
            "reason": f"photocurrent_processed_data_unavailable: {exc}",
        }
    axis_title_validation = _validate_photocurrent_axis_titles(snapshot, headers)
    if not axis_title_validation.get("ok"):
        return {
            "applied": False,
            "reason": "photocurrent_axis_title_hard_gate_failed",
            "axis_title_validation": axis_title_validation,
        }
    _apply_exemplar_axis_title_text(operations, graph_name, snapshot)
    entries = _plain_text_legend_entries(product)
    written = update_native_legend(
        operations, graph_name, entries,
        plot_indices=range(1, len(entries) + 1),
    ).ok
    layout = snapshot.get("layout_values") if isinstance(snapshot, dict) else {}
    if not isinstance(layout, dict):
        layout = {}

    def legend_value(name: str, fallback: float) -> float:
        value = _finite_float(layout.get(f"legend.{name}"))
        return fallback if value is None else value

    font_name = style.font_family or "Arial"
    font_size = max(1, int(round(legend_value("fsize", float(style.legend_font_size or 14)))))
    bold = int(round(legend_value("bold", 0.0)))
    background = int(round(legend_value("background", 1.0)))
    border = int(round(legend_value("border", 0.0)))
    frame = int(round(legend_value("frame", 0.0)))
    fill = int(round(legend_value("fill", 0.0)))
    fill_color = int(round(legend_value("fillColor", -4.0)))
    border_color = int(round(legend_value("borderColor", 1.0)))
    line_width = legend_value("lineWidth", 1.0)
    legend_x = legend_value("x", 247.59324665243545)
    legend_y = legend_value("y", 1.747362576346474e-06)
    reference_x_from = _finite_float(layout.get("layer.x.from"))
    reference_x_to = _finite_float(layout.get("layer.x.to"))
    reference_y_from = _finite_float(layout.get("layer.y.from"))
    reference_y_to = _finite_float(layout.get("layer.y.to"))
    if (
        reference_x_from is None
        or reference_x_to is None
        or reference_y_from is None
        or reference_y_to is None
        or abs(reference_x_to - reference_x_from) <= 1e-12
        or abs(reference_y_to - reference_y_from) <= 1e-12
    ):
        return {
            "applied": False,
            "reason": "photocurrent_reference_legend_fraction_unavailable",
            "axis_title_validation": axis_title_validation,
        }
    legend_x_fraction = min(
        0.95,
        max(0.05, (legend_x - reference_x_from) / (reference_x_to - reference_x_from)),
    )
    legend_y_fraction = min(
        0.95,
        max(0.05, (legend_y - reference_y_from) / (reference_y_to - reference_y_from)),
    )
    graph = quote_labtalk(graph_name)
    command = (
        f'win -a "{graph}"; legend.show=1; '
        f'legend.font$="{quote_labtalk(font_name)}"; legend.fsize={font_size}; '
        f"legend.bold={bold}; "
        f"legend.x=layer.x.from+{_origin_number(legend_x_fraction)}*(layer.x.to-layer.x.from); "
        f"legend.y=layer.y.from+{_origin_number(legend_y_fraction)}*(layer.y.to-layer.y.from); "
        f"legend.background={background}; legend.border={border}; legend.frame={frame}; "
        f"legend.fill={fill}; legend.fillColor={fill_color}; legend.borderColor={border_color}; "
        f"legend.lineWidth={_origin_number(line_width)};"
    )
    labtalk = operations.run_labtalk(command)
    com_style = _style_graph_object(
        operations,
        graph_name,
        "Legend",
        font_name=font_name,
        font_size=font_size,
        color=1,
        bold=bold,
        background=background,
        border=border,
        frame=frame,
        fill=fill,
        fill_color=fill_color,
        border_color=border_color,
        line_width=line_width,
    )
    return {
        "applied": written and (bool(getattr(labtalk, "ok", False)) or com_style),
        "method": "adaptive_photocurrent_dynamic_snapshot_legend_with_line_samples",
        "entries": entries,
        "native_legend": True,
        "line_samples_preserved": True,
        "font_name": font_name,
        "font_size": font_size,
        "bold": bold,
        "background": background,
        "border": border,
        "frame": frame,
        "fill": fill,
        "fill_color": fill_color,
        "border_color": border_color,
        "line_width": line_width,
        "x": legend_x,
        "y": legend_y,
        "x_fraction": legend_x_fraction,
        "y_fraction": legend_y_fraction,
        "styled_with_com": com_style,
        "axis_titles_restored_from_style_snapshot": bool(snapshot),
        "axis_title_validation": axis_title_validation,
    }


def _apply_mott_schottky_candidate_guides(
    operations: object,
    graph_name: str,
    product: ProductContext,
    snapshot: dict[str, object],
    *,
    series_count: int = 3,
) -> dict[str, object]:
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"processed_data_unavailable: {exc}"}
    candidate = _mott_schottky_candidate_guides(
        headers,
        rows,
        series_count=series_count,
    )
    if not candidate:
        return {"applied": False, "reason": "no_defensible_common_linear_window"}

    graph = quote_labtalk(graph_name)
    cleared = operations.run_labtalk(
        f'win -a "{graph}"; '
        "label -r Line3; label -r Line4; label -r Line5; label -r Text; "
        "label -r rdop_mott_fit_1; label -r rdop_mott_fit_2; "
        "label -r rdop_mott_fit_3; label -r rdop_mott_x_intercept;"
    )
    if not getattr(cleared, "ok", False):
        return {
            "applied": False,
            "reason": "template_candidate_guide_cleanup_failed",
            **candidate,
        }
    x_intercept = float(candidate["shared_x_intercept_candidate"])
    x_end = float(candidate["guide_x_end"])
    line_results: list[dict[str, object]] = []
    for index, slope in enumerate(candidate["constrained_slopes"], start=1):
        name = f"rdop_mott_fit_{index}"
        y_end = float(slope) * (x_end - x_intercept)
        command = (
            f'win -a "{graph}"; label -r {name}; '
            f"draw -n {name} -w 3 -d 1 -l "
            f"{{{_origin_number(x_intercept)},0,{_origin_number(x_end)},{_origin_number(y_end)}}}; "
            f"{name}.color=color(128,128,128);"
        )
        result = operations.run_labtalk(command)
        if not getattr(result, "ok", False):
            return {
                "applied": False,
                "reason": "origin_candidate_guide_creation_failed",
                "failed_guide": index,
                **candidate,
            }
        line_results.append({"object_name": name, "slope": slope, "x_end": x_end, "y_end": y_end})

    layout = snapshot.get("layout_values") if isinstance(snapshot, dict) else None
    x_span = _snapshot_axis_span(layout, "layer.x", fallback=float(candidate["data_x_span"]))
    y_max = _snapshot_axis_value(layout, "layer.y.to")
    if y_max is None or y_max <= 0:
        y_max = float(candidate["visible_y_max"])
    label_x = x_intercept + 0.03 * x_span
    label_y = 0.2 * y_max
    label_text = f"{x_intercept:.2f} V"
    label_name = "rdop_mott_x_intercept"
    operations.run_labtalk(f'win -a "{graph}"; label -r {label_name};')
    label_result = operations.run_labtalk(
        f'win -a "{graph}"; label -n {label_name} '
        f'"{_quote_origin_rich_text(origin_bold_text(label_text))}"; '
        f"{label_name}.attach=2; {label_name}.x={_origin_number(label_x)}; "
        f"{label_name}.y={_origin_number(label_y)}; {label_name}.show=1;"
    )
    label_text_refreshed = _set_origin_graph_object_text(
        operations,
        graph_name,
        label_name,
        origin_bold_text(label_text),
    )
    label_styled = _style_graph_object(
        operations,
        graph_name,
        label_name,
        font_name="Arial",
        font_size=28,
        color=1,
    )
    com_required = getattr(operations, "app", None) is not None
    if not getattr(label_result, "ok", False) or (com_required and (not label_text_refreshed or not label_styled)):
        return {
            "applied": False,
            "reason": "origin_candidate_intercept_label_creation_failed",
            "labtalk_created": bool(getattr(label_result, "ok", False)),
            "com_text_refreshed": label_text_refreshed,
            "com_style_applied": label_styled,
            "guides_created": line_results,
            **candidate,
        }
    return {
        "applied": True,
        "method": "shared_intercept_three_point_linear_window_candidate",
        "manual_check_required": True,
        "visible_claim": "numeric x-intercept candidate only",
        "forbidden_automatic_claims": ["carrier type", "carrier density", "band-edge position"],
        "annotation": label_text,
        "annotation_object": label_name,
        "guides": line_results,
        **candidate,
    }


def _snapshot_axis_value(layout: object, key: str) -> float | None:
    if not isinstance(layout, dict):
        return None
    return _finite_float(layout.get(key))


def _snapshot_axis_span(layout: object, prefix: str, *, fallback: float) -> float:
    start = _snapshot_axis_value(layout, f"{prefix}.from")
    stop = _snapshot_axis_value(layout, f"{prefix}.to")
    if start is not None and stop is not None and stop > start:
        return stop - start
    return max(fallback, 1.0)


def _origin_number(value: object) -> str:
    number = _finite_float(value)
    if number is None:
        raise ValueError(f"Origin numeric value must be finite: {value!r}")
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.15g}"


def _apply_cached_style_rich_text_policies(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    *,
    snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    if product.product_key in REVIEWED_TEMPLATE_VISIBLE_PLOTS:
        entries = _plain_text_legend_entries(product)
        preserved_legend_policy = _format_preserved_line_sample_legend(operations, graph_name, style)
        policy = _plain_text_legend_policy(
            product,
            entries=entries,
            anchor_policy={"applied": False, "visible": True, "reason": "reviewed_template_legend_position_preserved"},
            line_samples_removed=False,
            preserved_line_sample_policy=preserved_legend_policy,
        )
        policy["legend_com_text_refreshed_after_formatting"] = _refresh_reviewed_template_legend_com_text(
            operations,
            graph_name,
            product,
        )
        return policy
    commands = _bold_template_axis_title_commands({"xb.text$": product.x_label, "yl.text$": product.y_label})
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if commands:
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; {commands}')
    entries = _plain_text_legend_entries(product)
    xrd_keep_line_legend = _xrd_standard_card_keeps_line_sample_legend(product)
    if xrd_keep_line_legend:
        preserved_legend_policy = _format_preserved_line_sample_legend(operations, graph_name, style)
        xrd_card_label_policy = _apply_xrd_standard_card_legend_and_label(
            operations,
            graph_name,
            product,
            entries,
            style,
        )
        return _plain_text_legend_policy(
            product,
            entries=entries,
            anchor_policy={"applied": False, "reason": "xrd_standard_card_keeps_template_line_sample_legend"},
            xrd_plain_label_policy={"applied": False, "reason": "xrd_standard_card_keeps_template_line_sample_legend"},
            line_samples_removed=False,
            preserved_line_sample_policy=preserved_legend_policy,
            xrd_card_label_policy=xrd_card_label_policy,
            xrd_standard_card_reference_sticks_present=True,
        )
    anchor_policy = _apply_saved_template_legend_anchor(
        operations,
        graph_name,
        snapshot or {},
    )
    if not anchor_policy.get("applied"):
        anchor_policy = {"applied": False, "reason": "native_legend_layout_deferred"}
    if product.product_key == "XRD":
        xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(
            operations,
            graph_name,
            product,
            entries,
            style,
        )
        return _plain_text_legend_policy(
            product,
            entries=entries,
            anchor_policy=anchor_policy,
            xrd_plain_label_policy=xrd_plain_label_policy,
            line_samples_removed=True,
            xrd_standard_card_reference_sticks_present=False,
        )
    _update_template_native_legend(
        operations,
        graph_name,
        entries,
        style,
    )
    return _plain_text_legend_policy(product, entries=entries, anchor_policy=anchor_policy, line_samples_removed=False)


def _apply_exemplar_axis_title_text(operations: object, graph_name: str, exemplar_snapshot: object) -> None:
    audit_strings = getattr(exemplar_snapshot, "audit_string_values", None)
    if not isinstance(audit_strings, dict) and isinstance(exemplar_snapshot, dict):
        audit_strings = exemplar_snapshot.get("audit_string_values")
    if not isinstance(audit_strings, dict):
        return
    commands: list[str] = []
    x_title = _origin_rich_text_for_labtalk(audit_strings.get("xb.text$"))
    y_title = _origin_rich_text_for_labtalk(audit_strings.get("yl.text$"))
    if x_title:
        commands.append(f"label -s -xb {x_title};")
    if y_title:
        commands.append(f"label -s -yl {y_title};")
    if commands:
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; ' + " ".join(commands))


def _processed_csv_plot_pairs(product: ProductContext, headers: list[str]) -> list[tuple[int, int]]:
    if len(headers) < 2:
        return []
    if product.product_key == "Raman":
        pairs = _adjacent_independent_xy_pairs(
            headers,
            x_suffix="_raman_shift_cm-1",
            y_suffix="_intensity",
        )
        if pairs:
            return pairs
        return _legacy_shared_x_pairs(
            headers,
            x_headers={"raman_shift_cm-1", "raman_shift"},
        )
    if product.product_key == "FTIR":
        pairs = _adjacent_independent_xy_pairs(
            headers,
            x_suffix="_wavenumber_cm-1",
            y_suffix="_transmittance",
        )
        if pairs:
            return pairs
        return _legacy_shared_x_pairs(headers, x_headers={"wavenumber_cm-1", "wavenumber"})
    if product.product_key == "photocurrent":
        pairs = _adjacent_independent_xy_pairs(
            headers,
            x_suffix="_time_s",
            y_suffix="_current_a",
        )
        if pairs:
            return pairs
        return _legacy_shared_x_pairs(headers, x_headers={"time_s"})
    if product.product_key == "UV-vis DRS":
        return _adjacent_independent_xy_pairs(
            headers,
            x_suffix="_wavelength_nm",
            y_suffix="_drs_signal",
        )
    if product.product_key == "Tauc":
        return _adjacent_independent_xy_pairs(
            headers,
            x_suffix="_photon_energy_eV",
            y_suffix="_tauc_y_direct_candidate",
        )
    if product.product_key.startswith("XPS"):
        x_columns = {
            str(header)[: -len("_binding_energy_eV")]: index + 1
            for index, header in enumerate(headers)
            if str(header).casefold().endswith("_binding_energy_ev")
        }
        if x_columns:
            pairs: list[tuple[int, int]] = []
            for index, header in enumerate(headers, start=1):
                text = str(header)
                if text.casefold().endswith("_binding_energy_ev"):
                    continue
                sample = next(
                    (
                        identity
                        for identity in x_columns
                        if text.startswith(identity + "_")
                    ),
                    "",
                )
                if sample:
                    pairs.append((x_columns[sample], index))
            if pairs:
                return pairs
        if str(headers[0]).strip().casefold() == "binding_energy_ev":
            return [(1, column) for column in range(2, len(headers) + 1)]
    if product.product_key == "BET":
        paired_x_suffix = "_relative_pressure_p_p0"
        paired_y_suffix = "_quantity_adsorbed_cm3_g_stp"
        if len(headers) % 2 == 0 and all(
            str(headers[index]).endswith(paired_x_suffix)
            and str(headers[index + 1]).endswith(paired_y_suffix)
            for index in range(0, len(headers), 2)
        ):
            return [
                (column, column + 1)
                for column in range(1, len(headers) + 1, 2)
                if column + 1 <= len(headers)
            ]
    if product.product_key == "EIS" and len(headers) >= 4:
        return [(column, column + 1) for column in range(1, len(headers), 2) if column + 1 <= len(headers)]
    if product.product_key == "XRD":
        return [(1, csv_index + 1) for csv_index, _header in _xrd_plotted_y_headers(product, headers)]
    return [(1, column) for column in range(2, len(headers) + 1)]


def _adjacent_independent_xy_pairs(
    headers: list[str],
    *,
    x_suffix: str,
    y_suffix: str,
) -> list[tuple[int, int]]:
    if len(headers) < 2 or len(headers) % 2 != 0:
        return []
    pairs: list[tuple[int, int]] = []
    identities: list[str] = []
    for index in range(0, len(headers), 2):
        x_header = str(headers[index]).strip()
        y_header = str(headers[index + 1]).strip()
        if not x_header.endswith(x_suffix) or not y_header.endswith(y_suffix):
            return []
        x_identity = x_header[: -len(x_suffix)].strip()
        y_identity = y_header[: -len(y_suffix)].strip()
        if not x_identity or x_identity != y_identity:
            return []
        identities.append(x_identity.casefold())
        pairs.append((index + 1, index + 2))
    if len(identities) != len(set(identities)):
        return []
    return pairs


def _legacy_shared_x_pairs(
    headers: list[str],
    *,
    x_headers: set[str],
) -> list[tuple[int, int]]:
    if len(headers) < 2 or str(headers[0]).strip().casefold() not in x_headers:
        return []
    y_headers = [str(value).strip() for value in headers[1:]]
    if any(not value for value in y_headers) or len(
        {value.casefold() for value in y_headers}
    ) != len(y_headers):
        return []
    return [(1, index) for index in range(2, len(headers) + 1)]


def _xrd_plotted_y_headers(product: ProductContext, headers: list[str]) -> list[tuple[int, str]]:
    return [
        (index, str(header).strip())
        for index, header in enumerate(headers[1:], start=1)
        if str(header).strip()
    ]


def _apply_adaptive_epr_data_axis_range(
    operations: object,
    graph_name: str,
    product: ProductContext,
    *,
    reference_style_snapshot: dict[str, object],
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    set_axis_range = getattr(operations, "set_axis_range", None)
    if not callable(set_axis_range):
        return {"applied": False, "reason": "set_axis_range_unavailable"}
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"epr_processed_data_unavailable: {exc}"}
    pairs = _processed_csv_plot_pairs(product, headers)
    series = _photocurrent_xy_series(rows, pairs)
    if not pairs or len(series) != len(pairs):
        return {"applied": False, "reason": "epr_current_xy_series_unavailable"}
    x_values = [value for x_series, _ in series for value in x_series]
    y_values = [value for _, y_series in series for value in y_series]
    x_data_min, x_data_max = min(x_values), max(x_values)
    y_data_min, y_data_max = min(y_values), max(y_values)
    if x_data_max <= x_data_min or y_data_max <= y_data_min:
        return {"applied": False, "reason": "epr_current_xy_bounds_invalid"}

    layout = reference_style_snapshot.get("layout_values")
    template_x_from = _snapshot_axis_value(layout, "layer.x.from")
    template_x_to = _snapshot_axis_value(layout, "layer.x.to")
    template_y_from = _snapshot_axis_value(layout, "layer.y.from")
    template_y_to = _snapshot_axis_value(layout, "layer.y.to")
    if None in {template_x_from, template_x_to, template_y_from, template_y_to}:
        return {"applied": False, "reason": "epr_reference_axis_contract_unavailable"}
    if template_x_to <= template_x_from or template_y_to <= template_y_from:
        return {"applied": False, "reason": "epr_reference_axis_contract_invalid"}

    x_span = x_data_max - x_data_min
    x_padding = max(x_span * 0.02, 1e-9)
    x_from = x_data_min - x_padding
    x_to = x_data_max + x_padding
    y_contract_contains_current = (
        y_data_min >= float(template_y_from)
        and y_data_max <= float(template_y_to)
    )
    if y_contract_contains_current:
        y_from, y_to = float(template_y_from), float(template_y_to)
        y_decision = "reviewed_range_preserved"
    else:
        y_span = y_data_max - y_data_min
        y_padding = max(y_span * 0.08, 1.0)
        y_from, y_to = y_data_min - y_padding, y_data_max + y_padding
        y_decision = "current_data_padded"

    result = set_axis_range(
        graph_name,
        x_min=x_from,
        x_max=x_to,
        y_min=y_from,
        y_max=y_to,
    )
    if not getattr(result, "ok", False):
        return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}

    title_position = _position_adaptive_epr_axis_titles(
        operations,
        graph_name,
        product.x_label,
        product.y_label,
        reference_style_snapshot,
        style,
    )
    if not title_position.get("applied"):
        return {
            "applied": False,
            "reason": "epr_axis_title_page_geometry_restore_failed",
            "axis_title_policy": title_position,
        }
    return {
        "applied": True,
        "method": "current_epr_bounds_with_reviewed_y_range_when_nonclipping",
        "range_changed": True,
        "x_min": x_from,
        "x_max": x_to,
        "y_min": y_from,
        "y_max": y_to,
        "current_x_min": x_data_min,
        "current_x_max": x_data_max,
        "current_y_min": y_data_min,
        "current_y_max": y_data_max,
        "y_range_decision": y_decision,
        "axis_title_policy": title_position,
    }


def _position_adaptive_epr_axis_titles(
    operations: object,
    graph_name: str,
    x_label: str,
    y_label: str,
    style_snapshot: dict[str, object],
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    positioned = _position_adaptive_xrd_axis_titles(
        operations,
        graph_name,
        x_label,
        y_label,
        style_snapshot,
        style,
    )
    if not positioned.get("applied"):
        return positioned
    saved_positions = style_snapshot.get("graph_object_positions")
    if not isinstance(saved_positions, dict):
        return {"applied": False, "reason": "epr_reviewed_axis_title_geometry_missing"}
    restored: dict[str, object] = {}
    for object_name in ("XB", "YL"):
        geometry = saved_positions.get(object_name)
        if not isinstance(geometry, dict):
            return {
                "applied": False,
                "reason": "epr_reviewed_axis_title_geometry_missing",
                "object_name": object_name,
            }
        result = _restore_graph_object_geometry(
            operations,
            graph_name,
            object_name,
            geometry,
        )
        if not result.get("applied"):
            return {
                "applied": False,
                "reason": "epr_reviewed_axis_title_geometry_restore_failed",
                "object_name": object_name,
                "geometry_restore": result,
            }
        restored[object_name] = result
    refreshed = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; doc -uw;'
    )
    if not getattr(refreshed, "ok", False):
        return {"applied": False, "reason": "epr_axis_title_geometry_refresh_failed"}
    return {
        **positioned,
        "method": "origin_native_axis_titles_with_exact_reviewed_epr_page_geometry",
        "reviewed_geometry_restored": restored,
    }


def _apply_adaptive_epr_direct_labels(
    operations: object,
    graph_name: str,
    product: ProductContext,
    snapshot: dict[str, object],
    rows: list[list[object]],
    plot_pairs: list[tuple[int, int]],
    axis_policy: dict[str, object],
) -> dict[str, object]:
    entries = [str(value).strip() for value in _plain_text_legend_entries(product)]
    if not entries or any(not value for value in entries) or len(
        {value.casefold() for value in entries}
    ) != len(entries):
        return {"applied": False, "reason": "epr_current_labels_must_be_nonempty_and_unique"}
    if len(entries) != len(plot_pairs):
        return {
            "applied": False,
            "reason": "epr_current_label_plot_count_mismatch",
            "label_count": len(entries),
            "plot_count": len(plot_pairs),
        }
    series = _photocurrent_xy_series(rows, plot_pairs)
    if len(series) != len(plot_pairs):
        return {"applied": False, "reason": "epr_current_xy_series_unavailable"}
    contract = snapshot.get("adaptive_direct_label_contract")
    if not isinstance(contract, dict):
        return {"applied": False, "reason": "epr_direct_label_contract_missing"}
    font_name = str(contract.get("font_name") or "Arial")
    font_size = int(_finite_float(contract.get("font_size")) or 28)
    specs: list[dict[str, object]] = []
    positioning = ""
    if len(entries) == int(contract.get("fixed_reference_count") or 0):
        fixed_positions = contract.get("fixed_page_positions")
        if not isinstance(fixed_positions, dict):
            return {"applied": False, "reason": "epr_fixed_direct_label_positions_missing"}
        for index, entry in enumerate(entries, start=1):
            name = f"DL{index}"
            geometry = fixed_positions.get(name)
            if not isinstance(geometry, dict):
                return {"applied": False, "reason": f"epr_fixed_direct_label_position_missing:{name}"}
            left = _finite_float(geometry.get("left"))
            top = _finite_float(geometry.get("top"))
            if left is None or top is None:
                return {"applied": False, "reason": f"epr_fixed_direct_label_position_invalid:{name}"}
            specs.append(
                {
                    "name": name,
                    "text": origin_bold_text(entry),
                    "left": left,
                    "top": top,
                    "font_name": font_name,
                    "font_size": font_size,
                }
            )
        positioning = "reviewed_page_geometry_for_three_reference_roles"
    else:
        x_from = _finite_float(axis_policy.get("x_min"))
        x_to = _finite_float(axis_policy.get("x_max"))
        y_from = _finite_float(axis_policy.get("y_min"))
        y_to = _finite_float(axis_policy.get("y_max"))
        if None in {x_from, x_to, y_from, y_to} or x_to <= x_from or y_to <= y_from:
            return {"applied": False, "reason": "epr_adaptive_axis_bounds_unavailable_for_labels"}
        x_fraction = _finite_float(contract.get("variable_x_fraction")) or 0.82
        y_offset_fraction = _finite_float(contract.get("variable_y_offset_fraction")) or 0.025
        x_anchor = x_from + min(0.92, max(0.60, x_fraction)) * (x_to - x_from)
        y_span = y_to - y_from
        for index, (entry, (x_values, y_values)) in enumerate(zip(entries, series), start=1):
            nearest_count = max(16, min(96, len(x_values) // 20))
            nearest_indices = heapq.nsmallest(
                nearest_count,
                range(len(x_values)),
                key=lambda item: (abs(x_values[item] - x_anchor), item),
            )
            label_y = median(y_values[item] for item in nearest_indices) + y_offset_fraction * y_span
            label_y = min(y_to - 0.06 * y_span, max(y_from + 0.06 * y_span, label_y))
            specs.append(
                {
                    "name": f"DL{index}",
                    "text": origin_bold_text(entry),
                    "x": x_anchor,
                    "y": label_y,
                    "font_name": font_name,
                    "font_size": font_size,
                }
            )
        positioning = "current_curve_nearest_x_median_layer_scale_anchor"
    visibility_results = []
    for index in range(1, len(entries) + 1):
        result = operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; layer.plot{index}.show=1;'
        )
        if not getattr(result, "ok", False):
            return {"applied": False, "reason": f"epr_current_plot_visibility_failed:{index}"}
        visibility_results.append(index)
    replaced = operations.replace_graph_direct_labels(
        graph_name,
        specs,
        remove_names=[f"DL{index}" for index in range(1, max(32, len(entries)) + 1)],
        hide_legend=True,
    )
    if not getattr(replaced, "ok", False):
        return {
            "applied": False,
            "reason": getattr(replaced, "message", "epr_native_direct_label_replace_failed"),
        }
    removed_auto_legend = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        "label -r Legend;"
    )
    if not getattr(removed_auto_legend, "ok", False):
        return {"applied": False, "reason": "epr_auto_legend_remove_failed"}
    return {
        "applied": True,
        "method": "origin_native_current_data_direct_labels_without_legend",
        "positioning": positioning,
        "entries": entries,
        "object_names": [f"DL{index}" for index in range(1, len(entries) + 1)],
        "all_current_plots_visible": True,
        "visible_plot_indices": visibility_results,
        "legend_hidden": True,
        "auto_legend_removed_to_match_reviewed_epr_graph": True,
        "native_objects": getattr(replaced, "payload", {}).get("objects", []),
    }


def _apply_xps_non_in_situ_data_axis_range(
    operations: object,
    graph_name: str,
    product: ProductContext,
    *,
    reference_style_snapshot: dict[str, object] | None,
    reference_data_snapshot: dict[str, object] | None,
) -> dict[str, object]:
    set_axis_range = getattr(operations, "set_axis_range", None)
    if not callable(set_axis_range):
        return {"applied": False, "reason": "set_axis_range_unavailable"}
    same_data = _uvvis_current_data_matches_reference(
        product,
        reference_data_snapshot,
    )
    layout = (
        reference_style_snapshot.get("layout_values")
        if isinstance(reference_style_snapshot, dict)
        else None
    )
    if same_data.get("matches"):
        required = {
            key: _snapshot_axis_value(layout, key)
            for key in (
                "layer.x.from",
                "layer.x.to",
                "layer.y.from",
                "layer.y.to",
            )
        }
        if all(value is not None for value in required.values()):
            return {
                "applied": True,
                "method": "xps_non_in_situ_reference_data_match_preserves_template_axes",
                "decision": "template_preserved",
                "range_changed": False,
                "same_data_reference_match": same_data,
                **required,
            }
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {"applied": False, "reason": f"processed_data_unavailable: {exc}"}
    pairs = _processed_csv_plot_pairs(product, headers)
    x_values = [
        value
        for x_col, _y_col in pairs
        for row in rows
        if (value := _finite_numeric_value(row[x_col - 1])) is not None
    ]
    y_values = [
        value
        for _x_col, y_col in pairs
        for row in rows
        if (value := _finite_numeric_value(row[y_col - 1])) is not None
    ]
    if not x_values or not y_values:
        return {"applied": False, "reason": "xps_non_in_situ_csv_bounds_unavailable"}
    x_low, x_high = min(x_values), max(x_values)
    y_low, y_high = min(y_values), max(y_values)
    if x_high <= x_low or y_high <= y_low:
        return {"applied": False, "reason": "xps_non_in_situ_csv_bounds_invalid"}
    x_padding = (x_high - x_low) * 0.04
    y_padding = (y_high - y_low) * 0.16
    x_from, x_to = x_high + x_padding, x_low - x_padding
    y_from, y_to = y_low - y_padding, y_high + y_padding
    result = set_axis_range(
        graph_name,
        x_min=x_from,
        x_max=x_to,
        y_min=y_from,
        y_max=y_to,
    )
    if not getattr(result, "ok", False):
        return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
    return {
        "applied": True,
        "method": "xps_non_in_situ_changed_data_bounds_with_descending_binding_energy_axis",
        "decision": "adaptive_xy",
        "range_changed": True,
        "same_data_reference_match": same_data,
        "x_min": x_from,
        "x_max": x_to,
        "y_min": y_from,
        "y_max": y_to,
        "sample_count": (len(headers) - 1) // 9,
    }


def _apply_embedded_snapshot_data_axis_range(
    operations: object,
    graph_name: str,
    product: ProductContext,
    *,
    reference_style_snapshot: dict[str, object] | None = None,
    reference_data_snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    set_axis_range = getattr(operations, "set_axis_range", None)
    if not callable(set_axis_range):
        return {"applied": False, "reason": "set_axis_range_unavailable"}
    if product.product_key == "XRD":
        try:
            headers, _rows = _read_processed_csv(product.processed_data)
        except Exception:
            headers = []
        y_columns = tuple(
            index
            for index, header in _xrd_plotted_y_headers(product, headers)
            if not is_template_xrd_reference_stick_header(str(header))
        )
        has_reference_sticks = any(
            is_template_xrd_reference_stick_header(str(header))
            for _index, header in _xrd_plotted_y_headers(product, headers)
        )
        if not y_columns:
            return {"applied": False, "reason": "xrd_sample_columns_unavailable"}
        y_min, y_max = _csv_bounds_for_columns(product.processed_data, y_columns)
        if y_min is None or y_max is None:
            return {"applied": False, "reason": "csv_bounds_unavailable"}
        y_from, y_to = _padded_axis_bounds(y_min, y_max, zero_floor=True)
        if has_reference_sticks:
            span = max(y_max - y_min, 1.0)
            y_to = max(y_to, y_max + max(2.4, span * 0.54))
        result = set_axis_range(graph_name, y_min=y_from, y_max=y_to)
        if not getattr(result, "ok", False):
            return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
        return {
            "applied": True,
            "method": "xrd_normalized_offset_bounds_after_embedded_template_style",
            "y_min": y_from,
            "y_max": y_to,
            "source_y_min": y_min,
            "source_y_max": y_max,
            "sample_column_count": len(y_columns),
            "reference_sticks_present": has_reference_sticks,
        }
    if product.product_key == "BET":
        return _apply_bet_data_axis_range(
            operations,
            graph_name,
            product,
            set_axis_range=set_axis_range,
            reference_style_snapshot=reference_style_snapshot,
            reference_data_snapshot=reference_data_snapshot,
        )
    if product.product_key == "photocurrent":
        try:
            headers, rows = _read_processed_csv(product.processed_data)
        except (OSError, ValueError) as exc:
            return {
                "applied": False,
                "reason": f"photocurrent_processed_data_unavailable: {exc}",
            }
        pairs = _processed_csv_plot_pairs(product, headers)
        current_series = _photocurrent_xy_series(rows, pairs)
        if not pairs or len(current_series) != len(pairs):
            return {"applied": False, "reason": "photocurrent_xy_pairs_unavailable"}
        reference_series = _photocurrent_reference_xy_series(reference_data_snapshot)
        if not reference_series:
            return {
                "applied": False,
                "reason": "photocurrent_reference_data_snapshot_unavailable",
            }
        layout = (
            reference_style_snapshot.get("layout_values")
            if isinstance(reference_style_snapshot, dict)
            else None
        )
        template_x_from = _snapshot_axis_value(layout, "layer.x.from")
        template_x_to = _snapshot_axis_value(layout, "layer.x.to")
        template_y_from = _snapshot_axis_value(layout, "layer.y.from")
        template_y_to = _snapshot_axis_value(layout, "layer.y.to")
        if (
            template_x_from is None
            or template_x_to is None
            or template_y_from is None
            or template_y_to is None
            or template_x_to <= template_x_from
            or template_y_to <= template_y_from
        ):
            return {
                "applied": False,
                "reason": "photocurrent_reference_axis_range_unavailable",
            }

        same_x = _photocurrent_axis_series_match(current_series, reference_series, axis="x")
        same_y = _photocurrent_axis_series_match(current_series, reference_series, axis="y")
        current_x_values = [value for series in current_series for value in series[0]]
        current_y_values = [value for series in current_series for value in series[1]]
        x_min, x_max = min(current_x_values), max(current_x_values)
        y_min, y_max = min(current_y_values), max(current_y_values)

        if same_x and same_y:
            return {
                "applied": True,
                "method": "photocurrent_reference_data_match_preserves_template_axes",
                "decision": "template_preserved",
                "range_changed": False,
                "x_data_matches_reference": True,
                "y_data_matches_reference": True,
                "x_min": template_x_from,
                "x_max": template_x_to,
                "y_min": template_y_from,
                "y_max": template_y_to,
                "source_x_min": x_min,
                "source_x_max": x_max,
                "source_y_min": y_min,
                "source_y_max": y_max,
                "series_count": len(current_series),
                "axis_titles_recentered": False,
            }

        x_from: float | None = None
        x_to: float | None = None
        y_from: float | None = None
        y_to: float | None = None
        if not same_x:
            x_from, x_to = _padded_axis_bounds(x_min, x_max, zero_floor=x_min >= 0)
        if not same_y:
            y_from, y_to = _padded_axis_bounds(y_min, y_max)
        result = set_axis_range(
            graph_name,
            x_min=x_from,
            x_max=x_to,
            y_min=y_from,
            y_max=y_to,
        )
        if not getattr(result, "ok", False):
            return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
        title_centered = False
        if hasattr(operations, "run_labtalk"):
            recenter_commands: list[str] = []
            if not same_x:
                recenter_commands.append("xb.x=(layer.x.from+layer.x.to)/2;")
            if not same_y:
                recenter_commands.append("yl.y=(layer.y.from+layer.y.to)/2;")
            centered = operations.run_labtalk(
                f'win -a "{quote_labtalk(graph_name)}"; '
                + " ".join(recenter_commands)
            )
            title_centered = bool(getattr(centered, "ok", False))
        if not title_centered:
            return {
                "applied": False,
                "reason": "photocurrent_axis_title_recentering_failed",
            }
        return {
            "applied": True,
            "method": "photocurrent_changed_axes_use_current_data_bounds_after_reviewed_style",
            "decision": (
                "adaptive_xy"
                if not same_x and not same_y
                else "adaptive_x"
                if not same_x
                else "adaptive_y"
            ),
            "range_changed": True,
            "x_data_matches_reference": same_x,
            "y_data_matches_reference": same_y,
            "x_min": template_x_from if same_x else x_from,
            "x_max": template_x_to if same_x else x_to,
            "y_min": template_y_from if same_y else y_from,
            "y_max": template_y_to if same_y else y_to,
            "source_x_min": x_min,
            "source_x_max": x_max,
            "source_y_min": y_min,
            "source_y_max": y_max,
            "series_count": len(current_series),
            "axis_titles_recentered": True,
        }
    if product.product_key == "PL":
        try:
            headers, rows = _read_processed_csv(product.processed_data)
        except (OSError, ValueError) as exc:
            return {"applied": False, "reason": f"pl_processed_data_unavailable: {exc}"}
        pairs = _processed_csv_plot_pairs(product, headers)
        current_series = _shared_x_contiguous_y_series(rows, pairs)
        if not pairs or len(current_series) != len(pairs):
            return {"applied": False, "reason": "pl_xy_pairs_unavailable"}
        x_values = [value for series in current_series for value in series[0]]
        y_values = [value for series in current_series for value in series[1]]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        layout = (
            reference_style_snapshot.get("layout_values")
            if isinstance(reference_style_snapshot, dict)
            else None
        )
        template_x_from = _snapshot_axis_value(layout, "layer.x.from")
        template_x_to = _snapshot_axis_value(layout, "layer.x.to")
        template_y_from = _snapshot_axis_value(layout, "layer.y.from")
        template_y_to = _snapshot_axis_value(layout, "layer.y.to")
        template_valid = (
            template_x_from is not None
            and template_x_to is not None
            and template_y_from is not None
            and template_y_to is not None
            and template_x_from < template_x_to
            and template_y_from < template_y_to
        )
        x_inside = bool(
            template_valid
            and template_x_from <= x_min
            and x_max <= template_x_to
        )
        y_inside = bool(
            template_valid
            and template_y_from <= y_min
            and y_max <= template_y_to
        )
        if x_inside and y_inside:
            return {
                "applied": True,
                "method": "pl_current_data_inside_reviewed_axis_bounds",
                "decision": "template_preserved",
                "range_changed": False,
                "x_min": template_x_from,
                "x_max": template_x_to,
                "y_min": template_y_from,
                "y_max": template_y_to,
                "source_x_min": x_min,
                "source_x_max": x_max,
                "source_y_min": y_min,
                "source_y_max": y_max,
                "series_count": len(current_series),
            }
        x_from, x_to = (
            (None, None)
            if x_inside
            else _padded_axis_bounds(x_min, x_max)
        )
        y_from, y_to = (
            (None, None)
            if y_inside
            else _padded_axis_bounds(y_min, y_max, zero_floor=y_min >= 0)
        )
        result = set_axis_range(
            graph_name,
            x_min=x_from,
            x_max=x_to,
            y_min=y_from,
            y_max=y_to,
        )
        if not getattr(result, "ok", False):
            return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
        commands: list[str] = []
        if not x_inside:
            commands.append("xb.x=(layer.x.from+layer.x.to)/2;")
        if not y_inside:
            commands.append("yl.y=(layer.y.from+layer.y.to)/2;")
        centered = operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; ' + " ".join(commands)
        )
        if not getattr(centered, "ok", False):
            return {"applied": False, "reason": "pl_axis_title_recentering_failed"}
        return {
            "applied": True,
            "method": "pl_current_data_bounds_after_reviewed_style",
            "decision": (
                "adaptive_xy"
                if not x_inside and not y_inside
                else "adaptive_x"
                if not x_inside
                else "adaptive_y"
            ),
            "range_changed": True,
            "x_min": template_x_from if x_inside else x_from,
            "x_max": template_x_to if x_inside else x_to,
            "y_min": template_y_from if y_inside else y_from,
            "y_max": template_y_to if y_inside else y_to,
            "source_x_min": x_min,
            "source_x_max": x_max,
            "source_y_min": y_min,
            "source_y_max": y_max,
            "series_count": len(current_series),
        }
    if product.product_key in {"UV-vis DRS", "Tauc", "EPR"}:
        try:
            headers, rows = _read_processed_csv(product.processed_data)
        except (OSError, ValueError) as exc:
            return {"applied": False, "reason": f"processed_data_unavailable: {exc}"}
        pairs = _processed_csv_plot_pairs(product, headers)
        x_values = [
            value
            for x_col, _y_col in pairs
            for row in rows
            if (value := _finite_numeric_value(row[x_col - 1] if x_col - 1 < len(row) else None)) is not None
        ]
        y_values = [
            value
            for _x_col, y_col in pairs
            for row in rows
            if (value := _finite_numeric_value(row[y_col - 1] if y_col - 1 < len(row) else None)) is not None
        ]
        if not x_values or not y_values:
            return {"applied": False, "reason": "csv_xy_bounds_unavailable"}
        x_min, x_max = min(x_values), max(x_values)
        if x_max <= x_min:
            return {"applied": False, "reason": "csv_x_bounds_invalid"}
        if product.product_key == "EPR":
            y_from = y_to = None
            result = set_axis_range(graph_name, x_min=x_min, x_max=x_max)
        else:
            y_from, y_to = _padded_axis_bounds(min(y_values), max(y_values), zero_floor=True)
            result = set_axis_range(
                graph_name,
                x_min=x_min,
                x_max=x_max,
                y_min=y_from,
                y_max=y_to,
            )
        if not getattr(result, "ok", False):
            return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
        return {
            "applied": True,
            "method": (
                "uvvis_current_xy_bounds_after_reviewed_style"
                if product.product_key in {"UV-vis DRS", "Tauc"}
                else "epr_verified_field_bounds_after_legacy_style_geometry"
            ),
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_from,
            "y_max": y_to,
        }
    if product.product_key != "EIS":
        return {"applied": False, "reason": "not_required_for_product"}
    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except Exception:
        headers = []
    x_columns = tuple(range(0, len(headers), 2))
    y_columns = tuple(range(1, len(headers), 2))
    x_min, x_max = _csv_bounds_for_columns(product.processed_data, x_columns)
    y_min, y_max = _csv_bounds_for_columns(product.processed_data, y_columns)
    if x_min is None or x_max is None or y_min is None or y_max is None:
        return {"applied": False, "reason": "csv_bounds_unavailable"}
    x_from, x_to = _padded_axis_bounds(x_min, x_max, zero_floor=True)
    y_from, y_to = _padded_axis_bounds(y_min, y_max, zero_floor=True)
    if y_max > 0:
        x_to = max(x_to, y_max * 1.75)
    result = set_axis_range(graph_name, x_min=x_from, x_max=x_to, y_min=y_from, y_max=y_to)
    if not getattr(result, "ok", False):
        return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
    return {
        "applied": True,
        "method": "eis_all_measured_overlay_bounds_after_embedded_template_style",
        "x_min": x_from,
        "x_max": x_to,
        "y_min": y_from,
        "y_max": y_to,
    }


def _apply_bet_data_axis_range(
    operations: object,
    graph_name: str,
    product: ProductContext,
    *,
    set_axis_range: object,
    reference_style_snapshot: dict[str, object] | None,
    reference_data_snapshot: dict[str, object] | None,
) -> dict[str, object]:
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except (OSError, ValueError) as exc:
        return {
            "applied": False,
            "reason": f"bet_processed_data_unavailable: {exc}",
        }
    pairs = _processed_csv_plot_pairs(product, headers)
    current_series = _photocurrent_xy_series(rows, pairs)
    if not pairs or len(current_series) != len(pairs):
        return {"applied": False, "reason": "bet_xy_pairs_unavailable"}
    reference_series = _photocurrent_reference_xy_series(reference_data_snapshot)
    layout = (
        reference_style_snapshot.get("layout_values")
        if isinstance(reference_style_snapshot, dict)
        else None
    )
    template_x_from = _snapshot_axis_value(layout, "layer.x.from")
    template_x_to = _snapshot_axis_value(layout, "layer.x.to")
    template_y_from = _snapshot_axis_value(layout, "layer.y.from")
    template_y_to = _snapshot_axis_value(layout, "layer.y.to")
    if (
        template_x_from is None
        or template_x_to is None
        or template_y_from is None
        or template_y_to is None
        or template_x_to <= template_x_from
        or template_y_to <= template_y_from
    ):
        return {"applied": False, "reason": "bet_reference_axis_range_unavailable"}

    same_x = bool(reference_series) and _photocurrent_axis_series_match(
        current_series,
        reference_series,
        axis="x",
    )
    same_y = bool(reference_series) and _photocurrent_axis_series_match(
        current_series,
        reference_series,
        axis="y",
    )
    current_x_values = [value for series in current_series for value in series[0]]
    current_y_values = [value for series in current_series for value in series[1]]
    x_min, x_max = min(current_x_values), max(current_x_values)
    y_min, y_max = min(current_y_values), max(current_y_values)
    reference_x_contains_current = (
        x_min >= template_x_from - 1e-12
        and x_max <= template_x_to + 1e-12
    )
    change_x = not (same_x or reference_x_contains_current)
    change_y = not same_y
    if not change_x and not change_y:
        return {
            "applied": True,
            "method": "bet_reference_data_match_preserves_template_axes",
            "decision": "template_preserved",
            "range_changed": False,
            "x_data_matches_reference": same_x,
            "y_data_matches_reference": same_y,
            "x_min": template_x_from,
            "x_max": template_x_to,
            "y_min": template_y_from,
            "y_max": template_y_to,
            "source_x_min": x_min,
            "source_x_max": x_max,
            "source_y_min": y_min,
            "source_y_max": y_max,
            "series_count": len(current_series),
            "axis_titles_recentered": False,
        }

    x_from: float | None = None
    x_to: float | None = None
    y_from: float | None = None
    y_to: float | None = None
    if change_x:
        x_from, x_to = _padded_axis_bounds(
            x_min,
            x_max,
            zero_floor=x_min >= 0,
        )
    if change_y:
        y_from, y_to = _padded_axis_bounds(y_min, y_max)
    result = set_axis_range(
        graph_name,
        x_min=x_from,
        x_max=x_to,
        y_min=y_from,
        y_max=y_to,
    )
    if not getattr(result, "ok", False):
        return {
            "applied": False,
            "reason": getattr(result, "message", "set_axis_range_failed"),
        }
    recenter_commands: list[str] = []
    if change_x:
        recenter_commands.append("xb.x=(layer.x.from+layer.x.to)/2;")
    if change_y:
        recenter_commands.append("yl.y=(layer.y.from+layer.y.to)/2;")
    centered = operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        + " ".join(recenter_commands)
    )
    if not getattr(centered, "ok", False):
        return {
            "applied": False,
            "reason": "bet_axis_title_recentering_failed",
        }
    return {
        "applied": True,
        "method": "bet_current_data_bounds_after_reviewed_style",
        "decision": (
            "adaptive_xy"
            if change_x and change_y
            else "adaptive_x"
            if change_x
            else "adaptive_y"
        ),
        "range_changed": True,
        "x_data_matches_reference": same_x,
        "y_data_matches_reference": same_y,
        "reference_x_range_contains_current": reference_x_contains_current,
        "x_min": x_from if change_x else template_x_from,
        "x_max": x_to if change_x else template_x_to,
        "y_min": y_from if change_y else template_y_from,
        "y_max": y_to if change_y else template_y_to,
        "source_x_min": x_min,
        "source_x_max": x_max,
        "source_y_min": y_min,
        "source_y_max": y_max,
        "series_count": len(current_series),
        "axis_titles_recentered": True,
    }


def _apply_saved_template_legend_anchor(
    operations: object,
    graph_name: str,
    snapshot: dict[str, object],
    *,
    regenerate: bool = True,
) -> dict[str, object]:
    if not hasattr(operations, "run_labtalk"):
        return {"applied": False, "reason": "run_labtalk_unavailable"}
    layout = snapshot.get("layout_values") if isinstance(snapshot, dict) else None
    audit = snapshot.get("audit_numeric_values") if isinstance(snapshot, dict) else None
    legend_show = _snapshot_axis_value(audit, "legend.show")
    if legend_show is None or abs(legend_show - 1.0) > 1e-9:
        return {"applied": False, "reason": "saved_template_legend_not_visible"}
    object_positions = (
        snapshot.get("graph_object_positions")
        if isinstance(snapshot, dict)
        else None
    )
    legend_geometry: dict[str, object] | None = None
    if isinstance(object_positions, dict):
        for object_name, raw_geometry in object_positions.items():
            if (
                str(object_name).casefold() == "legend"
                and isinstance(raw_geometry, dict)
            ):
                legend_geometry = raw_geometry
                break
    if legend_geometry is not None:
        restored = _restore_graph_object_geometry(
            operations,
            graph_name,
            "Legend",
            legend_geometry,
        )
        if restored.get("applied"):
            operations.run_labtalk(
                f'win -a "{quote_labtalk(graph_name)}"; legend.show=1;'
            )
            return {
                "applied": True,
                "visible": True,
                "method": "saved_template_native_object_geometry",
                "geometry": restored.get("geometry"),
                "saved_geometry": restored.get("saved_geometry"),
                "position_restored": restored.get("position_restored"),
                "size_restored": restored.get("size_restored"),
            }
    x_from = _snapshot_axis_value(layout, "layer.x.from")
    x_to = _snapshot_axis_value(layout, "layer.x.to")
    y_from = _snapshot_axis_value(layout, "layer.y.from")
    y_to = _snapshot_axis_value(layout, "layer.y.to")
    legend_x = _snapshot_axis_value(layout, "legend.x")
    legend_y = _snapshot_axis_value(layout, "legend.y")
    if None in {x_from, x_to, y_from, y_to, legend_x, legend_y}:
        return {"applied": False, "reason": "saved_template_legend_coordinates_unavailable"}
    x_span = float(x_to) - float(x_from)
    y_span = float(y_to) - float(y_from)
    if abs(x_span) <= 1e-12 or abs(y_span) <= 1e-12:
        return {"applied": False, "reason": "saved_template_axis_span_invalid"}
    x_fraction = (float(legend_x) - float(x_from)) / x_span
    y_fraction = (float(legend_y) - float(y_from)) / y_span
    if not (math.isfinite(x_fraction) and math.isfinite(y_fraction)):
        return {"applied": False, "reason": "saved_template_legend_fraction_invalid"}
    x_fraction = min(0.95, max(0.05, x_fraction))
    y_fraction = min(0.95, max(0.05, y_fraction))
    regenerate_command = "legend -r; " if regenerate else ""
    operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        f"{regenerate_command}legend.show=1; "
        f"legend.x = layer.x.from + {x_fraction:.8g} * (layer.x.to - layer.x.from); "
        f"legend.y = layer.y.from + {y_fraction:.8g} * (layer.y.to - layer.y.from);"
    )
    return {
        "applied": True,
        "visible": True,
        "method": (
            "saved_template_fractional_anchor_before_plain_text_replacement"
            if regenerate
            else "saved_template_fractional_anchor_without_legend_regeneration"
        ),
        "x_fraction": x_fraction,
        "y_fraction": y_fraction,
        "saved_x": legend_x,
        "saved_y": legend_y,
    }


def _restore_graph_object_geometry(
    operations: object,
    graph_name: str,
    object_name: str,
    geometry: dict[str, object],
) -> dict[str, object]:
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "origin_app_unavailable"}
    values: dict[str, int] = {}
    for key in ("left", "top", "width", "height"):
        value = _finite_float(geometry.get(key))
        if value is None:
            return {
                "applied": False,
                "reason": "saved_template_object_geometry_incomplete",
                "missing": key,
            }
        values[key] = int(round(value))
    try:
        layer = (
            app.FindGraphLayer(f"[{graph_name}]Layer1")
            or app.FindGraphLayer(f"[{graph_name}]1")
            or app.FindGraphLayer(graph_name)
        )
    except Exception:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    if not layer:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    graph_object = _find_origin_graph_object(layer, object_name)
    if graph_object is None:
        return {"applied": False, "reason": "graph_object_unavailable"}
    try:
        graph_object.Left = values["left"]
        graph_object.Top = values["top"]
        graph_object.Width = values["width"]
        graph_object.Height = values["height"]
        actual = {
            "left": int(round(float(graph_object.Left))),
            "top": int(round(float(graph_object.Top))),
            "width": int(round(float(graph_object.Width))),
            "height": int(round(float(graph_object.Height))),
        }
    except Exception as exc:
        return {
            "applied": False,
            "reason": "graph_object_geometry_restore_failed",
            "message": str(exc),
        }
    position_keys = ("left", "top")
    position_matches = all(actual[key] == values[key] for key in position_keys)
    if not position_matches:
        return {
            "applied": False,
            "reason": "graph_object_position_readback_mismatch",
            "expected": values,
            "actual": actual,
        }
    size_matches = all(actual[key] == values[key] for key in ("width", "height"))
    return {
        "applied": True,
        "method": "origin_native_graph_object_geometry",
        "geometry": actual,
        "saved_geometry": values,
        "position_restored": True,
        # Origin auto-sizes native text objects from their current text.  A
        # shortened dynamic legend therefore legitimately rejects the saved
        # width/height while still preserving the reviewed Left/Top anchor.
        "size_restored": size_matches,
    }


def _update_template_native_legend(
    operations: object,
    graph_name: str,
    entries: list[str],
    style: ResolvedPlotStyle,
) -> None:
    result = update_native_legend(operations, graph_name, entries)
    if not getattr(result, "ok", False):
        raise RuntimeError(getattr(result, "message", "native legend update failed"))
    _style_graph_object(
        operations, graph_name, "Legend", font_name=style.font_family,
        font_size=int(style.legend_font_size), color=1,
    )


def _apply_xrd_template_plain_legend_labels(
    operations: object,
    graph_name: str,
    product: ProductContext,
    entries: list[str],
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    if product.product_key != "XRD" or not entries or not hasattr(operations, "run_labtalk"):
        return {"applied": False, "reason": "not_xrd_or_no_entries"}
    labels: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        label = _xrd_plain_label_text(entry)
        key = re.sub(r"\\[A-Za-z]+\(|\)|\s+", "", label).casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    if not labels:
        return {"applied": False, "reason": "no_clean_labels"}
    font_name = style.font_family or "Arial"
    font_size = int(style.legend_font_size or 26)
    graph = quote_labtalk(graph_name)
    label_names: list[str] = []
    label_positions = _xrd_direct_label_positions(product, labels)
    operations.run_labtalk(f'win -a "{graph}"; legend.show=0;')
    for index, (label, x_value, y_value) in enumerate(label_positions, start=1):
        name = f"rdop_xrd_plain_legend_{index}"
        label_names.append(name)
        operations.run_labtalk(f'win -a "{graph}"; label -r {name}; label -n {name} "x";')
        operations.run_labtalk(
            f'win -a "{graph}"; '
            f"{name}.x={x_value:g}; {name}.y={y_value:g}; "
            f'{name}.font$="{quote_labtalk(font_name)}"; {name}.font=font({quote_labtalk(font_name)}); '
            f"{name}.fsize={font_size}; {name}.bold=1; {name}.color=color(black); "
            f"{name}.background=0; {name}.border=0; {name}.frame=0; {name}.fill=0; {name}.show=1;"
        )
    positioned = _position_xrd_plain_legend_objects(
        operations,
        graph_name,
        label_names,
        labels[:6],
        font_name=font_name,
        font_size=font_size,
    )
    return {
        "applied": True,
        "method": "xrd_no_card_curve_direct_labels",
        "label_count": len(label_positions),
        "labels": [label for label, _x_value, _y_value in label_positions],
        "label_positions": [
            {"label": label, "x": x_value, "y": y_value}
            for label, x_value, y_value in label_positions
        ],
        "positioned_with_com": positioned,
        "font_name": font_name,
        "font_size": font_size,
    }


def _xrd_direct_label_positions(product: ProductContext, labels: list[str]) -> list[tuple[str, float, float]]:
    max_label_len = max((len(_plain_label_for_length(label)) for label in labels), default=0)
    label_x = max(52.0, 65.6 - max(0, max_label_len - 6) * 1.8)
    try:
        headers, rows = _read_processed_csv(product.processed_data)
    except Exception:
        headers, rows = [], []
    sample_columns = [
        index
        for index, header in enumerate(headers[1:], start=1)
        if not is_template_xrd_reference_stick_header(str(header))
    ]
    y_values: list[float] = []
    for column_index in sample_columns[: len(labels)]:
        values: list[float] = []
        for row in rows:
            if column_index >= len(row):
                continue
            try:
                value = float(row[column_index])
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                values.append(value)
        if values:
            y_low, y_high = min(values), max(values)
            y_values.append(y_low + (y_high - y_low) * 0.45)
    if len(y_values) < len(labels):
        y_values.extend(max(0.38, 0.80 - index * 0.085) for index in range(len(y_values), len(labels)))
    return [(label, label_x, y_values[index]) for index, label in enumerate(labels[:6])]


def _plain_label_for_length(label: object) -> str:
    text = str(label or "")
    text = re.sub(r"(?:\\|/)b\((.*?)\)", r"\1", text)
    text = re.sub(r"(?:\\|/)-\((.*?)\)", r"\1", text)
    return re.sub(r"\\[A-Za-z]+\(|\)|/|\\", "", text)


def _format_preserved_line_sample_legend(
    operations: object,
    graph_name: str,
    style: ResolvedPlotStyle,
    *,
    font_size: int | None = None,
) -> dict[str, object]:
    font_name = style.font_family or "Arial"
    resolved_font_size = int(font_size or style.legend_font_size or 26)
    commands = [
        f'win -a "{quote_labtalk(graph_name)}"; legend.show=1;',
        f'win -a "{quote_labtalk(graph_name)}"; legend.font$="{quote_labtalk(font_name)}";',
        f'win -a "{quote_labtalk(graph_name)}"; legend.fsize={resolved_font_size};',
        f'win -a "{quote_labtalk(graph_name)}"; legend.bold=1;',
        f'win -a "{quote_labtalk(graph_name)}"; legend.background=0;',
        f'win -a "{quote_labtalk(graph_name)}"; legend.border=0;',
        f'win -a "{quote_labtalk(graph_name)}"; legend.fill=0;',
    ]
    results = [operations.run_labtalk(command) for command in commands]
    com_style = _style_graph_object(
        operations,
        graph_name,
        "Legend",
        font_name=font_name,
        font_size=resolved_font_size,
        color=1,
    )
    applied = com_style or all(bool(getattr(result, "ok", False)) for result in results[:4])
    return {
        "applied": applied,
        "method": "preserve_line_samples_format_legend_text",
        "line_samples_preserved": True,
        "font_name": font_name,
        "font_size": resolved_font_size,
        "bold": True,
        "no_frame": True,
        "styled_with_com": com_style,
        "messages": [str(getattr(result, "message", "")) for result in results if not getattr(result, "ok", False)],
    }


def _apply_xrd_standard_card_legend_and_label(
    operations: object,
    graph_name: str,
    product: ProductContext,
    entries: list[str],
    style: ResolvedPlotStyle,
    *,
    apply_reference_plot_style: bool = True,
) -> dict[str, object]:
    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except Exception:
        headers = []
    plotted_headers = _xrd_plotted_y_headers(product, headers)
    sample_headers = [
        header
        for _csv_index, header in plotted_headers
        if not is_template_xrd_reference_stick_header(header)
    ]
    card_headers = [
        header
        for _csv_index, header in plotted_headers
        if is_template_xrd_reference_stick_header(header)
    ]
    labels = entries[: len(sample_headers)] if entries else [header.replace("_", " ") for header in sample_headers]
    labels = [_xrd_plain_label_text(label) for label in labels]
    graph = quote_labtalk(graph_name)
    max_label_len = max((_plain_label_for_length(label) for label in labels), key=len, default="")
    legend_x = max(58.0, 66.0 - max(0, len(max_label_len) - 8) * 1.2)
    legend_y = _xrd_standard_card_legend_y(product)
    sample_plot_indices = [
        index for index, (_csv_index, header) in enumerate(plotted_headers, start=1)
        if not is_template_xrd_reference_stick_header(header)
    ]
    native_legend = update_native_legend(
        operations, graph_name, labels, plot_indices=sample_plot_indices,
    )
    commands = [
        f'win -a "{graph}"; legend.show=1;',
        f"legend.x={legend_x:g}; legend.y={legend_y:g};",
        f'legend.font$="{quote_labtalk(style.font_family or "Arial")}"; legend.fsize={int(style.legend_font_size or 26)}; legend.bold=1;',
        "legend.background=0; legend.border=0; legend.fill=0;",
    ]
    results = [operations.run_labtalk(f'win -a "{graph}"; {command}' if not command.startswith("win -a") else command) for command in commands]
    legend_com_applied = _style_graph_object(
        operations,
        graph_name,
        "Legend",
        font_name=style.font_family or "Arial",
        font_size=int(style.legend_font_size or 26),
        color=1,
    )
    operations.run_labtalk(f'win -a "{graph}"; legend.x={legend_x:g}; legend.y={legend_y:g};')
    plot_names = operations._plot_names(graph_name) if hasattr(operations, "_plot_names") else []
    reference_plot_indices = [
        index
        for index, (_csv_index, header) in enumerate(plotted_headers, start=1)
        if is_template_xrd_reference_stick_header(header)
    ]
    reference_plot_style_results: list[dict[str, object]] = []
    for plot_index in reference_plot_indices if apply_reference_plot_style else []:
        if 1 <= plot_index <= len(plot_names):
            plot_name = plot_names[plot_index - 1]
            commands = [
                f"layer.plot{plot_index}.color={XRD_STANDARD_CARD_STICK_COLOR_EXPR};",
                f"set {plot_name} -c {XRD_STANDARD_CARD_STICK_COLOR_EXPR};",
                f"set {plot_name} -cl {XRD_STANDARD_CARD_STICK_COLOR_EXPR};",
                "set {plot_name} -pfb 1;".format(plot_name=plot_name),
                f"set {plot_name} -pfc {XRD_STANDARD_CARD_STICK_COLOR_EXPR};",
                f"set {plot_name} -pbc {XRD_STANDARD_CARD_STICK_COLOR_EXPR};",
                "set {plot_name} -pbw 0.5;".format(plot_name=plot_name),
                f"set {plot_name} -w {XRD_STANDARD_CARD_STICK_WIDTH};",
                f"set {plot_name} -wp {XRD_STANDARD_CARD_STICK_WIDTH_PT};",
                f"set {plot_name} -l 1;",
            ]
            command_results: list[dict[str, object]] = []
            for command in commands:
                result = operations.run_labtalk(f'win -a "{graph}"; {command}')
                command_results.append({"command": command, "ok": bool(getattr(result, "ok", False))})
            readback = _read_plot_style_options(
                operations,
                plot_name,
                ("-c", "-cl", "-pfb", "-pfc", "-pbc", "-pbw", "-w", "-wp", "-l"),
            )
            reference_plot_style_results.append(
                {
                    "plot_index": plot_index,
                    "plot_name": plot_name,
                    "commands": command_results,
                    "readback": readback,
                }
            )
    card_label = _xrd_card_label_from_header(card_headers[0]) if card_headers else ""
    card_label_applied = False
    card_label_source = ""
    existing_card_label_policy: dict[str, object] = {"applied": False}
    if card_label:
        existing_card_label_policy = _update_existing_xrd_card_label_object(
            operations,
            graph_name,
            card_label,
            style,
        )
        if existing_card_label_policy.get("applied"):
            card_label_applied = True
            card_label_source = "template_graph_object"
        else:
            card_y = _xrd_standard_card_label_y(product)
            operations.run_labtalk(
                f'win -a "{graph}"; '
                f'label -r rdop_xrd_card_label; label -n rdop_xrd_card_label "{_quote_origin_rich_text(card_label)}";'
            )
            label_result = operations.run_labtalk(
                f'win -a "{graph}"; '
                f"rdop_xrd_card_label.x=32; rdop_xrd_card_label.y={card_y:g}; "
                f'rdop_xrd_card_label.font$="{quote_labtalk(style.font_family or "Arial")}"; '
                f"rdop_xrd_card_label.font=font({quote_labtalk(style.font_family or 'Arial')}); "
                f"rdop_xrd_card_label.fsize={int(style.legend_font_size or 26)}; "
                "rdop_xrd_card_label.bold=1; rdop_xrd_card_label.color=color(181,91,0); "
                "rdop_xrd_card_label.background=0; rdop_xrd_card_label.border=0; "
                "rdop_xrd_card_label.frame=0; rdop_xrd_card_label.fill=0; rdop_xrd_card_label.show=1;"
            )
            card_label_com_applied = _style_graph_object(
                operations,
                graph_name,
                "rdop_xrd_card_label",
                font_name=style.font_family or "Arial",
                font_size=int(style.legend_font_size or 26),
                color=18128807,
                width=2700,
                height=260,
            )
            card_label_applied = bool(getattr(label_result, "ok", False)) or card_label_com_applied
            card_label_source = "created_graph_object"
            operations.run_labtalk(f'win -a "{graph}"; rdop_xrd_card_label.color=color(181,91,0);')
    return {
        "applied": bool(native_legend.ok and legend_com_applied and (not card_label or card_label_applied)),
        "native_legend": native_legend.payload,
        "native_legend_message": native_legend.message,
        "method": "xrd_standard_card_sample_legend_plus_card_label",
        "sample_legend_entries": labels,
        "reference_card_headers": card_headers,
        "legend_x": legend_x,
        "legend_y": legend_y,
        "card_label": card_label,
        "card_label_applied": card_label_applied,
        "card_label_source": card_label_source,
        "existing_card_label_object": existing_card_label_policy,
        "legend_com_applied": legend_com_applied,
        "reference_plot_style_applied": apply_reference_plot_style,
        "reference_plot_style": reference_plot_style_results,
    }


def _update_existing_xrd_card_label_object(
    operations: object,
    graph_name: str,
    card_label: str,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "no_origin_app"}
    updated: list[dict[str, object]] = []
    font_code = _origin_font_code(app, style.font_family or "Arial")
    for layer_index in range(1, 25):
        try:
            layer = app.FindGraphLayer(f"[{graph_name}]{layer_index}")
        except Exception:
            layer = None
        if not layer:
            if updated:
                break
            continue
        collection = getattr(layer, "GraphObjects", None)
        if collection is None:
            continue
        try:
            count = int(getattr(collection, "Count", 0))
        except Exception:
            continue
        for base in (0, 1):
            layer_updated = False
            for index in range(count):
                try:
                    graph_object = collection.Item(index + base)
                except Exception:
                    continue
                original_text = str(getattr(graph_object, "Text", "") or "")
                if "JCPDS" not in original_text:
                    continue
                try:
                    graph_object.Text = card_label
                except Exception:
                    continue
                for prop, value in (
                    ("font", font_code),
                    ("fsize", int(style.legend_font_size or 26)),
                    ("bold", 1),
                    ("color", 18128807),
                    ("background", 0),
                    ("border", 0),
                    ("frame", 0),
                    ("fill", 0),
                ):
                    try:
                        graph_object.SetNumProp(prop, value)
                    except Exception:
                        pass
                updated.append(
                    {
                        "layer_index": layer_index,
                        "object_name": str(getattr(graph_object, "Name", "") or ""),
                        "previous_text": original_text,
                    }
                )
                layer_updated = True
            if layer_updated:
                break
    return {
        "applied": bool(updated),
        "updated_count": len(updated),
        "updated_objects": updated,
    }


def _read_plot_style_options(
    operations: object,
    plot_name: str,
    options: tuple[str, ...],
) -> dict[str, object]:
    if not hasattr(operations, "get_labtalk_variable"):
        return {}
    values: dict[str, object] = {}
    for option in options:
        key = option.lstrip("-")
        variable = f"__rdop_plot_style_{re.sub(r'[^A-Za-z0-9_]+', '_', key)}"
        try:
            operations.run_labtalk(f"get {plot_name} {option} {variable};")
            result = operations.get_labtalk_variable(variable)
            values[key] = getattr(result, "payload", {}).get("value")
        except Exception as exc:
            values[key] = f"read_failed: {exc}"
    return values


def _quote_origin_rich_text(text: object) -> str:
    return str(text or "").replace('"', '\\"').replace("\r", " ").replace("\n", " ")


def _style_graph_object(
    operations: object,
    graph_name: str,
    object_name: str,
    *,
    font_name: str,
    font_size: int,
    color: int,
    left: int | None = None,
    top: int | None = None,
    width: int | None = None,
    height: int | None = None,
    bold: int = 1,
    background: int = 0,
    border: int = 0,
    frame: int = 0,
    fill: int = 0,
    fill_color: int | None = None,
    border_color: int | None = None,
    line_width: float | None = None,
) -> bool:
    app = getattr(operations, "app", None)
    if app is None:
        return False
    try:
        layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
    except Exception:
        return False
    if not layer:
        return False
    graph_object = _find_origin_graph_object(layer, object_name)
    if graph_object is None:
        return False
    font_code = _origin_font_code(app, font_name)
    try:
        if left is not None:
            graph_object.Left = left
        if top is not None:
            graph_object.Top = top
        if width is not None:
            graph_object.Width = width
        if height is not None:
            graph_object.Height = height
    except Exception:
        return False
    for prop, value in (
        ("font", font_code),
        ("fsize", int(font_size)),
        ("bold", int(bold)),
        ("color", int(color)),
        ("background", int(background)),
        ("border", int(border)),
        ("frame", int(frame)),
        ("fill", int(fill)),
        ("fillColor", fill_color),
        ("borderColor", border_color),
        ("lineWidth", line_width),
    ):
        if value is None:
            continue
        try:
            graph_object.SetNumProp(prop, value)
        except Exception:
            pass
    return True


def _xrd_standard_card_legend_y(product: ProductContext) -> float:
    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except Exception:
        headers = []
    sample_columns = tuple(
        index
        for index, header in _xrd_plotted_y_headers(product, headers)
        if not is_template_xrd_reference_stick_header(header)
    )
    y_min, y_max = _csv_bounds_for_columns(product.processed_data, sample_columns or tuple(range(1, 16)))
    if y_min is None or y_max is None:
        return 6.6
    span = max(y_max - y_min, 1.0)
    return y_max + max(0.95, span * 0.21)


def _xrd_standard_card_label_y(product: ProductContext) -> float:
    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except Exception:
        headers = []
    card_columns = tuple(
        index
        for index, header in _xrd_plotted_y_headers(product, headers)
        if is_template_xrd_reference_stick_header(str(header))
    )
    if not card_columns:
        return 0.95
    y_min, y_max = _csv_bounds_for_columns(product.processed_data, card_columns)
    if y_min is None or y_max is None:
        return 0.95
    return y_max + max(0.18, (y_max - y_min) * 0.18)


def _xrd_card_label_from_header(header: str) -> str:
    text = str(header or "")
    material = text.split("_PDF", 1)[0].replace("_", " ").strip() or "Reference"
    if material.casefold() == "cwo":
        material = r"CuWO\-(4)"
    match = re.search(r"(\d{2}-\d{3}-\d{4})", text)
    if match:
        return rf"\b({material} JCPDS card No.{match.group(1)})"
    return rf"\b({material} JCPDS card)"


def _xrd_standard_card_keeps_line_sample_legend(product: ProductContext) -> bool:
    if product.product_key != "XRD":
        return False
    try:
        headers, _rows = _read_processed_csv(product.processed_data)
    except Exception:
        headers = []
    return any(is_template_xrd_reference_stick_header(str(header)) for header in headers)


def _position_xrd_plain_legend_objects(
    operations: object,
    graph_name: str,
    names: list[str],
    labels: list[str],
    *,
    font_name: str,
    font_size: int,
) -> bool:
    app = getattr(operations, "app", None)
    if app is None:
        return False
    try:
        layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(graph_name)
    except Exception:
        return False
    if not layer:
        return False
    font_code = _origin_font_code(app, font_name)
    width = 1900
    height = 236
    positioned = False
    for index, (name, label) in enumerate(zip(names, labels), start=1):
        graph_object = _find_origin_graph_object(layer, name)
        if graph_object is None:
            continue
        try:
            graph_object.Text = label
            graph_object.Width = width
            graph_object.Height = height
        except Exception:
            continue
        for prop, value in (
            ("font", font_code),
            ("fsize", int(font_size)),
            ("bold", 1),
            ("color", 1),
            ("background", 0),
            ("border", 0),
            ("frame", 0),
            ("fill", 0),
        ):
            try:
                graph_object.SetNumProp(prop, value)
            except Exception:
                pass
        positioned = True
    return positioned


def _find_origin_graph_object(layer: object, name: str) -> object | None:
    collection = getattr(layer, "GraphObjects", None)
    if collection is None:
        return None
    try:
        return collection[name]
    except Exception:
        pass
    try:
        count = int(getattr(collection, "Count", 0))
    except Exception:
        return None
    for base in (0, 1):
        for index in range(count):
            try:
                obj = collection.Item(index + base)
            except Exception:
                continue
            if str(getattr(obj, "Name", "") or "").casefold() == name.casefold():
                return obj
    return None


def _find_unique_origin_graph_object(layer: object, name: str) -> object | None:
    """Return a named object only when the template contains it exactly once."""
    candidate = _find_origin_graph_object(layer, name)
    collection = getattr(layer, "GraphObjects", None)
    if candidate is None or collection is None:
        return None
    try:
        count = int(getattr(collection, "Count"))
    except (TypeError, ValueError, AttributeError):
        return None
    if count < 1:
        return None
    # Origin collections can be zero- or one-based depending on the COM
    # wrapper.  Use the first base that enumerates the full collection, then
    # reject duplicate case-insensitive object names rather than guessing.
    objects: list[object] = []
    for base in (0, 1):
        attempt: list[object] = []
        for index in range(count):
            try:
                attempt.append(collection.Item(index + base))
            except Exception:
                break
        if len(attempt) == count:
            objects = attempt
            break
    if not objects:
        return None
    matches = [
        graph_object
        for graph_object in objects
        if str(getattr(graph_object, "Name", "") or "").casefold() == name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _update_verified_epr_label_objects(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    labels = [str(value).strip() for value in entries]
    if (
        len(labels) != 3
        or any(not label for label in labels)
        or len({label.casefold() for label in labels}) != 3
    ):
        return {"applied": False, "reason": "epr_labels_must_be_three_nonempty_unique_values"}
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "no_origin_app"}
    try:
        layer = (
            app.FindGraphLayer(f"[{graph_name}]Layer1")
            or app.FindGraphLayer(f"[{graph_name}]1")
            or app.FindGraphLayer(graph_name)
        )
    except Exception:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    if not layer:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    readback: dict[str, str] = {}
    for object_name, label in zip(("DL1", "DL2", "DL3"), labels):
        graph_object = _find_unique_origin_graph_object(layer, object_name)
        if graph_object is None:
            return {
                "applied": False,
                "reason": "required_epr_label_missing_or_not_unique",
                "object_name": object_name,
            }
        rich_text = origin_bold_text(label)
        try:
            graph_object.Text = rich_text
            actual = str(getattr(graph_object, "Text", "") or "")
        except Exception:
            return {
                "applied": False,
                "reason": "epr_label_write_or_readback_failed",
                "object_name": object_name,
            }
        if actual != rich_text:
            return {
                "applied": False,
                "reason": "epr_label_readback_mismatch",
                "object_name": object_name,
                "expected": rich_text,
                "actual": actual,
            }
        readback[object_name] = actual
    return {
        "applied": True,
        "method": "template_dl_objects_current_bold_rich_text",
        "objects": readback,
        "entries": labels,
    }


def _update_verified_pl_legend(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    labels = [str(value).strip() for value in entries]
    if (
        not labels
        or any(not label for label in labels)
        or len({label.casefold() for label in labels}) != len(labels)
    ):
        return {"applied": False, "reason": "pl_legend_requires_nonempty_unique_current_values"}
    if not update_native_legend(
        operations, graph_name, labels,
        plot_indices=range(1, len(labels) + 1),
    ).ok:
        return {"applied": False, "reason": "pl_legend_com_text_write_failed"}
    return {
        "applied": True,
        "method": "template_legend_current_bold_rich_text",
        "entries": labels,
        "entry_count": len(labels),
        "line_samples_preserved": True,
    }


def _update_verified_raman_label_objects(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    """Rebuild Raman's distributed labels as native, linked Origin legends."""

    labels = [str(value).strip() for value in entries]
    if (
        len(labels) != 3
        or any(not label for label in labels)
        or len({label.casefold() for label in labels}) != 3
    ):
        return {
            "applied": False,
            "reason": "raman_labels_require_three_nonempty_unique_values",
        }
    app = getattr(operations, "app", None)
    if app is None or not hasattr(operations, "run_labtalk"):
        return {"applied": False, "reason": "no_origin_app"}

    def _layer(layer_index: int) -> object | None:
        references = [f"[{graph_name}]Layer{layer_index}", f"[{graph_name}]{layer_index}"]
        if layer_index == 1:
            references.append(graph_name)
        for reference in references:
            try:
                candidate = app.FindGraphLayer(reference)
            except Exception:
                continue
            if candidate is not None:
                return candidate
        return None

    layer1 = _layer(1)
    layer2 = _layer(2)
    if layer1 is None or layer2 is None:
        return {"applied": False, "reason": "graph_layer_unavailable"}

    def _snapshot(object_name: str, *, with_style: bool = True) -> dict[str, object] | None:
        graph_object = _find_unique_origin_graph_object(layer1, object_name)
        if graph_object is None:
            return None
        try:
            geometry = {
                key: getattr(graph_object, attribute)
                for key, attribute in (
                    ("left", "Left"), ("top", "Top"),
                    ("width", "Width"), ("height", "Height"),
                )
            }
            properties = {
                property_name: graph_object.GetNumProp(property_name)
                for property_name in (
                    "font", "fsize", "color", "bold", "background", "border", "frame",
                    "fill", "fillColor", "borderColor", "lineWidth",
                )
            } if with_style else {}
        except Exception:
            return None
        return {"geometry": geometry, "properties": properties}

    snapshots = {
        "Legend": _snapshot("Legend"),
        "Text1": _snapshot("Text1"),
        "Text": _snapshot("Text"),
        "Line1": _snapshot("Line1", with_style=False),
    }
    if any(snapshot is None for snapshot in snapshots.values()):
        return {"applied": False, "reason": "required_raman_label_missing_or_unreadable"}

    def _restore(
        layer: object,
        object_name: str,
        snapshot: dict[str, object],
        *,
        left: object | None = None,
        centered_top: object | None = None,
    ) -> bool:
        graph_object = _find_unique_origin_graph_object(layer, object_name)
        if graph_object is None:
            return False
        geometry = snapshot["geometry"]
        try:
            graph_object.Left = geometry["left"] if left is None else left
            graph_object.Top = geometry["top"] if centered_top is None else centered_top
            if left is None:
                graph_object.Width = geometry["width"]
                graph_object.Height = geometry["height"]
            for property_name, value in snapshot["properties"].items():
                graph_object.SetNumProp(property_name, value)
        except Exception:
            return False
        return True

    def _remove(layer_index: int, object_name: str) -> bool:
        return bool(getattr(operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; layer -s {layer_index}; '
            f'label -r {quote_labtalk(object_name)};'
        ), "ok", False))

    def _native(layer_index: int, plot_index: int, label: str, target_name: str) -> bool:
        generated = update_native_legend(
            operations, graph_name, [label], plot_indices=[plot_index], layer_index=layer_index,
        )
        if not getattr(generated, "ok", False):
            return False
        renamed = operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; layer -s {layer_index}; '
            f'legend.name$="{quote_labtalk(target_name)}";'
        )
        return bool(getattr(renamed, "ok", False))

    legend_snapshot = snapshots["Legend"]
    text1_snapshot = snapshots["Text1"]
    text_snapshot = snapshots["Text"]
    line_snapshot = snapshots["Line1"]
    assert all(value is not None for value in (legend_snapshot, text1_snapshot, text_snapshot, line_snapshot))

    if not _remove(1, "Text") or not _native(1, 2, labels[2], "Text"):
        return {"applied": False, "reason": "raman_native_legend_generation_failed"}
    if not _restore(layer1, "Text", text_snapshot):
        return {"applied": False, "reason": "raman_native_legend_layout_restore_failed"}

    if not _remove(1, "Text1") or not _remove(1, "Line1") or not _native(2, 1, labels[1], "Text1"):
        return {"applied": False, "reason": "raman_native_legend_generation_failed"}
    row_geometry = text1_snapshot["geometry"]
    sample_geometry = line_snapshot["geometry"]
    layer2_legend = _find_unique_origin_graph_object(layer2, "Text1")
    if layer2_legend is None:
        return {"applied": False, "reason": "raman_native_legend_layout_restore_failed"}
    centered_top = row_geometry["top"] + (row_geometry["height"] - layer2_legend.Height) / 2
    if not _restore(layer2, "Text1", text1_snapshot, left=sample_geometry["left"], centered_top=centered_top):
        return {"applied": False, "reason": "raman_native_legend_layout_restore_failed"}

    if not update_native_legend(
        operations, graph_name, [labels[0]], plot_indices=[1], layer_index=1,
    ).ok or not _restore(layer1, "Legend", legend_snapshot):
        return {"applied": False, "reason": "raman_native_legend_generation_failed"}
    return {
        "applied": True,
        "method": "origin_native_distributed_raman_legends",
        "entries": labels,
        "source_order_to_template_objects": {
            "1": "Legend/layer1_plot1",
            "2": "Text1/Line1(layer1)->layer2_plot1",
            "3": "Text/layer1_plot2",
        },
        "native_legends": True,
        "manual_line_removed": True,
    }


def _update_verified_photocurrent_legend(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    labels = [str(value).strip() for value in entries]
    if (
        len(labels) != 3
        or any(not label for label in labels)
        or len({label.casefold() for label in labels}) != 3
    ):
        return {
            "applied": False,
            "reason": "photocurrent_legend_requires_three_nonempty_unique_current_labels",
        }
    if not update_native_legend(
        operations, graph_name, labels,
        plot_indices=range(1, len(labels) + 1),
    ).ok:
        return {
            "applied": False,
            "reason": "photocurrent_legend_com_text_write_failed",
        }
    return {
        "applied": True,
        "method": "template_legend_current_bold_rich_text",
        "entries": labels,
        "native_legend": True,
        "line_samples_preserved": True,
        "old_sample_names_removed": True,
    }


def _update_verified_ftir_legend(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    labels = tuple(str(value).strip() for value in entries)
    if labels != VERIFIED_FTIR_SERIES_LABELS:
        return {
            "applied": False,
            "reason": "ftir_legend_requires_exact_reviewed_series_labels",
        }
    if not update_native_legend(
        operations, graph_name, _ftir_native_legend_labels(labels),
        plot_indices=range(1, len(labels) + 1),
    ).ok:
        return {"applied": False, "reason": "ftir_legend_com_text_write_failed"}
    return {
        "applied": True,
        "method": "template_legend_exact_reference_rich_text",
        "entries": list(labels),
        "native_legend": True,
        "line_samples_preserved": True,
    }


def _set_origin_graph_object_text(
    operations: object,
    graph_name: str,
    object_name: str,
    text: str,
) -> bool:
    app = getattr(operations, "app", None)
    if app is None:
        return False
    try:
        layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(f"[{graph_name}]1") or app.FindGraphLayer(graph_name)
    except Exception:
        return False
    if not layer:
        return False
    graph_object = _find_origin_graph_object(layer, object_name)
    if graph_object is None:
        return False
    try:
        # Refresh native annotation rendering after a LabTalk text change.
        graph_object.Text = text
    except Exception:
        return False
    return str(getattr(graph_object, "Text", "") or "") == text


def _origin_font_code(app: object, font_name: str) -> int:
    try:
        code = int(float(app.Evaluate(f"font({font_name})")))
        return code or 67
    except Exception:
        return 67


def _xrd_plain_label_text(entry: object) -> str:
    text = _origin_rich_text_for_labtalk(entry)
    text = re.sub(r"^\\l\(\d+\)\s*", "", text).strip()
    if not text:
        return ""
    if "\\b(" not in text:
        text = origin_bold_text(text)
    return text.replace(";", ",")


def _plain_text_legend_policy(
    product: ProductContext,
    *,
    entries: list[str] | None = None,
    anchor_policy: dict[str, object] | None = None,
    xrd_plain_label_policy: dict[str, object] | None = None,
    line_samples_removed: bool = True,
    preserved_line_sample_policy: dict[str, object] | None = None,
    xrd_card_label_policy: dict[str, object] | None = None,
    xrd_standard_card_reference_sticks_present: bool | None = None,
) -> dict[str, object]:
    resolved_entries = _plain_text_legend_entries(product) if entries is None else list(entries)
    policy = {
        "line_samples_removed": bool(line_samples_removed),
        "method": "plain_text_labels" if line_samples_removed else "template_line_sample_legend_preserved",
        "entry_count": len(resolved_entries),
        "entries": resolved_entries,
        "visible": bool(resolved_entries),
        "anchor_policy": anchor_policy or {},
        "reason": (
            "User requested legend text without the colored sample line."
            if line_samples_removed
            else (
                f"{product.product_key} preserves the reviewed template's colored line-sample legend."
                if product.product_key in REVIEWED_TEMPLATE_VISIBLE_PLOTS
                else "XRD standard-card figures keep the template legend colored line samples; no-card XRD removes them."
            )
        ),
    }
    if xrd_plain_label_policy:
        policy["xrd_plain_text_labels"] = xrd_plain_label_policy
    if preserved_line_sample_policy:
        policy["preserved_line_sample_legend"] = preserved_line_sample_policy
    if xrd_card_label_policy:
        policy["xrd_standard_card_labels"] = xrd_card_label_policy
    if product.product_key == "XRD":
        policy["xrd_standard_card_reference_sticks_present"] = (
            bool(not line_samples_removed)
            if xrd_standard_card_reference_sticks_present is None
            else bool(xrd_standard_card_reference_sticks_present)
        )
    return policy


def _plain_text_legend_entries(product: ProductContext, exemplar_snapshot: object | None = None) -> list[str]:
    if product.product_key == "EIS":
        entries = list(product.legend_entries)
        return entries[2:5] if len(entries) >= 5 else entries
    if product.product_key == "XRD":
        try:
            headers, _rows = _read_processed_csv(product.processed_data)
        except Exception:
            headers = []
        sample_headers = [
            header
            for _csv_index, header in _xrd_plotted_y_headers(product, headers)
            if not is_template_xrd_reference_stick_header(header)
        ]
        entries = list(product.legend_entries)
        if entries and sample_headers:
            return entries[: len(sample_headers)]
        if entries:
            return entries
        return [header.replace("_", " ").strip() for header in sample_headers]
    if product.product_key.startswith("XPS"):
        entries = _xps_measured_legend_entries(product.processed_data)
        if entries:
            return entries
    entries = _legend_entries_for_product(product, exemplar_snapshot)
    return _strip_redundant_measurement_suffixes(product.product_key, entries)


def _strip_redundant_measurement_suffixes(product_key: str, entries: list[str]) -> list[str]:
    suffixes = {
        "FTIR": ("transmittance",),
        "PL": ("counts",),
        "Raman": ("intensity",),
        "UV-vis DRS": ("drs signal",),
        "Tauc": ("tauc y direct candidate",),
        "photocurrent": ("current a",),
    }.get(product_key, ())
    if not suffixes:
        return entries
    cleaned: list[str] = []
    for entry in entries:
        text = str(entry).strip()
        for suffix in suffixes:
            text = re.sub(rf"\s+{re.escape(suffix)}\s*$", "", text, flags=re.IGNORECASE)
        cleaned.append(text)
    return cleaned


def _xps_measured_legend_entries(processed_csv: Path) -> list[str]:
    try:
        headers, _rows = _read_processed_csv(processed_csv)
    except Exception:
        return []
    entries: list[str] = []
    seen: set[str] = set()
    for header in headers:
        text = str(header).strip()
        if not text.casefold().endswith("_measured"):
            continue
        label = text[: -len("_measured")].replace("_", " ").strip()
        if not label or label.casefold() in seen:
            continue
        seen.add(label.casefold())
        entries.append(label)
    return entries[:6]


def _legend_entries_for_product(product: ProductContext, exemplar_snapshot: object | None = None) -> list[str]:
    entries = _legend_entries_from_exemplar_snapshot(exemplar_snapshot)
    return entries or list(product.legend_entries)


def _legend_entries_from_exemplar_snapshot(exemplar_snapshot: object | None) -> list[str]:
    if exemplar_snapshot is None:
        return []
    audit_strings = getattr(exemplar_snapshot, "audit_string_values", None)
    if not isinstance(audit_strings, dict) and isinstance(exemplar_snapshot, dict):
        audit_strings = exemplar_snapshot.get("audit_string_values")
    if not isinstance(audit_strings, dict):
        return []
    text = str(audit_strings.get("legend.text$") or "").strip()
    if not text:
        return []
    entries: list[str] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(r"(?:\\|/)l\(\d+\)\s*(.*?)(?=(?:\\|/)l\(\d+\)|$)", re.DOTALL)
    matches = list(pattern.finditer(normalized))
    parts = [match.group(1) for match in matches] if matches else normalized.split("\n")
    for part in parts:
        entry = _clean_exemplar_legend_entry(part)
        if entry and "%(" not in entry:
            entries.append(entry)
    return entries


def _clean_exemplar_legend_entry(value: object) -> str:
    text = str(value or "").replace("/", "\\").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"^\\l\(\d+\)\s*", "", text).strip()
    text = re.sub(r"\\+$", "", text).strip()
    text = text.strip(" /\t")
    return text


def _origin_rich_text_for_labtalk(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(
        r"/(?=(?:[bil]\(|[cf](?::|\d)|[+\-]\(|\(\d+\)))",
        r"\\",
        text,
    )
    return re.sub(r"[/\\]+$", "", text).strip()


def _strip_raster_metadata(path: Path, *, dpi: int) -> str:
    if path.suffix.casefold() in {".tif", ".tiff"}:
        return (
            f"TIFF metadata stripping is disabled for {path.name}; "
            "production TIFFs must remain the native Origin export and pass physical-resolution validation."
        )
    try:
        from PIL import Image

        with Image.open(path) as image:
            fmt = image.format or path.suffix.lstrip(".").upper()
            image.load()
            clean = Image.new(image.mode, image.size)
            # Copy the native pixel buffer without millions of Python pixel tuples.
            clean.paste(image)
            clean.info.clear()
            tmp = path.with_name(f"{path.stem}.stripped{path.suffix}")
            save_kwargs: dict[str, object] = {"dpi": (dpi, dpi)}
            if fmt.upper() in {"TIF", "TIFF"}:
                save_kwargs["compression"] = "tiff_lzw"
            clean.save(tmp, format=fmt, **save_kwargs)
        tmp.replace(path)
        return ""
    except Exception as exc:
        return f"raster metadata strip skipped for {path.name}: {exc}"


def _apply_template_base_global_policies(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
    template_axis_titles: dict[str, object] | None = None,
) -> None:
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    axis_commands = _bold_template_axis_title_commands(template_axis_titles or {})
    if axis_commands:
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; {axis_commands}')
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; xb.bold=1; yl.bold=1; xb.show=1; yl.show=1;')
    operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        f"doc -e DY {{set %C -wp {float(style.line_width_pt):g}; set %C -lw {float(style.line_width_pt):g};}} "
        "xb.bold=1; yl.bold=1; xb.show=1; yl.show=1;"
    )

def _bold_template_axis_title_commands(axis_titles: dict[str, object]) -> str:
    x_title = _bold_axis_title_message(axis_titles.get("xb.text$"))
    y_title = _bold_axis_title_message(axis_titles.get("yl.text$"))
    commands: list[str] = []
    if x_title:
        commands.append(f"label -s -xb {x_title};")
    if y_title:
        commands.append(f"label -s -yl {y_title};")
    return " ".join(commands)


def _bold_axis_title_message(value: object) -> str:
    text = str(value or "").replace(";", ",").replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return ""
    return origin_bold_text(text)


def _template_base_xps_fill_intent(product: ProductContext, replacement: dict[str, object]) -> dict[str, object]:
    required = product.product_key.startswith("XPS")
    updates = replacement.get("template_dataset_updates") if isinstance(replacement.get("template_dataset_updates"), dict) else {}
    return {
        "required": required,
        "applied": required,
        "policy": "XPS component fill/gradient objects are preserved from the OPJU template base; only referenced workbook data are replaced.",
        "component_plot_count": updates.get("visual_plot_count", 0) if required else 0,
        "unique_dataset_count": (
            updates.get("unique_plot_pair_count", updates.get("unique_dataset_count", 0))
            if required
            else 0
        ),
    }


def _read_processed_csv(path: Path) -> tuple[list[str], list[list[object]]]:
    cache = current_template_inputs()
    if cache is not None and path in cache.tables:
        return cache.tables[path]
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        rows = [row for row in reader if any(str(cell).strip() for cell in row)]
    if len(rows) < 2:
        raise ValueError(f"processed CSV has no numeric rows: {path.name}")
    headers = [str(cell).strip() for cell in rows[0]]
    data_rows: list[list[object]] = []
    for row in rows[1:]:
        data_rows.append([_coerce_csv_cell(cell) for cell in row])
    result = headers, data_rows
    if cache is not None:
        cache.tables[path] = result
    return result


def _write_processed_csv(
    path: Path,
    headers: list[str],
    rows: list[list[object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(
                [
                    ""
                    if value is None
                    or (isinstance(value, float) and not math.isfinite(value))
                    else value
                    for value in row
                ]
            )
    invalidate_processed_table(path)


def _coerce_csv_cell(value: object) -> object:
    text = str(value).strip()
    if text == "":
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return text


def _write_template_format_docs(project_root: Path, run_root: Path, result: dict[str, object]) -> None:
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    products = result.get("products") if isinstance(result.get("products"), list) else []
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    payload = {
        "policy": "Each product records its selected Origin route. Verified fixed bindings use the accepted OTPU asset; adaptive bindings use the accepted OTH+JSON bundle. Explicit exemplar-driven mode uses an isolated reference OPJU copy. Asset registry, data, style and export acceptance gates remain required.",
        "one_to_one_policy": "No product may claim one-to-one replication unless reference and generated graphs use identical per-plot X/Y data and mappings, then pass save/reopen readback, native 600 dpi export, exact decoded-pixel comparison, and manual preview.",
        "summary": summary,
        "products": products,
    }
    (reports / "template_format_executor_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Template-format product executor",
        "",
        "- Origin route: each product below reports the actual selected route and decision; skipped or blocked exports do not claim a completed route.",
        "- Fixed route: a verified `.otpu` asset with the matching fixed data-binding contract.",
        "- Adaptive route: the accepted `.oth` + JSON bundle and the current product's validated data bindings.",
        "- Explicit exemplar-driven mode: an isolated reference OPJU copy with mapped worksheet replacement.",
        "- Asset rule: registry validation and the existing data, style and export acceptance gates apply to the selected route.",
        "- Exactness rule: compare only graphs built from identical per-plot X/Y data and mappings; one-to-one replication is not claimed until save/reopen readback, native 600 dpi export, zero decoded-pixel difference, and manual preview all pass.",
        "- Style rule: line width, fonts, axes, layers, plot types, legend geometry, and other graph formatting are compared with the selected exemplar rather than forced to global constants.",
        "",
        f"- Run root: {render_output_path(run_root, project_root=project_root)}",
        f"- Product count: {summary.get('product_count', '')}",
        f"- Accepted/success count: {summary.get('accepted_count', summary.get('success_count', ''))}",
        f"- Blocked count: {summary.get('blocked_count', '')}",
        f"- Failed count: {summary.get('failed_count', '')}",
    ]
    for product in products:
        if not isinstance(product, dict):
            continue
        decision = product.get("origin_style_decision")
        decision = decision if isinstance(decision, dict) else {}
        selected_mode = decision.get("selected_mode") or product.get("template_format_mode") or "not executed"
        reason = str(decision.get("reason_code") or "")
        lines.append(
            f"- {product.get('product_key') or product.get('type') or 'Product'}: "
            f"{selected_mode}" + (f" ({reason})" if reason else "")
        )
    (reports / "template_format_executor_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
