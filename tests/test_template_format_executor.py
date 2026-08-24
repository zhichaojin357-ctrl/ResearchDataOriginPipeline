from __future__ import annotations

import json
import hashlib
import math
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cli import main
from src.core.template_product_common import ProductContext, TargetPairing
from src.core.template_format_executor import (
    FINAL_TEMPLATE_STYLE_OVERRIDE,
    TEMPLATE_FORMAT_COMMAND,
    TEMPLATE_FORMAT_SCOPE,
    TemplateFormatExecutorOptions,
    _adaptive_eis_conformance_reference,
    _adaptive_raman_conformance_reference,
    _adaptive_epr_conformance_reference,
    _adaptive_pl_conformance_reference,
    _adaptive_series_count_conformance,
    _adaptive_oth_json_readback_validation,
    _adaptive_photocurrent_validation_ranges,
    _apply_embedded_snapshot_data_axis_range,
    _apply_adaptive_epr_data_axis_range,
    _apply_adaptive_epr_direct_labels,
    _apply_adaptive_bet_oth_json_text_policy,
    _apply_adaptive_dynamic_legend_policy,
    _apply_adaptive_xrd_standard_card_plot_styles,
    _position_adaptive_xrd_axis_titles,
    _apply_adaptive_photocurrent_oth_json_text_policy,
    _apply_cached_style_rich_text_policies,
    _apply_external_reference_plot_sequence,
    _apply_reviewed_template_plot_styles,
    _apply_mott_schottky_source_masks,
    _export_verified_graph_template_product_with_origin,
    _export_external_reference_preview_if_requested,
    _apply_nonoverlap_plain_legend_anchor,
    _apply_reviewed_template_plot_policy,
    _apply_saved_template_legend_anchor,
    _apply_template_base_global_policies,
    _apply_xrd_standard_card_legend_and_label,
    _apply_xrd_template_plain_legend_labels,
    _clean_exemplar_legend_entry,
    _format_preserved_line_sample_legend,
    _load_saved_data_snapshot,
    _load_saved_style_snapshot,
    _mott_schottky_candidate_guides,
    _origin_rich_text_for_labtalk,
    _plain_text_legend_policy,
    _plain_text_legend_entries,
    _prepare_verified_bet_otpu_binding,
    _prepare_verified_eis_otpu_binding,
    _prepare_verified_epr_otpu_binding,
    _prepare_verified_ftir_otpu_binding,
    _prepare_verified_mott_otpu_binding,
    _prepare_verified_pl_otpu_binding,
    _prepare_verified_photocurrent_otpu_binding,
    _prepare_verified_raman_otpu_binding,
    _prepare_verified_uvvis_otpu_binding,
    _prepare_verified_xps_in_situ_otpu_binding,
    _prepare_verified_xps_non_in_situ_otpu_binding,
    _prepare_verified_otpu_binding,
    _populate_verified_otpu_workbook,
    _apply_verified_otpu_post_plot_style,
    _apply_uvvis_current_axis_titles,
    _apply_verified_uvvis_fixed_visibility,
    _processed_csv_plot_pairs,
    _refresh_graph_for_export,
    _replace_eis_dynamic_legend_with_static_rich_text,
    _remove_tauc_reference_candidate_guides,
    _validate_tauc_reference_guides_removed,
    _resolve_origin_style_execution_route,
    _select_plain_legend_anchor,
    _saved_theme_reference_policy,
    _set_origin_graph_object_text,
    _strip_raster_metadata,
    _strict_adaptive_source_validation,
    _validate_adaptive_xrd_standard_card_headers,
    _validate_xrd_axis_title_page_bounds,
    _with_default_xps_non_in_situ_template_root,
    _verified_otpu_conformance_reference,
    _validate_verified_current_data,
    _validate_xps_in_situ_reopened_plot_styles,
    _validate_adaptive_xps_in_situ_reopened_plot_styles,
    _validate_xps_non_in_situ_reopened_plot_styles,
    _validate_adaptive_xps_non_in_situ_reopened_plot_styles,
    _validate_adaptive_epr_reopened_plot_styles,
    _validate_adaptive_eis_reopened_plot_styles,
    _validate_adaptive_reopened_plot_style_cycle,
    _validate_photocurrent_axis_titles,
    _validate_bet_axis_titles,
    _update_verified_epr_label_objects,
    _update_verified_ftir_legend,
    _update_verified_pl_legend,
    _update_verified_photocurrent_legend,
    _update_verified_raman_label_objects,
    _verified_otpu_axis_title_bold_policy,
    _verified_otpu_required_line_width_pt,
    _verified_otpu_style_contract,
    _xps_in_situ_current_data_matches_reference,
    _xps_non_in_situ_adaptive_plot_format_contracts,
    _xrd_direct_label_positions,
    _xrd_plain_label_text,
    _xrd_standard_card_keeps_line_sample_legend,
    _xrd_standard_card_legend_rows,
    apply_template_base_data_replacement,
    build_template_product_builder_options,
    export_template_base_product_with_origin,
)
from src.origin.operations import OperationResult
from src.origin.style_mimic import OpjuStyleSnapshot
from src.origin.user_style import ResolvedPlotStyle


def _runtime_validated_style_entry(
    product_key: str,
    graph_page: str,
    format_theme: str,
    **extra: object,
) -> dict[str, object]:
    return {
        "product_key": product_key,
        "data_type": product_key,
        "graph_page": graph_page,
        "format_theme": format_theme,
        "asset_kind": "oth",
        "status": "accepted",
        "runtime_validation": {
            "status": "accepted",
            "comparison_scope": "fresh_project_same_data",
            "fresh_project_verified": True,
            "style_asset_only": True,
            "same_data_verified": True,
            "reference_plot_values_sha256": "1" * 64,
            "generated_plot_values_sha256": "1" * 64,
            "reference_plot_mapping_sha256": "2" * 64,
            "generated_plot_mapping_sha256": "2" * 64,
            "saved_reopened": True,
            "native_tif_600dpi_verified": True,
            "manual_preview_passed": True,
            "exact_pixel_match": True,
            "same_size": True,
            "changed_pixels": 0,
            "rms": 0,
            "reference_opju_self_replay": False,
        },
        **extra,
    }


def _write_style_manifest(style_root: Path, entry: dict[str, object]) -> None:
    runtime_kind = str(entry.get("asset_kind") or "oth").casefold().lstrip(".")
    runtime_field = {"oth": "format_theme", "otpu": "graph_template"}[runtime_kind]
    runtime_relative = str(entry[runtime_field])
    runtime_path = style_root / runtime_relative
    runtime_sha256 = hashlib.sha256(runtime_path.read_bytes()).hexdigest()
    entry["sha256"] = runtime_sha256
    entry["file_integrity"] = {
        **dict(entry.get("file_integrity") or {}),
        runtime_field: {
            "kind": runtime_kind,
            "sha256": runtime_sha256,
            "size_bytes": runtime_path.stat().st_size,
        },
    }
    runtime_validation = dict(entry.get("runtime_validation") or {})
    runtime_validation.update(
        {
            "asset_kind": runtime_kind,
            "asset_path": runtime_relative.replace("\\", "/"),
            "asset_sha256": runtime_sha256,
        }
    )
    entry["runtime_validation"] = runtime_validation
    (style_root / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "assets": [entry]}),
        encoding="utf-8",
    )


class _FakeTemplateOps:
    def __init__(self) -> None:
        self.replaced: dict[str, dict[int, list[float]]] | None = None
        self.commands: list[str] = []

    def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
        if layer_index != 1:
            return OperationResult(False, "missing layer")
        return OperationResult(True, "ok", {"graph_name": graph_name, "plot_dataset_names": ["Book1_B", "Book1_C"]})

    def replace_template_workbook_columns(self, workbook_columns: dict[str, dict[int, list[float]]]) -> OperationResult:
        self.replaced = workbook_columns
        return OperationResult(True, "replaced", {"updated_columns": [{"book_name": "Book1", "column_index": 2}]})

    def run_labtalk(self, command: str) -> OperationResult:
        self.commands.append(command)
        return OperationResult(True, "ok")

    def set_axis_labels(self, graph_name: str, x_label: str, y_label: str, title: str = "") -> OperationResult:
        self.commands.append(f"axis:{graph_name}:{x_label}:{y_label}:{title}")
        return OperationResult(True, "ok")

    def set_graph_font(self, graph_name: str, **_kwargs: object) -> OperationResult:
        self.commands.append(f"font:{graph_name}")
        return OperationResult(True, "ok")


class _FakeAxisOps:
    def __init__(self) -> None:
        self.axis_calls: list[dict[str, float | None]] = []
        self.commands: list[str] = []

    def set_axis_range(
        self,
        graph_name: str,
        x_min: float | None = None,
        x_max: float | None = None,
        y_min: float | None = None,
        y_max: float | None = None,
    ) -> OperationResult:
        self.axis_calls.append({"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max})
        return OperationResult(True, "axis", {"graph_name": graph_name})

    def run_labtalk(self, command: str) -> OperationResult:
        self.commands.append(command)
        return OperationResult(True, "ok")


class _FakeCachedStyleOps:
    def __init__(self) -> None:
        self.created_from_template: Path | None = None
        self.created_graphs: list[str] = []
        self.applied_themes: list[Path] = []
        self.saved_paths: list[Path] = []
        self.exported_paths: list[Path] = []
        self.loaded_paths: list[Path] = []
        self.closed = False
        self.commands: list[str] = []
        self.font_calls: list[dict[str, object]] = []
        self.events: list[str] = []
        self.plot_mappings: list[dict[str, object]] = [
            {
                "plot_index": 1,
                "x_dataset": "Book1_A",
                "y_dataset": "Book1_B",
                "row_from": 1,
                "row_to": 2,
                "status": "ready",
            }
        ]

    def new_project(self) -> OperationResult:
        self.events.append("new_project")
        return OperationResult(True, "new")

    def load_project(self, path: Path) -> OperationResult:
        self.loaded_paths.append(Path(path))
        self.events.append(f"load:{Path(path).name}")
        return OperationResult(True, "loaded")

    def list_worksheets(self) -> OperationResult:
        self.events.append("list_pages")
        graph_pages = self.created_graphs or ["Graph1"]
        return OperationResult(
            True,
            "listed",
            {"pages": [{"name": graph_name, "type": "graph"} for graph_name in graph_pages]},
        )

    def get_graph_plot_dataset_names(self, _graph_name: str, layer_index: int = 1) -> OperationResult:
        if layer_index != 1:
            return OperationResult(False, "missing layer")
        return OperationResult(True, "ok", {"plot_dataset_names": ["Book1_B"]})

    def get_graph_plot_dataset_mappings(self, _graph_name: str, layer_index: int = 1) -> OperationResult:
        if layer_index != 1:
            return OperationResult(False, "missing layer")
        return OperationResult(
            True,
            "ok",
            {
                "plot_mappings": list(self.plot_mappings),
                "mapping_failure_count": 0,
            },
        )

    def replace_template_workbook_columns(self, _workbook_columns: dict[str, dict[int, list[float]]]) -> OperationResult:
        return OperationResult(True, "replaced", {"updated_columns": [{"book_name": "Book1", "column_index": 2}]})

    def import_csv_to_worksheet(self, _path: Path, book_name: str = "", delimiter: str = ",") -> OperationResult:
        return OperationResult(True, "imported", {"book_name": book_name or "Book1"})

    def create_graph_from_template(self, graph_name: str, template_path: Path) -> OperationResult:
        self.created_from_template = template_path
        return OperationResult(True, "created", {"graph_name": graph_name})

    def create_graph(
        self,
        graph_name: str,
        data_book: str,
        data_sheet: str,
        x_col: int,
        y_col: int,
        plot_type: str = "line",
        y_error_col: int = 0,
        title: str = "",
    ) -> OperationResult:
        self.created_graphs.append(graph_name)
        return OperationResult(True, "created", {"graph_name": graph_name, "plot_type": plot_type})

    def apply_graph_theme(self, graph_name: str, theme_path: Path) -> OperationResult:
        self.applied_themes.append(Path(theme_path))
        return OperationResult(True, "applied", {"graph_name": graph_name, "theme_path": str(theme_path)})

    def add_plot_to_graph(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "added")

    def set_axis_labels(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "axis")

    def set_graph_font(self, _graph_name: str, **kwargs: object) -> OperationResult:
        self.font_calls.append(kwargs)
        return OperationResult(True, "font")

    def apply_graph4_fixed_style(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "style")

    def set_tick_style(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "ticks")

    def set_axis_and_tick_visibility(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "visibility")

    def set_legend(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "legend")

    def replace_legend_with_plain_text_labels(
        self,
        graph_name: str,
        entries: list[str],
        font_name: str = "Arial",
        font_size: int = 26,
        max_entries: int = 12,
        prefer_existing_text: bool = False,
    ) -> OperationResult:
        selected = [str(entry) for entry in entries[:max_entries]]
        source = "existing" if prefer_existing_text else "entries"
        self.commands.append(f"plain_legend:{source}:{graph_name}:{font_name}:{font_size}:{'|'.join(selected)}")
        return OperationResult(
            True,
            "plain legend",
            {"created_labels": [f"rdop_plain_legend_{index}" for index in range(1, len(selected) + 1)]},
        )

    def run_labtalk(self, command: str) -> OperationResult:
        self.commands.append(command)
        return OperationResult(True, "labtalk")

    def get_labtalk_variable(self, name: str) -> OperationResult:
        if name.endswith("$"):
            value: object = "Arial"
        elif name in {"page.width", "page.height"}:
            value = 100
        elif name in {"xb.fsize", "yl.fsize"}:
            value = 36
        elif name == "page.nlayers":
            value = 1
        else:
            value = 1
        return OperationResult(True, "read", {"name": name, "value": value})

    def reset_project_identity_for_export(self) -> OperationResult:
        self.events.append("identity_reset")
        return OperationResult(
            True,
            "identity reset",
            {"project_path_empty": True, "project_name_untitled": True},
        )

    def save_project(self, path: Path) -> OperationResult:
        self.saved_paths.append(Path(path))
        self.events.append(f"save:{Path(path).name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"opju")
        return OperationResult(True, "saved")

    def export_graph(self, graph_name: str, path: Path, _format: str, **_kwargs: object) -> OperationResult:
        self.exported_paths.append(Path(path))
        self.events.append(f"export:{graph_name}:{Path(path).name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if _format.casefold() in {"tif", "tiff"}:
            from PIL import Image

            Image.new("RGB", (60, 60), "white").save(path, format="TIFF", dpi=(600, 600))
        else:
            path.write_bytes(b"figure")
        return OperationResult(True, "exported")

    def close(self) -> OperationResult:
        self.closed = True
        return OperationResult(True, "closed")


def test_template_format_builder_options_use_final_scope(tmp_path: Path) -> None:
    options = build_template_product_builder_options(
        TemplateFormatExecutorOptions(
            pairing_path=tmp_path / "pairing.json",
            output_root=tmp_path / "out",
            timestamp="20260607_210000",
            f_drive_template_root=tmp_path / "f",
            xps_reference_template_root=tmp_path / "xps",
            xps_non_in_situ_template_root=tmp_path / "xps_non",
            with_origin=True,
        )
    )

    assert options.run_scope == TEMPLATE_FORMAT_SCOPE
    assert options.command_name == TEMPLATE_FORMAT_COMMAND
    assert options.product_slug_version == "template_format"
    assert options.with_origin is True
    assert options.xps_non_in_situ_template_root == tmp_path / "xps_non"
    assert options.xps_reference_templates_for_all_xps is True
    assert options.xps_templates_from_reference_only is True
    assert options.xps_smooth_gradient_fill is True
    assert options.cleanup_empty_run_layout_dirs is True
    assert options.only_type is None


def test_default_xps_non_in_situ_template_root_is_not_added_for_project_style_asset_mode(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    default_root = project_root.parent / "26.6.3组会数据" / "结果汇总" / "XPS" / "xps_heterojunction_stacked" / "origin_projects"
    default_root.mkdir(parents=True)

    options = _with_default_xps_non_in_situ_template_root(
        project_root,
        TemplateFormatExecutorOptions(pairing_path=tmp_path / "pairing.json"),
    )

    assert options.xps_non_in_situ_template_root is None


def test_apply_template_base_data_replacement_uses_template_plot_datasets(tmp_path: Path) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    ops = _FakeTemplateOps()

    result = apply_template_base_data_replacement(ops, product, "Graph1")

    assert result["ok"] is True
    assert result["template_dataset_updates"]["visual_plot_count"] == 2
    assert ops.replaced == {"Book1": {0: [0.0, 1.0], 1: [10.0, 11.0], 2: [20.0, 21.0]}}


def test_apply_template_base_data_replacement_reads_multiple_template_layers(tmp_path: Path) -> None:
    class MultiLayerOps(_FakeTemplateOps):
        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index == 1:
                return OperationResult(True, "ok", {"graph_name": graph_name, "plot_dataset_names": ["Book1_B"]})
            if layer_index == 2:
                return OperationResult(True, "ok", {"graph_name": graph_name, "plot_dataset_names": ["Book2_B"]})
            return OperationResult(False, "missing layer")

    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    ops = MultiLayerOps()

    result = apply_template_base_data_replacement(ops, product, "Graph1")

    assert result["ok"] is True
    assert result["template_dataset_updates"]["visual_plot_count"] == 2
    assert ops.replaced == {"Book1": {0: [0.0, 1.0], 1: [10.0, 11.0]}, "Book2": {0: [0.0, 1.0], 1: [20.0, 21.0]}}


def test_epr_template_replacement_uses_template_bottom_to_top_series_order(tmp_path: Path) -> None:
    class EprOps(_FakeTemplateOps):
        def get_graph_plot_dataset_names(self, graph_name: str, layer_index: int = 1) -> OperationResult:
            if layer_index != 1:
                return OperationResult(False, "missing layer")
            return OperationResult(True, "ok", {"graph_name": graph_name, "plot_dataset_names": ["OH_B", "OH_D", "OH_F"]})

    processed = tmp_path / "processed.csv"
    processed.write_text("magnetic_field,BC,CWO,BOBC\n324,1,2,3\n325,10,20,30\n", encoding="utf-8")
    product = replace(_product(tmp_path, processed), product_key="EPR")
    ops = EprOps()

    result = apply_template_base_data_replacement(ops, product, "ohG")

    assert result["ok"] is True
    assert result["processed_headers"] == ["magnetic_field", "BOBC", "CWO", "BC"]
    assert result["processed_column_mapping"]["applied"] is True
    assert ops.replaced == {
        "OH": {
            0: [324.0, 325.0],
            1: [3.0, 30.0],
            3: [2.0, 20.0],
            5: [1.0, 10.0],
        }
    }


def test_template_base_global_policy_preserves_template_axis_title_text(tmp_path: Path) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    ops = _FakeTemplateOps()

    _apply_template_base_global_policies(
        ops,
        "Graph1",
        product,
        ResolvedPlotStyle(),
        template_axis_titles={"xb.text$": "%(?X)", "yl.text$": "Offset Y values"},
    )

    commands = "\n".join(ops.commands)
    assert 'xb.text$=' not in commands
    assert 'yl.text$=' not in commands
    assert not any(command.startswith("axis:") for command in ops.commands)
    assert "label -s -xb \\b(%(?X));" in commands
    assert "label -s -yl \\b(Offset Y values);" in commands
    assert "xb.fsize=" not in commands
    assert "yl.fsize=" not in commands
    assert "xb.bold=1; yl.bold=1" in commands


def test_template_base_global_policy_preserves_template_legend_text(tmp_path: Path) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n", encoding="utf-8")
    product = replace(_product(tmp_path, processed), product_key="Raman", legend_entries=["BOBC", "CWO"])
    ops = _FakeTemplateOps()

    _apply_template_base_global_policies(ops, "Graph1", product, ResolvedPlotStyle())

    commands = "\n".join(ops.commands)
    assert "legend.text$" not in commands
    assert "legend.background=0" not in commands
    assert "legend -r" not in commands


def test_verified_bet_otpu_binding_uses_six_explicit_independent_xy_pairs(
    tmp_path: Path,
) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("unused\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        legend_entries=[
            "BOBC Adsorption",
            "BOBC Desorption",
            "CWO Adsorption",
            "CWO Desorption",
            "BiCu Adsorption",
            "BiCu Desorption",
        ],
    )
    identities = [
        "BOBC_adsorption",
        "BOBC_desorption",
        "CWO_adsorption",
        "CWO_desorption",
        "BiCu_adsorption",
        "BiCu_desorption",
    ]
    headers = [
        value
        for identity in identities
        for value in (
            f"{identity}_relative_pressure_p_p0",
            f"{identity}_quantity_adsorbed_cm3_g_stp",
        )
    ]
    rows = [
        [float(row + column / 100) for column in range(12)]
        for row in range(1, 5)
    ]

    result = _prepare_verified_bet_otpu_binding(product, headers, rows)

    assert result["ok"] is True
    assert result["graph_page"] == "Graph5"
    assert result["book_name"] == "Isotherm"
    assert result["xy_ranges"] == [
        {"x_col": index, "y_col": index + 1, "row_from": 1, "row_to": 4}
        for index in range(1, 12, 2)
    ]
    assert len(result["column_metadata"]) == 12
    assert result["column_metadata"][0]["type"] == 4
    assert result["column_metadata"][1]["type"] == 1
    assert result["column_metadata"][5]["long_name"] == "\\b(CWO (Adsorption))"
    assert result["column_metadata"][7]["long_name"] == "\\b(CWO (Desorption))"
    assert result["column_metadata"][9]["long_name"] == "\\b(BiCu (Adsorption))"
    assert result["column_metadata"][11]["long_name"] == "\\b(BiCu (Desorption))"


def _verified_eis_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[object]], Path]:
    processed = tmp_path / "eis_processed.csv"
    identities = [f"sample_{index}" for index in range(1, 9)]
    headers = [
        value
        for identity in identities
        for value in (
            f"{identity}_z_real_kohm",
            f"{identity}_minus_z_imag_kohm",
        )
    ]
    rows = [
        [float(row_index * 100 + column_index) for column_index in range(16)]
        for row_index in range(1, 4)
    ]
    processed.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(str(value) for value in row) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="EIS",
        legend_entries=["Current sample 3", "Current sample 4", "Current sample 5"],
    )
    contract_path = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "EIS.json"
    )
    return product, headers, rows, contract_path


def test_verified_eis_otpu_binding_uses_eight_sheets_e_g_and_ungrouped_plots(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_eis_product_and_table(tmp_path)

    result = _prepare_verified_eis_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    assert result["ok"] is True
    assert result["graph_page"] == "Graph1"
    assert result["book_name"] == "Book1"
    assert result["plot_type"] == "scatter"
    assert result["group_plots"] is False
    assert result["visible_plot_indices"] == [3, 4, 5]
    assert result["visible_legend_entries"] == [
        "Current sample 3",
        "Current sample 4",
        "Current sample 5",
    ]
    assert len(result["sheets"]) == 8
    assert result["xy_ranges"] == [
        {
            "x_col": 5,
            "y_col": 7,
            "row_from": 1,
            "row_to": 3,
            "sheet_index": index,
            "source_x_index": (index - 1) * 2,
            "source_y_index": (index - 1) * 2 + 1,
            "source_row_from": 1,
            "source_row_to": 3,
        }
        for index in range(1, 9)
    ]


@pytest.mark.parametrize(
    "case",
    ["seven_pairs", "duplicate_prefix", "missing_value", "ambiguous_legend"],
)
def test_verified_eis_otpu_binding_rejects_ambiguous_or_incomplete_sources(
    tmp_path: Path,
    case: str,
) -> None:
    product, headers, rows, contract_path = _verified_eis_product_and_table(tmp_path)
    if case == "seven_pairs":
        headers = headers[:-2]
        rows = [row[:-2] for row in rows]
    elif case == "duplicate_prefix":
        headers[2:4] = headers[0:2]
    elif case == "missing_value":
        rows[1][0] = math.nan
        rows[1][1] = math.nan
    else:
        product = replace(product, legend_entries=["one", "two", "three", "four"])

    result = _prepare_verified_eis_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    assert result["ok"] is False


def test_verified_eis_workbook_writes_eight_seven_column_sheets_with_e_g_data(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_eis_product_and_table(tmp_path)
    binding = _prepare_verified_eis_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    class WorkbookOps:
        def __init__(self) -> None:
            self.data_writes: list[tuple[str, str, list[list[float]]]] = []
            self.metadata_sheets: list[int] = []

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "created", {"book_name": book_name, "sheet_name": sheet_name})

        def add_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "added", {"book_name": book_name, "sheet_name": sheet_name})

        def set_worksheet_data(
            self,
            book_name: str,
            sheet_name: str,
            columns: list[list[float]],
            column_names: list[str] | None = None,
        ) -> OperationResult:
            self.data_writes.append((book_name, sheet_name, columns))
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            columns: list[dict[str, object]],
            *,
            sheet_index: int = 1,
        ) -> OperationResult:
            assert [column["column_index"] for column in columns] == [5, 7]
            self.metadata_sheets.append(sheet_index)
            return OperationResult(True, "metadata")

    operations = WorkbookOps()

    result = _populate_verified_otpu_workbook(
        operations,
        product,
        headers,
        rows,
        binding,
    )

    assert result["ok"] is True
    assert result["sheet_count"] == 8
    assert len(operations.data_writes) == 8
    assert operations.metadata_sheets == list(range(1, 9))
    for sheet_index, (_book, _sheet, columns) in enumerate(operations.data_writes, start=1):
        assert len(columns) == 7
        assert columns[4] == [row[(sheet_index - 1) * 2] for row in rows]
        assert columns[6] == [row[(sheet_index - 1) * 2 + 1] for row in rows]
        assert all(math.isnan(value) for value in columns[0])


