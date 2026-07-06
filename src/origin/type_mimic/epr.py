from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="EPR",
    output_slug="EPR_BC_O3_dark_exemplar",
    manual_review_items=(
        "Confirm condition grouping manually.",
        "Confirm radical assignment manually if labels are needed.",
        "Y-axis ticks and numeric labels stay hidden by default while the axis line/title remains visible.",
    ),
    forbidden_claims_avoided=(
        "no radical species assignment",
        "no mechanism conclusion",
    ),
    reference_policy_notes=(
        "Overlay/decode graph style only.",
        "Radical labels in exemplars are not copied as conclusions.",
    ),
)
