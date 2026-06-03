# Next GOAL Queue

Date: 2026-06-04

This queue reflects the current repository state after the whole-project convergence audit. It supersedes older recommendations that still treated XPS no-artifact test design as unfinished.

## A. Automatically Safe To Continue

### 1. GOAL: Remaining Documentation Dirty Review

Purpose:

- review `AGENTS.md`, root docs, compatibility/intake docs, indexes, method cards, and the existing untracked root doc;
- commit only reviewed, lightweight, formal documentation;
- do not bulk stage `docs/agent_reports/`;
- do not touch output content.

### 2. GOAL: Output Reports Markdown And Baseline Policy Decision

Purpose:

- decide whether tracked modified `output/reports` baseline reports should be restored, committed as formal lightweight evidence, or kept dirty;
- decide whether untracked Markdown reports under `output/reports` should be moved into docs, committed, ignored, or left visible;
- keep generated machine-readable JSON/CSV report families ignored unless the user asks to track a specific one.

### 3. GOAL: Data-Type Plot Fix Sequence Planning

Purpose:

- choose the next data-type plotting/visual task from BET, XPS, Raman, EIS, XRD, HPLC/LC, Mott-Schottky, UV-vis DRS, PL, photocurrent, and FTIR;
- define evidence and acceptance criteria;
- do not run Origin, process real data, or generate artifacts.

## B. Needs User Manual Confirmation

### `docs/agent_reports`

User decisions needed:

- whether historical phase agent reports should be committed, archived, ignored, or kept dirty;
- whether the newer untracked handoff documents are formal docs or session outputs;
- whether modified existing agent reports should be accepted.

### `output/reports`

User decisions needed:

- whether tracked modified JSON/MD/CSV baseline reports should remain tracked;
- whether untracked Markdown reports are formal evidence or generated report artifacts;
- whether any additional generated report files should be untracked with explicit paths.

### Old Output Cleanup

User decisions needed:

- whether old output report history can be deleted or archived locally;
- whether `output/final_locked_results` and canonical/release-freeze packages must remain untouched;
- which OPJU/PNG/TIF/XLSX deliverables are still needed.

## C. Needs Origin, Real Data, Or Visual Acceptance

Do not run these under a no-Origin/no-artifact goal:

- XPS OPJU exemplar comparison and visual review;
- Raman OPJU warning review;
- BET visual acceptance;
- EIS plot contract review;
- XRD OPJU/exemplar visual review;
- HPLC/LC workflow work if it needs real data;
- Mott-Schottky, UV-vis DRS/Tauc, PL, photocurrent, and FTIR plot regeneration or interpretation checks.

## Recommended Next GOAL

```text
GOAL: Remaining Documentation Dirty Review
```

Reason:

- source/config/tests/scripts are clean;
- generated machine-readable output reports are now covered by narrow ignore rules;
- the largest remaining non-output surface is `docs/agent_reports` plus formal documentation changes;
- this can proceed without Origin, real data, or generated artifacts.

If the user wants an output policy step first, use:

```text
GOAL: Output Reports Markdown And Baseline Policy Decision
```

If the user wants XPS next, use:

```text
GOAL: XPS Origin And Visual Blocker Planning
```

Current XPS source/test files are clean, so another XPS source hunk split is not the immediate next step unless a new source diff appears.
