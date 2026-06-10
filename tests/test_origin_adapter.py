from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.origin.adapter import (
    BetCombinedSource,
    _ensure_tif_600_dpi,
    _bet_material_display_name,
    build_origin_invocation_script,
    build_origin_plot_job,
    build_bet_combined_origin_job,
    build_bet_combined_origin_invocation_script,
    export_plot,
    origin_smoke_test,
    write_origin_error,
    write_origin_success,
    _run_origin_job,
)
from src.origin.plot_policy import GRAPH4_FIXED_STYLE


class _FakeOperationResult:
    def __init__(self, ok: bool = True, message: str = "ok", payload: dict | None = None) -> None:
        self.ok = ok
        self.message = message
        self.payload = payload or {}


class _FakeOriginOperations:
    def __init__(self) -> None:
        self.closed = False
        self.axis_labels: list[tuple[str, str, str, str]] = []

    def new_project(self) -> _FakeOperationResult:
        return _FakeOperationResult()

    def import_csv_to_worksheet(self, _path: Path, book_name: str = "", delimiter: str = ",") -> _FakeOperationResult:
        return _FakeOperationResult(payload={"book_name": book_name or "Book1"})

    def create_graph(self, graph_name: str, *_args, **_kwargs) -> _FakeOperationResult:
        return _FakeOperationResult(payload={"graph_name": graph_name})

    def set_axis_labels(self, graph_name: str, x_label: str = "", y_label: str = "", title: str = "") -> _FakeOperationResult:
        self.axis_labels.append((graph_name, x_label, y_label, title))
        return _FakeOperationResult()

    def save_project(self, path: Path) -> _FakeOperationResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("opju", encoding="utf-8")
        return _FakeOperationResult()

    def export_graph(self, _graph_name: str, path: Path, _format: str) -> _FakeOperationResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("figure", encoding="utf-8")
        return _FakeOperationResult()

    def close(self) -> _FakeOperationResult:
        self.closed = True
        return _FakeOperationResult()


