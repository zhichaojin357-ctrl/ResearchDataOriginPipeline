import csv
import struct
import tempfile
import unittest
from pathlib import Path

from src.core.epr_jeol import decode_jeol_cacqu_rows, looks_like_jeol_cwesr_file
from src.core.triage import TriageOptions, run_triage
from src.processors.base import process_table_dataset


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
        "supported_in_phase_1": True,
    }


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
        with (root / metadata["processed_data"]).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_jeol_cacqu_no_extension_decodes_to_project_epr_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)

            self.assertTrue(looks_like_jeol_cwesr_file(source))
            rows = decode_jeol_cacqu_rows(source)

            self.assertEqual(len(rows), 4096)
            self.assertEqual(set(rows[0]), {"magnetic field", "intensity"})
            self.assertEqual(rows[0]["magnetic field"], "3300.0")
            self.assertEqual(rows[0]["intensity"], "7.5")

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
            self.assertEqual(len(processed), 4096)
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
            self.assertEqual(item["numeric_shape_hint"]["rows"], 4096)

    def test_non_cacqu_jeol_header_is_not_silently_processed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "EPR" / "spin_candidate"
            source.parent.mkdir(parents=True)
            write_synthetic_jeol_cacqu(source, process_type="spin")

            self.assertTrue(looks_like_jeol_cwesr_file(source))
            with self.assertRaisesRegex(ValueError, "only cAcqu"):
                process_table_dataset(root, classification("EPR", "epr_processor"), source, no_origin=True)


if __name__ == "__main__":
    unittest.main()
