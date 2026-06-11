import csv
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from src.cli import main as cli_main
from src.core.epr_jeol import (
    DEFAULT_EXPORT_POINTS,
    decode_jeol_cacqu_rows,
    decode_jeol_cacqu_series,
    export_jeol_cwesr_to_xlsx,
    looks_like_jeol_cwesr_file,
    read_xy_xlsx,
    write_data_xlsx,
)
from src.core.project import default_output_root
from src.core.triage import TriageOptions, run_triage
from src.processors.base import process_table_dataset


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
        "supported_in_phase_1": True,
    }


def _artifact_path(root: Path, rendered_path: str) -> Path:
    rendered = Path(rendered_path)
    if rendered.parts and rendered.parts[0] == "output":
        return default_output_root(root) / Path(*rendered.parts[1:])
    return rendered if rendered.is_absolute() else root / rendered


def write_synthetic_jeol_cacqu(path: Path, *, process_type: str = "cAcqu", data_length: int = 65536) -> None:
    header = bytearray(9500)
    offset = 0

    def put_c_string(value: str, length: int) -> None:
        nonlocal offset
        raw = value.encode("latin1")[: length - 1]
        header[offset : offset + length] = raw + b"\0" * (length - len(raw))
        offset += length

    def put_i32(value: int) -> None:
        nonlocal offset
        header[offset : offset + 4] = struct.pack("<i", value)
        offset += 4

    def put_f32(value: float) -> None:
        nonlocal offset
        header[offset : offset + 4] = struct.pack("<f", value)
        offset += 4

    put_c_string(process_type, 16)
    put_c_string(path.name, 64)
    offset += 4
    put_i32(0)
    put_i32(1)
    put_i32(data_length)
    put_c_string("complex", 15)
    offset += 1
    put_f32(3300.0)
    put_f32(1600.0)
    put_c_string("G", 16)
    offset += 8
    put_c_string("x", 16)
    offset += 4
    put_c_string("intensity", 16)
    put_f32(3300.0)
    put_f32(4900.0)

    ch1 = [float(index % 16) for index in range(data_length)]
    ch2 = [0.0 for _ in range(data_length)]
    path.write_bytes(bytes(header) + struct.pack(f"<{data_length}f", *ch1) + struct.pack(f"<{data_length}f", *ch2))


