# Output Reports Keep And User Decision

Date: 2026-06-04

Scope: ORP-KEEP-USER batch.

## Completed Automated Policy Actions

Automated safe actions completed under `output/reports`:

- untracked 19 dirty generated JSON reports with explicit paths;
- untracked 1 dirty generated CSV report with an explicit path;
- confirmed no visible TXT/ZIP/PNG/XLSX candidates;
- untracked 21 dirty generated Markdown reports with explicit paths;
- added scoped ignore rules for generated JSON, CSV, TXT, and generated Markdown report families.

No local output files were deleted or moved.

## Remaining Keep/User Decision

The only remaining visible `output/reports` dirty path after the Markdown policy is:

```text
output/reports/README.md
```

Classification:

- tracked modified;
- folder entry/pointer document;
- likely curated rather than a disposable generated report;
- output content, therefore not committed in this MEGA batch.

Required user decision:

1. Keep it tracked and commit a reviewed pointer-only update in a future explicit docs/output policy goal.
2. Restore it to HEAD in a future explicit cleanup goal.
3. Move equivalent status into `docs/` and later untrack the output README with explicit approval.

## Generated Markdown Rule Gap Closed

`output/reports/duplicate_candidates.md` became visible as untracked after the generated Markdown untrack batch. It is a generated duplicate-candidate report and is now covered by an explicit scoped ignore rule:

```gitignore
output/reports/duplicate_candidates.md
```

## Final Output Reports Policy State

Current expected state:

- generated machine-readable report files under `output/reports` are not future-tracked by default;
- generated report Markdown families under `output/reports` are ignored;
- `output/reports/README.md` remains tracked and visible as a user-decision item;
- clean tracked historical report files not touched in this MEGA goal remain in Git history until a future explicit decision.
