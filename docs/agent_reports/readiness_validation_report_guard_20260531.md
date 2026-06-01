# Readiness Validation Report Guard

Date: 2026-05-31

## Change

`run.py readiness` now checks `output/reports/validation_report.md` before reporting the project ready.

The new check fails readiness when:

- the validation report is missing or empty;
- the report contains a `## Failures` section;
- deferred/reference registry semantics are not reported as pass;
- PPT forbidden paths are not reported as pass;
- kinetics processor path checks are not reported as pass.

## Reason

The readiness preflight already checked current artifacts and dry-run safety flags, but it could still pass if the latest validation report contained a safety failure. This guard makes readiness reflect the validation safety state instead of only artifact presence.

## Verification

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 3 tests.
- `D:\Python\python.exe run.py readiness`: passed, 13 checks, 0 failures, 0 warnings.
- `D:\Python\python.exe -m pytest`: passed, 159 tests, 2 warnings.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check: none found.
