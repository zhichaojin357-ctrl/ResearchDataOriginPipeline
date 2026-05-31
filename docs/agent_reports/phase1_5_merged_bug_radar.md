# Phase 1.5 Merged Bug Radar

Created at: 2026-05-31 00:49 +08:00

## Summary

This radar combines local inspection, current reports, and read-only subagent review.

| priority | count | status |
|---|---:|---|
| P0 | 0 | none found |
| P1 | 4 | 2 fixed in loop 1; 2 open/deferred |
| P2 | 3 | open/deferred |
| P3 | 2 | open/deferred |

## P0

No active P0 found.

Specifically checked:

- no evidence that ordinary `pytest` launches Origin;
- no evidence that `triage` launches Origin;
- no evidence that `process --from-queue` launches Origin by default;
- no current processing failures;
- no generated output inside F-drive backup;
- no PPT or kinetics processor paths reported by validate.

## P1

### P1-001: Origin execution needed explicit positive authorization

Status: fixed in loop 1.

Before fix, non-queue `process` defaulted to `ProcessOptions.no_origin=False`, so direct processing without `--no-origin` could enter Origin export. This conflicted with Phase 1.5 safety policy.

Fix:

- `process` now has explicit `--with-origin`.
- `--no-origin` and `--with-origin` are mutually exclusive.
- `run_process()` normalizes default behavior to no-Origin unless `with_origin=True`.

### P1-002: Origin failure was recorded as generic processing failure

Status: fixed in loop 1.

Before fix, `export_plot()` returning failure caused metadata status `fail`, which `run_process()` recorded as failure stage `processing`.

Fix:

- `_failure_from_metadata()` maps Origin-related warning text to `failure_stage = origin_export`.

### P1-003: Origin lifecycle cleanup after timeout/failure needs stronger evidence

Status: open.

Current adapter has cleanup in PowerShell and reports failures, but Python-side timeout/fallback paths could provide clearer residual-process evidence. This needs a bounded follow-up patch with tests.

### P1-004: Broader safe promotion flow is not yet implemented

Status: open/in progress.

Read-only safe-promotion analysis identified 149 conservative MANUAL_REVIEW candidates, but no promotion queue files have been generated yet.

## P2

### P2-001: `.xls` parsing gap due missing `xlrd`

Status: open.

Triage reports 35 parser errors requiring `xlrd >= 2.0.1`. The current instruction forbids installing/upgrading dependencies without explicit user permission, so this remains a warning unless handled by documentation or optional dependency installation approval.

### P2-002: Global pytest Origin guard could be stronger

Status: open.

Existing tests mock Origin paths, but a future test could accidentally call real Origin. A global fixture can hard-block real Origin calls except tests explicitly marked as mocked.

### P2-003: `origin_errors.md` currentness can be improved

Status: open.

`write_origin_success()` clears stale errors, but ordinary `export_plot()` success does not clearly reset the error report. Needs a small adapter patch.

## P3

### P3-001: Reports can be made more concise for large real-data batches

Status: open.

Current reports are complete but long. A compact dashboard/index would make review easier.

### P3-002: User-facing final result folder still needs a clearer browsing structure

Status: in progress.

The user requested a new folder containing selected data, processed outputs, previews/screenshots, and labels tying each output to its source file.

## Fixed In Loop 1

- P1-001 explicit Origin authorization.
- P1-002 Origin failure stage.

## Open Issues To Continue

- P1-003 Origin lifecycle residual-process reporting.
- P1-004 safe promotion queue generation and no-Origin processing.
- P2-001 `.xls` parser gap.
- P2-002 global pytest Origin guard.
- P2-003 stale Origin error cleanup.
- P3-001 compact report/dashboard improvement.
- P3-002 final result browser folder.
