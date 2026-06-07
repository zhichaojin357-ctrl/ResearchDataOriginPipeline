# Template Format Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Origin-backed plotting so every data type starts from its matching OPJU/template style source, exports the reference image for visual comparison, generates products through a template/format base instead of loose parameter mimicry, and keeps iterating until one-to-one replication is achieved.

**Architecture:** Add a dedicated template-format execution layer under `src/origin/` and a small orchestrator under `src/core/`. Existing v3/v4 product builders remain available but must not absorb the new template/format policy. Low-level Origin COM/LabTalk operations stay behind named wrappers; data-type processors call the new policy layer rather than issuing ad hoc Origin commands.

**Tech Stack:** Python, pytest, Origin COM automation, LabTalk only through `src/origin/operations.py` wrappers, existing ResearchDataOriginPipeline processors and CLI.

---

## Constraints

- [ ] Never modify source data under `F:\` or original OPJU exemplars.
- [ ] Write all generated OPJU/TIF/PNG/metadata/report files under the external output root.
- [ ] For every plotted data type, resolve the matching exemplar before processing starts.
- [ ] Export the exemplar graph image and store it next to product previews for side-by-side audit.
- [ ] Prefer template-as-base or Origin copy-format/theme/template behavior over hand-built parameter mimicry.
- [ ] If the OPJU exemplar is missing, require a saved Theme/Graph Template/style package before claiming reproducible plotting.
- [ ] Preserve global plot rules: 3 pt curves where applicable and bold axis titles.
- [ ] Keep scripts organized by stable modules and formal CLI entry points; no loose one-off scripts in project root.
- [ ] Stage and commit only exact files changed for this task.

## Implementation Tasks

- [ ] Add tests for the template-format policy:
  - [ ] OPJU exemplar available -> execution plan uses `opju_template_base`.
  - [ ] OPJU missing but cached style package available -> execution plan uses `cached_style_package`.
  - [ ] Both missing -> execution is blocked and cannot claim one-to-one replication.
  - [ ] Every data-type job records exemplar preview, product preview, and comparison metadata.
  - [ ] Axis title bold and 3 pt curve policy are emitted in plot intent.

- [ ] Inspect Origin capability:
  - [ ] Check official Origin documentation for reusable Theme/Graph Template/Copy Format behavior.
  - [ ] Probe local Origin COM object for safe project, page, graph, template, and worksheet operations.
  - [ ] Record findings in a repo doc so future runs do not rely on memory or chat text.

- [ ] Implement new modules:
  - [ ] `src/origin/template_format.py` for template source resolution, style-package manifest handling, and plot intent policy.
  - [ ] `src/core/template_format_executor.py` for data-type orchestration and run-manifest/report generation.
  - [ ] CLI entry point for template-format conformance that does not replace v3/v4 silently.

- [ ] Integrate with current products:
  - [ ] Reuse existing data processing outputs where correct.
  - [ ] Before each type, load the selected exemplar metadata and exported exemplar preview.
  - [ ] Generate product outputs under a new timestamped run directory.
  - [ ] Mark any not-yet-exact item as manual calibration required; do not overstate exactness.

- [ ] Verify:
  - [ ] Run py_compile on new and touched modules/tests.
  - [ ] Run targeted pytest.
  - [ ] Run a template-format dry run or real run, depending on available safe Origin operations.
  - [ ] Check generated folders for zero-byte/empty artifact issues.

- [ ] Commit:
  - [ ] Review `git status --short`.
  - [ ] Stage exact files only.
  - [ ] Review cached diff.
  - [ ] Commit with a message scoped to template-format executor work.

## Acceptance Criteria

- [ ] The project has a durable template/format execution path separate from older mimic scripts.
- [ ] The code refuses to claim exact replication when neither OPJU nor saved style package exists.
- [ ] Reference exports are first-class comparison artifacts for every data type handled by the new path.
- [ ] Tests cover policy behavior and prevent fallback to silent parameter-only mimicry.
- [ ] The final report clearly states current exactness, remaining gaps, and next calibration work.
