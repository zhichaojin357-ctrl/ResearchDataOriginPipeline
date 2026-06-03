# Generated Artifact Policy

Date: 2026-06-03

## Purpose

This policy prevents future generated artifacts from continuing to pollute `git status`.

It does not delete files and does not make tracked files disappear from git. Already tracked files remain tracked even if they match a new ignore rule.

## Current `.gitignore` Baseline

The repository already ignored many generated output roots:

- `output/processed_data/`
- `output/metadata/`
- `output/figures_preview/`
- `output/figures_tif/`
- `output/origin_files/`
- `output/origin_jobs/`
- `output/phase1_*/`
- `output/unclassified/`
- `output/material_collections/`
- `output/xps_*/`
- `outputs/`

It intentionally unignored:

- `output/reports/`
- `output/reports/**`
- `output/review_dashboard/`
- `output/review_dashboard/**`

This means report history is still visible unless a later, narrower rule ignores a specific temporary/binary report pattern.

## Tracked Artifact Check

Tracked binary/report-like files currently include:

- `docs/agent_reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`
- `docs/agent_reports/phase1_8_manual_review_required_filtered.xlsx`
- `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`
- `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- `output/reports/phase1_9_manual_review_required_final.xlsx`

Because these are already tracked, new ignore rules do not remove them from git or hide their modifications.

## Rules Added In This GOAL

Generated output roots:

```gitignore
output/runs/
output/regression/
output/adapter_shadow_runs/
output/bet_reference_compare/
output/opju_exemplar_regression/
output/final_locked_results/
```

Generated report-side temporary/binary artifacts:

```gitignore
output/reports/_tmp_*
output/reports/tmp_*
output/reports/*.png
output/reports/*.zip
output/reports/*.xlsx
output/reports/xps_template_compare/
output/reports/phase1_14_single_queues/
```

## Rationale

| Pattern | Reason | Risk |
| --- | --- | --- |
| `output/runs/` | future run-scoped output root | low |
| `output/regression/` | future generated regression material | low |
| `output/adapter_shadow_runs/` | generated adapter/shadow output | low |
| `output/bet_reference_compare/` | generated comparison output | low |
| `output/opju_exemplar_regression/` | generated OPJU regression material | low |
| `output/final_locked_results/` | generated/historical locked result material; keep locally, do not commit as output | medium; do not delete automatically |
| `output/reports/_tmp_*` | temporary/debug report output | low |
| `output/reports/tmp_*` | temporary/debug report output | low |
| `output/reports/*.png` | generated report image artifact | low |
| `output/reports/*.zip` | generated report archive artifact | low |
| `output/reports/*.xlsx` | generated report spreadsheet artifact | medium; tracked XLSX remains tracked |
| `output/reports/xps_template_compare/` | generated XPS comparison material | low |
| `output/reports/phase1_14_single_queues/` | generated queue material | low |

## Rules Not Added

The following broad rules were intentionally not added:

- `output/`
- `output/reports/*.md`
- `output/reports/*.json`
- `docs/`
- `docs/agent_reports/`
- `src/`
- `tests/`
- `config/`

Reason:

- `output/` is too broad and would obscure historical package visibility.
- `output/reports/*.md` and `output/reports/*.json` may still be intentionally reviewed as lightweight reports.
- source, config, tests, and docs must remain visible.

## Effect

After the new ignore rules, visible dirty entries dropped from 290 to 281.

This confirms the rules are narrow: they hide obvious untracked generated roots/binaries while leaving tracked reports and ordinary docs visible for explicit decisions.

## Policy Going Forward

- New run outputs should use `output/runs/` and should not enter git.
- OPJU/TIF/PNG/XLSX/ZIP artifacts should not be committed unless the user explicitly requests a delivery package.
- Historical locked packages should be kept until user-reviewed, not deleted automatically.
- Tracked generated reports need a separate restore/commit/keep-dirty decision.
