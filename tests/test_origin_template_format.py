from __future__ import annotations

from pathlib import Path

from src.origin.template_format import (
    build_template_dataset_updates,
    build_template_format_plan,
    parse_origin_dataset_name,
    parse_origin_dataset_reference,
)


def test_template_format_plan_uses_opju_template_base_when_exemplar_exists(tmp_path: Path) -> None:
    opju = tmp_path / "template.opju"
    opju.write_bytes(b"opju")

    plan = build_template_format_plan(
        "BET",
        opju_path=opju,
        graph_page="Graph3",
        reference_preview_png=tmp_path / "reference.png",
        product_preview_png=tmp_path / "product.png",
    )

    assert plan.status == "ready"
    assert plan.mode == "opju_template_base"
    assert plan.source_opju == opju
    assert plan.graph_page == "Graph3"
    assert plan.plot_intent["curve_line_width_pt"] == 3.0
    assert plan.plot_intent["axis_title_bold"] is True
    assert plan.plot_intent["template_image_comparison_required"] is True
    assert plan.one_to_one_claim_allowed is False


def test_template_format_plan_can_use_saved_format_theme_when_opju_missing(tmp_path: Path) -> None:
    style_package = tmp_path / "xps_style.oth"
    style_package.write_text("style", encoding="utf-8")

    plan = build_template_format_plan(
        "XPS_non_in_situ",
        opju_path=tmp_path / "missing.opju",
        graph_page="Bi_4f",
        style_package_path=style_package,
    )

    assert plan.status == "ready"
    assert plan.mode == "saved_format_theme"
    assert plan.style_package_path == style_package
    assert "saved format theme" in "; ".join(plan.warnings)
    assert plan.one_to_one_claim_allowed is False


def test_template_format_plan_blocks_otpu_as_the_only_runtime_style_source(tmp_path: Path) -> None:
    style_package = tmp_path / "BET.otpu"
    style_package.write_text("style", encoding="utf-8")

    source_plan = build_template_format_plan(
        "BET",
        opju_path=style_package,
        graph_page="Graph1",
    )
    package_plan = build_template_format_plan(
        "BET",
        opju_path=tmp_path / "missing.opju",
        graph_page="Graph1",
        style_package_path=style_package,
    )

    for plan in (source_plan, package_plan):
        assert plan.status == "blocked"
        assert plan.mode == "untrusted_graph_template"
        assert plan.can_execute is False
        assert plan.graph_page == "Graph1"
        assert plan.one_to_one_claim_allowed is False
        assert ".otpu" in "; ".join(plan.warnings)


def test_template_format_plan_blocks_without_opju_or_style_package(tmp_path: Path) -> None:
    plan = build_template_format_plan(
        "EPR",
        opju_path=tmp_path / "missing.opju",
        graph_page="ohG",
    )

    assert plan.status == "blocked"
    assert plan.mode == "missing_template_source"
    assert plan.can_execute is False
    assert plan.one_to_one_claim_allowed is False
    assert "No OPJU exemplar or saved style package" in "; ".join(plan.warnings)


def test_template_format_plan_can_use_embedded_snapshot_without_opju(tmp_path: Path) -> None:
    plan = build_template_format_plan(
        "EPR",
        opju_path=tmp_path / "missing.opju",
        graph_page="EPR0519OH",
        embedded_snapshot_available=True,
    )

    assert plan.status == "ready"
    assert plan.mode == "embedded_template_snapshot"
    assert plan.can_execute is True
    assert plan.graph_page == "EPR0519OH"
    assert plan.plot_intent["origin_template_or_format_source_required"] is False
    assert "embedded Origin template snapshot" in "; ".join(plan.warnings)


def test_parse_origin_dataset_name_handles_book_column_tokens() -> None:
    assert parse_origin_dataset_name("Book8_B") == ("Book8", 1)
    assert parse_origin_dataset_name("Book10_AA") == ("Book10", 26)
    assert parse_origin_dataset_name("not-a-dataset") is None


