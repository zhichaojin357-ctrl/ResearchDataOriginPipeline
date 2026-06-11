# Reviewer Report

Date: 2026-06-11

Scope: audit of `src/` and `config/` for Phase 1 rule compliance, followed by branch fixes in the formal modules and tests. No raw data was inspected or touched. `input/raw_data/` was not modified. This section supersedes the historical report below.

## Summary

The audit identified near-blocking risks in output-path hygiene and product metadata consistency. This branch fixes the generic failure-report, queue/planner, manifest-normalizer, auto-queue Markdown, triage parser-error, metadata nested-payload, XRD overlay, XPS in situ quality/report-note, XPS heterojunction preview, readiness portability, dependency-policy, and `process --auto-select --output-root` issues. Specialized product metadata naming remains documented as a broader schema unification item for historical/product-builder commands.

Passing checks:
- No `src/ppt/`, `templates/ppt/`, `ppt_layout.yaml`, `slide_plan.json`, or `presentation.pptx` implementation was found in `src/` or `config/`.
- No kinetics processor was found. `config/processor_registry.yaml` classifies `kinetics_reference_literature` / `动力学` as scan-only `reference_literature` with `selected_processor: none`.
- `config/claim_policy.yaml` contains high-risk claim guardrails for mechanism, heterojunction, XPS, EPR, XRD, LC-MS/MS, HRTEM lattice, and kinetics-reference misuse.
- Generic processor metadata uses `metadata/<type>/<slug>/metadata.json` and checks expected `.opju`, `.tif`, and `manual_check_required` fields before success metadata is written.

## Findings

### 1. Failure reports can leak absolute local/raw paths

Severity: High

Evidence:
- `src/core/process.py:409` builds failure records.
- `src/core/process.py:415` stores `source_file` as `str(source)`.
- `src/core/process.py:422` stores `error_message` as raw `str(exc)`.
- `src/core/process.py:449` to `src/core/process.py:468` writes these records to `processing_failures.json` and `processing_failures.md`.

Risk:
Reader/parser exceptions commonly include full Windows paths. This can leak local workspace paths, raw-data layout hints, user names, or other machine traces into output reports.

Suggested fix:
Pass `project_root` and the active output root into `_failure_from_exception()`, render source paths with `render_output_path()`, and scrub exception text with `scrub_output_text()` before writing JSON/Markdown reports.

Branch status:
Fixed in `src/core/process.py` with regression coverage in `tests/test_phase1_1_process_cli.py` and `tests/test_output_routing.py`.

### 2. Queue/planner reports write absolute input and package paths without sanitizer

Severity: High

Evidence:
- `src/core/origin_batch.py:135` to `src/core/origin_batch.py:139` writes `manifest` and `package_root` as resolved absolute paths.
- `src/core/origin_batch.py:313`, `src/core/origin_batch.py:320`, and `src/core/origin_batch.py:349` write `source_path_checked` as absolute paths.
- `src/core/reviewed_queue.py:160` to `src/core/reviewed_queue.py:165` writes absolute `proposals` and `decisions` paths.
- `src/core/manifest_normalizer.py:42` to `src/core/manifest_normalizer.py:47` writes absolute `source_manifest` and `source_package` paths.

Risk:
These JSON/Markdown outputs may expose local workspace names, external package locations, and source-data layout. The destination path guard only protects where files are written; it does not sanitize payload values.

Suggested fix:
Normalize all report payload paths through `render_output_path(..., project_root=..., output_root=...)` or a dedicated report-path serializer. For external package roots, prefer a short label plus hash evidence instead of full absolute path.

Branch status:
Fixed for the reviewed planner/queue/manifest payloads in `src/core/origin_batch.py`, `src/core/reviewed_queue.py`, and `src/core/manifest_normalizer.py`, with regression coverage in the Phase 1.7, Phase 1.8, and Phase 1.10 tests.

### 3. Several formal commands can write run outputs outside canonical `output/`

Severity: High

Evidence:
- `src/core/runtime_paths.py:58` to `src/core/runtime_paths.py:82` allows explicit output roots, `config/local.yaml` output roots, environment output roots, and configured output roots.
- `src/core/runtime_paths.py:99` to `src/core/runtime_paths.py:105` creates run layouts under the chosen base.
- `src/core/project.py:25` to `src/core/project.py:39` allows any caller-provided `output_root` as an allowed write root.
- `src/cli.py:88` to `src/cli.py:191` exposes `--output-root` on OPJU/product rebuild commands, described as an external output root in several help strings.