def test_verified_eis_post_plot_order_preserves_snapshot_style_then_fits_current_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, _contract_path = _verified_eis_product_and_table(tmp_path)
    theme = tmp_path / "EIS.oth"
    theme.write_bytes(b"oth")
    events: list[str] = []

    class StyleOps:
        def apply_graph_theme(self, graph_name: str, theme_path: Path) -> OperationResult:
            assert graph_name == "Graph1"
            assert theme_path == theme
            events.append("oth")
            return OperationResult(True, "theme")

        def run_labtalk(self, command: str) -> OperationResult:
            assert "legend.x = layer.x.from + 0.8" in command
            assert "legend.y = layer.y.from + 0.8" in command
            events.append("template_legend_anchor")
            return OperationResult(True, "legend anchor")

    def snapshot_apply(*_args: object, **kwargs: object) -> bool:
        assert kwargs == {"apply_default_font": False, "apply_axis_titles": True}
        events.append("snapshot")
        return True

    def axis_apply(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("current_data_axis")
        return {"applied": True, "x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 5.0}

    def refresh(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("refresh")
        return {"applied": True}

    def legend(*args: object, **_kwargs: object) -> dict[str, object]:
        assert [str(value) for value in args[2].legend_entries] == [
            "Current sample 3",
            "Current sample 4",
            "Current sample 5",
        ]
        events.append("current_legend_3_5")
        return {"applied": True, "visible_plot_indices": [3, 4, 5]}

    monkeypatch.setattr("src.core.template_format_executor.apply_style_snapshot", snapshot_apply)
    monkeypatch.setattr("src.core.template_format_executor._apply_embedded_snapshot_data_axis_range", axis_apply)
    monkeypatch.setattr("src.core.template_format_executor._refresh_graph_for_export", refresh)
    monkeypatch.setattr("src.core.template_format_executor._finalize_reviewed_template_legend", legend)
    monkeypatch.setattr(
        "src.core.template_format_executor.apply_resolved_style_overrides",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("3 pt override must not run")),
    )

    result = _apply_verified_otpu_post_plot_style(
        StyleOps(),
        product,
        "Graph1",
        {
            "status": "extracted",
            "audit_numeric_values": {"legend.show": 1},
            "layout_values": {
                "page.width": 6432,
                "layer.x.from": 0,
                "layer.x.to": 10,
                "layer.y.from": 0,
                "layer.y.to": 5,
                "legend.x": 8,
                "legend.y": 4,
            },
        },
        ResolvedPlotStyle(line_width_pt=3.0),
        runtime_theme=theme,
    )

    assert result["ok"] is True
    assert result["apply_default_font"] is False
    assert events == [
        "oth",
        "snapshot",
        "current_data_axis",
        "template_legend_anchor",
        "refresh",
        "current_legend_3_5",
    ]


def test_verified_eis_conformance_allows_only_data_dependent_axis_and_legend_values() -> None:
    reference = {
        "layout_values": {
            "layer.x.from": 0,
            "legend.x": 5,
            "xb.y": -100,
            "yl.x": -200,
            "page.width": 6432,
        },
        "audit_numeric_values": {"legend.show": 1, "xb.bold": 1},
        "plot_line_widths": [0.5] * 8,
    }
    product = {
        "layout_values": {
            "layer.x.from": 2,
            "legend.x": 8,
            "xb.y": -120,
            "yl.x": -230,
            "page.width": 9999,
        },
        "audit_numeric_values": {"legend.show": 0, "xb.bold": 0},
        "plot_line_widths": [3.0] * 8,
    }

    adjusted = _verified_otpu_conformance_reference("EIS", reference, product)

    assert adjusted["layout_values"] == {
        "layer.x.from": 2,
        "legend.x": 8,
        "xb.y": -120,
        "yl.x": -230,
        "page.width": 6432,
    }
    assert adjusted["audit_numeric_values"] == {"legend.show": 0, "xb.bold": 1}
    assert adjusted["plot_line_widths"] == [0.5] * 8
    assert reference["layout_values"]["layer.x.from"] == 0


def _write_verified_epr_contract(path: Path, *, layout: str = "shared_x_y_columns") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contract_kind": "reference_opju_explicit_plot_binding",
                "contracts": [
                    {
                        "product_key": "EPR",
                        "status": "mapping_readback_complete",
                        "reference_opju_sha256": "0" * 64,
                        "graph_page": "EPR0601FULL",
                        "source_series_count": 3,
                        "source_schema": {
                            "status": "ready",
                            "layout": layout,
                            "source_csv_indices": [0, 1, 2, 3],
                            "group_plots": False,
                            "plot_type": "line",
                        },
                        "plots": [
                            {
                                "layer_index": 1,
                                "plot_index": index,
                                "x_dataset": "EPR_A",
                                "y_dataset": f"EPR_{chr(65 + index)}",
                                "row_from": 1,
                                "row_to": 3,
                                "source_series_index": index,
                                "semantic_role": f"trace_{index}",
                            }
                            for index in range(1, 4)
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _verified_epr_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[object]], Path]:
    processed = tmp_path / "epr_processed.csv"
    headers = ["magnetic_field", "BC", "CWO", "BOBC"]
    rows = [
        [324.0, 1.0, 2.0, 3.0],
        [324.1, 4.0, 5.0, 6.0],
        [324.2, 7.0, 8.0, 9.0],
    ]
    processed.write_text(
        ",".join(headers) + "\n" + "\n".join(",".join(str(value) for value in row) for row in rows) + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="EPR",
        legend_entries=["BC", "CWO", "BOBC"],
    )
    contract_path = tmp_path / "EPR.json"
    _write_verified_epr_contract(contract_path)
    return product, headers, rows, contract_path


def test_verified_epr_otpu_binding_uses_one_shared_x_sheet_and_columns_k_to_m(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_epr_product_and_table(tmp_path)

    result = _prepare_verified_epr_otpu_binding(
        product, headers, rows, contract_path=contract_path
    )

    assert result["ok"] is True
    assert result["graph_page"] == "EPR0601FULL"
    assert result["book_name"] == "EPR"
    assert result["group_plots"] is False
    assert result["xy_ranges"] == [
        {
            "x_col": 1,
            "y_col": 10 + index,
            "row_from": 1,
            "row_to": 3,
            "source_x_index": 0,
            "source_y_index": index,
            "source_row_from": 1,
            "source_row_to": 3,
        }
        for index in range(1, 4)
    ]


@pytest.mark.parametrize("case", ["extra_column", "missing_values", "wrong_contract_layout"])
def test_verified_epr_otpu_binding_rejects_noncontracted_shared_x_structure(
    tmp_path: Path,
    case: str,
) -> None:
    product, headers, rows, contract_path = _verified_epr_product_and_table(tmp_path)
    if case == "extra_column":
        headers.append("unexpected")
        rows = [row + [1.0] for row in rows]
    elif case == "missing_values":
        rows[1][2] = math.nan
    else:
        _write_verified_epr_contract(contract_path, layout="paired_xy_columns")

    result = _prepare_verified_epr_otpu_binding(
        product, headers, rows, contract_path=contract_path
    )

    assert result["ok"] is False


def test_verified_epr_workbook_adapter_reuses_shared_origin_transform(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, headers, rows, contract_path = _verified_epr_product_and_table(tmp_path)
    binding = _prepare_verified_epr_otpu_binding(
        product, headers, rows, contract_path=contract_path
    )
    calls: list[object] = []

    def transform(operations: object, transformed_product: ProductContext) -> dict[str, object]:
        calls.extend([operations, transformed_product])
        return {
            "ok": True,
            "book_name": "EPR_raw",
            "headers": ["magnetic_field", "BC", "CWO", "BOBC"],
            "origin_processing": {"required": True, "applied": True},
        }

    monkeypatch.setattr(
        "src.core.template_format_executor._prepare_template_epr_origin_processed_workbook",
        transform,
    )
    operations = object()
    result = _populate_verified_otpu_workbook(operations, product, headers, rows, binding)

    assert result["ok"] is True
    assert result["method"] == "shared_epr_origin_baseline_aav7_offset_transform"
    assert result["book_name"] == "EPR_raw"
    assert calls == [operations, product]


def test_verified_epr_export_validates_the_csv_reread_after_origin_transform(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, contract_path = _verified_epr_product_and_table(tmp_path)
    template = tmp_path / "EPR.otpu"
    theme = tmp_path / "EPR.oth"
    snapshot = tmp_path / "EPR_snapshot.json"
    template.write_bytes(b"otpu")
    theme.write_bytes(b"oth")
    snapshot.write_text(json.dumps({"status": "extracted"}), encoding="utf-8")
    asset = SimpleNamespace(
        runtime_asset_path=template,
        runtime_asset_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
        runtime_asset_kind="otpu",
        binding_contract_path=contract_path,
        graph_page="EPR0601FULL",
        style_snapshot_path=snapshot,
        format_theme_path=theme,
    )
    transformed_rows = [[324.0, 101.0, 102.0, 103.0], [324.1, 104.0, 105.0, 106.0], [324.2, 107.0, 108.0, 109.0]]
    captured: dict[str, object] = {}

    class Ops:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "new")

        def create_graph_from_xy_pairs_template(self, graph_name: str, *_args: object, **_kwargs: object) -> OperationResult:
            return OperationResult(True, "created", {"graph_name": graph_name})

        def save_project(self, path: Path) -> OperationResult:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"opju")
            return OperationResult(True, "saved")

        def load_project(self, _path: Path) -> OperationResult:
            return OperationResult(True, "loaded")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(True, "pages", {"pages": [{"name": "EPR0601FULL", "type": "graph"}]})

        def export_graph(self, _graph_name: str, path: Path, _format: str, **_kwargs: object) -> OperationResult:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"png")
            return OperationResult(True, "exported")

    def populate(*_args: object, **_kwargs: object) -> dict[str, object]:
        product.processed_data.write_text(
            "magnetic_field,BC,CWO,BOBC\n"
            + "\n".join(",".join(str(value) for value in row) for row in transformed_rows)
            + "\n",
            encoding="utf-8",
        )
        return {"ok": True, "book_name": "EPR_raw"}

    def validate(_key: str, rows: list[list[object]], *_args: object) -> dict[str, object]:
        captured["rows"] = rows
        return {"ok": True, "status": "matched"}

    def native_tif(_ops: object, _graph_name: str, path: Path, **_kwargs: object) -> dict[str, object]:
        path.write_bytes(b"tif")
        return {"ok": True, "evidence": {}}

    monkeypatch.setattr("src.core.template_format_executor._populate_verified_otpu_workbook", populate)
    monkeypatch.setattr("src.core.template_format_executor._apply_verified_otpu_post_plot_style", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr("src.core.template_format_executor._refresh_graph_for_export", lambda *_args, **_kwargs: {"applied": True})
    monkeypatch.setattr("src.core.template_format_executor.read_graph_style_snapshot", lambda *_args, **_kwargs: OpjuStyleSnapshot("product", "extracted", graph_page="EPR0601FULL"))
    monkeypatch.setattr("src.core.template_format_executor.compare_style_snapshots", lambda *_args, **_kwargs: SimpleNamespace(to_dict=lambda: {"status": "pass"}))
    monkeypatch.setattr("src.core.template_format_executor.read_graph_data_snapshot", lambda *_args, **_kwargs: {"status": "ready", "plots": []})
    monkeypatch.setattr("src.core.template_format_executor._validate_verified_current_data", validate)
    monkeypatch.setattr("src.core.template_format_executor._export_native_tif_with_physical_validation", native_tif)
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    result = _export_verified_graph_template_product_with_origin(
        Ops(), product, ResolvedPlotStyle(line_width_pt=3.0), asset, runtime_dir=runtime
    )

    assert result["ok"] is True
    assert captured["rows"] == transformed_rows


def test_verified_epr_dl_labels_are_current_bold_rich_text_and_fail_closed() -> None:
    class GraphObject:
        def __init__(self, name: str, text: str) -> None:
            self.Name = name
            self.Text = text
            self.Left = 100
            self.Top = 100
            self.Color = 1

    class GraphObjects:
        def __init__(self, objects: list[GraphObject]) -> None:
            self._objects = objects
            self.Count = len(objects)

        def __getitem__(self, name: str) -> GraphObject:
            for graph_object in self._objects:
                if graph_object.Name == name:
                    return graph_object
            raise KeyError(name)

        def Item(self, index: int) -> GraphObject:
            return self._objects[index]

    class Layer:
        def __init__(self, objects: list[GraphObject]) -> None:
            self.GraphObjects = GraphObjects(objects)

    class App:
        def __init__(self, layer: Layer) -> None:
            self._layer = layer

        def FindGraphLayer(self, _name: str) -> Layer:
            return self._layer

    class Ops:
        def __init__(self, layer: Layer) -> None:
            self.app = App(layer)

    objects = [
        GraphObject("DL1", "CuWO4"),
        GraphObject("DL2", "BiOBr"),
        GraphObject("DL3", "BiCu-10"),
    ]
    result = _update_verified_epr_label_objects(Ops(Layer(objects)), "EPR0601FULL", ["BC", "CWO", "BOBC"])

    assert result["applied"] is True
    assert [item.Text for item in objects] == ["\\b(BC)", "\\b(CWO)", "\\b(BOBC)"]
    assert [item.Left for item in objects] == [100, 100, 100]
    duplicate = _update_verified_epr_label_objects(
        Ops(Layer(objects + [GraphObject("DL1", "duplicate")])),
        "EPR0601FULL",
        ["BC", "CWO", "BOBC"],
    )
    assert duplicate == {
        "applied": False,
        "reason": "required_epr_label_missing_or_not_unique",
        "object_name": "DL1",
    }


def test_verified_epr_post_plot_order_is_otpu_then_oth_snapshot_axis_and_dl_labels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, _contract_path = _verified_epr_product_and_table(tmp_path)
    theme = tmp_path / "EPR.oth"
    theme.write_bytes(b"oth")
    events: list[str] = []

    class StyleOps:
        def apply_graph_theme(self, graph_name: str, theme_path: Path) -> OperationResult:
            assert graph_name == "EPR0601FULL"
            assert theme_path == theme
            events.append("oth")
            return OperationResult(True, "theme")

    def snapshot_apply(*_args: object, **kwargs: object) -> bool:
        assert kwargs == {"apply_default_font": False, "apply_axis_titles": True}
        events.append("snapshot")
        return True

    def axis_apply(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("current_data_axis")
        return {"applied": True, "x_min": 324.0, "x_max": 324.6}

    def labels(*args: object, **_kwargs: object) -> dict[str, object]:
        assert list(args[2]) == ["BC", "CWO", "BOBC"]
        events.append("dl_labels")
        return {"applied": True}

    monkeypatch.setattr("src.core.template_format_executor.apply_style_snapshot", snapshot_apply)
    monkeypatch.setattr("src.core.template_format_executor._apply_embedded_snapshot_data_axis_range", axis_apply)
    monkeypatch.setattr("src.core.template_format_executor._update_verified_epr_label_objects", labels)

    result = _apply_verified_otpu_post_plot_style(
        StyleOps(),
        product,
        "EPR0601FULL",
        {"status": "extracted"},
        ResolvedPlotStyle(line_width_pt=3.0),
        runtime_theme=theme,
    )

    assert result["ok"] is True
    assert events == ["oth", "snapshot", "current_data_axis", "dl_labels"]


def test_verified_epr_conformance_allows_only_current_x_range_and_x_title_position() -> None:
    reference = {
        "layout_values": {"layer.x.from": 324.0, "layer.x.to": 324.6, "xb.x": 324.3, "xb.y": -805.0, "layer.y.to": 1300.0},
        "audit_numeric_values": {"xb.bold": 1},
    }
    product = {
        "layout_values": {"layer.x.from": 325.0, "layer.x.to": 326.0, "xb.x": 325.5, "xb.y": -820.0, "layer.y.to": 1301.0},
        "audit_numeric_values": {"xb.bold": 1},
    }

    adjusted = _verified_otpu_conformance_reference("EPR", reference, product)

    assert adjusted["layout_values"] == {
        "layer.x.from": 325.0,
        "layer.x.to": 326.0,
        "xb.x": 325.5,
        "xb.y": -820.0,
        "layer.y.to": 1300.0,
    }


def _write_verified_pl_contract(
    path: Path,
    *,
    layout: str = "shared_x_y_columns",
    destinations: tuple[str, str, str] = ("B", "D", "F"),
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contract_kind": "reference_opju_explicit_plot_binding",
                "contracts": [
                    {
                        "product_key": "PL",
                        "status": "mapping_readback_complete",
                        "reference_opju_sha256": "0" * 64,
                        "graph_page": "EXJF",
                        "source_series_count": 3,
                        "source_schema": {
                            "status": "ready",
                            "layout": layout,
                            "source_csv_indices": [0, 1, 2, 3],
                            "group_plots": False,
                            "plot_type": "line",
                        },
                        "plots": [
                            {
                                "layer_index": 1,
                                "plot_index": index,
                                "x_dataset": "Book1_A",
                                "y_dataset": f"Book1_{destination}",
                                "row_from": 1,
                                "row_to": 351 if index != 2 else 176,
                                "source_series_index": index,
                                "semantic_role": f"trace_{index}",
                            }
                            for index, destination in enumerate(destinations, start=1)
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _verified_pl_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[object]], Path]:
    processed = tmp_path / "pl_processed.csv"
    headers = ["wavelength_nm", "BOBC_counts", "CWO_counts", "BC_counts"]
    rows = [
        [
            float(249 + index),
            float(index),
            float(index * 10) if index <= 176 else math.nan,
            float(index * 100),
        ]
        for index in range(1, 352)
    ]
    processed.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(str(value) for value in row) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="PL",
        legend_entries=["BOBC", "CWO", "BC"],
    )
    contract_path = tmp_path / "PL.json"
    _write_verified_pl_contract(contract_path)
    return product, headers, rows, contract_path


def test_verified_pl_otpu_binding_accepts_distinct_contiguous_bounds_and_maps_a_b_d_f(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_pl_product_and_table(tmp_path)

    result = _prepare_verified_pl_otpu_binding(
        product, headers, rows, contract_path=contract_path
    )

    assert result["ok"] is True
    assert result["graph_page"] == "EXJF"
    assert result["book_name"] == "PL"
    assert result["group_plots"] is False
    assert result["xy_ranges"] == [
        {
            "x_col": 1,
            "y_col": 2,
            "expected_x_col_letter": "A",
            "expected_y_col_letter": "B",
            "row_from": 1,
            "row_to": 351,
            "source_x_index": 0,
            "source_y_index": 1,
            "source_row_from": 1,
            "source_row_to": 351,
        },
        {
            "x_col": 1,
            "y_col": 4,
            "expected_x_col_letter": "A",
            "expected_y_col_letter": "D",
            "row_from": 1,
            "row_to": 176,
            "source_x_index": 0,
            "source_y_index": 2,
            "source_row_from": 1,
            "source_row_to": 176,
        },
        {
            "x_col": 1,
            "y_col": 6,
            "expected_x_col_letter": "A",
            "expected_y_col_letter": "F",
            "row_from": 1,
            "row_to": 351,
            "source_x_index": 0,
            "source_y_index": 3,
            "source_row_from": 1,
            "source_row_to": 351,
        },
    ]


@pytest.mark.parametrize(
    "case",
    ["wrong_layout", "wrong_destination", "header_mismatch", "legend_mismatch", "internal_gap"],
)
def test_verified_pl_otpu_binding_rejects_noncontracted_or_gapped_input(
    tmp_path: Path,
    case: str,
) -> None:
    product, headers, rows, contract_path = _verified_pl_product_and_table(tmp_path)
    if case == "wrong_layout":
        _write_verified_pl_contract(contract_path, layout="paired_xy_columns")
    elif case == "wrong_destination":
        _write_verified_pl_contract(contract_path, destinations=("B", "C", "F"))
    elif case == "header_mismatch":
        headers[2] = "wrong_counts"
    elif case == "legend_mismatch":
        product = replace(product, legend_entries=["BOBC", "CWO", "CWO"])
    else:
        rows[87][2] = math.nan

    result = _prepare_verified_pl_otpu_binding(
        product, headers, rows, contract_path=contract_path
    )

    assert result["ok"] is False


def test_verified_pl_workbook_writes_six_columns_and_a_b_d_f_metadata(tmp_path: Path) -> None:
    product, headers, rows, contract_path = _verified_pl_product_and_table(tmp_path)
    binding = _prepare_verified_pl_otpu_binding(
        product, headers, rows, contract_path=contract_path
    )

    class WorkbookOps:
        def __init__(self) -> None:
            self.data_write: tuple[str, str, list[list[float]]] | None = None
            self.metadata: list[dict[str, object]] | None = None

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "created", {"book_name": book_name, "sheet_name": sheet_name})

        def set_worksheet_data(
            self,
            book_name: str,
            sheet_name: str,
            columns: list[list[float]],
            column_names: list[str] | None = None,
        ) -> OperationResult:
            self.data_write = (book_name, sheet_name, columns)
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            columns: list[dict[str, object]],
            **_kwargs: object,
        ) -> OperationResult:
            self.metadata = columns
            return OperationResult(True, "metadata")

    operations = WorkbookOps()
    result = _populate_verified_otpu_workbook(operations, product, headers, rows, binding)

    assert result == {
        "ok": True,
        "method": "pl_shared_x_explicit_a_b_d_f_copy",
        "book_name": "PL",
        "sheet_count": 1,
    }
    assert operations.data_write is not None
    book_name, sheet_name, columns = operations.data_write
    assert (book_name, sheet_name) == ("PL", "Sheet1")
    assert len(columns) == 6
    assert columns[0] == [row[0] for row in rows]
    assert columns[1] == [row[1] for row in rows]
    assert all(math.isnan(value) for value in columns[2])
    assert columns[3] == [row[2] for row in rows]
    assert all(math.isnan(value) for value in columns[4])
    assert columns[5] == [row[3] for row in rows]
    assert operations.metadata is not None
    assert [column["column_index"] for column in operations.metadata] == [1, 2, 4, 6]
    assert [column["long_name"] for column in operations.metadata] == headers
    assert [column["type"] for column in operations.metadata] == [4, 1, 1, 1]


def test_verified_pl_post_plot_order_and_legend_helper_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, _contract_path = _verified_pl_product_and_table(tmp_path)
    theme = tmp_path / "PL.oth"
    theme.write_bytes(b"oth")
    events: list[str] = []

    class StyleOps:
        def apply_graph_theme(self, graph_name: str, theme_path: Path) -> OperationResult:
            assert graph_name == "EXJF"
            assert theme_path == theme
            events.append("oth")
            return OperationResult(True, "theme")

    def snapshot_apply(*_args: object, **kwargs: object) -> bool:
        assert kwargs == {"apply_default_font": False, "apply_axis_titles": True}
        events.append("snapshot")
        return True

    def legend(operations: object, graph_name: str, entries: list[str]) -> dict[str, object]:
        assert isinstance(operations, StyleOps)
        assert graph_name == "EXJF"
        assert entries == ["BOBC", "CWO", "BC"]
        events.append("current_legend")
        return {"applied": True, "entries": entries}

    monkeypatch.setattr("src.core.template_format_executor.apply_style_snapshot", snapshot_apply)
    monkeypatch.setattr("src.core.template_format_executor._update_verified_pl_legend", legend)

    result = _apply_verified_otpu_post_plot_style(
        StyleOps(),
        product,
        "EXJF",
        {"status": "extracted"},
        ResolvedPlotStyle(line_width_pt=3.0),
        runtime_theme=theme,
    )

    assert result["ok"] is True
    assert result["method"] == "otpu_then_oth_then_snapshot_then_current_legend"
    assert events == ["oth", "snapshot", "current_legend"]
    assert _update_verified_pl_legend(object(), "EXJF", ["BOBC", "CWO", "BC"]) == {
        "applied": False,
        "reason": "pl_legend_com_text_write_failed",
    }
    assert _update_verified_pl_legend(object(), "EXJF", ["BOBC", "CWO", "CWO"]) == {
        "applied": False,
        "reason": "pl_legend_requires_nonempty_unique_current_values",
    }


def test_verified_pl_legend_preserves_template_line_sample_spacing(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def write_text(
        operations: object,
        graph_name: str,
        object_name: str,
        text: str,
    ) -> bool:
        captured.update(
            operations=operations,
            graph_name=graph_name,
            object_name=object_name,
            text=text,
        )
        return True

    monkeypatch.setattr(
        "src.core.template_format_executor._set_origin_graph_object_text",
        write_text,
    )
    operations = object()

    result = _update_verified_pl_legend(
        operations,
        "EXJF",
        ["BOBC", "CWO", "BC"],
    )

    assert result["applied"] is True
    assert captured == {
        "operations": operations,
        "graph_name": "EXJF",
        "object_name": "Legend",
        "text": "\\l(1)\\b( BOBC)\r\n\\l(2)\\b( CWO)\r\n\\l(3)\\b( BC)",
    }


def test_verified_pl_conformance_allows_only_current_legend_text() -> None:
    reference = {
        "layout_values": {"page.width": 6983, "legend.x": 3954, "legend.y": 251},
        "audit_numeric_values": {"xb.bold": 1, "yl.bold": 1},
        "audit_string_values": {"legend.text$": r"\\l(1)\\b(BOBC)"},
    }
    product = {
        "layout_values": {"page.width": 9999, "legend.x": 3954, "legend.y": 251},
        "audit_numeric_values": {"xb.bold": 1, "yl.bold": 1},
        "audit_string_values": {"legend.text$": r"\\l(1)\\b(Current BOBC)"},
    }

    adjusted = _verified_otpu_conformance_reference("PL", reference, product)

    assert adjusted["layout_values"] == reference["layout_values"]
    assert adjusted["audit_numeric_values"] == reference["audit_numeric_values"]
    assert adjusted["audit_string_values"] == {
        "legend.text$": r"\\l(1)\\b(Current BOBC)",
    }
    assert reference["audit_string_values"]["legend.text$"] == r"\\l(1)\\b(BOBC)"


def test_adaptive_pl_conformance_allows_only_current_data_geometry_and_legend() -> None:
    reference = {
        "layout_values": {
            "page.width": 6983,
            "layer.x.from": 239.5,
            "layer.y.to": 70000,
            "legend.x": 555,
        },
        "audit_numeric_values": {"layer.x.from": 239.5, "xb.bold": 1},
        "audit_string_values": {"legend.text$": r"\\l(1)\\b(BOBC)"},
    }
    product = {
        "layout_values": {
            "page.width": 9999,
            "layer.x.from": 250,
            "layer.y.to": 80000,
            "legend.x": 580,
        },
        "audit_numeric_values": {"layer.x.from": 250, "xb.bold": 0},
        "audit_string_values": {"legend.text$": r"\\l(1)\\b(Current)"},
    }

    adjusted = _adaptive_pl_conformance_reference(reference, product)

    assert adjusted["layout_values"] == {
        "page.width": 6983,
        "layer.x.from": 250,
        "layer.y.to": 80000,
        "legend.x": 580,
    }
    assert adjusted["audit_numeric_values"] == {
        "layer.x.from": 250,
        "xb.bold": 1,
    }
    assert adjusted["audit_string_values"] == {
        "legend.text$": r"\\l(1)\\b(Current)",
    }


def _write_verified_photocurrent_contract(
    path: Path,
    *,
    layout: str = "paired_xy_columns",
    worksheet_layout: str = "one_sheet_three_independent_xy_pairs_at_i_j_m_n_q_r",
    source_indices: list[int] | None = None,
    group_plots: bool = False,
    destinations: tuple[tuple[str, str], ...] = (
        ("Book1_I", "Book1_J"),
        ("Book1_M", "Book1_N"),
        ("Book1_Q", "Book1_R"),
    ),
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contract_kind": "reference_opju_explicit_plot_binding",
                "contracts": [
                    {
                        "product_key": "photocurrent",
                        "status": "mapping_readback_complete",
                        "reference_opju_sha256": "0" * 64,
                        "graph_page": "Graph2",
                        "source_series_count": 3,
                        "source_schema": {
                            "status": "ready",
                            "layout": layout,
                            "worksheet_layout": worksheet_layout,
                            "source_csv_indices": (
                                [0, 1, 2, 3, 4, 5]
                                if source_indices is None
                                else source_indices
                            ),
                            "x_header_suffix": "_time_s",
                            "y_header_suffix": "_current_a",
                            "transform": "independent_photocurrent_xy_pairs_without_interpolation_smoothing_or_normalization",
                            "plot_type": "line",
                            "group_plots": group_plots,
                        },
                        "plots": [
                            {
                                "layer_index": 1,
                                "plot_index": index,
                                "x_dataset": x_dataset,
                                "y_dataset": y_dataset,
                                "row_from": 1,
                                "row_to": 5,
                                "source_series_index": index,
                                "semantic_role": f"material_{index}_photocurrent",
                            }
                            for index, (x_dataset, y_dataset) in enumerate(
                                destinations,
                                start=1,
                            )
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _verified_photocurrent_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[object]], Path]:
    labels = ["Sample Alpha", "Control-2", "Catalyst/Z"]
    headers = [
        "Sample_Alpha_time_s",
        "Sample_Alpha_current_a",
        "Control-2_time_s",
        "Control-2_current_a",
        "Catalyst_Z_time_s",
        "Catalyst_Z_current_a",
    ]
    rows = [
        [
            float(index),
            float(index) * 1e-7,
            float(index) if index <= 4 else math.nan,
            float(index) * 2e-7 if index <= 4 else math.nan,
            float(index) if index <= 3 else math.nan,
            float(index) * 3e-7 if index <= 3 else math.nan,
        ]
        for index in range(1, 6)
    ]
    processed = tmp_path / "photocurrent_processed.csv"
    processed.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(
            ",".join("" if not math.isfinite(float(value)) else str(value) for value in row)
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="photocurrent",
        legend_entries=labels,
    )
    contract_path = tmp_path / "photocurrent.json"
    _write_verified_photocurrent_contract(contract_path)
    return product, headers, rows, contract_path


def _photocurrent_reference_data_snapshot(
    rows: list[list[object]],
    *,
    series_count: int = 3,
) -> dict[str, object]:
    """Build the small structured reference snapshot used by axis-policy tests."""
    plots: list[dict[str, object]] = []
    for series_index in range(series_count):
        x_index = series_index * 2
        y_index = x_index + 1
        values = [
            (row[x_index], row[y_index])
            for row in rows
            if x_index < len(row)
            and y_index < len(row)
            and math.isfinite(float(row[x_index]))
            and math.isfinite(float(row[y_index]))
        ]
        plots.append(
            {
                "x_values": [float(x) for x, _y in values],
                "y_values": [float(y) for _x, y in values],
            }
        )
    return {"status": "ready", "plots": plots}


def _photocurrent_reference_style_snapshot() -> dict[str, object]:
    return {
        "status": "extracted",
        "layout_values": {
            "layer.x.from": 20.0,
            "layer.x.to": 250.0,
            "layer.y.from": -1e-8,
            "layer.y.to": 2e-7,
            "legend.x": 190.5859553123575,
            "legend.y": 1.6692024886877828e-7,
        },
        "audit_numeric_values": {"legend.show": 1.0},
    }


def _write_photocurrent_rows(
    path: Path,
    headers: list[str],
    rows: list[list[object]],
) -> None:
    path.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(
            ",".join(
                "" if not math.isfinite(float(value)) else str(value)
                for value in row
            )
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )


def test_verified_photocurrent_binding_maps_independent_pairs_with_distinct_bounds(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_photocurrent_product_and_table(tmp_path)

    result = _prepare_verified_photocurrent_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    assert result["ok"] is True
    assert result["graph_page"] == "Graph2"
    assert result["book_name"] == "Book1"
    assert result["group_plots"] is False
    assert result["xy_ranges"] == [
        {
            "x_col": 9,
            "y_col": 10,
            "expected_x_col_letter": "I",
            "expected_y_col_letter": "J",
            "row_from": 1,
            "row_to": 5,
            "source_x_index": 0,
            "source_y_index": 1,
            "source_row_from": 1,
            "source_row_to": 5,
        },
        {
            "x_col": 13,
            "y_col": 14,
            "expected_x_col_letter": "M",
            "expected_y_col_letter": "N",
            "row_from": 1,
            "row_to": 4,
            "source_x_index": 2,
            "source_y_index": 3,
            "source_row_from": 1,
            "source_row_to": 4,
        },
        {
            "x_col": 17,
            "y_col": 18,
            "expected_x_col_letter": "Q",
            "expected_y_col_letter": "R",
            "row_from": 1,
            "row_to": 3,
            "source_x_index": 4,
            "source_y_index": 5,
            "source_row_from": 1,
            "source_row_to": 3,
        },
    ]


def test_photocurrent_axis_policy_preserves_template_for_reference_arrays(
    tmp_path: Path,
) -> None:
    product, _headers, rows, _contract_path = _verified_photocurrent_product_and_table(tmp_path)
    operations = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(
        operations,
        "Graph2",
        product,
        reference_style_snapshot=_photocurrent_reference_style_snapshot(),
        reference_data_snapshot=_photocurrent_reference_data_snapshot(rows),
    )

    assert result["applied"] is True
    assert result["decision"] == "template_preserved"
    assert result["range_changed"] is False
    assert result["x_data_matches_reference"] is True
    assert result["y_data_matches_reference"] is True
    assert operations.axis_calls == []
    assert operations.commands == []


def test_photocurrent_axis_policy_changes_only_y_for_same_x_data(
    tmp_path: Path,
) -> None:
    product, headers, rows, _contract_path = _verified_photocurrent_product_and_table(tmp_path)
    reference_data = _photocurrent_reference_data_snapshot(rows)
    changed_rows = [list(row) for row in rows]
    for row in changed_rows:
        for column in (1, 3, 5):
            if math.isfinite(float(row[column])):
                row[column] = float(row[column]) + 1e-5
    _write_photocurrent_rows(product.processed_data, headers, changed_rows)
    operations = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(
        operations,
        "Graph2",
        product,
        reference_style_snapshot=_photocurrent_reference_style_snapshot(),
        reference_data_snapshot=reference_data,
    )

    assert result["applied"] is True
    assert result["decision"] == "adaptive_y"
    assert result["x_data_matches_reference"] is True
    assert result["y_data_matches_reference"] is False
    assert operations.axis_calls == [
        {
            "x_min": None,
            "x_max": None,
            "y_min": pytest.approx(result["y_min"]),
            "y_max": pytest.approx(result["y_max"]),
        }
    ]
    assert operations.commands
    assert "yl.y=(layer.y.from+layer.y.to)/2;" in operations.commands[-1]
    assert "xb.x=(layer.x.from+layer.x.to)/2;" not in operations.commands[-1]
    assert result["y_min"] == pytest.approx(1.0036e-5)
    assert result["y_max"] == pytest.approx(1.0964e-5)


def test_photocurrent_axis_policy_adapts_both_axes_with_eight_percent_padding(
    tmp_path: Path,
) -> None:
    product, headers, rows, _contract_path = _verified_photocurrent_product_and_table(tmp_path)
    reference_data = _photocurrent_reference_data_snapshot(rows)
    changed_rows = [list(row) for row in rows]
    for row in changed_rows:
        for column in (0, 2, 4):
            if math.isfinite(float(row[column])):
                row[column] = float(row[column]) * 2.0
        for column in (1, 3, 5):
            if math.isfinite(float(row[column])):
                row[column] = float(row[column]) + 1e-5
    _write_photocurrent_rows(product.processed_data, headers, changed_rows)
    operations = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(
        operations,
        "Graph2",
        product,
        reference_style_snapshot=_photocurrent_reference_style_snapshot(),
        reference_data_snapshot=reference_data,
    )

    assert result["applied"] is True
    assert result["decision"] == "adaptive_xy"
    assert result["x_data_matches_reference"] is False
    assert result["y_data_matches_reference"] is False
    assert operations.axis_calls == [
        {
            "x_min": pytest.approx(0.0),
            "x_max": pytest.approx(10.64),
            "y_min": pytest.approx(1.0036e-5),
            "y_max": pytest.approx(1.0964e-5),
        }
    ]
    assert operations.commands
    assert "xb.x=(layer.x.from+layer.x.to)/2;" in operations.commands[-1]
    assert "yl.y=(layer.y.from+layer.y.to)/2;" in operations.commands[-1]


def test_photocurrent_axis_policy_adapts_when_curve_count_changes(
    tmp_path: Path,
) -> None:
    product, headers, rows, _contract_path = _verified_photocurrent_product_and_table(tmp_path)
    reference_data = _photocurrent_reference_data_snapshot(rows)
    current_headers = headers[:4]
    current_rows = [list(row[:4]) for row in rows]
    _write_photocurrent_rows(product.processed_data, current_headers, current_rows)
    current_product = replace(product, legend_entries=["Sample Alpha", "Control-2"])
    operations = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(
        operations,
        "Graph2",
        current_product,
        reference_style_snapshot=_photocurrent_reference_style_snapshot(),
        reference_data_snapshot=reference_data,
    )

    assert result["applied"] is True
    assert result["decision"] == "adaptive_xy"
    assert result["series_count"] == 2
    assert operations.axis_calls[0]["x_min"] == pytest.approx(0.0)
    assert operations.axis_calls[0]["x_max"] == pytest.approx(5.32)
    assert operations.commands
    assert "xb.x=(layer.x.from+layer.x.to)/2;" in operations.commands[-1]
    assert "yl.y=(layer.y.from+layer.y.to)/2;" in operations.commands[-1]


def test_bet_axis_policy_preserves_scientific_x_range_and_adapts_current_y(
    tmp_path: Path,
) -> None:
    processed = tmp_path / "bet_adaptive.csv"
    processed.write_text(
        "BOBC_adsorption_relative_pressure_p_p0,"
        "BOBC_adsorption_quantity_adsorbed_cm3_g_stp,"
        "BOBC_desorption_relative_pressure_p_p0,"
        "BOBC_desorption_quantity_adsorbed_cm3_g_stp\n"
        "0.01,0.1,0.95,2.0\n"
        "0.50,1.0,0.50,1.2\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        legend_entries=["BOBC adsorption", "BOBC desorption"],
    )
    reference_style = {
        "layout_values": {
            "layer.x.from": 0.0,
            "layer.x.to": 1.0,
            "layer.y.from": -2.5,
            "layer.y.to": 32.5,
        }
    }
    reference_data = {
        "plots": [
            {"x_values": [0.1, 0.9], "y_values": [10.0, 20.0]}
            for _index in range(6)
        ]
    }
    operations = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(
        operations,
        "Graph5",
        product,
        reference_style_snapshot=reference_style,
        reference_data_snapshot=reference_data,
    )

    assert result["applied"] is True
    assert result["decision"] == "adaptive_y"
    assert result["reference_x_range_contains_current"] is True
    assert operations.axis_calls == [
        {
            "x_min": None,
            "x_max": None,
            "y_min": pytest.approx(-0.052),
            "y_max": pytest.approx(2.152),
        }
    ]
    assert "yl.y=(layer.y.from+layer.y.to)/2;" in operations.commands[-1]
    assert "xb.x=(layer.x.from+layer.x.to)/2;" not in operations.commands[-1]


def test_adaptive_bet_text_policy_restores_reviewed_titles_legend_size_and_current_labels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processed = tmp_path / "bet.csv"
    processed.write_text("x,y\n0,1\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        legend_entries=["BOBC adsorption", "BOBC desorption"],
    )
    written: dict[str, str] = {}

    def write_text(_operations, _graph, name, value):
        written[name] = value
        return True

    monkeypatch.setattr(
        "src.core.template_format_executor._set_origin_graph_object_text",
        write_text,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._format_preserved_line_sample_legend",
        lambda *_args, **kwargs: {
            "applied": True,
            "font_size": kwargs["font_size"],
        },
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._style_graph_object",
        lambda *_args, **_kwargs: True,
    )

    result = _apply_adaptive_bet_oth_json_text_policy(
        _FakeAxisOps(),
        "Graph5",
        product,
        ResolvedPlotStyle(),
        {"layout_values": {"legend.fsize": 36.0}},
    )

    assert result["applied"] is True
    assert result["axis_title_objects_styled"] is True
    assert result["y_title_rotation_restored"] is True
    assert result["font_size"] == 36
    assert written["XB"] == r"\b(Relative Pressure (P/Po))"
    assert written["YL"] == r"\b(Quantity Adsorbed (cm3/g STP))"
    assert r"\l(1)\b( BOBC (Adsorption))" in written["Legend"]
    assert r"\l(2)\b( BOBC (Desorption))" in written["Legend"]


def test_bet_axis_title_hard_gate_rejects_internal_csv_headers() -> None:
    headers = [
        "BOBC_adsorption_relative_pressure_p_p0",
        "BOBC_adsorption_quantity_adsorbed_cm3_g_stp",
    ]
    accepted = _validate_bet_axis_titles(
        {
            "audit_string_values": {
                "xb.text$": r"\b(Relative Pressure (P/Po))",
                "yl.text$": r"\b(Quantity Adsorbed (cm3/g STP))",
            }
        },
        headers,
    )
    rejected = _validate_bet_axis_titles(
        {
            "audit_string_values": {
                "xb.text$": r"\b(BOBC_adsorption_relative_pressure_p_p0)",
                "yl.text$": r"\b(BOBC_adsorption_quantity_adsorbed_cm3_g_stp)",
            }
        },
        headers,
    )

    assert accepted["ok"] is True
    assert rejected["ok"] is False
    assert rejected["internal_header_rejected"] is False


def test_verified_photocurrent_reopen_validation_requires_explicit_i_j_m_n_q_r_mapping(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_photocurrent_product_and_table(tmp_path)
    binding = _prepare_verified_photocurrent_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )
    plots = []
    for xy_range in binding["xy_ranges"]:
        source_from = int(xy_range["source_row_from"])
        source_to = int(xy_range["source_row_to"])
        source_x = int(xy_range["source_x_index"])
        source_y = int(xy_range["source_y_index"])
        selected = rows[source_from - 1 : source_to]
        plots.append(
            {
                "x_values": [row[source_x] for row in selected],
                "y_values": [row[source_y] for row in selected],
                "plot_row_from": int(xy_range["row_from"]),
                "plot_row_to": int(xy_range["row_to"]),
                "x_col_letter": xy_range["expected_x_col_letter"],
                "y_col_letter": xy_range["expected_y_col_letter"],
                "x_mapping_source": "graph_plot_mapping",
            }
        )

    matched = _validate_verified_current_data(
        "photocurrent",
        rows,
        binding["xy_ranges"],
        {"status": "ready", "plots": plots},
    )
    assert matched["ok"] is True

    plots[1]["x_col_letter"] = "I"
    plots[2]["x_mapping_source"] = "worksheet_designation_fallback"
    rejected = _validate_verified_current_data(
        "photocurrent",
        rows,
        binding["xy_ranges"],
        {"status": "ready", "plots": plots},
    )
    assert rejected["ok"] is False
    assert "plot 2 X dataset column differs" in rejected["reasons"]
    assert "plot 3 lacks explicit graph X mapping readback" in rejected["reasons"]


def test_verified_current_data_reports_nonfinite_reopened_values_without_raising() -> None:
    result = _validate_verified_current_data(
        "UV-vis DRS",
        [[260.0, 10.0], [261.0, 11.0]],
        [
            {
                "x_col": 1,
                "y_col": 2,
                "row_from": 1,
                "row_to": 2,
                "source_x_index": 0,
                "source_y_index": 1,
                "source_row_from": 1,
                "source_row_to": 2,
            }
        ],
        {
            "status": "ready",
            "plots": [
                {
                    "x_values": [260.0, None],
                    "y_values": [10.0, 11.0],
                    "plot_row_from": 1,
                    "plot_row_to": 2,
                }
            ],
        },
    )

    assert result["ok"] is False
    assert result["reasons"] == [
        "plot 1 reopened X/Y range contains a nonfinite value"
    ]


def test_photocurrent_axis_title_hard_gate_accepts_only_reviewed_scientific_titles() -> None:
    headers = [
        "Sample_Alpha_time_s",
        "Sample_Alpha_current_a",
        "Control-2_time_s",
        "Control-2_current_a",
    ]
    accepted = _validate_photocurrent_axis_titles(
        {
            "audit_string_values": {
                "xb.text$": r"\b(Time (s))",
                "yl.text$": r"\b(Photocurrent \(40))\f:g(\b(\f:Arial(μ)))\b(A\(41))",
            }
        },
        headers,
    )
    assert accepted["ok"] is True

    for x_title, y_title in (
        ("A", "B"),
        ("%(?X)", "%(?Y)"),
        ("Sample_Alpha_time_s", "Sample_Alpha_current_a"),
        ("Time (s)", "Current (A)"),
    ):
        rejected = _validate_photocurrent_axis_titles(
            {"audit_string_values": {"xb.text$": x_title, "yl.text$": y_title}},
            headers,
        )
        assert rejected["ok"] is False


def test_verified_photocurrent_legend_uses_only_current_sample_labels(
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}

    def set_text(_ops, _graph, _name, value):
        captured["text"] = value
        return True

    monkeypatch.setattr(
        "src.core.template_format_executor._set_origin_graph_object_text",
        set_text,
    )
    labels = ["New Sample 1", "Control-X", "Catalyst/Z"]
    result = _update_verified_photocurrent_legend(
        object(),
        "Graph2",
        labels,
    )

    assert result["applied"] is True
    assert result["entries"] == labels
    assert all(label in captured["text"] for label in labels)
    assert "BOBr" not in captured["text"]
    assert "CuWO" not in captured["text"]


@pytest.mark.parametrize(
    "case",
    [
        "wrong_layout",
        "wrong_worksheet_layout",
        "wrong_source_indices",
        "grouped",
        "wrong_destination",
        "extra_header",
        "header_mismatch",
        "duplicate_label",
        "internal_gap",
        "unpaired_value",
        "leading_blank",
        "extra_row_column",
    ],
)
def test_verified_photocurrent_binding_rejects_noncontracted_or_gapped_input(
    tmp_path: Path,
    case: str,
) -> None:
    product, headers, rows, contract_path = _verified_photocurrent_product_and_table(tmp_path)
    if case == "wrong_layout":
        _write_verified_photocurrent_contract(contract_path, layout="shared_x_y_columns")
    elif case == "wrong_worksheet_layout":
        _write_verified_photocurrent_contract(contract_path, worksheet_layout="three_sheets")
    elif case == "wrong_source_indices":
        _write_verified_photocurrent_contract(contract_path, source_indices=[0, 1, 2, 3])
    elif case == "grouped":
        _write_verified_photocurrent_contract(contract_path, group_plots=True)
    elif case == "wrong_destination":
        _write_verified_photocurrent_contract(
            contract_path,
            destinations=(("Book1_I", "Book1_J"), ("Book1_I", "Book1_N"), ("Book1_Q", "Book1_R")),
        )
    elif case == "extra_header":
        headers.append("extra")
    elif case == "header_mismatch":
        headers[3] = "wrong_current_a"
    elif case == "duplicate_label":
        product = replace(product, legend_entries=["BOBC", "CWO", "CWO"])
    elif case == "internal_gap":
        rows[1][2] = math.nan
        rows[1][3] = math.nan
    elif case == "unpaired_value":
        rows[1][3] = math.nan
    elif case == "leading_blank":
        rows[0][4] = math.nan
        rows[0][5] = math.nan
    else:
        rows[0].append(99.0)

    result = _prepare_verified_photocurrent_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    assert result["ok"] is False


def test_verified_photocurrent_workbook_writes_current_pairs_to_i_j_m_n_q_r(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_photocurrent_product_and_table(tmp_path)
    binding = _prepare_verified_photocurrent_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    class WorkbookOps:
        def __init__(self) -> None:
            self.data_write: tuple[str, str, list[list[float]]] | None = None
            self.metadata: list[dict[str, object]] | None = None

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(
                True,
                "created",
                {"book_name": book_name, "sheet_name": sheet_name},
            )

        def set_worksheet_data(
            self,
            book_name: str,
            sheet_name: str,
            columns: list[list[float]],
        ) -> OperationResult:
            self.data_write = (book_name, sheet_name, columns)
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            columns: list[dict[str, object]],
        ) -> OperationResult:
            self.metadata = columns
            return OperationResult(True, "metadata")

    operations = WorkbookOps()
    result = _populate_verified_otpu_workbook(
        operations,
        product,
        headers,
        rows,
        binding,
    )

    assert result == {
        "ok": True,
        "method": "photocurrent_independent_i_j_m_n_q_r_copy",
        "book_name": "Book1",
        "sheet_count": 1,
        "destination_pairs": [
            {"x_col": 9, "y_col": 10},
            {"x_col": 13, "y_col": 14},
            {"x_col": 17, "y_col": 18},
        ],
    }
    assert operations.data_write is not None
    book_name, sheet_name, columns = operations.data_write
    assert (book_name, sheet_name) == ("Book1", "Sheet1")
    assert len(columns) == 18
    destination_by_source = {0: 8, 1: 9, 2: 12, 3: 13, 4: 16, 5: 17}
    for source_index, destination_index in destination_by_source.items():
        expected = [float(row[source_index]) for row in rows]
        assert len(columns[destination_index]) == len(expected)
        for actual, wanted in zip(columns[destination_index], expected):
            assert (math.isnan(actual) and math.isnan(wanted)) or actual == wanted
    for reserved_index in set(range(18)) - set(destination_by_source.values()):
        assert all(math.isnan(value) for value in columns[reserved_index])
    assert operations.metadata == [
        {"column_index": 9, "long_name": "", "unit": "", "comment": "", "type": 4},
        {"column_index": 10, "long_name": "", "unit": "", "comment": "Sample Alpha", "type": 1},
        {"column_index": 13, "long_name": "", "unit": "", "comment": "", "type": 4},
        {"column_index": 14, "long_name": "", "unit": "", "comment": "Control-2", "type": 1},
        {"column_index": 17, "long_name": "", "unit": "", "comment": "", "type": 4},
        {"column_index": 18, "long_name": "", "unit": "", "comment": "Catalyst/Z", "type": 1},
    ]


def test_verified_photocurrent_style_uses_reviewed_oth_and_snapshot_and_preserves_reference_weight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, rows, _contract_path = _verified_photocurrent_product_and_table(tmp_path)
    calls: list[dict[str, object]] = []

    def snapshot_apply(*args: object, **kwargs: object) -> bool:
        calls.append({"args": args, "kwargs": kwargs})
        return True

    monkeypatch.setattr(
        "src.core.template_format_executor.apply_style_snapshot",
        snapshot_apply,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._update_verified_photocurrent_legend",
        lambda *_args, **_kwargs: {
            "applied": True,
            "entries": list(product.legend_entries),
        },
    )
    reference = _photocurrent_reference_style_snapshot()
    reference["audit_numeric_values"] = {
        "xb.bold": 0.0,
        "yl.bold": 0.0,
        "legend.show": 1.0,
    }
    reference["audit_string_values"] = {
        "xb.text$": r"\b(Time (s))",
        "yl.text$": r"\b(Photocurrent (μA))",
    }
    reference["plot_line_widths"] = [1500.0, 1500.0, 1500.0]

    theme = tmp_path / "photocurrent.oth"
    theme.write_bytes(b"oth")

    class ThemeOps:
        def apply_graph_theme(self, graph_name: str, theme_path: Path) -> OperationResult:
            assert graph_name == "Graph2"
            assert theme_path == theme
            return OperationResult(True, "theme applied")

        def set_axis_range(self, *_args: object, **_kwargs: object) -> OperationResult:
            pytest.fail("reference-equivalent data must preserve the template axes")

        def run_labtalk(self, _command: str) -> OperationResult:
            return OperationResult(True, "legend anchored")

    result = _apply_verified_otpu_post_plot_style(
        ThemeOps(),
        product,
        "Graph2",
        reference,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        runtime_theme=theme,
        reference_data=_photocurrent_reference_data_snapshot(rows),
    )

    assert result["ok"] is True
    assert result["method"] == "otpu_then_oth_then_snapshot_then_current_legend"
    assert result["format_theme_applied"] is True
    assert result["style_snapshot_applied"] is True
    assert result["apply_default_font"] is False
    assert result["apply_axis_titles"] is True
    assert result["axis_range_policy"]["decision"] == "template_preserved"
    assert result["legend_policy"] == {
        "applied": True,
        "entries": list(product.legend_entries),
    }
    assert calls[0]["kwargs"] == {
        "apply_default_font": False,
        "apply_axis_titles": True,
    }
    assert _apply_verified_otpu_post_plot_style(
        ThemeOps(),
        product,
        "Graph2",
        reference,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        runtime_theme=None,
    )["ok"] is False


def test_verified_photocurrent_dispatch_requires_snapshot_and_oth(
    tmp_path: Path,
) -> None:
    product, _headers, _rows, contract_path = _verified_photocurrent_product_and_table(tmp_path)
    template = tmp_path / "photocurrent.otpu"
    template.write_bytes(b"photocurrent-template")
    missing_snapshot = tmp_path / "missing_snapshot.json"
    asset = SimpleNamespace(
        runtime_asset_path=template,
        runtime_asset_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
        runtime_asset_kind="otpu",
        binding_contract_path=contract_path,
        graph_page="Graph2",
        style_snapshot_path=missing_snapshot,
        format_theme_path=tmp_path / "missing.oth",
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    missing = _export_verified_graph_template_product_with_origin(
        object(),
        product,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        asset,
        runtime_dir=runtime,
    )
    assert missing["ok"] is False
    assert "saved style snapshot" in missing["message"]

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "status": "extracted",
                "audit_numeric_values": {"xb.bold": 0.0, "yl.bold": 0.0},
                "audit_string_values": {
                    "xb.text$": r"\b(Time (s))",
                    "yl.text$": r"\b(Photocurrent (μA))",
                },
            }
        ),
        encoding="utf-8",
    )
    asset.style_snapshot_path = snapshot
    data_snapshot = tmp_path / "data_snapshot.json"
    data_snapshot.write_text(
        json.dumps({"status": "ready", "plots": []}),
        encoding="utf-8",
    )
    asset.data_snapshot_path = data_snapshot

    missing_theme = _export_verified_graph_template_product_with_origin(
        object(),
        product,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        asset,
        runtime_dir=runtime,
    )
    assert missing_theme["ok"] is False
    assert "reviewed OTH asset" in missing_theme["message"]

    theme = tmp_path / "photocurrent.oth"
    theme.write_bytes(b"oth")
    asset.format_theme_path = theme

    class StopAfterAssetChecks:
        def __init__(self) -> None:
            self.new_project_called = False

        def new_project(self) -> OperationResult:
            self.new_project_called = True
            return OperationResult(False, "intentional stop")

    operations = StopAfterAssetChecks()
    ready_assets = _export_verified_graph_template_product_with_origin(
        operations,
        product,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        asset,
        runtime_dir=runtime,
    )
    assert ready_assets["ok"] is False
    assert ready_assets["message"] == "intentional stop"
    assert operations.new_project_called is True


def test_verified_photocurrent_export_reports_reference_line_and_bold_policies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, contract_path = _verified_photocurrent_product_and_table(tmp_path)
    template = tmp_path / "photocurrent.otpu"
    template.write_bytes(b"photocurrent-template")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "status": "extracted",
                "audit_numeric_values": {"xb.bold": 0.0, "yl.bold": 0.0},
                "audit_string_values": {
                    "xb.text$": r"\b(Time (s))",
                    "yl.text$": r"\b(Photocurrent (μA))",
                },
                "plot_line_widths": [1500.0, 1500.0, 1500.0],
            }
        ),
        encoding="utf-8",
    )
    asset = SimpleNamespace(
        runtime_asset_path=template,
        runtime_asset_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
        runtime_asset_kind="otpu",
        binding_contract_path=contract_path,
        graph_page="Graph2",
        style_snapshot_path=snapshot,
        format_theme_path=(tmp_path / "photocurrent.oth"),
    )
    asset.format_theme_path.write_bytes(b"oth")
    data_snapshot = tmp_path / "data_snapshot.json"
    data_snapshot.write_text(
        json.dumps({"status": "ready", "plots": []}),
        encoding="utf-8",
    )
    asset.data_snapshot_path = data_snapshot

    class Ops:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "new")

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(
                True,
                "created",
                {"book_name": book_name, "sheet_name": sheet_name},
            )

        def set_worksheet_data(self, *_args: object, **_kwargs: object) -> OperationResult:
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(self, *_args: object, **_kwargs: object) -> OperationResult:
            return OperationResult(True, "metadata")

        def create_graph_from_xy_pairs_template(
            self,
            graph_name: str,
            *_args: object,
            **_kwargs: object,
        ) -> OperationResult:
            return OperationResult(True, "created", {"graph_name": graph_name})

        def apply_graph_theme(self, _graph_name: str, theme_path: Path) -> OperationResult:
            assert theme_path.is_file()
            return OperationResult(True, "theme applied")

        def save_project(self, path: Path) -> OperationResult:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"opju")
            return OperationResult(True, "saved")

        def load_project(self, _path: Path) -> OperationResult:
            return OperationResult(True, "loaded")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(
                True,
                "pages",
                {"pages": [{"name": "Graph2", "type": "graph"}]},
            )

        def export_graph(
            self,
            _graph_name: str,
            path: Path,
            _format: str,
            **_kwargs: object,
        ) -> OperationResult:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"png")
            return OperationResult(True, "exported")

    captured: dict[str, object] = {}

    def compare(*_args: object, **kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(to_dict=lambda: {"status": "pass"})

    def native_tif(
        _operations: object,
        _graph_name: str,
        path: Path,
        **_kwargs: object,
    ) -> dict[str, object]:
        path.write_bytes(b"tif")
        return {"ok": True, "evidence": {}}

    monkeypatch.setattr("src.core.template_format_executor.apply_style_snapshot", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "src.core.template_format_executor._apply_embedded_snapshot_data_axis_range",
        lambda *_args, **_kwargs: {
            "applied": True,
            "decision": "template_preserved",
            "range_changed": False,
        },
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._apply_saved_template_legend_anchor",
        lambda *_args, **_kwargs: {"applied": True},
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._update_verified_photocurrent_legend",
        lambda *_args, **_kwargs: {"applied": True},
    )
    monkeypatch.setattr("src.core.template_format_executor._refresh_graph_for_export", lambda *_args, **_kwargs: {"applied": True})
    monkeypatch.setattr(
        "src.core.template_format_executor.read_graph_style_snapshot",
        lambda *_args, **_kwargs: OpjuStyleSnapshot(
            "product",
            "extracted",
            graph_page="Graph2",
            audit_numeric_values={"xb.bold": 0.0, "yl.bold": 0.0},
            audit_string_values={
                "xb.text$": r"\b(Time (s))",
                "yl.text$": r"\b(Photocurrent (μA))",
                "legend.text$": r"\l(1)\b(Sample Alpha)",
            },
            plot_line_widths=[1500.0, 1500.0, 1500.0],
        ),
    )
    monkeypatch.setattr("src.core.template_format_executor.compare_style_snapshots", compare)
    monkeypatch.setattr(
        "src.core.template_format_executor.read_graph_data_snapshot",
        lambda *_args, **_kwargs: {"status": "ready", "plots": []},
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._validate_verified_current_data",
        lambda *_args, **_kwargs: {"ok": True, "status": "matched"},
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._export_native_tif_with_physical_validation",
        native_tif,
    )
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    result = _export_verified_graph_template_product_with_origin(
        Ops(),
        product,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        asset,
        runtime_dir=runtime,
    )

    assert result["ok"] is True
    assert result["origin_processing"]["style_contract"] == "preserve_exemplar_exact"
    assert result["origin_processing"]["post_plot_style"]["format_theme_applied"] is True
    assert result["line_width_policy_pt"] == 3.0
    assert result["axis_title_bold_policy"] is True
    assert captured == {
        "required_line_width_pt": 3.0,
        "require_axis_title_bold": True,
    }


def test_verified_photocurrent_conformance_allows_only_current_legend_text() -> None:
    reference = {
        "layout_values": {
            "page.width": 6432.0,
            "page.height": 4923.0,
            "layer.left": 17.89,
            "layer.top": 11.6,
            "layer.width": 68.19,
            "layer.height": 71.83,
            "layer.x.from": 20.0,
            "layer.x.to": 250.0,
            "layer.y.from": -1e-8,
            "layer.y.to": 2e-7,
            "legend.x": 247.5,
            "legend.y": 1.5e-7,
            "xb.x": 135.0,
            "yl.y": 9e-8,
        },
        "audit_numeric_values": {"xb.bold": 0.0, "yl.bold": 0.0},
        "audit_string_values": {
            "xb.text$": r"\b(Time (s))",
            "yl.text$": r"\b(Photocurrent (μA))",
            "legend.text$": r"\l(1)\b(Old sample)",
            "title.text$": "fixed",
        },
    }
    product = {
        "layout_values": {
            "page.width": 9999.0,
            "page.height": 7000.0,
            "layer.left": 99.0,
            "layer.top": 88.0,
            "layer.width": 77.0,
            "layer.height": 66.0,
            "layer.x.from": 0.0,
            "layer.x.to": 600.0,
            "layer.y.from": -2e-7,
            "layer.y.to": 8e-7,
            "legend.x": 999.0,
            "legend.y": 8e-7,
            "xb.x": 300.0,
            "yl.y": 3e-7,
        },
        "audit_numeric_values": {"xb.bold": 1.0, "yl.bold": 1.0},
        "audit_string_values": {
            "xb.text$": r"\b(Time (s))",
            "yl.text$": r"\b(Photocurrent (μA))",
            "legend.text$": r"\l(1)\b(Current sample)",
            "title.text$": "changed",
        },
    }

    adjusted = _verified_otpu_conformance_reference(
        "photocurrent",
        reference,
        product,
    )

    adjusted_layout = adjusted["layout_values"]
    for field in (
        "page.width",
        "page.height",
        "layer.left",
        "layer.top",
        "layer.width",
        "layer.height",
    ):
        assert adjusted_layout[field] == reference["layout_values"][field]
    for field in (
        "layer.x.from",
        "layer.x.to",
        "layer.y.from",
        "layer.y.to",
        "xb.x",
        "yl.y",
        "legend.x",
        "legend.y",
    ):
        assert adjusted_layout[field] == product["layout_values"][field]
    assert adjusted["audit_numeric_values"] == reference["audit_numeric_values"]
    assert adjusted["audit_string_values"] == {
        "xb.text$": r"\b(Time (s))",
        "yl.text$": r"\b(Photocurrent (μA))",
        "legend.text$": r"\l(1)\b(Current sample)",
        "title.text$": "fixed",
    }


def _write_verified_ftir_contract(
    path: Path,
    *,
    schema_updates: dict[str, object] | None = None,
    graph_page: str = "Graph3",
    destinations: tuple[tuple[str, str], ...] = (
        ("Book2_A", "Book2_B"),
        ("Book2_E", "Book2_F"),
        ("Book2_G", "Book2_H"),
    ),
) -> None:
    source_schema: dict[str, object] = {
        "status": "ready",
        "layout": "paired_xy_columns",
        "worksheet_layout": "one_sheet_three_independent_xy_pairs_with_reserved_cd",
        "source_csv_indices": [0, 1, 2, 3, 4, 5],
        "x_header_suffix": "_wavenumber_cm-1",
        "y_header_suffix": "_transmittance",
        "transform": "independent_ftir_xy_pairs_with_explicit_reference_vertical_offsets_without_interpolation_smoothing_or_normalization",
        "raw_to_plotted_vertical_offsets": [
            0.6992644978783592,
            0.48749646393210766,
            -0.174144271570014,
        ],
        "last_origin_curve_translate_annotations": [
            0.69926449787836,
            0.48749646393211,
            -0.62347949080622,
        ],
        "source_series_labels": ["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"],
        "plot_type": "line",
        "group_plots": False,
    }
    source_schema.update(schema_updates or {})
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contract_kind": "reference_opju_explicit_plot_binding",
                "contracts": [
                    {
                        "product_key": "FTIR",
                        "status": "mapping_readback_complete",
                        "reference_opju_sha256": "0" * 64,
                        "graph_page": graph_page,
                        "source_series_count": 3,
                        "source_schema": source_schema,
                        "plots": [
                            {
                                "layer_index": 1,
                                "plot_index": index,
                                "x_dataset": x_dataset,
                                "y_dataset": y_dataset,
                                "row_from": 1,
                                "row_to": 5,
                                "source_series_index": index,
                                "semantic_role": f"ftir_series_{index}",
                            }
                            for index, (x_dataset, y_dataset) in enumerate(
                                destinations,
                                start=1,
                            )
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _verified_ftir_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[object]], Path]:
    labels = ["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"]
    headers = [
        "BiOBr0.5Cl0.5_wavenumber_cm-1",
        "BiOBr0.5Cl0.5_transmittance",
        "CuWO4_wavenumber_cm-1",
        "CuWO4_transmittance",
        "BiCu-10_wavenumber_cm-1",
        "BiCu-10_transmittance",
    ]
    rows = [
        [
            1000.0 - index,
            1.0 + index * 0.01,
            1000.0 - index if index <= 4 else math.nan,
            1.2 + index * 0.01 if index <= 4 else math.nan,
            1000.0 - index if index <= 3 else math.nan,
            1.4 + index * 0.01 if index <= 3 else math.nan,
        ]
        for index in range(1, 6)
    ]
    processed = tmp_path / "FTIR_processed.csv"
    processed.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(
            ",".join(
                "" if not math.isfinite(float(value)) else str(value)
                for value in row
            )
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="FTIR",
        legend_entries=labels,
    )
    contract_path = tmp_path / "FTIR.json"
    _write_verified_ftir_contract(contract_path)
    return product, headers, rows, contract_path


def test_verified_ftir_binding_maps_final_xy_to_a_b_e_f_g_h_without_transform(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_ftir_product_and_table(tmp_path)

    result = _prepare_verified_ftir_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    assert result["ok"] is True
    assert result["graph_page"] == "Graph3"
    assert result["book_name"] == "Book2"
    assert result["reserved_columns"] == [3, 4]
    assert result["raw_to_plotted_vertical_offsets"] == [
        0.6992644978783592,
        0.48749646393210766,
        -0.174144271570014,
    ]
    assert [
        (
            value["x_col"],
            value["y_col"],
            value["expected_x_col_letter"],
            value["expected_y_col_letter"],
            value["row_to"],
            value["source_x_index"],
            value["source_y_index"],
        )
        for value in result["xy_ranges"]
    ] == [
        (1, 2, "A", "B", 5, 0, 1),
        (5, 6, "E", "F", 4, 2, 3),
        (7, 8, "G", "H", 3, 4, 5),
    ]
    assert _prepare_verified_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )["ok"] is True


@pytest.mark.parametrize(
    "case",
    [
        "wrong_net_offsets",
        "wrong_annotation_offsets",
        "wrong_contract_labels",
        "wrong_destination",
        "wrong_graph",
        "wrong_header",
        "wrong_current_labels",
        "internal_gap",
        "unpaired_value",
        "leading_blank",
    ],
)
def test_verified_ftir_binding_rejects_noncontracted_data(
    tmp_path: Path,
    case: str,
) -> None:
    product, headers, rows, contract_path = _verified_ftir_product_and_table(tmp_path)
    if case == "wrong_net_offsets":
        _write_verified_ftir_contract(
            contract_path,
            schema_updates={"raw_to_plotted_vertical_offsets": [0.0, 0.0, 0.0]},
        )
    elif case == "wrong_annotation_offsets":
        _write_verified_ftir_contract(
            contract_path,
            schema_updates={"last_origin_curve_translate_annotations": [0.0, 0.0, 0.0]},
        )
    elif case == "wrong_contract_labels":
        _write_verified_ftir_contract(
            contract_path,
            schema_updates={"source_series_labels": ["A", "B", "C"]},
        )
    elif case == "wrong_destination":
        _write_verified_ftir_contract(
            contract_path,
            destinations=(("Book2_A", "Book2_B"), ("Book2_C", "Book2_D"), ("Book2_G", "Book2_H")),
        )
    elif case == "wrong_graph":
        _write_verified_ftir_contract(contract_path, graph_page="Graph2")
    elif case == "wrong_header":
        headers[3] = "wrong_transmittance"
    elif case == "wrong_current_labels":
        product = replace(product, legend_entries=["CuWO4", "BiOBr0.5Cl0.5", "BiCu-10"])
    elif case == "internal_gap":
        rows[1][2] = math.nan
        rows[1][3] = math.nan
    elif case == "unpaired_value":
        rows[1][3] = math.nan
    else:
        rows[0][4] = math.nan
        rows[0][5] = math.nan

    assert _prepare_verified_ftir_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )["ok"] is False


def test_verified_ftir_workbook_preserves_reserved_columns_and_annotation_only_offsets(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_ftir_product_and_table(tmp_path)
    binding = _prepare_verified_ftir_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )

    class WorkbookOps:
        def __init__(self) -> None:
            self.data_write: tuple[str, str, list[list[float]]] | None = None
            self.metadata: list[dict[str, object]] | None = None

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "created", {"book_name": book_name, "sheet_name": sheet_name})

        def set_worksheet_data(
            self,
            book_name: str,
            sheet_name: str,
            columns: list[list[float]],
        ) -> OperationResult:
            self.data_write = (book_name, sheet_name, columns)
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            columns: list[dict[str, object]],
        ) -> OperationResult:
            self.metadata = columns
            return OperationResult(True, "metadata")

    operations = WorkbookOps()
    result = _populate_verified_otpu_workbook(
        operations,
        product,
        headers,
        rows,
        binding,
    )

    assert result["ok"] is True
    assert result["method"] == "ftir_independent_a_b_e_f_g_h_copy_with_reserved_c_d"
    assert result["raw_to_plotted_vertical_offsets"] == binding["raw_to_plotted_vertical_offsets"]
    assert operations.data_write is not None
    book_name, sheet_name, columns = operations.data_write
    assert (book_name, sheet_name) == ("Book2", "Sheet1")
    assert len(columns) == 8
    assert all(math.isnan(value) for value in columns[2])
    assert all(math.isnan(value) for value in columns[3])
    for source_index, destination_index in zip(range(6), (0, 1, 4, 5, 6, 7)):
        expected = [float(row[source_index]) for row in rows]
        for actual, wanted in zip(columns[destination_index], expected):
            assert (math.isnan(actual) and math.isnan(wanted)) or actual == wanted
    assert operations.metadata is not None
    assert [item["column_index"] for item in operations.metadata] == [1, 2, 5, 6, 7, 8]
    assert [item["type"] for item in operations.metadata] == [4, 1, 4, 1, 4, 1]
    assert [item["long_name"] for item in operations.metadata] == [""] * 6
    assert [item["unit"] for item in operations.metadata] == [""] * 6
    comments = {item["column_index"]: item["comment"] for item in operations.metadata}
    assert [comments[index] for index in (2, 6, 8)] == [
        "curve translate:\r\nB is moved vertically by 0.69926449787836",
        "curve translate:\r\nF is moved vertically by 0.48749646393211",
        "curve translate:\r\nH is moved vertically by -0.62347949080622",
    ]


