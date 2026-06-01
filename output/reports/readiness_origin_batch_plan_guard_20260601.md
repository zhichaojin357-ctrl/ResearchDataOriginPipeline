# Readiness Origin Batch Plan Guard

- Date: 2026-06-01
- `readiness` now checks `phase1_7_manifest_runner_plan.json`.
- The origin-batch plan must match the expected Phase 1.6 count, skip all completed items, have zero blocked items, and keep Origin launch flags false.
- Targeted verification: `tests/test_readiness.py` passed 20 tests with 2 upstream openpyxl warnings.
- Full verification: `D:\Python\python.exe -m pytest` passed 213 tests with 2 upstream openpyxl warnings; `deps-audit`, `validate`, real Phase 1.6 `origin-batch --dry-run`, default readiness, and portable readiness all exited 0.
