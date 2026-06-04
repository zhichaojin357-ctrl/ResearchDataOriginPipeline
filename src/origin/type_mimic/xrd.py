from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="XRD",
    output_slug="XRD_BOBC_exemplar_pilot",
    manual_review_items=(
        "Confirm whether reference-card/stick-pattern content should be copied before any final figure.",
        "Confirm phase labels and crystal-plane labels manually if needed.",
    ),
    forbidden_claims_avoided=(
        "no phase assignment",
        "no crystal-plane assignment",
        "no automatic reference-card copying",
    ),
    reference_policy_notes=(
        "Raw pattern or stacked visual style only.",
        "Reference-card content in an exemplar is recorded for review, not copied.",
    ),
)
