from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.core.file_utils import file_sha256
from src.core.image_artifacts import (
    expected_raster_pixels,
    validate_tif_physical_resolution,
)
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.plot_labels import XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE
from src.core.template_product_common import (
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
from src.core.epr_jeol import read_verified_jeol_export_series
from src.core.epr_overlay import DEFAULT_EPR_GROUPS
from src.core.remaining_template_products import (
    _build_remaining_processed_plot_table,
    _coerced_xy_rows,
    _data_points_rows,
    load_remaining_pairings,
)
from src.core.runtime_paths import create_run_output_layout, resolve_output_root
from src.core.table_reader import read_table
from src.core.xrd_no_card_overlay import xrd_no_card_offset_for_index
from src.core.xps_heterojunction import (
    XpsFitRecord,
    XpsHeterojunctionOptions,
    _component_key,
    _select_best_records,
    build_comparison_plan,
    load_xps_fit_workbooks,
)
from src.origin.conformance import compare_style_snapshots
from src.origin.embedded_template_snapshots import (
    embedded_template_path,
    embedded_template_snapshot_dict,
)
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.style_registry import (
    load_origin_style_manifest,
    origin_style_asset_runtime_validated,
    origin_style_manifest_path,
    resolve_origin_style_asset,
    resolve_origin_runtime_style_asset,
    validate_origin_style_asset_integrity,
)
from src.origin.style_mimic import OpjuStyleSnapshot, apply_style_snapshot, extract_style_snapshot, read_graph_style_snapshot
from src.origin.text_format import origin_bold_text
from src.origin.user_style import ResolvedPlotStyle, apply_resolved_style_overrides, load_user_plot_style, resolve_user_plot_style
from src.processors.base import safe_name
from src.processors.calculations import bet_processed_table, mott_schottky_numeric
from src.processors.eis import (
    EisPoint,
    clean_eis_file,
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
    "Mott-Schottky",
)

TEMPLATE_ACCEPTED_TYPES = TEMPLATE_TARGET_TYPES
TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES = TEMPLATE_TARGET_TYPES

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
    "Mott-Schottky": "Mott_Schottky",
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
    "Mott-Schottky": "Mott_Schottky_exemplar",
}

FIRST_BATCH_TYPES = {"BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR"}
SKIPPED_TEMPLATE_TYPES = (
    {
        "type": "HPLC/LC",
        "status": "skipped",
        "reason": "No reviewed OPJU exemplar is available; conversion/selectivity/yield and product identity remain deferred.",
    },
    {
        "type": "reaction_condition_screening",
        "status": "skipped",
        "reason": "No clear reviewed data table plus OPJU pair is available for final template product generation.",
    },
)

PREFERRED_EPR_TEMPLATE_DIR_PARTS = (
    "\u7ed3\u679c\u6c47\u603b",
    "EPR",
    "final_EPR_OPJU_package_20260602",
    "origin_files",
)

OriginExporter = Callable[[ProductContext, ResolvedPlotStyle], dict[str, object]]
PROJECT_LOCAL_TEMPLATE_SOURCES = frozenset({"project_origin_style_asset", "embedded_template_snapshot"})


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
    prefer_project_style_assets: bool = False
    external_reference_preview_comparison: bool = False
    asset_only: bool = False
    exemplar_driven: bool = False
    compact_output: bool = False
    only_type: str | None = None
    style_replay_report: Path | None = None


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


