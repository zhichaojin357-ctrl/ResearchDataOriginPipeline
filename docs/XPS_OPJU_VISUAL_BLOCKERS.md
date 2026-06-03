# XPS OPJU Visual Blockers

Date: 2026-06-03

## Purpose

This document records XPS work that cannot be completed in a no-Origin, no-artifact, no-visual GOAL.

## Blockers

### Heterojunction Stacked XPS

Current dirty changes include:

- Origin-generated graph script styling;
- native gradient fill behavior;
- axis and tick geometry changes;
- page size and label positioning;
- TIF export width and DPI post-processing;
- removal of official PNG preview output;
- Cu2p color and peak annotation behavior changes.

These require at least one of:

- Origin execution;
- OPJU/TIF/PNG artifact inspection;
- exemplar comparison;
- user visual acceptance.

They must not be committed as a no-Origin contract-only change without that validation.

### XPS In-Situ

Current dirty changes include:

- matplotlib figure styling and export path changes;
- PNG/PDF/TIF output relocation;
- Origin OPJU grouping into separate editable graph projects;
- Origin style validation text outputs;
- quality checks over generated image and Origin artifacts.

These require artifact-generation validation and likely visual review. They are blocked in this GOAL.

### OPJU Exemplar Evidence

This GOAL did not find or create evidence that XPS OPJU exemplar comparison is fully complete. Existing XPS output/QC files are not treated as a completed exemplar visual acceptance unless a dedicated report proves it.

## Non-Goals

This document does not approve:

- running Origin;
- generating XPS artifacts;
- claiming visual acceptance;
- claiming XPS valence or mechanism interpretation.

## Next Safe Step

Recommended follow-up:

```text
GOAL: XPS OPJU Exemplar and Visual Acceptance Preflight
```

That follow-up should explicitly decide whether Origin execution and image/OPJU artifact generation are allowed.
