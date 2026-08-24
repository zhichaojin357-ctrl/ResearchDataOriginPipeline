from __future__ import annotations

import tempfile
import unittest
import math
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
        self.graph_layer_plot_names: dict[str, list[str]] = {}
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
        if script == "doc -rn; doc -s;":
            self.ltstrs["%X"] = ""
            self.ltstrs["%G"] = "UNTITLED"
            return True
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
        if "template_saveas " in script:
            template_name = _between(script, 'template:="', '"')
            template_folder = _between(script, 'filepath:="', '"')
            if template_name and template_folder:
                Path(template_folder).mkdir(parents=True, exist_ok=True)
                (Path(template_folder) / f"{template_name}.otpu").write_bytes(b"fake graph template")
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
        return FakeLayer(self, self.graph_layer_plot_names.get(name))


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
        self.assertIsNone(ops.app)
        self.assertTrue(ops.close().ok)

    def test_reset_project_identity_for_export_executes_and_verifies_exact_state(self):
        app = FakeOriginApp()
        app.ltstrs["%X"] = "D:/private/project/"
        app.ltstrs["%G"] = "secret.opju"
        ops = OriginOperations(app)

        result = ops.reset_project_identity_for_export()

        self.assertTrue(result.ok)
        self.assertEqual(app.commands[-1], "doc -rn; doc -s;")
        self.assertEqual(
            result.payload,
            {
                "project_path_empty": True,
                "project_name_untitled": True,
            },
        )

    def test_reset_project_identity_for_export_tolerates_origin_case_and_whitespace(self):
        class TolerantIdentityApp(FakeOriginApp):
            def Execute(self, script: str):
                result = super().Execute(script)
                if script == "doc -rn; doc -s;":
                    self.ltstrs["%X"] = " \t "
                    self.ltstrs["%G"] = "  untitled  "
                return result

        result = OriginOperations(TolerantIdentityApp()).reset_project_identity_for_export()

        self.assertTrue(result.ok)
        self.assertEqual(
            result.payload,
            {
                "project_path_empty": True,
                "project_name_untitled": True,
            },
        )

    def test_reset_project_identity_for_export_fails_closed_without_identity_leak(self):
        secret_path = "D:/private/project/"
        secret_name = "secret.opju"

        class IdentityNotResetApp(FakeOriginApp):
            def Execute(self, script: str):
                self.commands.append(script)
                if script == "doc -rn; doc -s;":
                    return True
                return super().Execute(script)

        app = IdentityNotResetApp()
        app.ltstrs["%X"] = secret_path
        app.ltstrs["%G"] = secret_name
        result = OriginOperations(app).reset_project_identity_for_export()

        self.assertFalse(result.ok)
        rendered = f"{result.message} {result.payload}"
        self.assertNotIn(secret_path, rendered)
        self.assertNotIn(secret_name, rendered)
        self.assertEqual(
            result.payload,
            {
                "project_path_empty": False,
                "project_name_untitled": False,
            },
        )

    def test_reset_project_identity_for_export_rejects_command_failure_without_readback(self):
        class ResetFailureApp(FakeOriginApp):
            def Execute(self, script: str):
                self.commands.append(script)
                if script == "doc -rn; doc -s;":
                    return False
                return super().Execute(script)

            def LTStr(self, name: str):
                raise AssertionError(f"identity must not be read after failed reset: {name}")

        app = ResetFailureApp()
        result = OriginOperations(app).reset_project_identity_for_export()

        self.assertFalse(result.ok)
        self.assertEqual(app.commands, ["doc -rn; doc -s;"])
        self.assertEqual(result.payload, {})

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

    def test_set_worksheet_column_mask_rows_uses_native_mask_state(self):
        app = FakeOriginApp()
        result = OriginOperations(app).set_worksheet_column_mask_rows(
            "Book1",
            4,
            [5, 1, 2, 2],
            sheet_index=1,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["masked_rows"], [1, 2, 5])
        commands = "\n".join(app.commands)
        self.assertIn('win -a "Book1"; layer -s 1;', commands)
        self.assertIn("wcol(4)<1>=1;", commands)
        self.assertIn("wcol(4)<2>=1;", commands)
        self.assertIn("wcol(4)<5>=1;", commands)

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
        self.assertEqual(replaced.payload["updated_columns"][2]["sheet_reference"], "Sheet1")
        self.assertEqual(replaced.payload["updated_columns"][2]["column_index"], 2)
        self.assertEqual(replaced.payload["updated_columns"][2]["rows"], 2)
        self.assertEqual(replaced.payload["updated_columns"][2]["write_mode"], "single")

    def test_graph_plot_dataset_mappings_read_actual_x_y_and_sheet_suffixes(self):
        class PlotMappingOriginApp(FakeOriginApp):
            plot_mappings = {
                1: ("Book1_A", "Book1_B", 1, 2),
                2: ("Book1_F@2", "Book1_G@2", 3, 4),
            }

            def FindGraphLayer(self, name: str):
                if name in {"[Fig1]1", "[Fig1]Layer1", "[Fig1]", "Fig1"}:
                    return FakeLayer(self, ["Book1_B", "Book1_G@2"])
                return None

            def Execute(self, script: str):
                match = re.search(r"range\s+-wx\s+\S+=\[Fig1\]1!(\d+)", script)
                if match:
                    plot_index = int(match.group(1))
                    x_dataset, y_dataset, row_from, row_to = self.plot_mappings[plot_index]
                    self.ltstrs["__rdop_plot_x$"] = x_dataset
                    self.ltstrs["__rdop_plot_y$"] = y_dataset
                    self.ltvars["__rdop_plot_begin"] = float(row_from)
                    self.ltvars["__rdop_plot_end"] = float(row_to)
                return super().Execute(script)

        app = PlotMappingOriginApp()
        result = OriginOperations(app).get_graph_plot_dataset_mappings("Fig1")

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["mapping_failure_count"], 0)
        self.assertEqual(result.payload["plot_x_dataset_names"], ["Book1_A", "Book1_F@2"])
        self.assertEqual(result.payload["plot_y_dataset_names"], ["Book1_B", "Book1_G@2"])
        self.assertEqual(
            result.payload["plot_mappings"][1],
            {
                "plot_index": 2,
                "x_dataset": "Book1_F@2",
                "y_dataset": "Book1_G@2",
                "dataplot_name": "Book1_G@2",
                "dataplot_name_matches": True,
                "row_from": 3,
                "row_to": 4,
                "row_count": 2,
                "status": "ready",
            },
        )

    def test_template_worksheet_column_replacement_uses_explicit_sheet_creation_index(self):
        app = FakeOriginApp()
        replaced = OriginOperations(app).replace_template_worksheet_columns(
            {
                "Book1": {
                    1: {0: [0.0, 1.0], 1: [10.0, 11.0]},
                    2: {5: [2.0, 3.0], 6: [20.0, 21.0]},
                }
            }
        )

        self.assertTrue(replaced.ok)
        self.assertEqual(app.worksheets["[Book1]1"], [[0.0, 10.0], [1.0, 11.0]])
        self.assertEqual(app.worksheets["[Book1]2"][0][5:7], [2.0, 20.0])
        self.assertEqual(replaced.payload["updated_columns"][2]["sheet_reference"], "2")

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
        self.assertTrue(
            ops.add_plot_to_graph(
                "Fig1",
                "Data",
                "Sheet1",
                4,
                5,
                "line",
                row_from=2,
                row_to=9,
            ).ok
        )
        self.assertIn(
            "[Data]Sheet1!(4[2:9],5[2:9])",
            "\n".join(app.commands),
        )
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
            self.assertIn("tr2.TIF.dotsperinch:=600", "\n".join(app.commands))
            self.assertIn("sysopts:=0", "\n".join(app.commands))

            png = ops.export_graph("Fig1", Path(tmpdir) / "preview", "png", dpi=300, timeout_seconds=0.1)
            self.assertTrue(png.ok)
            self.assertTrue(Path(png.payload["file_path"]).is_file())
            self.assertEqual(Path(png.payload["file_path"]).suffix, ".png")
            self.assertIn("tr2.PNG.dotsperinch:=300", "\n".join(app.commands))

            all_exported = ops.export_all_graphs(tmpdir, "tif", dpi=600)
            self.assertTrue(all_exported.ok)
            self.assertEqual(len(all_exported.payload["exported"]), 1)

    def test_export_graph_rejects_invalid_dpi_before_running_origin_export(self):
        invalid_values = (True, 0, -1, 71, 1201, 600.0, "600")
        for dpi in invalid_values:
            with self.subTest(dpi=dpi):
                app = FakeOriginApp()
                ops = OriginOperations(app)
                with tempfile.TemporaryDirectory() as tmpdir:
                    result = ops.export_graph(
                        "Fig1",
                        Path(tmpdir) / "figure.tif",
                        "tif",
                        dpi=dpi,  # type: ignore[arg-type]
                        timeout_seconds=0.1,
                    )

                self.assertFalse(result.ok)
                self.assertIn("DPI", result.message)
                self.assertNotIn("expGraph", "\n".join(app.commands))

    def test_export_graph_activation_failure_preserves_existing_artifact(self):
        class MissingGraphApp(FakeOriginApp):
            def Execute(self, script: str):
                self.commands.append(script)
                if script.startswith('win -a "MissingGraph"'):
                    return False
                return True

        app = MissingGraphApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "existing.tif"
            target.write_bytes(b"previous validated figure")

            result = ops.export_graph(
                "MissingGraph",
                target,
                "tif",
                dpi=600,
            )

            self.assertFalse(result.ok)
            self.assertEqual(target.read_bytes(), b"previous validated figure")
            self.assertNotIn("expGraph", "\n".join(app.commands))

    def test_export_graph_uses_explicit_pixel_width_with_raster_dpi(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ops.export_graph(
                "Fig1",
                Path(tmpdir) / "figure.tif",
                "tif",
                dpi=600,
                timeout_seconds=0.1,
                pixel_width=3859,
            )

        self.assertTrue(result.ok)
        command = next(value for value in app.commands if "expGraph" in value)
        self.assertIn("sysopts:=0", command)
        self.assertIn("tr.Margin:=2", command)
        self.assertIn("tr1.Unit:=2", command)
        self.assertIn("tr1.Width:=3859", command)
        self.assertIn("tr2.TIF.dotsperinch:=600", command)

    def test_export_graph_rejects_invalid_pixel_width(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ops.export_graph(
                "Fig1",
                Path(tmpdir) / "figure.tif",
                "tif",
                dpi=600,
                pixel_width=0,
            )

        self.assertFalse(result.ok)
        self.assertIn("pixel width", result.message)
        self.assertNotIn("expGraph", "\n".join(app.commands))

    def test_export_graph_applies_dpi_to_other_raster_formats_only(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            for suffix, export_format, dpi in (("bmp", "bmp", 150), ("jpg", "jpeg", 1200)):
                result = ops.export_graph(
                    "Fig1",
                    Path(tmpdir) / f"figure.{suffix}",
                    export_format,
                    dpi=dpi,
                    timeout_seconds=0.1,
                )
                self.assertTrue(result.ok)

            vector = ops.export_graph(
                "Fig1",
                Path(tmpdir) / "figure.svg",
                "svg",
                dpi=600,
                timeout_seconds=0.1,
            )
            self.assertTrue(vector.ok)

        export_commands = [command for command in app.commands if "expGraph" in command]
        self.assertIn("tr2.BMP.dotsperinch:=150", export_commands[0])
        self.assertIn("tr2.JPG.dotsperinch:=1200", export_commands[1])
        self.assertIn("sysopts:=0", export_commands[0])
        self.assertIn("sysopts:=0", export_commands[1])
        self.assertNotIn("dotsperinch", export_commands[2])
        self.assertNotIn("sysopts:=0", export_commands[2])

    def test_save_graph_template_uses_template_saveas_without_system_override(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "GraphStyle.otpu"
            result = ops.save_graph_template("Graph1", template_path)

        self.assertTrue(result.ok)
        command_text = "\n".join(app.commands)
        self.assertIn('win -a "Graph1"', command_text)
        self.assertIn("template_saveas pg:=Graph1", command_text)
        self.assertIn('template:="GraphStyle"', command_text)
        self.assertIn("loadsys:=0", command_text)
        self.assertNotIn("save -t", command_text)

    def test_create_graph_from_xy_pairs_template_uses_absolute_template_and_explicit_ranges(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "GraphStyle.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph5",
                template_path,
                "Isotherm",
                [
                    {"x_col": 1, "y_col": 2, "row_from": 1, "row_to": 32},
                    {"x_col": 3, "y_col": 4, "row_from": 1, "row_to": 33},
                ],
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["plot_count"], 2)
        command_text = "\n".join(app.commands)
        absolute_template = str(template_path.resolve()).replace("\\", "/")
        self.assertIn(f'template:="{absolute_template}"', command_text)
        self.assertIn("iy:=((1,2[1:32]),(3,4[1:33]))", command_text)
        self.assertIn("plot:=202", command_text)
        self.assertIn("size:=-1", command_text)
        self.assertIn("rescale:=0", command_text)
        self.assertIn("legend:=0", command_text)

    def test_create_graph_from_xy_pairs_template_supports_explicit_worksheet_indices(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "EIS.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph1",
                template_path,
                "Book1",
                [
                    {
                        "sheet_index": 1,
                        "x_col": 5,
                        "y_col": 7,
                        "row_from": 1,
                        "row_to": 101,
                    },
                    {
                        "sheet_index": 2,
                        "x_col": 5,
                        "y_col": 7,
                        "row_from": 1,
                        "row_to": 101,
                    },
                ],
                plot_type="scatter",
                group_plots=True,
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["xy_ranges"][1]["sheet_index"], 2)
        command_text = "\n".join(app.commands)
        self.assertIn(
            "iy:=([Book1]1!(5[1:101],7[1:101]),[Book1]2!(5[1:101],7[1:101]))",
            command_text,
        )
        self.assertIn("plot:=201", command_text)
        self.assertIn('win -a "Graph1"; layer -s 1; layer -g;', command_text)

    def test_create_graph_from_xy_pairs_template_supports_multiple_named_workbooks(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "XRD.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph4",
                template_path,
                "PrimaryBook",
                [
                    {
                        "book_name": "SampleA",
                        "sheet_index": 2,
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                    },
                    {
                        "book_name": "SampleB",
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                    },
                ],
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.payload["xy_ranges"][0]["book_name"], "SampleA")
        self.assertEqual(result.payload["xy_ranges"][0]["sheet_index"], 2)
        self.assertEqual(result.payload["xy_ranges"][1]["book_name"], "SampleB")
        self.assertEqual(result.payload["xy_ranges"][1]["sheet_index"], 1)
        command_text = "\n".join(app.commands)
        self.assertIn(
            "iy:=([SampleA]2!(1[1:501],2[1:501]),[SampleB]1!(1[1:501],2[1:501]))",
            command_text,
        )

    def test_create_graph_from_xy_pairs_template_rejects_unsafe_range_workbook_name(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "XRD.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph4",
                template_path,
                "PrimaryBook",
                [
                    {
                        "book_name": "SampleA;doc -s",
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                    },
                ],
            )

        self.assertFalse(result.ok)
        self.assertIn("unsafe workbook", result.message)
        self.assertFalse(any("plotxy" in command for command in app.commands))

    def test_create_graph_from_xy_pairs_template_routes_ranges_to_explicit_graph_layers(self):
        app = FakeOriginApp()
        app.graph_layer_plot_names["[Graph4]1"] = ["SampleA_B"]
        app.graph_layer_plot_names["[Graph4]2"] = ["SampleB_B"]
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "XRD.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph4",
                template_path,
                "SampleA",
                [
                    {
                        "book_name": "SampleA",
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                    },
                    {
                        "book_name": "SampleB",
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                        "layer_index": 2,
                    },
                ],
            )

        self.assertTrue(result.ok)
        self.assertEqual([item["layer_index"] for item in result.payload["xy_ranges"]], [1, 2])
        command_text = "\n".join(app.commands)
        self.assertIn(
            f"CreatePage:3:Graph4:{template_path.resolve()}",
            command_text,
        )
        self.assertIn(
            "plotxy iy:=[SampleA]1!(1[1:501],2[1:501]) plot:=202 size:=-1 rescale:=0 legend:=0 ogl:=[Graph4]1;",
            command_text,
        )
        self.assertIn(
            "plotxy iy:=[SampleB]1!(1[1:501],2[1:501]) plot:=202 size:=-1 rescale:=0 legend:=0 ogl:=[Graph4]2;",
            command_text,
        )
        self.assertNotIn("<new template:", command_text)

    def test_create_graph_from_xy_pairs_template_applies_native_formats_and_stack_without_forced_grouping(self):
        class StackAwareOriginApp(FakeOriginApp):
            def __init__(self):
                super().__init__()
                self.stack_values: dict[tuple[str, str], float] = {}
                self.plot_values: dict[tuple[str, str], float] = {}

            def Execute(self, script: str):
                result = super().Execute(script)
                for plot_name, option, value in re.findall(
                    r"set\s+([A-Za-z_][A-Za-z0-9_]*)\s+-(sx|sy|sxs|sys)\s+([-+0-9.eE]+);",
                    script,
                ):
                    self.stack_values[(plot_name, option)] = float(value)
                for plot_name, option, value in re.findall(
                    r"set\s+([A-Za-z_][A-Za-z0-9_]*)\s+-(c|cl|w|d|l|lv|lvc|lvs|lvw)\s+([-+0-9.eE]+);",
                    script,
                ):
                    self.plot_values[(plot_name, option)] = float(value)
                match = re.fullmatch(
                    r"get\s+([A-Za-z_][A-Za-z0-9_]*)\s+-(sx|sy|sxs|sys)\s+([A-Za-z_][A-Za-z0-9_]*);",
                    script,
                )
                if match:
                    plot_name, option, variable = match.groups()
                    self.ltvars[variable] = self.stack_values.get(
                        (plot_name, option),
                        1.0 if option in {"sxs", "sys"} else 0.0,
                    )
                plot_match = re.fullmatch(
                    r"get\s+([A-Za-z_][A-Za-z0-9_]*)\s+-(c|cl|w|d|l|lv|lvc|lvs|lvw)\s+([A-Za-z_][A-Za-z0-9_]*);",
                    script,
                )
                if plot_match:
                    plot_name, option, variable = plot_match.groups()
                    self.ltvars[variable] = self.plot_values[(plot_name, option)]
                return result

        app = StackAwareOriginApp()
        app.graph_layer_plot_names["[Graph4]1"] = [
            "Book2_B",
            "Book2_D",
            "Book2_F",
        ]
        app.graph_layer_plot_names["[Graph4]2"] = ["Book2_H"]
        app.graph_layer_plot_names["[Graph4]3"] = ["Book3_F"]
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "XRD.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph4",
                template_path,
                "Book2",
                [
                    {"book_name": "Book2", "x_col": 1, "y_col": 2, "row_from": 1, "row_to": 3855, "layer_index": 1},
                    {"book_name": "Book2", "x_col": 3, "y_col": 4, "row_from": 1, "row_to": 3855, "layer_index": 1},
                    {"book_name": "Book2", "x_col": 5, "y_col": 6, "row_from": 1, "row_to": 3855, "layer_index": 1},
                    {"book_name": "Book2", "x_col": 7, "y_col": 8, "row_from": 1, "row_to": 198, "layer_index": 2},
                    {"book_name": "Book3", "x_col": 5, "y_col": 6, "row_from": 1, "row_to": 3855, "layer_index": 3},
                ],
                plot_type="line",
                group_plots=False,
                individual_stack_offsets=[
                    {"layer_index": 1, "plot_index": 1, "y_offset": 0.0},
                    {"layer_index": 1, "plot_index": 2, "y_offset": 560.2891913966785},
                    {"layer_index": 1, "plot_index": 3, "y_offset": -2808.5009666953847},
                ],
                plot_format_contracts=[
                    {"layer_index": 1, "plot_index": 2, "color": 33518174, "line_width": 1500},
                    {"layer_index": 2, "plot_index": 1, "connect": 0, "vertical_drop_lines": 1, "vertical_drop_line_color": 17585584, "vertical_drop_line_width": 3},
                ],
            )

        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.payload["group_layer_indices"], [])
        self.assertEqual(len(result.payload["individual_stack_readback"]), 3)
        self.assertEqual(len(result.payload["plot_format_readback"]), 2)
        command_text = "\n".join(app.commands)
        self.assertNotIn("layer -g;", command_text)
        self.assertIn("layer -b s 4 0 1;", command_text)
        self.assertNotIn("set Book2_D -sx", command_text)
        self.assertNotIn("set Book2_D -sxs", command_text)
        self.assertAlmostEqual(app.stack_values[("Book2_D", "sy")], 560.2891913966785)
        self.assertAlmostEqual(app.stack_values[("Book2_F", "sy")], -2808.5009666953847)
        self.assertEqual(app.plot_values[("Book2_D", "c")], 33518174.0)
        self.assertEqual(app.plot_values[("Book2_H", "l")], 0.0)
        self.assertEqual(app.plot_values[("Book2_H", "lv")], 1.0)

    def test_create_graph_from_xy_pairs_template_keeps_template_cd_best_effort_for_layers(self):
        class CdFailingOriginApp(FakeOriginApp):
            def Execute(self, script: str):
                if script.startswith('cd '):
                    self.commands.append(script)
                    return False
                return super().Execute(script)

        app = CdFailingOriginApp()
        app.graph_layer_plot_names["[Graph4]1"] = ["SampleA_B"]
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "XRD.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph4",
                template_path,
                "SampleA",
                [
                    {
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                        "layer_index": 1,
                    },
                ],
            )

        self.assertTrue(result.ok)
        command_text = "\n".join(app.commands)
        self.assertIn(
            f"CreatePage:3:Graph4:{template_path.resolve()}",
            command_text,
        )
        self.assertIn("ogl:=[Graph4]1;", command_text)

    def test_create_graph_from_xy_pairs_template_rejects_invalid_graph_layer_index(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "XRD.otpu"
            template_path.write_bytes(b"otpu")
            result = ops.create_graph_from_xy_pairs_template(
                "Graph4",
                template_path,
                "SampleA",
                [
                    {
                        "x_col": 1,
                        "y_col": 2,
                        "row_from": 1,
                        "row_to": 501,
                        "layer_index": 1.5,
                    },
                ],
            )

        self.assertFalse(result.ok)
        self.assertIn("layer index", result.message)
        self.assertFalse(any("plotxy" in command or "CreatePage" in command for command in app.commands))

    def test_add_worksheet_and_metadata_operations_target_requested_sheet(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)

        added = ops.add_worksheet("Book1", "Sheet2")
        read = ops.get_worksheet_column_metadata("Book1", [5, 7], sheet_index=2)
        written = ops.set_worksheet_column_metadata(
            "Book1",
            [
                {
                    "column_index": 5,
                    "long_name": "Z real",
                    "unit": "ohm",
                    "comment": "",
                    "type": 4,
                },
                {
                    "column_index": 7,
                    "long_name": "minus Z imaginary",
                    "unit": "ohm",
                    "comment": "",
                    "type": 1,
                },
            ],
            sheet_index=2,
        )

        self.assertTrue(added.ok)
        self.assertTrue(read.ok)
        self.assertTrue(written.ok)
        command_text = "\n".join(app.commands)
        self.assertIn('newsheet name:="Sheet2" active:=1', command_text)
        self.assertGreaterEqual(command_text.count("layer -s 2"), 2)

    def test_worksheet_column_metadata_roundtrip_commands_use_singular_origin_properties(self):
        app = FakeOriginApp()
        ops = OriginOperations(app)

        read = ops.get_worksheet_column_metadata("Isotherm", [1, 2])
        written = ops.set_worksheet_column_metadata(
            "Isotherm",
            [
                {
                    "column_index": 1,
                    "long_name": r"\b(Relative Pressure)",
                    "unit": "P/P0",
                    "comment": "",
                    "type": 4,
                },
                {
                    "column_index": 2,
                    "long_name": "Quantity Adsorbed",
                    "unit": "cm3/g STP",
                    "comment": "",
                    "type": 1,
                },
            ],
        )

        self.assertTrue(read.ok)
        self.assertTrue(written.ok)
        command_text = "\n".join(app.commands)
        self.assertIn("wks.col1.unit$", command_text)
        self.assertIn("wks.col1.comment$", command_text)
        self.assertNotIn("wks.col1.units$", command_text)
        self.assertNotIn("wks.col1.comments$", command_text)
        self.assertIn(r'wks.col1.lname$="\b(Relative Pressure)"', command_text)
        self.assertNotIn(r'wks.col1.lname$="\\b(Relative Pressure)"', command_text)

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

        with (
            mock.patch("src.origin.operations.origin_process_ids", return_value=set()),
            mock.patch.dict(
                "sys.modules",
                {
                    "win32com.client": fake_client,
                    "win32com": type("M", (), {"client": fake_client})(),
                },
            ),
        ):
            ops = connect_origin(isolated=True)

        self.assertIsInstance(ops, OriginOperations)
        self.assertEqual(fake_client.created, [("DispatchEx", "Origin.Application")])

    def test_connect_origin_refuses_to_attach_when_origin_is_already_running(self):
        with mock.patch(
            "src.origin.operations.origin_process_ids",
            return_value={8123, 8456},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"refusing to attach.*8123, 8456",
            ):
                connect_origin(isolated=True)

    def test_origin_process_ids_fails_closed_when_inspection_fails(self):
        completed = type(
            "Completed",
            (),
            {
                "returncode": 1,
                "stderr": "inspection unavailable",
                "stdout": "",
            },
        )()
        with mock.patch(
            "src.origin.operations.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Could not inspect existing Origin processes safely",
            ):
                from src.origin.operations import origin_process_ids

                origin_process_ids()

    def test_origin_process_ids_filters_only_confirmed_zero_thread_residue(self):
        completed = type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stderr": "",
                "stdout": "8123\n",
            },
        )()
        with mock.patch(
            "src.origin.operations.subprocess.run",
            return_value=completed,
        ) as run:
            from src.origin.operations import origin_process_ids

            self.assertEqual(origin_process_ids(), {8123})

        command = run.call_args.args[0]
        self.assertIn("@($originProcess.Threads).Count -gt 0", command[-1])
        self.assertIn("catch { $originProcess.Id }", command[-1])

    def test_origin_process_ids_fails_closed_on_unparseable_output(self):
        completed = type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stderr": "",
                "stdout": "8123\nnot-a-pid\n",
            },
        )()
        with mock.patch(
            "src.origin.operations.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "unexpected process identifier",
            ):
                from src.origin.operations import origin_process_ids

                origin_process_ids()


if __name__ == "__main__":
    unittest.main()
