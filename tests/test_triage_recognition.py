from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from src.core.process import ProcessOptions, run_process
from src.core.triage import TriageOptions, run_triage
from src.core.project import default_output_root


def test_unnamed_excel_numeric_fallback_can_be_high_confidence_without_origin():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "XPS"
        raw.mkdir(parents=True)
        _write_unnamed_excel(raw / "xps_numeric.xlsx", rows=80)

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["data_type_candidate"] == "XPS"
        assert item["decision"] == "AUTO_PROCESS"
        assert "unnamed_columns_with_numeric_data" in item["recognition_fallbacks"]
        assert any("do not automatically assign XPS" in claim for claim in _forbidden_claims_for(project, item))


def test_multisheet_auto_scoring_keeps_conflicted_high_risk_file_manual_review():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "PL"
        raw.mkdir(parents=True)
        path = raw / "conflicted_xps.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "notes"
        ws.append(["label", "value"])
        ws.append(["not_data", "x"])
        data = wb.create_sheet("numeric_xps")
        data.append(["Binding Energy (eV)", "Intensity (cps)"])
        for index in range(40):
            data.append([280 + index * 0.1, 1000 - index])
        wb.save(path)

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["folder_type_hint"] == "PL"
        assert item["header_type_hint"] == "XPS"
        assert item["sheet_name"] == "numeric_xps"
        assert item["header_row_index"] == 0
        assert item["decision"] == "MANUAL_REVIEW"
        assert item["folder_header_conflict_level"] in {"mild", "severe"}


def test_chinese_and_unit_headers_are_recognized():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data"
        uv = raw / "UV-vis DRS"
        ms = raw / "Mott-Schottky"
        uv.mkdir(parents=True)
        ms.mkdir(parents=True)
        (uv / "uv.csv").write_text("波长 (nm),吸光度 (a.u.)\n400,0.2\n500,0.5\n600,0.7\n", encoding="utf-8")
        (ms / "ms.csv").write_text("Potential/V,1/C^2\n-0.2,1.0\n-0.1,1.3\n0.0,1.6\n0.1,1.9\n", encoding="utf-8")

        result = run_triage(project, raw, TriageOptions(explain=True))
        by_name = {Path(item["relative_path"]).name: item for item in result["items"]}

        assert by_name["uv.csv"]["header_type_hint"] == "UV-vis DRS"
        assert by_name["ms.csv"]["header_type_hint"] == "Mott-Schottky"
        assert by_name["ms.csv"]["data_type_candidate"] == "Mott-Schottky"


def test_chi_impedance_potential_export_in_mott_folder_is_mott_schottky_not_eis():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "Mott-Schottky"
        raw.mkdir(parents=True)
        rows = "\n".join(
            [
                "Nov. 26, 2025   21:24:18",
                "Impedance - Potential",
                "Instrument Model:  CHI660E",
                "",
                "Frequency (Hz) = 1000",
                "",
                "Potential/V, Z'/ohm, Z\"/ohm, Z/ohm, Phase/deg",
                "",
                "1.700e-1, 3.754e+1, 4.904e+1, 6.176e+1, 52.6",
                "2.200e-1, 3.743e+1, 4.885e+1, 6.154e+1, 52.5",
                "2.700e-1, 3.746e+1, 4.877e+1, 6.150e+1, 52.5",
            ]
        )
        (raw / "chi_mott.csv").write_text(rows, encoding="utf-8")

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["header_type_hint"] == "Mott-Schottky"
        assert item["data_type_candidate"] == "Mott-Schottky"
        assert item["decision"] == "AUTO_PROCESS"
        assert item["folder_header_conflict_level"] == "none"
        assert item["parser_probe_status"] == "success"


def test_raman_unit_headers_do_not_get_first_match_ft_ir():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "Raman"
        raw.mkdir(parents=True)
        rows = "\n".join(f"{100 + index * 10},{index + 1}" for index in range(30))
        (raw / "raman.csv").write_text("Raman Shift (cm-1),Intensity\n" + rows + "\n", encoding="utf-8")

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["header_type_hint"] == "Raman"
        assert item["data_type_candidate"] == "Raman"
        assert item["decision"] == "AUTO_PROCESS"


def test_headerless_numeric_fallback_does_not_override_severe_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "SEM"
        raw.mkdir(parents=True)
        (raw / "numeric.txt").write_text("1 2\n2 3\n3 4\n4 5\n", encoding="utf-8")

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["decision"] == "DEFERRED_TYPE"
        assert item["data_type_candidate"] == "SEM_image_data"


def test_mild_folder_header_conflict_is_candidate_only_not_auto_processed():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "XRD"
        raw.mkdir(parents=True)
        (raw / "raman_like.csv").write_text("Raman Shift (cm-1),Intensity\n100,1\n200,3\n300,2\n", encoding="utf-8")

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["header_type_hint"] == "Raman"
        assert item["decision"] == "MANUAL_REVIEW"
        assert "folder_header_type_conflict" in " ".join(item["decision_reasons"])


def test_folder_only_unknown_header_numeric_table_stays_manual_review():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "XRD"
        raw.mkdir(parents=True)
        rows = "\n".join(f"{index},{index * 2}" for index in range(1, 80))
        (raw / "ambiguous_sample_headers.csv").write_text("Sample,LL-1\n" + rows + "\n", encoding="utf-8")

        result = run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))
        item = result["items"][0]

        assert item["folder_type_hint"] == "XRD"
        assert item["header_type_hint"] is None
        assert item["decision"] == "MANUAL_REVIEW"
        assert item["confidence_score"] < 0.75


