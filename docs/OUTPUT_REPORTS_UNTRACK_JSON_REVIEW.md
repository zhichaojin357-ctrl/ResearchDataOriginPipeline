# Output Reports Untrack JSON Review

Date: 2026-06-04

Scope: ORP-JSON batch.

## Decision

Untrack 19 currently dirty generated JSON files under `output/reports` with explicit paths. These files are generated machine-readable reports, manifests, indexes, or queues. Their local files must remain on disk.

## Paths To Untrack

```text
output/reports/ambiguous_files.json
output/reports/data_triage_manifest.json
output/reports/dependency_audit.json
output/reports/duplicate_candidates.json
output/reports/excluded_files.json
output/reports/inventory_manifest.json
output/reports/phase1_6_material_color_map.json
output/reports/phase1_8_new_auto_process_plan.json
output/reports/phase1_8_new_auto_process_queue.json
output/reports/phase1_9_journal_figure_qc.json
output/reports/phase1_9_origin_plotting_skill_snapshot.json
output/reports/phase1_9_package_integration_report.json
output/reports/processing_queue.json
output/reports/processing_report.json
output/reports/processing_summary.json
output/reports/readiness_report.json
output/reports/readiness_report_no_desktop.json
output/reports/source_hash_index.json
output/reports/traceability_groups.json
```

## `.gitignore`

Added JSON rules:

```gitignore
output/reports/*.json
output/reports/**/*.json
```

Existing specific generated JSON family rules are retained. These rules do not ignore source, config, tests, scripts, docs, or Markdown.

## Safety Checks

- No local files should be deleted by this batch.
- No output file content should be committed.
- Staged output paths should be index removals only.
- Batch size is 19 paths, below the 50-path limit.

## Deferred JSON

Clean tracked historical JSON reports are not untracked in this batch. They remain tracked until a future explicit user decision or a separate reviewed batch.
