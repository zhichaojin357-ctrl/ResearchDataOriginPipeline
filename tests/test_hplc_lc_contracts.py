from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

from src.core.runtime_paths import create_run_output_layout
from src.processors.base import process_table_dataset
from src.processors.calculations import (
    build_hplc_lc_manual_review_reason,
    build_hplc_lc_plot_intent,
    classify_hplc_lc_exported_table,
    extract_hplc_lc_calibration_candidate,
    extract_hplc_lc_chromatogram_candidate,
    extract_hplc_lc_peak_table_candidate,
)


def _classification() -> dict:
    return {
        "inferred_data_type": "HPLC/LC exported data",
        "selected_processor": "lc_exported_data_processor",
    }


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _processed_rows(project_root: Path, metadata: dict) -> list[dict[str, str]]:
    with (project_root / metadata["processed_data"]).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _forbidden_quantitation_keys(metadata: dict) -> set[str]:
    keys = set(metadata["key_results"])
    return {
        key
        for key in keys
        if any(token in key for token in ("conversion", "selectivity", "yield", "product_identity", "final_concentration"))
    }


def test_chromatogram_export_returns_candidate_without_conversion(tmp_path: Path):
    source = tmp_path / "input" / "synthetic_lc_chromatogram.csv"
    _write_csv(
        source,
        ["retention time min", "intensity mAU"],
        [[0.0, 1.0], [0.5, 5.0], [1.0, 2.0]],
    )

    metadata = process_table_dataset(tmp_path, _classification(), source)

    assert metadata["processing_status"] == "processed_no_origin"
    assert metadata["key_results"]["lc_export_mode"] == "chromatogram"
    assert metadata["key_results"]["lc_plot_intent"] == {
        "candidate": True,
        "plot_type": "chromatogram",
        "x_axis": "retention_time_min",
        "y_axis": "signal",
        "manual_check_required": True,
    }
    assert metadata["plot_type"] == "chromatogram"
    assert metadata["key_results"]["retention_time_range"] == [0.0, 1.0]
    assert not _forbidden_quantitation_keys(metadata)

    rows = _processed_rows(tmp_path, metadata)
    assert set(rows[0]) == {"retention_time_min", "signal"}


def test_hplc_lc_helper_api_classifies_dataframe_and_extracts_chromatogram_candidate():
    import pandas as pd

    frame = pd.DataFrame(
        [
            {"retention time min": 0.0, "absorbance mAU": 1.0},
            {"retention time min": 0.5, "absorbance mAU": 4.0},
        ]
    )

    assert classify_hplc_lc_exported_table(frame) == "chromatogram"
    candidate = extract_hplc_lc_chromatogram_candidate(frame)

    assert candidate == {
        "candidate": True,
        "mode": "chromatogram",
        "point_count": 2,
        "retention_time_range": [0.0, 0.5],
        "x_axis": "retention_time_min",
        "y_axis": "signal",
        "manual_check_required": True,
        "forbidden_claims": [
            "no_peak_identity_assignment",
            "no_product_identity_assignment",
            "no_conversion_selectivity_yield_without_calibration_mapping",
        ],
        "plot_intent": {
            "candidate": True,
            "plot_type": "chromatogram",
            "x_axis": "retention_time_min",
            "y_axis": "signal",
            "manual_check_required": True,
        },
    }


def test_peak_table_export_preserves_candidates_without_product_identity(tmp_path: Path):
    source = tmp_path / "input" / "synthetic_lc_peak_table.csv"
    _write_csv(
        source,
        ["retention time", "area", "height", "peak name"],
        [[1.5, 10.0, 3.0, "P1"], [2.0, 20.0, 7.0, "target?"]],
    )

    metadata = process_table_dataset(tmp_path, _classification(), source)

    assert metadata["key_results"]["lc_export_mode"] == "peak_table"
    assert metadata["key_results"]["lc_plot_intent"]["plot_type"] == "peak_table_summary"
    assert metadata["key_results"]["lc_requires_manual_calibration"] is True
    assert metadata["key_results"]["lc_candidate_peaks"] == [
        {
            "retention_time": 1.5,
            "area": 10.0,
            "height": 3.0,
            "peak_name": "P1",
            "identity_assignment": "unassigned_manual_mapping_required",
        },
        {
            "retention_time": 2.0,
            "area": 20.0,
            "height": 7.0,
            "peak_name": "target?",
            "identity_assignment": "unassigned_manual_mapping_required",
        },
    ]
    assert metadata["key_results"]["peak_area_total_candidate"] == 30.0
    assert "product_identity_candidate" not in metadata["key_results"]
    assert not _forbidden_quantitation_keys(metadata)

    rows = _processed_rows(tmp_path, metadata)
    assert set(rows[0]) == {
        "retention_time_min",
        "signal",
        "peak_area_optional",
        "peak_height_optional",
        "peak_name_optional",
    }
    assert rows[1]["peak_name_optional"] == "target?"


