# Batch 2D Remaining Plan

Date: 2026-06-03

## Completed In This GOAL

- Table reader contracts for ZPlotW and bracketed `[Data]` synthetic exports.
- Metadata success preview manual-review checklist wording.
- Processor base axis-title/provenance contracts.
- Photocurrent processed output unit/header contract.
- BET candidate extraction for summary-only, isotherm, pore-distribution, and ambiguous synthetic cases.
- Processor organization strategy documentation.

## Remaining Dirty Files In Batch 2D Scope

Remaining dirty source/test files observed before summary-doc generation:

- `src/processors/calculations.py`

## Remaining Micro-Batches

### Optional Adapter Bridge

Likely paths:

- `src/processors/calculations.py`
- Existing adapter tests or a new focused processor calculation test.
- `docs/BATCH2D_CALCULATIONS_ADAPTER_BRIDGE_REVIEW.md`

Scope:

- Peak detection adapter bridge before scipy fallback.
- Baseline adapter bridge before direct `pybaselines` handling.

Required validation:

- `D:\Python\python.exe -m py_compile src/processors/calculations.py`
- Adapter-specific targeted tests that do not require optional packages to be installed.
- Tests must confirm fallback/candidate-only behavior without scientific interpretation.

## Recommended Next Order

1. `Batch 2D-CALC-ADAPTER-BRIDGE` preflight and targeted adapter tests.
2. XPS-specific preflight remains separate and should not be mixed with Batch 2D.
3. Future output routing planning can start after remaining source/test batches are separated.

Do not enter visual plotting fixes until output routing and remaining source boundaries are stable.
