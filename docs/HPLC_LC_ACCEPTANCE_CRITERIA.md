# HPLC/LC Acceptance Criteria

Updated: 2026-07-24

This contract covers exported HPLC/LC tables and the dedicated Agilent OpenLab raw-data export command. Raw decoding does not authorize Origin execution, plotting, automatic chemical identity, or unsupported quantitative conclusions.

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

## F. Agilent OpenLab Raw Result Sets

The formal command `python run.py hplc-openlab-export` may process `.rslt` result sets containing `.dx`, `.rx`, and `.acaml` components.

Allowed behavior:

- Determine the inclusive date boundary from each result-set injection timestamp, converted to the local offset recorded by its `.dx` manifest, not only from folder names.
- Decode detector chromatograms from `.dx` with `rainbow-api>=1.3.1`.
- Preserve each signal's exact time grid and measured values in the processed audit dataset without interpolation, resampling, smoothing, or baseline correction.
- Read OpenLab's existing integration results from paired `.rx` files.
- Preserve sample, vial, method, detector, wavelength, point-count, source hash, and result-set provenance.
- Write one summary workbook plus one workbook per top-level acquisition batch folder.
- Put sample metadata in a dedicated sheet and create one peak-area sheet per `.rslt` result set.
- Keep raw signal points out of the user-facing Excel files unless a later request explicitly asks for them.
- Use plain white data rows with explicit thin gray cell borders and no alternating-row color style.
- Write metadata, verification records, and a preview of every generated sheet under the configured external output root.

Required failure behavior:

- Fail the run when any in-scope `.dx` acquisition cannot be decoded completely.
- Fail when the workbook builder or workbook verification step fails.
- Never silently replace a missing `.rx` file with newly guessed peaks; record the missing vendor result instead.

Scientific boundary:

- OpenLab peak rows remain vendor integration results, not chemical identities.
- Retention time and source peak names must not be promoted to product identity.
- Calibration, analyte-role mapping, response factors, and dilution rules are required before concentration, conversion, selectivity, or yield can be reported.
- Instrument telemetry channels are excluded from this Excel workflow unless a separate request defines their scope.

## Output Contract

- Raw input is read-only.
- Formal outputs stay under an explicit external output root and never inside the raw-data tree.
- The OpenLab raw workflow produces no Origin, OPJU, chart, or scientific figure.
- Workbook previews are verification artifacts only and are not scientific plots.
- All peak identities and derived chemistry remain manual-review records until supported by user-supplied evidence.
