# Origin Style Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the accepted V5 Origin graph styles into project-local style assets so future runs can discover a saved Graph Template/style package without relying on external OPJU exemplars.

**Architecture:** Add a small style-asset registry under `src/origin/`, a real Origin operation for saving graph pages as `.otpu`, and a CLI command that harvests accepted V5 product OPJUs into `templates/origin_styles/`. Existing V5 OPJU-template replacement remains available, but the project will now have a reviewed local style-package fallback with tests and manifest metadata.

**Tech Stack:** Python, pytest, Origin COM automation, LabTalk `save -t`, JSON manifest files.

---

## Tasks

- [x] Add tests for manifest loading, data-type lookup, and OPJU-missing fallback to a project-local `.otpu`.
- [x] Add an `OriginOperations.save_graph_template()` wrapper around LabTalk `save -t`.
- [x] Add a formal CLI command to export style assets from an accepted V5 run.
- [x] Export 11 accepted V5 graph templates into `templates/origin_styles/graph_templates/`.
- [x] Write `templates/origin_styles/manifest.json` with product key, graph template path, source run, source OPJU, preview, status, and visual comparison metadata.
- [x] Update docs to state the new dependency boundary: future runs no longer need external OPJU exemplars for style discovery, but exact products still require preview validation.
- [x] Run py_compile, targeted pytest, real asset existence checks, and git status.
- [x] Commit only exact files changed for this task.
