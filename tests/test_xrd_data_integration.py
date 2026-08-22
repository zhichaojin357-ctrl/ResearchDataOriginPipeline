from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.xrd_jade import XrdPhaseMatchOptions
from src.processors.base import process_table_dataset
from src.processors.calculations import local_peak_positions


def _classification() -> dict[str, object]:
    return {
        "inferred_data_type": "XRD",
        "selected_processor": "xrd_processor",
    }


def _write_xrd(source: Path) -> list[tuple[float, float]]:
    points = [
        (10.0, 0.0),
        (11.0, 10.0),
        (12.0, 0.0),
        (13.0, 0.0),
        (14.0, 0.01),
        (15.0, 0.0),
    ]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["two theta", "intensity"])
        writer.writerows(points)
    return points


def test_plain_xrd_preserves_legacy_candidate_peak_output(tmp_path: Path) -> None:
    source = tmp_path / "plain.csv"
    points = _write_xrd(source)

    output_root = tmp_path / "output"
    metadata = process_table_dataset(tmp_path, _classification(), source, output_root=output_root)

    assert metadata["key_results"]["peak_position_candidates"] == local_peak_positions(points)
    assert "peak_detection" not in metadata["key_results"]
    provenance = metadata["parameters"]["algorithm_provenance"]
    assert provenance["candidate_methods"] == ["local_neighbor_peak_candidates"]
    with (output_root / "processed_data" / "XRD" / "plain_processed.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert [float(row["two_theta_deg"]) for row in rows if row["peak_candidate_flag"] == "1"] == local_peak_positions(points)


def test_phase_screening_records_actual_parameterized_peak_detector(tmp_path: Path) -> None:
    source = tmp_path / "phase.csv"
    _write_xrd(source)
    options = XrdPhaseMatchOptions(database_dir=tmp_path / "jade", card_ids=("97-000-0001",))
    phase_result = {
        "status": "selected_cards_screened_candidates_manual_review_required",
        "candidate_count": 0,
        "database": {"format": "test"},
        "peak_detection": {"method": "test matcher result"},
        "parameters": {},
        "warnings": [],
        "matches": [],
        "manual_check_items": [],
        "forbidden_claims": [],
    }

    with patch("src.core.xrd_jade.match_xrd_phases", return_value=phase_result):
        metadata = process_table_dataset(
            tmp_path,
            _classification(),
            source,
            output_root=tmp_path / "output",
            xrd_phase_options=options,
        )

    detection = metadata["key_results"]["peak_detection"]
    provenance = metadata["parameters"]["algorithm_provenance"]
    assert provenance["xrd_peak_detection"] == detection
    if detection["method"] == "scipy.signal.find_peaks":
        assert "scipy_prominence_distance_peak_candidates" in provenance["candidate_methods"]
    else:
        assert "local_neighbor_peak_candidates" not in provenance["candidate_methods"]
        assert any(item.startswith("xrd_phase_peak_detection_") or item.endswith("_fallback") for item in provenance["candidate_methods"])
    assert not list((tmp_path / "output").rglob("*.opju"))
    assert not list((tmp_path / "output").rglob("*.tif"))
    assert not list((tmp_path / "output").rglob("*.png"))


def test_phase_failure_leaves_no_processed_or_metadata_files(tmp_path: Path) -> None:
    source = tmp_path / "phase_failure.csv"
    _write_xrd(source)
    output_root = tmp_path / "output"
    options = XrdPhaseMatchOptions(database_dir=tmp_path / "jade", card_ids=("97-000-0001",))

    with patch("src.core.xrd_jade.match_xrd_phases", side_effect=RuntimeError("Jade reader failed")):
        with pytest.raises(RuntimeError, match="Jade reader failed"):
            process_table_dataset(
                tmp_path,
                _classification(),
                source,
                output_root=output_root,
                xrd_phase_options=options,
            )

    assert not list(output_root.rglob("*_processed.csv"))
    assert not list(output_root.rglob("metadata.json"))
    assert not list(output_root.rglob("card_match_candidates.json"))
