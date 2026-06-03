# XPS CLI Output Routing Review

Date: 2026-06-03

## Scope

Reviewed path:

- `src/cli.py`
- `tests/test_xps_no_artifact_contracts.py`

## Current State

`src/cli.py` is clean in the current XPS no-artifact scope. The previous safe CLI help-text hunk has already been committed.

No remaining `src/cli.py` dirty hunk was found that could be split into a new XPS/output-routing commit during this goal.

## Safe Coverage

`test_xps_cli_contract_parses_without_processing_or_visual_claims` now covers:

- parser construction;
- dry-run argument parsing;
- `--with-origin` remains explicit;
- help text does not claim visual acceptance or S-scheme proof;
- no artifact files are generated.

## Not Completed

No new user-facing run-output CLI flag was added in this goal.

If XPS run-scoped output becomes a user-facing option, it should be handled in a separate CLI batch with parser-only tests and no real command execution.
