# Method Card: Agilent OpenLab HPLC/LC Raw Data

## Scope

This workflow processes Agilent OpenLab CDS result sets stored as `.rslt` directories. It directly decodes detector chromatograms in `.dx`, uses successfully processed paired `.rx` peak rows as the formal target-peak source, and independently integrates every usable `.dx` for audit and fallback. An explicit opt-in mode can copy selected result sets into the external output staging area and invoke Agilent Processing Server from the project-bundled runtime with a complete PMX method before extraction. It does not process LC-MS spectra, instrument telemetry, or create plots.

Formal entrypoint:

```powershell
python run.py hplc-openlab-export `
  --input <openlab-root> `
  --since YYYY-MM-DD `
  --output-root <external-output-root> `
  --node-exe <node.exe> `
  --builder-workdir <artifact-tool-workdir>
```

Original-vendor reprocessing is explicit. The checked-in, hash-verified OpenLab
2.5 processing bundle and default normalization-percent PMX are used when no
runtime override is supplied:

```powershell
python run.py hplc-openlab-export `
  <the arguments above> `
  --vendor-reprocess
```

## Decoder And Reused Components

- Production decoder: `project-native-agilent-openlab-dx` version `1.0.0`.
- The decoder uses Python ZIP/XML support and NumPy. It strictly accepts the verified `urn:schemas-agilent-com:acmd20` manifest and `Agilent.OpenLab.Rawdata/Signal179` integrable-signal encoding.
- For Signal179, the decoder verifies the 6,144-byte header and `\x03` + `179` signature, reads the declared count of little-endian float64 values, applies the ACMD `Slope`, and constructs the time grid from `TimeStart` through `TimeEnd` in minutes.
- Python XML/ZIP support also parses result-set `.acaml` metadata and optional paired `.rx` `Base/InjectionACAML` vendor results.
- `@oai/artifact-tool` writes, inspects, renders, and exports the final Excel workbook.

`rainbow-api` 1.3.1 may be used by the controlled decoder regression as an optional black-box numerical oracle. It is not imported by the production decoder and is not required for the default stored-`.rx` mode. The OpenLab runtime and PMX likewise remain optional for that default mode. In `--vendor-reprocess` mode, the formal command verifies and extracts the project-bundled OpenLab 2.5 processing closure, invokes Agilent's Processing Server through the checked-in bridge, and passes the complete PMX to Agilent's `ModifyAndReprocessSingleRun`; it never treats PMX as a stand-alone executable or reimplements the vendor algorithm.

Unsupported ACMD schemas, signal encodings, malformed payloads, empty integrable signals, non-finite values, or non-increasing time axes fail explicitly instead of falling back to a guessed decode.

## Vendor-Only Peak Integration

For each injection, the formal target source is selected by a fixed, versioned rule:

1. A paired `.rx` result whose OpenLab state is `Passed`, `PassedWithWarning`, or `not_recorded` is usable. Its target RT, peak ordinal, integration bounds, height, baseline fields, and area are selected inside the user-configured RT windows.
2. A successful zero-peak `.rx` is a valid vendor non-detection and contributes zero area; it is not confused with a missing result.
3. `missing_rx`, `missing_result`, unreadable results, and `NoMethodProvided` are unavailable vendor results. Those injections are not automatically quantified and require `--vendor-reprocess`.
4. Vendor availability never changes raw-signal quality classification, rerun grouping, or anomaly exclusion. It does determine whether an injection is eligible for automatic quantification.

The bundled-runtime R01 validation reprocessed all 7 injections and reproduced all 23 stored vendor peaks bit-exactly after chronological peak-ordinal normalization. For the formerly `NoMethodProvided` R16 result set, all 9 injections completed original-vendor processing and produced 31 peaks. Merely copying PMX or editing `DaMethodName` was insufficient; the formal adapter constructs a checksum-valid single-injection ACAML closure for each injection inside staging and calls Agilent's `ModifyAndReprocessSingleRun`.

The project stores the approved processing runtime as one ZIP plus a per-file
SHA-256 manifest and the selected PMX. On first use it rejects unsafe archive
paths, verifies the archive and every extracted file, and materializes the
runtime only under `.local_vendor_runtime`. Vendor mode hashes the runtime,
bridge, method, old/new RX, and original inputs, processes only copied result
sets, and aborts instead of silently falling back when the vendor call fails.

The previous project-native integrator, ChemStation-compatible candidate, PMX/native hybrid, declarative PMX reader, and their comparison scripts were removed after the original-vendor path passed the R01 and R16 gates. No project code now performs HPLC peak detection, baseline selection, or peak-area integration.

## Selection Rule

- Recursively discover `.dx` acquisitions below the requested input root.
- Read the injection-specific `InjectionAcqDateTime` from result-set `.acaml` metadata and convert it to the local UTC offset recorded by the `.dx` manifest.
- Include acquisitions whose local acquisition date is greater than or equal to `--since`.
- Do not infer the date boundary solely from a result-set or batch folder name.
- Sort included injections by acquisition timestamp and relative source path.

## Preserved Data

- Exact time and detector-signal arrays in the processed audit dataset, with no resampling, interpolation, smoothing, or baseline correction.
- OpenLab vendor peak rows, when present, including retention time, integration bounds, area, area percent, height, symmetry, and baseline fields; successful rows are the sole formal target source.
- Batch, result set, sample, vial, method, detector, wavelength, unit, point count, acquisition time, source size, relative path, and SHA-256 provenance.
- Raw signal arrays and source hashes remain in the audit dataset and are intentionally omitted from the user-facing Excel files.

An `.rx` processing state of `NoMethodProvided` does not mean that the `.dx` signal is corrupt. It means that the vendor peak source is unavailable, so the injection cannot be automatically quantified until `--vendor-reprocess` succeeds. Strict `.dx` decoding remains available for raw-signal provenance and quality checks only.

When `--vendor-reprocess` is selected, the previous state is historical input only: the copied injection must be reprocessed by Agilent with the selected complete PMX, and the newly generated `.rx` is labelled `agilent_processing_server_reprocessed_rx`. It is never mislabeled as a stored historical result.

## Seven-Sheet Excel Contract

The formal result is one compact analysis workbook with exactly these seven worksheets:

1. `样品结果`: one row per final sample after wash/pre-reaction exclusion and rerun resolution; contains batch/result-set/sample/method provenance, selected target RT/area, candidate concentrations and reaction metrics, quality status, and review reasons.
2. `峰明细`: one row per final sample. Each of the three configured components uses the adjacent column order `峰序号 → 出峰时间 → 峰面积`, followed by quality and sample/method provenance.
3. `数据处理记录`: normalization, classification, target matching, calibration, rerun selection, and calculation decisions.
4. `排除数据`: wash, pre-reaction, superseded rerun, abnormal, or otherwise excluded records and explicit reasons.
5. `重打分组明细`: every member of each rerun group, evidence, quality comparison, final-use flag, and selection method.
6. `待人工复核`: unresolved quality, unavailable vendor results, ambiguous RT, unusual calculation, and other review items.
7. `分析参数`: decoder/vendor-integration provenance, target RT windows, calibration equations, dilution factor, thresholds, date/light rules, and scientific-boundary statements.

The user-facing workbook uses one `采集方法` column because acquisition and processing method names represent the same method in this workflow. Workbook body rows are white with explicit thin gray borders and no alternating-row color fill. Raw signal points stay in the processed audit dataset rather than being crowded into Excel.

No chart sheet, Origin project, OPJU, TIF, PNG scientific figure, or other plot is expected. A seven-sheet, data-only workbook is the normal successful product; rendered worksheet previews are QA artifacts, not chromatograms or scientific figures.

## Vendor Validation

`verify_openlab_vendor_reprocessing.py` creates a JSON-only validation run on copied data. R01 requires exact peak identity and bit-exact agreement for all compared RT, bounds, width, area, area%, height, height%, symmetry, baseline values/codes/models, peak type, units, and purity flags. R16 verifies that every formerly method-free injection can be processed and produce new vendor peaks. Neither validation creates Excel or plots.

## Validation and Failure Policy

- All decoded time axes must be finite and strictly increasing.
- Every decoded signal must be finite and have the same point count as its time axis.
- Any in-scope decode failure aborts the export instead of producing a partial workbook.
- In default mode, missing `.rx` data and `NoMethodProvided` are recorded as unavailable vendor results and prohibit automatic quantification.
- In `--vendor-reprocess` mode, every selected injection must complete Agilent processing and produce a readable `.rx`; bridge, checksum, PMX, load, processing, timeout, or output failures abort the package.
- An invalid/short raw signal or failed required quality gate is recorded for manual review; successful vendor peak rows do not erase raw-signal quality evidence.
- Workbook inspection searches for formula errors and every sheet in every generated workbook is rendered to a preview for visual QA.
- Successful workbook verification requires the exact seven-sheet contract above.

## Scientific Boundary

- Vendor peak integration is not chemical identification.
- Target-window labels are user-configured candidate mappings; peak names and retention times alone are not proof of substrate or product identity.
- Concentration, conversion, selectivity, yield, and recovery are calculated only when the user-supplied calibration, dilution, formula, and analyte-role mapping are complete. They remain candidate results requiring review and are never clamped to an expected range.
- All peak identities and derived chemistry remain `manual_check_required`.

## Registry Contract

- Registry entry: `HPLC/LC OpenLab raw data`
- Selected processor: `hplc_openlab_raw_exporter`
- Special handling: `dedicated_hplc_openlab_export_command`
