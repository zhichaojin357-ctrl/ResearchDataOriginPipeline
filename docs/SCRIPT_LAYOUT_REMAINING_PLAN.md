# Script Layout Remaining Plan

Date: 2026-06-03

## Completed In This Goal

- Current script README files now list the classified helper scripts.
- `docs/indexes/scripts_index.md` indexes the current classified paths instead of the old root paths.
- Old root script paths are marked as non-current entrypoints in `scripts/README.md`.

## Historical References To Keep

Do not rewrite old paths inside prior review/status evidence unless a future documentation cleanup explicitly targets historical wording:

- Batch 3A review materials for `scripts/regenerate_manual_review_filtered.py`.
- XPS in-situ drift review and hold documents for `scripts/build_xps_in_situ_20260506.py`.
- `patches/xps_in_situ_root_drift.patch`, which must keep the old root script path because it preserves the root drift diff.

## Future Checks

Before moving or deleting any additional script:

- Run `git grep` for the exact script basename and path.
- Separate current entrypoints from historical references.
- Update live imports, tests, README entries, and `docs/indexes/scripts_index.md` together.
- Keep broad helpers in function-first folders unless the script is strongly bound to one data type or raw format.

## Deferred Items

- No additional script movement is planned from this consistency pass.
- Do not re-create old root entrypoints during cleanup.
- Do not run Origin-related helpers during script layout work.
