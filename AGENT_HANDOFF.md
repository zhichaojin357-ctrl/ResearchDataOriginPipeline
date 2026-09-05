# Agent Handoff

Start from the live repository state, not old handoff reports.

Read first:

- `AGENTS.md`
- `docs/OPTIMIZATION_HANDOFF.md` — optimization branch changes, targeted test commands, and pending Windows / Origin comparison checklist.
- `README.md`
- `docs/CURRENT_STATUS.md`
- `docs/PROJECT_INDEX.md`
- `docs/REAL_DATA_INTAKE_GUIDE.md`

Rules for future work:

- The optimization branch is implemented but has not passed native Origin visual acceptance. Follow the handoff checklist before merging; historical accepted assets do not verify the new runtime code.
- Run tests by impact scope. Record unrelated existing failures without expanding the optimization task.
- Use formal CLI commands before diagnosing failures.
- Fix project modules, configuration, templates, or tests when a formal command fails.
- Do not deliver one-off script output as the final result.
- Keep generated runs outside the repo using the current runtime output-root configuration.
- Preserve raw data and external templates.
