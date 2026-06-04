from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="XPS_in_situ",
    output_slug="XPS_in_situ_BOBC_exemplar_pilot",
    manual_review_items=(
        "Confirm BOBC, dark, and light sample mapping.",
        "Confirm binding-energy calibration and display direction.",
        "Confirm fitted component/background/envelope/residual roles manually.",
    ),
    forbidden_claims_avoided=(
        "no valence assignment",
        "no electron-transfer conclusion",
        "no S-scheme mechanism conclusion",
    ),
    reference_policy_notes=(
        "In-situ XPS stays separate from non-in-situ XPS.",
        "Reference OPJU is only a visual exemplar for manual calibration.",
    ),
)
