# HPLC/LC Goal Summary

Date: 2026-06-04

## Current Support Status

- `HPLC/LC exported data` is registered in `config/processor_registry.yaml` as Phase 1 supported with `lc_exported_data_processor`.
- The implementation remains exported-table only. It does not decode proprietary raw vendor directories.
- The processor path is the generic `process_table_dataset()` flow with HPLC/LC-specific contract logic in `src/processors/calculations.py`.
- Metadata now records explicit HPLC/LC plot intent and candidate boundaries for chromatogram, peak table, calibration curve, and ambiguous tables.

## Contracts Added or Confirmed

- Chromatogram contract: retention time or time plus signal/intensity/absorbance/mAU can produce a chromatogram candidate.
- Peak table contract: retention time plus area/height can produce a peak-table summary candidate while preserving candidate peak rows.
- Calibration contract: concentration plus response/peak area plus analyte/manual mapping can produce a manual-check linear calibration candidate with slope, intercept, and R squared.
- No-calibration boundary: peak tables without calibration record `requires_manual_calibration` and do not emit conversion, selectivity, yield, or product-identity candidates.
- Ambiguous-table boundary: unclear exported tables are marked `manual_review`, record missing fields, and do not emit a plot candidate.

## Tests Covered

- `tests/test_hplc_lc_contracts.py`
  - synthetic chromatogram candidate;
  - synthetic peak-table candidate;
  - synthetic calibration candidate;
  - no-calibration conversion/selectivity/yield boundary;
  - ambiguous table manual-review boundary;
  - run-scoped output compatibility using a temporary run root.
- `tests/test_processor_behaviors.py`
  - existing processor behavior coverage after the shared HPLC/LC helper changes.

## Safety Checks

- Origin run: no.
- Real HPLC/LC data processed: no.
- OPJU/TIF/PNG/PDF/XLSX/ZIP artifacts generated: no.
- Repository `output/` written: no.
- Repository `outputs/` written: no.
- Full pytest run: no.

## Real Data Validation Needs

Before any real HPLC/LC exported sample dry-run, the user must provide or confirm:

- exported chromatogram or peak-table file scope;
- source provenance and whether the file is an export rather than raw vendor data;
- calibration table if quantification is requested;
- analyte mapping;
- substrate/product role mapping;
- dilution, volume, concentration, and response-factor rules;
- manual acceptance of any product-identity or conversion/selectivity/yield claims.

## Next Step Recommendation

Recommended next GOAL: `GOAL: HPLC/LC Synthetic Processor Contract Execution`.

Alternative next GOALs:

- `GOAL: HPLC/LC Small Real Exported Sample Dry-Run`
- `GOAL: BET Visual Acceptance Preflight`
