import csv
import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

import src.core.file_utils as file_utils
import src.core.epr_jeol as epr_jeol
from src.cli import main as cli_main
from src.core.epr_jeol import (
    DEFAULT_EXPORT_POINTS,
    decode_jeol_cacqu_rows,
    decode_jeol_cacqu_series,
    export_jeol_cwesr_to_xlsx,
    looks_like_jeol_cwesr_file,
    read_verified_jeol_export_series,
    read_xy_xlsx,
    write_data_xlsx,
)
from src.core.file_utils import file_sha256
from src.core.project import default_output_root
from src.core.triage import TriageOptions, run_triage
from src.processors.base import process_table_dataset


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
        "supported_in_pipeline": True,
    }


def _artifact_path(root: Path, rendered_path: str) -> Path:
    rendered = Path(rendered_path)
    if rendered.parts and rendered.parts[0] == "output":
        return default_output_root(root) / Path(*rendered.parts[1:])
    return rendered if rendered.is_absolute() else root / rendered


def write_synthetic_jeol_cacqu(
    path: Path,
    *,
    process_type: str = "cAcqu",
    data_length: int = 65536,
    signal_offset: float = 0.0,
) -> None:
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

    ch1 = [signal_offset + float(index % 16) for index in range(data_length)]
    ch2 = [0.0 for _ in range(data_length)]
    path.write_bytes(bytes(header) + struct.pack(f"<{data_length}f", *ch1) + struct.pack(f"<{data_length}f", *ch2))


def expected_first_aggregation_center(*, raw_points: int = 65536, export_points: int = DEFAULT_EXPORT_POINTS) -> float:
    repeats = raw_points // export_points
    raw_step = 1600.0 / (raw_points - 1)
    return round(3300.0 + raw_step * ((repeats - 1) / 2), 4)


