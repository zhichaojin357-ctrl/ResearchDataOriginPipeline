# Remaining Source Dirty Queue

Date: 2026-06-03

## Current Source/Test Dirty Files

Only three source/test files remain dirty:

| File | Category | Current status | Next GOAL |
| --- | --- | --- | --- |
| `src/core/xps_heterojunction.py` | XPS workflow source | blocked | XPS No-Artifact Contract Test Design |
| `src/core/xps_in_situ.py` | XPS workflow source | blocked | XPS No-Artifact Contract Test Design |
| `tests/test_xps_heterojunction_stacked.py` | XPS workflow tests | blocked | XPS No-Artifact Contract Test Design |

## XPS Blocker

The XPS dirty source/test diff is blocked because it mixes:

- no-Origin contracts;
- Origin/OPJU path contracts;
- visual style changes;
- PNG/TIF/XLSX artifact generation;
- tests that create temporary binary/artifact files.

This should not be committed until tests exist that can validate table/path/report contracts without generating OPJU/TIF/PNG/XLSX artifacts.

## Config And Scripts

Current dirty count:

- `config/`: 0
- `scripts/`: 0

No script-layout action is recommended in this GOAL.

## Root And Docs Queue

Potential docs-only review queue:

- `AGENTS.md`
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- `docs/REAL_DATA_INTAKE_GUIDE.md`
- `docs/indexes/output_reports_index.md`
- `docs/indexes/outputs_index.md`
- `docs/method_cards/README.md`
- `docs/method_cards/bet.md`
- `docs/method_cards/epr.md`
- `docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md`

These should be handled in a docs-only review after source blockers are understood. Do not mix them with generated output or XPS source commits.

## Historical Agent Reports Queue

`docs/agent_reports/` has 71 dirty entries. They are historical reports and should not be batch committed. Suggested handling:

- keep as untracked review material;
- select a small subset only if needed for formal status history;
- otherwise leave for user review or later archival policy.

## Recommended Processing Order

1. `GOAL: XPS No-Artifact Contract Test Design`
2. `GOAL: Remaining Documentation Dirty Review`
3. `GOAL: Output Manual Cleanup Review`
4. `GOAL: Data-Type Plot Fix Sequence Planning`

## Validation Boundaries

Do not use Origin, real data, or generated image/Excel artifacts to resolve the source queue unless the user explicitly changes the GOAL constraints.
