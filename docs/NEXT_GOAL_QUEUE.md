# Next GOAL Queue

Date: 2026-06-04

This queue reflects the current repository state after the MEGA convergence work. It supersedes older recommendations that still treated XPS no-artifact test design, broad output report policy, or `docs/agent_reports` classification as unfinished.

## A. Automatically Safe To Continue

### 1. GOAL: Review Dashboard Policy Decision

Purpose:

- decide whether `output/review_dashboard` remains tracked output content, gets untracked as generated dashboard artifacts, or is represented by docs-only policy;
- do not touch output content.

### 2. GOAL: Remaining Output README Decision

Purpose:

- decide whether `output/reports/README.md` should remain tracked and be reviewed, be restored in a future cleanup, or be represented by docs and later untracked with explicit approval;
- do not commit output content under a no-output-content goal.

### 3. GOAL: Data-Type Plot Fix Sequence Planning

Purpose:

- choose the next data-type plotting/visual task from BET, XPS, Raman, EIS, XRD, HPLC/LC, Mott-Schottky, UV-vis DRS, PL, photocurrent, and FTIR;
- define evidence and acceptance criteria;
- do not run Origin, process real data, or generate artifacts.

## B. Needs User Manual Confirmation

### `output/reports`

User decisions needed:

- whether `output/reports/README.md` should remain as tracked output content;
- whether clean historical tracked report files should remain tracked or be handled by a future explicit policy batch.

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
GOAL: Review Dashboard Policy Decision
```

Reason:

- source/config/tests/scripts are clean;
- `docs/agent_reports` is clean and committed;
- generated output report policy has been executed;
- the remaining output-facing dirty surface is the review dashboard plus `output/reports/README.md`;
- this can proceed without Origin, real data, or generated artifacts.

If the user wants docs-only follow-up first, use:

```text
GOAL: Final Documentation Pointer Polish
```

If the user wants XPS next, use:

```text
GOAL: XPS Origin And Visual Blocker Planning
```

Current XPS source/test files are clean, so another XPS source hunk split is not the immediate next step unless a new source diff appears.
