# Output Cleanup User Checklist

日期：2026-06-03

This checklist is for manual cleanup after review. This GOAL did not delete, move, restore, or clean any `output/` or `outputs/` file.

## 1. Open These First

Review these before touching generated output:

- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`
- `output/material_collections`
- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/xps_heterojunction_stacked`
- `outputs/xps_in_situ_20260506`
- `output/reports`
- `output/review_dashboard`

## 2. Directories You May Review For Manual Deletion

These are likely generated historical output roots:

- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`
- `output/adapter_shadow_runs`

Review before deleting:

- Is it part of a final package?
- Is it referenced by a report or manifest?
- Does it contain OPJU/TIF/PNG/PDF evidence still useful for a presentation, manuscript, or comparison?
- Is there a backup outside this repository?

## 3. Do Not Delete First

Do not delete these without explicit confirmation:

- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`
- `output/material_collections`
- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/xps_heterojunction_stacked`
- `outputs/xps_in_situ_20260506`
- `output/reports`
- `output/review_dashboard`

## 4. Back Up Before Manual Cleanup

Before deleting, back up:

- canonical locked package;
- release-freeze manifests;
- OPJU reference/exemplar folders;
- XPS dedicated outputs;
- BET/EPR/XRD report families;
- material collection outputs;
- any XLSX or OPJU that was used for a meeting, paper, or manual comparison.

Recommended approach:

- move candidates to an external backup/quarantine folder first;
- do not permanently delete in the first pass;
- keep the backup until you have verified the repository still works and no needed evidence is missing.

## 5. Suggested Quarantine Instead Of Permanent Delete

Use an external folder outside this repository, for example:

```text
D:\OutputCleanupQuarantine\ResearchDataOriginPipeline\YYYYMMDD\
```

Do not use an in-repo quarantine folder unless you also update `.gitignore`, otherwise Git status may stay noisy.

## 6. Checks After Manual Cleanup

After manual cleanup, run:

```powershell
git status --short -- output outputs
git status --short -- output/reports
git status --short | Measure-Object -Line
```

Expected result:

- `output/outputs` dirty count should drop if untracked generated files were removed or quarantined.
- tracked modified files will stay dirty unless restored or committed.

## 7. Confirm Git Status Drops

Use:

```powershell
git status --short -- output outputs | Measure-Object -Line
git status --short -- output/reports | Measure-Object -Line
```

Current baseline before manual cleanup:

- `output/outputs`: 197
- `output/reports`: 194

## 8. If You Delete A Tracked File By Mistake

Git can restore tracked files:

```powershell
git restore -- path\to\tracked_file
```

Before restoring, check:

```powershell
git status --short -- path\to\tracked_file
```

## 9. If You Delete An Untracked File By Mistake

Git cannot restore untracked files.

Recovery requires:

- external backup;
- quarantine folder;
- Windows recycle bin, if deletion used normal Explorer deletion;
- rerunning the original workflow, only if that is explicitly safe and allowed.

For this project, do not rerun processing, Origin, or real data workflows unless a new GOAL explicitly allows it.
