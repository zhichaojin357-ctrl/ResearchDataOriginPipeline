# Future Output Routing Origin Review

## Batch

OR-4: Origin adapter path acceptance without running Origin.

## Purpose

Allow future with-Origin runs to construct OPJU, TIF, PNG preview, Origin job CSV/script, and Origin error-report paths under a run-scoped output root. This batch does not run Origin and does not change plotting style or visual semantics.

## Strict Allowlist

- `src/origin/adapter.py`
- `src/processors/base.py`
- `tests/test_output_routing.py`
- `docs/FUTURE_OUTPUT_ROUTING_ORIGIN_REVIEW.md`

## File Rationale

- `src/origin/adapter.py`: adds optional `output_root` support to Origin job builders and Origin error/success/material-color reports.
- `src/processors/base.py`: passes the already available process `output_root` into `export_plot` for future with-Origin runs.
- `tests/test_output_routing.py`: verifies path construction and Origin-disabled error reporting without launching Origin.

## Excluded Nearby Files

- `src/cli.py`: already dirty with unrelated XPS help text; no CLI option is staged in this batch.
- `src/origin/operations.py`: no path contract change required for this batch.
- `output/`, `outputs/`, OPJU/TIF/PNG/XLSX/ZIP: never staged.

## Risk

- Origin risk: LOW; tests explicitly disable Origin and only inspect path construction/error reporting.
- Output risk: LOW; tests use tmp_path run roots and check legacy paths are not created.
- Legacy compatibility risk: LOW; all new parameters default to `None`, retaining legacy output paths.
- Scientific claim risk: none; no plotting visual or interpretation logic is changed.

## Verification

```powershell
D:\Python\python.exe -m py_compile src/origin/adapter.py src/processors/base.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_output_routing.py tests/test_origin_adapter.py -q
git status --short -- output outputs
```

## Staging Recommendation

Recommended after py_compile, targeted pytest, `git diff --check`, and output-pollution checks pass.

Commit message:

```text
origin: accept run-scoped artifact paths
```
