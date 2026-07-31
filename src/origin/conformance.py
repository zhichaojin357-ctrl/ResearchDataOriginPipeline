from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.origin.style_mimic import OpjuStyleSnapshot


PAGE_LAYER_FIELDS = (
    "page.width",
    "page.height",
    "layer.left",
    "layer.top",
    "layer.width",
    "layer.height",
    "layer.x.thickness",
    "layer.y.thickness",
)

GRAPH4_GEOMETRY_FIELDS = (
    "page.width",
    "page.height",
    "layer.left",
    "layer.top",
    "layer.width",
    "layer.height",
)

AXIS_FIELDS = (
    "layer.x.ticks",
    "layer.y.ticks",
    "layer.x.majorLen",
    "layer.y.majorLen",
    "layer.x.minor",
    "layer.y.minor",
    "layer.x.label.pt",
    "layer.y.label.pt",
    "layer.x.label.bold",
    "layer.y.label.bold",
    "layer.x.label.offset",
    "layer.y.label.offset",
    "xb.fsize",
    "yl.fsize",
    "xb.bold",
    "yl.bold",
    "xb.x",
    "xb.y",
    "yl.x",
    "yl.y",
    "layer.x.from",
    "layer.x.to",
    "layer.y.from",
    "layer.y.to",
)

LEGEND_TITLE_FIELDS = (
    "legend.show",
    "legend.x",
    "legend.y",
    "legend.fsize",
    "legend.bold",
    "title.show",
    "title.x",
    "title.y",
    "title.fsize",
    "title.bold",
)

REQUIRED_FIELD_GROUPS = {
    "page_layer": PAGE_LAYER_FIELDS,
    "axis": AXIS_FIELDS,
    "legend_title": LEGEND_TITLE_FIELDS,
}

CRITICAL_FIELDS = frozenset(
    (
        *GRAPH4_GEOMETRY_FIELDS,
        "layer.x.thickness",
        "layer.y.thickness",
        "layer.x.label.pt",
        "layer.y.label.pt",
        "xb.fsize",
        "yl.fsize",
        "xb.bold",
        "yl.bold",
    )
)


@dataclass(frozen=True)
class ConformanceIssue:
    field: str
    exemplar: float | str | None
    product: float | str | None
    category: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "field": self.field,
            "exemplar": self.exemplar,
            "product": self.product,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class ConformanceReport:
    status: str
    compared_fields: int
    matched_fields: int
    missing_fields: list[str] = field(default_factory=list)
    issues: list[ConformanceIssue] = field(default_factory=list)
    plot_line_width_origin_units: list[float] = field(default_factory=list)
    axis_title_bold: bool = False
    axis_title_no_overlap_check: str = "manual_review"
    product_closer_than_v1: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "compared_fields": self.compared_fields,
            "matched_fields": self.matched_fields,
            "missing_fields": list(self.missing_fields),
            "issues": [issue.to_dict() for issue in self.issues],
            "plot_line_width_origin_units": list(self.plot_line_width_origin_units),
            "axis_title_bold": self.axis_title_bold,
            "axis_title_no_overlap_check": self.axis_title_no_overlap_check,
            "product_closer_than_v1": self.product_closer_than_v1,
        }


