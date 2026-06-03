# Output Reports Markdown Policy Review

Date: 2026-06-04

Scope: ORP-MD-GENERATED batch.

## Markdown Classification

Markdown under `output/reports` is not treated as one class.

### Keep Tracked / User Decision

```text
output/reports/README.md
```

Reason: this is an entry/pointer document for the report folder and may be curated. Its current local modification is not committed in this batch because committing output content is forbidden. It remains tracked and dirty until a dedicated user decision or docs migration.

### Generated Markdown To Untrack

These 21 tracked modified Markdown files are generated report summaries, queue/status summaries, or validation/readiness/report outputs. Their current status is represented by docs review files, and the local Markdown files remain on disk after index removal.

```text
output/reports/ambiguous_files.md
output/reports/classification_report.md
output/reports/data_triage_report.md
output/reports/dependency_audit.md
output/reports/duplicate_candidates.md
output/reports/excluded_files.md
output/reports/origin_errors.md
output/reports/pending_cleanup_candidates.md
output/reports/phase1_6_material_color_map.md
output/reports/phase1_8_new_auto_process_plan.md
output/reports/phase1_9_journal_figure_qc.md
output/reports/phase1_9_journal_ready_index.md
output/reports/phase1_9_origin_plotting_skill_snapshot.md
output/reports/phase1_9_package_integration_report.md
output/reports/processing_queue.md
output/reports/processing_report.md
output/reports/processing_summary.md
output/reports/readiness_report.md
output/reports/readiness_report_no_desktop.md
output/reports/traceability_groups.md
output/reports/validation_report.md
```

### Untracked Generated Markdown

The 52 untracked Markdown files under `output/reports` match generated phase/report families. They are not committed. They are covered by scoped `.gitignore` rules in this batch.

## `.gitignore`

Added scoped generated Markdown rules for `output/reports`, including:

- phase report Markdown;
- EPR/BET/XRD/project-cleanup report Markdown;
- generated top-level status/report summaries;
- handoff Markdown located under `output/reports`.

These rules do not ignore `output/reports/README.md`, repository docs, source, config, tests, or scripts.

## Safety Checks

- Batch size for `git rm --cached`: 21 paths, below the 50-path limit.
- No local files should be deleted.
- No output file content should be staged.
- Staged output paths should be index removals only.
