# HPLC/LC Scripts

HPLC/LC-specific helpers live here only when they are tied to a formal HPLC/LC command.

Current scripts:

- `plot_hplc_calibration_origin.ps1`: rebuilds the three anisole calibration curves from the fixed HPLC calibration OPJU template, exports OPJU/PNG/TIF outputs, and writes a template-comparison report.
- `build_openlab_workbook.mjs`: internal `@oai/artifact-tool` workbook builder used by `python run.py hplc-openlab-export`; it is not a standalone raw-data entrypoint.

The OpenLab command reads `.rslt/.dx/.rx` data and writes one compact summary workbook plus one workbook per top-level acquisition batch. Batch workbooks contain sample information and result-set-specific peak-area sheets; decoded raw signal points remain in the audit dataset instead of being crowded into Excel. The command intentionally creates no plots and must be invoked through `run.py`.
