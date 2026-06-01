# Readiness Auto-Queue Consistency Guard

Date: 2026-05-31

`run.py readiness` now verifies that the Phase 1.8 auto-queue plan and generated candidate queue agree.

Current state:

- accepted_count: 105
- queue items: 105
- Origin-allowed queue items: 0
- readiness: 16 checks, 0 failures, 0 warnings

Verification:

- Full pytest: passed, 165 tests, 2 warnings.
- validate/deps-audit: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
