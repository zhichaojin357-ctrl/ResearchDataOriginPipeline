from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path

from src.cli import main
from src.core.template_product_common import ProductContext, TargetPairing
from src.core.template_format_executor import (
    FINAL_TEMPLATE_STYLE_OVERRIDE,
    TEMPLATE_FORMAT_COMMAND,
    TEMPLATE_FORMAT_SCOPE,
    TemplateFormatExecutorOptions,
    _apply_embedded_snapshot_data_axis_range,
    _apply_cached_style_rich_text_policies,
    _apply_external_reference_plot_sequence,
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
    _plain_text_legend_policy,
    _plain_text_legend_entries,
    _prepare_verified_bet_otpu_binding,
    _processed_csv_plot_pairs,
    _refresh_graph_for_export,
    _replace_eis_dynamic_legend_with_static_rich_text,
    _select_plain_legend_anchor,
    _set_origin_graph_object_text,
    _strip_raster_metadata,
    _with_default_xps_non_in_situ_template_root,
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
    assert any("legend.x = layer.x.from" in command for command in ops.commands)


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


def test_uvvis_wavelength_data_overrides_tauc_theme_axis_range(tmp_path: Path) -> None:
    processed = tmp_path / "uvvis.csv"
    processed.write_text(
        "wavelength_nm,BOBC,CWO\n200,1,2\n1000,3,4\n",
        encoding="utf-8",
    )
    product = replace(_product(tmp_path, processed), product_key="UV-vis DRS / Tauc")
    ops = _FakeAxisOps()

    result = _apply_embedded_snapshot_data_axis_range(ops, "Graph2", product)

    assert result == {
        "applied": True,
        "method": "uvvis_wavelength_bounds_after_tauc_style_geometry",
        "x_min": 200.0,
        "x_max": 1000.0,
    }
    assert ops.axis_calls == [{"x_min": 200.0, "x_max": 1000.0, "y_min": None, "y_max": None}]


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


def test_xrd_standard_card_uses_four_sample_plots_plus_card(tmp_path: Path) -> None:
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

    assert _processed_csv_plot_pairs(product, headers) == [(1, 2), (1, 3), (1, 4), (1, 5), (1, 7)]
    assert _plain_text_legend_entries(product) == ["BOBC", "BOBC600", "bobc600", "BOBC BOBC15"]


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
        "layout_values": {"layer.x.from": -1.2, "layer.x.to": 0.78, "layer.y.to": 2.7e9},
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
        "two_theta_deg,BOBC,BOBC600,bobc600,BOBC_BOBC15,BOBC_CWO15,CWO_PDF_04-009-8466_JCPDS_card_sticks\n"
        "5,5.9,5.5,4.3,2.6,1.4,0\n"
        "6,6.0,5.6,4.4,2.7,1.5,10\n",
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
