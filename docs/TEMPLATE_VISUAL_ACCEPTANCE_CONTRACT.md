# Template-format visual acceptance contract

- Allowed statuses: accepted, blocked, skipped, failed.
- accepted requires OPJU, TIF, PNG, processed data, metadata, and report to exist.
- accepted requires no-label audit pass, Origin readback, non-default 3 pt curve width, bold axis titles, and template path/graph recorded.
- EIS accepted requires cleaned points, ignored-point reporting, Model A Rs + (Rct || CPE), and a measured-range main fit curve that does not distort the axis range.
- Files merely existing are insufficient for accepted status.
- `--asset-only` acceptance requires `external_template_dependency=false`, a project-local asset path, and no external-reference preview execution.
- Pixel equality is evaluated by `origin-style-asset-replay` using identical template data. A product generated from different current data cannot be required to have identical pixels; it must instead pass plot-count, style-readback, structural, and visual checks.
- A style-replay pass requires all requested graph pages to exist and every comparison to report `rms=0` and `exact_pixel_match=true`.
