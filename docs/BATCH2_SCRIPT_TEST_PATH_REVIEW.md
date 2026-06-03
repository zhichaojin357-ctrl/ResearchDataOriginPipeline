# Batch 2 Script Test Path Review

Date: 2026-06-03

## Batch Name

Batch 2 script migration test path cleanup.

## Purpose

Commit the remaining test-only fallout from the already committed `regenerate_manual_review_filtered` script migration. The script itself was moved in Batch 3A; this batch only updates the test import path so the tracked test points at the formal `scripts/reports/` location.

## Strict Allowlist

- `tests/test_manual_review_filtered_report.py`
- `docs/BATCH2_SCRIPT_TEST_PATH_REVIEW.md`

## File Rationale

- `tests/test_manual_review_filtered_report.py`: changes one import from `scripts.regenerate_manual_review_filtered` to `scripts.reports.regenerate_manual_review_filtered`.
- `docs/BATCH2_SCRIPT_TEST_PATH_REVIEW.md`: records this test-only review and validation scope.

## Excluded Nearby Files

- `scripts/reports/regenerate_manual_review_filtered.py`: already committed in Batch 3A; not touched in this batch.
- `scripts/`: no script layout or code changes are included.
- `output/` and `outputs/`: excluded.
- `src/`, `config/`, and unrelated tests: excluded.

## Diff Summary

The diff is a one-line import-path update in the targeted test file.

## Risk Level

LOW. This is test-only path alignment for an already committed script move.

## Checks

Planned commands:

- `git diff --check -- tests/test_manual_review_filtered_report.py docs/BATCH2_SCRIPT_TEST_PATH_REVIEW.md`
- `D:\Python\python.exe -m py_compile tests/test_manual_review_filtered_report.py`
- `D:\Python\python.exe -m pytest tests/test_manual_review_filtered_report.py -q`

The pytest file uses `tmp_path` for generated reports and does not write into the repository `output/` tree.

## Safety Gates

- Touches output: no repository `output/` writes expected.
- Requires Origin: no.
- Requires real data: no.
- Generates OPJU/TIF/PNG/XLSX/ZIP/large JSON: no.

## Staging Recommendation

Recommended if the checks pass and staged files strictly match the allowlist.

## Commit Message

`tests: update manual review generator import`
