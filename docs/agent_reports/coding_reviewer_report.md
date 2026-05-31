# Coding Reviewer Report

Date: 2026-05-30

Scope: read-only review of the current ResearchDataOriginPipeline coding checkpoint. I inspected code, tests, configs, docs, and existing reports. I did not call Origin, did not process raw data, did not run the test suite because it would rewrite files under `output/`, and did not modify code/config/raw data/output data. This report is the only file written.

## Findings

### P0 - `validate` command cannot import because `src/core/validate.py` is syntactically invalid

Evidence:
- `src/core/validate.py:60` contains an f-string expression with escaped quotes: `{'pass' if 'format: \"tif\"' in text ...}`.
- Python AST parsing reports: `SyntaxError: f-string expression part cannot include a backslash`.
- `src/cli.py:8` imports `validate` at module import time, so this parse error prevents the CLI from starting, including commands unrelated to validation.

Impact:
- Current checkpoint is not runnable as a CLI from source.
- Existing `output/reports/validation_report.md` appears to be stale evidence from a previous valid state; it should not be treated as proof that the current source validates.

### P1 - Coding order has jumped ahead and mixed multiple stages

Evidence:
- `src/cli.py:34-46` exposes `scan`, `process`, `origin-test`, `deps-audit`, and `validate`.
- `src/scanner/scanner.py` implements scanning and report writing.
- `src/core/metadata.py`, `src/core/deps.py`, `src/core/table_reader.py`, `src/origin/adapter.py`, and `src/core/validate.py` are all present.
- `src/processors/base.py` implements a generic processor path and dispatch for every supported registry entry.

Assessment:
- This goes beyond the first coding-order item (`scanner`) and includes metadata, dependency audit, Origin test, table reader, generic processing, and validate in one checkpoint.
- It does not create PPT or kinetics code, but the implementation is not staged according to the documented order.

### P1 - Processor implementation is too generic for the stated objective

Evidence:
- `src/processors/base.py:87-93` sends every `supported_in_phase_1` file to one generic `process_table_dataset`.
- `src/processors/base.py:27-67` reads two numeric columns, sorts by x, writes `x,y`, and calls Origin for all data types.

Impact:
- Required domain-specific outputs are mostly missing: XRD peak candidates, UV-vis DRS Kubelka-Munk/Tauc calculations, EIS Nyquist/Bode handling, photocurrent metrics, XPS-specific safeguards, PL/FTIR/Raman peak candidates, LC/BET/EPR/Mott-Schottky handling, etc.
- The generic processor may be acceptable as a temporary skeleton only if labeled as such; it is not a completed Phase 1 processor implementation.

### P1 - Origin implementation does not yet meet the required Origin behavior

Evidence:
- `src/origin/adapter.py:15-24` honestly checks `originpro` and `win32com` availability.
- `src/origin/adapter.py:27-32` writes failures to `output/reports/origin_errors.md`.
- `src/origin/adapter.py:52-60` uses the default Origin `line` template and exports TIF, but does not apply the required `Graph4` template workflow, plot style config, 600 dpi setting, or PNG preview inspection.
- `src/origin/adapter.py:68-76` creates test CSV data under `output/processed_data/_origin_test`, which is output-scoped and not raw-data mutation.

Assessment:
- Origin failures are reported honestly.
- The current Origin adapter is a smoke-test placeholder, not the specified final plotting workflow.

### P2 - Scan path is mostly in scope, but the `--config` argument is ignored

Evidence:
- `src/cli.py:16-18` accepts `--config` for `scan`.
- `src/cli.py:34-35` calls `scan_raw_data(project_root, Path(args.input))` without passing the config path.
- `src/scanner/scanner.py:58-115` reads the processor registry and writes only under `output/reports`.

Impact:
- The command surface matches the spec, but config-driven path behavior is incomplete.
- This is not a scope violation, but it is a missing implementation piece.

### P2 - Tests exist but are not currently usable as checkpoint evidence

