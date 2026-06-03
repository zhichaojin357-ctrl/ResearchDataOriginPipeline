# Output Layout Cleanup Plan

Audit time: 2026-06-03 15:36:34 +08:00.

Scope: layout audit only. No files were moved, deleted, regenerated, or normalized in this phase.

## Current Output Roots

There are two output roots:

- `output/`: primary project output root.
- `outputs/`: specialized/historical output root.

Do not infer current status from directory names alone. Use manifests, reports, and CLI dry-run evidence. Phase 1.6 is a locked canonical package, not the current engineering phase.

## Current `output/` Inventory

| directory | files | size MB | role |
|---|---:|---:|---|
| `adapter_shadow_runs` | 1 | 0.01 | Phase 1.13 adapter shadow-mode evidence |
| `bet_reference_compare` | 11 | 1.27 | BET OPJU/reference comparison trials |
| `figures_preview` | 193 | 17.18 | Generated PNG previews from current/historical runs |
| `figures_tif` | 189 | 45.88 | Generated TIF figures from current/historical runs |
| `final_locked_results` | 7 | 0.73 | Release-freeze pointer/final manifest artifacts |
| `material_collections` | 1584 | 2029.20 | Large mixed material-selection package; not a standard processing package |
| `metadata` | 183 | 1.04 | Generated metadata JSON by data type |
| `opju_exemplar_regression` | 88 | 15.27 | Copied OPJU references, reference exports, focused inputs, regression material |
| `origin_files` | 189 | 8.60 | Generated OPJU files from current/historical runs |
| `origin_jobs` | 0 | 0.00 | Temporary Origin job scripts/input; currently empty after cleanup |
| `phase1_5_processed_results_20260531_005613` | 709 | 28.10 | Historical no-Origin result package |
| `phase1_6_origin_results_20260531_041538` | 1207 | 72.40 | Canonical locked 167-result Origin package |
| `processed_data` | 197 | 9.04 | Generated processed CSVs from current/historical runs |
| `reports` | 416 | 28.74 | Markdown/JSON/CSV/XLSX/TXT/ZIP reports and dry-run plans |
| `review_dashboard` | 7 | 0.27 | Review dashboards/indexes |
| `unclassified` | 1 | 0.66 | Early scan/unclassified artifact |
| `xps_heterojunction_stacked` | 68 | 12.71 | Dedicated XPS heterojunction stacked outputs |

## Current `outputs/` Inventory

| directory | files | size MB | role |
|---|---:|---:|---|
| `xps_in_situ_20260506` | 26 | 11.05 | Dedicated/historical XPS in-situ output, not raw data |

## Formal Result Packages

Formal or locked packages:

- `output/phase1_6_origin_results_20260531_041538`
  - Canonical locked Origin package.
  - 167 rows in the package index.
  - Do not call this the current engineering phase.
- `output/final_locked_results/freeze_20260602_011419`
  - Release-freeze pointer and manifest artifacts around the canonical package.
  - Treat as release-baseline metadata, not a new processing run.

Historical package:

- `output/phase1_5_processed_results_20260531_005613`
  - Historical no-Origin package.
  - Keep for provenance, not as current next-batch input.

Specialized figure result groups:

- `output/xps_heterojunction_stacked`
- `outputs/xps_in_situ_20260506`

These are dedicated XPS workflows. They are not the general queue pipeline.

## Historical Results

Historical/current-mixed result directories:

- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`

These contain Phase 1.6-era outputs plus later Phase 1.14/BET/XRD/EPR outputs. They should not be used as source inputs for future processing. They are output evidence only.

## Regression / Comparison Materials

Regression and comparison directories:

- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/adapter_shadow_runs`
- `output/reports/xps_template_compare`
- selected `output/reports/phase1_14*`
- selected `output/reports/xrd_*`

These should be retained on disk for auditability. They should not be bulk committed and should not be treated as general production input unless a focused validation queue explicitly points to a copied input.

## Reports

`output/reports` is currently mixed:

- active readiness/validation/dependency reports
- phase reports
- handoff JSON/Markdown
- dry-run plans
- queue files
- pip install logs
- OPJU regression reports
- temporary comparison files
- XPS template preview/debug material

This directory is operational but too crowded. It should be treated as an evidence store, not a clean formal API.

## Directories Not To Use As Next Processing Input

Do not use these as next-batch input:

- `output/reports/processing_queue.json`
  - Raw queue; use `phase1_8_new_auto_process_queue.json` only after reviewing its plan.
- `output/material_collections/*/index.csv`
  - Mixed material-selection packages; run manifest normalization/dry-run first in a later execution phase if needed.
- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`
- `output/phase1_5_processed_results_20260531_005613`
- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`
- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/xps_heterojunction_stacked`
- `outputs/*`

Only use raw/workspace data roots or explicitly copied validation inputs when a reviewed queue/report states that is the intended input.

## Proposed Future Output Naming Policy

Do not move files now. For future runs, use a consistent layout so status is easier to audit:

```text
output/
  packages/
    locked/
      phase1_6_origin_results_20260531_041538/
    historical/
      phase1_5_processed_results_20260531_005613/
  runs/
    YYYYMMDD_HHMMSS_<scope>/
      processed_data/
      metadata/
      origin_files/
      figures_tif/
      figures_preview/
      reports/
  regression/
    opju_exemplar/
      YYYYMMDD_<scope>/
        input/
        reference_opju/
        reference_exports/
        generated/
        reports/
  reports/
    active/
    archive/
  review/
    dashboards/
    workbooks/
```

If the existing layout is kept, future generated names should at least include:

- date/time or phase
- data type
- source queue id hash
- run mode: `no_origin`, `with_origin`, `dry_run`, `regression`, `reference_export`
- whether the artifact is generated, copied reference, or formal package output

## Cleanup Policy For Later Light Execution

Allowed later, only with explicit user approval:

1. Add `.gitignore` rules for clearly temporary comparison files if not already covered.
2. Move only known temporary/debug files into an archive/quarantine folder, never delete directly.
3. Keep canonical packages and formal outputs in place.
4. Do not move F-drive backup data or workspace source data.
5. Do not rewrite report contents just to reduce clutter.

## Highest-Risk Layout Problems

- `output/reports` mixes active reports, old phase reports, pip logs, queues, temporary comparison files, and handoff bundles.
- `output/material_collections` is very large and can be mistaken for a standard result package.
- `output/opju_exemplar_regression` contains both copied inputs/references and temporary compare images.
- `output/processed_data`, `output/origin_files`, and figure directories mix Phase 1.6 outputs with later focused runs.
- `outputs/` exists separately and can be confused with `output/`, but it is specialized/historical.
