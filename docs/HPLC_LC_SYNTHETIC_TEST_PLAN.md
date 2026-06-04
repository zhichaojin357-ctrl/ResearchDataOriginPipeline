# HPLC/LC Synthetic Test Plan

Date: 2026-06-04

The tests use synthetic CSV fixtures created inside `tmp_path`. They do not read real HPLC/LC data, run Origin, or write repository `output/` or `outputs/`.

## Test Cases

1. Chromatogram table
   - Input columns: `retention time min`, `intensity mAU`.
   - Expected: `lc_export_mode = chromatogram`.
   - Expected: plot intent is a chromatogram candidate.
   - Expected: no conversion, selectivity, yield, product, or concentration candidate.

2. Peak table
   - Input columns: `retention time`, `area`, `height`, optional `peak name`.
   - Expected: `lc_export_mode = peak_table`.
   - Expected: plot intent is a peak-table summary candidate.
   - Expected: peak rows are preserved as candidates.
   - Expected: no automatic product identity.

3. Calibration table
   - Input columns: `analyte`, `concentration`, `peak area`.
   - Expected: `lc_export_mode = calibration_curve`.
   - Expected: calibration candidate contains slope, intercept, R squared, point count, and fit method.
   - Expected: manual-check marker is present.
   - Expected: no final concentration, conversion, selectivity, or yield.

4. No-calibration case
   - Input columns: peak-table fields plus conversion/selectivity/product-like columns.
   - Expected: no conversion, selectivity, or yield candidate.
   - Expected: `requires_manual_calibration` boundary and warning are recorded.

5. Ambiguous table
   - Input columns: insufficient generic columns.
   - Expected: manual review marker.
   - Expected: missing-field list.
   - Expected: no plot candidate.

6. Run-scoped output compatibility
   - Use `src.core.runtime_paths.create_run_output_layout()` to create a temporary run root.
   - Process a synthetic HPLC/LC export with `output_root=layout.root`.
   - Expected: metadata and processed CSV live under the run root.
   - Expected: repository-style root output directories are not created outside the run root.

## Verification Commands

- `D:\Python\python.exe -m py_compile tests/test_hplc_lc_contracts.py`
- `D:\Python\python.exe -m py_compile src/processors/base.py src/processors/calculations.py`
- `D:\Python\python.exe -m pytest tests/test_hplc_lc_contracts.py -q`
- `D:\Python\python.exe -m pytest tests/test_processor_behaviors.py -q` if common processor behavior changes.

Each verification round must be followed by:

- `git status --short -- output outputs`
- `git diff --cached --name-status`
