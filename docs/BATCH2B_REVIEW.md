# Batch 2B Review: JEOL EPR Decode / EPR Overlay

Batch name: Batch 2B

Purpose: stabilize JEOL cAcqu EPR decode exports and EPR overlay table workflow without running Origin, processing real data, or making radical/mechanism claims.

Strict allowlist:

- `config/data_selection_rules.yaml`
- `config/default.yaml`
- `src/cli.py` (EPR CLI hunks only; keep the unrelated XPS help-text hunk unstaged)
- `src/core/epr_jeol.py`
- `src/core/epr_overlay.py`
- `src/core/runtime_paths.py`
- `tests/test_jeol_epr_decode.py`
- `tests/test_epr_overlay.py`
- `docs/BATCH2B_REVIEW.md`

File rationale:

- `config/data_selection_rules.yaml`: records the current workspace copy path used for source-safety routing.
- `config/default.yaml`: records the current workspace data/root path used by EPR defaults.
- `src/cli.py`: adds `jeol-epr-decode` and `epr-overlay` command wiring only.
- `src/core/epr_jeol.py`: adds data-only XLSX export, comparison report helpers, and verified 4096-point cAcqu export series helpers.
- `src/core/epr_overlay.py`: builds condition-group EPR overlay processed/detail CSV tables and optional Origin export path, with `with_origin=False` as the tested cleanup path.
- `src/core/runtime_paths.py`: aligns the legacy workspace root with the current configured workspace path.
- `tests/test_jeol_epr_decode.py`: targeted JEOL decode/export/CLI tests using temporary directories.
- `tests/test_epr_overlay.py`: targeted overlay table tests using temporary directories and `with_origin=False`.
- `docs/BATCH2B_REVIEW.md`: records this batch review.

Excluded nearby files:

- `scripts/one_off/verify_jeol_epr_decode_against_exports.py` is referenced by tests but was already classified in Batch 3D; it is not staged here.
- The unrelated `src/cli.py` XPS `--with-origin` help text change is not part of this batch.
- `src/origin/*` was handled in Batch 2A.
- Any `output/` or `outputs/` path.
- Any OPJU/TIF/PNG/XLSX/ZIP/large JSON.

Diff summary:

- Adds verified JEOL cAcqu series export and XLSX comparison helpers.
- Adds EPR overlay table construction with explicit no-claim reporting.
- Adds EPR CLI commands for decode and overlay workflows.
- Updates workspace root config to the current machine-local workspace copy.
- Adds tempdir-based tests for decode/export/overlay behavior.

Risk level: MEDIUM.

Risk rationale:

- The batch promotes new formal CLI commands and updates workspace routing.
- Targeted tests are tempdir-based and do not call Origin.
- The EPR overlay module can write output when run on the real project, but this batch does not run that command and only tests tempdir outputs.

Required py_compile command:

- `D:\Python\python.exe -m py_compile src/cli.py src/core/epr_jeol.py src/core/epr_overlay.py src/core/runtime_paths.py`

Required targeted test command:

- `D:\Python\python.exe -m pytest tests/test_jeol_epr_decode.py tests/test_epr_overlay.py -q`

Output touch check:

- This batch must not stage or modify `output/` or `outputs/`.
- Tests write only under pytest/unittest temporary directories.

Origin requirement:

- No live Origin run is required.
- EPR overlay tests must use `with_origin=False`.

Real data requirement:

- No real data processing is required.

Staging recommendation: yes, if py_compile, targeted tests, partial `src/cli.py` staging verification, and cached allowlist checks pass.

Commit message:

- `epr: stabilize jeol decode and overlay workflows`

This batch does not assign radical species, infer EPR mechanisms, or claim visual plotting correctness.
