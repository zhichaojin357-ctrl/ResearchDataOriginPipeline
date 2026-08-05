# OpenLab vendor bridge

`OpenLabVendorBridge.cs` is a small .NET Framework bridge to Agilent's original
OpenLab Processing Server. It does not reimplement the vendor integrator.

The repository contains a hash-verified OpenLab Data Analysis 2.5 processing
bundle at `vendor/agilent_openlab_processing/2.5`. The formal workflow verifies
the archive and every payload file, extracts it under the ignored
`.local_vendor_runtime` cache, and invokes the compiled bridge from that cache:

```text
OpenLabVendorBridge.exe <work-area> <method-relative> <jobs.tsv> <report-json>
```

`<work-area>` must be an isolated copy under the pipeline output directory.
The remaining arguments are paths relative to that copy. `jobs.tsv` has no
header; each row is:

```text
single_acaml_relative<TAB>injection_guid<TAB>raw_dx_relative
```

For every row the bridge verifies the ACAML checksum. If a *derived,
single-injection* job ACAML has an invalid checksum (for example after the
formal adapter has structurally cropped it), the bridge regenerates its
embedded checksum inside `<work-area>` and records `checksum_rebuilt: true` in
the report. It then requires exactly one injection from OpenLab's `DataAccess`, and calls the original
`ModifyAndReprocessSingleRun` operation with the complete `.pmx` processing
method. It records the vendor processing log and requires the paired `.rx` to
exist. Warnings are reported but are not failures; any load error, processing
failure, invalid job, or missing `.rx` produces a non-zero exit code.

The bridge rejects absolute and `..` job paths and never starts from, deletes,
or writes outside `<work-area>`. It relies on `DataAnalysisClient` to manage
its own local Processing Server connection and does not enumerate or terminate
existing OpenLab processes.

The formal caller may split a multi-injection result set (including the R16
case) into derived one-injection ACAML job files before calling this bridge.

`runtime_bundle.py verify` verifies the checked-in archive and every archived
file against `manifest.json`. `runtime_bundle.py build` is the controlled
maintainer command for rebuilding the single archive from an approved runtime
payload; it is not a data-processing entrypoint.
