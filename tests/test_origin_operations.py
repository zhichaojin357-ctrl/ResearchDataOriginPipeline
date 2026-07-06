from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path
import re

from src.origin.operations import OriginOperations, connect_origin, normalize_export_path, safe_origin_name
from src.origin.plot_policy import GRAPH4_FIXED_STYLE


class FakeDataPlot:
    def __init__(self, name: str):
        self.Name = name


class FakeDataPlots:
    def __init__(self, names: list[str]):
        self._items = [FakeDataPlot(name) for name in names]
        self.Count = len(self._items)

    def Item(self, index: int) -> FakeDataPlot:
        return self._items[index]


class FakeGraphObject:
    def __init__(
        self,
        name: str,
        text: str = "",
        left: float = 0,
        top: float = 0,
        width: float = 0,
        height: float = 0,
    ):
        self.Name = name
        self.Text = text
        self.Left = left
        self.Top = top
        self.Width = width
        self.Height = height


class FakeGraphObjects:
    def __init__(self, items: list[FakeGraphObject]):
        self._items = items

    @property
    def Count(self) -> int:
        return len(self._items)

    def Item(self, index: int) -> FakeGraphObject:
        return self._items[index]


class FakeLayer:
    def __init__(self, app: "FakeOriginApp", plot_names: list[str] | None = None):
        self._app = app
        self.DataPlots = FakeDataPlots(plot_names or ["Book1_B", "Book1_C"])
        self.GraphObjects = FakeGraphObjects(app.graph_objects)

    def Execute(self, script: str) -> bool:
        self._app.Execute(script)
        return True


class FakeOriginApp:
    def __init__(self):
        self.Visible = 0
        self.commands: list[str] = []
        self.saved: list[str] = []
        self.loaded: list[str] = []
        self.closed = False
        self.pages = ["Book1|workbook", "Fig1|graph"]
        self.worksheets: dict[str, list[list[float]]] = {}
        self.ltvars: dict[str, float] = {}
        self.ltstrs: dict[str, str] = {}
        self.putworksheet_fail_above: int | None = None
        self.putworksheet_calls: list[tuple[str, int, int, int]] = []
        self.graph_objects: list[FakeGraphObject] = [
            FakeGraphObject("Legend", "\\l(1)\\b(A)", 3569, 827, 1800, 893),
            FakeGraphObject("Line", "", 3558, 676, 496, 82),
            FakeGraphObject("Text", "\\b(Old)", 4111, 587, 823, 251),
            FakeGraphObject("LineOutside", "", 100, 100, 200, 50),
        ]

    def NewProject(self):
        self.commands.append("NewProject")

    def Save(self, path: str):
        self.saved.append(path)

    def Load(self, path: str):
        self.loaded.append(path)

    def Exit(self):
        self.closed = True

    def CreatePage(self, page_type: int, name: str, template: str):
        self.commands.append(f"CreatePage:{page_type}:{name}:{template}")
        return name

    def Execute(self, script: str):
        self.commands.append(script)
        if "doc -e W" in script:
            return True
        if "expGraph" in script:
            folder = _between(script, 'path:="', '"')
            filename = _between(script, 'filename:="', '"')
            export_type = _after(script, "type:=").split()[0]
            if folder and filename and export_type:
                Path(folder).mkdir(parents=True, exist_ok=True)
                (Path(folder) / f"{filename}.{export_type}").write_bytes(b"fake exported image")
        if "save -t" in script:
            template_path = _between(script, ' "', '"')
            if template_path:
                Path(template_path).parent.mkdir(parents=True, exist_ok=True)
                Path(template_path).write_bytes(b"fake graph template")
        if "run.LoadOC" in script:
            self.ltvars["__rdop_theme_load_err"] = 0.0
        if "__rdop_theme_copy_ok=0" in script:
            self.ltvars["__rdop_theme_copy_ok"] = 0.0
        if "CopyFormat()" in script:
            self.ltvars["__rdop_theme_copy_ok"] = 1.0
        if "__rdop_theme_apply_ok=0" in script:
            self.ltvars["__rdop_theme_apply_ok"] = 0.0
        if "theme_apply_graph_options" in script:
            self.ltvars["__rdop_theme_apply_ok"] = 1.0
        for name in re.findall(r"label\s+-r\s+([A-Za-z0-9_]+)", script):
            self.graph_objects[:] = [item for item in self.graph_objects if item.Name != name]
        for name in re.findall(r"label\s+-n\s+([A-Za-z0-9_]+)\s+-s", script):
            if not any(item.Name == name for item in self.graph_objects):
                self.graph_objects.append(FakeGraphObject(name, "", 0, 0, 0, 0))
        return True

    def PutWorksheet(self, target: str, values: list[float], row: int, col: int):
        self.putworksheet_calls.append((target, len(values), row, col))
        if self.putworksheet_fail_above is not None and len(values) > self.putworksheet_fail_above:
            raise RuntimeError("simulated PutWorksheet memory lock")
        rows = self.worksheets.setdefault(target, [])
        for index, value in enumerate(values):
            row_index = int(row) + index
            while len(rows) <= row_index:
                rows.append([])
            while len(rows[row_index]) <= col:
                rows[row_index].append(float("nan"))
            rows[row_index][col] = value

    def GetWorksheet(self, target: str):
        return self.worksheets.get(target)

    def LTStr(self, name: str):
        if name == "__rdop_pages$":
            return ";".join(self.pages) + ";"
        if name in self.ltstrs:
            return self.ltstrs[name]
        return "hello"

    def LTVar(self, name: str):
        if name in self.ltvars:
            return self.ltvars[name]
        return 42.0

    def FindGraphLayer(self, name: str):
        return FakeLayer(self)


