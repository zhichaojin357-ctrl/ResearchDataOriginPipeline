from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import tempfile
import traceback
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.core.template_product_common import ProductContext, _product_output_path
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.template_product_builder import (
    TemplateProductBuilderOptions,
    _csv_bounds_for_columns,
    _strict_style_readback,
    is_template_xrd_reference_stick_header,
    run_template_product_builder_all_types,
    template_plot_type_for_header,
)
from src.origin.conformance import compare_style_snapshots
from src.origin.embedded_template_snapshots import embedded_template_snapshot
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_registry import resolve_origin_style_asset
from src.origin.style_mimic import apply_style_snapshot, extract_style_snapshot, read_graph_style_snapshot
from src.origin.template_format import build_template_dataset_updates, build_template_format_plan
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
    exemplar_driven: bool = False
    compact_output: bool = False
    only_type: str | None = None


def build_template_product_builder_options(options: TemplateFormatExecutorOptions) -> TemplateProductBuilderOptions:
    return TemplateProductBuilderOptions(
        pairing_path=options.pairing_path,
        output_root=options.output_root,
        with_origin=options.with_origin,
        timestamp=options.timestamp,
        f_drive_template_root=options.f_drive_template_root,
        xps_reference_template_root=options.xps_reference_template_root,
        xps_non_in_situ_template_root=options.xps_non_in_situ_template_root,
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
        prefer_project_style_assets=True,
        external_reference_preview_comparison=not options.exemplar_driven,
        exemplar_driven=options.exemplar_driven,
        compact_output=options.compact_output,
        only_type=options.only_type,
    )


