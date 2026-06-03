# XPS Workflow Preflight

Date: 2026-06-03

## Scope

This preflight covers only the current XPS workflow dirty state:

- `src/cli.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`
- `tests/test_xps_in_situ.py`
- existing XPS script layout references

This round did not run Origin, did not process real XPS data, and did not generate OPJU/TIF/PNG/XLSX/ZIP artifacts.

## Start State

Current HEAD at the start of this preflight was `beb7135`.

Relevant dirty files found:

- `M src/cli.py`
- `M src/core/xps_heterojunction.py`
- `M src/core/xps_in_situ.py`
- `M tests/test_xps_heterojunction_stacked.py`

Relevant clean files in this scope:

- `src/core/runtime_paths.py`
- `src/core/process.py`
- `src/origin/adapter.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `tests/test_xps_in_situ.py`

The scoped diff is large:

- `src/cli.py`: one help-text hunk.
- `src/core/xps_heterojunction.py`: mixed Origin artifact, Origin script, plot styling, Cu2p color/annotation, and summary report changes.
- `src/core/xps_in_situ.py`: mixed output subdirectory, report/table location, matplotlib figure export, Origin project grouping, and style validation changes.
- `tests/test_xps_heterojunction_stacked.py`: tests for the mixed heterojunction Origin/visual changes.

## CLI Hunk

`src/cli.py` has a single XPS hunk:

- old help text: Origin exports `OPJU/TIF/PNG`
- new help text: Origin COM exports `OPJU/TIF`

No `--run-output`, `output_run`, or `run_scoped` CLI hunk is currently present in `src/cli.py`.

## XPS Heterojunction State

The heterojunction diff is not a pure no-Origin contract change. It includes:

- removal of the official `figures_preview` output directory from the task subdirs;
- temporary PNG preview handling inside Origin job space;
- changed Origin artifact success criteria from OPJU/TIF/PNG to OPJU/TIF;
- TIF DPI post-processing;
- Origin plot policy fields in generated scripts;
- Origin native gradient fill and axis/tick/page geometry changes;
- Cu2p color assignment and peak annotation behavior changes;
- summary report text and table schema changes.

These changes may be useful, but they cross no-Origin contract, Origin artifact policy, and visual/styling boundaries. They need separate review before entering git.

## XPS In-Situ State

The in-situ diff is also not a pure no-Origin contract change. It includes:

- new output subdirectories under the provided output directory;
- report and manifest relocation;
- table output relocation for `peak_positions_summary.xlsx`;
- matplotlib PNG/PDF/TIF figure output relocation;
- two Origin OPJU project groups;
- Origin TIF export and style validation reports;
- quality checks for TIF/PNG/PDF/OPJU artifact locations.

The diff still uses output paths passed by the caller; it is not yet integrated with the future run-scoped output helper layer.

## Test Availability

Available XPS tests:

- `tests/test_xps_heterojunction_stacked.py`
- `tests/test_xps_in_situ.py`

The heterojunction tests create temporary `.xlsx`, `.opju`, `.png`, or `.tif` fixture artifacts in several nodes. The in-situ production path writes `.xlsx`, `.png`, `.pdf`, and `.tif` artifacts. Because this GOAL explicitly forbids generating OPJU/TIF/PNG/XLSX/ZIP artifacts, these pytest nodes were not used as validation for commits in this preflight.

Safe checks for this round:

- `git diff --check` on scoped files.
- `py_compile` on edited Python files.

## Run-Scoped Output Integration

Future output routing core helpers already exist, but the current XPS workflow dirty code has not cleanly integrated with that contract:

- `src/core/runtime_paths.py` is clean in this XPS scope.
- `src/core/process.py` is clean in this XPS scope.
- XPS dedicated workflows still expose direct `output_dir` style contracts.
- No user-facing `--run-output` CLI hunk exists in `src/cli.py`.

## Recommended Batch Split

LOW risk:

- XPS CLI help-text clarification in `src/cli.py`.

HIGH risk / blocker:

- XPS heterojunction Origin/visual/artifact-policy changes.
- XPS in-situ output subdir, image export, Origin grouping, and style validation changes.
- XPS run-scoped output integration for dedicated workflows.
- XPS OPJU exemplar/visual acceptance.

## Preflight Conclusion

Only the `src/cli.py` help-text hunk is small enough for an automatic commit in this GOAL. The rest of the XPS source/test dirty state should stay uncommitted until a dedicated XPS workflow review can separate nonvisual contracts from Origin/visual/artifact behavior.
