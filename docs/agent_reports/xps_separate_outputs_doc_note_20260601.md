# Separate XPS Outputs Documentation Note

- Date: 2026-06-01
- Scope: top-level project documentation.
- Safety: documentation-only; no data processing and no Origin launch.

## Problem

Top-level Phase 1.8 documentation correctly said the Phase 1.8 queue gate did not process new real datasets or launch Origin, but the repository also contains separate XPS figure-output products outside that queue gate. This could be misread as a contradiction.

## Change

Added a short note to:

- `README.md`
- `PROJECT_STATUS.md`
- `AGENT_HANDOFF.md`

The note points readers to:

- `docs/xps_origin_plotting_guardrails.md`
- `output/xps_heterojunction_stacked/reports/xps_heterojunction_stacked_summary.md`
- `outputs/xps_in_situ_20260506/xps_data_mapping_report.md`

These outputs are documented as dedicated XPS figure products, not Phase 1.8 queue-processing results.

## Verification Snapshot

- Confirmed all linked paths exist.
- `D:\Python\python.exe -m pytest`: 182 passed, 2 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0; 21 checks, 0 failures, 0 warnings.
