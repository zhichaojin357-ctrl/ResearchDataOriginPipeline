import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.process import ProcessOptions, run_process
from src.core.project import ensure_write_path_allowed
from src.core.table_reader import coerce_numeric_rows, read_table


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FIXTURE_RAW = ROOT / "tests" / "fixtures" / "synthetic_phase1" / "raw_data"


def run_cli(*args, cwd=ROOT):
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [PYTHON, str(ROOT / "run.py"), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


class Phase11ProcessCliTest(unittest.TestCase):
    def _copy_project_inputs(self, project: Path) -> Path:
        raw = project / "input" / "raw_data"
        shutil.copytree(FIXTURE_RAW, raw)
        config = project / "config"
        config.mkdir()
        (config / "default.yaml").write_text("paths:\n  raw_data: input/raw_data\n", encoding="utf-8")
        return raw

    def test_process_no_origin_generates_processed_csv_and_metadata_without_export_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)

            with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
                code = run_process(project, raw, ProcessOptions(no_origin=True, force=True))

            self.assertEqual(code, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            processed_files = list((project / "output" / "processed_data").rglob("*_processed.csv"))
            self.assertGreaterEqual(len(metadata_files), 16)
            self.assertGreaterEqual(len(processed_files), 16)
            for metadata_file in metadata_files:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                self.assertEqual(metadata["processing_status"], "processed_no_origin")
                self.assertIsNone(metadata["origin_file"])
                self.assertIsNone(metadata["figure_tif"])
                self.assertIsNone(metadata["preview_png"])
                self.assertNotIn("conversion_candidate", metadata.get("key_results", {}))

    def test_process_defaults_to_no_origin_unless_with_origin_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            (raw / "synthetic_xrd.csv").write_text("2theta,intensity\n10,1\n20,4\n", encoding="utf-8")

            with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run by default")):
                code = run_process(project, project / "input" / "raw_data", ProcessOptions(force=True))

            self.assertEqual(code, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 1)
            metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(metadata["processing_status"], "processed_no_origin")

    def test_process_rejects_conflicting_origin_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            raw.mkdir(parents=True)

            with self.assertRaises(ValueError):
                run_process(project, raw, ProcessOptions(no_origin=True, with_origin=True))

    def test_process_rejects_auto_select_with_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            raw.mkdir(parents=True)

            with self.assertRaises(ValueError):
                run_process(project, raw, ProcessOptions(auto_select=True, with_origin=True))

    def test_process_rejects_auto_select_with_explicit_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            raw.mkdir(parents=True)
            queue = project / "output" / "reports" / "processing_queue.json"
            queue.parent.mkdir(parents=True)
            queue.write_text('{"items": []}', encoding="utf-8")

            with self.assertRaises(ValueError):
                run_process(project, raw, ProcessOptions(auto_select=True, from_queue=queue))

    def test_process_from_queue_accepts_utf8_bom_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)
            queue = project / "output" / "reports" / "processing_queue.json"
            queue.parent.mkdir(parents=True, exist_ok=True)
            queue.write_text('{"items": []}', encoding="utf-8-sig")

            code = run_process(project, raw, ProcessOptions(from_queue=queue, no_origin=True, force=True))

            self.assertEqual(code, 0)

    def test_cli_rejects_no_origin_with_origin_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--config",
                str(project / "config" / "default.yaml"),
                "--no-origin",
                "--with-origin",
                "--force",
                cwd=project,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not allowed with argument", result.stderr)

    def test_cli_reports_auto_select_with_origin_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--config",
                str(project / "config" / "default.yaml"),
                "--auto-select",
                "--with-origin",
                "--force",
                cwd=project,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("--auto-select cannot be combined with --with-origin", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_reports_missing_queue_file_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            (raw / "XRD").mkdir(parents=True)
            (raw / "XRD" / "sample.csv").write_text("2theta,intensity\n10,1\n", encoding="utf-8")
            missing_queue = project / "output" / "reports" / "missing_queue.json"

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--from-queue",
                str(missing_queue),
                "--no-origin",
                cwd=project,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("missing_queue.json", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_reports_invalid_queue_json_shape_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            (raw / "XRD").mkdir(parents=True)
            (raw / "XRD" / "sample.csv").write_text("2theta,intensity\n10,1\n", encoding="utf-8")
            queue = project / "output" / "reports" / "bad_queue.json"
            queue.parent.mkdir(parents=True)
            queue.write_text("[]", encoding="utf-8")

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--from-queue",
                str(queue),
                "--no-origin",
                cwd=project,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("queue JSON must be an object", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_reports_invalid_queue_items_shape_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            (raw / "XRD").mkdir(parents=True)
            (raw / "XRD" / "sample.csv").write_text("2theta,intensity\n10,1\n", encoding="utf-8")
            queue = project / "output" / "reports" / "bad_queue.json"
            queue.parent.mkdir(parents=True)
            queue.write_text('{"items": {}}', encoding="utf-8")

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--from-queue",
                str(queue),
                "--no-origin",
                cwd=project,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("queue JSON items must be a list", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_reports_non_object_queue_item_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            (raw / "XRD").mkdir(parents=True)
            (raw / "XRD" / "sample.csv").write_text("2theta,intensity\n10,1\n", encoding="utf-8")
            queue = project / "output" / "reports" / "bad_queue.json"
            queue.parent.mkdir(parents=True)
            queue.write_text('{"items": ["not-an-object"]}', encoding="utf-8")

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--from-queue",
                str(queue),
                "--no-origin",
                cwd=project,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("queue JSON item 1 must be an object", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_with_origin_failure_is_recorded_as_origin_export_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            (raw / "synthetic_xrd.csv").write_text("2theta,intensity\n10,1\n20,4\n", encoding="utf-8")

            with patch("src.processors.base.export_plot") as export_plot:
                export_plot.return_value.ok = False
                export_plot.return_value.origin_file = None
                export_plot.return_value.figure_tif = None
                export_plot.return_value.preview_png = None
                export_plot.return_value.message = "Origin export failed: synthetic failure"
                code = run_process(project, project / "input" / "raw_data", ProcessOptions(with_origin=True, force=True))

            self.assertEqual(code, 2)
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "origin_export")
            self.assertIn("Origin export failed", failures["failures"][0]["error_message"])

    def test_process_only_type_and_only_folder_limit_batch_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)

            only_type = run_process(
                project,
                raw,
                ProcessOptions(no_origin=True, only_type="XRD", force=True),
            )
            self.assertEqual(only_type, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 1)
            self.assertIn("XRD", str(metadata_files[0]))

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)

            only_folder = run_process(
                project,
                raw,
                ProcessOptions(no_origin=True, only_folder="液相", force=True),
            )
            self.assertEqual(only_folder, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 2)
            for metadata_file in metadata_files:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
                self.assertEqual(metadata["data_type"], "HPLC/LC exported data")

    def test_batch_failure_isolation_writes_failure_records_and_fail_fast_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            (raw / "synthetic_good.csv").write_text("2theta,intensity\n10,1\n20,4\n", encoding="utf-8")
            (raw / "synthetic_bad.csv").write_bytes(b"\xff\xfe\x00\x00")

            code = run_process(project, project / "input" / "raw_data", ProcessOptions(no_origin=True, force=True))

            self.assertEqual(code, 2)
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(len(failures["failures"]), 1)
            summary = json.loads((project / "output" / "reports" / "processing_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["total_dataset_count"], 2)
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["failure_count"], 1)
            record = failures["failures"][0]
            self.assertEqual(record["inferred_data_type"], "XRD")
            self.assertEqual(record["processor_name"], "xrd_processor")
            self.assertFalse(Path(record["source_file"]).is_absolute())
            self.assertNotIn(str(project), json.dumps(failures, ensure_ascii=False))
            self.assertIn(record["failure_stage"], {"read_table", "processing"})
            self.assertTrue(record["manual_fix_hint"])
            self.assertTrue((project / "output" / "reports" / "processing_failures.md").exists())

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            (raw / "synthetic_bad_a.csv").write_bytes(b"\xff\xfe\x00\x00")
            (raw / "synthetic_bad_b.csv").write_bytes(b"\xff\xfe\x00\x00")

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(no_origin=True, fail_fast=True, force=True),
            )

            self.assertEqual(code, 2)
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(len(failures["failures"]), 1)

    def test_path_guard_rejects_writes_outside_allowed_project_areas(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            allowed = project / "output" / "reports" / "ok.md"
            outside = project / "input" / "raw_data" / "bad.md"

            self.assertEqual(ensure_write_path_allowed(project, allowed), allowed)
            with self.assertRaises(ValueError):
                ensure_write_path_allowed(project, outside)

    def test_cli_flags_are_accepted_and_no_origin_processes_synthetic_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = self._copy_project_inputs(project)

            result = run_cli(
                "process",
                "--input",
                str(raw),
                "--config",
                str(project / "config" / "default.yaml"),
                "--no-origin",
                "--only-type",
                "XRD",
                "--force",
                cwd=project,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 1)

    def test_chinese_paths_headers_samples_and_encodings_are_read_without_origin(self):
        with tempfile.TemporaryDirectory(prefix="科研_") as tmp:
            raw = Path(tmp) / "input" / "raw_data" / "固体紫外"
            raw.mkdir(parents=True)
            gb18030 = raw / "synthetic_中文样品_gb18030.csv"
            gb18030.write_bytes("样品,波长,吸光度\n样品A,400,0.5\n样品A,500,0.8\n".encode("gb18030"))
            bom = raw / "synthetic_utf8_bom.csv"
            bom.write_text("波长,吸光度\n400,0.5\n500,0.8\n", encoding="utf-8-sig")
            headerless = raw / "synthetic_headerless.dat"
            headerless.write_text("400 0.5\n500 0.8\n", encoding="utf-8")
            xlsx = raw / "synthetic_中文sheet.xlsx"
            try:
                import pandas as pd
            except ImportError:
                self.skipTest("pandas/openpyxl unavailable")
            with pd.ExcelWriter(xlsx) as writer:
                pd.DataFrame({"波长": [400, 500], "吸光度": [0.5, 0.8]}).to_excel(
                    writer,
                    sheet_name="中文表",
                    index=False,
                )

            for source in (gb18030, bom, headerless, xlsx):
                with self.subTest(source=source.name):
                    rows = read_table(source)
                    numeric = coerce_numeric_rows(rows)
                    self.assertEqual(numeric, [(400.0, 0.5), (500.0, 0.8)])


if __name__ == "__main__":
    unittest.main()
