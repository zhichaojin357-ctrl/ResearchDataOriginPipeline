# Script Layout Batch Plan

Date: 2026-06-03

Scope: plan only. Do not execute staging, commit, move, delete, import updates, output edits, Origin runs, validation/readiness/full pytest, data processing, or plotting fixes from this document without explicit user approval.

## Batch 3A: Regenerate Manual Review Filtered Migration

Purpose:

Confirm whether `scripts/regenerate_manual_review_filtered.py` can be removed as a tracked root script and replaced by `scripts/reports/regenerate_manual_review_filtered.py`.

Allowed file scope:

- `scripts/regenerate_manual_review_filtered.py`
- `scripts/reports/regenerate_manual_review_filtered.py`
- `scripts/reports/README.md` only if needed for the report-script package context
- `tests/test_manual_review_filtered_report.py`
- `docs/indexes/scripts_index.md`
- optionally `docs/SCRIPT_LAYOUT_PREFLIGHT.md` or a small follow-up review report

Forbidden in Batch 3A:

- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- output/outputS files
- source/config changes
- plotting fixes
- Origin execution
- broad script-directory staging
- cache files

Required checks before staging:

```powershell
git status --short -- scripts tests/test_manual_review_filtered_report.py docs/indexes/scripts_index.md
git grep -n "regenerate_manual_review_filtered"
git grep -n "scripts/regenerate_manual_review_filtered.py"
git grep -n "scripts.reports.regenerate_manual_review_filtered"
git diff -- scripts/regenerate_manual_review_filtered.py scripts/reports/regenerate_manual_review_filtered.py tests/test_manual_review_filtered_report.py docs/indexes/scripts_index.md
```

Recommended verification after staging:

```powershell
git diff --cached --name-only
git diff --cached --check
D:\Python\python.exe -m pytest tests/test_manual_review_filtered_report.py
```

Commit gate:

- staged file list must contain only the approved Batch 3A paths
- no output/source/config/XPS/Origin-maintenance files staged
- targeted test passes, or the user explicitly accepts a no-test commit

## Batch 3B: Script Directory Documentation

Purpose:

Commit directory-level script-layout documentation after the migration decision is clear.

Allowed file scope:

- `scripts/README.md`
- `scripts/reports/README.md`
- `scripts/maintenance/README.md`
- `scripts/one_off/README.md`
- `scripts/data_types/README.md`
- `scripts/data_types/xps/README.md`
- optionally `docs/indexes/scripts_index.md` if the index is part of the same documentation-only staging decision

Forbidden in Batch 3B:

- Python script files
- test files
- source/config/output files
- deleted tracked scripts
- `__pycache__/`
- OPJU/TIF/PNG/XLSX/ZIP/large JSON artifacts

Required checks:

```powershell
git status --short -- scripts docs/indexes/scripts_index.md
git diff -- scripts/README.md scripts/reports/README.md scripts/maintenance/README.md scripts/one_off/README.md scripts/data_types/README.md scripts/data_types/xps/README.md docs/indexes/scripts_index.md
git diff --check -- scripts/README.md scripts/reports/README.md scripts/maintenance/README.md scripts/one_off/README.md scripts/data_types/README.md scripts/data_types/xps/README.md docs/indexes/scripts_index.md
```

Commit gate:

- staged file list is documentation-only
- no Python scripts staged
- no output or cache files staged

## Batch 3C: Reference Path Updates

Purpose:

Update remaining references only if Batch 3A or Batch 3B leaves live references pointing at stale script paths.

Allowed file scope:

- `tests/test_manual_review_filtered_report.py`
- `docs/indexes/scripts_index.md`
- minimal docs that reference moved script paths
- root status docs only if they contain stale script-path guidance that must be corrected

Forbidden in Batch 3C:

- script moves
- script deletions
- script functional edits
- source/config/output edits
- Origin execution
- full pytest
- any data processing

Required checks:

```powershell
git grep -n "scripts/regenerate_manual_review_filtered.py"
git grep -n "scripts.reports.regenerate_manual_review_filtered"
git grep -n "scripts/reports/regenerate_manual_review_filtered.py"
git diff -- <approved-reference-files>
git diff --check -- <approved-reference-files>
```

Recommended targeted verification when test imports change:

```powershell
D:\Python\python.exe -m pytest tests/test_manual_review_filtered_report.py
```

Commit gate:

- only approved reference files staged
- no script or output files staged unless this batch is explicitly merged with Batch 3A by user approval

## Deferred Work

Do not handle these in Batch 3A-3C unless explicitly re-scoped:

- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- any output/report generated artifact
- any plotting or data-type bug fix

The XPS script duplicate requires its own focused review because the root file has functional/CLI changes and the data-type copy has a different repo-root calculation.
