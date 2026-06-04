# HPLC/LC Module Completion Summary

Date: 2026-06-04

## Commits Completed

- `500c8fa` - `hplc: complete exported table candidate helpers`
- `5ddc9df` - `hplc: integrate exported data candidates into processing flow`
- `1cd262e` - `hplc: route exported data plot intents through run metadata`
- `e74b7cf` - `docs: document hplc lc exported data method card`
- `3b33424` - `docs: plan hplc lc real sample dry run`

## Current Support Scope

The HPLC/LC exported data module now supports no-Origin, synthetic-verified candidate processing for:

- exported chromatogram tables;
- exported peak tables;
- exported calibration tables;
- no-calibration quantification boundaries;
- ambiguous exported table manual review;
- run-scoped metadata and plot intent.

The module remains candidate-only. It does not emit final scientific conclusions.

## Supported Exported Chromatogram

Supported when exported columns contain time or retention-time values plus signal, intensity, absorbance, detector response, or mAU values.

Recorded output:

- `lc_export_mode = chromatogram`;
- `lc_plot_intent.plot_type = chromatogram`;
- candidate x-axis and y-axis;
- manual-check metadata;
- no product identity.

## Supported Exported Peak Table

Supported when exported columns contain retention time plus area or height information.

Recorded output:

- `lc_export_mode = peak_table`;
- `lc_candidate_peaks`;
- peak area totals as candidate values;
- peak names preserved only as labels;
- `identity_assignment = unassigned_manual_mapping_required`;
- no product identity from peak name or retention time.

## Supported Calibration Candidate

Supported when exported columns contain concentration, response or peak area, and analyte or manual mapping.

Recorded output:

- `lc_export_mode = calibration_curve`;
- `lc_calibration_candidate`;
- slope, intercept, R squared, point count, analyte, and fit method;
- calibration plot intent;
- manual-check required.

## No-Calibration Boundary

When peak tables contain conversion, selectivity, yield, product, amount, concentration, or identity-like fields without calibration evidence:

- `lc_quantification_boundary = requires_manual_calibration`;
- `lc_quantification_blocked_reason` is recorded;
- warnings include the calibration boundary;
- no conversion, selectivity, yield, final concentration, or product identity candidate is emitted.

## Ambiguous Table Manual Review

When exported columns are not enough to classify chromatogram, peak table, or calibration table intent:

- processing status is `manual_review`;
- plot type is `manual_review`;
- no plot candidate is emitted;
- missing fields are recorded.

## Run-Scoped Output Intent

Synthetic tests verified that HPLC/LC metadata and processed CSVs route under a temporary run root when `output_root` is provided.

Verified no-Origin metadata fields:

- `run_output_root`;
- `metadata_path`;
- `processed_data`;
- `lc_plot_intent`;
- `origin_file = None`;
- `figure_tif = None`;
- `preview_png = None`.

## Explicitly Not Supported

- Agilent `.d` raw vendor directories;
- Waters `.raw` raw vendor directories;
- LC-MS raw decode;
- raw proprietary binary decode;
- automatic product identity;
- automatic substrate/product role mapping;
- conversion without calibration and mapping;
- selectivity without calibration and mapping;
- yield without calibration and mapping;
- reaction-completion conclusion;
- Origin export or visual acceptance in this no-Origin module goal.

## Validation Evidence

Final targeted tests:

- `D:\Python\python.exe -m pytest tests/test_hplc_lc_contracts.py tests/test_hplc_lc_process_integration.py tests/test_hplc_lc_output_routing.py -q`
  - Result: `16 passed in 0.70s`
- `D:\Python\python.exe -m pytest tests/test_processor_behaviors.py -q`
  - Result: `47 passed, 3 subtests passed in 1.28s`

Safety checks after final tests:

- `git status --short`: clean before writing this summary.
- `git status --short -- output outputs`: clean before writing this summary.
- `git diff --cached --name-status`: clean before writing this summary.

## Safety Outcome

- Origin run: no.
- Real HPLC/LC data processed: no.
- OPJU/TIF/PNG/PDF/XLSX/ZIP artifacts generated: no.
- Repository `output/` written: no.
- Repository `outputs/` written: no.
- Non-HPLC data types modified: no.

## Next Step

Recommended next GOAL: `GOAL: HPLC/LC Small Real Exported Sample Dry-Run`.

This next step requires a user-approved small exported HPLC/LC table and explicit confirmation that the run remains no-Origin unless the user changes scope.
