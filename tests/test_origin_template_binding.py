from __future__ import annotations

from pathlib import Path

from src.origin.template_binding import (
    load_template_binding_contracts,
    resolve_template_binding_contract,
)


def test_checked_in_binding_contracts_load_and_quarantine_unresolved_types() -> None:
    contracts = load_template_binding_contracts()

    assert len(contracts) == 12
    assert contracts["bet"].ready is True
    assert contracts["eis"].source_series_count == 8
    assert contracts["uv_vis_drs___tauc"].ready is False
    assert contracts["xrd"].status == "blocked_independent_reference_card_required"
    assert contracts["xps_in_situ"].status == "blocked_explicit_aliases_required"
    assert contracts["xps_non_in_situ"].status == "blocked_empty_reference_plots"


def test_checked_in_bet_runtime_binding_contract_is_standalone() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "BET.json"
    )

    contracts = load_template_binding_contracts(path)

    assert set(contracts) == {"bet"}
    assert contracts["bet"].ready is True


def test_bet_binding_contract_requires_exact_xy_datasets_and_display_rows() -> None:
    mappings = [
        {
            "layer_index": 1,
            "plot_index": index,
            "x_dataset": f"Isotherm_{x_column}",
            "y_dataset": f"Isotherm_{y_column}",
            "row_from": 1,
            "row_to": 32 if index <= 2 else 33,
        }
        for index, (x_column, y_column) in enumerate(
            (("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"), ("I", "J"), ("K", "L")),
            start=1,
        )
    ]

    resolution = resolve_template_binding_contract("BET", "Graph5", mappings)

    assert resolution.ok is True
    assert [item["source_series_index"] for item in resolution.plot_mappings] == [1, 2, 3, 4, 5, 6]
    assert resolution.contract is not None
    assert resolution.contract.reference_opju_sha256.startswith("90dccbf4")


def test_raman_binding_contract_does_not_infer_source_order_from_plot_order() -> None:
    resolution = resolve_template_binding_contract(
        "Raman",
        "Graph2",
        [
            {"layer_index": 1, "plot_index": 1, "x_dataset": "Book2_A", "y_dataset": "Book2_B", "row_from": 1, "row_to": 1214},
            {"layer_index": 1, "plot_index": 2, "x_dataset": "Book2_E", "y_dataset": "Book2_F", "row_from": 1, "row_to": 1186},
            {"layer_index": 2, "plot_index": 1, "x_dataset": "Book2_C", "y_dataset": "Book2_D", "row_from": 1, "row_to": 1214},
        ],
    )

    assert resolution.ok is True
    assert [item["source_series_index"] for item in resolution.plot_mappings] == [1, 3, 2]


def test_binding_contract_fails_closed_when_reference_row_range_changes() -> None:
    resolution = resolve_template_binding_contract(
        "BET",
        "Graph5",
        [
            {"layer_index": 1, "plot_index": index, "x_dataset": f"Isotherm_{x}", "y_dataset": f"Isotherm_{y}", "row_from": 1, "row_to": 33}
            for index, (x, y) in enumerate(
                (("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"), ("I", "J"), ("K", "L")),
                start=1,
            )
        ],
    )

    assert resolution.ok is False
    assert resolution.status == "mapping_mismatch"
    assert "expected 1:32" in resolution.message


def test_uv_contract_blocks_wavelength_signal_to_tauc_guessing() -> None:
    resolution = resolve_template_binding_contract("UV-vis DRS / Tauc", "Graph2", [])

    assert resolution.ok is False
    assert resolution.status == "blocked_semantic_transform_required"
    assert "photon-energy/Tauc" in resolution.message
