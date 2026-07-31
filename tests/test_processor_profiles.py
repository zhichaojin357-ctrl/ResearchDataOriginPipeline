import unittest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.processors.profiles import SUPPORTED_PROCESSOR_PROFILES
from src.core.project import default_output_root
from src.core.validate import _processor_registry_summary_failures, validate


class ProcessorProfilesTest(unittest.TestCase):
    def test_supported_profiles_cover_exactly_fifteen_pipeline_data_types(self):
        self.assertEqual(len(SUPPORTED_PROCESSOR_PROFILES), 15)

    def test_profiles_match_supported_registry_entries_exactly(self):
        registry = json.loads((ROOT / "config" / "processor_registry.yaml").read_text(encoding="utf-8"))
        supported = {
            entry["inferred_data_type"]: entry["selected_processor"]
            for entry in registry["entries"]
            if entry["supported_in_pipeline"]
        }

        self.assertEqual(set(SUPPORTED_PROCESSOR_PROFILES), set(supported))
        for data_type, profile in SUPPORTED_PROCESSOR_PROFILES.items():
            self.assertEqual(profile["selected_processor"], supported[data_type])

    def test_registry_supported_summary_matches_supported_entries_exactly(self):
        registry = json.loads((ROOT / "config" / "processor_registry.yaml").read_text(encoding="utf-8"))

        self.assertEqual(_processor_registry_summary_failures(registry), [])
        self.assertEqual(registry["pipeline_supported_count"], 15)
        self.assertIn("HPLC/LC OpenLab raw data", registry["pipeline_supported"])

    def test_registry_supported_summary_diagnostics_identify_count_and_list_drift(self):
        registry = {
            "pipeline_supported_count": 1,
            "pipeline_supported": ["XRD", "obsolete"],
            "entries": [
                {"inferred_data_type": "XRD", "supported_in_pipeline": True},
                {"inferred_data_type": "HPLC/LC OpenLab raw data", "supported_in_pipeline": True},
                {"inferred_data_type": "NMR", "supported_in_pipeline": False},
            ],
        }

        failures = _processor_registry_summary_failures(registry)

        self.assertTrue(any("pipeline_supported_count=1" in failure for failure in failures))
        self.assertTrue(
            any(
                "pipeline_supported missing supported entry types: HPLC/LC OpenLab raw data" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any("pipeline_supported contains non-supported types: obsolete" in failure for failure in failures)
        )

    def test_validate_report_explicitly_identifies_supported_summary_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            config = project / "config"
            config.mkdir(parents=True)
            for name in [
                "default.yaml",
                "processor_registry.yaml",
                "claim_policy.yaml",
                "plot_style.yaml",
                "sample_registry.yaml",
                "manual_overrides.yaml",
            ]:
                (config / name).write_text(
                    (ROOT / "config" / name).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            registry_path = config / "processor_registry.yaml"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["pipeline_supported_count"] = 14
            registry["pipeline_supported"].remove("HPLC/LC OpenLab raw data")
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with (
                patch("src.core.validate.dependency_audit", return_value=(0, {})),
                patch(
                    "src.core.validate.check_origin_available",
                    return_value=(False, "RESEARCH_ORIGIN_DISABLE=1"),
                ),
                patch(
                    "src.core.validate.validate_origin_style_asset_integrity",
                    return_value={
                        "ok": True,
                        "schema_version": 2,
                        "asset_count": 0,
                        "warnings": [],
                        "failures": [],
                    },
                ),
            ):
                exit_code = validate(project)

            report = (
                default_output_root(project) / "reports" / "validation_report.md"
            ).read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertIn("- Processor registry supported summary: fail", report)
        self.assertIn(
            "pipeline_supported_count=14 but entries declare 15 supported types",
            report,
        )
        self.assertIn(
            "pipeline_supported missing supported entry types: HPLC/LC OpenLab raw data",
            report,
        )
        self.assertIn("processor registry supported summary drift", report)

    def test_registry_keeps_deferred_and_reference_entries_scan_only(self):
        registry = json.loads((ROOT / "config" / "processor_registry.yaml").read_text(encoding="utf-8"))
        by_folder = {entry["folder_name"]: entry for entry in registry["entries"]}

        for folder in ["SEM", "TEM", "核磁", "质谱"]:
            self.assertFalse(by_folder[folder]["supported_in_pipeline"])
            self.assertEqual(by_folder[folder]["special_handling"], "scan_only")
            self.assertEqual(by_folder[folder]["selected_processor"], "none")

        self.assertFalse(by_folder["动力学"]["supported_in_pipeline"])
        self.assertEqual(by_folder["动力学"]["inferred_data_type"], "reference_literature")
        self.assertEqual(by_folder["动力学"]["special_handling"], "scan_only")
        self.assertEqual(by_folder["动力学"]["selected_processor"], "none")

    def test_no_kinetics_processor_profile_is_supported(self):
        processor_names = {
            profile["selected_processor"]
            for profile in SUPPORTED_PROCESSOR_PROFILES.values()
        }
        profile_names = set(SUPPORTED_PROCESSOR_PROFILES)

        self.assertNotIn("kinetics_processor", processor_names)
        self.assertFalse(
            any("kinetic" in name.lower() for name in profile_names | processor_names)
        )

    def test_chinese_kinetics_folder_is_absent_from_supported_profiles(self):
        self.assertNotIn("动力学", SUPPORTED_PROCESSOR_PROFILES)
        self.assertFalse(
            any("动力学" in profile["data_type"] for profile in SUPPORTED_PROCESSOR_PROFILES.values())
        )

    def test_each_profile_has_planning_metadata(self):
        for data_type, profile in SUPPORTED_PROCESSOR_PROFILES.items():
            with self.subTest(data_type=data_type):
                self.assertEqual(profile["data_type"], data_type)
                self.assertTrue(profile["manual_check_items"])
                self.assertTrue(profile["forbidden_claims"])
                self.assertTrue(profile["plot_type_hints"])


if __name__ == "__main__":
    unittest.main()
