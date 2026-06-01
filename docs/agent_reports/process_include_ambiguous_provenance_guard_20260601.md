# Include-Ambiguous Provenance Guard

- Date: 2026-06-01
- Scope: `run.py process --from-queue --include-ambiguous`.
- Safety: no raw data changes, no workspace source changes, no F-drive writes, no Origin launch in validation.

## Problem

`--include-ambiguous` allowed any `MANUAL_REVIEW` item in a supplied queue to proceed if path/hash validation passed. That was too broad for the project's safety policy because it could process a manually assembled MANUAL_REVIEW queue without explicit promotion or user approval provenance.

## Change

MANUAL_REVIEW queue items now require:

- `original_triage_decision=MANUAL_REVIEW`
- non-empty `promoted_by_phase`
- either `promoted_from_manual_review=true` or `current_decision=USER_APPROVED_NO_ORIGIN_QUEUE`

Items that do not satisfy this are recorded as `queue_validation` failures before processing.

## Verification Snapshot

- RED: `D:\Python\python.exe -m pytest tests/test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_include_ambiguous_requires_manual_review_promotion_provenance -q` returned code 0 instead of expected queue-validation failure before implementation.
- GREEN: `D:\Python\python.exe -m pytest tests/test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_include_ambiguous_requires_manual_review_promotion_provenance tests/test_phase1_2_mixed_triage.py::Phase12MixedTriageTest::test_manual_review_promotion_queue_records_audit_fields tests/test_phase1_2_mixed_triage.py -q`: 19 passed.
- `D:\Python\python.exe -m pytest`: 182 passed, 2 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py readiness`: exit 0; 21 checks, 0 failures, 0 warnings.
- Residual process check after a short wait: no `python`, `EXCEL`, `Origin`, or `OriginPro` process remained.

## Files Updated

- `src/core/process.py`
- `tests/test_phase1_2_mixed_triage.py`
- `README.md`
- `PROJECT_STATUS.md`
- `TASK_BOARD.md`
- `AGENT_HANDOFF.md`
