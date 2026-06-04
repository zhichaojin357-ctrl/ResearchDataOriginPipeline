# Method Card: HPLC/LC Exported Data

## Scope

This method card covers exported HPLC/LC tabular data only:

- chromatogram exports;
- peak table exports;
- calibration or standard-curve exports;
- ambiguous exported tables that require manual review.

Raw vendor directories and raw mass-spectrometry files are out of scope.

## Supported File Formats

- `.csv`
- `.txt`
- `.xlsx`
- `.xls`

The file must be an exported table with readable columns. Proprietary raw formats such as Agilent `.d`, Waters `.raw`, and LC-MS raw data are not decoded by this processor.

## Recognition Signals

Chromatogram table:

- time, retention time, or RT column;
- signal, intensity, absorbance, detector response, or mAU column.

Peak table:

- retention time or RT column;
- area or peak area column;
- height or peak height column;
- optional peak name or integration metadata.

Calibration table:

- concentration or standard concentration column;
- response, area, or peak area column;
- analyte or manual mapping column.

Ambiguous table:

- missing time or retention-time fields;
- missing signal, area, height, response, or calibration fields;
- unable to separate chromatogram, peak table, and calibration table intent.

## Processing Contract

The processor may emit candidate-level records only:

- `lc_export_mode`;
- `lc_plot_intent`;
- `lc_candidate_peaks`;
- `lc_calibration_candidate`;
- `lc_quantification_boundary`;
- `lc_missing_fields`;
- manual-review warnings and metadata provenance.

The processor must not emit final scientific conclusions.

## Candidate Outputs

Chromatogram candidate:

- x-axis: retention time or time;
- y-axis: signal, intensity, absorbance, or detector response;
- plot intent: `chromatogram`;
- no peak identity or product identity assignment.

Peak table candidate:

- preserve retention time, area, height, and optional peak name;
- plot intent: `peak_table_summary`;
- mark peak identity as `unassigned_manual_mapping_required`;
- no product identity assignment from peak name or retention time.

Calibration candidate:

- fit a linear candidate when concentration and response are present;
- record slope, intercept, R squared, point count, analyte, and fit method;
- plot intent: `calibration_curve`;
- mark manual check required.

Ambiguous exported table:

- processing status: `manual_review`;
- plot intent: no candidate;
- record missing fields and manual-review reason.

## Quantification Boundary

Conversion, selectivity, yield, and final concentration are blocked unless all required inputs are present:

- calibration;
- analyte mapping;
- substrate/product role mapping;
- dilution, volume, concentration, and response-factor rules;
- explicit user-provided manual mapping where needed.

Without those inputs, the processor may preserve the table and emit candidate metadata only. It must record `requires_manual_calibration` or an equivalent manual-review boundary.

## Manual Checks Required

- Confirm source file is an exported table, not a raw vendor directory.
- Confirm detector, wavelength, units, and integration settings.
- Confirm peak identity using a user-provided mapping or validated standard.
- Confirm calibration curve and response factors.
- Confirm dilution, volume, concentration, and role rules before any conversion, selectivity, or yield calculation.
- Confirm any real-data result before plotting or reporting.

## Forbidden Claims

- Do not identify products from peak names.
- Do not identify products from retention time.
- Do not calculate real conversion without calibration and manual mapping.
- Do not calculate real selectivity without calibration and manual mapping.
- Do not calculate real yield without calibration and manual mapping.
- Do not infer reaction completion.
- Do not decode Agilent `.d`, Waters `.raw`, or LC-MS raw data in this module.

## Output and Origin Policy

- Synthetic and no-Origin tests must write only to a temporary run root.
- Repository `output/` and `outputs/` must remain untouched during synthetic tests.
- Origin is not required for no-Origin candidate processing.
- OPJU, TIF, PNG, PDF, XLSX, ZIP, and large JSON artifacts are not produced by this no-Origin module completion goal.

## Implementation Status

- Registry entry: `HPLC/LC exported data`
- Selected processor: `lc_exported_data_processor`
- Candidate helper location: `src/processors/calculations.py`
- Processor integration: `src/processors/base.py`
- Contract tests: `tests/test_hplc_lc_contracts.py`
- Process integration tests: `tests/test_hplc_lc_process_integration.py`
- Output routing tests: `tests/test_hplc_lc_output_routing.py`
