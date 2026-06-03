# Processor Structure Plan

Date: 2026-06-03

## Purpose

This plan defines how future processor/data-type work should be organized before any broad source-tree move.

## Principles

1. Shared capabilities are grouped by function.
2. Data-specific processing is grouped by data type only when the code is strongly bound to that data type, instrument, or raw format.
3. Do not mass-move `src/` during cleanup. Move code only after references, tests, and output contracts are clear.
4. Public output, metadata, Origin, and style rules should remain centralized so each data type does not grow a separate output/style system.
5. Scientific interpretation remains manual-review gated. Processor code may emit candidate metrics, not final assignments or mechanisms.

## Current Responsibilities

- `src/core/`: shared orchestration, validation, metadata, table reading, and project path contracts.
- `src/origin/`: Origin invocation, plotting operation helpers, plot policy, and text formatting contracts.
- `src/scanner/`: inventory, classification, triage, and source-discovery logic.
- `src/processors/`: shared processor entrypoint and candidate calculation helpers for supported data tables.
- `src/adapters/`: optional scientific package shims with fallback behavior and candidate-only outputs.

## Future Data-Type Cleanup Pattern

When repairing a specific data type such as BET, XRD, EIS, HPLC, or photocurrent:

1. Start with a preflight that identifies current source hunks, tests, expected outputs, and real-data risks.
2. Keep shared table reading, metadata, output routing, and Origin style contracts in shared modules.
3. Move or extract data-specific code only when the target data-type boundary is clear and all live callers/imports can be updated.
4. Add synthetic or tmp-path targeted tests before touching real data or Origin.
5. Do not duplicate Origin output/style logic per data type.
6. If real data or visual review is required, stop at preflight and request a separate data-type GOAL.

## Optional Future Shape

The current layout can evolve toward:

- `src/processors/base.py`: common processor entrypoint and policy boundaries.
- `src/processors/calculations.py`: shared generic helpers only.
- `src/processors/data_types/<type>.py`: strongly type-specific candidate extraction once a type has enough stable logic.
- `tests/test_processor_<type>.py`: focused synthetic tests per data type.

This GOAL does not execute that move.

## Instruction For Future Codex Runs

Before changing a processor for a specific data type, read this plan, the current Batch 2D summary, and any data-type-specific preflight docs. Prefer micro-batches with targeted tests over broad mixed commits.
