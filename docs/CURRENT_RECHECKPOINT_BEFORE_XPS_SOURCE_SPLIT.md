# Current Recheckpoint Before XPS Source Split

Date: 2026-06-03

Repository root used for this checkpoint:

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

This checkpoint uses only the current disk repository, Git HEAD, Git status, and committed Git history. It does not rely on prior conversation memory. The dirty counts below are the snapshot captured before creating this checkpoint document; this document itself will add one additional dirty `docs/` entry after it is written.

## 1. Current HEAD Commit

Current HEAD:

`8e1263f598197a83755128b0392fee0e70cb7cec`

Short form:

`8e1263f docs: summarize xps no-artifact stabilization`

## 2. Staged State

`git diff --cached --name-status` returned no paths.

Staged entries: 0

Conclusion: staged is 0.

## 3. Dirty Count

Required count commands, captured before this document was generated:

| Scope | Count |
|---|---:|
| `git status --short` | 280 |
| `git status --short -- src config tests scripts docs output outputs` | 279 |
| `git status --short -- output outputs` | 197 |
| `git status --short -- src config tests scripts docs` | 82 |

The difference between total dirty count 280 and scoped count 279 is `AGENTS.md`, which is outside `src config tests scripts docs output outputs`.

## 4. Dirty Composition

Global dirty composition:

| Category | Count |
|---|---:|
| tracked modified | 63 |
| tracked deleted | 0 |
| untracked | 217 |
| staged entries | 0 |
| unstaged tracked entries | 63 |

Grouped dirty composition:

| Group | Total | Modified | Deleted | Untracked |
|---|---:|---:|---:|---:|
| `output/outputs` | 197 | 45 | 0 | 152 |
| `src/config/tests/scripts/docs` | 82 | 17 | 0 | 65 |
| other | 1 | 1 | 0 | 0 |

Other dirty path:

- `AGENTS.md` tracked modified.

## 5. Recent 30 Commit Phase Summary

Recent 30 commits:

```text
8e1263f docs: summarize xps no-artifact stabilization
fa95f20 tests: add xps no-artifact workflow contracts
e8e8814 docs: summarize dirty worktree convergence
07d597f chore: ignore generated run artifacts
2de5126 docs: map remaining dirty worktree
66abdbc docs: summarize xps workflow preflight
b34d2bf cli: clarify xps with-origin artifact contract
beb7135 docs: document future output routing policy
c9052f1 origin: accept run-scoped artifact paths
49e207c core: route queue reports through run outputs
4c6ab10 core: route process artifacts into run outputs
a114121 core: add run-scoped output path helpers
7ac2ab9 docs: summarize optional adapter bridge micro-batch
1fc9875 adapters: stabilize optional adapter bridge
823d093 docs: summarize bet candidate extraction micro-batch
d5a24b1 processors: stabilize bet candidate extraction
e3360e3 docs: summarize processor table reader stabilization
870d088 processors: express photocurrent outputs in microamps
bdeff29 processors: tighten processor base contracts
3e46e5e core: tighten metadata preview review checklist
d8f54e5 core: stabilize table reader contracts
18bb19e docs: summarize governance and script consistency goal
a0cedbe docs: sync script layout references
dbe0a58 core: isolate governance report tests
1fb85f0 docs: summarize batch2 autonomous stabilization
b860453 tests: update manual review generator import
f09fcf3 adapters: add optional scientific adapter shims
cc2e13e epr: stabilize jeol decode and overlay workflows
76c3c5c origin: stabilize plotting policy helpers
0d316a9 docs: record batch2 source review progress
```

Phase grouping from the commit subjects:

- XPS no-artifact stabilization: `fa95f20`, `8e1263f`.
- Dirty worktree convergence and XPS workflow preflight documentation: `e8e8814`, `07d597f`, `2de5126`, `66abdbc`, `b34d2bf`.
- Future run-scoped output routing: `beb7135`, `c9052f1`, `49e207c`, `4c6ab10`, `a114121`.
- Optional adapters, BET candidate extraction, processor base, metadata, and table reader work: `7ac2ab9`, `1fc9875`, `823d093`, `d5a24b1`, `e3360e3`, `870d088`, `bdeff29`, `3e46e5e`, `d8f54e5`.
- Governance output-safe tests and script layout consistency: `18bb19e`, `a0cedbe`, `dbe0a58`.
- Earlier batch2, EPR workflow, optional scientific adapter, and Origin policy helper stabilization: `1fb85f0`, `b860453`, `f09fcf3`, `cc2e13e`, `76c3c5c`, `0d316a9`.

