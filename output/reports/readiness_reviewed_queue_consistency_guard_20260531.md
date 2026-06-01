# Readiness Reviewed-Queue Consistency Guard

`run.py readiness` now verifies that reviewed-queue proposal JSON, user decision CSV template, and dry-run plan are current and internally consistent.

Current status:

- Proposals: 18
- Decision rows: 18
- Approved: 0
- Blocked: 0
- Will launch Origin: false
- Will run process: false
- readiness: 21 checks, 0 failures, 0 warnings

Verification:

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 14 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.
