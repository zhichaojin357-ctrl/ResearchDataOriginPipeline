# Validation Report Freshness Guard

- Date: 2026-06-01
- Scope: readiness validation evidence.
- Safety: no raw data changes, no workspace source changes, no F-drive writes, no Origin launch, no processing run.

## Problem

`run.py readiness` checked that `output/reports/validation_report.md` contained key pass markers, but it did not prove that the report was generated after validation-related source/config files changed. A stale report could therefore look current after edits to validation logic or validation inputs.

## Change

`run.py readiness` now fails `validation_report_current` when `validation_report.md` is older than any of these existing inputs:

- `src/core/validate.py`
- `src/core/deps.py`
- `src/core/project.py`
- `src/origin/adapter.py`
- `config/default.yaml`
- `config/processor_registry.yaml`
- `config/claim_policy.yaml`
- `config/plot_style.yaml`
- `config/sample_registry.yaml`
- `config/manual_overrides.yaml`

The existing pass-marker checks remain in place.

## Verification Snapshot

- RED: `D:\Python\python.exe -m pytest tests/test_readiness.py::test_readiness_fails_when_validation_report_is_older_than_validation_inputs -q` failed before implementation.
- GREEN: the same test passed after implementation.
- `D:\Python\python.exe -m pytest tests/test_readiness.py -q`: 16 passed, 2 warnings.
- `D:\Python\python.exe -m pytest`: 179 passed, 2 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0; 21 checks, 0 failures, 0 warnings.
- Residual process check after a short wait: no `python`, `EXCEL`, `Origin`, or `OriginPro` process remained.

## Files Updated

- `src/core/readiness.py`
- `tests/test_readiness.py`
- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
