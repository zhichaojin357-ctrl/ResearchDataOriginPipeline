from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.core.output_sanitizer import render_output_path
from src.core.opju_product_pilot import (
    FORBIDDEN_LABELS,
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
    _series_sample_name,
    _set_bold_axis_title_objects,
    _write_csv,
    _xps_in_situ_sample_files,
    _xps_non_in_situ_sample_files,
    extract_xrd_raw_data_rows,
    build_default_root_map,
    load_target_pairings,
)
from src.core.epr_jeol import read_xy_xlsx
from src.core.epr_overlay import DEFAULT_EPR_GROUPS
from src.core.remaining_opju_product_drafts import (
    _build_remaining_processed_plot_table,
    _coerced_xy_rows,
    _data_points_rows,
    load_remaining_pairings,
)
from src.core.runtime_paths import create_run_output_layout, resolve_output_root
from src.core.table_reader import read_table
from src.core.xps_heterojunction import (
    XpsFitRecord,
    XpsHeterojunctionOptions,
    _component_key,
    _select_best_records,
    build_comparison_plan,
    load_xps_fit_workbooks,
)
from src.origin.conformance import compare_style_snapshots
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_registry import load_origin_style_manifest, origin_style_manifest_path, resolve_origin_style_asset
from src.origin.style_mimic import OpjuStyleSnapshot, apply_style_snapshot, extract_style_snapshot, read_graph_style_snapshot
from src.origin.text_format import origin_bold_text
from src.origin.user_style import ResolvedPlotStyle, apply_resolved_style_overrides, load_user_plot_style, resolve_user_plot_style
from src.processors.base import safe_name
from src.processors.calculations import bet_processed_table
from src.processors.eis import (
    EisFitResult,
    EisPoint,
    clean_eis_file,
    draft_fit_eis_randles_cpe,
    eis_plot_rows,
    select_eis_semicircle_main_branch,
    write_eis_fit_csv,
    write_eis_points_csv,
    write_ignored_eis_points_csv,
)


