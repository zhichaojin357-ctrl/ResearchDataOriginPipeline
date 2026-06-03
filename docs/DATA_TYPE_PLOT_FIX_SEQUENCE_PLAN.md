# Data-Type Plot Fix Sequence Plan

Date: 2026-06-04

Scope: planning only. No Origin, no real data processing, and no artifact generation were performed.

## Recommended Order

| Priority | Workflow | Why next | First small batch |
|---:|---|---|---|
| 1 | HPLC/LC exported data | High user value before group meeting if chromatogram/export tables need clearer handling; likely less coupled to OPJU visual style than XPS. | Inspect registry, method card, and representative exported table schemas only; define reader/plot contract without real-data processing. |
| 2 | BET visual acceptance | BET has local OPJU exemplars and a clearer visual target; method-card constraints are now documented. | Compare requirements against existing docs; define no-new-output acceptance checklist for adsorption/desorption branches. |
| 3 | Raman OPJU warning | Existing OPJU comparison reports flag a warning that must be accepted or fixed before relying on Raman figures. | Review warning evidence and define exact visual/contract delta; no Origin rerun yet. |
| 4 | EIS plot contract | EIS has shared plot-policy/origin helper coverage and can be verified by contract before visual rerun. | Inspect EIS method expectations and tests; define axis/legend/export contract. |
| 5 | XRD contract | XRD has exemplar comparison evidence and path cleanup reports, but visual/phase claims need care. | Review XRD OPJU/exemplar evidence gaps and forbidden-claim boundaries. |
| 6 | XPS Origin/OPJU visual validation | XPS source/test files are clean, but visual/OPJU evidence remains blocked. | Plan required Origin evidence and no-artifact contract references; do not edit source. |
| 7 | Mott-Schottky | Processor guards exist; plotting/axis contract still needs acceptance. | Review method card and current processor behavior; define plot contract. |
| 8 | UV-vis DRS / Tauc | Needs strong no-claim boundary for band positions and Tauc interpretation. | Define plotting and candidate extraction boundaries; do not infer CB/VB. |
| 9 | PL | Mechanistic interpretation risk is high. | Define plot-only contract and explicit forbidden claims. |
| 10 | Photocurrent | Microamp output contract exists; figure acceptance remains visual. | Review output-unit contract and plot policy. |
| 11 | FTIR | Likely lower immediate blocker value; interpretation must remain manual. | Define plot contract and forbidden functional-group claims. |

## Common Rules

- One data type per execution goal.
- Start with docs, registry, method card, tests, and existing reports.
- Do not process real data unless the user approves a named source scope.
- Do not run Origin unless the goal explicitly allows Origin.
- Do not generate OPJU/TIF/PNG/PDF/XLSX unless the goal explicitly allows artifacts.
- Do not infer scientific conclusions automatically.

## Highest-Value Pre-Meeting Path

Recommended next data-type planning goal:

```text
GOAL: HPLC/LC Exported Data Plot Contract Preflight
```

Reason:

- it can start as a read-only contract/schema review;
- it does not require immediate Origin or visual acceptance;
- it helps define whether HPLC/LC is a real processor workflow or an exported-data table/plot workflow.

If the user wants to prioritize existing visual outputs instead, use:

```text
GOAL: BET Visual Acceptance Preflight
```
