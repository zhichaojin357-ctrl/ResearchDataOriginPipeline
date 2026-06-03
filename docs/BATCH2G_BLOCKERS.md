# Batch 2G Blockers

Date: 2026-06-03

This file records Batch 2 source/config/test changes that were intentionally not auto-committed during the autonomous stabilization GOAL.

## Resolved: Governance / Validation

Resolved by:

- `dbe0a58 core: isolate governance report tests`

Resolution:

- Governance tests that previously wrote temporary files under repository `output/reports` now use temporary project roots under `tmp_path`.
- Targeted pytest passed: `73 passed in 18.71s`.
- No repository `output/reports/_test_*` files were created.

## Processor / Table Reader

Files:

- `src/core/metadata.py`
- `src/core/table_reader.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`

Reason blocked:

- The diff changes behavior for multiple data types: BET isotherm/pore-distribution extraction, photocurrent unit conversion, XRD RAW4 text sections, ZPlotW EIS text parsing, spectral baseline adapters, and metadata review text.
- These are real data processing semantics, not only cleanup.
- The batch should not be auto-committed without a more focused review and acceptance criteria per data type.

Recommended next review:

- Split into smaller reviews:
  - `Batch 2D-table-reader`: ZPlotW and bracketed `[Data]` parsing only.
  - `Batch 2D-BET`: BET vendor isotherm and pore distribution extraction only.
  - `Batch 2D-photocurrent`: microamp/current-density unit contract only.
  - `Batch 2D-adapter-bridge`: baseline and peak detection adapter bridge only.

## XPS Source Workflows

Files:

- `src/cli.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`

Reason blocked:

- The diffs include generated Origin script behavior, label formatting, XPS artifact path changes, preview/TIF export semantics, in-situ panel generation, and CLI help text.
- Even though some unit tests compile generated scripts without running Origin, full acceptance would require XPS-specific review and likely visual or artifact-level checks.
- This GOAL forbids Origin runs and user visual judgments.

Recommended next review:

- `XPS Source Workflow Preflight`
- Keep the remaining `src/cli.py` XPS help-text hunk with this review.
- Do not commit any XPS behavior until the review separates pure contract changes from visual/Origin-dependent behavior.

## General Stop Reason

The autonomous loop stopped before a sixth functional commit. A sixth commit is reserved for the final GOAL documentation summary. No blocked batch was staged.
