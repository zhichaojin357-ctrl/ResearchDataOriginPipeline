from __future__ import annotations

from src.origin.conformance import compare_style_snapshots
from src.origin.style_mimic import OpjuStyleSnapshot


def test_conformance_comparison_checks_layout_axis_plot_width_and_bold_titles() -> None:
    exemplar = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        layout_values={
            "page.width": 720,
            "page.height": 540,
            "layer.left": 20,
            "layer.top": 10,
            "layer.width": 60,
            "layer.height": 62,
            "layer.x.thickness": 2,
            "layer.y.thickness": 2,
            "layer.x.label.pt": 24,
            "layer.y.label.pt": 24,
        },
        audit_numeric_values={"xb.fsize": 28, "yl.fsize": 28, "xb.bold": 1, "yl.bold": 1},
        plot_line_widths=[30.0],
    )
    product = OpjuStyleSnapshot(
        source_opju="product.opju",
        status="extracted",
        layout_values=dict(exemplar.layout_values),
        audit_numeric_values=dict(exemplar.audit_numeric_values),
        plot_line_widths=[30.0],
    )

    report = compare_style_snapshots(exemplar, product)

    assert report.status == "pass"
    assert report.matched_fields == report.compared_fields
    assert report.plot_line_width_origin_units == [30.0]
    assert report.axis_title_bold is True


def test_conformance_comparison_flags_non_3pt_width_and_nonbold_axis_titles() -> None:
    exemplar = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        layout_values={"page.width": 720, "page.height": 540},
        audit_numeric_values={"xb.bold": 1, "yl.bold": 1, "xb.fsize": 28, "yl.fsize": 28},
        plot_line_widths=[30.0],
    )
    product = OpjuStyleSnapshot(
        source_opju="product.opju",
        status="extracted",
        layout_values={"page.width": 720, "page.height": 540},
        audit_numeric_values={"xb.bold": 1, "yl.bold": 0, "xb.fsize": 28, "yl.fsize": 28},
        plot_line_widths=[15.0],
    )

    report = compare_style_snapshots(exemplar, product)

    assert report.status == "fail"
    assert any(issue.field == "plot[1].line_width" for issue in report.issues)
    assert any(issue.field == "axis_title.bold" for issue in report.issues)


def test_conformance_accepts_origin_rich_text_bold_axis_titles() -> None:
    exemplar = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        audit_numeric_values={"xb.bold": 1, "yl.bold": 1, "xb.fsize": 28, "yl.fsize": 28},
    )
    product = OpjuStyleSnapshot(
        source_opju="product.opju",
        status="extracted",
        audit_numeric_values={"xb.bold": 0, "yl.bold": 0, "xb.fsize": 28, "yl.fsize": 28},
        audit_string_values={"xb.text$": "\\b(Z' (ohm))", "yl.text$": "\\b(-Z'' (ohm))"},
        plot_line_widths=[30.0],
    )

    report = compare_style_snapshots(exemplar, product)

    assert report.axis_title_bold is True
    assert not any(issue.field == "axis_title.bold" for issue in report.issues)
