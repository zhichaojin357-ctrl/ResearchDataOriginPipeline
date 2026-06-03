# XPS In-Situ Batch 3C Review

Date: 2026-06-03

Scope: review only. This document reviews whether
`build_xps_in_situ_20260506.py` can be committed as a pure script-layout move
from the root `scripts/` directory into `scripts/data_types/xps/`. No script was
edited, moved, deleted, staged, or committed in this review.

## Checked Paths

Core comparison paths:

- `HEAD:scripts/build_xps_in_situ_20260506.py`
- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`

Related review context:

- `docs/XPS_IN_SITU_SCRIPT_DRIFT_PREFLIGHT.md`
- `scripts/data_types/xps/README.md`
- `scripts/README.md`

## Commands Used

Read-only commands used in this review:

```powershell
git status --short
git status --short -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py docs/XPS_IN_SITU_SCRIPT_DRIFT_PREFLIGHT.md
git diff --stat -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py
git diff -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py
git diff --no-index -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py
git grep -n "build_xps_in_situ_20260506"
git grep -n "scripts/build_xps_in_situ_20260506.py"
git grep -n "scripts/data_types/xps/build_xps_in_situ_20260506.py"
```

No XPS in-situ generation script, Origin automation, `validate`, `readiness`, or
full `pytest` command was run.

## Current Git State For Review Files

- `scripts/build_xps_in_situ_20260506.py`: tracked modified.
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`: untracked.
- `docs/XPS_IN_SITU_SCRIPT_DRIFT_PREFLIGHT.md`: untracked.
- staged files: none.

`git diff --stat` for the tracked root script reports:

```text
scripts/build_xps_in_situ_20260506.py | 29 +++++++++++++++--------------
1 file changed, 15 insertions(+), 14 deletions(-)
```

Untracked files do not appear in that tracked diff stat.

## Three-Way Version Relationship

The three reviewed versions are:

- HEAD old root version:
  - tracked baseline at `HEAD:scripts/build_xps_in_situ_20260506.py`
  - blob: `d2257d2666635df8b81592e99361064b338dfd76`
- current root working-tree version:
  - `scripts/build_xps_in_situ_20260506.py`
  - blob: `71c9f50af13177b5ac1dcd71f38b60676ed31e9a`
- current nested working-tree version:
  - `scripts/data_types/xps/build_xps_in_situ_20260506.py`
  - blob: `3d787aa7ae4ab233285083df3eac586b83c7435f`

Equivalence checks:

- HEAD root equals current root working tree: false.
- HEAD root equals nested working tree: false.
- HEAD root adjusted from `parents[1]` to `parents[3]` equals nested working
  tree: true.
- current root working tree equals nested working tree: false.

Conclusion: the nested version is a pure relocation candidate. It preserves the
HEAD script behavior while changing only the repo-root parent depth required by
the new nested path.

## HEAD Old Version Vs Nested Migration Version

The nested migration version differs from HEAD only in path-depth logic:

```text
HEAD:   PROJECT_ROOT = Path(__file__).resolve().parents[1]
nested: PROJECT_ROOT = Path(__file__).resolve().parents[3]
```

All CLI behavior and entry behavior remain aligned with HEAD:

- `main() -> int`
- `argparse.ArgumentParser(description="Build CWO/BOBC/Dark/Light in-situ fitted XPS panels.")`
- `--output-dir` uses `type=Path`
- default output is `Path("outputs") / "xps_in_situ_20260506"`
- `--with-origin` help remains `"Also save an Origin OPJU project."`
- output directory resolution remains
  `args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir`
- `build_xps_in_situ_outputs(PROJECT_ROOT, output_dir, with_origin=args.with_origin)`
- `origin_ok` prints `str(result.origin_status.get("ok"))`
- `main()` returns `0`
- entry point is `raise SystemExit(main())`

This is suitable for a pure script-layout migration.

## HEAD Old Version Vs Current Root Drift Version

The current root working-tree version contains behavior-adjacent changes beyond
layout migration:

- changes conditional `sys.path` insertion to unconditional insertion.
- changes `main() -> int` to `main() -> None`.
- broadens the CLI description.
- changes `--output-dir` from a `Path` argument to a string default with manual
  `Path(args.output_dir)` conversion.
