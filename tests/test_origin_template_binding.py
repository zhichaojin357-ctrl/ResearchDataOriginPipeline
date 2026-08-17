from __future__ import annotations

from src.origin.template_binding import (
    load_template_binding_contracts,
    resolve_template_binding_contract,
)


def test_checked_in_binding_contract_contains_only_verified_bet_asset() -> None:
    contracts = load_template_binding_contracts()

    assert set(contracts) == {"bet"}
    assert contracts["bet"].ready is True
    assert contracts["bet"].source_series_count == 6


def _bet_mappings(*, first_pair_row_to: int = 32) -> list[dict[str, object]]:
    return [
        {
            "layer_index": 1,
            "plot_index": index,
            "x_dataset": f"Isotherm_{x_column}",
            "y_dataset": f"Isotherm_{y_column}",
            "row_from": 1,
            "row_to": first_pair_row_to if index <= 2 else 33,
        }
        for index, (x_column, y_column) in enumerate(
            (("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"), ("I", "J"), ("K", "L")),
            start=1,
        )
    ]


def test_bet_binding_contract_requires_exact_xy_datasets_and_display_rows() -> None:
    resolution = resolve_template_binding_contract("BET", "Graph5", _bet_mappings())

    assert resolution.ok is True
    assert [item["source_series_index"] for item in resolution.plot_mappings] == [1, 2, 3, 4, 5, 6]
    assert resolution.contract is not None
    assert resolution.contract.reference_opju_sha256.startswith("90dccbf4")


def test_bet_binding_contract_fails_when_reference_row_range_changes() -> None:
    resolution = resolve_template_binding_contract(
        "BET",
        "Graph5",
        _bet_mappings(first_pair_row_to=33),
    )

    assert resolution.ok is False
    assert resolution.status == "mapping_mismatch"
    assert "expected 1:32" in resolution.message
