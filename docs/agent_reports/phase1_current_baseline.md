# Phase 1 Current Baseline

Date: 2026-05-30

## Repository State

- `git status`: not available; this project directory is not a Git repository.
- Existing successful Origin smoke artifacts are retained.
- `input/raw_data/` remains the raw-data intake location and must not be modified by scan/process/validate/origin-test.

## Verified Baseline Before Phase 1.1

- Unit tests: 57 tests pass.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
- `D:\Python\python.exe run.py scan --config config/default.yaml`: exit 0.
- `D:\Python\python.exe run.py process --config config/default.yaml`: exit 0 when `input/raw_data/` is empty.
- `D:\Python\python.exe run.py origin-test`: exit 0 and generated:
  - `output/origin_files/origin_smoke_test.opju`
  - `output/figures_tif/origin_smoke_test.tif`
  - `output/figures_preview/origin_smoke_test.png`

## Phase 1.1 Baseline Additions

- `process --no-origin` is the normal compatibility-test path and must not launch Origin.
- Routine unit tests must not launch Origin.
- Real Origin export tests remain available through `origin-test` and run headless/hidden.
- Synthetic fixtures are stored under `tests/fixtures/` and are explicitly named synthetic.
- Phase 1.1 still forbids PPT generation, PPT modules/templates, kinetics processors, and treating `动力学` as experimental data.