## 6. Completed Capabilities

The following capabilities are represented in committed history:

- Scripts classification/layout references: script layout documentation was synchronized in `a0cedbe`, with governance/script consistency summarized in `18bb19e`.
- Origin policy helpers: plotting policy helpers were stabilized in `76c3c5c`; run-scoped artifact path acceptance exists in `c9052f1`.
- EPR: JEOL decode and overlay workflows were stabilized in `cc2e13e`.
- Optional adapters: optional scientific adapter shims and bridge stabilization are represented by `f09fcf3` and `1fc9875`.
- Governance output-safe tests: governance report tests were isolated in `dbe0a58`; the goal was summarized in `18bb19e`.
- Table reader, metadata, and processor base: table reader contracts, metadata preview review checklist, processor base contracts, and photocurrent output units are represented by `d8f54e5`, `3e46e5e`, `bdeff29`, and `870d088`; the table reader stabilization summary is `e3360e3`.
- BET candidate extraction: processor support and documentation are represented by `d5a24b1` and `823d093`.
- Future run-scoped output routing: helpers and process/queue routing are represented by `a114121`, `4c6ab10`, `49e207c`, `c9052f1`, and `beb7135`.
- XPS no-artifact tests: workflow contract tests and summary documentation are represented by `fa95f20` and `8e1263f`.

## 7. Still Unfinished

- `src/core/xps_heterojunction.py` has a large unstaged source diff.
- `src/core/xps_in_situ.py` has a large unstaged source diff.
- `tests/test_xps_heterojunction_stacked.py` has unstaged test changes.
- XPS run-scoped output source integration is not committed and remains mixed with larger source/style/artifact diffs.
- XPS Origin/OPJU/visual/export validation remains blocked; no Origin run was performed for this checkpoint.
- Real data processing remains blocked; no real data processing was performed for this checkpoint.
- Generated outputs/reports remain a large dirty component: 197 entries under `output/outputs`.
- There are 217 untracked dirty entries overall.

## 8. Current XPS Dirty Files

The required XPS path status command reports:

```text
 M src/core/xps_heterojunction.py
 M src/core/xps_in_situ.py
 M tests/test_xps_heterojunction_stacked.py
```

No dirty entries were reported for:

- `src/cli.py`
- `tests/test_xps_in_situ.py`
- `tests/test_xps_no_artifact_contracts.py`
- `tests/test_output_routing.py`

Diff stat for the requested XPS paths:

```text
src/core/xps_heterojunction.py           | 320 +++++++++++------
src/core/xps_in_situ.py                  | 586 ++++++++++++++++++++++++-------
tests/test_xps_heterojunction_stacked.py | 173 ++++++++-
3 files changed, 824 insertions(+), 255 deletions(-)
```

Numstat:

| File | Insertions | Deletions |
|---|---:|---:|
| `src/core/xps_heterojunction.py` | 208 | 112 |
| `src/core/xps_in_situ.py` | 460 | 126 |
| `tests/test_xps_heterojunction_stacked.py` | 156 | 17 |

Git emitted LF-to-CRLF working-copy warnings for the three dirty XPS files while generating diff stats.

## 9. `src/core/xps_heterojunction.py` Diff Themes

The current diff broadly mixes these change types:

- Origin adapter/policy imports: adds `_ensure_tif_600_dpi` and `get_plot_policy`.
- Artifact contract changes: removes `figures_preview` from the task subdirectory set, stops requiring preview PNG as a success artifact for the COM export path, validates only OPJU and TIF, returns `preview_png: None` on COM success, and enforces TIF DPI.
- Origin script/export changes: uses larger TIF export width, changes Origin page/layer geometry, tick visibility, axis label styling, and label bolding.
- Plot policy propagation: injects policy fields such as plot code, primitive, marker mode, fit overlay mode, and axis/tick visibility into the generated helper script.
- Native gradient fill changes: replaces layered light-to-color gradient columns with Origin native gradient fill behavior and simplified fill upper/lower columns.
- Label and chemistry formatting: adds helpers for bold multiline labels and chemical subscripts.
- Component and peak behavior: changes Cu2p component color assignment from integer binding-key grouping toward visual binding-energy windows; changes component peak binding helpers; changes peak annotation handling.
- Report schema/content changes: removes preview column from generated/planned figures and updates prose about y ticks, component fills, and color assignment.

