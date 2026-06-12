# Scripts

Operational helper scripts are kept here. Formal processing entrypoints remain `run.py` and `src/cli.py`; scripts are only supporting tools for reporting, Origin integration, or format verification.

Organize scripts by function first and data type second. Use `scripts/data_types/<data_type>/` only for scripts that are strongly bound to one instrument, one data type, or one raw format.

## Contents

- `archive/`
- `data_types/`
- `one_off/`
- `origin/`
- `reports/`

Current classified helpers:

- `reports/regenerate_manual_review_filtered.py`: reusable manual-review report generator.
- `origin/origin_plot_from_template.ps1`: project-local Origin helper used by the formal Origin adapter; imports data by writing neutral workbook cells so OPJU outputs do not inherit source-file paths.
- `one_off/verify_jeol_epr_decode_against_exports.py`: JEOL EPR decode verification helper kept for traceability.
- `data_types/hplc_lc/plot_hplc_calibration_origin.ps1`: HPLC/LC calibration-curve Origin script using the fixed completed OPJU template.

Do not add root-level script entrypoints. Put new helpers under the functional folder that owns them and keep formal data processing in `run.py`/`src/cli.py`.
