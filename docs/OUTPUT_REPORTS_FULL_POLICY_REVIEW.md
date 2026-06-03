# Output Reports Full Policy Review

Date: 2026-06-04

Scope: `output/reports` policy audit for the MEGA convergence goal. No output file content was edited, deleted, moved, restored, or staged.

## Audit Commands

Commands executed:

```powershell
git status --short -- output/reports
git ls-files output/reports
git ls-files -m output/reports
git ls-files --others --exclude-standard output/reports
git ls-files -d output/reports
```

## Current Visible Dirty Counts

| Status | Extension | Count |
|---|---|---:|
| tracked modified | `.md` | 22 |
| tracked modified | `.json` | 19 |
| tracked modified | `.csv` | 1 |
| tracked deleted | any | 0 |
| untracked | `.md` | 52 |
| untracked | `.json` | 0 |
| untracked | `.csv` | 0 |
| untracked | `.txt` | 0 |
| untracked | `.xlsx/.zip/.png` | 0 |

## Policy Classification

### JSON

All currently dirty JSON files under `output/reports` are machine-readable generated reports, manifests, queues, indexes, or status outputs. They are suitable for explicit `git rm --cached -- <path>` because current status and decisions now live in `docs/` review documents.

Clean historical tracked JSON files are not touched in this batch. They remain either historical evidence or future user-decision candidates.

### CSV

The only dirty CSV is a generated journal-ready index:

```text
output/reports/phase1_9_journal_ready_index.csv
```

It is suitable for an explicit CSV untrack batch after JSON is committed.

### Binary, Logs, And XLSX

No visible tracked or untracked `.txt`, `.zip`, `.png`, or `.xlsx` report artifacts are currently exposed by Git status.

### Markdown

Markdown is not treated as one class. It is split into:

- keep tracked / high-value: `output/reports/README.md` until a replacement pointer is committed;
- generated and likely replaceable: current machine-generated report summaries and phase report Markdown;
- user-decision required: Markdown whose human/provenance value is unclear.

The Markdown batch must be reviewed separately.

## Safety Decision

Safe automated actions from this audit:

1. Untrack the 19 currently dirty generated JSON files with explicit paths.
2. Add `.gitignore` JSON rules for future generated report JSON.
3. Review the single dirty CSV in the next CSV batch.
4. Review generated Markdown separately without broad Markdown rules.
