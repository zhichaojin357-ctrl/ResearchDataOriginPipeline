# Agent Reports Policy Review

Date: 2026-06-04

Scope: `docs/agent_reports` policy audit for the MEGA convergence goal.

## Audit Commands

Commands executed:

```powershell
git status --short -- docs/agent_reports
git ls-files docs/agent_reports
git ls-files -m docs/agent_reports
git ls-files --others --exclude-standard docs/agent_reports
```

## Dirty Counts At Audit

| Status | Count |
|---|---:|
| tracked modified | 7 |
| untracked | 64 |
| tracked deleted | 0 |
| total | 71 |

## Policy Decision

The current dirty files under `docs/agent_reports` are documentation/provenance files, not output artifacts. They are also represented by the current `docs/agent_reports/README.md` navigation update and by `docs/indexes/agent_reports_index.md`, which marks the phase reports as keep/current or keep/historical.

Decision:

- keep and commit the dirty `docs/agent_reports` Markdown files as documentation/provenance;
- do not run `git rm --cached` for `docs/agent_reports` in this MEGA goal;
- do not ignore the `docs/agent_reports` directory;
- do not add broad Markdown ignore rules under docs.

## Keep Categories

Keep tracked:

- current handoff files for Phase 1.9 through Phase 1.13;
- final validation and commit-readiness reports;
- path audits and cleanup audits;
- package/adaptor/BET/EPR/Origin operation reports referenced by current status documents;
- `docs/agent_reports/README.md` navigation refresh;
- existing tracked modified summaries that align agent reports with current documentation.

## Generated/Untrack Decision

No safe generated-agent-report untrack batch was executed.

Reason:

- these files are under `docs/`, not under generated output roots;
- the current index classifies them as keep;
- many are referenced by current status/index documents;
- hiding them would risk losing provenance or navigation targets.

## User Decision

No immediate user decision is needed to keep the current dirty Markdown files as formal documentation. Future user decisions may still choose to archive older historical reports, but this MEGA goal does not delete, move, or ignore them.
