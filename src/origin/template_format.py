from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.output_sanitizer import render_output_path


GRAPH_THEME_SUFFIXES = {".oth"}
GRAPH_TEMPLATE_SUFFIXES = {".otp", ".otpu", ".ogg"}
STYLE_PACKAGE_SUFFIXES = GRAPH_THEME_SUFFIXES | GRAPH_TEMPLATE_SUFFIXES


@dataclass(frozen=True)
class TemplateFormatPlan:
    data_type: str
    status: str
    mode: str
    source_opju: Path | None = None
    graph_page: str = ""
    style_package_path: Path | None = None
    reference_preview_png: Path | None = None
    product_preview_png: Path | None = None
    can_execute: bool = False
    one_to_one_claim_allowed: bool = False
    plot_intent: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_type": self.data_type,
            "status": self.status,
            "mode": self.mode,
            "source_opju": render_output_path(self.source_opju) if self.source_opju else "",
            "graph_page": self.graph_page,
            "style_package_path": render_output_path(self.style_package_path) if self.style_package_path else "",
            "reference_preview_png": render_output_path(self.reference_preview_png) if self.reference_preview_png else "",
            "product_preview_png": render_output_path(self.product_preview_png) if self.product_preview_png else "",
            "can_execute": self.can_execute,
            "one_to_one_claim_allowed": self.one_to_one_claim_allowed,
            "plot_intent": dict(self.plot_intent),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class TemplateDatasetUpdates:
    status: str
    workbook_columns: dict[str, dict[int, list[float]]]
    visual_plot_count: int
    unique_dataset_count: int
    missing_series_count: int = 0
    duplicate_dataset_references: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "workbook_columns": {
                book: {str(col): list(values) for col, values in columns.items()}
                for book, columns in self.workbook_columns.items()
            },
            "visual_plot_count": self.visual_plot_count,
            "unique_dataset_count": self.unique_dataset_count,
            "missing_series_count": self.missing_series_count,
            "duplicate_dataset_references": dict(self.duplicate_dataset_references),
            "warnings": list(self.warnings),
        }


def build_template_format_plan(
    data_type: str,
    *,
    opju_path: str | Path | None = None,
    graph_page: str = "",
    style_package_path: str | Path | None = None,
    reference_preview_png: str | Path | None = None,
    product_preview_png: str | Path | None = None,
    curve_line_width_pt: float = 3.0,
    axis_title_bold: bool = True,
) -> TemplateFormatPlan:
    source_opju = Path(opju_path) if opju_path is not None and str(opju_path).strip() else None
    style_package = Path(style_package_path) if style_package_path is not None and str(style_package_path).strip() else None
    intent = {
        "curve_line_width_pt": float(curve_line_width_pt),
        "axis_title_bold": bool(axis_title_bold),
        "reference_preview_required": True,
        "product_preview_required": True,
        "template_image_comparison_required": True,
        "origin_template_or_format_source_required": True,
    }
    warnings: list[str] = []
    if style_package is not None and _is_saved_format_theme(style_package):
        if source_opju is None or not source_opju.is_file():
            warnings.append("OPJU exemplar missing; using a project-local saved format theme instead of a live template project.")
        else:
            warnings.append("Project-local saved format theme selected; OPJU exemplar is not used as the product base.")
        return TemplateFormatPlan(
            data_type=data_type,
            status="ready",
            mode="saved_format_theme",
            source_opju=source_opju,
            graph_page=graph_page,
            style_package_path=style_package,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=True,
            one_to_one_claim_allowed=False,
            plot_intent=intent,
            warnings=tuple(warnings),
        )
    if style_package is not None and _is_graph_template_package(style_package):
        warnings.append("Saved format theme missing; using graph-template compatibility fallback.")
        return TemplateFormatPlan(
            data_type=data_type,
            status="ready",
            mode="cached_graph_template",
            source_opju=source_opju,
            graph_page=graph_page,
            style_package_path=style_package,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=True,
            one_to_one_claim_allowed=False,
            plot_intent=intent,
            warnings=tuple(warnings),
        )
    if source_opju is not None and source_opju.is_file() and source_opju.suffix.casefold() in {".opju", ".opj"}:
        warnings.append("Saved style package missing; using OPJU template base compatibility path.")
        return TemplateFormatPlan(
            data_type=data_type,
            status="ready",
            mode="opju_template_base",
            source_opju=source_opju,
            graph_page=graph_page,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=True,
            one_to_one_claim_allowed=False,
            plot_intent=intent,
            warnings=tuple(warnings),
        )
    style_package = style_package or (
        source_opju if source_opju is not None and source_opju.is_file() and _is_supported_style_package(source_opju) else None
    )
    if style_package is not None and _is_saved_format_theme(style_package):
        warnings.append("OPJU exemplar missing; using a saved format theme instead of live template project.")
        return TemplateFormatPlan(
            data_type=data_type,
            status="ready",
            mode="saved_format_theme",
            source_opju=source_opju,
            graph_page=graph_page,
            style_package_path=style_package,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=True,
            one_to_one_claim_allowed=False,
            plot_intent=intent,
            warnings=tuple(warnings),
        )
    if style_package is not None and _is_graph_template_package(style_package):
        warnings.append("Saved format theme missing; using graph-template compatibility fallback.")
        return TemplateFormatPlan(
            data_type=data_type,
            status="ready",
            mode="cached_graph_template",
            source_opju=source_opju,
            graph_page=graph_page,
            style_package_path=style_package,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=True,
            one_to_one_claim_allowed=False,
            plot_intent=intent,
            warnings=tuple(warnings),
        )
    warnings.append("No OPJU exemplar or saved style package is available; one-to-one plotting must be blocked.")
    return TemplateFormatPlan(
        data_type=data_type,
        status="blocked",
        mode="missing_template_source",
        source_opju=source_opju,
        graph_page=graph_page,
        style_package_path=style_package,
        reference_preview_png=_optional_path(reference_preview_png),
        product_preview_png=_optional_path(product_preview_png),
        can_execute=False,
        one_to_one_claim_allowed=False,
        plot_intent=intent,
        warnings=tuple(warnings),
    )


