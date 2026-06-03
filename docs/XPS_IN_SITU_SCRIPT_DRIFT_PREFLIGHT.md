# XPS In-Situ Script Drift Preflight

Date: 2026-06-03

Scope: review only. This preflight compares the root XPS in-situ helper with the
data-type-specific copy and records whether a later small script-layout batch can
handle the drift. No scripts, imports, source code, tests, output files, staged
files, or commits were changed by this review.

## Checked Paths

Core paths:

- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/README.md`
- `scripts/README.md`
- `docs/SCRIPT_LAYOUT_BATCH3B_REVIEW.md`

Related read-only references:

- `src/core/xps_in_situ.py`
- `tests/`
- `docs/`
- `output/` and `outputs/` references mentioning `xps_in_situ`

## Commands Used

Read-only status and diff checks:

```powershell
git status --short
git status --short -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py scripts/data_types/xps/README.md scripts/README.md
git diff --stat -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py scripts/data_types/xps/README.md scripts/README.md
git diff -- scripts/build_xps_in_situ_20260506.py scripts/data_types/xps/build_xps_in_situ_20260506.py scripts/data_types/xps/README.md scripts/README.md
git grep -n "build_xps_in_situ_20260506"
git grep -n "scripts/build_xps_in_situ_20260506.py"
git grep -n "scripts/data_types/xps/build_xps_in_situ_20260506.py"
git grep -n "xps_in_situ"
```

No Origin, XPS in-situ generation script, `validate`, `readiness`, or full
`pytest` run was executed.

## Git State For The Two Scripts

- `scripts/build_xps_in_situ_20260506.py`: tracked modified.
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`: untracked.
- `scripts/README.md`: clean after Batch 3B.
- `scripts/data_types/xps/README.md`: clean after Batch 3B.
- Staged files during this preflight: none.

Observed blob comparison:

- HEAD root blob: `d2257d2666635df8b81592e99361064b338dfd76`
- root working-tree blob: `71c9f50af13177b5ac1dcd71f38b60676ed31e9a`
- nested working-tree blob: `3d787aa7ae4ab233285083df3eac586b83c7435f`

The two working-tree scripts are not byte-identical or text-identical.

## Script Comparison

The nested script is equivalent to the HEAD root script after the expected path
depth adjustment:

- HEAD/root uses `PROJECT_ROOT = Path(__file__).resolve().parents[1]`.
- Nested/data-type path uses `PROJECT_ROOT = Path(__file__).resolve().parents[3]`.
- After only that `PROJECT_ROOT` depth adjustment, the nested file matches the
HEAD root version.

The current modified root script does not match the nested file. Its changes are
broader than a pure path migration.

## Root Working-Tree Drift

Compared with the nested script and the HEAD root script, the current modified
root script changes:

- `PROJECT_ROOT` setup: keeps `parents[1]` but changes `sys.path` insertion from
  conditional to unconditional.
- `main` signature: changes `main() -> int` to `main() -> None`.
- CLI description: changes from a fitted-panel-specific description to a broader
  "figures and editable Origin project" description.
- `--output-dir`: changes from `type=Path` with a `Path(...)` default to a string
  default plus manual `Path(args.output_dir)` conversion.
- `--with-origin` help text: changes wording.
- core call: introduces a local `project_root` variable.
- status output: changes `origin_ok` printing from the raw status value to
  `bool(...)`.
- missing-output message labels: changes printed names.
- process exit behavior: removes `return 0` and changes
  `raise SystemExit(main())` to direct `main()`.

These changes are functional or behavior-adjacent drift, not only relocation.
They should not be mixed into a script-layout cleanup batch without a separate
review.

## Reference Check

`git grep` found no formal source-code or test dependency on the old root script
path. Functional XPS in-situ tests import `src.core.xps_in_situ`, not either
script path.

Reference classes observed:

- Formal code:
  - `scripts/build_xps_in_situ_20260506.py` imports
    `src.core.xps_in_situ.build_xps_in_situ_outputs`.
  - `src/core/xps_in_situ.py` contains the formal implementation.
- Tests:
  - `tests/test_xps_in_situ.py` targets `src.core.xps_in_situ`.
  - `tests/test_runtime_path_configuration.py` imports core modules and does not
    depend on either script path.
- Current documentation and cleanup docs:
  - Several docs mention both root and nested script paths as known dirty-worktree
    items or script-layout candidates.
  - `docs/indexes/scripts_index.md` points to the nested
    `scripts/data_types/xps/build_xps_in_situ_20260506.py` path.
- Historical reports and output references:
  - XPS in-situ report/output references mention `outputs/xps_in_situ_20260506`
    and related generated artifacts, not a live dependency on the old root script.

Conclusion: old root-path references remain in documentation/status history, but
no formal runtime, source, or targeted test reference was found that requires
`scripts/build_xps_in_situ_20260506.py`.

## Layout Conclusion

The nested path is the better fit for the current script layout because this
helper is strongly bound to the XPS data type:

- preferred location: `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- old root location: `scripts/build_xps_in_situ_20260506.py`

However, the root working-tree script currently contains functional drift. A
later cleanup must decide whether to preserve any of that drift. It should not be
accepted automatically as part of a pure migration.

## Recommendation For XPS In-Situ Batch 3C Review

Batch 3C review can proceed, but it should stay narrow:

- Compare the HEAD root script against the nested relocated script.
- Treat the nested script as the pure relocation candidate because it matches
  HEAD except for the required `PROJECT_ROOT` parent-depth change.
- Treat the modified root script as a separate drift candidate and do not submit
  its behavior changes unless explicitly approved.
- Check and, if needed, update only live documentation references that still point
  to the root path.
- Do not include `src/`, `config/`, `tests/`, `output/`, `outputs/`, OPJU, TIF,
  PNG, XLSX, ZIP, or large JSON files.

Suggested minimum Batch 3C review scope:

- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- any directly related lightweight script-index or review document updates

Suggested no-output verification for a later staging review:

```powershell
git grep -n "build_xps_in_situ_20260506"
D:\Python\python.exe -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/data_types/xps/build_xps_in_situ_20260506.py').read_text(encoding='utf-8'))"
```

If targeted tests are allowed in a later review, prefer a narrow no-Origin test
such as:

```powershell
D:\Python\python.exe -m pytest tests/test_xps_in_situ.py -q
```

Do not run the XPS in-situ generation script during layout review unless the user
explicitly authorizes generation of new output.
