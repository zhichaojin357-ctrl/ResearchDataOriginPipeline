from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="PL",
    output_slug="PL_BOBC_exemplar_draft",
    manual_review_items=(
        "Confirm emission versus excitation mode.",
        "Confirm overlay grouping manually.",
        "No recombination-efficiency conclusion is generated.",
    ),
    forbidden_claims_avoided=(
        "no recombination mechanism conclusion",
        "no charge-separation conclusion",
    ),
    reference_policy_notes=(
        "Saved Origin format asset is used only for PL visual style.",
        "Excitation/emission interpretation remains manual review only.",
    ),
)
