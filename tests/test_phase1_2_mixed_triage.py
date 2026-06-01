import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.metadata import file_hash
from src.core.process import ProcessOptions, _write_processing_summary, run_process
from src.core.triage import TriageOptions, run_triage


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


def write_xrd(path: Path, rows: int = 60) -> None:
    lines = ["2theta,intensity"]
    for index in range(rows):
        lines.append(f"{10 + index},{100 + index}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_hplc_like(path: Path, rows: int = 5) -> None:
    lines = ["Retention Time,Area,mAU"]
    for index in range(rows):
        lines.append(f"{index + 1},{100 + index * 10},{20 + index}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Phase12MixedTriageTest(unittest.TestCase):
    def test_triage_creates_queue_reports_and_never_modifies_raw_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data"
            xrd = raw / "XRD"
            kinetics = raw / "动力学"
            sem = raw / "SEM"
            misc = raw / "misc"
            for folder in (xrd, kinetics, sem, misc):
                folder.mkdir(parents=True)
            good = xrd / "synthetic_xrd.csv"
            write_xrd(good)
            duplicate = xrd / "synthetic_xrd_copy.csv"
            shutil.copyfile(good, duplicate)
            empty = xrd / "empty.csv"
            empty.write_text("", encoding="utf-8")
            image = xrd / "plot.png"
            image.write_bytes(b"\x89PNG\r\n")
            reference = kinetics / "reference.pdf"
            reference.write_bytes(b"%PDF-1.4")
            deferred = sem / "sem_image.tif"
            deferred.write_bytes(b"II*\x00")
            unknown = misc / "notes.txt"
            unknown.write_text("this is a note, not a numeric table", encoding="utf-8")
            before = {path: path.read_bytes() for path in raw.rglob("*") if path.is_file()}

            result = run_triage(project, raw, TriageOptions(explain=True, min_confidence=0.75))

            after = {path: path.read_bytes() for path in raw.rglob("*") if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(result["summary"]["total_files"], 7)
            manifest = json.loads((project / "output" / "reports" / "data_triage_manifest.json").read_text(encoding="utf-8"))
            decisions = {Path(item["relative_path"]).name: item["decision"] for item in manifest["items"]}
            self.assertEqual(decisions["synthetic_xrd.csv"], "AUTO_PROCESS")
            self.assertEqual(decisions["synthetic_xrd_copy.csv"], "DUPLICATE_SUPPRESSED")
            self.assertEqual(decisions["empty.csv"], "EXCLUDE_INVALID")
            self.assertIn(decisions["plot.png"], {"AUXILIARY_ONLY", "EXCLUDE_INVALID"})
            self.assertEqual(decisions["reference.pdf"], "REFERENCE_ONLY")
            self.assertEqual(decisions["sem_image.tif"], "DEFERRED_TYPE")
            self.assertIn(decisions["notes.txt"], {"AUXILIARY_ONLY", "EXCLUDE_INVALID", "MANUAL_REVIEW"})

            queue = json.loads((project / "output" / "reports" / "processing_queue.json").read_text(encoding="utf-8"))
            self.assertEqual(len(queue["items"]), 1)
            self.assertEqual(queue["items"][0]["decision"], "AUTO_PROCESS")
            self.assertTrue((project / "output" / "reports" / "ambiguous_files.md").exists())
            self.assertTrue((project / "output" / "reports" / "excluded_files.md").exists())
            self.assertTrue((project / "output" / "reports" / "duplicate_candidates.md").exists())
            self.assertTrue((project / "output" / "reports" / "source_hash_index.json").exists())
            self.assertTrue((project / "output" / "reports" / "traceability_groups.json").exists())
            self.assertTrue((project / "output" / "reports" / "traceability_groups.md").exists())
            self.assertTrue((project / "output" / "review_dashboard" / "triage_index.md").exists())

    def test_scan_only_subfolders_inside_mixed_reaction_folder_override_header_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            mixed = project / "input" / "raw_data" / "13_反应产物分析_液相_质谱_核磁"
            ms = mixed / "质谱"
            nmr = mixed / "核磁"
            lc = mixed / "液相"
            for folder in (ms, nmr, lc):
                folder.mkdir(parents=True)
            write_hplc_like(ms / "ms_export.csv")
            write_hplc_like(nmr / "nmr_export.csv")
            write_hplc_like(lc / "lc_export.csv")

            result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True, min_confidence=0.75))

            by_name = {Path(item["relative_path"]).name: item for item in result["items"]}
            self.assertEqual(by_name["ms_export.csv"]["folder_type_hint"], "MS")
            self.assertEqual(by_name["ms_export.csv"]["header_type_hint"], "HPLC/LC exported data")
            self.assertEqual(by_name["ms_export.csv"]["data_type_candidate"], "MS")
            self.assertEqual(by_name["ms_export.csv"]["decision"], "DEFERRED_TYPE")
            self.assertEqual(by_name["nmr_export.csv"]["folder_type_hint"], "NMR")
            self.assertEqual(by_name["nmr_export.csv"]["header_type_hint"], "HPLC/LC exported data")
            self.assertEqual(by_name["nmr_export.csv"]["data_type_candidate"], "NMR")
            self.assertEqual(by_name["nmr_export.csv"]["decision"], "DEFERRED_TYPE")
            self.assertEqual(by_name["lc_export.csv"]["data_type_candidate"], "HPLC/LC exported data")

    def test_origin_project_files_stay_grouped_with_same_folder_data_but_out_of_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "01_XRD" / "sample_group"
            origin_project = raw / "origin_project"
            origin_project.mkdir(parents=True)
            write_xrd(raw / "sample.csv")
            (origin_project / "sample_reference.opju").write_bytes(b"origin project")

            result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True, min_confidence=0.75))

            by_name = {Path(item["relative_path"]).name: item for item in result["items"]}
            self.assertEqual(by_name["sample_reference.opju"]["folder_type_hint"], "XRD")
            self.assertEqual(by_name["sample_reference.opju"]["data_type_candidate"], "XRD")
            self.assertEqual(by_name["sample_reference.opju"]["decision"], "AUXILIARY_ONLY")
            self.assertEqual(by_name["sample_reference.opju"]["traceability_role"], "origin_project_reference")
            self.assertEqual(by_name["sample.csv"]["traceability_role"], "raw_or_exported_numeric_table")
            self.assertEqual(by_name["sample_reference.opju"]["traceability_group_id"], by_name["sample.csv"]["traceability_group_id"])
            self.assertEqual(by_name["sample_reference.opju"]["traceability_group_path"], "01_XRD/sample_group")
            self.assertIn(
                "origin_project_file_grouped_with_same_folder_data",
                by_name["sample_reference.opju"]["decision_reasons"],
            )
            self.assertEqual([item["relative_path"] for item in result["queue"]["items"]], ["01_XRD/sample_group/sample.csv"])
            self.assertEqual(result["queue"]["items"][0]["traceability_group_id"], by_name["sample.csv"]["traceability_group_id"])
            traceability_groups = json.loads((project / "output" / "reports" / "traceability_groups.json").read_text(encoding="utf-8"))
            groups = {group["traceability_group_path"]: group for group in traceability_groups["groups"]}
            self.assertIn("01_XRD/sample_group", groups)
            self.assertEqual(groups["01_XRD/sample_group"]["origin_project_files"], ["01_XRD/sample_group/origin_project/sample_reference.opju"])
            self.assertEqual(groups["01_XRD/sample_group"]["queued_files"], ["01_XRD/sample_group/sample.csv"])

    def test_process_from_queue_no_origin_processes_only_auto_process_and_records_triage_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            write_xrd(raw / "synthetic_xrd.csv")
            (raw / "manual_short.csv").write_text("2theta,intensity\n10,1\n", encoding="utf-8")
            run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))

            with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
                code = run_process(
                    project,
                    project / "input" / "raw_data",
                    ProcessOptions(
                        no_origin=True,
                        from_queue=project / "output" / "reports" / "processing_queue.json",
                        force=True,
                    ),
                )

            self.assertEqual(code, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 1)
            metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(metadata["triage"]["triage_decision"], "AUTO_PROCESS")
            self.assertGreaterEqual(metadata["triage"]["confidence_score"], 0.75)
            self.assertIn("queue_id", metadata["triage"])
            self.assertEqual(metadata["processing_status"], "processed_no_origin")
            dashboard = (project / "output" / "review_dashboard" / "index.md").read_text(encoding="utf-8")
            self.assertIn("Triage Summary", dashboard)
            self.assertIn("Queue items", dashboard)

    def test_process_from_queue_defaults_to_no_origin_even_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            write_xrd(raw / "synthetic_xrd.csv")
            run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))

            with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run for queue processing by default")):
                code = run_process(
                    project,
                    project / "input" / "raw_data",
                    ProcessOptions(
                        from_queue=project / "output" / "reports" / "processing_queue.json",
                        force=True,
                    ),
                )

            self.assertEqual(code, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 1)
            metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(metadata["processing_status"], "processed_no_origin")
            summary = json.loads((project / "output" / "reports" / "processing_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["missing_artifacts"], [])

    def test_manual_review_promotion_queue_records_audit_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_root = project / "input" / "raw_data"
            raw = raw_root / "XRD"
            raw.mkdir(parents=True)
            source = raw / "manual_short.csv"
            write_xrd(source, rows=3)
            queue_path = project / "output" / "reports" / "promoted_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue = {
                "items": [
                    {
                        "queue_id": "promote_xrd_manual_0001",
                        "relative_path": "XRD/manual_short.csv",
                        "absolute_path": str(source),
                        "source_hash": file_hash(source),
                        "data_type": "XRD",
                        "selected_processor": "xrd_processor",
                        "decision": "MANUAL_REVIEW",
                        "confidence_score": 0.6,
                        "validity_score": 0.8,
                        "reasons": ["safe manual promotion test"],
                        "evidence": [],
                        "original_triage_decision": "MANUAL_REVIEW",
                        "promoted_from_manual_review": True,
                        "promoted_by_phase": "phase1_5",
                        "promoted_batch": "A",
                        "promoted_confidence": 0.6,
                        "promoted_validity": 0.8,
                        "promotion_reason": "parser success and isolated no-Origin processing",
                        "promotion_rule": "test_rule",
                        "traceability_group_id": "group-1",
                        "traceability_group_path": "XRD",
                        "traceability_role": "raw_data",
                        "traceability_basis": ["role_folder=raw_data"],
                    }
                ]
            }
            queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

            code = run_process(
                project,
                raw_root,
                ProcessOptions(
                    no_origin=True,
                    include_ambiguous=True,
                    from_queue=queue_path,
                    force=True,
                ),
            )

            self.assertEqual(code, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 1)
            triage = json.loads(metadata_files[0].read_text(encoding="utf-8"))["triage"]
            self.assertEqual(triage["triage_decision"], "MANUAL_REVIEW")
            self.assertTrue(triage["promoted_from_manual_review"])
            self.assertEqual(triage["original_triage_decision"], "MANUAL_REVIEW")
            self.assertEqual(triage["promoted_by_phase"], "phase1_5")
            self.assertEqual(triage["promoted_batch"], "A")
            self.assertEqual(triage["promotion_rule"], "test_rule")
            self.assertEqual(triage["traceability_group_path"], "XRD")

    def test_include_ambiguous_requires_manual_review_promotion_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_root = project / "input" / "raw_data"
            raw = raw_root / "XRD"
            raw.mkdir(parents=True)
            source = raw / "manual_unreviewed.csv"
            write_xrd(source, rows=3)
            queue_path = project / "output" / "reports" / "unreviewed_manual_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "queue_id": "manual_unreviewed_001",
                                "relative_path": "XRD/manual_unreviewed.csv",
                                "source_hash": file_hash(source),
                                "data_type": "XRD",
                                "selected_processor": "xrd_processor",
                                "decision": "MANUAL_REVIEW",
                                "confidence_score": 0.6,
                                "validity_score": 0.8,
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            code = run_process(
                project,
                raw_root,
                ProcessOptions(no_origin=True, include_ambiguous=True, from_queue=queue_path, force=True),
            )

            self.assertEqual(code, 2)
            self.assertEqual(list((project / "output" / "metadata").rglob("metadata.json")), [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("manual review queue item requires promotion provenance", failures["failures"][0]["error_message"])

    def test_processing_summary_reports_missing_no_origin_artifact_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            metadata = {
                "dataset_id": "EIS_missing_artifacts",
                "data_type": "EIS",
                "processing_status": "processed_no_origin",
                "source_files": [str(project / "input" / "raw_data" / "EIS" / "missing.txt")],
                "processed_data": str(project / "output" / "processed_data" / "EIS" / "missing.csv"),
                "metadata_path": str(project / "output" / "metadata" / "EIS" / "missing" / "metadata.json"),
                "manual_check_required": False,
                "forbidden_claims": [],
            }
            manifest = {"classifications": []}

            _write_processing_summary(project, manifest, [metadata], [])

            summary = json.loads((project / "output" / "reports" / "processing_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                summary["missing_artifacts"],
                [
                    {
                        "dataset_id": "EIS_missing_artifacts",
                        "missing": ["processed_data", "metadata_path"],
                    }
                ],
            )

    def test_queue_processing_keeps_same_stem_files_from_overwriting_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            first = project / "input" / "raw_data" / "XRD" / "sample_a"
            second = project / "input" / "raw_data" / "XRD" / "sample_b"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            write_xrd(first / "same_name.csv", rows=60)
            write_xrd(second / "same_name.csv", rows=70)
            run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(
                    no_origin=True,
                    from_queue=project / "output" / "reports" / "processing_queue.json",
                    force=True,
                ),
            )

            self.assertEqual(code, 0)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(len(metadata_files), 2)
            processed_paths = {
                json.loads(path.read_text(encoding="utf-8"))["processed_data"]
                for path in metadata_files
            }
            self.assertEqual(len(processed_paths), 2)

    def test_process_from_queue_reports_stale_hash_without_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            source = raw / "synthetic_xrd.csv"
            write_xrd(source)
            run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))
            source.write_text("2theta,intensity\n1,1\n", encoding="utf-8")

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(
                    no_origin=True,
                    from_queue=project / "output" / "reports" / "processing_queue.json",
                    force=True,
                ),
            )

            self.assertEqual(code, 2)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(metadata_files, [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(len(failures["failures"]), 1)
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertEqual(failures["failures"][0]["triage_decision"], "AUTO_PROCESS")
            self.assertTrue(failures["failures"][0]["whether_retry_with_manual_override_is_possible"])

    def test_process_blocks_raw_queue_when_phase1_6_processed_hashes_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            source = raw / "synthetic_xrd.csv"
            write_xrd(source)
            run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))
            phase1_6 = project / "output" / "phase1_6_origin_results_20260531_041538"
            phase1_6.mkdir(parents=True)
            (phase1_6 / "index.csv").write_text(f"source_hash\n{file_hash(source)}\n", encoding="utf-8")

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(
                    no_origin=True,
                    from_queue=project / "output" / "reports" / "processing_queue.json",
                    force=True,
                ),
            )

            self.assertEqual(code, 2)
            self.assertEqual(list((project / "output" / "metadata").rglob("metadata.json")), [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("phase1_8_new_auto_process_queue.json", failures["failures"][0]["error_message"])

    def test_auto_select_blocks_phase1_6_processed_hashes_from_raw_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            source = raw / "synthetic_xrd.csv"
            write_xrd(source)
            phase1_6 = project / "output" / "phase1_6_origin_results_20260531_041538"
            phase1_6.mkdir(parents=True)
            (phase1_6 / "index.csv").write_text(f"source_hash\n{file_hash(source)}\n", encoding="utf-8")

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(no_origin=True, auto_select=True, force=True),
            )

            self.assertEqual(code, 2)
            self.assertEqual(list((project / "output" / "metadata").rglob("metadata.json")), [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("phase1_8_new_auto_process_queue.json", failures["failures"][0]["error_message"])

    def test_process_from_queue_reports_missing_source_hash_without_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            write_xrd(raw / "synthetic_xrd.csv")
            run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))
            queue_path = project / "output" / "reports" / "processing_queue.json"
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            queue["items"][0].pop("source_hash")
            queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(
                    no_origin=True,
                    from_queue=queue_path,
                    force=True,
                ),
            )

            self.assertEqual(code, 2)
            metadata_files = list((project / "output" / "metadata").rglob("metadata.json"))
            self.assertEqual(metadata_files, [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("source hash missing", failures["failures"][0]["error_message"])

    def test_process_from_queue_blocks_unknown_registry_data_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "Unknown"
            raw.mkdir(parents=True)
            source = raw / "synthetic_unknown.csv"
            source.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
            queue_path = project / "output" / "reports" / "unknown_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "queue_id": "unknown_001",
                                "relative_path": "Unknown/synthetic_unknown.csv",
                                "source_hash": file_hash(source),
                                "data_type": "unknown_numeric_type",
                                "selected_processor": "unknown_processor",
                                "decision": "AUTO_PROCESS",
                                "confidence_score": 1.0,
                                "validity_score": 1.0,
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            code = run_process(project, project / "input" / "raw_data", ProcessOptions(no_origin=True, from_queue=queue_path, force=True))

            self.assertEqual(code, 2)
            self.assertEqual(list((project / "output" / "metadata").rglob("metadata.json")), [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("not in processor registry", failures["failures"][0]["error_message"])

    def test_process_from_queue_rejects_absolute_path_outside_input_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_root = project / "input" / "raw_data"
            raw_root.mkdir(parents=True)
            outside = project / "outside.csv"
            write_xrd(outside)
            queue_path = project / "output" / "reports" / "unsafe_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "queue_id": "unsafe_absolute",
                                "relative_path": "XRD/synthetic_xrd.csv",
                                "absolute_path": str(outside),
                                "source_hash": file_hash(outside),
                                "data_type": "XRD",
                                "selected_processor": "xrd_processor",
                                "decision": "AUTO_PROCESS",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            code = run_process(project, raw_root, ProcessOptions(no_origin=True, from_queue=queue_path, force=True))

            self.assertEqual(code, 2)
            self.assertEqual(list((project / "output" / "metadata").rglob("metadata.json")), [])
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("outside input root", failures["failures"][0]["error_message"])

    def test_process_from_queue_rejects_relative_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_root = project / "input" / "raw_data"
            raw_root.mkdir(parents=True)
            outside = project / "input" / "outside.csv"
            write_xrd(outside)
            queue_path = project / "output" / "reports" / "unsafe_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "queue_id": "unsafe_relative",
                                "relative_path": "../outside.csv",
                                "source_hash": file_hash(outside),
                                "data_type": "XRD",
                                "selected_processor": "xrd_processor",
                                "decision": "AUTO_PROCESS",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            code = run_process(project, raw_root, ProcessOptions(no_origin=True, from_queue=queue_path, force=True))

            self.assertEqual(code, 2)
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("outside input root", failures["failures"][0]["error_message"])

    def test_process_from_queue_with_origin_requires_explicit_origin_export_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw_root = project / "input" / "raw_data" / "XRD"
            raw_root.mkdir(parents=True)
            source = raw_root / "synthetic_xrd.csv"
            write_xrd(source)
            queue_path = project / "output" / "reports" / "origin_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "queue_id": "origin_without_allow",
                                "relative_path": "XRD/synthetic_xrd.csv",
                                "absolute_path": str(source),
                                "source_hash": file_hash(source),
                                "data_type": "XRD",
                                "selected_processor": "xrd_processor",
                                "decision": "AUTO_PROCESS",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run without origin_export_allowed")):
                code = run_process(project, project / "input" / "raw_data", ProcessOptions(with_origin=True, from_queue=queue_path, force=True))

            self.assertEqual(code, 2)
            failures = json.loads((project / "output" / "reports" / "processing_failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures["failures"][0]["failure_stage"], "queue_validation")
            self.assertIn("origin_export_allowed", failures["failures"][0]["error_message"])

    def test_exact_duplicate_suppression_also_handles_manual_review_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "mixed"
            raw.mkdir(parents=True)
            manual_a = raw / "manual_a.csv"
            manual_b = raw / "manual_b.csv"
            lines = ["binding energy,intensity"]
            for index in range(60):
                lines.append(f"{280 + index * 0.1},{1000 + index}")
            manual_a.write_text("\n".join(lines) + "\n", encoding="utf-8")
            shutil.copyfile(manual_a, manual_b)

            result = run_triage(project, project / "input" / "raw_data", TriageOptions(min_confidence=0.75))

            decisions = {Path(item["relative_path"]).name: item["decision"] for item in result["items"]}
            self.assertEqual(list(decisions.values()).count("DUPLICATE_SUPPRESSED"), 1)
            self.assertEqual(list(decisions.values()).count("MANUAL_REVIEW"), 1)
            duplicates = json.loads((project / "output" / "reports" / "duplicate_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(len(duplicates["items"]), 1)
            self.assertTrue(duplicates["items"][0]["suppressed_by"])

    def test_cli_triage_and_process_from_queue_flags_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            raw = project / "input" / "raw_data" / "XRD"
            raw.mkdir(parents=True)
            write_xrd(raw / "synthetic_xrd.csv")
            config = project / "config"
            config.mkdir()
            (config / "default.yaml").write_text("paths:\n  raw_data: input/raw_data\n", encoding="utf-8")

            triage = run_cli("triage", "--input", str(project / "input" / "raw_data"), "--config", str(config / "default.yaml"), "--explain", cwd=project)
            self.assertEqual(triage.returncode, 0, triage.stderr)
            process = run_cli(
                "process",
                "--input",
                str(project / "input" / "raw_data"),
                "--config",
                str(config / "default.yaml"),
                "--from-queue",
                str(project / "output" / "reports" / "processing_queue.json"),
                "--no-origin",
                "--force",
                cwd=project,
            )
            self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
