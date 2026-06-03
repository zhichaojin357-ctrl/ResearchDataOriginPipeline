# Whole Project Remaining Blockers

Date: 2026-06-04

This file records blockers left after the MASTER GOAL convergence audit. It intentionally does not resolve them, because each item requires user policy, Origin, real data, visual judgment, or a separate narrow execution goal.

## Git And Output Report Blockers

| Area | Current evidence | Blocker |
|---|---|---|
| `output/reports` tracked modified | 42 visible tracked modified report files remain | Requires user decision: restore to HEAD, commit a reviewed subset as formal lightweight reports, or keep dirty. |
| `output/reports` untracked Markdown | 52 untracked Markdown reports remain visible | Requires user decision because Markdown reports may be evidence/handoff documents. |
| `output/review_dashboard` | 2 tracked modified, 1 untracked | Requires review before treating dashboard files as formal docs or generated output. |
| generated JSON/CSV under `output/reports` | Narrow `.gitignore` rules now hide untracked machine-readable generated report families | No local files were deleted; tracked JSON/CSV modifications remain visible and unresolved. |

No additional `git rm --cached` was executed in this batch. Broad untracking of JSON, CSV, or Markdown reports remains blocked.

## Documentation Blockers

| Area | Current evidence | Blocker |
|---|---|---|
| `docs/agent_reports` | 64 untracked, 7 tracked modified | Needs formal review before bulk commit, ignore, archive, or restore decisions. |
| `docs` root-level files | 7 tracked modified plus 1 untracked pre-existing doc | Needs narrow review; do not batch commit unknown documentation changes. |
| `AGENTS.md` | 1 tracked modified root file | Needs review before commit because it can alter agent behavior. |
| Root entry docs | `README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, and `AGENT_HANDOFF.md` are pointer files with stale body text | Larger refresh should be a dedicated docs cleanup goal. |
| `docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md` | Still mention older HEAD/status context | Superseded by current audit docs until refreshed. |

## Source, Config, Test, And Script Blockers

Current status:

```text
git status --short -- src config tests scripts
0
```

There is no remaining source/config/test/script dirty work to auto-fix in this batch.

Blocked source work:

- Do not invent source changes from blocker docs.
- Do not restore old XPS large diffs.
- Do not start new XPS source edits without a narrow source goal.

## XPS Blockers

Current status:

- `src/core/xps_heterojunction.py`: clean.
- `src/core/xps_in_situ.py`: clean.
- `src/cli.py`: clean in the XPS check set.
- `tests/test_xps_heterojunction_stacked.py`: clean.
- `tests/test_xps_in_situ.py`: clean.
- `tests/test_xps_no_artifact_contracts.py`: clean.
- `tests/test_output_routing.py`: clean.

Remaining XPS blockers:

- Origin execution is blocked.
- OPJU/TIF/PNG/PDF/XLSX generation is blocked.
- Real data processing is blocked.
- Visual acceptance is blocked without user review or an explicit visual/Origin goal.
- XPS OPJU-exemplar comparison still needs a dedicated current evidence report.

## Data And Plotting Blockers

The following require explicit future goals:

- BET visual acceptance and OPJU-style comparison.
- Raman OPJU warning review.
- EIS plot contract review.
- XRD OPJU/exemplar visual review.
- HPLC/LC workflow review if real data or output generation is required.
- Mott-Schottky visual/contract review.
- UV-vis DRS / Tauc plotting contract.
- PL plotting and interpretation boundary review.
- Photocurrent plotting contract and output acceptance.
- FTIR plotting contract.

None of these were executed in this batch.
