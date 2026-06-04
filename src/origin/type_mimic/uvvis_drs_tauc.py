from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


SPEC = TypeMimicSpec(
    product_key="UV-vis DRS / Tauc",
    output_slug="UV_vis_DRS_Tauc_BOBC_exemplar_draft",
    manual_review_items=(
        "Confirm DRS or Tauc display mode and transform parameters.",
        "Bandgap values are candidates only if manually reviewed.",
        "Band-edge positions are not inferred.",
    ),
    forbidden_claims_avoided=(
        "no final bandgap conclusion",
        "no CB or VB position conclusion",
    ),
    reference_policy_notes=(
        "Reference OPJU may contain DRS and Tauc panels; only safe axis/style traits are used.",
        "Tauc interval selection remains manual review only.",
    ),
)
