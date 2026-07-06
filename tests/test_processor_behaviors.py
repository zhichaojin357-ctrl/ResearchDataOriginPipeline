import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.project import default_output_root
from src.core.table_reader import TableReadResult, _configure_excel_for_safe_read, coerce_numeric_rows, read_table, read_table_with_metadata
from src.processors.base import process_table_dataset


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
    }


def _artifact_path(root: Path, rendered_path: str) -> Path:
    rendered = Path(rendered_path)
    if rendered.parts and rendered.parts[0] == "output":
        return default_output_root(root) / Path(*rendered.parts[1:])
    return rendered if rendered.is_absolute() else root / rendered


class ProcessorBehaviorTest(unittest.TestCase):
    def _processed_rows(self, root: Path, metadata: dict) -> list[dict[str, str]]:
        with _artifact_path(root, metadata["processed_data"]).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_generic_reader_preserves_first_row_from_headerless_whitespace_numeric_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "sample.xy"
            source.write_text("10 1\n20 5\n30 2\n", encoding="utf-8")

            rows = read_table(source)
            numeric = coerce_numeric_rows(rows)

            self.assertEqual(numeric, [(10.0, 1.0), (20.0, 5.0), (30.0, 2.0)])

    def test_generic_reader_accepts_headerless_tsv_numeric_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "bet.tsv"
            source.write_text("0.1\t5\n0.2\t7\n", encoding="utf-8")

            rows = read_table(source)
            numeric = coerce_numeric_rows(rows)

            self.assertEqual(numeric, [(0.1, 5.0), (0.2, 7.0)])

    def test_text_reader_detects_instrument_metadata_header_before_numeric_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "mott.csv"
            source.write_text(
                "\n".join(
                    [
                        "Nov. 26, 2025   21:24:18",
                        "Impedance - Potential",
                        "Instrument Model:  CHI660E",
                        "",
                        "Init E (V) = 0.17",
                        "Final E (V) = 1.17",
                        "Incr E (V) = 0.05",
                        "Frequency (Hz) = 1000",
                        "",
                        "Potential/V, Z'/ohm, Z\"/ohm, Z/ohm, Phase/deg",
                        "",
                        "1.700e-1, 3.754e+1, 4.904e+1, 6.176e+1, 52.6",
                        "2.200e-1, 3.743e+1, 4.885e+1, 6.154e+1, 52.5",
                    ]
                ),
                encoding="utf-8",
            )

            result = read_table_with_metadata(source)

            self.assertEqual(result.header_row_index, 9)
            self.assertIn("Potential/V", result.rows[0])
            self.assertIn("Z'/ohm", result.rows[0])
            self.assertEqual(result.rows[0]["Potential/V"], "1.700e-1")
            self.assertEqual(result.rows[0]["Z'/ohm"], " 3.754e+1")

    def test_text_reader_accepts_zplotw_eis_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "bobc-z.txt"
            source.write_text(
                "\n".join(
                    [
                        '"ZPlotW Data File: Version 2.70"',
                        '"Modified Data"',
                        '"Sweep Frequency: Control Voltage"',
                        '"Date: 2-2-2026     Time: 10:57:9"',
                        '""',
                        '"Frequency"',
                        "0,2,0,1,0.001,1000000",
                        "101",
                        '"  Freq(Hz)    Ampl     Bias   Time(Sec)   Z\'(a)    Z\'\'(b)    GD   Err   Range"',
                        "1.000000E+06, 0.0000E+00, 0.0000E+00, 1.000000E+00, 6.1320E+01, -2.7362E-03, 0.0000E+00, 0, 0",
                        "8.128305E+05, 0.0000E+00, 0.0000E+00, 2.000000E+00, 6.1321E+01, -3.2932E-03, 0.0000E+00, 0, 0",
                    ]
                ),
                encoding="utf-8",
            )

            result = read_table_with_metadata(source)

            self.assertEqual(result.header_row_index, 8)
            self.assertEqual(len(result.rows), 2)
            self.assertIn("Freq(Hz)", result.rows[0])
            self.assertIn("Z'(a)", result.rows[0])
            self.assertIn("Z''(b)", result.rows[0])
            self.assertEqual(coerce_numeric_rows(result.rows), [(1000000.0, 61.32), (812830.5, 61.321)])

    def test_text_reader_accepts_z60w_eis_export_with_spaced_frequency_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "bobc-z60w.txt"
            source.write_text(
                "\n".join(
                    [
                        '"Z60W Data File: Version 1.1"',
                        '""',
                        '""',
                        "0,2,0,1,0.01,100000",
                        "71",
                        '"  Freq (Hz)    Ampl     Bias   Time(Sec)   Z\'(a)    Z\'\'(b)    GD   Err   Range"',
                        "100000,0,0,0,5.3440234422322,-1.04536632441473,0,0,0",
                        "79433,0,0,0,5.41929828179486,-1.03747488174572,0,0,0",
                    ]
                ),
                encoding="utf-8",
            )

            result = read_table_with_metadata(source)

            self.assertEqual(result.header_row_index, 5)
            self.assertEqual(len(result.rows), 2)
            self.assertIn("Freq(Hz)", result.rows[0])
            self.assertIn("Z'(a)", result.rows[0])
            self.assertIn("Z''(b)", result.rows[0])
            self.assertEqual(coerce_numeric_rows(result.rows), [(100000.0, 5.3440234422322), (79433.0, 5.41929828179486)])

    def test_text_reader_scans_long_chi_amperometric_metadata_before_data_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "photocurrent_ocp.txt"
            lines = [
                "Jan. 15, 2026   19:05:59",
                "Amperometric i-t Curve",
                "File: 1-bco-2(ocp).bin",
                "Data Source:  Experiment",
                "Instrument Model:  CHI760E",
                "",
                "Init E (V) = 0.238",
                "Sample Interval (s) = 0.1",
                "Run Time (sec) = 260",
                "Results:",
                "",
                "Channel 1:",
            ]
            for index in range(6):
                lines.extend([f"tp = {19.4 + index * 40:.2f}s", f"ip = {4.3 - index * 0.2:.3f}e-7A", ""])
            lines.extend(
                [
                    "Time/sec, Current/A",
                    "",
                    "1.000e-1, 1.197e-7",
                    "2.000e-1, 1.015e-7",
                    "3.000e-1, 8.988e-8",
                ]
            )
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = read_table_with_metadata(source)

            self.assertGreaterEqual(result.header_row_index or 0, 30)
            self.assertEqual(list(result.rows[0].keys()), ["Time/sec", "Current/A"])
            self.assertEqual(coerce_numeric_rows(result.rows), [(0.1, 1.197e-7), (0.2, 1.015e-7), (0.3, 8.988e-8)])

    def test_generic_reader_accepts_xlsm_workbooks_without_excel_com(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "eis.xlsm"

            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["frequency", "Re(Z)", "-Im(Z)"])
            sheet.append([1000, 10, 3])
            sheet.append([100, 20, 8])
            workbook.save(source)

            with patch("src.core.table_reader._read_legacy_xls_with_excel_com") as fallback:
                rows = read_table(source)

            fallback.assert_not_called()
            self.assertEqual(coerce_numeric_rows(rows), [(1000.0, 10.0), (100.0, 20.0)])

    def test_legacy_xls_uses_excel_com_fallback_when_xlrd_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "legacy.xls"
            source.write_bytes(b"not used by mocked reader")

            def missing_xlrd(*_args, **_kwargs):
                raise ImportError("Missing optional dependency 'xlrd'. Install xlrd >= 2.0.1 for xls Excel support")

            with patch("pandas.read_excel", side_effect=missing_xlrd), patch(
                "src.core.table_reader._read_legacy_xls_with_excel_com",
                return_value=TableReadResult(
                    [{"relative pressure": "0.1", "quantity adsorbed": "5"}],
                    sheet_name="Sheet1",
                    header_row_index=0,
                    sheet_scores={"Sheet1": {"score": 12, "header_bonus": 2, "numeric_rows": 1, "numeric_columns": 2, "header_row_index": 0}},
                ),
            ) as fallback:
                result = read_table_with_metadata(source)

            fallback.assert_called_once_with(source)
            self.assertEqual(result.rows[0]["relative pressure"], "0.1")

    def test_legacy_xls_com_fallback_can_be_disabled_for_triage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "legacy.xls"
            source.write_bytes(b"not used by mocked reader")

            def missing_xlrd(*_args, **_kwargs):
                raise ImportError("Missing optional dependency 'xlrd'. Install xlrd >= 2.0.1 for xls Excel support")

            with patch("pandas.read_excel", side_effect=missing_xlrd), patch(
                "src.core.table_reader._read_legacy_xls_with_excel_com"
            ) as fallback:
                with self.assertRaisesRegex(RuntimeError, "legacy .xls requires xlrd"):
                    read_table_with_metadata(source, allow_legacy_xls_com=False)

            fallback.assert_not_called()

    def test_excel_com_reader_disables_macros_events_and_prompts(self):
        class ExcelStub:
            pass

        excel = ExcelStub()
        _configure_excel_for_safe_read(excel)

        self.assertEqual(excel.Visible, False)
        self.assertEqual(excel.DisplayAlerts, False)
        self.assertEqual(excel.EnableEvents, False)
        self.assertEqual(excel.AskToUpdateLinks, False)
        self.assertEqual(excel.AutomationSecurity, 3)

    def test_excel_reader_handles_empty_sheet_without_parser_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import pandas as pd

            source = Path(tmpdir) / "empty.xlsx"
            source.write_bytes(b"not used by mocked reader")

            with patch("pandas.read_excel", return_value={"Sheet1": pd.DataFrame()}):
                result = read_table_with_metadata(source)

            self.assertEqual(result.rows, [])
            self.assertEqual(result.sheet_name, "Sheet1")

    def test_excel_reader_deduplicates_repeated_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import pandas as pd

            source = Path(tmpdir) / "duplicate_headers.xlsx"
            source.write_bytes(b"not used by mocked reader")
            frame = pd.DataFrame([
                ["x", "x", "intensity"],
                [1, 10, 5],
                [2, 20, 7],
            ])

            with patch("pandas.read_excel", return_value={"Sheet1": frame}):
                rows = read_table(source)

            self.assertEqual(set(rows[0]), {"x", "x.1", "intensity"})
            self.assertEqual(coerce_numeric_rows(rows), [(1.0, 5.0), (2.0, 7.0)])

    def test_excel_header_scoring_handles_duplicate_column_labels(self):
        import pandas as pd

        from src.core import table_reader

        frame = pd.DataFrame([
            ["x", "x", "intensity"],
            [1, 10, 5],
            [2, 20, 7],
        ])

        with patch("src.core.table_reader._dedupe_headers", side_effect=lambda headers: headers):
            data, _header_index, _numeric_rows, numeric_columns, _header_bonus = table_reader._best_header_row(frame)

        self.assertEqual(numeric_columns, 3)
        self.assertEqual(list(data.iloc[:, 0]), [1, 2])

    def test_generic_reader_handles_gbk_encoded_chinese_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "uvvis_gbk.csv"
            source.write_bytes("波长,吸光度\n400,0.5\n500,0.8\n".encode("gbk"))

            rows = read_table(source)
            numeric = coerce_numeric_rows(rows)

            self.assertIn("波长", rows[0])
            self.assertIn("吸光度", rows[0])
            self.assertEqual(numeric, [(400.0, 0.5), (500.0, 0.8)])

    def test_xrd_outputs_candidate_peak_positions_without_phase_assignment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xrd.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["2theta", "intensity"])
                writer.writerow([10, 1])
                writer.writerow([20, 10])
                writer.writerow([30, 2])

            metadata = process_table_dataset(root, classification("XRD", "xrd_processor"), source)

            self.assertIn(20.0, metadata["key_results"]["peak_position_candidates"])
            self.assertIn("candidate peak positions", " ".join(metadata["manual_check_items"]))
            self.assertNotIn("phase", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertEqual(set(rows[0]), {"two_theta_deg", "intensity", "normalized_intensity", "peak_candidate_flag"})
            self.assertEqual(rows[1]["peak_candidate_flag"], "1")

    def test_xrd_reads_raw4_text_data_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xrd_raw4.txt"
            source.write_text(
                "\n".join(
                    [
                        ";RAW4.00",
                        "[RawHeader]",
                        "Date=04/03/2025",
                        "[Data]",
                        "     Angle,       PSD,",
                        "         5,      2014,",
                        "   5.01946,      1943,",
                        "   5.03892,      2012,",
                    ]
                ),
                encoding="utf-8",
            )

            metadata = process_table_dataset(root, classification("XRD", "xrd_processor"), source)

            self.assertEqual(metadata["key_results"]["point_count"], 3)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(rows[0]["two_theta_deg"], "5.0")
            self.assertEqual(rows[0]["intensity"], "2014.0")

    def test_reviewed_queue_same_stem_uses_unique_output_suffixes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_a = root / "workspace" / "batch_a" / "sample.csv"
            source_b = root / "workspace" / "batch_b" / "sample.csv"
            for source, scale in ((source_a, 1), (source_b, 2)):
                source.parent.mkdir(parents=True)
                with source.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["2theta", "intensity"])
                    writer.writerow([10, scale])
                    writer.writerow([20, scale * 2])

            metadata_a = process_table_dataset(
                root,
                classification("XRD", "xrd_processor"),
                source_a,
                triage={"queue_id": "reviewed_queue_aaaaaaaaaaaaaaaa"},
            )
            metadata_b = process_table_dataset(
                root,
                classification("XRD", "xrd_processor"),
                source_b,
                triage={"queue_id": "reviewed_queue_bbbbbbbbbbbbbbbb"},
            )

            self.assertNotEqual(metadata_a["dataset_id"], metadata_b["dataset_id"])
            self.assertNotEqual(metadata_a["processed_data"], metadata_b["processed_data"])
            self.assertNotEqual(metadata_a["metadata_path"], metadata_b["metadata_path"])

    def test_processor_passes_method_specific_axis_titles_to_origin_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xrd.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["2theta", "intensity"])
                writer.writerow([10, 1])
                writer.writerow([20, 3])

            with patch("src.processors.base.export_plot") as export_plot:
                export_plot.return_value.ok = False
                export_plot.return_value.origin_file = None
                export_plot.return_value.figure_tif = None
                export_plot.return_value.preview_png = None
                export_plot.return_value.message = "Origin unavailable"
                process_table_dataset(root, classification("XRD", "xrd_processor"), source, no_origin=False)

            args, kwargs = export_plot.call_args
            self.assertEqual(args[3], "2θ (degree)")
            self.assertEqual(args[4], "Intensity (a.u.)")
            self.assertEqual(kwargs["data_type"], "XRD")

    def test_photocurrent_outputs_peak_and_steady_current_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "photocurrent.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["time", "current"])
                writer.writerow([0, 0.1])
                writer.writerow([1, 0.3])
                writer.writerow([2, 0.2])

            metadata = process_table_dataset(root, classification("photocurrent", "photocurrent_processor"), source)

            self.assertEqual(metadata["key_results"]["peak_current_candidate"], 0.3)
            self.assertAlmostEqual(metadata["key_results"]["steady_current_candidate"], 0.2)
            self.assertIn("on_off_ratio_candidate", metadata["key_results"])
            self.assertIn("light on/off intervals", " ".join(metadata["manual_check_items"]))
            rows = self._processed_rows(root, metadata)
            self.assertEqual(set(rows[0]), {"time_s", "photocurrent_uA", "cycle_candidate_id"})
            self.assertEqual(rows[1]["photocurrent_uA"], "300000.0")

    def test_photocurrent_response_outputs_peak_and_steady_current_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "photocurrent_response.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["time", "current"])
                writer.writerow([0, 0.0])
                writer.writerow([1, 0.6])
                writer.writerow([2, 0.4])

            metadata = process_table_dataset(root, classification("photocurrent_response", "photocurrent_processor"), source)

            self.assertEqual(metadata["key_results"]["peak_current_candidate"], 0.6)
            self.assertAlmostEqual(metadata["key_results"]["steady_current_candidate"], (0.0 + 0.6 + 0.4) / 3)
            self.assertEqual(metadata["key_results"]["on_off_ratio_candidate"], None)
            self.assertIn("response-cycle boundaries", " ".join(metadata["manual_check_items"]))

    def test_photocurrent_uses_light_markers_for_cycles_and_current_density_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "photocurrent_marked.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["time", "current", "light", "area_cm2"])
                writer.writerow([0, 0.1, "off", 2.0])
                writer.writerow([1, 0.2, "off", 2.0])
                writer.writerow([2, 1.0, "on", 2.0])
                writer.writerow([3, 1.2, "on", 2.0])

            metadata = process_table_dataset(root, classification("photocurrent", "photocurrent_processor"), source)

            self.assertAlmostEqual(metadata["key_results"]["on_off_ratio_candidate"], 7.333333333333333)
            self.assertEqual(metadata["key_results"]["light_on_points"], 2)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(set(rows[0]), {"time_s", "photocurrent_uA", "light_state", "cycle_candidate_id", "current_density_uA_cm2_optional"})
            self.assertEqual([row["cycle_candidate_id"] for row in rows], ["1", "1", "2", "2"])
            self.assertEqual(rows[2]["current_density_uA_cm2_optional"], "500000.0")

    def test_rejects_scan_only_reference_literature_when_called_directly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "kinetics.csv"
            source.write_text("x,y\n1,2\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                process_table_dataset(
                    root,
                    {
                        "inferred_data_type": "reference_literature",
                        "selected_processor": "none",
                        "supported_in_pipeline": False,
                    },
                    source,
                )

    def test_uvvis_drs_outputs_kubelka_munk_and_tauc_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "uvvis.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["wavelength", "reflectance"])
                writer.writerow([400, 50])
                writer.writerow([500, 40])

            metadata = process_table_dataset(root, classification("UV-vis DRS", "uvvis_drs_processor"), source)

            self.assertEqual(metadata["key_results"]["kubelka_munk_points"], 2)
            self.assertIn("photon_energy_range_eV", metadata["key_results"])
            self.assertIn("Eg_candidate", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertIn("reflectance_fraction", rows[0])
            self.assertIn("kubelka_munk", rows[0])
            self.assertIn("photon_energy_eV", rows[0])
            self.assertIn("tauc_y_direct_candidate", rows[0])

    def test_uvvis_drs_accepts_absorbance_exports_without_mislabeling_as_reflectance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "uvvis_abs.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["wavelength", "absorbance"])
                writer.writerow([400, 0.5])
                writer.writerow([500, 0.8])

            metadata = process_table_dataset(root, classification("UV-vis DRS", "uvvis_drs_processor"), source)

            self.assertEqual(metadata["key_results"]["uvvis_input_signal"], "absorbance")
            self.assertIn("tauc_interval_candidate_eV", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertIn("absorbance", rows[0])
            self.assertIn("tauc_y_absorbance_direct_candidate", rows[0])
            self.assertNotIn("reflectance", rows[0])

    def test_eis_outputs_nyquist_and_bode_candidates_from_impedance_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "eis.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["frequency", "Re(Z)", "-Im(Z)", "|Z|", "phase"])
                writer.writerow([1000, 10, 3, 10.44, -20])
                writer.writerow([100, 20, 8, 21.54, -30])

            metadata = process_table_dataset(root, classification("EIS", "eis_processor"), source)

            self.assertEqual(metadata["key_results"]["nyquist_points"], 2)
            self.assertEqual(metadata["key_results"]["bode_points"], 2)
            self.assertEqual(metadata["key_results"]["max_negative_imaginary_impedance"], 8.0)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(
                set(rows[0]),
                {"cleaned_z_real_ohm", "cleaned_minus_z_imag_ohm", "fit_z_real_ohm", "draft_fit_minus_z_imag_ohm"},
            )
            self.assertEqual(rows[0]["cleaned_z_real_ohm"], "10.0")
            self.assertEqual(rows[0]["cleaned_minus_z_imag_ohm"], "3.0")

    def test_eis_converts_imaginary_sign_and_derives_missing_impedance_magnitude(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "eis_imag.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["freq/Hz", "Zreal", "Im(Z)", "phase"])
                writer.writerow([1000, 3, -4, -53.1])
                writer.writerow([100, 5, -12, -67.4])

            metadata = process_table_dataset(root, classification("EIS", "eis_processor"), source)

            self.assertEqual(metadata["key_results"]["max_negative_imaginary_impedance"], 12.0)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(rows[0]["cleaned_minus_z_imag_ohm"], "4.0")
            self.assertEqual(rows[1]["cleaned_minus_z_imag_ohm"], "12.0")

    def test_eis_accepts_common_chi_z_prime_and_z_double_prime_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "eis_chi.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Freq/Hz", "Z'/ohm", 'Z"/ohm', "Phase/deg"])
                writer.writerow([1000, 3, 4, -53.1])
                writer.writerow([100, 5, 12, -67.4])

            metadata = process_table_dataset(root, classification("EIS", "eis_processor"), source)

            self.assertEqual(metadata["key_results"]["max_negative_imaginary_impedance"], 12.0)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(
                set(rows[0]),
                {"cleaned_z_real_ohm", "cleaned_minus_z_imag_ohm", "fit_z_real_ohm", "draft_fit_minus_z_imag_ohm"},
            )
            self.assertEqual(rows[0]["cleaned_z_real_ohm"], "3.0")
            self.assertEqual(rows[0]["cleaned_minus_z_imag_ohm"], "4.0")

    def test_eis_formal_processor_writes_cleaned_points_and_fit_curve_sidecars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "eis_semicircle.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Frequency (Hz)", "Z' (ohm)", "-Z'' (ohm)"])
                for index in range(1, 16):
                    writer.writerow([10 ** (5 - index / 3), 8 + index * 2.5, max(0.2, index * (16 - index) * 0.45)])
                writer.writerow([0.01, -100, -50])

            metadata = process_table_dataset(root, classification("EIS", "eis_processor"), source)

            self.assertEqual(metadata["processing_status"], "processed_no_origin")
            self.assertEqual(metadata["key_results"]["eis_fit"]["model"], "Model A: Rs + (Rct || CPE)")
            self.assertTrue(metadata["key_results"]["eis_cleaning"]["ignored_point_count"] >= 1)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(
                set(rows[0]),
                {
                    "cleaned_z_real_ohm",
                    "cleaned_minus_z_imag_ohm",
                    "fit_z_real_ohm",
                    "draft_fit_minus_z_imag_ohm",
                },
            )
            self.assertTrue(any(row["fit_z_real_ohm"] for row in rows))
            processed_path = _artifact_path(root, metadata["processed_data"])
            sidecar_dir = processed_path.parent / f"{processed_path.stem}_eis_sidecars"
            self.assertTrue((sidecar_dir / "raw_eis_data.csv").exists())
            self.assertTrue((sidecar_dir / "cleaned_eis_data.csv").exists())
            self.assertTrue((sidecar_dir / "ignored_eis_points.csv").exists())
            self.assertTrue((sidecar_dir / "eis_randles_cpe_fit_curve.csv").exists())
            self.assertTrue((sidecar_dir / "eis_cleaning_and_fit_metadata.json").exists())

    def test_pl_ftir_raman_output_peak_candidates(self):
        for data_type, processor in [
            ("PL", "pl_processor"),
            ("FTIR", "ftir_processor"),
            ("Raman", "raman_processor"),
        ]:
            with self.subTest(data_type=data_type), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                source = root / f"{data_type}.csv"
                with source.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["x", "intensity"])
                    writer.writerow([100, 1])
                    writer.writerow([200, 5])
                    writer.writerow([300, 2])

                metadata = process_table_dataset(root, classification(data_type, processor), source)

                self.assertIn(200.0, metadata["key_results"]["peak_position_candidates"])
                self.assertEqual(metadata["key_results"]["peak_intensity_candidate"], 5.0)
                self.assertEqual(metadata["key_results"]["integral_area_candidate"], 650.0)
                rows = self._processed_rows(root, metadata)
                self.assertIn("normalized_intensity", rows[0])

    def test_spectral_processors_add_optional_pybaselines_corrected_signal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "raman_baseline.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Raman shift", "intensity"])
                writer.writerow([100, 10])
                writer.writerow([200, 25])
                writer.writerow([300, 11])

            metadata = process_table_dataset(root, classification("Raman", "raman_processor"), source)

            self.assertEqual(metadata["key_results"]["pybaselines_baseline_correction_available"], True)
            self.assertEqual(metadata["key_results"]["pybaselines_method"], "asls_candidate")
            rows = self._processed_rows(root, metadata)
            self.assertIn("pybaselines_baseline_optional", rows[0])
            self.assertIn("pybaselines_corrected_intensity_optional", rows[0])

    def test_ftir_outputs_valley_candidates_for_transmittance_spectra(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "ftir_valley.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["wavenumber", "transmittance"])
                writer.writerow([4000, 90])
                writer.writerow([3400, 60])
                writer.writerow([2800, 85])

            metadata = process_table_dataset(root, classification("FTIR", "ftir_processor"), source)

            self.assertIn(3400.0, metadata["key_results"]["valley_position_candidates"])
            rows = self._processed_rows(root, metadata)
            self.assertIn("valley_candidate_flag", rows[0])
            self.assertEqual(rows[1]["valley_candidate_flag"], "1")

    def test_raman_preserves_baseline_raw_and_corrected_export_columns_as_facts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "raman_baseline.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Raman shift", "raw intensity", "baseline", "corrected intensity"])
                writer.writerow([100, 10, 2, 8])
                writer.writerow([200, 15, 3, 12])
                writer.writerow([300, 9, 2, 7])

            metadata = process_table_dataset(root, classification("Raman", "raman_processor"), source)

            self.assertEqual(metadata["key_results"]["baseline_column_preserved"], True)
            self.assertEqual(metadata["key_results"]["baseline_corrected_signal_present"], True)
            self.assertEqual(metadata["key_results"]["raw_signal_present"], True)
            self.assertNotIn("recombination_reduced", metadata["key_results"])
            self.assertNotIn("defect_type", metadata["key_results"])
            self.assertNotIn("chemical_bond_assignment", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertIn("raw_intensity_optional", rows[0])
            self.assertIn("baseline_optional", rows[0])
            self.assertIn("corrected_intensity_optional", rows[0])
            self.assertEqual(rows[1]["corrected_intensity_optional"], "12.0")

    def test_xps_outputs_descending_binding_energy_and_peak_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xps.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["binding energy", "intensity"])
                writer.writerow([280, 1])
                writer.writerow([282, 5])
                writer.writerow([284, 2])

            metadata = process_table_dataset(root, classification("XPS", "xps_processor"), source)

            self.assertIn(282.0, metadata["key_results"]["peak_position_candidates"])
            self.assertIn("area_candidate", metadata["key_results"])
            self.assertEqual(metadata["key_results"]["binding_energy_display"], "descending")
            self.assertIn("oxygen vacancies", " ".join(metadata["forbidden_claims"]))
            self.assertNotIn("valence", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertEqual(set(rows[0]), {"binding_energy_eV", "raw_intensity", "peak_candidate_flag"})

    def test_xps_preserves_exported_background_envelope_and_component_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xps_fit_export.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["binding energy", "raw intensity", "background", "envelope", "component A"])
                writer.writerow([284, 10, 1, 9, 4])
                writer.writerow([282, 20, 2, 18, 12])
                writer.writerow([280, 12, 1, 11, 6])

            metadata = process_table_dataset(root, classification("XPS", "xps_processor"), source)

            self.assertEqual(metadata["key_results"]["xps_component_columns"], ["component A"])
            self.assertEqual(metadata["key_results"]["xps_component_area_candidates"], {"component A": 34.0})
            self.assertIn("no valence assignment", " ".join(metadata["manual_check_items"]))
            rows = self._processed_rows(root, metadata)
            self.assertIn("background_optional", rows[0])
            self.assertIn("envelope_optional", rows[0])
            self.assertIn("component_A_optional", rows[0])
            self.assertEqual(rows[0]["binding_energy_eV"], "284.0")

    def test_xps_residuals_are_not_treated_as_fit_components(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xps_fit_export_residuals.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["binding energy", "raw intensity", "background", "envelope", "Residuals", "component A"])
                writer.writerow([284, 10, 1, 9, 0.1, 4])
                writer.writerow([282, 20, 2, 18, -0.2, 12])
                writer.writerow([280, 12, 1, 11, 0.1, 6])

            metadata = process_table_dataset(root, classification("XPS", "xps_processor"), source)

            self.assertEqual(metadata["key_results"]["xps_component_columns"], ["component A"])
            self.assertEqual(metadata["key_results"]["xps_component_area_candidates"], {"component A": 34.0})
            rows = self._processed_rows(root, metadata)
            self.assertNotIn("Residuals_optional", rows[0])

    def test_xps_uses_numeric_fallback_for_unnamed_export_columns_without_nan_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xps_unnamed_export.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Unnamed: 0", "Unnamed: 1", "Acquisition Parameters :", "Experiment Descriptions :"])
                writer.writerow(["nan", "nan", "instrument note", ""])
                writer.writerow(["", "", "metadata row", ""])
                writer.writerow([284, 10, "", ""])
                writer.writerow([282, 20, "", ""])
                writer.writerow([280, 12, "", ""])

            metadata = process_table_dataset(root, classification("XPS", "xps_processor"), source)

            self.assertEqual(metadata["key_results"]["point_count"], 3)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(len(rows), 3)
            self.assertEqual(set(rows[0]), {"binding_energy_eV", "raw_intensity", "peak_candidate_flag"})
            self.assertEqual(rows[0]["binding_energy_eV"], "284.0")
            self.assertEqual(rows[1]["raw_intensity"], "20.0")
            self.assertNotIn("nan", _artifact_path(root, metadata["processed_data"]).read_text(encoding="utf-8").lower())

    def test_condition_screening_and_lc_exported_data_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            screening = root / "screening.csv"
            with screening.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["condition", "yield"])
                writer.writerow([1, 20])
                writer.writerow([2, 45])
            screen_meta = process_table_dataset(root, classification("reaction_condition_screening", "condition_screening_processor"), screening)
            self.assertEqual(screen_meta["key_results"]["best_condition_value_candidate"], 45.0)
            screen_rows = self._processed_rows(root, screen_meta)
            self.assertEqual(set(screen_rows[0]), {"condition", "response_value", "best_condition_candidate_flag"})

            lc = root / "lc.csv"
            with lc.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["retention time", "area"])
                writer.writerow([1.5, 10])
                writer.writerow([2.0, 20])
            lc_meta = process_table_dataset(root, classification("HPLC/LC exported data", "lc_exported_data_processor"), lc)
            self.assertEqual(lc_meta["key_results"]["retention_time_range"], [1.5, 2.0])
            self.assertEqual(lc_meta["key_results"]["peak_area_total_candidate"], 30.0)
            self.assertEqual(lc_meta["key_results"]["lc_export_mode"], "peak_table")
            lc_rows = self._processed_rows(root, lc_meta)
            self.assertEqual(set(lc_rows[0]), {"retention_time_min", "signal", "peak_area_optional", "peak_height_optional"})

            chromatogram = root / "lc_chromatogram.csv"
            with chromatogram.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["time", "mAU"])
                writer.writerow([0.0, 1])
                writer.writerow([0.5, 5])
            chrom_meta = process_table_dataset(root, classification("HPLC/LC exported data", "lc_exported_data_processor"), chromatogram)
            self.assertEqual(chrom_meta["key_results"]["lc_export_mode"], "chromatogram")
            chrom_rows = self._processed_rows(root, chrom_meta)
            self.assertEqual(set(chrom_rows[0]), {"retention_time_min", "signal"})

    def test_lc_blocks_quantification_claims_without_calibration_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lc = root / "lc_quantification.csv"
            with lc.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["retention time", "area", "conversion", "selectivity", "product"])
                writer.writerow([1.5, 10, 80, 95, "target"])
                writer.writerow([2.0, 20, 85, 90, "byproduct"])

            metadata = process_table_dataset(root, classification("HPLC/LC exported data", "lc_exported_data_processor"), lc)

            self.assertEqual(metadata["key_results"]["peak_area_total_candidate"], 30.0)
            self.assertIn("lc_quantification_blocked_reason", metadata["key_results"])
            self.assertIn("calibration", metadata["key_results"]["lc_quantification_blocked_reason"])
            self.assertIn("calibration", " ".join(metadata["warnings"]).lower())
            self.assertNotIn("conversion_candidate", metadata["key_results"])
            self.assertNotIn("selectivity_candidate", metadata["key_results"])

    def test_xps_component_intensity_columns_are_kept_as_exported_components(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "xps_component_intensity.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["binding energy", "raw intensity", "background", "C 1s component intensity"])
                writer.writerow([284, 10, 1, 4])
                writer.writerow([282, 20, 2, 12])
                writer.writerow([280, 12, 1, 6])

            metadata = process_table_dataset(root, classification("XPS", "xps_processor"), source)

            self.assertEqual(metadata["key_results"]["xps_component_columns"], ["C 1s component intensity"])
            self.assertEqual(metadata["key_results"]["xps_component_area_candidates"], {"C 1s component intensity": 34.0})
            rows = self._processed_rows(root, metadata)
            self.assertIn("C_1s_component_intensity_optional", rows[0])

    def test_condition_screening_preserves_categorical_conditions_and_selects_best_response(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            screening = root / "categorical_screening.csv"
            with screening.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["catalyst", "solvent", "yield"])
                writer.writerow(["CWO", "water", 18])
                writer.writerow(["BOBC", "methanol", 42])

            metadata = process_table_dataset(
                root,
                classification("reaction_condition_screening", "condition_screening_processor"),
                screening,
            )

            self.assertEqual(metadata["key_results"]["best_condition_value_candidate"], 42.0)
            rows = self._processed_rows(root, metadata)
            self.assertEqual(rows[0]["condition"], "CWO | water")
            self.assertEqual(rows[1]["condition"], "BOBC | methanol")
            self.assertEqual(rows[1]["best_condition_candidate_flag"], "1")

    def test_bet_epr_mott_schottky_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bet = root / "bet.csv"
            with bet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["relative pressure", "quantity adsorbed"])
                writer.writerow([0.1, 5])
                writer.writerow([0.2, 7])
            bet_meta = process_table_dataset(root, classification("BET", "bet_processor"), bet)
            self.assertEqual(bet_meta["key_results"]["isotherm_points"], 2)
            self.assertEqual(bet_meta["key_results"]["pygaps_relative_pressure_range"], [0.1, 0.2])
            self.assertEqual(
                bet_meta["key_results"]["adapter_results"]["BET"]["metadata_provenance"]["adapter"],
                "bet_pygaps_adapter",
            )
            self.assertIn(
                "pygaps_pointisotherm_candidate_no_bet_fit",
                bet_meta["parameters"]["algorithm_provenance"]["candidate_methods"],
            )
            bet_rows = self._processed_rows(root, bet_meta)
            self.assertEqual(set(bet_rows[0]), {"relative_pressure_p_p0", "adsorbed_volume", "desorption_volume_optional"})

            epr = root / "epr.csv"
            with epr.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["magnetic field", "intensity"])
                writer.writerow([3400, -2])
                writer.writerow([3450, 3])
            epr_meta = process_table_dataset(root, classification("EPR", "epr_processor"), epr)
            self.assertEqual(epr_meta["key_results"]["peak_to_peak_intensity_candidate"], 5.0)
            epr_rows = self._processed_rows(root, epr_meta)
            self.assertEqual(set(epr_rows[0]), {"magnetic_field", "intensity", "normalized_intensity"})

            mott = root / "mott.csv"
            with mott.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["potential", "capacitance"])
                writer.writerow([-0.2, 1.0])
                writer.writerow([0.1, 10.0])
                writer.writerow([0.4, 0.5])
            mott_meta = process_table_dataset(root, classification("Mott-Schottky", "mott_schottky_processor"), mott)
            self.assertAlmostEqual(
                mott_meta["key_results"]["flat_band_potential_candidate"],
                mott_meta["key_results"]["linear_x_intercept_candidate"],
            )
            mott_rows = self._processed_rows(root, mott_meta)
            self.assertIn("one_over_c_squared", mott_rows[0])
            self.assertEqual(mott_rows[1]["one_over_c_squared"], "0.01")

    def test_mott_schottky_does_not_treat_current_as_capacitance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "mott_current_only.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Potential/V", "Current/A"])
                writer.writerow([0.0, 2.0])
                writer.writerow([0.1, 4.0])

            metadata = process_table_dataset(root, classification("Mott-Schottky", "mott_schottky_processor"), source)

            rows = self._processed_rows(root, metadata)
            self.assertEqual(rows, [])
            self.assertNotIn("linear_x_intercept_candidate", metadata["key_results"])

    def test_metadata_records_algorithm_provenance_for_candidate_calculations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "mott_linear.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["potential", "1/C^2"])
                writer.writerow([-0.2, -1.0])
                writer.writerow([0.0, 1.0])
                writer.writerow([0.2, 3.0])

            metadata = process_table_dataset(root, classification("Mott-Schottky", "mott_schottky_processor"), source)

            provenance = metadata["parameters"]["algorithm_provenance"]
            self.assertEqual(provenance["processor_name"], "mott_schottky_processor")
            self.assertEqual(provenance["calculation_module"], "src.processors.calculations")
            self.assertIn("linear_region_candidate", provenance["candidate_methods"])
            self.assertEqual(provenance["fit_point_count"], 3)

    def test_bet_summary_table_extracts_surface_area_pore_volume_and_diameter_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bet = root / "bet_summary.csv"
            with bet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["BET surface area", "total pore volume", "average pore diameter"])
                writer.writerow([58.2, 0.18, 12.4])

            metadata = process_table_dataset(root, classification("BET", "bet_processor"), bet)

            self.assertEqual(metadata["key_results"]["bet_surface_area_m2_g_candidate"], 58.2)
            self.assertEqual(metadata["key_results"]["pore_volume_cm3_g_candidate"], 0.18)
            self.assertEqual(metadata["key_results"]["average_pore_diameter_nm_candidate"], 12.4)
            self.assertEqual(metadata["key_results"]["bet_table_kind_candidate"], "summary_only")
            self.assertNotIn("isotherm_points", metadata["key_results"])
            self.assertNotIn("pore_distribution_points", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertEqual(
                set(rows[0]),
                {"bet_surface_area_m2_g_candidate", "pore_volume_cm3_g_candidate", "average_pore_diameter_nm_candidate"},
            )

    def test_bet_metric_value_unit_summary_table_extracts_reported_values_without_fitting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bet = root / "bet_metric_summary.csv"
            with bet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["metric", "value", "unit"])
                writer.writerow(["BET surface area", 52.3, "m2/g"])
                writer.writerow(["total pore volume", 0.18, "cm3/g"])
                writer.writerow(["average pore diameter", 14.2, "nm"])

            metadata = process_table_dataset(root, classification("BET", "bet_processor"), bet)

            self.assertEqual(metadata["key_results"]["bet_surface_area_m2_g_candidate"], 52.3)
            self.assertEqual(metadata["key_results"]["pore_volume_cm3_g_candidate"], 0.18)
            self.assertEqual(metadata["key_results"]["average_pore_diameter_nm_candidate"], 14.2)
            self.assertEqual(metadata["key_results"]["bet_table_kind_candidate"], "summary_only")
            self.assertNotIn("isotherm_points", metadata["key_results"])
            self.assertNotIn("pore_distribution_points", metadata["key_results"])
            self.assertNotIn("bet_fit", metadata["key_results"])

    def test_bet_summary_like_multirow_table_does_not_become_pore_distribution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bet = root / "bet_sample_summary_rows.csv"
            with bet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["sample", "average pore diameter", "total pore volume"])
                writer.writerow(["A", 12.4, 0.18])
                writer.writerow(["B", 15.2, 0.20])
                writer.writerow(["C", 18.1, 0.24])

            metadata = process_table_dataset(root, classification("BET", "bet_processor"), bet)

            self.assertEqual(metadata["key_results"]["bet_table_kind_candidate"], "summary_only")
            self.assertNotIn("isotherm_points", metadata["key_results"])
            self.assertNotIn("pore_distribution_points", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertEqual(
                set(rows[0]),
                {"bet_surface_area_m2_g_candidate", "pore_volume_cm3_g_candidate", "average_pore_diameter_nm_candidate"},
            )

    def test_bet_vendor_report_extracts_isotherm_branches_instead_of_summary_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bet = root / "vendor_bet_report.csv"
            with bet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["report_a", "report_b", "report_c", "report_d", "report_e"])
                writer.writerow(["Sample:", "BOBC", "", "", ""])
                writer.writerow(
                    [
                        "Relative Pressure (P/Po)",
                        "Quantity Adsorbed (cm³/g STP)",
                        "Relative Pressure (P/Po)",
                        "Quantity Adsorbed (cm³/g STP)",
                        "",
                    ]
                )
                for pressure, adsorbed, des_pressure, desorbed in [
                    (0.01, 0.8, 0.99, 16.0),
                    (0.10, 1.0, 0.90, 3.4),
                    (0.30, 1.2, 0.70, 1.9),
                    (0.60, 1.6, 0.40, 1.4),
                    (0.90, 3.0, 0.10, 1.0),
                    (0.99, 16.0, 0.01, 0.8),
                ]:
                    writer.writerow([pressure, adsorbed, des_pressure, desorbed, ""])

            metadata = process_table_dataset(root, classification("BET", "bet_processor"), bet)

            rows = self._processed_rows(root, metadata)
            self.assertGreaterEqual(len(rows), 6)
            self.assertEqual(
                set(rows[0]),
                {"relative_pressure_p_p0", "adsorbed_volume", "desorption_volume_optional"},
            )
            self.assertEqual(rows[0]["relative_pressure_p_p0"], "0.01")
            self.assertEqual(rows[-1]["relative_pressure_p_p0"], "0.99")
            self.assertNotIn("bet_surface_area_m2_g_candidate", rows[0])
            self.assertEqual(metadata["key_results"]["bet_table_kind_candidate"], "isotherm")
            self.assertEqual(metadata["key_results"]["isotherm_points"], 6)
            self.assertNotIn("pore_distribution_points", metadata["key_results"])

    def test_bet_pore_distribution_table_extracts_curve_not_summary_point(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bet = root / "bet_pore_distribution.csv"
            with bet.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["pore size (nm)", "dV/dlog(D) pore volume (cm3/g)", "BET surface area"])
                writer.writerow([2.0, 0.01, 52.3])
                writer.writerow([8.0, 0.12, 52.3])
                writer.writerow([20.0, 0.03, 52.3])

            metadata = process_table_dataset(root, classification("BET", "bet_processor"), bet)

            rows = self._processed_rows(root, metadata)
            self.assertEqual(set(rows[0]), {"pore_size_nm", "pore_volume_cm3_g"})
            self.assertEqual(rows[0]["pore_size_nm"], "2.0")
            self.assertEqual(rows[1]["pore_volume_cm3_g"], "0.12")
            self.assertEqual(metadata["key_results"]["bet_table_kind_candidate"], "pore_distribution")
            self.assertEqual(metadata["key_results"]["pore_distribution_points"], 3)
            self.assertNotIn("isotherm_points", metadata["key_results"])
            self.assertNotIn("bet_surface_area_m2_g_candidate", rows[0])

    def test_epr_reports_extrema_and_g_candidate_when_microwave_frequency_is_exported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epr = root / "epr_g.csv"
            with epr.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["magnetic field G", "intensity", "microwave frequency GHz"])
                writer.writerow([3450, -2, 9.8])
                writer.writerow([3500, 6, 9.8])
                writer.writerow([3550, 1, 9.8])

            metadata = process_table_dataset(root, classification("EPR", "epr_processor"), epr)

            self.assertEqual(metadata["key_results"]["minimum_intensity_field"], 3450.0)
            self.assertEqual(metadata["key_results"]["maximum_intensity_field"], 3500.0)
            self.assertAlmostEqual(metadata["key_results"]["g_candidate_at_max_intensity"], 2.0005, places=3)
            rows = self._processed_rows(root, metadata)
            self.assertIn("g_candidate_optional", rows[0])

    def test_epr_frequency_lookup_supports_constant_time_reuse(self):
        from src.processors.calculations import epr_frequency_for_field, epr_frequency_lookup

        rows = [
            {"magnetic field": str(3400 + index), "microwave frequency GHz": "9.8"}
            for index in range(1000)
        ]

        lookup = epr_frequency_lookup(rows)

        self.assertEqual(len(lookup), 1000)
        self.assertEqual(epr_frequency_for_field([], 3500, lookup), 9.8)
        self.assertEqual(epr_frequency_for_field([], 3500.0000000001, lookup), 9.8)

    def test_mott_schottky_reports_linear_x_intercept_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mott = root / "mott_linear.csv"
            with mott.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["potential", "1/C^2"])
                writer.writerow([-0.2, -1.0])
                writer.writerow([0.0, 1.0])
                writer.writerow([0.2, 3.0])

            metadata = process_table_dataset(root, classification("Mott-Schottky", "mott_schottky_processor"), mott)

            self.assertAlmostEqual(metadata["key_results"]["flat_band_potential_candidate"], -0.1)
            self.assertAlmostEqual(metadata["key_results"]["linear_x_intercept_candidate"], -0.1)
            self.assertIn("linear_interval_candidate", metadata["key_results"])
            self.assertGreaterEqual(metadata["key_results"]["linear_region_candidates"][0]["r_squared"], 0.999)

    def test_mott_schottky_groups_linear_regression_by_frequency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mott = root / "mott_frequency.csv"
            with mott.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["potential", "1/C^2", "frequency Hz"])
                writer.writerow([0.0, 1.0, 1000])
                writer.writerow([0.0, 10.0, 2000])
                writer.writerow([1.0, 3.0, 1000])
                writer.writerow([1.0, 7.0, 2000])
                writer.writerow([2.0, 5.0, 1000])
                writer.writerow([2.0, 4.0, 2000])

            metadata = process_table_dataset(root, classification("Mott-Schottky", "mott_schottky_processor"), mott)

            groups = {
                group["frequency"]: group
                for group in metadata["key_results"]["mott_schottky_frequency_groups"]
            }
            self.assertEqual(set(groups), {1000.0, 2000.0})
            self.assertEqual(groups[1000.0]["point_count"], 3)
            self.assertAlmostEqual(groups[1000.0]["linear_slope_candidate"], 2.0)
            self.assertAlmostEqual(groups[1000.0]["linear_intercept_candidate"], 1.0)
            self.assertAlmostEqual(groups[1000.0]["linear_x_intercept_candidate"], -0.5)
            self.assertAlmostEqual(groups[2000.0]["linear_slope_candidate"], -3.0)
            self.assertAlmostEqual(groups[2000.0]["linear_intercept_candidate"], 10.0)
            self.assertAlmostEqual(groups[2000.0]["linear_x_intercept_candidate"], 10.0 / 3.0)
            self.assertGreaterEqual(groups[1000.0]["r_squared"], 0.999)
            self.assertGreaterEqual(groups[2000.0]["r_squared"], 0.999)
            self.assertNotIn("conduction_band_candidate", metadata["key_results"])
            self.assertNotIn("valence_band_candidate", metadata["key_results"])
            rows = self._processed_rows(root, metadata)
            self.assertIn("frequency_optional", rows[0])
            self.assertEqual(rows[1]["frequency_optional"], "2000.0")


if __name__ == "__main__":
    unittest.main()
