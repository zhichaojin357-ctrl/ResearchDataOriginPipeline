# XPS CLI Hunk Split Review

Date: 2026-06-03

## Scope

Reviewed:

- `src/cli.py`
- focused grep references for XPS and run-scoped output CLI terms

No Origin command was run. No output artifacts were generated.

## Findings

`src/cli.py` currently contains exactly one dirty hunk in this scope:

- `xps-heterojunction-stacked --with-origin` help text now says Origin COM exports `OPJU/TIF`.

This hunk is XPS-specific and reflects the current working-tree heterojunction artifact contract. It is separable from both:

- future output routing CLI surfacing;
- the large XPS heterojunction/in-situ source diffs.

Search results:

- `run-output`: found only in `docs/FUTURE_OUTPUT_ROUTING_GOAL_SUMMARY.md` as a note that CLI surfacing was deferred.
- `output_run`: no current `src/cli.py` hit.
- `run_scoped`: no current `src/cli.py` hit.

## Hunk Classification

XPS CLI hunk:

- `src/cli.py`

Future output routing CLI flag hunk:

- none present in the current `src/cli.py` diff.

Unrelated CLI hunk:

- none present in the current `src/cli.py` diff.

## Strict Allowlist

Allowed for the CLI batch:

- `src/cli.py`
- `docs/XPS_CLI_HUNK_SPLIT_REVIEW.md`

Explicitly excluded:

- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`
- `tests/test_xps_in_situ.py`
- `src/core/runtime_paths.py`
- `src/core/process.py`
- `output/`
- `outputs/`

## Validation

Recommended validation:

```powershell
git diff --stat -- src/cli.py docs/XPS_CLI_HUNK_SPLIT_REVIEW.md
git diff --check -- src/cli.py docs/XPS_CLI_HUNK_SPLIT_REVIEW.md
D:\Python\python.exe -m py_compile src/cli.py
```

No pytest is recommended for this CLI-only hunk because the available XPS CLI tests create temporary `.xlsx` fixtures, and this GOAL forbids generating XLSX artifacts.

## Staging Recommendation

Recommended: yes.

Commit message:

```text
cli: clarify xps with-origin artifact contract
```

Exact staging command:

```powershell
git add src/cli.py docs/XPS_CLI_HUNK_SPLIT_REVIEW.md
```
