# Batch 2E Output-Safe Governance Review

Date: 2026-06-03

## Scope

This review covers governance, validation, and phase-report test isolation work only. It does not cover processor/table-reader behavior, XPS source workflows, output cleanup, or any Origin execution.

## Dirty Files In Scope

- `src/core/phase1_7.py`
- `src/core/phase1_9.py`
- `src/core/validate.py`
- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_contracts.py`

`src/core/readiness.py` is in the allowed review scope, but it is not dirty in this working tree.

## Real Output Write Risks Found Before Pytest

Pre-test grep found tests that previously wrote temporary reports under the repository `output/reports` tree:

- `tests/test_phase1_7_manifest_runner.py`
  - `test_manifest_runner_writes_default_reports`
  - Previous pattern: `project_root / "output" / "reports" / "_test_phase1_7..."`
- `tests/test_phase1_8_reviewed_queue.py`
  - `test_reviewed_queue_template_generation_covers_all_proposals`
  - `test_reviewed_queue_cli_help_and_blank_dry_run`
  - Previous pattern: `project_root / "output" / "reports" / "_test_phase1_8..."`
- `tests/test_phase1_10_manifest_normalizer.py`
  - `test_normalized_manifest_dry_run_is_controlled_with_zero_safe_items`
  - `test_manifest_normalize_cli_writes_origin_batch_compatible_outputs`
  - Previous pattern: `project_root / "output" / "reports" / "_test_phase1_10..."`
- `tests/test_phase1_contracts.py`
  - `test_validate_reports_scope_guards_and_registry_semantics`
  - Previous pattern: `run_cli("validate")` with default `cwd=ROOT`, which writes `ROOT/output/reports/validation_report.md`.

## Isolation Plan

The fix should use test-owned temporary paths:

- Write Phase 1.7 report outputs to `tmp_path / "phase1_7_reports"`.
- Write Phase 1.8 template/report outputs to `tmp_path`.
- Write Phase 1.10 normalize outputs to `tmp_path`.
- Run the validation contract test against a temporary project with copied config files instead of the real repository root.

No production-code output root change is required.

## Strict Allowlist

- `src/core/phase1_7.py`
- `src/core/phase1_9.py`
- `src/core/validate.py`
- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_contracts.py`
- `docs/BATCH2E_OUTPUT_SAFE_REVIEW.md`
- `docs/BATCH2E_OUTPUT_SAFE_FIX_LOG.md`

## Excluded Nearby Files

- `src/core/readiness.py`: allowed but not dirty; not included unless a later targeted failure requires it.
- `src/cli.py`: remaining XPS help-text hunk belongs to XPS review.
- `src/core/xps_heterojunction.py`, `src/core/xps_in_situ.py`, `tests/test_xps_heterojunction_stacked.py`: XPS-specific review only.
- `src/core/table_reader.py`, `src/processors/base.py`, `src/processors/calculations.py`, `tests/test_processor_behaviors.py`: processor/table-reader micro-batches only.
- `output/`, `outputs/`, `docs/agent_reports/`, and `output/reports/`: excluded.

## Targeted Checks

Planned commands:

- `D:\Python\python.exe -m py_compile src/core/validate.py src/core/readiness.py src/core/phase1_7.py src/core/phase1_9.py`
- `D:\Python\python.exe -m py_compile tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py`
- `D:\Python\python.exe -m pytest tests/test_phase1_7_manifest_runner.py tests/test_phase1_8_reviewed_queue.py tests/test_phase1_9_governance.py tests/test_phase1_10_manifest_normalizer.py tests/test_phase1_contracts.py -q`
- `git status --short -- output outputs`
- `git status --short -- output/reports`

## Risk Level

MEDIUM.

Reason: governance source diffs are coherent and testable without Origin, but the historical tests had real repository-output writes. This batch is safe only if the new targeted pytest run leaves `output/` and `output/reports` status unchanged from the pre-run state.

## Staging Recommendation

Recommended only if:

- py_compile passes;
- targeted pytest passes;
- no new `output/reports/_test_*` or generated artifact appears;
- staged files strictly match the allowlist.

## Commit Message

`core: isolate governance report tests`
