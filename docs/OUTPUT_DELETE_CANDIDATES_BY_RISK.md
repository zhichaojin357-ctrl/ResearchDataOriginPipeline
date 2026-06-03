# Output Delete Candidates By Risk

日期：2026-06-03

This is a manual review list only. This GOAL did not delete, move, restore, or clean any file.

## A. Never Auto Delete

These paths must not be automatically deleted:

- `output/phase1_6_origin_results_20260531_041538`
  - locked canonical result package;
  - current file count: 1207;
  - current size: 72.40 MB;
  - keep as frozen provenance even though it is generated output.
- `output/final_locked_results`
  - release-freeze pointer/manifest material;
  - current file count: 7;
  - current size: 0.73 MB.

Also never auto delete:

- any directory explicitly labeled locked/canonical/release-freeze;
- any OPJU exemplar that is used as reference evidence;
- any output tied to accepted final delivery packages unless the user explicitly approves archival or deletion.

## B. Keep Until User Confirms

These may contain useful result evidence or regression/reference material. Keep them until the user confirms the exact deletion or quarantine scope:

- `output/phase1_5_processed_results_20260531_005613`
  - historical no-Origin package;
  - 709 files, 28.10 MB.
- `output/material_collections`
  - large material-selection package;
  - 1584 files, 2029.20 MB;
  - high risk because it may contain manually useful selection/provenance evidence.
- `output/opju_exemplar_regression`
  - OPJU exemplar regression/reference material;
  - 88 files, 15.27 MB.
- `output/bet_reference_compare`
  - BET comparison/reference material;
  - 11 files, 1.27 MB.
- `output/xps_heterojunction_stacked`
  - dedicated XPS output evidence;
  - 68 files, 12.71 MB.
- `outputs/xps_in_situ_20260506`
  - historical XPS in-situ output;
  - 26 files, 11.05 MB.
- `output/reports`
  - mixed report evidence store;
  - 416 files, 28.74 MB;
  - 194 visible dirty entries.
- `output/review_dashboard`
  - review dashboard evidence;
  - 7 files, 0.27 MB;
  - 3 visible dirty entries.

## C. User Can Review For Deletion

These are likely generated current/historical output roots. The user can manually review them for deletion or quarantine, but this GOAL does not delete them:

- `output/processed_data`
  - 197 files, 9.04 MB.
- `output/metadata`
  - 183 files, 1.04 MB.
- `output/origin_files`
  - 189 files, 8.60 MB.
- `output/figures_tif`
  - 189 files, 45.88 MB.
- `output/figures_preview`
  - 193 files, 17.18 MB.
- `output/adapter_shadow_runs`
  - 1 file, 0.01 MB.
- future generated roots if created:
  - `output/runs`
  - `output/regression`

Manual review rule:

- If a directory contains final OPJU/TIF/PNG/PDF deliverables the user still wants, keep or back up first.
- If there is no need to preserve historical output, move to an external backup/quarantine location before permanent deletion.
- Do not treat ignored status as delete approval.

## D. Likely Generated Junk

These look temporary or cache-like and can be reviewed first for quarantine. Still do not delete automatically:

- `output/reports/_tmp_xps_bi_check.png`
- `output/reports/tmp_opju_compare.json`
- `output/reports/tmp_opju_compare.md`
- `output/reports/xps_template_compare/`
- `output/reports/phase1_14_single_queues/`
- `output/reports/phase1_9_handoff_report_bundle.zip`
- `output/reports/phase1_13_pip_*.txt`
- `output/reports/non_xrd_temp_job_cleanup_deleted_items_*.json`
- `output/reports/xrd_temp_job_quarantine_deleted_items_*.json`

Recommended action:

- Review the file names and dates.
- If no longer needed, move them to external backup/quarantine first.
- After quarantine, re-run `git status --short -- output outputs` to verify status change.

## E. Unknown

Keep unknown items until reviewed:

- files without extension;
- `other` extension files;
- any folder not listed in `docs/OUTPUT_MANUAL_CLEANUP_REVIEW.md`;
- any report whose filename does not clearly map to a known phase, data type, or validation purpose.

Unknown items should be opened or inventoried before manual cleanup.
