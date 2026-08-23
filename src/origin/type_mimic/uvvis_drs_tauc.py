from __future__ import annotations

from src.origin.type_mimic.common import TypeMimicSpec


DRS_SPEC = TypeMimicSpec(
    product_key="UV-vis DRS",
    output_slug="UV_vis_DRS_BOBC_exemplar",
    manual_review_items=(
        "Confirm whether the displayed signal is absorbance or reflectance.",
        "Confirm wavelength range and current sample labels.",
        "Band-edge positions are not inferred.",
    ),
    forbidden_claims_avoided=(
        "no final bandgap conclusion",
        "no CB or VB position conclusion",
    ),
    reference_policy_notes=(
        "Graph1 of the reviewed OPJU is the DRS style authority.",
        "Current spectra keep independent X/Y grids without interpolation, smoothing, normalization, or added offsets.",
    ),
)


TAUC_SPEC = TypeMimicSpec(
    product_key="Tauc",
    output_slug="Tauc_BOBC_exemplar",
    manual_review_items=(
        "Confirm the Kubelka-Munk or absorbance transform used for every source spectrum.",
        "Bandgap values and linear intervals are candidates only if manually reviewed.",
        "Band-edge positions are not inferred.",
    ),
    forbidden_claims_avoided=(
        "no final bandgap conclusion",
        "no CB or VB position conclusion",
    ),
    reference_policy_notes=(
        "Graph2 of the reviewed OPJU is the Tauc style authority.",
        "Reference fit guides and numeric intercept labels are retained only for exact same-data replay; new data require current fit provenance.",
    ),
)