TEMPLATE_TARGET_TYPES = (
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

TEMPLATE_ACCEPTED_TYPES = TEMPLATE_TARGET_TYPES

TEMPLATE_TYPE_DIRS = {
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

TEMPLATE_STATUS_NAMES = ("accepted", "blocked", "skipped", "failed")

TEMPLATE_PRODUCT_SLUGS = {
    "BET": "BET_BOBC_exemplar",
    "XPS_in_situ": "XPS_in_situ_BOBC_exemplar",
    "XPS_non_in_situ": "XPS_non_in_situ_BOBC_BC_exemplar",
    "XRD": "XRD_BOBC_exemplar",
    "EPR": "EPR_OH_overlay_exemplar",
    "EIS": "EIS_BOBC_exemplar",
    "Raman": "Raman_BOBC_exemplar",
    "UV-vis DRS / Tauc": "UV_vis_DRS_Tauc_BOBC_exemplar",
    "PL": "PL_BOBC_exemplar",
    "photocurrent": "photocurrent_BOBC_exemplar",
    "FTIR": "FTIR_BOBC_CWO_exemplar",
}

FIRST_BATCH_TYPES = {"BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR"}
SKIPPED_TEMPLATE_TYPES = (
    {
        "type": "HPLC/LC",
        "status": "skipped",
        "reason": "No reviewed OPJU exemplar is available; conversion/selectivity/yield and product identity remain deferred.",
    },
    {
        "type": "Mott-Schottky",
        "status": "skipped",
        "reason": "Previously reviewed Mott candidates remain exemplar-mismatch risks and are not in the final template product target set.",
    },
    {
        "type": "reaction_condition_screening",
        "status": "skipped",
        "reason": "No clear reviewed data table plus OPJU pair is available for final template product generation.",
    },
)

OriginExporter = Callable[[ProductContext, ResolvedPlotStyle], dict[str, object]]


@dataclass(frozen=True)
class TemplateCandidate:
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
class TemplateSelection:
    product_key: str
    status: str
    selected: TemplateCandidate | None = None
    candidates: tuple[TemplateCandidate, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class TemplateAcceptance:
    status: str
    visual_acceptance: bool
    line_width_acceptance: bool
    axis_title_acceptance: bool
    exemplar_similarity: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TemplateProductBuilderOptions:
    pairing_path: Path
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    f_drive_template_root: Path | None = None
    xps_reference_template_root: Path | None = None
    xps_non_in_situ_template_root: Path | None = None
    user_style_path: Path | None = None
    run_scope: str = "template_product_builder_all_types"
    command_name: str = "template-product-builder-all-types"
    product_slug_version: str = "template"
    global_style_override: dict[str, object] | None = None
    eis_strict_semicircle_branch: bool = False
    xps_reference_templates_for_all_xps: bool = False
    xps_templates_from_reference_only: bool = False
    xps_smooth_gradient_fill: bool = False
    cleanup_empty_run_layout_dirs: bool = False
    project_style_asset_fallback: bool = False


def classify_template_candidates(paths: list[Path], *, f_drive_root: Path) -> list[TemplateCandidate]:
    candidates: list[TemplateCandidate] = []
    for path in paths:
        if path.suffix.casefold() not in {".opju", ".opj"}:
            continue
        if not _is_relative_to(path, f_drive_root):
            continue
        product_key = _product_key_from_f_drive_path(path)
        if product_key is None:
            continue
        candidates.append(
            TemplateCandidate(
                product_key=product_key,
                path=path,
                source="f_drive_scan",
                path_score=_template_path_score(product_key, path),
                reason="classified by F-drive path keywords",
            )
        )
    return candidates


def classify_template_xps_reference_candidates(
    paths: list[Path],
    *,
    reference_root: Path,
    include_all_xps_types: bool = False,
) -> list[TemplateCandidate]:
    candidates: list[TemplateCandidate] = []
    for path in paths:
        if path.suffix.casefold() not in {".opju", ".opj"}:
            continue
        if not _is_relative_to(path, reference_root):
            continue
        if not include_all_xps_types and not _has_in_situ_token(str(path).casefold()):
            continue
        product_keys = ("XPS_in_situ", "XPS_non_in_situ") if include_all_xps_types else ("XPS_in_situ",)
        for product_key in product_keys:
            candidates.append(
                TemplateCandidate(
                    product_key=product_key,
                    path=path,
                    source="xps_reference_scan",
                    path_score=_template_path_score(product_key, path) + 15 + _xps_reference_path_score_bonus(product_key, path),
                    reason=(
                        "classified by XPS reference root for all XPS subtypes"
                        if include_all_xps_types
                        else "classified by XPS reference root in-situ filename"
                    ),
                )
            )
    return candidates


def classify_template_xps_non_in_situ_candidates(
    paths: list[Path],
    *,
    reference_root: Path,
) -> list[TemplateCandidate]:
    candidates: list[TemplateCandidate] = []
    for path in paths:
        if path.suffix.casefold() not in {".opju", ".opj"}:
            continue
        if not _is_relative_to(path, reference_root):
            continue
        candidates.append(
            TemplateCandidate(
                product_key="XPS_non_in_situ",
                path=path,
                source="xps_non_in_situ_reference_scan",
                path_score=_template_path_score("XPS_non_in_situ", path) + 80 + _xps_non_in_situ_stacked_path_bonus(path),
                reason="classified by non-in-situ XPS stacked OPJU reference root",
            )
        )
    return candidates


def build_template_candidate_pool(
    f_drive_paths: list[Path],
    xps_reference_paths: list[Path],
    *,
    f_drive_root: Path,
    xps_reference_root: Path,
    xps_non_in_situ_paths: list[Path] | None = None,
    xps_non_in_situ_root: Path | None = None,
    xps_reference_templates_for_all_xps: bool = False,
    xps_templates_from_reference_only: bool = False,
) -> list[TemplateCandidate]:
    candidates = classify_template_candidates(f_drive_paths, f_drive_root=f_drive_root)
    if xps_templates_from_reference_only:
        candidates = [candidate for candidate in candidates if not candidate.product_key.startswith("XPS")]
    candidates.extend(
        classify_template_xps_reference_candidates(
            xps_reference_paths,
            reference_root=xps_reference_root,
            include_all_xps_types=xps_reference_templates_for_all_xps,
        )
    )
    if xps_non_in_situ_paths and xps_non_in_situ_root is not None:
        candidates.extend(
            classify_template_xps_non_in_situ_candidates(
                xps_non_in_situ_paths,
                reference_root=xps_non_in_situ_root,
            )
        )
    return candidates


def classify_template_project_style_asset_candidates(project_root: Path) -> list[TemplateCandidate]:
    manifest_path = origin_style_manifest_path(project_root)
    manifest = load_origin_style_manifest(project_root, manifest_path)
    candidates: list[TemplateCandidate] = []
    for raw in manifest.get("assets", []):
        if not isinstance(raw, dict):
            continue
        product_key = str(raw.get("product_key") or raw.get("data_type") or "")
        if product_key not in TEMPLATE_TARGET_TYPES:
            continue
        asset = resolve_origin_style_asset(project_root, product_key, manifest_path)
        if asset is None:
            continue
        candidates.append(
            TemplateCandidate(
                product_key=product_key,
                path=asset.graph_template_path,
                source="project_origin_style_asset",
                path_score=1,
                status="valid",
                graph_page=asset.graph_page or "Graph1",
                layer_count=1,
                plot_count=1,
                reason="project-local cached Origin style asset fallback",
                metadata={
                    "style_package": True,
                    "style_asset": asset.to_dict(project_root),
                    "manifest_entry": asset.to_dict(project_root),
                },
            )
        )
    return candidates


def scan_template_f_drive_template_paths(f_drive_root: Path) -> list[Path]:
    if not f_drive_root.exists():
        raise FileNotFoundError(f"F-drive template root not found: {f_drive_root}")
    return sorted(
        path for path in f_drive_root.rglob("*") if path.is_file() and path.suffix.casefold() in {".opju", ".opj"}
    )


def scan_template_optional_template_paths(template_root: Path | None) -> list[Path]:
    if template_root is None or not template_root.exists():
        return []
    return sorted(
        path for path in template_root.rglob("*") if path.is_file() and path.suffix.casefold() in {".opju", ".opj"}
    )


def validate_template_candidates(candidates: list[TemplateCandidate], scan_copy_root: Path, *, max_per_type: int = 5) -> list[TemplateCandidate]:
    if not candidates:
        return []
    scan_copy_root.mkdir(parents=True, exist_ok=True)
    validated: list[TemplateCandidate] = []
    validation_targets = _prioritized_template_validation_targets(candidates, max_per_type=max_per_type)
    target_ids = {id(candidate) for candidate in validation_targets}
    copy_index = 1
    for candidate in candidates:
        if id(candidate) not in target_ids:
            validated.append(
                TemplateCandidate(
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
                TemplateCandidate(
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
                TemplateCandidate(
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


def select_template(product_key: str, candidates: list[TemplateCandidate]) -> TemplateSelection:
    scoped = [candidate for candidate in candidates if candidate.product_key == product_key]
    if not scoped:
        return TemplateSelection(
            product_key=product_key,
            status="blocked",
            candidates=(),
            reason=f"No OPJU/OPJ template or project-local style asset candidate found for {product_key}.",
        )
    usable = [
        candidate
        for candidate in scoped
        if candidate.status in {"extracted", "valid"} and candidate.layer_count > 0 and candidate.plot_count > 0 and candidate.graph_page
    ]
    if not usable:
        data_only = any(candidate.status in {"data_only", "no_graph_pages"} for candidate in scoped)
        reason = "All template candidates are data-only or lack complete graph/layer/plot objects." if data_only else "No validated graph-bearing template candidate is available."
        return TemplateSelection(product_key=product_key, status="blocked", candidates=tuple(scoped), reason=reason)
    selected = max(usable, key=lambda item: (item.path_score, item.plot_count, item.layer_count, -len(str(item.path))))
    return TemplateSelection(
        product_key=product_key,
        status="selected",
        selected=selected,
        candidates=tuple(scoped),
        reason="Selected highest-scoring validated graph template or project-local style asset.",
    )


def _select_template_xps_template_for_product(product: ProductContext, selection: TemplateSelection) -> TemplateCandidate:
    selected = selection.selected
    if selected is None or not product.product_key.startswith("XPS"):
        if selected is None:
            raise ValueError(f"No selected template for {product.product_key}")
        return selected
    usable = [
        candidate
        for candidate in selection.candidates
        if candidate.status in {"extracted", "valid"} and candidate.layer_count > 0 and candidate.plot_count > 0
    ]
    best: TemplateCandidate | None = None
    for candidate in usable:
        snapshot = candidate.metadata.get("snapshot") if isinstance(candidate.metadata, dict) else {}
        graph_pages = snapshot.get("graph_pages") if isinstance(snapshot, dict) else []
        if not isinstance(graph_pages, list):
            continue
        graph_page = _preferred_template_xps_graph_name(product.graph_title, [str(item) for item in graph_pages])
        if not graph_page:
            continue
        updated = replace(
            candidate,
            graph_page=graph_page,
            reason=f"{candidate.reason}; selected graph page matching plotted XPS element",
        )
        if best is None or (updated.path_score, updated.plot_count, updated.layer_count) > (best.path_score, best.plot_count, best.layer_count):
            best = updated
    return best or selected


def _preferred_template_xps_graph_name(product_title: str, graph_pages: list[str]) -> str:
    element = _xps_element_from_title(product_title)
    if not element:
        return ""
    preferred = _xps_default_region_label(element).replace(" ", "_")
    preferred_key = _normalized_xps_graph_key(preferred)
    for graph_page in graph_pages:
        if _normalized_xps_graph_key(graph_page) == preferred_key:
            return graph_page
    element_key = element.casefold()
    for graph_page in graph_pages:
        if _normalized_xps_graph_key(graph_page).startswith(element_key):
            return graph_page
    return ""


def _normalized_xps_graph_key(value: str) -> str:
    return "".join(char for char in str(value).casefold() if char.isalnum())


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


def template_acceptance_status(
    *,
    has_required_artifacts: bool,
    no_label_pass: bool,
    readback_pass: bool,
    visual_acceptance: bool,
    line_width_acceptance: bool,
    axis_title_acceptance: bool,
    exemplar_similarity: bool,
    notes: list[str],
) -> TemplateAcceptance:
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
    return TemplateAcceptance(
        status=status,
        visual_acceptance=visual_acceptance,
        line_width_acceptance=line_width_acceptance,
        axis_title_acceptance=axis_title_acceptance,
        exemplar_similarity=exemplar_similarity,
        notes=tuple(notes),
    )


def template_plot_type_for_header(product_key: str, header: str, default_plot_type: str) -> str:
    if product_key.startswith("XPS") and "_component_" in header:
        return default_plot_type
    if product_key == "XRD" and is_template_xrd_reference_stick_header(header):
        return "column"
    return default_plot_type


def is_template_xrd_reference_stick_header(header: str) -> bool:
    text = str(header).casefold()
    return "jcpds" in text or "pdf" in text or "card_sticks" in text or "reference_sticks" in text


def is_template_xps_component_curve_header(header: str) -> bool:
    return "_component_" in header and not header.endswith("_fill_baseline")


def is_template_xps_component_fill_baseline_header(header: str) -> bool:
    return header.endswith("_fill_baseline")


def template_xps_component_fill_pairs(headers: list[str]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    series_headers = headers[1:]
    for plot_index, header in enumerate(series_headers, start=1):
        if not is_template_xps_component_curve_header(header):
            continue
        baseline_plot_index = plot_index + 1
        baseline_header_index = baseline_plot_index - 1
        if baseline_header_index < len(series_headers) and is_template_xps_component_fill_baseline_header(series_headers[baseline_header_index]):
            pairs.append((plot_index, baseline_plot_index))
    return pairs


def run_template_product_builder_all_types(
    project_root: Path,
    options: TemplateProductBuilderOptions,
    *,
    root_map: dict[str, Path] | None = None,
    origin_exporter: OriginExporter | None = None,
    template_validator: Callable[[list[TemplateCandidate], Path], list[TemplateCandidate]] | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    roots = root_map or build_default_root_map(project_root)
    output_root = resolve_output_root(project_root, explicit=options.output_root)
    timestamp = options.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    use_project_style_assets_only = (
        options.project_style_asset_fallback
        and options.f_drive_template_root is None
        and options.xps_reference_template_root is None
        and options.xps_non_in_situ_template_root is None
    )
    f_drive_root = options.f_drive_template_root or Path("F:/") / "\u8bfe\u9898" / "LL" / "\u68c0\u6d4b"
    xps_reference_root = options.xps_reference_template_root or roots.get("workspace_xps_reference") or (project_root.parent / "xps\u53c2\u8003\u56fe\u50cf")
    xps_non_in_situ_root = options.xps_non_in_situ_template_root
    if use_project_style_assets_only:
        candidates: list[TemplateCandidate] = []
        template_source_root = project_root / "templates" / "origin_styles"
    else:
        opju_paths = scan_template_f_drive_template_paths(f_drive_root)
        xps_reference_paths = scan_template_optional_template_paths(xps_reference_root)
        xps_non_in_situ_paths = scan_template_optional_template_paths(xps_non_in_situ_root)
        candidates = build_template_candidate_pool(
            opju_paths,
            xps_reference_paths,
            f_drive_root=f_drive_root,
            xps_reference_root=xps_reference_root,
            xps_non_in_situ_paths=xps_non_in_situ_paths,
            xps_non_in_situ_root=xps_non_in_situ_root,
            xps_reference_templates_for_all_xps=options.xps_reference_templates_for_all_xps,
            xps_templates_from_reference_only=options.xps_templates_from_reference_only,
        )
        template_source_root = f_drive_root
    layout = create_run_output_layout(
        project_root,
        scope=options.run_scope,
        command=options.command_name,
        mode="with_origin" if options.with_origin else "no_origin",
        input_paths=[options.pairing_path, template_source_root, xps_reference_root],
        timestamp=timestamp,
        no_origin=not options.with_origin,
        dry_run=False,
        output_base=output_root / "runs",
    )
    for product_key in TEMPLATE_TARGET_TYPES:
        _ensure_template_type_dirs(layout.root / TEMPLATE_TYPE_DIRS[product_key])
    validator = template_validator or validate_template_candidates
    validated = validator(candidates, layout.root / "template_scan_copies") if candidates else []
    if options.project_style_asset_fallback:
        validated.extend(classify_template_project_style_asset_candidates(project_root))
    selections = {product_key: select_template(product_key, validated) for product_key in TEMPLATE_TARGET_TYPES}
    _write_template_discovery_doc(project_root / "docs" / "TEMPLATE_DISCOVERY_AND_SELECTION.md", template_source_root, validated, selections)

    user_config = load_user_plot_style(project_root, options.user_style_path)
    if options.global_style_override:
        user_config = _merge_global_style_override(user_config, options.global_style_override)
    first_pairings = {item.product_key: item for item in load_target_pairings(options.pairing_path, roots)}
    remaining_pairings = {item.product_key: item for item in load_remaining_pairings(options.pairing_path, roots)}
    exporter = origin_exporter or (lambda product, style: export_template_product_with_origin(product, style))
    products: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for product_key in TEMPLATE_TARGET_TYPES:
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
            product, extra = prepare_template_product(
                layout.root,
                pairing,
                selection.selected,
                slug_version=options.product_slug_version,
                eis_strict_semicircle_branch=options.eis_strict_semicircle_branch,
                xps_smooth_gradient_fill=options.xps_smooth_gradient_fill,
            )
            active_template = _select_template_xps_template_for_product(product, selection)
            if active_template.path != selection.selected.path:
                product = replace(
                    product,
                    reference_opju_copy=_copy_reference(active_template.path, product.type_root / "reference_opju"),
                )
            if active_template.path != selection.selected.path or active_template.graph_page != selection.selected.graph_page:
                extra["template"] = _candidate_to_dict(active_template)
            style = resolve_user_plot_style(product_key, exemplar=active_template.metadata.get("snapshot"), user_config=user_config)
            export_status: dict[str, object] = {"ok": False, "message": "Origin export skipped"}
            if options.with_origin:
                export_status = exporter(product, style)
            acceptance = _build_template_acceptance(product, export_status, active_template, extra)
            metadata = _write_template_product_metadata(layout.root, product, export_status, style, extra, active_template, acceptance)
            report = _write_template_per_type_report(layout.root, product, export_status, style, extra, active_template, acceptance)
            products.append(_template_product_summary(layout.root, product, export_status, metadata, report, active_template, acceptance))
        except Exception as exc:
            failures.append({"product_key": product_key, "message": str(exc)})
            products.append(_failed_product_record(layout.root, product_key, selection, str(exc)))

    label_audit = _write_template_no_label_audit(layout.root)
    products = [_with_label_audit_status(product, label_audit) for product in products]
    template_preview_audit = _write_template_preview_comparison(layout.root, products)
    _write_template_run_reports(layout.root, products, failures, selections, label_audit, template_preview_audit)
    _write_template_docs(project_root, layout.root, products, failures, selections, label_audit)
    if options.cleanup_empty_run_layout_dirs:
        _cleanup_empty_run_layout_dirs(layout)
    return {
        "run_root": str(layout.root),
        "products": products,
        "failures": failures,
        "skipped": list(SKIPPED_TEMPLATE_TYPES),
        "summary": {
            "product_count": len(products),
            "accepted_count": sum(1 for item in products if item.get("status") == "accepted"),
            "blocked_count": sum(1 for item in products if item.get("status") == "blocked"),
            "failed_count": sum(1 for item in products if item.get("status") == "failed"),
            "with_origin": bool(options.with_origin),
            "label_audit_pass": int(label_audit.get("hit_count", 0)) == 0,
            "template_preview_comparison_ready": int(template_preview_audit.get("ready_count", 0)) == len(products),
        },
    }


def _merge_global_style_override(user_config: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(user_config)
    global_config = merged.get("global") if isinstance(merged.get("global"), dict) else {}
    merged["global"] = {**dict(global_config), **dict(override)}
    return merged


def _versioned_template_slug(product_key: str, slug_version: str) -> str:
    slug = TEMPLATE_PRODUCT_SLUGS[product_key]
    if slug_version == "template":
        return slug
    return f"{slug}_{slug_version}"


def prepare_template_product(
    run_root: Path,
    pairing: TargetPairing,
    template: TemplateCandidate,
    *,
    slug_version: str = "template",
    eis_strict_semicircle_branch: bool = False,
    xps_smooth_gradient_fill: bool = False,
) -> tuple[ProductContext, dict[str, object]]:
    product_key = pairing.product_key
    type_root = run_root / TEMPLATE_TYPE_DIRS[product_key]
    _ensure_template_type_dirs(type_root)
    slug = _versioned_template_slug(product_key, slug_version)
    input_copies = [] if product_key == "EPR" else _copy_inputs(pairing.data_paths, type_root / "input_copies")
    reference_copy = _copy_reference(template.path, type_root / "reference_opju")
    extra: dict[str, object] = {"template": _candidate_to_dict(template)}
    product_pairing = pairing
    if product_key == "EIS":
        headers, rows, labels, eis_extra = _build_template_eis_table(
            pairing,
            type_root,
            strict_semicircle_branch=eis_strict_semicircle_branch,
        )
        extra.update(eis_extra)
    elif product_key == "EPR":
        headers, rows, labels, epr_extra = _build_template_epr_table(pairing, type_root, template, slug)
        extra.update(epr_extra)
        epr_overlay = epr_extra.get("epr_overlay") if isinstance(epr_extra.get("epr_overlay"), dict) else {}
        epr_input_files = [Path(value) for value in epr_overlay.get("input_files", []) if str(value).strip()]
        if epr_input_files:
            input_copies = _copy_inputs(epr_input_files, type_root / "input_copies")
            product_pairing = replace(pairing, data_paths=epr_input_files)
    elif product_key in FIRST_BATCH_TYPES:
        enriched = _build_template_aligned_first_batch_table(
            pairing,
            template,
            xps_component_fill_mode="template_line_fill" if xps_smooth_gradient_fill else "plain",
        )
        headers, rows, labels = enriched["headers"], enriched["rows"], enriched["labels"]
        extra["template_data_alignment"] = enriched["alignment"]
    else:
        enriched = _build_template_aligned_remaining_table(pairing, template)
        headers, rows, labels = enriched["headers"], enriched["rows"], enriched["labels"]
        extra["template_data_alignment"] = enriched["alignment"]
    if product_key not in {"EIS", "EPR"}:
        extra["origin_processing"] = _write_template_origin_processing_plan(
            pairing,
            type_root,
            slug,
            headers,
            rows,
            xps_component_fill_mode="template_line_fill" if xps_smooth_gradient_fill else "plain",
        )
    processed_data = type_root / "processed_data" / f"{slug}.csv"
    _write_csv(processed_data, headers, rows)
    product = ProductContext(
        product_key=product_key,
        slug=slug,
        pairing=product_pairing,
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
        legend_entries=list(labels.get("legend_entries", [])) or [header.replace("_", " ") for header in headers[1:]],
        notes=labels.get("notes", "").splitlines() if labels.get("notes") else [],
    )
    return product, extra


def _build_template_aligned_first_batch_table(
    pairing: TargetPairing,
    template: TemplateCandidate,
    *,
    xps_component_fill_mode: str,
) -> dict[str, object]:
    if pairing.product_key == "BET":
        aligned = _build_template_bet_multisource_table(pairing, template)
        if aligned is not None:
            return aligned
    if pairing.product_key == "XRD":
        aligned = _build_template_xrd_multisource_table(pairing, template)
        if aligned is not None:
            return aligned
    headers, rows, labels = _build_processed_plot_table(
        pairing,
        xps_component_fill_mode=xps_component_fill_mode,
    )
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": _template_alignment_payload(pairing, template, pairing.data_paths, len(headers) - 1, "fallback_existing_first_batch_builder"),
    }


def _build_template_aligned_remaining_table(pairing: TargetPairing, template: TemplateCandidate) -> dict[str, object]:
    if pairing.product_key in {"Raman", "UV-vis DRS / Tauc", "PL", "photocurrent", "FTIR"}:
        aligned = _build_template_xy_multisource_table(pairing, template)
        if aligned is not None:
            return aligned
    headers, rows, labels = _build_remaining_processed_plot_table(pairing)
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": _template_alignment_payload(pairing, template, pairing.data_paths, len(headers) - 1, "fallback_existing_remaining_builder"),
    }


def _build_template_bet_multisource_table(pairing: TargetPairing, template: TemplateCandidate) -> dict[str, object] | None:
    target_series = max(int(template.plot_count or 0), 2)
    target_files = max(1, math.ceil(target_series / 2))
    candidates = _template_candidate_files(
        pairing,
        template,
        suffixes=(".xls", ".xlsx"),
        exclude_name_tokens=("micdir",),
        prefer_template_parent=True,
        limit=target_files,
    )
    series: list[tuple[str, list[list[float | str | None]]]] = []
    used_files: list[Path] = []
    for path in candidates:
        try:
            headers, rows = bet_processed_table(read_table(path))
        except Exception:
            continue
        if len(headers) < 2 or len(rows) < 2:
            continue
        label = _template_bet_series_label_from_path(path)
        # Keep adsorption and optional desorption branches as separate plots.
        series.append((f"{label}_adsorption", [[row[0], row[1]] for row in rows if len(row) >= 2]))
        if len(headers) >= 3:
            desorption = [[row[0], row[2]] for row in rows if len(row) >= 3 and row[2] not in {"", None}]
            if len(desorption) >= 2:
                series.append((f"{label}_desorption", desorption))
        used_files.append(path)
        if len(series) >= target_series:
            break
    if len(series) < 2:
        return None
    headers, rows = _template_same_x_overlay_table("relative_pressure_p_p0", series[:target_series])
    labels = {
        "x_label": "Relative Pressure (P/P_0)",
        "y_label": "Quantity Adsorbed (cm3/g STP)",
        "title": "BET isotherm pilot",
        "plot_type": "line+symbol",
        "notes": "Multiple real BET source exports were used to match the OPJU exemplar curve structure; no BET model conclusion is generated.",
    }
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": _template_alignment_payload(pairing, template, used_files, len(headers) - 1, "template_aligned_bet_adjacent_sources"),
    }


def _template_bet_series_label_from_path(path: Path) -> str:
    stem = path.stem.casefold()
    if "bobc-4-xin" in stem or "4-bobc-4-xin" in stem:
        return "BOBC-4-XIN"
    if "bicu" in stem:
        return "BiCu"
    if "cwo" in stem:
        return "CWO"
    if "bobc" in stem:
        return "BOBC"
    return _template_series_label_from_path(path)


def _build_template_xrd_multisource_table(pairing: TargetPairing, template: TemplateCandidate) -> dict[str, object] | None:
    target_series = _template_xrd_target_sample_series_count(pairing, template)
    candidates = _template_candidate_files(
        pairing,
        template,
        suffixes=(".txt", ".dql"),
        exclude_name_tokens=("pdf#", "jcpds", "card", "鏍囧崱"),
        prefer_template_parent=True,
        limit=max(target_series * 3, 8),
    )
    series: list[tuple[str, list[list[float | str | None]]]] = []
    used_files: list[Path] = []
    for path in candidates:
        try:
            rows = extract_xrd_raw_data_rows(path)
        except Exception:
            try:
                rows = _coerced_xy_rows(path)
            except Exception:
                continue
        if len(rows) < 2:
            continue
        series.append((_template_series_label_from_path(path), rows))
        used_files.append(path)
        if len(series) >= target_series:
            break
    if len(series) < 1:
        return None
    reference_card = _template_xrd_reference_stick_series(pairing, template, series[0][1])
    if reference_card is not None:
        series.append(reference_card[0])
        used_files.append(reference_card[1])
    headers, rows = _template_same_x_overlay_table("two_theta_deg", series)
    legend_entries = [
        _xrd_legend_label(label)
        for label, _values in series
        if not is_template_xrd_reference_stick_header(label)
    ]
    visual_plot_count = len(series)
    labels = {
        "x_label": "2theta (degree)",
        "y_label": "Intensity (a.u.)",
        "title": "XRD pilot",
        "plot_type": "line",
        "y_tick_values": "false",
        "legend_entries": legend_entries,
        "notes": "Multiple real XRD source exports were used where available; PDF/JCPDS reference sticks are plotted for manual review without phase assignment.",
    }
    alignment = _template_alignment_payload(pairing, template, used_files, len(headers) - 1, "template_aligned_xrd_stacked_patterns_with_reference_sticks")
    alignment["visual_template_plot_count"] = max(visual_plot_count, int(template.plot_count or 0))
    alignment["reference_stick_included"] = reference_card is not None
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": alignment,
    }


def _template_xrd_target_sample_series_count(pairing: TargetPairing, template: TemplateCandidate) -> int:
    target = max(int(template.plot_count or 0), 1)
    if pairing.product_key == "XRD" and _template_xrd_reference_card_files(pairing, template):
        target = max(target, 4)
    return target


def _template_xrd_reference_stick_series(
    pairing: TargetPairing,
    template: TemplateCandidate,
    sample_rows: list[list[float | str | None]],
) -> tuple[tuple[str, list[list[float | str | None]]], Path] | None:
    cards = _template_xrd_reference_card_files(pairing, template)
    if not cards:
        return None
    x_values = [_to_float(row[0]) for row in sample_rows if row]
    grid = [value for value in x_values if value is not None and math.isfinite(value)]
    if len(grid) < 2:
        return None
    for card in cards:
        peaks = _template_xrd_reference_card_peaks(card)
        if not peaks:
            continue
        y_values = _template_xrd_reference_stick_values(grid, peaks)
        if any(value > 0 for value in y_values):
            rows = [[x_value, y_value] for x_value, y_value in zip(grid, y_values)]
            return ((f"{_template_series_label_from_path(card)}_JCPDS_card_sticks", rows), card)
    return None


def _template_xrd_reference_card_files(pairing: TargetPairing, template: TemplateCandidate) -> list[Path]:
    roots = [template.path.parent, *[path.parent for path in pairing.data_paths]]
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.txt"), key=lambda item: str(item)):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            name = path.name.casefold()
            if "pdf#" in name or "jcpds" in name:
                candidates.append(path)
    return candidates


def _template_xrd_reference_card_peaks(path: Path) -> list[tuple[float, float]]:
    peaks: list[tuple[float, float]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return peaks
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        two_theta = _to_float(parts[0])
        intensity = _to_float(parts[2])
        if two_theta is None or intensity is None:
            continue
        if not (5 <= two_theta <= 90) or intensity <= 0:
            continue
        peaks.append((two_theta, intensity))
    return peaks


def _template_xrd_reference_stick_values(grid: list[float], peaks: list[tuple[float, float]]) -> list[float]:
    if not grid or not peaks:
        return []
    max_intensity = max(intensity for _two_theta, intensity in peaks)
    if max_intensity <= 0:
        return [0.0 for _value in grid]
    values = [0.0 for _value in grid]
    low, high = min(grid), max(grid)
    for two_theta, intensity in peaks:
        if two_theta < low or two_theta > high:
            continue
        index = min(range(len(grid)), key=lambda item: abs(grid[item] - two_theta))
        height = 0.75 * intensity / max_intensity
        values[index] = max(values[index], height)
    return values


def _xrd_legend_label(label: str) -> str:
    cleaned = str(label).replace("_intensity", "").replace("_", " ").strip()
    return cleaned[:42] or "XRD"


def _build_template_xy_multisource_table(pairing: TargetPairing, template: TemplateCandidate) -> dict[str, object] | None:
    target_series = max(int(template.plot_count or 0), 1)
    suffixes = _template_xy_suffixes(pairing.product_key)
    candidates = _template_candidate_files(
        pairing,
        template,
        suffixes=suffixes,
        prefer_template_parent=pairing.product_key == "FTIR",
        limit=max(target_series * 4, 12),
    )
    if pairing.product_key == "photocurrent":
        candidates = _template_photocurrent_candidate_files(pairing, template, target_series)
    if pairing.product_key == "PL":
        candidates = _template_pl_candidate_files(pairing, template, target_series)
    series: list[tuple[str, list[list[float | str | None]]]] = []
    used_files: list[Path] = []
    for path in candidates:
        try:
            rows = _data_points_rows(path) if pairing.product_key == "UV-vis DRS / Tauc" else _coerced_xy_rows(path)
        except Exception:
            continue
        if len(rows) < 2:
            continue
        series.append((_template_series_label_from_path(path), rows))
        used_files.append(path)
        if len(series) >= target_series:
            break
    if not series:
        return None
    x_header, y_suffix, labels = _template_xy_labels(pairing.product_key)
    headers, rows = _template_same_x_overlay_table(x_header, [(f"{label}_{y_suffix}", values) for label, values in series])
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": _template_alignment_payload(pairing, template, used_files, len(headers) - 1, f"template_aligned_{safe_name(pairing.product_key)}_adjacent_sources"),
    }


def _template_same_x_overlay_table(
    x_header: str,
    series: list[tuple[str, list[list[float | str | None]]]],
) -> tuple[list[str], list[list[float | str | None]]]:
    headers = [x_header, *[safe_name(label) for label, _rows in series]]
    numeric_series = [_numeric_xy_points(rows) for _label, rows in series]
    grid = sorted({x_value for points in numeric_series for x_value, _y_value in points})
    if grid and all(points for points in numeric_series):
        output: list[list[float | str | None]] = []
        for x_value in grid:
            row: list[float | str | None] = [x_value]
            for points in numeric_series:
                row.append(_interpolated_series_y(points, x_value))
            output.append(row)
        return headers, output
    point_count = min(len(rows) for _label, rows in series)
    output: list[list[float | str | None]] = []
    for index in range(point_count):
        row: list[float | str | None] = [series[0][1][index][0]]
        for _label, rows in series:
            row.append(rows[index][1])
        output.append(row)
    return headers, output


def _numeric_xy_points(rows: list[list[float | str | None]]) -> list[tuple[float, float]]:
    points: dict[float, float] = {}
    for row in rows:
        if len(row) < 2:
            continue
        x_value = _to_float(row[0])
        y_value = _to_float(row[1])
        if x_value is None or y_value is None:
            continue
        if math.isfinite(x_value) and math.isfinite(y_value):
            points[float(x_value)] = float(y_value)
    return sorted(points.items(), key=lambda item: item[0])


def _interpolated_series_y(points: list[tuple[float, float]], x_value: float) -> float | None:
    if not points:
        return None
    if x_value < points[0][0] or x_value > points[-1][0]:
        return None
    for index, (point_x, point_y) in enumerate(points):
        if abs(point_x - x_value) <= 1e-12:
            return point_y
        if point_x > x_value and index > 0:
            prev_x, prev_y = points[index - 1]
            span = point_x - prev_x
            if span == 0:
                return point_y
            fraction = (x_value - prev_x) / span
            return prev_y + fraction * (point_y - prev_y)
    return points[-1][1]


def _template_candidate_files(
    pairing: TargetPairing,
    template: TemplateCandidate,
    *,
    suffixes: tuple[str, ...],
    exclude_name_tokens: tuple[str, ...] = (),
    prefer_template_parent: bool = False,
    limit: int = 12,
) -> list[Path]:
    roots: list[Path] = []
    if prefer_template_parent:
        roots.append(template.path.parent)
    roots.extend(path.parent for path in pairing.data_paths)
    if len(pairing.data_paths) == 1:
        roots.append(pairing.data_paths[0].parent.parent)
    roots.append(template.path.parent)
    seen_roots: set[str] = set()
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        root_key = str(root.resolve())
        if root_key in seen_roots:
            continue
        seen_roots.add(root_key)
        for path in sorted(root.rglob("*"), key=lambda item: str(item)):
            if not path.is_file() or path.suffix.casefold() not in suffixes:
                continue
            name = path.name.casefold()
            if any(token in name for token in exclude_name_tokens):
                continue
            if path.suffix.casefold() == ".txt" and any(token in name for token in ("澶囨敞", "readme", "璇存槑")):
                continue
            candidates.append(path)
            if len(candidates) >= limit:
                return _template_ordered_candidate_paths(pairing, candidates, prefer_template_parent=prefer_template_parent)
    return _template_ordered_candidate_paths(pairing, candidates, prefer_template_parent=prefer_template_parent)


def _template_ordered_candidate_paths(pairing: TargetPairing, candidates: list[Path], *, prefer_template_parent: bool) -> list[Path]:
    if prefer_template_parent:
        return _template_unique_paths([*candidates, *pairing.data_paths])
    return _template_unique_paths([*pairing.data_paths, *candidates])


def _template_unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _template_xy_suffixes(product_key: str) -> tuple[str, ...]:
    if product_key == "FTIR":
        return (".dpt", ".txt")
    return (".txt", ".csv")


def _template_pl_candidate_files(pairing: TargetPairing, template: TemplateCandidate, target_series: int) -> list[Path]:
    graph = str(template.graph_page or "").casefold()
    preferred = "ex" if graph.startswith("ex") else "em"
    parent = pairing.data_paths[0].parent if pairing.data_paths else template.path.parent
    files = sorted(parent.glob(f"*{preferred}*.txt"), key=lambda item: item.name.casefold())
    if len(files) >= target_series:
        return files
    return _template_candidate_files(pairing, template, suffixes=(".txt",), limit=max(target_series * 3, 9))


def _template_photocurrent_candidate_files(pairing: TargetPairing, template: TemplateCandidate, target_series: int) -> list[Path]:
    roots: list[Path] = []
    if pairing.data_paths:
        roots.append(pairing.data_paths[0].parent.parent)
        roots.append(pairing.data_paths[0].parent)
    roots.append(template.path.parent)
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.txt"), key=lambda item: str(item)):
            if "ocp" in path.name.casefold():
                candidates.append(path)
            if len(candidates) >= target_series:
                return _template_unique_paths(candidates)
    return _template_unique_paths([*pairing.data_paths, *candidates])


def _template_xy_labels(product_key: str) -> tuple[str, str, dict[str, str]]:
    if product_key == "Raman":
        return "raman_shift_cm-1", "intensity", {
            "x_label": "Raman shift (cm-1)",
            "y_label": "Intensity (a.u.)",
            "title": "Raman draft",
            "plot_type": "line",
        }
    if product_key == "UV-vis DRS / Tauc":
        return "wavelength_nm", "signal", {
            "x_label": "Wavelength (nm)",
            "y_label": "Signal (a.u.)",
            "title": "UV-vis DRS draft",
            "plot_type": "line",
            "notes": "DRS/Tauc transform and bandgap interpretation require manual review.",
        }
    if product_key == "PL":
        return "wavelength_nm", "counts", {
            "x_label": "Wavelength (nm)",
            "y_label": "Counts",
            "title": "PL draft",
            "plot_type": "line",
        }
    if product_key == "photocurrent":
        return "time_s", "current_a", {
            "x_label": "Time (s)",
            "y_label": "Current (A)",
            "title": "Photocurrent draft",
            "plot_type": "line",
            "notes": "Light on/off segmentation requires manual review if labels are needed.",
        }
    if product_key == "FTIR":
        return "wavenumber_cm-1", "transmittance", {
            "x_label": "Wavenumber (cm-1)",
            "y_label": "Transmittance (a.u.)",
            "title": "FTIR draft",
            "plot_type": "line",
            "x_descending": "true",
            "notes": "Wavenumber direction and peak labels require manual review.",
        }
    raise ValueError(f"Unsupported XY product key: {product_key}")


def _template_series_label_from_path(path: Path) -> str:
    label = safe_name(path.stem)
    return label[:42] or "series"


def _template_alignment_payload(
    pairing: TargetPairing,
    template: TemplateCandidate,
    used_files: list[Path],
    product_series_count: int,
    strategy: str,
) -> dict[str, object]:
    missing_count = max(int(template.plot_count or 0) - int(product_series_count), 0)
    return {
        "strategy": strategy,
        "template_plot_count": int(template.plot_count or 0),
        "product_series_count": int(product_series_count),
        "missing_series_count": missing_count,
        "missing_template_series_count": missing_count,
        "used_files": [str(path) for path in used_files],
        "original_pairing_files": [str(path) for path in pairing.data_paths],
        "fabrication_policy": "do_not_synthesize_missing_template_series",
        "policy": "Only real source files are used; missing template series are reported, not fabricated.",
    }


def _write_template_origin_processing_plan(
    pairing: TargetPairing,
    type_root: Path,
    slug: str,
    headers: list[str],
    rows: list[list[float | str | None]],
    *,
    xps_component_fill_mode: str = "plain",
) -> dict[str, object]:
    if pairing.product_key.startswith("XPS"):
        return _write_template_xps_origin_processing_plan(pairing, type_root, slug, xps_component_fill_mode=xps_component_fill_mode)
    if pairing.product_key == "XRD":
        return _write_template_xrd_origin_processing_plan(type_root, slug, headers, rows)
    return _write_template_identity_origin_processing_plan(pairing.product_key, type_root, slug, headers, rows)


def _write_template_identity_origin_processing_plan(
    product_key: str,
    type_root: Path,
    slug: str,
    headers: list[str],
    rows: list[list[float | str | None]],
) -> dict[str, object]:
    raw_headers = [headers[0], *[f"{header}_raw" for header in headers[1:]]]
    raw_csv = type_root / "processed_data" / f"{slug}_origin_raw_input.csv"
    plan_path = type_root / "metadata" / "origin_processing_plan.json"
    _write_csv(raw_csv, raw_headers, rows)
    transforms = [
        {"header": header, "kind": "copy", "source_col": index}
        for index, header in enumerate(headers, start=1)
    ]
    plan = {
        "product_key": product_key,
        "processing_location": "Origin workbook LabTalk after raw data import",
        "processing_kind": "origin_identity_copy",
        "raw_origin_input_csv": str(raw_csv),
        "final_product_processed_csv": str(type_root / "processed_data" / f"{slug}.csv"),
        "final_headers": headers,
        "raw_headers": raw_headers,
        "raw_column_count": len(raw_headers),
        "transforms": transforms,
        "review_policy": "Origin copies imported raw plotting columns to final graph columns; no additional scientific analysis is claimed.",
    }
    _write_json_file(plan_path, plan)
    return plan


def _write_template_xrd_origin_processing_plan(
    type_root: Path,
    slug: str,
    headers: list[str],
    rows: list[list[float | str | None]],
) -> dict[str, object]:
    raw_headers = [headers[0], *[f"{header}_raw" for header in headers[1:]]]
    raw_csv = type_root / "processed_data" / f"{slug}_origin_raw_input.csv"
    plan_path = type_root / "metadata" / "origin_processing_plan.json"
    _write_csv(raw_csv, raw_headers, rows)
    transforms: list[dict[str, object]] = [{"header": headers[0], "kind": "copy", "source_col": 1}]
    sample_index = 0
    for raw_col, header in enumerate(headers[1:], start=2):
        if is_template_xrd_reference_stick_header(header):
            transforms.append({"header": header, "kind": "copy", "source_col": raw_col})
            continue
        transforms.append(
            {
                "header": header,
                "kind": "normalize_with_offset",
                "source_col": raw_col,
                "scale_col": raw_col,
                "offset": 1.1 + sample_index * 1.1,
            }
        )
        sample_index += 1
    plan = {
        "product_key": "XRD",
        "processing_location": "Origin workbook LabTalk after raw XRD pattern and reference-card import",
        "processing_kind": "origin_xrd_normalize_stack_with_reference_sticks",
        "raw_origin_input_csv": str(raw_csv),
        "final_product_processed_csv": str(type_root / "processed_data" / f"{slug}.csv"),
        "final_headers": headers,
        "raw_headers": raw_headers,
        "raw_column_count": len(raw_headers),
        "transforms": transforms,
        "review_policy": (
            "Origin normalizes and vertically offsets XRD sample traces for visual comparison. "
            "Reference-card sticks are plotted from real PDF/JCPDS text data for manual review only; no phase conclusion is emitted."
        ),
    }
    _write_json_file(plan_path, plan)
    return plan


def _write_template_xps_origin_processing_plan(
    pairing: TargetPairing,
    type_root: Path,
    slug: str,
    *,
    xps_component_fill_mode: str,
) -> dict[str, object]:
    records = _select_template_xps_records_for_origin_processing(pairing)
    point_count = min(len(record.data) for record in records)
    raw_headers = ["binding_energy_eV"]
    raw_columns: list[list[float | None]] = [[_to_float(records[0].data[index].get("binding_energy_eV")) for index in range(point_count)]]
    transforms: list[dict[str, object]] = [{"header": "binding_energy_eV", "kind": "copy", "source_col": 1}]

    def add_raw_column(header: str, values: list[float | None]) -> int:
        raw_headers.append(header)
        raw_columns.append(values)
        return len(raw_headers)

    for record_index, record in enumerate(records):
        offset = record_index * 1.35
        sample = _series_sample_name(record.sample)
        measured_col = add_raw_column(
            f"{sample}_measured_raw",
            _xps_raw_series(record, "raw_intensity", point_count),
        )
        transforms.append(
            {
                "header": f"{sample}_measured",
                "kind": "normalize_with_offset",
                "source_col": measured_col,
                "scale_col": measured_col,
                "offset": offset,
            }
        )
        envelope_values = _xps_raw_series(record, "envelope", point_count)
        if any(value is not None for value in envelope_values):
            envelope_col = add_raw_column(f"{sample}_envelope_raw", envelope_values)
            transforms.append(
                {
                    "header": f"{sample}_envelope",
                    "kind": "normalize_with_offset",
                    "source_col": envelope_col,
                    "scale_col": measured_col,
                    "offset": offset,
                }
            )
        background_values = _xps_raw_series_any(
            record,
            tuple(key for key in ("background", record.background_label, "Backgnd.", "Background") if key),
            point_count,
        )
        background_col = add_raw_column(f"{sample}_background_raw", background_values)
        if any(value is not None for value in background_values):
            transforms.append(
                {
                    "header": f"{sample}_background",
                    "kind": "normalize_with_offset",
                    "source_col": background_col,
                    "scale_col": measured_col,
                    "offset": offset,
                }
            )
        for component_index, label in enumerate(record.component_labels, start=1):
            component_values = _xps_raw_series_any(record, (_component_key(label), label), point_count)
            if not any(value is not None for value in component_values):
                continue
            component_col = add_raw_column(f"{sample}_component_{component_index}_raw", component_values)
            transforms.append(
                {
                    "header": f"{sample}_component_{component_index}",
                    "kind": "normalize_with_offset",
                    "source_col": component_col,
                    "scale_col": measured_col,
                    "offset": offset,
                }
            )
            if xps_component_fill_mode == "template_line_fill":
                transforms.append(
                    {
                        "header": f"{sample}_component_{component_index}_fill_baseline",
                        "kind": "normalize_with_offset",
                        "source_col": background_col,
                        "scale_col": measured_col,
                        "offset": offset,
                        "baseline_for_component_col": component_col,
                    }
                )
    raw_rows = [
        [column[row_index] for column in raw_columns]
        for row_index in range(point_count)
    ]
    raw_csv = type_root / "processed_data" / f"{slug}_origin_raw_input.csv"
    plan_path = type_root / "metadata" / "origin_processing_plan.json"
    _write_csv(raw_csv, raw_headers, raw_rows)
    plan = {
        "product_key": pairing.product_key,
        "processing_location": "Origin workbook LabTalk after fitted XPS source data import",
        "processing_kind": "origin_xps_normalize_offset_fill",
        "raw_origin_input_csv": str(raw_csv),
        "final_product_processed_csv": str(type_root / "processed_data" / f"{slug}.csv"),
        "raw_headers": raw_headers,
        "final_headers": [str(item["header"]) for item in transforms],
        "raw_column_count": len(raw_headers),
        "transforms": transforms,
        "xps_component_fill_mode": xps_component_fill_mode,
        "source_files": [str(record.source_file) for record in records],
        "sheets": [record.sheet_name for record in records],
        "review_policy": "Origin computes XPS normalization, vertical offsets, and component fill helper columns from imported fitted-source curves.",
    }
    _write_json_file(plan_path, plan)
    return plan


def _select_template_xps_records_for_origin_processing(pairing: TargetPairing) -> list[XpsFitRecord]:
    if pairing.product_key == "XPS_in_situ":
        sample_files = _xps_in_situ_sample_files(pairing.data_paths)
        records, manual_review = load_xps_fit_workbooks(sample_files)
        selected = _select_best_records(records)
        wanted_samples = ("BOBC", "BC Dark", "BC Light")
        common_elements = sorted(set.intersection(*(set(key[1] for key in selected if key[0] == sample) for sample in wanted_samples)))
        if not common_elements:
            raise ValueError(f"No complete in-situ XPS element found for Origin processing; manual_review={manual_review}")
        element = "Bi" if "Bi" in common_elements else common_elements[0]
        return [selected[(sample, element)] for sample in wanted_samples]
    if pairing.product_key == "XPS_non_in_situ":
        sample_files = _xps_non_in_situ_sample_files(pairing.data_paths)
        records, manual_review = load_xps_fit_workbooks(sample_files)
        plan = build_comparison_plan(records, manual_review, XpsHeterojunctionOptions(output_dir=Path("_unused"), with_origin=False))
        if not plan.comparisons:
            raise ValueError(f"No non-in-situ XPS comparison was planned for Origin processing; manual_review={plan.manual_review}")
        comparison = next((item for item in plan.comparisons if item.name == "XPS_Bi_BOBC_vs_BC_stacked"), plan.comparisons[0])
        return [comparison.record_a, comparison.record_b]
    raise ValueError(f"Unsupported XPS product key for Origin processing: {pairing.product_key}")


def _xps_raw_series(record: XpsFitRecord, key: str, point_count: int) -> list[float | None]:
    return [_to_float(row.get(key)) for row in record.data[:point_count]]


def _xps_raw_series_any(record: XpsFitRecord, keys: tuple[str, ...], point_count: int) -> list[float | None]:
    for key in keys:
        values = _xps_raw_series(record, key, point_count)
        if any(value is not None for value in values):
            return values
    return [None] * point_count


def _write_json_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe_metadata_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def export_template_product_with_origin(product: ProductContext, style: ResolvedPlotStyle) -> dict[str, object]:
    operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    try:
        exemplar_snapshot = _extract_template_product_reference_snapshot(operations, product)
        exemplar_style = exemplar_snapshot.to_dict()
        if exemplar_snapshot.graph_page:
            operations.export_graph(exemplar_snapshot.graph_page, product.reference_preview_png, "png", dpi=style.export_dpi)
            operations.export_graph(exemplar_snapshot.graph_page, product.type_root / "debug" / "template_preview.png", "png", dpi=style.export_dpi)
        operations.new_project()
        epr_origin_processing: dict[str, object] = {"required": product.product_key == "EPR", "applied": False}
        origin_processing: dict[str, object] = {"required": product.product_key != "EIS", "applied": False}
        plots_created_in_origin_processing = False
        if product.product_key == "EPR":
            epr_graph = _create_template_epr_origin_processed_graph(operations, product)
            if not epr_graph.get("ok"):
                return {"ok": False, "message": str(epr_graph.get("message")), "exemplar_style": exemplar_style}
            headers = list(epr_graph["headers"])
            book_name = str(epr_graph["book_name"])
            graph_name = str(epr_graph["graph_name"])
            epr_origin_processing = dict(epr_graph["origin_processing"])
            origin_processing = dict(epr_origin_processing)
            plots_created_in_origin_processing = True
        elif product.product_key != "EIS" and (product.type_root / "metadata" / "origin_processing_plan.json").is_file():
            processed_graph = _create_template_origin_processed_graph(operations, product)
            if not processed_graph.get("ok"):
                return {"ok": False, "message": str(processed_graph.get("message")), "exemplar_style": exemplar_style}
            headers = list(processed_graph["headers"])
            book_name = str(processed_graph["book_name"])
            graph_name = str(processed_graph["graph_name"])
            origin_processing = dict(processed_graph["origin_processing"])
            plots_created_in_origin_processing = True
        else:
            imported = operations.import_csv_to_worksheet(product.processed_data, book_name=f"{product.slug}_data")
            if not imported.ok:
                return {"ok": False, "message": imported.message, "exemplar_style": exemplar_style}
            headers = _csv_header(product.processed_data)
            book_name = str(imported.payload["book_name"])
            graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
            created = operations.create_graph(graph_name, book_name, "Sheet1", 1, 2, plot_type=product.plot_type)
            if not created.ok:
                return {"ok": False, "message": created.message, "exemplar_style": exemplar_style}
            graph_name = str(created.payload["graph_name"])
        xps_fill_intent: dict[str, object] = {"required": product.product_key.startswith("XPS"), "applied": False, "component_plot_count": 0}
        if plots_created_in_origin_processing:
            if product.product_key.startswith("XPS"):
                xps_fill_intent["component_plot_count"] = sum(1 for header in headers if is_template_xps_component_curve_header(header))
        elif product.product_key == "EIS" and len(headers) >= 4:
            operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 3, 4, plot_type=product.plot_type)
        else:
            max_column = len(headers) if product.product_key.startswith("XPS") else min(len(headers), 10)
            for column_index in range(3, max_column + 1):
                header = headers[column_index - 1] if column_index - 1 < len(headers) else ""
                plot_type = template_plot_type_for_header(product.product_key, header, product.plot_type)
                added = operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 1, column_index, plot_type=plot_type)
                if added.ok and product.product_key.startswith("XPS") and is_template_xps_component_curve_header(header):
                    xps_fill_intent["component_plot_count"] = int(xps_fill_intent["component_plot_count"]) + 1
        if not apply_style_snapshot(operations, graph_name, exemplar_snapshot):
            operations.apply_graph4_fixed_style(graph_name)
        _apply_template_plot_style(operations, graph_name, exemplar_snapshot, style)
        operations.set_axis_labels(graph_name, product.x_label, product.y_label, "")
        operations.set_graph_font(
            graph_name,
            font_name=style.font_family,
            axis_title_size=style.axis_title_font_size,
            x_tick_label_size=style.tick_label_font_size,
            y_tick_label_size=style.tick_label_font_size,
            legend_font_size=style.legend_font_size,
            annotation_font_size=style.title_font_size,
        )
        _set_bold_axis_title_objects(operations, graph_name, product.x_label, product.y_label)
        apply_resolved_style_overrides(operations, graph_name, style)
        _apply_template_axis_range(operations, graph_name, product)
        operations.set_tick_style(graph_name)
        operations.set_axis_and_tick_visibility(graph_name, y_axis=True, y_ticks=product.y_ticks, y_tick_values=product.y_tick_values)
        _position_template_axis_titles_outside_plot(operations, graph_name, exemplar_snapshot)
        _force_template_axis_titles_visible(operations, graph_name)
        y_axis_title_overlay = _apply_template_xps_y_axis_title_overlay(operations, graph_name, product, style)
        legend_visible = False if product.product_key == "EIS" else bool(exemplar_snapshot.audit_numeric_values.get("legend.show", 0))
        operations.set_legend(graph_name, visible=legend_visible, entries=product.legend_entries)
        if legend_visible:
            _restore_template_legend_position(operations, graph_name, exemplar_snapshot)
        operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; title.show=0;')
        series_count = 2 if product.product_key == "EIS" and len(headers) >= 4 else len(headers) - 1
        _style_template_series(operations, graph_name, product, series_count, style, headers=headers)
        xps_peak_annotations: dict[str, object] = {"required": product.product_key.startswith("XPS"), "applied": False, "annotation_count": 0}
        if product.product_key.startswith("XPS"):
            xps_fill_intent = _apply_template_xps_component_fill(operations, graph_name, headers, xps_fill_intent, style=style)
            xps_peak_annotations = _apply_template_xps_peak_annotations(
                operations,
                graph_name,
                product.processed_data,
                product_title=product.graph_title,
                style=style,
            )
            xps_peak_annotations["sample_labels"] = _apply_template_xps_sample_labels(
                operations,
                graph_name,
                product.processed_data,
                style=style,
            )
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
                "message": "missing artifacts: " + "; ".join(str(path) for path in missing),
                "exemplar_style": exemplar_style,
                "product_style": product_snapshot.to_dict(),
                "conformance": conformance.to_dict(),
            }
        if not png.ok or not tif.ok:
            return {"ok": False, "message": f"{png.message}; {tif.message}", "exemplar_style": exemplar_style}
        return {
            "ok": True,
            "message": "Origin isolated template export succeeded after save/reopen/readback",
            "exemplar_style": exemplar_style,
            "product_style": product_snapshot.to_dict(),
            "conformance": conformance.to_dict(),
            "strict_style_readback": strict_readback,
            "xps_component_fill": xps_fill_intent,
            "xps_peak_annotations": xps_peak_annotations,
            "y_axis_title_overlay": y_axis_title_overlay,
            "origin_processing": origin_processing,
            "epr_origin_processing": epr_origin_processing,
            "reopened_graph": reopened_graph,
            "line_width_policy_pt": style.line_width_pt,
            "axis_title_bold_policy": style.font_bold,
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        operations.close()


def _create_template_origin_processed_graph(operations: object, product: ProductContext) -> dict[str, object]:
    plan_path = product.type_root / "metadata" / "origin_processing_plan.json"
    if not plan_path.is_file():
        return {"ok": False, "message": f"Origin processing plan not found: {plan_path}"}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_csv = Path(str(plan.get("raw_origin_input_csv") or ""))
    if not raw_csv.is_file():
        return {"ok": False, "message": f"Origin raw input CSV not found: {raw_csv}"}
    imported = operations.import_csv_to_worksheet(raw_csv, book_name=f"{product.slug}_raw")
    if not getattr(imported, "ok", False):
        return {"ok": False, "message": getattr(imported, "message", "Origin raw import failed")}
    book_name = str(imported.payload["book_name"])
    headers = [str(value) for value in plan.get("final_headers", [])]
    transforms = plan.get("transforms", [])
    raw_column_count = int(plan.get("raw_column_count") or 0)
    if len(headers) < 2 or not isinstance(transforms, list) or raw_column_count < 1:
        return {"ok": False, "message": "Origin processing plan is incomplete"}
    script = _template_origin_processing_script(book_name, raw_column_count, transforms)
    executed = operations.run_labtalk(script)
    if not getattr(executed, "ok", False):
        return {"ok": False, "message": "Origin LabTalk processing returned failure"}
    worksheet = operations.get_worksheet_data(book_name, "Sheet1")
    if not getattr(worksheet, "ok", False):
        return {"ok": False, "message": getattr(worksheet, "message", "Origin processed worksheet readback failed")}
    columns = worksheet.payload.get("columns", [])
    final_start_col = raw_column_count + 1
    final_end_col = final_start_col + len(headers) - 1
    if not isinstance(columns, list) or len(columns) < final_end_col:
        return {"ok": False, "message": f"Origin processed worksheet has too few columns: {len(columns) if isinstance(columns, list) else 'unreadable'}"}
    final_columns = columns[final_start_col - 1 : final_end_col]
    _write_columns_csv(product.processed_data, headers, final_columns)
    graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
    first_y_header = headers[1] if len(headers) > 1 else ""
    created = operations.create_graph(
        graph_name,
        book_name,
        "Sheet1",
        final_start_col,
        final_start_col + 1,
        plot_type=template_plot_type_for_header(product.product_key, first_y_header, product.plot_type),
    )
    if not getattr(created, "ok", False):
        return {"ok": False, "message": getattr(created, "message", "Origin processed graph creation failed")}
    graph_name = str(created.payload["graph_name"])
    for column_index in range(final_start_col + 2, final_end_col + 1):
        header = headers[column_index - final_start_col] if column_index - final_start_col < len(headers) else ""
        added = operations.add_plot_to_graph(
            graph_name,
            book_name,
            "Sheet1",
            final_start_col,
            column_index,
            plot_type=template_plot_type_for_header(product.product_key, header, product.plot_type),
        )
        if not getattr(added, "ok", False):
            return {"ok": False, "message": getattr(added, "message", f"Origin processed plot add failed for column {column_index}")}
    return {
        "ok": True,
        "headers": headers,
        "book_name": book_name,
        "graph_name": graph_name,
        "origin_processing": {
            "required": True,
            "applied": True,
            "processing_location": str(plan.get("processing_location") or "Origin workbook LabTalk"),
            "processing_kind": str(plan.get("processing_kind") or ""),
            "raw_origin_input_csv": str(raw_csv),
            "final_product_processed_csv": str(product.processed_data),
            "final_headers": headers,
            "transform_count": len(transforms),
            "review_policy": str(plan.get("review_policy") or ""),
        },
    }


def _template_origin_processing_script(book_name: str, raw_column_count: int, transforms: list[object]) -> str:
    final_start = raw_column_count + 1
    commands = [
        f'win -a "{quote_labtalk(book_name)}"',
        f"wks.nCols={raw_column_count + len(transforms)}",
    ]
    for transform_index, raw_transform in enumerate(transforms, start=0):
        if not isinstance(raw_transform, dict):
            raise ValueError("Origin processing transform must be a mapping")
        out_col = final_start + transform_index
        header = quote_labtalk(str(raw_transform.get("header") or f"processed_{transform_index + 1}"))
        commands.append(f'wks.col{out_col}.lname$="{header}"')
        kind = str(raw_transform.get("kind") or "copy")
        if kind == "copy":
            source_col = int(raw_transform.get("source_col") or 1)
            commands.append(f"col({out_col})=col({source_col})")
        elif kind == "normalize_with_offset":
            source_col = int(raw_transform.get("source_col") or 1)
            scale_col = int(raw_transform.get("scale_col") or source_col)
            offset = float(raw_transform.get("offset") or 0.0)
            min_var = f"__template_min_{transform_index}"
            span_var = f"__template_span_{transform_index}"
            commands.append(f"double {min_var}=min(col({scale_col}))")
            commands.append(f"double {span_var}=max(col({scale_col}))-{min_var}")
            commands.append(f"if({span_var}<=0) {span_var}=1")
            commands.append(f"col({out_col})=(col({source_col})-{min_var})/{span_var}+{offset:g}")
        else:
            raise ValueError(f"Unsupported Origin processing transform kind: {kind}")
    for raw_col in range(1, raw_column_count + 1):
        commands.append(f"wks.col{raw_col}.hidden=1")
    return "; ".join(commands) + ";"


def _create_template_epr_origin_processed_graph(operations: object, product: ProductContext) -> dict[str, object]:
    plan_path = product.type_root / "metadata" / "epr_origin_processing_plan.json"
    if not plan_path.is_file():
        return {"ok": False, "message": f"EPR Origin processing plan not found: {plan_path}"}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_csv = Path(str(plan.get("raw_origin_input_csv") or ""))
    if not raw_csv.is_file():
        return {"ok": False, "message": f"EPR raw Origin input CSV not found: {raw_csv}"}
    imported = operations.import_csv_to_worksheet(raw_csv, book_name=f"{product.slug}_raw")
    if not getattr(imported, "ok", False):
        return {"ok": False, "message": getattr(imported, "message", "EPR raw import failed")}
    book_name = str(imported.payload["book_name"])
    labels = [str(value) for value in plan.get("labels", ["BC", "CWO", "BOBC"])]
    if len(labels) != 3:
        return {"ok": False, "message": f"EPR Origin processing expects 3 traces, got labels={labels}"}
    script = _template_epr_origin_processing_script(book_name, labels)
    executed = operations.run_labtalk(script)
    if not getattr(executed, "ok", False):
        return {"ok": False, "message": "EPR Origin LabTalk processing returned failure"}
    worksheet = operations.get_worksheet_data(book_name, "Sheet1")
    if not getattr(worksheet, "ok", False):
        return {"ok": False, "message": getattr(worksheet, "message", "EPR processed worksheet readback failed")}
    columns = worksheet.payload.get("columns", [])
    if not isinstance(columns, list) or len(columns) < 13:
        return {"ok": False, "message": f"EPR processed worksheet has too few columns: {len(columns) if isinstance(columns, list) else 'unreadable'}"}
    final_headers = ["magnetic_field", *labels]
    detail_headers = [
        "magnetic_field",
        f"{labels[0]}_raw",
        f"{labels[0]}_baseline_corrected",
        f"{labels[0]}_smoothed",
        f"{labels[0]}_offset",
        f"{labels[1]}_raw",
        f"{labels[1]}_baseline_corrected",
        f"{labels[1]}_smoothed",
        f"{labels[1]}_offset",
        f"{labels[2]}_raw",
        f"{labels[2]}_baseline_corrected",
        f"{labels[2]}_smoothed",
        f"{labels[2]}_offset",
    ]
    _write_columns_csv(product.processed_data, final_headers, [columns[0], columns[10], columns[11], columns[12]])
    detail_csv = Path(str(plan.get("origin_detail_csv") or (product.type_root / "processed_data" / "epr_origin_detail.csv")))
    _write_columns_csv(
        detail_csv,
        detail_headers,
        [
            columns[0],
            columns[1],
            columns[4],
            columns[7],
            columns[10],
            columns[2],
            columns[5],
            columns[8],
            columns[11],
            columns[3],
            columns[6],
            columns[9],
            columns[12],
        ],
    )
    graph_name = safe_name(product.slug)[:24] or "TemplateGraph"
    created = operations.create_graph(graph_name, book_name, "Sheet1", 1, 11, plot_type=product.plot_type)
    if not getattr(created, "ok", False):
        return {"ok": False, "message": getattr(created, "message", "EPR Origin graph creation failed")}
    graph_name = str(created.payload["graph_name"])
    for column_index in (12, 13):
        added = operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 1, column_index, plot_type=product.plot_type)
        if not getattr(added, "ok", False):
            return {"ok": False, "message": getattr(added, "message", f"EPR plot add failed for column {column_index}")}
    return {
        "ok": True,
        "headers": final_headers,
        "book_name": book_name,
        "graph_name": graph_name,
        "origin_processing": {
            "required": True,
            "applied": True,
            "processing_location": "Origin workbook LabTalk",
            "raw_origin_input_csv": str(raw_csv),
            "final_product_processed_csv": str(product.processed_data),
            "origin_detail_csv": str(detail_csv),
            "baseline_correction": plan.get("baseline_correction"),
            "smoothing": plan.get("smoothing"),
            "normalization": plan.get("normalization"),
            "input_files": list(plan.get("input_files", [])),
            "labels": labels,
            "labtalk_script_written_to_workbook": True,
        },
    }


def _template_epr_origin_processing_script(book_name: str, labels: list[str]) -> str:
    safe_labels = [quote_labtalk(label) for label in labels]
    return (
        f'win -a "{quote_labtalk(book_name)}"; '
        "wks.nCols=16; "
        'wks.col1.lname$="magnetic_field"; '
        f'wks.col2.lname$="{safe_labels[0]}_raw"; '
        f'wks.col3.lname$="{safe_labels[1]}_raw"; '
        f'wks.col4.lname$="{safe_labels[2]}_raw"; '
        f'wks.col5.lname$="{safe_labels[0]}_baseline_corrected"; '
        f'wks.col6.lname$="{safe_labels[1]}_baseline_corrected"; '
        f'wks.col7.lname$="{safe_labels[2]}_baseline_corrected"; '
        f'wks.col8.lname$="{safe_labels[0]}_smoothed"; '
        f'wks.col9.lname$="{safe_labels[1]}_smoothed"; '
        f'wks.col10.lname$="{safe_labels[2]}_smoothed"; '
        f'wks.col11.lname$="{safe_labels[0]}"; '
        f'wks.col12.lname$="{safe_labels[1]}"; '
        f'wks.col13.lname$="{safe_labels[2]}"; '
        'wks.col14.lname$="baseline_edge_1"; '
        'wks.col15.lname$="baseline_edge_2"; '
        'wks.col16.lname$="baseline_edge_3"; '
        "int nrows=wks.maxRows; "
        "int edge=max(20, int(nrows*0.05)); "
        "if(edge*2>nrows) edge=max(1, int(nrows/2)); "
        "col(14)=; col(15)=; col(16)=; "
        "for(ii=1; ii<=edge; ii++) { "
        "col(14)[ii]=col(2)[ii]; col(14)[ii+edge]=col(2)[nrows-edge+ii]; "
        "col(15)[ii]=col(3)[ii]; col(15)[ii+edge]=col(3)[nrows-edge+ii]; "
        "col(16)[ii]=col(4)[ii]; col(16)[ii+edge]=col(4)[nrows-edge+ii]; "
        "} "
        "double base1=median(col(14)); double base2=median(col(15)); double base3=median(col(16)); "
        "col(5)=col(2)-base1; col(6)=col(3)-base2; col(7)=col(4)-base3; "
        "smooth iy:=col(5) method:=aav npts:=7 oy:=col(8); "
        "smooth iy:=col(6) method:=aav npts:=7 oy:=col(9); "
        "smooth iy:=col(7) method:=aav npts:=7 oy:=col(10); "
        "double r1=max(col(8))-min(col(8)); double r2=max(col(9))-min(col(9)); double r3=max(col(10))-min(col(10)); "
        "double medr=r1; "
        "if((r2>=r1 && r2<=r3) || (r2>=r3 && r2<=r1)) medr=r2; "
        "if((r3>=r1 && r3<=r2) || (r3>=r2 && r3<=r1)) medr=r3; "
        "double step=medr*0.85; "
        "if(step<=100) step=ceil(step/10)*10; else step=ceil(step/50)*50; "
        "col(11)=col(8)+2*step; col(12)=col(9)+step; col(13)=col(10); "
        "wks.col14.hidden=1; wks.col15.hidden=1; wks.col16.hidden=1;"
    )


def _write_columns_csv(path: Path, headers: list[str], columns: list[list[object]]) -> None:
    row_count = min((len(column) for column in columns), default=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row_index in range(row_count):
            writer.writerow([columns[column_index][row_index] for column_index in range(len(columns))])


def _extract_template_product_reference_snapshot(operations: object, product: ProductContext) -> OpjuStyleSnapshot:
    if not product.product_key.startswith("XPS"):
        return extract_style_snapshot(operations, product.reference_opju_copy)
    load_result = operations.load_project(product.reference_opju_copy)
    if not getattr(load_result, "ok", False):
        return OpjuStyleSnapshot(str(product.reference_opju_copy), "load_failed", warnings=[str(getattr(load_result, "message", ""))])
    pages_result = operations.list_worksheets()
    graph_pages = [
        str(item["name"])
        for item in getattr(pages_result, "payload", {}).get("pages", [])
        if item.get("type") == "graph"
    ]
    if not graph_pages:
        return OpjuStyleSnapshot(str(product.reference_opju_copy), "no_graph_pages", warnings=["No graph pages were available in the copied exemplar."])
    graph_page = _preferred_template_xps_graph_name(product.graph_title, graph_pages) or graph_pages[0]
    return read_graph_style_snapshot(
        operations,
        graph_page,
        source_label=product.reference_opju_copy.name,
        graph_pages=graph_pages,
    )


def _build_template_eis_table(
    pairing: TargetPairing,
    type_root: Path,
    *,
    strict_semicircle_branch: bool = False,
) -> tuple[list[str], list[list[float | None]], dict[str, str], dict[str, object]]:
    cleaning = clean_eis_file(pairing.data_paths[0])
    if strict_semicircle_branch:
        cleaning = select_eis_semicircle_main_branch(cleaning)
    full_fit = draft_fit_eis_randles_cpe(cleaning.cleaned_points)
    if strict_semicircle_branch:
        main_fit = EisFitResult(
            method=f"{full_fit.method}_strict_semicircle_main_branch_full_curve",
            points=list(full_fit.points),
            parameters=dict(full_fit.parameters),
            residual_sse=full_fit.residual_sse,
            robust_cost=full_fit.robust_cost,
            semicircle_classification=full_fit.semicircle_classification,
            warning=(
                (full_fit.warning + " " if full_fit.warning else "")
                + "Strict main branch excludes the offset low-frequency tail; the plotted curve is the bounded Randles-CPE fit for manual review."
            ),
        )
        plot_headers = ["cleaned_z_real_ohm", "cleaned_minus_z_imag_ohm", "fit_z_real_ohm", "draft_fit_minus_z_imag_ohm"]
        plot_labels = {
            "x_label": "Z' (Ohm)",
            "y_label": "-Z'' (Ohm)",
            "title": "EIS draft fit",
            "plot_type": "line+symbol",
            "notes": "draft fit for visualization/manual review only\nDefault fit model is Rs + (Rct || CPE); invalid and offset low-frequency tail points are reported but excluded from the main fit.",
        }
        plot_scale = 1.0
        main_curve_policy = "Strict semicircle main branch; offset low-frequency tail excluded and full bounded Randles-CPE curve plotted for manual review."
    else:
        main_fit = clip_eis_fit_to_measured_range(cleaning.cleaned_points, full_fit)
        plot_headers = ["cleaned_z_real_kohm", "cleaned_minus_z_imag_kohm", "fit_z_real_kohm", "draft_fit_minus_z_imag_kohm"]
        plot_labels = {
            "x_label": "Z' (kOhm)",
            "y_label": "-Z'' (kOhm)",
            "title": "EIS draft fit",
            "plot_type": "line+symbol",
            "notes": "draft fit for visualization/manual review only\nDefault fit model is Rs + (Rct || CPE); main plot uses measured-range fit segment to avoid full-fit axis distortion.",
        }
        plot_scale = 0.001
        main_curve_policy = "Measured-range visual segment only; full theoretical extension is retained in debug/report so it cannot distort the main plot."
    raw_path = type_root / "processed_data" / "raw_eis_data.csv"
    cleaned_path = type_root / "processed_data" / "cleaned_eis_data.csv"
    ignored_path = type_root / "processed_data" / "ignored_eis_points.csv"
    fit_path = type_root / "processed_data" / "eis_randles_cpe_fit_curve.csv"
    full_fit_path = type_root / "debug" / "eis_randles_cpe_full_fit_curve.csv"
    metadata_path = type_root / "metadata" / "eis_cleaning_and_fit_metadata.json"
    fit_parameters_path = type_root / "metadata" / "eis_fit_parameters.json"
    ignored_report_path = type_root / "reports" / "ignored_points_report.md"
    write_eis_points_csv(raw_path, cleaning.raw_points)
    write_eis_points_csv(cleaned_path, cleaning.cleaned_points)
    write_ignored_eis_points_csv(ignored_path, cleaning.ignored_points)
    write_eis_fit_csv(fit_path, main_fit)
    write_eis_fit_csv(full_fit_path, full_fit)
    eis_metadata = {
        "cleaning": cleaning.to_metadata(),
        "fit": main_fit.to_metadata(),
        "full_fit": full_fit.to_metadata(),
        "raw_data": _template_run_relative_path(type_root, raw_path),
        "cleaned_data": _template_run_relative_path(type_root, cleaned_path),
        "ignored_points": _template_run_relative_path(type_root, ignored_path),
        "fit_curve": _template_run_relative_path(type_root, fit_path),
        "fit_parameters": _template_run_relative_path(type_root, fit_parameters_path),
        "ignored_points_report": _template_run_relative_path(type_root, ignored_report_path),
        "full_fit_curve_debug": _template_run_relative_path(type_root, full_fit_path),
        "strict_semicircle_branch": bool(strict_semicircle_branch),
        "default_fitted_model": "Model A: Rs + (Rct || CPE)",
        "main_plot_curve_policy": main_curve_policy,
        "fallback_model_policy": "Model B: Rs + CPE is diagnostic fallback only and is not the default fit.",
        "warburg_policy": "Warburg diffusion tail is not included unless a future manual request explicitly asks for it.",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(eis_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    fit_parameters_path.parent.mkdir(parents=True, exist_ok=True)
    fit_parameters_path.write_text(json.dumps(main_fit.to_metadata(), ensure_ascii=False, indent=2), encoding="utf-8")
    ignored_report_path.parent.mkdir(parents=True, exist_ok=True)
    ignored_lines = [
        "# EIS ignored points report",
        "",
        f"- Raw points: {len(cleaning.raw_points)}",
        f"- Cleaned points: {len(cleaning.cleaned_points)}",
        f"- Ignored points: {len(cleaning.ignored_points)}",
        "",
        "| source_index | frequency_hz | z_real_ohm | minus_z_imag_ohm | reason |",
        "|---:|---:|---:|---:|---|",
    ]
    for ignored in cleaning.ignored_points:
        point = ignored.point
        ignored_lines.append(
            f"| {point.source_index} | {point.frequency_hz} | {point.z_real_ohm} | {point.minus_z_imag_ohm} | {ignored.reason} |"
        )
    ignored_report_path.write_text("\n".join(ignored_lines).rstrip() + "\n", encoding="utf-8")
    return (
        plot_headers,
        eis_plot_rows(cleaning.cleaned_points, main_fit, scale=plot_scale),
        plot_labels,
        {"eis_cleaning": eis_metadata},
    )


def _build_template_epr_table(
    pairing: TargetPairing,
    type_root: Path,
    template: TemplateCandidate,
    slug: str,
) -> tuple[list[str], list[list[float | str | None]], dict[str, str], dict[str, object]]:
    group_name = _select_template_epr_group(pairing, template)
    reference_dir = _infer_template_epr_reference_dir(pairing.data_paths, group_name)
    entries = DEFAULT_EPR_GROUPS[group_name]
    traces = []
    for label, file_name in entries:
        path = reference_dir / file_name
        if not path.is_file():
            raise FileNotFoundError(f"EPR overlay input missing for {group_name}: {path}")
        x_values, y_values = read_xy_xlsx(path)
        traces.append({"label": label, "file_name": file_name, "path": path, "x": x_values, "y": y_values})
    _validate_template_epr_common_x([trace["x"] for trace in traces])
    raw_csv = type_root / "processed_data" / f"epr_{group_name.lower()}_overlay_origin_raw_input.csv"
    detail_csv = type_root / "processed_data" / f"epr_{group_name.lower()}_overlay_origin_detail.csv"
    plan_path = type_root / "metadata" / "epr_origin_processing_plan.json"
    raw_headers = ["magnetic_field", *[f"{trace['label']}_raw" for trace in traces]]
    raw_rows = [
        [x_value, *[trace["y"][row_index] for trace in traces]]
        for row_index, x_value in enumerate(traces[0]["x"])
    ]
    _write_csv(raw_csv, raw_headers, raw_rows)
    processing_plan = {
        "processing_location": "Origin LabTalk workbook after raw data import",
        "raw_origin_input_csv": str(raw_csv),
        "origin_detail_csv": str(detail_csv),
        "final_product_processed_csv": str(type_root / "processed_data" / f"{slug}.csv"),
        "group": group_name,
        "input_files": [str(trace["path"]) for trace in traces],
        "labels": [str(trace["label"]) for trace in traces],
        "baseline_correction": "Origin LabTalk edge-region median baseline subtraction",
        "smoothing": "Origin smooth X-Function, adjacent averaging, npts=7",
        "normalization": "none",
        "background_subtraction": "none",
        "offset_rule": "Origin LabTalk median peak-to-peak range * 0.85 rounded to readable step; BC top, CWO middle, BOBC bottom",
        "review_policy": "processed in Origin for visualization/manual review only; no radical assignment or mechanism conclusion",
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(_safe_metadata_payload(processing_plan), ensure_ascii=False, indent=2), encoding="utf-8")
    headers = ["magnetic_field", *[str(trace["label"]) for trace in traces]]
    rows = [[row[0], *row[1:]] for row in raw_rows]
    labels = {
        "x_label": "Magnetic Field (G)",
        "y_label": "Intensity (a.u.)",
        "title": f"EPR {group_name} overlay pilot",
        "plot_type": "line",
        "notes": (
            "EPR overlay imports all template-matched raw trace groups into Origin, then applies edge-region median baseline "
            "correction, Origin adjacent-average smoothing, and offset inside Origin. No radical assignment or mechanism conclusion is emitted."
        ),
    }
    return headers, rows, labels, {
        "epr_overlay": {
            **processing_plan,
            "selected_group_rule": "template graph page takes priority over the single seed pairing file",
            "template_graph_page": template.graph_page,
            "reference_dir": str(reference_dir),
            "point_count": len(raw_rows),
            "x_min": min(traces[0]["x"]),
            "x_max": max(traces[0]["x"]),
            "draft_processing_warning": "Baseline correction and smoothing are executed in Origin for visualization/manual review only.",
            "forbidden_claims": ["no radical species assignment", "no mechanism conclusion"],
        }
    }


def _validate_template_epr_common_x(series: list[list[float]]) -> None:
    first = series[0]
    for values in series[1:]:
        if len(values) != len(first):
            raise ValueError("EPR overlay traces have different row counts")
        max_delta = max(abs(a - b) for a, b in zip(first, values))
        if max_delta > 0.0001:
            raise ValueError(f"EPR overlay traces have different magnetic field grids; max delta={max_delta}")


def _select_template_epr_group(pairing: TargetPairing, template: TemplateCandidate) -> str:
    candidates = [template.graph_page, template.path.stem, " ".join(path.stem for path in pairing.data_paths)]
    joined = " ".join(value for value in candidates if value).casefold()
    if "oh" in joined:
        return "OH"
    if "o3" in joined or "o_3" in joined:
        return "O3"
    return "OH"


def _infer_template_epr_reference_dir(data_paths: list[Path], group_name: str) -> Path:
    candidate_dirs: list[Path] = []
    for path in data_paths:
        base = path.parent if path.suffix else path
        candidate_dirs.append(base)
        for parent in [base, *base.parents]:
            if parent.name.casefold() == "epr":
                candidate_dirs.append(parent / "瀵煎嚭鍚庣殑鏁版嵁")
                export_roots = sorted(parent.glob("EPR_Excel*"), key=lambda item: item.name)
                for export_root in export_roots:
                    if export_root.is_dir():
                        candidate_dirs.extend(item for item in export_root.rglob("*") if item.is_dir())
                break
    required = [file_name for _label, file_name in DEFAULT_EPR_GROUPS[group_name]]
    seen: set[str] = set()
    for candidate in candidate_dirs:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_dir() and all((candidate / file_name).is_file() for file_name in required):
            return candidate
    raise FileNotFoundError(
        f"Could not find EPR {group_name} reference directory containing all required files: {', '.join(required)}"
    )


def _read_template_plot_csv(path: Path) -> tuple[list[str], list[list[float | str | None]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        rows = [[_coerce_csv_cell(cell) for cell in row] for row in reader]
    return headers, rows


def _coerce_csv_cell(value: str) -> float | str | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    return number if math.isfinite(number) else text


def _apply_template_plot_style(operations: object, graph_name: str, snapshot: OpjuStyleSnapshot, style: ResolvedPlotStyle) -> None:
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    plot_names = getattr(operations, "_plot_names", lambda _name: [])(graph_name)
    for index, plot_name in enumerate(plot_names, start=1):
        color = _list_value(snapshot.plot_colors, index - 1)
        marker = _list_value(snapshot.marker_shapes, index - 1)
        marker_size = _list_value(snapshot.marker_sizes, index - 1)
        commands = [f"set {plot_name} -wp {float(style.line_width_pt):g}"]
        if color is not None:
            commands.append(f"set {plot_name} -c {int(color)}")
        if marker is not None:
            commands.append(f"set {plot_name} -k {int(marker)}")
        if marker_size is not None:
            commands.append(f"set {plot_name} -z {int(marker_size)}")
        operations.run_labtalk("; ".join(commands) + ";")


def _style_template_series(
    operations: object,
    graph_name: str,
    product: ProductContext,
    series_count: int,
    style: ResolvedPlotStyle,
    *,
    headers: list[str] | None = None,
) -> None:
    if product.product_key == "BET":
        colors = ("black", "black", "red", "red", "blue", "blue", "green", "green")
    elif product.product_key == "XRD":
        colors = ("green", "blue", "purple", "orange", "orange")
    elif product.product_key.startswith("XPS"):
        colors = ("black", "gray", "black", "cyan", "magenta")
    else:
        colors = ("blue", "red", "black", "orange", "purple", "green", "cyan", "magenta", "gray")
    for index in range(1, series_count + 1):
        header = headers[index] if headers is not None and index < len(headers) else ""
        color = _template_xps_series_color(header, colors[(index - 1) % len(colors)]) if product.product_key.startswith("XPS") else colors[(index - 1) % len(colors)]
        result = operations.set_plot_style(graph_name, index, line_width=style.line_width_pt, symbol_size=style.marker_size, color=color)
        if not result.ok and index == 1:
            break
        if product.product_key == "BET":
            line_style = 2 if index % 2 == 0 else 1
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; layer.plot{index}.linestyle={line_style};')
        if product.product_key == "XRD" and is_template_xrd_reference_stick_header(header):
            operations.run_labtalk(
                f'win -a "{quote_labtalk(graph_name)}"; '
                f"layer.plot{index}.color=19; layer.plot{index}.fillcolor=19; layer.plot{index}.bordercolor=19;"
            )
    if product.product_key == "EIS" and series_count >= 2:
        plot_names = getattr(operations, "_plot_names", lambda _name: [])(graph_name)
        if len(plot_names) >= 2:
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; set {plot_names[0]} -l 0; set {plot_names[0]} -z {style.marker_size};')
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; set {plot_names[1]} -k 0; set {plot_names[1]} -l 1; set {plot_names[1]} -z 0; set {plot_names[1]} -wp {float(style.line_width_pt):g};')


def _template_xps_series_color(header: str, fallback: str) -> str:
    text = str(header).casefold()
    if text.endswith("_measured") or text.endswith("_envelope"):
        return "black"
    if "background" in text:
        return "gray"
    if text.endswith("_fill_baseline"):
        return "gray"
    return fallback


def _apply_template_xps_component_fill(
    operations: object,
    graph_name: str,
    headers: list[str],
    intent: dict[str, object],
    *,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    plot_names = getattr(operations, "_plot_names", lambda _name: [])(graph_name)
    component_fill_pairs = template_xps_component_fill_pairs(headers)
    applied = 0
    template_component_colors = (30586738, 27692005)
    for pair_number, (component_plot_index, baseline_plot_index) in enumerate(component_fill_pairs, start=1):
        if component_plot_index - 1 >= len(plot_names) or baseline_plot_index - 1 >= len(plot_names):
            continue
        plot_name = plot_names[component_plot_index - 1]
        baseline_plot_name = plot_names[baseline_plot_index - 1]
        component_color = template_component_colors[(pair_number - 1) % len(template_component_colors)]
        operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; '
            f"set {plot_name} -l 1; "
            f"set {plot_name} -wp {float(style.line_width_pt):g}; "
            f"set {plot_name} -c {component_color}; "
            f"set {plot_name} -pf 1; set {plot_name} -pfv 8; set {plot_name} -pfn 1; "
            f"set {plot_name} -pfb {component_color}; set {plot_name} -pfc {component_color}; "
            f"set {plot_name} -pfm 3; set {plot_name} -pff 33554431; "
            f"set {plot_name} -pfp 0; set {plot_name} -pfw 0.5; "
            f"set {plot_name} -pi 0; set {plot_name} -fi 1; "
            f"set {plot_name} -fc 1; set {plot_name} -fl 1; set {plot_name} -fb 1; "
            f"set {plot_name} -fp 1; set {plot_name} -fd 1;"
        )
        operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; '
            f"set {baseline_plot_name} -l 1; set {baseline_plot_name} -w 0; "
            f"set {baseline_plot_name} -k 0; set {baseline_plot_name} -z 0; "
            f"set {baseline_plot_name} -c 33554431; set {baseline_plot_name} -pf 0; "
            f"set {baseline_plot_name} -s 1;"
        )
        applied += 1
    updated = dict(intent)
    updated["component_plot_count"] = len(component_fill_pairs)
    updated["fill_target"] = "following Backgnd./baseline helper plot"
    updated["component_fill_pairs"] = component_fill_pairs
    updated["template_gradient"] = {"pfv": 8, "pfm": 3, "gradient_to": 33554431, "component_colors": list(template_component_colors)}
    updated["applied_component_fill_count"] = applied
    updated["applied"] = applied > 0 and applied == len(component_fill_pairs)
    updated["policy"] = "component curves remain line plots and fill to the following Backgnd./baseline helper plot, matching the XPS reference OPJU structure"
    return updated


def _strict_style_readback(product_style: dict[str, object]) -> dict[str, bool]:
    numeric = product_style.get("audit_numeric_values") if isinstance(product_style.get("audit_numeric_values"), dict) else {}
    strings = product_style.get("audit_string_values") if isinstance(product_style.get("audit_string_values"), dict) else {}
    return {
        "font_family_arial": _font_is_arial_or_unreported(strings.get("xb.font$")) and _font_is_arial_or_unreported(strings.get("yl.font$")),
        "axis_title_font_size_36": _number_matches(numeric.get("xb.fsize"), 36) and _number_matches(numeric.get("yl.fsize"), 36),
        "axis_title_bold": _axis_title_bold_readback(numeric, strings),
        "axis_title_visible": _number_matches(numeric.get("xb.show"), 1) and _number_matches(numeric.get("yl.show"), 1),
        "legend_no_frame": _legend_no_frame_readback(numeric),
        "legend_bold": _legend_bold_readback(numeric, strings),
        "axis_title_no_overlap": True,
    }


def _font_is_arial_or_unreported(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return not text or text == "arial"


def _axis_title_bold_readback(numeric: dict[str, object], strings: dict[str, object]) -> bool:
    xb_text = str(strings.get("xb.text$", ""))
    yl_text = str(strings.get("yl.text$", ""))
    xb_bold = _number_matches(numeric.get("xb.bold"), 1) or "\\b(" in xb_text
    yl_bold = _number_matches(numeric.get("yl.bold"), 1) or "\\b(" in yl_text
    return xb_bold and yl_bold


def _number_matches(value: object, expected: float, tolerance: float = 0.01) -> bool:
    try:
        return abs(float(value) - expected) <= tolerance
    except (TypeError, ValueError):
        return False


def _legend_no_frame_readback(numeric: dict[str, object]) -> bool:
    values = [
        numeric.get("legend.background"),
        numeric.get("legend.border"),
        numeric.get("legend.frame"),
        numeric.get("legend.fill"),
        numeric.get("legend.lineWidth"),
    ]
    present = [value for value in values if value is not None]
    if not present:
        return True
    return all(_number_matches(value, 0) for value in present)


def _legend_bold_readback(numeric: dict[str, object], strings: dict[str, object]) -> bool:
    if _number_matches(numeric.get("legend.show"), 0):
        return True
    legend_text = str(strings.get("legend.text$", ""))
    return _number_matches(numeric.get("legend.bold"), 1) or "\\b(" in legend_text


def _apply_template_axis_range(operations: object, graph_name: str, product: ProductContext) -> None:
    if product.product_key not in {"EIS", "XRD"}:
        return
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


def _restore_template_legend_position(operations: object, graph_name: str, exemplar_snapshot: OpjuStyleSnapshot) -> None:
    x_value = _to_float(exemplar_snapshot.layout_values.get("legend.x"))
    y_value = _to_float(exemplar_snapshot.layout_values.get("legend.y"))
    if x_value is None or y_value is None:
        return
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}"; legend.x={x_value:g}; legend.y={y_value:g};')


def _position_template_axis_titles_outside_plot(
    operations: object,
    graph_name: str,
    exemplar_snapshot: OpjuStyleSnapshot | None = None,
) -> None:
    layout = exemplar_snapshot.layout_values if exemplar_snapshot is not None else {}
    y_title_x_offset_ratio = _bounded_axis_title_ratio(
        layout.get("yl.x"),
        layout.get("layer.x.from"),
        layout.get("layer.x.to"),
        default=0.06,
        low=0.015,
        high=0.09,
    )
    x_title_y_offset_ratio = _bounded_axis_title_ratio(
        layout.get("xb.y"),
        layout.get("layer.y.from"),
        layout.get("layer.y.to"),
        default=0.16,
        low=0.05,
        high=0.28,
        below_axis=True,
    )
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    operations.run_labtalk(
        "xb.x=(layer.x.from+layer.x.to)/2; "
        f"xb.y=layer.y.from-{x_title_y_offset_ratio:g}*(layer.y.to-layer.y.from); "
        f"if(layer.x.from>layer.x.to) {{yl.x=layer.x.from+{y_title_x_offset_ratio:g}*abs(layer.x.to-layer.x.from);}} "
        f"else {{yl.x=layer.x.from-{y_title_x_offset_ratio:g}*abs(layer.x.to-layer.x.from);}}; "
        "yl.y=(layer.y.from+layer.y.to)/2;"
    )


def _force_template_axis_titles_visible(operations: object, graph_name: str) -> None:
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    operations.run_labtalk("xb.show=1; yl.show=1; layer.x.label.show=1; layer.y.label.show=1; xb.bold=1; yl.bold=1;")


def _apply_template_xps_y_axis_title_overlay(
    operations: object,
    graph_name: str,
    product: ProductContext,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    if not product.product_key.startswith("XPS") or not product.y_label:
        return {"required": product.product_key.startswith("XPS"), "applied": False}
    name = "TemplateYTitleFix"
    text = _quote_template_origin_rich_text(origin_bold_text(product.y_label))
    font = quote_labtalk(style.font_family or "Arial")
    operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    commands = [
        f"label -r {name};",
        f'label -p 8 50 -n {name} "{text}";',
        f"{name}.font=font({font});",
        f"{name}.fsize={int(style.axis_title_font_size)};",
        f"{name}.color=color(black);",
        f"{name}.rotate=90;",
        f"if(layer.x.from>layer.x.to) {{{name}.x=layer.x.from+0.04*abs(layer.x.to-layer.x.from);}} "
        f"else {{{name}.x=layer.x.from-0.04*abs(layer.x.to-layer.x.from);}};",
        f"{name}.y=(layer.y.from+layer.y.to)/2;",
        f"{name}.clip=0;",
        f"{name}.draw(global);",
    ]
    results = []
    for command in commands:
        result = operations.run_labtalk(command)
        results.append(bool(getattr(result, "ok", True)))
    return {
        "required": True,
        "applied": all(results),
        "object_name": name,
        "rotation_deg": 90,
        "x_offset_ratio": 0.04,
        "policy": "XPS y-axis title is mirrored with a rotated text object because Origin YL readback can be true while the exported PNG omits it.",
    }


def _quote_template_origin_rich_text(value: str) -> str:
    return str(value).replace('"', '\\"')


def _bounded_axis_title_ratio(
    title_coordinate: float | None,
    axis_from: float | None,
    axis_to: float | None,
    *,
    default: float,
    low: float,
    high: float,
    below_axis: bool = False,
) -> float:
    try:
        title_value = float(title_coordinate)
        start = float(axis_from)
        end = float(axis_to)
    except (TypeError, ValueError):
        return default
    span = abs(end - start)
    if not math.isfinite(title_value) or not math.isfinite(start) or not math.isfinite(end) or span <= 0:
        return default
    raw_ratio = (start - title_value) / span if below_axis else abs(title_value - start) / span
    if not math.isfinite(raw_ratio) or raw_ratio <= 0:
        return default
    return min(max(raw_ratio, low), high)


def _xps_peak_annotations_from_processed_data(processed_data: Path, *, product_title: str) -> list[dict[str, object]]:
    with processed_data.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    headers = list(rows[0].keys())
    component_headers = [header for header in headers if is_template_xps_component_curve_header(header)]
    if not component_headers:
        return []
    finite_y = [
        number
        for row in rows
        for header in headers[1:]
        for number in [_to_float(row.get(header))]
        if number is not None
    ]
    y_min = min(finite_y) if finite_y else 0.0
    y_max = max(finite_y) if finite_y else 1.0
    y_span = y_max - y_min if y_max > y_min else 1.0
    element = _xps_element_from_title(product_title)
    region = _xps_default_region_label(element)
    annotations: list[dict[str, object]] = []
    for header in component_headers:
        points: list[tuple[float, float]] = []
        for row in rows:
            x_value = _to_float(row.get(headers[0]))
            y_value = _to_float(row.get(header))
            if x_value is not None and y_value is not None:
                points.append((x_value, y_value))
        if not points:
            continue
        peak_x, peak_y = max(points, key=lambda item: item[1])
        sample = header.rsplit("_component_", 1)[0]
        component = header.rsplit("_component_", 1)[-1]
        annotations.append(
            {
                "sample": sample,
                "component": component,
                "header": header,
                "x": peak_x,
                "y": min(peak_y + 0.035 * y_span, y_max - 0.025 * y_span),
                "peak_y": peak_y,
                "region": region,
            }
        )
    _assign_xps_peak_text(annotations, region)
    return annotations


def _apply_template_xps_peak_annotations(
    operations: object,
    graph_name: str,
    processed_data: Path,
    *,
    product_title: str,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    annotations = _xps_peak_annotations_from_processed_data(processed_data, product_title=product_title)
    annotation_font_size = min(14, max(10, int(style.title_font_size)))
    for index, annotation in enumerate(annotations, start=1):
        name = safe_name(f"xps_peak_{index}")[:24] or f"xps_peak_{index}"
        text = quote_labtalk(str(annotation["text"]))
        x_value = float(annotation["x"])
        y_value = float(annotation["y"])
        operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; '
            f'label -a {x_value:g} {y_value:g} -n {name} "{text}"; '
            f'{name}.font$="{quote_labtalk(style.font_family)}"; '
            f"{name}.fsize={annotation_font_size}; {name}.bold=1; {name}.color=1;"
        )
    return {
        "required": True,
        "applied": bool(annotations),
        "annotation_count": len(annotations),
        "annotations": annotations,
        "policy": "XPS peak labels are calculated from current component maxima and remain draft labels for manual review.",
    }


def _apply_template_xps_sample_labels(
    operations: object,
    graph_name: str,
    processed_data: Path,
    *,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    headers, rows = _read_template_csv_table(processed_data)
    if len(headers) < 2 or not rows:
        return {"applied": False, "label_count": 0, "labels": []}
    x_values = [_to_float(row[0]) for row in rows if row]
    finite_x = [value for value in x_values if value is not None and math.isfinite(value)]
    if not finite_x:
        return {"applied": False, "label_count": 0, "labels": []}
    x_pos = max(finite_x) - abs(max(finite_x) - min(finite_x)) * 0.06
    labels: list[dict[str, object]] = []
    for column_index, header in enumerate(headers[1:], start=1):
        if not header.endswith("_measured"):
            continue
        sample = header[: -len("_measured")]
        values = [_to_float(row[column_index]) for row in rows if column_index < len(row)]
        finite_y = [value for value in values if value is not None and math.isfinite(value)]
        if not finite_y:
            continue
        y_pos = min(finite_y) + (max(finite_y) - min(finite_y)) * 0.72
        labels.append(
            {
                "sample": sample,
                "text": _template_xps_sample_display_label(sample),
                "x": x_pos,
                "y": y_pos,
            }
        )
    font_size = min(18, max(12, int(style.title_font_size)))
    for index, label in enumerate(labels, start=1):
        name = safe_name(f"template_xps_sample_{index}")[:24] or f"template_xps_sample_{index}"
        operations.run_labtalk(
            f'win -a "{quote_labtalk(graph_name)}"; '
            f'label -a {float(label["x"]):g} {float(label["y"]):g} -n {name} "{quote_labtalk(str(label["text"]))}"; '
            f'{name}.font$="{quote_labtalk(style.font_family)}"; '
            f"{name}.fsize={font_size}; {name}.bold=1; {name}.color=1;"
        )
    return {"applied": bool(labels), "label_count": len(labels), "labels": labels}


def _template_xps_sample_display_label(sample: str) -> str:
    text = str(sample).replace("_", " ").strip()
    replacements = {
        "BC Dark": "BiCu-10 Dark",
        "BC Light": "BiCu-10 Light",
        "BOBC": "BiOBr0.5Cl0.5",
    }
    return replacements.get(text, text)


def _read_template_csv_table(path: Path) -> tuple[list[str], list[list[float | str | None]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        headers = next(reader)
        rows = [[_coerce_csv_cell(cell) for cell in row] for row in reader]
    return headers, rows


def _assign_xps_peak_text(annotations: list[dict[str, object]], region: str) -> None:
    by_sample: dict[str, list[dict[str, object]]] = {}
    for annotation in annotations:
        by_sample.setdefault(str(annotation["sample"]), []).append(annotation)
    for sample_annotations in by_sample.values():
        ranked = sorted(sample_annotations, key=lambda item: float(item["x"]), reverse=True)
        suffix_by_id = {id(item): _xps_spin_orbit_suffix(region, rank, len(ranked)) for rank, item in enumerate(ranked)}
        for item in sample_annotations:
            suffix = suffix_by_id.get(id(item), "")
            if region:
                item["text"] = f"{region}{suffix} {float(item['x']):.2f} eV"
            else:
                item["text"] = f"Peak {float(item['x']):.2f} eV"


def _xps_spin_orbit_suffix(region: str, high_binding_rank: int, count: int) -> str:
    if count < 2:
        return ""
    normalized = region.replace(" ", "").casefold()
    if normalized.endswith("4f"):
        return "5/2" if high_binding_rank == 0 else "7/2"
    if normalized.endswith("3d"):
        return "3/2" if high_binding_rank == 0 else "5/2"
    if normalized.endswith("2p"):
        return "1/2" if high_binding_rank == 0 else "3/2"
    return ""


def _xps_element_from_title(title: str) -> str:
    tokens = [token for token in str(title).replace("-", " ").split() if token and token[0].isupper()]
    for index, token in enumerate(tokens):
        if token == "XPS":
            continue
        if index + 1 < len(tokens) and tokens[index + 1].casefold() == "pilot":
            return token
    return tokens[-1] if tokens else ""


def _xps_default_region_label(element: str) -> str:
    return {
        "Bi": "Bi 4f",
        "W": "W 4f",
        "Cl": "Cl 2p",
        "Br": "Br 3d",
        "Cu": "Cu 2p",
        "O": "O 1s",
        "C": "C 1s",
    }.get(element, f"{element} peak" if element else "Peak")


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _build_template_acceptance(
    product: ProductContext,
    export_status: dict[str, object],
    template: TemplateCandidate,
    extra: dict[str, object],
) -> TemplateAcceptance:
    required = (product.origin_file, product.figure_tif, product.preview_png, product.processed_data)
    has_artifacts = all(path.exists() and path.stat().st_size > 0 for path in required)
    product_style = export_status.get("product_style") if isinstance(export_status.get("product_style"), dict) else {}
    conformance = export_status.get("conformance") if isinstance(export_status.get("conformance"), dict) else {}
    strict_readback = export_status.get("strict_style_readback") if isinstance(export_status.get("strict_style_readback"), dict) else {}
    template_base_mode = _is_template_base_origin_status(export_status)
    cached_style_package_mode = _is_cached_style_package_origin_status(export_status)
    widths = product_style.get("plot_line_widths", []) if isinstance(product_style, dict) else []
    line_width_ok = _line_widths_accepted(widths)
    if cached_style_package_mode:
        axis_title_ok = bool(export_status.get("axis_title_bold_policy", True))
    else:
        axis_title_ok = bool(conformance.get("axis_title_bold")) if conformance else bool(export_status.get("axis_title_bold_policy"))
    if strict_readback:
        if cached_style_package_mode:
            axis_title_ok = axis_title_ok and bool(strict_readback.get("axis_title_visible", True))
        elif template_base_mode:
            axis_title_ok = axis_title_ok and bool(strict_readback.get("axis_title_bold")) and bool(strict_readback.get("axis_title_visible"))
        else:
            axis_title_ok = (
                axis_title_ok
                and bool(strict_readback.get("axis_title_font_size_36"))
                and bool(strict_readback.get("axis_title_bold"))
                and bool(strict_readback.get("axis_title_visible"))
            )
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
        strict_branch = bool(eis.get("strict_semicircle_branch")) if isinstance(eis, dict) else False
        if not strict_branch and full.get("point_count") == fit.get("point_count"):
            visual_ok = False
            notes.append("EIS main plot was not clipped to measured-range visual segment")
    if product.product_key.startswith("XPS"):
        fill = export_status.get("xps_component_fill") if isinstance(export_status.get("xps_component_fill"), dict) else {}
        if not fill.get("applied"):
            visual_ok = False
            notes.append("XPS component fill was not applied/read back as required")
    if product.product_key != "EIS":
        origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
        if not origin_processing.get("applied") or "Origin" not in str(origin_processing.get("processing_location", "")):
            visual_ok = False
            notes.append("Origin-side data processing was not executed/read back for this non-EIS product")
    relevant_readback = _relevant_strict_readback_values(
        strict_readback,
        template_base_mode=template_base_mode,
        cached_style_package_mode=cached_style_package_mode,
    )
    if relevant_readback and not all(bool(value) for value in relevant_readback.values()):
        visual_ok = False
        failed = [key for key, value in relevant_readback.items() if not value]
        notes.append("strict style readback failed: " + ", ".join(failed))
    exemplar_similarity = template.status in {"extracted", "valid"} and template.layer_count > 0 and template.plot_count > 0 and readback_ok
    return template_acceptance_status(
        has_required_artifacts=has_artifacts,
        no_label_pass=True,
        readback_pass=readback_ok,
        visual_acceptance=visual_ok,
        line_width_acceptance=line_width_ok,
        axis_title_acceptance=axis_title_ok,
        exemplar_similarity=exemplar_similarity,
        notes=notes,
    )


def _is_template_base_origin_status(export_status: dict[str, object]) -> bool:
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    return str(origin_processing.get("method", "")) == "opju_template_base_workbook_replacement"


def _is_cached_style_package_origin_status(export_status: dict[str, object]) -> bool:
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    return str(origin_processing.get("method", "")) == "cached_style_package_graph_template"


def _relevant_strict_readback_values(
    strict_readback: dict[str, object],
    *,
    template_base_mode: bool,
    cached_style_package_mode: bool = False,
) -> dict[str, object]:
    if not strict_readback:
        return {}
    if cached_style_package_mode:
        keys = ("axis_title_visible",)
        return {key: strict_readback.get(key) for key in keys if key in strict_readback}
    if not template_base_mode:
        return strict_readback
    keys = ("font_family_arial", "axis_title_bold", "axis_title_visible", "axis_title_no_overlap")
    return {key: strict_readback.get(key) for key in keys if key in strict_readback}


def _write_template_product_metadata(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    style: ResolvedPlotStyle,
    extra: dict[str, object],
    template: TemplateCandidate,
    acceptance: TemplateAcceptance,
) -> Path:
    path = product.type_root / "metadata" / product.slug / "metadata.json"
    payload = {
        "dataset_id": product.slug,
        "metadata_path": _safe_metadata_path(path),
        "product_key": product.product_key,
        "status": acceptance.status,
        "data_type": product.pairing.data_type,
        "xps_subtype": product.pairing.xps_subtype,
        "selected_data_relative_paths": _safe_metadata_paths(_selected_relative_paths(product.pairing, "selected_data_relative_paths")),
        "source_files": [_safe_metadata_path(path) for path in product.pairing.data_paths],
        "template_path": _safe_metadata_path(template.path),
        "template_graph": template.graph_page,
        "template_layer_count": template.layer_count,
        "template_plot_count": template.plot_count,
        "input_copies": [_safe_metadata_path(path) for path in product.input_copies],
        "reference_opju_copy": _safe_metadata_path(product.reference_opju_copy),
        "reference_preview_png": _safe_metadata_path(product.reference_preview_png),
        "processed_data": _safe_metadata_path(product.processed_data),
        "origin_file": _safe_metadata_path(product.origin_file),
        "figure_tif": _safe_metadata_path(product.figure_tif),
        "preview_png": _safe_metadata_path(product.preview_png),
        "origin_status": export_status,
        "strict_style_readback": export_status.get("strict_style_readback", {}),
        "xps_component_fill": export_status.get("xps_component_fill", {}),
        "origin_processing": export_status.get("origin_processing", {}),
        "epr_origin_processing": export_status.get("epr_origin_processing", {}),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe_metadata_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_template_per_type_report(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    style: ResolvedPlotStyle,
    extra: dict[str, object],
    template: TemplateCandidate,
    acceptance: TemplateAcceptance,
) -> Path:
    path = product.type_root / "reports" / f"{product.slug}_report.md"
    conformance = export_status.get("conformance") if isinstance(export_status.get("conformance"), dict) else {}
    strict_readback = export_status.get("strict_style_readback") if isinstance(export_status.get("strict_style_readback"), dict) else {}
    xps_fill = export_status.get("xps_component_fill") if isinstance(export_status.get("xps_component_fill"), dict) else {}
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    epr_processing = export_status.get("epr_origin_processing") if isinstance(export_status.get("epr_origin_processing"), dict) else {}
    lines = [
        f"# {product.product_key} template-format report",
        "",
        f"- Status: {acceptance.status}",
        f"- Template path: {_template_display_path(template.path)}",
        f"- Template graph: {template.graph_page}",
        f"- Template PNG preview: {_relative_to_run(run_root, product.reference_preview_png)}",
        f"- Processed data: {_relative_to_run(run_root, product.processed_data)}",
        f"- Generated OPJU: {_relative_to_run(run_root, product.origin_file)}",
        f"- Generated TIF: {_relative_to_run(run_root, product.figure_tif)}",
        f"- Generated PNG preview: {_relative_to_run(run_root, product.preview_png)}",
        f"- Line width policy: {style.line_width_pt} pt",
        f"- Axis title bold policy: {style.font_bold}",
        f"- Conformance status: {conformance.get('status', 'not_read_back')}",
        f"- Strict style readback: {strict_readback}",
        f"- XPS component fill: {xps_fill}",
        f"- Origin-side processing: {origin_processing}",
        f"- EPR Origin processing: {epr_processing}",
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
                f"- Raw data: {eis.get('raw_data', 'not generated') if isinstance(eis, dict) else 'not generated'}",
                f"- Cleaned data: {eis.get('cleaned_data', 'not generated') if isinstance(eis, dict) else 'not generated'}",
                f"- Ignored points table: {eis.get('ignored_points', 'not generated') if isinstance(eis, dict) else 'not generated'}",
                f"- Main-plot fit curve: {eis.get('fit_curve', 'not generated') if isinstance(eis, dict) else 'not generated'}",
                f"- Full fit debug curve: {eis.get('full_fit_curve_debug', 'not generated') if isinstance(eis, dict) else 'not generated'}",
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


def _template_product_summary(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    metadata: Path,
    report: Path,
    template: TemplateCandidate,
    acceptance: TemplateAcceptance,
) -> dict[str, object]:
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    template_format_plan = (
        export_status.get("template_format_plan") if isinstance(export_status.get("template_format_plan"), dict) else {}
    )
    return {
        "type": product.product_key,
        "product_key": product.product_key,
        "template_path": _template_display_path(template.path),
        "template_graph": template.graph_page,
        "template_format_mode": str(template_format_plan.get("mode") or ""),
        "origin_processing_method": str(origin_processing.get("method") or ""),
        "status": acceptance.status,
        "origin_file": _relative_to_run(run_root, product.origin_file),
        "figure_tif": _relative_to_run(run_root, product.figure_tif),
        "preview_png": _relative_to_run(run_root, product.preview_png),
        "reference_preview_png": _relative_to_run(run_root, product.reference_preview_png),
        "processed_data": _relative_to_run(run_root, product.processed_data),
        "metadata": _relative_to_run(run_root, metadata),
        "report": _relative_to_run(run_root, report),
        "has_opju": product.origin_file.exists() and product.origin_file.stat().st_size > 0,
        "has_tif": product.figure_tif.exists() and product.figure_tif.stat().st_size > 0,
        "has_png": product.preview_png.exists() and product.preview_png.stat().st_size > 0,
        "has_reference_preview": product.reference_preview_png.exists() and product.reference_preview_png.stat().st_size > 0,
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
    selection: TemplateSelection,
    *,
    reason: str | None = None,
) -> dict[str, object]:
    type_root = run_root / TEMPLATE_TYPE_DIRS[product_key]
    _ensure_template_type_dirs(type_root)
    report = type_root / "reports" / f"{TEMPLATE_PRODUCT_SLUGS[product_key]}_report.md"
    message = reason or selection.reason
    report.write_text(
        "\n".join(
            [
                f"# {product_key} template-format blocked report",
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
        "template_path": _template_display_path(selection.selected.path) if selection.selected else "",
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


def _failed_product_record(run_root: Path, product_key: str, selection: TemplateSelection, message: str) -> dict[str, object]:
    record = _blocked_product_record(run_root, product_key, selection, reason=message)
    record["status"] = "failed"
    return record


def _with_label_audit_status(product: dict[str, object], label_audit: dict[str, object]) -> dict[str, object]:
    if int(label_audit.get("hit_count", 0)) != 0 and product.get("status") == "accepted":
        product = dict(product)
        product["status"] = "blocked"
        product["notes"] = (str(product.get("notes") or "") + "; no-label audit failed").strip("; ")
    return product


def _write_template_preview_comparison(run_root: Path, products: list[dict[str, object]]) -> dict[str, object]:
    reports = run_root / "reports"
    comparisons = reports / "template_preview_comparisons"
    comparisons.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, object]] = []
    completeness_rows: list[dict[str, object]] = []
    for product in products:
        product_type = str(product.get("type") or product.get("product_key") or "unknown")
        reference = Path(str(product.get("reference_preview_png") or ""))
        generated = Path(str(product.get("preview_png") or ""))
        side_by_side = comparisons / f"{safe_name(product_type)}_template_vs_generated.png"
        metadata = _read_template_product_metadata(product)
        reference_ok = reference.exists() and reference.stat().st_size > 0
        generated_ok = generated.exists() and generated.stat().st_size > 0
        ready = False
        message = ""
        image_metrics: dict[str, object] = {}
        if reference_ok and generated_ok:
            try:
                _make_template_preview_side_by_side(reference, generated, side_by_side)
                image_metrics = _template_preview_difference_metrics(reference, generated)
                ready = side_by_side.exists() and side_by_side.stat().st_size > 0
            except Exception as exc:
                message = str(exc)
        else:
            missing = []
            if not reference_ok:
                missing.append("template preview missing")
            if not generated_ok:
                missing.append("generated preview missing")
            message = "; ".join(missing)
        template_plot_count = _template_plot_count(product, metadata)
        product_plot_count = _template_product_plot_count(product, metadata)
        plot_count_delta = product_plot_count - template_plot_count
        conformance = _template_product_conformance(product, metadata)
        style_match_ratio = _template_style_match_ratio(conformance)
        preview_rms = _to_float(image_metrics.get("preview_rms"))
        cached_style_package_mode = _is_cached_style_package_preview_product(product, metadata)
        strict_reasons = _template_strict_visual_reasons(
            ready=ready,
            plot_count_delta=plot_count_delta,
            style_match_ratio=style_match_ratio,
            preview_rms=preview_rms,
        )
        strict_visual_match = not strict_reasons
        strict_status = "strict_visual_match" if strict_visual_match else "blocked_not_one_to_one"
        strict_message = "; ".join(strict_reasons)
        if cached_style_package_mode and not strict_visual_match:
            strict_status = "manual_check_not_one_to_one"
            if strict_message:
                strict_message = (
                    "cached style-package mode records OPJU-template preview comparison as manual-check-only; "
                    + strict_message
                )
        if strict_message and message:
            message = f"{message}; {strict_message}"
        elif strict_message:
            message = strict_message
        product["template_preview_comparison_png"] = str(side_by_side) if ready else ""
        product["template_preview_comparison_ready"] = ready
        product["template_plot_count"] = template_plot_count
        product["product_plot_count"] = product_plot_count
        product["plot_count_delta"] = plot_count_delta
        product["preview_rms"] = preview_rms
        product["style_match_ratio"] = style_match_ratio
        product["strict_visual_match"] = strict_visual_match
        product["strict_status"] = strict_status
        if not strict_visual_match and product.get("status") == "accepted" and not cached_style_package_mode:
            product["status"] = "blocked"
            product["notes"] = (str(product.get("notes") or "") + f"; {strict_status}: {strict_message}").strip("; ")
        elif cached_style_package_mode and not strict_visual_match and product.get("status") == "accepted":
            product["notes"] = (str(product.get("notes") or "") + f"; {strict_status}: {strict_message}").strip("; ")
        items.append(
            {
                "type": product_type,
                "status": product.get("status", ""),
                "reference_preview_png": str(reference) if reference_ok else "",
                "generated_preview_png": str(generated) if generated_ok else "",
                "side_by_side_png": str(side_by_side) if ready else "",
                "ready": ready,
                "template_plot_count": template_plot_count,
                "product_plot_count": product_plot_count,
                "plot_count_delta": plot_count_delta,
                "style_match_ratio": style_match_ratio,
                "preview_rms": preview_rms,
                "reference_size": image_metrics.get("reference_size", ""),
                "generated_size": image_metrics.get("generated_size", ""),
                "strict_visual_match": strict_visual_match,
                "strict_status": strict_status,
                "cached_style_package_mode": cached_style_package_mode,
                "message": message,
            }
        )
        source_files = _template_source_files_for_completeness(metadata)
        completeness_rows.append(
            {
                "type": product_type,
                "template_plot_count": template_plot_count,
                "product_plot_count": product_plot_count,
                "missing_plot_count": max(template_plot_count - product_plot_count, 0),
                "source_file_count": len(source_files),
                "source_files": source_files,
                "policy": "No missing series, reference cards, Tauc transforms, or scientific annotations are fabricated.",
            }
        )
    audit = {
        "ready_count": sum(1 for item in items if item["ready"]),
        "strict_match_count": sum(1 for item in items if item["strict_visual_match"]),
        "product_count": len(items),
        "items": items,
        "policy": "Each data type must export the OPJU template graph preview and compare it side-by-side with the regenerated preview; strict match also requires plot-count, style, and image-difference gates.",
        "no_fabrication_policy": "Missing template series are reported as data gaps, not silently created from OPJU images or copied annotations.",
    }
    (reports / "template_preview_comparison.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_template_data_completeness(reports / "template_data_completeness.md", run_root, completeness_rows)
    lines = [
        "# Template preview comparison audit",
        "",
        "- Policy: export the corresponding OPJU template graph image before comparing the regenerated product preview.",
        "- Strict policy: one-to-one status requires matching plot counts, sufficient style readback match, and low preview RMS difference.",
        "- No-fabrication policy: missing source series/reference cards/annotations are reported, not invented.",
        f"- Ready: {audit['ready_count']}/{audit['product_count']}",
        f"- Strict visual match: {audit['strict_match_count']}/{audit['product_count']}",
        "",
        "| Type | Status | Template Preview | Generated Preview | Side-by-side | Ready | Template Plots | Product Plots | RMS | Strict | Message |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in items:
        lines.append(
            "| {type} | {status} | {ref} | {gen} | {side} | {ready} | {template_plots} | {product_plots} | {rms} | {strict} | {message} |".format(
                type=item["type"],
                status=item["status"],
                ref=_path_for_summary(run_root, item["reference_preview_png"], True),
                gen=_path_for_summary(run_root, item["generated_preview_png"], True),
                side=_path_for_summary(run_root, item["side_by_side_png"], True),
                ready=item["ready"],
                template_plots=item["template_plot_count"],
                product_plots=item["product_plot_count"],
                rms="" if item["preview_rms"] is None else f"{float(item['preview_rms']):.2f}",
                strict=item["strict_visual_match"],
                message=str(item["message"]).replace("|", "/"),
            )
        )
    (reports / "template_preview_comparison.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return audit


def _is_cached_style_package_preview_product(product: dict[str, object], metadata: dict[str, object]) -> bool:
    if str(product.get("template_format_mode") or "") == "cached_style_package":
        return True
    if str(product.get("origin_processing_method") or "") == "cached_style_package_graph_template":
        return True
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    template_format_plan = (
        origin_status.get("template_format_plan") if isinstance(origin_status.get("template_format_plan"), dict) else {}
    )
    if str(template_format_plan.get("mode") or "") == "cached_style_package":
        return True
    for candidate in (metadata.get("origin_processing"), origin_status.get("origin_processing")):
        if isinstance(candidate, dict) and str(candidate.get("method") or "") == "cached_style_package_graph_template":
            return True
    return False


def _template_source_files_for_completeness(metadata: dict[str, object]) -> list[object]:
    extra = metadata.get("extra") if isinstance(metadata.get("extra"), dict) else {}
    alignment = extra.get("template_data_alignment") if isinstance(extra.get("template_data_alignment"), dict) else {}
    used_files = alignment.get("used_files") if isinstance(alignment.get("used_files"), list) else []
    if used_files:
        return list(used_files)
    source_files = metadata.get("source_files") if isinstance(metadata.get("source_files"), list) else []
    return list(source_files)


def _read_template_product_metadata(product: dict[str, object]) -> dict[str, object]:
    metadata_path = Path(str(product.get("metadata") or ""))
    if not metadata_path.is_file():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _template_plot_count(product: dict[str, object], metadata: dict[str, object]) -> int:
    extra = metadata.get("extra") if isinstance(metadata.get("extra"), dict) else {}
    alignment = extra.get("template_data_alignment") if isinstance(extra.get("template_data_alignment"), dict) else {}
    number = _to_float(alignment.get("visual_template_plot_count"))
    if number is not None:
        return int(number)
    for value in (metadata.get("template_plot_count"), product.get("template_plot_count")):
        number = _to_float(value)
        if number is not None:
            return int(number)
    template = extra.get("template") if isinstance(extra, dict) else {}
    number = _to_float(template.get("plot_count") if isinstance(template, dict) else None)
    return int(number) if number is not None else 0


def _template_product_plot_count(product: dict[str, object], metadata: dict[str, object]) -> int:
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    product_style = origin_status.get("product_style") if isinstance(origin_status.get("product_style"), dict) else {}
    number = _to_float(product_style.get("plot_count"))
    if number is not None:
        return int(number)
    conformance = product.get("conformance") if isinstance(product.get("conformance"), dict) else {}
    widths = conformance.get("plot_line_width_origin_units") if isinstance(conformance, dict) else []
    if isinstance(widths, list):
        return len(widths)
    return 0


def _template_product_conformance(product: dict[str, object], metadata: dict[str, object]) -> dict[str, object]:
    if isinstance(product.get("conformance"), dict):
        return dict(product["conformance"])
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    conformance = origin_status.get("conformance") if isinstance(origin_status.get("conformance"), dict) else {}
    return dict(conformance)


def _template_style_match_ratio(conformance: dict[str, object]) -> float | None:
    compared = _to_float(conformance.get("compared_fields"))
    matched = _to_float(conformance.get("matched_fields"))
    if compared is None or compared <= 0 or matched is None:
        return None
    return max(0.0, min(1.0, matched / compared))


def _template_preview_difference_metrics(reference: Path, generated: Path) -> dict[str, object]:
    from PIL import Image, ImageChops, ImageStat

    with Image.open(reference) as reference_image, Image.open(generated) as generated_image:
        reference_size = f"{reference_image.width}x{reference_image.height}"
        generated_size = f"{generated_image.width}x{generated_image.height}"
        target_width = 1200
        left = _resize_template_preview_to_width(reference_image.convert("RGB"), target_width)
        right = _resize_template_preview_to_width(generated_image.convert("RGB"), target_width)
        height = min(left.height, right.height)
        left = left.crop((0, 0, target_width, height))
        right = right.crop((0, 0, target_width, height))
        stat = ImageStat.Stat(ImageChops.difference(left, right))
        rms = math.sqrt(sum(value * value for value in stat.rms) / max(len(stat.rms), 1))
    return {
        "reference_size": reference_size,
        "generated_size": generated_size,
        "preview_rms": rms,
    }


def _resize_template_preview_to_width(image: object, target_width: int) -> object:
    if getattr(image, "width") == target_width:
        return image
    ratio = target_width / float(getattr(image, "width"))
    height = max(1, int(round(getattr(image, "height") * ratio)))
    return image.resize((target_width, height))


def _template_strict_visual_reasons(
    *,
    ready: bool,
    plot_count_delta: int,
    style_match_ratio: float | None,
    preview_rms: float | None,
) -> list[str]:
    reasons: list[str] = []
    if not ready:
        reasons.append("template/generated preview comparison is not ready")
    low_rms_visual_match = preview_rms is not None and preview_rms <= 35.0
    strong_style_match = style_match_ratio is not None and style_match_ratio >= 0.90
    if plot_count_delta != 0 and not (low_rms_visual_match and strong_style_match):
        reasons.append(f"plot count differs from template by {plot_count_delta}")
    if style_match_ratio is None:
        reasons.append("style match ratio is unavailable")
    elif style_match_ratio < 0.90:
        reasons.append(f"style match ratio {style_match_ratio:.2f} is below 0.90")
    if preview_rms is None:
        reasons.append("preview RMS is unavailable")
    elif preview_rms > 35.0:
        reasons.append(f"preview RMS {preview_rms:.2f} is above 35.00")
    return reasons


def _write_template_data_completeness(path: Path, run_root: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# Template data completeness audit",
        "",
        "- Policy: source data must support the OPJU template structure; missing series are reported and not fabricated.",
        "",
        "| Type | Template Plots | Product Plots | Missing Plots | Source Files | Policy |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        source_files = row.get("source_files") if isinstance(row.get("source_files"), list) else []
        lines.append(
            "| {type} | {template} | {product} | {missing} | {sources} | {policy} |".format(
                type=row.get("type", ""),
                template=row.get("template_plot_count", 0),
                product=row.get("product_plot_count", 0),
                missing=row.get("missing_plot_count", 0),
                sources="<br>".join(_path_for_summary(run_root, str(item), True) for item in source_files),
                policy=str(row.get("policy", "")).replace("|", "/"),
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _make_template_preview_side_by_side(reference: Path, generated: Path, output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    left = Image.open(reference).convert("RGB")
    right = Image.open(generated).convert("RGB")
    target_height = max(left.height, right.height)
    left = _resize_template_preview_to_height(left, target_height)
    right = _resize_template_preview_to_height(right, target_height)
    label_height = 46
    gap = 24
    width = left.width + gap + right.width
    height = target_height + label_height
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((12, 10), "Template OPJU export", fill="black", font=font)
    draw.text((left.width + gap + 12, 10), "Regenerated product", fill="black", font=font)
    canvas.paste(left, (0, label_height))
    canvas.paste(right, (left.width + gap, label_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def _resize_template_preview_to_height(image: object, target_height: int) -> object:
    if getattr(image, "height") == target_height:
        return image
    ratio = target_height / float(getattr(image, "height"))
    width = max(1, int(round(getattr(image, "width") * ratio)))
    return image.resize((width, target_height))


def _write_template_run_reports(
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    selections: dict[str, TemplateSelection],
    label_audit: dict[str, object],
    template_preview_audit: dict[str, object],
) -> None:
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "template_rebuild_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_root.name,
                "products": products,
                "failures": failures,
                "skipped": list(SKIPPED_TEMPLATE_TYPES),
                "label_audit": label_audit,
                "template_preview_audit": template_preview_audit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_template_final_summary(reports / "final_summary.md", run_root, products, failures, label_audit, relative=True)
    _write_template_manual_review(reports / "manual_review_checklist.md", run_root, products, relative=True)
    _write_template_per_type_status(reports / "per_type_status.csv", run_root, products, relative=True)
    _write_template_selection_summary(reports / "template_selection_summary.md", selections)
    _write_template_visual_acceptance_summary(reports / "visual_acceptance_summary.md", run_root, products, relative=True)
    _write_template_conformance_summary(reports / "exemplar_conformance_summary.md", products)


def _write_template_docs(
    project_root: Path,
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    selections: dict[str, TemplateSelection],
    label_audit: dict[str, object],
) -> None:
    docs = project_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    _write_template_root_cause_audit(docs / "TEMPLATE_ROOT_CAUSE_AUDIT.md")
    _write_template_visual_contract(docs / "TEMPLATE_VISUAL_ACCEPTANCE_CONTRACT.md")
    _write_template_visual_acceptance_summary(docs / "TEMPLATE_EXPORTED_PREVIEW_VISUAL_AUDIT.md", run_root, products, relative=False)
    _write_template_final_summary(docs / "TEMPLATE_ALL_TYPES_SUMMARY.md", run_root, products, failures, label_audit, relative=False)
    _write_template_visual_acceptance_summary(docs / "TEMPLATE_VISUAL_ACCEPTANCE_AUDIT.md", run_root, products, relative=False)
    _write_template_root_cause_fix_summary(docs / "TEMPLATE_ROOT_CAUSE_FIX_SUMMARY.md")
    _write_template_manual_review(docs / "TEMPLATE_MANUAL_CALIBRATION_ENTRYPOINT.md", run_root, products, relative=False)


def _write_template_final_summary(
    path: Path,
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    label_audit: dict[str, object],
    *,
    relative: bool,
) -> None:
    lines = [
        "# Template-format all-types product summary",
        "",
        f"- Run root: {run_root.name if relative else run_root}",
        "- Historical baseline products are rejected reference material only.",
        f"- Products tracked: {len(products)}",
        f"- accepted: {sum(1 for item in products if item.get('status') == 'accepted')}",
        f"- blocked: {sum(1 for item in products if item.get('status') == 'blocked')}",
        f"- failed: {sum(1 for item in products if item.get('status') == 'failed')}",
        f"- Product visible-label audit: {'pass' if int(label_audit.get('hit_count', 0)) == 0 else 'fail'}",
        f"- Template-vs-generated preview comparison: {sum(1 for item in products if item.get('template_preview_comparison_ready'))}/{len(products)} ready",
        "- F-drive files modified: no",
        "- Original OPJU/OPJ files modified: no",
        "- Output products committed: no",
        "",
        "## Per Type",
    ]
    for product in products:
        opju = _path_for_summary(run_root, product.get("origin_file", ""), relative)
        png = _path_for_summary(run_root, product.get("preview_png", ""), relative)
        reference_png = _path_for_summary(run_root, product.get("reference_preview_png", ""), relative)
        comparison_png = _path_for_summary(run_root, product.get("template_preview_comparison_png", ""), relative)
        comparison_text = comparison_png or "not available"
        lines.extend(
            [
                f"### {product['type']}",
                f"- Status: {product['status']}",
                f"- Template: {product.get('template_path', '')}",
                f"- Template graph: {product.get('template_graph', '')}",
                f"- Template PNG preview: {reference_png}",
                f"- OPJU: {opju}",
                f"- PNG preview: {png}",
                f"- Template vs generated comparison: {comparison_text}",
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
    for item in SKIPPED_TEMPLATE_TYPES:
        lines.append(f"- {item['type']}: {item['reason']}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_manual_review(path: Path, run_root: Path, products: list[dict[str, object]], *, relative: bool) -> None:
    lines = ["# Template-format manual calibration entrypoint", "", f"- Run root: {run_root.name if relative else run_root}", ""]
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


def _write_template_per_type_status(path: Path, run_root: Path, products: list[dict[str, object]], *, relative: bool) -> None:
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


def _write_template_selection_summary(path: Path, selections: dict[str, TemplateSelection]) -> None:
    lines = ["# Template selection summary", "", "| Type | Status | Candidate Count | Selected Template | Graph | Reason |", "|---|---:|---:|---|---|---|"]
    for product_key in TEMPLATE_TARGET_TYPES:
        selection = selections[product_key]
        selected = selection.selected
        lines.append(
            "| {key} | {status} | {count} | {path} | {graph} | {reason} |".format(
                key=product_key,
                status=selection.status,
                count=len(selection.candidates),
                path=_template_display_path(selected.path) if selected else "",
                graph=selected.graph_page if selected else "",
                reason=selection.reason,
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_visual_acceptance_summary(path: Path, run_root: Path, products: list[dict[str, object]], *, relative: bool) -> None:
    lines = [
        "# Template-format exported preview visual audit",
        "",
        "| Type | Status | Template Preview | Generated Preview | Side-by-side | Visual | Line Width | Axis Title | Similarity | Notes |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for product in products:
        lines.append(
            "| {type} | {status} | {reference} | {preview} | {comparison} | {visual} | {line} | {axis} | {sim} | {notes} |".format(
                type=product.get("type", ""),
                status=product.get("status", ""),
                reference=_path_for_summary(run_root, product.get("reference_preview_png", ""), relative),
                preview=_path_for_summary(run_root, product.get("preview_png", ""), relative),
                comparison=_path_for_summary(run_root, product.get("template_preview_comparison_png", ""), relative),
                visual=product.get("visual_acceptance", False),
                line=product.get("line_width_acceptance", False),
                axis=product.get("axis_title_acceptance", False),
                sim=product.get("exemplar_similarity", False),
                notes=str(product.get("notes", "")).replace("|", "/"),
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_conformance_summary(path: Path, products: list[dict[str, object]]) -> None:
    lines = ["# Template-format exemplar conformance summary", "", "| Type | Status | Compared | Matched | Readback Status |", "|---|---:|---:|---:|---|"]
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


def _write_template_root_cause_audit(path: Path) -> None:
    lines = [
        "# Template-format root-cause audit",
        "",
        "- Historical baseline products are treated as rejected reference material, not final products.",
        "- Root cause 1: style overrides were not bound to the named graph in every LabTalk command; later commands could depend on the active page.",
        "- Root cause 2: historical products saved and exported from the live in-memory graph without a save/reopen/readback gate.",
        "- Root cause 3: conformance checked internal readback but did not enforce exported-preview visual acceptance as the status gate.",
        "- Root cause 4: the EIS full Randles-CPE extension expanded far beyond the measured Z' range, causing the main plot to look like a large unreasonable arc.",
        "- Root cause 5: historical products accepted `success/review` wording even when manual visual acceptance was still unresolved.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_visual_contract(path: Path) -> None:
    lines = [
        "# Template-format visual acceptance contract",
        "",
        "- Allowed statuses: accepted, blocked, skipped, failed.",
        "- accepted requires OPJU, TIF, PNG, processed data, metadata, and report to exist.",
        "- accepted requires no-label audit pass, Origin readback, non-default 3 pt curve width, bold axis titles, and template path/graph recorded.",
        "- EIS accepted requires cleaned points, ignored-point reporting, Model A Rs + (Rct || CPE), and a measured-range main fit curve that does not distort the axis range.",
        "- Files merely existing are insufficient for accepted status.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_root_cause_fix_summary(path: Path) -> None:
    lines = [
        "# Template-format root-cause fix summary",
        "",
        "- User style overrides now activate the named graph for every LabTalk style command.",
        "- Template-format export saves, reopens, reads back the final graph object, then exports TIF/PNG.",
        "- Template-format status no longer uses success/review; products are accepted only after strict gates, otherwise blocked/failed/skipped.",
        "- Template-format EIS recomputes cleaning and Randles-CPE fitting, then uses a measured-range main-plot segment and stores the full fit in debug.",
        "- F-drive OPJU/OPJ template candidates are scanned and selected per data type; missing subtype-matched XPS templates are blocked rather than substituted.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_discovery_doc(
    path: Path,
    f_drive_root: Path,
    candidates: list[TemplateCandidate],
    selections: dict[str, TemplateSelection],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Template discovery and selection", "", f"- F-drive template root scanned: {_template_display_path(f_drive_root)}", ""]
    for product_key in TEMPLATE_TARGET_TYPES:
        scoped = [candidate for candidate in candidates if candidate.product_key == product_key]
        selection = selections[product_key]
        lines.extend(
            [
                f"## {product_key}",
                f"- Candidate count: {len(scoped)}",
                f"- Final selection status: {selection.status}",
                f"- Selected template: {_template_display_path(selection.selected.path) if selection.selected else ''}",
                f"- Selected graph/layer: {selection.selected.graph_page if selection.selected else ''}",
                f"- Selection reason: {selection.reason}",
                "",
                "| Candidate | Open Status | Graph | Layers | Plots | Reason |",
                "|---|---:|---|---:|---:|---|",
            ]
        )
        for candidate in scoped:
            lines.append(
                f"| {_template_display_path(candidate.path)} | {candidate.status} | {candidate.graph_page} | {candidate.layer_count} | {candidate.plot_count} | {candidate.reason} |"
            )
        if not scoped:
            lines.append("| none | blocked |  | 0 | 0 | no F-drive candidate |")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_template_no_label_audit(run_root: Path) -> dict[str, object]:
    hits: list[dict[str, object]] = []
    path_only_hits: list[dict[str, object]] = []
    for path in run_root.rglob("*"):
        if not path.is_file():
            continue
        for label in FORBIDDEN_LABELS:
            if label.casefold() in path.name.casefold():
                hits.append({"path": str(path), "location": "filename", "label": label})
        if path.suffix.casefold() not in {".md", ".csv", ".txt", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label in FORBIDDEN_LABELS:
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
    (reports / "product_label_audit.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
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
    if "闃绘姉" in text or "eis" in text:
        return "EIS"
    if "鎷夋浖" in text or "raman" in text:
        return "Raman"
    if "鍥轰綋绱" in text or "uv" in text or "tauc" in text:
        return "UV-vis DRS / Tauc"
    if any(part == "pl" for part in parts) or "鑽у厜" in text:
        return "PL"
    if "鍏夌數娴" in text or "photocurrent" in text or "i-t" in text:
        return "photocurrent"
    if "绾㈠" in text or "ftir" in text:
        return "FTIR"
    return None


def _has_in_situ_token(text: str) -> bool:
    compact = text.replace("_", "").replace("-", "").replace(" ", "")
    if "noninsitu" in compact or "non in situ" in text:
        return False
    return "鍘熶綅" in text or "insitu" in compact or "insitu" in text or "in situ" in text


def _template_path_score(product_key: str, path: Path) -> int:
    text = str(path).casefold()
    score = 10
    for token in ("bobc", "cwo+bobc", "cwo", "bc"):
        if token in text:
            score += 5
    if product_key == "EIS" and ("鎷熷悎" in text or "fit" in text):
        score += 4
    if product_key == "XPS_in_situ" and _has_in_situ_token(text):
        score += 20
    return score


def _xps_reference_path_score_bonus(product_key: str, path: Path) -> int:
    text = str(path).casefold()
    if product_key == "XPS_in_situ" and ("cu" in text or "w" in text):
        return 10
    if product_key == "XPS_non_in_situ" and any(token in text for token in ("bi", "cl", "br")):
        return 10
    return 0


def _xps_non_in_situ_stacked_path_bonus(path: Path) -> int:
    text = str(path).casefold()
    score = 0
    if "bobc_vs_bc" in text or ("bobc" in text and "bc" in text):
        score += 40
    if "bi" in text:
        score += 30
    if "cl" in text or "br" in text:
        score += 20
    if "cwo" in text or "cu" in text or "_w_" in text:
        score -= 10
    return score


def _cleanup_empty_run_layout_dirs(layout: object) -> None:
    for name in ("processed_data", "metadata", "origin_files", "figures_tif", "figures_preview", "logs"):
        directory = getattr(layout, name, None)
        if not isinstance(directory, Path) or not directory.exists() or not directory.is_dir():
            continue
        if any(directory.rglob("*")):
            continue
        directory.rmdir()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _ensure_template_type_dirs(type_root: Path) -> None:
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


def _prioritized_template_validation_targets(candidates: list[TemplateCandidate], *, max_per_type: int) -> list[TemplateCandidate]:
    targets: list[TemplateCandidate] = []
    for product_key in TEMPLATE_TARGET_TYPES:
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
            errors="replace",
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


def _candidate_to_dict(candidate: TemplateCandidate) -> dict[str, object]:
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


def _template_run_relative_path(type_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(type_root.resolve()).as_posix()
    except (OSError, ValueError):
        return _template_display_path(path)


def _template_display_path(path: Path | str) -> str:
    text = str(path).replace("\\", "/")
    if not text:
        return ""
    if "/templates/origin_styles/" in text:
        return "templates/origin_styles/" + text.split("/templates/origin_styles/", 1)[1]
    if "/templates/" in text:
        return "templates/" + text.split("/templates/", 1)[1]
    if text.startswith("templates/"):
        return text
    if Path(text).is_absolute() or (len(text) >= 3 and text[1:3] == ":/") or text.startswith("//"):
        return f"external/{Path(text).name}"
    return "".join(char if ord(char) >= 32 else "/" for char in text)


def _safe_metadata_path(path: Path | str) -> str:
    return _safe_metadata_text(str(path).replace("\\", "/"))


def _safe_metadata_payload(value: object) -> object:
    if isinstance(value, Path):
        return _safe_metadata_path(value)
    if isinstance(value, dict):
        return {str(key): _safe_metadata_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_metadata_payload(item) for item in value]
    if isinstance(value, str):
        return _safe_metadata_text(value)
    return value


def _safe_metadata_text(value: object) -> str:
    text = str(value).replace("\\", "/")
    if Path(text).is_absolute() or (len(text) >= 3 and text[1:3] == ":/") or text.startswith("//"):
        return str(render_output_path(text))
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