- changes `--with-origin` help wording.
- introduces a local `project_root` variable.
- changes `origin_ok` from raw status printing to `bool(...)` printing.
- changes names used in the missing-output message formatter.
- removes `return 0`.
- changes `raise SystemExit(main())` to direct `main()`.

These may be useful cleanup changes, but they are not required for relocating
the script and should stay out of a pure migration commit.

## Current Root Drift Vs Nested Migration Version

The root drift version and nested migration version are not equivalent. Their
differences include both the expected `PROJECT_ROOT` depth change and the
functional/CLI/entry behavior listed above.

The root drift version should be treated as a separate feature or behavior review
candidate, not as the source of truth for Batch 3C migration.

## Reference Review

`git grep` found no formal runtime source-code or test dependency on
`scripts/build_xps_in_situ_20260506.py`.

Reference classes:

- Formal code references:
  - none found pointing to the old root script path.
- Test references:
  - none found pointing to either script path.
  - existing XPS in-situ tests target `src.core.xps_in_situ`, not the script.
- README/current docs:
  - cleanup docs and current status/index docs mention the root script as a
    dirty-worktree or migration candidate.
  - `docs/indexes/scripts_index.md` already indexes the nested path.
- Historical reports:
  - prior cleanup review documents mention both paths as evidence.

Conclusion: old root-path references remaining in docs do not block a pure
migration, but any live status/index wording should be reviewed separately if it
would confuse future operators.

## Can Batch 3C Be A Pure Migration Commit?

Yes, with one important condition: preserve the current root drift before
removing or staging deletion of the root script.

A pure migration commit can be based on:

- delete old root script path from the tracked tree.
- add nested data-type-specific path.
- keep nested script content aligned with HEAD except for the required
  `PROJECT_ROOT` depth change.
- do not include the current root working-tree CLI/entry behavior changes.

The migration itself is not blocked by code references.

## Root Drift Hold Requirement

The root working-tree drift contains potential cleanup work. It should be held
before any action that deletes or overwrites `scripts/build_xps_in_situ_20260506.py`.

Recommended hold options for the next step:

- generate `docs/XPS_IN_SITU_ROOT_DRIFT_HOLD.md` summarizing the root drift
  changes and their possible intent; or
- generate `patches/xps_in_situ_root_drift.patch` from the root script diff.

This review did not generate a patch because no deletion, move, staging, or
overwrite was performed in this round. There is no immediate loss risk while the
root working-tree file remains in place. The risk appears when Batch 3C staging
actually removes the old root path.

## Recommended Batch 3C Staging Scope

Recommended only after the root drift has been held:

- `scripts/build_xps_in_situ_20260506.py`
  - staged as deletion of the old root path only.
  - do not stage the current root drift as a modification.
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
  - staged as the nested migration path.
- `docs/XPS_IN_SITU_SCRIPT_DRIFT_PREFLIGHT.md`
- `docs/XPS_IN_SITU_BATCH3C_REVIEW.md`

Potential drift-hold file, if the user chooses to commit it with the migration
review:

- `docs/XPS_IN_SITU_ROOT_DRIFT_HOLD.md`

Do not include unless explicitly authorized:

- `scripts/README.md`
- `scripts/data_types/xps/README.md`
- `src/`
- `config/`
- `tests/`
- `output/`
- `outputs/`
- any OPJU, TIF, PNG, XLSX, ZIP, or large JSON file
- any plotting function fix

## Recommended No-Output Verification For Staging Review

Before staging a later Batch 3C commit:

```powershell
git status --short -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py docs/XPS_IN_SITU_SCRIPT_DRIFT_PREFLIGHT.md docs/XPS_IN_SITU_BATCH3C_REVIEW.md
git grep -n "build_xps_in_situ_20260506"
D:\Python\python.exe -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/data_types/xps/build_xps_in_situ_20260506.py').read_text(encoding='utf-8'))"
git diff --cached --check
```

Do not run Origin, the XPS in-situ generation script, or any output-refreshing
command for this layout-only commit.

## Review Decision

Recommendation: proceed to XPS in-situ Batch 3C staging review only as a
conditional pure migration.

Condition: preserve the root-path drift first, then stage only the old root path
deletion, the nested migrated script, and the approved review documents.

There is no blocker in the nested migration content itself. The only staging
risk is accidental loss or accidental inclusion of the root working-tree drift.
