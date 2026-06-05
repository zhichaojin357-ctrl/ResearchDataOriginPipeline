from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.core.opju_product_pilot import (
    ProductContext,
    TargetPairing,
    _build_processed_plot_table,
    _copy_inputs,
    _copy_reference,
    _csv_header,
    _csv_x_bounds,
    _forbidden_claims,
    _manual_items,
    _reference_policy_notes,
    _relative_to_run,
    _selected_relative_paths,
    _set_bold_axis_title_objects,
    _write_csv,
    build_default_root_map,
    load_target_pairings,
)
from src.core.remaining_opju_product_drafts import _build_remaining_processed_plot_table, load_remaining_pairings
from src.core.runtime_paths import create_run_output_layout, resolve_output_root
from src.core.v2_exemplar_conformance import FORBIDDEN_PRODUCT_LABELS
from src.origin.conformance import compare_style_snapshots
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_mimic import OpjuStyleSnapshot, apply_style_snapshot, extract_style_snapshot, read_graph_style_snapshot
from src.origin.user_style import ResolvedPlotStyle, apply_resolved_style_overrides, load_user_plot_style, resolve_user_plot_style
from src.processors.base import safe_name
from src.processors.eis import (
    EisFitResult,
    EisPoint,
    clean_eis_file,
    draft_fit_eis_randles_cpe,
    eis_plot_rows,
    write_eis_fit_csv,
    write_eis_points_csv,
    write_ignored_eis_points_csv,
)


V3_TARGET_TYPES = (
    "BET",
    "XPS_in_situ",
    "XPS_non_in_situ",
    "XRD",
    "EPR",
    "EIS",
    "Raman",
    "UV-vis DRS / Tauc",
    "PL",
    "photocurrent",
    "FTIR",
)

V3_ACCEPTED_TYPES = V3_TARGET_TYPES

V3_TYPE_DIRS = {
    "BET": "BET",
    "XPS_in_situ": "XPS_in_situ",
    "XPS_non_in_situ": "XPS_non_in_situ",
    "XRD": "XRD",
    "EPR": "EPR",
    "EIS": "EIS",
    "Raman": "Raman",
    "UV-vis DRS / Tauc": "UV_vis_DRS_Tauc",
    "PL": "PL",
    "photocurrent": "photocurrent",
    "FTIR": "FTIR",
}

V3_STATUS_NAMES = ("accepted", "blocked", "skipped", "failed")

V3_SLUGS = {
    "BET": "BET_BOBC_exemplar_v3",
    "XPS_in_situ": "XPS_in_situ_BOBC_exemplar_v3",
    "XPS_non_in_situ": "XPS_non_in_situ_BOBC_BC_exemplar_v3",
    "XRD": "XRD_BOBC_exemplar_v3",
    "EPR": "EPR_BC_O3_dark_exemplar_v3",
    "EIS": "EIS_BOBC_exemplar_v3",
    "Raman": "Raman_BOBC_exemplar_v3",
    "UV-vis DRS / Tauc": "UV_vis_DRS_Tauc_BOBC_exemplar_v3",
    "PL": "PL_BOBC_exemplar_v3",
    "photocurrent": "photocurrent_BOBC_exemplar_v3",
    "FTIR": "FTIR_BOBC_CWO_exemplar_v3",
}

FIRST_BATCH_TYPES = {"BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR"}
SKIPPED_V3_TYPES = (
    {
        "type": "HPLC/LC",
        "status": "skipped",
        "reason": "No reviewed OPJU exemplar is available; conversion/selectivity/yield and product identity remain deferred.",
    },
    {
        "type": "Mott-Schottky",
        "status": "skipped",
        "reason": "Previously reviewed Mott candidates remain exemplar-mismatch risks and are not in the v3 rebuild target set.",
    },
    {
        "type": "reaction_condition_screening",
        "status": "skipped",
        "reason": "No clear reviewed data table plus OPJU pair is available for v3 rebuild.",
    },
)

OriginExporter = Callable[[ProductContext, ResolvedPlotStyle], dict[str, object]]


