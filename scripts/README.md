# Scripts

Operational scripts are kept here. Deprecated scripts should move to `scripts/archive/` only after no CLI or documentation entrypoint references them.

Organize scripts by function first and data type second. Use `scripts/data_types/<data_type>/` only for scripts that are strongly bound to one instrument, one data type, or one raw format.

## Contents

- `archive/`
- `data_types/`
- `maintenance/`
- `one_off/`
- `origin/`
- `reports/`

Current classified helpers:

- `reports/regenerate_manual_review_filtered.py`: reusable manual-review report generator.
- `origin/origin_plot_from_template.ps1`: project-local Origin helper used by the formal Origin adapter; imports data by writing neutral workbook cells so OPJU outputs do not inherit source-file paths.
- `maintenance/opju_exemplar_regression.py`: OPJU exemplar regression/comparison helper, not a production processor.
- `one_off/verify_jeol_epr_decode_against_exports.py`: JEOL EPR decode verification helper kept for traceability.
- `data_types/hplc_lc/plot_hplc_calibration_origin.ps1`: HPLC/LC calibration-curve Origin script using the fixed completed OPJU template.
- `data_types/xps/build_xps_in_situ_20260506.py`: XPS-specific historical helper.

Do not use old root paths as current entrypoints:

- `scripts/regenerate_manual_review_filtered.py`
- `scripts/build_xps_in_situ_20260506.py`
