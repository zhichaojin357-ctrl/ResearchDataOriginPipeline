from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="FTIR",
    output_slug="FTIR_BOBC_CWO_exemplar_draft",
    manual_review_items=(
        "Confirm wavenumber axis direction before final use.",
        "Confirm whether peak or valley labels should be added manually.",
        "No functional-group assignment is generated.",
    ),
    forbidden_claims_avoided=(
        "no functional-group assignment",
        "no bond or mechanism conclusion",
    ),
    reference_policy_notes=(
        "Reference OPJU is used only for FTIR axis/style traits.",
        "Peak and valley labels remain manual review only.",
    ),
)