def _between(value: str, left: str, right: str) -> str:
    start = value.find(left)
    if start < 0:
        return ""
    start += len(left)
    end = value.find(right, start)
    if end < 0:
        return ""
    return value[start:end]


def _after(value: str, left: str) -> str:
    start = value.find(left)
    if start < 0:
        return ""
    return value[start + len(left) :]


def _quoted_args(value: str) -> list[str]:
    return re.findall(r'"([^"]*)"', value)


class OriginOperationsSmokeTest(unittest.TestCase):
    def test_project_and_labtalk_operations(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        self.assertTrue(ops.new_project().ok)
        self.assertTrue(ops.save_project("D:/tmp/test.opju").ok)
        self.assertIn('page.comments$=""', "\n".join(app.commands))
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "test.opju"
            project.write_text("fake", encoding="utf-8")
            self.assertTrue(ops.load_project(project).ok)
        self.assertFalse(ops.load_project("missing.opju").ok)
        self.assertTrue(ops.run_labtalk("type -b done;").ok)
        self.assertEqual(ops.get_labtalk_variable("aa").payload["value"], 42.0)
        self.assertEqual(ops.get_labtalk_variable("str$").payload["value"], "hello")
        self.assertTrue(ops.close().ok)
        self.assertTrue(app.closed)

    def test_worksheet_operations_and_csv_import(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        created = ops.create_worksheet("Data", "Raw")
        self.assertTrue(created.ok)
        written = ops.set_worksheet_data("Data", "Sheet1", [[1, 2, 3], [4, 5, 6]], ["X", "Y"])
        self.assertTrue(written.ok)
        read = ops.get_worksheet_data("Data", "Sheet1")
        self.assertTrue(read.ok)
        self.assertEqual(read.payload["columns"], [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        listed = ops.list_worksheets()
        self.assertEqual(listed.payload["pages"], [{"name": "Book1", "type": "workbook"}, {"name": "Fig1", "type": "graph"}])

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "input.csv"
            csv_path.write_text("x,y\n0,1\n1,2\n", encoding="utf-8")
            imported = ops.import_csv_to_worksheet(csv_path, "Imported")
            self.assertTrue(imported.ok)
            self.assertEqual(imported.payload["columns"], 2)

    def test_get_worksheet_data_handles_non_iterable_origin_return(self):
        app = FakeOriginApp()
        app.worksheets["[Bad]Sheet1"] = 1  # Origin can return a status code for inaccessible worksheet refs.
        ops = OriginOperations(app)

        read = ops.get_worksheet_data("Bad", "Sheet1")

        self.assertFalse(read.ok)
        self.assertIn("not iterable", read.message)

    def test_template_workbook_column_replacement_operations(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)

        names = ops.get_graph_plot_dataset_names("Fig1")
        self.assertTrue(names.ok)
        self.assertEqual(names.payload["plot_dataset_names"], ["Book1_B", "Book1_C"])

        replaced = ops.replace_template_workbook_columns(
            {
                "Book1": {
                    0: [0.0, 1.0],
                    1: [10.0, 11.0],
                    2: [20.0, 21.0],
                }
            }
        )

        self.assertTrue(replaced.ok)
        self.assertEqual(app.worksheets["[Book1]Sheet1"], [[0.0, 10.0, 20.0], [1.0, 11.0, 21.0]])
        self.assertEqual(replaced.payload["updated_columns"][2]["book_name"], "Book1")
        self.assertEqual(replaced.payload["updated_columns"][2]["column_index"], 2)
        self.assertEqual(replaced.payload["updated_columns"][2]["rows"], 2)
        self.assertEqual(replaced.payload["updated_columns"][2]["write_mode"], "single")

    def test_graph_plot_dataset_names_use_numeric_layer_references_for_multilayer_graphs(self):
        class MultiLayerOriginApp(FakeOriginApp):
            def FindGraphLayer(self, name: str):
                if name in {"[Fig1]1", "[Fig1]Layer1", "[Fig1]", "Fig1"}:
                    return FakeLayer(self, ["Book1_B", "Book1_D"])
                if name == "[Fig1]2":
                    return FakeLayer(self, ["Book1_F"])
                if name == "[Fig1]3":
                    return FakeLayer(self, ["Book2_B"])
                return None

        app = MultiLayerOriginApp()
        ops = OriginOperations(app)

        layer2 = ops.get_graph_plot_dataset_names("Fig1", layer_index=2)
        all_names = ops._plot_names("Fig1")

        self.assertTrue(layer2.ok)
        self.assertEqual(layer2.payload["plot_dataset_names"], ["Book1_F"])
        self.assertEqual(all_names, ["Book1_B", "Book1_D", "Book1_F", "Book2_B"])

    def test_template_workbook_column_replacement_falls_back_to_chunks(self):
        app = FakeOriginApp()
        app.putworksheet_fail_above = 512
        ops = OriginOperations(app)

        values = [float(index) for index in range(1200)]
        replaced = ops.replace_template_workbook_columns({"Book1": {1: values}})

        self.assertTrue(replaced.ok)
        self.assertEqual(app.worksheets["[Book1]Sheet1"][0][1], 0.0)
        self.assertEqual(app.worksheets["[Book1]Sheet1"][1199][1], 1199.0)
        self.assertEqual(replaced.payload["updated_columns"][0]["write_mode"], "chunked_512")
        self.assertGreater(len(app.putworksheet_calls), 2)

    def test_replace_legend_with_plain_text_labels_removes_template_line_samples(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)

        result = ops.replace_legend_with_plain_text_labels("Fig1", ["BOBC", "BiCu-10"], font_name="Arial", font_size=26)

        self.assertTrue(result.ok)
        names = [item.Name for item in app.graph_objects]
        self.assertNotIn("Legend", names)
        self.assertNotIn("Line", names)
        self.assertIn("Text", names)
        self.assertIn("LineOutside", names)
        labels = {item.Name: item for item in app.graph_objects if item.Name == "Text" or item.Name.startswith("rdop_plain_legend_")}
        self.assertEqual(labels["Text"].Text, r"\b(BOBC)")
        self.assertEqual(labels["rdop_plain_legend_2"].Text, r"\b(BiCu-10)")
        self.assertEqual(labels["Text"].Left, 4111)
        self.assertEqual(labels["Text"].Top, 587)
        self.assertEqual(labels["rdop_plain_legend_2"].Left, 4111)
        self.assertEqual(labels["rdop_plain_legend_2"].Top, 847)
        command_text = "\n".join(app.commands)
        self.assertIn("label -r Legend", command_text)
        self.assertIn("label -r Line", command_text)
        self.assertNotIn("label -r Text", command_text)
        self.assertNotIn('label -n rdop_plain_legend_1 -s " "', command_text)
        self.assertIn('label -n rdop_plain_legend_2 -s " "', command_text)
        self.assertNotIn("label -n rdop_plain_legend_1 -s \\b(BOBC)", command_text)

    def test_replace_legend_with_plain_text_labels_can_reuse_template_text(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)

        result = ops.replace_legend_with_plain_text_labels(
            "Fig1",
            ["Fallback A", "Fallback B"],
            font_name="Arial",
            font_size=26,
            prefer_existing_text=True,
        )

        self.assertTrue(result.ok)
        labels = {item.Name: item for item in app.graph_objects if item.Name == "Text" or item.Name.startswith("rdop_plain_legend_")}
        self.assertEqual(labels["Text"].Text, r"\b(Old)")
        self.assertEqual(labels["rdop_plain_legend_2"].Text, r"\b(A)")
        self.assertEqual(result.payload["text_source"], "existing_legend")

    def test_replace_legend_with_plain_text_labels_uses_native_legend_data_anchor(self):
        app = FakeOriginApp()
        app.graph_objects = [
            FakeGraphObject("Legend", "\\l(1)\\b(A)\r\n\\l(2)\\b(B)", 100, 200, 500, 300),
            FakeGraphObject("Line", "", 120, 220, 80, 10),
        ]
        app.ltvars["legend.x"] = 0.456
        app.ltvars["legend.y"] = 20.074
        ops = OriginOperations(app)

        result = ops.replace_legend_with_plain_text_labels("Fig1", ["BOBC", "CWO"], font_name="Arial", font_size=26)

        self.assertTrue(result.ok)
        labels = {item.Name: item for item in app.graph_objects if item.Name.startswith("rdop_plain_legend")}
        self.assertEqual(list(labels), ["rdop_plain_legend"])
        self.assertEqual(labels["rdop_plain_legend"].Text, "\\b(BOBC)\r\n\\b(CWO)")
        command_text = "\n".join(app.commands)
        self.assertIn("rdop_plain_legend.x=0.456", command_text)
        self.assertIn("rdop_plain_legend.y=20.074", command_text)
        self.assertEqual(result.payload["anchor_data"], {"x": 0.456, "y": 20.074})

    def test_graph_style_and_export_operations(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        self.assertTrue(ops.create_graph("Fig1", "Data", "Sheet1", 1, 2, "line").ok)
        self.assertTrue(ops.add_plot_to_graph("Fig1", "Data", "Sheet1", 1, 3, "scatter").ok)
        self.assertTrue(ops.set_axis_labels("Fig1", "Time (s)", "Signal").ok)
        self.assertTrue(ops.set_axis_range("Fig1", 0, 10, -1, 1).ok)
        self.assertTrue(ops.set_plot_style("Fig1", 1, line_width=3, symbol_size=9, color="blue").ok)
        self.assertTrue(
            ops.set_graph_font(
                "Fig1",
                "Arial",
                axis_title_size=36,
                x_tick_label_size=28,
                y_tick_label_size=36,
                legend_font_size=26,
                annotation_font_size=26,
                target="all",
            ).ok
        )
        self.assertTrue(ops.set_legend("Fig1", True, "top-right", ["A", "B"]).ok)
        self.assertTrue(ops.set_tick_style("Fig1", "in", 8, 4).ok)
        self.assertTrue(ops.apply_publication_style("Fig1", "X", "Y", 0, 1, 0, 2, ["A", "B"]).ok)
        self.assertTrue(ops.set_y_tick_values_visible("Fig1", False).ok)
        self.assertTrue(ops.set_axis_and_tick_visibility("Fig1", y_axis=True, y_ticks=True, y_tick_values=False).ok)
        self.assertTrue(ops.apply_graph4_fixed_style("Fig1", GRAPH4_FIXED_STYLE).ok)
        command_text = "\n".join(app.commands)
        self.assertIn("layer.x.label.pt = 28", command_text)
        self.assertIn("layer.y.label.pt = 36", command_text)
        self.assertIn("legend.fsize = 26", command_text)
        self.assertIn("legend.font = font(Arial)", command_text)
        self.assertIn("legend.bold = 1", command_text)
        self.assertIn("legend.color = color(black)", command_text)
        self.assertIn("legend.text$ = \\l(1) \\b(A)\n\\l(2) \\b(B);", command_text)
        self.assertNotIn("legend.text1$", command_text)
        self.assertIn("legend.background = 0", command_text)
        self.assertIn("legend.border = 0", command_text)
        self.assertIn("legend.frame = 0", command_text)
        self.assertIn("legend.fill = 0", command_text)
        self.assertIn("layer.y.label.show = 0", command_text)
        self.assertIn("layer.y.showLabels = 0", command_text)
        self.assertIn("layer.x.showLabels = 1", command_text)
        self.assertIn("layer.y.show = 1", command_text)
        self.assertIn("layer.y.ticks = 1", command_text)
        self.assertIn("layer.x.thickness = 3", command_text)
        self.assertIn("doc -e DY {set %C -lw 3;}", command_text)

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = ops.export_graph("Fig1", Path(tmpdir) / "fig", "tif", dpi=600, timeout_seconds=0.1)
            self.assertTrue(exported.ok)
            self.assertTrue(Path(exported.payload["file_path"]).is_file())
            self.assertEqual(Path(exported.payload["file_path"]).suffix, ".tif")
            all_exported = ops.export_all_graphs(tmpdir, "tif", dpi=600)
            self.assertTrue(all_exported.ok)
            self.assertEqual(len(all_exported.payload["exported"]), 1)

    def test_save_graph_template_uses_labtalk_save_t(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "GraphStyle.otpu"
            result = ops.save_graph_template("Graph1", template_path)

        self.assertTrue(result.ok)
        command_text = "\n".join(app.commands)
        self.assertIn('win -a "Graph1"', command_text)
        self.assertIn("save -t Graph1", command_text)
        self.assertIn("GraphStyle.otpu", command_text)

    def test_create_graph_from_template_uses_project_local_otpu(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "GraphStyle.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_template("ProductGraph", template_path)

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["graph_name"], "ProductGraph")
        command_text = "\n".join(app.commands)
        expected_folder = str(template_path.parent).replace("\\", "/")
        self.assertIn(f'cd "{expected_folder}"', command_text)
        self.assertIn("CreatePage:3:ProductGraph:GraphStyle.otpu", app.commands)
        self.assertNotIn(f"CreatePage:3:ProductGraph:{template_path}", app.commands)

    def test_save_graph_theme_saves_origin_copy_format_clipboard_style(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            theme_path = Path(tmpdir) / "GraphStyle.oth"
            with mock.patch("src.origin.operations._read_origin_xml_style_clipboard", return_value=b"fake graph theme"):
                result = ops.save_graph_theme("Graph1", theme_path)
            saved_bytes = theme_path.read_bytes()

        self.assertTrue(result.ok)
        self.assertEqual(saved_bytes, b"fake graph theme")
        command_text = "\n".join(app.commands)
        self.assertIn('win -a "Graph1"', command_text)
        self.assertIn("PrepareCopyFormats", command_text)
        self.assertIn("CopyFormat()", command_text)
        self.assertNotIn("run.LoadOC", command_text)

    def test_apply_graph_theme_uses_origin_builtin_theme_apply(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            theme_path = Path(tmpdir) / "GraphStyle.oth"
            theme_path.write_bytes(b"oth")
            result = ops.apply_graph_theme("ProductGraph", theme_path)

        self.assertTrue(result.ok)
        command_text = "\n".join(app.commands)
        self.assertIn('win -a "ProductGraph"', command_text)
        self.assertIn("theme_apply_graph_options", command_text)
        self.assertIn("GraphStyle.oth", command_text)
        self.assertNotIn("run.LoadOC", command_text)

    def test_helpers_and_connect_origin_dispatch_mode(self):
        self.assertEqual(safe_origin_name("123 unsafe name"), "Page_123_unsafe_name")
        output, export_format = normalize_export_path("figure", "tiff")
        self.assertEqual(output.name, "figure.tif")
        self.assertEqual(export_format, "tif")

        class FakeClient:
            def __init__(self):
                self.created = []

            def DispatchEx(self, entrypoint):
                self.created.append(("DispatchEx", entrypoint))
                return FakeOriginApp()

        fake_client = FakeClient()

        with mock.patch.dict("sys.modules", {"win32com.client": fake_client, "win32com": type("M", (), {"client": fake_client})()}):
            ops = connect_origin(isolated=True)

        self.assertIsInstance(ops, OriginOperations)
        self.assertEqual(fake_client.created, [("DispatchEx", "Origin.Application")])


if __name__ == "__main__":
    unittest.main()
