# CLI Input Directory Guard

- Date: 2026-06-01
- `scan`, `triage`, and `process` now validate input directories before writing outputs.
- Missing input directories and file paths fail with concise CLI errors and exit code 2.
- Targeted verification: `tests/test_phase1_contracts.py` passed 19 tests.
- Full verification: `D:\Python\python.exe -m pytest` passed 217 tests with 2 upstream openpyxl warnings; `deps-audit`, `validate`, real Phase 1.6 `origin-batch --dry-run`, default readiness, and portable readiness all exited 0.
- No Origin launch and no real user-data processing were performed.
