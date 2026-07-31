from __future__ import annotations

from src.origin.type_mimic import ALL_TYPE_MIMIC_SPECS, TYPE_MIMIC_SPECS


def test_type_mimic_specs_keep_core_exemplars_and_cover_current_products() -> None:
    assert set(TYPE_MIMIC_SPECS) == {"BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR"}
    assert {"Raman", "EIS", "Mott-Schottky", "UV-vis DRS / Tauc", "PL", "photocurrent", "FTIR"}.issubset(
        ALL_TYPE_MIMIC_SPECS
    )


def test_type_mimic_specs_use_required_neutral_product_names() -> None:
    assert TYPE_MIMIC_SPECS["BET"].output_slug == "BET_BOBC_exemplar"
    assert TYPE_MIMIC_SPECS["XPS_in_situ"].output_slug == "XPS_in_situ_BOBC_exemplar"
    assert TYPE_MIMIC_SPECS["XPS_non_in_situ"].output_slug == "XPS_non_in_situ_BOBC_BC_exemplar"
    assert TYPE_MIMIC_SPECS["XRD"].output_slug == "XRD_BOBC_exemplar"
    assert TYPE_MIMIC_SPECS["EPR"].output_slug == "EPR_BC_O3_dark_exemplar"


def test_type_mimic_specs_keep_scientific_claims_manual() -> None:
    assert "no S-scheme mechanism conclusion" in TYPE_MIMIC_SPECS["XPS_in_situ"].forbidden_claims_avoided
    assert "no S-scheme mechanism conclusion" in TYPE_MIMIC_SPECS["XPS_non_in_situ"].forbidden_claims_avoided
    assert "no phase assignment" in TYPE_MIMIC_SPECS["XRD"].forbidden_claims_avoided
    assert "no radical species assignment" in TYPE_MIMIC_SPECS["EPR"].forbidden_claims_avoided
