from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="BET",
    output_slug="BET_BOBC_exemplar_pilot",
    manual_review_items=(
        "Confirm adsorption/desorption branch mapping and units.",
        "Confirm whether the plotted table should remain an isotherm or use pore-distribution data.",
        "Do not infer pore structure quality or BET model validity from this pilot.",
    ),
    forbidden_claims_avoided=(
        "no pore-structure conclusion",
        "no BET model-validity conclusion",
    ),
    reference_policy_notes=(
        "Saved Origin format asset is used as visual/layout guidance only.",
        "Summary-only BET tables must not be converted into fake single-point isotherms.",
    ),
)
