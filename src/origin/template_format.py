from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.output_sanitizer import render_output_path


GRAPH_THEME_SUFFIXES = {".oth"}
GRAPH_TEMPLATE_SUFFIXES = {".otp", ".otpu", ".ogg"}


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


@dataclass(frozen=True)
class OriginDatasetReference:
    """Origin worksheet dataset identity, including the sheet creation index."""

    dataset_name: str
    book_name: str
    column_index: int
    sheet_index: int = 1

    @property
    def sheet_reference(self) -> str:
        return str(self.sheet_index)


@dataclass(frozen=True)
class TemplateXYDatasetUpdates:
    """Exact plot-to-worksheet replacement plan using explicit X/Y datasets."""

    status: str
    worksheet_columns: dict[str, dict[int, dict[int, list[float]]]]
    worksheet_ranges: tuple[dict[str, object], ...]
    visual_plot_count: int
    unique_plot_pair_count: int
    source_series_count: int
    missing_series_count: int
    unused_source_series_count: int
    duplicate_plot_pair_references: dict[str, int] = field(default_factory=dict)
    mappings: tuple[dict[str, object], ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        targets = [
            {
                "book_name": book_name,
                "sheet_index": sheet_index,
                "column_indices": sorted(columns),
            }
            for book_name, sheets in self.worksheet_columns.items()
            for sheet_index, columns in sheets.items()
        ]
        return {
            "status": self.status,
            "visual_plot_count": self.visual_plot_count,
            "unique_plot_pair_count": self.unique_plot_pair_count,
            "source_series_count": self.source_series_count,
            "missing_series_count": self.missing_series_count,
            "unused_source_series_count": self.unused_source_series_count,
            "duplicate_plot_pair_references": dict(self.duplicate_plot_pair_references),
            "worksheet_column_targets": targets,
            "worksheet_range_targets": [
                {
                    key: value
                    for key, value in item.items()
                    if key != "values"
                }
                for item in self.worksheet_ranges
            ],
            "mappings": [dict(item) for item in self.mappings],
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
    embedded_snapshot_available: bool = False,
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
        source_opju if source_opju is not None and source_opju.is_file() and _is_saved_format_theme(source_opju) else None
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
    graph_template = _graph_template_source(source_opju, style_package)
    if graph_template is not None:
        warnings.append(
            f"{graph_template.suffix.casefold()} graph templates are retained only as unreviewed harvest assets "
            "and cannot be used as a runtime style source; supply an accepted .oth format theme or OPJU/OPJ exemplar."
        )
        return TemplateFormatPlan(
            data_type=data_type,
            status="blocked",
            mode="untrusted_graph_template",
            source_opju=source_opju,
            graph_page=graph_page,
            style_package_path=graph_template,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=False,
            one_to_one_claim_allowed=False,
            plot_intent=intent,
            warnings=tuple(warnings),
        )
    if embedded_snapshot_available:
        warnings.append("No live OPJU template is required; using the reviewed embedded Origin template snapshot.")
        return TemplateFormatPlan(
            data_type=data_type,
            status="ready",
            mode="embedded_template_snapshot",
            source_opju=source_opju,
            graph_page=graph_page,
            style_package_path=style_package,
            reference_preview_png=_optional_path(reference_preview_png),
            product_preview_png=_optional_path(product_preview_png),
            can_execute=True,
            one_to_one_claim_allowed=False,
            plot_intent={**intent, "origin_template_or_format_source_required": False},
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
    reference = parse_origin_dataset_reference(name)
    if reference is None:
        return None
    return reference.book_name, reference.column_index


def parse_origin_dataset_reference(name: str) -> OriginDatasetReference | None:
    dataset_name = str(name).strip()
    match = re.match(r"^(.+)_([A-Za-z]+)(?:@([1-9]\d*))?$", dataset_name)
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
    sheet_index = int(match.group(3) or 1)
    return OriginDatasetReference(
        dataset_name=dataset_name,
        book_name=book_name,
        column_index=col_index - 1,
        sheet_index=sheet_index,
    )


def build_template_dataset_updates(
    plot_dataset_names: list[str] | tuple[str, ...],
    headers: list[str] | tuple[str, ...],
    rows: list[list[object]] | tuple[tuple[object, ...], ...],
    *,
    allow_partial: bool = False,
    paired_xy_columns: bool = False,
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
        target_x_col = max(target_y_col - 1, 0) if paired_xy_columns else 0
        book_updates[target_x_col] = x_values
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


def build_template_xy_dataset_updates(
    plot_mappings: list[dict[str, object]] | tuple[dict[str, object], ...],
    headers: list[str] | tuple[str, ...],
    rows: list[list[object]] | tuple[tuple[object, ...], ...],
    source_pairs: list[tuple[int, int]] | tuple[tuple[int, int], ...],
    *,
    require_exact_series_count: bool = True,
    require_explicit_source_bindings: bool = False,
) -> TemplateXYDatasetUpdates:
    """Map processed series to the actual X/Y datasets used by an Origin graph.

    Source-pair indices are zero based.  Legacy callers may still use the
    deterministic target-column ordering.  Strict callers must provide a
    one-based ``source_series_index`` on every plot mapping; those bindings are
    then authoritative and target ordering is never used to infer semantics.
    """

    warnings: list[str] = []
    parsed_rows: list[
        tuple[
            int,
            OriginDatasetReference,
            OriginDatasetReference,
            str,
            int,
            int,
            int | None,
            str,
        ]
    ] = []
    pair_counts: dict[str, int] = {}
    for first_index, raw in enumerate(plot_mappings):
        x_dataset = str(raw.get("x_dataset") or "").strip()
        y_dataset = str(raw.get("y_dataset") or "").strip()
        x_reference = parse_origin_dataset_reference(x_dataset)
        y_reference = parse_origin_dataset_reference(y_dataset)
        try:
            row_from = int(raw.get("row_from"))
            row_to = int(raw.get("row_to"))
        except (TypeError, ValueError):
            row_from = 0
            row_to = -1
        if x_reference is None or y_reference is None or row_from < 1 or row_to < row_from:
            warnings.append(
                f"Plot mapping {first_index + 1} has an invalid X/Y dataset or plotted row range: "
                f"{x_dataset or '<missing>'} -> {y_dataset or '<missing>'}, rows {row_from}:{row_to}."
            )
            continue
        raw_source_series_index = raw.get("source_series_index")
        source_series_index: int | None = None
        if raw_source_series_index is not None:
            try:
                source_series_index = int(raw_source_series_index)
            except (TypeError, ValueError):
                source_series_index = None
        semantic_role = str(raw.get("semantic_role") or "").strip()
        if require_explicit_source_bindings and (
            source_series_index is None or source_series_index < 1 or not semantic_role
        ):
            warnings.append(
                f"Plot mapping {first_index + 1} lacks a positive source_series_index "
                "or semantic_role required by the explicit binding contract."
            )
        pair_key = f"{x_dataset}->{y_dataset}"
        pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
        parsed_rows.append(
            (
                first_index,
                x_reference,
                y_reference,
                pair_key,
                row_from,
                row_to,
                source_series_index,
                semantic_role,
            )
        )

    unique_by_pair: dict[
        str,
        tuple[
            int,
            OriginDatasetReference,
            OriginDatasetReference,
            str,
            int,
            int,
            int | None,
            str,
        ],
    ] = {}
    pair_ranges: dict[str, set[tuple[int, int]]] = {}
    pair_source_bindings: dict[str, set[tuple[int | None, str]]] = {}
    group_order: dict[tuple[str, int], int] = {}
    for item in parsed_rows:
        (
            first_index,
            _x_reference,
            y_reference,
            pair_key,
            row_from,
            row_to,
            source_series_index,
            semantic_role,
        ) = item
        unique_by_pair.setdefault(pair_key, item)
        pair_ranges.setdefault(pair_key, set()).add((row_from, row_to))
        pair_source_bindings.setdefault(pair_key, set()).add(
            (source_series_index, semantic_role.casefold())
        )
        group_key = (y_reference.book_name, y_reference.sheet_index)
        group_order.setdefault(group_key, first_index)
    if require_explicit_source_bindings:
        unique_targets = list(unique_by_pair.values())
    else:
        unique_targets = sorted(
            unique_by_pair.values(),
            key=lambda item: (
                group_order[(item[2].book_name, item[2].sheet_index)],
                item[2].column_index,
                item[1].column_index,
                item[0],
            ),
        )
    inconsistent_pair_ranges = {
        pair_key: sorted(ranges)
        for pair_key, ranges in pair_ranges.items()
        if len(ranges) > 1
    }
    for pair_key, ranges in inconsistent_pair_ranges.items():
        warnings.append(f"Repeated template plot pair {pair_key} has inconsistent row ranges: {ranges}.")
    inconsistent_source_bindings = {
        pair_key: sorted(bindings, key=lambda item: (item[0] or 0, item[1]))
        for pair_key, bindings in pair_source_bindings.items()
        if len(bindings) > 1
    }
    for pair_key, bindings in inconsistent_source_bindings.items():
        warnings.append(
            f"Repeated template plot pair {pair_key} has inconsistent explicit source bindings: "
            f"{bindings}."
        )

    valid_source_pairs: list[tuple[int, int]] = []
    for source_index, pair in enumerate(source_pairs, start=1):
        try:
            x_index, y_index = int(pair[0]), int(pair[1])
        except (TypeError, ValueError, IndexError):
            warnings.append(f"Processed source series {source_index} has an invalid X/Y pair.")
            continue
        if x_index < 0 or y_index < 0 or x_index >= len(headers) or y_index >= len(headers):
            warnings.append(
                f"Processed source series {source_index} references unavailable columns "
                f"({x_index}, {y_index}) for {len(headers)} headers."
            )
            continue
        valid_source_pairs.append((x_index, y_index))

    explicit_source_indices = {
        int(item[6])
        for item in unique_targets
        if item[6] is not None and int(item[6]) > 0
    }
    if require_explicit_source_bindings:
        unavailable_explicit_indices = {
            index for index in explicit_source_indices if index > len(valid_source_pairs)
        }
        missing_binding_count = sum(item[6] is None or int(item[6]) < 1 for item in unique_targets)
        missing = len(unavailable_explicit_indices) + missing_binding_count
        unused = max(len(valid_source_pairs) - len(explicit_source_indices), 0)
    else:
        unavailable_explicit_indices = set()
        missing = max(len(unique_targets) - len(valid_source_pairs), 0)
        unused = max(len(valid_source_pairs) - len(unique_targets), 0)
    if missing:
        warnings.append(
            f"Template requires {len(unique_targets)} unique X/Y dataset pairs but processed data has "
            f"{len(valid_source_pairs)} series."
        )
    if unused:
        warnings.append(
            f"Processed data has {len(valid_source_pairs)} series but the template exposes only "
            f"{len(unique_targets)} unique X/Y dataset pairs."
        )
    if len(parsed_rows) != len(plot_mappings):
        warnings.append("Not every template plot has a readable explicit X/Y dataset mapping.")

    target_source_pairs: list[
        tuple[
            tuple[
                int,
                OriginDatasetReference,
                OriginDatasetReference,
                str,
                int,
                int,
                int | None,
                str,
            ],
            tuple[int, int],
            int,
        ]
    ] = []
    if require_explicit_source_bindings:
        for target in unique_targets:
            source_series_index = target[6]
            if (
                source_series_index is None
                or source_series_index < 1
                or source_series_index > len(valid_source_pairs)
            ):
                continue
            target_source_pairs.append(
                (target, valid_source_pairs[source_series_index - 1], source_series_index)
            )
    else:
        target_source_pairs = [
            (target, source_pair, target_index)
            for target_index, (target, source_pair) in enumerate(
                zip(unique_targets, valid_source_pairs),
                start=1,
            )
        ]

    worksheet_columns: dict[str, dict[int, dict[int, list[float]]]] = {}
    range_by_dataset: dict[str, dict[str, object]] = {}
    mappings: list[dict[str, object]] = []
    collision = False
    row_count_mismatch = False
    for target_index, (target, source_pair, source_series_index) in enumerate(
        target_source_pairs,
        start=1,
    ):
        (
            _first_index,
            x_reference,
            y_reference,
            pair_key,
            row_from,
            row_to,
            _contract_source_series_index,
            semantic_role,
        ) = target
        source_x_index, source_y_index = source_pair
        x_values = _column_from_rows(rows, source_x_index)
        y_values = _column_from_rows(rows, source_y_index)
        expected_row_count = row_to - row_from + 1
        x_values, y_values, source_rows_fit = _fit_xy_to_target_row_count(
            x_values,
            y_values,
            expected_row_count,
        )
        if not source_rows_fit:
            row_count_mismatch = True
            warnings.append(
                f"Target pair {pair_key} plots rows {row_from}:{row_to} ({expected_row_count} rows) "
                f"but source series {source_series_index} cannot be fitted without dropping nonmissing plotted values."
            )
        for reference, values, role in (
            (x_reference, x_values, "x"),
            (y_reference, y_values, "y"),
        ):
            columns = worksheet_columns.setdefault(reference.book_name, {}).setdefault(
                reference.sheet_index,
                {},
            )
            existing = columns.get(reference.column_index)
            if existing is not None and not _numeric_columns_equal(existing, values):
                collision = True
                warnings.append(
                    f"Target dataset {reference.dataset_name} receives conflicting {role.upper()} data."
                )
            else:
                columns[reference.column_index] = values
            existing_range = range_by_dataset.get(reference.dataset_name)
            candidate_range = {
                "book_name": reference.book_name,
                "sheet_index": reference.sheet_index,
                "sheet_reference": reference.sheet_reference,
                "column_index": reference.column_index,
                "dataset_name": reference.dataset_name,
                "row_from": row_from,
                "row_to": row_to,
                "values": values,
            }
            if existing_range is None:
                range_by_dataset[reference.dataset_name] = candidate_range
            elif (
                existing_range.get("row_from") != row_from
                or existing_range.get("row_to") != row_to
                or not _numeric_columns_equal(
                    list(existing_range.get("values") or []),
                    values,
                )
            ):
                collision = True
                warnings.append(
                    f"Target dataset {reference.dataset_name} receives conflicting plotted ranges or values."
                )
        mappings.append(
            {
                "series_index": target_index,
                "source_series_index": source_series_index,
                "semantic_role": semantic_role,
                "target_x_dataset": x_reference.dataset_name,
                "target_y_dataset": y_reference.dataset_name,
                "source_x_column_index": source_x_index,
                "source_y_column_index": source_y_index,
                "source_x_header": str(headers[source_x_index]),
                "source_y_header": str(headers[source_y_index]),
                "row_count": min(len(x_values), len(y_values)),
                "target_row_from": row_from,
                "target_row_to": row_to,
                "template_plot_reference_count": pair_counts[pair_key],
            }
        )

    blocked = (
        not plot_mappings
        or not parsed_rows
        or len(parsed_rows) != len(plot_mappings)
        or missing > 0
        or collision
        or row_count_mismatch
        or bool(inconsistent_pair_ranges)
        or bool(inconsistent_source_bindings)
        or bool(unavailable_explicit_indices)
        or (require_exact_series_count and unused > 0)
    )
    return TemplateXYDatasetUpdates(
        status="blocked" if blocked else ("partial" if unused else "ready"),
        worksheet_columns=worksheet_columns,
        worksheet_ranges=tuple(range_by_dataset.values()),
        visual_plot_count=len(plot_mappings),
        unique_plot_pair_count=len(unique_targets),
        source_series_count=len(valid_source_pairs),
        missing_series_count=missing,
        unused_source_series_count=unused,
        duplicate_plot_pair_references={
            key: count for key, count in pair_counts.items() if count > 1
        },
        mappings=tuple(mappings),
        warnings=tuple(warnings),
    )


def _column_from_rows(rows: list[list[object]] | tuple[tuple[object, ...], ...], index: int) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row[index] if index < len(row) else math.nan
        values.append(_to_float(value))
    return values


def _numeric_columns_equal(left: list[float], right: list[float]) -> bool:
    if len(left) != len(right):
        return False
    return all(
        (math.isnan(a) and math.isnan(b)) or a == b
        for a, b in zip(left, right)
    )


def _fit_xy_to_target_row_count(
    x_values: list[float],
    y_values: list[float],
    expected_row_count: int,
) -> tuple[list[float], list[float], bool]:
    available = min(len(x_values), len(y_values))
    if available < expected_row_count:
        return x_values[:available], y_values[:available], False
    trailing_pairs = zip(
        x_values[expected_row_count:available],
        y_values[expected_row_count:available],
    )
    if any(not math.isnan(x_value) and not math.isnan(y_value) for x_value, y_value in trailing_pairs):
        return x_values[:available], y_values[:available], False
    return (
        x_values[:expected_row_count],
        y_values[:expected_row_count],
        True,
    )


def _to_float(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _is_saved_format_theme(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in GRAPH_THEME_SUFFIXES


def _graph_template_source(source_opju: Path | None, style_package: Path | None) -> Path | None:
    for path in (style_package, source_opju):
        if path is not None and path.is_file() and path.suffix.casefold() in GRAPH_TEMPLATE_SUFFIXES:
            return path
    return None


def _optional_path(path: str | Path | None) -> Path | None:
    if path is None or not str(path).strip():
        return None
    return Path(path)
