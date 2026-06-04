# HPLC/LC Acceptance Criteria

Date: 2026-06-04

This contract applies only to exported HPLC/LC tabular data. It does not allow raw vendor decoding, Origin execution, real-data processing, or automatic chemical conclusions.

## A. Chromatogram Exported Data

An exported table may produce a chromatogram candidate when it contains:

- time or retention-time values;
- detector signal, intensity, absorbance, or mAU values.

Allowed behavior:

- Use time or retention time as the x-axis.
- Use signal, intensity, absorbance, or detector response as the y-axis.
- Preserve detectable units in metadata when present.
- Record `chromatogram` plot intent.

Forbidden behavior:

- Do not automatically identify peaks.
- Do not assert product identity.
- Do not calculate conversion.
- Do not infer chromatographic purity.

## B. Peak Table Exported Data

An exported table may produce a peak-table summary candidate when it contains:

- retention time;
- area;
- height;
- optional peak name;
- optional integration metadata.

Allowed behavior:

- Preserve peak rows.
- Mark rows as candidate peaks only.
- Record area and height values.
- Preserve source-table provenance in metadata.

Forbidden behavior:

- Do not use peak name as product identity.
- Do not use retention time as product identity.
- Do not compute true concentration, conversion, selectivity, or yield without calibration and mapping.

## C. Calibration / Standard Curve

A calibration table may produce a standard-curve candidate only when it contains:

- concentration;
- response or peak area;
- analyte name or explicit manual mapping;
- optional replicate or sample information.

Allowed behavior:

- Fit a candidate linear calibration.
- Record candidate slope, intercept, and R squared.
- Mark the candidate as requiring manual check.
- Preserve analyte or manual-mapping provenance.

Forbidden behavior:

- Do not force quantification when no calibration table exists.
- Do not convert peak area to concentration without analyte mapping.
- Do not treat peak name as final product identity.

## D. Conversion / Selectivity / Yield

Candidate conversion, selectivity, or yield calculations are allowed only when all required inputs are present:

- calibration;
- analyte mapping;
- substrate/product role mapping;
- dilution, volume, and concentration rules;
- or an explicit user-provided manual mapping that supplies the missing pieces.

If any required input is missing:

- Output only peak-table or chromatogram candidates.
- Record `requires_manual_calibration`.
- Do not emit final conversion, selectivity, or yield.

## E. Ambiguous Exported Table

If exported columns do not clearly identify chromatogram, peak table, or calibration data:

- Do not generate a plot candidate.
- Mark the table for manual review.
- Record missing fields.
- Do not guess a mode from generic numeric columns.

## Output Contract

- Synthetic tests may write processed CSV and metadata only under a temporary run root.
- No repository `output/` or `outputs/` paths may be modified by this goal.
- Origin artifacts are out of scope: no OPJU, TIF, PNG, PDF, XLSX, ZIP, or large JSON artifacts.
- All scientific outputs remain candidate/provenance records until manually reviewed.
