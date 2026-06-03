# Script Layout Preflight

Date: 2026-06-03

Scope: preflight only. No files were moved or deleted, no imports were modified, no source functionality was changed, no output files were touched, no validation/readiness/pytest command was run, no Origin command was run, and no git staging or commit was performed.

Baseline commit before this preflight: `3625b7c docs: add current project status and cleanup staging plan`.

## Commands Run

Read-only checks run in this preflight:

- `git status --short`
- `git ls-files scripts`
- `git status --short -- scripts`
- `git grep -n "regenerate_manual_review_filtered"`
- `git grep -n "scripts/regenerate_manual_review_filtered.py"`
- `git grep -n "scripts.reports.regenerate_manual_review_filtered"`
- `Get-Content scripts/README.md`
- script tree/status/function-entrypoint inspection commands

## Current Scripts Layout

Tracked scripts in `HEAD`:

- `scripts/README.md`
- `scripts/archive/README.md`
- `scripts/build_xps_in_situ_20260506.py`
- `scripts/maintenance/README.md`
- `scripts/one_off/README.md`
- `scripts/regenerate_manual_review_filtered.py`

Current working-tree script files visible on disk:

- `scripts/README.md`
- `scripts/archive/README.md`
- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/maintenance/README.md`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/README.md`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `scripts/reports/README.md`
- `scripts/reports/regenerate_manual_review_filtered.py`

Ignored/cache files also exist under `scripts/**/__pycache__/`. They are not script-layout candidates.

## Script Status

Tracked modified or deleted under `scripts/`:

- `M scripts/README.md`
- `M scripts/build_xps_in_situ_20260506.py`
- `D scripts/regenerate_manual_review_filtered.py`

Untracked under `scripts/`:

- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `scripts/reports/README.md`
- `scripts/reports/regenerate_manual_review_filtered.py`

## README Policy

Current `scripts/README.md` says:

- operational scripts live under `scripts/`
- deprecated scripts move to `scripts/archive/` only after references are checked
- organization should be function-first and data-type-second
- `scripts/data_types/<data_type>/` is only for scripts strongly bound to one instrument, one data type, or one raw format
- recognized subdirectories are `archive/`, `data_types/`, `maintenance/`, `one_off/`, and `reports/`

This matches the intended script-layout rule, but it is still an unstaged tracked modification.

## Regenerate Manual Review Filtered

Paths under review:

- old tracked path: `scripts/regenerate_manual_review_filtered.py`
- new working-tree path: `scripts/reports/regenerate_manual_review_filtered.py`

Current evidence:

- Old path exists in `HEAD`: yes.
- Old path exists in the working tree: no.
- New path exists in `HEAD`: no.
- New path exists in the working tree: yes.
- New path is untracked.
- `tests/test_manual_review_filtered_report.py` has a tracked modification changing the import from `scripts.regenerate_manual_review_filtered` to `scripts.reports.regenerate_manual_review_filtered`.
- `docs/indexes/scripts_index.md` has a tracked modification replacing the old root path with the new report-script path.
- `git grep -n "scripts/regenerate_manual_review_filtered.py"` finds only current status/cleanup documentation references, not live code imports or commands.
- `git grep -n "scripts.reports.regenerate_manual_review_filtered"` finds the modified test import and cleanup documentation references.

Function/entrypoint comparison:

- Both old HEAD content and the new working-tree file expose:
  - `norm_key`
  - `short_reason`
  - `action_for`
  - `phase16_keys`
  - `build_rows`
  - `write_csv`
  - `write_xlsx`
  - `write_report`
  - `main`
  - `if __name__ == "__main__"`
- Both inspected versions have 233 lines.
- A direct line comparison was not byte/text identical. The visible differences are concentrated in Chinese user-facing strings or encoding representation. Because the hash and text comparison are not identical, this preflight does not claim full equivalence.

Preflight conclusion:

`scripts/regenerate_manual_review_filtered.py` can enter the next migration/deletion candidate review, but only as a conditional candidate. Batch 3A must inspect the non-identical text differences, confirm that the changed strings are acceptable, stage the new report path and reference updates together, and run a targeted test/smoke check before confirming deletion.

This preflight did not delete or restore the old path.

## Current Layout Classification

Formal reusable scripts:

- None at root should be treated as clean reusable production entrypoints yet.
- `scripts/reports/regenerate_manual_review_filtered.py` is a reusable report helper candidate, pending Batch 3A equivalence and reference review.

Report-generation scripts:

- `scripts/reports/regenerate_manual_review_filtered.py`
- `scripts/reports/README.md`

Maintenance scripts:

- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/maintenance/README.md`

Note: `opju_exemplar_regression.py` imports Origin operation helpers and is Origin-related. Do not run it in layout cleanup unless the user explicitly authorizes Origin-related verification.

One-off scripts:

- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `scripts/one_off/README.md`

Data-type-specific scripts:

- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/README.md`
- `scripts/data_types/README.md`

Ambiguous or unsafe-to-move scripts:

- `scripts/build_xps_in_situ_20260506.py`
  - It is still tracked and modified at the root.
  - A new XPS-specific copy exists under `scripts/data_types/xps/`.
  - The root file's working-tree diff changes function behavior/signature text, not only layout.
  - Do not delete, overwrite, or stage it until a focused XPS-script migration review is approved.
- `scripts/**/__pycache__/`
  - Cache files only; do not stage.

## Suspected Migrations

High-confidence but not yet committed:

- `scripts/regenerate_manual_review_filtered.py` -> `scripts/reports/regenerate_manual_review_filtered.py`
  - Evidence: old tracked path deleted, new report path present, test import changed, scripts index changed, same function/entrypoint names.
  - Blocker: new and old text are not byte/text identical, so Batch 3A must review changed strings before confirming deletion.

Separate and higher-risk:

- `scripts/build_xps_in_situ_20260506.py` -> `scripts/data_types/xps/build_xps_in_situ_20260506.py`
  - Evidence: root tracked file remains modified and untracked XPS path exists.
  - Blocker: root file contains functional/CLI wording changes and the new XPS path has different `PROJECT_ROOT` depth. This should not be handled in Batch 3A.

## Batch 3 Candidates

Can enter later Batch 3 review:

- `scripts/reports/regenerate_manual_review_filtered.py`
- `scripts/reports/README.md`
- deletion confirmation for `scripts/regenerate_manual_review_filtered.py`
- `tests/test_manual_review_filtered_report.py`
- `docs/indexes/scripts_index.md`
- `scripts/README.md`
- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- `scripts/maintenance/README.md`
- `scripts/one_off/README.md`

Potentially later, but not in Batch 3A:

- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/build_xps_in_situ_20260506.py`

Cannot move or delete in the next small batch:

- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- any `scripts/**/__pycache__/`
- any source/config/test/output files outside an explicitly approved Batch 3 allowlist

## Largest Risks

The biggest current script-layout risk is mixing a real migration with unrelated functional drift:

- `regenerate_manual_review_filtered` has a plausible report-folder migration, but the file content is not identical.
- `build_xps_in_situ_20260506` has a duplicated root/data-type layout and root-file functional changes.
- modified tests and `docs/indexes/scripts_index.md` already point at the new report path, so staging only scripts without references would be inconsistent.

## Recommended Minimal Order

1. Batch 3A: review and stage only the `regenerate_manual_review_filtered` migration/deletion with its necessary import/index references.
2. Batch 3B: stage script-layout README files only.
3. Batch 3C: stage any remaining reference-path updates that were not included in 3A, after `git grep` confirms old references are not live.
4. Separate later review: XPS script root/data-type duplicate and any Origin-bearing maintenance script handling.
