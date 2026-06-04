from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="photocurrent",
    output_slug="photocurrent_BOBC_exemplar_draft",
    manual_review_items=(
        "Confirm time-current axis mapping.",
        "Confirm light on/off segmentation manually if needed.",
        "No carrier-separation enhancement conclusion is generated.",
    ),
    forbidden_claims_avoided=(
        "no carrier-separation conclusion",
        "no photocatalytic mechanism conclusion",
    ),
    reference_policy_notes=(
        "Reference OPJU is used only as a time-current style exemplar.",
        "Light on/off labels are not inferred or copied.",
    ),
)
