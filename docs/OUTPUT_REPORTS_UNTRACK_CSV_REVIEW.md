# Output Reports Untrack CSV Review

Date: 2026-06-04

Scope: ORP-CSV batch.

## Decision

Untrack the only currently dirty generated CSV report:

```text
output/reports/phase1_9_journal_ready_index.csv
```

This file is a generated journal-ready index under `output/reports`. The current project status and decisions are now represented in docs. The local CSV file must remain on disk.

## `.gitignore`

Added CSV rules:

```gitignore
output/reports/*.csv
output/reports/**/*.csv
```

These rules are scoped to `output/reports` only. They do not hide source, config, tests, scripts, docs, or Markdown.

## Deferred CSV

Clean tracked historical CSV files under `output/reports` are not touched in this batch. They remain tracked until a future explicit user decision or separate reviewed batch.

## Safety Checks

- Batch size: 1 path.
- No local files should be deleted.
- No output content should be staged.
- Staged output path should be an index removal only.
