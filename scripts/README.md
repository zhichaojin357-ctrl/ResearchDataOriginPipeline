# Scripts

Operational scripts are kept here. Deprecated scripts should move to `scripts/archive/` only after no CLI or documentation entrypoint references them.

Organize scripts by function first and data type second. Use `scripts/data_types/<data_type>/` only for scripts that are strongly bound to one instrument, one data type, or one raw format.

## Contents

- `archive/`
- `data_types/`
- `maintenance/`
- `one_off/`
- `reports/`

Current classified helpers:

- `reports/regenerate_manual_review_filtered.py`: reusable manual-review report generator.
- `maintenance/opju_exemplar_regression.py`: OPJU exemplar regression/comparison helper, not a production processor.
- `one_off/verify_jeol_epr_decode_against_exports.py`: JEOL EPR decode verification helper kept for traceability.
- `data_types/xps/build_xps_in_situ_20260506.py`: XPS-specific historical helper.

Do not use old root paths as current entrypoints:

- `scripts/regenerate_manual_review_filtered.py`
- `scripts/build_xps_in_situ_20260506.py`
