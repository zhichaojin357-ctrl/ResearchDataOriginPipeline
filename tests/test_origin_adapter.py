from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.origin.adapter import (
    PLOT_TYPE_CODES,
    build_origin_invocation_script,
    build_origin_plot_job,
    export_plot,
    origin_smoke_test,
    write_origin_error,
    write_origin_success,
    _run_origin_job,
)


class OriginSmokeTestUnavailableDependencies(unittest.TestCase):
    def test_phase1_plot_types_are_explicitly_mapped(self) -> None:
        line_plot_types = {
            "XRD",
            "UV-vis DRS",
            "EIS",
            "photocurrent",
            "photocurrent_response",
            "XPS",
            "PL",
            "FTIR",
            "Raman",
            "HPLC/LC exported data",
            "BET",
            "EPR",
            "Mott-Schottky",
        }

        self.assertEqual(PLOT_TYPE_CODES["reaction_condition_screening"], "203")
        for data_type in line_plot_types:
            with self.subTest(data_type=data_type):
                self.assertEqual(PLOT_TYPE_CODES[data_type], "200")

    def test_reaction_condition_screening_uses_column_plot_type_in_job_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "screening.csv"
            data.write_text("condition,yield\nA,10\nB,20\n", encoding="utf-8")

            job = build_origin_plot_job(
                project_root,
                "condition_screen",
                data,
                "Condition",
                "Yield",
                "reaction_condition_screening",
            )
            script = build_origin_invocation_script(job)

            self.assertEqual(job.plot_type_code, "203")
            self.assertIn("PlotType = '203'", script)

    def test_builds_graph4_helper_job_without_forbidden_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            config = project_root / "config"
            config.mkdir()
            (config / "plot_style.yaml").write_text(
                "\n".join(
                    [
                        'font_family: "Arial"',
                        "line_width: 3",
                        "axis_line_width: 3",
                        "origin_template:",
                        '  default_graph_page: "Graph4"',
                        '  automation_entrypoint: "Origin.Application"',
                        '  avoid_entrypoint: "Origin.ApplicationSI"',
                        f'  reference_search_pattern: "{str(project_root / "refs" / "CWO+BOBC+reference.opju")}"',
                    ]
                ),
                encoding="utf-8",
            )
            reference = project_root / "refs" / "CWO+BOBC+reference.opju"
            reference.parent.mkdir()
            reference.write_text("placeholder", encoding="utf-8")
            data = project_root / "processed.csv"
            data.write_text("x,Sample A,Sample B\n0,1,2\n", encoding="utf-8")

            job = build_origin_plot_job(project_root, "XRD sample; unsafe", data, "2theta", "Intensity", "XRD")
            script = build_origin_invocation_script(job)

            self.assertEqual(job.reference_graph, "Graph4")
            self.assertIsNone(job.reference_opju)
            self.assertEqual(job.automation_entrypoint, "Origin.Application")
            self.assertEqual(job.line_width, 3)
            self.assertEqual(job.axis_line_width, 3)
            self.assertNotIn(" ", job.page_name)
            self.assertNotIn(";", job.page_name)
            self.assertEqual(job.column_count, 3)
            self.assertEqual(job.labels, ("Sample A", "Sample B"))
            self.assertIn("origin_plot_from_template.ps1", script)
            self.assertNotIn("-ReferenceOpju", script)
            self.assertNotIn("@referenceArg", script)
            self.assertIn("-ReferenceGraph 'Graph4'", script)
            self.assertIn("-Headless -CloseOrigin", script)
            self.assertNotIn("ApplicationSI", script)
            self.assertIn("Get-Process -Name Origin*", script)
            self.assertIn("AddSeconds(30)", script)
            self.assertIn("Start-Sleep -Milliseconds 500", script)
            self.assertIn("PNG preview was not exported", script)
            self.assertNotIn("expGraph type:=tif", script)

    def test_origin_page_name_includes_stable_hash_within_origin_short_name_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")

            first = build_origin_plot_job(project_root, "Raman_" + "same_prefix_" * 8 + "A", data, "x", "y", "Raman")
            second = build_origin_plot_job(project_root, "Raman_" + "same_prefix_" * 8 + "B", data, "x", "y", "Raman")

            self.assertNotEqual(first.page_name, second.page_name)
            self.assertNotEqual(first.preview_png, second.preview_png)
            self.assertNotEqual(first.figure_tif, second.figure_tif)
            self.assertLessEqual(len(first.page_name), 24)

    def test_origin_job_filters_auxiliary_columns_and_uses_material_color(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "photocurrent.csv"
            data.write_text("time_s,current,cycle_candidate_id\n0,1,1\n1,2,1\n", encoding="utf-8")
            source = project_root / "1-BOC-(OCP).txt"

            job = build_origin_plot_job(
                project_root,
                "photocurrent_1-BOC-_OCP_82c78732",
                data,
                "time_s",
                "current",
                "photocurrent",
                source_file=source,
            )
            script = build_origin_invocation_script(job)

            self.assertEqual(job.labels, ("1-BOC",))
            self.assertEqual(job.curve_colors, (32093270,))
            self.assertEqual(job.color_assignments[0]["material_key"], "BOC")
            self.assertIn("Palette = @(32093270)", script)
            self.assertEqual(job.plot_csv.read_text(encoding="utf-8").splitlines()[0], "time_s,current")
            self.assertNotIn("cycle_candidate_id", job.plot_csv.read_text(encoding="utf-8"))

    def test_same_material_gets_same_curve_color_across_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            first_data = project_root / "first.csv"
            second_data = project_root / "second.csv"
            first_data.write_text("x,intensity\n0,1\n", encoding="utf-8")
            second_data.write_text("potential,one_over_c_squared\n0,2\n", encoding="utf-8")

            first = build_origin_plot_job(
                project_root,
                "Raman_CWO_1_69ed0044",
                first_data,
                "x",
                "intensity",
                "Raman",
                source_file=project_root / "CWO_1.txt",
            )
            second = build_origin_plot_job(
                project_root,
                "Mott-Schottky_CWO1000_b536ae79",
                second_data,
                "potential",
                "one_over_c_squared",
                "Mott-Schottky",
                source_file=project_root / "CWO1000.csv",
            )

            self.assertEqual(first.color_assignments[0]["material_key"], "CWO")
            self.assertEqual(second.color_assignments[0]["material_key"], "CWO")
            self.assertEqual(first.curve_colors, second.curve_colors)

    def test_curve_label_material_takes_priority_over_folder_composite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")
            source = project_root / "CWO+BOBC" / "BOBC-A.txt"

            job = build_origin_plot_job(
                project_root,
                "EIS_BOBC-A_bbba2791",
                data,
                "x",
                "y",
                "EIS",
                source_file=source,
            )

            self.assertEqual(job.labels, ("BOBC-A",))
            self.assertEqual(job.color_assignments[0]["material_key"], "BOBC")
            self.assertEqual(job.curve_colors, (16818150,))

    def test_writes_origin_job_script_with_utf8_bom_for_chinese_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="科研_") as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "数据.csv"
            data.write_text("x,样品A\n0,1\n", encoding="utf-8")
            job = build_origin_plot_job(project_root, "样品 A", data, "角度", "强度", "XRD")

            with patch("src.origin.adapter.subprocess.run") as run:
                run.return_value.returncode = 1
                run.return_value.stdout = ""
                run.return_value.stderr = "skip"
                _run_origin_job(job)

            self.assertTrue(job.job_script.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_writes_origin_error_report_when_dependencies_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            with patch(
                "src.origin.adapter.check_origin_available",
                return_value=(False, "originpro unavailable: No module named 'originpro'"),
            ) as check_origin_available:
                result = origin_smoke_test(project_root)

            self.assertFalse(result.ok)
            self.assertIsNone(result.origin_file)
            self.assertIsNone(result.figure_tif)
            self.assertIsNone(result.preview_png)
            self.assertEqual(result.message, "originpro unavailable: No module named 'originpro'")
            check_origin_available.assert_called_once_with()

            report_path = project_root / "output" / "reports" / "origin_errors.md"
            self.assertTrue(report_path.exists())
            self.assertEqual(
                report_path.read_text(encoding="utf-8"),
                "# Origin Errors\n\n- originpro unavailable: No module named 'originpro'\n",
            )
            self.assertFalse((project_root / "output" / "processed_data").exists())

    def test_check_origin_available_honors_test_disable_guard(self) -> None:
        with patch.dict("src.origin.adapter.os.environ", {"GROUPMEETINGAUTOPPT_DISABLE_ORIGIN": "1"}):
            from src.origin.adapter import check_origin_available

            ok, message = check_origin_available()

        self.assertFalse(ok)
        self.assertIn("GROUPMEETINGAUTOPPT_DISABLE_ORIGIN", message)

    def test_write_origin_error_deduplicates_identical_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            write_origin_error(project_root, "originpro unavailable: No module named 'originpro'")
            write_origin_error(project_root, "originpro unavailable: No module named 'originpro'")

            report = project_root / "output" / "reports" / "origin_errors.md"
            self.assertEqual(
                report.read_text(encoding="utf-8"),
                "# Origin Errors\n\n- originpro unavailable: No module named 'originpro'\n",
            )

    def test_write_origin_error_normalizes_existing_duplicate_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            report = project_root / "output" / "reports" / "origin_errors.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                "# Origin Errors\n\n- old duplicate\n\n- old duplicate\n",
                encoding="utf-8",
            )

            write_origin_error(project_root, "new failure")

            self.assertEqual(
                report.read_text(encoding="utf-8"),
                "# Origin Errors\n\n- old duplicate\n\n- new failure\n",
            )

    def test_write_origin_success_replaces_stale_error_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            write_origin_error(project_root, "old failure")

            write_origin_success(project_root)

            report = project_root / "output" / "reports" / "origin_errors.md"
            self.assertEqual(report.read_text(encoding="utf-8"), "# Origin Errors\n\nNo current Origin errors.\n")

    def test_origin_job_rejects_non_graph4_line_width_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            config = project_root / "config"
            config.mkdir()
            (config / "plot_style.yaml").write_text(
                "\n".join(
                    [
                        "line_width: 2",
                        "axis_line_width: 2",
                        "origin_template:",
                        '  default_graph_page: "Graph4"',
                        '  automation_entrypoint: "Origin.Application"',
                        '  avoid_entrypoint: "Origin.ApplicationSI"',
                    ]
                ),
                encoding="utf-8",
            )
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                build_origin_plot_job(project_root, "bad_width", data, "x", "y", "XRD")

    def test_export_plot_rejects_success_without_nonempty_preview_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")

            def fake_run(job):
                job.origin_file.write_text("opju", encoding="utf-8")
                job.figure_tif.write_text("tif", encoding="utf-8")
                job.preview_png.write_bytes(b"")
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with patch("src.origin.adapter.check_origin_available", return_value=(True, "ok")):
                with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                    result = export_plot(project_root, "empty_preview", data, "x", "y", "XRD")

            self.assertFalse(result.ok)
            self.assertIn("PNG preview", result.message)

    def test_export_plot_uses_originpro_tif_fallback_when_labtalk_tif_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")

            def fake_run(job):
                job.origin_file.write_text("opju", encoding="utf-8")
                job.preview_png.write_bytes(b"png preview")
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            def fake_tif_export(job):
                job.figure_tif.write_text("tif", encoding="utf-8")

            with patch("src.origin.adapter.check_origin_available", return_value=(True, "ok")):
                with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                    with patch("src.origin.adapter._export_tif_with_originpro", side_effect=fake_tif_export):
                        result = export_plot(project_root, "fallback_tif", data, "x", "y", "XRD")

            self.assertTrue(result.ok)
            self.assertIsNotNone(result.figure_tif)
            self.assertTrue(result.figure_tif.exists())

    def test_export_plot_success_does_not_clear_stale_batch_error_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")
            write_origin_error(project_root, "old failure")

            def fake_run(job):
                job.origin_file.write_text("opju", encoding="utf-8")
                job.figure_tif.write_text("tif", encoding="utf-8")
                job.preview_png.write_bytes(b"png preview")
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with patch("src.origin.adapter.check_origin_available", return_value=(True, "ok")):
                with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                    result = export_plot(project_root, "clear_stale", data, "x", "y", "XRD")

            self.assertTrue(result.ok)
            report = project_root / "output" / "reports" / "origin_errors.md"
            self.assertEqual(report.read_text(encoding="utf-8"), "# Origin Errors\n\n- old failure\n")

    def test_export_plot_rejects_success_without_nonempty_tif_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")

            def fake_run(job):
                job.origin_file.write_text("opju", encoding="utf-8")
                job.figure_tif.write_bytes(b"")
                job.preview_png.write_bytes(b"png preview")
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with patch("src.origin.adapter.check_origin_available", return_value=(True, "ok")):
                with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                    result = export_plot(project_root, "empty_tif", data, "x", "y", "XRD")

            self.assertFalse(result.ok)
            self.assertIn("TIF", result.message)

    def test_export_plot_removes_stale_artifacts_before_current_origin_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")
            stale_job = build_origin_plot_job(project_root, "stale_outputs", data, "x", "y", "XRD")
            stale_job.origin_file.write_text("old opju", encoding="utf-8")
            stale_job.figure_tif.write_text("old tif", encoding="utf-8")
            stale_job.preview_png.write_bytes(b"old png")

            def fake_run(job):
                self.assertFalse(job.origin_file.exists())
                self.assertFalse(job.figure_tif.exists())
                self.assertFalse(job.preview_png.exists())
                job.origin_file.write_text("new opju", encoding="utf-8")
                job.preview_png.write_bytes(b"new png")
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            def fake_tif_export(job):
                job.figure_tif.write_text("new tif", encoding="utf-8")

            with patch("src.origin.adapter.check_origin_available", return_value=(True, "ok")):
                with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                    with patch("src.origin.adapter._export_tif_with_originpro", side_effect=fake_tif_export):
                        result = export_plot(project_root, "stale_outputs", data, "x", "y", "XRD")

            self.assertTrue(result.ok)
            self.assertEqual(stale_job.origin_file.read_text(encoding="utf-8"), "new opju")
            self.assertEqual(stale_job.figure_tif.read_text(encoding="utf-8"), "new tif")
            self.assertEqual(stale_job.preview_png.read_bytes(), b"new png")


if __name__ == "__main__":
    unittest.main()
