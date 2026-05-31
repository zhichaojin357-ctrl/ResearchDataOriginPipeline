import unittest
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.processors.profiles import SUPPORTED_PROCESSOR_PROFILES


class ProcessorProfilesTest(unittest.TestCase):
    def test_supported_profiles_cover_exactly_fourteen_phase1_data_types(self):
        self.assertEqual(len(SUPPORTED_PROCESSOR_PROFILES), 14)

    def test_profiles_match_supported_registry_entries_exactly(self):
        registry = json.loads((ROOT / "config" / "processor_registry.yaml").read_text(encoding="utf-8"))
        supported = {
            entry["inferred_data_type"]: entry["selected_processor"]
            for entry in registry["entries"]
            if entry["supported_in_phase_1"]
        }

        self.assertEqual(set(SUPPORTED_PROCESSOR_PROFILES), set(supported))
        for data_type, profile in SUPPORTED_PROCESSOR_PROFILES.items():
            self.assertEqual(profile["selected_processor"], supported[data_type])

    def test_registry_keeps_deferred_and_reference_entries_scan_only(self):
        registry = json.loads((ROOT / "config" / "processor_registry.yaml").read_text(encoding="utf-8"))
        by_folder = {entry["folder_name"]: entry for entry in registry["entries"]}

        for folder in ["SEM", "TEM", "核磁", "质谱"]:
            self.assertFalse(by_folder[folder]["supported_in_phase_1"])
            self.assertEqual(by_folder[folder]["special_handling"], "scan_only")
            self.assertEqual(by_folder[folder]["selected_processor"], "none")

        self.assertFalse(by_folder["动力学"]["supported_in_phase_1"])
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