def test_parse_origin_dataset_reference_preserves_sheet_creation_index() -> None:
    first = parse_origin_dataset_reference("Book8_B")
    second = parse_origin_dataset_reference("Book8_AA@2")

    assert first is not None
    assert (first.book_name, first.column_index, first.sheet_index) == ("Book8", 1, 1)
    assert first.sheet_reference == "1"
    assert second is not None
    assert (second.book_name, second.column_index, second.sheet_index) == ("Book8", 26, 2)
    assert second.sheet_reference == "2"


def test_template_dataset_updates_map_processed_columns_to_template_workbooks() -> None:
    headers = ["x", "adsorption", "desorption"]
    rows = [[0.0, 10.0, 20.0], [1.0, 11.0, 21.0]]

    updates = build_template_dataset_updates(["Book1_B", "Book1_C"], headers, rows)

    assert updates.status == "ready"
    assert updates.visual_plot_count == 2
    assert updates.unique_dataset_count == 2
    assert updates.missing_series_count == 0
    assert updates.workbook_columns["Book1"][0] == [0.0, 1.0]
    assert updates.workbook_columns["Book1"][1] == [10.0, 11.0]
    assert updates.workbook_columns["Book1"][2] == [20.0, 21.0]


def test_template_dataset_updates_can_replace_paired_xy_columns() -> None:
    headers = ["x", "sample_a", "sample_b", "sample_c"]
    rows = [[5.0, 10.0, 20.0, 30.0], [6.0, 11.0, 21.0, 31.0]]

    updates = build_template_dataset_updates(
        ["Book2_B", "Book2_D", "Book3_F"],
        headers,
        rows,
        paired_xy_columns=True,
    )

    assert updates.status == "ready"
    assert updates.workbook_columns["Book2"][0] == [5.0, 6.0]
    assert updates.workbook_columns["Book2"][1] == [10.0, 11.0]
    assert updates.workbook_columns["Book2"][2] == [5.0, 6.0]
    assert updates.workbook_columns["Book2"][3] == [20.0, 21.0]
    assert updates.workbook_columns["Book3"][4] == [5.0, 6.0]
    assert updates.workbook_columns["Book3"][5] == [30.0, 31.0]


def test_template_dataset_updates_report_duplicate_dataset_references() -> None:
    headers = ["x", "component", "baseline"]
    rows = [[100.0, 1.0, 0.0], [101.0, 2.0, 0.1]]

    updates = build_template_dataset_updates(["Book8_E", "Book8_D", "Book8_E"], headers, rows)

    assert updates.status == "ready"
    assert updates.visual_plot_count == 3
    assert updates.unique_dataset_count == 2
    assert updates.duplicate_dataset_references == {"Book8_E": 2}
    assert updates.workbook_columns["Book8"][0] == [100.0, 101.0]
    assert updates.workbook_columns["Book8"][4] == [1.0, 2.0]
    assert updates.workbook_columns["Book8"][3] == [0.0, 0.1]


def test_template_dataset_updates_block_when_template_requires_more_unique_series_than_data() -> None:
    headers = ["x", "only_one"]
    rows = [[0.0, 1.0], [1.0, 2.0]]

    updates = build_template_dataset_updates(["Book1_B", "Book1_C"], headers, rows)

    assert updates.status == "blocked"
    assert updates.missing_series_count == 1
    assert "Template requires 2 unique Y datasets but processed data has 1" in "; ".join(updates.warnings)


def test_template_dataset_updates_can_report_partial_missing_series_without_fabricating_values() -> None:
    headers = ["x", "only_one"]
    rows = [[0.0, 1.0], [1.0, 2.0]]

    updates = build_template_dataset_updates(["Book1_B", "Book1_C"], headers, rows, allow_partial=True)

    assert updates.status == "partial"
    assert updates.missing_series_count == 1
    assert updates.workbook_columns["Book1"][0] == [0.0, 1.0]
    assert updates.workbook_columns["Book1"][1] == [1.0, 2.0]
    assert all(value != value for value in updates.workbook_columns["Book1"][2])
