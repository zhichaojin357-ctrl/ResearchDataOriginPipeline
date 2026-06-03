# Dirty Worktree Goal Summary

Date: 2026-06-03

## Goal

Dirty Worktree Convergence + Generated Artifact Policy + Remaining Source Queue.

This GOAL classified the remaining dirty worktree, added narrow generated-artifact ignore rules, and created the next source/output cleanup queue.

## Commits Completed

### `2de5126` - `docs: map remaining dirty worktree`

Files:

- `docs/DIRTY_WORKTREE_CONVERGENCE_REPORT.md`
- `docs/OUTPUT_MANUAL_CLEANUP_CANDIDATES.md`
- `docs/REMAINING_SOURCE_DIRTY_QUEUE.md`
- `docs/NEXT_GOAL_QUEUE.md`

### `07d597f` - `chore: ignore generated run artifacts`

Files:

- `.gitignore`
- `docs/GENERATED_ARTIFACT_POLICY.md`

## Dirty Counts

Start of GOAL:

- total dirty entries: 290
- staged entries: 0
- tracked modified: 63
- tracked deleted: 0
- untracked: 227
- `output/` + `outputs/`: 207
- `src` + `config` + `tests` + `scripts` + `docs`: 82

After `.gitignore` and two commits:

- total dirty entries: 280
- staged entries: 0
- tracked modified: 63
- tracked deleted: 0
- untracked: 217
- `output/` + `outputs/`: 197
- `src` + `config` + `tests` + `scripts` + `docs`: 82

Current path bucket counts:

| Bucket | Modified | Deleted | Untracked | Total |
| --- | ---: | ---: | ---: | ---: |
| `src` | 2 | 0 | 0 | 2 |
| `config` | 0 | 0 | 0 | 0 |
| `tests` | 1 | 0 | 0 | 1 |
| `scripts` | 0 | 0 | 0 | 0 |
| `docs` | 7 | 0 | 1 | 8 |
| `docs/agent_reports` | 7 | 0 | 64 | 71 |
| `output` | 2 | 0 | 1 | 3 |
| `outputs` | 0 | 0 | 0 | 0 |
| `output/reports` | 43 | 0 | 151 | 194 |
| root files | 1 | 0 | 0 | 1 |

## Main Dirty Sources

1. `output/reports`: generated report history and tracked modified generated reports.
2. `docs/agent_reports`: historical phase reports, not suitable for batch commit.
3. XPS source/test blockers:
   - `src/core/xps_heterojunction.py`
   - `src/core/xps_in_situ.py`
   - `tests/test_xps_heterojunction_stacked.py`
4. Ordinary docs/root docs:
   - `AGENTS.md`
   - real-data compatibility/intake docs
   - output indexes
   - method cards
   - `docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md`

## `.gitignore`

Modified: yes.

Rules added:

- `output/runs/`
- `output/regression/`
- `output/adapter_shadow_runs/`
- `output/bet_reference_compare/`
- `output/opju_exemplar_regression/`
- `output/final_locked_results/`
- `output/reports/_tmp_*`
- `output/reports/tmp_*`
- `output/reports/*.png`
- `output/reports/*.zip`
- `output/reports/*.xlsx`
- `output/reports/xps_template_compare/`
- `output/reports/phase1_14_single_queues/`

These are narrow generated-artifact rules. They do not ignore source, config, tests, scripts, root docs, Markdown report docs, or JSON report docs.

## Analyzer

No dirty analyzer script was added. Direct read-only git/Python classification was sufficient for this GOAL.

## Safety Statement

This GOAL did not:

- delete any file;
- move any file;
- restore any file;
- clean `output/` or `outputs/`;
- run Origin;
- process real data;
- run any pipeline;
- submit generated `output/` or `outputs/` artifacts;
- stage or commit OPJU/TIF/PNG/XLSX/ZIP/large JSON artifacts.

## User Manual Review Items

The user should decide later:

- whether to delete or archive old `output/reports` history;
- whether to keep or ignore historical `docs/agent_reports`;
- whether `output/final_locked_results` should remain locally;
- whether tracked modified output reports should be restored, kept dirty, or committed as a narrow formal subset.

## Next Recommendation

Recommended next GOAL:

```text
GOAL: XPS No-Artifact Contract Test Design
```

Reason:

- the only remaining source/test dirty files are XPS-related;
- they are blocked because current tests and diffs involve generated XPS artifacts;
- designing safe no-artifact contract tests is the cleanest next step before further source commits.
