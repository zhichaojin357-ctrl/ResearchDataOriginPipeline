from __future__ import annotations

from pathlib import Path

from src.origin.template_format import (
    build_template_dataset_updates,
    build_template_format_plan,
    build_template_xy_dataset_updates,
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


def test_explicit_xy_updates_replace_every_independent_bet_x_column() -> None:
    mappings = [
        {"x_dataset": "Isotherm_A", "y_dataset": "Isotherm_B", "row_from": 1, "row_to": 2},
        {"x_dataset": "Isotherm_C", "y_dataset": "Isotherm_D", "row_from": 1, "row_to": 2},
        {"x_dataset": "Isotherm_E", "y_dataset": "Isotherm_F", "row_from": 1, "row_to": 2},
    ]
    headers = ["pressure", "adsorption", "desorption", "third"]
    rows = [[0.1, 10.0, 20.0, 30.0], [0.2, 11.0, 21.0, 31.0]]

    updates = build_template_xy_dataset_updates(
        mappings,
        headers,
        rows,
        [(0, 1), (0, 2), (0, 3)],
    )

    assert updates.status == "ready"
    columns = updates.worksheet_columns["Isotherm"][1]
    assert columns[0] == [0.1, 0.2]
    assert columns[2] == [0.1, 0.2]
    assert columns[4] == [0.1, 0.2]
    assert columns[1] == [10.0, 11.0]
    assert columns[3] == [20.0, 21.0]
    assert columns[5] == [30.0, 31.0]
    assert all(item["row_from"] == 1 and item["row_to"] == 2 for item in updates.worksheet_ranges)


def test_explicit_xy_updates_preserve_eis_sheet_creation_indices() -> None:
    mappings = [
        {"x_dataset": "Book1_F", "y_dataset": "Book1_G", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book1_F@2", "y_dataset": "Book1_G@2", "row_from": 1, "row_to": 2},
    ]
    headers = ["z_real_1", "z_imag_1", "z_real_2", "z_imag_2"]
    rows = [[1.0, -1.0, 2.0, -2.0], [1.5, -1.5, 2.5, -2.5]]

    updates = build_template_xy_dataset_updates(
        mappings,
        headers,
        rows,
        [(0, 1), (2, 3)],
    )

    assert updates.status == "ready"
    assert updates.worksheet_columns["Book1"][1][5] == [1.0, 1.5]
    assert updates.worksheet_columns["Book1"][1][6] == [-1.0, -1.5]
    assert updates.worksheet_columns["Book1"][2][5] == [2.0, 2.5]
    assert updates.worksheet_columns["Book1"][2][6] == [-2.0, -2.5]


def test_explicit_xy_updates_use_contract_source_indices_not_target_sort_order() -> None:
    mappings = [
        {
            "layer_index": 1,
            "plot_index": 1,
            "x_dataset": "Book2_A",
            "y_dataset": "Book2_B",
            "row_from": 1,
            "row_to": 2,
            "source_series_index": 1,
            "semantic_role": "series_1",
        },
        {
            "layer_index": 1,
            "plot_index": 2,
            "x_dataset": "Book2_E",
            "y_dataset": "Book2_F",
            "row_from": 1,
            "row_to": 2,
            "source_series_index": 3,
            "semantic_role": "series_3",
        },
        {
            "layer_index": 2,
            "plot_index": 1,
            "x_dataset": "Book2_C",
            "y_dataset": "Book2_D",
            "row_from": 1,
            "row_to": 2,
            "source_series_index": 2,
            "semantic_role": "series_2",
        },
    ]
    headers = ["x1", "y1", "x2", "y2", "x3", "y3"]
    rows = [
        [1.0, 11.0, 2.0, 22.0, 3.0, 33.0],
        [1.5, 11.5, 2.5, 22.5, 3.5, 33.5],
    ]

    updates = build_template_xy_dataset_updates(
        mappings,
        headers,
        rows,
        [(0, 1), (2, 3), (4, 5)],
        require_explicit_source_bindings=True,
    )

    assert updates.status == "ready"
    columns = updates.worksheet_columns["Book2"][1]
    assert columns[1] == [11.0, 11.5]
    assert columns[5] == [33.0, 33.5]
    assert columns[3] == [22.0, 22.5]
    assert [item["source_series_index"] for item in updates.mappings] == [1, 3, 2]


def test_explicit_xy_updates_fail_closed_without_contract_source_binding() -> None:
    updates = build_template_xy_dataset_updates(
        [
            {
                "x_dataset": "Book1_A",
                "y_dataset": "Book1_B",
                "row_from": 1,
                "row_to": 1,
            }
        ],
        ["x", "y"],
        [[0.0, 1.0]],
        [(0, 1)],
        require_explicit_source_bindings=True,
    )

    assert updates.status == "blocked"
    assert "source_series_index" in "; ".join(updates.warnings)


def test_explicit_xy_updates_sort_unique_xps_targets_by_column_not_fill_plot_order() -> None:
    mappings = [
        {"x_dataset": "Book2_A", "y_dataset": "Book2_B", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book2_A", "y_dataset": "Book2_C", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book2_A", "y_dataset": "Book2_E", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book2_A", "y_dataset": "Book2_D", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book2_A", "y_dataset": "Book2_E", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book2_A", "y_dataset": "Book2_E", "row_from": 1, "row_to": 2},
        {"x_dataset": "Book2_A", "y_dataset": "Book2_F", "row_from": 1, "row_to": 2},
    ]
    headers = ["binding_energy", "measured", "component_1", "component_2", "background", "envelope"]
    rows = [[168.0, 10.0, 2.0, 3.0, 1.0, 10.0], [167.0, 11.0, 2.1, 3.1, 1.1, 11.0]]

    updates = build_template_xy_dataset_updates(
        mappings,
        headers,
        rows,
        [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)],
    )

    assert updates.status == "ready"
    assert updates.unique_plot_pair_count == 5
    assert updates.duplicate_plot_pair_references == {"Book2_A->Book2_E": 3}
    columns = updates.worksheet_columns["Book2"][1]
    assert columns[1] == [10.0, 11.0]
    assert columns[2] == [2.0, 2.1]
    assert columns[3] == [3.0, 3.1]
    assert columns[4] == [1.0, 1.1]
    assert columns[5] == [10.0, 11.0]


def test_explicit_xy_updates_block_surplus_processed_series_in_exact_mapping() -> None:
    updates = build_template_xy_dataset_updates(
        [{"x_dataset": "Book1_A", "y_dataset": "Book1_B", "row_from": 1, "row_to": 1}],
        ["x", "y1", "y2"],
        [[0.0, 1.0, 2.0]],
        [(0, 1), (0, 2)],
    )

    assert updates.status == "blocked"
    assert updates.unused_source_series_count == 1
    assert "template exposes only 1" in "; ".join(updates.warnings)


def test_explicit_xy_updates_preserve_nonfirst_plot_row_offset_and_block_length_mismatch() -> None:
    mapping = [
        {"x_dataset": "Book1_A", "y_dataset": "Book1_B", "row_from": 3, "row_to": 4}
    ]
    ready = build_template_xy_dataset_updates(
        mapping,
        ["x", "y"],
        [[0.0, 1.0], [1.0, 2.0]],
        [(0, 1)],
    )
    mismatched = build_template_xy_dataset_updates(
        mapping,
        ["x", "y"],
        [[0.0, 1.0], [1.0, 2.0], [2.0, 3.0], [3.0, 4.0]],
        [(0, 1)],
    )

    assert ready.status == "ready"
    assert {item["row_from"] for item in ready.worksheet_ranges} == {3}
    assert {item["row_to"] for item in ready.worksheet_ranges} == {4}
    assert mismatched.status == "blocked"
    assert "without dropping nonmissing plotted values" in "; ".join(mismatched.warnings)


def test_explicit_xy_updates_may_drop_only_trailing_nonplotted_missing_pairs() -> None:
    updates = build_template_xy_dataset_updates(
        [{"x_dataset": "Book1_A", "y_dataset": "Book1_B", "row_from": 1, "row_to": 2}],
        ["x", "y"],
        [[0.0, 1.0], [1.0, 2.0], [float("nan"), float("nan")]],
        [(0, 1)],
    )

    assert updates.status == "ready"
    ranges = {item["dataset_name"]: item for item in updates.worksheet_ranges}
    assert ranges["Book1_A"]["values"] == [0.0, 1.0]
    assert ranges["Book1_B"]["values"] == [1.0, 2.0]
