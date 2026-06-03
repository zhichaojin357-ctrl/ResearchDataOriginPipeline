# Batch 2D-small Review: BOM-tolerant Process JSON Reads

Batch name: Batch 2D-small

Purpose: accept UTF-8 BOM JSON for processing queues and existing report JSON reads without changing processing behavior or output routing.

Strict allowlist:

- `src/core/process.py`
- `tests/test_phase1_1_process_cli.py`
- `docs/BATCH2D_REVIEW.md`

File rationale:

- `src/core/process.py`: changes `read_text(encoding="utf-8")` to `read_text(encoding="utf-8-sig")` for queue JSON and report JSON loading.
- `tests/test_phase1_1_process_cli.py`: adds a narrow test for an empty BOM-prefixed queue JSON with `no_origin=True`.
- `docs/BATCH2D_REVIEW.md`: records this batch review.

Easy-to-mix files excluded:

- `src/processors/calculations.py`
- `src/processors/base.py`
- `src/core/table_reader.py`
- `tests/test_processor_behaviors.py`
- Any `output/` or `outputs/` path
- Any Origin, XPS, EPR overlay, or optional adapter files

Diff risk: LOW. The source change is encoding-only for JSON reads. The targeted test uses a temporary project and does not call Origin.

Required checks:

- `git diff --stat -- src/core/process.py tests/test_phase1_1_process_cli.py`
- `git diff --check -- src/core/process.py tests/test_phase1_1_process_cli.py`
- `D:\Python\python.exe -m py_compile src/core/process.py`
- `D:\Python\python.exe -m pytest tests/test_phase1_1_process_cli.py::Phase11ProcessCliTest::test_process_from_queue_accepts_utf8_bom_json -q`

Staging recommendation: yes, if all required checks pass and staged files strictly equal the allowlist.

Commit message:

- `core: accept utf-8-sig process json`

No Origin, output cleanup, data processing, plotting fix, or new data handling is part of this batch.
