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
- Detect and integrate peaks with `project-native-hplc-target-integrator` version `1.1.0`; label every such peak `peak_source=native_dx` and retain its algorithm version and integration audit fields.
- Read available OpenLab `.rx` integration rows as validation evidence, while keeping them distinct from native results.
- Process a strictly decoded `NoMethodProvided` acquisition through native integration. The absence of an OpenLab processing method is not, by itself, raw-data corruption or a reason to discard the signal.
- Preserve sample, vial, method, detector, wavelength, point-count, source hash, and result-set provenance.
- Write one data-only analysis workbook with exactly seven sheets: `样品结果`, `峰明细`, `数据处理记录`, `排除数据`, `重打分组明细`, `待人工复核`, and `分析参数`.
- Keep one row per final sample in `样品结果`; retain every injection/rerun/exclusion decision in the audit sheets instead of duplicating final samples.
- Represent acquisition/processing method as one user-facing `方法` column while retaining source provenance in the processed audit dataset.
- In `峰明细`, place peak ordinal immediately before retention time and retain bounds, height, area, source, integrator version, target matching, and optional vendor-comparison fields.
- Keep raw signal points out of the user-facing Excel files unless a later request explicitly asks for them.
- Use plain white data rows with explicit thin gray cell borders and no alternating-row color style.
- Write metadata, verification records, and a rendered preview of every one of the seven sheets under the configured external output root.

Required failure behavior:

- Fail the run when any in-scope `.dx` acquisition cannot be decoded completely.
- Fail when the workbook builder or workbook verification step fails.
- Fail workbook verification if the required seven-sheet contract is incomplete or formula-error inspection fails.
- Never label a native result as a vendor result. If `.rx` is missing or reports `NoMethodProvided`, record that vendor validation is unavailable and use only the separately labelled native result.
- Treat an unreadable optional `.rx` as unavailable vendor-comparison evidence; record the parse error without blocking a valid `.dx` decode/integration.
- Keep `.rx` comparison strictly side-channel: its presence, absence, area difference, or detection difference may add a validation-review record but must not alter native signal quality, rerun selection, calculated native values, or the final-use set.
- Never execute or claim to execute a `.pmx` processing method independently. OpenLab, Agilent assemblies, MestReNova, and `.pmx` files are not required by the production decoder/integrator.

### Native integration method contract

The version `1.1.0` native integrator must use the checked-in analysis configuration and record effective parameters in `分析参数`:

- 9-point, third-order Savitzky-Golay smoothing for extrema detection only;
- morphological baseline half-window `0.40 min`;
- minimum corrected height `1.70 mAU`;
- minimum base width `0.02 min`;
- minimum integrated area `1.0 mAU·s`;
- nearest local-minimum bounds and a straight line between the estimated baseline endpoint values for an isolated peak;
- one common straight baseline between the outer endpoint values of adjacent accepted peaks that share a valley, with the valley retained as a vertical peak-allocation boundary only when every internal valley remains above that common baseline; otherwise split the chain recursively at the lowest nonpositive drop;
- trapezoidal integration of the unsmoothed signal with minutes converted to seconds;
- configured target RT windows, nearest-RT selection, and ambiguity reporting when multiple candidates occur.

Smoothing must not overwrite the preserved raw signal. Missing local maxima/bounds, rejected candidates, multiple candidates, and data-quality failures must remain auditable and must not be replaced with a window-edge maximum or another silent fallback.

For each shared-cluster allocation, retain the corresponding individual-baseline area and mark the baseline model uncertain. If any proposed shared allocation is non-finite or below the configured minimum area, reject that allocation for the entire cluster and retain the individual-baseline results.

### Vendor comparison and holdout gates

Available `.rx` rows are numerical oracles only. Vendor-boundary reconstruction uses the raw signal inside `BeginTime`/`EndTime`, subtracts the straight line from `BaselineStart` to `BaselineEnd`, applies trapezoidal integration, and converts minutes to seconds. It must satisfy:

- all-peak median APE `<= 0.1%`;
- all-peak P95 APE `<= 0.5%`;
- all-peak maximum APE `<= 3.0%`;
- each configured target's P95 APE `<= 0.1%`.

Algorithm tuning and acceptance data must be separated by complete result sets. The current controlled split is training through `2026-07-21` and locked holdout from `2026-07-23`. For each configured target, holdout acceptance requires:

- sensitivity and specificity `>= 0.99`;
- RT absolute-error P95 `<= 0.01 min`;
- area APE median `<= 2%`;
- area APE P90 `<= 5%`;
- area APE P95 `<= 10%`.

Any native/vendor detection disagreement or target-area APE over `15%` must be written as a vendor side-channel item in `待人工复核`; it must not be hidden by averaging, substituted for the native value, or allowed to change final-use selection. Ambiguous native target matching remains a native quality review condition.

Scientific boundary:

- Native and OpenLab peak rows are integration measurements, not chemical identities.
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
