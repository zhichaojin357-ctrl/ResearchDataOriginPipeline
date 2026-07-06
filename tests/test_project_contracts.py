import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.cli import build_parser
from src.core.metadata import write_metadata
from src.core.project import default_output_root, REQUIRED_OUTPUT_DIRS
from src.scanner.scanner import scan_raw_data


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


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


class Phase1ContractsTest(unittest.TestCase):
    def test_readiness_cli_defaults_to_desktop_review_workbook_check(self):
        args = build_parser().parse_args(["readiness"])

        self.assertEqual(args.command, "readiness")
        self.assertEqual(args.desktop_review_xlsx, Path.home() / "Desktop" / "manual_review_required_filtered.xlsx")

    def test_readiness_cli_can_skip_desktop_review_workbook_check(self):
        args = build_parser().parse_args(["readiness", "--no-desktop-review-xlsx"])

        self.assertEqual(args.command, "readiness")
        self.assertTrue(args.no_desktop_review_xlsx)

    def test_readiness_cli_can_require_historical_artifacts_strictly(self):
        args = build_parser().parse_args(["readiness", "--strict-artifacts"])

        self.assertEqual(args.command, "readiness")
        self.assertTrue(args.strict_artifacts)

    def test_scan_classifies_required_folders_without_touching_raw_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            raw.mkdir(parents=True)
            xrd = raw / "XRD"
            xrd.mkdir()
            source = xrd / "sample.csv"
            source.write_text("2theta,intensity\n10,100\n20,200\n", encoding="utf-8")

            config = project / "config" / "default.yaml"
            config.parent.mkdir()
            config.write_text("paths:\n  raw_data: input/raw_data\n", encoding="utf-8")

            result = run_cli("scan", "--input", str(raw), "--config", str(config), cwd=project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), "2theta,intensity\n10,100\n20,200\n")
            manifest = json.loads((default_output_root(project) / "reports" / "inventory_manifest.json").read_text(encoding="utf-8"))
            names = {item["folder_name"]: item for item in manifest["classifications"]}
            self.assertEqual(names["XRD"]["inferred_data_type"], "XRD")
            self.assertTrue(names["XRD"]["supported_in_pipeline"])
            self.assertEqual(names["动力学"]["inferred_data_type"], "reference_literature")
            self.assertEqual(names["动力学"]["special_handling"], "scan_only")
            self.assertEqual(names["SEM"]["special_handling"], "scan_only")
            self.assertTrue((default_output_root(project) / "reports" / "classification_report.md").exists())

    def test_scan_uses_config_default_input_and_registers_unclassified_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "custom_raw"
            unknown = raw / "unknown_folder"
            unknown.mkdir(parents=True)
            source = unknown / "mystery.csv"
            source.write_text("a,b\n1,2\n", encoding="utf-8")

            config = project / "config" / "default.yaml"
            config.parent.mkdir()
            config.write_text("paths:\n  raw_data: custom_raw\n", encoding="utf-8")

            result = run_cli("scan", "--config", str(config), cwd=project)

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((default_output_root(project) / "reports" / "inventory_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(manifest["scan_root"]), Path("custom_raw"))
            self.assertFalse(Path(manifest["scan_root"]).is_absolute())
            self.assertEqual(len(manifest["unclassified_files"]), 1)
            self.assertEqual(manifest["unclassified_files"][0]["relative_path"], "unknown_folder\\mystery.csv")
            self.assertFalse(Path(manifest["unclassified_files"][0]["path"]).is_absolute())
            unclassified = default_output_root(project) / "unclassified" / "unclassified_manifest.json"
            self.assertTrue(unclassified.exists())
            self.assertEqual(source.read_text(encoding="utf-8"), "a,b\n1,2\n")

    def test_scan_cli_reports_missing_input_directory_without_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            missing = project / "missing_raw_data"

            result = run_cli("scan", "--input", str(missing), cwd=project)

            self.assertEqual(result.returncode, 2)
            self.assertIn("input directory does not exist", result.stderr)
            self.assertIn("missing_raw_data", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((default_output_root(project)).exists())

    def test_triage_cli_reports_missing_input_directory_without_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            missing = project / "missing_raw_data"

            result = run_cli("triage", "--input", str(missing), cwd=project)

            self.assertEqual(result.returncode, 2)
            self.assertIn("input directory does not exist", result.stderr)
            self.assertIn("missing_raw_data", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((default_output_root(project)).exists())

    def test_process_cli_reports_missing_input_directory_without_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            missing = project / "missing_raw_data"

            result = run_cli("process", "--input", str(missing), "--no-origin", cwd=project)

            self.assertEqual(result.returncode, 2)
            self.assertIn("input directory does not exist", result.stderr)
            self.assertIn("missing_raw_data", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((default_output_root(project)).exists())

    def test_scan_matches_nested_and_multiple_known_folders_and_reports_unsupported_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            xrd_a = raw / "batch1" / "XRD"
            xrd_b = raw / "batch2" / "my_XRD_export"
            xrd_a.mkdir(parents=True)
            xrd_b.mkdir(parents=True)
            (xrd_a / "a.csv").write_text("2theta,intensity\n10,1\n", encoding="utf-8")
            (xrd_b / "b.xy").write_text("20 2\n", encoding="utf-8")
            (xrd_b / "note.unsupported").write_text("not processable\n", encoding="utf-8")

            result = run_cli("scan", "--input", str(raw), cwd=project)

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((default_output_root(project) / "reports" / "inventory_manifest.json").read_text(encoding="utf-8"))
            xrd = {item["folder_name"]: item for item in manifest["classifications"]}["XRD"]
            self.assertEqual(xrd["physical_presence"], "present")
            self.assertEqual(len(xrd["folder_paths"]), 2)
            self.assertEqual(len(xrd["files"]), 2)
            self.assertEqual(len(manifest["unsupported_files_in_known_folders"]), 1)
            self.assertEqual(manifest["unsupported_files_in_known_folders"][0]["relative_path"], "batch2\\my_XRD_export\\note.unsupported")

    def test_scan_assigns_overlapping_keyword_folders_to_most_specific_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            raw = project / "input" / "raw_data"
            photocurrent = raw / "20260109 光电流"
            response = raw / "光电流响应"
            photocurrent.mkdir(parents=True)
            response.mkdir(parents=True)
            (photocurrent / "pc.txt").write_text("Time/sec, Current/A\n0.1,1e-7\n0.2,2e-7\n", encoding="utf-8")
            (response / "response.txt").write_text("Time/sec, Current/A\n0.1,3e-7\n0.2,4e-7\n", encoding="utf-8")

            manifest = scan_raw_data(project, raw, output_root=Path(tmp) / "output")
            by_type = {item["inferred_data_type"]: item for item in manifest["classifications"]}

            self.assertEqual([Path(path).name for path in by_type["photocurrent"]["files"]], ["pc.txt"])
            self.assertEqual([Path(path).name for path in by_type["photocurrent_response"]["files"]], ["response.txt"])

    def test_process_xrd_writes_processed_data_and_failure_metadata_when_origin_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            with (raw / "sample.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["2theta", "intensity"])
                writer.writerow([20, 200])
                writer.writerow([10, 100])

            (project / "config").mkdir()
            (project / "config" / "default.yaml").write_text("paths:\n  raw_data: input/raw_data\n", encoding="utf-8")

            result = run_cli(
                "process",
                "--input",
                str(project / "input" / "raw_data"),
                "--config",
                str(project / "config" / "default.yaml"),
                "--no-origin",
                "--force",
                cwd=project,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            processed = default_output_root(project) / "processed_data" / "XRD" / "sample_processed.csv"
            metadata = default_output_root(project) / "metadata" / "XRD" / "sample" / "metadata.json"
            report = default_output_root(project) / "reports" / "processing_report.md"
            self.assertTrue(processed.exists())
            self.assertTrue(metadata.exists())
            self.assertTrue(report.exists())
            with processed.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["two_theta_deg"] for row in rows], ["10.0", "20.0"])
            self.assertEqual([row["intensity"] for row in rows], ["100.0", "200.0"])
            self.assertIn("peak_candidate_flag", rows[0])
            data = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(data["data_type"], "XRD")
            self.assertTrue(data["manual_check_required"])
            self.assertEqual(data["processing_status"], "processed_no_origin")
            self.assertIn("Origin export skipped", " ".join(data["warnings"]))

    def test_metadata_rejects_success_without_required_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "source.csv"
            source.write_text("x,y\n1,2\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                write_metadata(
                    project_root=project,
                    path=default_output_root(project) / "metadata" / "XRD" / "sample" / "metadata.json",
                    dataset_id="XRD_sample",
                    data_type="XRD",
                    source_file=source,
                    processor_name="xrd_processor",
                    processing_status="success",
                    plot_type="2theta-intensity line plot",
                    origin_file=default_output_root(project) / "origin_files" / "missing.opju",
                    figure_tif=default_output_root(project) / "figures_tif" / "missing.tif",
                    processed_data=default_output_root(project) / "processed_data" / "missing.csv",
                    manual_check_items=[],
                    forbidden_claims=[],
                    warnings=[],
                    key_results={},
                )

    def test_success_metadata_requires_and_records_png_preview_for_manual_visual_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "source.csv"
            source.write_text("x,y\n1,2\n", encoding="utf-8")
            origin_file = default_output_root(project) / "origin_files" / "sample.opju"
            figure_tif = default_output_root(project) / "figures_tif" / "sample.tif"
            preview_png = default_output_root(project) / "figures_preview" / "sample.png"
            processed = default_output_root(project) / "processed_data" / "sample.csv"
            for artifact in (origin_file, figure_tif, preview_png, processed):
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("artifact\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                write_metadata(
                    project_root=project,
                    path=default_output_root(project) / "metadata" / "XRD" / "sample" / "metadata.json",
                    dataset_id="XRD_sample",
                    data_type="XRD",
                    source_file=source,
                    processor_name="xrd_processor",
                    processing_status="success",
                    plot_type="2theta-intensity line plot",
                    origin_file=origin_file,
                    figure_tif=figure_tif,
                    processed_data=processed,
                    manual_check_items=[],
                    forbidden_claims=[],
                    warnings=[],
                    key_results={},
                )

            metadata = write_metadata(
                project_root=project,
                path=default_output_root(project) / "metadata" / "XRD" / "sample" / "metadata.json",
                dataset_id="XRD_sample",
                data_type="XRD",
                source_file=source,
                processor_name="xrd_processor",
                processing_status="success",
                plot_type="2theta-intensity line plot",
                origin_file=origin_file,
                figure_tif=figure_tif,
                preview_png=preview_png,
                processed_data=processed,
                manual_check_items=[],
                forbidden_claims=[],
                warnings=[f"warning from {project}"],
                key_results={"source_path": source, "nested": {"message": f"read {project / 'source.csv'}"}},
                parameters={"alpha": 1, "path": project / "params" / "local.txt"},
                triage={"decision": "AUTO_PROCESS", "error": f"parser saw {project / 'source.csv'}"},
            )

            self.assertEqual(metadata["preview_png"], "output/figures_preview/sample.png")
            manual_items = " ".join(metadata["manual_check_items"])
            self.assertIn("PNG preview", manual_items)
            self.assertIn("frame/fill box", manual_items)
            self.assertIn("chemical formula subscripts", manual_items)
            self.assertEqual(metadata["confidence_level"]["plotting"], "medium")
            self.assertEqual(metadata["origin_template_used"], "Graph4 cached snapshot")
            self.assertNotIn("CodexData", json.dumps(metadata, ensure_ascii=False))
            self.assertNotIn(".codex", json.dumps(metadata, ensure_ascii=False))
            rendered = json.dumps(metadata, ensure_ascii=False)
            self.assertNotIn(str(project), rendered)
            self.assertEqual(metadata["key_results"]["source_path"], "source.csv")
            self.assertEqual(metadata["parameters"]["path"], "params/local.txt")

    def test_success_metadata_rejects_artifacts_outside_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / "source.csv"
            source.write_text("x,y\n1,2\n", encoding="utf-8")
            processed = default_output_root(project) / "processed_data" / "sample.csv"
            processed.parent.mkdir(parents=True)
            processed.write_text("x,y\n1,2\n", encoding="utf-8")
            external = project / "external"
            origin_file = external / "sample.opju"
            figure_tif = external / "sample.tif"
            preview_png = external / "sample.png"
            for artifact in (origin_file, figure_tif, preview_png):
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("artifact\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                write_metadata(
                    project_root=project,
                    path=default_output_root(project) / "metadata" / "XRD" / "sample" / "metadata.json",
                    dataset_id="XRD_sample",
                    data_type="XRD",
                    source_file=source,
                    processor_name="xrd_processor",
                    processing_status="success",
                    plot_type="2theta-intensity line plot",
                    origin_file=origin_file,
                    figure_tif=figure_tif,
                    preview_png=preview_png,
                    processed_data=processed,
                    manual_check_items=[],
                    forbidden_claims=[],
                    warnings=[],
                    key_results={},
                )

    def test_deps_audit_writes_reports_and_fails_only_for_missing_core_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            result = run_cli("deps-audit", cwd=project)

            audit_json = default_output_root(project) / "reports" / "dependency_audit.json"
            audit_md = default_output_root(project) / "reports" / "dependency_audit.md"
            self.assertTrue(audit_json.exists())
            self.assertTrue(audit_md.exists())
            data = json.loads(audit_json.read_text(encoding="utf-8"))
            self.assertIn("core", data)
            self.assertIn("optional", data)
            self.assertIn("reference_only", data)
            self.assertIn("blocked", data)
            self.assertIn("summary", data)
            missing_core = [name for name, item in data["core"].items() if not item["available"]]
            for item in data["core"].values():
                self.assertEqual(item["severity"], "fail")
            for item in data["optional"].values():
                self.assertEqual(item["severity"], "warning")
            for item in data["reference_only"].values():
                self.assertEqual(item["severity"], "reference_only")
            for item in data["blocked"].values():
                self.assertEqual(item["severity"], "blocked")
                self.assertEqual(item["status"], "blocked")
            self.assertNotIn("matchms", data["optional"])
            self.assertIn("matchms", data["blocked"])
            self.assertNotIn("hplc-py", data["optional"])
            self.assertIn("hplc-py", data["reference_only"])
            self.assertNotIn("scikit-image", data["optional"])
            self.assertIn("scikit-image", data["reference_only"])
            self.assertEqual(data["summary"]["missing_core"], missing_core)
            self.assertEqual(result.returncode, 1 if missing_core else 0)

    def test_run_py_bootstraps_project_imports_without_pythonpath(self):
        env = dict(**__import__("os").environ)
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            ["python", "run.py", "--help"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scan", result.stdout)

    def test_validate_reports_scope_guards_and_registry_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "config").mkdir()
            for name in [
                "default.yaml",
                "processor_registry.yaml",
                "claim_policy.yaml",
                "plot_style.yaml",
                "sample_registry.yaml",
                "manual_overrides.yaml",
            ]:
                (project / "config" / name).write_text((ROOT / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")

            result = run_cli("validate", cwd=project)

            self.assertIn(result.returncode, (0, 1))
            report = default_output_root(project) / "reports" / "validation_report.md"
            self.assertTrue(report.exists())
            text = report.read_text(encoding="utf-8")
        self.assertIn("max_threads = 5", text)
        self.assertIn("动力学", text)
        self.assertIn("reference_literature", text)
        self.assertIn("PPT forbidden paths", text)
        self.assertIn("Required output directories", text)
        self.assertIn("figures_preview", REQUIRED_OUTPUT_DIRS)
        self.assertIn("origin_jobs", REQUIRED_OUTPUT_DIRS)
        self.assertIn("Processor registry required fields: pass", text)
        self.assertIn("Kinetics processor paths: pass", text)
        self.assertIn("Graph4", text)
        self.assertIn("Origin.Application", text)
        self.assertIn("PNG preview inspection", text)
        self.assertIn("explicit bold legend rows", text)
        self.assertIn("legend has no frame or fill", text)
        self.assertIn("line width 3", text)

    def test_validate_rejects_forbidden_presentation_outputs_outside_exact_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "config").mkdir()
            for name in [
                "default.yaml",
                "processor_registry.yaml",
                "claim_policy.yaml",
                "plot_style.yaml",
                "sample_registry.yaml",
                "manual_overrides.yaml",
            ]:
                (project / "config" / name).write_text((ROOT / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")
            forbidden = default_output_root(project) / "reports" / "draft_presentation.pptx"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("forbidden", encoding="utf-8")

            result = run_cli("validate", cwd=project)

            self.assertEqual(result.returncode, 1)
            report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")
            self.assertIn("Forbidden presentation artifacts: fail", report)
            self.assertIn("draft_presentation.pptx", report)

    def test_validate_allows_presentation_files_inside_workspace_data_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "config").mkdir()
            for name in [
                "default.yaml",
                "processor_registry.yaml",
                "claim_policy.yaml",
                "plot_style.yaml",
                "sample_registry.yaml",
                "manual_overrides.yaml",
            ]:
                (project / "config" / name).write_text((ROOT / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")
            copied_raw_ppt = project / "workspace_data" / "raw_copy" / "instrument_export.pptx"
            copied_raw_ppt.parent.mkdir(parents=True)
            copied_raw_ppt.write_text("copied raw source file", encoding="utf-8")

            result = run_cli("validate", cwd=project)

            self.assertEqual(result.returncode, 0)
            report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")
            self.assertIn("Forbidden presentation artifacts: pass", report)

    def test_validate_rejects_kinetics_processor_package_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "config").mkdir()
            for name in [
                "default.yaml",
                "processor_registry.yaml",
                "claim_policy.yaml",
                "plot_style.yaml",
                "sample_registry.yaml",
                "manual_overrides.yaml",
            ]:
                (project / "config" / name).write_text((ROOT / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")
            kinetic_package = project / "src" / "processors" / "kinetics" / "__init__.py"
            kinetic_package.parent.mkdir(parents=True)
            kinetic_package.write_text("# forbidden\n", encoding="utf-8")

            result = run_cli("validate", cwd=project)

            self.assertEqual(result.returncode, 1)
            report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")
            self.assertIn("Kinetics processor paths: fail", report)
            self.assertIn("src\\processors\\kinetics\\__init__.py", report)

    def test_validate_rejects_deferred_registry_entries_with_processors(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            config = project / "config"
            config.mkdir()
            for name in [
                "default.yaml",
                "processor_registry.yaml",
                "claim_policy.yaml",
                "plot_style.yaml",
                "sample_registry.yaml",
                "manual_overrides.yaml",
            ]:
                (config / name).write_text((ROOT / "config" / name).read_text(encoding="utf-8"), encoding="utf-8")
            registry_path = config / "processor_registry.yaml"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for entry in registry["entries"]:
                if entry["inferred_data_type"] == "NMR":
                    entry["selected_processor"] = "nmr_processor"
                if entry["folder_name"] == "动力学":
                    entry["special_handling"] = "process_when_present"
            registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_cli("validate", cwd=project)

            self.assertEqual(result.returncode, 1)
            report = (default_output_root(project) / "reports" / "validation_report.md").read_text(encoding="utf-8")
            self.assertIn("deferred/reference registry semantics", report)
            self.assertIn("NMR", report)
            self.assertIn("动力学", report)


if __name__ == "__main__":
    unittest.main()
