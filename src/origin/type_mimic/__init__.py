from __future__ import annotations

from src.origin.type_mimic.bet import SPEC as BET_SPEC
from src.origin.type_mimic.common import TypeMimicSpec
from src.origin.type_mimic.eis import SPEC as EIS_SPEC
from src.origin.type_mimic.epr import SPEC as EPR_SPEC
from src.origin.type_mimic.ftir import SPEC as FTIR_SPEC
from src.origin.type_mimic.mott_schottky import SPEC as MOTT_SCHOTTKY_SPEC
from src.origin.type_mimic.photocurrent import SPEC as PHOTOCURRENT_SPEC
from src.origin.type_mimic.pl import SPEC as PL_SPEC
from src.origin.type_mimic.raman import SPEC as RAMAN_SPEC
from src.origin.type_mimic.reaction_condition_screening import SPEC as REACTION_CONDITION_SCREENING_SPEC
from src.origin.type_mimic.uvvis_drs_tauc import SPEC as UVVIS_DRS_TAUC_SPEC
from src.origin.type_mimic.xps_in_situ import SPEC as XPS_IN_SITU_SPEC
from src.origin.type_mimic.xps_non_in_situ import SPEC as XPS_NON_IN_SITU_SPEC
from src.origin.type_mimic.xrd import SPEC as XRD_SPEC


TYPE_MIMIC_SPECS: dict[str, TypeMimicSpec] = {
    spec.product_key: spec
    for spec in (BET_SPEC, XPS_IN_SITU_SPEC, XPS_NON_IN_SITU_SPEC, XRD_SPEC, EPR_SPEC)
}

REMAINING_TYPE_MIMIC_SPECS: dict[str, TypeMimicSpec] = {
    spec.product_key: spec
    for spec in (
        EIS_SPEC,
        RAMAN_SPEC,
        MOTT_SCHOTTKY_SPEC,
        UVVIS_DRS_TAUC_SPEC,
        PL_SPEC,
        PHOTOCURRENT_SPEC,
        FTIR_SPEC,
        REACTION_CONDITION_SCREENING_SPEC,
    )
}

ALL_TYPE_MIMIC_SPECS: dict[str, TypeMimicSpec] = {
    **TYPE_MIMIC_SPECS,
    **REMAINING_TYPE_MIMIC_SPECS,
}

for _spec in ALL_TYPE_MIMIC_SPECS.values():
    _spec.validate_neutral_output_slug()
