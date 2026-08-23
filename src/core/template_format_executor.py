from __future__ import annotations

import csv
import json
import math
import re
import shutil
import tempfile
import traceback
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path

from src.core.file_utils import file_sha256
from src.core.origin_style_assets import (
    compare_graph_data_snapshots,
    read_graph_data_snapshot,
)
from src.core.template_product_common import ProductContext, _product_output_path
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
    is_template_xrd_reference_stick_header,
    run_template_product_builder_all_types,
    template_plot_type_for_header,
)
from src.origin.conformance import compare_style_snapshots
from src.origin.embedded_template_snapshots import embedded_template_snapshot
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_registry import (
    resolve_origin_adaptive_style_asset,
    resolve_origin_runtime_style_asset,
)
from src.origin.style_mimic import (
    _origin_plot_color_for_labtalk,
    apply_style_snapshot,
    extract_style_snapshot,
    read_graph_style_snapshot,
)
from src.origin.template_binding import (
    load_template_binding_contracts,
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
XRD_STANDARD_CARD_SAMPLE_LIMIT = 4
XRD_STANDARD_CARD_SAMPLE_COLOR_SEQUENCE = (16814848, 33518174, 18128807, 16814848)
XRD_STANDARD_CARD_STICK_COLOR_EXPR = "color(181,91,0)"
XRD_STANDARD_CARD_STICK_WIDTH = 1500
XRD_STANDARD_CARD_STICK_WIDTH_PT = 3
REVIEWED_TEMPLATE_VISIBLE_PLOTS = {
    "EIS": (3, 4, 5),
    "Mott-Schottky": (1, 2, 3),
}
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
    else:
        failures.append(f"adaptive source layout is unsupported: {layout!r}")

    for series_index, (x_index, y_index) in enumerate(source_pairs, start=1):
        states: list[bool] = []
        for row in rows:
            x_value = _finite_numeric_value(row[x_index]) if x_index < len(row) else None
            y_value = _finite_numeric_value(row[y_index]) if y_index < len(row) else None
            if (x_value is None) != (y_value is None):
                failures.append(f"series {series_index} contains an unpaired X or Y value")
                break
            states.append(x_value is not None)
        bounds = _paired_numeric_row_bounds(rows, x_index, y_index)
        if bounds is None:
            failures.append(f"series {series_index} has no contiguous finite X/Y run")
        elif any(states[bounds[1] :]):
            failures.append(f"series {series_index} contains data after a blank tail")
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

    try:
        adaptive_asset = resolve_origin_adaptive_style_asset(
            project_root,
            product.product_key,
            allow_candidate=mode == "oth-json",
        )
    except (OSError, ValueError) as exc:
        if mode == "oth-json":
            return (
                _style_execution_decision(
                    product,
                    requested_mode=mode,
                    selected_mode="blocked",
                    reason_code="adaptive_asset_registry_invalid",
                    message=str(exc),
                    current_series_count=current_count,
                    contract_series_count=0,
                    asset=None,
                    ok=False,
                    candidate_assets_allowed=True,
                ),
                None,
            )
        adaptive_asset = None

    contract_asset = exact_asset or adaptive_asset
    contract, contract_error = _binding_contract_for_asset(
        product.product_key,
        contract_asset,
    )
    contract_count = int(getattr(contract, "source_series_count", 0) or 0)

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
        complete, message = _adaptive_asset_complete(adaptive_asset)
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
        complete, _message = _adaptive_asset_complete(adaptive_asset)
        if complete:
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
            if product.product_key in {"UV-vis DRS", "Tauc"}:
                source_validation = _strict_adaptive_source_validation(
                    contract,
                    headers,
                    rows,
                    [(x_col - 1, y_col - 1) for x_col, y_col in plot_pairs],
                )
                adaptive_complete, adaptive_error = _adaptive_asset_complete(adaptive_asset)
                if source_validation.get("ok") and adaptive_complete:
                    return (
                        _style_execution_decision(
                            product,
                            requested_mode=mode,
                            selected_mode="oth-json",
                            reason_code="fixed_cardinality_semantics_select_adaptive_uvvis",
                            message=(
                                "Current UV-vis columns are valid spectra but do not carry the "
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
    complete, adaptive_error = _adaptive_asset_complete(adaptive_asset)
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
            project_template_opju = _project_local_template_opju_for_product(product, style_asset)
            reference_source = project_template_opju or product.reference_opju_copy
            runtime_reference = runtime / reference_source.name
            plan_opju: Path | None = None
            if (
                not asset_only
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
                style_package_path=None if project_template_opju is not None else (style_asset.format_theme_path if style_asset else None),
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
                    legend_anchor_policy = _apply_nonoverlap_plain_legend_anchor(
                        operations,
                        graph_name,
                        product,
                        legend_entries,
                    )
                    if product.product_key == "XRD":
                        xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(
                            operations,
                            graph_name,
                            product,
                            legend_entries,
                            style,
                        )
                    else:
                        _replace_legend_with_plain_text_labels(
                            operations,
                            graph_name,
                            legend_entries,
                            style,
                            prefer_existing_text=False,
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
                    line_samples_removed=not xrd_keep_line_legend,
                    preserved_line_sample_policy=preserved_legend_policy if xrd_keep_line_legend else None,
                    xrd_card_label_policy=xrd_card_label_policy if xrd_keep_line_legend else None,
                    xrd_standard_card_reference_sticks_present=xrd_keep_line_legend,
                )
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


def _project_local_template_opju_for_product(product: ProductContext, style_asset: object | None) -> Path | None:
    # A saved project-local OPJU is kept as an extraction/recovery asset, but it
    # should not be the default product base unless a future manifest explicitly
    # opts into exact workbook-template replacement. Current XRD card products
    # vary in series count, so the clean graph + saved format theme path is safer.
    return None


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
        legend_anchor_policy = _apply_nonoverlap_plain_legend_anchor(operations, graph_name, product, legend_entries)
        if product.product_key == "XRD":
            xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(
                operations,
                graph_name,
                product,
                legend_entries,
                style,
            )
        else:
            _replace_legend_with_plain_text_labels(
                operations,
                graph_name,
                legend_entries,
                style,
                prefer_existing_text=False,
            )
            xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(operations, graph_name, product, legend_entries, style)
    plot_sequence = _apply_external_reference_plot_sequence(
        operations,
        graph_name,
        exemplar_snapshot.to_dict(),
        product=product,
    )
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; title.show=0;')

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
                line_samples_removed=not xrd_keep_line_legend,
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
    if file_sha256(template_path) != template_sha256:
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
    if product.product_key in {"Raman", "photocurrent", "Mott-Schottky", "UV-vis DRS", "Tauc"} and (
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
    # EPR starts from raw data and intentionally overwrites processed_data only
    # after its approved Origin transform.  All later validation must therefore
    # read the transformed CSV rather than retain the pre-transform rows.
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
        product.product_key in {"Raman", "Mott-Schottky", "UV-vis DRS", "Tauc"}
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
        "xps_component_fill": {"required": False, "applied": False},
    }


def _prepare_verified_otpu_binding(
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    *,
    contract_path: str | Path | None = None,
) -> dict[str, object]:
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
    }
    prepare = preparers.get(product.product_key)
    if prepare is None:
        return {
            "ok": False,
            "message": (
                f"Verified OTPU runtime dispatch is not implemented for {product.product_key}."
            ),
        }
    return prepare(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )


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
    return None if product_key in {"EIS", "Raman", "Mott-Schottky"} else style.line_width_pt


def _verified_otpu_axis_title_bold_policy(
    product_key: str,
    reference_style: dict[str, object],
) -> bool:
    if product_key in {"photocurrent", "FTIR"}:
        return _style_snapshot_axis_title_bold_required(reference_style)
    return True


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
        paired_states: list[bool] = []
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
            paired_states.append(x_value is not None)
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
        if any(paired_states[row_to:]):
            return {
                "ok": False,
                "message": (
                    f"Photocurrent source pair {pair_index + 1} contains finite data "
                    "after its blank tail begins."
                ),
            }
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
        paired_states: list[bool] = []
        for row in rows:
            x_value = _finite_numeric_value(row[source_x])
            y_value = _finite_numeric_value(row[source_y])
            if (x_value is None) != (y_value is None):
                return {
                    "ok": False,
                    "message": f"FTIR source pair {pair_index} contains an unpaired X or Y value.",
                }
            paired_states.append(x_value is not None)
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
        if any(paired_states[row_to:]):
            return {
                "ok": False,
                "message": f"FTIR source pair {pair_index} contains data after its blank tail begins.",
            }
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


def _populate_verified_otpu_workbook(
    operations: object,
    product: ProductContext,
    headers: list[str],
    rows: list[list[object]],
    binding: dict[str, object],
) -> dict[str, object]:
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
    rows = [
        f"\\l({index})\\b({_reviewed_template_legend_rich_text(labels[index - 1])})"
        for index in visible_indices
    ]
    text = "\r\n".join(rows)
    written = _set_origin_graph_object_text(operations, graph_name, "Legend", text)
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
            strings = reference_style.get("audit_string_values")
            strings = strings if isinstance(strings, dict) else {}
            legend_text = str(strings.get("legend.text$") or "")
            legend_restored = bool(legend_text) and _set_origin_graph_object_text(
                operations,
                graph_name,
                "Legend",
                legend_text,
            )
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


def _paired_numeric_row_bounds(
    rows: list[list[object]],
    x_index: int,
    y_index: int,
) -> tuple[int, int] | None:
    valid_rows = [
        row_index
        for row_index, row in enumerate(rows, start=1)
        if x_index < len(row)
        and y_index < len(row)
        and _finite_numeric_value(row[x_index]) is not None
        and _finite_numeric_value(row[y_index]) is not None
    ]
    if not valid_rows:
        return None
    if valid_rows != list(range(valid_rows[0], valid_rows[-1] + 1)):
        return None
    return min(valid_rows), max(valid_rows)


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


def _finite_numeric_value(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_verified_current_data(
    product_key: str,
    rows: list[list[object]],
    xy_ranges: list[dict[str, object]],
    graph_snapshot: dict[str, object],
) -> dict[str, object]:
    plots = [
        dict(plot)
        for plot in graph_snapshot.get("plots", [])
        if isinstance(plot, dict)
    ]
    reasons: list[str] = []
    if str(graph_snapshot.get("status") or "") != "ready":
        reasons.append("reopened graph data snapshot is not ready")
    if len(plots) != len(xy_ranges):
        reasons.append(
            f"reopened graph has {len(plots)} plots; expected {len(xy_ranges)}"
        )
    for index, expected in enumerate(xy_ranges):
        if index >= len(plots):
            break
        plot = plots[index]
        source_x_index = int(expected.get("source_x_index", expected["x_col"] - 1))
        source_y_index = int(expected.get("source_y_index", expected["y_col"] - 1))
        source_row_from = int(expected.get("source_row_from", expected["row_from"]))
        source_row_to = int(expected.get("source_row_to", expected["row_to"]))
        expected_x_raw = [
            _finite_numeric_value(rows[row_index - 1][source_x_index])
            for row_index in range(source_row_from, source_row_to + 1)
        ]
        expected_y_raw = [
            _finite_numeric_value(rows[row_index - 1][source_y_index])
            for row_index in range(source_row_from, source_row_to + 1)
        ]
        actual_x_raw = [
            _finite_numeric_value(value)
            for value in list(plot.get("x_values") or [])
        ]
        actual_y_raw = [
            _finite_numeric_value(value)
            for value in list(plot.get("y_values") or [])
        ]
        if any(value is None for value in expected_x_raw + expected_y_raw):
            reasons.append(f"plot {index + 1} expected CSV range contains a nonfinite X/Y value")
            continue
        if any(value is None for value in actual_x_raw + actual_y_raw):
            reasons.append(f"plot {index + 1} reopened X/Y range contains a nonfinite value")
            continue
        expected_x = [float(value) for value in expected_x_raw if value is not None]
        expected_y = [float(value) for value in expected_y_raw if value is not None]
        actual_x = [float(value) for value in actual_x_raw if value is not None]
        actual_y = [float(value) for value in actual_y_raw if value is not None]
        if actual_x != expected_x:
            reasons.append(f"plot {index + 1} X values differ from processed CSV")
        if actual_y != expected_y:
            reasons.append(f"plot {index + 1} Y values differ from processed CSV")
        if (
            int(plot.get("plot_row_from") or 0) != expected["row_from"]
            or int(plot.get("plot_row_to") or 0) != expected["row_to"]
        ):
            reasons.append(f"plot {index + 1} displayed row range differs")
        expected_x_letter = str(expected.get("expected_x_col_letter") or "")
        expected_y_letter = str(expected.get("expected_y_col_letter") or "")
        if expected_x_letter and str(plot.get("x_col_letter") or "").upper() != expected_x_letter:
            reasons.append(f"plot {index + 1} X dataset column differs")
        if expected_y_letter and str(plot.get("y_col_letter") or "").upper() != expected_y_letter:
            reasons.append(f"plot {index + 1} Y dataset column differs")
        if expected_x_letter and str(plot.get("x_mapping_source") or "") != "graph_plot_mapping":
            reasons.append(f"plot {index + 1} lacks explicit graph X mapping readback")
        if "expected_y_masked_rows" in expected:
            expected_masked_rows = [
                int(value) for value in list(expected.get("expected_y_masked_rows") or [])
            ]
            actual_masked_rows = [
                int(value) for value in list(plot.get("y_masked_rows") or [])
            ]
            if str(plot.get("mask_readback_status") or "") != "ready":
                reasons.append(f"plot {index + 1} lacks native mask-state readback")
            elif actual_masked_rows != expected_masked_rows:
                reasons.append(f"plot {index + 1} Y masked rows differ")
    return {
        "ok": not reasons,
        "status": "matched" if not reasons else "mismatch",
        "message": (
            f"Reopened {product_key} graph contains the exact processed CSV X/Y values "
            "and displayed row ranges."
            if not reasons
            else "; ".join(reasons)
        ),
        "expected_plot_count": len(xy_ranges),
        "actual_plot_count": len(plots),
        "reasons": reasons,
    }


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
        mismatches = [
            field
            for field in style_fields
            if reference_style.get(field) != current_style.get(field)
        ]
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


def _validate_verified_bet_current_data(
    rows: list[list[object]],
    xy_ranges: list[dict[str, int]],
    graph_snapshot: dict[str, object],
) -> dict[str, object]:
    return _validate_verified_current_data("BET", rows, xy_ranges, graph_snapshot)


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

        operations.new_project()
        imported = operations.import_csv_to_worksheet(product.processed_data, book_name=f"{product.slug}_data")
        if not getattr(imported, "ok", False):
            return {"ok": False, "message": getattr(imported, "message", "CSV import failed"), "template_format_plan": plan.to_dict()}
        book_name = str(imported.payload["book_name"])
        graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
        plot_pairs = _processed_csv_plot_pairs(product, headers)
        if not plot_pairs:
            return {"ok": False, "message": "processed CSV does not contain plottable column pairs", "template_format_plan": plan.to_dict()}
        selected_oth_json = str(
            (style_execution_decision or {}).get("selected_mode") or ""
        ) == "oth-json"
        adaptive_plot_bounds: dict[tuple[int, int], tuple[int, int]] = {}
        if selected_oth_json and product.product_key in {
            "Raman",
            "UV-vis DRS",
            "Tauc",
        }:
            for x_col, y_col in plot_pairs:
                bounds = _paired_numeric_row_bounds(rows, x_col - 1, y_col - 1)
                if bounds is None or bounds[0] != 1:
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
        first_header = headers[plot_pairs[0][1] - 1] if plot_pairs[0][1] - 1 < len(headers) else ""
        first_bounds = adaptive_plot_bounds.get(plot_pairs[0], (0, 0))
        first_row_kwargs = (
            {"row_from": first_bounds[0], "row_to": first_bounds[1]}
            if first_bounds[0] > 0
            else {}
        )
        created = operations.create_graph(
            graph_name,
            book_name,
            "Sheet1",
            plot_pairs[0][0],
            plot_pairs[0][1],
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
        for x_col, y_col in plot_pairs[1:]:
            header = headers[y_col - 1] if y_col - 1 < len(headers) else ""
            row_bounds = adaptive_plot_bounds.get((x_col, y_col), (0, 0))
            row_kwargs = (
                {"row_from": row_bounds[0], "row_to": row_bounds[1]}
                if row_bounds[0] > 0
                else {}
            )
            added = operations.add_plot_to_graph(
                graph_name,
                book_name,
                "Sheet1",
                x_col,
                y_col,
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
            if product.product_key in {"photocurrent", "UV-vis DRS", "Tauc"}
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
        adaptive_snapshot_style_applied = bool(
            selected_oth_json
            and saved_style_snapshot
            and apply_style_snapshot(
                operations,
                graph_name,
                saved_style_snapshot,
                apply_default_font=False,
                apply_axis_titles=True,
                preserve_custom_rgb=product.product_key == "Mott-Schottky",
            )
        )
        plot_sequence = _apply_external_reference_plot_sequence(
            operations,
            graph_name,
            saved_style_snapshot
            or (external_reference_preview.get("style_snapshot") if isinstance(external_reference_preview, dict) else {}),
            product=product,
        )
        adaptive_plot_style_policy = (
            _apply_adaptive_oth_json_plot_styles(
                operations,
                graph_name,
                saved_data_snapshot,
                cycle_styles=adaptive_cardinality or adaptive_uvvis,
                preserve_custom_rgb=product.product_key == "Mott-Schottky",
                product_key=product.product_key,
            )
            if selected_oth_json
            else {"applied": False, "reason": "not_oth_json_mode"}
        )
        reviewed_plot_policy = (
            {"applied": False, "reason": "adaptive_route_uses_all_current_plots"}
            if adaptive_cardinality or adaptive_uvvis
            else _apply_reviewed_template_plot_policy(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                style,
                data_snapshot=saved_data_snapshot,
            )
        )
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
        if product.product_key == "FTIR" and selected_oth_json:
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
            if selected_oth_json and product.product_key in {"BET", "FTIR", "photocurrent", "UV-vis DRS", "Tauc"}
            else {"applied": False, "reason": "adaptive_cardinality_uses_dynamic_current_legend"}
            if adaptive_cardinality or adaptive_uvvis
            else _finalize_reviewed_template_legend(
                operations,
                graph_name,
                product,
                saved_style_snapshot,
                style,
            )
        )
        render_refresh = _refresh_graph_for_export(operations, graph_name)
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
                prefer_custom_rgb=product.product_key == "Mott-Schottky",
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
            "Raman",
            "photocurrent",
            "Mott-Schottky",
            "UV-vis DRS",
            "Tauc",
        }:
            current_data_snapshot = read_graph_data_snapshot(
                operations,
                reopened_graph,
                source_label=product.origin_file.name,
            )
            validation_ranges = _adaptive_photocurrent_validation_ranges(
                rows,
                plot_pairs,
                mask_negative_x=product.product_key == "Mott-Schottky",
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
            _adaptive_raman_conformance_reference(
                reference_style_snapshot,
                saved_data_snapshot,
                len(plot_pairs),
            )
            if selected_oth_json and product.product_key == "Raman"
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
        if str(conformance.get("status") or "").casefold() == "fail":
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
        "UV-vis DRS",
        "Tauc",
    }
    if requires_all_current_plots_visible and not all_current_plots_visible:
        failures.append(
            "not every current CSV curve is visible after adaptive save/reopen"
        )
    if not relaxed and str(conformance.get("status") or "").casefold() == "fail":
        failures.append("fixed-cardinality OTH+JSON style conformance failed")
    requires_current_data_match = product.product_key in {
        "BET",
        "Raman",
        "photocurrent",
        "Mott-Schottky",
        "UV-vis DRS",
        "Tauc",
    }
    current_data_match = bool(
        isinstance(current_data_validation, dict)
        and current_data_validation.get("ok") is True
        and current_data_validation.get("status") == "matched"
    )
    if requires_current_data_match and not current_data_match:
        failures.append("reopened graph X/Y values do not match the current processed CSV")
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
    }


def _adaptive_photocurrent_validation_ranges(
    rows: list[list[object]],
    plot_pairs: list[tuple[int, int]],
    *,
    mask_negative_x: bool = False,
) -> list[dict[str, object]]:
    series = _photocurrent_xy_series(rows, plot_pairs)
    if len(series) != len(plot_pairs):
        return []
    ranges: list[dict[str, object]] = []
    for (x_column, y_column), (x_values, _y_values) in zip(plot_pairs, series):
        record: dict[str, int | list[int]] = {
            "x_col": x_column,
            "y_col": y_column,
            "row_from": 1,
            "row_to": len(x_values),
            "source_x_index": x_column - 1,
            "source_y_index": y_column - 1,
            "source_row_from": 1,
            "source_row_to": len(x_values),
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
    if not source.is_file():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
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
    legend_rows = [
        f"\\l({plot_index})\\b({_reviewed_template_legend_rich_text(label)})"
        for plot_index, label in zip(visible_indices, entries)
    ]
    legend_text = "%(CRLF)".join(legend_rows)
    legend_font_size = _reviewed_template_legend_font_size(snapshot, style)
    operations.run_labtalk(
        f'win -a "{graph}"; legend.show=1; legend.text$="{_quote_origin_rich_text(legend_text)}"; '
        f'legend.font$="{quote_labtalk(style.font_family or "Arial")}"; '
        f"legend.fsize={legend_font_size}; legend.bold=1; "
        "legend.background=0; legend.border=0; legend.fill=0;"
    )
    legend_com_text_refreshed = _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        "\r\n".join(legend_rows),
    )
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
        "applied": True,
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
    rows = [
        f"\\l({plot_index})\\b({_reviewed_template_legend_rich_text(label)})"
        for plot_index, label in zip(visible_indices, entries)
    ]
    return _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        "\r\n".join(rows),
    )


def _replace_eis_dynamic_legend_with_static_rich_text(
    operations: object,
    graph_name: str,
    product: ProductContext,
    snapshot: dict[str, object],
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    if product.product_key != "EIS":
        return {"applied": False, "reason": "not_required_for_product"}
    visible_indices = REVIEWED_TEMPLATE_VISIBLE_PLOTS["EIS"]
    entries = _plain_text_legend_entries(product)
    if len(entries) != len(visible_indices):
        return {"applied": False, "reason": "legend_entry_count_mismatch"}
    app = getattr(operations, "app", None)
    if app is None:
        return {"applied": False, "reason": "no_origin_app"}
    try:
        layer = app.FindGraphLayer(f"[{graph_name}]Layer1") or app.FindGraphLayer(f"[{graph_name}]1") or app.FindGraphLayer(graph_name)
    except Exception:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    if not layer:
        return {"applied": False, "reason": "graph_layer_unavailable"}
    dynamic_legend = _find_origin_graph_object(layer, "Legend")
    if dynamic_legend is None:
        return {"applied": False, "reason": "dynamic_legend_unavailable"}
    try:
        left = int(dynamic_legend.Left)
        top = int(dynamic_legend.Top)
        dynamic_legend.Show = 0
        dynamic_legend.SetNumProp("show", 0)
    except Exception:
        return {"applied": False, "reason": "dynamic_legend_hide_failed"}

    object_name = "rdop_reviewed_legend"
    graph = quote_labtalk(graph_name)
    operations.run_labtalk(f'win -a "{graph}"; label -r {object_name};')
    created = operations.run_labtalk(f'win -a "{graph}"; label -n {object_name} "x";')
    static_legend = _find_origin_graph_object(layer, object_name)
    if static_legend is None:
        return {
            "applied": False,
            "reason": "static_legend_creation_failed",
            "labtalk_created": bool(getattr(created, "ok", False)),
        }
    rows = [
        f"\\l({plot_index})\\b({_reviewed_template_legend_rich_text(label)})"
        for plot_index, label in zip(visible_indices, entries)
    ]
    font_size = _reviewed_template_legend_font_size(snapshot, style)
    try:
        static_legend.Text = "\r\n".join(rows)
        static_legend.Left = left
        static_legend.Top = top
    except Exception:
        return {"applied": False, "reason": "static_legend_text_or_position_failed"}
    font_code = _origin_font_code(app, style.font_family or "Arial")
    for prop, value in (
        ("font", font_code),
        ("fsize", font_size),
        ("bold", 1),
        ("color", 1),
        ("background", 0),
        ("border", 0),
        ("frame", 0),
        ("fill", 0),
        ("show", 1),
    ):
        try:
            static_legend.SetNumProp(prop, value)
        except Exception:
            pass
    return {
        "applied": str(getattr(static_legend, "Text", "") or "") == "\r\n".join(rows),
        "method": "static_rich_text_legend_with_template_line_samples",
        "dynamic_legend_hidden": True,
        "object_name": object_name,
        "entries": entries,
        "visible_plot_indices": list(visible_indices),
        "font_size": font_size,
        "left": left,
        "top": top,
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
        return _replace_eis_dynamic_legend_with_static_rich_text(
            operations,
            graph_name,
            product,
            snapshot,
            style,
        )
    if product.product_key in REVIEWED_TEMPLATE_VISIBLE_PLOTS:
        return {
            "applied": _refresh_reviewed_template_legend_com_text(operations, graph_name, product),
            "method": "dynamic_legend_com_text_refresh",
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
            commands.append(f"set {plot_name} {option} {_origin_number(rendered)};")
            restored[field] = rendered
        color = _finite_float(plot_style.get("color"))
        if color is not None:
            if preserve_custom_rgb:
                color_option, color_value = _origin_plot_color_for_labtalk(color)
            else:
                color_option, color_value = "-c", str(int(round(color)))
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
    return _apply_reviewed_template_plot_styles(
        operations,
        graph_name,
        snapshot,
        cycle_styles=cycle_styles,
        preserve_custom_rgb=preserve_custom_rgb,
    )


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
    rows = [
        f"\\l({index})\\b({_reviewed_template_legend_rich_text(label)})"
        for index, label in enumerate(entries, start=1)
    ]
    text = "\r\n".join(rows)
    written = bool(rows) and _set_origin_graph_object_text(
        operations, graph_name, "Legend", text
    )
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
    rows = [
        f"\\l({index})\\b( {_reviewed_template_legend_rich_text(label)})"
        for index, label in enumerate(entries, start=1)
    ]
    text = "\r\n".join(rows)
    legend_written = bool(rows) and _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        text,
    )
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
        "rich_text": text,
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
    reviewed_legend_bodies = {
        "BiOBr0.5Cl0.5": r"\b(\i( )\c1(BiOBr)\-(\c1(0.5))\c1(Cl)\-(\c1(0.5)))",
        "CuWO4": r"\b(\i( )CuWO\-(4))",
        "BiCu-10": r"\b(\i( )BiCu-10)",
    }
    legend_bodies = [
        reviewed_legend_bodies.get(
            label,
            "\\b(" + _reviewed_template_legend_rich_text(label) + ")",
        )
        for label in entries
    ]
    rows = [
        f"\\l({index}){body}"
        for index, body in enumerate(legend_bodies, start=1)
    ]
    text = "\r\n".join(rows)
    written = bool(rows) and _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        text,
    )
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
        "rich_text": text,
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
    rows = [
        f"\\l({index})\\b( {_reviewed_template_legend_rich_text(label)})"
        for index, label in enumerate(entries, start=1)
    ]
    text = "\r\n".join(rows)
    written = bool(rows) and _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        text,
    )
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
        "rich_text": text,
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


def _mott_schottky_candidate_guides(
    headers: list[str],
    rows: list[list[object]],
    *,
    series_count: int,
) -> dict[str, object]:
    if series_count < 1 or len(headers) < series_count + 1:
        return {}
    numeric: list[tuple[float, list[float]]] = []
    for row in rows:
        if len(row) < series_count + 1:
            continue
        x_value = _finite_float(row[0])
        y_values = [_finite_float(value) for value in row[1 : series_count + 1]]
        if x_value is None or any(value is None for value in y_values):
            continue
        numeric.append((x_value, [float(value) for value in y_values if value is not None]))
    numeric.sort(key=lambda item: item[0])
    if len(numeric) < 5 or any(numeric[index][0] >= numeric[index + 1][0] for index in range(len(numeric) - 1)):
        return {}

    x_values = [item[0] for item in numeric]
    series = [[item[1][series_index] for item in numeric] for series_index in range(series_count)]
    rising_end = min(max(range(len(values)), key=values.__getitem__) for values in series)
    window_size = 3
    if rising_end + 1 < window_size:
        return {}

    candidates: list[tuple[tuple[float, float], int, list[dict[str, float]]]] = []
    for start in range(0, rising_end - window_size + 2):
        stop = start + window_size
        x_window = x_values[start:stop]
        fits = [_linear_fit(x_window, values[start:stop]) for values in series]
        if any(not fit or float(fit["slope"]) <= 0 for fit in fits):
            continue
        minimum_r_squared = min(float(fit["r_squared"]) for fit in fits)
        mean_r_squared = sum(float(fit["r_squared"]) for fit in fits) / len(fits)
        candidates.append(((minimum_r_squared, mean_r_squared), start, fits))
    if not candidates:
        return {}
    _score, start, independent_fits = max(candidates, key=lambda item: item[0])
    stop = start + window_size
    x_window = x_values[start:stop]
    y_windows = [values[start:stop] for values in series]
    shared = _shared_x_intercept_fit(x_window, y_windows, full_x_span=x_values[-1] - x_values[0])
    if not shared or min(float(value) for value in shared.get("r_squared", [])) < 0.98:
        return {}

    next_index = stop if stop <= rising_end else stop - 1
    guide_x_end = x_values[next_index]
    return {
        "series_headers": headers[1 : series_count + 1],
        "linear_interval_candidate": [x_window[0], x_window[-1]],
        "linear_fit_point_count": window_size,
        "independent_linear_fits": independent_fits,
        "shared_x_intercept_candidate": shared["x_intercept"],
        "constrained_slopes": shared["slopes"],
        "constrained_r_squared": shared["r_squared"],
        "guide_x_end": guide_x_end,
        "data_x_span": x_values[-1] - x_values[0],
        "visible_y_max": max(max(values) for values in series),
    }


def _linear_fit(x_values: list[float], y_values: list[float]) -> dict[str, float]:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return {}
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    denominator = sum((value - mean_x) ** 2 for value in x_values)
    if denominator <= 0:
        return {}
    slope = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(x_values, y_values)) / denominator
    intercept = mean_y - slope * mean_x
    total = sum((value - mean_y) ** 2 for value in y_values)
    residual = sum((y_value - (slope * x_value + intercept)) ** 2 for x_value, y_value in zip(x_values, y_values))
    r_squared = 1.0 if total <= 0 else 1.0 - residual / total
    return {"slope": slope, "intercept": intercept, "r_squared": r_squared}


def _shared_x_intercept_fit(
    x_values: list[float],
    y_series: list[list[float]],
    *,
    full_x_span: float,
) -> dict[str, object]:
    if len(x_values) < 3 or full_x_span <= 0 or any(len(values) != len(x_values) for values in y_series):
        return {}
    upper = x_values[0] - max(full_x_span * 1e-6, abs(x_values[-1] - x_values[0]) * 0.01)
    lower = x_values[0] - 5.0 * full_x_span
    grid_count = 4000
    step = (upper - lower) / grid_count

    def evaluate(x_intercept: float) -> tuple[float, list[float], list[float]]:
        offsets = [x_value - x_intercept for x_value in x_values]
        denominator = sum(value * value for value in offsets)
        if denominator <= 0:
            return math.inf, [], []
        slopes: list[float] = []
        r_squared_values: list[float] = []
        objective = 0.0
        for values in y_series:
            slope = sum(offset * y_value for offset, y_value in zip(offsets, values)) / denominator
            if slope <= 0:
                return math.inf, [], []
            residual = sum((y_value - slope * offset) ** 2 for offset, y_value in zip(offsets, values))
            mean_y = sum(values) / len(values)
            total = sum((y_value - mean_y) ** 2 for y_value in values)
            if total <= 0:
                return math.inf, [], []
            objective += residual / total
            slopes.append(slope)
            r_squared_values.append(1.0 - residual / total)
        return objective, slopes, r_squared_values

    best_index = -1
    best: tuple[float, list[float], list[float]] = (math.inf, [], [])
    for index in range(grid_count + 1):
        candidate = evaluate(lower + index * step)
        if candidate[0] < best[0]:
            best = candidate
            best_index = index
    if best_index <= 0 or best_index >= grid_count:
        return {}

    left = lower + (best_index - 1) * step
    right = lower + (best_index + 1) * step
    for _ in range(50):
        first = left + (right - left) / 3.0
        second = right - (right - left) / 3.0
        if evaluate(first)[0] <= evaluate(second)[0]:
            right = second
        else:
            left = first
    x_intercept = (left + right) / 2.0
    objective, slopes, r_squared_values = evaluate(x_intercept)
    if not math.isfinite(objective) or not slopes:
        return {}
    return {
        "x_intercept": x_intercept,
        "slopes": slopes,
        "r_squared": r_squared_values,
        "normalized_residual_objective": objective,
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


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


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
        anchor_policy = _apply_nonoverlap_plain_legend_anchor(operations, graph_name, product, entries)
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
    _replace_legend_with_plain_text_labels(
        operations,
        graph_name,
        entries,
        style,
    )
    return _plain_text_legend_policy(product, entries=entries, anchor_policy=anchor_policy, line_samples_removed=True)


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
    records = [
        (index, str(header).strip())
        for index, header in enumerate(headers[1:], start=1)
        if str(header).strip()
    ]
    if product.product_key != "XRD" or not any(
        is_template_xrd_reference_stick_header(header) for _index, header in records
    ):
        return records
    sample_records = [
        (index, header)
        for index, header in records
        if not is_template_xrd_reference_stick_header(header)
    ]
    card_records = [
        (index, header)
        for index, header in records
        if is_template_xrd_reference_stick_header(header)
    ]
    return sample_records[:XRD_STANDARD_CARD_SAMPLE_LIMIT] + card_records[:1]


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



def _padded_axis_bounds(min_value: float, max_value: float, *, zero_floor: bool = False) -> tuple[float, float]:
    if max_value <= min_value:
        span = max(abs(max_value), abs(min_value), 1.0)
    else:
        span = max_value - min_value
    pad = max(span * 0.08, 1e-9)
    lower = min_value - pad
    upper = max_value + pad
    if zero_floor and min_value >= 0:
        lower = 0.0
    return lower, upper


def _photocurrent_xy_series(
    rows: list[list[object]],
    pairs: list[tuple[int, int]],
) -> list[tuple[list[float], list[float]]]:
    """Return strict contiguous finite X/Y runs for each processed photocurrent pair."""
    series: list[tuple[list[float], list[float]]] = []
    for x_column, y_column in pairs:
        x_index = x_column - 1
        y_index = y_column - 1
        x_values: list[float] = []
        y_values: list[float] = []
        finite_run_ended = False
        for row in rows:
            x_value = _finite_numeric_value(row[x_index]) if x_index < len(row) else None
            y_value = _finite_numeric_value(row[y_index]) if y_index < len(row) else None
            if x_value is None and y_value is None:
                if x_values:
                    finite_run_ended = True
                continue
            if x_value is None or y_value is None or finite_run_ended:
                return []
            x_values.append(float(x_value))
            y_values.append(float(y_value))
        if not x_values or len(x_values) != len(y_values):
            return []
        series.append((x_values, y_values))
    return series


def _photocurrent_reference_xy_series(
    snapshot: dict[str, object] | None,
) -> list[tuple[list[float], list[float]]]:
    if not isinstance(snapshot, dict):
        return []
    plots = snapshot.get("plots")
    if not isinstance(plots, list) or not plots:
        return []
    series: list[tuple[list[float], list[float]]] = []
    for plot in plots:
        if not isinstance(plot, dict):
            return []
        raw_x = plot.get("x_values")
        raw_y = plot.get("y_values")
        if not isinstance(raw_x, list) or not isinstance(raw_y, list) or len(raw_x) != len(raw_y):
            return []
        x_values: list[float] = []
        y_values: list[float] = []
        finite_run_ended = False
        for raw_x_value, raw_y_value in zip(raw_x, raw_y):
            x_value = _finite_numeric_value(raw_x_value)
            y_value = _finite_numeric_value(raw_y_value)
            if x_value is None and y_value is None:
                if x_values:
                    finite_run_ended = True
                continue
            if x_value is None or y_value is None or finite_run_ended:
                return []
            x_values.append(float(x_value))
            y_values.append(float(y_value))
        if not x_values:
            return []
        series.append((x_values, y_values))
    return series


def _photocurrent_axis_series_match(
    current: list[tuple[list[float], list[float]]],
    reference: list[tuple[list[float], list[float]]],
    *,
    axis: str,
) -> bool:
    if axis not in {"x", "y"} or len(current) != len(reference):
        return False
    axis_index = 0 if axis == "x" else 1
    reference_values = [value for series in reference for value in series[axis_index]]
    if not reference_values:
        return False
    reference_span = max(reference_values) - min(reference_values)
    absolute_tolerance = max(abs(reference_span) * 1e-12, 1e-15)
    for current_series, reference_series in zip(current, reference):
        current_values = current_series[axis_index]
        expected_values = reference_series[axis_index]
        if len(current_values) != len(expected_values):
            return False
        if any(
            not math.isclose(
                actual,
                expected,
                rel_tol=1e-9,
                abs_tol=absolute_tolerance,
            )
            for actual, expected in zip(current_values, expected_values)
        ):
            return False
    return True


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


def _apply_nonoverlap_plain_legend_anchor(
    operations: object,
    graph_name: str,
    product: ProductContext,
    entries: list[str],
) -> dict[str, object]:
    if product.product_key == "EIS" or not entries:
        if hasattr(operations, "run_labtalk"):
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; legend.show=0;')
        return {"applied": False, "visible": False, "reason": "legend_hidden_or_empty"}
    if not hasattr(operations, "run_labtalk"):
        return {"applied": False, "visible": True, "reason": "run_labtalk_unavailable"}
    try:
        headers, rows = _read_processed_csv(product.processed_data)
        points = _normalized_plot_points(product, headers, rows)
    except Exception as exc:
        points = []
        error = str(exc)
    else:
        error = ""
    anchor = _select_plain_legend_anchor(entries, points)
    operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        "legend -r; legend.show=1; "
        f"legend.x = layer.x.from + {anchor['x_fraction']:.6g} * (layer.x.to - layer.x.from); "
        f"legend.y = layer.y.from + {anchor['y_fraction']:.6g} * (layer.y.to - layer.y.from);"
    )
    return {
        "applied": True,
        "visible": True,
        "method": "data_sparse_corner_anchor_before_plain_text_replacement",
        "corner": anchor["corner"],
        "x_fraction": anchor["x_fraction"],
        "y_fraction": anchor["y_fraction"],
        "occupancy_score": anchor["score"],
        "point_count": len(points),
        "error": error,
    }


def _normalized_plot_points(product: ProductContext, headers: list[str], rows: list[list[object]]) -> list[tuple[float, float]]:
    pairs = _processed_csv_plot_pairs(product, headers)
    raw_points: list[tuple[float, float]] = []
    for x_col, y_col in pairs:
        x_index = x_col - 1
        y_index = y_col - 1
        for row in rows:
            if x_index >= len(row) or y_index >= len(row):
                continue
            try:
                x_value = float(row[x_index])
                y_value = float(row[y_index])
            except (TypeError, ValueError):
                continue
            if math.isfinite(x_value) and math.isfinite(y_value):
                raw_points.append((x_value, y_value))
    if not raw_points:
        return []
    x_values = [point[0] for point in raw_points]
    y_values = [point[1] for point in raw_points]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    x_span = x_max - x_min
    y_span = y_max - y_min
    if x_span <= 0 or y_span <= 0:
        return []
    return [((x - x_min) / x_span, (y - y_min) / y_span) for x, y in raw_points]


def _select_plain_legend_anchor(entries: list[str], points: list[tuple[float, float]]) -> dict[str, object]:
    longest = max((len(str(entry)) for entry in entries), default=8)
    box_width = min(0.38, max(0.18, longest * 0.018))
    box_height = min(0.34, max(0.10, len(entries) * 0.075))
    candidates = [
        ("top-right", 0.60, 0.88),
        ("top-left", 0.07, 0.88),
        ("bottom-right", 0.60, 0.25),
        ("bottom-left", 0.07, 0.25),
    ]
    scored: list[tuple[float, str, float, float]] = []
    for corner, x_fraction, y_fraction in candidates:
        x0 = x_fraction
        x1 = min(1.0, x_fraction + box_width)
        y1 = y_fraction
        y0 = max(0.0, y_fraction - box_height)
        expanded_x0 = max(0.0, x0 - 0.035)
        expanded_x1 = min(1.0, x1 + 0.035)
        expanded_y0 = max(0.0, y0 - 0.035)
        expanded_y1 = min(1.0, y1 + 0.035)
        overlap = sum(1 for x, y in points if expanded_x0 <= x <= expanded_x1 and expanded_y0 <= y <= expanded_y1)
        distance_penalty = 0.0
        if points:
            nearest = min(
                _distance_to_box(x, y, expanded_x0, expanded_x1, expanded_y0, expanded_y1)
                for x, y in points
            )
            distance_penalty = max(0.0, 0.12 - nearest)
        bottom_penalty = 100.0 if corner.startswith("bottom") else 0.0
        score = overlap + distance_penalty + bottom_penalty
        scored.append((score, corner, x_fraction, y_fraction))
    score, corner, x_fraction, y_fraction = min(scored, key=lambda item: (item[0], 0 if item[1] == "top-right" else 1))
    return {"corner": corner, "x_fraction": x_fraction, "y_fraction": y_fraction, "score": score}


def _distance_to_box(x: float, y: float, x0: float, x1: float, y0: float, y1: float) -> float:
    dx = 0.0 if x0 <= x <= x1 else min(abs(x - x0), abs(x - x1))
    dy = 0.0 if y0 <= y <= y1 else min(abs(y - y0), abs(y - y1))
    return math.sqrt(dx * dx + dy * dy)


def _replace_legend_with_plain_text_labels(
    operations: object,
    graph_name: str,
    entries: list[str],
    style: ResolvedPlotStyle,
    *,
    prefer_existing_text: bool = False,
) -> None:
    replace_legend = getattr(operations, "replace_legend_with_plain_text_labels", None)
    if not callable(replace_legend):
        raise RuntimeError("Origin operation replace_legend_with_plain_text_labels is unavailable.")
    result = replace_legend(
        graph_name,
        entries,
        font_name=style.font_family,
        font_size=int(style.legend_font_size),
        prefer_existing_text=prefer_existing_text,
    )
    if not getattr(result, "ok", False):
        raise RuntimeError(getattr(result, "message", "plain-text legend replacement failed"))


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
    legend_entries = [f"\\l({index}){label}" for index, label in enumerate(labels, start=1)]
    max_label_len = max((_plain_label_for_length(label) for label in labels), key=len, default="")
    legend_x = max(58.0, 66.0 - max(0, len(max_label_len) - 8) * 1.2)
    legend_y = _xrd_standard_card_legend_y(product)
    legend_rows = _xrd_standard_card_legend_rows(legend_entries)
    legend_text = "%(CRLF)".join(legend_rows)
    commands = [
        f'win -a "{graph}"; legend.show=1;',
        f'legend.text$="{_quote_origin_rich_text(legend_text)}";',
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
    for plot_index in reference_plot_indices:
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
        "applied": bool(legend_com_applied and (not card_label or card_label_applied)),
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


def _xrd_standard_card_legend_rows(entries: list[str]) -> list[str]:
    return list(entries)


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
        len(labels) != 3
        or any(not label for label in labels)
        or len({label.casefold() for label in labels}) != 3
    ):
        return {"applied": False, "reason": "pl_legend_requires_three_nonempty_unique_values"}
    rows = [
        f"\\l({index})\\b( {_reviewed_template_legend_rich_text(label)})"
        for index, label in enumerate(labels, start=1)
    ]
    if not _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        "\r\n".join(rows),
    ):
        return {"applied": False, "reason": "pl_legend_com_text_write_failed"}
    return {
        "applied": True,
        "method": "template_legend_current_bold_rich_text",
        "entries": labels,
        "line_samples_preserved": True,
    }


def _update_verified_raman_label_objects(
    operations: object,
    graph_name: str,
    entries: list[str],
) -> dict[str, object]:
    """Replace Raman's three distributed native label objects in source order."""

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

    top_label = (
        r"\l(1)\b(\c33518175(\c1( BiOBr)\-(\c1(0.5))\c1(Cl)\-(\c1(0.5))))"
        if labels[0] == "BiOBr0.5Cl0.5"
        else f"\\l(1)\\b( {_reviewed_template_legend_rich_text(labels[0])})"
    )
    object_text = {
        "Legend": top_label,
        "Text1": f"\\b(           {_reviewed_template_legend_rich_text(labels[1])})",
        "Text": f"\\l(2)\\b( {_reviewed_template_legend_rich_text(labels[2])})",
    }
    readback: dict[str, str] = {}
    for object_name, text in object_text.items():
        graph_object = _find_unique_origin_graph_object(layer, object_name)
        if graph_object is None:
            return {
                "applied": False,
                "reason": "required_raman_label_missing_or_not_unique",
                "object_name": object_name,
            }
        try:
            graph_object.Text = text
            actual = str(getattr(graph_object, "Text", "") or "")
        except Exception:
            return {
                "applied": False,
                "reason": "raman_label_write_or_readback_failed",
                "object_name": object_name,
            }
        if actual != text:
            return {
                "applied": False,
                "reason": "raman_label_readback_mismatch",
                "object_name": object_name,
                "expected": text,
                "actual": actual,
            }
        readback[object_name] = actual
    return {
        "applied": True,
        "method": "template_distributed_label_objects_current_bold_rich_text",
        "entries": labels,
        "objects": readback,
        "source_order_to_template_objects": {
            "1": "Legend/plot1",
            "2": "Text1/Line1/layer2_plot1",
            "3": "Text/plot2",
        },
        "native_line_samples_preserved": True,
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
    rows = [
        f"\\l({index})\\b( {_reviewed_template_legend_rich_text(label)})"
        for index, label in enumerate(labels, start=1)
    ]
    text = "\r\n".join(rows)
    if not _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        text,
    ):
        return {
            "applied": False,
            "reason": "photocurrent_legend_com_text_write_failed",
        }
    return {
        "applied": True,
        "method": "template_legend_current_bold_rich_text",
        "entries": labels,
        "rich_text": text,
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
    rows = [
        r"\l(1)\b(\i( )\c1(BiOBr)\-(\c1(0.5))\c1(Cl)\-(\c1(0.5)))",
        r"\l(2)\b(\i( )CuWO\-(4))",
        r"\l(3)\b(\i( )BiCu-10)",
    ]
    text = "\r\n".join(rows)
    if not _set_origin_graph_object_text(
        operations,
        graph_name,
        "Legend",
        text,
    ):
        return {"applied": False, "reason": "ftir_legend_com_text_write_failed"}
    return {
        "applied": True,
        "method": "template_legend_exact_reference_rich_text",
        "entries": list(labels),
        "rich_text": text,
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
        # Reassigning the same text is intentional: Origin can retain a stale
        # rendered legend even after the LabTalk text value has changed.
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
            pixel_data = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
            clean.putdata(list(pixel_data))
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
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        rows = [row for row in reader if any(str(cell).strip() for cell in row)]
    if len(rows) < 2:
        raise ValueError(f"processed CSV has no numeric rows: {path.name}")
    headers = [str(cell).strip() for cell in rows[0]]
    data_rows: list[list[object]] = []
    for row in rows[1:]:
        data_rows.append([_coerce_csv_cell(cell) for cell in row])
    return headers, data_rows


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
        "policy": "Template-format products default to an isolated copy of the reviewed pairing-plan OPJU and replace only its mapped worksheet data; detached .oth/.otpu assets remain quarantined unless independently validated.",
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
        "- Default Origin source: a task-local copy of the reviewed OPJU selected by the pairing plan.",
        "- Data rule: only explicitly mapped worksheet columns may be replaced; graph objects and style are not globally rewritten.",
        "- Detached-asset rule: `.oth` and `.otpu` are not runtime fallbacks unless a fresh-project, same-data replay has independently passed.",
        "- Exactness rule: compare only graphs built from identical per-plot X/Y data and mappings; one-to-one replication is not claimed until save/reopen readback, native 600 dpi export, zero decoded-pixel difference, and manual preview all pass.",
        "- Style rule: line width, fonts, axes, layers, plot types, legend geometry, and other graph formatting are compared with the selected exemplar rather than forced to global constants.",
        "",
        f"- Run root: {render_output_path(run_root, project_root=project_root)}",
        f"- Product count: {summary.get('product_count', '')}",
        f"- Accepted/success count: {summary.get('accepted_count', summary.get('success_count', ''))}",
        f"- Blocked count: {summary.get('blocked_count', '')}",
        f"- Failed count: {summary.get('failed_count', '')}",
    ]
    (reports / "template_format_executor_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
