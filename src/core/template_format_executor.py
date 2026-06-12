from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.core.opju_product_pilot import ProductContext, _product_output_path
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.template_product_builder import (
    TemplateProductBuilderOptions,
    _strict_style_readback,
    run_template_product_builder_all_types,
)
from src.origin.conformance import compare_style_snapshots
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_registry import resolve_origin_style_asset
from src.origin.style_mimic import extract_style_snapshot, read_graph_style_snapshot
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
        global_style_override=FINAL_TEMPLATE_STYLE_OVERRIDE,
        eis_strict_semicircle_branch=True,
        xps_reference_templates_for_all_xps=True,
        xps_templates_from_reference_only=True,
        xps_smooth_gradient_fill=True,
        cleanup_empty_run_layout_dirs=True,
        project_style_asset_fallback=True,
    )


def run_template_format_executor(project_root: Path, options: TemplateFormatExecutorOptions) -> dict[str, object]:
    options = _with_default_xps_non_in_situ_template_root(project_root, options)
    result = run_template_product_builder_all_types(
        project_root,
        build_template_product_builder_options(options),
        origin_exporter=lambda product, style: export_template_base_product_with_origin(product, style, project_root=project_root),
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
    updates = build_template_dataset_updates(plot_dataset_names, headers, rows, allow_partial=True)
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
) -> dict[str, object]:
    operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    try:
        style_asset = resolve_origin_style_asset(project_root, product.product_key) if project_root is not None else None
        neutral_root = _neutral_origin_runtime_root()
        with tempfile.TemporaryDirectory(prefix="rdop_origin_", dir=neutral_root) as runtime_text:
            runtime = Path(runtime_text)
            runtime_reference = runtime / product.reference_opju_copy.name
            plan_opju = product.reference_opju_copy
            if product.reference_opju_copy.is_file():
                shutil.copy2(product.reference_opju_copy, runtime_reference)
                plan_opju = runtime_reference
            runtime_origin = runtime / product.origin_file.name
            runtime_reference_png = runtime / product.reference_preview_png.name
            runtime_preview_png = runtime / product.preview_png.name
            runtime_tif = runtime / product.figure_tif.name
            runtime_debug = runtime / "debug"
            runtime_template_debug = runtime_debug / "template_preview.png"
            runtime_generated_debug = runtime_debug / "generated_preview.png"

            plan = build_template_format_plan(
                product.product_key,
                opju_path=plan_opju,
                style_package_path=style_asset.graph_template_path if style_asset else None,
                graph_page=style_asset.graph_page if style_asset else "",
                reference_preview_png=runtime_reference_png,
                product_preview_png=runtime_preview_png,
                curve_line_width_pt=style.line_width_pt,
                axis_title_bold=style.font_bold,
            )
            if not plan.can_execute:
                return {"ok": False, "message": "; ".join(plan.warnings), "template_format_plan": plan.to_dict()}
            if plan.mode == "cached_style_package":
                return _export_cached_style_package_product_with_origin(operations, product, style, plan)
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

            replacement = apply_template_base_data_replacement(operations, product, graph_name)
            if not replacement.get("ok"):
                return {
                    "ok": False,
                    "message": str(replacement.get("message") or "template base data replacement failed"),
                    "template_format_plan": plan.to_dict(),
                    "template_base_replacement": replacement,
                    "exemplar_style": exemplar_style,
                }

            _apply_template_base_global_policies(
                operations,
                graph_name,
                product,
                style,
                template_axis_titles=exemplar_snapshot.audit_string_values,
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
            },
            "xps_component_fill": _template_base_xps_fill_intent(product, replacement),
            "reopened_graph": reopened_graph,
            "line_width_policy_pt": style.line_width_pt,
            "axis_title_bold_policy": style.font_bold,
        }
    except Exception as exc:
        return {"ok": False, "message": scrub_output_text(str(exc), output_root=product.type_root.parent)}
    finally:
        operations.close()


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
        for column_index in range(2, len(headers) + 1):
            added = operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 1, column_index, plot_type=product.plot_type)
            if not getattr(added, "ok", False) and column_index == 2:
                return {"ok": False, "message": getattr(added, "message", "first plot add failed"), "template_format_plan": plan.to_dict()}
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
        _apply_template_base_global_policies(operations, graph_name, product, style)
        apply_resolved_style_overrides(operations, graph_name, style)
        _apply_cached_style_rich_text_policies(operations, graph_name, product)
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
        },
        "product_style": product_style,
        "strict_style_readback": strict_readback,
        "conformance": conformance,
        "xps_component_fill": _cached_style_package_xps_fill_intent(product),
        "reopened_graph": graph_name,
        "line_width_policy_pt": style.line_width_pt,
        "axis_title_bold_policy": style.font_bold,
    }


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


def _apply_cached_style_rich_text_policies(operations: object, graph_name: str, product: ProductContext) -> None:
    commands = _bold_template_axis_title_commands({"xb.text$": product.x_label, "yl.text$": product.y_label})
    legend_text = _cached_style_legend_text(product.legend_entries)
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if commands:
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; {commands}')
    if legend_text:
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; legend.text$ = {legend_text}; legend.bold=1;')
    operations.run_labtalk(
        f'win -a "{quote_labtalk(graph_name)}"; '
        "legend.background=0; legend.border=0; legend.frame=0; legend.fill=0; "
        "legend.fillColor=0; legend.borderColor=0; legend.lineWidth=0;"
    )


def _cached_style_legend_text(entries: list[str]) -> str:
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        text = origin_bold_text(entry)
        text = str(text).replace(";", ",").replace("\r", " ").replace("\n", " ").strip()
        if text:
            lines.append(f"\\l({index}) {text}")
    return "\n".join(lines)


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
        "policy": "Template-format products prefer project-local saved .otpu graph templates in a clean Origin project; OPJU template-base replacement is compatibility fallback only.",
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
        "- Origin source path: project-local saved `.otpu` graph template applied to a clean Origin project.",
        "- Data rule: the current processed CSV is imported into the clean project; final products must not reuse workbook data from the template OPJU.",
        "- OPJU compatibility rule: copied OPJU exemplars are used only when the saved graph-template asset is missing.",
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
