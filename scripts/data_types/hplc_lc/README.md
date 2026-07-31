# HPLC/LC Scripts

HPLC/LC-specific helpers here are either internal to a formal HPLC/LC command
or narrowly scoped regression/rebuild tools. They are not additional generic
data-processing entrypoints.

Current scripts:

- `plot_hplc_calibration_origin.ps1`: controlled regression/rebuild tool for the three fixed anisole calibration datasets and a user-selected HPLC calibration OPJU. It is not a reader for arbitrary HPLC data and must not substitute for a formal OpenLab or exported-table result.
- `build_openlab_workbook.mjs`: internal `@oai/artifact-tool` workbook builder used by `python run.py hplc-openlab-export`; it is not a standalone raw-data entrypoint.

The OpenLab command reads `.rslt/.dx/.rx` data and writes one compact summary workbook plus one workbook per top-level acquisition batch. Batch workbooks contain sample information and result-set-specific peak-area sheets. The Excel view uses one `方法` column and one row per injection/sample; each row line-aligns peak ordinal, elution time, peak area, and area percent. Decoded raw signal points and the separate source method fields remain in the audit dataset instead of being crowded into Excel. The command intentionally creates no plots and must be invoked through `run.py`.
