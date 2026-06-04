from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="XPS_non_in_situ",
    output_slug="XPS_non_in_situ_BOBC_BC_exemplar_pilot",
    manual_review_items=(
        "Confirm BOBC/BC or CWO/BC comparison choice.",
        "Confirm binding-energy calibration and display direction.",
        "Confirm fitted component/background/envelope/residual roles manually.",
        "Panel/comparison grouping is reported for manual review and must not be mixed with in-situ XPS.",
    ),
    forbidden_claims_avoided=(
        "no valence assignment",
        "no electron-transfer conclusion",
        "no S-scheme mechanism conclusion",
    ),
    reference_policy_notes=(
        "Non-in-situ XPS must use a non-in-situ exemplar only.",
        "Archived exemplars are copied before Origin opens them.",
        "Panel grouping information is metadata for review, not a valence or mechanism conclusion.",
    ),
)