class OriginSmokeTestUnavailableDependencies(unittest.TestCase):
    def test_phase1_plot_types_are_explicitly_mapped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "processed.csv"
            data.write_text("x,y\n0,1\n", encoding="utf-8")

            expectations = {
                "XRD": ("line", "200", True, False, False),
                "EIS": ("line+symbol", "202", True, True, True),
                "BET": ("line+symbol", "202", True, True, True),
                "Mott-Schottky": ("line+symbol", "202", True, True, True),
                "reaction_condition_screening": ("column", "203", True, True, True),
                "XPS fitted": ("fitted_component_overlay", "200", True, True, False),
                "SEM_image_panel": ("image_panel", "200", False, False, False),
            }
            for data_type, expected in expectations.items():
                with self.subTest(data_type=data_type):
                    if data_type == "BET":
                        data.write_text("relative_pressure_p_p0,adsorbed_volume\n0.01,0.8\n0.99,16\n", encoding="utf-8")
                    else:
                        data.write_text("x,y\n0,1\n", encoding="utf-8")
                    job = build_origin_plot_job(project_root, f"{data_type}_sample", data, "x", "y", data_type)
                    self.assertEqual(
                        (
                            job.plot_policy.plot_primitive,
                            job.plot_type_code,
                            job.plot_policy.y_axis_visible,
                            job.plot_policy.y_ticks_visible,
                            job.plot_policy.y_tick_values_visible,
                        ),
                        expected,
                    )

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
            self.assertEqual(job.plot_policy.plot_primitive, "column")
            self.assertTrue(job.plot_policy.y_tick_values_visible)
            self.assertIn("PlotType = '203'", script)
            self.assertIn("PlotPrimitive = 'column'", script)
            self.assertIn("ShowYTickValues = $true", script)

    def test_spectral_policy_hides_only_y_numeric_tick_values_in_job_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "raman.csv"
            data.write_text("shift,intensity\n100,1\n200,2\n", encoding="utf-8")

            job = build_origin_plot_job(project_root, "raman_offset", data, "Raman shift", "Intensity", "Raman")
            script = build_origin_invocation_script(job)

            self.assertTrue(job.plot_policy.y_axis_visible)
            self.assertTrue(job.plot_policy.y_ticks_visible)
            self.assertFalse(job.plot_policy.y_tick_values_visible)
            self.assertIn("ShowYAxis = $true", script)
            self.assertIn("ShowYTicks = $true", script)
            self.assertIn("ShowYTickValues = $false", script)
            self.assertIn("MarkerMode = 'none'", script)

    def test_epr_plot_uses_raw_intensity_and_hides_y_axis_ticks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "epr_processed.csv"
            data.write_text(
                "\n".join(
                    [
                        "magnetic_field,intensity,normalized_intensity",
                        "324.0,40,0.3",
                        "324.1,42,0.4",
                    ]
                ),
                encoding="utf-8",
            )

            job = build_origin_plot_job(project_root, "epr_oh_dark", data, "Magnetic Field (G)", "Intensity (a.u.)", "EPR")
            script = build_origin_invocation_script(job)

            self.assertEqual(job.plot_csv.read_text(encoding="utf-8").splitlines()[0], "magnetic_field,intensity")
            self.assertEqual(job.labels, ("epr oh dark",))
            self.assertTrue(job.plot_policy.y_axis_visible)
            self.assertFalse(job.plot_policy.y_ticks_visible)
            self.assertFalse(job.plot_policy.y_tick_values_visible)
            self.assertIn("ShowYTicks = $false", script)
            self.assertIn("ShowYTickValues = $false", script)

    def test_point_line_policy_uses_line_symbol_origin_plot_type_and_marker_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "eis.csv"
            data.write_text("real_impedance,neg_imag_impedance,residual\n1,2,0.1\n", encoding="utf-8")

            job = build_origin_plot_job(project_root, "eis_nyquist", data, "Z'", "-Z''", "EIS")
            script = build_origin_invocation_script(job)

            self.assertEqual(job.plot_type_code, "202")
            self.assertEqual(job.plot_policy.plot_primitive, "line+symbol")
            self.assertEqual(job.plot_csv.read_text(encoding="utf-8").splitlines()[0], "real_impedance,neg_imag_impedance")
            self.assertIn("PlotType = '202'", script)
            self.assertIn("MarkerMode = 'markers_preferred'", script)
            self.assertIn("ShowYTickValues = $true", script)

    def test_bet_isotherm_uses_relative_pressure_and_branch_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "bet_isotherm.csv"
            data.write_text(
                "\n".join(
                    [
                        "relative_pressure_p_p0,adsorbed_volume,desorption_volume_optional,bet_surface_area_m2_g_candidate",
                        "0.01,0.8,0.7,52.3",
                        "0.10,1.0,0.9,52.3",
                        "0.99,16.0,15.5,52.3",
                    ]
                ),
                encoding="utf-8",
            )

            job = build_origin_plot_job(project_root, "bet_isotherm", data, "Relative Pressure (P/Po)", "Quantity Adsorbed", "BET")
            script = build_origin_invocation_script(job)

            self.assertEqual(job.plot_csv.read_text(encoding="utf-8").splitlines()[0], "relative_pressure_p_p0,adsorbed_volume,desorption_volume_optional")
            self.assertEqual(job.plot_policy.plot_primitive, "line+symbol")
            self.assertEqual(job.plot_type_code, "202")
            self.assertEqual(job.plot_policy.marker_policy, "symbols_required_for_branches")
            self.assertTrue(job.plot_policy.y_tick_values_visible)
            self.assertIn("MarkerMode = 'symbols_required_for_branches'", script)
            self.assertIn("ShowYTickValues = $true", script)

    def test_bet_pore_distribution_uses_pore_size_and_volume_curve_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "bet_pore_distribution.csv"
            data.write_text(
                "\n".join(
                    [
                        "pore_size_nm,pore_volume_cm3_g,bet_surface_area_m2_g_candidate",
                        "2.0,0.01,52.3",
                        "8.0,0.12,52.3",
                        "20.0,0.03,52.3",
                    ]
                ),
                encoding="utf-8",
            )

            job = build_origin_plot_job(project_root, "bet_pore_distribution", data, "Pore size (nm)", "Pore volume", "BET")
            script = build_origin_invocation_script(job)

            self.assertEqual(job.plot_csv.read_text(encoding="utf-8").splitlines()[0], "pore_size_nm,pore_volume_cm3_g")
            self.assertEqual(job.plot_policy.plot_primitive, "line+symbol")
            self.assertEqual(job.plot_type_code, "202")
            self.assertTrue(job.plot_policy.y_tick_values_visible)
            self.assertIn("ShowYTickValues = $true", script)

    def test_bet_summary_metrics_are_not_plotted_as_single_point_curves(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "bet_summary.csv"
            data.write_text(
                "bet_surface_area_m2_g_candidate,pore_volume_cm3_g_candidate,average_pore_diameter_nm_candidate\n"
                "58.2,0.18,12.4\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "BET Origin plot requires"):
                build_origin_plot_job(project_root, "bet_summary", data, "BET surface area", "Pore volume", "BET")

    def test_spectral_plot_uses_raw_intensity_not_normalized_or_optional_corrections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "raman_processed.csv"
            data.write_text(
                "\n".join(
                    [
                        "x,intensity,normalized_intensity,pybaselines_corrected_intensity_optional",
                        "100,10,0.1,2",
                        "200,20,0.2,3",
                    ]
                ),
                encoding="utf-8",
            )

            job = build_origin_plot_job(project_root, "Raman_BOBC", data, "Raman Shift (cm-1)", "Intensity (a.u.)", "Raman")

            self.assertEqual(job.plot_csv.read_text(encoding="utf-8").splitlines()[0], "x,intensity")
            self.assertEqual(job.labels, ("Raman BOBC",))

    def test_xrd_plot_uses_raw_pattern_only_not_reference_card_or_phase_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "xrd_processed.csv"
            data.write_text(
                "\n".join(
                    [
                        "two_theta_deg,intensity,normalized_intensity,peak_candidate_flag,reference_card_intensity,JCPDS_pdf_intensity,hkl_101,phase_label",
                        "10,100,0.5,0,5,8,1,CWO",
                        "20,200,1.0,1,9,12,1,CWO",
                    ]
                ),
                encoding="utf-8",
            )

            job = build_origin_plot_job(project_root, "xrd_raw_only", data, "2theta", "Intensity", "XRD")
            script = build_origin_invocation_script(job)
            plot_text = job.plot_csv.read_text(encoding="utf-8")

            self.assertEqual(plot_text.splitlines()[0], "two_theta_deg,intensity")
            self.assertEqual(job.plot_policy.plot_primitive, "line")
            self.assertEqual(job.plot_type_code, "200")
            self.assertFalse(job.plot_policy.y_tick_values_visible)
            self.assertIn("PlotPrimitive = 'line'", script)
            self.assertIn("ShowYTicks = $false", script)
            self.assertIn("ShowYTickValues = $false", script)
            helper_text = job.helper_script.read_text(encoding="utf-8")
            self.assertIn("layer.y.ticklength=0", helper_text)
            self.assertIn("layer.y2.ticks=0", helper_text)
            self.assertNotIn("reference_card", plot_text)
            self.assertNotIn("JCPDS", plot_text)
            self.assertNotIn("hkl", plot_text)
            self.assertNotIn("phase", plot_text)

    def test_xrd_reference_card_only_table_is_rejected_for_automatic_plotting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "xrd_reference_only.csv"
            data.write_text(
                "\n".join(
                    [
                        "two_theta_deg,reference_card_intensity,JCPDS_pdf_intensity,hkl_101,phase_label",
                        "10,5,8,1,CWO",
                        "20,9,12,1,CWO",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "XRD plot requires a raw pattern"):
                build_origin_plot_job(project_root, "xrd_reference_only", data, "2theta", "Intensity", "XRD")

    def test_origin_helper_falls_back_to_extracted_reference_style_when_template_save_missing(self) -> None:
        helper = Path("scripts/origin/origin_plot_from_template.ps1").read_text(encoding="utf-8")

        self.assertIn("REFERENCE_TEMPLATE_SAVE_FAILED_USING_EXTRACTED_STYLE", helper)
        self.assertIn("$template = $null", helper)

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
                        "axis_title_size: 36",
                        "x_tick_label_size: 28",
                        "y_tick_label_size: 36",
                        "legend_font_size: 26",
                        "annotation_font_size: 26",
                        "font_bold: true",
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
            self.assertEqual(job.fixed_style.x_tick_label_size, 28)
            self.assertEqual(job.fixed_style.y_tick_label_size, 36)
            self.assertEqual(job.fixed_style.legend_font_size, 26)
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

    def test_bet_origin_job_keeps_desorption_optional_branch_as_plot_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            data = project_root / "bet_processed.csv"
            data.write_text(
                "\n".join(
                    [
                        "relative_pressure_p_p0,adsorbed_volume,desorption_volume_optional",
                        "0.01,0.8,0.9",
                        "0.99,16.0,7.8",
                    ]
                ),
                encoding="utf-8",
            )

            job = build_origin_plot_job(
                project_root,
                "BET_BOBC",
                data,
                "Relative Pressure (P/P0)",
                "Quantity Adsorbed (cm3/g STP)",
                "BET",
                source_file=project_root / "BOBC.xls",
            )

            self.assertEqual(
                job.plot_csv.read_text(encoding="utf-8").splitlines()[0],
                "relative_pressure_p_p0,adsorbed_volume,desorption_volume_optional",
            )
            self.assertEqual(job.labels, ("Quantity Adsorbed", "Quantity Desorption"))
            self.assertEqual(job.color_assignments[0]["material_role"], "branch")
            self.assertEqual(job.color_assignments[1]["material_role"], "branch")
            self.assertFalse(job.color_assignments[0]["requires_user_review"])
            self.assertFalse(job.color_assignments[1]["requires_user_review"])
            self.assertNotEqual(job.curve_colors[0], job.curve_colors[1])
            self.assertEqual(job.column_count, 3)

    def test_bet_material_names_expand_to_full_formula_labels(self) -> None:
        self.assertEqual(_bet_material_display_name("XWM-LL-260421-2-CWO-All Pore"), "CuWO4")
        self.assertEqual(_bet_material_display_name("XWM-LL-260421-3-BiCu-All Pore"), "BiCu-10")
        self.assertEqual(_bet_material_display_name("XWM-LL-260428-1-BOBC-All Pore"), "BiOBrCl")

    def test_bet_combined_origin_job_groups_primary_three_then_remaining_in_one_opju(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            def write_processed(name: str, scale: float) -> Path:
                path = project_root / f"{name}_processed.csv"
                path.write_text(
                    "\n".join(
                        [
                            "relative_pressure_p_p0,adsorbed_volume,desorption_volume_optional",
                            f"0.01,{scale},{scale + 0.1}",
                            f"0.99,{scale + 1},{scale + 1.1}",
                        ]
                    ),
                    encoding="utf-8",
                )
                return path

            sources = [
                BetCombinedSource("BOBC early", write_processed("bobc_early", 1), project_root / "XWM-LL-260421-1-BOBC-All Pore.XLS"),
                BetCombinedSource("CWO", write_processed("cwo", 2), project_root / "XWM-LL-260421-2-CWO-All Pore.XLS"),
                BetCombinedSource("BiCu", write_processed("bicu", 3), project_root / "XWM-LL-260421-3-BiCu-All Pore.XLS"),
                BetCombinedSource("BOBC xin", write_processed("bobc_xin", 4), project_root / "XWM-LL-260421-4-BOBC-4-XIN-All Pore.XLS"),
                BetCombinedSource("BiCu later", write_processed("bicu_later", 5), project_root / "XWM-LL-1-260522-BiCu-All Pore.XLS"),
                BetCombinedSource("BOBC later", write_processed("bobc_later", 6), project_root / "XWM-LL-260428-1-BOBC-All Pore.XLS"),
            ]

            job = build_bet_combined_origin_job(project_root, "BET_combined_26_5_29", sources)
            script = build_bet_combined_origin_invocation_script(job)

            self.assertEqual(job.origin_file.name, "BET_combined_26_5_29.opju")
            self.assertEqual([group.page_name for group in job.groups], ["BET_primary_materials", "BET_additional_materials"])
            self.assertEqual(
                job.groups[0].labels,
                (
                    "CuWO4 adsorption",
                    "CuWO4 desorption",
                    "BiCu-10 adsorption",
                    "BiCu-10 desorption",
                    "BiOBrCl adsorption",
                    "BiOBrCl desorption",
                ),
            )
            self.assertEqual(
                job.groups[1].labels,
                (
                    "BiOBrCl adsorption",
                    "BiOBrCl desorption",
                    "BiCu-10 adsorption",
                    "BiCu-10 desorption",
                    "BiOBrCl adsorption",
                    "BiOBrCl desorption",
                ),
            )
            self.assertIn("-OutputOpju", script)
            self.assertEqual(script.count("PageName ="), 2)
            self.assertIn("BET_primary_materials", script)
            self.assertIn("BET_additional_materials", script)
            self.assertIn("CuWO4 adsorption", script)
            self.assertIn("BiCu-10 adsorption", script)
            self.assertIn("BiOBrCl adsorption", script)

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

    def test_origin_smoke_test_uses_isolated_operations_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            fake = _FakeOriginOperations()

            with patch("src.origin.adapter.check_origin_available", return_value=(True, "origin available")):
                with patch("src.origin.adapter.connect_origin", return_value=fake) as connect_origin:
                    result = origin_smoke_test(project_root)

            self.assertTrue(result.ok)
            self.assertEqual(result.message, "Origin isolated operations smoke test succeeded")
            connect_origin.assert_called_once_with(entrypoint="Origin.Application", isolated=True, visible=False)
            self.assertTrue(fake.closed)
            self.assertEqual(fake.axis_labels, [("origin_smoke_test", "x", "y", "")])
            self.assertTrue((project_root / "output" / "origin_files" / "origin_smoke_test.opju").exists())
            self.assertTrue((project_root / "output" / "figures_tif" / "origin_smoke_test.tif").exists())
            self.assertTrue((project_root / "output" / "figures_preview" / "origin_smoke_test.png").exists())
            self.assertEqual(
                (project_root / "output" / "reports" / "origin_errors.md").read_text(encoding="utf-8"),
                "# Origin Errors\n\nNo current Origin errors.\n",
            )

    def test_check_origin_available_honors_test_disable_guard(self) -> None:
        with patch.dict(
            "src.origin.adapter.os.environ",
            {"RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN": "1"},
            clear=True,
        ):
            from src.origin.adapter import check_origin_available

            ok, message = check_origin_available()

        self.assertFalse(ok)
        self.assertIn("RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN", message)

    def test_check_origin_available_honors_legacy_disable_guard(self) -> None:
        with patch.dict(
            "src.origin.adapter.os.environ",
            {"GROUPMEETINGAUTOPPT_DISABLE_ORIGIN": "1"},
            clear=True,
        ):
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
                        "axis_title_size: 36",
                        "x_tick_label_size: 28",
                        "y_tick_label_size: 36",
                        "legend_font_size: 26",
                        "annotation_font_size: 26",
                        "font_bold: true",
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
                with patch("src.origin.adapter._wait_for_no_origin_process", return_value=True):
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
                with patch("src.origin.adapter._wait_for_no_origin_process", return_value=True):
                    with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                        with patch("src.origin.adapter._export_tif_with_originpro", side_effect=fake_tif_export):
                            result = export_plot(project_root, "fallback_tif", data, "x", "y", "XRD")

            self.assertTrue(result.ok)
            self.assertIsNotNone(result.figure_tif)
            self.assertTrue(result.figure_tif.exists())

    def test_tif_postprocess_normalizes_to_graph4_600_dpi_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "figure.tif"
            from PIL import Image

            Image.new("RGB", (3216, 2461), "white").save(path, format="TIFF", dpi=(300, 300))

            _ensure_tif_600_dpi(path, GRAPH4_FIXED_STYLE)

            with Image.open(path) as image:
                self.assertEqual(image.width, GRAPH4_FIXED_STYLE.page_width)
                self.assertGreaterEqual(image.height, GRAPH4_FIXED_STYLE.page_height - 2)
                self.assertEqual(tuple(round(value) for value in image.info.get("dpi", (0, 0))), (600, 600))

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
                with patch("src.origin.adapter._wait_for_no_origin_process", return_value=True):
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
                with patch("src.origin.adapter._wait_for_no_origin_process", return_value=True):
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
                with patch("src.origin.adapter._wait_for_no_origin_process", return_value=True):
                    with patch("src.origin.adapter._run_origin_job", side_effect=fake_run):
                        with patch("src.origin.adapter._export_tif_with_originpro", side_effect=fake_tif_export):
                            result = export_plot(project_root, "stale_outputs", data, "x", "y", "XRD")

            self.assertTrue(result.ok)
            self.assertEqual(stale_job.origin_file.read_text(encoding="utf-8"), "new opju")
            self.assertEqual(stale_job.figure_tif.read_text(encoding="utf-8"), "new tif")
            self.assertEqual(stale_job.preview_png.read_bytes(), b"new png")


if __name__ == "__main__":
    unittest.main()
