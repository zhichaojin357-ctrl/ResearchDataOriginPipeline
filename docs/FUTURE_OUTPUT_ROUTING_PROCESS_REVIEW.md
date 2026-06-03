# Future Output Routing Process Review

## Scope

This batch routes process and metadata artifacts into an explicit run output root.

## Strict Allowlist

- `src/core/project.py`
- `src/core/process.py`
- `src/core/metadata.py`
- `src/processors/base.py`
- `src/scanner/scanner.py`
- `tests/test_output_routing.py`
- `docs/FUTURE_OUTPUT_ROUTING_PROCESS_REVIEW.md`

## Purpose

`process` currently writes processed tables, metadata, processing reports, summaries, and review dashboard files through legacy `output/` helpers. This batch adds explicit `output_root` support so future process runs can write under `output/runs/<run_id>/` while preserving legacy behavior when no run root is supplied.

## Excluded Files

- `src/cli.py`, because it has a pre-existing XPS help-text dirty hunk and should not be mixed into this process-routing commit.
- `src/origin/adapter.py`, because Origin path acceptance is a separate OR-4 batch.
- `output/` and `outputs/`.

## Risks

- Output risk: MEDIUM. The batch changes shared output path helpers, so tests must prove legacy root is not touched when a run root is supplied.
- Origin risk: LOW for this batch. Test patches `export_plot` and uses `no_origin=True`.
- Real data risk: LOW. Test uses a synthetic XRD CSV in `tmp_path`.

## Targeted Checks

```powershell
D:\Python\python.exe -m py_compile src/core/project.py src/core/process.py src/core/metadata.py src/processors/base.py src/scanner/scanner.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_output_routing.py -q
git status --short -- output outputs
```

## Recommendation

Proceed if the explicit run-root test passes and no real `output/` changes are introduced.

Commit message:

```text
core: route process artifacts into run outputs
```
