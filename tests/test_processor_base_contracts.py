from __future__ import annotations

import csv
from types import SimpleNamespace
from unittest.mock import patch

from src.processors.base import process_table_dataset


def classification(data_type: str, processor: str) -> dict:
    return {
        "inferred_data_type": data_type,
        "selected_processor": processor,
    }


def test_raman_generic_xy_headers_use_data_type_axis_titles(tmp_path):
    source = tmp_path / "raman.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "intensity"])
        writer.writerow([100, 1])
        writer.writerow([200, 5])

    with patch("src.processors.base.export_plot") as export_plot:
        export_plot.return_value = SimpleNamespace(
            ok=False,
            origin_file=None,
            figure_tif=None,
            preview_png=None,
            message="Origin unavailable",
        )
        process_table_dataset(tmp_path, classification("Raman", "raman_processor"), source, no_origin=False)

    args, kwargs = export_plot.call_args
    assert args[3] == "Raman Shift (cm-1)"
    assert args[4] == "Intensity (a.u.)"
    assert kwargs["data_type"] == "Raman"


def test_algorithm_provenance_records_optional_adapter_policy(tmp_path):
    source = tmp_path / "mott_linear.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["potential", "1/C^2"])
        writer.writerow([-0.2, -1.0])
        writer.writerow([0.0, 1.0])
        writer.writerow([0.2, 3.0])

    metadata = process_table_dataset(
        tmp_path,
        classification("Mott-Schottky", "mott_schottky_processor"),
        source,
    )

    provenance = metadata["parameters"]["algorithm_provenance"]
    assert provenance["adapter_layer"] == "src.adapters"
    assert provenance["adapter_policy"] == "lazy optional adapters with fallback; candidate metrics only"
    assert provenance["interpretation_policy"] == "candidate metrics only; scientific interpretation requires manual review"
