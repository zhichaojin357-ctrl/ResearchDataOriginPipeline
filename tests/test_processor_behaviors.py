import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.table_reader import coerce_numeric_rows, read_table
from src.processors.base import process_table_dataset


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
    }


class ProcessorBehaviorTest(unittest.TestCase):
    def _processed_rows(self, root: Path, metadata: dict) -> list[dict[str, str]]:
        with (root / metadata["processed_data"]).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_generic_reader_preserves_first_row_from_headerless_whitespace_numeric_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "sample.xy"
            source.write_text("10 1\n20 5\n30 2\n", encoding="utf-8")

            rows = read_table(source)
            numeric = coerce_numeric_rows(rows)

            self.assertEqual(numeric, [(10.0, 1.0), (20.0, 5.0), (30.0, 2.0)])

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
            self.assertEqual(args[3], "two_theta_deg")
            self.assertEqual(args[4], "intensity")
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
            self.assertEqual(set(rows[0]), {"time_s", "current", "cycle_candidate_id"})

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
            self.assertEqual(set(rows[0]), {"time_s", "current", "light_state", "cycle_candidate_id", "current_density_optional"})
            self.assertEqual([row["cycle_candidate_id"] for row in rows], ["1", "1", "2", "2"])
            self.assertEqual(rows[2]["current_density_optional"], "0.5")

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
                        "supported_in_phase_1": False,
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
            self.assertEqual(set(rows[0]), {"frequency", "real_impedance", "neg_imag_impedance", "impedance_magnitude", "phase"})
            self.assertEqual(rows[0]["real_impedance"], "10.0")
            self.assertEqual(rows[0]["neg_imag_impedance"], "3.0")

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
            self.assertEqual(rows[0]["neg_imag_impedance"], "4.0")
            self.assertEqual(rows[0]["impedance_magnitude"], "5.0")
            self.assertEqual(rows[1]["impedance_magnitude"], "13.0")

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
            self.assertNotIn("nan", (root / metadata["processed_data"]).read_text(encoding="utf-8").lower())

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
            self.assertNotIn("bet_fit", metadata["key_results"])

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