def compare_style_snapshots(
    exemplar: OpjuStyleSnapshot | dict[str, Any],
    product: OpjuStyleSnapshot | dict[str, Any],
    *,
    tolerance: float = 0.10,
    required_line_width_pt: float = 3.0,
    require_axis_title_bold: bool = True,
    product_closer_than_v1: bool | None = None,
) -> ConformanceReport:
    exemplar_values = _combined_numeric_values(exemplar)
    product_values = _combined_numeric_values(product)
    issues: list[ConformanceIssue] = []
    missing: list[str] = []
    compared = 0
    matched = 0
    for category, fields in REQUIRED_FIELD_GROUPS.items():
        for field_name in fields:
            if field_name not in exemplar_values:
                missing.append(f"exemplar:{field_name}")
                if field_name in CRITICAL_FIELDS:
                    issues.append(
                        ConformanceIssue(
                            field=field_name,
                            exemplar=None,
                            product=product_values.get(field_name),
                            category=category,
                            severity="fail",
                            message="critical exemplar style field is unavailable",
                        )
                    )
                continue
            if field_name not in product_values:
                missing.append(f"product:{field_name}")
                if field_name in CRITICAL_FIELDS:
                    issues.append(
                        ConformanceIssue(
                            field=field_name,
                            exemplar=exemplar_values[field_name],
                            product=None,
                            category=category,
                            severity="fail",
                            message="critical product style field is unavailable",
                        )
                    )
                continue
            compared += 1
            expected = exemplar_values[field_name]
            actual = product_values[field_name]
            if field_name in GRAPH4_GEOMETRY_FIELDS:
                matches = _within_absolute_tolerance(expected, actual, 0.01)
            else:
                matches = _within_tolerance(expected, actual, tolerance)
            if matches:
                matched += 1
            else:
                geometry_failure = field_name in GRAPH4_GEOMETRY_FIELDS
                issues.append(
                    ConformanceIssue(
                        field=field_name,
                        exemplar=expected,
                        product=actual,
                        category=category,
                        severity="fail" if geometry_failure else "review",
                        message=(
                            "Graph4 page/layer geometry differs by more than the absolute 0.01 tolerance"
                            if geometry_failure
                            else "numeric style value differs from exemplar beyond tolerance"
                        ),
                    )
                )

    for field_name, tolerance_kind in (
        ("plot_colors", "exact"),
        ("marker_shapes", "exact"),
        ("marker_sizes", "relative"),
    ):
        expected_values = _series_style_values(exemplar, field_name)
        if not expected_values:
            continue
        actual_values = _series_style_values(product, field_name)
        if not actual_values:
            missing.append(f"product:{field_name}")
            issues.append(
                ConformanceIssue(
                    field=field_name,
                    exemplar=str(expected_values),
                    product=None,
                    category="plot",
                    severity="fail",
                    message=f"critical product {field_name} readback is unavailable",
                )
            )
            continue
        if len(expected_values) != len(actual_values):
            issues.append(
                ConformanceIssue(
                    field=field_name,
                    exemplar=str(expected_values),
                    product=str(actual_values),
                    category="plot",
                    severity="fail",
                    message=(
                        f"{field_name} count differs from the exemplar "
                        f"({len(actual_values)} vs {len(expected_values)})"
                    ),
                )
            )
        for index, (expected, actual) in enumerate(
            zip(expected_values, actual_values),
            start=1,
        ):
            compared += 1
            matches = (
                _within_absolute_tolerance(expected, actual, 0.01)
                if tolerance_kind == "exact"
                else _within_tolerance(expected, actual, 0.02)
            )
            if matches:
                matched += 1
            else:
                issues.append(
                    ConformanceIssue(
                        field=f"{field_name}[{index}]",
                        exemplar=expected,
                        product=actual,
                        category="plot",
                        severity="fail",
                        message=f"product {field_name} differs from exemplar",
                    )
                )

    line_widths = _plot_widths(product)
    if not line_widths:
        missing.append("product:plot_line_widths")
        issues.append(
            ConformanceIssue(
                field="plot_line_widths",
                exemplar=None,
                product=None,
                category="plot",
                severity="fail",
                message="critical product plot line-width readback is unavailable",
            )
        )
    expected_origin_width = required_line_width_pt * 500.0
    for index, value in enumerate(line_widths, start=1):
        if not _within_tolerance(expected_origin_width, value, 0.02):
            issues.append(
                ConformanceIssue(
                    field=f"plot[{index}].line_width",
                    exemplar=expected_origin_width,
                    product=value,
                    category="plot",
                    severity="fail",
                    message="product line width does not match required 3 pt policy",
                )
            )

    axis_bold = _axis_titles_bold(product)
    if require_axis_title_bold and not axis_bold:
        issues.append(
            ConformanceIssue(
                field="axis_title.bold",
                exemplar=1.0,
                product=0.0,
                category="axis",
                severity="fail",
                message="x/y axis titles are not both bold",
            )
        )

    no_overlap = _axis_title_overlap_status(product)
    if no_overlap == "risk":
        issues.append(
            ConformanceIssue(
                field="axis_title.offset",
                exemplar=None,
                product=None,
                category="axis",
                severity="review",
                message="axis title position readback suggests possible tick-label overlap",
            )
        )

    failed = any(issue.severity == "fail" for issue in issues)
    status = "pass" if not failed else "fail"
    if issues and not failed:
        status = "review"
    return ConformanceReport(
        status=status,
        compared_fields=compared,
        matched_fields=matched,
        missing_fields=missing,
        issues=issues,
        plot_line_width_origin_units=line_widths,
        axis_title_bold=axis_bold,
        axis_title_no_overlap_check=no_overlap,
        product_closer_than_v1=product_closer_than_v1,
    )


