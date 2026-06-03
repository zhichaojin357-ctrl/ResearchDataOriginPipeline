# Batch 2D Blockers

Date: 2026-06-03

## Deferred Changes

### BET Candidate Extraction

Status: deferred, not failed.

Reason:

- Remaining BET hunks are larger than the already-committed micro-batches.
- They touch vendor isotherm extraction, pore distribution extraction, numeric fallback, processed table headers, and type-specific result counts.
- The tests are synthetic, but the behavior is data-type-specific and should receive a dedicated review document and cached-version compile.

Do not mix this with optional adapter bridge changes.

### Optional Adapter Bridge

Status: deferred, not failed.

Reason:

- Remaining adapter hunks change peak detection and baseline helper routing through `src.adapters`.
- This should be tested independently from BET and photocurrent changes.
- Validation must show fallback/candidate-only behavior and must not require optional packages to be installed.

Do not mix this with BET extraction changes.

## Hard Blockers Not Encountered

- No Origin-required verification was encountered for committed batches.
- No user visual judgment was required for committed batches.
- No real data processing was required for committed batches.
- No new output-generation task was run.

## Stop Reason

This GOAL stopped after four source/test commits to reserve the fifth allowed commit for summary and organization docs. Remaining changes are still suitable for future micro-batches, but not safe to collapse into one broad commit.