def test_verified_ftir_reopen_validation_requires_a_b_e_f_g_h_mapping(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_ftir_product_and_table(tmp_path)
    binding = _prepare_verified_ftir_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract_path,
    )
    plots = []
    for xy_range in binding["xy_ranges"]:
        selected = rows[
            int(xy_range["source_row_from"]) - 1 : int(xy_range["source_row_to"])
        ]
        plots.append(
            {
                "x_values": [row[int(xy_range["source_x_index"])] for row in selected],
                "y_values": [row[int(xy_range["source_y_index"])] for row in selected],
                "plot_row_from": xy_range["row_from"],
                "plot_row_to": xy_range["row_to"],
                "x_col_letter": xy_range["expected_x_col_letter"],
                "y_col_letter": xy_range["expected_y_col_letter"],
                "x_mapping_source": "graph_plot_mapping",
            }
        )
    assert _validate_verified_current_data(
        "FTIR",
        rows,
        binding["xy_ranges"],
        {"status": "ready", "plots": plots},
    )["ok"] is True
    plots[1]["y_col_letter"] = "D"
    plots[2]["x_mapping_source"] = "worksheet_designation_fallback"
    rejected = _validate_verified_current_data(
        "FTIR",
        rows,
        binding["xy_ranges"],
        {"status": "ready", "plots": plots},
    )
    assert rejected["ok"] is False
    assert "plot 2 Y dataset column differs" in rejected["reasons"]
    assert "plot 3 lacks explicit graph X mapping readback" in rejected["reasons"]


