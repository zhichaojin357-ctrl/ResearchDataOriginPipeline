# Batch 2D Processor / Table Reader / Metadata Review

Date: 2026-06-03

## Scope

This review covers only the Processor / Table Reader / Metadata GOAL scope:

- `src/core/table_reader.py`
- `src/core/metadata.py`
- `src/core/process.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `config/processor_registry.yaml`
- `config/data_selection_rules.yaml`
- `config/default.yaml`
- `tests/test_processor_behaviors.py`
- `tests/test_phase1_1_process_cli.py`

The repository started this GOAL with 296 dirty `git status --short` entries and no staged files.

## Current Dirty Files In Scope

Dirty files in the Batch 2D scope:

- `src/core/metadata.py`
- `src/core/table_reader.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`

No dirty changes were present in the reviewed config files or in `tests/test_phase1_1_process_cli.py`.

## Diff Grouping

### Table Reader Contracts

Files:

- `src/core/table_reader.py`
- `tests/test_processor_behaviors.py`

Observed changes:

- Adds EIS ZPlotW text export detection and parsing for `Freq(Hz)`, `Z'`, and `Z''` columns.
- Adds bracketed `[Data]` section parsing for text exports such as XRD RAW4-style tables.
- Extends x/y column detection needles for frequency and real impedance labels.
- Adds synthetic tests for ZPlotW EIS text export and XRD RAW4 `[Data]` section handling.

Risk: LOW.

Recommended micro-batch: `Batch 2D-TR`.

Recommended validation:

```powershell
D:\Python\python.exe -m py_compile src/core/table_reader.py
D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_text_reader_accepts_zplotw_eis_export tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_xrd_reads_raw4_text_data_section -q
```

### Metadata Manual Review Contract

Files:

- `src/core/metadata.py`

Observed changes:

- Narrows the success preview manual-review item to mention legend frame/fill box and chemical formula subscripts in addition to existing Graph4/style checks.

Risk: LOW to MEDIUM because the text is style-related, but it only changes metadata/manual-review checklist wording and does not run Origin or generate artifacts.

Recommended micro-batch: `Batch 2D-MD` after table reader.

Recommended validation:

```powershell
D:\Python\python.exe -m py_compile src/core/metadata.py
```

Use a targeted metadata test only if one directly covers `_manual_check_items` or success metadata generation without writing real `output/`.

### Processor Base Contracts

Files:

- `src/processors/base.py`

Observed changes:

- Makes Origin axis-title defaults aware of data type and processed header names.
- Adds optional adapter provenance fields and candidate adapter names.

Risk: MEDIUM because this touches shared processor metadata and Origin invocation metadata, even though it does not run Origin.

Recommended micro-batch: `Batch 2D-PB`, but only after isolating tests that assert axis title/provenance contracts.

### Calculation Helpers

Files:

- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`

Observed changes:

- Adds BET vendor isotherm extraction and BET pore distribution extraction.
- Converts photocurrent processed outputs to microamps and optional current density to microamps per square centimeter.
- Routes peak detection and spectral baseline candidate helpers through optional adapter shims.
- Adds or updates synthetic tests for BET and photocurrent behavior.

Risk: MEDIUM to HIGH because multiple data-type behaviors are mixed in one file. These should be split further into smaller batches before commit.

Candidate follow-up micro-batches:

- `Batch 2D-CALC-PHOTOCURRENT`
- `Batch 2D-CALC-BET`
- `Batch 2D-CALC-ADAPTER-BRIDGE`

### Process Orchestration

Files:

- `src/core/process.py`
- `tests/test_phase1_1_process_cli.py`

Observed changes:

- No current dirty changes in this GOAL scope.
- BOM-tolerant process JSON handling was already committed in `fb152fc` and must not be repeated here.

## Output And Real Data Risk Scan

Pre-test risk search results:

- `output/` matched existing production validation text in `src/core/metadata.py` and existing queue safety text in `src/core/process.py`.
- `outputs/` had no matches in the reviewed scope.
- `workspace` appeared only in `tests/test_processor_behaviors.py` temporary-directory fixture paths.
- `MANUAL_REVIEW` matched existing process orchestration guards in `src/core/process.py`.
- BET/XRD/EIS matches are present in processor logic and synthetic tests; data-type-specific behavior must stay split into small batches.

No review evidence currently requires Origin, real data processing, or writing to real `output/` for the table-reader batch.

## Recommended Execution Order

1. `Batch 2D-TR`: table reader contracts, synthetic tests only. Risk LOW.
2. `Batch 2D-MD`: metadata manual-review checklist wording. Risk LOW/MEDIUM.
3. `Batch 2D-PB`: processor base axis/provenance contracts, only if targeted tests are clear. Risk MEDIUM.
4. `Batch 2D-CALC-*`: split calculations into photocurrent, BET, and adapter bridge micro-batches. Risk MEDIUM/HIGH.
5. `Batch 2D-ORG-DOCS`: docs-only processor organization strategy. Risk LOW.

## Blocker Candidates

Do not auto-commit as a broad batch:

- Combined `src/processors/calculations.py` changes, because BET, photocurrent, and optional adapter bridge behavior are unrelated enough to require separate review.
- Any test or change that needs real BET, photocurrent, XRD RAW4, or EIS ZPlotW files from the production data tree.
- Any verification path that writes real `output/` or `outputs/`.
- Any visual/Origin result judgment.

## Batch 2D-Small Already Covered

Commit `fb152fc` already handled core BOM-tolerant process JSON behavior. This review does not reopen or duplicate that change.
