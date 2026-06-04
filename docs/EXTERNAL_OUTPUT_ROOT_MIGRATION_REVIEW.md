# External Output Root Migration Review

Date: 2026-06-04

## Scope

This review covers the current project output-routing state before moving legacy `output/` and `outputs/` content. It does not move, delete, or regenerate any product artifact.

Target external output root for this machine:

```text
D:\Codex Project\科研数据处理\输出
```

## Current Routing State

- `src/core/project.py` is the central writer helper. `output_dir()` and `report_path()` accept an optional `output_root`, but fallback to `project_root / "output"` when no root is supplied.
- `src/core/runtime_paths.py` already has `create_run_output_layout()` for run-scoped output roots, but its default base is still `project_root / "output" / "runs"`.
- `src/core/process.py`, `src/scanner/scanner.py`, `src/processors/base.py`, `src/core/metadata.py`, `src/core/triage.py`, `src/core/auto_queue.py`, `src/core/reviewed_queue.py`, `src/core/origin_batch.py`, and `src/origin/adapter.py` already pass optional `output_root` through major processing/report paths.
- `src/cli.py` exposes explicit output-root-like control only for selected commands, for example `xps-heterojunction-stacked --output-dir` and `jeol-epr-decode --out`; normal `scan`, `triage`, and `process` do not resolve a configured external default.
- `ensure_write_path_allowed()` currently allows project `output/`, `docs/`, `tests/fixtures/`, `golden_examples/`, `config/`, and `.codex/`. It does not yet allow the configured external output root.

## Configuration State

- `config/default.yaml` still defines historical project-local paths such as `paths.output: output`, `paths.processed_data: output/processed_data`, `paths.origin_files: output/origin_files`, `paths.figures_tif: output/figures_tif`, `paths.figures_preview: output/figures_preview`, and `paths.reports: output/reports`.
- `config/local.yaml` exists and is gitignored. It currently configures F-drive/XPS paths, but not the external output root.
- `config/local.example.yaml` mirrors the local machine paths and should be updated to document the external output-root setting without forcing it as a portable default.
- Environment variable support exists for several runtime paths, but not yet for `RESEARCH_PIPELINE_OUTPUT_ROOT`.

## Tests And Assumptions

- `tests/test_output_routing.py` already proves that core callers can route output into an isolated run root under `tmp_path`.
- `tests/test_hplc_lc_output_routing.py` and `tests/test_hplc_lc_contracts.py` assert run-scoped metadata paths under isolated `tmp_path` projects.
- Some tests intentionally assert legacy relative metadata strings such as `output/runs/<run_id>/...`; those should remain for compatibility when the run root is inside project `output/`.
- New tests should use `tmp_path` or an explicitly isolated external root under `tmp_path`. They must not write to `D:\Codex Project\科研数据处理\输出`.

## Documentation To Update

- `docs/EXTERNAL_OUTPUT_ROOT_MIGRATION_REVIEW.md` records this pre-change review.
- `docs/LEGACY_OUTPUT_ARCHIVE_REPORT.md` should be written after archiving old project outputs.
- `docs/OPJU_BACKED_REAL_DATA_PILOT_REVIEW.md`, `docs/HPLC_LC_DEFERRED_NO_OPJU_NOTE.md`, `docs/PRODUCT_NO_CODEX_LABEL_AUDIT.md`, and `docs/OPJU_BACKED_REAL_DATA_PILOT_SUMMARY.md` should be written during the pilot phases.
- Existing old phase documents mention project-local `output/` for historical packages. They should not be rewritten wholesale because they are historical evidence.

## Recommended Implementation

1. Add a small output-root resolver with this priority:
   - explicit CLI/config argument if supplied;
   - `config/local.yaml` value;
   - `RESEARCH_PIPELINE_OUTPUT_ROOT`;
   - `config/default.yaml` value;
   - compatibility fallback to project `output/`.
2. Allow `ensure_write_path_allowed()` to accept a resolved output-root parameter, while still blocking arbitrary unconfigured paths.
3. Update `create_run_output_layout()` to use the resolved output root when `output_base` is not explicit, creating runs under `<external_output_root>/runs/<run_id>/`.
4. Add `--output-root` to formal CLI commands that already support `output_root` internally: `scan`, `triage`, `process`, `origin-batch`, `reviewed-queue`, and `auto-queue`.
5. Update `config/local.example.yaml` and gitignored `config/local.yaml` to include the current machine external root.
6. Keep `config/default.yaml` portable. Do not hard-code the D-drive output root into default config.
7. Preserve legacy output paths for historical package resolution and tests unless an output root is explicitly or locally configured.

## Pre-Migration Risk

- Moving legacy outputs before the resolver works would risk immediate regeneration under project `output/`.
- The old `AGENTS.md` rule says all run outputs must write to `output/`; the current user instruction explicitly supersedes it for this goal.
- Existing tracked files may remain under `output/` or `outputs/`. Phase 3 must inspect `git ls-files output outputs` before archiving.