def conformance_distance(report: ConformanceReport | dict[str, Any]) -> float:
    payload = report.to_dict() if isinstance(report, ConformanceReport) else report
    compared = float(payload.get("compared_fields") or 0)
    matched = float(payload.get("matched_fields") or 0)
    issue_penalty = len(payload.get("issues") or []) * 0.25
    if compared <= 0:
        return float("inf")
    return max(compared - matched, 0.0) / compared + issue_penalty


def _combined_numeric_values(snapshot: OpjuStyleSnapshot | dict[str, Any]) -> dict[str, float]:
    if isinstance(snapshot, OpjuStyleSnapshot):
        values = {**snapshot.layout_values, **snapshot.audit_numeric_values}
    else:
        values = {
            **dict(snapshot.get("layout_values") or {}),
            **dict(snapshot.get("audit_numeric_values") or {}),
        }
    output: dict[str, float] = {}
    for key, value in values.items():
        number = _to_float(value)
        if number is not None:
            output[str(key)] = number
    return output


def _plot_widths(snapshot: OpjuStyleSnapshot | dict[str, Any]) -> list[float]:
    values = snapshot.plot_line_widths if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("plot_line_widths", [])
    return [number for item in values if (number := _to_float(item)) is not None]


def _series_style_values(
    snapshot: OpjuStyleSnapshot | dict[str, Any],
    field_name: str,
) -> list[float]:
    values = (
        getattr(snapshot, field_name, [])
        if isinstance(snapshot, OpjuStyleSnapshot)
        else snapshot.get(field_name, [])
    )
    if not isinstance(values, (list, tuple)):
        return []
    return [
        number
        for item in values
        if (number := _to_float(item)) is not None
    ]


def _axis_titles_bold(snapshot: OpjuStyleSnapshot | dict[str, Any]) -> bool:
    values = _combined_numeric_values(snapshot)
    strings = snapshot.audit_string_values if isinstance(snapshot, OpjuStyleSnapshot) else snapshot.get("audit_string_values", {})
    xb_text = str(strings.get("xb.text$", "")) if isinstance(strings, dict) else ""
    yl_text = str(strings.get("yl.text$", "")) if isinstance(strings, dict) else ""
    xb_bold = values.get("xb.bold") == 1.0 or "\\b(" in xb_text
    yl_bold = values.get("yl.bold") == 1.0 or "\\b(" in yl_text
    return xb_bold and yl_bold


def _axis_title_overlap_status(snapshot: OpjuStyleSnapshot | dict[str, Any]) -> str:
    values = _combined_numeric_values(snapshot)
    x_size = values.get("xb.fsize")
    y_size = values.get("yl.fsize")
    tick_x = values.get("layer.x.label.pt")
    tick_y = values.get("layer.y.label.pt")
    if None in (x_size, y_size, tick_x, tick_y):
        return "manual_review"
    if (x_size or 0) < 8 or (y_size or 0) < 8:
        return "risk"
    if (tick_x or 0) > (x_size or 0) * 1.8 or (tick_y or 0) > (y_size or 0) * 1.8:
        return "risk"
    return "pass"


def _within_tolerance(expected: float, actual: float, tolerance: float) -> bool:
    if not math.isfinite(expected) or not math.isfinite(actual):
        return False
    scale = max(abs(expected), 1.0)
    return abs(expected - actual) <= max(tolerance * scale, 1e-6)


def _within_absolute_tolerance(expected: float, actual: float, tolerance: float) -> bool:
    if not math.isfinite(expected) or not math.isfinite(actual):
        return False
    return abs(expected - actual) <= tolerance


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
