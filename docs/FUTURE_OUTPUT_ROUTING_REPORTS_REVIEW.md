# Future Output Routing Reports Review

## Batch

OR-3: Queue / report routing.

## Purpose

Route future triage, auto-queue, reviewed-queue, and origin-batch dry-run reports into a run-scoped `reports/` directory when callers provide an explicit run output root. Legacy defaults stay readable and writable for compatibility.

## Strict Allowlist

- `src/core/triage.py`
- `src/core/auto_queue.py`
- `src/core/reviewed_queue.py`
- `src/core/origin_batch.py`
- `tests/test_output_routing.py`
- `docs/FUTURE_OUTPUT_ROUTING_REPORTS_REVIEW.md`

## File Rationale

- `src/core/triage.py`: adds an optional run output root to triage options and writes triage reports under that run when present.
- `src/core/auto_queue.py`: adds an optional run output root for dry-run plan, markdown, and candidate queue outputs.
- `src/core/reviewed_queue.py`: adds an optional run output root for decision template and reviewed-queue plan reports.
- `src/core/origin_batch.py`: adds an optional run output root for manifest-runner dry-run reports.
- `tests/test_output_routing.py`: synthetic tmp-path tests for the new report-routing contracts.

## Excluded Nearby Files

- `src/cli.py`: already dirty with unrelated XPS help text and not staged in this batch.
- `src/origin/adapter.py`: reserved for OR-4 path construction only.
- `output/`, `outputs/`, `docs/agent_reports/`: never staged in this batch.

## Risk

- Output risk: LOW when `output_root` is supplied because tests use tmp_path run roots.
- Legacy compatibility risk: LOW because default arguments still use legacy `output/reports`.
- Origin risk: none; origin-batch remains planning only and no Origin automation is invoked.
- Real data risk: none; tests use synthetic CSV/JSON fixtures.

## Verification

```powershell
D:\Python\python.exe -m py_compile src/core/triage.py src/core/auto_queue.py src/core/reviewed_queue.py src/core/origin_batch.py tests/test_output_routing.py
D:\Python\python.exe -m pytest tests/test_output_routing.py -q
git status --short -- output outputs
```

## Staging Recommendation

Recommended after py_compile, targeted pytest, `git diff --check`, and output-pollution checks pass.

Commit message:

```text
core: route queue reports through run outputs
```
