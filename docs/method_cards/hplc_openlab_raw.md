# Method Card: Agilent OpenLab HPLC/LC Raw Data

## Scope

This workflow processes Agilent OpenLab CDS result sets stored as `.rslt` directories. It directly decodes detector chromatograms in `.dx`, independently detects and integrates configured HPLC target peaks, and uses paired `.rx` peak rows only as optional validation evidence. It does not process LC-MS spectra, instrument telemetry, or create plots.

Formal entrypoint:

```powershell
python run.py hplc-openlab-export `
  --input <openlab-root> `
  --since YYYY-MM-DD `
  --output-root <external-output-root> `
  --node-exe <node.exe> `
  --builder-workdir <artifact-tool-workdir>
```

## Decoder And Reused Components

- Production decoder: `project-native-agilent-openlab-dx` version `1.0.0`.
- The decoder uses Python ZIP/XML support and NumPy. It strictly accepts the verified `urn:schemas-agilent-com:acmd20` manifest and `Agilent.OpenLab.Rawdata/Signal179` integrable-signal encoding.
- For Signal179, the decoder verifies the 6,144-byte header and `\x03` + `179` signature, reads the declared count of little-endian float64 values, applies the ACMD `Slope`, and constructs the time grid from `TimeStart` through `TimeEnd` in minutes.
- SciPy and pybaselines provide public-API smoothing, local-extrema, and morphological-baseline operations for the native integrator.
- Python XML/ZIP support also parses result-set `.acaml` metadata and optional paired `.rx` `Base/InjectionACAML` vendor results.
- `@oai/artifact-tool` writes, inspects, renders, and exports the final Excel workbook.

`rainbow-api` 1.3.1 may be used by the controlled decoder regression as an optional black-box numerical oracle. It is not imported by the production path and is not required to run the formal command. OpenLab, MestReNova, Agilent assemblies, and `.pmx` processing methods are also not production dependencies. The project does not claim that a `.pmx` file can be executed independently. A standard-library-only PMX reader may extract declarative settings for the controlled candidate comparison described below; it never loads vendor assemblies or treats PMX as an executable engine.

Unsupported ACMD schemas, signal encodings, malformed payloads, empty integrable signals, non-finite values, or non-increasing time axes fail explicitly instead of falling back to a guessed decode.

## Native Peak Integration

Production integrator: `project-native-hplc-target-integrator` version `1.1.0`.

The versioned algorithm is configured in `config/hplc_openlab_analysis.yaml`:

1. Preserve the decoded raw time/signal arrays unchanged for provenance.
2. Apply a 9-point, third-order Savitzky-Golay filter only for apex/minimum detection.
3. Estimate an independent morphological baseline with a `0.40 min` half-window.
4. Accept true local maxima with baseline-corrected height at least `1.70 mAU`.
5. Use the nearest smoothed local minima as initial peak bounds; require base width at least `0.02 min`.
6. For an isolated peak, interpolate a straight integration baseline between the morphological-baseline values at the two bounds.
7. When adjacent accepted peaks share the same valley bound, propose one common straight baseline between the cluster's outer morphological endpoints. Retain a shared valley as a vertical drop-line only if it lies above that common line; recursively split at the lowest valley that lies on or below the proposed baseline. Cluster membership is structural and uses no fitted tolerance or vendor result.
8. Integrate the unsmoothed signal minus the allocated line with the trapezoidal rule and multiply minutes by 60, producing `mAU·s`; reject areas below `1.0 mAU·s`.
9. Match targets inside their configured RT windows. Multiple candidates remain auditable, the nearest RT is selected for the one-row result, and close alternatives are flagged as ambiguous.

The allocation model follows Agilent's documented baseline/valley semantics rather than a fitted sample-name rule: the [OpenLab Data Analysis Reference Guide](https://www.agilent.com/cs/library/usermanuals/public/CDS_v2.8_DataAnalysisReferenceGuide_en.pdf) describes a common baseline with vertical valley drop-lines for unresolved peak clusters, and the [OpenLab baseline-code reference](https://openlab.help.agilent.com/en/mergedProjects/DataAnalysis/54043198932979595.htm) defines `V` as a valley drop-line. The surrounding implementation also follows the independently documented pattern of finding boundaries on a smoothed trace while integrating the raw chromatogram, as used by [OpenMS PeakPickerChromatogram](https://github.com/OpenMS/OpenMS/blob/develop/src/openms/source/ANALYSIS/OPENSWATH/PeakPickerChromatogram.cpp), and keeps baseline estimation in the BSD-licensed [pybaselines](https://pybaselines.readthedocs.io/en/stable/algorithms/morphological.html) package. [MOCCA2's peak finder](https://github.com/Bayer-Group/MOCCA/blob/main/src/mocca2/peaks/find_peaks.py) was reviewed as an independent prominence/noise-aware boundary and merge/split reference, but it is not a production dependency and its parameters were not fitted into this decoder.

Anti-overfit controls are explicit. A wider `0.50 min` morphology window was rejected because it improved training-set sulfone error but worsened the date-grouped holdout. Replacing every endpoint with the raw signal was also rejected because it failed on valley-separated clusters. Version `1.1.0` changes only the parameter-free shared-valley allocation rule; target RT windows, detection thresholds, smoothing, morphology window, and raw-signal integration remain unchanged. Because the historical holdout was inspected while confirming this version, it is now a confirmation set rather than a blind set; a future blind-performance claim requires newly acquired, complete result sets.

Every native peak is labelled `peak_source=native_dx` and retains integrator name/version, bounds, baseline, height, area, and manual-review status. Candidates rejected after passing the height gate remain in `analysis.native_rejected_candidates` with injection provenance, retention time, height, and rejection reason. A shared-cluster allocation additionally retains the original individual-baseline area and `baseline_model_uncertain=true`, because raw geometry alone cannot always distinguish a true valley drop-line from two baseline-resolved peaks. Native integration is not presented as an OpenLab vendor result.

## PMX-Configured ChemStation-Compatible Candidate

`src/core/agilent_pmx.py` independently reads the enabled transformation chain from a PMX ZIP/XML package. For the current corpus it selects the enabled `TwelveToneIntegratorTransformation64`, not the disabled EZChrom transform or the manual integration transform. The corpus audit parses every PMX copy and requires one effective integration-policy signature before comparison.

The current PMX settings are slope sensitivity `1`, initial peak width `0.02 min`, area reject `1 mAU*s`, height reject `1.7 mAU`, area-percent reject `0`, shoulders off, Advanced baseline correction, Peak-to-Valley `500`, no timed events, no signal smoothing, and front/tail skim height ratios `0`. Because the method disables shoulders and skim, the candidate does not invent those branches.

`src/core/hplc_chemstation_integration.py` is a labelled non-production candidate. It implements the published three recognition-filter spans, deterministic bunching resolution, up/down accumulators with threshold `15`, parabolic apex time, dynamic LC peak-width update, Advanced non-penetrating pegs-and-thread surrogate, Peak-to-Valley allocation, raw-signal trapezoidal area, and PMX reject events. Because Agilent does not disclose the baseline-cone normalization, the candidate also has an explicitly labelled `surrogate_stable_return_to_baseline` end condition; every peak records whether its cluster ended through the documented accumulator/envelope path, this surrogate, overlap merging, or end-of-signal. It records `validation_status=candidate` and `vendor_equivalent=false`.

Agilent does not publish the exact recognition-filter coefficients and normalization, the overlap/hysteresis choices in the bunching table, the response-unit mapping of slope sensitivity, or the objective function used by Advanced baseline optimization. Therefore the candidate is an independent compatibility experiment, not an OpenLab clone. The controlled comparator requires identical input fingerprints, local PMX coverage for every vendor-validation result set, paired detection/RT/relative-and-absolute-area/outlier non-regression, at least one material improvement, and a separately registered fresh blind dataset. The current historical holdout can never auto-promote a candidate. The comparator is `scripts/data_types/hplc_lc/compare_chemstation_candidate.py`.

## Selection Rule

- Recursively discover `.dx` acquisitions below the requested input root.
- Read the injection-specific `InjectionAcqDateTime` from result-set `.acaml` metadata and convert it to the local UTC offset recorded by the `.dx` manifest.
- Include acquisitions whose local acquisition date is greater than or equal to `--since`.
- Do not infer the date boundary solely from a result-set or batch folder name.
- Sort included injections by acquisition timestamp and relative source path.

## Preserved Data

- Exact time and detector-signal arrays in the processed audit dataset, with no resampling, interpolation, smoothing, or baseline correction.
- Native peak rows and target matches, including source, algorithm version, retention time, integration bounds, area, height, and baseline fields.
- OpenLab vendor peak rows, when present, including retention time, integration bounds, area, area percent, height, symmetry, and baseline fields; these are retained separately for validation.
- Batch, result set, sample, vial, method, detector, wavelength, unit, point count, acquisition time, source size, relative path, and SHA-256 provenance.
- Raw signal arrays and source hashes remain in the audit dataset and are intentionally omitted from the user-facing Excel files.

An `.rx` processing state of `NoMethodProvided` does not mean that the `.dx` signal is corrupt. When strict decoding and native integration succeed, those acquisitions are processed from `native_dx` and remain subject to the same data-quality and manual-review rules. A missing, unreadable, or method-free `.rx` only means that vendor comparison evidence is unavailable. Vendor presence and comparison differences are side-channel diagnostics and cannot change native quality, rerun selection, native values, or the final-use set.

## Seven-Sheet Excel Contract

The formal result is one compact analysis workbook with exactly these seven worksheets:

1. `样品结果`: one row per final sample after wash/pre-reaction exclusion and rerun resolution; contains batch/result-set/sample/method provenance, selected target RT/area, candidate concentrations and reaction metrics, quality status, and review reasons.
2. `峰明细`: auditable native peak details. Peak ordinal is followed by retention time, then bounds, height, area, source, algorithm version, target match, and vendor-comparison fields where available.
3. `数据处理记录`: normalization, classification, target matching, calibration, rerun selection, and calculation decisions.
4. `排除数据`: wash, pre-reaction, superseded rerun, abnormal, or otherwise excluded records and explicit reasons.
5. `重打分组明细`: every member of each rerun group, evidence, quality comparison, final-use flag, and selection method.
6. `待人工复核`: unresolved quality, ambiguous RT, native/vendor disagreement, unusual calculation, and other review items.
7. `分析参数`: decoder/integrator versions, target RT windows, calibration equations, dilution factor, thresholds, date/light rules, and scientific-boundary statements.

The user-facing workbook uses one `采集方法` column because acquisition and processing method names represent the same method in this workflow. Workbook body rows are white with explicit thin gray borders and no alternating-row color fill. Raw signal points stay in the processed audit dataset rather than being crowded into Excel.

No chart sheet, Origin project, OPJU, TIF, PNG scientific figure, or other plot is expected. A seven-sheet, data-only workbook is the normal successful product; rendered worksheet previews are QA artifacts, not chromatograms or scientific figures.

## Validation And Vendor Comparison

The controlled validation command groups complete result sets by acquisition date so tuning and holdout injections are not mixed:

- training: acquisition date through `2026-07-21`;
- locked holdout: acquisition date from `2026-07-23` onward.

Vendor rows are numerical comparison evidence only. Recalculation using vendor `BeginTime`, `EndTime`, and the linear `BaselineStart`/`BaselineEnd` fields must meet all of these gates:

- all-peak median APE no more than `0.1%`;
- all-peak P95 APE no more than `0.5%`;
- all-peak maximum APE no more than `3.0%`;
- each configured target's P95 APE no more than `0.1%`.

The independent target detector/integrator must meet, for every configured target on the locked holdout:

- sensitivity at least `0.99`;
- specificity at least `0.99`;
- RT absolute-error P95 no more than `0.01 min`;
- area APE median no more than `2%`;
- area APE P90 no more than `5%`;
- area APE P95 no more than `10%`.

A native/vendor target-area APE above `15%`, a detection disagreement, or ambiguous target matching creates an explicit manual-review item. These thresholds validate reproducibility against available vendor results; they do not make OpenLab the production computation source.

## Validation and Failure Policy

- All decoded time axes must be finite and strictly increasing.
- Every decoded signal must be finite and have the same point count as its time axis.
- Any in-scope decode failure aborts the export instead of producing a partial workbook.
- Missing `.rx` data and `NoMethodProvided` are recorded as unavailable vendor evidence and do not block a valid native decode/integration.
- Native integration failure, an invalid/short signal, or a failed required quality gate is recorded for manual review and cannot be silently replaced by vendor values.
- Workbook inspection searches for formula errors and every sheet in every generated workbook is rendered to a preview for visual QA.
- Successful workbook verification requires the exact seven-sheet contract above.

## Scientific Boundary

- Native or vendor peak integration is not chemical identification.
- Target-window labels are user-configured candidate mappings; peak names and retention times alone are not proof of substrate or product identity.
- Concentration, conversion, selectivity, yield, and recovery are calculated only when the user-supplied calibration, dilution, formula, and analyte-role mapping are complete. They remain candidate results requiring review and are never clamped to an expected range.
- All peak identities and derived chemistry remain `manual_check_required`.

## Registry Contract

- Registry entry: `HPLC/LC OpenLab raw data`
- Selected processor: `hplc_openlab_raw_exporter`
- Special handling: `dedicated_hplc_openlab_export_command`