Evidence:
- `tests/test_phase1_contracts.py` is syntactically valid by AST parse.
- Tests include temp-project coverage for scan, process, and deps-audit.
- `tests/test_phase1_contracts.py:104-114` runs `validate` against the real project root and writes `output/reports/validation_report.md`.

Assessment:
- I did not run tests because the review constraints prohibit modifying output data other than this report.
- Even if run were allowed, the current CLI import blocker would prevent the suite from exercising the implementation from source.

## Scope Guard Review

Passing or mostly passing:
- No `src/ppt/`, `templates/ppt/`, `ppt_layout.yaml`, `slide_plan.json`, or `presentation.pptx` was found by filename/path-name inspection.
- No kinetics processor file was found. The only kinetics-named item is the allowed reference-literature note.
- `config/processor_registry.yaml` marks `动力学` as `reference_literature`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`.
- `src/scanner/scanner.py` reads raw data and writes reports under `output/reports`; it does not mutate raw files.
- `src/core/process.py` and `src/processors/base.py` write processed data, metadata, reports, Origin files, and figures under `output/`.
- `input/raw_data/` was observed empty; no raw data was processed during this review.

Risks:
- Because `process` currently dispatches generic processing to all supported entries, future real raw data could be processed before per-method safeguards are ready.
- The existing generated reports under `output/reports` are stale relative to the current syntactically invalid `validate.py`.

## Missing Pieces Against Coding Order

1. Scanner: partially implemented. Needs config argument handling and stronger classification evidence for real raw folders when data exists.
2. Metadata protocol: partially implemented. Schema exists, but `forbidden_claims` is always empty and template usage is hardcoded even when Graph4 is not actually used.
3. Deps-audit: implemented at basic import-check level. Existing report shows missing core dependencies.
4. Origin-test: placeholder implemented. Needs actual required style/export behavior, DPI control, `.opju`/`.tif` verification, and visual preview workflow before claiming graph correctness.
5. Generic table reader: implemented minimally. Needs method-aware parsing and safer handling of non-table extensions listed in the registry.
6. XRD processor: not implemented as a real XRD processor; only generic two-column normalization/sorting exists.
7. UV-vis DRS processor: not implemented; no Kubelka-Munk/Tauc calculations.
8. EIS processor: not implemented; no Nyquist/Bode-specific output.
9. Photocurrent processor: not implemented; no peak/steady/on-off candidate metrics.
10. XPS processor: not implemented; no XPS-specific plotting or candidate extraction beyond generic manual-check metadata.
11. PL / FTIR / Raman processors: not implemented beyond generic two-column output.
12. Condition screening / LC exported data processors: not implemented beyond generic two-column output.
13. BET / EPR / Mott-Schottky processors: not implemented beyond generic two-column output.
14. Validate: intended implementation exists but is currently blocked by syntax error.

## Verification Performed

- Read source, docs, configs, existing reports, and tests.
- Used read-only AST parsing to check syntax for `src/core/validate.py` and `tests/test_phase1_contracts.py`.
- Did not run `pytest`, `run.py validate`, `run.py process`, or `run.py origin-test` because those commands would modify `output/` and/or call Origin.
- Did not call Origin.
- Did not process raw data.

## Recommended Fix Order

1. Fix `src/core/validate.py` syntax first; this unblocks all CLI imports.
2. Re-run validation only in an implementation turn where output writes are allowed.
3. Re-stage the checkpoint: complete and test scanner, metadata, deps-audit, and origin-test before broad processor dispatch.
4. Keep `process` either disabled for unsupported/incomplete processors or clearly fail-fast until the relevant processor is implemented.
5. Update Origin adapter to follow the documented Graph4/template and preview-inspection workflow before treating Origin export as complete.
# Historical Status

Historical coding-review snapshot. Superseded detail: candidate-output calculations now exist for the listed methods. Remaining risk: these are still candidate/scaffold calculations, not fully validated method-specific processors. Python 3.10 parse compatibility has been rechecked for the updated core modules in the current coding checkpoint.
