from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="EIS",
    output_slug="EIS_BOBC_exemplar_draft",
    manual_review_items=(
        "Confirm Z' and -Z'' column mapping before final use.",
        "Confirm whether Nyquist, Bode, or fitting panels are needed.",
        "Equivalent-circuit text from the exemplar is not copied.",
    ),
    forbidden_claims_avoided=(
        "no equivalent-circuit conclusion",
        "no resistance or mechanism interpretation",
    ),
    reference_policy_notes=(
        "Reference OPJU is used only as a visual exemplar.",
        "Nyquist or Bode interpretation remains manual review only.",
    ),
)
