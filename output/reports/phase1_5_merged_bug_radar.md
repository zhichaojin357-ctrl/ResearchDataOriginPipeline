# Phase 1.5 Merged Bug Radar

See `docs\agent_reports\phase1_5_merged_bug_radar.md` for the full report.

## Counts

- P0: 0
- P1: 4
- P2: 3
- P3: 2

## Fixed In Loop 1

- P1-001: Origin execution now requires explicit `--with-origin`; default processing is no-Origin.
- P1-002: Origin export failures are recorded with `failure_stage = origin_export`.

## Open

- P1-003: Origin lifecycle residual-process reporting.
- P1-004: Safe promotion queue generation and no-Origin processing.
- P2-001: `.xls` parser gap due missing optional `xlrd`.
- P2-002: Global pytest Origin guard.
- P2-003: stale Origin error cleanup.
- P3-001: compact reports/dashboard.
- P3-002: final result browser folder.
