from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="Raman",
    output_slug="Raman_BOBC_exemplar_draft",
    manual_review_items=(
        "Confirm Raman shift axis and intensity units.",
        "Peak labels or phase/defect assignments require manual review.",
        "Overlay grouping from the exemplar is a style candidate only.",
    ),
    forbidden_claims_avoided=(
        "no phase assignment",
        "no defect or bond assignment",
    ),
    reference_policy_notes=(
        "Saved Origin format asset is used only for axis and visual style.",
        "Scientific peak labels are not copied into the draft.",
    ),
)
