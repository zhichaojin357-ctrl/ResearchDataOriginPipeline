# Script Layout Consistency Review

Date: 2026-06-03

## Scope

Docs/index-only synchronization after prior script layout commits. No `.py` script was moved, deleted, renamed, or edited in this review.

## Current Classified Scripts

- `scripts/reports/regenerate_manual_review_filtered.py`
  - report-generation helper;
  - replaces the old root path `scripts/regenerate_manual_review_filtered.py`.
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
  - XPS-specific helper;
  - replaces the old root path `scripts/build_xps_in_situ_20260506.py` for layout purposes.
- `scripts/maintenance/opju_exemplar_regression.py`
  - maintenance/regression helper;
  - not a production processor.
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
  - one-off JEOL EPR raw decode verification helper kept for traceability.

## Old Path References

`git grep` still finds old root paths, but the hits are historical status/review documents or the XPS root-drift patch:

- `scripts/regenerate_manual_review_filtered.py`
  - historical cleanup/status documents and Batch 3A review materials;
  - no live code or current README/index dependency found.
- `scripts/build_xps_in_situ_20260506.py`
  - historical XPS drift review/hold documents and `patches/xps_in_situ_root_drift.patch`;
  - no current script README/index entrypoint dependency found.

These historical references are intentionally not rewritten because they document earlier review evidence.

## Current README / Index Updates

Updated current script layout docs:

- `scripts/README.md`
  - lists current classified helpers;
  - warns not to use old root paths as current entrypoints.
- `scripts/reports/README.md`
  - lists `regenerate_manual_review_filtered.py`.
- `scripts/maintenance/README.md`
  - lists `opju_exemplar_regression.py` and marks it non-production.
- `scripts/one_off/README.md`
  - lists `verify_jeol_epr_decode_against_exports.py`.
- `scripts/data_types/README.md`
  - lists `xps/` as the current data-type folder.
- `scripts/data_types/xps/README.md`
  - lists `build_xps_in_situ_20260506.py` and points to drift-hold evidence.
- `docs/indexes/scripts_index.md`
  - already replaces old root entries with the current classified script paths.

## Misleading Current Paths

No misleading current README/index entrypoint still points to:

- `scripts/regenerate_manual_review_filtered.py`
- `scripts/build_xps_in_situ_20260506.py`

## Strict Allowlist

- `scripts/README.md`
- `scripts/reports/README.md`
- `scripts/maintenance/README.md`
- `scripts/one_off/README.md`
- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- `docs/indexes/scripts_index.md`
- `docs/SCRIPT_LAYOUT_CONSISTENCY_REVIEW.md`
- `docs/SCRIPT_LAYOUT_REMAINING_PLAN.md`

## Validation

Required before staging:

- `git diff --check -- <allowlist>`
- `git diff --cached --check` after staging.

No pytest is required because this batch is docs/index-only.

## Staging Recommendation

Recommended if staged files strictly match the allowlist and no `.py`, `output/`, or generated artifact appears.

## Commit Message

`docs: sync script layout references`