Risk:
The Phase 1 rule says all run outputs must be under `output/`. Product and rebuild commands can intentionally route output elsewhere. Generic `write_metadata()` is stricter, but several product paths write metadata manually and therefore do not inherit that guard.

Suggested fix:
For Phase 1, enforce `project_root/output` as the only canonical output root, or explicitly mark external-output commands as historical/non-deliverable and exclude them from readiness. If `--output-root` remains, sanitize reports against that output root and fail readiness when deliverables are outside canonical `output/`.

Branch status:
External run roots remain an intentional run-scoped feature for selected commands, but this branch adds sanitizer coverage and route consistency for the reviewed report/queue paths. Readiness now distinguishes portable missing generated artifacts from strict artifact validation.

### 4. Specialized product metadata is not consistently named `metadata.json`

Severity: High

Evidence:
- `src/core/opju_product_pilot.py:646` to `src/core/opju_product_pilot.py:674` writes `metadata/<slug>.json` manually.
- `src/core/remaining_opju_product_drafts.py:175` reuses the same product metadata writer.
- `src/core/v2_exemplar_conformance.py:708` to `src/core/v2_exemplar_conformance.py:739` writes `metadata/<slug>.json`.
- `src/core/v3_real_template_rebuild.py:2794` to `src/core/v3_real_template_rebuild.py:2832` writes `metadata/<slug>.json`.
- `src/core/xps_heterojunction.py:324` to `src/core/xps_heterojunction.py:325` writes `<comparison>_metadata.json`.
- `src/core/xps_in_situ.py:211` to `src/core/xps_in_situ.py:227` writes a manifest report, but no per-dataset `metadata.json`.

Risk:
The project rule requires every processor/successful dataset to output `metadata.json`. These specialized paths may be invisible to downstream validators expecting `metadata.json`, and they bypass the unified success-artifact checks in `src/core/metadata.py`.

Suggested fix:
Use `write_metadata()` for specialized product outputs where possible, or write a canonical `metadata/<dataset_id>/metadata.json` alongside legacy product JSON. Keep one schema for `origin_file`, `figure_tif`, `preview_png`, `manual_check_required`, `status`, and source-path rendering.

Branch status:
Recorded as a broader schema-unification follow-up. This branch hardens the shared `write_metadata()` path and fixes newly audited path/message leakage in specialized outputs without changing legacy product metadata filenames.

### 5. XPS heterojunction Origin export drops preview PNG from success metadata

Severity: Medium

Evidence:
- `src/core/xps_heterojunction.py:418` to `src/core/xps_heterojunction.py:435` computes `origin_file`, `figure_tif`, and `preview_png`.
- `src/core/xps_heterojunction.py:471` to `src/core/xps_heterojunction.py:475` checks only `.opju` and `.tif` after Origin export.
- `src/core/xps_heterojunction.py:476` returns `preview_png: None` on success.
- `src/core/xps_heterojunction.py:318` to `src/core/xps_heterojunction.py:325` then records the incomplete artifact set into metadata.

Risk:
The report can claim a successful Origin product while omitting preview evidence needed for visual QC. This is not raw-data destructive, but it weakens the OPJU/TIF/preview completeness trail.

Suggested fix:
Return the real preview PNG path on success, include it in missing/empty artifact checks if visual preview is required, and apply the same path rendering/sanitization used by the generic Origin adapter.

Branch status:
Fixed in `src/core/xps_heterojunction.py`; successful XPS heterojunction Origin export now requires and returns the preview PNG.

### 6. `xps_in_situ` accepts arbitrary output directories and lacks canonical metadata

Severity: Medium

Evidence:
- `src/core/xps_in_situ.py:164` to `src/core/xps_in_situ.py:174` resolves and creates the supplied `output_dir` directly.
- `src/core/xps_in_situ.py:211` to `src/core/xps_in_situ.py:227` writes manifest/report JSON under that directory.
- `src/core/xps_in_situ.py:685` to `src/core/xps_in_situ.py:690` returns only `origin_file` in the Origin status, not a complete `.opju`/`.tif`/preview metadata record.