def test_hplc_lc_peak_helper_never_treats_peak_name_or_retention_time_as_identity():
    rows = [
        {"retention time": "2.50", "area": "1200", "height": "60", "peak name": "desired product"},
        {"retention time": "3.10", "area": "300", "height": "20", "peak name": "substrate"},
    ]

    assert classify_hplc_lc_exported_table(rows) == "peak_table"
    candidate = extract_hplc_lc_peak_table_candidate(rows)

    assert candidate["candidate"] is True
    assert candidate["mode"] == "peak_table"
    assert candidate["requires_manual_calibration"] is True
    assert candidate["requires_manual_mapping"] is True
    assert candidate["plot_intent"]["plot_type"] == "peak_table_summary"
    assert "product_identity_candidate" not in candidate
    assert "retention_time_identity_candidate" not in candidate
    assert [peak["identity_assignment"] for peak in candidate["peaks"]] == [
        "unassigned_manual_mapping_required",
        "unassigned_manual_mapping_required",
    ]
    assert [peak["peak_name"] for peak in candidate["peaks"]] == ["desired product", "substrate"]


def test_calibration_table_returns_manual_check_linear_candidate(tmp_path: Path):
    source = tmp_path / "input" / "synthetic_lc_calibration.csv"
    _write_csv(
        source,
        ["analyte", "concentration uM", "peak area"],
        [["standard_A", 0.0, 1.0], ["standard_A", 1.0, 3.0], ["standard_A", 2.0, 5.0]],
    )

    metadata = process_table_dataset(tmp_path, _classification(), source)

    assert metadata["key_results"]["lc_export_mode"] == "calibration_curve"
    assert metadata["key_results"]["lc_plot_intent"]["plot_type"] == "calibration_curve"
    candidate = metadata["key_results"]["lc_calibration_candidate"]
    assert candidate["manual_check_required"] is True
    assert candidate["fit_method"] == "ordinary_least_squares_candidate"
    assert candidate["point_count"] == 3
    assert candidate["analyte"] == "standard_A"
    assert candidate["slope"] == 2.0
    assert candidate["intercept"] == 1.0
    assert candidate["r_squared"] == 1.0
    assert "final_concentration_candidate" not in metadata["key_results"]
    assert not _forbidden_quantitation_keys(metadata)

    rows = _processed_rows(tmp_path, metadata)
    assert set(rows[0]) == {"concentration", "response", "analyte_optional", "manual_check_required"}


def test_hplc_lc_calibration_helper_is_candidate_only_and_manual_check():
    rows = [
        {"manual mapping": "standard_A", "concentration": "0", "response": "1"},
        {"manual mapping": "standard_A", "concentration": "1", "response": "3"},
        {"manual mapping": "standard_A", "concentration": "2", "response": "5"},
    ]

    assert classify_hplc_lc_exported_table(rows) == "calibration_curve"
    candidate = extract_hplc_lc_calibration_candidate(rows)

    assert candidate["candidate"] is True
    assert candidate["mode"] == "calibration_curve"
    assert candidate["manual_check_required"] is True
    assert candidate["requires_manual_mapping"] is True
    assert candidate["fit_method"] == "ordinary_least_squares_candidate"
    assert candidate["slope"] == 2.0
    assert candidate["intercept"] == 1.0
    assert candidate["r_squared"] == 1.0
    assert "final_quantification" not in candidate


