# XPS Workflow No-Origin Review

Date: 2026-06-03

## Scope

Reviewed:

- `src/core/xps_heterojunction.py`
- `src/core/xps_in_situ.py`
- `tests/test_xps_heterojunction_stacked.py`
- `tests/test_xps_in_situ.py`

This review was no-Origin and non-generating. It did not run XPS processing or pytest nodes that create OPJU/TIF/PNG/XLSX artifacts.

## Heterojunction Workflow

The heterojunction dirty diff includes no-Origin-adjacent contract changes, but they are mixed with Origin and visual behavior:

- official PNG preview output is removed from task subdirectories;
- Origin success criteria change to OPJU/TIF only;
- generated Origin scripts include plot policy, axis/tick, page geometry, gradient fill, and TIF export width changes;
- Cu2p peak annotation and color-window logic changes;
- summary report wording and artifact table columns change.

Because these hunks mix contract and visual/Origin behavior, the current diff is not safe as an automatic no-Origin contract commit.

## In-Situ Workflow

The in-situ dirty diff includes:

- output subdirectory creation under a caller-provided output directory;
- report and manifest relocation;
- `peak_positions_summary.xlsx` relocation under `tables/`;
- matplotlib PNG/PDF/TIF figure output relocation;
- Origin OPJU grouping and style validation report changes.

The production workflow writes image and Excel artifacts by design. This GOAL cannot run that workflow or its artifact-generating tests.

## Test Boundary

The available heterojunction tests include temporary XLSX workbooks and tests involving `.opju`, `.png`, or `.tif` paths. The available in-situ production path writes `.xlsx`, `.png`, `.pdf`, and `.tif` files.

Given the explicit artifact-generation ban in this GOAL, validation is limited to non-generating checks:

- `git diff --check`;
- `py_compile`.

## Scientific-Claim Boundary

No reviewed change may be treated as proof of:

- XPS valence-state assignment;
- charge transfer;
- heterojunction mechanism;
- S-scheme mechanism;
- carrier migration path.

Those claims require separate scientific review and are outside this GOAL.

## Recommendation

Do not commit the current `src/core/xps_heterojunction.py`, `src/core/xps_in_situ.py`, or `tests/test_xps_heterojunction_stacked.py` dirty hunks in this GOAL.

Recommended next review:

- split heterojunction OPJU/TIF artifact contract from visual Origin script behavior;
- split in-situ output layout contract from matplotlib/Origin export behavior;
- add no-artifact tests that use only in-memory or plain-text path contracts if future no-Origin commits are needed.
