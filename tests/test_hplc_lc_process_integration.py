from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

from src.core.process import ProcessOptions, run_process
from src.core.runtime_paths import create_run_output_layout


def _write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _metadata_by_stem(layout_root: Path) -> dict[str, dict]:
    output = {}
    for path in layout_root.glob("metadata/HPLC_LC_exported_data/*/metadata.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        source_name = Path(metadata["source_files"][0]).name
        output[source_name] = metadata
    return output


def test_run_process_integrates_hplc_lc_synthetic_exports_without_origin(tmp_path: Path):
    input_root = tmp_path / "input" / "raw_data"
    lc_root = input_root / "LC"
    _write_csv(
        lc_root / "hplc_chromatogram.csv",
        ["retention time min", "intensity mAU"],
        [[0.0, 1.0], [0.5, 4.0], [1.0, 2.0]],
    )
    _write_csv(
        lc_root / "hplc_peak_table.csv",
        ["retention time", "area", "height", "peak name"],
        [[1.5, 10.0, 3.0, "product-like name"], [2.0, 20.0, 7.0, "substrate-like name"]],
    )
    _write_csv(
        lc_root / "hplc_calibration.csv",
        ["analyte", "concentration", "peak area"],
        [["standard_A", 0.0, 1.0], ["standard_A", 1.0, 3.0], ["standard_A", 2.0, 5.0]],
    )
    _write_csv(
        lc_root / "hplc_no_calibration_quant.csv",
        ["retention time", "area", "height", "conversion", "selectivity", "yield", "product"],
        [[1.5, 10.0, 3.0, 80.0, 90.0, 70.0, "target"]],
    )
    layout = create_run_output_layout(
        tmp_path,
        scope="hplc_lc_process_integration",
        command="process",
        mode="no_origin",
        input_paths=[input_root],
        timestamp="20260604_121000",
        no_origin=True,
        dry_run=False,
    )

    with patch("src.processors.base.export_plot", side_effect=AssertionError("Origin must not run")):
        code = run_process(
            tmp_path,
            input_root,
            ProcessOptions(no_origin=True, force=True, only_type="HPLC/LC exported data", output_root=layout.root),
        )

    assert code == 0
    metadata_by_name = _metadata_by_stem(layout.root)
    assert set(metadata_by_name) == {
        "hplc_chromatogram.csv",
        "hplc_peak_table.csv",
        "hplc_calibration.csv",
        "hplc_no_calibration_quant.csv",
    }

    chromatogram = metadata_by_name["hplc_chromatogram.csv"]
    assert chromatogram["key_results"]["lc_export_mode"] == "chromatogram"
    assert chromatogram["key_results"]["lc_plot_intent"]["plot_type"] == "chromatogram"
    assert chromatogram["processing_status"] == "processed_no_origin"

    peak_table = metadata_by_name["hplc_peak_table.csv"]
    assert peak_table["key_results"]["lc_export_mode"] == "peak_table"
    assert peak_table["key_results"]["lc_plot_intent"]["plot_type"] == "peak_table_summary"
    assert all(
        peak["identity_assignment"] == "unassigned_manual_mapping_required"
        for peak in peak_table["key_results"]["lc_candidate_peaks"]
    )
    assert "product_identity_candidate" not in peak_table["key_results"]

    calibration = metadata_by_name["hplc_calibration.csv"]
    assert calibration["key_results"]["lc_export_mode"] == "calibration_curve"
    assert calibration["key_results"]["lc_plot_intent"]["plot_type"] == "calibration_curve"
    assert calibration["key_results"]["lc_calibration_candidate"]["r_squared"] == 1.0
    assert calibration["parameters"]["algorithm_provenance"]["candidate_methods"] == [
        "lc_exported_table_contract_classification",
        "lc_calibration_linear_fit_candidate",
    ]

    no_calibration = metadata_by_name["hplc_no_calibration_quant.csv"]
    assert no_calibration["key_results"]["lc_export_mode"] == "peak_table"
    assert no_calibration["key_results"]["lc_quantification_boundary"] == "requires_manual_calibration"
    assert "lc_quantification_blocked_reason" in no_calibration["key_results"]
    assert "conversion_candidate" not in no_calibration["key_results"]
    assert "selectivity_candidate" not in no_calibration["key_results"]
    assert "yield_candidate" not in no_calibration["key_results"]

    processed_files = list(layout.root.glob("processed_data/HPLC_LC_exported_data/*_processed.csv"))
    assert len(processed_files) == 4
    assert (layout.root / "reports" / "processing_report.md").exists()
    assert not (tmp_path / "output" / "metadata").exists()
    assert not (tmp_path / "output" / "processed_data").exists()
