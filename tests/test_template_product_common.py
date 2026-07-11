from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from src.core.template_product_common import (
    ProductContext,
    TargetPairing,
    _build_processed_plot_table,
    extract_xrd_raw_data_rows,
    export_product_with_origin,
    build_default_root_map,
    load_target_pairings,
    _write_no_label_audit,
)


def test_default_root_map_allows_local_pairing_root_overrides(tmp_path: Path) -> None:
    project = tmp_path / "project"
    config = project / "config"
    config.mkdir(parents=True)
    (config / "default.yaml").write_text("project:\n  name: test\n", encoding="utf-8")
    (config / "local.yaml").write_text(
        "template_pairing_roots:\n"
        "  f_drive_detection: external/raw\n"
        "  workspace_xps_data: external/xps\n",
        encoding="utf-8",
    )

    roots = build_default_root_map(project)

    assert roots["f_drive_detection"] == project / "external" / "raw"
    assert roots["workspace_xps_data"] == project / "external" / "xps"
    assert roots["origin_manual_save"] == project / "templates" / "origin_styles" / "reference_opju"


def test_load_target_pairings_selects_only_authorized_product_types(tmp_path: Path) -> None:
    roots = _root_map(tmp_path)
    pairing = tmp_path / "pairing.json"
    _write_pairing(
        pairing,
        [
            _pair("BET", "", "f_drive_detection", ["BET/bet.csv"], "f_drive_detection", "BET/style.opju"),
            _pair("XRD", "", "f_drive_detection", ["XRD/xrd.txt"], "f_drive_detection", "XRD/style.opju"),
            _pair("EPR", "", "f_drive_detection", ["EPR/epr.xlsx"], "f_drive_detection", "EPR/style.opju"),
            _pair("XPS", "XPS_in_situ", "workspace_xps_data", ["insitu/bobc.xlsx"], "workspace_xps_reference", "insitu.opju"),
            _pair("XPS", "XPS_non_in_situ", "workspace_xps_data", ["non/bc.xlsx"], "workspace_group_data", "xps/out.opju"),
            _pair("HPLC/LC exported data", "", "f_drive_detection", ["LC/lc.pdf"], "", ""),
            _pair("Raman", "", "f_drive_detection", ["Raman/r.txt"], "f_drive_detection", "Raman/style.opju"),
        ],
    )

    selected = load_target_pairings(pairing, roots)

    assert [item.product_key for item in selected] == ["BET", "XRD", "EPR", "XPS_in_situ", "XPS_non_in_situ"]
    assert selected[0].data_paths == [roots["f_drive_detection"] / "BET" / "bet.csv"]
    assert selected[3].reference_opju == roots["workspace_xps_reference"] / "insitu.opju"
    assert all("HPLC" not in item.product_key and item.product_key != "Raman" for item in selected)


def test_extract_xrd_raw_data_rows_uses_only_bracketed_data_section(tmp_path: Path) -> None:
    raw = tmp_path / "xrd.txt"
    raw.write_text(
        "\n".join(
            [
                ";RAW4.00",
                "NumberOfMeasuredData=3855",
                "PSDOpening=14.325",
                "",
                "[Data]",
                "Angle, PSD",
                "5, 824",
                "5.01946, 894",
                "5.03892, 849",
                "",
                "[Other]",
                "1, 999999",
            ]
        ),
        encoding="utf-8",
    )

    rows = extract_xrd_raw_data_rows(raw)

    assert rows == [[5.0, 824.0], [5.01946, 894.0], [5.03892, 849.0]]


def test_xrd_product_label_uses_greek_theta_axis_title(tmp_path: Path) -> None:
    raw = tmp_path / "xrd.txt"
    raw.write_text(
        "\n".join([";RAW4.00", "[Data]", "Angle, PSD", "5, 824", "6, 900", ""]),
        encoding="utf-8",
    )
    pairing = TargetPairing("XRD", "XRD", "", "root", [raw], "root", tmp_path / "style.opju")

    _headers, _rows, labels = _build_processed_plot_table(pairing)

    assert labels["x_label"] == "2θ (degree)"