Risk:
This source API can write outside canonical `output/` when called by scripts, and its deliverable metadata does not match the Phase 1 `metadata.json` expectation.

Suggested fix:
Require a project-root-relative output plan, guard with the same output-root policy used by formal commands, and emit canonical `metadata.json` for every successful dataset/product.

Branch status:
Partially fixed for path hygiene: quality-check keys, loader notes, origin messages, and report payloads are sanitized. Canonical per-dataset `metadata.json` remains part of the broader specialized product metadata unification item.

### 7. `process --auto-select --output-root` has inconsistent output-root routing

Severity: Medium

Evidence:
- `src/core/process.py:35` to `src/core/process.py:39` runs triage without forwarding `options.output_root`.
- `src/core/process.py:47` later reads `processing_queue.json` from `report_path(..., output_root=options.output_root)`.

Risk:
With a non-default output root, auto-select can write the queue to the default output tree and then try to read it from a different tree. This is mainly a reliability issue, but it also makes output-location guarantees harder to reason about.

Suggested fix:
Forward `output_root=options.output_root` into `TriageOptions`, or reject `--auto-select` with an external output root.

Branch status:
Fixed in `src/core/process.py`; covered by `tests/test_output_routing.py`.

## Additional Notes

Raw-data safety:
- No obvious `input/raw_data/` delete/move/overwrite path was found in the reviewed `src/` and `config/` files.
- Destructive file operations observed in `src/origin/adapter.py` and `src/core/xps_heterojunction.py` target generated artifacts or temporary job scripts, not raw input paths, based on the reviewed code.

Origin / OPJU:
- `config/plot_style.yaml` requires `.tif` at 600 dpi.
- `src/origin/adapter.py` contains stronger generic checks for `.opju`, `.tif`, preview PNG, file existence, non-empty artifacts, and TIF normalization than several specialized product builders.

Claim guardrails:
- `config/claim_policy.yaml` and `src/core/metadata.py` provide explicit controls requiring `manual_check_required` for high-risk conclusions.
- The main residual risk is bypass: specialized manual metadata/report writers need to use the same policy path so XPS/EPR/XRD/LC-MS/heterojunction claims cannot be promoted by product-specific code.

GPL/source-copying:
- No copied GPL source implementation was evident from the reviewed `src/` and `config/` paths. GPL-like references found in adapter audit metadata appear to be policy/reference annotations, not vendored source code.

Recommended priority order:
1. Keep failure, planner, queue, and manifest payload path-sanitizer tests in the main smoke set.
2. Decide whether external output roots remain an intentional run-scoped feature or should be limited to historical/non-deliverable commands.
3. Standardize specialized product metadata to canonical `metadata.json`.
4. Continue aligning older specialized Origin exporters with the generic adapter artifact checks.

---

# Reviewer Report

Date: 2026-05-30

Scope: final reviewer recheck for the Phase 1 planning checkpoint after the JSON-compatible YAML repair. No source code, config files, raw data, output data, PPT files, processor files, data processing, or Origin workflows were modified or executed. This report is the only file intentionally overwritten by the reviewer.

## Findings

### No blocking findings remain

Severity: None

The previous blocking findings for `config/processor_registry.yaml` and `config/claim_policy.yaml` are resolved.

Evidence:
- `config/processor_registry.yaml` parses successfully as JSON, which is valid YAML syntax.
- `config/claim_policy.yaml` parses successfully as JSON, which is valid YAML syntax.
- Neither repaired config contains the malformed Chinese mapping-key pattern such as `动力学:`.
- The repaired configs do not show collapsed list/map lines or unterminated quoted strings.
- Unicode escapes such as `\u52a8\u529b\u5b66` decode correctly to Chinese folder names, including `动力学`.

## Registry Audit

`config/processor_registry.yaml` is structurally safe and matches the required Phase 1 scope.

Parser-confirmed results:
- Total entries: 19.
- Supported entries: 14.
- Declared `phase1_supported_count`: 14.
- Deferred/reference entries: 5.

