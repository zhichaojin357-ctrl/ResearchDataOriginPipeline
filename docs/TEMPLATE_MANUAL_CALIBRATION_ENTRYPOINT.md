# Template Manual Calibration Entrypoint

Template-format products are produced by `run.py template-format-products`. The command copies or embeds the approved Origin style structure into the generated run so future plotting does not depend on hand-edited external templates.

## Required Acceptance Evidence

The latest successful run must contain these reports under `../输出/runs/<timestamp>_template_format_*/reports`:

- `template_format_executor_summary.json`
- `template_preview_comparison.json`
- `visual_acceptance_summary.md`
- `product_no_label_audit.json`

Acceptance requires:

- all expected data types are accepted with no failed products
- strict template comparison is ready and passes for every expected product
- OPJU-facing names use only the source data filename
- OPJU comments are blank
- no generated product contains an automation/tool name or absolute local path

If a product falls back to cached style-package mode or reports manual-check-only template comparison, the run is not release evidence for strict template matching.
