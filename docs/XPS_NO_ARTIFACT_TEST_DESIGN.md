# XPS No-Artifact Test Design

Date: 2026-06-03

## Purpose

The XPS workflow needs an explicit no-artifact contract before any Origin, OPJU, image, or visual-acceptance work resumes. These tests document behavior that can be verified without real data or generated artifacts.

## Contract Rules

The no-artifact contract means:

- no Origin launch;
- no real XPS workbook processing;
- no OPJU/TIF/PNG/PDF/XLSX/ZIP generation;
- no writes to real `output/` or `outputs/`;
- synthetic fixtures only;
- no XPS valence, electron-transfer, heterojunction-mechanism, or S-scheme conclusions.

## Covered Cases

### Heterojunction Planning

`test_xps_heterojunction_plan_is_no_artifact_until_execution` builds synthetic `XpsFitRecord` objects and calls `build_comparison_plan`.

It verifies:

- a valid BOBC/BC comparison can be planned;
- no output directory is created by the planning step;
- no artifact suffixes are produced.

`test_xps_heterojunction_missing_counterpart_stays_manual_review_only` verifies that a missing BC counterpart remains a manual-review item and does not create a single-sided plot artifact.

### In-Situ Planning

`test_xps_in_situ_panel_planning_is_no_artifact_metadata_only` uses synthetic `InSituRecordStatus` values and calls `planned_panels`.

It verifies:

- complete panels can be planned as metadata;
- incomplete panels stay in missing/manual-review state;
- no artifacts are created.

### CLI Contract

`test_xps_cli_contract_parses_without_processing_or_visual_claims` builds the parser and parses a dry-run XPS command.

It verifies:

- parser construction and dry-run parsing do not process data;
- `--with-origin` remains an explicit Origin-launch flag in help text;
- help text does not claim visual acceptance or S-scheme proof;
- no artifacts are created.

## Explicit Non-Coverage

These tests do not validate:

- OPJU exemplar comparison;
- TIF/PNG/PDF/XLSX export;
- Origin COM behavior;
- visual acceptance;
- real XPS fitted workbook parsing;
- scientific interpretation.

Those items remain blockers for a later Origin/visual phase.
