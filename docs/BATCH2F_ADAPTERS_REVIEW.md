# Batch 2F-remain Review: Optional Scientific Adapter Shims

Batch name: Batch 2F-remain

Purpose: add optional, candidate-only scientific adapter shims and their smoke tests without committing processor bridge changes or dependency metadata already handled in `209d9f3`.

Strict allowlist:

- `src/adapters/__init__.py`
- `src/adapters/baseline_adapter.py`
- `src/adapters/bet_pygaps_adapter.py`
- `src/adapters/common.py`
- `src/adapters/eis_impedance_adapter.py`
- `src/adapters/eis_pyimpspec_adapter.py`
- `src/adapters/electrochem_import_adapter.py`
- `src/adapters/epr_adapter.py`
- `src/adapters/hplc_adapter.py`
- `src/adapters/image_metadata_adapter.py`
- `src/adapters/ms_adapter.py`
- `src/adapters/nmr_adapter.py`
- `src/adapters/peak_detection_adapter.py`
- `src/adapters/raman_adapter.py`
- `src/adapters/xps_lmfitxps_adapter.py`
- `tests/test_phase1_13_adapters.py`
- `docs/BATCH2F_ADAPTERS_REVIEW.md`

File rationale:

- `src/adapters/`: optional package probes and candidate-only processing helpers for baseline, peak, EIS, BET, XPS, EPR, Raman, electrochemistry, HPLC, NMR, MS, and image metadata.
- `tests/test_phase1_13_adapters.py`: targeted smoke tests for adapter fallback behavior and no-claim boundaries.
- `docs/BATCH2F_ADAPTERS_REVIEW.md`: records this batch review.

Excluded nearby files:

- `src/processors/base.py`
- `src/processors/calculations.py`
- `tests/test_processor_behaviors.py`
- `optional_requirements.txt`
- `pyproject.toml`
- `src/core/deps.py`
- Any `output/` or `outputs/` path.
- Any OPJU/TIF/PNG/XLSX/ZIP/large JSON.

Diff summary:

- Adds a lazy optional adapter package under `src/adapters/`.
- Adds adapter-level provenance, optional import probes, and candidate outputs.
- Keeps scientific assignments blocked through forbidden-claim/candidate-only metadata.
- Adds targeted adapter smoke tests.

Risk level: LOW-MEDIUM.

Risk rationale:

- The adapter package is new, but it is optional and candidate-only.
- No live Origin path exists in these modules.
- No formal processor bridge is staged in this batch; processor bridge changes remain for a separate review.
- `image_metadata_adapter` can create a thumbnail only when an explicit `output_dir` is supplied; targeted tests use `tmp_path`.

Required py_compile command:

- `D:\Python\python.exe -m py_compile src/adapters/__init__.py src/adapters/baseline_adapter.py src/adapters/bet_pygaps_adapter.py src/adapters/common.py src/adapters/eis_impedance_adapter.py src/adapters/eis_pyimpspec_adapter.py src/adapters/electrochem_import_adapter.py src/adapters/epr_adapter.py src/adapters/hplc_adapter.py src/adapters/image_metadata_adapter.py src/adapters/ms_adapter.py src/adapters/nmr_adapter.py src/adapters/peak_detection_adapter.py src/adapters/raman_adapter.py src/adapters/xps_lmfitxps_adapter.py`

Required targeted test command:

- `D:\Python\python.exe -m pytest tests/test_phase1_13_adapters.py -q`

Output touch check:

- This batch must not stage or modify `output/` or `outputs/`.
- Tests write only under pytest temporary directories.

Origin requirement:

- No live Origin run is required.

Real data requirement:

- No real data processing is required.

Staging recommendation: yes, if py_compile, targeted tests, and cached allowlist checks pass.

Commit message:

- `adapters: add optional scientific adapter shims`

This batch does not claim scientific assignments, mechanisms, or visual plotting fixes.
