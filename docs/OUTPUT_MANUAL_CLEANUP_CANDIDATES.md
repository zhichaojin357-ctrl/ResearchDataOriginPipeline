# Output Manual Cleanup Candidates

Date: 2026-06-03

## Policy

This document is a cleanup candidate list only.

This GOAL did not delete, move, rename, restore, or clean any file under `output/` or `outputs/`.

## Do Not Delete Automatically

These paths are locked or historically important and must stay until the user explicitly reviews and confirms removal:

- `output/phase1_6_origin_results_20260531_041538`
  - locked canonical result package;
  - do not treat Phase 1.6 as the current engineering phase, but do keep this package as the frozen result package.
- `output/final_locked_results`
  - release-freeze pointer/package material;
  - currently treated as generated/historical output, but not a deletion candidate without user confirmation.
- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`
- `output/material_collections`
- `output/xps_heterojunction_stacked`
- `outputs/xps_in_situ_20260506`

## Safe-Looking Generated Junk

These look like generated or temporary material. They can be reviewed by the user later, but this GOAL does not remove them:

- `output/reports/_tmp_xps_bi_check.png`
- `output/reports/tmp_opju_compare.json`
- `output/reports/tmp_opju_compare.md`
- `output/reports/xps_template_compare/`
- `output/reports/phase1_14_single_queues/`
- `output/reports/phase1_9_handoff_report_bundle.zip`
- `output/adapter_shadow_runs/`
- `output/bet_reference_compare/`
- `output/opju_exemplar_regression/`

## Historical Reports, Review Before Delete

These are generated report families. They should not be committed in bulk, but they may still be useful for audit history:

- `output/reports/phase1_9_*`
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

## Tracked Reports, Do Not Assume Ignore Will Hide Them

Several `output/reports` files are already tracked and modified. `.gitignore` cannot hide tracked files. The visible tracked report diffs should be handled by a separate policy decision:

- restore them to HEAD if they are stale generated reports;
- or commit a narrow, necessary subset if they are accepted as formal lightweight records;
- or keep them dirty until the user reviews historical output.

This GOAL makes no choice among those options.

## Future Run Output

New future outputs should go under:

```text
output/runs/<run_id>_<scope>/
```

That directory is generated output and should not enter git by default.

## User Manual Review Checklist

Before deleting old output manually, check:

- whether the path is part of the Phase 1.6 locked package;
- whether it is referenced by current status/index docs;
- whether it contains final OPJU/TIF/PNG deliverables the user still wants;
- whether it is regression/exemplar evidence;
- whether there is an equivalent committed manifest or report elsewhere.
