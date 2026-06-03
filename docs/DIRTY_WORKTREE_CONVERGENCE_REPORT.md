# Dirty Worktree Convergence Report

Date: 2026-06-03

## Scope

This report classifies the current dirty worktree. It does not delete, move, restore, or clean any file.

Commands used were read-only `git status`, `git diff --cached`, `git ls-files`, `git check-ignore`, and path/category counting from `git status --short`.

## Baseline Snapshot

Before this GOAL modified `.gitignore`:

- total dirty status entries: 290
- staged entries: 0
- tracked modified entries: 63
- tracked deleted entries: 0
- untracked entries: 227
- `output/` + `outputs/` entries: 207
- `src` + `config` + `tests` + `scripts` + `docs` entries: 82

Path bucket counts before `.gitignore` update:

| Bucket | Modified | Deleted | Untracked | Total |
| --- | ---: | ---: | ---: | ---: |
| `src` | 2 | 0 | 0 | 2 |
| `config` | 0 | 0 | 0 | 0 |
| `tests` | 1 | 0 | 0 | 1 |
| `scripts` | 0 | 0 | 0 | 0 |
| `docs` | 7 | 0 | 1 | 8 |
| `docs/agent_reports` | 7 | 0 | 64 | 71 |
| `output` | 2 | 0 | 5 | 7 |
| `outputs` | 0 | 0 | 0 | 0 |
| `output/reports` | 43 | 0 | 157 | 200 |
| root files | 1 | 0 | 0 | 1 |

Artifact category counts before `.gitignore` update:

| Category | Count | Recommendation |
| --- | ---: | --- |
| generated reports | 197 | do not commit as a batch |
| historical `docs/agent_reports` | 71 | do not batch commit; review only if needed |
| ordinary docs/root docs | 9 | review before commit |
| generated output data/artifacts | 7 | do not commit; manual cleanup candidate |
| generated report binary/artifact | 3 | do not commit |
| XPS source code | 2 | blocked source diff |
| XPS tests | 1 | blocked test diff |

After the narrow `.gitignore` update in this GOAL:

- total dirty status entries: 281
- tracked modified entries: 64, including `.gitignore`
- tracked deleted entries: 0
- untracked entries: 217
- `output/` + `outputs/` entries: 197

The count dropped because newly ignored entries include generated output roots and report-side temporary/binary artifacts. Tracked output reports still remain dirty because `.gitignore` does not hide already tracked files.

## Current Source Dirty

The only current dirty source/test files are XPS blocker files:

- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`

They are blocked because their diffs mix source contracts, Origin/OPJU behavior, visual styling, image/Excel artifact behavior, and tests that currently involve generated artifacts.

## Documentation Dirty

Dirty docs outside generated output:

- `AGENTS.md`
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- `docs/REAL_DATA_INTAKE_GUIDE.md`
- `docs/indexes/output_reports_index.md`
- `docs/indexes/outputs_index.md`
- `docs/method_cards/README.md`
- `docs/method_cards/bet.md`
- `docs/method_cards/epr.md`
- `docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md`

These should not be mixed with source or output cleanup commits. They need a docs-only review if the user wants them preserved.

## Historical Agent Reports

`docs/agent_reports/` currently contributes 71 status entries:

- 7 tracked modified entries;
- 64 untracked entries.

These are historical phase reports and handoff reports. They should not be batch committed by default. Keep them as review material unless the user chooses a specific lightweight subset.

## Generated Output Dirty

`output/` and `output/reports/` dominate the remaining dirty state:

- `output/reports`: 194 entries after the `.gitignore` update;
- `output`: 3 entries after the `.gitignore` update;
- `outputs`: 0 visible entries.

Most visible `output/reports` entries are JSON/Markdown/CSV report outputs. Some are tracked modified reports, so ignore rules cannot remove them from status.

## Worktree Convergence Conclusion

The dirty worktree is now mostly understood:

- real source/test work: 3 XPS blocker files;
- docs needing review: 9 ordinary docs/root docs;
- historical agent reports: 71 entries;
- generated output/report material: about 197 entries after ignoring obvious generated roots/binaries.

Next convergence work should not start with output deletion. It should start with XPS no-artifact contract tests or remaining source/doc triage, then user-reviewed output cleanup.
