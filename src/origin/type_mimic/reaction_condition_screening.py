from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="reaction_condition_screening",
    output_slug="reaction_condition_screening_draft",
    manual_review_items=(
        "Confirm condition labels and values before plotting.",
        "No best-condition claim is generated.",
        "Conversion and selectivity are not calculated unless explicit values are provided.",
    ),
    forbidden_claims_avoided=(
        "no optimum-condition conclusion",
        "no conversion or selectivity calculation from ambiguous data",
    ),
    reference_policy_notes=(
        "Saved Origin format candidates are bar-chart style exemplars only.",
        "If no clear data table is present, this type is skipped.",
    ),
)
