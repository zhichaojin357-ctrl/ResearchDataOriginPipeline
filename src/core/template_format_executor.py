from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.core.opju_product_pilot import ProductContext, _product_output_path
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.v3_real_template_rebuild import (
    V3RealTemplateRebuildOptions,
    _strict_style_readback,
    run_v3_real_template_rebuild_all_types,
)
from src.core.v4_strict_template_conformance import V4_STRICT_GLOBAL_STYLE_OVERRIDE
from src.origin.conformance import compare_style_snapshots
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_mimic import extract_style_snapshot, read_graph_style_snapshot
from src.origin.template_format import build_template_dataset_updates, build_template_format_plan
from src.origin.text_format import origin_bold_text
from src.origin.user_style import ResolvedPlotStyle


TEMPLATE_FORMAT_SCOPE = "unified_v5_template_format_conformance_all_types"
TEMPLATE_FORMAT_COMMAND = "unified-v5-template-format-conformance-all-types"


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


def build_template_format_v3_options(options: TemplateFormatExecutorOptions) -> V3RealTemplateRebuildOptions:
    return V3RealTemplateRebuildOptions(
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
        product_slug_version="v5_template_format",
        global_style_override=V4_STRICT_GLOBAL_STYLE_OVERRIDE,
        eis_strict_semicircle_branch=True,
        xps_reference_templates_for_all_xps=True,
        xps_templates_from_reference_only=True,
        xps_smooth_gradient_fill=True,
        cleanup_empty_run_layout_dirs=True,
    )


def run_template_format_executor(project_root: Path, options: TemplateFormatExecutorOptions) -> dict[str, object]:
    options = _with_default_xps_non_in_situ_template_root(project_root, options)
    result = run_v3_real_template_rebuild_all_types(
        project_root,
        build_template_format_v3_options(options),
        origin_exporter=export_template_base_product_with_origin,
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


def export_template_base_product_with_origin(product: ProductContext, style: ResolvedPlotStyle) -> dict[str, object]:
    operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    try:
        plan = build_template_format_plan(
            product.product_key,
            opju_path=product.reference_opju_copy,
            reference_preview_png=product.reference_preview_png,
            product_preview_png=product.preview_png,
            curve_line_width_pt=style.line_width_pt,
            axis_title_bold=style.font_bold,
        )
        if not plan.can_execute:
            return {"ok": False, "message": "; ".join(plan.warnings), "template_format_plan": plan.to_dict()}

        exemplar_snapshot = extract_style_snapshot(operations, product.reference_opju_copy)
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
            opju_path=product.reference_opju_copy,
            graph_page=graph_name,
            reference_preview_png=product.reference_preview_png,
            product_preview_png=product.preview_png,
            curve_line_width_pt=style.line_width_pt,
            axis_title_bold=style.font_bold,
        )
        operations.export_graph(graph_name, product.reference_preview_png, "png", dpi=style.export_dpi)
        operations.export_graph(graph_name, product.type_root / "debug" / "template_preview.png", "png", dpi=style.export_dpi)

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
        product.origin_file.parent.mkdir(parents=True, exist_ok=True)
        saved = operations.save_project(product.origin_file)
        if not getattr(saved, "ok", False):
            return {"ok": False, "message": getattr(saved, "message", "project save failed"), "exemplar_style": exemplar_style}

        operations.new_project()
        loaded = operations.load_project(product.origin_file)
        if not getattr(loaded, "ok", False):
            return {"ok": False, "message": getattr(loaded, "message", "saved product reload failed"), "exemplar_style": exemplar_style}
        pages = operations.list_worksheets().payload.get("pages", [])
        graph_pages = [str(item["name"]) for item in pages if item.get("type") == "graph"]
        reopened_graph = graph_name if graph_name in graph_pages else (graph_pages[0] if graph_pages else graph_name)
        product_snapshot = read_graph_style_snapshot(operations, reopened_graph, source_label=product.origin_file.name, graph_pages=graph_pages)
        conformance = compare_style_snapshots(exemplar_snapshot, product_snapshot, required_line_width_pt=style.line_width_pt)
        strict_readback = _strict_style_readback(product_snapshot.to_dict())
        png = operations.export_graph(reopened_graph, product.preview_png, "png", dpi=style.export_dpi)
        tif = operations.export_graph(reopened_graph, product.figure_tif, "tif", dpi=style.export_dpi)
        operations.export_graph(reopened_graph, product.type_root / "debug" / "generated_preview.png", "png", dpi=style.export_dpi)
        missing = [path for path in (product.origin_file, product.preview_png, product.figure_tif) if not path.exists() or path.stat().st_size == 0]
        if missing:
            return {
                "ok": False,
                "message": "missing artifacts: " + "; ".join(_product_output_path(product.type_root.parent, path) for path in missing),
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
        operations.save_project(product.origin_file)
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
        "policy": "V5 uses OPJU template-base workbook replacement for Origin export when --with-origin is enabled.",
        "one_to_one_policy": "No product may claim one-to-one replication until the reference preview, generated preview, plot counts, style readback, and visual comparison all pass.",
        "summary": summary,
        "products": products,
    }
    (reports / "template_format_executor_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# V5 template-format executor",
        "",
        "- Origin source path: OPJU template-base workbook replacement.",
        "- Fallback rule: missing OPJU requires a saved Theme/Graph Template/style package; otherwise plotting is blocked.",
        "- Exactness rule: one-to-one replication is not claimed until exported reference and product previews pass comparison.",
        "- Global policy: plotted curves are forced to 3 pt where Origin exposes plot objects; axis titles are bold.",
        "",
        f"- Run root: {render_output_path(run_root, project_root=project_root)}",
        f"- Product count: {summary.get('product_count', '')}",
        f"- Accepted/success count: {summary.get('accepted_count', summary.get('success_count', ''))}",
        f"- Blocked count: {summary.get('blocked_count', '')}",
        f"- Failed count: {summary.get('failed_count', '')}",
    ]
    (reports / "template_format_executor_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    docs_path = project_root / "docs" / "V5_TEMPLATE_FORMAT_EXECUTOR.md"
    docs_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
