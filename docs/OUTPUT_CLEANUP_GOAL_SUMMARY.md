# Output Cleanup Goal Summary

日期：2026-06-03

## 1. Starting Dirty Counts

| 项目 | 数量 |
|---|---:|
| total dirty | 277 |
| staged | 0 |
| `output/outputs` dirty | 197 |
| `output/reports` dirty | 194 |
| `output/outputs` tracked modified | 45 |
| `output/outputs` tracked deleted | 0 |
| `output/outputs` untracked | 152 |
| ignored under `output/outputs` | 27 |

## 2. Main Dirty Output Sources

The dirty output surface is dominated by:

- `output/reports`: 194 dirty entries;
- `output/review_dashboard`: 3 dirty entries.

Most large generated roots are ignored and not visible as dirty:

- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`
- `output/material_collections`
- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/xps_heterojunction_stacked`
- `outputs/`

## 3. Never Auto Delete

Never auto delete:

- `output/phase1_6_origin_results_20260531_041538`
- `output/final_locked_results`

Also keep until explicit confirmation:

- locked/canonical packages;
- release-freeze manifests;
- OPJU exemplar references;
- regression/reference material;
- outputs tied to current group meeting, manuscript review, or visual comparison.

## 4. User Manual Review Candidates

User can manually review for possible delete/quarantine:

- `output/processed_data`
- `output/metadata`
- `output/origin_files`
- `output/figures_tif`
- `output/figures_preview`
- `output/adapter_shadow_runs`
- temporary/debug report artifacts such as `_tmp_*`, `tmp_*`, report ZIP/PNG, and pip logs.

Keep until user confirms:

- `output/reports`
- `output/review_dashboard`
- `output/material_collections`
- `output/opju_exemplar_regression`
- `output/bet_reference_compare`
- `output/xps_heterojunction_stacked`
- `outputs/xps_in_situ_20260506`

## 5. Dry-Run Script

Added:

- `scripts/maintenance/dry_run_output_cleanup_plan.py`

Behavior:

- read-only;
- no deletion;
- no moving;
- no output modification;
- prints risk-classified cleanup candidates to stdout;
- accepts `--root`;
- includes explicit `--dry-run` semantics;
- no external package dependency.

Verification:

```powershell
D:\Python\python.exe -m py_compile scripts/maintenance/dry_run_output_cleanup_plan.py
```

## 6. Safety Results

- Deleted output: no.
- Moved output: no.
- Restored output: no.
- Modified `output/` or `outputs/`: no.
- Ran Origin: no.
- Processed real data: no.
- Generated OPJU/TIF/PNG/PDF/XLSX/ZIP/large JSON: no.
- Staged/committed `output/` or `outputs/`: no.

## 7. Next Recommendation

Recommended next GOAL:

```text
GOAL: Tracked Output Reports Policy Decision
```

Minimum scope:

- decide whether tracked modified `output/reports` files should be restored to HEAD, kept dirty, or committed as selected lightweight evidence;
- do not batch commit generated reports;
- do not delete or move output without user confirmation.
