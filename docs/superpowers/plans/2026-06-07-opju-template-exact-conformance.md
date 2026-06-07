# OPJU Template Exact Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every generated scientific plot explicitly compare against its matched OPJU exemplar export and block or report products that are not structurally and visually close enough.

**Architecture:** Keep the existing unified V4 Origin pipeline, but add a strict conformance layer that compares exported template PNGs with regenerated product PNGs, records plot-count/style/image metrics, and refuses to call a product visually exact when source data cannot reproduce the template structure. Per-type source enrichment is limited to real adjacent source files; no template image or embedded scientific annotation is copied as fake data.

**Tech Stack:** Python 3, Origin COM through `src.origin.operations`, Pillow for PNG metrics, pytest contract tests, existing `run.py unified-v4-strict-template-conformance-all-types`.

---

### Task 1: Add Image And Structure Metrics

**Files:**
- Modify: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\src\core\v3_real_template_rebuild.py`
- Test: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\tests\test_v4_strict_template_conformance.py`

- [ ] **Step 1: Add a failing test for preview metrics**

Add a test that creates a white template PNG and black product PNG, calls the template comparison writer, and asserts the audit JSON includes `preview_rms`, `template_plot_count`, `product_plot_count`, and `strict_visual_match=false`.

- [ ] **Step 2: Implement preview metrics**

In `_write_v3_template_preview_comparison`, calculate normalized-size RMS difference, image sizes, and plot-count delta from product metadata/conformance fields.

- [ ] **Step 3: Run tests**

Run:

```powershell
D:\Python\python.exe -m pytest tests\test_v4_strict_template_conformance.py -q
```

### Task 2: Enforce Strict Visual Status

**Files:**
- Modify: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\src\core\v3_real_template_rebuild.py`
- Test: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\tests\test_v4_strict_template_conformance.py`

- [ ] **Step 1: Add a failing test for plot-count mismatch**

Construct a product summary with `template_plot_count=3`, `product_plot_count=1`, and assert strict exemplar status is `blocked_not_one_to_one`.

- [ ] **Step 2: Implement strict status**

Add a run-level strict audit after image comparison. If plot count differs, image RMS is high, or style match ratio is below threshold, record a blocking reason. Do not delete generated OPJU/TIF/PNG; mark them draft/manual-review.

- [ ] **Step 3: Run tests**

Run the V4 test file and existing Origin/style tests.

### Task 3: Add Per-Type Data Completeness Report

**Files:**
- Modify: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\src\core\v3_real_template_rebuild.py`
- Create: run output report `reports\template_data_completeness.md`
- Test: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\tests\test_v4_strict_template_conformance.py`

- [ ] **Step 1: Add a failing test for missing series report**

Assert that when template plot count is greater than generated plot count, the report lists the missing series count and says no data were fabricated.

- [ ] **Step 2: Implement report writer**

Write one row per type with selected template, template plot count, generated plot count, source files used, and missing count.

- [ ] **Step 3: Run tests**

Run:

```powershell
D:\Python\python.exe -m pytest tests\test_v4_strict_template_conformance.py -q
```

### Task 4: Opportunistically Enrich Real Multi-Series Data

**Files:**
- Modify: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\src\core\v3_real_template_rebuild.py`
- Modify only if needed: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\src\core\remaining_opju_product_drafts.py`
- Test: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\tests\test_v4_strict_template_conformance.py`

- [ ] **Step 1: Add tests for adjacent-source discovery**

Use temporary folders with multiple same-type files next to a template path and assert the discovery function returns real files only.

- [ ] **Step 2: Implement conservative discovery**

For BET, Raman, PL, photocurrent, FTIR, UV-vis, and XRD, discover adjacent source files from the selected data folder or selected template folder only when they are parseable and clearly belong to the same data type.

- [ ] **Step 3: Keep scientific boundaries**

Do not fabricate JCPDS cards, Tauc transforms, peak labels, or fitted curves. Record missing structure when source data are absent.

### Task 5: Real Origin Run And Cleanup

**Files:**
- Output only under `D:\Codex Project\科研数据处理\输出\runs\<timestamp>_unified_v4_strict_template_conformance_all_types`
- Desktop report folder only after verification.

- [ ] **Step 1: Run py_compile and pytest**

```powershell
D:\Python\python.exe -m py_compile src\core\v3_real_template_rebuild.py tests\test_v4_strict_template_conformance.py
D:\Python\python.exe -m pytest tests\test_v4_strict_template_conformance.py tests\test_epr_overlay.py tests\test_origin_operations.py tests\test_origin_style_mimic.py tests\test_user_plot_style_override.py tests\test_opju_exemplar_conformance.py -q
```

- [ ] **Step 2: Run unified V4 with Origin**

Use the final pairing file copied into the previous run and write to a new timestamped run root.

- [ ] **Step 3: Verify**

Check OPJU/TIF/PNG nonempty, template export present, side-by-side image present, strict audit present, no empty folders, no Origin process left open.

- [ ] **Step 4: Cleanup**

Keep only the latest verified run under `D:\Codex Project\科研数据处理\输出\runs`.

## Self-Review

- Spec coverage: every data type is covered by the same OPJU-template export and comparison audit; per-type data gaps are reported rather than hidden.
- Placeholder scan: no placeholder implementation steps are left.
- Type consistency: all changes are anchored in existing V4 pipeline functions and current test file names.
