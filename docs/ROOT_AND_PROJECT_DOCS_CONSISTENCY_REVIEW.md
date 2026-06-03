# Root And Project Docs Consistency Review

Date: 2026-06-04

Scope: Section C review for root docs, `AGENTS.md`, current status/index docs, intake docs, indexes, and method cards.

## Audit Commands

Commands executed:

```powershell
git status --short -- AGENTS.md README.md PROJECT_STATUS.md TASK_BOARD.md AGENT_HANDOFF.md docs/CURRENT_STATUS.md docs/PROJECT_INDEX.md docs/NEXT_GOAL_QUEUE.md docs/REMAINING_SOURCE_DIRTY_QUEUE.md
git diff --stat -- AGENTS.md README.md PROJECT_STATUS.md TASK_BOARD.md AGENT_HANDOFF.md docs/CURRENT_STATUS.md docs/PROJECT_INDEX.md docs/NEXT_GOAL_QUEUE.md docs/REMAINING_SOURCE_DIRTY_QUEUE.md
```

## Directly Dirty In Required Set

```text
AGENTS.md
```

`README.md`, `PROJECT_STATUS.md`, `TASK_BOARD.md`, `AGENT_HANDOFF.md`, and `docs/REMAINING_SOURCE_DIRTY_QUEUE.md` were not dirty in the required check. `docs/CURRENT_STATUS.md`, `docs/PROJECT_INDEX.md`, and `docs/NEXT_GOAL_QUEUE.md` were refreshed in this batch to avoid stale guidance.

## Additional Documentation Dirty Reviewed

Reviewed and kept as documentation:

```text
docs/REAL_DATA_COMPATIBILITY_MATRIX.md
docs/REAL_DATA_INTAKE_GUIDE.md
docs/indexes/output_reports_index.md
docs/indexes/outputs_index.md
docs/method_cards/README.md
docs/method_cards/bet.md
docs/method_cards/epr.md
docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md
```

## Decisions

- Keep `AGENTS.md` project-entrypoint guidance because it reinforces formal CLI/module-first execution.
- Keep intake and compatibility path updates pointing to the external workspace copy.
- Keep method-card updates for BET and EPR because they document plotting/reader boundaries and do not claim completed visual acceptance.
- Keep output index updates, but mark `output_reports_index` as a historical inventory superseded by MEGA output-report policy.
- Keep `ROOT_DOCS_EXTRA_CHANGES_HOLD.md` as a review note; it does not authorize automatic root-doc expansion.
- Do not claim Origin, visual acceptance, or real-data processing has been completed.

## Remaining Docs Policy

Root pointer files remain intentionally concise. Future root-doc expansion should be a separate goal and should avoid duplicating current status details that now live in `docs/`.
