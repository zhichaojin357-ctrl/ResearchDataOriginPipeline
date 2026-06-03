# Batch 2D Autocommit Log

Date: 2026-06-03

## Starting State

- Starting known commit before this GOAL: `18bb19e`.
- Start-state dirty count observed during Phase 0: 296.
- Staged files at start: none.

## Commits Completed

### `d8f54e5` - `core: stabilize table reader contracts`

Files:

- `docs/BATCH2D_TABLE_READER_REVIEW.md`
- `src/core/table_reader.py`
- `tests/test_processor_behaviors.py`

Verification:

- `D:\Python\python.exe -m py_compile src/core/table_reader.py` - pass.
- `D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_text_reader_accepts_zplotw_eis_export tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_xrd_reads_raw4_text_data_section -q` - 2 passed.

### `3e46e5e` - `core: tighten metadata preview review checklist`

Files:

- `docs/BATCH2D_METADATA_REVIEW.md`
- `src/core/metadata.py`
- `tests/test_phase1_contracts.py`

Verification:

- `D:\Python\python.exe -m py_compile src/core/metadata.py` - pass.
- `D:\Python\python.exe -m pytest tests/test_phase1_contracts.py::Phase1ContractsTest::test_success_metadata_requires_and_records_png_preview_for_manual_visual_check -q` - 1 passed.

### `bdeff29` - `processors: tighten processor base contracts`

Files:

- `docs/BATCH2D_PROCESSOR_BASE_REVIEW.md`
- `src/processors/base.py`
- `tests/test_processor_base_contracts.py`

Verification:

- `D:\Python\python.exe -m py_compile src/processors/base.py tests/test_processor_base_contracts.py` - pass.
- `D:\Python\python.exe -m pytest tests/test_processor_base_contracts.py -q` - 2 passed.

### `870d088` - `processors: express photocurrent outputs in microamps`

Files:

- `docs/BATCH2D_CALCULATIONS_PHOTOCURRENT_REVIEW.md`
- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`

Verification:

- `D:\Python\python.exe -m py_compile src/processors/calculations.py` - pass.
- `D:\Python\python.exe -m pytest tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_photocurrent_outputs_peak_and_steady_current_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_photocurrent_response_outputs_peak_and_steady_current_candidates tests/test_processor_behaviors.py::ProcessorBehaviorTest::test_photocurrent_uses_light_markers_for_cycles_and_current_density_candidate -q` - 3 passed.
- `git show :src/processors/calculations.py | D:\Python\python.exe -c "import sys; compile(sys.stdin.read(), 'src/processors/calculations.py', 'exec')"` - pass.
- `git show :tests/test_processor_behaviors.py | D:\Python\python.exe -c "import sys; compile(sys.stdin.read(), 'tests/test_processor_behaviors.py', 'exec')"` - pass.

## Safety Notes

- Origin was not run.
- Real data processing was not run.
- No output cleanup, deletion, move, or rename was performed.
- No OPJU/TIF/PNG/XLSX/ZIP/large JSON files were staged or committed.
- Existing dirty `output/` and `output/reports/` files remained unprocessed.