def test_manual_review_is_not_processed_by_default_even_after_recognition_improvement():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        raw = project / "input" / "raw_data" / "XRD"
        raw.mkdir(parents=True)
        (raw / "raman_like.csv").write_text("Raman Shift (cm-1),Intensity\n100,1\n200,3\n300,2\n", encoding="utf-8")
        run_triage(project, project / "input" / "raw_data", TriageOptions(explain=True))

        with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
            code = run_process(
                project,
                project / "input" / "raw_data",
                ProcessOptions(from_queue=default_output_root(project) / "reports" / "processing_queue.json", force=True),
            )

        queue = json.loads((default_output_root(project) / "reports" / "processing_queue.json").read_text(encoding="utf-8"))
        assert queue["items"] == []
        assert queue["policy_version"] == "triage_policy_v2"
        assert len(queue["config_hash"]) == 64
        int(queue["config_hash"], 16)
        assert code == 0


def test_photocurrent_response_folder_is_compatible_with_generic_time_current_headers(tmp_path: Path):
    raw = tmp_path / "input" / "raw_data" / "光电流响应"
    raw.mkdir(parents=True)
    rows = "\n".join(f"{index},{index * 1e-6}" for index in range(20))
    (raw / "response.txt").write_text("Time/sec,Current/A\n" + rows + "\n", encoding="utf-8")

    result = run_triage(tmp_path, tmp_path / "input" / "raw_data", TriageOptions(explain=True))
    item = result["items"][0]

    assert item["folder_type_hint"] == "photocurrent_response"
    assert item["header_type_hint"] == "photocurrent"
    assert item["data_type_candidate"] == "photocurrent_response"
    assert item["folder_type_conflict"] is False
    assert item["decision"] == "AUTO_PROCESS"


def test_reaction_condition_table_accepts_categorical_condition_and_numeric_response(tmp_path: Path):
    raw = tmp_path / "input" / "raw_data" / "光反应的条件筛选"
    raw.mkdir(parents=True)
    (raw / "screening.csv").write_text(
        "condition,yield\nSolvent A,42.1\nSolvent B,57.8\nSolvent C,51.4\n",
        encoding="utf-8",
    )

    result = run_triage(tmp_path, tmp_path / "input" / "raw_data", TriageOptions(explain=True))
    item = result["items"][0]

    assert item["header_type_hint"] == "reaction_condition_screening"
    assert item["data_type_candidate"] == "reaction_condition_screening"
    assert item["numeric_shape_hint"]["numeric_columns"] == 1
    assert item["processable_row_count"] == 3
    assert item["column_role_candidates"] == {"x": ["condition"], "y": ["yield"]}
    assert item["decision"] == "AUTO_PROCESS"


def test_reaction_condition_table_accepts_generic_value_response(tmp_path: Path):
    raw = tmp_path / "input" / "raw_data" / "condition screening"
    raw.mkdir(parents=True)
    (raw / "screening.csv").write_text(
        "condition,value\nSolvent A,42.1\nSolvent B,57.8\nSolvent C,51.4\n",
        encoding="utf-8",
    )

    result = run_triage(tmp_path, tmp_path / "input" / "raw_data", TriageOptions(explain=True))
    item = result["items"][0]

    assert item["data_type_candidate"] == "reaction_condition_screening"
    assert item["numeric_shape_hint"]["numeric_columns"] == 1
    assert item["processable_row_count"] == 3
    assert item["column_role_candidates"] == {"x": ["condition"], "y": ["value"]}
    assert item["decision"] == "AUTO_PROCESS"


def test_reaction_condition_requires_separate_condition_and_response_columns(tmp_path: Path):
    raw = tmp_path / "input" / "raw_data" / "condition screening"
    raw.mkdir(parents=True)
    (raw / "screening.csv").write_text("condition_value\n1\n2\n3\n", encoding="utf-8")

    result = run_triage(tmp_path, tmp_path / "input" / "raw_data", TriageOptions(explain=True))
    item = result["items"][0]

    assert item["data_type_candidate"] == "reaction_condition_screening"
    assert item["decision"] == "EXCLUDE_INVALID"
    assert "insufficient_numeric_table" in item["decision_reasons"]


def test_generic_label_value_table_is_not_misclassified_as_reaction_screening(tmp_path: Path):
    raw = tmp_path / "input" / "raw_data" / "misc"
    raw.mkdir(parents=True)
    (raw / "data.csv").write_text("label,value\nA,1\nB,2\nC,3\n", encoding="utf-8")

    result = run_triage(tmp_path, tmp_path / "input" / "raw_data", TriageOptions(explain=True))
    item = result["items"][0]

    assert item["data_type_candidate"] != "reaction_condition_screening"


def _write_unnamed_excel(path: Path, rows: int) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append([None, None])
    for index in range(rows):
        ws.append([280 + index * 0.1, 1000 - index])
    wb.save(path)


def _forbidden_claims_for(project: Path, item: dict) -> list[str]:
    # The claim guard lives in metadata; this lightweight test ensures the policy file remains available.
    policy = Path(__file__).resolve().parents[1] / "config" / "claim_policy.yaml"
    text = policy.read_text(encoding="utf-8")
    return [line.strip().strip('"').strip(",") for line in text.splitlines() if "assign XPS" in line]
