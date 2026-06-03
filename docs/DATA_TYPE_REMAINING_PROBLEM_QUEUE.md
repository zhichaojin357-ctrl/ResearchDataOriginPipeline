# Data-Type Remaining Problem Queue

Date: 2026-06-04

Scope: planning only. No Origin, no real data processing, and no artifact generation were performed.

## Priority Queue

| Priority | Data type / workflow | Next smallest safe step | Blocked operation |
|---:|---|---|---|
| 1 | BET visual acceptance | Review existing BET requirement docs and define a no-new-output acceptance checklist | Visual acceptance and OPJU comparison require user/Origin evidence. |
| 2 | XPS | Plan a dedicated XPS Origin/visual blocker review; source hunk split is not needed while XPS source/test files are clean | Origin, OPJU/TIF/PNG/PDF generation, real data, and visual judgment. |
| 3 | Raman | Review existing OPJU warning evidence and define the exact delta to inspect | Origin/visual judgment required to accept or fix the warning. |
| 4 | EIS | Inspect committed plot-policy and processor contracts only | Any plot regeneration or Origin comparison is blocked. |
| 5 | XRD | Review existing XRD OPJU/exemplar comparison docs and remaining evidence gaps | Origin/visual review and any new artifact generation are blocked. |
| 6 | HPLC/LC exported data | Audit method card and registry expectations | Real data processing is blocked unless the user approves a dedicated data goal. |
| 7 | Mott-Schottky | Review method card and current processor contract | Visual acceptance and regenerated figures are blocked. |
| 8 | UV-vis DRS / Tauc | Define no-claim plotting and candidate extraction boundaries | Real data processing and scientific interpretation are blocked. |
| 9 | PL | Define plotting contract and interpretation guardrails | Mechanistic claims and regenerated plots are blocked. |
| 10 | Photocurrent | Review microamp-output contract and plotting policy | Carrier-separation claims and regenerated plots are blocked. |
| 11 | FTIR | Review method card and expected figure contract | New real-data processing and figure generation are blocked. |

## General Rules For The Next Data-Type Goal

- Use one data type per execution goal.
- Start from docs, registry, method cards, and committed tests.
- Do not launch Origin unless the goal explicitly allows Origin.
- Do not process real data unless the goal explicitly allows a named input scope.
- Do not generate OPJU/TIF/PNG/PDF/XLSX unless the goal explicitly allows artifacts.
- Do not make scientific claims from automated processing alone.

## Recommended First Planning Goal

```text
GOAL: Data-Type Plot Fix Sequence Planning
```

Minimum scope:

- rank BET, XPS, Raman, EIS, and XRD by user value and blocker cost;
- define the evidence needed for the top one;
- still do not run Origin or process real data.
