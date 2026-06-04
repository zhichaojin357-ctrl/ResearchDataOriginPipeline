from __future__ import annotations

from src.origin.type_mimic import TYPE_MIMIC_SPECS
from src.origin.type_mimic.common import FORBIDDEN_PRODUCT_TYPES


def test_type_mimic_specs_cover_only_current_round_products() -> None:
    assert set(TYPE_MIMIC_SPECS) == {"BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR"}
    assert "HPLC/LC exported data" in FORBIDDEN_PRODUCT_TYPES
    assert "Raman" in FORBIDDEN_PRODUCT_TYPES


def test_type_mimic_specs_use_required_neutral_product_names() -> None:
    assert TYPE_MIMIC_SPECS["BET"].output_slug == "BET_BOBC_exemplar_pilot"
    assert TYPE_MIMIC_SPECS["XPS_in_situ"].output_slug == "XPS_in_situ_BOBC_exemplar_pilot"
    assert TYPE_MIMIC_SPECS["XPS_non_in_situ"].output_slug == "XPS_non_in_situ_BOBC_BC_exemplar_pilot"
    assert TYPE_MIMIC_SPECS["XRD"].output_slug == "XRD_BOBC_exemplar_pilot"
    assert TYPE_MIMIC_SPECS["EPR"].output_slug == "EPR_BC_O3_dark_exemplar_pilot"


def test_type_mimic_specs_keep_scientific_claims_manual() -> None:
    assert "no S-scheme mechanism conclusion" in TYPE_MIMIC_SPECS["XPS_in_situ"].forbidden_claims_avoided
    assert "no S-scheme mechanism conclusion" in TYPE_MIMIC_SPECS["XPS_non_in_situ"].forbidden_claims_avoided
    assert "no phase assignment" in TYPE_MIMIC_SPECS["XRD"].forbidden_claims_avoided
    assert "no radical species assignment" in TYPE_MIMIC_SPECS["EPR"].forbidden_claims_avoided
