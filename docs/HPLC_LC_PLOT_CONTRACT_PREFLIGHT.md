# HPLC/LC Plot Contract Preflight

Date: 2026-06-04

## Audit Commands

- `git status --short`: clean before this document.
- `git diff --cached --name-status`: clean before this document.
- `git status --short -- config src tests docs`: clean before this document.
- `git grep -n "HPLC" -- config src tests docs`: found registry, method-card, adapter, processor, plot-policy, and behavior-test references.
- `git grep -n "LC exported" -- config src tests docs`: found registry, method-card, adapter, processor, and behavior-test references.
- `git grep -n "chromatogram" -- config src tests docs`: found method-card, plot-policy, calculation, profile, and behavior-test references.
- `git grep -n "peak table" -- config src tests docs`: found method-card and profile references.
- `git grep -n "calibration" -- config src tests docs`: found HPLC/LC method-card, plot-policy, adapter, calculation, and no-calibration behavior-test references.
- `git grep -n "conversion" -- config src tests docs`: found claim policy, method-card, calculation guard, and no-conversion behavior-test references.
- `git grep -n "selectivity" -- config src tests docs`: found claim policy, method-card, calculation guard, and no-selectivity behavior-test references.

## Current Support

1. Registry status: `config/processor_registry.yaml` already registers `HPLC/LC exported data` as Phase 1 supported with `selected_processor: lc_exported_data_processor`.
2. Processor status: there is no separate HPLC/LC processor module; HPLC/LC currently uses the generic `src.processors.base.process_table_dataset()` path and type-specific helpers in `src.processors.calculations`.
3. Test status: existing `tests/test_processor_behaviors.py` covers basic HPLC/LC peak-table, chromatogram, and no-calibration blocking behavior. A dedicated `tests/test_hplc_lc_contracts.py` file did not exist at audit time.
4. Table-reader status: `src/core/table_reader.py` can read CSV/TXT/XLSX/XLS/XLSM exported tables and coerce retention-time, time, signal, absorbance, intensity, mAU, area, and height-like columns into numeric rows.
5. Calculation status: `src/processors/calculations.py` currently detects HPLC/LC chromatogram versus peak-table mode and blocks quantification/product-identity fields when calibration evidence is missing. Dedicated calibration-curve candidate extraction and ambiguous-table manual-review metadata are incomplete.
6. Metadata status: `src/core/metadata.py` records run output root, source provenance, manual-check items, forbidden claims, warnings, key results, and algorithm provenance. It can carry HPLC/LC candidate intent through `key_results` and `parameters`.
7. Origin policy status: `src/origin/plot_policy.py` already defines `HPLC/LC exported data`, `HPLC/LC peak summary`, and generic `calibration_curve` plot policies with forbidden automatic-product and no-calibration claims.

## Risks

- HPLC/LC exported files can mix chromatogram tables, peak tables, calibration standards, and vendor metadata in similar CSV/XLSX shapes.
- Peak names and retention times are not product identities without user-provided mapping.
- Peak area is not concentration without calibration and analyte mapping.
- Conversion, selectivity, and yield require calibration, analyte role mapping, and dilution/volume/concentration rules.
- Ambiguous tables must not fall through to generic two-column plotting as if they were chromatograms.
- Synthetic tests must use a temporary run root and must not write repository `output/` or `outputs/`.

## Recommended Implementation Range

- Add a dedicated synthetic HPLC/LC contract test file.
- Extend the existing HPLC/LC calculation helper only as needed to classify exported tables as chromatogram, peak table, calibration curve, or ambiguous manual-review.
- Keep all outputs as candidate/provenance metadata, not final scientific conclusions.
- Route synthetic processing outputs into a `tmp_path` run root.
- Do not add real-data fixtures or Origin execution.

## Synthetic Tests

Synthetic tests are recommended and should cover:

- chromatogram exported table;
- peak table exported table;
- calibration table candidate;
- peak table without calibration;
- ambiguous exported table;
- run-scoped output compatibility.

## Strict Allowlist

Allowed files for this goal:

- `config/processor_registry.yaml`
- `src/core/table_reader.py`
- `src/core/process.py`
- `src/core/metadata.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- HPLC/LC related processor code if it exists
- `tests/test_hplc_lc_contracts.py`
- `docs/HPLC_LC_PLOT_CONTRACT_PREFLIGHT.md`
- `docs/HPLC_LC_ACCEPTANCE_CRITERIA.md`
- `docs/HPLC_LC_SYNTHETIC_TEST_PLAN.md`
- `docs/HPLC_LC_GOAL_SUMMARY.md`
