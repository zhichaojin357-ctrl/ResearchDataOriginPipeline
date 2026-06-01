# Readiness Auto-Queue Provenance Guard

`run.py readiness` now verifies that every generated Phase 1.8 auto-queue candidate keeps dry-run provenance and an explicit no-processing note.

Current status:

- Candidate queue items: 105
- Missing dry-run provenance items: 0
- Missing no-processing note items: 0
- readiness: 20 checks, 0 failures, 0 warnings

Verification:

- `D:\Python\python.exe -m pytest tests\test_readiness.py -q`: passed, 12 tests.
- `D:\Python\python.exe run.py readiness`: exit 0.