def parse_origin_dataset_name(name: str) -> tuple[str, int] | None:
    match = re.match(r"^(.+)_([A-Za-z]+)$", str(name).strip())
    if not match:
        return None
    book_name = match.group(1)
    col_token = match.group(2).upper()
    if not book_name or not col_token:
        return None
    col_index = 0
    for char in col_token:
        if not ("A" <= char <= "Z"):
            return None
        col_index = col_index * 26 + (ord(char) - ord("A") + 1)
    return book_name, col_index - 1


def build_template_dataset_updates(
    plot_dataset_names: list[str] | tuple[str, ...],
    headers: list[str] | tuple[str, ...],
    rows: list[list[object]] | tuple[tuple[object, ...], ...],
    *,
    allow_partial: bool = False,
) -> TemplateDatasetUpdates:
    parsed: list[tuple[str, str, int]] = []
    counts: dict[str, int] = {}
    warnings: list[str] = []
    for name in plot_dataset_names:
        dataset = str(name).strip()
        counts[dataset] = counts.get(dataset, 0) + 1
        parsed_name = parse_origin_dataset_name(dataset)
        if parsed_name is None:
            warnings.append(f"Ignored unparsable Origin dataset name: {dataset}")
            continue
        book_name, col_index = parsed_name
        parsed.append((dataset, book_name, col_index))

    unique: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for dataset, book_name, col_index in parsed:
        if dataset in seen:
            continue
        seen.add(dataset)
        unique.append((dataset, book_name, col_index))

    duplicate_refs = {dataset: count for dataset, count in counts.items() if count > 1 and parse_origin_dataset_name(dataset) is not None}
    data_series_count = max(len(headers) - 1, 0)
    missing = max(len(unique) - data_series_count, 0)
    if missing:
        warnings.append(
            f"Template requires {len(unique)} unique Y datasets but processed data has {data_series_count}."
        )

    workbook_columns: dict[str, dict[int, list[float]]] = {}
    x_values = _column_from_rows(rows, 0)
    for series_index, (_dataset, book_name, target_y_col) in enumerate(unique, start=1):
        if series_index > data_series_count and not allow_partial:
            break
        book_updates = workbook_columns.setdefault(book_name, {})
        book_updates[0] = x_values
        if series_index > data_series_count:
            book_updates[target_y_col] = [math.nan for _row in rows]
        else:
            book_updates[target_y_col] = _column_from_rows(rows, series_index)

    return TemplateDatasetUpdates(
        status="partial" if missing and allow_partial else ("blocked" if missing else "ready"),
        workbook_columns=workbook_columns,
        visual_plot_count=len(parsed),
        unique_dataset_count=len(unique),
        missing_series_count=missing,
        duplicate_dataset_references=duplicate_refs,
        warnings=tuple(warnings),
    )


def _column_from_rows(rows: list[list[object]] | tuple[tuple[object, ...], ...], index: int) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row[index] if index < len(row) else math.nan
        values.append(_to_float(value))
    return values


def _to_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _is_supported_style_package(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in STYLE_PACKAGE_SUFFIXES


def _is_saved_format_theme(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in GRAPH_THEME_SUFFIXES


def _is_graph_template_package(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in GRAPH_TEMPLATE_SUFFIXES


def _optional_path(path: str | Path | None) -> Path | None:
    if path is None or not str(path).strip():
        return None
    return Path(path)
