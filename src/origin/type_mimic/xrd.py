from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="XRD",
    output_slug="XRD_BOBC_exemplar",
    manual_review_items=(
        "Confirm whether reference-card/stick-pattern content should be copied before any final figure.",
        "Confirm local-database card identifiers, phase-match confidence, and any crystal-plane labels.",
    ),
    forbidden_claims_avoided=(
        "no crystal-plane assignment",
        "no automatic phase-purity claim",
        "no automatic reference-card copying",
    ),
    reference_policy_notes=(
        "Raw pattern or stacked visual style only.",
        "Reference-card content in an exemplar is recorded for review, not copied.",
        "reference_card_present_in_exemplar_not_copied",
    ),
)
