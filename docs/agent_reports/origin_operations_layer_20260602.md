# Origin Operations Layer Integration

## Reference Projects

- https://github.com/youngminsw/Origin-Pro-MCP
- https://github.com/leima-max/origin-pro-mcp-skill

Reusable design ideas adopted:

- Stable named operations instead of ad hoc COM property guessing.
- Separate project, worksheet, graph, style, export, and LabTalk operations.
- Export must verify that the target file exists and is nonempty.
- `run_labtalk` is an explicit fallback, not the default path.
- Ordinary tests use fake Origin COM objects and do not start Origin.

No third-party source code was copied into this project.

## New Skill

Created:

- `D:\CodexData\.codex\skills\origin-automation-operations\SKILL.md`
- `D:\CodexData\.codex\skills\origin-automation-operations\agents\openai.yaml`

Scope:

- Handles Origin operations only.
- Does not define Graph4 dimensions, figure style, y tick policy, material colors, or output package rules.
- `origin-plotting` remains the source for figure specifications and Graph4 style.

## Project Code

Added:

- `src\origin\operations.py`

Updated:

- `src\origin\__init__.py`

Main operation functions:

- `connect_origin`
- `new_project`
- `save_project`
- `load_project`
- `create_worksheet`
- `set_worksheet_data`
- `get_worksheet_data`
- `import_csv_to_worksheet`
- `list_worksheets`
- `create_graph`
- `add_plot_to_graph`
- `set_axis_labels`
- `set_axis_range`
- `export_graph`
- `export_all_graphs`
- `apply_publication_style`
- `set_plot_style`
- `set_graph_font`
- `set_legend`
- `set_tick_style`
- `run_labtalk`
- `get_labtalk_variable`

Default graph export for this operation layer is now 600 dpi TIF. PNG remains a preview/export format only when explicitly requested by another workflow.

## Smoke Tests

Added:

- `tests\test_origin_operations.py`

Coverage:

- Project operations.
- Worksheet create/read/write/import/list operations.
- Graph creation and plot addition.
- Axis labels and axis ranges.
- Plot style, font, legend, tick style, publication-style operation bundle.
- TIF export and export-all.
- LabTalk execution and variable read.
- `connect_origin` dispatch mode with a fake COM object.

## Verification

Commands run:

- `D:\Python\python.exe -m pytest tests\test_origin_operations.py -q`
- `D:\Python\python.exe -m pytest tests\test_origin_operations.py tests\test_origin_adapter.py -q`
- `D:\Python\python.exe D:\CodexData\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\CodexData\.codex\skills\origin-automation-operations`

Results:

- `tests\test_origin_operations.py`: 4 passed.
- `tests\test_origin_operations.py tests\test_origin_adapter.py`: 24 passed, 13 subtests passed.
- Skill validation: passed.

## Live Origin Test

Report:

- `output\reports\origin_operations_live_smoke.json`

Live task-owned Origin operations that passed:

- `new_project`
- `create_worksheet`
- `set_worksheet_data`
- `get_worksheet_data`
- `create_graph`
- `add_plot_to_graph`
- `set_axis_labels`
- `set_axis_range`
- `set_graph_font`
- `set_tick_style`
- `set_legend`
- `set_plot_style`
- `apply_publication_style`
- `run_labtalk`
- `get_labtalk_variable`
- `export_graph_tif`
- `export_all_graphs_tif`
- `save_project`
- `close`

Live output checks:

- TIF existed and was nonempty during test.
- OPJU existed and was nonempty during test.
- Temporary test directory was cleaned.

## Not Yet Verified

- Curve fitting operations were studied in the reference projects but not added to this layer yet because the current request focused on Origin operations and export.
- Complex multi-layer graph operations remain in the existing `origin-plotting` helper and Graph4 workflow.
- Parallel Origin execution remains intentionally out of scope until a task-owned instance tracker is added.
