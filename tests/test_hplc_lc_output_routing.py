from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

from src.core.runtime_paths import create_run_output_layout
from src.processors.base import process_table_dataset


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


def _process_in_run_root(tmp_path: Path, source: Path) -> dict:
    layout = create_run_output_layout(
        tmp_path,
        scope=f"hplc_lc_{source.stem}",
        command="process",
        mode="no_origin",
        input_paths=[source],
        timestamp=f"20260604_{abs(hash(source.stem)) % 1000000:06d}",
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
    assert metadata["run_output_root"].startswith("output/runs/")
    assert metadata["metadata_path"].startswith(metadata["run_output_root"] + "/metadata/")
    assert metadata["processed_data"].startswith(metadata["run_output_root"] + "/processed_data/")
    assert metadata["origin_file"] is None
    assert metadata["figure_tif"] is None
    assert metadata["preview_png"] is None
    assert not (tmp_path / "output" / "metadata").exists()
    assert not (tmp_path / "output" / "processed_data").exists()
    assert not (tmp_path / "output" / "origin_files").exists()
    assert not (tmp_path / "output" / "figures_tif").exists()
    assert not (tmp_path / "output" / "figures_preview").exists()
    return metadata


def test_chromatogram_plot_intent_is_run_scoped_and_candidate_only(tmp_path: Path):
    source = tmp_path / "input" / "hplc_chromatogram.csv"
    _write_csv(source, ["time min", "absorbance"], [[0.0, 0.1], [0.5, 0.4], [1.0, 0.2]])

    metadata = _process_in_run_root(tmp_path, source)

    assert metadata["plot_type"] == "chromatogram"
    assert metadata["key_results"]["lc_plot_intent"] == {
        "candidate": True,
        "plot_type": "chromatogram",
        "x_axis": "retention_time_min",
        "y_axis": "signal",
        "manual_check_required": True,
    }
    assert "product_identity_candidate" not in metadata["key_results"]


def test_peak_table_plot_intent_is_summary_without_conversion(tmp_path: Path):
    source = tmp_path / "input" / "hplc_peak_table.csv"
    _write_csv(
        source,
        ["retention time", "area", "height", "peak name"],
        [[1.2, 100.0, 8.0, "named peak"]],
    )

    metadata = _process_in_run_root(tmp_path, source)

    assert metadata["plot_type"] == "peak_table_summary"
    assert metadata["key_results"]["lc_plot_intent"] == {
        "candidate": True,
        "plot_type": "peak_table_summary",
        "x_axis": "retention_time_min",
        "y_axis": "peak_area_optional",
        "manual_check_required": True,
    }
    assert metadata["key_results"]["lc_candidate_peaks"][0]["peak_name"] == "named peak"
    assert metadata["key_results"]["lc_candidate_peaks"][0]["identity_assignment"] == "unassigned_manual_mapping_required"
    assert "conversion_candidate" not in metadata["key_results"]


def test_calibration_plot_intent_is_manual_check_fit_candidate(tmp_path: Path):
    source = tmp_path / "input" / "hplc_calibration.csv"
    _write_csv(
        source,
        ["manual mapping", "concentration", "response"],
        [["standard", 0.0, 2.0], ["standard", 1.0, 5.0], ["standard", 2.0, 8.0]],
    )

    metadata = _process_in_run_root(tmp_path, source)

    assert metadata["plot_type"] == "calibration_curve"
    assert metadata["key_results"]["lc_plot_intent"] == {
        "candidate": True,
        "plot_type": "calibration_curve",
        "x_axis": "concentration",
        "y_axis": "response",
        "manual_check_required": True,
    }
    candidate = metadata["key_results"]["lc_calibration_candidate"]
    assert candidate["manual_check_required"] is True
    assert candidate["slope"] == 3.0
    assert candidate["intercept"] == 2.0
    assert candidate["r_squared"] == 1.0


def test_no_calibration_peak_table_has_no_quantification_plot_intent(tmp_path: Path):
    source = tmp_path / "input" / "hplc_no_calibration.csv"
    _write_csv(
        source,
        ["retention time", "area", "height", "conversion", "selectivity", "yield", "product"],
        [[1.2, 100.0, 8.0, 80.0, 90.0, 70.0, "target"]],
    )

    metadata = _process_in_run_root(tmp_path, source)

    assert metadata["key_results"]["lc_quantification_boundary"] == "requires_manual_calibration"
    assert metadata["key_results"]["lc_plot_intent"]["plot_type"] == "peak_table_summary"
    assert "conversion_candidate" not in metadata["key_results"]
    assert "selectivity_candidate" not in metadata["key_results"]
    assert "yield_candidate" not in metadata["key_results"]


def test_ambiguous_export_has_no_plot_intent_and_manual_review_reason(tmp_path: Path):
    source = tmp_path / "input" / "hplc_ambiguous.csv"
    _write_csv(source, ["sample", "value"], [["A", 1.0], ["B", 2.0]])

    metadata = _process_in_run_root(tmp_path, source)

    assert metadata["processing_status"] == "manual_review"
    assert metadata["plot_type"] == "manual_review"
    assert metadata["key_results"]["lc_plot_intent"] == {
        "candidate": False,
        "reason": "ambiguous_exported_table",
    }
    assert metadata["key_results"]["lc_manual_review_required"] is True
    assert metadata["key_results"]["lc_missing_fields"] == [
        "time_or_retention_time",
        "signal_or_peak_area_or_calibration_response",
    ]
