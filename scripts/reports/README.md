# Report Scripts

Report-generation and index-refresh helpers live here when they are reusable but not part of the public CLI.

Keep parser and format verification helpers in `scripts/validation/`. Historical maintenance probes should not be kept in the final runtime script set.

Current scripts:

- `regenerate_manual_review_filtered.py`: rebuilds filtered manual-review CSV/XLSX/report outputs from existing report inputs.
