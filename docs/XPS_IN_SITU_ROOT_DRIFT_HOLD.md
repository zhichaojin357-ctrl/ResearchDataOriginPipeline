# XPS In-Situ Root Drift Hold

Date: 2026-06-03

Purpose: preserve the current root-path `build_xps_in_situ_20260506.py`
working-tree drift before any later pure migration removes the old root script
path. This hold is evidence only; it is not an approval to merge those behavior
changes into the script-layout migration.

## Scope

Reviewed paths:

- `HEAD:scripts/build_xps_in_situ_20260506.py`
- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`

Generated evidence:

- `docs/XPS_IN_SITU_ROOT_DRIFT_HOLD.md`
- `patches/xps_in_situ_root_drift.patch`

## Three-Version Relationship

- HEAD old root version:
  - official tracked baseline before this dirty-worktree cleanup sequence.
  - root path: `scripts/build_xps_in_situ_20260506.py`
- current root drift version:
  - working-tree modification at `scripts/build_xps_in_situ_20260506.py`.
  - contains CLI, entry-point, status-printing, and exit-behavior changes.
- current nested migration version:
  - working-tree untracked file at
    `scripts/data_types/xps/build_xps_in_situ_20260506.py`.
  - matches the HEAD root script after only changing `PROJECT_ROOT` from
    `parents[1]` to `parents[3]`.

Batch 3C migration should use the nested migration version as the pure relocation
candidate. The current root drift should remain separate.

## Root Drift Relative To HEAD

The current root-path script changes these CLI, entry, and output behaviors
relative to the HEAD tracked script:

- changes `sys.path` insertion from conditional insertion to unconditional
  insertion.
- changes `main() -> int` to `main() -> None`.
- broadens the parser description from fitted XPS panels to in-situ XPS figures
  and an editable Origin project.
- changes `--output-dir` from `type=Path` with a `Path(...)` default to a string
  default plus manual `Path(args.output_dir)` conversion.
- changes `--output-dir` help text from "under the project root" to "relative to
  the project root unless absolute".
- changes `--with-origin` help from "Also save an Origin OPJU project" to
  "Create editable Origin graph pages and export figures".
- introduces a local `project_root` variable before computing the output path.
- changes the core call from `build_xps_in_situ_outputs(PROJECT_ROOT, ...)` to
  `build_xps_in_situ_outputs(project_root, ...)`.
- changes `origin_ok` printing from the raw `origin_status["ok"]` value to a
  boolean cast.
- changes the variable names used in the missing-output message formatter.
- removes `return 0`.
- changes the module entry from `raise SystemExit(main())` to `main()`.

## Potentially Useful Drift

These pieces may be useful in a later feature or behavior review:

- clearer `--output-dir` handling for string input and absolute/relative paths.
- broader CLI help text for users expecting both figures and editable Origin
  outputs.
- explicit `project_root` variable, which may make future refactors clearer.
- boolean normalization for `origin_ok`, if downstream consumers expect a stable
  `True` or `False` string.

These possible benefits are unverified in this hold. They should not be treated
as accepted changes.

## Not For Pure Migration

The root drift must not be mixed into a pure Batch 3C migration commit because:

- it changes CLI and entry-point behavior, not only file location.
- it changes process exit behavior.
- it changes status-printing semantics.
- it is not required to move the script under `scripts/data_types/xps/`.
- the nested migration script already represents the pure relocation candidate.

## Future Feature Review

If the project later wants to absorb any root drift behavior, open a separate
XPS in-situ feature review. That review should:

- start from the nested path script after migration.
- compare against `patches/xps_in_situ_root_drift.patch`.
- decide which changes are intentional.
- run only explicitly approved no-output or targeted tests.
- avoid Origin and output generation unless the user explicitly authorizes them.

## What This Round Did Not Do

This round did not:

- delete `scripts/build_xps_in_situ_20260506.py`.
- move any script.
- modify any `.py` script.
- stage any file.
- commit any file.
- run the XPS in-situ generation script.
- run Origin.
- run `validate`, `readiness`, or full `pytest`.
- generate or modify output files.
