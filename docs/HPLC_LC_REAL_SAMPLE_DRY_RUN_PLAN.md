# HPLC/LC Real Sample Dry-Run Plan

Date: 2026-06-04

This plan defines how to run a future small real exported HPLC/LC sample safely. This GOAL does not run real data.

## Required User Inputs

Before a real dry-run, the user must provide or confirm:

- one small exported chromatogram table, peak table, or calibration table;
- source provenance and instrument export method;
- whether the file is an exported table rather than a raw vendor folder;
- detector channel and units if available;
- retention-time units;
- signal or response units;
- whether peak names are labels only or mapped standards;
- calibration table if quantification is requested;
- analyte mapping;
- substrate/product role mapping;
- dilution, volume, concentration, and response-factor rules;
- whether Origin export should remain disabled.

## Supported Exported Formats

Supported for dry-run:

- `.csv`
- `.txt`
- `.xlsx`
- `.xls`

The file must contain readable tabular columns.

## Unsupported Formats

Not supported in this module:

- Agilent `.d` directories;
- Waters `.raw` directories;
- LC-MS raw files;
- proprietary binary vendor exports;
- exported reports that contain only images or embedded plots;
- files requiring Origin to interpret.

## Dry-Run Steps

1. Place a copy of the small exported table in a temporary test input folder.
2. Create a run-scoped output root with the project run-output helper or CLI support.
3. Run process in no-Origin mode and restrict the data type to `HPLC/LC exported data`.
4. Confirm all metadata and processed CSV outputs are under the run root.
5. Confirm repository root `output/` and `outputs/` are not modified unless the user explicitly chose a repository run root.
6. Inspect `metadata.json` for `lc_export_mode`, `lc_plot_intent`, manual-check items, and forbidden claims.
7. Do not report product identity, conversion, selectivity, or yield unless the required calibration and mapping inputs are supplied and manually confirmed.

## Chromatogram Candidate Check

Expected input fields:

- time, retention time, or RT;
- signal, intensity, absorbance, detector response, or mAU.

Expected metadata:

- `lc_export_mode = chromatogram`;
- `lc_plot_intent.plot_type = chromatogram`;
- candidate x-axis and y-axis recorded;
- no product identity.

## Peak Table Candidate Check

Expected input fields:

- retention time or RT;
- area or peak area;
- height or peak height;
- optional peak name.

Expected metadata:

- `lc_export_mode = peak_table`;
- `lc_plot_intent.plot_type = peak_table_summary`;
- candidate peaks preserved;
- `identity_assignment = unassigned_manual_mapping_required`;
- no product identity from peak name or retention time.

## Calibration Candidate Check

Expected input fields:

- concentration or standard concentration;
- response, area, or peak area;
- analyte or manual mapping.

Expected metadata:

- `lc_export_mode = calibration_curve`;
- `lc_plot_intent.plot_type = calibration_curve`;
- `lc_calibration_candidate.slope`;
- `lc_calibration_candidate.intercept`;
- `lc_calibration_candidate.r_squared`;
- manual-check required.

## Quantification Boundary

Conversion, selectivity, yield, and final concentration may be considered only after the user confirms:

- calibration source;
- analyte mapping;
- substrate/product role mapping;
- dilution, volume, concentration, and response-factor rules;
- manual acceptance of the formula and assumptions.

If any required item is absent, metadata must keep `requires_manual_calibration` or a manual-review boundary and must not emit final calculation candidates.

## Pre-Run Confirmation Checklist

- Confirm no Origin run is requested.
- Confirm no raw vendor directory is being processed.
- Confirm no LC-MS raw decode is requested.
- Confirm the run output root.
- Confirm whether the run is candidate-only or whether calibration/mapping inputs are complete.
- Confirm that product identity claims remain blocked unless manually mapped.

## Stop Conditions

Stop the dry-run if:

- the file is a raw vendor directory;
- Origin is required to read or export the file;
- calibration or mapping is missing for requested quantification;
- the table is ambiguous and cannot be classified safely;
- output would be written outside the approved run root;
- the user asks for product identity inference from peak name or retention time alone.
