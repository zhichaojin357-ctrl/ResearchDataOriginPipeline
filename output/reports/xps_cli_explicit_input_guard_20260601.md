# XPS CLI Explicit Input Guard

- Date: 2026-06-01
- `xps-heterojunction-stacked` now validates explicit `--bobc`, `--cwo`, and `--bc` file paths before creating outputs.
- Missing files or directory paths now fail with concise CLI errors and exit code 2.
- Targeted verification: `tests/test_xps_heterojunction_stacked.py` passed 11 tests with 2 upstream openpyxl warnings.
- Full verification: `D:\Python\python.exe -m pytest` passed 214 tests with 2 upstream openpyxl warnings; `deps-audit`, `validate`, real Phase 1.6 `origin-batch --dry-run`, default readiness, and portable readiness all exited 0.
- No Origin launch and no real user-data processing were performed.
