# Batch 2F Adapter Bridge Review

## Scope

This review covers only the optional adapter bridge still dirty after `209d9f3` and `f09fcf3`.

Dirty adapter-bridge file at the start of this GOAL:

- `src/processors/calculations.py`

Focused test/doc additions in this micro-batch:

- `tests/test_phase1_13_adapters.py`
- `docs/BATCH2F_ADAPTER_BRIDGE_REVIEW.md`

## Prior Coverage

- `209d9f3` already covered optional dependency metadata in `pyproject.toml`, `optional_requirements.txt`, and dependency audit metadata.
- `f09fcf3` already covered the adapter shim modules under `src/adapters/`.
- This batch must not restage those completed metadata or adapter-module changes unless a new focused issue is found.

## Remaining Diff

`src/processors/calculations.py` now routes two processor calculation helpers through optional adapters:

- `scipy_peak_positions()` first calls `src.adapters.peak_detection_adapter.process_or_analyze()` and only falls back to direct `scipy.signal.find_peaks` if no adapter candidate peaks are returned.
- `spectral_package_baseline_records()` calls `src.adapters.baseline_adapter.process_or_analyze()` and returns corrected signal values only when the adapter reports `ok` and lengths match.

The bridge is lazy at function-call time. The adapter modules use `import_optional()` internally, so missing external packages should produce unavailable/fallback results rather than import-time failure.

## Risk Search Results

- Hard dependency risk: LOW. No top-level optional external package import was found in `src/adapters/`; optional imports are routed through `import_optional()`.
- Import-time failure risk: LOW. `src/processors/calculations.py` imports the project adapter modules inside helper functions.
- Real data dependency: LOW. The focused tests use synthetic numeric arrays only.
- Output risk: LOW. `git grep "output/"` found no matches in the adapter bridge files or focused adapter tests.
- Origin risk: LOW. The only `Origin` match in the searched scope is an existing `--no-origin` warning in `src/processors/base.py`, outside this batch.
- Manual-review or scientific-claim risk: LOW. The bridge produces candidate peak/baseline records only; it does not make material, phase, valence, radical, circuit, or mechanism claims.

## Strict Allowlist

Allowed for this commit:

- `src/processors/calculations.py`
- `tests/test_phase1_13_adapters.py`
- `docs/BATCH2F_ADAPTER_BRIDGE_REVIEW.md`

Excluded nearby files:

- `src/adapters/`
- `src/core/deps.py`
- `src/processors/base.py`
- `pyproject.toml`
- `optional_requirements.txt`
- `output/`
- `outputs/`
- `scripts/`

## Targeted Checks

```powershell
D:\Python\python.exe -m py_compile src/processors/calculations.py tests/test_phase1_13_adapters.py
D:\Python\python.exe -m pytest tests/test_phase1_13_adapters.py -q
git status --short -- output outputs
git status --short -- output/reports
```

## Staging Recommendation

Proceed to staging only if py_compile and the focused adapter test pass, no output pollution appears, and staged files are exactly the strict allowlist.

Commit message:

```text
adapters: stabilize optional adapter bridge
```
