# Origin Batch Manifest Schema Hardening

- Date: 2026-06-01
- `origin-batch` manifest CSV headers are now validated before planning.
- Missing required headers, duplicate headers, blank headers, missing source locator headers, row-width mismatches, and CSV parse errors now produce concise CLI errors with exit code 2.
- Older package manifests without a `source_copy` column now use package-local `selected_source_data` SHA256 matching before falling back to workspace paths.
- The runner remains dry-run/planning-only and does not launch Origin.
- Targeted verification: `tests/test_phase1_7_manifest_runner.py` passed 18 tests.
- Real Phase 1.6 package dry-run: exit 0; 167 skipped as already complete; 0 planned; 0 blocked; Origin launch false.
- Full verification: `D:\Python\python.exe -m pytest` passed 211 tests with 2 upstream openpyxl warnings; `deps-audit`, `validate`, default `readiness`, portable readiness, and real Phase 1.6 `origin-batch --dry-run` all exited 0.
