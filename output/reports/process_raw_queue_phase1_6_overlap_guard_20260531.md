# Process Raw Queue Phase 1.6 Overlap Guard

Date: 2026-05-31

Direct use of `run.py process --from-queue output/reports/processing_queue.json` is now blocked when the raw queue overlaps the locked Phase 1.6 result package by `source_hash`.

Use the vetted dry-run output instead:

`output/reports/phase1_8_new_auto_process_queue.json`

The `process --auto-select` shortcut now has clearer CLI help, and regression coverage confirms it is also blocked by the same Phase 1.6 overlap guard when its generated raw queue is stale for the current package.

Verification so far:

- Targeted guard test: passed.
- Auto-select overlap guard test: passed.
- Related queue/readiness tests: passed, 25 tests.
- Full pytest: passed, 161 tests, 2 warnings.
- validate/readiness/deps-audit: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
