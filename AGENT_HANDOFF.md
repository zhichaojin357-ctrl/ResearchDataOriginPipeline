# Agent Handoff

Latest optimization review: [docs/OPTIMIZATION_SECOND_REVIEW.md](docs/OPTIMIZATION_SECOND_REVIEW.md).
Read its current Linux / Windows CI evidence before using the first-round
handoff's failure counts. Native Origin plotting and same-route visual acceptance
still require the workstation checklist.

Start from the live repository state, not old handoff reports.

Read first:

- `AGENTS.md`
- `docs/OPTIMIZATION_SECOND_REVIEW.md` — second review, additional fixes, restored asset-byte integrity, and current test evidence.
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

For a small follow-up fix, use the second-round test commands in
`docs/OPTIMIZATION_HANDOFF.md`; for a whole-batch acceptance, run the full suite
once. Windows CI exercises PowerShell and process APIs but does not establish
Origin rendering correctness.
