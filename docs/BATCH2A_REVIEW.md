# Batch 2A Review: Origin Adapter / Plot Policy Helpers

Batch name: Batch 2A

Purpose: stabilize the pure-Python Origin plotting policy/helper layer without running Origin or validating visual output.

Strict allowlist:

- `config/plot_style.yaml`
- `src/origin/__init__.py`
- `src/origin/adapter.py`
- `src/origin/operations.py`
- `src/origin/plot_policy.py`
- `src/origin/text_format.py`
- `tests/test_origin_adapter.py`
- `tests/test_origin_operations.py`
- `tests/test_origin_plot_policy.py`
- `docs/BATCH2A_REVIEW.md`

File rationale:

- `config/plot_style.yaml`: records Graph4 fixed-style contract fields used by the helper code.
- `src/origin/__init__.py`: exposes the stable operations wrapper API.
- `src/origin/adapter.py`: builds Origin job metadata/scripts, applies plot policies, handles export evidence checks, and keeps Origin launch checks behind mocks in tests.
- `src/origin/operations.py`: provides named COM operation wrappers, but this batch tests them against fake app objects only.
- `src/origin/plot_policy.py`: centralizes data-type plotting policy fields and Graph4 contract validation.
- `src/origin/text_format.py`: formats chemical formula digits for Origin rich-text strings.
- `tests/test_origin_adapter.py`: targeted pure-Python and mocked adapter tests.
- `tests/test_origin_operations.py`: targeted fake-Origin operations tests.
- `tests/test_origin_plot_policy.py`: targeted plot policy/text formatting tests.
- `docs/BATCH2A_REVIEW.md`: records this batch review.

Excluded nearby files:

- `src/core/phase1_9.py`
- `src/core/validate.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `src/processors/calculations.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_xps_heterojunction_stacked.py`
- Any `output/` or `outputs/` path
- Any OPJU/TIF/PNG/XLSX/ZIP/large JSON

Diff summary:

- Adds explicit Graph4 style fields and chemical subscript policy to `config/plot_style.yaml`.
- Adds plot-policy dataclasses and data-type policy lookup.
- Adds text formatting helpers for chemical subscripts/bold text.
- Adds stable Origin operations wrapper functions.
- Expands adapter job construction, column selection, policy/script metadata, and export evidence checks.
- Expands targeted tests for policy, text formatting, job construction, mocked export paths, and fake COM operation wrappers.

Risk level: MEDIUM.

Risk rationale:

- The batch touches plotting policy and Origin helper behavior, but this commit does not run Origin and does not claim visual correctness.
- The targeted tests are pure Python, tempdir-based, or mocked.
- Live Origin export and PNG/TIF visual inspection remain outside this batch.

Required py_compile command:

- `D:\Python\python.exe -m py_compile src/origin/adapter.py src/origin/operations.py src/origin/plot_policy.py src/origin/text_format.py`

Required targeted test command:

- `D:\Python\python.exe -m pytest tests/test_origin_adapter.py tests/test_origin_operations.py tests/test_origin_plot_policy.py -q`

Output touch check:

- This batch should not stage or modify `output/` or `outputs/`.
- Tests may create temporary `output/` folders under pytest temp directories only.

Origin requirement:

- No live Origin run is required.
- If targeted tests require Origin or fail because of live Origin state, this batch must stop and not commit.

Real data requirement:

- No real data processing is required.

Staging recommendation: yes, only if py_compile, targeted tests, and cached staged allowlist checks pass.

Commit message:

- `origin: stabilize plotting policy helpers`

This batch does not claim any XPS, Raman, BET, XRD, EPR, or other visual plotting issue is fixed.