class JeolEprDecodeTest(unittest.TestCase):
    def test_prepared_export_releases_raw_channels_after_aggregation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)
            plan = epr_jeol._JeolEprExportPlan(
                root, source, source.name, root / "signal.xlsx", root / "metadata.json",
            )
            prepared = epr_jeol._prepare_jeol_export(plan)

            self.assertFalse(hasattr(prepared, "decoded"))
            self.assertEqual(prepared.header.data_length, 65536)
            self.assertEqual(prepared.x_values[0], expected_first_aggregation_center())
            self.assertEqual(prepared.y_values, [7.5] * DEFAULT_EXPORT_POINTS)
            self.assertEqual(prepared.source_sha256_before, prepared.source_sha256_after)

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
            self.assertEqual(set(rows[0]), {"magnetic field G", "intensity"})
            self.assertEqual(rows[0]["magnetic field G"], str(expected_first_aggregation_center()))
            self.assertEqual(rows[0]["intensity"], "7.5")

    def test_jeol_cacqu_points_override_uses_requested_export_grid_when_compatible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CWO-OH-light1"
            write_synthetic_jeol_cacqu(source)

            x_values, y_values = decode_jeol_cacqu_series(source, points=2048)

            self.assertEqual(len(x_values), 2048)
            self.assertEqual(len(y_values), 2048)
            self.assertEqual(x_values[0], expected_first_aggregation_center(export_points=2048))
            self.assertEqual(y_values[0], 7.5)

    def test_jeol_cacqu_downsampled_x_values_use_the_aggregation_bin_centers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CWO-OH-light1"
            raw_points = 65536
            write_synthetic_jeol_cacqu(source, data_length=raw_points)

            x_values, _ = decode_jeol_cacqu_series(source)

            repeats = raw_points // DEFAULT_EXPORT_POINTS
            raw_step = 1600.0 / (raw_points - 1)
            expected_first = round(3300.0 + raw_step * ((repeats - 1) / 2), 4)
            expected_last = round(3300.0 + raw_step * (raw_points - 1 - (repeats - 1) / 2), 4)
            self.assertEqual(x_values[0], expected_first)
            self.assertEqual(x_values[-1], expected_last)
            self.assertGreater(x_values[-1] - x_values[0], 1599.0)

    def test_verified_excel_export_reuses_matching_raw_field_axis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "EPR"
            raw_dir = root / "20260410-3"
            export_dir = root / "EPR_Excel_verified" / "20260410-3"
            raw_dir.mkdir(parents=True)
            export_dir.mkdir(parents=True)
            raw = raw_dir / "BC-O3-light5"
            export = export_dir / "BC-O3-light5.xlsx"
            write_synthetic_jeol_cacqu(raw)
            _correct_x, decoded_y = decode_jeol_cacqu_series(raw)
            legacy_step = 1600.0 / (65536 - 1)
            legacy_x = [3300.0 + legacy_step * index for index in range(DEFAULT_EXPORT_POINTS)]
            write_data_xlsx(export, legacy_x, decoded_y)

            result = read_verified_jeol_export_series(export)

            self.assertEqual(result.axis_source, "verified_jeol_raw_header")
            self.assertEqual(result.x_unit, "G")
            self.assertEqual(result.raw_source, raw)
            self.assertEqual(result.y_values, decoded_y)
            self.assertGreater(result.x_values[-1] - result.x_values[0], 1599.0)

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
            source_hash_before = file_sha256(source)

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
            self.assertEqual(rows[0], (expected_first_aggregation_center(), 7.5))
            self.assertEqual(float(rows[0][0]), expected_first_aggregation_center())
            self.assertEqual(file_sha256(source), source_hash_before)

            metadata_path = out / "metadata" / source_root.name / "BC-OH-light" / "metadata.json"
            self.assertEqual(result["metadata_files"], ["output/metadata/raw/BC-OH-light/metadata.json"])
            self.assertTrue(metadata_path.is_file())
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["processing_status"], "processed_no_origin")
            self.assertEqual(metadata["source"]["sha256"], source_hash_before)
            self.assertEqual(metadata["jeol_header"]["x_unit"], "G")
            self.assertEqual(metadata["decode"]["raw_point_count"], 65536)
            self.assertEqual(metadata["decode"]["exported_point_count"], DEFAULT_EXPORT_POINTS)
            self.assertEqual(metadata["decode"]["aggregation_factor"], 16)
            self.assertEqual(metadata["outputs"]["xlsx_sha256"], file_sha256(exported))
            self.assertTrue(metadata["manual_check_required"])
            self.assertFalse(metadata["scientific_claims"]["radical_assignment_generated"])
            self.assertIn("radical species", " ".join(metadata["forbidden_claims"]))
            verified = read_verified_jeol_export_series(exported)
            self.assertEqual(
                verified.axis_source,
                "verified_jeol_decoder_metadata",
            )
            self.assertEqual(verified.x_unit, "G")
            self.assertIsNone(verified.raw_source)

            metadata["outputs"]["xlsx_sha256"] = "0" * 64
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tampered = read_verified_jeol_export_series(exported)
            self.assertEqual(tampered.axis_source, "excel_export")
            self.assertEqual(tampered.x_unit, "")

    def test_jeol_export_keeps_same_name_sources_from_distinct_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            first = source_root / "group_a" / "same-name"
            second = source_root / "group_b" / "same-name"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            write_synthetic_jeol_cacqu(first)
            write_synthetic_jeol_cacqu(second, signal_offset=100.0)
            source_hashes = {
                "raw/group_a/same-name": file_sha256(first),
                "raw/group_b/same-name": file_sha256(second),
            }
            out = root / "decoded"

            result = export_jeol_cwesr_to_xlsx([source_root], out)

            self.assertEqual(result["exported_xlsx"], 2)
            self.assertEqual(result["source_keys"], sorted(source_hashes))
            first_xlsx = out / "raw" / "group_a" / "same-name.xlsx"
            second_xlsx = out / "raw" / "group_b" / "same-name.xlsx"
            self.assertEqual(read_xy_xlsx(first_xlsx)[1][0], 7.5)
            self.assertEqual(read_xy_xlsx(second_xlsx)[1][0], 107.5)
            self.assertEqual(file_sha256(first), source_hashes["raw/group_a/same-name"])
            self.assertEqual(file_sha256(second), source_hashes["raw/group_b/same-name"])

            metadata_payloads = []
            for group, source_key in (
                ("group_a", "raw/group_a/same-name"),
                ("group_b", "raw/group_b/same-name"),
            ):
                metadata_path = (
                    out
                    / "metadata"
                    / "raw"
                    / group
                    / "same-name"
                    / "metadata.json"
                )
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata_payloads.append(metadata)
                self.assertEqual(metadata["source_key"], source_key)
                self.assertEqual(
                    metadata["source"]["sha256_before"],
                    source_hashes[source_key],
                )
                self.assertEqual(
                    metadata["source"]["sha256_after"],
                    source_hashes[source_key],
                )
            self.assertNotEqual(
                metadata_payloads[0]["dataset_id"],
                metadata_payloads[1]["dataset_id"],
            )

    def test_jeol_export_preflights_existing_targets_before_writing_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            first = source_root / "group_a" / "first"
            second = source_root / "group_b" / "second"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            write_synthetic_jeol_cacqu(first)
            write_synthetic_jeol_cacqu(second)
            out = root / "decoded"
            existing_target = out / "raw" / "group_b" / "second.xlsx"
            existing_target.parent.mkdir(parents=True)
            existing_target.write_bytes(b"keep-existing")

            with self.assertRaisesRegex(
                FileExistsError,
                "rerun with force=True",
            ):
                export_jeol_cwesr_to_xlsx([source_root], out)

            self.assertEqual(existing_target.read_bytes(), b"keep-existing")
            self.assertFalse((out / "raw" / "group_a" / "first.xlsx").exists())
            self.assertFalse(
                (
                    out
                    / "metadata"
                    / "raw"
                    / "group_a"
                    / "first"
                    / "metadata.json"
                ).exists()
            )

    def test_jeol_export_requires_explicit_force_to_replace_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "same-run"
            write_synthetic_jeol_cacqu(source)
            out = root / "decoded"
            export_jeol_cwesr_to_xlsx([source_root], out)

            with self.assertRaises(FileExistsError):
                export_jeol_cwesr_to_xlsx([source_root], out)

            result = export_jeol_cwesr_to_xlsx(
                [source_root],
                out,
                force=True,
            )
            self.assertEqual(result["exported_xlsx"], 1)
            self.assertEqual(result["source_keys"], ["raw/same-run"])

    def test_jeol_force_rejects_reparse_leaf_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "same-run"
            write_synthetic_jeol_cacqu(source)
            source_hash = file_sha256(source)
            out = root / "decoded"
            unsafe_leaf = out / "raw" / "same-run.xlsx"
            unsafe_leaf.parent.mkdir(parents=True)
            unsafe_leaf.write_bytes(b"must-not-overwrite")
            unsafe_key = file_utils.lexical_absolute_path(unsafe_leaf)
            original_check = file_utils._path_is_link_or_reparse

            with patch(
                "src.core.file_utils._path_is_link_or_reparse",
                side_effect=lambda path: (
                    file_utils.lexical_absolute_path(path) == unsafe_key
                    or original_check(path)
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "symlink, junction, or reparse",
                ):
                    export_jeol_cwesr_to_xlsx(
                        [source_root],
                        out,
                        force=True,
                    )

            self.assertEqual(file_sha256(source), source_hash)
            self.assertEqual(unsafe_leaf.read_bytes(), b"must-not-overwrite")
            self.assertFalse((out / "metadata").exists())

    def test_jeol_force_unlinks_hardlink_before_writing_replacement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "same-run"
            write_synthetic_jeol_cacqu(source)
            external = root / "external-preserve.bin"
            external.write_bytes(b"external-hardlink-content")
            out = root / "decoded"
            target = out / "raw" / "same-run.xlsx"
            target.parent.mkdir(parents=True)
            try:
                os.link(external, target)
            except OSError as exc:
                self.skipTest(f"hard links unavailable in this environment: {exc}")

            export_jeol_cwesr_to_xlsx([source_root], out, force=True)

            self.assertEqual(external.read_bytes(), b"external-hardlink-content")
            self.assertNotEqual(target.read_bytes(), external.read_bytes())
            self.assertEqual(os.stat(external).st_nlink, 1)

    def test_jeol_export_rejects_colliding_root_labels_before_writing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first_root = root / "first" / "raw"
            second_root = root / "second" / "raw"
            first_root.mkdir(parents=True)
            second_root.mkdir(parents=True)
            write_synthetic_jeol_cacqu(first_root / "same-name")
            write_synthetic_jeol_cacqu(second_root / "same-name")
            out = root / "decoded"

            with self.assertRaisesRegex(
                ValueError,
                "source key collision",
            ):
                export_jeol_cwesr_to_xlsx(
                    [first_root, second_root],
                    out,
                )

            self.assertFalse(out.exists())

    def test_jeol_export_rejects_missing_or_non_directory_roots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "decoded"

            with self.assertRaisesRegex(FileNotFoundError, "does not exist"):
                export_jeol_cwesr_to_xlsx([root / "missing"], output)

            non_directory = root / "raw-file"
            non_directory.write_bytes(b"not a directory")
            with self.assertRaisesRegex(NotADirectoryError, "not a directory"):
                export_jeol_cwesr_to_xlsx([non_directory], output)

    def test_jeol_export_rejects_output_root_overlapping_input_tree_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "same-run"
            write_synthetic_jeol_cacqu(source)
            source_hash_before = file_sha256(source)

            with self.assertRaisesRegex(ValueError, "overlaps protected input"):
                export_jeol_cwesr_to_xlsx([source_root], source_root)

            self.assertEqual(file_sha256(source), source_hash_before)
            self.assertEqual(list(source_root.iterdir()), [source])

    def test_jeol_commit_rolls_back_all_old_files_when_second_install_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_root = root / "decoded"
            stage_root = output_root / ".stage"
            final_first = output_root / "raw" / "first.xlsx"
            final_second = output_root / "metadata" / "first" / "metadata.json"
            staged_first = stage_root / "raw" / "first.xlsx"
            staged_second = stage_root / "metadata" / "first" / "metadata.json"
            for path, content in (
                (final_first, b"old first\n"),
                (final_second, b"old second\n"),
                (staged_first, b"new first\n"),
                (staged_second, b"new second\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            real_replace = os.replace
            installs = 0

            def fail_second_install(source: Path, target: Path) -> None:
                nonlocal installs
                if target in (final_first, final_second) and source in (staged_first, staged_second):
                    installs += 1
                    if installs == 2:
                        raise OSError("injected second JEOL install failure")
                real_replace(source, target)

            with patch("src.core.epr_jeol._atomic_replace_jeol", side_effect=fail_second_install):
                with self.assertRaisesRegex(RuntimeError, "previous outputs were restored"):
                    epr_jeol._commit_staged_jeol_files(
                        (staged_first, staged_second),
                        (final_first, final_second),
                        output_root=output_root,
                        stage_root=stage_root,
                        force=True,
                    )

            self.assertEqual(final_first.read_bytes(), b"old first\n")
            self.assertEqual(final_second.read_bytes(), b"old second\n")

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

            report = root / "decoded" / "compare.xlsx"
            export_jeol_cwesr_to_xlsx([source_root], root / "decoded", reference_dir=ref, report_xlsx=report)

            self.assertTrue(report.is_file())
            workbook = load_workbook(report, read_only=True, data_only=True)
            try:
                same_sheet = workbook["same_name_compare"]
                rows = list(same_sheet.iter_rows(values_only=True))
            finally:
                workbook.close()
            self.assertEqual(rows[1][-1], "PASS")

    def test_compare_report_must_stay_under_decode_output_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "CWO-O3-dark"
            write_synthetic_jeol_cacqu(source)
            ref = root / "reference"
            x_values, y_values = decode_jeol_cacqu_series(source)
            write_data_xlsx(ref / "CWO-O3-dark.xlsx", x_values, y_values)

            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                export_jeol_cwesr_to_xlsx([source_root], root / "decoded", reference_dir=ref, report_xlsx=root / "compare.xlsx")

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

    def test_jeol_epr_decode_cli_relative_out_uses_external_output_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = root / "project"
            project.mkdir()
            source_root = root / "raw"
            source_root.mkdir()
            source = source_root / "BOBC-O3-light1"
            write_synthetic_jeol_cacqu(source)
            old_cwd = Path.cwd()
            try:
                os.chdir(project)
                code = cli_main(["jeol-epr-decode", "--out", "output/epr_decoded", str(source_root)])
            finally:
                os.chdir(old_cwd)

            out = default_output_root(project) / "output" / "epr_decoded"
            self.assertEqual(code, 0)
            self.assertFalse((project / "output").exists())
            x_values, y_values = read_xy_xlsx(out / source_root.name / "BOBC-O3-light1.xlsx")
            self.assertEqual(len(x_values), DEFAULT_EXPORT_POINTS)
            self.assertEqual(y_values[0], 7.5)

    def test_validation_reference_verifier_cleans_decoded_test_outputs(self):
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

            script = Path(__file__).resolve().parents[1] / "scripts" / "validation" / "verify_jeol_epr_decode_against_exports.py"
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

    def test_validation_reference_verifier_defaults_to_configured_output_root(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "validation" / "verify_jeol_epr_decode_against_exports.py"
        spec = importlib.util.spec_from_file_location("verify_jeol_epr_decode_against_exports_defaults", script)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        args = module.parse_args(["--keep-decoded"])
        script_text = script.read_text(encoding="utf-8")

        self.assertEqual(args.report_json, module.DEFAULT_OUTPUT_ROOT / "reports" / "jeol_epr_decode_reference_check.json")
        self.assertEqual(args.report_md, module.DEFAULT_OUTPUT_ROOT / "reports" / "jeol_epr_decode_reference_check.md")
        self.assertNotIn('PROJECT_ROOT / "output"', script_text)


if __name__ == "__main__":
    unittest.main()
