# HPLC/LC Acceptance Criteria

Updated: 2026-08-02

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

The formal command `python run.py hplc-openlab-export` may process `.rslt` result sets containing `.dx`, optional `.rx`, and `.acaml` components.

Allowed behavior:

- Determine the inclusive date boundary from each result-set injection timestamp, converted to the local offset recorded by its `.dx` manifest, not only from folder names.
- Decode detector chromatograms with the project-native strict OPC/ACMD20/Signal179 decoder, version `1.0.0`.
- Require the verified ACMD20 namespace, Signal179 encoding, declared payload size, 6,144-byte header/signature, finite signal values, and a strictly increasing time grid; reject unsupported variants explicitly.
- Preserve each signal's exact time grid and measured values in the processed audit dataset without interpolation, resampling, smoothing, or baseline correction.
- Read only successful OpenLab `.rx` integration rows as target-peak measurements; the project does not implement or retain a native peak-integration fallback.
- In default mode, record missing, unreadable, failed, or `NoMethodProvided` vendor results as unavailable and prohibit automatic quantification. In explicit vendor mode, derive a checksum-valid single-injection ACAML only in staging and require Agilent's Processing Server to produce a new `.rx` with the selected complete PMX.
- Preserve sample, vial, method, detector, wavelength, point-count, source hash, and result-set provenance.
- Write one data-only analysis workbook with exactly seven sheets: `样品结果`, `峰明细`, `数据处理记录`, `排除数据`, `重打分组明细`, `待人工复核`, and `分析参数`.
- Keep one row per final sample in `样品结果`; retain every injection/rerun/exclusion decision in the audit sheets instead of duplicating final samples.
- Keep one row per final sample in `峰明细`; for each configured component, place peak ordinal immediately before peak time and peak area.
- Represent acquisition/processing method as one user-facing `方法` column while retaining source provenance in the processed audit dataset.
- In `峰明细`, place peak ordinal immediately before peak time and retain area, target matching, candidate concentrations, and sample/method provenance.
- Keep raw signal points out of the user-facing Excel files unless a later request explicitly asks for them.
- Use plain white data rows with explicit thin gray cell borders and no alternating-row color style.
- Write metadata, verification records, and a rendered preview of every one of the seven sheets under the configured external output root.

Required failure behavior:

- Fail the run when any in-scope `.dx` acquisition cannot be decoded completely.
- Fail when the workbook builder or workbook verification step fails.
- Fail workbook verification if the required seven-sheet contract is incomplete or formula-error inspection fails.
- Never create a project-integrated peak when the vendor result is unavailable. In default mode, such injections remain unquantified; in explicit vendor mode, any missing/failed new `.rx` aborts the package.
- Treat a successful zero-peak `.rx` as a valid vendor non-detection, not as a missing result.
- Vendor-result availability must not alter raw-signal quality classification, rerun grouping, or anomaly exclusion; unavailable results make the affected injection ineligible for automatic quantification.
- Never execute or claim to execute a `.pmx` independently. The optional `--vendor-reprocess` path passes the checked-in complete PMX to Agilent `ModifyAndReprocessSingleRun`; that is vendor execution.

### Vendor integration contract

The only accepted peak-integration sources are:

- a successful stored Agilent OpenLab `.rx`; or
- a new `.rx` produced on a copied result set by the bundled Agilent Processing Server with the complete selected PMX.

R01 validation must retain bit-exact peak identity and fields after chronological ordinal normalization. Formerly unprocessed R16 data must complete every selected injection through the original Processing Server. Runtime, method, source, and old/new result hashes remain auditable.

Raw `.dx` time/signal arrays remain unchanged for provenance and quality checks. They are not smoothed, baseline-corrected, peak-picked, or integrated by project code.

Scientific boundary:

- OpenLab peak rows are integration measurements, not chemical identities.
- A configured RT window is a candidate user mapping and must not be promoted to product identity without the user's supporting evidence.
- Calibration, analyte-role mapping, response factors, dilution/volume rules, and explicit formulas are required before candidate concentration, conversion, selectivity, yield, or recovery values can be calculated.
- Derived values are not clamped to `0–100%`; unusual values are preserved and flagged for manual review.
- Instrument telemetry channels are excluded from this Excel workflow unless a separate request defines their scope.

## Output Contract

- Raw input is read-only.
- Formal outputs stay under an explicit external output root and never inside the raw-data tree.
- The OpenLab raw workflow normally produces the seven-sheet data workbook and no Origin, OPJU, chart, or scientific figure. Absence of a plot is expected, not a fallback or incomplete success.
- Workbook previews are verification artifacts only and are not scientific plots.
- All peak identities and derived chemistry remain manual-review records until supported by user-supplied evidence.
