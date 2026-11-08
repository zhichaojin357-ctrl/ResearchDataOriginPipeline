# GC calibration exported data

Dedicated command: `python run.py gc-calibration --source <xlsx> --sheet <selected-sheet> --selection-note <provenance> [--area-unit <verified-unit>] [--with-origin]`.

For already processed selected tables, `--plot-only` imports the existing concentration/area pairs directly into Origin, skips new processed CSV exports and implies Origin execution. Fit recalculation serves verification only; metadata and an audit report remain required.

The user selects a worksheet explicitly. Supported XLSX/XLSM tables contain horizontal blocks: an English analyte name immediately above or immediately left of `浓度 (mM)` / `实测峰面积` (or `Concentration (mM)` / `Peak area`; `峰面积` is also accepted). Consecutive concentration/area rows up to the first blank pair are used. Missing, nonfinite, negative, constant-response or insufficient standards are rejected. Raw GC vendor files are outside scope.

No point selection, R² optimization, smoothing, forced-zero intercept or response correction is performed. Ordinary unweighted least squares reuses the shared regression functions. Processed CSV preserves all points, source cells, predicted areas, residuals and back-calculated concentration candidates. Metadata records the selected sheet, source, selection rationale, units, manual checks and claim policy. Percent residual uses prediction as denominator; it is not a back-calculation accuracy acceptance rule.

`--with-origin` creates a fresh task-owned Origin.Application project with one scatter graph per analyte. Origin `fitlr` recomputes the fit from imported raw standards; coefficients and R² must agree with the processor. The fit line is not displayed. Graph4 fixed geometry/fonts and calibration-specific orange points are used. Y labels use a declared ×10⁴ area display scale; data and equation coefficients retain raw area units. GC area units are not inferred from an HPLC detector.

The saved OPJU is reopened; standards, plot count and key geometry/font sizes are read back before native TIFF and PNG export. TIFF pixels, tags and effective physical DPI must match 600 dpi. PNG visual review remains pending until actually inspected by the operator. Existing Origin sessions cause a preflight failure. Unique output directories avoid overwriting prior products; a failed run records its error and is not labeled successful.

Manual checks: exclusion rationale, preparation and replicate reliability, peak mapping, integration/detector units, low-concentration residuals, leverage and independent repeat calibration. A high R² of a post hoc selected subset does not establish validated linearity, detection limits, peak identity, conversion, yield or selectivity.
