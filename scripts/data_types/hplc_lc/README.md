# HPLC/LC Scripts

HPLC/LC-specific helpers here are either internal to a formal HPLC/LC command
or narrowly scoped regression/rebuild tools. They are not additional generic
data-processing entrypoints.

Current scripts:

- `plot_hplc_calibration_origin.ps1`: controlled regression/rebuild tool for the three fixed anisole calibration datasets and a user-selected HPLC calibration OPJU. It is not a reader for arbitrary HPLC data and must not substitute for a formal OpenLab or exported-table result.
- `build_openlab_workbook.mjs`: internal `@oai/artifact-tool` workbook builder used by `python run.py hplc-openlab-export`; it is not a standalone raw-data entrypoint.
- `validate_agilent_dx_decoder.py`: controlled regression validator for the in-repository `.dx` decoder against the independently installed `rainbow-api` oracle. It never supplies production decode values.
- `openlab_vendor_bridge/OpenLabVendorBridge.cs`: .NET Framework bridge used by the explicit `--vendor-reprocess` path. It calls Agilent `ModifyAndReprocessSingleRun` with the checked-in complete PMX against checksum-valid single-injection ACAML files in an isolated copied result set. The matching, conservative OpenLab 2.5 processing closure is stored as one hash-verified project archive and materialized only under `.local_vendor_runtime`.
- `openlab_vendor_bridge/runtime_bundle.py`: controlled archive builder/verifier for the bundled OpenLab processing closure. It is not a data-processing entrypoint.
- `verify_openlab_vendor_reprocessing.py`: JSON-only feasibility/equivalence check. It runs the bundled Agilent Processing Server against copied result sets and creates neither Excel nor plots.

The OpenLab command decodes `.dx` chromatograms with the in-repository native decoder, but peak integration is vendor-only. Default mode accepts successful stored `.rx`; explicit vendor mode regenerates `.rx` on result-set copies by calling Agilent's original Processing Server with the selected complete PMX. Missing vendor results remain unquantified and never fall back to project peak integration. The main sheet consolidates each final sample or repeat group to one row and has one `采集方法` column. Peak detail places `峰序号` immediately before `出峰时间(min)`. Processing logs, exclusions, repeat grouping, manual-review items, and analysis parameters live on separate sheets. Decoded raw signal points remain in the audit dataset instead of being crowded into Excel. The command intentionally creates no plots and must be invoked through `run.py`.
