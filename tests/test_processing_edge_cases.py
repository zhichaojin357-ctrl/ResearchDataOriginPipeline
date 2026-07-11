from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.process import ProcessOptions, run_process
from src.core.table_reader import coerce_numeric_rows
from src.processors.base import process_table_dataset
from src.scanner.scanner import scan_raw_data


ROOT = Path(__file__).resolve().parents[1]


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
        "supported_in_pipeline": True,
    }


def artifact_path(project: Path, rendered_path: str) -> Path:
    path = Path(rendered_path)
    return path if path.is_absolute() else project / path


class ProcessingEdgeCaseTest(unittest.TestCase):
    def _processed_rows(self, project: Path, metadata: dict) -> list[dict[str, str]]:
        with artifact_path(project, metadata["processed_data"]).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_table_reader_short_xy_needles_do_not_match_index_or_binding_energy(self):
        rows = [
            {"Index": "1", "Binding Energy (eV)": "284.8", "Intensity (cps)": "100"},
            {"Index": "2", "Binding Energy (eV)": "285.1", "Intensity (cps)": "80"},
        ]

        self.assertEqual(coerce_numeric_rows(rows), [(284.8, 100.0), (285.1, 80.0)])

    def test_table_reader_still_accepts_true_xy_columns(self):
        rows = [
            {"Index": "99", "X": "1.5", "Y": "2.5"},
            {"Index": "100", "X": "3.5", "Y": "4.5"},
        ]

        self.assertEqual(coerce_numeric_rows(rows), [(1.5, 2.5), (3.5, 4.5)])

    def test_photocurrent_header_units_are_converted_to_microamps(self):
        cases = (
            ("A", 2.5, 2_500_000.0),
            ("mA", 2.5, 2_500.0),
            ("uA", 2.5, 2.5),
            ("µA", 2.5, 2.5),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()
            output_root = project / "output"
            for unit, raw_value, expected_uA in cases:
                with self.subTest(unit=unit):
                    source = project / f"photocurrent_{unit}.csv"
                    source.write_text(
                        f"Time (s),Current ({unit})\n0,{raw_value}\n1,{raw_value}\n",
                        encoding="utf-8",
                    )

                    metadata = process_table_dataset(
                        project,
                        classification("photocurrent", "photocurrent_processor"),
                        source,
                        output_root=output_root,
                    )

                    rows = self._processed_rows(project, metadata)
                    self.assertEqual(float(rows[0]["photocurrent_uA"]), expected_uA)
                    self.assertEqual(metadata["key_results"]["photocurrent_input_current_unit"], unit.replace("µ", "u"))

    def test_photocurrent_unknown_unit_records_explicit_assumption_and_manual_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()
            source = project / "photocurrent_unknown.csv"
            source.write_text("time,current\n0,0.000002\n1,0.000003\n", encoding="utf-8")

            metadata = process_table_dataset(
                project,
                classification("photocurrent", "photocurrent_processor"),
                source,
                output_root=project / "output",
            )

            rows = self._processed_rows(project, metadata)
            self.assertEqual(float(rows[0]["photocurrent_uA"]), 2.0)
            self.assertEqual(metadata["key_results"]["photocurrent_input_current_unit"], "unknown")
            self.assertEqual(metadata["key_results"]["photocurrent_assumed_current_unit"], "A")
            self.assertIn("assumed A", " ".join(metadata["warnings"]))
            self.assertIn("current unit", " ".join(metadata["manual_check_items"]).lower())

    def test_uvvis_percent_header_converts_sub_one_percent_reflectance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()
            source = project / "uvvis_percent.csv"
            source.write_text(
                "Wavelength (nm),Reflectance (%)\n400,0.5\n500,1.0\n",
                encoding="utf-8",
            )

            metadata = process_table_dataset(
                project,
                classification("UV-vis DRS", "uvvis_drs_processor"),
                source,
                output_root=project / "output",
            )

            rows = self._processed_rows(project, metadata)
            self.assertAlmostEqual(float(rows[0]["reflectance_fraction"]), 0.005)
            self.assertAlmostEqual(float(rows[1]["reflectance_fraction"]), 0.01)

    def test_mott_schottky_short_v_needle_does_not_match_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()
            source = project / "mott_value.csv"
            source.write_text(
                "Value,1/C^2,Potential (V)\n99,4,0.1\n100,9,0.2\n",
                encoding="utf-8",
            )

            metadata = process_table_dataset(
                project,
                classification("Mott-Schottky", "mott_schottky_processor"),
                source,
                output_root=project / "output",
            )

            rows = self._processed_rows(project, metadata)
            self.assertEqual([float(row["potential"]) for row in rows], [0.1, 0.2])

    def test_scanner_short_pl_keyword_does_not_match_samples_or_accept_zero_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            raw = project / "input" / "raw_data" / "samples"
            raw.mkdir(parents=True)
            source = raw / "data.csv"
            source.write_text("x,y\n1,2\n", encoding="utf-8")

            manifest = scan_raw_data(
                project,
                project / "input" / "raw_data",
                output_root=project / "output",
            )

            pl = next(item for item in manifest["classifications"] if item["inferred_data_type"] == "PL")
            self.assertEqual(pl["physical_presence"], "absent")
            self.assertEqual(pl["files"], [])
            self.assertIn(str(source), {item["path"] for item in manifest["unclassified_files"]})

    def test_xps_registry_exposes_vgd_and_vgp_extensions(self):
        registry = json.loads((ROOT / "config" / "processor_registry.yaml").read_text(encoding="utf-8"))
        xps = next(item for item in registry["entries"] if item["id"] == "xps")

        self.assertTrue({".vgd", ".vgp"}.issubset(set(xps["extensions"])))

    def test_bet_summary_origin_rejection_still_writes_failed_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()
            source = project / "bet_summary.csv"
            source.write_text(
                "BET surface area,total pore volume,average pore diameter\n58.2,0.18,12.4\n",
                encoding="utf-8",
            )

            with patch(
                "src.processors.base.export_plot",
                side_effect=ValueError("BET summary-only table has no plottable curve"),
            ):
                metadata = process_table_dataset(
                    project,
                    classification("BET", "bet_processor"),
                    source,
                    no_origin=False,
                    output_root=project / "output",
                )

            self.assertEqual(metadata["processing_status"], "fail")
            self.assertIsNone(metadata["origin_file"])
            self.assertTrue(artifact_path(project, metadata["metadata_path"]).is_file())
            self.assertIn("no plottable curve", " ".join(metadata["warnings"]))

    def test_processing_summary_resolves_artifacts_in_custom_run_output_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            (raw / "sample.csv").write_text("2theta,intensity\n10,1\n20,3\n", encoding="utf-8")
            run_output_root = Path(tmpdir) / "output" / "runs" / "edge-case-run"

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(no_origin=True, force=True, output_root=run_output_root),
            )

            summary = json.loads(
                (run_output_root / "reports" / "processing_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(code, 0)
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["missing_artifacts"], [])

    def test_processing_summary_resolves_project_relative_nested_output_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            (raw / "sample.csv").write_text("2theta,intensity\n10,1\n20,3\n", encoding="utf-8")
            nested_output_root = project / "output" / "worker" / "process"

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(no_origin=True, force=True, output_root=nested_output_root),
            )

            summary = json.loads(
                (nested_output_root / "reports" / "processing_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(code, 0)
            self.assertEqual(summary["missing_artifacts"], [])


if __name__ == "__main__":
    unittest.main()
