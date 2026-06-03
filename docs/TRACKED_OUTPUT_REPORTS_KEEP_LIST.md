# Tracked Output Reports Keep List

日期：2026-06-03

## Keep Tracked For Now

Keep these tracked report families visible until the user makes a wider report policy decision:

- active/baseline reports:
  - `output/reports/README.md`
  - `output/reports/processing_report.md`
  - `output/reports/processing_summary.md`
  - `output/reports/processing_queue.md`
  - `output/reports/readiness_report.md`
  - `output/reports/readiness_report_no_desktop.md`
  - `output/reports/validation_report.md`
  - `output/reports/dependency_audit.md`
  - `output/reports/inventory_manifest.json`
  - `output/reports/source_hash_index.json`
  - `output/reports/traceability_groups.md`
  - `output/reports/classification_report.md`
- historical phase Markdown/JSON summaries that explain previous project state;
- selected EPR, BET, XRD, OPJU, package, and cleanup reports if the user still uses them as evidence.

## Never Auto-Untrack

Never auto-untrack:

- any locked package pointer;
- any manually curated report;
- any report required by current CLI tests or release baseline;
- any file outside `output/reports` unless a later GOAL explicitly allows it.

Protected output roots remain protected:

- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`
- `output/phase1_5_processed_results_20260531_005613`
- `output/material_collections`
- OPJU references / copied reference material under `output/opju_exemplar_regression`

## Do Not Batch Process

Do not batch process these in this GOAL:

- `output/reports/*.json`
- `output/reports/*.csv`
- `output/reports/*.md`
- all of `output/reports/`

Reason:

- broad JSON/CSV/MD untracking could hide useful status evidence;
- Markdown reports may be human-readable project history;
- `output/reports` is intentionally unignored in `.gitignore`.

## Explicit Pilot Exception

The only tracked files approved for pilot untrack in this GOAL are generated XLSX report artifacts:

- `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`
- `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- `output/reports/phase1_9_manual_review_required_final.xlsx`

These files should remain on disk. Only Git index tracking should stop.
