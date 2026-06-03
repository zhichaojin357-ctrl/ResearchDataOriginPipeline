# Whole Project Legacy Convergence Audit

Date: 2026-06-04

Scope: MASTER GOAL convergence audit under no-Origin, no-real-data, no-output-content safety rules. This audit used current disk state, Git HEAD, Git status, and committed history. No Origin process was started, no real data was processed, no output files were deleted, moved, restored, or edited, and no output file content was staged.

## Repository Snapshot

Repository root resolved by Git:

```text
ResearchDataOriginPipeline
```

Start HEAD before this audit batch:

```text
8b788a78d0ba53bb30ac66619afe89ab96f9e210
8b788a7 chore: stop tracking temporary output report artifacts
```

Staged entries at start:

```text
0
```

## Phase 0 Dirty Snapshot

Counts before the new generated-report ignore rules were added:

| Scope | Count |
|---|---:|
| `git status --short` | 253 |
| `git status --short -- output outputs` | 173 |
| `git status --short -- output/reports` | 170 |
| `git status --short -- src config tests scripts docs AGENTS.md` | 80 |
| `git status --short -- src config tests scripts` | 0 |

No XPS source/test paths were dirty in the required XPS check set.

## Safe Convergence Action

The only automatic reduction performed in this batch was a narrow `.gitignore` update for untracked generated machine-readable reports under `output/reports`.

Added rule families:

```gitignore
output/reports/bet_*.json
output/reports/epr_*.json
output/reports/jeol_epr_*.json
output/reports/non_xrd_*.json
output/reports/origin_operations_*.json
output/reports/phase1_9_*.json
output/reports/phase1_10_*.json
output/reports/phase1_10_*.csv
output/reports/phase1_11_*.json
output/reports/phase1_12*.json
output/reports/phase1_13_*.json
output/reports/phase1_14_*.json
output/reports/project_cleanup_*.json
output/reports/xrd_*.json
```

Safety boundary:

- Markdown reports under `output/reports` remain visible for user review.
- Tracked modified output reports remain visible; `.gitignore` does not hide tracked files.
- No `git rm --cached` was run in this batch.
- No broad `output/reports/*.json`, `output/reports/*.csv`, or `output/reports/*.md` rule was added.
- No source, config, test, or script file was changed.

Verification examples:

```text
.gitignore:58:output/reports/phase1_13_*.json output/reports/phase1_13_final_validation.json
.gitignore:37:!output/reports/** output/reports/phase1_13_final_validation.md
.gitignore:49:output/reports/epr_*.json output/reports/epr_overlay_report.json
.gitignore:37:!output/reports/** output/reports/epr_overlay_report.md
```

## Post-Policy Dirty Snapshot

Counts after the `.gitignore` update and before writing this audit document:

| Scope | Count |
|---|---:|
| `git status --short` | 178 |
| `git status --short -- output outputs` | 97 |
| `git status --short -- output/reports` | 94 |
| `git status --short -- src config tests scripts` | 0 |

Post-policy composition before this audit document was written:

| Group | Category | Count |
|---|---|---:|
| `docs/agent_reports` | untracked | 64 |
| `output/reports` | untracked Markdown | 52 |
| `output/reports` | tracked modified | 42 |
| `docs/agent_reports` | tracked modified | 7 |
| `docs` | tracked modified | 7 |
| `output/review_dashboard` | tracked modified | 2 |
| `output/review_dashboard` | untracked | 1 |
| root docs | tracked modified | 1 |
| `.gitignore` | tracked modified | 1 |
| `docs` | untracked | 1 |

Tracked deleted entries: 0.

## Recent Commit Phase Summary

Recent committed work clusters:

- Project status and cleanup planning: current status/index/cleanup docs and dirty grouping summaries.
- Scripts layout organization: script movement, script layout references, and script consistency reviews.
- Origin policy helpers: plotting policy, text formatting, run-scoped artifact path acceptance, and Origin operation helper stabilization.
- EPR workflows: JEOL decode and overlay workflow stabilization.
- Optional adapters: optional scientific adapter shims and adapter bridge stabilization.
- Governance output-safe tests: report-test isolation and generated artifact safety.
- Table reader, metadata, and processor base: table reader contracts, metadata review checklist, processor base contracts, and photocurrent microamp outputs.
- BET candidate extraction: BET candidate extraction and its summary documentation.
- Future run-scoped output routing: path helpers and process/queue/report routing support.
- Dirty worktree convergence: generated run artifact ignores and remaining dirty maps.
- XPS no-artifact and source split work: no-artifact contract tests, SAFE-1 heterojunction contract adjustment, SAFE-2 in-situ output routing, and XPS post-split summaries.
- Output report tracking policy: tracked output report policy and pilot untracking of three generated XLSX report artifacts.

## Documentation Consistency

Root entry files `README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, and `AGENT_HANDOFF.md` are still pointer-style entry points, but their bodies contain older Phase 1.8/1.9/1.10/1.12 framing. They should not be treated as the latest status authority without reading newer audit documents.

`docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md` are useful but still mention the older `116b393` baseline in places. This audit supersedes them for current Git/dirty counts until those larger documents are refreshed in a dedicated documentation cleanup batch.

`docs/NEXT_GOAL_QUEUE.md` was refreshed in this batch to remove the stale recommendation to design XPS no-artifact tests, because those tests are now committed and the XPS source/test paths are clean.

## Stop Condition

The MASTER GOAL should stop after this batch because the remaining dirty state is dominated by:

- output/generated artifacts that need user report-policy decisions;
- `docs/agent_reports` and documentation changes that need review before broad commit;
- Origin, real-data, or visual-acceptance blockers.

This matches stop conditions 13 and 14: the safely automatic work has been completed, and the remaining work requires user decision, Origin, real data, or visual judgment.
