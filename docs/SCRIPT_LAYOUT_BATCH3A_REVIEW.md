# Script Layout Batch 3A Review

Date: 2026-06-03

Scope: review only for `regenerate_manual_review_filtered` migration. No `git add`, no `git commit`, no file deletion, no file move, no import edit, no source-function edit, no output edit, no Origin run, no validate/readiness/full pytest, and no XPS script handling was performed.

## Review Scope

Core paths reviewed:

- `scripts/regenerate_manual_review_filtered.py`
- `scripts/reports/regenerate_manual_review_filtered.py`
- `scripts/README.md`
- `scripts/reports/README.md`
- `tests/test_manual_review_filtered_report.py`
- direct references containing `regenerate_manual_review_filtered`

Explicitly not handled:

- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/`
- XPS in-situ scripts
- plotting functionality
- `output/`
- `src/`
- `config/`
- unrelated tests

## Commands Run

Status and diff:

```powershell
git status --short
git status --short -- scripts
git diff --stat -- scripts/regenerate_manual_review_filtered.py scripts/reports/regenerate_manual_review_filtered.py scripts/README.md scripts/reports/README.md tests/test_manual_review_filtered_report.py
git diff -- scripts/regenerate_manual_review_filtered.py scripts/reports/regenerate_manual_review_filtered.py scripts/README.md scripts/reports/README.md tests/test_manual_review_filtered_report.py
```

Reference checks:

```powershell
git grep -n "regenerate_manual_review_filtered"
git grep -n "scripts/regenerate_manual_review_filtered.py"
git grep -n "scripts.reports.regenerate_manual_review_filtered"
git grep -n --untracked "regenerate_manual_review_filtered"
```

Equivalence checks:

```powershell
git rev-parse HEAD:scripts/regenerate_manual_review_filtered.py
git hash-object scripts/reports/regenerate_manual_review_filtered.py
```

Targeted test:

```powershell
D:\Python\python.exe -m pytest tests/test_manual_review_filtered_report.py -q
```

## Current Status

`git status --short -- scripts` reports:

```text
 M scripts/README.md
 M scripts/build_xps_in_situ_20260506.py
 D scripts/regenerate_manual_review_filtered.py
?? scripts/data_types/
?? scripts/maintenance/opju_exemplar_regression.py
?? scripts/one_off/verify_jeol_epr_decode_against_exports.py
?? scripts/reports/
```

Only the `regenerate_manual_review_filtered` paths and direct references are eligible for Batch 3A. The XPS script and unrelated new script directories must stay out of Batch 3A.

## Old Path / New Path

Old tracked path:

- `scripts/regenerate_manual_review_filtered.py`
- exists in `HEAD`: yes
- exists in current working tree: no, tracked deletion

New path:

- `scripts/reports/regenerate_manual_review_filtered.py`
- exists in `HEAD`: no
- exists in current working tree: yes, untracked

Blob identity:

```text
HEAD:scripts/regenerate_manual_review_filtered.py = 538b6f5228edc13c635dabe2b8e95093d7521a36
scripts/reports/regenerate_manual_review_filtered.py = 538b6f5228edc13c635dabe2b8e95093d7521a36
```

Conclusion: the new file is byte-identical to the old tracked file. The earlier preflight concern about non-identical text was caused by a text/encoding inspection method, not by a real script-content difference.

## Function and CLI Entrypoints

Both the old `HEAD` file and the new working-tree file expose the same imports and entrypoints:

- `norm_key(path_text: str) -> str`
- `short_reason(item: dict) -> str`
- `action_for(item: dict) -> str`
- `phase16_keys(root: Path) -> set[str]`
- `build_rows(root: Path) -> tuple[list[dict], list[dict], dict]`
- `write_csv(path: Path, rows: list[dict], fallback_headers: list[str]) -> None`
- `write_xlsx(path: Path, rows: list[dict], title: str, fallback_headers: list[str]) -> None`
- `write_report(path: Path, kept: list[dict], excluded: list[dict], summary: dict) -> None`
- `main() -> None`
- `if __name__ == "__main__": main()`

Because the blob hashes are identical, there are no behavior changes inside the script.

## Behavior Differences

Script behavior differences:

- none found

Migration behavior difference:

- import path changes from `scripts.regenerate_manual_review_filtered` to `scripts.reports.regenerate_manual_review_filtered`
- filesystem path changes from `scripts/regenerate_manual_review_filtered.py` to `scripts/reports/regenerate_manual_review_filtered.py`

These are necessary path changes for the report-script migration, not unrelated functional drift.

## Unrelated Drift Review

No unrelated functional drift was found in the old/new `regenerate_manual_review_filtered` script content.

Adjacent files that should not be included blindly in Batch 3A:

- `scripts/README.md`
  - current diff is broader script-layout documentation, including `data_types/`, `maintenance/`, `one_off/`, and `reports/`
  - defer to Batch 3B
- `docs/indexes/scripts_index.md`
  - directly references the new report script, but its current diff also adds XPS/data_types/maintenance/one_off entries
  - do not stage as-is in Batch 3A unless the user explicitly accepts the broader index update or the diff is narrowed in a later review
- `scripts/build_xps_in_situ_20260506.py`
  - unrelated XPS script drift; excluded from Batch 3A
- `scripts/data_types/xps/`
  - unrelated XPS script migration area; excluded from Batch 3A

## References

Functional references:

- `tests/test_manual_review_filtered_report.py`
  - current working tree imports `build_rows`, `main`, `write_csv`, and `write_xlsx` from `scripts.reports.regenerate_manual_review_filtered`

Documentation/index references:

- `docs/indexes/scripts_index.md`
  - current working tree lists `scripts\reports\regenerate_manual_review_filtered.py`
- Batch 1 cleanup/status docs mention the old path as a tracked deletion and the new path as the likely replacement.
- `docs/SCRIPT_LAYOUT_PREFLIGHT.md` and `docs/SCRIPT_LAYOUT_BATCH_PLAN.md` mention both paths as planning/review evidence.

Historical/generated references:

- several committed status/planning docs mention the old path as historical cleanup context
- at least one generated output report JSON also mentions the new path

Formal code/README dependency on old path:

- no formal code import was found pointing to `scripts.regenerate_manual_review_filtered`
- no `scripts/README.md` dependency on the old script path remains in the current working tree
- remaining old-path references are cleanup/status documentation references, not runtime imports

## Targeted Test

Command:

```powershell
D:\Python\python.exe -m pytest tests/test_manual_review_filtered_report.py -q
```

Exit code: 0

Result:

```text
4 passed in 0.23s
```

No full pytest, validate, readiness, Origin, output processing, or plotting command was run.

## Recommendation

Batch 3A can proceed to staging for the core `regenerate_manual_review_filtered` migration.

Recommended staging command:

```powershell
git add -- scripts/regenerate_manual_review_filtered.py scripts/reports/regenerate_manual_review_filtered.py scripts/reports/README.md tests/test_manual_review_filtered_report.py docs/SCRIPT_LAYOUT_BATCH3A_REVIEW.md
```

Do not include these in Batch 3A staging:

- `scripts/README.md`
- `docs/indexes/scripts_index.md` unless explicitly approved despite broader script-index changes
- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/`
- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- any `output/`, `src/`, `config/`, unrelated tests, cache files, or generated artifacts

After Batch 3A, handle broader script-layout documentation and indexes in Batch 3B/3C.
