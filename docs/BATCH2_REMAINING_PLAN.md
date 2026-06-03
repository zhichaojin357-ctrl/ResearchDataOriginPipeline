# Batch 2 Remaining Plan

Date: 2026-06-03

This plan tracks source/config/test cleanup batches that remain after the automatic Batch 2 stabilization commits. It does not cover `output/`, `outputs/`, Origin-generated artifacts, or bulk reports.

## Current Continuation State

Continuation baseline after future output routing: `c9052f1 origin: accept run-scoped artifact paths`.

Dirty count observed after the future output routing implementation commits and before this summary-doc edit: 291 items.

Staged files after the adapter bridge source commit: 0.

## Completed Batch 2 Items

- `fb152fc core: accept utf-8-sig process json`
- `209d9f3 deps: record optional adapter metadata`
- `0d316a9 docs: record batch2 source review progress`
- `76c3c5c origin: stabilize plotting policy helpers`
- `cc2e13e epr: stabilize jeol decode and overlay workflows`
- `f09fcf3 adapters: add optional scientific adapter shims`
- `b860453 tests: update manual review generator import`
- `1fb85f0 docs: summarize batch2 autonomous stabilization`
- `dbe0a58 core: isolate governance report tests`
- `a0cedbe docs: sync script layout references`
- `18bb19e docs: summarize governance and script consistency goal`
- `d8f54e5 core: stabilize table reader contracts`
- `3e46e5e core: add metadata preview checklist`
- `bdeff29 processors: tighten processor base contracts`
- `870d088 processors: preserve photocurrent microamp outputs`
- `e3360e3 docs: summarize processor table reader stabilization`
- `d5a24b1 processors: stabilize bet candidate extraction`
- `823d093 docs: summarize bet candidate extraction micro-batch`
- `1fc9875 adapters: stabilize optional adapter bridge`
- `7ac2ab9 docs: summarize optional adapter bridge micro-batch`
- `a114121 core: add run-scoped output path helpers`
- `4c6ab10 core: route process artifacts into run outputs`
- `49e207c core: route queue reports through run outputs`
- `c9052f1 origin: accept run-scoped artifact paths`

## Remaining Source/Config/Test Review Order

1. XPS workflow preflight
   - Files currently known dirty: `src/cli.py`, `src/core/xps_heterojunction.py`, `src/core/xps_in_situ.py`, `tests/test_xps_heterojunction_stacked.py`.
   - Boundary: review path/CLI/contract behavior only; do not run Origin, do not generate XPS outputs, and do not claim valence or mechanism conclusions.

2. Remaining source dirty triage
   - Re-run a narrow `git status --short -- src config tests pyproject.toml optional_requirements.txt`.
   - Confirm whether any non-XPS source/test files remain after the adapter bridge commit.
   - Any remaining source change needs its own allowlist and targeted tests.

3. Future output routing policy follow-up
   - Core run-scoped output helpers and report/artifact path routing are implemented.
   - CLI surfacing is not implemented because `src/cli.py` has unrelated XPS dirty content; handle that only after XPS preflight.
   - Output/report directories remain dirty and should be handled as a later cleanup/governance batch.
   - Do not move, delete, or stage generated artifacts without a separate allowlist and review.

4. Data-type plot fix sequence planning
   - Start only after output routing boundaries and XPS workflow preflight are clear.
   - Each data type fix must enter the formal code path, rerun from original/synthetic inputs as appropriate, and provide focused verification.

## Global Rules

- Do not stage `output/`, `outputs/`, OPJU, TIF, PNG, XLSX, ZIP, or large JSON files.
- Do not run Origin during cleanup reviews.
- Do not install optional packages during source cleanup.
- Do not use directory-level staging.
- Each remaining batch needs its own allowlist, targeted checks, and post-stage verification.
