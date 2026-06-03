# XPS Heterojunction Contract Review

Date: 2026-06-03

## Scope

Reviewed path:

- `src/core/xps_heterojunction.py`
- `tests/test_xps_heterojunction_stacked.py`
- `tests/test_xps_no_artifact_contracts.py`

## Current State

The current heterojunction source diff is not safe to stage as a no-artifact batch. It mixes:

- comparison planning and manual-review metadata;
- Origin helper script generation;
- OPJU/TIF/PNG path construction;
- TIF DPI post-processing;
- visual styling helpers;
- peak annotation presentation details;
- summary report table changes.

The related existing test diff also mixes safe planning checks with temp `.xlsx`, `.opju`, `.png`, and `.tif` expectations.

## Safe Contract Captured

`tests/test_xps_no_artifact_contracts.py` now covers:

- synthetic BOBC/BC comparison planning through `build_comparison_plan`;
- no output directory creation during planning;
- no OPJU/TIF/PNG/PDF/XLSX/ZIP artifact generation during planning;
- missing counterpart behavior as manual-review-only.

## Not Safe To Commit In This Goal

Do not stage current `src/core/xps_heterojunction.py` as-is. The diff contains artifact-generation and visual-style changes that require a separate Origin/visual review.

Do not run or stage current `tests/test_xps_heterojunction_stacked.py` wholesale. The dirty test file includes artifact-bearing temp paths and with-Origin behavior.

## Next Safe Split

The next heterojunction batch should first isolate only non-generating source hunks:

- planning metadata;
- manual-review fields;
- forbidden-claim wording;
- path intent without file generation.

Artifact-producing hunks should remain blocked until Origin and visual acceptance are explicitly approved.
