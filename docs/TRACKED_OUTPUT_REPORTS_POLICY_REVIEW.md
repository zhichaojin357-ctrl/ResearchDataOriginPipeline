# Tracked Output Reports Policy Review

日期：2026-06-03

## Scope

本轮只审查 `output/reports` 的 Git 跟踪策略。没有删除、移动、恢复或清理任何本地 output 文件。

## Baseline Counts

| item | count |
|---|---:|
| `output/reports` dirty total | 194 |
| tracked reports | 220 |
| tracked modified reports | 43 |
| untracked reports | 151 |
| deleted reports | 0 |
| ignored reports | 12 |

当前 staged 为 0。

## File-Type Distribution

统计范围包括 tracked、visible untracked 和 ignored `output/reports` 文件。

| extension | count |
|---|---:|
| `.json` | 173 |
| `.md` | 172 |
| `.txt` | 15 |
| `.csv` | 10 |
| other | 6 |
| `.xlsx` | 3 |
| no extension | 2 |
| `.zip` | 1 |
| `.png` | 1 |

## Active Reports

这些当前先保持 tracked 或至少保持用户决策状态，不在本轮自动 untrack：

- `output/reports/README.md`
- `output/reports/processing_report.md`
- `output/reports/processing_summary.md`
- `output/reports/processing_queue.md`
- `output/reports/readiness_report.md`
- `output/reports/readiness_report_no_desktop.md`
- `output/reports/validation_report.md`
- `output/reports/dependency_audit.md`
- `output/reports/inventory_manifest.json`
- `output/reports/source_hash_index.json`
- `output/reports/traceability_groups.md`
- `output/reports/classification_report.md`

Reason: these are lightweight current/baseline status evidence or index-like reports. They may still be referenced by docs or manual review workflows.

## Historical Phase Reports

Examples:

- `output/reports/phase1_6_*`
- `output/reports/phase1_8_*`
- `output/reports/phase1_9_*`
- untracked `output/reports/phase1_10_*`
- untracked `output/reports/phase1_11_*`
- untracked `output/reports/phase1_12*`
- untracked `output/reports/phase1_13_*`
- untracked `output/reports/phase1_14_*`

Policy: user decision required for JSON/MD/CSV phase reports. Many are generated and likely should not be tracked long-term, but this GOAL does not batch untrack JSON, CSV, or Markdown reports.

## Temporary / Debug Reports

Examples:

- `output/reports/_tmp_xps_bi_check.png`
- `output/reports/tmp_opju_compare.json`
- `output/reports/tmp_opju_compare.md`
- `output/reports/xps_template_compare/`
- `output/reports/phase1_14_single_queues/`
- `output/reports/PHASE1_*_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json`
- `output/reports/phase1_13_pip_*.txt`
- `output/reports/*_temp_*_deleted_items_*.json`

Policy: temporary/debug artifacts should not be tracked. Existing ignore rules already cover `_tmp_*`, `tmp_*`, PNG, ZIP, XLSX, `xps_template_compare/`, and `phase1_14_single_queues/`. This GOAL adds narrow ignore rules for handoff JSON, pip TXT, and temp deleted-items JSON.

## Queue / Manifest Reports

Examples:

- `output/reports/processing_queue.json`
- `output/reports/processing_summary.json`
- `output/reports/data_triage_manifest.json`
- `output/reports/phase1_*_queue*.json`
- untracked `output/reports/*manifest*.json`

Policy: generated queue/manifest JSON should be reviewed before untracking. Do not batch untrack JSON in this GOAL because some manifest/index files may be evidence used by docs.

## Dependency / Pip Logs

Examples:

- tracked `output/reports/dependency_audit.json`
- tracked `output/reports/dependency_audit.md`
- untracked `output/reports/phase1_13_pip_*.txt`
- untracked package install/dry-run reports.

Policy: keep dependency audit reports until user decides. Ignore future pip TXT logs because they are generated package-operation logs.

## OPJU / Template Comparison

Examples:

- `output/reports/xps_template_compare/`
- `output/reports/phase1_14_opju_*`
- `output/reports/tmp_opju_compare.*`
- `output/reports/xrd_opju_*`
- `output/reports/bet_*`

Policy: comparison material is evidence, but temporary compare files and generated binary/report artifacts should not be tracked. JSON/MD reports remain user-decision items.

## Keep Tracked For Now

Keep tracked for now:

- active/baseline status reports;
- current lightweight Markdown summaries;
- dependency/readiness/validation reports until replaced by docs-level status;
- files possibly referenced by current docs or release status.

## Should Not Continue Tracked

The clearest current tracked generated artifacts are:

- `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`
- `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- `output/reports/phase1_9_manual_review_required_final.xlsx`

Policy: these are generated XLSX report artifacts. They are covered by `.gitignore` for future changes and are suitable for an explicit pilot `git rm --cached` while preserving local files.

## User Decision Required

User decision required:

- tracked modified JSON/MD baseline reports;
- tracked modified phase reports;
- tracked CSV report indexes;
- any Markdown report that may be intentionally part of project history;
- generated JSON/CSV if the desired policy is to move current status entirely into `docs/`.

This GOAL does not restore tracked report changes and does not batch untrack JSON/CSV/MD.
