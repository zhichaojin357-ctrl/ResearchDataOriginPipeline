# Batch 2 Source/Config/Tests Review

Date: 2026-06-03

Scope reviewed:

- `src/`
- `config/`
- `tests/`
- `pyproject.toml`
- `optional_requirements.txt`

Commands run before grouping:

- `git status --short`
- `git status --short -- src config tests pyproject.toml optional_requirements.txt`
- `git diff --stat -- src config tests pyproject.toml optional_requirements.txt`
- `git diff --check -- src config tests pyproject.toml optional_requirements.txt`

`git diff --check` result: passed for Batch 2 scope. Git reported LF-to-CRLF conversion warnings only.

Initial dirty count: 329 items.

## Dirty Files In Scope

Tracked modified:

- `config/data_selection_rules.yaml`
- `config/default.yaml`
- `config/plot_style.yaml`
- `optional_requirements.txt`
- `pyproject.toml`
- `src/cli.py`
- `src/core/deps.py`
- `src/core/epr_jeol.py`
- `src/core/metadata.py`
- `src/core/phase1_7.py`
- `src/core/phase1_9.py`
- `src/core/process.py`
- `src/core/runtime_paths.py`
- `src/core/table_reader.py`
- `src/core/validate.py`
- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `src/origin/__init__.py`
- `src/origin/adapter.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `tests/test_jeol_epr_decode.py`
- `tests/test_manual_review_filtered_report.py`
- `tests/test_origin_adapter.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_1_process_cli.py`
- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`
- `tests/test_phase1_contracts.py`
- `tests/test_processor_behaviors.py`
- `tests/test_xps_heterojunction_stacked.py`

Untracked:

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
- `src/core/epr_overlay.py`
- `src/origin/operations.py`
- `src/origin/plot_policy.py`
- `src/origin/text_format.py`
- `tests/test_epr_overlay.py`
- `tests/test_origin_operations.py`
- `tests/test_origin_plot_policy.py`
- `tests/test_phase1_13_adapters.py`

## Functional Groups

### Batch 2A: Origin Adapter / Operations / Plot Policy / Text Formatting

Files:

- `config/plot_style.yaml`
- `src/origin/__init__.py`
- `src/origin/adapter.py`
- `src/origin/operations.py`
- `src/origin/plot_policy.py`
- `src/origin/text_format.py`
- `tests/test_origin_adapter.py`
- `tests/test_origin_operations.py`
- `tests/test_origin_plot_policy.py`

Likely function: Origin operation wrapper, Graph4 style contract, plot policy, text formatting, TIF handling, and data-type plotting adapter behavior.

Same-batch assessment: related but broad. The diff includes plot policy, adapter contract, BET/XRD column behavior, TIF post-processing, and Origin job-writing behavior.

Pollution check: no output files in this group, but it is tightly coupled to plotting behavior and Origin artifact generation.

Automatic commit suitability: no for this round.

Recommended tests:

- `D:\Python\python.exe -m py_compile src/origin/adapter.py src/origin/operations.py src/origin/plot_policy.py src/origin/text_format.py`
- `D:\Python\python.exe -m pytest tests/test_origin_adapter.py tests/test_origin_operations.py tests/test_origin_plot_policy.py -q`

Risk: HIGH. It touches plotting contracts and needs separate review under the no-plotting-fix boundary.

### Batch 2B: JEOL EPR Decode / EPR Overlay

Files:

- `config/data_selection_rules.yaml`
- `config/default.yaml`
- `src/cli.py`
- `src/core/epr_jeol.py`
- `src/core/epr_overlay.py`
- `src/core/runtime_paths.py`
- `tests/test_jeol_epr_decode.py`
- `tests/test_epr_overlay.py`

Likely function: JEOL EPR raw decode export, EPR overlay CLI, workspace path routing, and related tests.

Same-batch assessment: mostly related, but it promotes new CLI entry points and includes workspace path/config changes.

Pollution check: no output files in this group. Overlay commands can write outputs when run, so only no-Origin/non-generating tests are acceptable.

Automatic commit suitability: no for this round. It is coherent but changes formal CLI behavior and should get a dedicated review.

Recommended tests:

- `D:\Python\python.exe -m py_compile src/core/epr_jeol.py src/core/epr_overlay.py src/cli.py`
- `D:\Python\python.exe -m pytest tests/test_jeol_epr_decode.py tests/test_epr_overlay.py -q`

Risk: MEDIUM.

### Batch 2C: XPS Helpers / Heterojunction / In-situ Source Path

Files:

- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`

Likely function: XPS heterojunction and in-situ helper behavior, Origin script generation, artifact routing, annotation/styling policy, and tests.

Same-batch assessment: related to XPS, but very large and includes plotting/style behavior.

Pollution check: no output files in the diff scope, but it changes generated Origin scripts and artifact path expectations.

Automatic commit suitability: no for this round.

Recommended tests:

- `D:\Python\python.exe -m py_compile src/core/xps_heterojunction.py src/core/xps_in_situ.py`
- Targeted XPS tests only after a separate XPS review; do not run the XPS generation script in this cleanup pass.

Risk: HIGH.

### Batch 2D: Processor Base / Calculations / Table Reader / Metadata / Process Orchestration

Files:

- `src/core/metadata.py`
- `src/core/process.py`
- `src/core/table_reader.py`
- `src/processors/base.py`
- `src/processors/calculations.py`
- `tests/test_phase1_1_process_cli.py`
- `tests/test_processor_behaviors.py`
- `tests/test_phase1_contracts.py`

Likely function: core processing contracts, table reading, metadata path handling, processor outputs, BET/photocurrent data handling, and JSON reading compatibility.

Same-batch assessment: mixed. Most files are too broad for automatic commit. One isolated subset is safe: BOM-tolerant JSON reads in `src/core/process.py` plus the matching CLI test.

Pollution check: no output files in allowlisted subset.

Automatic commit suitability: yes, only for the narrow BOM JSON subset.

Recommended tests for narrow subset:

- `D:\Python\python.exe -m py_compile src/core/process.py`
- `D:\Python\python.exe -m pytest tests/test_phase1_1_process_cli.py::Phase11ProcessCliTest::test_process_from_queue_accepts_utf8_bom_json -q`

Risk: LOW for the narrow subset; HIGH for the full group.

### Batch 2E: Validation / Readiness / Phase Governance

Files:

- `src/core/phase1_7.py`
- `src/core/phase1_9.py`
- `src/core/validate.py`
- `tests/test_manual_review_filtered_report.py`
- `tests/test_phase1_10_manifest_normalizer.py`
- `tests/test_phase1_7_manifest_runner.py`
- `tests/test_phase1_8_reviewed_queue.py`
- `tests/test_phase1_9_governance.py`

Likely function: manifest/governance report hygiene, Origin process discovery encoding, plot policy fields in Phase 1.9 reports, validation contract checks, and test cleanup of temporary report outputs.

Same-batch assessment: related to governance but mixed with Origin plot policy fields and several phase-specific tests.

Pollution check: no output files should be staged. Some tests create temporary reports and clean them up.

Automatic commit suitability: no for this round.

Recommended tests:

- `D:\Python\python.exe -m py_compile src/core/phase1_7.py src/core/phase1_9.py src/core/validate.py`
- Targeted phase governance tests after a dedicated review.

Risk: MEDIUM.

### Batch 2F: Optional Adapters / Optional Requirements / Dependency Metadata

Files:

- `optional_requirements.txt`
- `pyproject.toml`
- `src/core/deps.py`
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

Likely function: optional scientific adapter metadata and candidate-only adapter layer.

Same-batch assessment: the metadata subset is independent. The adapter package itself is not independent because `tests/test_phase1_13_adapters.py` references processor-calculation bridge changes that are not safe to include automatically.

Pollution check: no output files in this group. Adapter tests may use temp directories only.

Automatic commit suitability: yes, only for the metadata subset:

- `optional_requirements.txt`
- `pyproject.toml`
- `src/core/deps.py`

Recommended checks for metadata subset:

- `D:\Python\python.exe -m py_compile src/core/deps.py`
- `D:\Python\python.exe -c "from src.core.deps import OPTIONAL; assert OPTIONAL.get('EPRpy') == 'eprpy'; print('deps optional metadata ok')"`

Risk: LOW for metadata subset; MEDIUM for full adapter package.

### Batch 2G: Ambiguous Or Risky Changes

Files:

- Any full Batch 2A Origin plotting group.
- Any full Batch 2C XPS group.
- Full adapter package plus processor calculation bridge.
- Full processor-calculation data-type changes.
- JEOL/EPR overlay CLI group until separately reviewed.

Automatic commit suitability: no.

Risk: HIGH where plotting behavior, data-type calculations, formal CLI paths, or scientific output semantics change.

## Automatic Selection For This Round

Selected maximum two safe sub-batches:

1. Batch 2D-small: BOM-tolerant queue/report JSON reads.
2. Batch 2F-lite: optional dependency metadata and pytest warning filters.

Not selected:

- Origin adapter/plot policy: too close to plotting behavior.
- JEOL/EPR decode/overlay: formal CLI and workspace-path changes need dedicated review.
- XPS: generated Origin script and plotting behavior changes are too broad.
- Optional adapter package: has hidden dependency on processor calculation bridge.
- Processor calculation/table-reader changes: multiple data-type behavior changes.

## GOAL Continuation Note

This review was carried forward into the autonomous Batch 2 GOAL continuation from commit `209d9f3`.

Continuation Phase 0 confirmed:

- Dirty count: 327 items.
- Staged files: 0.
- Batch 2 scope still has remaining source/config/test changes after `fb152fc` and `209d9f3`.
- `git diff --check -- src config tests pyproject.toml optional_requirements.txt` passed with LF-to-CRLF conversion warnings only.

This document does not claim Batch 2 is complete.
