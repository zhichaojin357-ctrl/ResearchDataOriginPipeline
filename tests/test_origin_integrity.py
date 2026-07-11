from __future__ import annotations

from src.origin.conformance import compare_style_snapshots
from src.origin.style_mimic import OpjuStyleSnapshot


def _graph4_snapshot(*, layer_width: float = 68.19) -> OpjuStyleSnapshot:
    return OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        graph_page="Graph4",
        layout_values={
            "page.width": 6432.0,
            "page.height": 4923.0,
            "layer.left": 17.89,
            "layer.top": 11.6,
            "layer.width": layer_width,
            "layer.height": 71.81,
            "layer.x.thickness": 3.0,
            "layer.y.thickness": 3.0,
            "layer.x.label.pt": 28.0,
            "layer.y.label.pt": 36.0,
            "layer.x.from": 100.0,
        },
        audit_numeric_values={
            "xb.fsize": 36.0,
            "yl.fsize": 36.0,
            "xb.bold": 1.0,
            "yl.bold": 1.0,
        },
        plot_line_widths=[1500.0],
    )


def test_conformance_missing_critical_product_field_is_a_failure() -> None:
    exemplar = _graph4_snapshot()
    product_payload = exemplar.to_dict()
    product_payload["layout_values"].pop("layer.width")

    report = compare_style_snapshots(exemplar, product_payload)

    assert report.status == "fail"
    assert "product:layer.width" in report.missing_fields
    assert any(issue.field == "layer.width" and issue.severity == "fail" for issue in report.issues)


def test_graph4_geometry_uses_absolute_point_zero_one_tolerance() -> None:
    exemplar = _graph4_snapshot()
    within = _graph4_snapshot(layer_width=68.199)
    outside = _graph4_snapshot(layer_width=68.201)

    within_report = compare_style_snapshots(exemplar, within)
    outside_report = compare_style_snapshots(exemplar, outside)

    assert not any(issue.field == "layer.width" for issue in within_report.issues)
    assert outside_report.status == "fail"
    assert any(issue.field == "layer.width" and issue.severity == "fail" for issue in outside_report.issues)


def test_non_geometry_numeric_fields_keep_relative_tolerance_strategy() -> None:
    exemplar = _graph4_snapshot()
    product_payload = exemplar.to_dict()
    product_payload["layout_values"]["layer.x.from"] = 105.0

    report = compare_style_snapshots(exemplar, product_payload, tolerance=0.10)

    assert not any(issue.field == "layer.x.from" for issue in report.issues)