def test_peak_table_without_calibration_blocks_conversion_selectivity_yield(tmp_path: Path):
    source = tmp_path / "input" / "synthetic_lc_no_calibration.csv"
    _write_csv(
        source,
        ["retention time", "area", "height", "conversion", "selectivity", "yield", "product"],
        [[1.5, 10.0, 3.0, 80.0, 90.0, 70.0, "target"]],
    )

    metadata = process_table_dataset(tmp_path, _classification(), source)

    assert metadata["key_results"]["lc_export_mode"] == "peak_table"
    assert metadata["key_results"]["lc_requires_manual_calibration"] is True
    assert metadata["key_results"]["lc_quantification_boundary"] == "requires_manual_calibration"
    assert "lc_quantification_blocked_reason" in metadata["key_results"]
    assert "calibration" in metadata["key_results"]["lc_quantification_blocked_reason"].lower()
    assert "calibration" in " ".join(metadata["warnings"]).lower()
    assert not _forbidden_quantitation_keys(metadata) - {
        "lc_quantification_blocked_reason",
        "lc_quantification_boundary",
    }


def test_ambiguous_exported_table_requires_manual_review_without_plot_candidate(tmp_path: Path):
    source = tmp_path / "input" / "synthetic_lc_ambiguous.csv"
    _write_csv(source, ["sample", "value"], [["A", 10.0], ["B", 20.0]])

    metadata = process_table_dataset(tmp_path, _classification(), source)

    assert metadata["processing_status"] == "manual_review"
    assert metadata["plot_type"] == "manual_review"
    assert metadata["key_results"]["lc_export_mode"] == "ambiguous"
    assert metadata["key_results"]["lc_manual_review_required"] is True
    assert metadata["key_results"]["lc_plot_intent"] == {
        "candidate": False,
        "reason": "ambiguous_exported_table",
    }
    assert "time_or_retention_time" in metadata["key_results"]["lc_missing_fields"]
    assert "signal_or_peak_area_or_calibration_response" in metadata["key_results"]["lc_missing_fields"]


def test_hplc_lc_manual_review_and_plot_intent_helpers_for_ambiguous_table():
    rows = [{"sample": "A", "value": "10"}]

    assert classify_hplc_lc_exported_table(rows) == "ambiguous"
    reason = build_hplc_lc_manual_review_reason(rows)
    intent = build_hplc_lc_plot_intent("ambiguous")

    assert reason == {
        "manual_review_required": True,
        "reason": "ambiguous_exported_table",
        "missing_fields": [
            "time_or_retention_time",
            "signal_or_peak_area_or_calibration_response",
        ],
    }
    assert intent == {
        "candidate": False,
        "reason": "ambiguous_exported_table",
    }


def test_hplc_lc_metadata_and_plot_intent_route_into_tmp_run_root(tmp_path: Path):
    source = tmp_path / "input" / "raw_data" / "LC" / "sample.csv"
    _write_csv(source, ["retention time min", "signal"], [[0.0, 1.0], [0.5, 4.0]])
    layout = create_run_output_layout(
        tmp_path,
        scope="hplc_lc_contract",
        command="process",
        mode="no_origin",
        input_paths=[tmp_path / "input" / "raw_data"],
        timestamp="20260604_120000",
        no_origin=True,
        dry_run=False,
    )

    with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
        metadata = process_table_dataset(
            tmp_path,
            _classification(),
            source,
            output_root=layout.root,
        )

    assert metadata["run_output_root"] == "output/runs/20260604_120000_hplc_lc_contract"
    assert metadata["processed_data"].startswith("output/runs/20260604_120000_hplc_lc_contract/processed_data/")
    assert metadata["metadata_path"].startswith("output/runs/20260604_120000_hplc_lc_contract/metadata/")
    assert (layout.root / "metadata").is_dir()
    assert (layout.root / "processed_data").is_dir()
    assert not (tmp_path / "output" / "metadata").exists()
    assert not (tmp_path / "output" / "processed_data").exists()

    metadata_path = tmp_path / metadata["metadata_path"]
    recorded = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert recorded["key_results"]["lc_plot_intent"]["plot_type"] == "chromatogram"