def test_export_product_with_origin_creates_output_parents_before_saving(tmp_path: Path, monkeypatch) -> None:
    processed = _write(tmp_path / "processed" / "plot.csv", "x,y\n1,2\n2,3\n")
    reference = _write(tmp_path / "reference.opju", "reference")
    pairing = TargetPairing("BET", "BET", "", "root", [processed], "root", reference)
    product = ProductContext(
        product_key="BET",
        slug="bet_test",
        pairing=pairing,
        processed_data=processed,
        type_root=tmp_path / "missing" / "BET",
        input_copies=[],
        reference_opju_copy=reference,
        reference_preview_png=tmp_path / "missing" / "BET" / "reference_exports" / "bet_test_reference_preview.png",
        origin_file=tmp_path / "missing" / "origin_files" / "BET" / "bet_test.opju",
        figure_tif=tmp_path / "missing" / "figures_tif" / "BET" / "bet_test.tif",
        preview_png=tmp_path / "missing" / "figures_preview" / "BET" / "bet_test.png",
        x_label="x",
        y_label="y",
        graph_title="title",
        legend_entries=["measured"],
    )
    fake = _FakeOriginOps()
    monkeypatch.setattr("src.core.template_product_common.connect_origin", lambda **_kwargs: fake)

    result = export_product_with_origin(product)

    assert result["ok"] is True
    assert product.origin_file.exists()
    assert product.figure_tif.exists()
    assert product.preview_png.exists()
    assert fake.save_parent_existed is True
    assert fake.axis_title == ""
    assert fake.legend_visible == [False]
    assert fake.line_widths == [3.0]
    assert any("xb.bold=1" in script and "yl.bold=1" in script for script in fake.labtalk_scripts)
    assert fake.app.objects["XB"].Text == r"\b(x)"
    assert fake.app.objects["YL"].Text == r"\b(y)"
    assert fake.app.objects["XB"].props["fsize"] == 28
    assert fake.app.objects["YL"].props["bold"] == 1
    assert fake.app.objects["YL"].Top >= 120
    assert fake.app.objects["XB"].Top <= 3200


