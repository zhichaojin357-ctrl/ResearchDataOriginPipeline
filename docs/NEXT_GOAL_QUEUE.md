# Next GOAL Queue

Date: 2026-06-03

## A. Automatically Continue

### 1. GOAL: XPS No-Artifact Contract Test Design

Purpose:

- design or refactor XPS tests so table/path/report contracts can be validated without creating OPJU/TIF/PNG/XLSX artifacts;
- separate heterojunction and in-situ no-Origin contracts from visual/Origin behavior;
- keep current dirty XPS source files blocked until the tests are safe.

### 2. GOAL: Remaining Documentation Dirty Review

Purpose:

- review `AGENTS.md`, compatibility/intake docs, indexes, method cards, and `ROOT_DOCS_EXTRA_CHANGES_HOLD.md`;
- commit only current, lightweight, non-generated documentation if still useful;
- do not include `docs/agent_reports/` in bulk.

### 3. GOAL: Data-Type Plot Fix Sequence Planning

Purpose:

- order future data-type plotting work after source/output boundaries are stable;
- choose between XPS, Raman, BET visual acceptance, EIS, XRD, HPLC/LC, and other workflows;
- do not run Origin until the user permits an Origin/visual GOAL.

## B. Needs User Manual Confirmation

### Output Manual Cleanup Review

User decisions needed:

- whether old `output/reports` history can be deleted or archived;
- whether `output/final_locked_results` should remain as local generated output;
- which OPJU/PNG/TIF/XLSX deliverables are still needed;
- whether historical `docs/agent_reports` should be retained, archived, or ignored.

### Tracked Output Reports

Tracked modified `output/reports` files remain visible. User must choose whether to:

- restore generated reports to HEAD;
- keep them dirty;
- or commit a narrow subset as formal lightweight reports.

## C. Needs Origin Or Visual Acceptance

These should not run under a no-Origin/no-artifact GOAL:

- XPS OPJU exemplar comparison;
- Raman OPJU warning review;
- BET visual acceptance;
- EIS plot contract review;
- XRD OPJU/exemplar visual review;
- HPLC/LC data workflow review if it requires real data or output generation.

## Recommended Next GOAL

```text
GOAL: XPS No-Artifact Contract Test Design
```

Reason:

- the only remaining source/test dirty files are XPS-related;
- they are blocked specifically because safe no-artifact tests do not yet exist;
- resolving that boundary will make later XPS source commits safer.