This is not a single-purpose diff. It combines artifact contract, visual style, generated Origin script, component-color algorithm, peak annotation, report formatting, and output path behavior.

## 10. `src/core/xps_in_situ.py` Diff Themes

The current diff broadly mixes these change types:

- Artifact/output routing: adds structured output subdirectories for `figures_tif`, `figures_png`, `figures_pdf`, `origin_projects`, `reports`, and `tables`; routes peak summary, manifest, reports, and figures into those subdirectories.
- Origin artifact handling: adds `_ensure_tif_600_dpi`; splits Origin output into grouped OPJU projects; removes the old combined final PNG image-page behavior; exports per-panel TIF/PNG/PDF artifacts.
- Origin project structure: adds `ORIGIN_PROJECT_GROUPS`, per-panel graphs, per-record worksheets, record-column roles, counts headers, sample offsets, panel labels, style validation, and Origin color helpers.
- Matplotlib visual changes: adds gradient fill between background and component curves, thicker component/envelope lines, changed sample label placement, peak guide lines, changed tick direction/visibility, and revised save paths.
- Panel planning/record filtering: adjusts planned panel behavior and filters panel records to complete records.
- Quality checks: changes quality checks to inspect structured subdirectories and grouped Origin projects.
- Status/report shape: Origin status now returns `origin_files`; the success message describes grouped editable graph projects and no final PNG image page.

This is also not a single-purpose diff. It combines run-scoped output routing, Origin project design, matplotlib style, artifact generation behavior, quality checks, and report/status shape changes.

## 11. XPS Content Suitable For Next Source Hunk Split

The next `XPS Source Hunk Split Preflight` can safely inspect and classify these current dirty XPS areas:

- The three dirty XPS files only: `src/core/xps_heterojunction.py`, `src/core/xps_in_situ.py`, and `tests/test_xps_heterojunction_stacked.py`.
- Text-level hunk grouping for no-artifact contract alignment, especially the heterojunction preview-PNG removal/TIF-only COM success behavior.
- Text-level hunk grouping for run-scoped output routing candidates in `xps_in_situ.py`, especially `_output_subdirs` and report/table/figure path routing.
- Text-level hunk grouping for style-only changes, including Origin page/layer formatting, tick labels, native gradient fills, matplotlib gradient fills, and label formatting.
- Text-level hunk grouping for algorithmic changes, including Cu2p color grouping, component peak binding, and annotation behavior.
- Test-diff classification in `tests/test_xps_heterojunction_stacked.py`, separating contract assertions from visual/style assertions.

The suitable next step is classification and minimal hunk-boundary planning, not source repair.

## 12. XPS Content That Must Remain Blocked

These areas should remain blocked until explicitly moved into a later execution goal:

- Running Origin or generating OPJU/TIF/PNG/PDF/XLSX artifacts.
- Running real data processing.
- Treating visual/style changes as accepted without Origin or screenshot/visual evidence.
- Staging or committing the current mixed XPS source diff before it is split and reviewed.
- Folding generated `output/outputs` artifacts into the source split.
- Broad source cleanup outside the three dirty XPS files.
- Full pytest.

## 13. Recommendation On Entering `GOAL: XPS Source Hunk Split Preflight`

Recommendation: yes, continue into `GOAL: XPS Source Hunk Split Preflight`, but only as a narrow preflight.

Reason: the committed no-artifact tests exist, staged is 0, and the XPS dirty surface is currently limited to three dirty files. The large source diffs are still mixed and blocked, so a hunk split preflight is the correct next checkpoint before any source changes, staging, or commits.

## 14. Recommended Minimal Next Scope

Minimum next scope:

1. Inspect only:
   - `src/core/xps_heterojunction.py`
   - `src/core/xps_in_situ.py`
   - `tests/test_xps_heterojunction_stacked.py`
   - committed contract tests in `tests/test_xps_no_artifact_contracts.py` as the reference contract.
2. Produce a hunk inventory that separates:
   - no-artifact contract hunks;
   - run-scoped output routing hunks;
   - visual/style hunks;
   - algorithmic peak/color/annotation hunks;
   - test-only hunks.
3. Do not stage, commit, run Origin, run real data, run full pytest, or generate artifacts during the preflight.

## 15. Blocking Points If Preflight Expands Beyond Scope

The preflight should stop if it requires any of the following:

- Origin execution.
- Visual artifact generation.
- Real data processing.
- Full pytest.
- Committing or staging before hunk classification is complete.
- Editing or repairing XPS functionality instead of only classifying the current source hunks.
