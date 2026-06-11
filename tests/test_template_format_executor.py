from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from src.cli import main
from src.core.opju_product_pilot import ProductContext, TargetPairing
from src.core.template_format_executor import (
    TEMPLATE_FORMAT_COMMAND,
    TEMPLATE_FORMAT_SCOPE,
    TemplateFormatExecutorOptions,
    _apply_template_base_global_policies,
    _strip_raster_metadata,
    apply_template_base_data_replacement,
    build_template_format_v3_options,
    export_template_base_product_with_origin,
)
from src.origin.operations import OperationResult
from src.origin.user_style import ResolvedPlotStyle


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


class _FakeCachedStyleOps:
    def __init__(self) -> None:
        self.created_from_template: Path | None = None
        self.saved_paths: list[Path] = []
        self.exported_paths: list[Path] = []
        self.closed = False
        self.commands: list[str] = []

    def new_project(self) -> OperationResult:
        return OperationResult(True, "new")

    def import_csv_to_worksheet(self, _path: Path, book_name: str = "", delimiter: str = ",") -> OperationResult:
        return OperationResult(True, "imported", {"book_name": book_name or "Book1"})

    def create_graph_from_template(self, graph_name: str, template_path: Path) -> OperationResult:
        self.created_from_template = template_path
        return OperationResult(True, "created", {"graph_name": graph_name})

    def add_plot_to_graph(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "added")

    def set_axis_labels(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "axis")

    def apply_graph4_fixed_style(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "style")

    def set_tick_style(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "ticks")

    def set_axis_and_tick_visibility(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "visibility")

    def set_legend(self, *_args: object, **_kwargs: object) -> OperationResult:
        return OperationResult(True, "legend")

    def run_labtalk(self, command: str) -> OperationResult:
        self.commands.append(command)
        return OperationResult(True, "labtalk")

    def save_project(self, path: Path) -> OperationResult:
        self.saved_paths.append(Path(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"opju")
        return OperationResult(True, "saved")

    def export_graph(self, _graph_name: str, path: Path, _format: str, **_kwargs: object) -> OperationResult:
        self.exported_paths.append(Path(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"figure")
        return OperationResult(True, "exported")

    def close(self) -> OperationResult:
        self.closed = True
        return OperationResult(True, "closed")


def test_template_format_v3_options_keep_v5_scope_separate(tmp_path: Path) -> None:
    options = build_template_format_v3_options(
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
    assert options.product_slug_version == "v5_template_format"
    assert options.with_origin is True
    assert options.xps_non_in_situ_template_root == tmp_path / "xps_non"
    assert options.xps_reference_templates_for_all_xps is True
    assert options.xps_templates_from_reference_only is True
    assert options.xps_smooth_gradient_fill is True
    assert options.cleanup_empty_run_layout_dirs is True


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


def test_export_template_base_uses_project_style_asset_when_reference_opju_missing(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    style_root = project_root / "templates" / "origin_styles"
    template = style_root / "graph_templates" / "BET.otpu"
    template.parent.mkdir(parents=True)
    template.write_bytes(b"otpu")
    (style_root / "manifest.json").write_text(
        '{"schema_version":1,"assets":[{"product_key":"BET","data_type":"BET","graph_page":"Graph3","graph_template":"graph_templates/BET.otpu","status":"accepted"}]}',
        encoding="utf-8",
    )
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a,b\n0,10,20\n1,11,21\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    fake = _FakeCachedStyleOps()
    monkeypatch.setattr("src.core.template_format_executor.connect_origin", lambda **_kwargs: fake)

    result = export_template_base_product_with_origin(product, ResolvedPlotStyle(), project_root=project_root)

    assert result["ok"] is True
    assert result["template_format_plan"]["mode"] == "cached_style_package"
    assert result["origin_processing"]["method"] == "cached_style_package_graph_template"
    assert result["origin_processing"]["neutral_runtime"] is True
    assert fake.created_from_template is not None
    assert fake.created_from_template.name == template.name
    assert "codex" not in str(fake.created_from_template).casefold()
    assert project_root not in fake.created_from_template.parents
    assert fake.saved_paths and fake.saved_paths[0] != product.origin_file
    assert fake.exported_paths and product.figure_tif not in fake.exported_paths
    assert product.origin_file.exists()
    assert product.figure_tif.exists()
    assert product.preview_png.exists()
    assert fake.closed is True


def test_strip_raster_metadata_removes_tiff_description_paths(tmp_path: Path) -> None:
    from PIL import Image, TiffImagePlugin

    figure = tmp_path / "figure.tif"
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[270] = r"D:\Codex Project\科研数据处理\product.opju"
    Image.new("RGB", (8, 6), "white").save(figure, tiffinfo=tags)
    assert b"Codex Project" in figure.read_bytes()

    warning = _strip_raster_metadata(figure, dpi=600)

    assert warning == ""
    cleaned = figure.read_bytes()
    assert b"Codex Project" not in cleaned
    assert b":\\" not in cleaned


def test_cli_unified_v5_template_format_passes_options(tmp_path: Path, monkeypatch) -> None:
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
            "run_root": str(output_root / "runs" / "20260607_210000_unified_v5_template_format_conformance_all_types"),
            "summary": {"product_count": 11, "success_count": 0, "blocked_count": 11, "failed_count": 0},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.run_template_format_executor", fake_run)

    code = main(
        [
            "unified-v5-template-format-conformance-all-types",
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
        ]
    )

    assert code == 0
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, TemplateFormatExecutorOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.f_drive_template_root == f_root
    assert options.xps_reference_template_root == xps_root
    assert options.xps_non_in_situ_template_root == xps_non_root
    assert options.with_origin is True


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
        slug="BET_v5",
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
