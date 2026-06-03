# Phase 1.9 Project Structure Inventory

Generated: 2026-06-02T00:50:48

Project name is `ResearchDataOriginPipeline`. Old `GroupMeetingAutoPPT` references remain in compatibility guards, tests, and rename history.

## Root Entries
|path|exists|
|---|---|
|AGENTS.md|True|
|AGENT_HANDOFF.md|True|
|GPT_HANDOFF_20260531.md|True|
|PROJECT_STATUS.md|True|
|TASK_BOARD.md|True|
|README.md|True|
|run.py|True|
|pyproject.toml|True|
|requirements.txt|True|
|optional_requirements.txt|True|
|.gitignore|True|
|.codex|True|
|.agents|True|

## src Entries
|path|exists|
|---|---|
|src/cli.py|True|
|src/core/triage.py|True|
|src/core/process.py|True|
|src/core/project.py|True|
|src/core/metadata.py|True|
|src/core/table_reader.py|True|
|src/core/auto_queue.py|True|
|src/core/reviewed_queue.py|True|
|src/core/origin_batch.py|True|
|src/core/runtime_paths.py|True|
|src/core/validate.py|True|
|src/core/readiness.py|True|
|src/core/deps.py|True|
|src/core/epr_jeol.py|True|
|src/core/xps_in_situ.py|True|
|src/core/xps_heterojunction.py|True|
|src/core/phase1_7.py|True|
|src/core/phase1_9.py|True|
|src/processors|True|
|src/scanner|True|
|src/origin|True|

## Config Entries
|path|exists|
|---|---|
|config/default.yaml|True|
|config/local.example.yaml|True|
|config/local.yaml|True|
|config/claim_policy.yaml|True|
|config/data_selection_rules.yaml|True|
|config/sample_registry.yaml|True|
|config/manual_overrides.yaml|True|
|config/processor_registry.yaml|True|
|config/plot_style.yaml|True|

## Counts
- tests: 17
- agent reports: 121
- method cards: 15
- data format notes: 6
- workspace exists: True

## Conclusion
Source: `src`; config: `config`; tests: `tests`; current products/reports: `output`; special/older products: `outputs`; raw workspace copy: `workspace_data`. Do not delete workspace, output, outputs, docs, or phase packages.
