# Legacy Output Archive Report

Date: 2026-06-04

## Archive Location

External output root:

```text
D:\Codex Project\科研数据处理\输出
```

Legacy archive root:

```text
D:\Codex Project\科研数据处理\输出\老版输出\20260604_180002_project_output_archive
```

Archive manifest files:

```text
D:\Codex Project\科研数据处理\输出\老版输出\20260604_180002_project_output_archive\archive_manifest.json
D:\Codex Project\科研数据处理\输出\老版输出\20260604_180002_project_output_archive\archive_manifest.md
```

## Archived Sources

| Source | Archived files | Archived bytes | Tracked files removed from Git index | Protected or canonical packages present |
|---|---:|---:|---:|---|
| `output` | 5050 | 2381416472 | 180 | `phase1_6_origin_results_20260531_041538`, `phase1_5_processed_results_20260531_005613`, `final_locked_results`, `reports`, `review_dashboard` |
| `outputs` | 26 | 11586538 | 0 | `xps_in_situ_20260506` |

The old project `output/` directory was moved out of the repository. The old project `outputs/` files were moved out of the repository; the source side currently contains only empty directories because Windows reported `origin_projects` as in use during final directory removal. No product files remain under project `outputs/`.

## Git Index Handling

Before archiving:

- `git ls-files output outputs` returned 180 tracked paths.
- All tracked paths were under `output/reports` and `output/review_dashboard`.
- `outputs/` had no tracked files.

Action taken:

- Staged `git rm --cached` removals for the 180 tracked generated report/dashboard paths.
- Did not stage or commit external archive products.
- Did not use `git add .`, `git add -A`, directory-level add, wildcard add, or `git commit -a`.

## Safety Notes

- No F-drive file was modified, moved, renamed, or deleted.
- No original OPJU reference was modified or overwritten.
- The archive process preserved legacy products in the external archive before removing project-root product files.
- The external archive includes generated reports and historical/canonical packages for traceability. These files are not claimed as manually accepted manuscript-ready figures.

## Verification Snapshot

After archiving:

- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output` does not exist.
- `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\outputs` contains 0 files; only empty locked directory residue remained at verification time.
- `git ls-files output outputs` returned 0 paths after staged index removals.
