# Batch 2F-lite Review: Optional Dependency Metadata

Batch name: Batch 2F-lite

Purpose: record optional scientific dependency metadata and pytest warning filters without committing the optional adapter package or any processor bridge.

Strict allowlist:

- `optional_requirements.txt`
- `pyproject.toml`
- `src/core/deps.py`
- `docs/BATCH2F_REVIEW.md`

File rationale:

- `optional_requirements.txt`: records optional/reference dependency candidates, adds `EPRpy` and `cwepr`, and documents why `matchms` remains blocked.
- `pyproject.toml`: adds warning filters for known optional-package import noise during targeted tests.
- `src/core/deps.py`: adds `EPRpy` to optional dependency audit metadata.
- `docs/BATCH2F_REVIEW.md`: records this batch review.

Easy-to-mix files excluded:

- `src/adapters/`
- `tests/test_phase1_13_adapters.py`
- `src/processors/calculations.py`
- `src/processors/base.py`
- `src/cli.py`
- Any `output/` or `outputs/` path
- Any generated OPJU/TIF/PNG/XLSX/ZIP/large JSON

Diff risk: LOW for this metadata-only subset. The untracked adapter package is intentionally excluded because its tests depend on processor-calculation bridge changes that are outside this safe batch.

Required checks:

- `git diff --stat -- optional_requirements.txt pyproject.toml src/core/deps.py`
- `git diff --check -- optional_requirements.txt pyproject.toml src/core/deps.py`
- `D:\Python\python.exe -m py_compile src/core/deps.py`
- `D:\Python\python.exe -c "from src.core.deps import OPTIONAL; assert OPTIONAL.get('EPRpy') == 'eprpy'; print('deps optional metadata ok')"`

Targeted test status:

- No narrower targeted test exists for metadata-only changes without running `deps-audit`, which writes dependency audit reports. This batch uses py_compile plus import-level metadata verification instead.

Staging recommendation: yes, if all required checks pass and staged files strictly equal the allowlist.

Commit message:

- `deps: record optional adapter metadata`

No optional adapter code, processor bridge, output report, or generated artifact is part of this batch.
