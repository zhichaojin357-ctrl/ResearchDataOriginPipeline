# Method Card: Agilent OpenLab HPLC/LC Raw Data

## Scope

This workflow processes Agilent OpenLab CDS result sets stored as `.rslt` directories. It targets detector chromatograms in `.dx` files and OpenLab's existing integration results in paired `.rx` files. It does not process LC-MS spectra, instrument telemetry, or create plots.

Formal entrypoint:

```powershell
python run.py hplc-openlab-export `
  --input <openlab-root> `
  --since YYYY-MM-DD `
  --output-root <external-output-root> `
  --node-exe <node.exe> `
  --builder-workdir <artifact-tool-workdir>
```

## Reused Components

- `rainbow-api>=1.3.1,<2` decodes the OpenLab `.dx` OPC package and detector signal.
- Python's standard XML and ZIP support parses result-set `.acaml` metadata and paired `.rx` `Base/InjectionACAML` integration results.
- `@oai/artifact-tool` writes, inspects, renders, and exports the split Excel workbooks.

The project integration code connects these components and enforces project-specific date, provenance, failure, and scientific-boundary rules.

## Selection Rule

- Recursively discover `.dx` acquisitions below the requested input root.
- Read the injection-specific `InjectionAcqDateTime` from result-set `.acaml` metadata and convert it to the local UTC offset recorded by the `.dx` manifest.
- Include acquisitions whose local acquisition date is greater than or equal to `--since`.
- Do not infer the date boundary solely from a result-set or batch folder name.
- Sort included injections by acquisition timestamp and relative source path.

## Preserved Data

- Exact time and detector-signal arrays in the processed audit dataset, with no resampling, interpolation, smoothing, or baseline correction.
- OpenLab vendor peak rows including retention time, integration bounds, area, area percent, height, symmetry, and baseline fields when present.
- Batch, result set, sample, vial, method, detector, wavelength, unit, point count, acquisition time, source size, relative path, and SHA-256 provenance.
- Raw signal arrays and source hashes remain in the audit dataset and are intentionally omitted from the user-facing Excel files.

## Output Workbooks

- One summary workbook contains `使用说明`, `批次索引`, and `样品索引`.
- One batch workbook is created for each top-level acquisition batch folder.
- Every batch workbook contains `批次说明` and `样品信息`.
- Every `.rslt` result set receives its own `Rxx_峰面积` worksheet inside the corresponding batch workbook.
- User-facing columns prioritize batch/result-set names, sample name, acquisition time, acquisition and processing methods, detector/wavelength, peak count, peak area, area percent, and height.
- Workbook body cells use a white background with explicit thin gray borders. No alternating-row color style is applied.
- The raw time/signal points are decoded and verified but not listed in Excel by default.

The workflow produces no chart sheets and never launches Origin.

## Validation and Failure Policy

- All decoded time axes must be finite and strictly increasing.
- Every decoded signal must be finite and have the same point count as its time axis.
- Any in-scope decode failure aborts the export instead of producing a partial workbook.
- Missing `.rx` data is recorded as a missing vendor result; the workflow does not invent replacement peaks.
- Workbook inspection searches for formula errors and every sheet in every generated workbook is rendered to a preview for visual QA.

## Scientific Boundary

- Vendor peak integration is not chemical identification.
- Peak names and retention times are not promoted to substrate or product identities.
- No concentration, conversion, selectivity, or yield is calculated without calibration, response factors, dilution rules, and analyte-role mapping supplied by the user.
- All peak rows remain `manual_check_required`.

## Registry Contract

- Registry entry: `HPLC/LC OpenLab raw data`
- Selected processor: `hplc_openlab_raw_exporter`
- Special handling: `dedicated_hplc_openlab_export_command`
