# Final Output Reports README Decision

Date: 2026-06-04

Scope: final decision for the last dirty path after MEGA convergence:

```text
output/reports/README.md
```

## Starting State

Phase 0 checks showed:

- staged entries: 0;
- total dirty: only `output/reports/README.md`;
- `output/reports/README.md` is tracked modified.

The current diff only changed generated report counts:

- `other: 67` to `other: 81`;
- added `phase1_10`, `phase1_11`, `phase1_12`, `phase1_12A`, and `phase1_13` counts;
- `phase1_9: 13` to `phase1_9: 33`.

The HEAD version is still a historical Phase 1.9 report-folder README.

## Option A: Keep And Commit Current README

Decision: rejected.

Reason:

- the dirty diff is count-only and generated-looking;
- the file still describes `output/reports` as a historical generated-report location, not the current policy authority;
- committing output content is disallowed unless clearly necessary;
- current output-report policy now lives in `docs/OUTPUT_REPORTS_*` documents.

## Option B: Restore README To HEAD

Decision: selected.

Reason:

- the current diff is stale/generated count churn;
- it duplicates policy/status information that now lives in `docs/`;
- keeping the diff would invite Codex to treat `output/reports` as a current status source;
- the HEAD version can remain as historical tracked content until a future explicit output README policy goal decides whether to keep, rewrite, or untrack it.

Command used:

```powershell
git restore -- output/reports/README.md
```

## Option C: Stop Tracking README

Decision: rejected for this GOAL.

Reason:

- the prompt explicitly warns not to untrack blindly just to reduce dirty;
- `output/reports/README.md` is a folder entry document and may still have historical navigation value;
- Option B fully resolves the dirty state without deleting, moving, or untracking the local file.

## Final Decision

Use Option B: restore `output/reports/README.md` to HEAD and commit only this decision document.