def test_verified_ftir_style_uses_otpu_only_and_exact_reference_legend(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, _contract_path = _verified_ftir_product_and_table(tmp_path)
    captured: dict[str, str] = {}

    def set_text(
        _operations: object,
        graph_name: str,
        object_name: str,
        text: str,
    ) -> bool:
        captured.update(graph_name=graph_name, object_name=object_name, text=text)
        return True

    monkeypatch.setattr(
        "src.core.template_format_executor._set_origin_graph_object_text",
        set_text,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor.apply_style_snapshot",
        lambda *_args, **_kwargs: pytest.fail("FTIR must not apply its audit-only snapshot"),
    )
    result = _apply_verified_otpu_post_plot_style(
        object(),
        product,
        "Graph3",
        {"status": "extracted"},
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        runtime_theme=None,
    )

    assert result["ok"] is True
    assert result["method"] == "otpu_native_style_then_exact_reference_legend"
    assert result["format_theme_applied"] is False
    assert result["style_snapshot_applied"] is False
    assert result["legend_policy"]["line_samples_preserved"] is True
    assert captured == {
        "graph_name": "Graph3",
        "object_name": "Legend",
        "text": (
            "\\l(1)\\b(\\i( )\\c1(BiOBr)\\-(\\c1(0.5))\\c1(Cl)\\-(\\c1(0.5)))\r\n"
            "\\l(2)\\b(\\i( )CuWO\\-(4))\r\n"
            "\\l(3)\\b(\\i( )BiCu-10)"
        ),
    }
    theme = tmp_path / "FTIR.oth"
    theme.write_bytes(b"not-runtime")
    assert _apply_verified_otpu_post_plot_style(
        object(),
        product,
        "Graph3",
        {"status": "extracted"},
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        runtime_theme=theme,
    )["ok"] is False


def test_verified_ftir_dispatch_uses_snapshot_for_audit_but_does_not_require_oth(
    tmp_path: Path,
) -> None:
    product, _headers, _rows, contract_path = _verified_ftir_product_and_table(tmp_path)
    template = tmp_path / "FTIR.otpu"
    template.write_bytes(b"FTIR-template")
    snapshot = tmp_path / "FTIR_snapshot.json"
    asset = SimpleNamespace(
        runtime_asset_path=template,
        runtime_asset_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
        runtime_asset_kind="otpu",
        binding_contract_path=contract_path,
        graph_page="Graph3",
        style_snapshot_path=snapshot,
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    missing = _export_verified_graph_template_product_with_origin(
        object(),
        product,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        asset,
        runtime_dir=runtime,
    )
    assert missing["ok"] is False
    assert "saved style snapshot" in missing["message"]

    snapshot.write_text(
        json.dumps(
            {
                "status": "extracted",
                "audit_numeric_values": {"xb.bold": 0.0, "yl.bold": 0.0},
                "audit_string_values": {
                    "xb.text$": "\\b(Wavenumber)",
                    "yl.text$": "\\b(Transmittance (a.u.))",
                },
                "plot_line_widths": [1500.0, 1500.0, 1500.0],
            }
        ),
        encoding="utf-8",
    )

    class StopAfterAssetChecks:
        def __init__(self) -> None:
            self.new_project_called = False

        def new_project(self) -> OperationResult:
            self.new_project_called = True
            return OperationResult(False, "intentional stop")

    operations = StopAfterAssetChecks()
    no_oth = _export_verified_graph_template_product_with_origin(
        operations,
        product,
        ResolvedPlotStyle(line_width_pt=3.0, font_bold=True),
        asset,
        runtime_dir=runtime,
    )
    assert no_oth["ok"] is False
    assert no_oth["message"] == "intentional stop"
    assert operations.new_project_called is True


def test_verified_ftir_exact_style_policy_keeps_three_point_and_rich_text_bold() -> None:
    reference = {
        "audit_numeric_values": {"xb.bold": 0.0, "yl.bold": 0.0},
        "audit_string_values": {
            "xb.text$": "\\b(Wavenumber)",
            "yl.text$": "\\b(Transmittance (a.u.))",
        },
    }
    style = ResolvedPlotStyle(line_width_pt=3.0, font_bold=True)

    assert _verified_otpu_style_contract("FTIR") == "preserve_exemplar_exact"
    assert _verified_otpu_required_line_width_pt("FTIR", style) == 3.0
    assert _verified_otpu_axis_title_bold_policy("FTIR", reference) is True
    assert _update_verified_ftir_legend(
        object(),
        "Graph3",
        ["CuWO4", "BiOBr0.5Cl0.5", "BiCu-10"],
    )["applied"] is False


def _saved_bet_theme_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    _write_style_manifest(
        style_root,
        _runtime_validated_style_entry("BET", "Graph3", "format_themes/BET.oth"),
    )
    return project_root


def test_export_template_base_uses_project_format_theme_when_reference_opju_missing(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    _write_style_manifest(
        style_root,
        _runtime_validated_style_entry("BET", "Graph3", "format_themes/BET.oth"),
    )
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = _FakeCachedStyleOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is True
    assert result["origin_style_decision"]["selected_mode"] == "legacy-oth"
    assert result["template_format_plan"]["mode"] == "saved_format_theme"
    assert result["origin_processing"]["method"] == "saved_format_theme_apply"
    assert result["origin_processing"]["neutral_runtime"] is True
    assert fake.created_from_template is None
    assert fake.created_graphs
    assert fake.applied_themes
    assert fake.applied_themes[0].name == theme.name
    assert "codex" not in str(fake.applied_themes[0]).casefold()
    assert project_root not in fake.applied_themes[0].parents
    assert fake.saved_paths and fake.saved_paths[0] != product.origin_file
    assert fake.exported_paths and product.figure_tif not in fake.exported_paths
    assert product.origin_file.exists()
    assert product.figure_tif.exists()
    assert product.preview_png.exists()
    assert fake.closed is True


def test_export_template_base_blocks_acceptance_when_origin_close_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class CloseFailureOps(_FakeCachedStyleOps):
        def close(self) -> OperationResult:
            self.closed = True
            return OperationResult(False, "simulated close failure")

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = CloseFailureOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(),
        project_root=project_root,
    )

    assert result["ok"] is False
    assert "product acceptance is blocked" in result["message"]
    assert result["origin_runtime_cleanup"]["status"] == "failed"
    assert result["origin_runtime_cleanup"]["origin_close_ok"] is False
    assert "simulated close failure" in result["origin_runtime_cleanup"]["origin_close_message"]
    diagnostic = product.type_root / "debug" / "origin_runtime_cleanup_failure.json"
    assert json.loads(diagnostic.read_text(encoding="utf-8"))["status"] == "failed"


def test_export_template_base_blocks_acceptance_when_origin_close_raises(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class CloseRaisesOps(_FakeCachedStyleOps):
        def close(self) -> OperationResult:
            self.closed = True
            raise RuntimeError("simulated close exception")

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = CloseRaisesOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(),
        project_root=project_root,
    )

    assert result["ok"] is False
    assert result["origin_runtime_cleanup"]["origin_close_ok"] is False
    assert "simulated close exception" in result["origin_runtime_cleanup"]["origin_close_message"]


def test_export_template_base_blocks_acceptance_when_runtime_cleanup_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = _FakeCachedStyleOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr(
        "src.core.template_format_executor._cleanup_origin_runtime_directory",
        lambda _path: {
            "ok": False,
            "status": "retained_after_bounded_retries",
            "attempts": 20,
            "runtime_directory": "rdop_origin_test",
            "error": "simulated lock",
        },
    )

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(),
        project_root=project_root,
    )

    assert result["ok"] is False
    assert "product acceptance is blocked" in result["message"]
    assert result["origin_runtime_cleanup"]["origin_close_ok"] is True
    assert result["origin_runtime_cleanup"]["runtime_cleanup"]["ok"] is False
    assert result["origin_runtime_cleanup"]["runtime_cleanup"]["status"] == "retained_after_bounded_retries"


def test_export_template_base_prefers_project_format_theme_over_reference_opju(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    _write_style_manifest(
        style_root,
        _runtime_validated_style_entry("BET", "Graph3", "format_themes/BET.oth"),
    )
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = replace(_product(tmp_path, processed), legend_entries=["Adsorption", "Desorption"])
    product.reference_opju_copy.write_bytes(b"opju")
    fake = _FakeCachedStyleOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is True
    assert result["template_format_plan"]["mode"] == "saved_format_theme"
    assert result["origin_processing"]["method"] == "saved_format_theme_apply"
    assert len(fake.loaded_paths) == 1
    assert fake.loaded_paths[0] == fake.saved_paths[0]
    assert result["reopened_graph"] == fake.created_graphs[0]
    assert fake.created_from_template is None
    assert fake.applied_themes and fake.applied_themes[0].name == theme.name
    commands = "\n".join(fake.commands)
    assert "xb.fsize=36" not in commands
    assert "label -s -xb \\b(Relative Pressure);" in commands
    assert "label -s -yl \\b(Quantity Adsorbed);" in commands
    assert "plain_legend:entries:BET_template:Arial:22:Adsorption|Desorption" in commands
    assert "label -n rdop_plain_legend_1 -s \\b(Adsorption);" not in commands
    assert "legend.text$" not in commands
    assert "\\l(1)" not in commands


def test_saved_format_theme_exports_only_after_save_reload_and_readback(tmp_path: Path, monkeypatch) -> None:
    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = _FakeCachedStyleOps()

    def readback(_operations: object, graph_name: str, **_kwargs: object) -> OpjuStyleSnapshot:
        fake.events.append(f"readback:{graph_name}")
        return OpjuStyleSnapshot(
            source_opju=product.origin_file.name,
            status="extracted",
            graph_page=graph_name,
            graph_pages=[graph_name],
            layer_count=1,
            plot_count=2,
            plot_line_widths=[1500.0, 1500.0],
            audit_numeric_values={"xb.show": 1, "yl.show": 1, "xb.bold": 1, "yl.bold": 1},
            audit_string_values={"xb.text$": product.x_label, "yl.text$": product.y_label},
        )

    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr("src.core.template_format_executor.read_graph_style_snapshot", readback)
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is True
    assert result["reopened_graph"] == "BET_template"
    assert fake.events == [
        "new_project",
        "save:product.opju",
        "new_project",
        "load:product.opju",
        "list_pages",
        "readback:BET_template",
        "export:BET_template:product.png",
        "identity_reset",
        "export:BET_template:product.tif",
        "new_project",
    ]


def test_saved_format_theme_conformance_uses_real_snapshot_comparison(tmp_path: Path, monkeypatch) -> None:
    project_root = _saved_bet_theme_project(tmp_path)
    snapshot_path = project_root / "templates" / "origin_styles" / "snapshots" / "BET.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "status": "extracted",
                "layout_values": {"page.width": 200.0, "page.height": 100.0},
                "audit_numeric_values": {"xb.bold": 0, "yl.bold": 0},
                "audit_string_values": {"xb.text$": "X", "yl.text$": "Y"},
                "plot_line_widths": [1500.0],
            }
        ),
        encoding="utf-8",
    )
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = _FakeCachedStyleOps()
    product_snapshot = OpjuStyleSnapshot(
        source_opju="product.opju",
        status="extracted",
        graph_page="BET_template",
        graph_pages=["BET_template"],
        layout_values={"page.width": 100.0, "page.height": 100.0},
        plot_count=1,
        plot_line_widths=[1500.0],
        audit_numeric_values={"xb.bold": 0, "yl.bold": 0},
        audit_string_values={"xb.text$": "X", "yl.text$": "Y"},
    )
    from src.origin.conformance import compare_style_snapshots as real_compare_style_snapshots

    compare_kwargs: list[dict[str, object]] = []

    def compare_with_capture(*args: object, **kwargs: object):
        compare_kwargs.append(dict(kwargs))
        return real_compare_style_snapshots(*args, **kwargs)

    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr(
        "src.core.template_format_executor.read_graph_style_snapshot",
        lambda *_args, **_kwargs: product_snapshot,
    )
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        "src.core.template_format_executor.compare_style_snapshots",
        compare_with_capture,
    )

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(),
        project_root=project_root,
    )

    assert result["ok"] is True
    assert result["conformance"]["compared_fields"] >= 2
    assert result["conformance"]["matched_fields"] < result["conformance"]["compared_fields"]
    assert result["conformance"]["status"] == "fail"
    assert result["conformance"]["reference_source"] == "saved_style_snapshot"
    assert compare_kwargs == [
        {
            "required_line_width_pt": 3.0,
            "require_axis_title_bold": False,
        }
    ]
    assert result["exemplar_style"]["audit_numeric_values"]["xb.bold"] == 0


def test_saved_format_theme_blocks_merely_tagged_nonphysical_tiff(tmp_path: Path, monkeypatch) -> None:
    class WrongPixelCountOps(_FakeCachedStyleOps):
        def export_graph(self, graph_name: str, path: Path, export_format: str, **_kwargs: object) -> OperationResult:
            if export_format.casefold() in {"tif", "tiff"}:
                from PIL import Image

                self.exported_paths.append(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (30, 30), "white").save(path, format="TIFF", dpi=(600, 600))
                return OperationResult(True, "tagged but undersized")
            return super().export_graph(graph_name, path, export_format, **_kwargs)

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = WrongPixelCountOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="product.opju",
        status="extracted",
        graph_page="BET_template",
        graph_pages=["BET_template"],
        plot_count=1,
        plot_line_widths=[1500.0],
        audit_numeric_values={"xb.bold": 1, "yl.bold": 1},
        audit_string_values={"xb.text$": "X", "yl.text$": "Y"},
    )
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr("src.core.template_format_executor.read_graph_style_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(),
        project_root=project_root,
    )

    assert result["ok"] is False
    assert "pixel dimensions" in result["message"]
    assert not product.figure_tif.exists()


def test_saved_format_theme_reload_failure_blocks_export_and_copy(tmp_path: Path, monkeypatch) -> None:
    class ReloadFailureOps(_FakeCachedStyleOps):
        def load_project(self, path: Path) -> OperationResult:
            self.loaded_paths.append(Path(path))
            self.events.append(f"load:{Path(path).name}")
            return OperationResult(False, "simulated reload failure")

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = ReloadFailureOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is False
    assert "reload failure" in result["message"]
    assert fake.exported_paths == []
    assert not product.origin_file.exists()
    assert not product.preview_png.exists()
    assert not product.figure_tif.exists()


def test_saved_format_theme_page_list_failure_blocks_export_and_copy(tmp_path: Path, monkeypatch) -> None:
    class PageListFailureOps(_FakeCachedStyleOps):
        def list_worksheets(self) -> OperationResult:
            self.events.append("list_pages")
            return OperationResult(False, "simulated page list failure")

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = PageListFailureOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is False
    assert "page list failure" in result["message"]
    assert fake.exported_paths == []
    assert not product.origin_file.exists()
    assert not product.preview_png.exists()
    assert not product.figure_tif.exists()


def test_saved_format_theme_missing_reopened_graph_blocks_export_and_copy(tmp_path: Path, monkeypatch) -> None:
    class MissingGraphOps(_FakeCachedStyleOps):
        def list_worksheets(self) -> OperationResult:
            self.events.append("list_pages")
            return OperationResult(True, "listed", {"pages": [{"name": "UnexpectedGraph", "type": "graph"}]})

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = MissingGraphOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is False
    assert "was missing after project reload" in result["message"]
    assert result["expected_graph_page"] == "BET_template"
    assert result["available_graph_pages"] == ["UnexpectedGraph"]
    assert "reopened_graph" not in result
    assert fake.exported_paths == []
    assert not product.origin_file.exists()
    assert not product.preview_png.exists()
    assert not product.figure_tif.exists()


def test_saved_format_theme_ambiguous_reopened_graph_blocks_export_and_copy(tmp_path: Path, monkeypatch) -> None:
    class AmbiguousGraphOps(_FakeCachedStyleOps):
        def list_worksheets(self) -> OperationResult:
            self.events.append("list_pages")
            return OperationResult(
                True,
                "listed",
                {
                    "pages": [
                        {"name": "BET_template", "type": "graph"},
                        {"name": "BET_template", "type": "graph"},
                    ]
                },
            )

    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = AmbiguousGraphOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is False
    assert "was ambiguous after project reload" in result["message"]
    assert "reopened_graph" not in result
    assert fake.exported_paths == []
    assert not product.origin_file.exists()
    assert not product.preview_png.exists()
    assert not product.figure_tif.exists()


def test_saved_format_theme_reopened_readback_failure_blocks_export_and_copy(tmp_path: Path, monkeypatch) -> None:
    project_root = _saved_bet_theme_project(tmp_path)
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = _FakeCachedStyleOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr(
        "src.core.template_format_executor.read_graph_style_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("simulated reopened readback failure")),
    )

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is False
    assert "reopened readback failure" in result["message"]
    assert "reopened_graph" not in result
    assert fake.exported_paths == []
    assert not product.origin_file.exists()
    assert not product.preview_png.exists()
    assert not product.figure_tif.exists()


def test_export_template_base_uses_project_format_theme_for_exemplar_driven(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    theme.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    _write_style_manifest(
        style_root,
        _runtime_validated_style_entry("BET", "Graph3", "format_themes/BET.oth"),
    )
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n1,11\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    product.reference_opju_copy.write_bytes(b"opju")
    fake = _FakeCachedStyleOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        graph_page="Graph1",
        graph_pages=["Graph1"],
        layer_count=1,
        plot_count=1,
        plot_line_widths=[1500.0],
        audit_numeric_values={"xb.show": 1, "yl.show": 1, "xb.bold": 1, "yl.bold": 1},
        audit_string_values={"xb.text$": "X", "yl.text$": "Y"},
    )
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr("src.core.template_format_executor.extract_style_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(
        "src.core.template_format_executor.read_graph_style_snapshot",
        lambda _operations, graph_name, **_kwargs: replace(
            snapshot,
            graph_page=graph_name,
            graph_pages=[graph_name],
        ),
    )
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is True
    assert result["template_format_plan"]["mode"] == "saved_format_theme"
    assert [path.name for path in fake.applied_themes] == [theme.name]


def test_export_template_base_photocurrent_falls_back_when_template_workbook_is_locked(tmp_path: Path, monkeypatch) -> None:
    class LockedTemplateOps(_FakeCachedStyleOps):
        def replace_template_workbook_columns(self, _workbook_columns: dict[str, dict[int, list[float]]]) -> OperationResult:
            raise RuntimeError("simulated PutWorksheet memory lock")

    processed = tmp_path / "processed.csv"
    processed.write_text("time_s,BOBC,CWO,BiCu-10\n0,1,2,3\n1,1.5,2.5,3.5\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        product_key="photocurrent",
        slug="photocurrent_BOBC_exemplar",
        x_label="Time (s)",
        y_label="Current (A)",
        legend_entries=["BOBC", "CWO", "BiCu-10"],
    )
    product.reference_opju_copy.write_bytes(b"opju")
    fake = LockedTemplateOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        graph_page="Graph1",
        graph_pages=["Graph1"],
        layout_values={"page.width": 6432.0, "page.height": 4923.0, "layer.left": 17.89},
        layer_count=1,
        plot_count=3,
        plot_line_widths=[30.0, 30.0, 30.0],
        plot_colors=[4.0, 2.0, 1.0],
        audit_numeric_values={"xb.show": 1, "yl.show": 1, "xb.bold": 1, "yl.bold": 1, "legend.show": 1},
        audit_string_values={"xb.text$": "Time (s)", "yl.text$": "Current (A)"},
    )
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr("src.core.template_format_executor.extract_style_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr("src.core.template_format_executor.read_graph_style_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(legend_font_size=26),
        prefer_project_style_asset=False,
    )

    assert result["ok"] is True
    assert result["origin_processing"]["method"] == "opju_template_snapshot_fallback_graph"
    assert result["template_base_replacement"]["fallback_applied"] is True
    assert "simulated PutWorksheet memory lock" in result["origin_processing"]["fallback_reason"]
    assert fake.created_graphs
    assert product.origin_file.exists()
    assert product.figure_tif.exists()
    assert product.preview_png.exists()
    commands = "\n".join(fake.commands)
    assert "plain_legend:entries:photocurrent_BOBC_exempl:Arial:26:BOBC|CWO|BiCu-10" in commands
    assert "label -n rdop_plain_legend_1 -s \\b(BOBC);" not in commands
    assert "legend.text$" not in commands
    assert "\\l(" not in commands
    assert "label -s -xb \\b(Time (s));" in commands
    assert "label -s -yl \\b(Current (A));" in commands
    assert fake.closed is True


def test_export_template_base_blocks_embedded_snapshot_without_independent_reference_preview(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    assert not product.reference_opju_copy.exists()
    fake = _FakeCachedStyleOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="embedded:BET",
        status="embedded",
        graph_page="BET_template",
        graph_pages=["BET_template"],
        layout_values={"page.width": 6432.0, "page.height": 4923.0, "layer.left": 17.89},
        layer_count=1,
        plot_count=2,
        plot_line_widths=[1500.0, 1500.0],
        audit_numeric_values={"xb.show": 1, "yl.show": 1, "xb.bold": 1, "yl.bold": 1, "legend.show": 1},
        audit_string_values={"xb.text$": "Relative Pressure", "yl.text$": "Quantity Adsorbed"},
    )
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr("src.core.template_format_executor.read_graph_style_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(legend_font_size=26),
        prefer_project_style_asset=False,
        preserve_exemplar_style=True,
    )

    assert result["ok"] is False
    assert result["template_format_plan"]["mode"] == "embedded_template_snapshot"
    assert "requires an independent reference preview" in result["message"]
    assert result["reference_preview"] == {
        "required": True,
        "available": False,
        "generated_preview_reuse_blocked": True,
    }
    assert result["template_base_replacement"]["embedded_template_snapshot"] is True
    assert fake.created_graphs == []
    assert fake.exported_paths == []
    assert not product.origin_file.exists()
    assert not product.figure_tif.exists()
    assert not product.preview_png.exists()
    assert not product.reference_preview_png.exists()
    assert all(path.name != product.reference_opju_copy.name for path in fake.loaded_paths)
    assert fake.closed is True