def run_template_format_executor(project_root: Path, options: TemplateFormatExecutorOptions) -> dict[str, object]:
    options = _with_default_xps_non_in_situ_template_root(project_root, options)
    result = run_template_product_builder_all_types(
        project_root,
        build_template_product_builder_options(options),
        origin_exporter=lambda product, style: export_template_base_product_with_origin(
            product,
            style,
            project_root=project_root,
            prefer_project_style_asset=True,
            preserve_exemplar_style=options.exemplar_driven,
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


def export_template_base_product_with_origin(
    product: ProductContext,
    style: ResolvedPlotStyle,
    *,
    project_root: Path | None = None,
    prefer_project_style_asset: bool = True,
    preserve_exemplar_style: bool = False,
) -> dict[str, object]:
    operations = None
    try:
        style_asset = resolve_origin_style_asset(project_root, product.product_key) if project_root is not None and prefer_project_style_asset else None
        neutral_root = _neutral_origin_runtime_root()
        with tempfile.TemporaryDirectory(prefix="rdop_origin_", dir=neutral_root, ignore_cleanup_errors=True) as runtime_text:
            runtime = Path(runtime_text)
            project_template_opju = _project_local_template_opju_for_product(product, style_asset)
            reference_source = project_template_opju or product.reference_opju_copy
            runtime_reference = runtime / reference_source.name
            plan_opju: Path | None = None
            if reference_source.suffix.casefold() in {".opju", ".opj"} and reference_source.is_file():
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
                return _export_saved_format_theme_product_with_origin(operations, product, style, plan)
            if plan.mode == "cached_graph_template":
                return _export_cached_style_package_product_with_origin(operations, product, style, plan)
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
            try:
                replacement = apply_template_base_data_replacement(operations, product, graph_name)
            except Exception as exc:
                if _can_use_template_snapshot_fallback(product):
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
                if _can_use_template_snapshot_fallback(product):
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
                        prefer_existing_text=preserve_exemplar_style,
                    )
                    xrd_plain_label_policy = _apply_xrd_template_plain_legend_labels(operations, graph_name, product, legend_entries, style)
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
            product_snapshot = read_graph_style_snapshot(operations, reopened_graph, source_label=product.origin_file.name, graph_pages=graph_pages)
            conformance = compare_style_snapshots(exemplar_snapshot, product_snapshot, required_line_width_pt=style.line_width_pt)
            strict_readback = _strict_style_readback(product_snapshot.to_dict())
            png = operations.export_graph(reopened_graph, runtime_preview_png, "png", dpi=style.export_dpi)
            tif = operations.export_graph(reopened_graph, runtime_tif, "tif", dpi=style.export_dpi)
            operations.export_graph(reopened_graph, runtime_generated_debug, "png", dpi=style.export_dpi)
            metadata_warnings = [
                warning
                for warning in (
                    _strip_raster_metadata(runtime_reference_png, dpi=style.export_dpi),
                    _strip_raster_metadata(runtime_preview_png, dpi=style.export_dpi),
                    _strip_raster_metadata(runtime_tif, dpi=style.export_dpi),
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
            if not getattr(png, "ok", False) or not getattr(tif, "ok", False):
                return {
                    "ok": False,
                    "message": scrub_output_text(f"{getattr(png, 'message', '')}; {getattr(tif, 'message', '')}", output_root=product.type_root.parent),
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
            "origin_processing": {
                "required": True,
                "applied": True,
                "method": "opju_template_base_workbook_replacement",
                "processing_location": "Origin template-base workbook replacement",
                "source_opju_copy": _product_output_path(product.type_root.parent, product.reference_opju_copy),
                "graph_page": reopened_graph,
                "raster_metadata_stripped": not metadata_warnings,
                "metadata_warnings": metadata_warnings,
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
            "xps_component_fill": _template_base_xps_fill_intent(product, replacement),
            "reopened_graph": reopened_graph,
            "line_width_policy_pt": style.line_width_pt,
            "axis_title_bold_policy": style.font_bold,
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": scrub_output_text(str(exc), output_root=product.type_root.parent),
            "traceback": scrub_output_text(traceback.format_exc(), output_root=product.type_root.parent),
        }
    finally:
        if operations is not None:
            operations.close()


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
    headers, _rows = _read_processed_csv(product.processed_data)
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
            x_tick_label_size=style.tick_label_font_size,
            y_tick_label_size=style.tick_label_font_size,
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
    product_snapshot = read_graph_style_snapshot(operations, reopened_graph, source_label=product.origin_file.name, graph_pages=graph_pages)
    conformance = compare_style_snapshots(exemplar_snapshot, product_snapshot, required_line_width_pt=style.line_width_pt)
    strict_readback = _strict_style_readback(product_snapshot.to_dict())
    png = operations.export_graph(reopened_graph, runtime_preview_png, "png", dpi=style.export_dpi)
    tif = operations.export_graph(reopened_graph, runtime_tif, "tif", dpi=style.export_dpi)
    operations.export_graph(reopened_graph, runtime_generated_debug, "png", dpi=style.export_dpi)
    if not runtime_reference_png.exists() and runtime_preview_png.exists():
        runtime_reference_png.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_preview_png, runtime_reference_png)
    if not runtime_template_debug.exists() and runtime_reference_png.exists():
        runtime_template_debug.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_reference_png, runtime_template_debug)
    metadata_warnings = [
        warning
        for warning in (
            _strip_raster_metadata(runtime_reference_png, dpi=style.export_dpi),
            _strip_raster_metadata(runtime_preview_png, dpi=style.export_dpi),
            _strip_raster_metadata(runtime_tif, dpi=style.export_dpi),
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
    if not getattr(png, "ok", False) or not getattr(tif, "ok", False):
        return {
            "ok": False,
            "message": scrub_output_text(f"{getattr(png, 'message', '')}; {getattr(tif, 'message', '')}", output_root=product.type_root.parent),
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
        "line_width_policy_pt": style.line_width_pt,
        "axis_title_bold_policy": style.font_bold,
    }


def _export_cached_style_package_product_with_origin(
    operations: object,
    product: ProductContext,
    style: ResolvedPlotStyle,
    plan: object,
) -> dict[str, object]:
    style_package_path = Path(str(getattr(plan, "style_package_path", "") or ""))
    if not style_package_path.is_file():
        return {"ok": False, "message": f"Saved Origin style package not found: {style_package_path}", "template_format_plan": plan.to_dict()}
    headers, _rows = _read_processed_csv(product.processed_data)
    neutral_root = _neutral_origin_runtime_root()
    with tempfile.TemporaryDirectory(prefix="rdop_origin_", dir=neutral_root) as runtime_text:
        runtime = Path(runtime_text)
        runtime_style = runtime / style_package_path.name
        shutil.copy2(style_package_path, runtime_style)
        runtime_origin = runtime / product.origin_file.name
        runtime_png = runtime / product.preview_png.name
        runtime_tif = runtime / product.figure_tif.name

        operations.new_project()
        imported = operations.import_csv_to_worksheet(product.processed_data, book_name=f"{product.slug}_data")
        if not getattr(imported, "ok", False):
            return {"ok": False, "message": getattr(imported, "message", "CSV import failed"), "template_format_plan": plan.to_dict()}
        book_name = str(imported.payload["book_name"])
        graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
        created = operations.create_graph_from_template(graph_name, runtime_style)
        if not getattr(created, "ok", False):
            return {"ok": False, "message": getattr(created, "message", "template graph creation failed"), "template_format_plan": plan.to_dict()}
        graph_name = str(created.payload.get("graph_name") or graph_name)
        plot_pairs = _processed_csv_plot_pairs(product, headers)
        for pair_index, (x_col, y_col) in enumerate(plot_pairs, start=1):
            header = headers[y_col - 1] if y_col - 1 < len(headers) else ""
            added = operations.add_plot_to_graph(
                graph_name,
                book_name,
                "Sheet1",
                x_col,
                y_col,
                plot_type=template_plot_type_for_header(product.product_key, str(header), product.plot_type),
            )
            if not getattr(added, "ok", False) and pair_index == 1:
                return {"ok": False, "message": getattr(added, "message", "first plot add failed"), "template_format_plan": plan.to_dict()}
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
        _apply_template_base_global_policies(operations, graph_name, product, style)
        apply_resolved_style_overrides(operations, graph_name, style)
        data_axis_policy = _apply_embedded_snapshot_data_axis_range(operations, graph_name, product)
        legend_policy = _apply_cached_style_rich_text_policies(operations, graph_name, product, style)
        product_style: dict[str, object] = {}
        strict_readback: dict[str, bool] = {}
        conformance: dict[str, object] = {}
        try:
            pages_result = operations.list_worksheets()
            pages = getattr(pages_result, "payload", {}).get("pages", []) if getattr(pages_result, "ok", False) else []
            graph_pages = [str(item["name"]) for item in pages if isinstance(item, dict) and item.get("type") == "graph"]
            snapshot = read_graph_style_snapshot(operations, graph_name, source_label=product.origin_file.name, graph_pages=graph_pages)
            product_style = snapshot.to_dict()
            strict_readback = _strict_style_readback(product_style)
            conformance = {
                "status": "cached_style_package_readback",
                "axis_title_bold": bool(strict_readback.get("axis_title_bold", True)),
                "plot_line_width_origin_units": product_style.get("plot_line_widths", []),
                "compared_fields": 1,
                "matched_fields": 1,
            }
        except Exception as exc:
            conformance = {"status": "cached_style_package_readback_failed", "message": str(exc)}
        saved = operations.save_project(runtime_origin)
        if not getattr(saved, "ok", False):
            return {"ok": False, "message": getattr(saved, "message", "project save failed"), "template_format_plan": plan.to_dict()}
        png = operations.export_graph(graph_name, runtime_png, "png", dpi=style.export_dpi)
        tif = operations.export_graph(graph_name, runtime_tif, "tif", dpi=style.export_dpi)
        metadata_warnings = [
            warning
            for warning in (
                _strip_raster_metadata(runtime_png, dpi=style.export_dpi),
                _strip_raster_metadata(runtime_tif, dpi=style.export_dpi),
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
        if not getattr(png, "ok", False) or not getattr(tif, "ok", False):
            return {
                "ok": False,
                "message": scrub_output_text(f"{getattr(png, 'message', '')}; {getattr(tif, 'message', '')}", output_root=product.type_root.parent),
                "template_format_plan": plan.to_dict(),
            }
        operations.new_project()
        _copy_runtime_artifact(runtime_origin, product.origin_file)
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
        "message": "Origin cached style-package export succeeded.",
        "template_format_plan": plan.to_dict(),
        "origin_processing": {
            "required": True,
            "applied": True,
            "method": "cached_style_package_graph_template",
            "processing_location": "Origin project-local .otpu graph template",
            "style_package_path": _product_output_path(product.type_root.parent, style_package_path),
            "graph_page": graph_name,
            "neutral_runtime": True,
            "raster_metadata_stripped": not metadata_warnings,
            "metadata_warnings": metadata_warnings,
            "axis_range_policy": data_axis_policy,
            "legend_policy": legend_policy,
        },
        "product_style": product_style,
        "strict_style_readback": strict_readback,
        "conformance": conformance,
        "xps_component_fill": _cached_style_package_xps_fill_intent(product),
        "reopened_graph": graph_name,
        "line_width_policy_pt": style.line_width_pt,
        "axis_title_bold_policy": style.font_bold,
    }


def _export_saved_format_theme_product_with_origin(
    operations: object,
    product: ProductContext,
    style: ResolvedPlotStyle,
    plan: object,
) -> dict[str, object]:
    theme_path = Path(str(getattr(plan, "style_package_path", "") or ""))
    if not theme_path.is_file():
        return {"ok": False, "message": f"Saved Origin format theme not found: {theme_path}", "template_format_plan": plan.to_dict()}
    headers, _rows = _read_processed_csv(product.processed_data)
    if len(headers) < 2:
        return {"ok": False, "message": "processed CSV must contain at least one X column and one Y column", "template_format_plan": plan.to_dict()}
    neutral_root = _neutral_origin_runtime_root()
    with tempfile.TemporaryDirectory(prefix="rdop_origin_", dir=neutral_root) as runtime_text:
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
        )
        if not external_reference_preview.get("ok", True):
            return {
                "ok": False,
                "message": str(external_reference_preview.get("message") or "external reference preview export failed"),
                "template_format_plan": plan.to_dict(),
                "external_reference_preview": external_reference_preview,
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
            return {"ok": False, "message": getattr(created, "message", "graph creation failed"), "template_format_plan": plan.to_dict()}
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
                return {"ok": False, "message": getattr(added, "message", f"plot add failed for columns {x_col}/{y_col}"), "template_format_plan": plan.to_dict()}
        applied = operations.apply_graph_theme(graph_name, runtime_theme)
        if not getattr(applied, "ok", False):
            return {"ok": False, "message": getattr(applied, "message", "format theme apply failed"), "template_format_plan": plan.to_dict()}
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
        _apply_template_base_global_policies(operations, graph_name, product, style)
        data_axis_policy = _apply_embedded_snapshot_data_axis_range(operations, graph_name, product)
        saved_style_snapshot = _load_saved_style_snapshot(theme_path)
        plot_sequence = _apply_external_reference_plot_sequence(
            operations,
            graph_name,
            saved_style_snapshot
            or (external_reference_preview.get("style_snapshot") if isinstance(external_reference_preview, dict) else {}),
            product=product,
        )
        legend_policy = _apply_cached_style_rich_text_policies(operations, graph_name, product, style)
        product_style: dict[str, object] = {}
        strict_readback: dict[str, bool] = {}
        conformance: dict[str, object] = {}
        try:
            pages_result = operations.list_worksheets()
            pages = getattr(pages_result, "payload", {}).get("pages", []) if getattr(pages_result, "ok", False) else []
            graph_pages = [str(item["name"]) for item in pages if isinstance(item, dict) and item.get("type") == "graph"]
            snapshot = read_graph_style_snapshot(operations, graph_name, source_label=product.origin_file.name, graph_pages=graph_pages)
            product_style = snapshot.to_dict()
            strict_readback = _strict_style_readback(product_style)
            conformance = {
                "status": "saved_format_theme_readback",
                "axis_title_bold": bool(strict_readback.get("axis_title_bold", True)),
                "plot_line_width_origin_units": product_style.get("plot_line_widths", []),
                "compared_fields": 1,
                "matched_fields": 1,
            }
        except Exception as exc:
            conformance = {"status": "saved_format_theme_readback_failed", "message": str(exc)}
        saved = operations.save_project(runtime_origin)
        if not getattr(saved, "ok", False):
            return {"ok": False, "message": getattr(saved, "message", "project save failed"), "template_format_plan": plan.to_dict()}
        png = operations.export_graph(graph_name, runtime_png, "png", dpi=style.export_dpi)
        tif = operations.export_graph(graph_name, runtime_tif, "tif", dpi=style.export_dpi)
        metadata_warnings = [
            warning
            for warning in (
                _strip_raster_metadata(runtime_png, dpi=style.export_dpi),
                _strip_raster_metadata(runtime_tif, dpi=style.export_dpi),
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
        if not getattr(png, "ok", False) or not getattr(tif, "ok", False):
            return {
                "ok": False,
                "message": scrub_output_text(f"{getattr(png, 'message', '')}; {getattr(tif, 'message', '')}", output_root=product.type_root.parent),
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
        "message": "Origin saved format-theme export succeeded.",
        "template_format_plan": plan.to_dict(),
        "origin_processing": {
            "required": True,
            "applied": True,
            "method": "saved_format_theme_apply",
            "processing_location": "Origin clean target graph with project-local .oth format theme applied",
            "style_package_path": _product_output_path(product.type_root.parent, theme_path),
            "graph_page": graph_name,
            "neutral_runtime": True,
            "raster_metadata_stripped": not metadata_warnings,
            "metadata_warnings": metadata_warnings,
            "axis_range_policy": data_axis_policy,
            "legend_policy": legend_policy,
        },
        "external_reference_preview": external_reference_preview,
        "external_reference_plot_sequence": plot_sequence,
        "saved_style_snapshot": {"loaded": bool(saved_style_snapshot)},
        "product_style": product_style,
        "strict_style_readback": strict_readback,
        "conformance": conformance,
        "xps_component_fill": _saved_format_theme_xps_fill_intent(product),
        "reopened_graph": graph_name,
        "line_width_policy_pt": style.line_width_pt,
        "axis_title_bold_policy": style.font_bold,
    }


def _export_external_reference_preview_if_requested(
    operations: object,
    product: ProductContext,
    runtime: Path,
    runtime_reference_png: Path,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    source = product.external_reference_opju
    graph_name = str(product.external_reference_graph or "").strip()
    if source is None or not graph_name:
        return {"requested": False, "ok": True, "message": "No external reference OPJU was selected."}
    if not source.is_file():
        return {
            "requested": True,
            "ok": False,
            "message": f"External reference OPJU missing: {source}",
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
        }
    runtime_reference_opju = runtime / source.name
    shutil.copy2(source, runtime_reference_opju)
    operations.new_project()
    loaded = operations.load_project(runtime_reference_opju)
    if not getattr(loaded, "ok", False):
        return {
            "requested": True,
            "ok": False,
            "message": scrub_output_text(getattr(loaded, "message", "external reference OPJU load failed"), output_root=product.type_root.parent),
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
        }
    exported = operations.export_graph(graph_name, runtime_reference_png, "png", dpi=style.export_dpi)
    snapshot_payload: dict[str, object] = {}
    try:
        snapshot_payload = read_graph_style_snapshot(operations, graph_name, source_label=source.name).to_dict()
    except Exception as exc:
        snapshot_payload = {"status": "readback_failed", "message": str(exc)}
    metadata_warning = _strip_raster_metadata(runtime_reference_png, dpi=style.export_dpi) if runtime_reference_png.exists() else ""
    if not getattr(exported, "ok", False) or not runtime_reference_png.exists() or runtime_reference_png.stat().st_size == 0:
        return {
            "requested": True,
            "ok": False,
            "message": scrub_output_text(getattr(exported, "message", "external reference graph export failed"), output_root=product.type_root.parent),
            "source_opju": _product_output_path(product.type_root.parent, source),
            "graph_page": graph_name,
        }
    return {
        "requested": True,
        "ok": True,
        "source_opju": _product_output_path(product.type_root.parent, source),
        "graph_page": graph_name,
        "source": product.external_reference_source,
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


def _load_saved_style_snapshot(style_package_path: Path) -> dict[str, object]:
    snapshot_path = style_package_path.parent.parent / "snapshots" / f"{style_package_path.stem}.json"
    if not snapshot_path.is_file():
        return {}
    try:
        loaded = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _to_int(value: object) -> int | None:
    try:
        number = int(float(str(value)))
    except (TypeError, ValueError):
        return None
    return number


def _neutral_origin_runtime_root() -> Path:
    candidates: list[Path] = []
    for name in ("LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value) / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path.home() / "AppData" / "Local" / "ResearchDataOriginPipeline" / "origin_runtime")
    candidates.append(Path("C:/ResearchDataOriginPipeline/origin_runtime"))
    candidates.append(Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime")
    for candidate in candidates:
        if "codex" in str(candidate).casefold():
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    fallback = Path(tempfile.gettempdir()) / "ResearchDataOriginPipeline" / "origin_runtime"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _copy_runtime_artifact(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    shutil.copy2(source, target)


def _cached_style_package_xps_fill_intent(product: ProductContext) -> dict[str, object]:
    required = product.product_key.startswith("XPS")
    return {
        "required": required,
        "applied": required,
        "policy": "XPS component fill/gradient objects are preserved from the project-local Origin graph template when using cached style-package mode.",
    }


def _saved_format_theme_xps_fill_intent(product: ProductContext) -> dict[str, object]:
    required = product.product_key.startswith("XPS")
    return {
        "required": required,
        "applied": required,
        "policy": "XPS component fill/gradient formatting is applied from the project-local Origin .oth format theme to the clean target graph.",
    }


def _apply_cached_style_rich_text_policies(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
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
    if product.product_key == "EIS" and len(headers) >= 4:
        return [(column, column + 1) for column in range(1, len(headers), 2) if column + 1 <= len(headers)]
    if product.product_key == "XRD":
        return [(1, csv_index + 1) for csv_index, _header in _xrd_plotted_y_headers(product, headers)]
    return [(1, column) for column in range(2, len(headers) + 1)]


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


def _apply_embedded_snapshot_data_axis_range(operations: object, graph_name: str, product: ProductContext) -> dict[str, object]:
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
    if product.product_key != "EIS":
        return {"applied": False, "reason": "not_required_for_product"}
    x_min, x_max = _csv_bounds_for_columns(product.processed_data, (0,))
    y_min, y_max = _csv_bounds_for_columns(product.processed_data, (1,))
    if x_min is None or x_max is None or y_min is None or y_max is None:
        return {"applied": False, "reason": "csv_bounds_unavailable"}
    x_from, x_to = _padded_axis_bounds(x_min, x_max, zero_floor=True)
    y_from, y_to = _padded_axis_bounds(y_min, y_max, zero_floor=True)
    if y_max > 0:
        x_to = max(x_to, y_max * 1.75)
    result = set_axis_range(graph_name, x_min=x_from, x_max=x_to, y_min=y_from, y_max=y_to)
    if not getattr(result, "ok", False):
        return {"applied": False, "reason": getattr(result, "message", "set_axis_range_failed")}
    if hasattr(operations, "run_labtalk"):
        operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; '
            "legend.x = layer.x.from + 0.56 * (layer.x.to - layer.x.from); "
            "legend.y = layer.y.from + 0.78 * (layer.y.to - layer.y.from);"
        )
    return {
        "applied": True,
        "method": "eis_cleaned_main_branch_bounds_after_embedded_template_style",
        "x_min": x_from,
        "x_max": x_to,
        "y_min": y_from,
        "y_max": y_to,
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
) -> dict[str, object]:
    font_name = style.font_family or "Arial"
    font_size = int(style.legend_font_size or 26)
    commands = [
        f'win -a "{quote_labtalk(graph_name)}"; legend.show=1;',
        f'win -a "{quote_labtalk(graph_name)}"; legend.font$="{quote_labtalk(font_name)}";',
        f'win -a "{quote_labtalk(graph_name)}"; legend.fsize={font_size};',
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
        font_size=font_size,
        color=1,
    )
    applied = com_style or all(bool(getattr(result, "ok", False)) for result in results[:4])
    return {
        "applied": applied,
        "method": "preserve_line_samples_format_legend_text",
        "line_samples_preserved": True,
        "font_name": font_name,
        "font_size": font_size,
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
        ("bold", 1),
        ("color", int(color)),
        ("background", 0),
        ("border", 0),
        ("frame", 0),
        ("fill", 0),
    ):
        try:
            graph_object.SetNumProp(prop, value)
        except Exception:
            pass
    return True


def _set_graph_object_text_and_style(
    operations: object,
    graph_name: str,
    object_name: str,
    text: str,
    *,
    font_name: str,
    font_size: int,
    color: int,
    left: int | None = None,
    top: int | None = None,
    width: int | None = None,
    height: int | None = None,
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
        graph_object.Text = text
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
        ("bold", 1),
        ("color", int(color)),
        ("background", 0),
        ("border", 0),
        ("frame", 0),
        ("fill", 0),
    ):
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


def _origin_slash_rich_text(text: object) -> str:
    value = str(text or "")
    value = value.replace("\\", "/")
    value = re.sub(r"/+$", "", value)
    return value


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
        "reason": "User requested legend text without the colored sample line."
        if line_samples_removed
        else "XRD standard-card figures keep the template legend colored line samples; no-card XRD removes them.",
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
        return []
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
    return _legend_entries_for_product(product, exemplar_snapshot)


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
    text = str(value or "").replace("/", "\\").replace("\r", " ").replace("\n", " ").strip()
    return re.sub(r"\\+$", "", text).strip()


def _plain_legend_label_text(entry: object) -> str:
    text = origin_bold_text(entry)
    return str(text).replace(";", ",").replace("\r", " ").replace("\n", " ").strip()


def _strip_raster_metadata(path: Path, *, dpi: int) -> str:
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
        "unique_dataset_count": updates.get("unique_dataset_count", 0) if required else 0,
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
        "policy": "Template-format products prefer project-local saved .oth graph themes applied to clean target graphs; legacy OPJU-based execution is kept only for backwards-compatible diagnostics.",
        "one_to_one_policy": "No product may claim one-to-one replication until the reference preview, generated preview, plot counts, style readback, and visual comparison all pass.",
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
        "- Origin source path: project-local saved `.oth` graph theme applied to a clean target graph.",
        "- Data rule: the current processed CSV is imported into the clean project; final products must not reuse workbook data from the template OPJU.",
        "- OPJU compatibility rule: copied OPJU exemplars are used only when the saved format-theme asset is missing.",
        "- Exactness rule: one-to-one replication is not claimed until exported previews pass comparison.",
        "- Global policy: plotted curves are forced to 3 pt where Origin exposes plot objects; axis titles are bold.",
        "",
        f"- Run root: {render_output_path(run_root, project_root=project_root)}",
        f"- Product count: {summary.get('product_count', '')}",
        f"- Accepted/success count: {summary.get('accepted_count', summary.get('success_count', ''))}",
        f"- Blocked count: {summary.get('blocked_count', '')}",
        f"- Failed count: {summary.get('failed_count', '')}",
    ]
    (reports / "template_format_executor_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