Supported Phase 1 processor planning entries:
- `photocurrent_20260109` -> `photocurrent_processor`.
- `bet` -> `bet_processor`.
- `epr` -> `epr_processor`.
- `pl` -> `pl_processor`.
- `xps` -> `xps_processor`.
- `xrd` -> `xrd_processor`.
- `uvvis_drs` -> `uvvis_drs_processor`.
- `photocurrent_response` -> `photocurrent_processor`.
- `reaction_condition_screening` -> `condition_screening_processor`.
- `ftir` -> `ftir_processor`.
- `raman` -> `raman_processor`.
- `mott_schottky` -> `mott_schottky_processor`.
- `lc_exported_data` -> `lc_exported_data_processor`.
- `eis` -> `eis_processor`.

Deferred scan-only entries:
- `SEM`: `SEM_image_data`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`, `deferred_reason=image_data_deferred`.
- `TEM`: `TEM_image_data`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`, `deferred_reason=image_data_deferred`.
- `核磁`: `NMR`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`, `deferred_reason=nmr_deferred`.
- `质谱`: `MS`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`, `deferred_reason=ms_deferred`.

Reference-literature scan-only entry:
- `动力学`: `reference_literature`, `supported_in_phase_1=false`, `selected_processor=none`, `special_handling=scan_only`, `deferred_reason=文献资料文件夹，不是实验动力学数据`.

## Claim Policy Audit

`config/claim_policy.yaml` is structurally safe and preserves the required claim guardrails.

Parser-confirmed results:
- `forbidden_claims` contains 14 entries.
- The global forbidden list includes "do not treat kinetics folder as experimental kinetics data".
- The global forbidden list includes "do not create kinetics processor".
- `type_specific.kinetics_reference_literature` decodes `folder_name` as `动力学`.
- `type_specific.kinetics_reference_literature.required_handling` is `reference_literature`.
- The kinetics type-specific forbidden rules prohibit creating a kinetics processor and prohibit processing, fitting, or plotting it as experimental kinetics data.

High-risk claim controls remain present for XPS, EPR, XRD, UV-vis DRS, EIS, LC/HPLC, LC-MS/MS, HRTEM lattice, Mott-Schottky band-edge interpretation, heterojunction mechanism, and reaction mechanism.

## Coordination And Origin Planning

Passing checks:
- `.codex/config.toml` sets `[agents] max_threads = 5`.
- `.codex/config.toml` sets `[agents] max_depth = 1`.
- `TASK_BOARD.md`, `PROJECT_STATUS.md`, `AGENT_HANDOFF.md`, and `docs/CODEX_GOAL_PHASE1.md` reflect max 5 concurrent subagents and prohibit nested subagents.
- `config/plot_style.yaml` references `D:\CodexData\.codex\skills\origin-plotting`.
- `config/plot_style.yaml` records `Graph4`, `Origin.Application`, avoidance of `Origin.ApplicationSI`, template residue cleanup, `.opju`/`.tif` output expectations, and PNG preview visual inspection before claiming the Origin graph is correct.

## Forbidden Scope Re-Audit

Passing checks:
- No `src/ppt/` path found.
- No `templates/ppt/` path found.
- No `ppt_layout.yaml` found.
- No `slide_plan.json` found.
- No `presentation.pptx` found.
- No kinetics processor file found by path/name inspection.
- `src/` currently contains only `src/cli.py` from this audit's file listing.
- `input/raw_data/` remains empty from a read-only listing.
- No raw data processing was performed.
- Origin was not called.

## Residual Risks

- This is still a planning checkpoint. The registry and policy are now parseable, but no scanner, validator, processor dispatch, or claim-enforcement runtime has been implemented or tested yet.
- `input/raw_data/` is currently empty, so real folder classification still needs revalidation after raw data is populated.
- Several older planning reports still contain mojibake-rendered Chinese text, but the repaired machine-readable configs decode the critical Chinese folder names correctly.
- Origin integration remains planning-only. The future implementation still needs a real smoke test and visual PNG preview inspection before any plotting correctness claim.

## Readiness Assessment

Ready for user decision on the next checkpoint. The prior config-readability blockers are resolved, the 19-entry registry matches the required 14 supported plus 5 deferred/reference scan-only scope, claim-policy guardrails are preserved, max concurrency/depth requirements are documented, Origin planning references the required workflow, and forbidden Phase 1 scope remains absent.

Per `TASK_BOARD.md`, the project should now stop and wait for explicit user confirmation before any coding checkpoint begins.
# Historical Status

Historical planning-checkpoint report. Superseded by the Phase 1 coding checkpoint documents for implementation status; still useful only for planning/config audit evidence.