def test_strip_raster_metadata_never_rewrites_native_tiff(tmp_path: Path) -> None:
    from PIL import Image, TiffImagePlugin

    figure = tmp_path / "figure.tif"
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[270] = r"D:\Codex Project\绉戠爺鏁版嵁澶勭悊\product.opju"
    Image.new("RGB", (8, 6), "white").save(figure, tiffinfo=tags)
    assert b"Codex Project" in figure.read_bytes()
    original = figure.read_bytes()

    warning = _strip_raster_metadata(figure, dpi=600)

    assert "disabled" in warning
    assert figure.read_bytes() == original


def test_cli_template_format_products_passes_options(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")
    output_root = tmp_path / "external"
    f_root = tmp_path / "f_drive"
    xps_root = tmp_path / "xps_reference"
    xps_non_root = tmp_path / "xps_non_reference"
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: TemplateFormatExecutorOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(output_root / "runs" / "20260607_210000_template_format_products"),
            "summary": {"product_count": 11, "success_count": 0, "blocked_count": 11, "failed_count": 0},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.core.template_format_executor.run_template_format_executor", fake_run)

    code = main(
        [
            "template-format-products",
            "--pairing",
            str(pairing),
            "--output-root",
            str(output_root),
            "--with-origin",
            "--timestamp",
            "20260607_210000",
            "--f-drive-template-root",
            str(f_root),
            "--xps-reference-template-root",
            str(xps_root),
            "--xps-non-in-situ-template-root",
            str(xps_non_root),
            "--exemplar-driven",
            "--compact-output",
            "--only-type",
            "XRD",
            "--origin-style-mode",
            "oth-json",
        ]
    )

    assert code == 1
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, TemplateFormatExecutorOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.f_drive_template_root == f_root
    assert options.xps_reference_template_root == xps_root
    assert options.xps_non_in_situ_template_root == xps_non_root
    assert options.with_origin is True
    assert options.asset_only is False
    assert options.exemplar_driven is True
    assert options.compact_output is True
    assert options.only_type == "XRD"
    assert options.origin_style_mode == "oth-json"


def test_cli_template_format_products_passes_asset_only(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: TemplateFormatExecutorOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(tmp_path / "out" / "runs" / "asset_only"),
            "summary": {
                "product_count": 1,
                "accepted_count": 0,
                "required_product_count": 1,
                "blocked_count": 1,
                "failed_count": 0,
            },
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.core.template_format_executor.run_template_format_executor", fake_run)

    code = main(["template-format-products", "--pairing", str(pairing), "--asset-only", "--only-type", "BET"])

    assert code == 1
    options = captured["options"]
    assert isinstance(options, TemplateFormatExecutorOptions)
    assert options.asset_only is True
    assert options.exemplar_driven is False


def test_asset_only_builder_options_disable_external_template_inputs(tmp_path: Path) -> None:
    options = TemplateFormatExecutorOptions(
        pairing_path=tmp_path / "pairing.json",
        asset_only=True,
        f_drive_template_root=tmp_path / "f_drive",
        xps_reference_template_root=tmp_path / "xps",
        xps_non_in_situ_template_root=tmp_path / "xps_non",
    )

    builder = build_template_product_builder_options(options)

    assert builder.asset_only is True
    assert builder.prefer_project_style_assets is True
    assert builder.external_reference_preview_comparison is False
    assert builder.f_drive_template_root is None
    assert builder.xps_reference_template_root is None
    assert builder.xps_non_in_situ_template_root is None


def test_default_builder_does_not_silently_switch_to_runtime_opju_replacement(
    tmp_path: Path,
) -> None:
    options = TemplateFormatExecutorOptions(pairing_path=tmp_path / "pairing.json")

    builder = build_template_product_builder_options(options)

    assert builder.exemplar_driven is False
    assert builder.prefer_project_style_assets is True
    assert builder.external_reference_preview_comparison is True
    assert builder.global_style_override == FINAL_TEMPLATE_STYLE_OVERRIDE


def test_exemplar_driven_builder_is_an_explicit_runtime_opju_baseline_mode(
    tmp_path: Path,
) -> None:
    options = TemplateFormatExecutorOptions(
        pairing_path=tmp_path / "pairing.json",
        exemplar_driven=True,
    )

    builder = build_template_product_builder_options(options)

    assert builder.exemplar_driven is True
    assert builder.prefer_project_style_assets is False
    assert builder.external_reference_preview_comparison is False
    assert builder.global_style_override == {}


def test_asset_only_uses_project_reference_opju_only_as_independent_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    style_root = project / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "BET.oth"
    project_reference = style_root / "reference_opju" / "BET.opju"
    theme.parent.mkdir(parents=True)
    project_reference.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    project_reference.write_bytes(b"reviewed-project-reference")
    _write_style_manifest(
        style_root,
        _runtime_validated_style_entry(
            "BET",
            "Graph1",
            "format_themes/BET.oth",
            template_opju="reference_opju/BET.opju",
        ),
    )
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,1\n1,2\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    product.reference_opju_copy.write_bytes(b"pairing-opju-must-not-be-used")
    reference_hash = project_reference.read_bytes()
    fake = _FakeCachedStyleOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="reference.opju",
        status="extracted",
        graph_page="Graph1",
        graph_pages=["Graph1"],
        layout_values={"page.width": 100.0, "page.height": 100.0},
        plot_count=1,
        plot_line_widths=[1500.0],
        audit_numeric_values={"xb.bold": 1, "yl.bold": 1},
        audit_string_values={"xb.text$": "X", "yl.text$": "Y"},
    )
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)
    monkeypatch.setattr(
        "src.core.template_format_executor.read_graph_style_snapshot",
        lambda _operations, graph_name, **_kwargs: replace(
            snapshot,
            graph_page=graph_name,
            graph_pages=[graph_name],
        ),
    )
    monkeypatch.setattr("src.core.template_format_executor._strip_raster_metadata", lambda *_args, **_kwargs: "")

    result = export_template_base_product_with_origin(
        product,
        ResolvedPlotStyle(),
        project_root=project,
        asset_only=True,
    )

    assert result["ok"] is True
    evidence = result["external_reference_preview"]
    assert evidence["reference_kind"] == "project_local_reference_opju"
    assert evidence["read_only_runtime_copy"] is True
    assert evidence["runtime_copy_write_protected"] is True
    assert evidence["used_as_product_base"] is False
    assert project_reference.read_bytes() == reference_hash
    assert all(path.name != product.reference_opju_copy.name for path in fake.loaded_paths)


