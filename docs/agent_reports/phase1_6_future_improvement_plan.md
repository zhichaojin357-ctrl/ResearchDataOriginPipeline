# Phase 1.7 Improvement Plan

- Updated: 2026-05-31 09:32:18

## Recommended Next Tasks

1. Add a manifest-driven Origin batch runner that records per-type retries and failures without overwriting `processing_report`.
2. Add a safe Origin parallelization proof: isolated COM sessions, unique output folders, per-instance lifecycle tracking, and explicit cap at 8 task-owned instances only after the proof passes.
3. Add a user-review checklist for Origin PNG previews and manual override proposals, including representative contact sheets by data type.
4. Extend the material-color registry only after confirming ambiguous sample codes such as BM, BC, MS, MB, and MT with the user.
5. Add optional visual-QC enrichment for tick-label policy, but keep it non-scientific and avoid OCR-driven claims unless explicitly needed.

## Completed Since Original Plan

- XPS processing was repaired for unnamed-column exports.
- 9 XPS no-Origin outputs and 9 XPS Origin exports now succeed.
- The Phase 1.6 package now contains 167 Origin result sets.

## Do Not Do Without User Approval

- Do not process all MANUAL_REVIEW files.
- Do not create PPT output or PPT source paths.
- Do not create kinetics, SEM, TEM, NMR, or MS processors.
- Do not modify the F-drive backup or workspace source data.