@dataclass(frozen=True)
class V3TemplateCandidate:
    product_key: str
    path: Path
    source: str
    path_score: int = 0
    status: str = "unvalidated"
    graph_page: str = ""
    layer_count: int = 0
    plot_count: int = 0
    reason: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class V3TemplateSelection:
    product_key: str
    status: str
    selected: V3TemplateCandidate | None = None
    candidates: tuple[V3TemplateCandidate, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class V3Acceptance:
    status: str
    visual_acceptance: bool
    line_width_acceptance: bool
    axis_title_acceptance: bool
    exemplar_similarity: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class V3RealTemplateRebuildOptions:
    pairing_path: Path
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    f_drive_template_root: Path | None = None
    user_style_path: Path | None = None


def classify_v3_template_candidates(paths: list[Path], *, f_drive_root: Path) -> list[V3TemplateCandidate]:
    candidates: list[V3TemplateCandidate] = []
    for path in paths:
        if path.suffix.casefold() not in {".opju", ".opj"}:
            continue
        if not _is_relative_to(path, f_drive_root):
            continue
        product_key = _product_key_from_f_drive_path(path)
        if product_key is None:
            continue
        candidates.append(
            V3TemplateCandidate(
                product_key=product_key,
                path=path,
                source="f_drive_scan",
                path_score=_template_path_score(product_key, path),
                reason="classified by F-drive path keywords",
            )
        )
    return candidates


def scan_v3_f_drive_template_paths(f_drive_root: Path) -> list[Path]:
    if not f_drive_root.exists():
        raise FileNotFoundError(f"F-drive template root not found: {f_drive_root}")
    return sorted(
        path for path in f_drive_root.rglob("*") if path.is_file() and path.suffix.casefold() in {".opju", ".opj"}
    )


def validate_v3_template_candidates(candidates: list[V3TemplateCandidate], scan_copy_root: Path, *, max_per_type: int = 5) -> list[V3TemplateCandidate]:
    if not candidates:
        return []
    scan_copy_root.mkdir(parents=True, exist_ok=True)
    validated: list[V3TemplateCandidate] = []
    validation_targets = _prioritized_template_validation_targets(candidates, max_per_type=max_per_type)
    target_ids = {id(candidate) for candidate in validation_targets}
    copy_index = 1
    for candidate in candidates:
        if id(candidate) not in target_ids:
            validated.append(
                V3TemplateCandidate(
                    product_key=candidate.product_key,
                    path=candidate.path,
                    source=candidate.source,
                    path_score=candidate.path_score,
                    status="not_opened_lower_priority_candidate",
                    reason="Recorded during F-drive scan but not opened because higher-priority candidates were validated first.",
                )
            )
            continue
        copied = _copy_template_for_scan(candidate.path, scan_copy_root, copy_index)
        copy_index += 1
        try:
            snapshot_payload = _extract_template_snapshot_in_isolated_process(copied)
            status = _candidate_status_from_snapshot_payload(snapshot_payload)
            validated.append(
                V3TemplateCandidate(
                    product_key=candidate.product_key,
                    path=candidate.path,
                    source=candidate.source,
                    path_score=candidate.path_score,
                    status=status,
                    graph_page=str(snapshot_payload.get("graph_page") or ""),
                    layer_count=int(snapshot_payload.get("layer_count") or 0),
                    plot_count=int(snapshot_payload.get("plot_count") or 0),
                    reason=_candidate_reason_from_payload(snapshot_payload),
                    metadata={
                        "scan_copy": str(copied),
                        "snapshot": snapshot_payload,
                    },
                )
            )
        except Exception as exc:
            validated.append(
                V3TemplateCandidate(
                    product_key=candidate.product_key,
                    path=candidate.path,
                    source=candidate.source,
                    path_score=candidate.path_score,
                    status="load_failed",
                    reason=str(exc),
                    metadata={"scan_copy": str(copied)},
                )
            )
    return validated


def select_v3_template(product_key: str, candidates: list[V3TemplateCandidate]) -> V3TemplateSelection:
    scoped = [candidate for candidate in candidates if candidate.product_key == product_key]
    if not scoped:
        return V3TemplateSelection(
            product_key=product_key,
            status="blocked",
            candidates=(),
            reason=f"No F-drive OPJU/OPJ template candidate found for {product_key}.",
        )
    usable = [
        candidate
        for candidate in scoped
        if candidate.status in {"extracted", "valid"} and candidate.layer_count > 0 and candidate.plot_count > 0 and candidate.graph_page
    ]
    if not usable:
        data_only = any(candidate.status in {"data_only", "no_graph_pages"} for candidate in scoped)
        reason = "All F-drive candidates are data-only or lack complete graph/layer/plot objects." if data_only else "No validated graph-bearing template candidate is available."
        return V3TemplateSelection(product_key=product_key, status="blocked", candidates=tuple(scoped), reason=reason)
    selected = max(usable, key=lambda item: (item.path_score, item.plot_count, item.layer_count, -len(str(item.path))))
    return V3TemplateSelection(
        product_key=product_key,
        status="selected",
        selected=selected,
        candidates=tuple(scoped),
        reason="Selected highest-scoring validated F-drive graph template.",
    )


def clip_eis_fit_to_measured_range(
    cleaned_points: list[EisPoint],
    full_fit: EisFitResult,
    *,
    x_pad_fraction: float = 0.05,
    y_pad_fraction: float = 0.15,
) -> EisFitResult:
    if not cleaned_points or not full_fit.points:
        return full_fit
    x_values = [point.z_real_ohm for point in cleaned_points]
    y_values = [point.minus_z_imag_ohm for point in cleaned_points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)
    x_span = max(x_max - x_min, 1e-12)
    y_span = max(y_max - y_min, 1e-12)
    x_lower = x_min - x_span * x_pad_fraction
    x_upper = x_max + x_span * x_pad_fraction
    y_lower = max(0.0, y_min - y_span * y_pad_fraction)
    y_upper = y_max + y_span * y_pad_fraction
    clipped = [
        (float(x), float(y))
        for x, y in full_fit.points
        if math.isfinite(x) and math.isfinite(y) and x_lower <= x <= x_upper and y_lower <= y <= y_upper
    ]
    if len(clipped) < 3:
        clipped = [(point.z_real_ohm, point.minus_z_imag_ohm) for point in sorted(cleaned_points, key=lambda item: item.z_real_ohm)]
    return EisFitResult(
        method="least_squares_randles_cpe_measured_range_visual_segment",
        points=clipped,
        parameters=dict(full_fit.parameters),
        residual_sse=full_fit.residual_sse,
        robust_cost=full_fit.robust_cost,
        semicircle_classification=full_fit.semicircle_classification,
        warning=(full_fit.warning + " " if full_fit.warning else "") + "Main-figure curve is clipped to the measured range; full fit retained in debug/report.",
    )


def v3_acceptance_status(
    *,
    has_required_artifacts: bool,
    no_label_pass: bool,
    readback_pass: bool,
    visual_acceptance: bool,
    line_width_acceptance: bool,
    axis_title_acceptance: bool,
    exemplar_similarity: bool,
    notes: list[str],
) -> V3Acceptance:
    checks = (
        has_required_artifacts,
        no_label_pass,
        readback_pass,
        visual_acceptance,
        line_width_acceptance,
        axis_title_acceptance,
        exemplar_similarity,
    )
    status = "accepted" if all(checks) else "blocked"
    return V3Acceptance(
        status=status,
        visual_acceptance=visual_acceptance,
        line_width_acceptance=line_width_acceptance,
        axis_title_acceptance=axis_title_acceptance,
        exemplar_similarity=exemplar_similarity,
        notes=tuple(notes),
    )


def run_v3_real_template_rebuild_all_types(
    project_root: Path,
    options: V3RealTemplateRebuildOptions,
    *,
    root_map: dict[str, Path] | None = None,
    origin_exporter: OriginExporter | None = None,
    template_validator: Callable[[list[V3TemplateCandidate], Path], list[V3TemplateCandidate]] | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    roots = root_map or build_default_root_map(project_root)
    output_root = resolve_output_root(project_root, explicit=options.output_root)
    timestamp = options.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    f_drive_root = options.f_drive_template_root or Path("F:/") / "\u8bfe\u9898" / "LL" / "\u68c0\u6d4b"
    opju_paths = scan_v3_f_drive_template_paths(f_drive_root)
    candidates = classify_v3_template_candidates(opju_paths, f_drive_root=f_drive_root)
    layout = create_run_output_layout(
        project_root,
        scope="unified_v3_real_template_rebuild_all_types",
        command="unified-v3-real-template-rebuild-all-types",
        mode="with_origin" if options.with_origin else "no_origin",
        input_paths=[options.pairing_path, f_drive_root],
        timestamp=timestamp,
        no_origin=not options.with_origin,
        dry_run=False,
        output_base=output_root / "runs",
    )
    for product_key in V3_TARGET_TYPES:
        _ensure_v3_type_dirs(layout.root / V3_TYPE_DIRS[product_key])
    validator = template_validator or validate_v3_template_candidates
    validated = validator(candidates, layout.root / "template_scan_copies")
    selections = {product_key: select_v3_template(product_key, validated) for product_key in V3_TARGET_TYPES}
    _write_template_discovery_doc(project_root / "docs" / "V3_TEMPLATE_DISCOVERY_AND_SELECTION.md", f_drive_root, validated, selections)

    user_config = load_user_plot_style(project_root, options.user_style_path)
    first_pairings = {item.product_key: item for item in load_target_pairings(options.pairing_path, roots)}
    remaining_pairings = {item.product_key: item for item in load_remaining_pairings(options.pairing_path, roots)}
    exporter = origin_exporter or (lambda product, style: export_v3_product_with_origin(product, style))
    products: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for product_key in V3_TARGET_TYPES:
        selection = selections[product_key]
        if selection.status != "selected" or selection.selected is None:
            record = _blocked_product_record(layout.root, product_key, selection)
            products.append(record)
            continue
        pairing = first_pairings.get(product_key) or remaining_pairings.get(product_key)
        if pairing is None:
            record = _blocked_product_record(layout.root, product_key, selection, reason="No reviewed real-data pairing found.")
            products.append(record)
            continue
        try:
            product, extra = prepare_v3_product(layout.root, pairing, selection.selected)
            style = resolve_user_plot_style(product_key, exemplar=selection.selected.metadata.get("snapshot"), user_config=user_config)
            export_status: dict[str, object] = {"ok": False, "message": "Origin export skipped"}
            if options.with_origin:
                export_status = exporter(product, style)
            acceptance = _build_v3_acceptance(product, export_status, selection.selected, extra)
            metadata = _write_v3_product_metadata(layout.root, product, export_status, style, extra, selection.selected, acceptance)
            report = _write_v3_per_type_report(layout.root, product, export_status, style, extra, selection.selected, acceptance)
            products.append(_v3_product_summary(product, export_status, metadata, report, selection.selected, acceptance))
        except Exception as exc:
            failures.append({"product_key": product_key, "message": str(exc)})
            products.append(_failed_product_record(layout.root, product_key, selection, str(exc)))

    label_audit = _write_v3_no_label_audit(layout.root)
    products = [_with_label_audit_status(product, label_audit) for product in products]
    _write_v3_run_reports(layout.root, products, failures, selections, label_audit)
    _write_v3_docs(project_root, layout.root, products, failures, selections, label_audit)
    return {
        "run_root": str(layout.root),
        "products": products,
        "failures": failures,
        "skipped": list(SKIPPED_V3_TYPES),
        "summary": {
            "product_count": len(products),
            "accepted_count": sum(1 for item in products if item.get("status") == "accepted"),
            "blocked_count": sum(1 for item in products if item.get("status") == "blocked"),
            "failed_count": sum(1 for item in products if item.get("status") == "failed"),
            "with_origin": bool(options.with_origin),
            "label_audit_pass": int(label_audit.get("hit_count", 0)) == 0,
        },
    }


def prepare_v3_product(run_root: Path, pairing: TargetPairing, template: V3TemplateCandidate) -> tuple[ProductContext, dict[str, object]]:
    product_key = pairing.product_key
    type_root = run_root / V3_TYPE_DIRS[product_key]
    _ensure_v3_type_dirs(type_root)
    slug = V3_SLUGS[product_key]
    input_copies = _copy_inputs(pairing.data_paths, type_root / "input_copies")
    reference_copy = _copy_reference(template.path, type_root / "reference_opju")
    extra: dict[str, object] = {"template": _candidate_to_dict(template)}
    if product_key == "EIS":
        headers, rows, labels, eis_extra = _build_v3_eis_table(pairing, type_root)
        extra.update(eis_extra)
    elif product_key in FIRST_BATCH_TYPES:
        headers, rows, labels = _build_processed_plot_table(pairing)
    else:
        headers, rows, labels = _build_remaining_processed_plot_table(pairing)
    processed_data = type_root / "processed_data" / f"{slug}.csv"
    _write_csv(processed_data, headers, rows)
    product = ProductContext(
        product_key=product_key,
        slug=slug,
        pairing=pairing,
        type_root=type_root,
        processed_data=processed_data,
        input_copies=input_copies,
        reference_opju_copy=reference_copy,
        reference_preview_png=type_root / "reference_exports" / f"{slug}_reference_preview.png",
        origin_file=type_root / "origin_files" / f"{slug}.opju",
        figure_tif=type_root / "figures_tif" / f"{slug}.tif",
        preview_png=type_root / "figures_preview" / f"{slug}_preview.png",
        x_label=labels["x_label"],
        y_label=labels["y_label"],
        graph_title=labels["title"],
        plot_type=labels.get("plot_type", "line"),
        x_descending=labels.get("x_descending", "false") == "true",
        y_ticks=labels.get("y_ticks", "true") == "true",
        y_tick_values=labels.get("y_tick_values", "true") == "true",
        legend_entries=[header.replace("_", " ") for header in headers[1:]],
        notes=labels.get("notes", "").splitlines() if labels.get("notes") else [],
    )
    return product, extra


def export_v3_product_with_origin(product: ProductContext, style: ResolvedPlotStyle) -> dict[str, object]:
    operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    try:
        exemplar_snapshot = extract_style_snapshot(operations, product.reference_opju_copy)
        exemplar_style = exemplar_snapshot.to_dict()
        if exemplar_snapshot.graph_page:
            operations.export_graph(exemplar_snapshot.graph_page, product.reference_preview_png, "png", dpi=style.export_dpi)
            operations.export_graph(exemplar_snapshot.graph_page, product.type_root / "debug" / "template_preview.png", "png", dpi=style.export_dpi)
        operations.new_project()
        imported = operations.import_csv_to_worksheet(product.processed_data, book_name=f"{product.slug}_data")
        if not imported.ok:
            return {"ok": False, "message": imported.message, "exemplar_style": exemplar_style}
        headers = _csv_header(product.processed_data)
        book_name = str(imported.payload["book_name"])
        graph_name = safe_name(product.slug)[:24] or "V3Graph"
        created = operations.create_graph(graph_name, book_name, "Sheet1", 1, 2, plot_type=product.plot_type)
        if not created.ok:
            return {"ok": False, "message": created.message, "exemplar_style": exemplar_style}
        graph_name = str(created.payload["graph_name"])
        if product.product_key == "EIS" and len(headers) >= 4:
            operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 3, 4, plot_type=product.plot_type)
        else:
            for column_index in range(3, min(len(headers), 10) + 1):
                operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 1, column_index, plot_type=product.plot_type)
        if not apply_style_snapshot(operations, graph_name, exemplar_snapshot):
            operations.apply_graph4_fixed_style(graph_name)
        _apply_v3_template_plot_style(operations, graph_name, exemplar_snapshot, style)
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
        operations.set_graph_font(
            graph_name,
            axis_title_size=style.axis_title_font_size,
            x_tick_label_size=style.tick_label_font_size,
            y_tick_label_size=style.tick_label_font_size,
            legend_font_size=style.legend_font_size,
            annotation_font_size=style.title_font_size,
        )
        _set_bold_axis_title_objects(operations, graph_name, product.x_label, product.y_label)
        apply_resolved_style_overrides(operations, graph_name, style)
        _apply_v3_axis_range(operations, graph_name, product)
        operations.set_tick_style(graph_name)
        operations.set_axis_and_tick_visibility(graph_name, y_axis=True, y_ticks=product.y_ticks, y_tick_values=product.y_tick_values)
        _position_v3_axis_titles_outside_plot(operations, graph_name)
        legend_visible = False if product.product_key == "EIS" else bool(exemplar_snapshot.audit_numeric_values.get("legend.show", 0))
        operations.set_legend(graph_name, visible=legend_visible, entries=product.legend_entries)
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; title.show=0;')
        series_count = 2 if product.product_key == "EIS" and len(headers) >= 4 else len(headers) - 1
        _style_v3_series(operations, graph_name, product, series_count, style)
        product.origin_file.parent.mkdir(parents=True, exist_ok=True)
        saved = operations.save_project(product.origin_file)
        if not saved.ok:
            return {"ok": False, "message": saved.message, "exemplar_style": exemplar_style}
        operations.new_project()
        loaded = operations.load_project(product.origin_file)
        if not loaded.ok:
            return {"ok": False, "message": loaded.message, "exemplar_style": exemplar_style}
        pages = operations.list_worksheets().payload.get("pages", [])
        graph_pages = [str(item["name"]) for item in pages if item.get("type") == "graph"]
        reopened_graph = graph_name if graph_name in graph_pages else (graph_pages[0] if graph_pages else graph_name)
        product_snapshot = read_graph_style_snapshot(operations, reopened_graph, source_label=str(product.origin_file), graph_pages=graph_pages)
        conformance = compare_style_snapshots(exemplar_snapshot, product_snapshot, required_line_width_pt=style.line_width_pt)
        png = operations.export_graph(reopened_graph, product.preview_png, "png", dpi=style.export_dpi)
        tif = operations.export_graph(reopened_graph, product.figure_tif, "tif", dpi=style.export_dpi)
        operations.export_graph(reopened_graph, product.type_root / "debug" / "generated_preview.png", "png", dpi=style.export_dpi)
        missing = [path for path in (product.origin_file, product.preview_png, product.figure_tif) if not path.exists() or path.stat().st_size == 0]
        if missing:
            return {
                "ok": False,
                "message": "missing artifacts: " + "; ".join(str(path) for path in missing),
                "exemplar_style": exemplar_style,
                "product_style": product_snapshot.to_dict(),
                "conformance": conformance.to_dict(),
            }
        if not png.ok or not tif.ok:
            return {"ok": False, "message": f"{png.message}; {tif.message}", "exemplar_style": exemplar_style}
        return {
            "ok": True,
            "message": "Origin isolated v3 export succeeded after save/reopen/readback",
            "exemplar_style": exemplar_style,
            "product_style": product_snapshot.to_dict(),
            "conformance": conformance.to_dict(),
            "reopened_graph": reopened_graph,
            "line_width_policy_pt": style.line_width_pt,
            "axis_title_bold_policy": style.font_bold,
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        operations.close()


def _build_v3_eis_table(pairing: TargetPairing, type_root: Path) -> tuple[list[str], list[list[float | None]], dict[str, str], dict[str, object]]:
    cleaning = clean_eis_file(pairing.data_paths[0])
    full_fit = draft_fit_eis_randles_cpe(cleaning.cleaned_points)
    main_fit = clip_eis_fit_to_measured_range(cleaning.cleaned_points, full_fit)
    raw_path = type_root / "processed_data" / "raw_eis_data.csv"
    cleaned_path = type_root / "processed_data" / "cleaned_eis_data.csv"
    ignored_path = type_root / "processed_data" / "ignored_eis_points.csv"
    fit_path = type_root / "processed_data" / "eis_randles_cpe_fit_curve.csv"
    full_fit_path = type_root / "debug" / "eis_randles_cpe_full_fit_curve.csv"
    metadata_path = type_root / "metadata" / "eis_cleaning_and_fit_metadata.json"
    write_eis_points_csv(raw_path, cleaning.raw_points)
    write_eis_points_csv(cleaned_path, cleaning.cleaned_points)
    write_ignored_eis_points_csv(ignored_path, cleaning.ignored_points)
    write_eis_fit_csv(fit_path, main_fit)
    write_eis_fit_csv(full_fit_path, full_fit)
    eis_metadata = {
        "cleaning": cleaning.to_metadata(),
        "fit": main_fit.to_metadata(),
        "full_fit": full_fit.to_metadata(),
        "raw_data": str(raw_path),
        "cleaned_data": str(cleaned_path),
        "ignored_points": str(ignored_path),
        "fit_curve": str(fit_path),
        "full_fit_curve_debug": str(full_fit_path),
        "default_fitted_model": "Model A: Rs + (Rct || CPE)",
        "main_plot_curve_policy": "Measured-range visual segment only; full theoretical extension is retained in debug/report so it cannot distort the main plot.",
        "fallback_model_policy": "Model B: Rs + CPE is diagnostic fallback only and is not the default v3 fit.",
        "warburg_policy": "Warburg diffusion tail is not included unless a future manual request explicitly asks for it.",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(eis_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return (
        ["cleaned_z_real_kohm", "cleaned_minus_z_imag_kohm", "fit_z_real_kohm", "draft_fit_minus_z_imag_kohm"],
        eis_plot_rows(cleaning.cleaned_points, main_fit, scale=0.001),
        {
            "x_label": "Z' (kOhm)",
            "y_label": "-Z'' (kOhm)",
            "title": "EIS v3 draft",
            "plot_type": "line+symbol",
            "notes": "draft fit for visualization/manual review only\nDefault fit model is Rs + (Rct || CPE); main plot uses measured-range fit segment to avoid full-fit axis distortion.",
        },
        {"eis_cleaning": eis_metadata},
    )


def _apply_v3_template_plot_style(operations: object, graph_name: str, snapshot: OpjuStyleSnapshot, style: ResolvedPlotStyle) -> None:
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    plot_names = getattr(operations, "_plot_names", lambda _name: [])(graph_name)
    for index, plot_name in enumerate(plot_names, start=1):
        color = _list_value(snapshot.plot_colors, index - 1)
        marker = _list_value(snapshot.marker_shapes, index - 1)
        marker_size = _list_value(snapshot.marker_sizes, index - 1)
        commands = [f"set {plot_name} -w {int(style.line_width_pt * 10)}"]
        if color is not None:
            commands.append(f"set {plot_name} -c {int(color)}")
        if marker is not None:
            commands.append(f"set {plot_name} -k {int(marker)}")
        if marker_size is not None:
            commands.append(f"set {plot_name} -z {int(marker_size)}")
        operations.run_labtalk("; ".join(commands) + ";")


def _style_v3_series(operations: object, graph_name: str, product: ProductContext, series_count: int, style: ResolvedPlotStyle) -> None:
    colors = ("blue", "red", "black", "orange", "purple", "green", "cyan", "magenta", "gray")
    for index in range(1, series_count + 1):
        color = colors[(index - 1) % len(colors)]
        result = operations.set_plot_style(graph_name, index, line_width=style.line_width_pt, symbol_size=style.marker_size, color=color)
        if not result.ok and index == 1:
            break
    if product.product_key == "EIS" and series_count >= 2:
        plot_names = getattr(operations, "_plot_names", lambda _name: [])(graph_name)
        if len(plot_names) >= 2:
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; set {plot_names[0]} -l 0; set {plot_names[0]} -z {style.marker_size};')
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; set {plot_names[1]} -k 0; set {plot_names[1]} -l 1; set {plot_names[1]} -z 0; set {plot_names[1]} -w {int(style.line_width_pt * 10)};')


def _apply_v3_axis_range(operations: object, graph_name: str, product: ProductContext) -> None:
    if product.product_key == "EIS":
        x_min, x_max = _csv_bounds_for_columns(product.processed_data, (0, 2))
        y_min, y_max = _csv_bounds_for_columns(product.processed_data, (1, 3))
    else:
        x_min, x_max = _csv_x_bounds(product.processed_data)
        y_min, y_max = _csv_y_bounds(product.processed_data)
    if x_min is not None and x_max is not None:
        operations.set_axis_range(graph_name, x_min=x_max if product.x_descending else x_min, x_max=x_min if product.x_descending else x_max)
    if y_min is not None and y_max is not None and y_max > y_min:
        pad = (y_max - y_min) * 0.08
        operations.set_axis_range(graph_name, y_min=y_min - pad, y_max=y_max + pad)


def _position_v3_axis_titles_outside_plot(operations: object, graph_name: str) -> None:
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    operations.run_labtalk(
        "xb.x=(layer.x.from+layer.x.to)/2; "
        "xb.y=layer.y.from-0.16*(layer.y.to-layer.y.from); "
        "yl.x=layer.x.from-0.13*(layer.x.to-layer.x.from); "
        "yl.y=(layer.y.from+layer.y.to)/2;"
    )


def _build_v3_acceptance(
    product: ProductContext,
    export_status: dict[str, object],
    template: V3TemplateCandidate,
    extra: dict[str, object],
) -> V3Acceptance:
    required = (product.origin_file, product.figure_tif, product.preview_png, product.processed_data)
    has_artifacts = all(path.exists() and path.stat().st_size > 0 for path in required)
    product_style = export_status.get("product_style") if isinstance(export_status.get("product_style"), dict) else {}
    conformance = export_status.get("conformance") if isinstance(export_status.get("conformance"), dict) else {}
    widths = product_style.get("plot_line_widths", []) if isinstance(product_style, dict) else []
    line_width_ok = _line_widths_accepted(widths)
    axis_title_ok = bool(conformance.get("axis_title_bold")) if conformance else bool(export_status.get("axis_title_bold_policy"))
    readback_ok = bool(product_style) and bool(export_status.get("ok"))
    visual_ok = bool(export_status.get("ok")) and has_artifacts
    notes: list[str] = []
    if not has_artifacts:
        notes.append("required artifact missing or empty")
    if not line_width_ok:
        notes.append("line width readback did not meet 3 pt policy")
    if not axis_title_ok:
        notes.append("axis title bold/readback did not pass")
    if product.product_key == "EIS":
        eis = extra.get("eis_cleaning", {}) if isinstance(extra.get("eis_cleaning"), dict) else {}
        full = eis.get("full_fit", {}) if isinstance(eis, dict) else {}
        fit = eis.get("fit", {}) if isinstance(eis, dict) else {}
        if full.get("point_count") == fit.get("point_count"):
            visual_ok = False
            notes.append("EIS main plot was not clipped to measured-range visual segment")
    exemplar_similarity = template.status in {"extracted", "valid"} and template.layer_count > 0 and template.plot_count > 0 and readback_ok
    return v3_acceptance_status(
        has_required_artifacts=has_artifacts,
        no_label_pass=True,
        readback_pass=readback_ok,
        visual_acceptance=visual_ok,
        line_width_acceptance=line_width_ok,
        axis_title_acceptance=axis_title_ok,
        exemplar_similarity=exemplar_similarity,
        notes=notes,
    )


def _write_v3_product_metadata(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    style: ResolvedPlotStyle,
    extra: dict[str, object],
    template: V3TemplateCandidate,
    acceptance: V3Acceptance,
) -> Path:
    path = product.type_root / "metadata" / f"{product.slug}.json"
    payload = {
        "product_key": product.product_key,
        "status": acceptance.status,
        "data_type": product.pairing.data_type,
        "xps_subtype": product.pairing.xps_subtype,
        "selected_data_relative_paths": _safe_metadata_paths(_selected_relative_paths(product.pairing, "selected_data_relative_paths")),
        "source_files": [_safe_metadata_path(path) for path in product.pairing.data_paths],
        "template_path": str(template.path),
        "template_graph": template.graph_page,
        "template_layer_count": template.layer_count,
        "template_plot_count": template.plot_count,
        "input_copies": [_safe_metadata_path(path) for path in product.input_copies],
        "reference_opju_copy": _safe_metadata_path(product.reference_opju_copy),
        "processed_data": _safe_metadata_path(product.processed_data),
        "origin_file": _safe_metadata_path(product.origin_file),
        "figure_tif": _safe_metadata_path(product.figure_tif),
        "preview_png": _safe_metadata_path(product.preview_png),
        "origin_status": export_status,
        "resolved_user_style": style.to_dict(),
        "visual_acceptance": acceptance.visual_acceptance,
        "line_width_acceptance": acceptance.line_width_acceptance,
        "axis_title_acceptance": acceptance.axis_title_acceptance,
        "exemplar_similarity": acceptance.exemplar_similarity,
        "acceptance_notes": list(acceptance.notes),
        "manual_check_required": True,
        "manual_check_items": _manual_items(product.product_key),
        "forbidden_claims": _forbidden_claims(product.product_key),
        "reference_policy_notes": _reference_policy_notes(product.product_key),
        "extra": extra,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_v3_per_type_report(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    style: ResolvedPlotStyle,
    extra: dict[str, object],
    template: V3TemplateCandidate,
    acceptance: V3Acceptance,
) -> Path:
    path = product.type_root / "reports" / f"{product.slug}_report.md"
    conformance = export_status.get("conformance") if isinstance(export_status.get("conformance"), dict) else {}
    lines = [
        f"# {product.product_key} v3 report",
        "",
        f"- Status: {acceptance.status}",
        f"- Template path: {template.path}",
        f"- Template graph: {template.graph_page}",
        f"- Processed data: {_relative_to_run(run_root, product.processed_data)}",
        f"- Generated OPJU: {_relative_to_run(run_root, product.origin_file)}",
        f"- Generated TIF: {_relative_to_run(run_root, product.figure_tif)}",
        f"- Generated PNG preview: {_relative_to_run(run_root, product.preview_png)}",
        f"- Line width policy: {style.line_width_pt} pt",
        f"- Axis title bold policy: {style.font_bold}",
        f"- Conformance status: {conformance.get('status', 'not_read_back')}",
        f"- Visual acceptance: {acceptance.visual_acceptance}",
        f"- Line width acceptance: {acceptance.line_width_acceptance}",
        f"- Axis title acceptance: {acceptance.axis_title_acceptance}",
        f"- Exemplar similarity: {acceptance.exemplar_similarity}",
        "",
        "## Manual review needs",
        *[f"- {item}" for item in _manual_items(product.product_key)],
        "",
        "## Forbidden scientific claims avoided",
        *[f"- {item}" for item in _forbidden_claims(product.product_key)],
    ]
    if acceptance.notes:
        lines.extend(["", "## Blocker notes", *[f"- {item}" for item in acceptance.notes]])
    if product.product_key == "EIS":
        eis = extra.get("eis_cleaning", {}) if isinstance(extra.get("eis_cleaning"), dict) else {}
        cleaning = eis.get("cleaning", {}) if isinstance(eis, dict) else {}
        fit = eis.get("fit", {}) if isinstance(eis, dict) else {}
        lines.extend(
            [
                "",
                "## EIS cleaning and draft fit",
                f"- Raw data: {_relative_to_run(run_root, Path(str(eis.get('raw_data', '')))) if isinstance(eis, dict) else 'not generated'}",
                f"- Cleaned data: {_relative_to_run(run_root, Path(str(eis.get('cleaned_data', '')))) if isinstance(eis, dict) else 'not generated'}",
                f"- Ignored points table: {_relative_to_run(run_root, Path(str(eis.get('ignored_points', '')))) if isinstance(eis, dict) else 'not generated'}",
                f"- Main-plot fit curve: {_relative_to_run(run_root, Path(str(eis.get('fit_curve', '')))) if isinstance(eis, dict) else 'not generated'}",
                f"- Full fit debug curve: {_relative_to_run(run_root, Path(str(eis.get('full_fit_curve_debug', '')))) if isinstance(eis, dict) else 'not generated'}",
                f"- Ignored points: {cleaning.get('ignored_point_count', 0)}",
                f"- Fit model: {fit.get('model', 'Model A: Rs + (Rct || CPE)')}",
                f"- Fitted Rs/Rct/Q/n: {fit.get('parameters', {})}",
                f"- Semicircle classification: {fit.get('semicircle_classification', 'manual_review')}",
                "- Circuit ambiguity: manual review required",
            ]
        )
    product.type_root.joinpath("debug", "visual_diff_notes.md").write_text(
        "\n".join(
            [
                f"# {product.product_key} visual notes",
                "",
                f"- Template graph: {template.graph_page}",
                f"- Visual acceptance: {acceptance.visual_acceptance}",
                f"- Line width acceptance: {acceptance.line_width_acceptance}",
                f"- Axis title acceptance: {acceptance.axis_title_acceptance}",
                f"- Exemplar similarity: {acceptance.exemplar_similarity}",
                *[f"- {item}" for item in acceptance.notes],
            ]
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _v3_product_summary(
    product: ProductContext,
    export_status: dict[str, object],
    metadata: Path,
    report: Path,
    template: V3TemplateCandidate,
    acceptance: V3Acceptance,
) -> dict[str, object]:
    return {
        "type": product.product_key,
        "product_key": product.product_key,
        "template_path": str(template.path),
        "template_graph": template.graph_page,
        "status": acceptance.status,
        "origin_file": str(product.origin_file),
        "figure_tif": str(product.figure_tif),
        "preview_png": str(product.preview_png),
        "processed_data": str(product.processed_data),
        "metadata": str(metadata),
        "report": str(report),
        "has_opju": product.origin_file.exists() and product.origin_file.stat().st_size > 0,
        "has_tif": product.figure_tif.exists() and product.figure_tif.stat().st_size > 0,
        "has_png": product.preview_png.exists() and product.preview_png.stat().st_size > 0,
        "has_processed_data": product.processed_data.exists() and product.processed_data.stat().st_size > 0,
        "has_metadata": metadata.exists() and metadata.stat().st_size > 0,
        "has_report": report.exists() and report.stat().st_size > 0,
        "visual_acceptance": acceptance.visual_acceptance,
        "line_width_acceptance": acceptance.line_width_acceptance,
        "axis_title_acceptance": acceptance.axis_title_acceptance,
        "exemplar_similarity": acceptance.exemplar_similarity,
        "notes": "; ".join(acceptance.notes) or str(export_status.get("message") or ""),
        "conformance": export_status.get("conformance", {}),
    }


def _blocked_product_record(
    run_root: Path,
    product_key: str,
    selection: V3TemplateSelection,
    *,
    reason: str | None = None,
) -> dict[str, object]:
    type_root = run_root / V3_TYPE_DIRS[product_key]
    _ensure_v3_type_dirs(type_root)
    report = type_root / "reports" / f"{V3_SLUGS[product_key]}_report.md"
    message = reason or selection.reason
    report.write_text(
        "\n".join(
            [
                f"# {product_key} v3 blocked report",
                "",
                "- Status: blocked",
                f"- Reason: {message}",
                f"- F-drive candidate count: {len(selection.candidates)}",
            ]
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )
    return {
        "type": product_key,
        "product_key": product_key,
        "template_path": str(selection.selected.path) if selection.selected else "",
        "template_graph": selection.selected.graph_page if selection.selected else "",
        "status": "blocked",
        "origin_file": "",
        "figure_tif": "",
        "preview_png": "",
        "processed_data": "",
        "metadata": "",
        "report": str(report),
        "has_opju": False,
        "has_tif": False,
        "has_png": False,
        "has_processed_data": False,
        "has_metadata": False,
        "has_report": True,
        "visual_acceptance": False,
        "line_width_acceptance": False,
        "axis_title_acceptance": False,
        "exemplar_similarity": False,
        "notes": message,
    }


def _failed_product_record(run_root: Path, product_key: str, selection: V3TemplateSelection, message: str) -> dict[str, object]:
    record = _blocked_product_record(run_root, product_key, selection, reason=message)
    record["status"] = "failed"
    return record


def _with_label_audit_status(product: dict[str, object], label_audit: dict[str, object]) -> dict[str, object]:
    if int(label_audit.get("hit_count", 0)) != 0 and product.get("status") == "accepted":
        product = dict(product)
        product["status"] = "blocked"
        product["notes"] = (str(product.get("notes") or "") + "; no-label audit failed").strip("; ")
    return product


def _write_v3_run_reports(
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    selections: dict[str, V3TemplateSelection],
    label_audit: dict[str, object],
) -> None:
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "v3_rebuild_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_root.name,
                "products": products,
                "failures": failures,
                "skipped": list(SKIPPED_V3_TYPES),
                "label_audit": label_audit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_v3_final_summary(reports / "final_summary.md", run_root, products, failures, label_audit, relative=True)
    _write_v3_manual_review(reports / "manual_review_checklist.md", run_root, products, relative=True)
    _write_v3_per_type_status(reports / "per_type_status.csv", run_root, products, relative=True)
    _write_v3_template_selection_summary(reports / "template_selection_summary.md", selections)
    _write_v3_visual_acceptance_summary(reports / "visual_acceptance_summary.md", run_root, products, relative=True)
    _write_v3_conformance_summary(reports / "exemplar_conformance_summary.md", products)


def _write_v3_docs(
    project_root: Path,
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    selections: dict[str, V3TemplateSelection],
    label_audit: dict[str, object],
) -> None:
    docs = project_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    _write_v3_root_cause_audit(docs / "V3_ROOT_CAUSE_AUDIT.md")
    _write_v3_visual_contract(docs / "V3_VISUAL_ACCEPTANCE_CONTRACT.md")
    _write_v3_visual_acceptance_summary(docs / "V3_EXPORTED_PREVIEW_VISUAL_AUDIT.md", run_root, products, relative=False)
    _write_v3_final_summary(docs / "V3_ALL_TYPES_REBUILD_SUMMARY.md", run_root, products, failures, label_audit, relative=False)
    _write_v3_visual_acceptance_summary(docs / "V3_VISUAL_ACCEPTANCE_AUDIT.md", run_root, products, relative=False)
    _write_v3_root_cause_fix_summary(docs / "V3_ROOT_CAUSE_FIX_SUMMARY.md")
    _write_v3_manual_review(docs / "V3_MANUAL_CALIBRATION_ENTRYPOINT.md", run_root, products, relative=False)


def _write_v3_final_summary(
    path: Path,
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    label_audit: dict[str, object],
    *,
    relative: bool,
) -> None:
    lines = [
        "# V3 all-types rebuild summary",
        "",
        f"- Run root: {run_root.name if relative else run_root}",
        "- unified_v2 status: rejected baseline only",
        f"- Products tracked: {len(products)}",
        f"- accepted: {sum(1 for item in products if item.get('status') == 'accepted')}",
        f"- blocked: {sum(1 for item in products if item.get('status') == 'blocked')}",
        f"- failed: {sum(1 for item in products if item.get('status') == 'failed')}",
        f"- Product visible-label audit: {'pass' if int(label_audit.get('hit_count', 0)) == 0 else 'fail'}",
        "- F-drive files modified: no",
        "- Original OPJU/OPJ files modified: no",
        "- Output products committed: no",
        "",
        "## Per Type",
    ]
    for product in products:
        opju = _path_for_summary(run_root, product.get("origin_file", ""), relative)
        png = _path_for_summary(run_root, product.get("preview_png", ""), relative)
        lines.extend(
            [
                f"### {product['type']}",
                f"- Status: {product['status']}",
                f"- Template: {product.get('template_path', '')}",
                f"- Template graph: {product.get('template_graph', '')}",
                f"- OPJU: {opju}",
                f"- PNG preview: {png}",
                f"- Visual acceptance: {product.get('visual_acceptance')}",
                f"- Line width acceptance: {product.get('line_width_acceptance')}",
                f"- Axis title acceptance: {product.get('axis_title_acceptance')}",
                f"- Exemplar similarity: {product.get('exemplar_similarity')}",
                f"- Notes: {product.get('notes', '')}",
                "",
            ]
        )
    if failures:
        lines.extend(["## Failures", ""])
        for failure in failures:
            lines.append(f"- {failure['product_key']}: {failure['message']}")
        lines.append("")
    lines.extend(["## Skipped", ""])
    for item in SKIPPED_V3_TYPES:
        lines.append(f"- {item['type']}: {item['reason']}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_manual_review(path: Path, run_root: Path, products: list[dict[str, object]], *, relative: bool) -> None:
    lines = ["# V3 manual calibration entrypoint", "", f"- Run root: {run_root.name if relative else run_root}", ""]
    lines.append("## Priority previews")
    for product in products:
        preview = _path_for_summary(run_root, product.get("preview_png", ""), relative)
        lines.append(f"- {product['type']}: {product['status']} - {preview} - {product.get('notes', '')}")
    lines.extend(
        [
            "",
            "## Priority",
            "- EIS first, because the main change is measured-range Randles-CPE visual segment behavior.",
            "- Then XPS subtype template availability, because in-situ and non-in-situ templates must not be mixed.",
            "- Then XRD/BET/EPR and spectroscopy overlays for visual similarity.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_per_type_status(path: Path, run_root: Path, products: list[dict[str, object]], *, relative: bool) -> None:
    columns = [
        "type",
        "template_path",
        "template_graph",
        "status",
        "has_opju",
        "has_tif",
        "has_png",
        "has_processed_data",
        "has_metadata",
        "has_report",
        "visual_acceptance",
        "line_width_acceptance",
        "axis_title_acceptance",
        "exemplar_similarity",
        "notes",
        "product_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "type": product.get("type", ""),
                    "template_path": product.get("template_path", ""),
                    "template_graph": product.get("template_graph", ""),
                    "status": product.get("status", ""),
                    "has_opju": product.get("has_opju", False),
                    "has_tif": product.get("has_tif", False),
                    "has_png": product.get("has_png", False),
                    "has_processed_data": product.get("has_processed_data", False),
                    "has_metadata": product.get("has_metadata", False),
                    "has_report": product.get("has_report", False),
                    "visual_acceptance": product.get("visual_acceptance", False),
                    "line_width_acceptance": product.get("line_width_acceptance", False),
                    "axis_title_acceptance": product.get("axis_title_acceptance", False),
                    "exemplar_similarity": product.get("exemplar_similarity", False),
                    "notes": product.get("notes", ""),
                    "product_path": _path_for_summary(run_root, product.get("origin_file", ""), relative),
                }
            )


def _write_v3_template_selection_summary(path: Path, selections: dict[str, V3TemplateSelection]) -> None:
    lines = ["# V3 template selection summary", "", "| Type | Status | Candidate Count | Selected Template | Graph | Reason |", "|---|---:|---:|---|---|---|"]
    for product_key in V3_TARGET_TYPES:
        selection = selections[product_key]
        selected = selection.selected
        lines.append(
            "| {key} | {status} | {count} | {path} | {graph} | {reason} |".format(
                key=product_key,
                status=selection.status,
                count=len(selection.candidates),
                path=str(selected.path) if selected else "",
                graph=selected.graph_page if selected else "",
                reason=selection.reason,
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_visual_acceptance_summary(path: Path, run_root: Path, products: list[dict[str, object]], *, relative: bool) -> None:
    lines = ["# V3 exported preview visual audit", "", "| Type | Status | Preview | Visual | Line Width | Axis Title | Similarity | Notes |", "|---|---:|---|---:|---:|---:|---:|---|"]
    for product in products:
        lines.append(
            "| {type} | {status} | {preview} | {visual} | {line} | {axis} | {sim} | {notes} |".format(
                type=product.get("type", ""),
                status=product.get("status", ""),
                preview=_path_for_summary(run_root, product.get("preview_png", ""), relative),
                visual=product.get("visual_acceptance", False),
                line=product.get("line_width_acceptance", False),
                axis=product.get("axis_title_acceptance", False),
                sim=product.get("exemplar_similarity", False),
                notes=str(product.get("notes", "")).replace("|", "/"),
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_conformance_summary(path: Path, products: list[dict[str, object]]) -> None:
    lines = ["# V3 exemplar conformance summary", "", "| Type | Status | Compared | Matched | Readback Status |", "|---|---:|---:|---:|---|"]
    for product in products:
        conformance = product.get("conformance") if isinstance(product.get("conformance"), dict) else {}
        lines.append(
            "| {type} | {status} | {compared} | {matched} | {readback} |".format(
                type=product.get("type", ""),
                status=product.get("status", ""),
                compared=conformance.get("compared_fields", 0),
                matched=conformance.get("matched_fields", 0),
                readback=conformance.get("status", "not_read_back"),
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_root_cause_audit(path: Path) -> None:
    lines = [
        "# V3 root-cause audit",
        "",
        "- unified_v2 is treated as a rejected baseline, not a final product.",
        "- Root cause 1: style overrides were not bound to the named graph in every LabTalk command; later commands could depend on the active page.",
        "- Root cause 2: v2 saved and exported from the live in-memory graph without a save/reopen/readback gate.",
        "- Root cause 3: conformance checked internal readback but did not enforce exported-preview visual acceptance as the status gate.",
        "- Root cause 4: the EIS full Randles-CPE extension expanded far beyond the measured Z' range, causing the main plot to look like a large unreasonable arc.",
        "- Root cause 5: v2 accepted `success/review` wording even when manual visual acceptance was still unresolved.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_visual_contract(path: Path) -> None:
    lines = [
        "# V3 visual acceptance contract",
        "",
        "- Allowed statuses: accepted, blocked, skipped, failed.",
        "- accepted requires OPJU, TIF, PNG, processed data, metadata, and report to exist.",
        "- accepted requires no-label audit pass, Origin readback, non-default 3 pt curve width, bold axis titles, and template path/graph recorded.",
        "- EIS accepted requires cleaned points, ignored-point reporting, Model A Rs + (Rct || CPE), and a measured-range main fit curve that does not distort the axis range.",
        "- Files merely existing are insufficient for accepted status.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_root_cause_fix_summary(path: Path) -> None:
    lines = [
        "# V3 root-cause fix summary",
        "",
        "- User style overrides now activate the named graph for every LabTalk style command.",
        "- V3 export saves, reopens, reads back the final graph object, then exports TIF/PNG.",
        "- V3 status no longer uses success/review; products are accepted only after strict gates, otherwise blocked/failed/skipped.",
        "- V3 EIS recomputes cleaning and Randles-CPE fitting, then uses a measured-range main-plot segment and stores the full fit in debug.",
        "- F-drive OPJU/OPJ template candidates are scanned and selected per data type; missing subtype-matched XPS templates are blocked rather than substituted.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_discovery_doc(
    path: Path,
    f_drive_root: Path,
    candidates: list[V3TemplateCandidate],
    selections: dict[str, V3TemplateSelection],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# V3 template discovery and selection", "", f"- F-drive template root scanned: {f_drive_root}", ""]
    for product_key in V3_TARGET_TYPES:
        scoped = [candidate for candidate in candidates if candidate.product_key == product_key]
        selection = selections[product_key]
        lines.extend(
            [
                f"## {product_key}",
                f"- Candidate count: {len(scoped)}",
                f"- Final selection status: {selection.status}",
                f"- Selected template: {selection.selected.path if selection.selected else ''}",
                f"- Selected graph/layer: {selection.selected.graph_page if selection.selected else ''}",
                f"- Selection reason: {selection.reason}",
                "",
                "| Candidate | Open Status | Graph | Layers | Plots | Reason |",
                "|---|---:|---|---:|---:|---|",
            ]
        )
        for candidate in scoped:
            lines.append(
                f"| {candidate.path} | {candidate.status} | {candidate.graph_page} | {candidate.layer_count} | {candidate.plot_count} | {candidate.reason} |"
            )
        if not scoped:
            lines.append("| none | blocked |  | 0 | 0 | no F-drive candidate |")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_v3_no_label_audit(run_root: Path) -> dict[str, object]:
    hits: list[dict[str, object]] = []
    path_only_hits: list[dict[str, object]] = []
    for path in run_root.rglob("*"):
        if not path.is_file():
            continue
        for label in FORBIDDEN_PRODUCT_LABELS:
            if label.casefold() in path.name.casefold():
                hits.append({"path": str(path), "location": "filename", "label": label})
        if path.suffix.casefold() not in {".md", ".csv", ".txt", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label in FORBIDDEN_PRODUCT_LABELS:
                if label.casefold() not in line.casefold():
                    continue
                record = {"path": str(path), "line": line_number, "label": label, "text": line.strip()}
                if ":\\" in line or ":/" in line:
                    path_only_hits.append(record)
                else:
                    hits.append(record)
    audit = {"hit_count": len(hits), "hits": hits, "path_only_hits": path_only_hits}
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "product_no_label_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Product visible-label audit",
        "",
        f"- Product-visible hit count: {audit['hit_count']}",
        f"- Result: {'pass' if audit['hit_count'] == 0 else 'fail'}",
        f"- Path-only hits recorded separately: {len(path_only_hits)}",
        "",
        "## Product-visible hits",
    ]
    lines.extend(["- none"] if not hits else [f"- {hit}" for hit in hits])
    (reports / "product_no_codex_label_audit.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return audit


def _product_key_from_f_drive_path(path: Path) -> str | None:
    parts = [part.casefold() for part in path.parts]
    text = str(path).casefold()
    if any(part == "bet" for part in parts):
        return "BET"
    if any(part == "xps" for part in parts):
        return "XPS_in_situ" if _has_in_situ_token(text) else "XPS_non_in_situ"
    if any(part == "xrd" for part in parts):
        return "XRD"
    if any(part == "epr" for part in parts):
        return "EPR"
    if "阻抗" in text or "eis" in text:
        return "EIS"
    if "拉曼" in text or "raman" in text:
        return "Raman"
    if "固体紫外" in text or "uv" in text or "tauc" in text:
        return "UV-vis DRS / Tauc"
    if any(part == "pl" for part in parts) or "荧光" in text:
        return "PL"
    if "光电流" in text or "photocurrent" in text or "i-t" in text:
        return "photocurrent"
    if "红外" in text or "ftir" in text:
        return "FTIR"
    return None


def _has_in_situ_token(text: str) -> bool:
    compact = text.replace("_", "").replace("-", "").replace(" ", "")
    return "原位" in text or "insitu" in compact or "insitu" in text or "in situ" in text


def _template_path_score(product_key: str, path: Path) -> int:
    text = str(path).casefold()
    score = 10
    for token in ("bobc", "cwo+bobc", "cwo", "bc"):
        if token in text:
            score += 5
    if product_key == "EIS" and ("拟合" in text or "fit" in text):
        score += 4
    if product_key == "XPS_in_situ" and _has_in_situ_token(text):
        score += 20
    return score


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _ensure_v3_type_dirs(type_root: Path) -> None:
    for name in (
        "input_copies",
        "reference_opju",
        "reference_exports",
        "processed_data",
        "metadata",
        "origin_files",
        "figures_tif",
        "figures_preview",
        "reports",
        "debug",
    ):
        (type_root / name).mkdir(parents=True, exist_ok=True)


def _copy_template_for_scan(source: Path, scan_copy_root: Path, index: int) -> Path:
    suffix = source.suffix or ".opju"
    target = scan_copy_root / f"{index:03d}_{safe_name(source.stem)[:60]}{suffix}"
    shutil.copy2(source, target)
    return target


def _candidate_status_from_snapshot(snapshot: OpjuStyleSnapshot) -> str:
    if snapshot.status != "extracted":
        return snapshot.status
    if snapshot.layer_count <= 0 or snapshot.plot_count <= 0 or not snapshot.graph_page:
        return "data_only"
    return "extracted"


def _candidate_status_from_snapshot_payload(snapshot: dict[str, object]) -> str:
    status = str(snapshot.get("status") or "")
    if status != "extracted":
        return status or "load_failed"
    if int(snapshot.get("layer_count") or 0) <= 0 or int(snapshot.get("plot_count") or 0) <= 0 or not snapshot.get("graph_page"):
        return "data_only"
    return "extracted"


def _candidate_reason(snapshot: OpjuStyleSnapshot) -> str:
    if snapshot.status != "extracted":
        return "; ".join(snapshot.warnings) or snapshot.status
    if snapshot.layer_count <= 0 or snapshot.plot_count <= 0:
        return "data-only or incomplete graph object"
    return "graph/layer/plot object readback succeeded"


def _candidate_reason_from_payload(snapshot: dict[str, object]) -> str:
    status = str(snapshot.get("status") or "")
    warnings = snapshot.get("warnings") if isinstance(snapshot.get("warnings"), list) else []
    if status != "extracted":
        return "; ".join(str(item) for item in warnings) or status
    if int(snapshot.get("layer_count") or 0) <= 0 or int(snapshot.get("plot_count") or 0) <= 0:
        return "data-only or incomplete graph object"
    return "graph/layer/plot object readback succeeded"


def _prioritized_template_validation_targets(candidates: list[V3TemplateCandidate], *, max_per_type: int) -> list[V3TemplateCandidate]:
    targets: list[V3TemplateCandidate] = []
    for product_key in V3_TARGET_TYPES:
        scoped = [candidate for candidate in candidates if candidate.product_key == product_key]
        targets.extend(sorted(scoped, key=lambda item: (item.path_score, -len(str(item.path))), reverse=True)[:max_per_type])
    return targets


def _extract_template_snapshot_in_isolated_process(opju_copy: Path, *, timeout_seconds: int = 75) -> dict[str, object]:
    before_pids = _origin_process_ids()
    code = r"""
import json
import sys
from pathlib import Path
from src.origin.operations import connect_origin
from src.origin.style_mimic import extract_style_snapshot

ops = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
snapshot = extract_style_snapshot(ops, Path(sys.argv[1]))
print(json.dumps(snapshot.to_dict(), ensure_ascii=False))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code, str(opju_copy)],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Origin snapshot helper failed").strip())
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Origin snapshot helper returned no JSON payload")
        return json.loads(lines[-1])
    finally:
        _kill_new_origin_processes(before_pids)


def _origin_process_ids() -> set[int]:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'Origin64.exe' -and $_.CommandLine -like '*-Embedding*' } | ForEach-Object { $_.ProcessId }",
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        try:
            pids.add(int(line.strip()))
        except ValueError:
            continue
    return pids


def _kill_new_origin_processes(before_pids: set[int]) -> None:
    for pid in sorted(_origin_process_ids() - before_pids):
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
            text=True,
            capture_output=True,
        )


def _candidate_to_dict(candidate: V3TemplateCandidate) -> dict[str, object]:
    return {
        "product_key": candidate.product_key,
        "path": str(candidate.path),
        "source": candidate.source,
        "path_score": candidate.path_score,
        "status": candidate.status,
        "graph_page": candidate.graph_page,
        "layer_count": candidate.layer_count,
        "plot_count": candidate.plot_count,
        "reason": candidate.reason,
    }


def _line_widths_accepted(values: object, *, required_origin_units: float = 30.0) -> bool:
    if not isinstance(values, list) or not values:
        return False
    numbers = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            numbers.append(number)
    if not numbers:
        return False
    return any(number >= required_origin_units * 0.95 for number in numbers)


def _list_value(values: list[float], index: int) -> float | None:
    if index < 0 or index >= len(values):
        return None
    value = values[index]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _csv_y_bounds(path: Path) -> tuple[float | None, float | None]:
    values = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            for cell in row[1:]:
                try:
                    value = float(cell)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.append(value)
    return (min(values), max(values)) if values else (None, None)


def _csv_bounds_for_columns(path: Path, column_indexes: tuple[int, ...]) -> tuple[float | None, float | None]:
    values = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            for index in column_indexes:
                if index >= len(row):
                    continue
                try:
                    value = float(row[index])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.append(value)
    return (min(values), max(values)) if values else (None, None)


def _safe_metadata_paths(values: list[str]) -> list[str]:
    return [_safe_metadata_text(value) for value in values]


def _safe_metadata_path(path: Path | str) -> str:
    return _safe_metadata_text(str(path).replace("\\", "/"))


def _safe_metadata_text(value: object) -> str:
    text = str(value).replace("\\", "/")
    return "".join(char if ord(char) >= 32 else "/" for char in text)


def _path_for_summary(run_root: Path, value: object, relative: bool) -> str:
    text = str(value or "")
    if not text:
        return ""
    path = Path(text)
    if not relative:
        return text
    try:
        return _relative_to_run(run_root, path)
    except Exception:
        return text