def build_external_reference_candidate_pool(
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
    candidates = build_template_candidate_pool(
        f_drive_paths,
        xps_reference_paths,
        f_drive_root=f_drive_root,
        xps_reference_root=xps_reference_root,
        xps_non_in_situ_paths=xps_non_in_situ_paths,
        xps_non_in_situ_root=xps_non_in_situ_root,
        xps_reference_templates_for_all_xps=xps_reference_templates_for_all_xps,
        xps_templates_from_reference_only=xps_templates_from_reference_only,
    )
    candidates.extend(classify_template_f_drive_xps_reference_candidates(f_drive_paths, f_drive_root=f_drive_root))
    return candidates


def classify_template_f_drive_xps_reference_candidates(paths: list[Path], *, f_drive_root: Path) -> list[TemplateCandidate]:
    candidates: list[TemplateCandidate] = []
    for path in paths:
        if path.suffix.casefold() not in {".opju", ".opj"}:
            continue
        if not _is_relative_to(path, f_drive_root):
            continue
        if not _is_f_drive_xps_path(path):
            continue
        for product_key in ("XPS_in_situ", "XPS_non_in_situ"):
            candidates.append(
                TemplateCandidate(
                    product_key=product_key,
                    path=path,
                    source="f_drive_xps_reference_scan",
                    path_score=_template_path_score(product_key, path) + 60 + _xps_reference_path_score_bonus(product_key, path),
                    reason="classified by F-drive XPS folder for external reference comparison",
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
        asset = resolve_origin_runtime_style_asset(project_root, product_key, manifest_path)
        if asset is None:
            continue
        style_asset = asset.to_dict(project_root)
        runtime_path = asset.runtime_asset_path or asset.format_theme_path
        snapshot_layer_count, snapshot_plot_count = _style_asset_snapshot_counts(asset.style_snapshot_path)
        candidates.append(
            TemplateCandidate(
                product_key=product_key,
                path=runtime_path,
                source="project_origin_style_asset",
                path_score=1,
                status="valid",
                graph_page=asset.graph_page or "Graph1",
                layer_count=_manifest_positive_int(
                    raw,
                    ("layer_count", "template_layer_count"),
                    default=snapshot_layer_count,
                ),
                plot_count=_manifest_positive_int(
                    raw,
                    ("template_plot_count", "plot_count", "product_plot_count"),
                    default=snapshot_plot_count,
                ),
                reason=(
                    "project-local independently validated Origin graph template"
                    if asset.runtime_asset_kind == "otpu"
                    else "project-local saved Origin format theme fallback"
                ),
                metadata={
                    "style_package": True,
                    "style_asset": style_asset,
                    "manifest_entry": _safe_manifest_entry(raw),
                },
            )
        )
    return candidates


def _style_asset_snapshot_counts(path: Path | None) -> tuple[int, int]:
    if path is None:
        return 1, 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Origin style snapshot must be a JSON object: {path}")
    layer_count = _manifest_positive_int(payload, ("layer_count",), default=1)
    plot_count = _manifest_positive_int(payload, ("plot_count",), default=1)
    return layer_count, plot_count


def _manifest_positive_int(raw: dict[str, object], keys: tuple[str, ...], *, default: int) -> int:
    for key in keys:
        try:
            value = int(float(str(raw.get(key, "")).strip()))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return default


def _safe_manifest_entry(raw: dict[str, object]) -> dict[str, object]:
    keep = {
        "product_key",
        "data_type",
        "graph_page",
        "format_theme",
        "graph_template",
        "template_opju",
        "source_opju",
        "preview_png",
        "reference_preview_png",
        "template_preview_comparison_png",
        "data_hint_paths",
        "status",
        "template_plot_count",
        "plot_count",
        "product_plot_count",
        "layer_count",
        "preview_rms",
    }
    return {key: raw[key] for key in keep if key in raw}


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
        if candidate.source == "embedded_template_snapshot":
            validated.append(candidate)
            continue
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
        copied: Path | None = None
        try:
            copied = _copy_template_for_scan(candidate.path, scan_copy_root, copy_index)
            copy_index += 1
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
                    metadata={"scan_copy": str(copied) if copied is not None else ""},
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
        if candidate.status in {"extracted", "valid", "embedded"} and candidate.layer_count > 0 and candidate.plot_count > 0 and candidate.graph_page
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


def _select_external_reference_template(
    product: ProductContext,
    selections: dict[str, TemplateSelection],
) -> TemplateCandidate | None:
    product_key = product.product_key
    selection = selections.get(product_key)
    if selection is None or selection.status != "selected" or selection.selected is None:
        return None
    candidate = _select_template_xps_template_for_product(product, selection) if product_key.startswith("XPS") else selection.selected
    if candidate.path.suffix.casefold() not in {".opju", ".opj"}:
        return None
    if candidate.status not in {"extracted", "valid"}:
        return None
    if not candidate.graph_page:
        return None
    return candidate


def _external_reference_source_path(candidate: TemplateCandidate) -> Path:
    scan_copy = candidate.metadata.get("scan_copy") if isinstance(candidate.metadata, dict) else None
    if scan_copy:
        path = Path(str(scan_copy))
        if path.is_file():
            return path
    return candidate.path


def _select_template_xps_template_for_product(product: ProductContext, selection: TemplateSelection) -> TemplateCandidate:
    selected = selection.selected
    if selected is None or not product.product_key.startswith("XPS"):
        if selected is None:
            raise ValueError(f"No selected template for {product.product_key}")
        return selected
    usable = [
        candidate
        for candidate in selection.candidates
        if candidate.status in {"extracted", "valid", "embedded"} and candidate.layer_count > 0 and candidate.plot_count > 0
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
    return (
        "_component_" in header
        and not header.endswith("_fill_baseline")
        and not header.endswith("_fill_upper")
    )


def is_template_xps_component_fill_upper_header(header: str) -> bool:
    return "_component_" in header and header.endswith("_fill_upper")


def is_template_xps_component_fill_baseline_header(header: str) -> bool:
    return header.endswith("_fill_baseline")


def template_xps_component_fill_pairs(headers: list[str]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    series_headers = headers[1:]
    for plot_index, header in enumerate(series_headers, start=1):
        if not (
            is_template_xps_component_curve_header(header)
            or is_template_xps_component_fill_upper_header(header)
        ):
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
    if options.asset_only and options.exemplar_driven:
        raise ValueError("asset_only and exemplar_driven are mutually exclusive")
    project_root = project_root.resolve()
    style_replay_evidence = _load_independent_style_replay_evidence(
        project_root,
        options.style_replay_report,
    )
    roots = root_map or build_default_root_map(project_root)
    output_root = resolve_output_root(project_root, explicit=options.output_root)
    timestamp = options.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    target_types = _template_target_types(options)
    if options.asset_only:
        _require_asset_only_style_integrity(project_root, target_types)
    first_pairings = {item.product_key: item for item in load_target_pairings(options.pairing_path, roots)}
    remaining_pairings = {item.product_key: item for item in load_remaining_pairings(options.pairing_path, roots)}
    remaining_pairings = _repair_mott_pairings(remaining_pairings, roots)
    if options.exemplar_driven:
        first_pairings, remaining_pairings = _repair_exemplar_driven_pairings(first_pairings, remaining_pairings, roots)
    pairings_by_key = {**remaining_pairings, **first_pairings}
    use_project_style_assets_only = options.asset_only or ((not options.exemplar_driven) and options.project_style_asset_fallback and (
        options.prefer_project_style_assets
        or (
            options.f_drive_template_root is None
            and options.xps_reference_template_root is None
            and options.xps_non_in_situ_template_root is None
            and not options.external_reference_preview_comparison
        )
    ))
    local_style_root = project_root / "templates" / "origin_styles"
    f_drive_root = local_style_root if options.asset_only else (options.f_drive_template_root or Path("F:/") / "\u8bfe\u9898" / "LL" / "\u68c0\u6d4b")
    xps_reference_root = local_style_root if options.asset_only else (options.xps_reference_template_root or roots.get("workspace_xps_reference") or (project_root.parent / "xps\u53c2\u8003\u56fe\u50cf"))
    xps_non_in_situ_root = None if options.asset_only else options.xps_non_in_situ_template_root
    if options.exemplar_driven:
        candidates = _build_pairing_template_candidates(pairings_by_key, target_types)
        template_source_root = options.pairing_path
    elif use_project_style_assets_only:
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
    external_reference_candidates: list[TemplateCandidate] = []
    if options.external_reference_preview_comparison and not options.exemplar_driven and not options.asset_only:
        external_reference_candidates = build_external_reference_candidate_pool(
            scan_template_f_drive_template_paths(f_drive_root) if f_drive_root.exists() else [],
            scan_template_optional_template_paths(xps_reference_root),
            f_drive_root=f_drive_root,
            xps_reference_root=xps_reference_root,
            xps_non_in_situ_paths=scan_template_optional_template_paths(xps_non_in_situ_root),
            xps_non_in_situ_root=xps_non_in_situ_root,
            xps_reference_templates_for_all_xps=options.xps_reference_templates_for_all_xps,
            xps_templates_from_reference_only=options.xps_templates_from_reference_only,
        )
    layout = create_run_output_layout(
        project_root,
        scope=options.run_scope,
        command=options.command_name,
        mode=("asset_only_with_origin" if options.with_origin else "asset_only_no_origin")
        if options.asset_only
        else ("with_origin" if options.with_origin else "no_origin"),
        input_paths=(
            [options.pairing_path, template_source_root]
            if options.asset_only
            else [options.pairing_path, template_source_root, xps_reference_root]
        )
        + ([options.style_replay_report] if options.style_replay_report else []),
        timestamp=timestamp,
        no_origin=not options.with_origin,
        dry_run=False,
        output_base=output_root / "runs",
    )
    for product_key in target_types:
        _ensure_template_type_dirs(_template_type_root(layout.root, product_key, compact=options.compact_output), compact=options.compact_output)
    validator = template_validator or validate_template_candidates
    max_validation_per_type = len(candidates) if options.exemplar_driven else 5
    if candidates:
        if template_validator is None:
            validated = validate_template_candidates(
                candidates,
                layout.root / "template_scan_copies",
                max_per_type=max_validation_per_type,
            )
        else:
            validated = validator(candidates, layout.root / "template_scan_copies")
    else:
        validated = []
    external_validated = (
        validate_template_candidates(
            external_reference_candidates,
            layout.root / "template_reference_scan_copies",
            max_per_type=len(external_reference_candidates) if options.exemplar_driven else 5,
        )
        if external_reference_candidates and template_validator is None
        else (
            validator(external_reference_candidates, layout.root / "template_reference_scan_copies")
            if external_reference_candidates
            else []
        )
    )
    if (options.project_style_asset_fallback or options.asset_only) and not options.exemplar_driven:
        project_style_candidates = classify_template_project_style_asset_candidates(project_root)
        if options.prefer_project_style_assets and project_style_candidates:
            validated = project_style_candidates
        else:
            validated.extend(project_style_candidates)
    selections = {product_key: select_template(product_key, validated) for product_key in target_types}
    external_reference_selections = {
        product_key: select_template(product_key, external_validated)
        for product_key in target_types
    } if external_validated else {}
    _write_template_discovery_doc(
        layout.root / "reports" / "template_discovery_and_selection.md",
        template_source_root,
        validated,
        selections,
        target_types=target_types,
    )
    if external_reference_selections:
        _write_template_selection_summary(
            layout.root / "reports" / "external_reference_template_selection_summary.md",
            external_reference_selections,
            target_types=target_types,
        )

    user_config = load_user_plot_style(project_root, options.user_style_path)
    if options.global_style_override:
        user_config = _merge_global_style_override(user_config, options.global_style_override)
    exporter = origin_exporter or (lambda product, style: export_template_product_with_origin(product, style))
    products: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for product_key in target_types:
        selection = selections[product_key]
        if selection.status != "selected" or selection.selected is None:
            record = _blocked_product_record(
                layout.root,
                product_key,
                selection,
                compact=options.compact_output,
                asset_only=options.asset_only,
            )
            products.append(record)
            continue
        pairing = first_pairings.get(product_key) or remaining_pairings.get(product_key)
        if pairing is None:
            record = _blocked_product_record(
                layout.root,
                product_key,
                selection,
                reason="No reviewed real-data pairing found.",
                compact=options.compact_output,
                asset_only=options.asset_only,
            )
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
                compact_output=options.compact_output,
            )
            active_template = _select_template_xps_template_for_product(product, selection)
            if active_template.path != selection.selected.path:
                reference_dir = "reference_opju" if active_template.path.suffix.casefold() in {".opju", ".opj"} else "format_assets"
                product = replace(
                    product,
                    reference_opju_copy=_copy_reference(active_template.path, product.type_root / reference_dir),
                )
            if active_template.path != selection.selected.path or active_template.graph_page != selection.selected.graph_page:
                extra["template"] = _candidate_to_dict(active_template)
            external_reference = _select_external_reference_template(product, external_reference_selections)
            if external_reference is not None:
                external_reference_source = _external_reference_source_path(external_reference)
                product = replace(
                    product,
                    external_reference_opju=external_reference_source,
                    external_reference_graph=external_reference.graph_page,
                    external_reference_source=external_reference.source,
                )
                external_reference_payload = _candidate_to_dict(external_reference)
                external_reference_payload["scan_copy"] = _relative_to_run(layout.root, external_reference_source)
                extra["external_reference_template"] = external_reference_payload
            elif options.external_reference_preview_comparison:
                if product.reference_preview_png.exists():
                    product.reference_preview_png.unlink()
                extra["external_reference_template"] = {
                    "status": "missing_external_reference",
                    "reason": "No validated F-drive/reference OPJU was selected for direct reference preview export.",
                }
            style = resolve_user_plot_style(product_key, exemplar=active_template.metadata.get("snapshot"), user_config=user_config)
            export_status: dict[str, object] = {"ok": False, "message": "Origin export skipped"}
            if options.with_origin:
                export_status = exporter(product, style)
            acceptance = _build_template_acceptance(product, export_status, active_template, extra)
            metadata = _write_template_product_metadata(
                layout.root,
                product,
                export_status,
                style,
                extra,
                active_template,
                acceptance,
                asset_only=options.asset_only,
            )
            report = _write_template_per_type_report(layout.root, product, export_status, style, extra, active_template, acceptance)
            products.append(
                _template_product_summary(
                    layout.root,
                    product,
                    export_status,
                    metadata,
                    report,
                    active_template,
                    acceptance,
                    asset_only=options.asset_only,
                )
            )
        except Exception as exc:
            failures.append({"product_key": product_key, "message": str(exc)})
            products.append(
                _failed_product_record(
                    layout.root,
                    product_key,
                    selection,
                    str(exc),
                    compact=options.compact_output,
                    asset_only=options.asset_only,
                )
            )

    label_audit = _write_template_no_label_audit(layout.root)
    products = [_with_label_audit_status(product, label_audit) for product in products]
    template_preview_audit = _write_template_preview_comparison(
        layout.root,
        products,
        label_audit=label_audit,
        style_replay_evidence=style_replay_evidence,
    )
    skipped = _skipped_template_types(options, roots)
    _write_template_run_reports(layout.root, products, failures, selections, label_audit, template_preview_audit, skipped, target_types=target_types)
    if options.compact_output:
        _cleanup_compact_transient_dirs(layout.root)
    if options.cleanup_empty_run_layout_dirs:
        _cleanup_empty_run_layout_dirs(layout)
    return {
        "run_root": str(layout.root),
        "products": products,
        "failures": failures,
        "skipped": skipped,
        "summary": {
            "product_count": len(products),
            "accepted_count": sum(1 for item in products if item.get("status") == "accepted"),
            "blocked_count": sum(1 for item in products if item.get("status") == "blocked"),
            "failed_count": sum(1 for item in products if item.get("status") == "failed"),
            "required_product_count": len(products),
            "with_origin": bool(options.with_origin),
            "label_audit_pass": _label_audit_passes(label_audit),
            "template_preview_comparison_ready": int(template_preview_audit.get("ready_count", 0)) == len(products),
            "asset_only": bool(options.asset_only),
            "external_template_dependency": False if options.asset_only else any(
                bool(item.get("external_template_dependency")) for item in products
            ),
            "exemplar_driven": bool(options.exemplar_driven),
            "compact_output": bool(options.compact_output),
        },
    }


def _merge_global_style_override(user_config: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(user_config)
    global_config = merged.get("global") if isinstance(merged.get("global"), dict) else {}
    merged["global"] = {**dict(global_config), **dict(override)}
    return merged


def _require_asset_only_style_integrity(project_root: Path, target_types: tuple[str, ...]) -> None:
    result = validate_origin_style_asset_integrity(project_root, required_product_keys=target_types)
    failures = [str(item) for item in result.get("failures", [])]
    if int(result.get("schema_version", 0) or 0) < 2:
        failures.insert(0, "Origin style manifest schema v2 is required for hash-verified asset-only generation")
    manifest = load_origin_style_manifest(project_root)
    validation_required = {
        str(item.get("product_key") or item.get("data_type") or "")
        for item in manifest.get("assets", [])
        if isinstance(item, dict)
        and str(item.get("asset_kind") or "oth").casefold().lstrip(".") != "oth"
    }
    runtime_validated = {
        str(item.get("product_key") or item.get("data_type") or "")
        for item in manifest.get("assets", [])
        if isinstance(item, dict) and origin_style_asset_runtime_validated(item)
    }
    missing_runtime_validation = [
        product_key
        for product_key in target_types
        if product_key in validation_required and product_key not in runtime_validated
    ]
    if missing_runtime_validation:
        failures.append(
            "missing independent fresh-project same-data visual validation: "
            + ", ".join(missing_runtime_validation)
        )
    if not bool(result.get("ok")) or failures:
        details = "; ".join(failures) or "unknown style-asset integrity failure"
        raise ValueError(f"Asset-only style integrity check failed: {details}")


def _template_target_types(options: TemplateProductBuilderOptions) -> tuple[str, ...]:
    target_types = TEMPLATE_EXEMPLAR_DRIVEN_TARGET_TYPES if options.exemplar_driven else TEMPLATE_TARGET_TYPES
    if not options.only_type:
        return target_types
    requested = str(options.only_type).strip()
    requested_key = requested.casefold().replace("-", "_").replace(" ", "_").replace("/", "_")
    matches = [
        product_key
        for product_key in target_types
        if product_key.casefold() == requested.casefold()
        or TEMPLATE_TYPE_DIRS[product_key].casefold() == requested.casefold()
        or TEMPLATE_TYPE_DIRS[product_key].casefold() == requested_key
    ]
    if not matches:
        raise ValueError(f"Unknown template product type for --only-type: {requested}")
    return (matches[0],)


def _template_type_root(run_root: Path, product_key: str, *, compact: bool = False) -> Path:
    parent = run_root / "products" if compact else run_root
    return parent / TEMPLATE_TYPE_DIRS[product_key]


def _build_pairing_template_candidates(
    pairings: dict[str, TargetPairing],
    target_types: tuple[str, ...],
) -> list[TemplateCandidate]:
    candidates: list[TemplateCandidate] = []
    for product_key in target_types:
        pairing = pairings.get(product_key)
        if pairing is not None and pairing.reference_opju:
            candidates.append(
                TemplateCandidate(
                    product_key=product_key,
                    path=pairing.reference_opju,
                    source="pairing_plan_exemplar",
                    path_score=1400,
                    reason="selected directly from reviewed OPJU/data pairing plan",
                    metadata={"pairing_plan_item": _safe_metadata_payload(pairing.raw)},
                )
            )
        embedded = _embedded_template_candidate(product_key)
        if embedded is not None:
            candidates.append(embedded)
    return candidates


def _embedded_template_candidate(product_key: str) -> TemplateCandidate | None:
    snapshot = embedded_template_snapshot_dict(product_key)
    if not snapshot:
        return None
    return TemplateCandidate(
        product_key=product_key,
        path=embedded_template_path(product_key),
        source="embedded_template_snapshot",
        path_score=1200,
        status="embedded",
        graph_page=str(snapshot.get("graph_page") or ""),
        layer_count=int(snapshot.get("layer_count") or 0),
        plot_count=int(snapshot.get("plot_count") or 0),
        reason="selected from reviewed script-embedded Origin template snapshot; no external OPJU is required for plotting",
        metadata={"snapshot": snapshot, "embedded_template_snapshot": True},
    )


def _repair_exemplar_driven_pairings(
    first_pairings: dict[str, TargetPairing],
    remaining_pairings: dict[str, TargetPairing],
    roots: dict[str, Path],
) -> tuple[dict[str, TargetPairing], dict[str, TargetPairing]]:
    repaired_first = dict(first_pairings)
    epr = repaired_first.get("EPR")
    if epr is not None:
        repaired = _select_preferred_epr_exemplar_pairing(epr, roots)
        if repaired is not None:
            repaired_first["EPR"] = repaired
    repaired_remaining = _repair_mott_pairings(remaining_pairings, roots)
    return repaired_first, repaired_remaining


def _repair_mott_pairings(
    remaining_pairings: dict[str, TargetPairing],
    roots: dict[str, Path],
) -> dict[str, TargetPairing]:
    repaired_remaining = dict(remaining_pairings)
    mott = repaired_remaining.get("Mott-Schottky")
    if mott is not None and _mott_pairing_needs_repair(mott):
        repaired = _select_mott_exemplar_pairing(mott, roots)
        if repaired is not None:
            repaired_remaining["Mott-Schottky"] = repaired
    return repaired_remaining


def _select_preferred_epr_exemplar_pairing(pairing: TargetPairing, roots: dict[str, Path]) -> TargetPairing | None:
    group_root = roots.get("workspace_group_data")
    if group_root is None:
        return None
    template_dir = group_root.joinpath(*PREFERRED_EPR_TEMPLATE_DIR_PARTS)
    if not template_dir.exists():
        return None
    opjus = [path for path in template_dir.iterdir() if path.is_file() and path.suffix.casefold() in {".opju", ".opj"}]
    if not opjus:
        return None
    selected = max(opjus, key=_preferred_epr_exemplar_score)
    if pairing.reference_opju == selected:
        return None
    raw = dict(pairing.raw)
    raw.update(
        {
            "selected_opju_root_label": "workspace_group_data",
            "selected_opju_relative_path": _relative_to_root(group_root, selected),
            "exemplar_driven_repair": "epr_pairing_reference_replaced_with_group_meeting_origin_package",
            "original_selected_opju_relative_path": pairing.raw.get("selected_opju_relative_path", ""),
        }
    )
    return replace(
        pairing,
        opju_root_label="workspace_group_data",
        reference_opju=selected,
        raw=raw,
    )


def _preferred_epr_exemplar_score(path: Path) -> tuple[int, str]:
    text = path.name.casefold()
    score = 0
    if "oh" in text:
        score += 100
    if "light_overlay" in text:
        score += 20
    if "overlay" in text:
        score += 10
    if "20260519" in text:
        score += 5
    return score, path.name


def _mott_pairing_needs_repair(pairing: TargetPairing) -> bool:
    text = str(pairing.reference_opju).replace("\\", "/").casefold()
    if "xrd/" in text or "没有明显峰" in text or "標準" in text or "标准卡片" in text:
        return True
    return "莫特肖特基" not in str(pairing.reference_opju)


def _select_mott_exemplar_pairing(pairing: TargetPairing, roots: dict[str, Path]) -> TargetPairing | None:
    f_root = roots.get("f_drive_detection")
    if f_root is None:
        return None
    mott_root = f_root / "莫特肖特基"
    if not mott_root.exists():
        return None
    opjus = [path for path in mott_root.rglob("*") if path.is_file() and path.suffix.casefold() in {".opju", ".opj"}]
    if not opjus:
        return None
    selected = max(opjus, key=_mott_exemplar_score)
    if _mott_exemplar_score(selected) < 0:
        return None
    data_paths = _mott_adjacent_data_files(selected)
    if not data_paths:
        return None
    raw = dict(pairing.raw)
    raw.update(
        {
            "selected_data_root_label": "f_drive_detection",
            "selected_data_relative_paths": [_relative_to_root(f_root, path) for path in data_paths],
            "selected_opju_root_label": "f_drive_detection",
            "selected_opju_relative_path": _relative_to_root(f_root, selected),
            "exemplar_driven_repair": "mott_pairing_reference_replaced_with_mott_folder_opju",
            "original_selected_opju_relative_path": pairing.raw.get("selected_opju_relative_path", ""),
        }
    )
    return replace(
        pairing,
        data_root_label="f_drive_detection",
        data_paths=data_paths,
        opju_root_label="f_drive_detection",
        reference_opju=selected,
        raw=raw,
    )


def _mott_exemplar_score(path: Path) -> int:
    text = str(path).casefold()
    name = path.name.casefold()
    score = 0
    if "没有明显峰" in text or "xrd" in text:
        score -= 1000
    if "莫特肖特基" not in str(path):
        score -= 200
    if "格式美化" in name:
        score += 120
    if "数据美化" in name:
        score += 90
    if "bobc" in text:
        score += 45
    if "cwo新" in name:
        score += 20
    if "mose2mt" in text or "ms.opju" == name:
        score += 15
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    if size >= 100_000:
        score += 10
    if size < 70_000:
        score -= 30
    if "cwo mt-2 +0.3.opju" == name:
        score -= 80
    return score


def _mott_adjacent_data_files(opju_path: Path) -> list[Path]:
    suffixes = {".csv", ".xlsx", ".xls", ".txt"}
    candidates = [
        path
        for path in sorted(opju_path.parent.glob("*"), key=lambda item: item.name.casefold())
        if path.is_file() and path.suffix.casefold() in suffixes
    ]
    if candidates:
        return candidates[:8]
    return [
        path
        for path in sorted(opju_path.parent.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file() and path.suffix.casefold() in suffixes
    ][:8]


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _skipped_template_types(options: TemplateProductBuilderOptions, roots: dict[str, Path]) -> list[dict[str, object]]:
    skipped = list(SKIPPED_TEMPLATE_TYPES)
    if options.exemplar_driven:
        skipped.extend(_unfinished_or_unpaired_exemplar_report_items(roots))
    return skipped


def _unfinished_or_unpaired_exemplar_report_items(roots: dict[str, Path]) -> list[dict[str, object]]:
    f_root = roots.get("f_drive_detection")
    if f_root is None:
        return []
    known: list[tuple[str, str, str]] = [
        ("BET", "BET/氮气吸附脱附等温曲线/BET -BOBC为负数.opju", "filename says BOBC is negative; do not use as finished exemplar"),
        ("XRD", "XRD/BOBC+MS/251024/20251024 MOSE2的量需要更多更多，没有明显峰，标准卡片没有导入.opju", "filename says no clear peak and standard card not imported"),
        ("XRD", "XRD/MS/BPO+MS.opju", "older MS/BPO exemplar is not the selected current data group"),
        ("Mott-Schottky", "莫特肖特基/CWO/CWO MT-2 +0.3.opju", "small early CWO MT draft; prettier/finished Mott files exist"),
        ("reaction_condition_screening", "光反应的条件筛选/时间反应取样.opju", "no clear paired exported data table"),
        ("reaction_condition_screening", "光反应的条件筛选/溶剂筛选.opju", "no clear paired exported data table"),
        ("reaction_condition_screening", "光反应的条件筛选/自由基捕获.opju", "no clear paired exported data table"),
        ("reaction_condition_screening", "光反应的条件筛选/CL/催化剂筛选.opju", "old CL draft without a reviewed data-table pairing"),
        ("reaction_condition_screening", "光反应的条件筛选/CL/溶剂筛选.opju", "old CL draft without a reviewed data-table pairing"),
        ("reaction_condition_screening", "光反应的条件筛选/CL/循环实验.opju", "old CL draft without a reviewed data-table pairing"),
        ("reaction_condition_screening", "光反应的条件筛选/CL/自由基猝灭.opju", "old CL draft without a reviewed data-table pairing"),
    ]
    items: list[dict[str, object]] = []
    for data_type, relative, reason in known:
        path = f_root / relative
        if not path.exists():
            continue
        items.append(
            {
                "type": data_type,
                "status": "skipped",
                "example": relative,
                "reason": reason,
            }
        )
    return items


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
    compact_output: bool = False,
) -> tuple[ProductContext, dict[str, object]]:
    product_key = pairing.product_key
    type_root = _template_type_root(run_root, product_key, compact=compact_output)
    _ensure_template_type_dirs(type_root, compact=compact_output)
    slug = _versioned_template_slug(product_key, slug_version)
    input_copies = [] if (compact_output or product_key == "EPR") else _copy_inputs(pairing.data_paths, type_root / "input_copies")
    if template.source == "embedded_template_snapshot":
        reference_copy = template.path
    elif compact_output:
        reference_copy = template.path
    else:
        reference_dir = "reference_opju" if template.path.suffix.casefold() in {".opju", ".opj"} else "format_assets"
        reference_copy = _copy_reference(template.path, type_root / reference_dir)
    extra: dict[str, object] = {"template": _candidate_to_dict(template)}
    product_pairing = pairing
    if product_key == "EIS":
        headers, rows, labels, eis_extra = _build_template_eis_table(
            pairing,
            type_root,
            template,
            strict_semicircle_branch=eis_strict_semicircle_branch,
            compact_output=compact_output,
        )
        extra.update(eis_extra)
        eis_overlay = eis_extra.get("eis_overlay") if isinstance(eis_extra.get("eis_overlay"), dict) else {}
        eis_input_files = [Path(value) for value in eis_overlay.get("source_files", []) if str(value).strip()]
        if eis_input_files:
            input_copies = [] if compact_output else _copy_inputs(eis_input_files, type_root / "input_copies")
            product_pairing = replace(pairing, data_paths=eis_input_files)
    elif product_key == "EPR":
        headers, rows, labels, epr_extra = _build_template_epr_table(
            pairing,
            type_root,
            template,
            slug,
            compact_output=compact_output,
        )
        extra.update(epr_extra)
        epr_overlay = epr_extra.get("epr_overlay") if isinstance(epr_extra.get("epr_overlay"), dict) else {}
        epr_input_files = [Path(value) for value in epr_overlay.get("input_files", []) if str(value).strip()]
        if epr_input_files:
            input_copies = [] if compact_output else _copy_inputs(epr_input_files, type_root / "input_copies")
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
            compact_output=compact_output,
        )
    processed_data = type_root / f"{slug}.csv" if compact_output else type_root / "processed_data" / f"{slug}.csv"
    _write_csv(processed_data, headers, rows)
    product = ProductContext(
        product_key=product_key,
        slug=slug,
        pairing=product_pairing,
        type_root=type_root,
        processed_data=processed_data,
        input_copies=input_copies,
        reference_opju_copy=reference_copy,
        reference_preview_png=type_root / f"{slug}_reference.png" if compact_output else type_root / "reference_exports" / f"{slug}_reference_preview.png",
        origin_file=type_root / f"{slug}.opju" if compact_output else type_root / "origin_files" / f"{slug}.opju",
        figure_tif=type_root / f"{slug}.tif" if compact_output else type_root / "figures_tif" / f"{slug}.tif",
        preview_png=type_root / f"{slug}.png" if compact_output else type_root / "figures_preview" / f"{slug}_preview.png",
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
    if pairing.product_key in {"Raman", "UV-vis DRS / Tauc", "PL", "photocurrent", "FTIR", "Mott-Schottky"}:
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
        limit=max(target_files * 8, 32),
    )
    candidates, cohort = _select_template_bet_candidate_cohort(candidates, target_files)
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
    selected_series = series[:target_series]
    headers, rows = _template_independent_xy_table(
        "relative_pressure_p_p0",
        "quantity_adsorbed_cm3_g_stp",
        selected_series,
    )
    labels = {
        "x_label": "Relative Pressure (P/P_0)",
        "y_label": "Quantity Adsorbed (cm3/g STP)",
        "title": "BET isotherm exemplar",
        "plot_type": "line+symbol",
        "legend_entries": [label.replace("_", " ") for label, _values in selected_series],
        "notes": "Multiple real BET source exports were used to match the OPJU exemplar curve structure; no BET model conclusion is generated.",
    }
    alignment = _template_alignment_payload(
        pairing,
        template,
        used_files,
        len(selected_series),
        "template_aligned_bet_independent_xy_coherent_material_cohort",
    )
    alignment["selected_materials"] = [_template_bet_series_label_from_path(path) for path in used_files]
    alignment["cohort_directory"] = str(cohort) if cohort is not None else ""
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": alignment,
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


def _select_template_bet_candidate_cohort(
    candidates: list[Path],
    target_files: int,
) -> tuple[list[Path], Path | None]:
    if target_files <= 0 or not candidates:
        return [], None
    unique = _template_unique_paths(candidates)
    groups: dict[Path, list[Path]] = {}
    for path in unique:
        for parent in path.parents:
            groups.setdefault(parent, []).append(path)

    eligible: list[tuple[tuple[int, int, int, int], Path, list[Path]]] = []
    for parent, paths in groups.items():
        material_count = len({_template_bet_series_label_from_path(path).casefold() for path in paths})
        if material_count < target_files:
            continue
        score = (
            min(material_count, target_files),
            -abs(len(paths) - target_files),
            len(parent.parts),
            -len(str(parent)),
        )
        eligible.append((score, parent, paths))
    if eligible:
        _score, cohort, pool = max(eligible, key=lambda item: item[0])
    else:
        cohort, pool = None, unique

    selected: list[Path] = []
    seen_materials: set[str] = set()
    for path in sorted(pool, key=lambda item: str(item).casefold()):
        material = _template_bet_series_label_from_path(path).casefold()
        if material in seen_materials:
            continue
        seen_materials.add(material)
        selected.append(path)
        if len(selected) >= target_files:
            return selected, cohort
    for path in unique:
        if path not in selected:
            selected.append(path)
        if len(selected) >= target_files:
            break
    return selected, cohort


def _build_template_xrd_multisource_table(pairing: TargetPairing, template: TemplateCandidate) -> dict[str, object] | None:
    target_series = _template_xrd_target_sample_series_count(pairing, template)
    candidates = _template_candidate_files(
        pairing,
        template,
        suffixes=(".txt", ".dql"),
        exclude_name_tokens=("pdf#", "jcpds", "card", "鏍囧崱"),
        prefer_template_parent=False,
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
        series.append((_template_xy_series_label(pairing.product_key, path), rows))
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
    rows = _template_xrd_normalized_offset_rows(headers, rows)
    legend_entries = [
        _xrd_legend_label(label)
        for label, _values in series
        if not is_template_xrd_reference_stick_header(label)
    ]
    visual_plot_count = len(series)
    labels = {
        "x_label": XRD_X_AXIS_TITLE,
        "y_label": XRD_Y_AXIS_TITLE,
        "title": "XRD exemplar",
        "plot_type": "line",
        "y_tick_values": "false",
        "legend_entries": legend_entries,
        "notes": "Multiple real XRD source exports were used where available; PDF/JCPDS reference sticks are plotted for manual review without phase assignment.",
    }
    alignment = _template_alignment_payload(pairing, template, used_files, len(headers) - 1, "template_aligned_xrd_stacked_patterns_with_reference_sticks")
    alignment["visual_template_plot_count"] = max(visual_plot_count, int(template.plot_count or 0))
    alignment["reference_stick_included"] = reference_card is not None
    alignment["normalization"] = "XRD sample traces are min-max normalized and vertically offset using the reviewed no-card overlay spacing."
    alignment["offset_step"] = 1.15
    return {
        "headers": headers,
        "rows": rows,
        "labels": labels,
        "alignment": alignment,
    }


def _template_xrd_target_sample_series_count(pairing: TargetPairing, template: TemplateCandidate) -> int:
    target = max(int(template.plot_count or 0), 1)
    if pairing.product_key == "XRD" and _template_xrd_reference_card_files(pairing, template):
        # The reviewed standard-card XRD template has extra plot/layer entries for
        # the card, so page plot_count is not the sample count.
        target = 4
    return target


def _template_xrd_normalized_offset_rows(
    headers: list[str],
    rows: list[list[float | str | None]],
) -> list[list[float | str | None]]:
    if len(headers) < 2 or not rows:
        return rows
    y_headers = headers[1:]
    reference_flags = [is_template_xrd_reference_stick_header(header) for header in y_headers]
    sample_count = sum(1 for is_reference in reference_flags if not is_reference)
    if sample_count <= 0:
        return rows
    offset_count = sample_count + (1 if any(reference_flags) else 0)
    bounds: dict[int, tuple[float, float]] = {}
    sample_index = 0
    offsets: dict[int, float] = {}
    for column_offset, is_reference in enumerate(reference_flags, start=1):
        if is_reference:
            continue
        values: list[float] = []
        for row in rows:
            if column_offset >= len(row):
                continue
            value = _to_float(row[column_offset])
            if value is not None and math.isfinite(value):
                values.append(value)
        if values:
            bounds[column_offset] = (min(values), max(values))
            offsets[column_offset] = xrd_no_card_offset_for_index(sample_index, offset_count)
        sample_index += 1
    normalized: list[list[float | str | None]] = []
    for row in rows:
        output = list(row)
        for column_offset, (min_value, max_value) in bounds.items():
            if column_offset >= len(output):
                continue
            value = _to_float(output[column_offset])
            if value is None or not math.isfinite(value):
                output[column_offset] = None
                continue
            span = max_value - min_value
            if span <= 0:
                span = 1.0
            output[column_offset] = (value - min_value) / span + offsets[column_offset]
        normalized.append(output)
    return normalized


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
    roots = [pairing.reference_opju.parent, template.path.parent, *[path.parent for path in pairing.data_paths]]
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
    prefer_template_parent = pairing.product_key in {"FTIR", "Mott-Schottky"} or bool(pairing.raw.get("exemplar_driven_repair"))
    candidates = _template_candidate_files(
        pairing,
        template,
        suffixes=suffixes,
        prefer_template_parent=prefer_template_parent,
        limit=max(target_series * 4, 12),
    )
    if pairing.product_key == "photocurrent":
        candidates = _template_photocurrent_candidate_files(pairing, template, target_series)
    if pairing.product_key == "PL":
        candidates = _template_pl_candidate_files(pairing, template, target_series)
    if pairing.product_key == "Mott-Schottky":
        candidates = _template_mott_candidate_files(pairing, candidates, target_series)
    series: list[tuple[str, list[list[float | str | None]]]] = []
    used_files: list[Path] = []
    for path in candidates:
        try:
            if pairing.product_key == "UV-vis DRS / Tauc":
                rows = _data_points_rows(path)
            elif pairing.product_key == "Mott-Schottky":
                rows = _template_mott_schottky_rows(path)
            else:
                rows = _coerced_xy_rows(path)
        except Exception:
            continue
        if len(rows) < 2:
            continue
        series.append((_template_xy_series_label(pairing.product_key, path), rows))
        used_files.append(path)
        if len(series) >= target_series:
            break
    if not series:
        return None
    x_header, y_suffix, labels = _template_xy_labels(pairing.product_key)
    labels = dict(labels)
    if pairing.product_key == "Mott-Schottky":
        labels["legend_entries"] = [
            f"{label}Hz BiOBr0.5Cl0.5"
            for label, _values in series[:3]
        ]
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


def _template_independent_xy_table(
    x_suffix: str,
    y_suffix: str,
    series: list[tuple[str, list[list[float | str | None]]]],
) -> tuple[list[str], list[list[float | str | None]]]:
    """Preserve every source series as its own adjacent X/Y column pair.

    This table intentionally performs no sorting, de-duplication, interpolation,
    or shared-grid projection.  Shorter series are padded only after their last
    supplied pair so strict Origin row-range binding can reject any nonmissing
    value that would otherwise be dropped.
    """

    headers: list[str] = []
    normalized: list[list[list[float | str | None]]] = []
    for label, source_rows in series:
        identity = safe_name(label)
        headers.extend((f"{identity}_{x_suffix}", f"{identity}_{y_suffix}"))
        normalized.append(
            [
                [row[0], row[1]]
                for row in source_rows
                if len(row) >= 2
            ]
        )
    row_count = max((len(source_rows) for source_rows in normalized), default=0)
    output: list[list[float | str | None]] = []
    for row_index in range(row_count):
        output_row: list[float | str | None] = []
        for source_rows in normalized:
            if row_index < len(source_rows):
                output_row.extend(source_rows[row_index])
            else:
                output_row.extend((None, None))
        output.append(output_row)
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
    candidates: list[Path] = _template_data_hint_paths(template, suffixes=suffixes)
    seen_candidates = {str(path.resolve()) for path in candidates if path.exists()}
    if prefer_template_parent:
        roots.append(template.path.parent)
    roots.extend(path.parent for path in pairing.data_paths)
    if len(pairing.data_paths) == 1:
        roots.append(pairing.data_paths[0].parent.parent)
    roots.append(template.path.parent)
    seen_roots: set[str] = set()
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
            candidate_key = str(path.resolve())
            if candidate_key in seen_candidates:
                continue
            seen_candidates.add(candidate_key)
            candidates.append(path)
            if len(candidates) >= limit:
                return _template_ordered_candidate_paths(pairing, candidates, prefer_template_parent=prefer_template_parent)
    return _template_ordered_candidate_paths(pairing, candidates, prefer_template_parent=prefer_template_parent)


def _template_ordered_candidate_paths(pairing: TargetPairing, candidates: list[Path], *, prefer_template_parent: bool) -> list[Path]:
    if prefer_template_parent:
        return _template_unique_paths([*candidates, *pairing.data_paths])
    return _template_unique_paths([*pairing.data_paths, *candidates])


def _template_data_hint_paths(template: TemplateCandidate, *, suffixes: tuple[str, ...]) -> list[Path]:
    manifest_entry = template.metadata.get("manifest_entry") if isinstance(template.metadata.get("manifest_entry"), dict) else {}
    raw_paths = manifest_entry.get("data_hint_paths") if isinstance(manifest_entry.get("data_hint_paths"), list) else []
    paths: list[Path] = []
    seen: set[str] = set()
    for raw in raw_paths:
        path = Path(str(raw))
        if not path.is_file() or path.suffix.casefold() not in suffixes:
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


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
    if product_key == "Mott-Schottky":
        return (".csv", ".xlsx", ".xls", ".txt")
    return (".txt", ".csv")


def _template_pl_candidate_files(pairing: TargetPairing, template: TemplateCandidate, target_series: int) -> list[Path]:
    graph = str(template.graph_page or "").casefold()
    preferred = "EX" if graph.startswith("ex") else "EM"
    parent = pairing.data_paths[0].parent if pairing.data_paths else template.path.parent
    scan_pattern = re.compile(rf"^\s*\d+\s*-\s*{preferred}\s*-", re.IGNORECASE)
    files = sorted(
        (path for path in parent.glob("*.txt") if scan_pattern.search(path.stem)),
        key=_template_numbered_series_sort_key,
    )
    if files:
        return files[:target_series]
    candidates = _template_candidate_files(pairing, template, suffixes=(".txt",), limit=max(target_series * 3, 9))
    return [path for path in candidates if scan_pattern.search(path.stem)][:target_series]


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
    candidates = _template_unique_paths([*pairing.data_paths, *candidates])
    candidates.sort(key=lambda path: _template_photocurrent_series_sort_key(path))
    return candidates[:target_series]


def _template_numbered_series_sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"^\s*(\d+)", path.stem)
    return (int(match.group(1)) if match else 10_000, path.name.casefold())


def _template_xy_series_label(product_key: str, path: Path) -> str:
    if product_key == "PL":
        match = re.match(r"^\s*(\d+)", path.stem)
        cohort = [part.strip() for part in path.parent.name.split("+") if part.strip()]
        if match and len(cohort) >= int(match.group(1)):
            return _canonical_material_label(cohort[int(match.group(1)) - 1])
    if product_key == "photocurrent":
        return _template_photocurrent_series_label(path)
    return _template_series_label_from_path(path)


def _template_photocurrent_series_sort_key(path: Path) -> tuple[int, str]:
    label = _template_photocurrent_series_label(path).casefold()
    rank = {"bobc": 0, "cwo": 1, "bicu-10": 2, "bicu": 2}.get(label, 100)
    return (rank, str(path).casefold())


def _template_photocurrent_series_label(path: Path) -> str:
    parent_label = _canonical_material_label(path.parent.name)
    if parent_label.casefold() == "bicu":
        for parent in path.parents:
            match = re.search(r"bicu\s*[-_]?\s*(\d+(?:\.\d+)?)", parent.name, re.IGNORECASE)
            if match:
                return f"BiCu-{match.group(1)}"
    return parent_label or _template_series_label_from_path(path)


def _canonical_material_label(value: str) -> str:
    text = str(value).strip().replace("_", "-")
    compact = re.sub(r"\s+", "", text).casefold()
    if compact == "bobc":
        return "BOBC"
    if compact == "cwo":
        return "CWO"
    if compact == "bc":
        return "BC"
    if compact == "bicu":
        return "BiCu"
    match = re.fullmatch(r"bicu-?(\d+(?:\.\d+)?)", compact)
    if match:
        return f"BiCu-{match.group(1)}"
    return text


def _template_mott_candidate_files(
    pairing: TargetPairing,
    candidates: list[Path],
    target_series: int,
) -> list[Path]:
    preferred = [path for path in pairing.data_paths if path.is_file()]
    pool = preferred if len(preferred) >= target_series else _template_unique_paths([*preferred, *candidates])

    def frequency_key(path: Path) -> tuple[int, float, str]:
        values = re.findall(r"\d+(?:\.\d+)?", path.stem)
        if not values:
            return (1, 0.0, path.name.casefold())
        return (0, float(values[-1]), path.name.casefold())

    ordered = sorted(pool, key=frequency_key)
    if len(ordered) <= target_series:
        return ordered
    start = max(0, (len(ordered) - target_series) // 2)
    return ordered[start : start + target_series]


def _template_mott_schottky_rows(path: Path) -> list[list[float | str | None]]:
    numeric = mott_schottky_numeric(read_table(path), [])
    if len(numeric) < 2:
        raise ValueError(f"Mott-Schottky source does not contain a validated potential/1-C-squared pair: {path}")
    return [[potential, one_over_c2] for potential, one_over_c2 in numeric]


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
    if product_key == "Mott-Schottky":
        return "potential_v", "one_over_c_squared", {
            "x_label": "Potential (V vs Ag/AgCl)",
            "y_label": "C^-2 (10^8 cm^4 F^-2)",
            "title": "Mott-Schottky draft",
            "plot_type": "line+symbol",
            "notes": "Potential/capacitance-derived columns require manual confirmation; no carrier type, carrier density, or band position is inferred.",
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
    compact_output: bool = False,
) -> dict[str, object]:
    if pairing.product_key.startswith("XPS"):
        return _write_template_xps_origin_processing_plan(pairing, type_root, slug, xps_component_fill_mode=xps_component_fill_mode, compact_output=compact_output)
    if pairing.product_key == "XRD":
        return _write_template_xrd_origin_processing_plan(type_root, slug, headers, rows, compact_output=compact_output)
    return _write_template_identity_origin_processing_plan(pairing.product_key, type_root, slug, headers, rows, compact_output=compact_output)


def _write_template_identity_origin_processing_plan(
    product_key: str,
    type_root: Path,
    slug: str,
    headers: list[str],
    rows: list[list[float | str | None]],
    *,
    compact_output: bool = False,
) -> dict[str, object]:
    raw_headers = [headers[0], *[f"{header}_raw" for header in headers[1:]]]
    raw_csv = type_root / "processed_data" / f"{slug}_origin_raw_input.csv"
    plan_path = type_root / "metadata" / "origin_processing_plan.json"
    final_csv = type_root / f"{slug}.csv" if compact_output else type_root / "processed_data" / f"{slug}.csv"
    if not compact_output:
        _write_csv(raw_csv, raw_headers, rows)
    transforms = [
        {"header": header, "kind": "copy", "source_col": index}
        for index, header in enumerate(headers, start=1)
    ]
    plan = {
        "product_key": product_key,
        "processing_location": "Origin workbook LabTalk after raw data import",
        "processing_kind": "origin_identity_copy",
        "raw_origin_input_csv": "" if compact_output else _template_plan_relative_path(plan_path, raw_csv),
        "final_product_processed_csv": _template_plan_relative_path(plan_path, final_csv),
        "final_headers": headers,
        "raw_headers": raw_headers,
        "raw_column_count": len(raw_headers),
        "transforms": transforms,
        "review_policy": "Origin copies imported raw plotting columns to final graph columns; no additional scientific analysis is claimed.",
    }
    if not compact_output:
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def _write_template_xrd_origin_processing_plan(
    type_root: Path,
    slug: str,
    headers: list[str],
    rows: list[list[float | str | None]],
    *,
    compact_output: bool = False,
) -> dict[str, object]:
    raw_headers = [headers[0], *[f"{header}_raw" for header in headers[1:]]]
    raw_csv = type_root / "processed_data" / f"{slug}_origin_raw_input.csv"
    plan_path = type_root / "metadata" / "origin_processing_plan.json"
    final_csv = type_root / f"{slug}.csv" if compact_output else type_root / "processed_data" / f"{slug}.csv"
    if not compact_output:
        _write_csv(raw_csv, raw_headers, rows)
    transforms: list[dict[str, object]] = [{"header": headers[0], "kind": "copy", "source_col": 1}]
    reference_count = sum(1 for header in headers[1:] if is_template_xrd_reference_stick_header(header))
    sample_count = max(0, len(headers) - 1 - reference_count)
    offset_count = sample_count + (1 if reference_count else 0)
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
                "offset": xrd_no_card_offset_for_index(sample_index, offset_count),
            }
        )
        sample_index += 1
    plan = {
        "product_key": "XRD",
        "processing_location": "Origin workbook LabTalk after raw XRD pattern and reference-card import",
        "processing_kind": "origin_xrd_normalize_stack_with_reference_sticks",
        "raw_origin_input_csv": "" if compact_output else _template_plan_relative_path(plan_path, raw_csv),
        "final_product_processed_csv": _template_plan_relative_path(plan_path, final_csv),
        "final_headers": headers,
        "raw_headers": raw_headers,
        "raw_column_count": len(raw_headers),
        "transforms": transforms,
        "review_policy": (
            "Origin normalizes and vertically offsets XRD sample traces for visual comparison. "
            "Offsets follow the reviewed xrd-no-card-overlay spacing rule. "
            "Reference-card sticks are plotted from real PDF/JCPDS text data for manual review only; no phase conclusion is emitted."
        ),
    }
    if not compact_output:
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def _write_template_xps_origin_processing_plan(
    pairing: TargetPairing,
    type_root: Path,
    slug: str,
    *,
    xps_component_fill_mode: str,
    compact_output: bool = False,
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
        measured_transform = {
            "header": f"{sample}_measured",
            "kind": "normalize_with_offset",
            "source_col": measured_col,
            "scale_col": measured_col,
            "offset": offset,
        }
        envelope_values = _xps_raw_series(record, "envelope", point_count)
        envelope_transform: dict[str, object] | None = None
        if any(value is not None for value in envelope_values):
            envelope_col = add_raw_column(f"{sample}_envelope_raw", envelope_values)
            envelope_transform = {
                "header": f"{sample}_envelope",
                "kind": "normalize_with_offset",
                "source_col": envelope_col,
                "scale_col": measured_col,
                "offset": offset,
            }
        background_values = _xps_raw_series_any(
            record,
            tuple(key for key in ("background", record.background_label, "Backgnd.", "Background") if key),
            point_count,
        )
        background_col = add_raw_column(f"{sample}_background_raw", background_values)
        background_transform: dict[str, object] | None = None
        if any(value is not None for value in background_values):
            background_transform = {
                "header": f"{sample}_background",
                "kind": "normalize_with_offset",
                "source_col": background_col,
                "scale_col": measured_col,
                "offset": offset,
            }
        component_transforms: list[tuple[dict[str, object], dict[str, object]]] = []
        for component_index, label in enumerate(record.component_labels, start=1):
            component_values = _xps_raw_series_any(record, (_component_key(label), label), point_count)
            if not any(value is not None for value in component_values):
                continue
            component_col = add_raw_column(f"{sample}_component_{component_index}_raw", component_values)
            component_transform = {
                "header": f"{sample}_component_{component_index}",
                "kind": "normalize_with_offset",
                "source_col": component_col,
                "scale_col": measured_col,
                "offset": offset,
            }
            baseline_transform = {
                "header": f"{sample}_component_{component_index}_fill_baseline",
                "kind": "normalize_with_offset",
                "source_col": background_col,
                "scale_col": measured_col,
                "offset": offset,
                "baseline_for_component_col": component_col,
            }
            component_transforms.append((component_transform, baseline_transform))

        if xps_component_fill_mode != "template_line_fill":
            transforms.append(measured_transform)
            if envelope_transform is not None:
                transforms.append(envelope_transform)
            if background_transform is not None:
                transforms.append(background_transform)
            transforms.extend(component for component, _baseline in component_transforms)
            continue

        if len(component_transforms) != 2:
            raise ValueError(
                f"XPS template Origin processing requires exactly two fitted components for {record.sample}; found {len(component_transforms)}"
            )
        if background_transform is None:
            raise ValueError(f"XPS template Origin processing requires a real background curve for {record.sample}")
        if envelope_transform is None:
            raise ValueError(f"XPS template Origin processing requires a real envelope curve for {record.sample}")
        if pairing.product_key == "XPS_in_situ":
            transforms.append(measured_transform)
            for component_transform, baseline_transform in component_transforms:
                transforms.extend((component_transform, baseline_transform))
            transforms.extend((background_transform, envelope_transform))
        else:
            for component_transform, baseline_transform in component_transforms:
                component_header = str(component_transform["header"])
                transforms.extend(
                    (
                        {**component_transform, "header": f"{component_header}_fill_upper"},
                        baseline_transform,
                        {**component_transform, "header": f"{component_header}_line"},
                    )
                )
            transforms.extend((measured_transform, background_transform, envelope_transform))
    raw_rows = [
        [column[row_index] for column in raw_columns]
        for row_index in range(point_count)
    ]
    raw_csv = type_root / "processed_data" / f"{slug}_origin_raw_input.csv"
    plan_path = type_root / "metadata" / "origin_processing_plan.json"
    final_csv = type_root / f"{slug}.csv" if compact_output else type_root / "processed_data" / f"{slug}.csv"
    if not compact_output:
        _write_csv(raw_csv, raw_headers, raw_rows)
    plan = {
        "product_key": pairing.product_key,
        "processing_location": "Origin workbook LabTalk after fitted XPS source data import",
        "processing_kind": "origin_xps_normalize_offset_fill",
        "raw_origin_input_csv": "" if compact_output else _template_plan_relative_path(plan_path, raw_csv),
        "final_product_processed_csv": _template_plan_relative_path(plan_path, final_csv),
        "raw_headers": raw_headers,
        "final_headers": [str(item["header"]) for item in transforms],
        "raw_column_count": len(raw_headers),
        "transforms": transforms,
        "xps_component_fill_mode": xps_component_fill_mode,
        "source_files": [str(record.source_file) for record in records],
        "sheets": [record.sheet_name for record in records],
        "review_policy": "Origin computes XPS normalization, vertical offsets, and component fill helper columns from imported fitted-source curves.",
    }
    if not compact_output:
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
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


def _export_native_tif_with_physical_validation(
    operations: object,
    graph_name: str,
    target: Path,
    *,
    dpi: int,
) -> dict[str, object]:
    activated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if not getattr(activated, "ok", False):
        return {"ok": False, "message": f"Could not activate reopened graph {graph_name!r} before TIFF export."}
    dimensions: dict[str, float] = {}
    for name in ("page.width", "page.height"):
        result = operations.get_labtalk_variable(name)
        if not getattr(result, "ok", False):
            return {"ok": False, "message": f"Could not read {name} from reopened graph {graph_name!r}."}
        try:
            value = float(getattr(result, "payload", {}).get("value"))
        except (TypeError, ValueError, OverflowError):
            return {"ok": False, "message": f"Reopened graph returned an invalid {name} value."}
        if not math.isfinite(value) or value <= 0:
            return {"ok": False, "message": f"Reopened graph returned a non-positive {name} value."}
        dimensions[name] = value
    expected_width, _expected_height = expected_raster_pixels(
        dimensions["page.width"],
        dimensions["page.height"],
        dpi=dpi,
    )
    reset_identity = getattr(operations, "reset_project_identity_for_export", None)
    if not callable(reset_identity):
        return {
            "ok": False,
            "message": "Origin project identity reset is unavailable before native TIFF export.",
        }
    try:
        identity = reset_identity()
    except Exception:
        return {
            "ok": False,
            "message": "Origin project identity reset failed before native TIFF export.",
        }
    if not getattr(identity, "ok", False):
        return {
            "ok": False,
            "message": "Origin project identity verification failed before native TIFF export.",
        }
    reactivated = operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
    if not getattr(reactivated, "ok", False):
        return {
            "ok": False,
            "message": f"Could not reactivate reopened graph {graph_name!r} after project identity reset.",
        }
    exported = operations.export_graph(
        graph_name,
        target,
        "tif",
        dpi=dpi,
        pixel_width=expected_width,
    )
    if not getattr(exported, "ok", False):
        return {
            "ok": False,
            "message": getattr(exported, "message", "Origin native TIFF export failed"),
        }
    try:
        evidence = validate_tif_physical_resolution(
            target,
            page_width_origin_units=dimensions["page.width"],
            page_height_origin_units=dimensions["page.height"],
            dpi=dpi,
        ).as_dict()
    except Exception as exc:
        return {
            "ok": False,
            "message": scrub_output_text(str(exc)),
        }
    evidence["path"] = target.name
    return {
        "ok": True,
        "message": "Origin native TIFF export passed physical-resolution validation.",
        "evidence": evidence,
    }


class _OriginLifecycleFinalizationError(RuntimeError):
    """Raised when an isolated Origin session cannot be confirmed closed."""


def export_template_product_with_origin(
    product: ProductContext,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
    try:
        return _export_template_product_with_origin_connected(product, style)
    except _OriginLifecycleFinalizationError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "failure_stage": "origin_close",
        }


def _export_template_product_with_origin_connected(
    product: ProductContext,
    style: ResolvedPlotStyle,
) -> dict[str, object]:
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
            for column_index in range(3, len(headers) + 1):
                header = headers[column_index - 1] if column_index - 1 < len(headers) else ""
                plot_type = template_plot_type_for_header(product.product_key, header, product.plot_type)
                added = operations.add_plot_to_graph(graph_name, book_name, "Sheet1", 1, column_index, plot_type=plot_type)
                if not getattr(added, "ok", False):
                    return {
                        "ok": False,
                        "message": getattr(added, "message", f"Origin plot add failed for column {column_index}"),
                        "exemplar_style": exemplar_style,
                    }
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
            x_tick_label_size=style.x_tick_label_font_size,
            y_tick_label_size=style.y_tick_label_font_size,
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
        tif = _export_native_tif_with_physical_validation(
            operations,
            reopened_graph,
            product.figure_tif,
            dpi=style.export_dpi,
        )
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
        if not png.ok or not bool(tif.get("ok")):
            return {
                "ok": False,
                "message": f"{png.message}; {tif.get('message', '')}",
                "exemplar_style": exemplar_style,
                "product_style": product_snapshot.to_dict(),
                "conformance": conformance.to_dict(),
            }
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
            "tif_resolution_evidence": tif.get("evidence", {}),
            "line_width_policy_pt": style.line_width_pt,
            "axis_title_bold_policy": style.font_bold,
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        try:
            close_result = operations.close()
        except Exception as exc:
            raise _OriginLifecycleFinalizationError(
                "Origin lifecycle close failed after template product export: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if not getattr(close_result, "ok", False):
            raise _OriginLifecycleFinalizationError(
                str(
                    getattr(
                    close_result,
                    "message",
                    "Origin lifecycle close did not confirm success after template product export.",
                    )
                )
            )


def _create_template_origin_processed_graph(operations: object, product: ProductContext) -> dict[str, object]:
    plan_path = product.type_root / "metadata" / "origin_processing_plan.json"
    if not plan_path.is_file():
        return {"ok": False, "message": f"Origin processing plan not found: {plan_path}"}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_csv = _resolve_template_plan_path(plan_path, plan.get("raw_origin_input_csv"))
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
    plan_path = _template_epr_origin_processing_plan_path(product)
    if not plan_path.is_file():
        return {"ok": False, "message": f"EPR Origin processing plan not found: {plan_path}"}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_csv = _resolve_template_plan_path(plan_path, plan.get("raw_origin_input_csv"))
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
    detail_csv = _resolve_template_plan_path(plan_path, plan.get("origin_detail_csv")) if plan.get("origin_detail_csv") else (product.type_root / "processed_data" / "epr_origin_detail.csv")
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


def _template_epr_origin_processing_plan_path(product: ProductContext) -> Path:
    candidates = [
        product.type_root / "metadata" / "epr_origin_processing_plan.json",
        product.type_root / "debug" / "epr_origin_processing_plan.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _template_plan_relative_path(plan_path: Path, target: Path) -> str:
    try:
        return os.path.relpath(target, start=plan_path.parent).replace("\\", "/")
    except ValueError:
        return str(target)


def _resolve_template_plan_path(plan_path: Path, value: object) -> Path:
    text = str(value or "").strip()
    if not text:
        return Path("")
    path = Path(text)
    if path.is_absolute():
        return path
    return (plan_path.parent / path).resolve()


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
    if product.reference_opju_copy.suffix.casefold() not in {".opju", ".opj"}:
        return OpjuStyleSnapshot(
            product.reference_opju_copy.name,
            "format_theme_source",
            warnings=["Saved format theme asset is not loaded as an OPJU exemplar."],
        )
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
    template: TemplateCandidate | None = None,
    *,
    strict_semicircle_branch: bool = False,
    compact_output: bool = False,
) -> tuple[list[str], list[list[float | None]], dict[str, str], dict[str, object]]:
    expected_plot_count = int(template.plot_count or 0) if template is not None else 0
    if expected_plot_count > 2:
        return _build_template_eis_overlay_table(
            pairing,
            type_root,
            expected_plot_count=expected_plot_count,
            strict_semicircle_branch_requested=strict_semicircle_branch,
            compact_output=compact_output,
        )
    cleaning = clean_eis_file(pairing.data_paths[0])
    measured_points = list(cleaning.raw_points)
    if len(measured_points) < 2:
        raise ValueError("EIS template product requires at least two measured Nyquist points")
    plot_scale = 0.001
    plot_headers = ["measured_z_real_kohm", "measured_minus_z_imag_kohm"]
    plot_labels = {
        "x_label": "Z' (kOhm)",
        "y_label": "-Z'' (kOhm)",
        "title": "EIS measured data",
        "plot_type": "line+symbol",
        "notes": (
            "Formal template product retains every parsed measured Nyquist point. "
            "Equivalent-circuit fitting, semicircle-branch selection, and automatic point exclusion are not run."
        ),
    }
    eis_metadata = {
        "mode": "formal_measured_points_only",
        "cleaning": {
            **cleaning.to_metadata(),
            "used_for_formal_plot": False,
            "purpose": "parse diagnostics only",
        },
        "fit": {
            "status": "not_run",
            "reason": "Formal template-format-products requires an explicit diagnostic opt-in before equivalent-circuit fitting.",
        },
        "full_fit": {},
        "raw_data": "",
        "cleaned_data": "",
        "ignored_points": "",
        "fit_curve": "",
        "fit_parameters": "",
        "ignored_points_report": "",
        "full_fit_curve_debug": "",
        "strict_semicircle_branch": False,
        "strict_semicircle_branch_requested": bool(strict_semicircle_branch),
        "raw_point_count": len(measured_points),
        "plotted_point_count": len(measured_points),
        "main_plot_curve_policy": "Retain all parsed measured sweep points in source order; do not select a branch or generate a fit curve.",
        "equivalent_circuit_policy": "No automatic equivalent-circuit fit or mechanistic interpretation is generated.",
    }
    return (
        plot_headers,
        [
            [point.z_real_ohm * plot_scale, point.minus_z_imag_ohm * plot_scale]
            for point in measured_points
        ],
        plot_labels,
        {"eis_cleaning": eis_metadata},
    )


def _build_template_eis_overlay_table(
    pairing: TargetPairing,
    type_root: Path,
    *,
    expected_plot_count: int,
    strict_semicircle_branch_requested: bool,
    compact_output: bool,
) -> tuple[list[str], list[list[float | None]], dict[str, str], dict[str, object]]:
    source_files = _discover_template_eis_overlay_sources(pairing, expected_plot_count)
    cleanings = [(path, clean_eis_file(path)) for path in source_files]
    if any(len(cleaning.raw_points) < 2 for _path, cleaning in cleanings):
        raise ValueError("EIS template overlay contains a source with fewer than two measured points")

    headers: list[str] = []
    columns: list[list[float | None]] = []
    legend_entries: list[str] = []
    scale = 0.001
    for path, cleaning in cleanings:
        label = _template_series_label_from_path(path)
        headers.extend((f"{label}_z_real_kohm", f"{label}_minus_z_imag_kohm"))
        columns.extend(
            (
                [point.z_real_ohm * scale for point in cleaning.raw_points],
                [point.minus_z_imag_ohm * scale for point in cleaning.raw_points],
            )
        )
        legend_entries.append(label.replace("_", " "))
    row_count = max((len(column) for column in columns), default=0)
    rows = [
        [column[row_index] if row_index < len(column) else None for column in columns]
        for row_index in range(row_count)
    ]

    sidecar_root = type_root / "debug" if compact_output else type_root / "processed_data"
    metadata_root = type_root / "debug" if compact_output else type_root / "metadata"
    report_root = type_root / "debug" if compact_output else type_root / "reports"
    raw_path = sidecar_root / "raw_eis_data.csv"
    cleaned_path = sidecar_root / "cleaned_eis_data.csv"
    ignored_path = sidecar_root / "ignored_eis_points.csv"
    metadata_path = metadata_root / "eis_cleaning_and_fit_metadata.json"
    fit_parameters_path = metadata_root / "eis_fit_parameters.json"
    ignored_report_path = report_root / "ignored_points_report.md"
    _write_csv(raw_path, headers, rows)

    cleaned_columns: list[list[float | None]] = []
    for _path, cleaning in cleanings:
        cleaned_columns.extend(
            (
                [point.z_real_ohm * scale for point in cleaning.cleaned_points],
                [point.minus_z_imag_ohm * scale for point in cleaning.cleaned_points],
            )
        )
    cleaned_row_count = max((len(column) for column in cleaned_columns), default=0)
    cleaned_rows = [
        [column[row_index] if row_index < len(column) else None for column in cleaned_columns]
        for row_index in range(cleaned_row_count)
    ]
    _write_csv(cleaned_path, headers, cleaned_rows)

    ignored_headers = ["source_file", "source_index", "frequency_hz", "z_real_ohm", "minus_z_imag_ohm", "reason"]
    ignored_rows: list[list[float | str | None]] = []
    for path, cleaning in cleanings:
        for ignored in cleaning.ignored_points:
            point = ignored.point
            ignored_rows.append(
                [path.name, point.source_index, point.frequency_hz, point.z_real_ohm, point.minus_z_imag_ohm, ignored.reason]
            )
    _write_csv(ignored_path, ignored_headers, ignored_rows)

    series_metadata = [
        {
            "source_file": str(path),
            "plot_label": legend_entries[index],
            "raw_point_count": len(cleaning.raw_points),
            "cleaned_point_count": len(cleaning.cleaned_points),
            "ignored_point_count": len(cleaning.ignored_points),
            "cleaning": cleaning.to_metadata(),
        }
        for index, (path, cleaning) in enumerate(cleanings)
    ]
    aggregate_cleaning = {
        "source_count": len(cleanings),
        "raw_point_count": sum(len(cleaning.raw_points) for _path, cleaning in cleanings),
        "cleaned_point_count": sum(len(cleaning.cleaned_points) for _path, cleaning in cleanings),
        "ignored_point_count": sum(len(cleaning.ignored_points) for _path, cleaning in cleanings),
    }
    eis_metadata = {
        "mode": "reviewed_template_multi_source_overlay",
        "cleaning": aggregate_cleaning,
        "series": series_metadata,
        "fit": {"status": "not_run", "reason": "The reviewed EIS template is a measured multi-source overlay, not a fitted-curve product."},
        "full_fit": {},
        "raw_data": _template_run_relative_path(type_root, raw_path),
        "cleaned_data": _template_run_relative_path(type_root, cleaned_path),
        "ignored_points": _template_run_relative_path(type_root, ignored_path),
        "fit_curve": "",
        "fit_parameters": _template_run_relative_path(type_root, fit_parameters_path),
        "ignored_points_report": _template_run_relative_path(type_root, ignored_report_path),
        "full_fit_curve_debug": "",
        "strict_semicircle_branch": False,
        "strict_semicircle_branch_requested": bool(strict_semicircle_branch_requested),
        "expected_plot_count": expected_plot_count,
        "plotted_source_count": len(source_files),
        "main_plot_curve_policy": "All real measured sweep points are retained because the reviewed template overlays measured Nyquist curves without a draft fit.",
        "equivalent_circuit_policy": "No equivalent-circuit fit or mechanistic interpretation is generated for this template overlay.",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(eis_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    fit_parameters_path.write_text(json.dumps(eis_metadata["fit"], ensure_ascii=False, indent=2), encoding="utf-8")
    ignored_report_path.parent.mkdir(parents=True, exist_ok=True)
    ignored_lines = [
        "# EIS ignored points report",
        "",
        f"- Source curves: {len(source_files)}",
        f"- Raw points: {aggregate_cleaning['raw_point_count']}",
        f"- Cleaned diagnostic points: {aggregate_cleaning['cleaned_point_count']}",
        f"- Ignored diagnostic points: {aggregate_cleaning['ignored_point_count']}",
        "- Main plot policy: retain all real measured sweep points to match the reviewed multi-source template.",
        "",
        "| source_file | source_index | frequency_hz | z_real_ohm | minus_z_imag_ohm | reason |",
        "|---|---:|---:|---:|---:|---|",
    ]
    ignored_lines.extend(
        f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |"
        for row in ignored_rows
    )
    ignored_report_path.write_text("\n".join(ignored_lines).rstrip() + "\n", encoding="utf-8")

    labels = {
        "x_label": "Z' (kOhm)",
        "y_label": "-Z'' (kOhm)",
        "title": "EIS measured overlay",
        "plot_type": "line+symbol",
        "legend_entries": ["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"],
        "notes": "Measured multi-source Nyquist overlay; equivalent-circuit interpretation requires manual review.",
    }
    overlay = {
        "source_files": [str(path) for path in source_files],
        "expected_plot_count": expected_plot_count,
        "plotted_source_count": len(source_files),
        "series_labels": legend_entries,
        "selection_policy": "Select one reviewed real EIS source family with exactly the template plot count; never duplicate or synthesize curves.",
    }
    return headers, rows, labels, {"eis_cleaning": eis_metadata, "eis_overlay": overlay}


def _discover_template_eis_overlay_sources(pairing: TargetPairing, expected_plot_count: int) -> list[Path]:
    if expected_plot_count < 1:
        raise ValueError("EIS template plot count must be positive")
    roots = [pairing.reference_opju.parent, pairing.reference_opju.parent.parent]
    roots.extend(path.parent for path in pairing.data_paths)
    roots.extend(path.parent.parent for path in pairing.data_paths)
    grouped: dict[Path, list[Path]] = {}
    seen_files: set[str] = set()
    suffixes = {".txt", ".csv", ".xls", ".xlsx", ".xlsm"}
    for root in _template_unique_paths(roots):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
            if not path.is_file() or path.suffix.casefold() not in suffixes:
                continue
            name = path.name.casefold()
            if any(token in name for token in ("readme", "report", "fit", "summary", "汇总")):
                continue
            key = str(path.resolve())
            if key in seen_files:
                continue
            seen_files.add(key)
            try:
                cleaning = clean_eis_file(path)
            except Exception:
                continue
            if len(cleaning.raw_points) < 10:
                continue
            grouped.setdefault(path.parent, []).append(path)

    eligible = [(parent, paths) for parent, paths in grouped.items() if len(paths) >= expected_plot_count]
    if not eligible:
        raise ValueError(
            f"Could not find a real EIS source family with {expected_plot_count} curves near the reviewed pairing; curves will not be duplicated or fabricated"
        )
    reference_dates = [int(value) for value in re.findall(r"20\d{6}", str(pairing.reference_opju))]
    reference_date = reference_dates[-1] if reference_dates else None

    def score(item: tuple[Path, list[Path]]) -> tuple[int, int, int, int, str]:
        parent, paths = item
        date_tokens = [int(value) for value in re.findall(r"20\d{6}", str(parent))]
        date_distance = abs(date_tokens[-1] - reference_date) if date_tokens and reference_date is not None else 99999999
        text_count = sum(path.suffix.casefold() == ".txt" for path in paths)
        return (
            int(len(paths) == expected_plot_count),
            -abs(len(paths) - expected_plot_count),
            -date_distance,
            text_count,
            str(parent).casefold(),
        )

    selected_parent, selected_paths = max(eligible, key=score)
    del selected_parent
    ordered = sorted(
        selected_paths,
        key=lambda path: (0 if path.suffix.casefold() == ".txt" else 1, path.name.casefold()),
    )[:expected_plot_count]
    if len(ordered) != expected_plot_count:
        raise ValueError(f"EIS source selection returned {len(ordered)} curves; expected {expected_plot_count}")
    return ordered


def _build_template_epr_table(
    pairing: TargetPairing,
    type_root: Path,
    template: TemplateCandidate,
    slug: str,
    *,
    compact_output: bool = False,
) -> tuple[list[str], list[list[float | str | None]], dict[str, str], dict[str, object]]:
    group_name = _select_template_epr_group(pairing, template)
    reference_dir = _infer_template_epr_reference_dir(pairing.data_paths, group_name)
    entries = DEFAULT_EPR_GROUPS[group_name]
    traces = []
    for label, file_name in entries:
        path = reference_dir / file_name
        if not path.is_file():
            raise FileNotFoundError(f"EPR overlay input missing for {group_name}: {path}")
        export = read_verified_jeol_export_series(path)
        traces.append(
            {
                "label": label,
                "file_name": file_name,
                "path": path,
                "x": export.x_values,
                "y": export.y_values,
                "field_unit": export.x_unit,
                "field_axis_source": export.axis_source,
                "raw_source": export.raw_source,
            }
        )
    _validate_template_epr_common_x([trace["x"] for trace in traces])
    field_units = {str(trace["field_unit"]) for trace in traces if str(trace["field_unit"]).strip()}
    if len(field_units) > 1:
        raise ValueError(f"EPR template inputs use inconsistent field units: {sorted(field_units)}")
    field_unit = next(iter(field_units), "G")
    sidecar_root = type_root / "debug" if compact_output else type_root / "processed_data"
    plan_root = type_root / "debug" if compact_output else type_root / "metadata"
    raw_csv = sidecar_root / f"epr_{group_name.lower()}_overlay_origin_raw_input.csv"
    detail_csv = sidecar_root / f"epr_{group_name.lower()}_overlay_origin_detail.csv"
    plan_path = plan_root / "epr_origin_processing_plan.json"
    final_csv = type_root / f"{slug}.csv" if compact_output else type_root / "processed_data" / f"{slug}.csv"
    raw_headers = ["magnetic_field", *[f"{trace['label']}_raw" for trace in traces]]
    raw_rows = [
        [x_value, *[trace["y"][row_index] for trace in traces]]
        for row_index, x_value in enumerate(traces[0]["x"])
    ]
    _write_csv(raw_csv, raw_headers, raw_rows)
    processing_plan = {
        "processing_location": "Origin LabTalk workbook after raw data import",
        "raw_origin_input_csv": _template_plan_relative_path(plan_path, raw_csv),
        "origin_detail_csv": _template_plan_relative_path(plan_path, detail_csv),
        "final_product_processed_csv": _template_plan_relative_path(plan_path, final_csv),
        "group": group_name,
        "input_files": [str(trace["path"]) for trace in traces],
        "labels": [str(trace["label"]) for trace in traces],
        "field_unit": field_unit,
        "field_axis_sources": {str(trace["label"]): str(trace["field_axis_source"]) for trace in traces},
        "verified_raw_sources": {
            str(trace["label"]): Path(str(trace["raw_source"])).name
            for trace in traces
            if trace["raw_source"] is not None
        },
        "baseline_correction": "Origin LabTalk edge-region median baseline subtraction",
        "smoothing": "Origin smooth X-Function, adjacent averaging, npts=7",
        "normalization": "none",
        "background_subtraction": "none",
        "offset_rule": "Origin LabTalk median peak-to-peak range * 0.85 rounded to readable step; BC top, CWO middle, BOBC bottom",
        "review_policy": "processed in Origin for visualization/manual review only; no radical assignment or mechanism conclusion",
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(processing_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    headers = ["magnetic_field", *[str(trace["label"]) for trace in traces]]
    rows = [[row[0], *row[1:]] for row in raw_rows]
    labels = {
        "x_label": f"Magnetic Field ({field_unit})",
        "y_label": "Intensity (a.u.)",
        "title": f"EPR {group_name} overlay exemplar",
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
                candidate_dirs.append(parent / "导出后的数据")
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
    xb_bold = _number_matches(numeric.get("xb.bold"), 1) or "\\b(" in xb_text or "/b(" in xb_text
    yl_bold = _number_matches(numeric.get("yl.bold"), 1) or "\\b(" in yl_text or "/b(" in yl_text
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
    if product.product_key not in {"EIS", "XRD", "EPR", "UV-vis DRS / Tauc"}:
        return
    if product.product_key == "EIS":
        x_min, x_max = _csv_bounds_for_columns(product.processed_data, (0, 2))
        y_min, y_max = _csv_bounds_for_columns(product.processed_data, (1, 3))
    elif product.product_key == "XRD":
        x_min, x_max = _csv_x_bounds(product.processed_data)
        y_min, y_max = _csv_y_bounds(product.processed_data)
    else:
        x_min, x_max = _csv_x_bounds(product.processed_data)
        y_min, y_max = None, None
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
        component = re.sub(r"_(?:line|fill_upper)$", "", header.rsplit("_component_", 1)[-1])
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
        if index + 1 < len(tokens) and tokens[index + 1].casefold() in {"pilot", "exemplar"}:
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
    core_artifacts_available = all(path.exists() and path.stat().st_size > 0 for path in required)
    independent_reference_available = _has_independent_reference_preview(product)
    has_artifacts = core_artifacts_available and independent_reference_available
    product_style = export_status.get("product_style") if isinstance(export_status.get("product_style"), dict) else {}
    conformance = export_status.get("conformance") if isinstance(export_status.get("conformance"), dict) else {}
    strict_readback = export_status.get("strict_style_readback") if isinstance(export_status.get("strict_style_readback"), dict) else {}
    template_base_mode = _is_template_base_origin_status(export_status)
    saved_format_theme_mode = _is_saved_format_theme_origin_status(export_status)
    cached_style_package_mode = _is_cached_style_package_origin_status(export_status)
    saved_style_asset_mode = (
        saved_format_theme_mode
        or cached_style_package_mode
        or _is_verified_graph_template_origin_status(export_status)
    )
    origin_processing = (
        export_status.get("origin_processing")
        if isinstance(export_status.get("origin_processing"), dict)
        else {}
    )
    preserve_exemplar_exact = (
        str(origin_processing.get("style_contract") or "")
        == "preserve_exemplar_exact"
    )
    axis_title_bold_required = _export_exemplar_axis_title_bold_required(export_status)
    widths = product_style.get("plot_line_widths", []) if isinstance(product_style, dict) else []
    line_width_ok = (
        _line_widths_match_exemplar_conformance(conformance, widths)
        if preserve_exemplar_exact
        else _line_widths_accepted(widths)
    )
    if preserve_exemplar_exact:
        exemplar_checks = _saved_style_asset_exemplar_readback(
            export_status.get("exemplar_style"),
            product_style,
        )
        axis_checks = {
            key: value
            for key, value in exemplar_checks.items()
            if key.startswith("axis_title_")
        }
        axis_title_ok = bool(axis_checks) and all(axis_checks.values())
    elif saved_style_asset_mode:
        axis_title_ok = bool(conformance) and (
            not axis_title_bold_required or bool(conformance.get("axis_title_bold"))
        )
    else:
        axis_title_ok = bool(conformance.get("axis_title_bold")) if conformance else bool(export_status.get("axis_title_bold_policy"))
    if strict_readback and not preserve_exemplar_exact:
        if saved_style_asset_mode:
            axis_title_ok = axis_title_ok and bool(strict_readback.get("axis_title_visible", True))
        elif template_base_mode:
            axis_title_ok = (
                (axis_title_ok or not axis_title_bold_required)
                and (bool(strict_readback.get("axis_title_bold")) or not axis_title_bold_required)
                and bool(strict_readback.get("axis_title_visible"))
            )
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
    if not core_artifacts_available:
        notes.append("required artifact missing or empty")
    if not independent_reference_available:
        notes.append(
            "independent reference preview missing or invalid; the generated product preview cannot serve as its own reference"
        )
    if not line_width_ok:
        notes.append(
            "line width readback did not match the exemplar"
            if preserve_exemplar_exact
            else "line width readback did not meet 3 pt policy"
        )
    if not axis_title_ok:
        notes.append("axis title bold/readback did not pass")
    conformance_reasons = _template_conformance_acceptance_reasons(conformance)
    if saved_style_asset_mode and not conformance:
        conformance_reasons.append("saved style asset conformance is unavailable")
    if conformance_reasons:
        visual_ok = False
        notes.extend(conformance_reasons)
    if product.product_key == "EIS":
        eis = extra.get("eis_cleaning", {}) if isinstance(extra.get("eis_cleaning"), dict) else {}
        if eis.get("mode") == "reviewed_template_multi_source_overlay":
            expected = int(eis.get("expected_plot_count") or 0)
            plotted = int(eis.get("plotted_source_count") or 0)
            if expected <= 0 or plotted != expected:
                visual_ok = False
                notes.append(f"EIS measured overlay plotted {plotted} real curves but template requires {expected}")
        elif eis.get("mode") == "formal_measured_points_only":
            fit = eis.get("fit", {}) if isinstance(eis, dict) else {}
            raw_count = int(eis.get("raw_point_count") or 0)
            plotted_count = int(eis.get("plotted_point_count") or 0)
            headers = [str(value).casefold() for value in _csv_header(product.processed_data)]
            fit_columns = [header for header in headers if "fit" in header]
            fit_sidecars = [
                path
                for path in (
                    product.type_root / "debug" / "eis_randles_cpe_fit_curve.csv",
                    product.type_root / "debug" / "eis_randles_cpe_full_fit_curve.csv",
                    product.type_root / "debug" / "eis_fit_parameters.json",
                    product.type_root / "processed_data" / "eis_randles_cpe_fit_curve.csv",
                    product.type_root / "metadata" / "eis_fit_parameters.json",
                )
                if path.exists()
            ]
            if raw_count <= 0 or plotted_count != raw_count:
                visual_ok = False
                notes.append(
                    f"EIS measured-point preservation failed: plotted {plotted_count} of {raw_count} parsed raw points"
                )
            if str(fit.get("status") or "") != "not_run":
                visual_ok = False
                notes.append("EIS formal product did not record fit.status=not_run")
            if fit_columns:
                visual_ok = False
                notes.append("EIS formal product contains forbidden automatic fit columns: " + ", ".join(fit_columns))
            if fit_sidecars:
                visual_ok = False
                notes.append(
                    "EIS formal product contains forbidden automatic fit sidecars: "
                    + ", ".join(path.name for path in fit_sidecars)
                )
        else:
            visual_ok = False
            notes.append("EIS processing mode was not a recognized measured-data-only workflow")
    if product.product_key.startswith("XPS"):
        fill = export_status.get("xps_component_fill") if isinstance(export_status.get("xps_component_fill"), dict) else {}
        if not fill.get("applied"):
            visual_ok = False
            notes.append("XPS component fill was not applied/read back as required")
    if product.product_key != "EIS":
        if not origin_processing.get("applied") or "Origin" not in str(origin_processing.get("processing_location", "")):
            visual_ok = False
            notes.append("Origin-side data processing was not executed/read back for this non-EIS product")
    relevant_readback = _relevant_strict_readback_values(
        strict_readback,
        template_base_mode=template_base_mode,
        saved_style_asset_mode=saved_style_asset_mode,
        preserve_exemplar_exact=preserve_exemplar_exact,
        axis_title_bold_required=axis_title_bold_required,
        exemplar_style=export_status.get("exemplar_style"),
        product_style=product_style,
    )
    if relevant_readback and not all(bool(value) for value in relevant_readback.values()):
        visual_ok = False
        failed = [key for key, value in relevant_readback.items() if not value]
        notes.append("strict style readback failed: " + ", ".join(failed))
    exemplar_similarity = template.status in {"extracted", "valid", "embedded"} and template.layer_count > 0 and template.plot_count > 0 and readback_ok
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


def _has_independent_reference_preview(product: ProductContext) -> bool:
    return _independent_preview_path_available(
        product.reference_preview_png,
        product.preview_png,
    )


def _independent_preview_path_available(reference: Path, generated: Path) -> bool:
    try:
        if not reference.is_file() or reference.stat().st_size <= 0:
            return False
        if reference.resolve(strict=False) == generated.resolve(strict=False):
            return False
        if generated.exists() and reference.samefile(generated):
            return False
    except OSError:
        return False
    return True


def _is_template_base_origin_status(export_status: dict[str, object]) -> bool:
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    return str(origin_processing.get("method", "")) in {
        "opju_template_base_workbook_replacement",
        "opju_template_snapshot_fallback_graph",
        "embedded_template_snapshot_graph",
    }


def _export_exemplar_axis_title_bold_required(export_status: dict[str, object]) -> bool:
    exemplar_style = export_status.get("exemplar_style") if isinstance(export_status.get("exemplar_style"), dict) else {}
    if not exemplar_style:
        return True
    return _style_snapshot_axis_title_bold_required(exemplar_style)


def _style_snapshot_axis_title_bold_required(snapshot: object) -> bool:
    payload = _style_snapshot_payload(snapshot)
    numeric = payload.get("audit_numeric_values") if isinstance(payload.get("audit_numeric_values"), dict) else {}
    strings = payload.get("audit_string_values") if isinstance(payload.get("audit_string_values"), dict) else {}
    return _axis_title_bold_readback(numeric, strings)


def _is_cached_style_package_origin_status(export_status: dict[str, object]) -> bool:
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    return str(origin_processing.get("method", "")) == "cached_style_package_graph_template"


def _is_saved_format_theme_origin_status(export_status: dict[str, object]) -> bool:
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    return str(origin_processing.get("method", "")) == "saved_format_theme_apply"


def _is_verified_graph_template_origin_status(
    export_status: dict[str, object],
) -> bool:
    origin_processing = (
        export_status.get("origin_processing")
        if isinstance(export_status.get("origin_processing"), dict)
        else {}
    )
    return (
        str(origin_processing.get("method", ""))
        == "fresh_graph_verified_otpu_explicit_xy"
    )


def _relevant_strict_readback_values(
    strict_readback: dict[str, object],
    *,
    template_base_mode: bool,
    saved_style_asset_mode: bool = False,
    preserve_exemplar_exact: bool = False,
    axis_title_bold_required: bool = True,
    exemplar_style: object = None,
    product_style: object = None,
) -> dict[str, object]:
    if not strict_readback:
        return {}
    if saved_style_asset_mode:
        values = {
            key: strict_readback.get(key)
            for key in ("axis_title_visible",)
            if key in strict_readback
        }
        values.update(
            _saved_style_asset_exemplar_readback(
                exemplar_style,
                product_style,
            )
        )
        return values
    if preserve_exemplar_exact:
        return _saved_style_asset_exemplar_readback(
            exemplar_style,
            product_style,
        )
    if not template_base_mode:
        return strict_readback
    keys = ("font_family_arial", "axis_title_visible", "axis_title_no_overlap")
    if axis_title_bold_required:
        keys = ("font_family_arial", "axis_title_bold", "axis_title_visible", "axis_title_no_overlap")
    return {key: strict_readback.get(key) for key in keys if key in strict_readback}


def _line_widths_match_exemplar_conformance(
    conformance: dict[str, object],
    widths: object,
) -> bool:
    if not isinstance(widths, (list, tuple)) or not widths or not conformance:
        return False
    issues = conformance.get("issues")
    rows = [item for item in issues if isinstance(item, dict)] if isinstance(issues, list) else []
    return not any(
        str(item.get("severity") or "").casefold() == "fail"
        and (
            str(item.get("field") or "") == "plot_line_widths"
            or str(item.get("field") or "").endswith(".line_width")
        )
        for item in rows
    )


def _saved_style_asset_exemplar_readback(
    exemplar_style: object,
    product_style: object,
) -> dict[str, bool]:
    exemplar = _style_snapshot_payload(exemplar_style)
    product = _style_snapshot_payload(product_style)
    if not exemplar or not product:
        return {}
    exemplar_numeric = exemplar.get("audit_numeric_values")
    product_numeric = product.get("audit_numeric_values")
    exemplar_strings = exemplar.get("audit_string_values")
    product_strings = product.get("audit_string_values")
    if not isinstance(exemplar_numeric, dict):
        exemplar_numeric = {}
    if not isinstance(product_numeric, dict):
        product_numeric = {}
    if not isinstance(exemplar_strings, dict):
        exemplar_strings = {}
    if not isinstance(product_strings, dict):
        product_strings = {}

    checks: dict[str, bool] = {}
    axis_size_fields = ("xb.fsize", "yl.fsize")
    if any(field in exemplar_numeric for field in axis_size_fields):
        checks["axis_title_font_size_matches_exemplar"] = _reported_numeric_fields_match(
            exemplar_numeric,
            product_numeric,
            axis_size_fields,
        )

    axis_visibility_fields = ("xb.show", "yl.show")
    if any(field in exemplar_numeric for field in axis_visibility_fields):
        checks["axis_title_visibility_matches_exemplar"] = _reported_numeric_fields_match(
            exemplar_numeric,
            product_numeric,
            axis_visibility_fields,
        )

    bold_evidence_fields = ("xb.bold", "yl.bold")
    bold_text_fields = ("xb.text$", "yl.text$")
    if any(field in exemplar_numeric for field in bold_evidence_fields) or any(
        str(exemplar_strings.get(field) or "").strip() for field in bold_text_fields
    ):
        checks["axis_title_bold_matches_exemplar"] = _axis_title_bold_readback(
            exemplar_numeric,
            exemplar_strings,
        ) == _axis_title_bold_readback(product_numeric, product_strings)

    axis_font_fields = ("xb.font$", "yl.font$")
    if any(str(exemplar_strings.get(field) or "").strip() for field in axis_font_fields):
        checks["axis_title_font_matches_exemplar"] = _reported_string_fields_match(
            exemplar_strings,
            product_strings,
            axis_font_fields,
        )

    legend_numeric_fields = (
        "legend.background",
        "legend.border",
        "legend.frame",
        "legend.fill",
        "legend.fillColor",
        "legend.borderColor",
        "legend.lineWidth",
    )
    if any(field in exemplar_numeric for field in legend_numeric_fields):
        checks["legend_frame_matches_exemplar"] = _reported_numeric_fields_match(
            exemplar_numeric,
            product_numeric,
            legend_numeric_fields,
        )
    if "legend.bold" in exemplar_numeric or str(exemplar_strings.get("legend.text$") or "").strip():
        checks["legend_bold_matches_exemplar"] = _legend_bold_readback(
            exemplar_numeric,
            exemplar_strings,
        ) == _legend_bold_readback(product_numeric, product_strings)
    if str(exemplar_strings.get("legend.font$") or "").strip():
        checks["legend_font_matches_exemplar"] = _reported_string_fields_match(
            exemplar_strings,
            product_strings,
            ("legend.font$",),
        )
    return checks


def _style_snapshot_payload(snapshot: object) -> dict[str, object]:
    if isinstance(snapshot, OpjuStyleSnapshot):
        return snapshot.to_dict()
    return dict(snapshot) if isinstance(snapshot, dict) else {}


def _reported_numeric_fields_match(
    exemplar: dict[str, object],
    product: dict[str, object],
    fields: tuple[str, ...],
) -> bool:
    for field in fields:
        if field not in exemplar:
            continue
        expected = _to_float(exemplar.get(field))
        actual = _to_float(product.get(field))
        if expected is None or actual is None or abs(expected - actual) > 0.01:
            return False
    return True


def _reported_string_fields_match(
    exemplar: dict[str, object],
    product: dict[str, object],
    fields: tuple[str, ...],
) -> bool:
    for field in fields:
        expected = str(exemplar.get(field) or "").strip()
        if not expected:
            continue
        actual = str(product.get(field) or "").strip()
        if actual.casefold() != expected.casefold():
            return False
    return True


def _template_conformance_acceptance_reasons(conformance: dict[str, object]) -> list[str]:
    if not conformance:
        return []
    reasons: list[str] = []
    status = str(conformance.get("status") or "").strip().casefold()
    issues = conformance.get("issues")
    issue_rows = [item for item in issues if isinstance(item, dict)] if isinstance(issues, list) else []
    fail_fields = [
        str(item.get("field") or "unknown")
        for item in issue_rows
        if str(item.get("severity") or "").casefold() == "fail"
    ]
    if status == "fail" or fail_fields:
        detail = ", ".join(fail_fields) if fail_fields else "reported fail status"
        reasons.append(f"style conformance has fail-severity differences: {detail}")

    if str(conformance.get("axis_title_no_overlap_check") or "").casefold() == "risk":
        reasons.append("axis-title readback indicates overlap risk")

    if status == "review":
        data_range_fields = {
            "layer.x.from",
            "layer.x.to",
            "layer.y.from",
            "layer.y.to",
        }
        non_range_review_fields = [
            str(item.get("field") or "unknown")
            for item in issue_rows
            if str(item.get("severity") or "").casefold() == "review"
            and str(item.get("field") or "") not in data_range_fields
        ]
        if non_range_review_fields:
            reasons.append(
                "style conformance requires review for non-data-range fields: "
                + ", ".join(non_range_review_fields)
            )
        elif not issue_rows:
            reasons.append("style conformance reported review without auditable issue details")
    return reasons


def _write_template_product_metadata(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    style: ResolvedPlotStyle,
    extra: dict[str, object],
    template: TemplateCandidate,
    acceptance: TemplateAcceptance,
    *,
    asset_only: bool = False,
) -> Path:
    compact = product.processed_data.parent == product.type_root
    path = product.type_root / "metadata.json" if compact else product.type_root / "metadata" / product.slug / "metadata.json"
    reference_opju_copy = (
        _safe_metadata_path(product.reference_opju_copy)
        if product.reference_opju_copy.suffix.casefold() in {".opju", ".opj"}
        else ""
    )
    reference_style_asset_copy = (
        _safe_metadata_path(product.reference_opju_copy)
        if product.reference_opju_copy.suffix.casefold() not in {".opju", ".opj"}
        else ""
    )
    payload = {
        "dataset_id": product.slug,
        "metadata_path": _safe_metadata_path(path),
        "product_key": product.product_key,
        "status": acceptance.status,
        "data_type": product.pairing.data_type,
        "xps_subtype": product.pairing.xps_subtype,
        "selected_data_relative_paths": _safe_metadata_paths(_selected_relative_paths(product.pairing, "selected_data_relative_paths")),
        "source_files": [_safe_metadata_path(path) for path in product.pairing.data_paths],
        "template_path": _template_display_path(template.path),
        "template_graph": template.graph_page,
        "template_layer_count": template.layer_count,
        "template_plot_count": template.plot_count,
        "asset_only": bool(asset_only),
        "external_template_dependency": False
        if asset_only
        else template.source not in PROJECT_LOCAL_TEMPLATE_SOURCES,
        "project_style_asset_path": _template_display_path(template.path)
        if template.source in PROJECT_LOCAL_TEMPLATE_SOURCES
        else "",
        "input_copies": [_safe_metadata_path(path) for path in product.input_copies],
        "reference_opju_copy": reference_opju_copy,
        "reference_style_asset_copy": reference_style_asset_copy,
        "external_reference_template": _external_reference_template_metadata(product),
        "reference_preview_png": _safe_metadata_path(product.reference_preview_png),
        "processed_data": _safe_metadata_path(product.processed_data),
        "origin_file": _safe_metadata_path(product.origin_file),
        "figure_tif": _safe_metadata_path(product.figure_tif),
        "preview_png": _safe_metadata_path(product.preview_png),
        "origin_status": export_status,
        "external_reference_preview": export_status.get("external_reference_preview", {}),
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


def _external_reference_template_metadata(product: ProductContext) -> dict[str, object]:
    if product.external_reference_opju is None:
        return {"selected": False}
    return {
        "selected": True,
        "source_opju": _relative_to_run(product.type_root.parent, product.external_reference_opju),
        "graph_page": product.external_reference_graph,
        "source": product.external_reference_source,
    }


def _write_template_per_type_report(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    style: ResolvedPlotStyle,
    extra: dict[str, object],
    template: TemplateCandidate,
    acceptance: TemplateAcceptance,
) -> Path:
    compact = product.processed_data.parent == product.type_root
    path = product.type_root / "report.md" if compact else product.type_root / "reports" / f"{product.slug}_report.md"
    conformance = export_status.get("conformance") if isinstance(export_status.get("conformance"), dict) else {}
    strict_readback = export_status.get("strict_style_readback") if isinstance(export_status.get("strict_style_readback"), dict) else {}
    xps_fill = export_status.get("xps_component_fill") if isinstance(export_status.get("xps_component_fill"), dict) else {}
    origin_processing = export_status.get("origin_processing") if isinstance(export_status.get("origin_processing"), dict) else {}
    epr_processing = export_status.get("epr_origin_processing") if isinstance(export_status.get("epr_origin_processing"), dict) else {}
    external_reference = _external_reference_template_metadata(product)
    external_reference_preview = export_status.get("external_reference_preview") if isinstance(export_status.get("external_reference_preview"), dict) else {}
    lines = [
        f"# {product.product_key} template-format report",
        "",
        f"- Status: {acceptance.status}",
        f"- Template path: {_template_display_path(template.path)}",
        f"- Template graph: {template.graph_page}",
        f"- Reference PNG preview: {_relative_to_run(run_root, product.reference_preview_png)}",
        f"- External reference OPJU: {external_reference.get('source_opju', '') if external_reference.get('selected') else 'not selected'}",
        f"- External reference graph: {external_reference.get('graph_page', '') if external_reference.get('selected') else ''}",
        f"- External reference preview export: {external_reference_preview}",
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
        if eis.get("mode") == "reviewed_template_multi_source_overlay":
            lines.extend(
                [
                    "",
                    "## EIS measured overlay",
                    f"- Real source curves: {eis.get('plotted_source_count', 0)} / template {eis.get('expected_plot_count', 0)}",
                    f"- Raw measured data: {eis.get('raw_data', 'not generated')}",
                    f"- Cleaned diagnostic data: {eis.get('cleaned_data', 'not generated')}",
                    f"- Ignored points table: {eis.get('ignored_points', 'not generated')}",
                    f"- Ignored diagnostic points: {cleaning.get('ignored_point_count', 0)}",
                    "- Draft fit: not run; the reviewed template is a measured multi-source overlay",
                    "- Equivalent-circuit interpretation: manual review required",
                ]
            )
        elif eis.get("mode") == "formal_measured_points_only":
            lines.extend(
                [
                    "",
                    "## EIS measured-data product",
                    f"- Parsed measured points: {eis.get('raw_point_count', 0)}",
                    f"- Plotted measured points: {eis.get('plotted_point_count', 0)}",
                    f"- Fit status: {fit.get('status', 'not_run')}",
                    "- Automatic cleaning/exclusion: not applied to the formal graph",
                    "- Semicircle-branch selection: not run",
                    "- Equivalent-circuit fit and fit sidecars: not generated",
                    "- Circuit interpretation: manual review required",
                ]
            )
        else:
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
    visual_notes_path = product.type_root.joinpath("debug", "visual_diff_notes.md")
    visual_notes_path.parent.mkdir(parents=True, exist_ok=True)
    visual_notes_path.write_text(
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
    *,
    asset_only: bool = False,
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
        "asset_only": bool(asset_only),
        "external_template_dependency": False if asset_only else template.source not in PROJECT_LOCAL_TEMPLATE_SOURCES,
        "project_style_asset_path": _template_display_path(template.path)
        if template.source in PROJECT_LOCAL_TEMPLATE_SOURCES
        else "",
        "external_reference_opju": _relative_to_run(run_root, product.external_reference_opju) if product.external_reference_opju else "",
        "external_reference_graph": product.external_reference_graph,
        "external_reference_source": product.external_reference_source,
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
    compact: bool = False,
    asset_only: bool = False,
) -> dict[str, object]:
    type_root = _template_type_root(run_root, product_key, compact=compact)
    _ensure_template_type_dirs(type_root, compact=compact)
    report = type_root / "report.md" if compact else type_root / "reports" / f"{TEMPLATE_PRODUCT_SLUGS[product_key]}_report.md"
    message = reason or selection.reason
    selected_source = selection.selected.source if selection.selected is not None else ""
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
        "asset_only": bool(asset_only),
        "external_template_dependency": False
        if asset_only
        else bool(selected_source and selected_source not in PROJECT_LOCAL_TEMPLATE_SOURCES),
        "project_style_asset_path": _template_display_path(selection.selected.path)
        if selection.selected is not None and selected_source in PROJECT_LOCAL_TEMPLATE_SOURCES
        else "",
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


def _failed_product_record(
    run_root: Path,
    product_key: str,
    selection: TemplateSelection,
    message: str,
    *,
    compact: bool = False,
    asset_only: bool = False,
) -> dict[str, object]:
    record = _blocked_product_record(
        run_root,
        product_key,
        selection,
        reason=message,
        compact=compact,
        asset_only=asset_only,
    )
    record["status"] = "failed"
    return record


def _with_label_audit_status(product: dict[str, object], label_audit: dict[str, object]) -> dict[str, object]:
    if not _label_audit_passes(label_audit) and product.get("status") == "accepted":
        product = dict(product)
        product["status"] = "blocked"
        product["visual_acceptance"] = False
        product["notes"] = (str(product.get("notes") or "") + "; no-label audit failed").strip("; ")
    return product


def _label_audit_passes(label_audit: dict[str, object]) -> bool:
    return int(label_audit.get("hit_count", 0)) == 0 and len(label_audit.get("path_only_hits") or []) == 0


def _append_template_acceptance_note(existing: object, note: str) -> str:
    notes = [item.strip() for item in str(existing or "").split(";") if item.strip()]
    normalized = note.strip()
    if normalized and normalized not in notes:
        notes.append(normalized)
    return "; ".join(notes)


def _write_template_preview_comparison(
    run_root: Path,
    products: list[dict[str, object]],
    *,
    label_audit: dict[str, object] | None = None,
    style_replay_evidence: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    reports = run_root / "reports"
    comparisons = reports / "template_preview_comparisons"
    comparisons.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, object]] = []
    completeness_rows: list[dict[str, object]] = []
    for product in products:
        product_type = str(product.get("type") or product.get("product_key") or "unknown")
        reference = _resolve_run_relative_artifact(run_root, product.get("reference_preview_png"))
        generated = _resolve_run_relative_artifact(run_root, product.get("preview_png"))
        side_by_side = comparisons / f"{safe_name(product_type)}_template_vs_generated.png"
        metadata = _read_template_product_metadata(product, run_root)
        reference_ok = _independent_preview_path_available(reference, generated)
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
                missing.append("independent template preview missing")
            if not generated_ok:
                missing.append("generated preview missing")
            message = "; ".join(missing)
        template_plot_count = _template_plot_count(product, metadata)
        product_plot_count = _template_product_plot_count(product, metadata)
        plot_count_delta = product_plot_count - template_plot_count
        conformance = _template_product_conformance(product, metadata)
        style_match_ratio = _template_style_match_ratio(conformance)
        preview_rms = _to_float(image_metrics.get("preview_rms"))
        preview_review_reasons = _template_preview_review_reasons(
            ready=ready,
            preview_rms=preview_rms,
            reference_size=str(image_metrics.get("reference_size") or ""),
            generated_size=str(image_metrics.get("generated_size") or ""),
        )
        saved_style_asset_mode = _is_saved_style_asset_preview_product(product, metadata)
        replay_validation = (
            (style_replay_evidence or {}).get(
                _style_replay_key(product_type),
                {
                    "ok": False,
                    "reason": "independent theme-application replay evidence was not supplied",
                },
            )
            if saved_style_asset_mode
            else {"ok": True, "reason": "not_required_for_this_template_mode"}
        )
        embedded_snapshot_mode = _is_embedded_template_snapshot_preview_product(product, metadata)
        xrd_clean_rebuild_mode = _is_xrd_clean_rebuild_preview_product(product, metadata)
        if embedded_snapshot_mode:
            strict_reasons = _embedded_template_snapshot_strict_visual_reasons(
                product,
                metadata,
                ready=ready,
                plot_count_delta=plot_count_delta,
                style_match_ratio=style_match_ratio,
                preview_rms=preview_rms,
            )
        elif xrd_clean_rebuild_mode:
            strict_reasons = _embedded_template_snapshot_strict_visual_reasons(
                product,
                metadata,
                ready=ready,
                plot_count_delta=plot_count_delta,
                style_match_ratio=style_match_ratio,
                preview_rms=preview_rms,
                allowed_methods={"opju_template_snapshot_fallback_graph"},
                mode_label="XRD clean graph rebuild",
            )
        else:
            strict_reasons = _template_style_data_binding_reasons(
                ready=ready,
                plot_count_delta=plot_count_delta,
                style_match_ratio=style_match_ratio,
                text_only_legend=_template_text_only_legend_policy(product, metadata),
            )
        for reason in _template_conformance_acceptance_reasons(conformance):
            if reason not in strict_reasons:
                strict_reasons.append(reason)
        if saved_style_asset_mode and not bool(replay_validation.get("ok")):
            strict_reasons.append(
                "saved style asset lacks valid independent theme-application "
                f"replay evidence: {replay_validation.get('reason', 'unknown reason')}"
            )
        plot_count_reason = f"plot count differs from template by {plot_count_delta}"
        if plot_count_delta != 0 and plot_count_reason not in strict_reasons:
            strict_reasons.append(plot_count_reason)
        # Different current data normally produce different pixels.  Once a
        # detached style asset has independent same-data exact validation,
        # reference/current preview RMS remains a manual-review signal and
        # must not be reinterpreted as a style/data-binding failure.
        validated_asset_rms_is_diagnostic = bool(
            saved_style_asset_mode and replay_validation.get("ok")
        )
        style_data_binding_status = (
            "blocked"
            if strict_reasons
            else (
                "review_required"
                if preview_review_reasons and not validated_asset_rms_is_diagnostic
                else "matched"
            )
        )
        style_data_binding_match = style_data_binding_status == "matched"
        strict_visual_match = style_data_binding_match
        if embedded_snapshot_mode:
            strict_status = "embedded_template_snapshot_match" if strict_visual_match else "blocked_embedded_template_snapshot"
        elif xrd_clean_rebuild_mode:
            strict_status = "xrd_clean_graph_rebuild_match" if strict_visual_match else "blocked_xrd_clean_graph_rebuild"
        else:
            strict_status = "strict_visual_match" if strict_visual_match else "blocked_not_one_to_one"
        style_data_binding = {
            "status": style_data_binding_status,
            "match": style_data_binding_match,
            "blocking_reasons": list(strict_reasons),
            "review_reasons": list(preview_review_reasons),
            "preview_review_is_diagnostic_only": validated_asset_rms_is_diagnostic,
            "preview_comparison_ready": ready,
            "preview_rms": preview_rms,
            "preview_rms_role": "diagnostic_only_not_exact_evidence",
            "plot_structure_pass": plot_count_delta == 0,
            "style_conformance_pass": not _template_conformance_acceptance_reasons(conformance),
        }
        asset_same_data_exact_validation = {
            "status": (
                "verified"
                if saved_style_asset_mode and bool(replay_validation.get("ok"))
                else ("invalid" if saved_style_asset_mode else "not_supplied")
            ),
            "asset_runtime_use_allowed": bool(
                saved_style_asset_mode and replay_validation.get("ok")
            ),
            "comparison_scope": (
                "fresh_project_same_data"
                if saved_style_asset_mode and bool(replay_validation.get("ok"))
                else "not_evaluated"
            ),
            "reason": str(
                replay_validation.get("reason")
                if saved_style_asset_mode
                else "same-data exact replay evidence was not supplied for this real-data product"
            ),
        }
        current_product_pixel_exact = {
            "status": "not_evaluated",
            "claim_allowed": False,
            "comparison_scope": "current_product",
            "reason": (
                "This product contains current processed data. A historical same-data style-asset "
                "validation cannot prove that this product is pixel-identical to the reference-data preview."
            ),
        }
        # Compatibility alias.  It intentionally describes the current product,
        # not the historical validation attached to the reusable style asset.
        same_data_exact = dict(current_product_pixel_exact)
        strict_message = "; ".join([*strict_reasons, *preview_review_reasons])
        if strict_message and message:
            message = f"{message}; {strict_message}"
        elif strict_message:
            message = strict_message
        product["template_preview_comparison_png"] = _relative_to_run(run_root, side_by_side) if ready else ""
        product["template_preview_comparison_ready"] = ready
        product["template_plot_count"] = template_plot_count
        product["product_plot_count"] = product_plot_count
        product["plot_count_delta"] = plot_count_delta
        product["preview_rms"] = preview_rms
        product["style_match_ratio"] = style_match_ratio
        product["independent_style_replay"] = replay_validation
        product["evidence_schema_version"] = 2
        product["style_data_binding"] = style_data_binding
        product["asset_same_data_exact_validation"] = asset_same_data_exact_validation
        product["current_product_pixel_exact"] = current_product_pixel_exact
        product["same_data_exact"] = same_data_exact
        product["one_to_one_exact_match"] = False
        product["strict_visual_match"] = strict_visual_match
        product["strict_visual_match_deprecated"] = True
        product["strict_status"] = strict_status
        previous_visual_acceptance = product.get("visual_acceptance")
        if previous_visual_acceptance is None:
            previous_visual_acceptance = product.get("status") == "accepted"
        product["visual_acceptance"] = bool(previous_visual_acceptance) and strict_visual_match
        if label_audit is not None and not _label_audit_passes(label_audit):
            product["visual_acceptance"] = False
            if product.get("status") == "accepted":
                product["status"] = "blocked"
            product["notes"] = _append_template_acceptance_note(
                product.get("notes"),
                "no-label audit failed",
            )
        if not strict_visual_match:
            if product.get("status") == "accepted":
                product["status"] = "blocked"
            detail = strict_message or "template/generated preview comparison did not pass"
            product["notes"] = _append_template_acceptance_note(
                product.get("notes"),
                f"style_data_binding_{style_data_binding_status}: {detail}",
            )
        items.append(
            {
                "type": product_type,
                "status": product.get("status", ""),
                "visual_acceptance": bool(product.get("visual_acceptance")),
                "reference_preview_png": _relative_to_run(run_root, reference) if reference_ok else "",
                "generated_preview_png": _relative_to_run(run_root, generated) if generated_ok else "",
                "side_by_side_png": _relative_to_run(run_root, side_by_side) if ready else "",
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
                "strict_visual_match_deprecated": True,
                "style_data_binding": style_data_binding,
                "asset_same_data_exact_validation": asset_same_data_exact_validation,
                "current_product_pixel_exact": current_product_pixel_exact,
                "same_data_exact": same_data_exact,
                "one_to_one_exact_match": False,
                "saved_style_asset_mode": saved_style_asset_mode,
                "independent_style_replay": replay_validation,
                "embedded_template_snapshot_mode": embedded_snapshot_mode,
                "xrd_clean_graph_rebuild_mode": xrd_clean_rebuild_mode,
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
        "style_data_binding_match_count": sum(
            1 for item in items if item["style_data_binding"]["status"] == "matched"
        ),
        "same_data_exact_match_count": sum(
            1 for item in items if item["one_to_one_exact_match"]
        ),
        "product_count": len(items),
        "items": items,
        "policy": "Real-data style/data-binding acceptance is separate from same-data exact replay. Preview RMS for different or unverified data is diagnostic and never proves one-to-one replication.",
        "no_fabrication_policy": "Missing reference-format series are reported as data gaps, not silently created from preview images or copied annotations.",
    }
    _synchronize_template_product_acceptance_artifacts(
        run_root,
        products,
        audit,
        label_audit=label_audit,
    )
    (reports / "template_preview_comparison.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_template_data_completeness(reports / "template_data_completeness.md", run_root, completeness_rows)
    lines = [
        "# Template preview comparison audit",
        "",
        "- Policy: external OPJU/template products compare the saved reference-format preview with the regenerated product preview.",
        "- Independent-reference policy: every accepted product must have a separate reference preview and a ready reference-vs-generated comparison; saved themes and embedded snapshots are not exemptions.",
        "- Exact policy: one-to-one status requires an independent fresh-project replay with identical per-plot X/Y values and mappings, save/reopen readback, native 600 dpi, zero decoded-pixel difference, and manual preview.",
        "- Real-data policy: style/data-binding is evaluated separately; preview RMS is diagnostic only because different data normally produce different pixels.",
        "- No-fabrication policy: missing source series/reference cards/annotations are reported, not invented.",
        f"- Ready: {audit['ready_count']}/{audit['product_count']}",
        f"- Style/data-binding match: {audit['style_data_binding_match_count']}/{audit['product_count']}",
        f"- Same-data exact match: {audit['same_data_exact_match_count']}/{audit['product_count']}",
        "",
        "| Type | Status | Reference Preview | Generated Preview | Side-by-side | Ready | Reference Plots | Product Plots | RMS (diagnostic) | Style/Data Binding | Same-data Exact | Message |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| {type} | {status} | {ref} | {gen} | {side} | {ready} | {template_plots} | {product_plots} | {rms} | {binding} | {exact} | {message} |".format(
                type=item["type"],
                status=item["status"],
                ref=_path_for_summary(run_root, item["reference_preview_png"], True),
                gen=_path_for_summary(run_root, item["generated_preview_png"], True),
                side=_path_for_summary(run_root, item["side_by_side_png"], True),
                ready=item["ready"],
                template_plots=item["template_plot_count"],
                product_plots=item["product_plot_count"],
                rms="" if item["preview_rms"] is None else f"{float(item['preview_rms']):.2f}",
                binding=item["style_data_binding"]["status"],
                exact=item["same_data_exact"]["status"],
                message=str(item["message"]).replace("|", "/"),
            )
        )
    (reports / "template_preview_comparison.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return audit


def _synchronize_template_product_acceptance_artifacts(
    run_root: Path,
    products: list[dict[str, object]],
    audit: dict[str, object],
    *,
    label_audit: dict[str, object] | None,
) -> None:
    items = audit.get("items") if isinstance(audit.get("items"), list) else []
    label_pass = None if label_audit is None else _label_audit_passes(label_audit)
    for product, raw_item in zip(products, items):
        item = raw_item if isinstance(raw_item, dict) else {}
        evidence = {
            "evidence_schema_version": 2,
            "final_status": str(product.get("status") or "blocked"),
            "visual_acceptance": bool(product.get("visual_acceptance")),
            "ready": bool(item.get("ready")),
            "strict_visual_match": bool(item.get("strict_visual_match")),
            "strict_visual_match_deprecated": True,
            "strict_status": str(item.get("strict_status") or ""),
            "style_data_binding": dict(item.get("style_data_binding") or {}),
            "asset_same_data_exact_validation": dict(
                item.get("asset_same_data_exact_validation") or {}
            ),
            "current_product_pixel_exact": dict(
                item.get("current_product_pixel_exact") or {}
            ),
            "same_data_exact": dict(item.get("same_data_exact") or {}),
            "one_to_one_exact_match": bool(item.get("one_to_one_exact_match")),
            "reference_preview_png": str(item.get("reference_preview_png") or ""),
            "generated_preview_png": str(item.get("generated_preview_png") or ""),
            "comparison_png": str(item.get("side_by_side_png") or ""),
            "template_plot_count": int(item.get("template_plot_count") or 0),
            "product_plot_count": int(item.get("product_plot_count") or 0),
            "plot_count_delta": int(item.get("plot_count_delta") or 0),
            "style_match_ratio": item.get("style_match_ratio"),
            "preview_rms": item.get("preview_rms"),
            "message": str(item.get("message") or ""),
            "label_audit_pass": label_pass,
        }
        product["template_preview_comparison_png"] = evidence["comparison_png"]
        product["template_preview_comparison_ready"] = evidence["ready"]
        product["reference_preview_available"] = bool(evidence["reference_preview_png"])
        product["visual_acceptance_audit"] = evidence

        metadata_path = _resolve_run_relative_artifact(run_root, product.get("metadata"))
        if metadata_path.is_file():
            metadata_payload = _read_template_product_metadata(product, run_root)
            if metadata_payload:
                metadata_payload["status"] = str(product.get("status") or "blocked")
                metadata_payload["visual_acceptance"] = bool(product.get("visual_acceptance"))
                metadata_payload["reference_preview_available"] = bool(evidence["reference_preview_png"])
                metadata_payload["template_preview_comparison_png"] = evidence["comparison_png"]
                metadata_payload["template_preview_comparison_ready"] = evidence["ready"]
                metadata_payload["strict_visual_match"] = evidence["strict_visual_match"]
                metadata_payload["strict_visual_match_deprecated"] = True
                metadata_payload["strict_status"] = evidence["strict_status"]
                metadata_payload["style_data_binding"] = evidence["style_data_binding"]
                metadata_payload["asset_same_data_exact_validation"] = evidence[
                    "asset_same_data_exact_validation"
                ]
                metadata_payload["current_product_pixel_exact"] = evidence[
                    "current_product_pixel_exact"
                ]
                metadata_payload["same_data_exact"] = evidence["same_data_exact"]
                metadata_payload["one_to_one_exact_match"] = evidence["one_to_one_exact_match"]
                metadata_payload["visual_acceptance_audit"] = evidence
                metadata_payload["acceptance_notes"] = _merged_template_acceptance_notes(
                    metadata_payload.get("acceptance_notes"),
                    product.get("notes"),
                )
                metadata_path.write_text(
                    json.dumps(_safe_metadata_payload(metadata_payload), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        report_path = _resolve_run_relative_artifact(run_root, product.get("report"))
        if report_path.is_file():
            _synchronize_template_product_report(
                report_path,
                product,
                evidence,
            )


def _merged_template_acceptance_notes(existing: object, final_notes: object) -> list[str]:
    notes: list[str] = []
    if isinstance(existing, list):
        candidates = [str(item) for item in existing]
    elif existing:
        candidates = [str(existing)]
    else:
        candidates = []
    candidates.extend(str(final_notes or "").split(";"))
    for candidate in candidates:
        normalized = candidate.strip()
        if normalized and normalized not in notes:
            notes.append(normalized)
    return notes


def _synchronize_template_product_report(
    report_path: Path,
    product: dict[str, object],
    evidence: dict[str, object],
) -> None:
    marker = "## Final visual acceptance audit"
    original = report_path.read_text(encoding="utf-8")
    body = original.split(marker, 1)[0].rstrip()
    lines = body.splitlines()
    replacements = {
        "- Status:": f"- Status: {product.get('status') or 'blocked'}",
        "- Visual acceptance:": f"- Visual acceptance: {bool(product.get('visual_acceptance'))}",
    }
    for prefix, replacement in replacements.items():
        for index, line in enumerate(lines):
            if line.startswith(prefix):
                lines[index] = replacement
                break
    label_pass = evidence.get("label_audit_pass")
    final_section = [
        "",
        marker,
        "",
        f"- Final status: {product.get('status') or 'blocked'}",
        f"- Final visual acceptance: {bool(product.get('visual_acceptance'))}",
        f"- No-label audit pass: {'not_run' if label_pass is None else bool(label_pass)}",
        f"- Independent reference preview: {evidence.get('reference_preview_png') or 'missing'}",
        f"- Generated preview: {evidence.get('generated_preview_png') or 'missing'}",
        f"- Side-by-side comparison: {evidence.get('comparison_png') or 'missing'}",
        f"- Comparison ready: {bool(evidence.get('ready'))}",
        f"- Real-data style/data-binding: {(evidence.get('style_data_binding') or {}).get('status', 'blocked')}",
        f"- Reusable asset same-data validation: {(evidence.get('asset_same_data_exact_validation') or {}).get('status', 'not_supplied')}",
        f"- Current-product pixel exactness: {(evidence.get('current_product_pixel_exact') or {}).get('status', 'not_evaluated')}",
        f"- One-to-one exact claim allowed: {bool(evidence.get('one_to_one_exact_match'))}",
        f"- Preview RMS: {evidence.get('preview_rms')} (diagnostic only; not exact evidence)",
        f"- Legacy strict visual match: {bool(evidence.get('strict_visual_match'))}",
        f"- Legacy strict status: {evidence.get('strict_status') or 'blocked_not_one_to_one'}",
        f"- Comparison message: {evidence.get('message') or 'none'}",
    ]
    report_path.write_text("\n".join([*lines, *final_section]).rstrip() + "\n", encoding="utf-8")


def _is_saved_style_asset_preview_product(product: dict[str, object], metadata: dict[str, object]) -> bool:
    if str(product.get("template_format_mode") or "") in {"saved_format_theme", "cached_style_package", "cached_graph_template", "verified_graph_template"}:
        return True
    if str(product.get("origin_processing_method") or "") in {"saved_format_theme_apply", "cached_style_package_graph_template", "fresh_graph_verified_otpu_explicit_xy"}:
        return True
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    template_format_plan = (
        origin_status.get("template_format_plan") if isinstance(origin_status.get("template_format_plan"), dict) else {}
    )
    if str(template_format_plan.get("mode") or "") in {"saved_format_theme", "cached_style_package", "cached_graph_template", "verified_graph_template"}:
        return True
    for candidate in (metadata.get("origin_processing"), origin_status.get("origin_processing")):
        if isinstance(candidate, dict) and str(candidate.get("method") or "") in {"saved_format_theme_apply", "cached_style_package_graph_template", "fresh_graph_verified_otpu_explicit_xy"}:
            return True
    return False


def _style_replay_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_")


def _load_independent_style_replay_evidence(
    project_root: Path,
    report_path: Path | None,
) -> dict[str, dict[str, object]]:
    if report_path is None:
        return {}
    path = report_path if report_path.is_absolute() else project_root / report_path
    if not path.is_file():
        raise FileNotFoundError(f"Style replay report does not exist: {report_path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Style replay report is not valid JSON: {report_path}") from exc
    items = payload.get("items") if isinstance(payload, dict) else None
    if (
        isinstance(payload, dict)
        and str(payload.get("evidence_kind") or "")
        == "origin_fresh_project_same_data_graph_template_validation"
    ):
        items = [{**payload, "_evidence_file": str(path)}]
    if not isinstance(items, list):
        raise ValueError(
            "Style replay report must contain an items list or one accepted graph-template validation record."
        )

    validations: dict[str, dict[str, object]] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        product_key = str(raw.get("product_key") or raw.get("data_type") or "").strip()
        if not product_key:
            raise ValueError("Style replay report item is missing product_key.")
        key = _style_replay_key(product_key)
        if key in validations:
            raise ValueError(f"Duplicate style replay product_key: {product_key}")
        validations[key] = _validate_independent_style_replay_item(
            project_root,
            product_key,
            raw,
        )
    return validations


def _validate_independent_style_replay_item(
    project_root: Path,
    product_key: str,
    item: dict[str, object],
) -> dict[str, object]:
    if (
        str(item.get("evidence_kind") or "")
        == "origin_fresh_project_same_data_graph_template_validation"
    ):
        return _validate_manifest_bound_graph_template_evidence(
            project_root,
            product_key,
            item,
        )
    comparison = item.get("comparison") if isinstance(item.get("comparison"), dict) else {}
    reasons: list[str] = []
    if str(item.get("status") or "") != "matched":
        reasons.append("status is not matched")
    if not bool(item.get("style_asset_validated")):
        reasons.append("style_asset_validated is false")
    if str(item.get("comparison_scope") or "") != "fresh_project_same_data":
        reasons.append("comparison_scope is not fresh_project_same_data")
    if str(item.get("asset_generation_mode") or "") != "new_graph_plus_format_theme":
        reasons.append("asset_generation_mode is not new_graph_plus_format_theme")
    if not bool(item.get("fresh_project_verified")):
        reasons.append("fresh_project_verified is false")
    if not bool(item.get("style_asset_only")):
        reasons.append("style_asset_only is false")
    if not bool(item.get("same_data_verified")):
        reasons.append("same_data_verified is false")
    reference_values_hash = str(item.get("reference_plot_values_sha256") or "").casefold()
    generated_values_hash = str(item.get("generated_plot_values_sha256") or "").casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", reference_values_hash):
        reasons.append("reference plot-values hash is missing or malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", generated_values_hash):
        reasons.append("generated plot-values hash is missing or malformed")
    if reference_values_hash and generated_values_hash and reference_values_hash != generated_values_hash:
        reasons.append("reference and generated plotted X/Y values differ")
    reference_mapping_hash = str(item.get("reference_plot_mapping_sha256") or "").casefold()
    generated_mapping_hash = str(item.get("generated_plot_mapping_sha256") or "").casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", reference_mapping_hash):
        reasons.append("reference plot-mapping hash is missing or malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", generated_mapping_hash):
        reasons.append("generated plot-mapping hash is missing or malformed")
    if reference_mapping_hash and generated_mapping_hash and reference_mapping_hash != generated_mapping_hash:
        reasons.append("reference and generated plot X/Y mappings differ")
    if not bool(item.get("saved_reopened")):
        reasons.append("saved_reopened is false")
    if not bool(item.get("native_tif_600dpi_verified")):
        reasons.append("native_tif_600dpi_verified is false")
    if not bool(item.get("manual_preview_passed")):
        reasons.append("manual_preview_passed is false")
    if not bool(comparison.get("exact_pixel_match")):
        reasons.append("exact_pixel_match is false")
    if comparison.get("same_size") is not True:
        reasons.append("same_size is not true")
    changed_pixels = _to_float(comparison.get("changed_pixels"))
    if changed_pixels is None or abs(changed_pixels) > 1e-12:
        reasons.append("changed_pixels is not zero")
    rms = _to_float(comparison.get("rms"))
    if rms is None or abs(rms) > 1e-12:
        reasons.append("RMS is not zero")

    source_hash = str(item.get("source_opju_sha256") or "").casefold()
    generated_hash = str(item.get("generated_opju_sha256") or "").casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        reasons.append("source OPJU hash is missing or malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", generated_hash):
        reasons.append("generated OPJU hash is missing or malformed")
    if source_hash and generated_hash and source_hash == generated_hash:
        reasons.append("source and generated OPJU hashes are identical")

    asset = resolve_origin_style_asset(project_root, product_key)
    if asset is None:
        reasons.append("current project style asset is missing")
    else:
        recorded_theme_hash = str(item.get("format_theme_sha256") or "").casefold()
        if (
            not asset.format_theme_path.is_file()
            or recorded_theme_hash != file_sha256(asset.format_theme_path)
        ):
            reasons.append("format theme hash does not match the current asset")
        recorded_data_hash = str(item.get("data_snapshot_sha256") or "").casefold()
        if (
            asset.data_snapshot_path is None
            or not asset.data_snapshot_path.is_file()
            or recorded_data_hash != file_sha256(asset.data_snapshot_path)
        ):
            reasons.append("data snapshot hash does not match the current asset")
        if str(item.get("graph_page") or "") != str(asset.graph_page or ""):
            reasons.append("graph page does not match the current asset")

    return {
        "ok": not reasons,
        "reason": "; ".join(reasons) if reasons else "validated",
        "status": str(item.get("status") or ""),
        "comparison_scope": str(item.get("comparison_scope") or ""),
        "asset_generation_mode": str(item.get("asset_generation_mode") or ""),
        "exact_pixel_match": bool(comparison.get("exact_pixel_match")),
        "same_size": comparison.get("same_size") is True,
        "changed_pixels": changed_pixels,
        "rms": rms,
    }


def _validate_manifest_bound_graph_template_evidence(
    project_root: Path,
    product_key: str,
    item: dict[str, object],
) -> dict[str, object]:
    reasons: list[str] = []
    asset_record = item.get("asset") if isinstance(item.get("asset"), dict) else {}
    reference = item.get("reference") if isinstance(item.get("reference"), dict) else {}
    binding = (
        item.get("binding_contract")
        if isinstance(item.get("binding_contract"), dict)
        else {}
    )
    same_data = item.get("same_data") if isinstance(item.get("same_data"), dict) else {}
    style = item.get("style") if isinstance(item.get("style"), dict) else {}
    pixels = item.get("pixels") if isinstance(item.get("pixels"), dict) else {}
    save_reopen = (
        item.get("save_reopen") if isinstance(item.get("save_reopen"), dict) else {}
    )
    tif = item.get("tif_600dpi") if isinstance(item.get("tif_600dpi"), dict) else {}
    if str(item.get("status") or "") != "accepted":
        reasons.append("validation evidence status is not accepted")
    if item.get("manual_preview_passed") is not True:
        reasons.append("manual preview is not accepted")
    if str(asset_record.get("kind") or "") != "otpu":
        reasons.append("validation evidence asset kind is not otpu")
    if reference.get("used_as_product_base") is not False:
        reasons.append("reference OPJU was not explicitly excluded as the product base")
    if reference.get("loaded_during_fresh_plot") is not False:
        reasons.append("reference OPJU was loaded during fresh graph construction")
    if reference.get("source_unchanged") is not True:
        reasons.append("reference OPJU unchanged check failed")
    if same_data.get("verified") is not True:
        reasons.append("same-data verification is false")
    reference_values = str(
        same_data.get("reference_plot_values_sha256") or ""
    ).casefold()
    generated_values = str(
        same_data.get("generated_plot_values_sha256") or ""
    ).casefold()
    reference_mapping = str(
        same_data.get("reference_plot_mapping_sha256") or ""
    ).casefold()
    generated_mapping = str(
        same_data.get("generated_plot_mapping_sha256") or ""
    ).casefold()
    if (
        re.fullmatch(r"[0-9a-f]{64}", reference_values) is None
        or reference_values != generated_values
    ):
        reasons.append("reference and generated plotted values are not hash-identical")
    if (
        re.fullmatch(r"[0-9a-f]{64}", reference_mapping) is None
        or reference_mapping != generated_mapping
    ):
        reasons.append("reference and generated plot mappings are not hash-identical")
    if str(style.get("status") or "") != "pass":
        reasons.append("style conformance did not pass")
    if style.get("axis_title_hard_gate") is not True:
        reasons.append("axis-title hard gate did not pass")
    if pixels.get("exact_pixel_match") is not True:
        reasons.append("exact decoded-pixel match is false")
    if pixels.get("same_size") is not True:
        reasons.append("reference and candidate image sizes differ")
    if _to_float(pixels.get("changed_pixels")) != 0:
        reasons.append("changed-pixel count is not zero")
    if _to_float(pixels.get("rms")) != 0:
        reasons.append("pixel RMS is not zero")
    if save_reopen.get("saved_reopened") is not True:
        reasons.append("candidate OPJU was not saved and reopened")
    if tif.get("verified") is not True or _to_float(tif.get("requested_dpi")) != 600:
        reasons.append("native 600 dpi TIFF validation failed")

    asset = resolve_origin_style_asset(
        project_root,
        product_key,
        require_runtime_validation=True,
    )
    if asset is None:
        reasons.append("current manifest-bound runtime style asset is unavailable")
    else:
        evidence_file = Path(str(item.get("_evidence_file") or ""))
        checks: list[tuple[str, Path | None, str]] = [
            (
                "runtime graph template",
                asset.runtime_asset_path,
                str(asset_record.get("sha256") or "").casefold(),
            ),
            (
                "reference OPJU",
                asset.template_opju_path,
                str(reference.get("sha256") or "").casefold(),
            ),
            (
                "binding contract",
                asset.binding_contract_path,
                str(binding.get("sha256") or "").casefold(),
            ),
            (
                "validation evidence",
                asset.runtime_validation_evidence_path,
                file_sha256(evidence_file) if evidence_file.is_file() else "",
            ),
        ]
        for label, path, recorded_hash in checks:
            if (
                path is None
                or not path.is_file()
                or re.fullmatch(r"[0-9a-f]{64}", recorded_hash) is None
                or file_sha256(path) != recorded_hash
            ):
                reasons.append(f"{label} does not match the current manifest-bound asset")
        if str(asset_record.get("path") or "").replace("\\", "/") != str(
            asset.runtime_asset_path.relative_to(
                project_root / "templates" / "origin_styles"
            )
        ).replace("\\", "/"):
            reasons.append("runtime graph-template path differs from the current asset")
        if str(reference.get("graph_page") or "") != str(asset.graph_page or ""):
            reasons.append("reference graph page differs from the current asset")

    return {
        "ok": not reasons,
        "reason": "; ".join(reasons) if reasons else "validated",
        "status": str(item.get("status") or ""),
        "comparison_scope": "fresh_project_same_data",
        "asset_generation_mode": "new_graph_plus_verified_otpu",
        "exact_pixel_match": pixels.get("exact_pixel_match") is True,
        "same_size": pixels.get("same_size") is True,
        "changed_pixels": _to_float(pixels.get("changed_pixels")),
        "rms": _to_float(pixels.get("rms")),
    }


def _is_embedded_template_snapshot_preview_product(product: dict[str, object], metadata: dict[str, object]) -> bool:
    if str(product.get("template_format_mode") or "") == "embedded_template_snapshot":
        return True
    if str(product.get("origin_processing_method") or "") == "embedded_template_snapshot_graph":
        return True
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    template_format_plan = (
        origin_status.get("template_format_plan") if isinstance(origin_status.get("template_format_plan"), dict) else {}
    )
    if str(template_format_plan.get("mode") or "") == "embedded_template_snapshot":
        return True
    for candidate in (metadata.get("origin_processing"), origin_status.get("origin_processing")):
        if isinstance(candidate, dict) and str(candidate.get("method") or "") == "embedded_template_snapshot_graph":
            return True
    return False


def _is_xrd_clean_rebuild_preview_product(product: dict[str, object], metadata: dict[str, object]) -> bool:
    if _metadata_product_key(product, metadata) != "XRD":
        return False
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    replacement = origin_status.get("template_base_replacement") if isinstance(origin_status.get("template_base_replacement"), dict) else {}
    if bool(replacement.get("xrd_clean_graph_rebuild")):
        return True
    for candidate in (metadata.get("template_base_replacement"), product.get("template_base_replacement")):
        if isinstance(candidate, dict) and bool(candidate.get("xrd_clean_graph_rebuild")):
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


def _read_template_product_metadata(product: dict[str, object], run_root: Path | None = None) -> dict[str, object]:
    metadata_path = _resolve_run_relative_artifact(run_root, product.get("metadata")) if run_root else Path(str(product.get("metadata") or ""))
    if not metadata_path.is_file():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_run_relative_artifact(run_root: Path | None, value: object) -> Path:
    text = str(value or "")
    if not text:
        return (run_root / ".missing_artifact") if run_root is not None else Path(".missing_artifact")
    path = Path(text)
    if path.is_absolute() or run_root is None:
        return path
    return run_root / path


def _template_plot_count(product: dict[str, object], metadata: dict[str, object]) -> int:
    extra = metadata.get("extra") if isinstance(metadata.get("extra"), dict) else {}
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
    text_only_legend: bool = False,
) -> list[str]:
    """Compatibility wrapper for the former combined visual gate.

    New code must consume style/data-binding blockers and preview-review
    signals separately.  Keeping this wrapper avoids breaking older callers.
    """

    reasons = _template_style_data_binding_reasons(
        ready=ready,
        plot_count_delta=plot_count_delta,
        style_match_ratio=style_match_ratio,
        text_only_legend=text_only_legend,
    )
    reasons.extend(
        _template_preview_review_reasons(
            ready=ready,
            preview_rms=preview_rms,
        )
    )
    return reasons


def _template_style_data_binding_reasons(
    *,
    ready: bool,
    plot_count_delta: int,
    style_match_ratio: float | None,
    text_only_legend: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if not ready:
        reasons.append("template/generated preview comparison is not ready")
    text_only_legend_match = bool(text_only_legend and plot_count_delta == 0 and style_match_ratio is not None and style_match_ratio >= 0.88)
    if plot_count_delta != 0:
        reasons.append(f"plot count differs from template by {plot_count_delta}")
    if style_match_ratio is None:
        reasons.append("style match ratio is unavailable")
    elif style_match_ratio < 0.90 and not text_only_legend_match:
        reasons.append(f"style match ratio {style_match_ratio:.2f} is below 0.90")
    return reasons


def _template_preview_review_reasons(
    *,
    ready: bool,
    preview_rms: float | None,
    reference_size: str = "",
    generated_size: str = "",
) -> list[str]:
    """Return manual-review signals that cannot establish exactness."""

    if not ready:
        return []
    reasons: list[str] = []
    if preview_rms is None:
        reasons.append("preview RMS is unavailable")
    elif preview_rms > 35.0:
        reasons.append(f"preview RMS {preview_rms:.2f} is above 35.00")
    if reference_size and generated_size and reference_size != generated_size:
        reasons.append(
            f"preview sizes differ ({reference_size} vs {generated_size}); manual review is required"
        )
    return reasons


def _embedded_template_snapshot_strict_visual_reasons(
    product: dict[str, object],
    metadata: dict[str, object],
    *,
    ready: bool,
    plot_count_delta: int,
    style_match_ratio: float | None,
    preview_rms: float | None,
    allowed_methods: set[str] | None = None,
    mode_label: str = "embedded template snapshot",
) -> list[str]:
    reasons = _template_style_data_binding_reasons(
        ready=ready,
        plot_count_delta=plot_count_delta,
        style_match_ratio=style_match_ratio,
        text_only_legend=_template_text_only_legend_policy(product, metadata),
    )
    if not ready:
        generic_not_ready = "template/generated preview comparison is not ready"
        if generic_not_ready in reasons:
            reasons.remove(generic_not_ready)
        reasons.append(f"{mode_label} template/generated preview artifact comparison is not ready")
    for field in ("has_opju", "has_tif", "has_png", "has_reference_preview", "has_processed_data", "has_metadata", "has_report"):
        if field in product and not bool(product.get(field)):
            reasons.append(f"{field} is false")
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    origin_processing = metadata.get("origin_processing") if isinstance(metadata.get("origin_processing"), dict) else {}
    status_processing = origin_status.get("origin_processing") if isinstance(origin_status.get("origin_processing"), dict) else {}
    processing = origin_processing if origin_processing else status_processing
    allowed = allowed_methods or {"embedded_template_snapshot_graph"}
    if not bool(processing.get("applied")) or str(processing.get("method") or "") not in allowed:
        reasons.append(f"{mode_label} Origin processing was not read back")
    if not _template_text_only_legend_policy(product, metadata):
        reasons.append("legend policy was not read back")
    strict_readback = metadata.get("strict_style_readback") if isinstance(metadata.get("strict_style_readback"), dict) else {}
    if not strict_readback:
        strict_readback = origin_status.get("strict_style_readback") if isinstance(origin_status.get("strict_style_readback"), dict) else {}
    axis_title_bold_required = _export_exemplar_axis_title_bold_required(origin_status)
    relevant = _relevant_strict_readback_values(
        strict_readback,
        template_base_mode=True,
        axis_title_bold_required=axis_title_bold_required,
    )
    if not relevant:
        reasons.append("strict style readback is unavailable")
    else:
        failed = [key for key, value in relevant.items() if not bool(value)]
        if failed:
            reasons.append("strict style readback failed: " + ", ".join(failed))
    return reasons


def _template_text_only_legend_policy(product: dict[str, object], metadata: dict[str, object]) -> bool:
    candidates: list[object] = []
    origin_processing = product.get("origin_processing")
    if isinstance(origin_processing, dict):
        candidates.append(origin_processing)
    metadata_processing = metadata.get("origin_processing")
    if isinstance(metadata_processing, dict):
        candidates.append(metadata_processing)
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    status_processing = origin_status.get("origin_processing") if isinstance(origin_status.get("origin_processing"), dict) else {}
    if isinstance(status_processing, dict):
        candidates.append(status_processing)
    for candidate in candidates:
        policy = candidate.get("legend_policy") if isinstance(candidate, dict) else None
        if not isinstance(policy, dict):
            continue
        if bool(policy.get("line_samples_removed")):
            return True
        if (
            _metadata_product_key(product, metadata) == "XRD"
            and str(policy.get("method") or "") == "template_line_sample_legend_preserved"
            and bool(policy.get("xrd_standard_card_reference_sticks_present"))
        ):
            return True
    return False


def _metadata_product_key(product: dict[str, object], metadata: dict[str, object]) -> str:
    for source in (product, metadata):
        for key in ("type", "product_key", "data_type"):
            value = source.get(key) if isinstance(source, dict) else None
            if value:
                return str(value)
    origin_status = metadata.get("origin_status") if isinstance(metadata.get("origin_status"), dict) else {}
    plan = origin_status.get("template_format_plan") if isinstance(origin_status.get("template_format_plan"), dict) else {}
    return str(plan.get("data_type") or "")


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
    draw.text((12, 10), "Reference format preview", fill="black", font=font)
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
    skipped: list[dict[str, object]],
    *,
    target_types: tuple[str, ...] = TEMPLATE_TARGET_TYPES,
) -> None:
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "template_rebuild_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_root.name,
                "products": products,
                "failures": failures,
                "skipped": skipped,
                "label_audit": label_audit,
                "template_preview_audit": template_preview_audit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_template_final_summary(reports / "final_summary.md", run_root, products, failures, label_audit, skipped, relative=True)
    _write_template_manual_review(reports / "manual_review_checklist.md", run_root, products, relative=True)
    _write_template_per_type_status(reports / "per_type_status.csv", run_root, products, relative=True)
    _write_template_selection_summary(reports / "template_selection_summary.md", selections, target_types=target_types)
    _write_template_visual_acceptance_summary(reports / "visual_acceptance_summary.md", run_root, products, relative=True)
    _write_template_conformance_summary(reports / "exemplar_conformance_summary.md", products)
    _write_template_root_cause_audit(reports / "template_root_cause_audit.md")
    _write_template_visual_contract(reports / "template_visual_acceptance_contract.md")
    _write_template_root_cause_fix_summary(reports / "template_root_cause_fix_summary.md")


def _write_template_final_summary(
    path: Path,
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    label_audit: dict[str, object],
    skipped: list[dict[str, object]],
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
        f"- Product visible-label audit: {'pass' if _label_audit_passes(label_audit) else 'fail'}",
        f"- Reference-vs-generated preview comparison: {sum(1 for item in products if item.get('template_preview_comparison_ready'))}/{len(products)} ready",
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
        f"- Reference PNG preview: {reference_png}",
        f"- External reference OPJU: {product.get('external_reference_opju', '') or 'not selected'}",
        f"- External reference graph: {product.get('external_reference_graph', '')}",
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
    for item in skipped:
        label = item.get("type", item.get("data_type", "unknown"))
        reason = item.get("reason", "")
        example = item.get("example", "")
        suffix = f" ({example})" if example else ""
        lines.append(f"- {label}: {reason}{suffix}")
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


def _write_template_selection_summary(
    path: Path,
    selections: dict[str, TemplateSelection],
    *,
    target_types: tuple[str, ...] = TEMPLATE_TARGET_TYPES,
) -> None:
    lines = ["# Template selection summary", "", "| Type | Status | Candidate Count | Selected Template | Graph | Reason |", "|---|---:|---:|---|---|---|"]
    for product_key in target_types:
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
    *,
    target_types: tuple[str, ...] = TEMPLATE_TARGET_TYPES,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Template discovery and selection", "", f"- F-drive template root scanned: {_template_display_path(f_drive_root)}", ""]
    for product_key in target_types:
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
                hits.append({"path": _relative_to_run(run_root, path), "location": "filename", "label": label})
        if path.suffix.casefold() not in {".md", ".csv", ".txt", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label in FORBIDDEN_LABELS:
                if label.casefold() not in line.casefold():
                    continue
                record = {
                    "path": _relative_to_run(run_root, path),
                    "line": line_number,
                    "label": label,
                    "text": scrub_output_text(line.strip(), output_root=run_root),
                }
                if ":\\" in line or ":/" in line:
                    path_only_hits.append(record)
                else:
                    hits.append(record)
    audit = {
        "hit_count": len(hits),
        "hits": hits,
        "path_only_hits": path_only_hits,
        "path_only_hit_count": len(path_only_hits),
        "pass": len(hits) == 0 and len(path_only_hits) == 0,
    }
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "product_no_label_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Product visible-label audit",
        "",
        f"- Product-visible hit count: {audit['hit_count']}",
        f"- Path-only hit count: {len(path_only_hits)}",
        f"- Result: {'pass' if audit['pass'] else 'fail'}",
        "",
        "## Product-visible hits",
    ]
    lines.extend(["- none"] if not hits else [f"- {hit}" for hit in hits])
    lines.extend(["", "## Absolute-path hits", *(["- none"] if not path_only_hits else [f"- {hit}" for hit in path_only_hits])])
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
    if "阻抗" in text:
        return "EIS"
    if "拉曼" in text:
        return "Raman"
    if "固体紫外" in text or "紫外" in text:
        return "UV-vis DRS / Tauc"
    if "激发" in text or "发射" in text:
        return "PL"
    if "光电流" in text:
        return "photocurrent"
    if "红外" in text:
        return "FTIR"
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


def _is_f_drive_xps_path(path: Path) -> bool:
    return any(part.casefold() == "xps" for part in path.parts)


def _has_in_situ_token(text: str) -> bool:
    compact = text.replace("_", "").replace("-", "").replace(" ", "")
    if "非原位" in text:
        return False
    if "原位" in text:
        return True
    if "noninsitu" in compact or "non in situ" in text:
        return False
    return "鍘熶綅" in text or "insitu" in compact or "insitu" in text or "in situ" in text


def _template_path_score(product_key: str, path: Path) -> int:
    text = str(path).casefold()
    score = 10
    for token in ("bobc", "cwo+bobc", "cwo", "bc"):
        if token in text:
            score += 5
    for token in ("负数", "没有明显峰", "老版本", "旧版本"):
        if token in text:
            score -= 25
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


def _cleanup_compact_transient_dirs(run_root: Path) -> None:
    for name in ("template_scan_copies", "template_reference_scan_copies"):
        path = run_root / name
        if path.exists() and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _ensure_template_type_dirs(type_root: Path, *, compact: bool = False) -> None:
    if compact:
        type_root.mkdir(parents=True, exist_ok=True)
        return
    for name in (
        "input_copies",
        "format_assets",
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


def _candidate_status_from_snapshot_payload(snapshot: dict[str, object]) -> str:
    status = str(snapshot.get("status") or "")
    if status != "extracted":
        return status or "load_failed"
    if int(snapshot.get("layer_count") or 0) <= 0 or int(snapshot.get("plot_count") or 0) <= 0 or not snapshot.get("graph_page"):
        return "data_only"
    return "extracted"


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
    product_keys = tuple(dict.fromkeys(candidate.product_key for candidate in candidates))
    for product_key in product_keys:
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
        "path": _template_display_path(candidate.path),
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
