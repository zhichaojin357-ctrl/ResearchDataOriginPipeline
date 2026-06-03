# XPS Artifact And Visual Blockers

Date: 2026-06-03

## Blocked Items

The following XPS workflow items are intentionally outside the no-artifact goal:

- OPJU exemplar comparison for heterojunction and in-situ XPS workflows.
- Origin COM execution.
- OPJU project generation.
- TIF/PNG/PDF/XLSX artifact generation.
- User visual acceptance of generated plots.
- Real fitted XPS workbook validation.
- Any automatic XPS valence-state, electron-transfer, heterojunction-mechanism, carrier-path, or S-scheme conclusion.

## Current Evidence Boundary

Current XPS source diffs include both safe planning/metadata logic and artifact-producing Origin/export logic. They must not be staged as a single commit.

The safe no-artifact work can only verify:

- planning contracts;
- manual-review behavior;
- path/parser contracts;
- absence of generated artifacts in synthetic tests.

## Future Work

A later XPS-specific Origin/visual phase should:

- run only after the no-artifact contract and source hunk split are stable;
- use explicit user approval to run Origin;
- write into a run-scoped output root;
- compare generated artifacts against approved OPJU exemplars;
- require user visual acceptance before claiming completion.

This goal did not run Origin, did not process real XPS data, did not generate artifacts, and did not modify old `output/` or `outputs/`.
