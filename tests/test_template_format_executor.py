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
    apply_template_base_data_replacement,
    build_template_format_v3_options,
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


def test_template_base_global_policy_writes_bold_axis_title_text(tmp_path: Path) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n", encoding="utf-8")
    product = _product(tmp_path, processed)
    ops = _FakeTemplateOps()

    _apply_template_base_global_policies(ops, "Graph1", product, ResolvedPlotStyle())

    commands = "\n".join(ops.commands)
    assert 'xb.text$="\\\\b(Relative Pressure)"' in commands
    assert 'yl.text$="\\\\b(Quantity Adsorbed)"' in commands
    assert "xb.bold=1; yl.bold=1" in commands


def test_template_base_global_policy_writes_bold_legend_without_rebuild(tmp_path: Path) -> None:
    processed = tmp_path / "processed.csv"
    processed.write_text("x,a\n0,10\n", encoding="utf-8")
    product = replace(_product(tmp_path, processed), product_key="Raman", legend_entries=["BOBC", "CWO"])
    ops = _FakeTemplateOps()

    _apply_template_base_global_policies(ops, "Graph1", product, ResolvedPlotStyle())

    commands = "\n".join(ops.commands)
    assert "legend.text$ = \\l(1) \\b(BOBC)" in commands
    assert "\\l(2) \\b(CWO)" in commands
    assert "legend -r" not in commands


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
