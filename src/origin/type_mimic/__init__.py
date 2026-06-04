from __future__ import annotations

from src.origin.type_mimic.bet import SPEC as BET_SPEC
from src.origin.type_mimic.common import TypeMimicSpec
from src.origin.type_mimic.epr import SPEC as EPR_SPEC
from src.origin.type_mimic.xps_in_situ import SPEC as XPS_IN_SITU_SPEC
from src.origin.type_mimic.xps_non_in_situ import SPEC as XPS_NON_IN_SITU_SPEC
from src.origin.type_mimic.xrd import SPEC as XRD_SPEC


TYPE_MIMIC_SPECS: dict[str, TypeMimicSpec] = {
    spec.product_key: spec
    for spec in (BET_SPEC, XPS_IN_SITU_SPEC, XPS_NON_IN_SITU_SPEC, XRD_SPEC, EPR_SPEC)
}

for _spec in TYPE_MIMIC_SPECS.values():
    _spec.validate_neutral_output_slug()
