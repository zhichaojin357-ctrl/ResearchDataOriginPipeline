# Readiness Active Docs Required Guard

`run.py readiness` now fails if required active entry documents are missing.

Current status:

- Required active entry documents: present
- Stale old-project references in active documents: none
- readiness: 20 checks, 0 failures, 0 warnings

Verification:

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 13 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.