class JeolEprDecodeTest(unittest.TestCase):
    def _processed_rows(self, root: Path, metadata: dict) -> list[dict[str, str]]:
        with _artifact_path(root, metadata["processed_data"]).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_jeol_cacqu_no_extension_decodes_to_project_epr_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)

            self.assertTrue(looks_like_jeol_cwesr_file(source))
            rows = decode_jeol_cacqu_rows(source)

            self.assertEqual(len(rows), DEFAULT_EXPORT_POINTS)
            self.assertEqual(set(rows[0]), {"magnetic field", "intensity"})
            self.assertEqual(rows[0]["magnetic field"], "3300.0")
            self.assertEqual(rows[0]["intensity"], "7.5")

    def test_jeol_cacqu_points_override_uses_requested_export_grid_when_compatible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)

            x_values, y_values = decode_jeol_cacqu_series(source, points=2048)

            self.assertEqual(len(x_values), 2048)
            self.assertEqual(len(y_values), 2048)
            self.assertEqual(x_values[0], 3300.0)
            self.assertEqual(y_values[0], 7.5)

    def test_jeol_cacqu_points_override_requires_raw_points_to_divide_export_points(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)

            with self.assertRaisesRegex(
                ValueError,
                r"raw_points 65536 must be divisible by export points 5000",
            ):
                decode_jeol_cacqu_series(source, points=5000)

    def test_epr_processor_accepts_verified_jeol_cacqu_without_origin_or_radical_claims(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)

            metadata = process_table_dataset(root, classification("EPR", "epr_processor"), source, no_origin=True)

            self.assertEqual(metadata["processing_status"], "processed_no_origin")
            self.assertIn("JEOL", " ".join(metadata["warnings"]))
            self.assertIn("microwave frequency", " ".join(metadata["manual_check_items"]))
            self.assertIn("radical species", " ".join(metadata["forbidden_claims"]))
            self.assertNotIn("radical", metadata["key_results"])
            processed = self._processed_rows(root, metadata)
            self.assertEqual(len(processed), DEFAULT_EXPORT_POINTS)
            self.assertEqual(set(processed[0]), {"magnetic_field", "intensity", "normalized_intensity"})

    def test_triage_recognizes_verified_jeol_cacqu_as_epr_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "EPR" / "raw_data" / "CWO-OH-light1"
            source.parent.mkdir(parents=True)
            write_synthetic_jeol_cacqu(source)

            result = run_triage(Path.cwd(), root, TriageOptions(explain=True, dry_run=True))
            item = result["items"][0]

            self.assertEqual(item["data_type_candidate"], "EPR")
            self.assertEqual(item["parser_probe_status"], "success")
            self.assertEqual(item["decision"], "AUTO_PROCESS")
            self.assertIn("jeol_cacqu_epr_binary_decode", item["recognition_fallbacks"])
            self.assertEqual(item["numeric_shape_hint"]["rows"], DEFAULT_EXPORT_POINTS)

    def test_non_cacqu_jeol_header_is_not_silently_processed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "EPR" / "spin_candidate"
            source.parent.mkdir(parents=True)
            write_synthetic_jeol_cacqu(source, process_type="spin")

            self.assertTrue(looks_like_jeol_cwesr_file(source))
            with self.assertRaisesRegex(ValueError, "only cAcqu"):
                process_table_dataset(root, classification("EPR", "epr_processor"), source, no_origin=True)

    def test_skill_compatible_data_only_xlsx_export_has_no_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "BC-OH-light"
            write_synthetic_jeol_cacqu(source)
            out = root / "decoded"

            result = export_jeol_cwesr_to_xlsx([source_root], out)

            self.assertEqual(result["exported_xlsx"], 1)
            exported = out / source_root.name / "BC-OH-light.xlsx"
            self.assertTrue(exported.is_file())
            workbook = load_workbook(exported, read_only=True, data_only=True)
            try:
                rows = list(workbook.active.iter_rows(values_only=True))
            finally:
                workbook.close()
            self.assertEqual(len(rows), DEFAULT_EXPORT_POINTS)
            self.assertEqual(rows[0], (3300.0, 7.5))
            self.assertEqual(float(rows[0][0]), 3300.0)

    def test_skill_compatible_compare_report_marks_exact_same_name_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "CWO-O3-dark"
            write_synthetic_jeol_cacqu(source)
            ref = root / "reference"
            x_values, y_values = decode_jeol_cacqu_series(source)
            write_data_xlsx(ref / "CWO-O3-dark.xlsx", x_values, y_values)

            report = root / "compare.xlsx"
            export_jeol_cwesr_to_xlsx([source_root], root / "decoded", reference_dir=ref, report_xlsx=report)

            self.assertTrue(report.is_file())
            workbook = load_workbook(report, read_only=True, data_only=True)
            try:
                same_sheet = workbook["same_name_compare"]
                rows = list(same_sheet.iter_rows(values_only=True))
            finally:
                workbook.close()
            self.assertEqual(rows[1][-1], "PASS")

    def test_jeol_epr_decode_cli_exports_data_only_workbook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "BOBC-O3-light1"
            write_synthetic_jeol_cacqu(source)
            out = root / "decoded"

            code = cli_main(["jeol-epr-decode", "--out", str(out), str(source_root)])

            self.assertEqual(code, 0)
            x_values, y_values = read_xy_xlsx(out / source_root.name / "BOBC-O3-light1.xlsx")
            self.assertEqual(len(x_values), DEFAULT_EXPORT_POINTS)
            self.assertEqual(y_values[0], 7.5)

    def test_one_off_reference_verifier_cleans_decoded_test_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "CWO-OH-dark"
            write_synthetic_jeol_cacqu(source)
            reference = root / "reference"
            x_values, y_values = decode_jeol_cacqu_series(source)
            write_data_xlsx(reference / "CWO-OH-dark.xlsx", x_values, y_values)
            report_json = root / "report.json"
            report_md = root / "report.md"

            script = Path(__file__).resolve().parents[1] / "scripts" / "one_off" / "verify_jeol_epr_decode_against_exports.py"
            spec = importlib.util.spec_from_file_location("verify_jeol_epr_decode_against_exports", script)
            module = importlib.util.module_from_spec(spec)
            self.assertIsNotNone(spec.loader)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            code = module.run(
                [
                    "--reference-dir",
                    str(reference),
                    "--report-json",
                    str(report_json),
                    "--report-md",
                    str(report_md),
                    str(source_root),
                ]
            )

            self.assertEqual(code, 0)
            report = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["decoded_test_outputs_cleaned"])
            self.assertFalse(Path(report["decoded_test_output_root"]).exists())
            self.assertEqual(report["exact_reference_match_count"], 1)
            self.assertIn("verified JEOL cAcqu 默认导出", report_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
