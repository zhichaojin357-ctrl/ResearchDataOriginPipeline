# Tracked Output Reports Untrack Plan

日期：2026-06-03

## Policy

This plan only covers Git index tracking. It does not delete local files.

Allowed action for this GOAL:

- explicit-path `git rm --cached -- <file>` for generated output report artifacts.

Forbidden:

- directory-level `git rm --cached`;
- wildcard `git rm --cached`;
- deleting or moving local files;
- untracking protected packages;
- untracking JSON/CSV/MD batches without user confirmation.

## Candidate Categories

| category | proposed action | risk | covered by `.gitignore` |
|---|---|---|---|
| tracked generated XLSX reports | `git rm --cached` pilot | low-medium; local files retained | yes, `output/reports/*.xlsx` |
| temporary `_tmp_*` / `tmp_*` reports | add ignore only unless tracked explicit file exists | low | yes |
| generated report PNG / ZIP | add ignore only unless tracked explicit file exists | low | yes |
| `xps_template_compare/` | add ignore only; no directory untrack in this GOAL | medium | yes |
| `phase1_14_single_queues/` | add ignore only; no directory untrack in this GOAL | medium | yes |
| pip TXT logs | add ignore only | low | yes, newly added |
| handoff JSON snapshots | add ignore only | low | yes, newly added |
| temp deleted-items JSON | add ignore only | low | yes, newly added |
| generated JSON / CSV reports | user decision required | medium | no broad ignore |
| Markdown reports | keep visible / user decision required | medium-high | no broad ignore |

## Pilot `git rm --cached` Allowlist

These exact tracked files are generated XLSX report artifacts and are suitable for pilot untrack:

| path | reason | risk | status | ignore coverage | proposed action |
|---|---|---|---|---|---|
| `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx` | generated manual-review spreadsheet artifact | low-medium | tracked | `output/reports/*.xlsx` | `git rm --cached` |
| `output/reports/phase1_8_manual_review_required_filtered.xlsx` | generated manual-review spreadsheet artifact | low-medium | tracked | `output/reports/*.xlsx` | `git rm --cached` |
| `output/reports/phase1_9_manual_review_required_final.xlsx` | generated manual-review spreadsheet artifact | low-medium | tracked modified | `output/reports/*.xlsx` | `git rm --cached` |

Safety checks for each path:

- not under protected locked/canonical/release-freeze paths;
- local file must exist before and after untrack;
- future files are covered by `.gitignore`;
- no file contents are staged or committed;
- only index removal is committed.

## Keep Tracked For Now

Do not untrack in this GOAL:

- `output/reports/README.md`
- `output/reports/processing_report.md`
- `output/reports/processing_summary.md`
- `output/reports/readiness_report.md`
- `output/reports/validation_report.md`
- `output/reports/dependency_audit.md`
- `output/reports/inventory_manifest.json`
- `output/reports/source_hash_index.json`
- `output/reports/traceability_groups.md`
- tracked JSON/MD phase reports.

Reason: these may still serve as current/historical evidence, and JSON/MD untracking needs user confirmation.

## User Decision Required

Before any future batch untrack, the user should decide:

- Should `output/reports/*.json` stay visible or become ignored generated reports?
- Should `output/reports/*.csv` stay visible or become ignored generated report indexes?
- Should Markdown reports remain tracked as history, or should current status move fully to `docs/`?
- Should tracked modified active reports be restored, committed selectively, or kept dirty?

This GOAL only executes the XLSX pilot if all safety checks pass.
