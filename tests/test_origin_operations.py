from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path

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


class FakeLayer:
    def __init__(self, app: "FakeOriginApp"):
        self._app = app
        self.DataPlots = FakeDataPlots(["Book1_B", "Book1_C"])

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
        return True

    def PutWorksheet(self, target: str, values: list[float], row: int, col: int):
        rows = self.worksheets.setdefault(target, [])
        for index, value in enumerate(values):
            while len(rows) <= index:
                rows.append([])
            while len(rows[index]) <= col:
                rows[index].append(float("nan"))
            rows[index][col] = value

    def GetWorksheet(self, target: str):
        return self.worksheets.get(target)

    def LTStr(self, name: str):
        if name == "__rdop_pages$":
            return ";".join(self.pages) + ";"
        return "hello"

    def LTVar(self, name: str):
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
        self.assertIn({"book_name": "Book1", "column_index": 2, "rows": 2}, replaced.payload["updated_columns"])

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
