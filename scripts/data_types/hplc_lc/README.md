# HPLC/LC Scripts

HPLC/LC-specific helpers here are either internal to a formal HPLC/LC command
or narrowly scoped regression/rebuild tools. They are not additional generic
data-processing entrypoints.

Current scripts:

- `plot_hplc_calibration_origin.ps1`: controlled regression/rebuild tool for the three fixed anisole calibration datasets and a user-selected HPLC calibration OPJU. It is not a reader for arbitrary HPLC data and must not substitute for a formal OpenLab or exported-table result.
- `build_openlab_workbook.mjs`: internal `@oai/artifact-tool` workbook builder used by `python run.py hplc-openlab-export`; it is not a standalone raw-data entrypoint.
- `validate_agilent_dx_decoder.py`: controlled regression validator for the in-repository `.dx` decoder against the independently installed `rainbow-api` oracle. It never supplies production decode values.
- `validate_native_peak_integration.py`: controlled validator for native target detection and integration against available vendor `.rx` peak records. It is not a second production entrypoint.
- `compare_chemstation_candidate.py`: controlled paired comparison of the production integrator and the independently implemented, PMX-configured ChemStation-compatible candidate. It parses every PMX copy, executes no vendor code, and cannot promote itself into production.

The OpenLab command decodes `.dx` chromatograms with the in-repository native decoder, uses optional `.rx` records only as a validation oracle, and writes one compact seven-sheet analysis workbook. The main sheet consolidates each final sample or repeat group to one row and has one `采集方法` column. Peak detail places `峰序号` immediately before `出峰时间(min)`. Processing logs, exclusions, repeat grouping, manual-review items, and analysis parameters live on separate sheets. Decoded raw signal points remain in the audit dataset instead of being crowded into Excel. The command intentionally creates no plots and must be invoked through `run.py`.