def test_no_label_audit_ignores_absolute_path_values_in_metadata(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    _write(run_root / "metadata" / "BET" / "meta.json", '{"source": "D:\\\\Codex Project\\\\file.csv"}')
    _write(run_root / "reports" / "visible.md", "No forbidden visible label here.\n")

    _write_no_label_audit(run_root)

    audit = json.loads((run_root / "reports" / "product_no_label_audit.json").read_text(encoding="utf-8"))
    assert audit["hit_count"] == 0
    assert "forbidden_labels" not in audit
    assert (run_root / "reports" / "product_label_audit.md").exists()
    assert not (run_root / "reports" / "product_no_codex_label_audit.md").exists()
    assert not (run_root / "reports" / "product_no_codex_label_audit.json").exists()


def _root_map(tmp_path: Path) -> dict[str, Path]:
    return {
        "f_drive_detection": tmp_path / "f_drive",
        "workspace_xps_data": tmp_path / "workspace" / "XPS",
        "workspace_xps_reference": tmp_path / "xps_reference",
        "workspace_group_data": tmp_path / "workspace",
    }


def _pair(
    data_type: str,
    xps_subtype: str,
    data_root: str,
    data_paths: list[str],
    opju_root: str,
    opju_path: str,
) -> dict[str, object]:
    return {
        "data_type": data_type,
        "xps_subtype": xps_subtype,
        "selected_data_root_label": data_root,
        "selected_data_relative_paths": data_paths,
        "selected_opju_root_label": opju_root,
        "selected_opju_relative_path": opju_path,
        "opju_validation_status": "valid_exemplar" if opju_path else "missing_opju",
        "planned_output_subdir": xps_subtype or data_type.replace("/", "_").replace(" ", "_"),
    }


def _write_pairing(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_xy_xlsx(path: Path, rows: list[tuple[float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    for x_value, y_value in rows:
        sheet.append([x_value, y_value])
    workbook.save(path)


def _write_xps_workbook(path: Path, sheets: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        for sheet_name, components in sheets.items():
            padding = [["" for _ in range(8)] for _ in range(14)]
            header = ["Binding Energy (E)", *components, "Backgnd.", "Envelope", "Residuals"]
            units = ["eV", *["Counts / s" for _ in components], "Counts / s", "Counts / s", "Counts / s"]
            data = [
                [168.0, 10.0, *([3.0] * (len(components) - 1)), 1.0, 9.5, 0.5],
                [167.5, 40.0, *([12.0] * (len(components) - 1)), 2.0, 38.0, 2.0],
                [167.0, 12.0, *([4.0] * (len(components) - 1)), 1.0, 11.0, 1.0],
            ]
            pd.DataFrame([*padding, header, units, *data]).to_excel(writer, sheet_name=sheet_name, header=False, index=False)


class _FakeResult:
    def __init__(self, ok: bool = True, message: str = "ok", payload: dict[str, object] | None = None) -> None:
        self.ok = ok
        self.message = message
        self.payload = payload or {}


class _FakeOriginOps:
    def __init__(self) -> None:
        self.save_parent_existed = False
        self.axis_title = None
        self.legend_visible: list[bool] = []
        self.line_widths: list[float] = []
        self.labtalk_scripts: list[str] = []
        self.app = _FakeOriginApp()

    def load_project(self, _path: Path) -> _FakeResult:
        return _FakeResult()

    def list_worksheets(self) -> _FakeResult:
        return _FakeResult(payload={"pages": [{"name": "Graph1", "type": "graph"}]})

    def run_labtalk(self, _script: str) -> _FakeResult:
        self.labtalk_scripts.append(_script)
        return _FakeResult()

    def get_labtalk_variable(self, _name: str) -> _FakeResult:
        return _FakeResult(payload={"value": 10.0})

    def new_project(self) -> _FakeResult:
        return _FakeResult()

    def import_csv_to_worksheet(self, _path: Path, book_name: str = "", delimiter: str = ",") -> _FakeResult:
        return _FakeResult(payload={"book_name": book_name or "Book1"})

    def create_graph(self, graph_name: str, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult(payload={"graph_name": graph_name})

    def add_plot_to_graph(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    def set_graph_font(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    def apply_graph4_fixed_style(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    def set_axis_labels(self, _graph_name: str, _x_label: str = "", _y_label: str = "", title: str = "") -> _FakeResult:
        self.axis_title = title
        return _FakeResult()

    def set_axis_range(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    def set_tick_style(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    def set_axis_and_tick_visibility(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    def set_legend(self, _graph_name: str, visible: bool = True, *_args, **_kwargs) -> _FakeResult:
        self.legend_visible.append(visible)
        return _FakeResult()

    def set_plot_style(self, *_args, **_kwargs) -> _FakeResult:
        if "line_width" in _kwargs:
            self.line_widths.append(float(_kwargs["line_width"]))
        return _FakeResult()

    def save_project(self, path: Path) -> _FakeResult:
        self.save_parent_existed = path.parent.exists()
        path.write_text("opju", encoding="utf-8")
        return _FakeResult()

    def export_graph(self, _graph_name: str, path: Path, _format: str) -> _FakeResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("figure", encoding="utf-8")
        return _FakeResult()

    def close(self) -> _FakeResult:
        return _FakeResult()


class _FakeGraphObject:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.Text = ""
        self.props: dict[str, object] = {}
        self.Top = -390 if name == "YL" else 3384

    def SetNumProp(self, prop: str, value: object) -> None:
        self.props[prop] = value


class _FakeGraphObjects:
    def __init__(self, objects: list[_FakeGraphObject]) -> None:
        self._objects = objects
        self.Count = len(objects)

    def Item(self, index: int) -> _FakeGraphObject:
        return self._objects[index]


class _FakeLayer:
    def __init__(self, objects: dict[str, _FakeGraphObject]) -> None:
        self.GraphObjects = _FakeGraphObjects(list(objects.values()))


class _FakeOriginApp:
    def __init__(self) -> None:
        self.objects = {"XB": _FakeGraphObject("XB"), "YL": _FakeGraphObject("YL")}

    def FindGraphLayer(self, _name: str) -> _FakeLayer:
        return _FakeLayer(self.objects)
