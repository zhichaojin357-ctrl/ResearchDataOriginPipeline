# Output Manual Cleanup Review

日期：2026-06-03

## Scope

本轮只审查 `output/` 和 `outputs/` 的 dirty/generated/historical artifacts。没有删除、移动、恢复、清理或修改任何 `output/` / `outputs/` 文件。

## Baseline

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

`output/reports` 的 dirty 构成：

| 类型 | 数量 |
|---|---:|
| tracked modified | 43 |
| tracked deleted | 0 |
| untracked | 151 |

## Directory Role Classification

Tracked count 是 Git 已跟踪文件数；visible untracked 是当前 `git status` 可见 untracked 数，不包含 ignored 目录中的 untracked 文件。

| directory | files | size MB | dirty | tracked | visible untracked | role | auto-delete risk |
|---|---:|---:|---:|---:|---:|---|---|
| `output/phase1_6_origin_results_20260531_041538` | 1207 | 72.40 | 0 | 0 | 0 | locked/canonical package | NEVER AUTO DELETE |
| `output/final_locked_results` | 7 | 0.73 | 0 | 0 | 0 | release-freeze/provenance | NEVER AUTO DELETE |
| `output/phase1_5_processed_results_20260531_005613` | 709 | 28.10 | 0 | 0 | 0 | historical package | KEEP UNTIL USER CONFIRMS |
| `output/processed_data` | 197 | 9.04 | 0 | 0 | 0 | generated historical outputs | USER CAN REVIEW FOR DELETE |
| `output/metadata` | 183 | 1.04 | 0 | 0 | 0 | generated metadata | USER CAN REVIEW FOR DELETE |
| `output/origin_files` | 189 | 8.60 | 0 | 0 | 0 | generated OPJU outputs | USER CAN REVIEW FOR DELETE |
| `output/figures_tif` | 189 | 45.88 | 0 | 0 | 0 | generated figure outputs | USER CAN REVIEW FOR DELETE |
| `output/figures_preview` | 193 | 17.18 | 0 | 0 | 0 | generated preview outputs | USER CAN REVIEW FOR DELETE |
| `output/reports` | 416 | 28.74 | 194 | 220 | 151 | mixed report evidence store | KEEP UNTIL USER CONFIRMS |
| `output/review_dashboard` | 7 | 0.27 | 3 | 6 | 1 | review dashboard evidence | KEEP UNTIL USER CONFIRMS |
| `output/material_collections` | 1584 | 2029.20 | 0 | 0 | 0 | large material-selection package | KEEP UNTIL USER CONFIRMS |
| `output/opju_exemplar_regression` | 88 | 15.27 | 0 | 0 | 0 | regression/reference material | KEEP UNTIL USER CONFIRMS |
| `output/bet_reference_compare` | 11 | 1.27 | 0 | 0 | 0 | regression/reference material | KEEP UNTIL USER CONFIRMS |
| `output/adapter_shadow_runs` | 1 | 0.01 | 0 | 0 | 0 | generated shadow-run evidence | USER CAN REVIEW FOR DELETE |
| `output/xps_heterojunction_stacked` | 68 | 12.71 | 0 | 0 | 0 | dedicated XPS output evidence | KEEP UNTIL USER CONFIRMS |
| `output/runs` | 0 | 0.00 | 0 | 0 | 0 | future generated run output | USER CAN REVIEW FOR DELETE |
| `output/regression` | 0 | 0.00 | 0 | 0 | 0 | future regression output | USER CAN REVIEW FOR DELETE |
| `outputs/xps_in_situ_20260506` | 26 | 11.05 | 0 | 0 | 0 | historical XPS in-situ output | KEEP UNTIL USER CONFIRMS |

## File-Type Classification

| extension | count | size MB | tracked | visible untracked | recommended policy | `.gitignore` future coverage |
|---|---:|---:|---:|---:|---|---|
| `.tif` | 605 | 2048.63 | 0 | 0 | generated figure artifacts; never commit in bulk | covered in generated roots |
| `.png` | 969 | 88.64 | 0 | 0 | generated previews/comparisons; review before delete | covered in generated roots and report PNG rule |
| `.opju` | 536 | 37.78 | 0 | 0 | Origin project artifacts; preserve canonical/reference packages | covered in generated roots |
| `.json` | 855 | 35.54 | 90 | 83 | lightweight reports/manifests; review per family | `output/reports/*.json` intentionally visible |
| `.csv` | 983 | 23.52 | 9 | 1 | data tables/manifests; review before delete | generated roots covered; report CSV visible |
| `.md` | 205 | 1.83 | 124 | 53 | report prose/evidence; review before commit/delete | `output/reports/*.md` intentionally visible |
| `.xlsx` | 198 | 8.14 | 3 | 0 | spreadsheets; tracked ones require explicit policy | future report XLSX ignored, tracked files remain visible |
| `.txt` | 305 | 7.02 | 0 | 15 | logs/pip outputs/reference text; review by family | logs ignored globally, report TXT visible |
| `.pdf` | 6 | 0.86 | 0 | 0 | generated deliverable artifacts; keep until reviewed | covered in generated roots |
| `.py` | 12 | 0.10 | 0 | 0 | generated/copied helper scripts; review manually | generated roots covered |
| `.zip` | 1 | 0.02 | 0 | 0 | generated bundle; not commit by default | report ZIP ignored |
| no extension | 41 | 13.81 | 0 | 0 | unknown or Origin-related payloads | depends on root |
| other | 360 | 16.26 | 0 | 0 | mixed generated/reference files | depends on root |

## Dirty Report Families

Largest visible dirty report families:

| family | dirty count | likely role |
|---|---:|---|
| baseline reports | 24 | active/historical generated reports |
| `phase1_13_pip*` | 15 | pip dry-run/install logs |
| `epr*` | 9 | EPR overlay/decode reports |
| `xrd*` | 8 | XRD OPJU/reference reports |
| `phase1_13_package*` | 6 | optional adapter package reports |
| `phase1_11_final*` | 6 | package validation reports |
| `phase1_14_opju*` | 5 | OPJU exemplar regression reports |
| `phase1_10_material*` | 5 | material collection reports |

Extension/status distribution for `output/reports` and `output/review_dashboard`:

| type | count |
|---|---:|
| `.json` untracked | 83 |
| `.md` untracked | 53 |
| `.md` modified | 24 |
| `.json` modified | 19 |
| `.txt` untracked | 15 |
| `.xlsx` modified | 1 |
| `.csv` untracked | 1 |
| `.csv` modified | 1 |

## Findings

- `output/phase1_6_origin_results_20260531_041538` is a locked canonical result package and must not be deleted automatically.
- `output/final_locked_results` is release-freeze/provenance material and must not be deleted automatically.
- Most large generated roots are ignored already, which is why they are not dirty despite containing many artifacts.
- Visible dirty is dominated by `output/reports`, because reports are intentionally unignored for review.
- Several tracked report files are modified; `.gitignore` cannot hide tracked changes.
- Manual cleanup should start with review and backup/quarantine planning, not deletion.

## Recommendation

Proceed with a manual review workflow, not automatic cleanup:

1. Review `docs/OUTPUT_KEEP_PROVENANCE_LIST.md`.
2. Review `docs/OUTPUT_DELETE_CANDIDATES_BY_RISK.md`.
3. Use `docs/OUTPUT_CLEANUP_USER_CHECKLIST.md` before deleting anything manually.
4. If using the dry-run helper, run it only as a read-only inventory command.
