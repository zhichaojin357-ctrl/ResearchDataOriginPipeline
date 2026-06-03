# Output Keep Provenance List

日期：2026-06-03

This list identifies output-side material that must be kept or treated as keep-until-confirmed provenance. It is not a deletion plan.

## Canonical Locked Package

Keep:

- `output/phase1_6_origin_results_20260531_041538`

Reason:

- locked canonical result package;
- 1207 files, 72.40 MB;
- current policy says it must not be automatically deleted.

## Release-Freeze Manifests

Keep:

- `output/final_locked_results`

Reason:

- release-freeze pointer and manifest material;
- 7 files, 0.73 MB;
- should remain available as provenance for the locked package.

## Reports Explaining Code/Workflow Changes

Keep until explicit review:

- `output/reports/phase1_10_*`
- `output/reports/phase1_11_*`
- `output/reports/phase1_12*`
- `output/reports/phase1_13_*`
- `output/reports/phase1_14_*`
- `output/reports/non_xrd_*`
- `output/reports/xrd_*`
- `output/reports/epr_*`
- `output/reports/jeol_epr_*`
- `output/reports/bet_*`
- `output/reports/project_cleanup_audit_*`
- `output/reports/origin_operations_live_smoke.json`

Reason:

- these reports document previous processing, adapter, EPR, BET, XRD, Origin, package, and cleanup decisions;
- many are visible in Git status because `output/reports` is intentionally unignored.

## OPJU Exemplar References

Keep until explicit review:

- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- any copied OPJU reference or reference export inside `output/reports` or regression folders.

Reason:

- may be needed for visual comparison, OPJU validation, and regression evidence.

## Regression / Reference Material

Keep until explicit review:

- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/xps_heterojunction_stacked`
- `outputs/xps_in_situ_20260506`
- `output/reports/xps_template_compare/`
- `output/reports/phase1_14_single_queues/`

Reason:

- may still be used for OPJU, XPS, BET, XRD, and visual regression checks.

## Group Meeting / Manuscript Review Related Output

Keep until the user confirms the meeting/manuscript value is expired:

- XPS dedicated outputs:
  - `output/xps_heterojunction_stacked`
  - `outputs/xps_in_situ_20260506`
- EPR overlay/decode reports:
  - `output/reports/epr_*`
  - `output/reports/jeol_epr_*`
- XRD OPJU/reference reports:
  - `output/reports/xrd_*`
- BET OPJU/reference reports:
  - `output/reports/bet_*`
- material-selection package:
  - `output/material_collections`

Reason:

- these may contain presentation, review, or manuscript-facing evidence even if they are generated outputs.

## Tracked Reports

Tracked modified files under `output/reports` should not be deleted casually. They need a policy choice:

- restore if stale generated reports should match HEAD;
- commit only if accepted as formal lightweight records;
- leave dirty until the user reviews them.

This GOAL does not make that choice.
