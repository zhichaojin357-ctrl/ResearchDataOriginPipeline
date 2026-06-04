from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="Mott-Schottky",
    output_slug="Mott_Schottky_BOBC_exemplar_draft",
    manual_review_items=(
        "Confirm the exemplar is genuinely a Mott-Schottky graph before plotting.",
        "Confirm potential and capacitance-derived columns manually.",
        "Carrier type, carrier density, and band positions are not inferred.",
    ),
    forbidden_claims_avoided=(
        "no carrier-type conclusion",
        "no carrier-density calculation",
        "no CB or VB position conclusion",
    ),
    reference_policy_notes=(
        "Mott-Schottky exemplar type must be checked by Origin readback.",
        "If the exemplar is XRD or another type, the product is skipped.",
    ),
)
