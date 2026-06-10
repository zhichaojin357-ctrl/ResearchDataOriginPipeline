# Maintenance Scripts

Reusable maintenance scripts should live here when they are not part of the public CLI.

Do not place one-off report generators, raw-data processing outputs, or result artifacts here.

Current scripts:

- `dry_run_output_cleanup_plan.py`: read-only inventory of output directories and cleanup risk classes. It never deletes or moves files.
- `dry_run_tracked_output_reports_policy.py`: read-only classifier for tracked and ignored `output/reports` files. It never changes Git or report files.
- `opju_exemplar_regression.py`: compares OPJU exemplar outputs and records regression evidence. It may depend on Origin-related artifacts; do not treat it as a production data processor or run it during layout cleanup.
