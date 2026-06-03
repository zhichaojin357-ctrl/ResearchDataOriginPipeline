# Phase 1.11 Gitignore Update Report

- Added explicit temporary patterns: `tmp_cli_probe/`, `tmp_malformed.csv`, `tmp_out.txt`.
- Existing cache patterns remain: `.pytest_cache/`, `__pycache__/`, `*.pyc`, `*.tmp`, `*.bak`.
- Did not ignore `output/` globally, `outputs/` globally beyond existing project policy, `docs/agent_reports/`, `workspace_data/`, `*.opju`, `*.tif`, `*.png`, or `*.csv` as broad patterns.
- Purpose: keep known local scratch files out of future commits without hiding formal reports or result packages.