def test_embedded_snapshot_eis_axis_range_uses_processed_csv_bounds(tmp_path: Path) -> None:
    processed = tmp_path / "eis.csv"
    processed.write_text(
        "\n".join(
            [
                "cleaned_z_real_ohm,cleaned_minus_z_imag_ohm,fit_z_real_ohm,draft_fit_minus_z_imag_ohm",
                "7,1,20,5",
                "16,20,98,32",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pairing = TargetPairing(
        product_key="EIS",
        data_type="EIS",
        xps_subtype="",
        data_root_label="test",
        data_paths=[],
        opju_root_label="test",
        reference_opju=tmp_path / "reference.opju",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="EIS",
        pairing=pairing,
        x_label="Z' (kΩ)",
        y_label="-Z'' (kΩ)",
        legend_entries=["BOBC"],
    )
    ops = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(ops, "Graph1", product)

    assert _processed_csv_plot_pairs(product, ["cleaned_x", "cleaned_y", "fit_x", "fit_y"]) == [(1, 2), (3, 4)]
    legend_policy = _plain_text_legend_policy(product)
    assert legend_policy["visible"] is True
    assert legend_policy["entries"] == ["BOBC"]
    assert legend_policy["entry_count"] == 1
    assert result["applied"] is True
    assert ops.axis_calls
    axis = ops.axis_calls[0]
    assert axis["x_min"] == 0.0
    assert axis["y_min"] == 0.0
    assert 105 < float(axis["x_max"]) < 106
    assert 34 < float(axis["y_max"]) < 35
    assert ops.commands == []


def test_xrd_direct_label_positions_follow_curve_offsets(tmp_path: Path) -> None:
    processed = tmp_path / "xrd.csv"
    processed.write_text(
        "two_theta_deg,BiOBr,BiOBr0.5Cl0.5,BiOCl\n"
        "5,4.6,2.3,0\n"
        "6,5.6,3.3,1\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="XRD")

    positions = _xrd_direct_label_positions(product, ["BiOBr", "BiOBr0.5Cl0.5", "BiOCl"])

    assert [label for label, _x, _y in positions] == ["BiOBr", "BiOBr0.5Cl0.5", "BiOCl"]
    assert all(52.0 <= x <= 65.6 for _label, x, _y in positions)
    assert [round(y, 2) for _label, _x, y in positions] == [5.05, 2.75, 0.45]


def test_embedded_snapshot_xrd_axis_range_uses_normalized_offset_sample_bounds(tmp_path: Path) -> None:
    processed = tmp_path / "xrd.csv"
    processed.write_text(
        "two_theta_deg,BOBC,CWO_PDF_04_009_6293_JCPDS_card_sticks,CWO\n"
        "5,1.1,0,2.2\n"
        "6,1.9,10,3.3\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="XRD")
    ops = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(ops, "Graph4", product)

    assert result["applied"] is True
    assert result["method"] == "xrd_normalized_offset_bounds_after_embedded_template_style"
    assert result["sample_column_count"] == 2
    axis = ops.axis_calls[0]
    assert axis["x_min"] is None
    assert axis["x_max"] is None
    assert axis["y_min"] == 0.0
    assert 5.6 < float(axis["y_max"]) < 5.8
    assert result["reference_sticks_present"] is True


def test_uvvis_drs_uses_current_paired_xy_axis_range(tmp_path: Path) -> None:
    processed = tmp_path / "uvvis.csv"
    processed.write_text(
        "BOBC_wavelength_nm,BOBC_drs_signal,CWO_wavelength_nm,CWO_drs_signal\n"
        "200,1,220,2\n1000,3,980,4\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="UV-vis DRS")
    ops = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(ops, "Graph1", product)

    assert result["applied"] is True
    assert result["method"] == "uvvis_current_xy_bounds_after_reviewed_style"
    assert result["x_min"] == 200.0
    assert result["x_max"] == 1000.0
    assert ops.axis_calls[0]["x_min"] == 200.0
    assert ops.axis_calls[0]["x_max"] == 1000.0
    assert ops.axis_calls[0]["y_min"] == 0.0
    assert float(ops.axis_calls[0]["y_max"]) > 4.0


def test_pl_axis_range_preserves_reviewed_bounds_when_current_data_fit(tmp_path: Path) -> None:
    processed = tmp_path / "pl.csv"
    processed.write_text(
        "wavelength_nm,BOBC_counts,CWO_counts,BC_counts\n"
        "250,100,200,300\n600,400,,500\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="PL")
    ops = _FakeAxisOps()
    style = {
        "layout_values": {
            "layer.x.from": 239.5,
            "layer.x.to": 610.5,
            "layer.y.from": -5000.0,
            "layer.y.to": 70000.0,
        }
    }

    result = _apply_embedded_snapshot_data_axis_range(
        ops,
        "EXJF",
        product,
        reference_style_snapshot=style,
    )

    assert result["applied"] is True
    assert result["decision"] == "template_preserved"
    assert result["range_changed"] is False
    assert ops.axis_calls == []


def test_epr_verified_field_data_overrides_legacy_template_axis_range(tmp_path: Path) -> None:
    processed = tmp_path / "epr.csv"
    processed.write_text(
        "magnetic_field,BC,CWO,BOBC\n324.0011,1,2,3\n333.9989,4,5,6\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="EPR")
    ops = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(ops, "EPR", product)

    assert result["method"] == "epr_verified_field_bounds_after_legacy_style_geometry"
    assert ops.axis_calls == [{"x_min": 324.0011, "x_max": 333.9989, "y_min": None, "y_max": None}]


def test_adaptive_epr_axis_contains_current_data_and_preserves_reviewed_y_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processed = tmp_path / "epr_adaptive.csv"
    processed.write_text(
        "magnetic_field,Sample_A,Sample_B\n"
        "324.0,900,300\n"
        "334.0,850,-100\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="EPR")
    ops = _FakeAxisOps()
    monkeypatch.setattr(
        "src.core.template_format_executor._position_adaptive_epr_axis_titles",
        lambda *_args, **_kwargs: {"applied": True, "positions": {"XB": {}, "YL": {}}},
    )
    snapshot = {
        "layout_values": {
            "layer.x.from": 324.02,
            "layer.x.to": 324.6,
            "layer.y.from": -500,
            "layer.y.to": 1300,
            "xb.x": 324.3111093023256,
            "xb.y": -805.0070721357849,
            "yl.x": 323.9861468308253,
            "yl.y": 400.2545968882603,
        }
    }

    result = _apply_adaptive_epr_data_axis_range(
        ops,
        "EPR",
        product,
        reference_style_snapshot=snapshot,
        style=ResolvedPlotStyle(),
    )

    assert result["applied"] is True
    assert result["y_range_decision"] == "reviewed_range_preserved"
    assert ops.axis_calls == [{"x_min": 323.8, "x_max": 334.2, "y_min": -500.0, "y_max": 1300.0}]
    assert result["axis_title_policy"]["applied"] is True


def test_adaptive_epr_variable_count_uses_native_current_labels(tmp_path: Path) -> None:
    processed = tmp_path / "epr_adaptive.csv"
    processed.write_text(
        "magnetic_field,Sample_A,Sample_B\n"
        "324.0,900,300\n"
        "325.0,880,280\n"
        "326.0,860,260\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="EPR",
        legend_entries=["Sample_A", "Sample_B"],
    )

    class Ops:
        def __init__(self) -> None:
            self.commands: list[str] = []
            self.labels: list[dict[str, object]] = []
            self.remove_names: list[str] = []

        def run_labtalk(self, command: str) -> OperationResult:
            self.commands.append(command)
            return OperationResult(True, "ok")

        def replace_graph_direct_labels(
            self,
            _graph_name: str,
            labels: list[dict[str, object]],
            *,
            remove_names: list[str],
            hide_legend: bool,
        ) -> OperationResult:
            assert hide_legend is True
            self.labels = labels
            self.remove_names = remove_names
            return OperationResult(True, "ok", {"objects": labels})

    ops = Ops()
    result = _apply_adaptive_epr_direct_labels(
        ops,
        "EPR",
        product,
        {
            "adaptive_direct_label_contract": {
                "fixed_reference_count": 3,
                "variable_x_fraction": 0.82,
                "variable_y_offset_fraction": 0.025,
                "font_name": "Arial",
                "font_size": 28,
            }
        },
        [[324.0, 900.0, 300.0], [325.0, 880.0, 280.0], [326.0, 860.0, 260.0]],
        [(1, 2), (1, 3)],
        {"x_min": 323.8, "x_max": 326.2, "y_min": -500.0, "y_max": 1300.0},
    )

    assert result["applied"] is True
    assert [value["name"] for value in ops.labels] == ["DL1", "DL2"]
    assert [value["text"] for value in ops.labels] == [r"\b(Sample_A)", r"\b(Sample_B)"]
    assert all("x" in value and "y" in value for value in ops.labels)
    assert "DL3" in ops.remove_names and "DL32" in ops.remove_names
    assert len(ops.commands) == 3
    assert "label -r Legend" in ops.commands[-1]


def test_adaptive_epr_reopened_styles_cycle_for_variable_curve_count() -> None:
    styles = [
        {"color": 10.0, "line_color": 10.0, "line_width_origin_units": 1500.0, "line_width_pt": 3.0, "line_style": 1.0, "symbol_shape": 0.0, "symbol_size": 9.0},
        {"color": 20.0, "line_color": 20.0, "line_width_origin_units": 1500.0, "line_width_pt": 3.0, "line_style": 1.0, "symbol_shape": 0.0, "symbol_size": 9.0},
        {"color": 30.0, "line_color": 30.0, "line_width_origin_units": 1500.0, "line_width_pt": 3.0, "line_style": 1.0, "symbol_shape": 0.0, "symbol_size": 9.0},
    ]
    reference = {
        "status": "ready",
        "plots": [
            {"layer_index": 1, "plot_index": index, "style": style}
            for index, style in enumerate(styles, start=1)
        ],
    }
    current = {
        "plots": [
            {"layer_index": 1, "plot_index": index, "style": dict(styles[(index - 1) % 3])}
            for index in range(1, 5)
        ]
    }

    assert _validate_adaptive_epr_reopened_plot_styles(
        reference,
        current,
        expected_plot_count=4,
    )["ok"] is True
    current["plots"][3]["style"]["line_width_pt"] = 2.0
    rejected = _validate_adaptive_epr_reopened_plot_styles(
        reference,
        current,
        expected_plot_count=4,
    )
    assert rejected["ok"] is False
    assert "line_width_pt" in rejected["message"]


def test_adaptive_epr_conformance_reference_cycles_styles_and_uses_current_data_geometry() -> None:
    style = {
        "plot_count": 3,
        "layer_count": 1,
        "plot_colors": [10, 20, 30],
        "plot_line_colors": [10, 20, 30],
        "plot_line_widths": [1500, 1500, 1500],
        "marker_shapes": [0, 0, 0],
        "marker_sizes": [9, 9, 9],
        "plot_visibility": [1, 1, 1],
        "layout_values": {
            "layer.y.from": -500,
            "layer.y.to": 1300,
            "legend.x": 0,
            "legend.y": 0,
            "legend.fsize": 0,
        },
        "audit_numeric_values": {"legend.x": 0, "legend.y": 0, "legend.fsize": 0},
    }
    data = {
        "plots": [
            {
                "layer_index": 1,
                "plot_index": index,
                "style": {
                    "color": color,
                    "line_color": color,
                    "line_width_origin_units": 1500,
                    "symbol_shape": 0,
                    "symbol_size": 9,
                },
            }
            for index, color in enumerate((10, 20, 30), start=1)
        ]
    }
    current = {
        "layout_values": {
            "layer.y.from": -600,
            "layer.y.to": 800,
            "legend.x": 333,
            "legend.y": 700,
            "legend.fsize": 14,
        }
    }

    result = _adaptive_epr_conformance_reference(style, data, 2, current)

    assert result["plot_count"] == 2
    assert result["plot_colors"] == [10, 20]
    assert result["plot_line_widths"] == [1500, 1500]
    assert result["plot_visibility"] == [1.0, 1.0]
    assert result["layout_values"]["layer.y.from"] == -600
    assert result["audit_numeric_values"]["legend.fsize"] == 14


def test_xrd_standard_card_keeps_every_selected_sample_plus_card(tmp_path: Path) -> None:
    processed = tmp_path / "xrd_card.csv"
    processed.write_text(
        "two_theta_deg,BOBC,BOBC600,bobc600,BOBC_BOBC15,BOBC_CWO15,CWO_PDF_04-009-8466_JCPDS_card_sticks\n"
        "5,5.9,5.5,4.3,2.6,1.4,0\n"
        "6,6.0,5.6,4.4,2.7,1.5,10\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="XRD",
        legend_entries=["BOBC", "BOBC600", "bobc600", "BOBC BOBC15", "BOBC CWO15"],
    )
    headers = [
        "two_theta_deg",
        "BOBC",
        "BOBC600",
        "bobc600",
        "BOBC_BOBC15",
        "BOBC_CWO15",
        "CWO_PDF_04-009-8466_JCPDS_card_sticks",
    ]

    assert _processed_csv_plot_pairs(product, headers) == [
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 5),
        (1, 6),
        (1, 7),
    ]
    assert _plain_text_legend_entries(product) == [
        "BOBC",
        "BOBC600",
        "bobc600",
        "BOBC BOBC15",
        "BOBC CWO15",
    ]


def test_plain_legend_anchor_avoids_data_dense_top_right_corner(tmp_path: Path) -> None:
    processed = tmp_path / "dense_top_right.csv"
    processed.write_text(
        "\n".join(
            [
                "x,y1,y2",
                "0,0,0",
                "6,2,1",
                "7,7,8",
                "8,8,9",
                "9,9,10",
                "10,10,9",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        legend_entries=["BOBC", "CWO"],
    )
    ops = _FakeAxisOps()

    policy = _apply_nonoverlap_plain_legend_anchor(ops, "Graph1", product, product.legend_entries)

    assert policy["applied"] is True
    assert policy["corner"] != "top-right"
    assert policy["point_count"] > 0
    assert any("legend -r; legend.show=1" in command for command in ops.commands)


def test_plain_legend_anchor_prefers_upper_blank_space_over_bottom_corners() -> None:
    anchor = _select_plain_legend_anchor(
        ["BiOBr", "CuWO4", "BiCu-10"],
        [(0.20, 0.15), (0.40, 0.25), (0.65, 0.18), (0.85, 0.30)],
    )

    assert str(anchor["corner"]).startswith("top")


def test_saved_template_legend_anchor_preserves_fraction_after_axis_change() -> None:
    ops = _FakeAxisOps()
    snapshot = {
        "audit_numeric_values": {"legend.show": 1},
        "layout_values": {
            "layer.x.from": 2.0,
            "layer.x.to": 4.0,
            "layer.y.from": -10.0,
            "layer.y.to": 30.0,
            "legend.x": 3.7,
            "legend.y": 25.0,
        }
    }

    policy = _apply_saved_template_legend_anchor(ops, "Graph1", snapshot)

    assert policy["applied"] is True
    assert policy["method"] == "saved_template_fractional_anchor_before_plain_text_replacement"
    assert abs(float(policy["x_fraction"]) - 0.85) < 1e-12
    assert abs(float(policy["y_fraction"]) - 0.875) < 1e-12
    assert "0.85 * (layer.x.to - layer.x.from)" in ops.commands[0]


def test_saved_template_legend_anchor_can_preserve_current_legend_text() -> None:
    ops = _FakeAxisOps()
    snapshot = {
        "audit_numeric_values": {"legend.show": 1},
        "layout_values": {
            "layer.x.from": -1.2,
            "layer.x.to": 0.8,
            "layer.y.from": 0.0,
            "layer.y.to": 28.0,
            "legend.x": -0.6,
            "legend.y": 25.0,
        },
    }

    policy = _apply_saved_template_legend_anchor(
        ops,
        "Graph2",
        snapshot,
        regenerate=False,
    )

    assert policy["applied"] is True
    assert policy["method"] == "saved_template_fractional_anchor_without_legend_regeneration"
    assert "legend -r" not in ops.commands[0]
    assert "legend.show=1" in ops.commands[0]


def test_saved_template_legend_anchor_restores_native_origin_geometry() -> None:
    class LegendObject:
        Name = "Legend"
        Left = 0
        Top = 0
        Width = 0
        Height = 0

    class GraphObjects:
        Count = 1

        def __init__(self, legend: LegendObject) -> None:
            self.legend = legend

        def Item(self, index: int) -> LegendObject:
            if index != 0:
                raise IndexError(index)
            return self.legend

    class Layer:
        def __init__(self, legend: LegendObject) -> None:
            self.GraphObjects = GraphObjects(legend)

    class App:
        def __init__(self, layer: Layer) -> None:
            self.layer = layer
            self.requested: list[str] = []

        def FindGraphLayer(self, name: str) -> Layer | None:
            self.requested.append(name)
            return self.layer if name == "[Graph2]Layer1" else None

    legend = LegendObject()
    ops = _FakeAxisOps()
    ops.app = App(Layer(legend))
    snapshot = {
        "audit_numeric_values": {"legend.show": 1},
        "graph_object_positions": {
            "Legend": {
                "left": 1037.0,
                "top": 541.0,
                "width": 2868.0,
                "height": 2210.0,
            }
        },
    }

    policy = _apply_saved_template_legend_anchor(
        ops,
        "Graph2",
        snapshot,
        regenerate=False,
    )

    assert policy == {
        "applied": True,
        "visible": True,
        "method": "saved_template_native_object_geometry",
        "geometry": {
            "left": 1037,
            "top": 541,
            "width": 2868,
            "height": 2210,
        },
        "saved_geometry": {
            "left": 1037,
            "top": 541,
            "width": 2868,
            "height": 2210,
        },
        "position_restored": True,
        "size_restored": True,
    }
    assert (legend.Left, legend.Top, legend.Width, legend.Height) == (
        1037,
        541,
        2868,
        2210,
    )
    assert ops.app.requested == ["[Graph2]Layer1"]
    assert all("legend -r" not in command for command in ops.commands)


def test_saved_template_legend_anchor_accepts_origin_native_auto_size() -> None:
    class AutoSizedLegend:
        Name = "Legend"

        def __init__(self) -> None:
            self.Left = 0
            self.Top = 0
            self._width = 2162
            self._height = 799

        @property
        def Width(self) -> int:
            return self._width

        @Width.setter
        def Width(self, _value: int) -> None:
            pass

        @property
        def Height(self) -> int:
            return self._height

        @Height.setter
        def Height(self, _value: int) -> None:
            pass

    class GraphObjects:
        Count = 1

        def __init__(self, legend: AutoSizedLegend) -> None:
            self.legend = legend

        def Item(self, index: int) -> AutoSizedLegend:
            if index != 0:
                raise IndexError(index)
            return self.legend

    class Layer:
        def __init__(self, legend: AutoSizedLegend) -> None:
            self.GraphObjects = GraphObjects(legend)

    class App:
        def __init__(self, layer: Layer) -> None:
            self.layer = layer

        def FindGraphLayer(self, name: str) -> Layer | None:
            return self.layer if name == "[Graph2]Layer1" else None

    legend = AutoSizedLegend()
    ops = _FakeAxisOps()
    ops.app = App(Layer(legend))
    snapshot = {
        "audit_numeric_values": {"legend.show": 1},
        "graph_object_positions": {
            "Legend": {"left": 1037, "top": 541, "width": 2868, "height": 2210}
        },
    }

    policy = _apply_saved_template_legend_anchor(
        ops,
        "Graph2",
        snapshot,
        regenerate=False,
    )

    assert policy["applied"] is True
    assert policy["method"] == "saved_template_native_object_geometry"
    assert policy["position_restored"] is True
    assert policy["size_restored"] is False
    assert policy["geometry"] == {
        "left": 1037,
        "top": 541,
        "width": 2162,
        "height": 799,
    }
    assert (legend.Left, legend.Top) == (1037, 541)


def test_executor_origin_rich_text_preserves_literal_scientific_slash() -> None:
    assert _origin_rich_text_for_labtalk(r"\b(Potential (V vs Ag/AgCl))") == (
        r"\b(Potential (V vs Ag/AgCl))"
    )


def test_saved_template_legend_anchor_rejects_hidden_placeholder_coordinates() -> None:
    ops = _FakeAxisOps()
    snapshot = {
        "audit_numeric_values": {"legend.show": 0},
        "layout_values": {
            "layer.x.from": 168.0,
            "layer.x.to": 154.0,
            "layer.y.from": 0.0,
            "layer.y.to": 1.0,
            "legend.x": 0.0,
            "legend.y": 0.0,
        },
    }

    policy = _apply_saved_template_legend_anchor(ops, "Graph1", snapshot)

    assert policy == {"applied": False, "reason": "saved_template_legend_not_visible"}
    assert ops.commands == []


def test_plain_legend_entries_remove_redundant_measurement_suffixes(tmp_path: Path) -> None:
    processed = tmp_path / "pl.csv"
    processed.write_text("wavelength_nm,BOBC_counts,CWO_counts,BC_counts\n250,1,2,3\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        product_key="PL",
        legend_entries=["BOBC counts", "CWO counts", "BC counts"],
    )

    assert _plain_text_legend_entries(product) == ["BOBC", "CWO", "BC"]


def test_xps_plain_legend_entries_keep_measured_samples_only(tmp_path: Path) -> None:
    processed = tmp_path / "xps.csv"
    processed.write_text(
        "\n".join(
            [
                "binding_energy_eV,BOBC_measured,BOBC_envelope,BOBC_component_1,BOBC_component_1_fill_baseline,BC_Dark_measured,BC_Dark_envelope",
                "200,1,1,0.5,0,0.8,0.8",
                "201,1.2,1.1,0.6,0,0.7,0.75",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pairing = TargetPairing(
        product_key="XPS_in_situ",
        data_type="XPS",
        xps_subtype="XPS_in_situ",
        data_root_label="test",
        data_paths=[],
        opju_root_label="test",
        reference_opju=tmp_path / "reference.opju",
    )
    product = replace(_product(tmp_path, processed), product_key="XPS_in_situ", pairing=pairing)

    entries = _plain_text_legend_entries(product)

    assert entries == ["BOBC", "BC Dark"]
    assert "component" not in " ".join(entries).casefold()
    assert "baseline" not in " ".join(entries).casefold()


def test_xrd_plain_legend_labels_use_text_objects_without_line_samples(tmp_path: Path) -> None:
    processed = tmp_path / "xrd.csv"
    processed.write_text("two_theta_deg,a\n5,1\n6,2\n", encoding="utf-8")
    product = replace(_product(tmp_path, processed), product_key="XRD")
    ops = _FakeAxisOps()

    policy = _apply_xrd_template_plain_legend_labels(
        ops,
        "Graph4",
        product,
        [r"\b( BiCu-30)", r"\b( BiOBr\-(0.5)Cl\-(0.5))"],
        ResolvedPlotStyle(font_family="Arial", legend_font_size=26),
    )

    joined = "\n".join(ops.commands)
    assert policy["applied"] is True
    assert "rdop_xrd_plain_legend_1" in joined
    assert "\\l(" not in joined
    assert 'font$="Arial"' in joined
    assert "fsize=26" in joined


def test_xrd_plain_legend_entries_ignore_exemplar_text_and_use_current_labels(tmp_path: Path) -> None:
    processed = tmp_path / "xrd.csv"
    processed.write_text("two_theta_deg,current_a,current_b\n5,1,2\n6,2,3\n", encoding="utf-8")
    product = replace(_product(tmp_path, processed), product_key="XRD", legend_entries=["Current A", "Current B"])
    exemplar = OpjuStyleSnapshot(
        source_opju="template.opju",
        status="extracted",
        graph_page="Graph4",
        audit_string_values={"legend.text$": r"\l(1) \b(Old Template A)\l(2) \b(Old Template B)"},
    )

    assert _plain_text_legend_entries(product, exemplar) == ["Current A", "Current B"]


def test_xrd_plain_label_text_cleans_exemplar_bold_wrappers() -> None:
    assert _xrd_plain_label_text("/b( BiCu-30)//") == r"\b( BiCu-30)"
    assert _xrd_plain_label_text(r"/b( BiOBr/-(0.5)Cl/-(0.5))//") == r"\b( BiOBr\-(0.5)Cl\-(0.5))"


def test_clean_exemplar_legend_entry_preserves_origin_bold_marker() -> None:
    assert _clean_exemplar_legend_entry(r"/l(1) /b( BiCu-30)//") == r"\b( BiCu-30)"


def test_xrd_standard_card_keeps_colored_line_sample_legend(tmp_path: Path) -> None:
    processed = tmp_path / "xrd_card.csv"
    processed.write_text(
        "two_theta_deg,BOBC,CWO_PDF_04_009_6293_JCPDS_card_sticks\n5,1,0\n6,2,10\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="XRD")

    policy = _plain_text_legend_policy(
        product,
        entries=["BOBC"],
        line_samples_removed=not _xrd_standard_card_keeps_line_sample_legend(product),
    )

    assert _xrd_standard_card_keeps_line_sample_legend(product) is True
    assert policy["line_samples_removed"] is False
    assert policy["method"] == "template_line_sample_legend_preserved"
    assert policy["xrd_standard_card_reference_sticks_present"] is True


def test_xrd_reference_card_notes_do_not_keep_colored_line_sample_legend(tmp_path: Path) -> None:
    processed = tmp_path / "xrd_no_card.csv"
    processed.write_text("two_theta_deg,BOBC,CWO\n5,1,2\n6,2,3\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        product_key="XRD",
        notes=["Reference-card content in an exemplar is recorded for review, not copied."],
    )

    policy = _plain_text_legend_policy(
        product,
        entries=["BOBC", "CWO"],
        line_samples_removed=not _xrd_standard_card_keeps_line_sample_legend(product),
    )

    assert _xrd_standard_card_keeps_line_sample_legend(product) is False
    assert policy["line_samples_removed"] is True
    assert policy["method"] == "plain_text_labels"
    assert policy["xrd_standard_card_reference_sticks_present"] is False


def test_preserved_line_sample_legend_is_formatted_without_removing_line_samples() -> None:
    ops = _FakeAxisOps()

    policy = _format_preserved_line_sample_legend(
        ops,
        "Graph4",
        ResolvedPlotStyle(font_family="Arial", legend_font_size=26),
    )

    joined = "\n".join(ops.commands)
    assert policy["applied"] is True
    assert policy["line_samples_preserved"] is True
    assert 'legend.font$="Arial"' in joined
    assert "legend.fsize=26" in joined
    assert "legend.bold=1" in joined
    assert "legend.border=0" in joined
    assert "legend.show=0" not in joined


def test_reviewed_eis_plot_policy_restores_template_visibility_legend_and_axis_titles(tmp_path: Path) -> None:
    class PlotOps(_FakeAxisOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return [f"Plot{index}" for index in range(1, 9)]

    product = replace(
        _product(tmp_path, tmp_path / "eis.csv"),
        product_key="EIS",
        legend_entries=["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"],
    )
    ops = PlotOps()
    snapshot = {
        "audit_string_values": {
            "xb.text$": r"\b(Z' \(40)k\f:g(Ω)\(41))",
            "yl.text$": r"\b(-Z'' \(40)k\f:g(Ω)\(41))",
        }
    }
    data_snapshot = {
        "plots": [
            {
                "style": {
                    "color": 26777852 + index,
                    "line_color": 24,
                    "line_width_pt": 0.5,
                    "line_style": 0,
                    "symbol_shape": 20,
                    "symbol_size": 12,
                    "fill_area": 1,
                    "fill_color": -9,
                    "border_color": 1,
                    "border_width": 0.5,
                }
            }
            for index in range(8)
        ]
    }

    policy = _apply_reviewed_template_plot_policy(
        ops,
        "Graph1",
        product,
        snapshot,
        ResolvedPlotStyle(font_family="Arial", legend_font_size=28),
        data_snapshot=data_snapshot,
    )

    joined = "\n".join(ops.commands)
    assert policy["applied"] is True
    assert policy["visible_indices"] == [3, 4, 5]
    assert "layer.plot1.show=0" in joined
    assert "layer.plot3.show=1" in joined
    assert "layer.plot8.show=0" in joined
    assert r"\l(3)\b(BiOBr\-(0.5)Cl\-(0.5))" in joined
    assert r"\l(4)\b(CuWO\-(4))" in joined
    assert "label -s -xb" in joined
    assert "label -s -yl" in joined
    assert "set Plot1 -wp 0.5" in joined
    assert "set Plot1 -l 0" in joined
    assert "set Plot1 -k 20" in joined
    assert "set Plot1 -pfb 1" in joined
    assert "set Plot1 -pfc -9" in joined
    assert "set Plot1 -c 26777852" in joined
    assert policy["plot_style"]["applied"] is True


def test_mott_candidate_guides_recover_reviewed_common_linear_window() -> None:
    data_snapshot_path = Path(__file__).parents[1] / "templates" / "origin_styles" / "data_snapshots" / "Mott_Schottky.json"
    data_snapshot = json.loads(data_snapshot_path.read_text(encoding="utf-8"))
    plots = data_snapshot["plots"][:3]
    headers = ["potential_v", "1500_one_over_c_squared", "2000_one_over_c_squared", "2500_one_over_c_squared"]
    rows = [
        [plots[0]["x_values"][index], *(plot["y_values"][index] for plot in plots)]
        for index in range(len(plots[0]["x_values"]))
    ]

    candidate = _mott_schottky_candidate_guides(headers, rows, series_count=3)

    assert candidate["linear_interval_candidate"] == [0.15, 0.25]
    assert candidate["linear_fit_point_count"] == 3
    assert abs(float(candidate["shared_x_intercept_candidate"]) - (-1.04)) < 0.01
    assert len(candidate["constrained_slopes"]) == 3
    assert min(candidate["constrained_r_squared"]) > 0.98


def _verified_raman_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[object]], Path]:
    data_snapshot_path = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "data_snapshots"
        / "Raman.json"
    )
    data_snapshot = json.loads(data_snapshot_path.read_text(encoding="utf-8"))
    plots = sorted(data_snapshot["plots"], key=lambda value: int(value["x_col_index"]))
    labels = ["BiOBr0.5Cl0.5", "CuWO4", "BiCu-30"]
    headers = [
        header
        for label in labels
        for header in (
            f"{label}_raman_shift_cm-1",
            f"{label}_intensity",
        )
    ]
    series = []
    for plot in plots:
        pairs = [
            [x_value, y_value]
            for x_value, y_value in zip(plot["x_values"], plot["y_values"])
            if x_value is not None and y_value is not None
        ]
        series.append(pairs)
    row_count = max(len(values) for values in series)
    rows: list[list[object]] = []
    for row_index in range(row_count):
        row: list[object] = []
        for values in series:
            row.extend(values[row_index] if row_index < len(values) else [None, None])
        rows.append(row)
    processed = tmp_path / "raman.csv"
    processed.write_text("placeholder", encoding="utf-8")
    pairing = TargetPairing(
        product_key="Raman",
        data_type="Raman",
        xps_subtype="",
        data_root_label="test",
        data_paths=[],
        opju_root_label="test",
        reference_opju=tmp_path / "reference.opju",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="Raman",
        pairing=pairing,
        legend_entries=labels,
        x_label="Raman shift (cm-1)",
        y_label="Intensity (a.u.)",
    )
    contract = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "Raman.json"
    )
    return product, headers, rows, contract


def test_verified_raman_binding_preserves_source_order_and_two_layer_mapping(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_raman_product_and_table(tmp_path)

    result = _prepare_verified_raman_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    assert result["ok"] is True
    assert result["graph_page"] == "Graph2"
    assert result["book_name"] == "Book2"
    assert [
        (value["layer_index"], value["x_col"], value["y_col"])
        for value in result["xy_ranges"]
    ] == [(1, 1, 2), (1, 5, 6), (2, 3, 4)]
    assert [
        (value["source_x_index"], value["source_y_index"])
        for value in result["xy_ranges"]
    ] == [(0, 1), (4, 5), (2, 3)]
    assert _processed_csv_plot_pairs(product, headers) == [(1, 2), (3, 4), (5, 6)]
    assert _prepare_verified_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )["ok"] is True


def test_verified_raman_workbook_copies_all_six_columns_without_transform(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_raman_product_and_table(tmp_path)
    binding = _prepare_verified_raman_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    class WorkbookOps:
        def __init__(self) -> None:
            self.columns: list[list[float]] = []
            self.metadata: list[dict[str, object]] = []

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "created", {"book_name": book_name, "sheet_name": sheet_name})

        def set_worksheet_data(
            self,
            _book_name: str,
            _sheet_name: str,
            columns: list[list[float]],
        ) -> OperationResult:
            self.columns = columns
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            metadata: list[dict[str, object]],
        ) -> OperationResult:
            self.metadata = metadata
            return OperationResult(True, "metadata")

    ops = WorkbookOps()
    result = _populate_verified_otpu_workbook(ops, product, headers, rows, binding)

    assert result["ok"] is True
    assert result["method"] == "raman_independent_a_b_c_d_e_f_copy_without_numeric_transform"
    assert len(ops.columns) == 6
    for column_index in range(6):
        expected = [
            float(row[column_index]) if row[column_index] is not None else math.nan
            for row in rows
        ]
        assert all(
            (math.isnan(actual) and math.isnan(reference)) or actual == reference
            for actual, reference in zip(ops.columns[column_index], expected)
        )
    assert [value["type"] for value in ops.metadata] == [4, 1, 4, 1, 4, 1]


def _verified_mott_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[float]], Path]:
    data_snapshot_path = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "data_snapshots"
        / "Mott_Schottky.json"
    )
    data_snapshot = json.loads(data_snapshot_path.read_text(encoding="utf-8"))
    plots = data_snapshot["plots"]
    headers = [
        "potential_v",
        "1500_one_over_c_squared",
        "2000_one_over_c_squared",
        "2500_one_over_c_squared",
        "3000_one_over_c_squared",
        "3500_one_over_c_squared",
    ]
    rows = [
        [plots[0]["x_values"][index], *(plot["y_values"][index] for plot in plots)]
        for index in range(len(plots[0]["x_values"]))
    ]
    processed = tmp_path / "mott.csv"
    processed.write_text(
        "\n".join(
            [",".join(headers), *[",".join(str(value) for value in row) for row in rows]]
        )
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="Mott-Schottky",
        legend_entries=[
            "1500Hz BiOBr0.5Cl0.5",
            "2000Hz BiOBr0.5Cl0.5",
            "2500Hz BiOBr0.5Cl0.5",
            "3000Hz BiOBr0.5Cl0.5",
            "3500Hz BiOBr0.5Cl0.5",
        ],
        plot_type="line+symbol",
    )
    contract = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "Mott_Schottky.json"
    )
    return product, headers, rows, contract


def test_verified_mott_otpu_binding_maps_shared_x_to_reviewed_d_to_l_columns(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_mott_product_and_table(tmp_path)

    result = _prepare_verified_mott_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    assert result["ok"] is True
    assert result["graph_page"] == "Graph2"
    assert result["page_mask_override"] == 0
    assert result["group_plots"] is False
    assert result["book_name"] == "Book1"
    assert all(value["book_name"] == "Book1" for value in result["xy_ranges"])
    assert all(value["sheet_index"] == 1 for value in result["xy_ranges"])
    assert all(value["layer_index"] == 1 for value in result["xy_ranges"])
    assert [(value["x_col"], value["y_col"]) for value in result["xy_ranges"]] == [
        (5, 4),
        (5, 6),
        (7, 8),
        (9, 10),
        (11, 12),
    ]
    assert [value["source_y_index"] for value in result["xy_ranges"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert [value["connect"] for value in result["plot_format_contracts"]] == [
        0,
        0,
        0,
        0,
        0,
    ]
    dispatched = _prepare_verified_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )
    assert dispatched["ok"] is True


def test_verified_mott_workbook_uses_native_columns_and_reference_mask_state(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_mott_product_and_table(tmp_path)
    binding = _prepare_verified_mott_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    class WorkbookOps:
        def __init__(self) -> None:
            self.columns: list[list[float]] = []
            self.metadata: list[dict[str, object]] = []
            self.masks: list[tuple[int, list[int]]] = []

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(
                True,
                "created",
                {"book_name": book_name, "sheet_name": sheet_name},
            )

        def set_worksheet_data(
            self,
            _book_name: str,
            _sheet_name: str,
            columns: list[list[float]],
        ) -> OperationResult:
            self.columns = columns
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            metadata: list[dict[str, object]],
        ) -> OperationResult:
            self.metadata = metadata
            return OperationResult(True, "metadata")

        def set_worksheet_column_mask_rows(
            self,
            _book_name: str,
            column_index: int,
            masked_rows: list[int],
        ) -> OperationResult:
            self.masks.append((column_index, list(masked_rows)))
            return OperationResult(True, "masked")

    operations = WorkbookOps()
    result = _populate_verified_otpu_workbook(
        operations,
        product,
        headers,
        rows,
        binding,
    )

    assert result["ok"] is True
    assert result["masked_rows"] == [1, 2, 3, 4, 5]
    assert result["masked_y_columns"] == [4, 6, 8, 10]
    assert len(operations.columns) == 12
    assert operations.columns[3] == [row[1] for row in rows]
    assert operations.columns[4] == [row[0] for row in rows]
    assert operations.columns[5] == [row[2] for row in rows]
    assert operations.columns[6] == [row[0] for row in rows]
    assert operations.columns[7] == [row[3] for row in rows]
    assert operations.columns[8] == [row[0] for row in rows]
    assert operations.columns[9] == [row[4] for row in rows]
    assert operations.columns[10] == [row[0] for row in rows]
    assert operations.columns[11] == [row[5] for row in rows]
    assert operations.masks == [
        (4, [1, 2, 3, 4, 5]),
        (6, [1, 2, 3, 4, 5]),
        (8, [1, 2, 3, 4, 5]),
        (10, [1, 2, 3, 4, 5]),
    ]


def test_adaptive_mott_masks_each_current_y_column_without_masking_numeric_zero() -> None:
    class MaskOps:
        def __init__(self) -> None:
            self.masks: list[tuple[int, list[int]]] = []

        def set_worksheet_column_mask_rows(
            self,
            _book_name: str,
            column_index: int,
            masked_rows: list[int],
        ) -> OperationResult:
            self.masks.append((column_index, list(masked_rows)))
            return OperationResult(True, "masked")

    operations = MaskOps()
    rows = [
        [-0.05, 1.0, 2.0],
        [-7.45e-9, 1.1, 2.1],
        [0.05, 1.2, 2.2],
    ]

    result = _apply_mott_schottky_source_masks(
        operations,
        "Mott",
        rows,
        [(1, 2), (1, 3)],
    )

    assert result["applied"] is True
    assert operations.masks == [(2, [1]), (3, [1])]


def test_reviewed_mott_policy_draws_data_dependent_candidate_guides(tmp_path: Path) -> None:
    data_snapshot_path = Path(__file__).parents[1] / "templates" / "origin_styles" / "data_snapshots" / "Mott_Schottky.json"
    data_snapshot = json.loads(data_snapshot_path.read_text(encoding="utf-8"))
    plots = data_snapshot["plots"]
    processed = tmp_path / "mott.csv"
    headers = ["potential_v", "1500_one_over_c_squared", "2000_one_over_c_squared", "2500_one_over_c_squared"]
    lines = [",".join(headers)]
    for index in range(len(plots[0]["x_values"])):
        lines.append(
            ",".join(
                str(value)
                for value in [plots[0]["x_values"][index], *(plot["y_values"][index] for plot in plots[:3])]
            )
        )
    processed.write_text("\n".join(lines) + "\n", encoding="utf-8")

    class PlotOps(_FakeAxisOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return [f"Plot{index}" for index in range(1, 6)]

    product = replace(
        _product(tmp_path, processed),
        product_key="Mott-Schottky",
        legend_entries=["1500Hz BiOBr0.5Cl0.5", "2000Hz BiOBr0.5Cl0.5", "2500Hz BiOBr0.5Cl0.5"],
    )
    ops = PlotOps()
    style_snapshot = {
        "layout_values": {
            "layer.x.from": -1.2,
            "layer.x.to": 0.78,
            "layer.y.to": 2.7e9,
            "legend.fsize": 28,
        },
        "audit_string_values": {"xb.text$": "Potential", "yl.text$": "C^-2"},
    }

    policy = _apply_reviewed_template_plot_policy(
        ops,
        "Graph2",
        product,
        style_snapshot,
        ResolvedPlotStyle(font_family="Arial", legend_font_size=28),
        data_snapshot=data_snapshot,
    )

    joined = "\n".join(ops.commands)
    guides = policy["mott_schottky_candidate_guides"]
    assert guides["applied"] is True
    assert guides["manual_check_required"] is True
    assert guides["annotation"] == "-1.04 V"
    assert policy["legend_font_size"] == 28
    assert "legend.fsize=28" in joined
    assert "draw -n rdop_mott_fit_1 -w 3 -d 1 -l" in joined
    assert "rdop_mott_fit_1.color=color(128,128,128)" in joined
    assert "label -a" not in joined
    assert "label -n rdop_mott_x_intercept" in joined
    assert "rdop_mott_x_intercept" in joined


def test_refresh_graph_for_export_forces_document_update_and_repaint() -> None:
    ops = _FakeAxisOps()

    result = _refresh_graph_for_export(ops, "Graph1")

    assert result["applied"] is True
    assert ops.commands == ['win -a "Graph1"; doc -uw;', 'win -a "Graph1"; draw -uwi;']


def test_origin_graph_object_text_reassignment_refreshes_cached_legend() -> None:
    class GraphObject:
        Text = "Sheet1"

    graph_object = GraphObject()

    class GraphObjects:
        def __getitem__(self, name: str) -> GraphObject:
            assert name == "Legend"
            return graph_object

    graph_objects = GraphObjects()

    class Layer:
        def __init__(self) -> None:
            self.GraphObjects = graph_objects

    class App:
        def FindGraphLayer(self, _name: str) -> Layer:
            return Layer()

    class Ops:
        app = App()

    text = r"\l(3)\b(BiOBr\-(0.5)Cl\-(0.5))"

    assert _set_origin_graph_object_text(Ops(), "Graph1", "Legend", text) is True
    assert graph_object.Text == text


def test_reviewed_legend_com_text_is_refreshed_after_legend_formatting(tmp_path: Path) -> None:
    class GraphObject:
        Text = "Sheet1"

        def SetNumProp(self, _prop: str, _value: object) -> None:
            return None

    graph_object = GraphObject()

    class GraphObjects:
        def __getitem__(self, name: str) -> GraphObject:
            assert name == "Legend"
            return graph_object

    graph_objects = GraphObjects()

    class Layer:
        def __init__(self) -> None:
            self.GraphObjects = graph_objects

    class App:
        def FindGraphLayer(self, _name: str) -> Layer:
            return Layer()

        def Evaluate(self, _expression: str) -> int:
            return 67

    class Ops:
        app = App()

        def run_labtalk(self, _command: str) -> OperationResult:
            graph_object.Text = "Sheet1"
            return OperationResult(True, "ok")

    product = replace(
        _product(tmp_path, tmp_path / "eis.csv"),
        product_key="EIS",
        legend_entries=["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"],
    )

    policy = _apply_cached_style_rich_text_policies(
        Ops(),
        "Graph1",
        product,
        ResolvedPlotStyle(font_family="Arial", legend_font_size=28),
    )

    assert policy["legend_com_text_refreshed_after_formatting"] is True
    assert graph_object.Text == (
        r"\l(3)\b(BiOBr\-(0.5)Cl\-(0.5))" "\r\n"
        r"\l(4)\b(CuWO\-(4))" "\r\n"
        r"\l(5)\b(BiCu-10)"
    )


def test_eis_final_legend_uses_static_rich_text_at_template_position(tmp_path: Path) -> None:
    class GraphObject:
        def __init__(self, name: str, text: str = "") -> None:
            self.Name = name
            self.Text = text
            self.Left = 2641
            self.Top = 870
            self.Width = 1478
            self.Height = 761
            self.Show = 1
            self.props: dict[str, object] = {}

        def SetNumProp(self, prop: str, value: object) -> None:
            self.props[prop] = value
            if prop == "show":
                self.Show = value

    objects = {"Legend": GraphObject("Legend", "Sheet1")}

    class GraphObjects:
        def __getitem__(self, name: str) -> GraphObject:
            return objects[name]

        @property
        def Count(self) -> int:
            return len(objects)

        def Item(self, index: int) -> GraphObject:
            return list(objects.values())[index]

    graph_objects = GraphObjects()

    class Layer:
        GraphObjects = graph_objects

    class App:
        def FindGraphLayer(self, _name: str) -> Layer:
            return Layer()

        def Evaluate(self, _expression: str) -> int:
            return 67

    class Ops:
        app = App()

        def run_labtalk(self, command: str) -> OperationResult:
            if "label -n rdop_reviewed_legend" in command:
                objects["rdop_reviewed_legend"] = GraphObject("rdop_reviewed_legend", "x")
            return OperationResult(True, "ok")

    product = replace(
        _product(tmp_path, tmp_path / "eis.csv"),
        product_key="EIS",
        legend_entries=["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"],
    )

    policy = _replace_eis_dynamic_legend_with_static_rich_text(
        Ops(),
        "Graph1",
        product,
        {"layout_values": {"legend.fsize": 28}},
        ResolvedPlotStyle(font_family="Arial", legend_font_size=22),
    )

    static = objects["rdop_reviewed_legend"]
    assert policy["applied"] is True
    assert policy["font_size"] == 28
    assert objects["Legend"].Show == 0
    assert static.Left == 2641
    assert static.Top == 870
    assert static.props["fsize"] == 28
    assert "BiOBr" in static.Text
    assert "Sheet1" not in static.Text


def test_xrd_standard_card_legend_uses_multiline_line_sample_entries(tmp_path: Path) -> None:
    processed = tmp_path / "xrd_card.csv"
    processed.write_text(
        "two_theta_deg,BOBC,BOBC600,CWO_PDF_04-009-8466_JCPDS_card_sticks\n"
        "5,2.3,1.15,0\n"
        "6,3.3,2.15,0.75\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="XRD")
    class PlotOps(_FakeAxisOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return ["Book_B", "Book_C", "Book_D"]

    ops = PlotOps()

    policy = _apply_xrd_standard_card_legend_and_label(
        ops,
        "Graph4",
        product,
        ["BOBC", "BOBC600"],
        ResolvedPlotStyle(font_family="Arial", legend_font_size=26),
    )

    joined = "\n".join(ops.commands)
    assert policy["sample_legend_entries"] == [r"\b(BOBC)", r"\b(BOBC\-(600))"]
    assert r"\l(1)\b(BOBC)%(CRLF)\l(2)\b(BOBC\-(600))" in joined
    assert "legend.show=1" in joined
    assert "layer.plot3.color=color(181,91,0)" in joined
    assert "set Book_D -cl color(181,91,0)" in joined
    assert "set Book_D -pfb 1" in joined
    assert "set Book_D -pfc color(181,91,0)" in joined
    assert "set Book_D -pbc color(181,91,0)" in joined
    assert "set Book_D -w 1500" in joined
    assert "set Book_D -wp 3" in joined
    assert "rdop_xrd_card_label.color=color(181,91,0)" in joined
    assert "rdop_xrd_card_label.fsize=26" in joined
    assert policy["card_label_applied"] is True


def test_external_reference_plot_sequence_skips_xrd_reference_card_plot(tmp_path: Path) -> None:
    processed = tmp_path / "xrd_card.csv"
    processed.write_text(
        "two_theta_deg,BOBC,BOBC600,CWO_PDF_04-009-8466_JCPDS_card_sticks\n"
        "5,2.3,1.15,0\n"
        "6,3.3,2.15,0.75\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="XRD")

    class PlotOps(_FakeAxisOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return ["Book_B", "Book_C", "Book_D"]

    ops = PlotOps()

    policy = _apply_external_reference_plot_sequence(
        ops,
        "Graph4",
        {"plot_colors": [11, 22, 33]},
        product=product,
    )

    joined = "\n".join(ops.commands)
    assert policy["applied"] is True
    assert policy["skipped_reference_plot_indices"] == [3]
    assert "set Book_B -c 11" in joined
    assert "set Book_B -cl 11" in joined
    assert "set Book_C -c 22" in joined
    assert "set Book_C -cl 22" in joined
    assert "set Book_D -c" not in joined


def test_external_reference_plot_sequence_uses_drawn_xrd_card_plot_order(tmp_path: Path) -> None:
    processed = tmp_path / "xrd_card.csv"
    processed.write_text(
        "two_theta_deg,BOBC,BOBC600,bobc600,BOBC_BOBC15,CWO_PDF_04-009-8466_JCPDS_card_sticks\n"
        "5,5.9,5.5,4.3,2.6,0\n"
        "6,6.0,5.6,4.4,2.7,10\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="XRD")

    class PlotOps(_FakeAxisOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return ["Book_B", "Book_C", "Book_D", "Book_E", "Book_G"]

    ops = PlotOps()

    policy = _apply_external_reference_plot_sequence(
        ops,
        "Graph4",
        {"plot_colors": [11, 22, 33, 0, 0]},
        product=product,
    )

    joined = "\n".join(ops.commands)
    assert policy["skipped_reference_plot_indices"] == [5]
    assert policy["sample_color_sequence"] == [11, 22, 33, 16814848]
    assert "set Book_E -c 16814848" in joined
    assert "set Book_E -cl 16814848" in joined
    assert "set Book_G -c" not in joined


def test_adaptive_xrd_standard_card_requires_exactly_one_final_card_header() -> None:
    headers = [
        "two_theta_deg",
        "BiCu-10",
        "CuWO4",
        "CWO_PDF_04-009-8466_JCPDS_card_sticks",
    ]
    pairs = [(1, 2), (1, 3), (1, 4)]

    accepted = _validate_adaptive_xrd_standard_card_headers(headers, pairs)

    assert accepted["ok"] is True
    assert accepted["sample_headers"] == ["BiCu-10", "CuWO4"]
    assert accepted["reference_card_header"] == headers[-1]

    many_samples = _validate_adaptive_xrd_standard_card_headers(
        ["two_theta_deg", *[f"sample_{index}" for index in range(1, 9)], headers[-1]],
        [(1, index) for index in range(2, 11)],
    )
    assert many_samples["ok"] is True
    assert len(many_samples["sample_headers"]) == 8

    no_card = _validate_adaptive_xrd_standard_card_headers(headers[:-1], pairs[:-1])
    assert no_card["ok"] is False
    assert "XRD_no_card" in str(no_card["message"])

    two_cards = _validate_adaptive_xrd_standard_card_headers(
        headers + ["BiOBr_PDF_00-001-0001_JCPDS_card_sticks"],
        pairs + [(1, 5)],
    )
    assert two_cards["ok"] is False
    assert two_cards["reference_card_count"] == 2


def test_adaptive_xrd_standard_card_semantic_styles_write_and_read_back() -> None:
    class PlotOps:
        def __init__(self) -> None:
            self.values: dict[tuple[str, str], float] = {}
            self.variables: dict[str, float] = {}
            self.commands: list[str] = []

        def _plot_names(self, _graph_name: str) -> list[str]:
            return ["Book_B", "Book_C", "Book_D"]

        def run_labtalk(self, command: str) -> OperationResult:
            self.commands.append(command)
            for plot, option, value in re.findall(
                r"set\s+([A-Za-z_][A-Za-z0-9_]*)\s+-(\w+)\s+(-?[0-9.]+);",
                command,
            ):
                self.values[(plot, option)] = float(value)
            match = re.search(
                r"get\s+([A-Za-z_][A-Za-z0-9_]*)\s+-(\w+)\s+([A-Za-z_][A-Za-z0-9_]*);",
                command,
            )
            if match:
                plot, option, variable = match.groups()
                self.variables[variable] = self.values[(plot, option)]
            return OperationResult(True, "")

        def get_labtalk_variable(self, variable: str) -> OperationResult:
            return OperationResult(True, "", {"value": self.variables[variable]})

    ops = PlotOps()
    policy = _apply_adaptive_xrd_standard_card_plot_styles(
        ops,
        "Graph4",
        [
            "two_theta_deg",
            "BiCu-10",
            "CuWO4",
            "CWO_PDF_04-009-8466_JCPDS_card_sticks",
        ],
    )

    assert policy["applied"] is True
    assert policy["reference_card_plot_index"] == 3
    assert [item["role"] for item in policy["plots"]] == [
        "sample_pattern",
        "sample_pattern",
        "reference_card_sticks",
    ]
    assert ops.values[("Book_B", "l")] == 1
    assert ops.values[("Book_B", "lv")] == 0
    assert ops.values[("Book_B", "c")] == 33518174
    assert ops.values[("Book_C", "c")] == 16814848
    assert ops.values[("Book_D", "l")] == 0
    assert ops.values[("Book_D", "lv")] == 0
    assert ops.values[("Book_D", "c")] == 22106449
    assert ops.values[("Book_D", "cl")] == 22106449
    assert ops.values[("Book_D", "pbc")] == 11
    assert ops.values[("Book_D", "pfb")] == 11
    assert ops.values[("Book_D", "pfc")] == 11
    assert ops.values[("Book_D", "pbs")] == 0
    assert ops.values[("Book_D", "pbw")] == 0.5


def test_adaptive_xrd_axis_titles_use_native_page_geometry_and_remain_in_bounds() -> None:
    class GraphObject:
        def __init__(self, name: str, width: int, height: int) -> None:
            self.Name = name
            self.Text = ""
            self.Left = 0
            self.Top = 0
            self.Width = width
            self.Height = height
            self.properties: dict[str, float] = {}

        def SetNumProp(self, name: str, value: float) -> None:
            self.properties[name] = value

    class GraphObjects:
        def __init__(self, objects: list[GraphObject]) -> None:
            self.objects = objects
            self.Count = len(objects)

        def __getitem__(self, name: str) -> GraphObject:
            for graph_object in self.objects:
                if graph_object.Name == name:
                    return graph_object
            raise KeyError(name)

        def Item(self, index: int) -> GraphObject:
            return self.objects[index]

    class Layer:
        def __init__(self, objects: list[GraphObject]) -> None:
            self.GraphObjects = GraphObjects(objects)

    class App:
        def __init__(self, layer: Layer) -> None:
            self.layer = layer

        def FindGraphLayer(self, name: str) -> Layer | None:
            return self.layer if name == "[Graph4]Layer1" else None

        def Evaluate(self, _expression: str) -> float:
            return 67

    class Ops:
        def __init__(self, app: App) -> None:
            self.app = app
            self.commands: list[str] = []

        def run_labtalk(self, command: str) -> OperationResult:
            self.commands.append(command)
            return OperationResult(True, "ok")

    xb = GraphObject("XB", 1598, 338)
    yl = GraphObject("YL", 350, 2036)
    ops = Ops(App(Layer([xb, yl])))
    snapshot = {
        "layout_values": {
            "page.width": 6432,
            "page.height": 4923,
            "layer.left": 17.89,
            "layer.top": 11.6,
            "layer.width": 68.19,
            "layer.height": 71.81,
        }
    }

    result = _position_adaptive_xrd_axis_titles(
        ops,
        "Graph4",
        "2θ (degree)",
        "Intensity (a.u.)",
        snapshot,
        ResolvedPlotStyle(),
    )

    assert result["applied"] is True
    assert xb.Text == r"\b(2θ (degree))"
    assert yl.Text == r"\b(Intensity (a.u.))"
    assert xb.Left == 2545
    assert yl.Left == 691
    assert xb.Top >= 0 and xb.Top + xb.Height <= 4923
    assert yl.Top >= 0 and yl.Top + yl.Height <= 4923
    assert xb.properties["show"] == 1
    assert yl.properties["bold"] == 1
    assert any("xb.attach=1; yl.attach=1" in command for command in ops.commands)
    assert any("xb.show=1; yl.show=1" in command for command in ops.commands)


def test_adaptive_xrd_axis_title_reopen_gate_rejects_off_page_objects() -> None:
    base = {
        "layout_values": {"page.width": 6432, "page.height": 4923},
        "graph_object_positions": {
            "XB": {"left": 2545, "top": 4485, "width": 1598, "height": 338},
            "YL": {"left": 691, "top": 1321, "width": 350, "height": 2036},
        },
    }

    accepted = _validate_xrd_axis_title_page_bounds(base)
    assert accepted["ok"] is True
    assert accepted["status"] == "matched"

    rejected = _validate_xrd_axis_title_page_bounds(
        {
            **base,
            "graph_object_positions": {
                **base["graph_object_positions"],
                "XB": {"left": 2545, "top": 3191178, "width": 1598, "height": 338},
            },
        }
    )
    assert rejected["ok"] is False
    assert "outside page height" in str(rejected["message"])


def test_adaptive_xrd_requires_current_data_and_one_layer_after_reopen() -> None:
    product = SimpleNamespace(product_key="XRD")
    decision = {"selected_mode": "oth-json", "contract_series_count": 5}
    current_style = {
        "plot_count": 3,
        "layer_count": 1,
        "plot_visibility": [1, 1, 1],
    }

    accepted = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (1, 3), (1, 4)],
        current_style,
        decision,
        {"status": "pass"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert accepted["ok"] is True
    assert accepted["xrd_adaptive_structure"]["actual_layer_count"] == 1

    wrong_layer = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (1, 3), (1, 4)],
        {**current_style, "layer_count": 3},
        decision,
        {"status": "pass"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert wrong_layer["ok"] is False
    assert "one layer" in str(wrong_layer["message"])

    wrong_data = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (1, 3), (1, 4)],
        current_style,
        decision,
        {"status": "pass"},
        current_data_validation={"ok": False, "status": "mismatch"},
    )
    assert wrong_data["ok"] is False
    assert "X/Y values" in str(wrong_data["message"])


def test_strict_adaptive_xrd_accepts_shared_x_card_contract_not_fixed_multibook_layout() -> None:
    contract = SimpleNamespace(
        product_key="XRD",
        source_schema={"layout": "multi_book_xy_pairs"},
    )
    headers = [
        "two_theta_deg",
        "BiCu-10",
        "CWO_PDF_04-009-8466_JCPDS_card_sticks",
    ]
    rows = [[5.0, 2.0, 0.0], [6.0, 3.0, 10.0]]

    result = _strict_adaptive_source_validation(contract, headers, rows, [(0, 1), (0, 2)])

    assert result["ok"] is True
    assert result["layout"] == "multi_book_xy_pairs"


def test_strict_adaptive_shared_x_accepts_distinct_contiguous_y_bounds() -> None:
    contract = SimpleNamespace(
        product_key="PL",
        source_schema={
            "layout": "shared_x_y_columns",
            "x_header": "wavelength_nm",
            "y_header_suffix": "_counts",
        },
    )
    headers = ["wavelength_nm", "BOBC_counts", "CWO_counts"]
    rows = [
        [250.0, 1.0, math.nan],
        [251.0, 2.0, 10.0],
        [252.0, 3.0, 11.0],
        [253.0, 4.0, math.nan],
    ]

    accepted = _strict_adaptive_source_validation(
        contract,
        headers,
        rows,
        [(0, 1), (0, 2)],
    )
    assert accepted["ok"] is True
    assert _adaptive_photocurrent_validation_ranges(
        rows,
        [(1, 2), (1, 3)],
        shared_x_variable_y=True,
    ) == [
        {
            "x_col": 1,
            "y_col": 2,
            "row_from": 1,
            "row_to": 4,
            "source_x_index": 0,
            "source_y_index": 1,
            "source_row_from": 1,
            "source_row_to": 4,
        },
        {
            "x_col": 1,
            "y_col": 3,
            "row_from": 2,
            "row_to": 3,
            "source_x_index": 0,
            "source_y_index": 2,
            "source_row_from": 2,
            "source_row_to": 3,
        },
    ]

    rows_with_gap = [list(row) for row in rows]
    rows_with_gap[1][2] = 10.0
    rows_with_gap[2][2] = math.nan
    rows_with_gap[3][2] = 12.0
    rejected = _strict_adaptive_source_validation(
        contract,
        headers,
        rows_with_gap,
        [(0, 1), (0, 2)],
    )
    assert rejected["ok"] is False
    assert "contiguous finite X/Y run" in rejected["message"]


def test_load_saved_style_snapshot_reads_adjacent_snapshot_file(tmp_path: Path) -> None:
    theme = tmp_path / "templates" / "origin_styles" / "format_themes" / "XRD.oth"
    snapshot = tmp_path / "templates" / "origin_styles" / "snapshots" / "XRD.json"
    theme.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    snapshot.write_text('{"plot_colors":[16814848,33518174]}', encoding="utf-8")

    loaded = _load_saved_style_snapshot(theme)

    assert loaded["plot_colors"] == [16814848, 33518174]


def test_load_saved_data_snapshot_reads_adjacent_data_snapshot_file(tmp_path: Path) -> None:
    theme = tmp_path / "templates" / "origin_styles" / "format_themes" / "EIS.oth"
    snapshot = tmp_path / "templates" / "origin_styles" / "data_snapshots" / "EIS.json"
    theme.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    theme.write_bytes(b"oth")
    snapshot.write_text('{"plots":[{"style":{"symbol_shape":20}}]}', encoding="utf-8")

    loaded = _load_saved_data_snapshot(theme)

    assert loaded["plots"][0]["style"]["symbol_shape"] == 20


def test_independent_reference_preview_rejects_missing_requested_graph_page(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference.opju"
    source.write_bytes(b"reference")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    processed = tmp_path / "processed.csv"
    processed.write_text("x,y\n0,1\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        external_reference_opju=source,
        external_reference_graph="MissingGraph",
        external_reference_source="test_reference",
    )

    class Ops:
        def new_project(self) -> OperationResult:
            return OperationResult(True, "new")

        def load_project(self, _path: Path) -> OperationResult:
            return OperationResult(True, "loaded")

        def list_worksheets(self) -> OperationResult:
            return OperationResult(
                True,
                "listed",
                {"pages": [{"name": "Graph4", "type": "graph"}]},
            )

        def export_graph(self, *_args, **_kwargs) -> OperationResult:
            raise AssertionError("missing graph page must fail before export")

    result = _export_external_reference_preview_if_requested(
        Ops(),
        product,
        runtime,
        runtime / "reference.png",
        ResolvedPlotStyle(),
    )

    assert result["ok"] is False
    assert result["graph_page"] == "MissingGraph"
    assert result["available_graph_pages"] == ["Graph4"]
    assert "does not exist" in str(result["message"])


def test_xrd_standard_card_legend_keeps_template_vertical_entries() -> None:
    entries = [rf"\l({index})\b(Sample {index})" for index in range(1, 5)]

    rows = _xrd_standard_card_legend_rows(entries)

    assert rows == [
        r"\l(1)\b(Sample 1)",
        r"\l(2)\b(Sample 2)",
        r"\l(3)\b(Sample 3)",
        r"\l(4)\b(Sample 4)",
    ]


def _product(tmp_path: Path, processed: Path) -> ProductContext:
    pairing = TargetPairing(
        product_key="BET",
        data_type="BET",
        xps_subtype="",
        data_root_label="test",
        data_paths=[],
        opju_root_label="test",
        reference_opju=tmp_path / "reference.opju",
    )
    return ProductContext(
        product_key="BET",
        slug="BET_template",
        pairing=pairing,
        type_root=tmp_path,
        processed_data=processed,
        input_copies=[],
        reference_opju_copy=tmp_path / "reference.opju",
        reference_preview_png=tmp_path / "reference.png",
        origin_file=tmp_path / "product.opju",
        figure_tif=tmp_path / "product.tif",
        preview_png=tmp_path / "product.png",
        x_label="Relative Pressure",
        y_label="Quantity Adsorbed",
        graph_title="BET",
        plot_type="line",
    )


def _verified_xps_in_situ_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[float]], Path]:
    roles = (
        "_measured",
        "_component_1",
        "_component_1_fill_baseline",
        "_component_2",
        "_component_2_fill_baseline",
        "_background",
        "_envelope",
    )
    samples = ("Sample_A", "Sample_B", "Sample_C")
    headers = [
        header
        for sample in samples
        for header in (sample + "_binding_energy_eV", *(sample + role for role in roles))
    ]
    rows: list[list[float]] = []
    for row_index, x_value in enumerate((168.0, 167.5, 167.0), start=1):
        row = []
        for sample_index in range(3):
            background = float(sample_index + 1) / 10.0
            row.extend(
                [
                    x_value - sample_index * 0.1,
                    float(row_index + sample_index),
                    float(row_index + sample_index) + 0.5,
                    background,
                    float(4 - row_index + sample_index) + 0.25,
                    background,
                    background,
                    float(row_index + sample_index) + 0.75,
                ]
            )
        rows.append(row)
    processed = tmp_path / "xps_in_situ.csv"
    processed.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(str(value) for value in row) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="XPS_in_situ",
        graph_title="Bi 4f",
        legend_entries=list(samples),
    )
    contract = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "XPS_in_situ.json"
    )
    return product, headers, rows, contract


def test_xps_in_situ_verified_binding_and_workbook_preserve_reviewed_native_topology(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_xps_in_situ_product_and_table(tmp_path)
    binding = _prepare_verified_xps_in_situ_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    assert binding["ok"] is True
    assert binding["graph_page"] == "Bi_4f"
    assert [value["book_name"] for value in binding["workbooks"]] == ["Book2", "Book3", "Book4"]
    assert [value["y_col"] for value in binding["xy_ranges"]] == [2, 3, 5, 4, 5, 5, 6] * 3
    assert [value["source_x_index"] for value in binding["xy_ranges"]] == [0] * 7 + [8] * 7 + [16] * 7
    assert [value["source_y_index"] for value in binding["xy_ranges"]] == [
        1, 4, 3, 2, 5, 6, 7,
        9, 12, 11, 10, 13, 14, 15,
        17, 20, 19, 18, 21, 22, 23,
    ]

    class WorkbookOps:
        def __init__(self) -> None:
            self.data: dict[str, list[list[float]]] = {}

        def create_worksheet(self, book_name: str, sheet_name: str) -> OperationResult:
            return OperationResult(True, "created", {"book_name": book_name, "sheet_name": sheet_name})

        def set_worksheet_data(
            self,
            book_name: str,
            _sheet_name: str,
            columns: list[list[float]],
        ) -> OperationResult:
            self.data[book_name] = columns
            return OperationResult(True, "written")

        def set_worksheet_column_metadata(
            self,
            _book_name: str,
            columns: list[dict[str, object]],
        ) -> OperationResult:
            assert [column["column_index"] for column in columns] == [1, 2, 3, 4, 5, 6]
            return OperationResult(True, "metadata")

    operations = WorkbookOps()
    result = _populate_verified_otpu_workbook(operations, product, headers, rows, binding)
    assert result["ok"] is True
    assert result["book_names"] == ["Book2", "Book3", "Book4"]
    assert all(len(columns) == 6 for columns in operations.data.values())
    assert operations.data["Book2"][0] == [row[0] for row in rows]
    assert operations.data["Book3"][0] == [row[8] for row in rows]
    assert operations.data["Book4"][0] == [row[16] for row in rows]
    assert min(operations.data["Book2"][1]) == pytest.approx(2.82)
    assert max(operations.data["Book2"][1]) == pytest.approx(3.82)
    assert min(operations.data["Book3"][1]) == pytest.approx(1.41)
    assert max(operations.data["Book3"][1]) == pytest.approx(2.41)
    assert min(operations.data["Book4"][1]) == pytest.approx(0.0)
    assert max(operations.data["Book4"][1]) == pytest.approx(1.0)
    assert operations.data["Book2"][2][0] > operations.data["Book2"][2][-1]
    assert operations.data["Book2"][3][0] < operations.data["Book2"][3][-1]


def test_xps_in_situ_verified_binding_rejects_nonshared_fill_baseline(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_xps_in_situ_product_and_table(tmp_path)
    rows[1][3] += 0.1

    result = _prepare_verified_xps_in_situ_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    assert result["ok"] is False
    assert "same supplied curve" in str(result["message"])


def test_xps_in_situ_verified_same_data_and_plot_style_hard_gates(tmp_path: Path) -> None:
    product, headers, rows, _contract = _verified_xps_in_situ_product_and_table(tmp_path)
    plots = []
    runtime_sources = [
        1, 4, 3, 2, 5, 6, 7,
        9, 12, 11, 10, 13, 14, 15,
        17, 20, 19, 18, 21, 22, 23,
    ]
    runtime_x_sources = [0] * 7 + [8] * 7 + [16] * 7
    for plot_index, (source_x_index, source_y_index) in enumerate(
        zip(runtime_x_sources, runtime_sources),
        start=1,
    ):
        role_index = (plot_index - 1) % 7 + 1
        plots.append(
            {
                "layer_index": 1,
                "plot_index": plot_index,
                "x_values": [row[source_x_index] for row in rows],
                "y_values": [row[source_y_index] for row in rows],
                "style": {
                    "color": role_index,
                    "line_color": role_index,
                    "line_width_origin_units": 0.0 if plot_index % 7 in {3, 5, 6} else 1500.0,
                    "line_width_pt": 0.0 if plot_index % 7 in {3, 5, 6} else 3.0,
                    "line_style": 1.0,
                    "symbol_shape": 0.0,
                    "symbol_size": 9.0,
                    "fill_area": 1.0,
                    "fill_color": -9.0,
                    "border_color": 1.0,
                    "border_width": 0.5,
                },
            }
        )
    reference = {"status": "ready", "plots": plots}
    assert _xps_in_situ_current_data_matches_reference(product, reference)["matches"] is True
    current = json.loads(json.dumps(reference))
    assert _validate_xps_in_situ_reopened_plot_styles(reference, current)["ok"] is True
    current["plots"][2]["style"]["line_width_pt"] = 3.0
    rejected = _validate_xps_in_situ_reopened_plot_styles(reference, current)
    assert rejected["ok"] is False
    assert "line_width_pt" in str(rejected["message"])


def test_xps_in_situ_adaptive_source_and_role_styles_support_two_sample_groups(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_xps_in_situ_product_and_table(tmp_path)
    headers = headers[:16]
    rows = [row[:16] for row in rows]
    for row in rows:
        row[2], row[4] = row[4], row[2]
        row[10], row[12] = row[12], row[10]
    product.processed_data.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(str(value) for value in row) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))["contracts"][0]
    pairs = [
        (x_column - 1, y_column - 1)
        for x_column, y_column in _processed_csv_plot_pairs(product, headers)
    ]
    validation = _strict_adaptive_source_validation(
        SimpleNamespace(source_schema=contract_payload["source_schema"]),
        headers,
        rows,
        pairs,
    )
    assert validation["ok"] is True
    assert validation["source_series_count"] == 14

    reference_plots = []
    for plot_index in range(1, 22):
        role_index = (plot_index - 1) % 7 + 1
        reference_plots.append(
            {
                "layer_index": 1,
                "plot_index": plot_index,
                "style": {
                    "color": role_index,
                    "line_color": role_index,
                    "line_width_origin_units": 0.0 if role_index in {3, 5, 6} else 1500.0,
                    "line_width_pt": 0.0 if role_index in {3, 5, 6} else 3.0,
                    "line_style": 1.0,
                    "symbol_shape": 0.0,
                    "symbol_size": 9.0,
                    "fill_area": 1.0,
                    "fill_color": -9.0,
                    "border_color": 1.0,
                    "border_width": 0.5,
                },
            }
        )
    reference = {"status": "ready", "plots": reference_plots}
    current = {"status": "ready", "plots": reference_plots[:14]}
    style_validation = _validate_adaptive_xps_in_situ_reopened_plot_styles(
        reference,
        current,
        expected_plot_count=14,
    )
    assert style_validation["ok"] is True


def _verified_xps_non_in_situ_product_and_table(
    tmp_path: Path,
) -> tuple[ProductContext, list[str], list[list[float]], Path]:
    roles = (
        "_component_1_fill_upper",
        "_component_1_fill_baseline",
        "_component_1_line",
        "_component_2_fill_upper",
        "_component_2_fill_baseline",
        "_component_2_line",
        "_measured",
        "_background",
        "_envelope",
    )
    samples = ("Sample_A", "Sample_B")
    headers = ["binding_energy_eV"] + [
        sample + role for sample in samples for role in roles
    ]
    rows: list[list[float]] = []
    for row_index, x_value in enumerate((168.0, 167.5, 167.0)):
        row = [x_value]
        for sample_index in range(2):
            offset = sample_index * 1.35
            background = offset + 0.05
            component_1 = offset + (0.2, 0.5, 0.2)[row_index]
            component_2 = offset + (0.1, 0.2, 0.6)[row_index]
            row.extend(
                [
                    component_1,
                    background,
                    component_1,
                    component_2,
                    background,
                    component_2,
                    offset + (0.3, 0.7, 0.8)[row_index],
                    background,
                    offset + (0.31, 0.71, 0.81)[row_index],
                ]
            )
        rows.append(row)
    processed = tmp_path / "xps_non_in_situ.csv"
    processed.write_text(
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(str(value) for value in row) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="XPS_non_in_situ",
        graph_title="Bi 4f",
        legend_entries=list(samples),
    )
    contract = (
        Path(__file__).parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "XPS_non_in_situ.json"
    )
    return product, headers, rows, contract


def test_xps_non_in_situ_verified_binding_preserves_reviewed_native_topology(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract = _verified_xps_non_in_situ_product_and_table(
        tmp_path
    )

    binding = _prepare_verified_xps_non_in_situ_otpu_binding(
        product,
        headers,
        rows,
        contract_path=contract,
    )

    assert binding["ok"] is True
    assert binding["graph_page"] == "XPS_Bi_BOBC_vs_c890fa98"
    assert [value["x_col"] for value in binding["xy_ranges"]] == [1] * 18
    assert [value["y_col"] for value in binding["xy_ranges"]] == list(range(2, 20))
    assert [value["source_y_index"] for value in binding["xy_ranges"]] == list(range(1, 19))
    assert [
        value["fill_above_color"] for value in binding["plot_format_contracts"]
    ] == [30972633, 1, 1, 25540850, 1, 1, 1, 1, 1] * 2

    class WorkbookOps:
        def import_csv_to_worksheet(
            self,
            _path: Path,
            *,
            book_name: str,
        ) -> OperationResult:
            return OperationResult(
                True,
                "imported",
                {"book_name": book_name, "sheet_name": "Sheet1"},
            )

        def set_worksheet_column_metadata(
            self,
            book_name: str,
            columns: list[dict[str, object]],
        ) -> OperationResult:
            assert book_name == "Book2"
            assert [value["column_index"] for value in columns] == list(range(1, 20))
            assert columns[0]["type"] == 4
            assert all(value["type"] == 1 for value in columns[1:])
            return OperationResult(True, "metadata")

    populated = _populate_verified_otpu_workbook(
        WorkbookOps(),
        product,
        headers,
        rows,
        binding,
    )
    assert populated["ok"] is True
    assert populated["method"] == "xps_non_in_situ_shared_x_eighteen_role_native_workbook"


def test_xps_non_in_situ_adaptive_contract_supports_variable_sample_count(
    tmp_path: Path,
) -> None:
    product, headers, rows, contract_path = _verified_xps_non_in_situ_product_and_table(
        tmp_path
    )
    one_sample_headers = headers[:10]
    one_sample_rows = [row[:10] for row in rows]
    contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))["contracts"][0]
    pairs = [
        (x_column - 1, y_column - 1)
        for x_column, y_column in _processed_csv_plot_pairs(
            product,
            one_sample_headers,
        )
    ]

    validation = _strict_adaptive_source_validation(
        SimpleNamespace(
            source_schema=contract_payload["source_schema"],
            product_key="XPS_non_in_situ",
        ),
        one_sample_headers,
        one_sample_rows,
        pairs,
    )

    assert validation["ok"] is True
    assert validation["source_series_count"] == 9
    assert _xps_non_in_situ_adaptive_plot_format_contracts(27)[18][
        "fill_above_color"
    ] == 30972633


def test_xps_non_in_situ_native_fill_readback_is_a_hard_gate() -> None:
    formats = _xps_non_in_situ_adaptive_plot_format_contracts(18)
    reference_plots = []
    for plot_index in range(1, 19):
        role_index = (plot_index - 1) % 9 + 1
        expected = formats[plot_index - 1]
        reference_plots.append(
            {
                "layer_index": 1,
                "plot_index": plot_index,
                "style": {
                    "color": role_index,
                    "line_color": role_index,
                    "line_width_origin_units": 0.0 if role_index in {1, 2, 4, 5} else 1500.0,
                    "line_width_pt": 0.0 if role_index in {1, 2, 4, 5} else 3.0,
                    "line_style": 1.0,
                    "symbol_shape": 0.0,
                    "symbol_size": 9.0,
                    "fill_enabled": float(expected["fill_enabled"]),
                    "fill_mode": float(expected["fill_mode"]),
                    "fill_above_color": float(expected["fill_above_color"]),
                    "fill_below_color": float(expected["fill_below_color"]),
                },
            }
        )
    reference = {"status": "ready", "plots": reference_plots}
    current = json.loads(json.dumps(reference))

    assert _validate_xps_non_in_situ_reopened_plot_styles(reference, current)["ok"] is True
    adaptive = _validate_adaptive_xps_non_in_situ_reopened_plot_styles(
        reference,
        {"status": "ready", "plots": reference_plots[:9]},
        expected_plot_count=9,
    )
    assert adaptive["ok"] is True
    current["plots"][0]["style"]["fill_above_color"] = -1.0
    rejected = _validate_xps_non_in_situ_reopened_plot_styles(reference, current)
    assert rejected["ok"] is False
    assert "fill_above_color" in str(rejected["message"])


def test_xps_non_in_situ_explicit_adaptive_route_rejects_other_xps_regions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    product, _headers, _rows, contract = _verified_xps_non_in_situ_product_and_table(
        tmp_path
    )
    product = replace(product, graph_title="Bi 5d")
    style_root = Path(__file__).parents[1] / "templates" / "origin_styles"
    theme = style_root / "format_themes" / "XPS_non_in_situ.oth"
    adaptive = SimpleNamespace(
        runtime_asset_kind="oth_json",
        runtime_asset_path=theme,
        format_theme_path=theme,
        style_snapshot_path=style_root / "snapshots" / "XPS_non_in_situ.json",
        data_snapshot_path=style_root
        / "data_snapshots"
        / "XPS_non_in_situ.json",
        binding_contract_path=contract,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor.resolve_origin_runtime_style_asset",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor.resolve_origin_adaptive_style_asset",
        lambda *_args, **_kwargs: adaptive,
    )

    decision, selected = _resolve_origin_style_execution_route(
        tmp_path,
        product,
        requested_mode="oth-json",
    )

    assert selected is None
    assert decision["ok"] is False
    assert decision["reason_code"] == "xps_non_in_situ_bi4f_scope_mismatch"
    assert "Bi 4f only" in str(decision["message"])


def _dual_mode_ftir_product(tmp_path: Path, processed: Path, labels: list[str]) -> ProductContext:
    pairing = TargetPairing(
        product_key="FTIR",
        data_type="FTIR",
        xps_subtype="",
        data_root_label="test",
        data_paths=[],
        opju_root_label="test",
        reference_opju=tmp_path / "reference.opju",
    )
    return replace(
        _product(tmp_path, processed),
        product_key="FTIR",
        pairing=pairing,
        legend_entries=labels,
        x_label="Wavenumber (cm-1)",
        y_label="Transmittance",
    )


def _dual_mode_assets(tmp_path: Path) -> tuple[SimpleNamespace, SimpleNamespace]:
    theme = tmp_path / "FTIR.oth"
    style_snapshot = tmp_path / "FTIR-style.json"
    data_snapshot = tmp_path / "FTIR-data.json"
    template = tmp_path / "FTIR.otpu"
    theme.write_bytes(b"oth")
    template.write_bytes(b"otpu")
    style_snapshot.write_text('{"status":"extracted","plot_count":3}', encoding="utf-8")
    data_snapshot.write_text('{"status":"ready","plot_count":3,"plots":[]}', encoding="utf-8")
    contract = Path(__file__).parents[1] / "templates" / "origin_styles" / "binding_contracts" / "FTIR.json"
    exact = SimpleNamespace(
        runtime_asset_kind="otpu",
        runtime_asset_path=template,
        format_theme_path=theme,
        style_snapshot_path=style_snapshot,
        data_snapshot_path=data_snapshot,
        binding_contract_path=contract,
    )
    adaptive = SimpleNamespace(
        runtime_asset_kind="oth_json",
        runtime_asset_path=theme,
        format_theme_path=theme,
        style_snapshot_path=style_snapshot,
        data_snapshot_path=data_snapshot,
        binding_contract_path=contract,
    )
    return exact, adaptive


def test_processed_csv_plot_pairs_strictly_recognizes_variable_independent_xy(tmp_path: Path) -> None:
    processed = tmp_path / "ftir.csv"
    processed.write_text("x,y\n1,2\n", encoding="utf-8")
    product = _dual_mode_ftir_product(tmp_path, processed, ["A", "B"])
    headers = [
        "A_wavenumber_cm-1",
        "A_transmittance",
        "B_wavenumber_cm-1",
        "B_transmittance",
    ]

    assert _processed_csv_plot_pairs(product, headers) == [(1, 2), (3, 4)]
    assert _processed_csv_plot_pairs(
        product,
        ["A_wavenumber_cm-1", "A_wavenumber_cm-1"],
    ) == []


def test_verified_uvvis_fixed_bindings_require_reviewed_semantic_roles(tmp_path: Path) -> None:
    cases = (
        (
            "UV-vis DRS",
            "UV_vis_DRS.json",
            "_wavelength_nm",
            "_drs_signal",
            [
                "CuWO4_hidden_raw",
                "BiOBr0_5Cl0_5_hidden_raw",
                "BiCu_10_hidden_raw",
                "CuWO4_visible",
                "BiOBr0_5Cl0_5_visible",
                "BiCu_10_visible",
            ],
            ["CuWO4", "BiOBr0.5Cl0.5", "BiCu-10", "CuWO4", "BiOBr0.5Cl0.5", "BiCu-10"],
            "Graph1",
            [(1, 2), (3, 4), (5, 6), (10, 11), (18, 19), (20, 21)],
        ),
        (
            "Tauc",
            "Tauc.json",
            "_photon_energy_eV",
            "_tauc_y_direct_candidate",
            ["CuWO4_unsmoothed_hidden", "BiOBr0_5Cl0_5_visible", "CuWO4_visible"],
            ["CuWO4", "BiOBr0.5Cl0.5", "CuWO4"],
            "Graph2",
            [(3, 4), (7, 8), (9, 10)],
        ),
    )
    contract_root = Path(__file__).parents[1] / "templates" / "origin_styles" / "binding_contracts"
    for product_key, contract_name, x_suffix, y_suffix, identities, labels, graph_page, destinations in cases:
        headers = [value for identity in identities for value in (identity + x_suffix, identity + y_suffix)]
        rows = [[float(index + 1) for index in range(len(headers))], [float(index + 2) for index in range(len(headers))]]
        processed = tmp_path / f"{product_key}.csv"
        processed.write_text(
            ",".join(headers) + "\n" + "\n".join(",".join(str(value) for value in row) for row in rows) + "\n",
            encoding="utf-8",
        )
        product = replace(
            _product(tmp_path, processed),
            product_key=product_key,
            legend_entries=labels,
        )

        binding = _prepare_verified_uvvis_otpu_binding(
            product,
            headers,
            rows,
            contract_path=contract_root / contract_name,
        )

        assert binding["ok"] is True
        assert binding["graph_page"] == graph_page
        assert [(value["x_col"], value["y_col"]) for value in binding["xy_ranges"]] == destinations
        wrong_headers = list(headers)
        wrong_headers[0] = "ordinary_sample" + x_suffix
        wrong_headers[1] = "ordinary_sample" + y_suffix
        rejected = _prepare_verified_uvvis_otpu_binding(
            product,
            wrong_headers,
            rows,
            contract_path=contract_root / contract_name,
        )
        assert rejected["ok"] is False
        assert "adaptive OTH+JSON" in rejected["message"]


def test_uvvis_auto_uses_adaptive_for_ordinary_same_cardinality_data(tmp_path: Path, monkeypatch) -> None:
    identities = [f"sample_{index}" for index in range(1, 7)]
    headers = [
        value
        for identity in identities
        for value in (identity + "_wavelength_nm", identity + "_drs_signal")
    ]
    processed = tmp_path / "uvvis.csv"
    processed.write_text(
        ",".join(headers) + "\n" + ",".join(str(index + 1) for index in range(len(headers))) + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="UV-vis DRS",
        legend_entries=identities,
    )
    theme = tmp_path / "UV_vis_DRS.oth"
    template = tmp_path / "UV_vis_DRS.otpu"
    style_snapshot = tmp_path / "UV_vis_DRS.style.json"
    data_snapshot = tmp_path / "UV_vis_DRS.data.json"
    theme.write_bytes(b"oth")
    template.write_bytes(b"otpu")
    style_snapshot.write_text('{"status":"extracted","plot_count":6}', encoding="utf-8")
    data_snapshot.write_text('{"status":"ready","plot_count":6,"plots":[]}', encoding="utf-8")
    contract = Path(__file__).parents[1] / "templates" / "origin_styles" / "binding_contracts" / "UV_vis_DRS.json"
    exact = SimpleNamespace(
        runtime_asset_kind="otpu",
        runtime_asset_path=template,
        format_theme_path=theme,
        style_snapshot_path=style_snapshot,
        data_snapshot_path=data_snapshot,
        binding_contract_path=contract,
    )
    adaptive = SimpleNamespace(
        runtime_asset_kind="oth_json",
        runtime_asset_path=theme,
        format_theme_path=theme,
        style_snapshot_path=style_snapshot,
        data_snapshot_path=data_snapshot,
        binding_contract_path=contract,
    )
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_runtime_style_asset", lambda *_a, **_k: exact)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_adaptive_style_asset", lambda *_a, **_k: adaptive)

    auto, selected = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="auto")
    explicit, explicit_asset = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="otpu")

    assert selected is adaptive
    assert auto["selected_mode"] == "oth-json"
    assert auto["reason_code"] == "fixed_cardinality_semantics_select_adaptive_uvvis"
    assert explicit_asset is None
    assert explicit["reason_code"] == "verified_otpu_binding_mismatch"


def test_changed_tauc_data_removes_reference_fit_guides() -> None:
    operations = _FakeTemplateOps()

    result = _remove_tauc_reference_candidate_guides(operations, "Graph2")

    assert result["applied"] is True
    assert result["manual_check_required"] is True
    command = operations.commands[-1]
    for name in (
        "Line", "Line1", "Line2", "Line3", "Line4", "Line5",
        "Arrow", "Arrow1", "Arrow2", "Arrow3", "Text", "Text1",
    ):
        assert f"label -r {name};" in command


def test_tauc_guide_cleanup_readback_rejects_any_remaining_reference_object() -> None:
    clean = _validate_tauc_reference_guides_removed(
        SimpleNamespace(app=None),
        "Graph2",
        {"graph_object_positions": {"Legend": {}}},
    )
    dirty = _validate_tauc_reference_guides_removed(
        SimpleNamespace(app=None),
        "Graph2",
        {"graph_object_positions": {"Line1": {}, "Text": {}}},
    )

    assert clean["ok"] is True
    assert dirty["ok"] is False
    assert dirty["present_objects"] == ["Line1", "Text"]


def test_verified_uvvis_fixed_visibility_restores_hidden_reference_plots() -> None:
    class Operations(_FakeTemplateOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return [f"plot{index}" for index in range(1, 7)]

    operations = Operations()

    result = _apply_verified_uvvis_fixed_visibility(
        operations,
        "Graph1",
        {"plot_visibility": [0, 0, 0, 1, 1, 1]},
    )

    assert result["applied"] is True
    assert result["plot_visibility"] == [0, 0, 0, 1, 1, 1]
    assert "layer.plot1.show=0" in operations.commands[0]
    assert "layer.plot6.show=1" in operations.commands[-1]


def test_uvvis_current_axis_titles_use_native_bold_objects_with_readback() -> None:
    class GraphObject:
        def __init__(self) -> None:
            self.Text = ""
            self.props: dict[str, float] = {"bold": 0.0}

        def SetNumProp(self, name: str, value: object) -> None:
            self.props[name] = float(value)

        def GetNumProp(self, name: str) -> float:
            assert name == "bold"
            return -1.23456789e-300

    objects = {"XB": GraphObject(), "YL": GraphObject()}

    class GraphObjects:
        def __getitem__(self, name: str) -> GraphObject:
            return objects[name]

    class Layer:
        def __init__(self) -> None:
            self.GraphObjects = GraphObjects()

    class App:
        def FindGraphLayer(self, _name: str) -> Layer:
            return Layer()

    class Operations:
        app = App()

        def set_axis_labels(
            self,
            _graph_name: str,
            _x_label: str,
            _y_label: str,
            _title: str,
        ) -> OperationResult:
            return OperationResult(True, "ok")

    result = _apply_uvvis_current_axis_titles(
        Operations(),
        "Graph1",
        "Wavelength (nm)",
        "Reflectance (a.u.)",
    )

    assert result["applied"] is True
    assert objects["XB"].Text == r"\b(Wavelength (nm))"
    assert objects["YL"].Text == r"\b(Reflectance (a.u.))"
    assert objects["XB"].props["bold"] == 1.0
    assert objects["YL"].props["bold"] == 1.0
    assert result["readback"]["XB"]["bold"] is None

    tauc = _apply_uvvis_current_axis_titles(
        Operations(),
        "Graph2",
        "hν (eV)",
        "(αhν)^2",
    )

    assert tauc["applied"] is True
    assert objects["XB"].Text == r"\b(\i(h\f:g(ν) )(eV))"
    assert objects["YL"].Text == r"\b(\(40)\i(\f:g(α)h\f:g(ν))\(41)\+(2))"


def test_auto_style_route_uses_otpu_for_exact_fixed_binding(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "ftir.csv"
    processed.write_text(
        "BiOBr0.5Cl0.5_wavenumber_cm-1,BiOBr0.5Cl0.5_transmittance,"
        "CuWO4_wavenumber_cm-1,CuWO4_transmittance,"
        "BiCu-10_wavenumber_cm-1,BiCu-10_transmittance\n"
        "1000,1,1000,2,1000,3\n900,1.1,900,2.1,900,3.1\n",
        encoding="utf-8",
    )
    product = _dual_mode_ftir_product(
        tmp_path,
        processed,
        ["BiOBr0.5Cl0.5", "CuWO4", "BiCu-10"],
    )
    exact, adaptive = _dual_mode_assets(tmp_path)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_runtime_style_asset", lambda *_a, **_k: exact)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_adaptive_style_asset", lambda *_a, **_k: adaptive)

    decision, selected = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="auto")

    assert selected is exact
    assert decision["selected_mode"] == "otpu"
    assert decision["otpu_one_to_one_allowed"] is True
    assert decision["automatic_error_fallback"] is False


def test_auto_style_route_uses_oth_json_only_for_cardinality_mismatch(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "ftir.csv"
    processed.write_text(
        "A_wavenumber_cm-1,A_transmittance,B_wavenumber_cm-1,B_transmittance\n"
        "1000,1,1000,2\n900,1.1,900,2.1\n",
        encoding="utf-8",
    )
    product = _dual_mode_ftir_product(tmp_path, processed, ["A", "B"])
    exact, adaptive = _dual_mode_assets(tmp_path)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_runtime_style_asset", lambda *_a, **_k: exact)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_adaptive_style_asset", lambda *_a, **_k: adaptive)

    decision, selected = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="auto")

    assert selected is adaptive
    assert decision["selected_mode"] == "oth-json"
    assert decision["reason_code"] == "auto_series_cardinality_mismatch_only"
    assert decision["current_series_count"] == 2
    assert decision["contract_series_count"] == 3
    assert decision["otpu_one_to_one_allowed"] is False


def test_explicit_otpu_never_falls_back_to_oth_json(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "ftir.csv"
    processed.write_text(
        "A_wavenumber_cm-1,A_transmittance,B_wavenumber_cm-1,B_transmittance\n"
        "1000,1,1000,2\n",
        encoding="utf-8",
    )
    product = _dual_mode_ftir_product(tmp_path, processed, ["A", "B"])
    exact, adaptive = _dual_mode_assets(tmp_path)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_runtime_style_asset", lambda *_a, **_k: exact)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_adaptive_style_asset", lambda *_a, **_k: adaptive)

    decision, selected = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="otpu")

    assert selected is None
    assert decision["ok"] is False
    assert decision["reason_code"] == "verified_otpu_binding_mismatch"
    assert decision["automatic_error_fallback"] is False


def test_explicit_oth_json_allows_candidate_resolution(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "ftir.csv"
    processed.write_text(
        "A_wavenumber_cm-1,A_transmittance\n1000,1\n",
        encoding="utf-8",
    )
    product = _dual_mode_ftir_product(tmp_path, processed, ["A"])
    _exact, adaptive = _dual_mode_assets(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_runtime_style_asset", lambda *_a, **_k: None)

    def resolve_adaptive(*_args, **kwargs):
        captured.update(kwargs)
        return adaptive

    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_adaptive_style_asset", resolve_adaptive)

    decision, selected = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="oth-json")

    assert selected is adaptive
    assert captured["allow_candidate"] is True
    assert decision["candidate_assets_allowed"] is True
    assert decision["selected_mode"] == "oth-json"


def test_explicit_oth_json_blocks_unpaired_numeric_source(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "ftir.csv"
    processed.write_text(
        "A_wavenumber_cm-1,A_transmittance\n1000,\n900,1\n",
        encoding="utf-8",
    )
    product = _dual_mode_ftir_product(tmp_path, processed, ["A"])
    _exact, adaptive = _dual_mode_assets(tmp_path)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_runtime_style_asset", lambda *_a, **_k: None)
    monkeypatch.setattr("src.core.template_format_executor.resolve_origin_adaptive_style_asset", lambda *_a, **_k: adaptive)

    decision, selected = _resolve_origin_style_execution_route(tmp_path, product, requested_mode="oth-json")

    assert selected is None
    assert decision["ok"] is False
    assert decision["reason_code"] == "adaptive_source_binding_invalid"
    assert decision["automatic_error_fallback"] is False


def test_adaptive_eis_legend_uses_all_current_series_not_fixed_visible_slots(tmp_path: Path, monkeypatch) -> None:
    processed = tmp_path / "eis.csv"
    processed.write_text("x,y\n0,1\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        product_key="EIS",
        legend_entries=["A", "B", "C", "D"],
    )
    class PlotOps(_FakeAxisOps):
        def _plot_names(self, _graph_name: str) -> list[str]:
            return ["Plot1", "Plot2", "Plot3", "Plot4"]

    ops = PlotOps()
    captured: dict[str, object] = {}

    def set_text(_ops, _graph, _name, text):
        captured["text"] = text
        return True

    monkeypatch.setattr("src.core.template_format_executor._set_origin_graph_object_text", set_text)
    monkeypatch.setattr(
        "src.core.template_format_executor._format_preserved_line_sample_legend",
        lambda *_a, **_k: {"applied": True},
    )

    policy = _apply_adaptive_dynamic_legend_policy(
        ops,
        "Graph1",
        product,
        ResolvedPlotStyle(),
        {"layout_values": {"legend.fsize": 28}},
    )

    assert policy["visible_plot_indices"] == [1, 2, 3, 4]
    assert policy["entries"] == ["A", "B", "C", "D"]
    assert "\\l(4)" in str(captured["text"])
    assert policy["line_samples_preserved"] is True
    assert policy["font_size"] == 28
    assert policy["all_current_plots_visible"] is True
    assert all(
        f"layer.plot{index}.show=1" in "\n".join(ops.commands)
        for index in range(1, 5)
    )


def test_adaptive_photocurrent_legend_restores_snapshot_format_and_current_entries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    processed = tmp_path / "photocurrent.csv"
    processed.write_text("x,y\n0,1\n", encoding="utf-8")
    product = replace(
        _product(tmp_path, processed),
        product_key="photocurrent",
        legend_entries=["BOBC", "CWO"],
    )
    ops = _FakeAxisOps()
    captured: dict[str, object] = {}

    def set_text(_ops, _graph, _name, value):
        captured["text"] = value
        return True

    def style_object(*_args, **kwargs):
        captured["style"] = kwargs
        return True

    monkeypatch.setattr(
        "src.core.template_format_executor._set_origin_graph_object_text",
        set_text,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._style_graph_object",
        style_object,
    )
    snapshot = {
        "audit_string_values": {
            "xb.text$": r"\b(Time (s))",
            "yl.text$": r"\b(Photocurrent (μA))",
        },
        "layout_values": {
            "layer.x.from": 20.0,
            "layer.x.to": 250.0,
            "layer.y.from": -1e-8,
            "layer.y.to": 2e-7,
            "legend.x": 247.5,
            "legend.y": 1.75e-6,
            "legend.fsize": 14,
            "legend.bold": 0,
            "legend.background": 1,
            "legend.border": 0,
            "legend.frame": 0,
            "legend.fill": 0,
            "legend.fillColor": -4,
            "legend.borderColor": 1,
            "legend.lineWidth": 1,
        },
    }

    policy = _apply_adaptive_photocurrent_oth_json_text_policy(
        ops,
        "Graph1",
        product,
        ResolvedPlotStyle(),
        snapshot,
    )

    assert policy["applied"] is True
    assert policy["entries"] == ["BOBC", "CWO"]
    assert "\\l(1)\\b( BOBC)" in str(captured["text"])
    assert "\\l(2)\\b( CWO)" in str(captured["text"])
    assert policy["font_size"] == 14
    assert policy["bold"] == 0
    assert policy["background"] == 1
    assert captured["style"]["bold"] == 0
    assert captured["style"]["fill_color"] == -4
    assert any("legend.show=1" in command for command in ops.commands)
    assert any("legend.fsize=14" in command for command in ops.commands)


def test_adaptive_photocurrent_supports_arbitrary_current_series_count_and_labels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    labels = ["Current A", "Current B", "Current C", "Current D"]
    headers = [
        header
        for label in labels
        for header in (
            f"{label.replace(' ', '_')}_time_s",
            f"{label.replace(' ', '_')}_current_a",
        )
    ]
    processed = tmp_path / "photocurrent_four_series.csv"
    processed.write_text(
        ",".join(headers) + "\n" + ",".join(str(index) for index in range(8)) + "\n",
        encoding="utf-8",
    )
    product = replace(
        _product(tmp_path, processed),
        product_key="photocurrent",
        legend_entries=labels,
    )
    pairs = _processed_csv_plot_pairs(product, headers)
    assert pairs == [(1, 2), (3, 4), (5, 6), (7, 8)]

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "src.core.template_format_executor._set_origin_graph_object_text",
        lambda _ops, _graph, _name, value: captured.setdefault("text", value) == value,
    )
    monkeypatch.setattr(
        "src.core.template_format_executor._style_graph_object",
        lambda *_args, **_kwargs: True,
    )
    result = _apply_adaptive_photocurrent_oth_json_text_policy(
        _FakeAxisOps(),
        "Graph2",
        product,
        ResolvedPlotStyle(),
            {
                "audit_string_values": {
                    "xb.text$": r"\b(Time (s))",
                    "yl.text$": r"\b(Photocurrent (μA))",
                },
                "layout_values": {
                    "layer.x.from": 20.0,
                    "layer.x.to": 250.0,
                    "layer.y.from": -1e-8,
                    "layer.y.to": 2e-7,
                    "legend.x": 190.0,
                    "legend.y": 1.5e-7,
                },
            },
    )

    assert result["applied"] is True
    assert result["entries"] == labels
    assert "\\l(4)" in captured["text"]
    assert all(label in captured["text"] for label in labels)


def test_oth_json_asset_only_never_loads_reference_opju() -> None:
    asset = SimpleNamespace(
        template_opju_path=Path("reference.opju"),
        graph_page="Graph3",
    )

    source, graph, required = _saved_theme_reference_policy(
        asset,
        {"selected_mode": "oth-json"},
        asset_only=True,
    )

    assert source is None
    assert graph == ""
    assert required is False


def test_adaptive_series_count_conformance_relaxes_only_per_plot_array_lengths() -> None:
    cardinality_fields = {
        "plot_count",
        "plot_colors",
        "plot_line_colors",
        "plot_line_widths",
        "marker_shapes",
        "marker_sizes",
        "plot_visibility",
    }
    conformance = {
        "status": "fail",
        "issues": [
            {
                "field": field,
                "severity": "fail",
                "message": "reference has three values; product has two",
            }
            for field in sorted(cardinality_fields)
        ]
        + [
            {
                "field": "plot_visibility[2]",
                "severity": "fail",
                "message": "the fixed reference plot is hidden but the current adaptive plot is visible",
            }
        ],
    }

    relaxed = _adaptive_series_count_conformance(
        conformance,
        {
            "current_csv_pair_count": 2,
            "reopened_plot_count": 2,
            "contract_series_count": 3,
            "all_current_plots_visible": True,
        },
    )

    assert relaxed["status"] == "pass"
    assert relaxed["issues"] == []
    assert relaxed["adaptive_series_cardinality_relaxed"] is True

    conformance["issues"].append(
        {
            "field": "layer.height",
            "severity": "fail",
            "message": "geometry differs",
        }
    )
    not_relaxed = _adaptive_series_count_conformance(
        conformance,
        {"current_csv_pair_count": 2, "reopened_plot_count": 2},
    )
    assert not_relaxed["status"] == "fail"
    assert [issue["field"] for issue in not_relaxed["issues"]] == [
        "plot_visibility[2]",
        "layer.height",
    ]


def test_adaptive_raman_conformance_uses_natural_source_order_and_cycles() -> None:
    style = {
        "plot_count": 3,
        "plot_colors": ["blue", "yellow", "green"],
        "plot_line_colors": ["blue", "yellow", "green"],
        "plot_line_widths": [1500, 1500, 0],
        "marker_shapes": [0, 0, 0],
        "marker_sizes": [9, 9, 0],
        "plot_visibility": [1, 1, 1],
    }
    data = {
        "plots": [
            {
                "book_name": "Book2",
                "sheet_index": 1,
                "x_col_index": 0,
                "style": {
                    "color": "blue",
                    "line_color": "blue",
                    "line_width_origin_units": 1500,
                    "symbol_shape": 0,
                    "symbol_size": 9,
                },
            },
            {
                "book_name": "Book2",
                "sheet_index": 1,
                "x_col_index": 4,
                "style": {
                    "color": "yellow",
                    "line_color": "yellow",
                    "line_width_origin_units": 1500,
                    "symbol_shape": 0,
                    "symbol_size": 9,
                },
            },
            {
                "book_name": "Book2",
                "sheet_index": 1,
                "x_col_index": 2,
                "style": {
                    "color": "green",
                    "line_color": "green",
                    "line_width_origin_units": 1500,
                    "symbol_shape": 0,
                    "symbol_size": 9,
                },
            },
        ]
    }

    reference = _adaptive_raman_conformance_reference(style, data, 4)

    assert reference["plot_count"] == 4
    assert reference["plot_colors"] == ["blue", "green", "yellow", "blue"]
    assert reference["plot_line_colors"] == ["blue", "green", "yellow", "blue"]
    assert reference["plot_line_widths"] == [1500, 1500, 1500, 1500]
    assert reference["marker_sizes"] == [9, 9, 9, 9]


def test_adaptive_raman_conformance_relaxes_only_verified_layer_count_change() -> None:
    conformance = {
        "status": "fail",
        "issues": [
            {"field": "layer_count", "severity": "fail"},
            {"field": "layer.height", "severity": "fail"},
        ],
    }

    relaxed = _adaptive_series_count_conformance(
        conformance,
        {
            "product_key": "Raman",
            "current_csv_pair_count": 2,
            "contract_series_count": 3,
            "all_current_plots_visible": True,
        },
    )

    assert relaxed["status"] == "fail"
    assert [issue["field"] for issue in relaxed["issues"]] == ["layer.height"]


def test_adaptive_photocurrent_readback_requires_current_xy_values_match() -> None:
    product = SimpleNamespace(product_key="photocurrent")
    decision = {"selected_mode": "oth-json", "contract_series_count": 3}
    matched = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (3, 4)],
        {"plot_count": 2, "plot_visibility": [1, 1]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert matched["ok"] is True
    assert matched["current_plot_values_match_csv"] is True

    mismatch = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (3, 4)],
        {"plot_count": 2, "plot_visibility": [1, 1]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": False, "status": "mismatch"},
    )
    assert mismatch["ok"] is False
    assert mismatch["current_plot_values_match_csv"] is False
    assert "X/Y values" in mismatch["message"]


def test_adaptive_pl_readback_requires_current_xy_and_visible_curves() -> None:
    product = SimpleNamespace(product_key="PL")
    decision = {"selected_mode": "oth-json", "contract_series_count": 3}

    matched = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (1, 3)],
        {"plot_count": 2, "plot_visibility": [1, 1]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert matched["ok"] is True
    assert matched["all_current_plots_visible"] is True
    assert matched["current_plot_values_match_csv"] is True

    hidden = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (1, 3)],
        {"plot_count": 2, "plot_visibility": [1, 0]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert hidden["ok"] is False
    assert "not every current CSV curve is visible" in hidden["message"]

    wrong_data = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (1, 3)],
        {"plot_count": 2, "plot_visibility": [1, 1]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": False, "status": "mismatch"},
    )
    assert wrong_data["ok"] is False
    assert "X/Y values" in wrong_data["message"]


def test_adaptive_pl_reopened_styles_use_reviewed_native_cycle() -> None:
    styles = [
        {
            "color": color,
            "line_color": color,
            "line_width_origin_units": 1500.0,
            "line_width_pt": 3.0,
            "line_style": 1.0,
            "symbol_shape": 0.0,
            "symbol_size": 9.0,
        }
        for color in (10.0, 20.0, 30.0)
    ]
    reference = {
        "status": "ready",
        "plots": [
            {"layer_index": 1, "plot_index": index, "style": style}
            for index, style in enumerate(styles, start=1)
        ],
    }
    current = {
        "plots": [
            {"layer_index": 1, "plot_index": index, "style": dict(styles[index - 1])}
            for index in range(1, 3)
        ]
    }

    matched = _validate_adaptive_reopened_plot_style_cycle(
        reference,
        current,
        product_key="PL",
        reference_plot_count=3,
        expected_plot_count=2,
    )
    assert matched["ok"] is True
    current["plots"][1]["style"]["line_color"] = 999.0
    rejected = _validate_adaptive_reopened_plot_style_cycle(
        reference,
        current,
        product_key="PL",
        reference_plot_count=3,
        expected_plot_count=2,
    )
    assert rejected["ok"] is False
    assert "line_color" in rejected["message"]


def test_adaptive_eis_uses_reviewed_visible_marker_cycle_after_reopen() -> None:
    styles = [
        {
            "color": float(100 + index),
            "line_color": 1.0,
            "line_width_origin_units": 250.0,
            "line_width_pt": 0.5,
            "line_style": 0.0,
            "symbol_shape": 20.0,
            "symbol_size": 12.0,
        }
        for index in range(1, 9)
    ]
    reference = {
        "status": "ready",
        "plots": [
            {"layer_index": 1, "plot_index": index, "style": style}
            for index, style in enumerate(styles, start=1)
        ],
    }
    current = {
        "status": "ready",
        "plots": [
            {
                "layer_index": 1,
                "plot_index": index,
                "style": dict(styles[index + 1]),
            }
            for index in range(1, 4)
        ],
    }

    matched = _validate_adaptive_eis_reopened_plot_styles(
        reference,
        current,
        expected_plot_count=3,
    )
    conformance = _adaptive_eis_conformance_reference(
        {"plot_count": 8, "plot_visibility": [0, 0, 1, 1, 1, 0, 0, 0]},
        reference,
        3,
        {"audit_string_values": {"legend.text$": "current"}},
    )

    assert matched["ok"] is True
    assert conformance["plot_count"] == 3
    assert conformance["plot_colors"] == [103.0, 104.0, 105.0]
    assert conformance["plot_visibility"] == [1.0, 1.0, 1.0]

    current["plots"][1]["style"]["symbol_shape"] = 18.0
    rejected = _validate_adaptive_eis_reopened_plot_styles(
        reference,
        current,
        expected_plot_count=3,
    )
    assert rejected["ok"] is False
    assert "symbol_shape" in rejected["message"]
    assert rejected["plots"][1]["expected_style"]["symbol_shape"] == 20.0
    assert rejected["plots"][1]["current_style"]["symbol_shape"] == 18.0


def test_adaptive_eis_custom_marker_color_is_restored_after_independent_line_color() -> None:
    class _PlotStyleOps:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def _plot_names(self, _graph_name: str) -> list[str]:
            return ["Book1_B"]

        def run_labtalk(self, command: str) -> OperationResult:
            self.commands.append(command)
            return OperationResult(True, "ok")

    operations = _PlotStyleOps()
    marker_color = 30847682.0
    line_color = 26724605.0
    restored = _apply_reviewed_template_plot_styles(
        operations,
        "Graph1",
        {
            "plots": [
                {
                    "style": {
                        "color": marker_color,
                        "line_color": line_color,
                        "line_width_pt": 0.5,
                        "line_style": 0.0,
                        "symbol_shape": 20.0,
                        "symbol_size": 12.0,
                    }
                }
            ]
        },
        preserve_custom_rgb=True,
    )

    assert restored["applied"] is True
    command = operations.commands[-1]
    marker = "color(194,178,214)"
    line = "color(253,200,151)"
    assert command.index("set Book1_B -cue 1;") < command.index(
        f"set Book1_B -c {marker};"
    )
    assert command.index(f"set Book1_B -c {marker};") < command.index(
        f"set Book1_B -cl {line};",
        command.index(f"set Book1_B -c {marker};"),
    )
    assert command.index(f"set Book1_B -cl {line};", command.index(f"set Book1_B -c {marker};")) < command.index(
        f"set Book1_B -cse {marker};"
    )


def test_adaptive_eis_readback_requires_visible_current_xy() -> None:
    product = SimpleNamespace(product_key="EIS")
    decision = {
        "selected_mode": "oth-json",
        "contract_series_count": 8,
    }
    matched = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (3, 4), (5, 6)],
        {"layer_count": 1, "plot_count": 3, "plot_visibility": [1, 1, 1]},
        decision,
        {"status": "pass"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert matched["ok"] is True
    assert matched["all_current_plots_visible"] is True
    assert matched["current_plot_values_match_csv"] is True
    assert matched["eis_adaptive_structure"]["status"] == "matched"

    rejected = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (3, 4), (5, 6)],
        {"layer_count": 1, "plot_count": 3, "plot_visibility": [1, 0, 1]},
        decision,
        {"status": "pass"},
        current_data_validation={"ok": False, "status": "mismatch"},
    )
    assert rejected["ok"] is False
    assert "visible" in rejected["message"]
    assert "X/Y" in rejected["message"]


def test_adaptive_photocurrent_validation_ranges_keep_per_pair_row_counts() -> None:
    rows = [
        [0.0, 1.0, 0.0, 2.0],
        [1.0, 1.5, 1.0, 2.5],
        [2.0, 1.25, math.nan, math.nan],
    ]


    assert _adaptive_photocurrent_validation_ranges(
        rows,
        [(1, 2), (3, 4)],
    ) == [
        {
            "x_col": 1,
            "y_col": 2,
            "row_from": 1,
            "row_to": 3,
            "source_x_index": 0,
            "source_y_index": 1,
            "source_row_from": 1,
            "source_row_to": 3,
        },
        {
            "x_col": 3,
            "y_col": 4,
            "row_from": 1,
            "row_to": 2,
            "source_x_index": 2,
            "source_y_index": 3,
            "source_row_from": 1,
            "source_row_to": 2,
        },
    ]


def test_adaptive_variable_cardinality_blocks_hidden_current_curve() -> None:
    result = _adaptive_oth_json_readback_validation(
        SimpleNamespace(product_key="Mott-Schottky"),
        [(1, 2), (1, 3), (1, 4), (1, 5)],
        {"plot_count": 4, "plot_visibility": [1, 1, 1, 0]},
        {"selected_mode": "oth-json", "contract_series_count": 5},
        {"status": "fail"},
        current_data_validation={"ok": True, "status": "matched"},
    )

    assert result["ok"] is False
    assert result["all_current_plots_visible"] is False
    assert "not every current CSV curve is visible" in result["message"]


def test_adaptive_bet_readback_requires_current_xy_values_match() -> None:
    product = SimpleNamespace(product_key="BET")
    decision = {"selected_mode": "oth-json", "contract_series_count": 6}

    matched = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (3, 4)],
        {"plot_count": 2, "plot_visibility": [1, 1]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": True, "status": "matched"},
    )
    assert matched["ok"] is True
    assert matched["current_plot_values_match_csv"] is True

    mismatch = _adaptive_oth_json_readback_validation(
        product,
        [(1, 2), (3, 4)],
        {"plot_count": 2, "plot_visibility": [1, 1]},
        decision,
        {"status": "fail"},
        current_data_validation={"ok": False, "status": "mismatch"},
    )
    assert mismatch["ok"] is False
    assert mismatch["current_plot_values_match_csv"] is False
    assert "X/Y values" in mismatch["message"]
