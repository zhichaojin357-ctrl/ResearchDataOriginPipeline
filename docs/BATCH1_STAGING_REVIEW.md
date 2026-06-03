# Batch 1 Staging Review

Date: 2026-06-03

Scope: review and pointer-only doc narrowing. No `git add`, `git commit`, file deletion, file move, source edit, script-structure edit, output edit, validation run, test run, data processing, or Origin run was performed.

## Candidate Files

Batch 1 staging review is limited to these files:

| File | Current git status | Intended Batch 1 purpose |
| --- | --- | --- |
| `README.md` | modified | Root-level pointer to the current status/index documents |
| `PROJECT_STATUS.md` | modified | Root-level pointer to the current status/index documents |
| `TASK_BOARD.md` | modified | Root-level pointer to the current status/index documents |
| `AGENT_HANDOFF.md` | modified | Root-level pointer to the current status/index documents |
| `docs/CURRENT_STATUS.md` | untracked | Current source-of-truth project status audit |
| `docs/PROJECT_INDEX.md` | untracked | Current project structure and entry-point index |
| `docs/DIRTY_WORKTREE_GROUPING_PLAN.md` | untracked | Dirty worktree grouping and retention plan |
| `docs/OUTPUT_LAYOUT_CLEANUP_PLAN.md` | untracked | Output/outputS layout cleanup plan |
| `docs/NEXT_FUNCTION_FIX_ORDER.md` | untracked | Future function-fix priority and acceptance rules |
| `docs/LIGHT_CLEANUP_EXECUTION_A_REPORT.md` | untracked | Report for light cleanup execution A |
| `docs/PROPOSED_COMMIT_BATCHES.md` | untracked | Proposed later commit batches |
| `docs/BATCH1_STAGING_REVIEW.md` | untracked | This Batch 1 review result |

`docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md` was created only to preserve non-pointer root-doc clues and is not a Batch 1 candidate.

## Pointer-Only Cleanup Result

The four root-level documents were narrowed to pointer-only changes. Their current tracked diff now adds only this top-level pointer block pattern:

- `## Current Status Pointer`
- Pointer to `docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md`
- Statement that Phase 1.6 is the locked canonical result package, not the current engineering phase
- Statement that the root document is an entry pointer, not the latest full status source

The following extra root-doc changes were removed from the Batch 1 root diffs and summarized in `docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md` for later review:

- Phase 1.13 adapter/package sections
- script layout expansion
- external workspace path replacements
- JEOL/EPR decode documentation
- Phase 1.13 task-board/checklist material

## Diff Stat

After pointer-only cleanup, `git diff --stat --` over the Batch 1 candidate list reports tracked root-doc changes only:

```text
 AGENT_HANDOFF.md  | 4 ++++
 PROJECT_STATUS.md | 4 ++++
 README.md         | 4 ++++
 TASK_BOARD.md     | 4 ++++
 4 files changed, 16 insertions(+)
```

Normal `git diff --stat` does not include untracked docs until they are staged. The untracked docs listed above remain Batch 1 candidates by path and content scope.

## Diff Check

`git diff --check --` over the Batch 1 candidate list passed with exit code 0.

Observed output was limited to line-ending warnings that LF will be replaced by CRLF for the modified root-level Markdown files. No whitespace-error or conflict-marker failure was reported.

## Scope Review

The root-level files now meet the requested pointer-only scope:

- No Phase 1.13 adapter/package section remains in the root diffs.
- No script-layout expansion remains in the root diffs.
- No JEOL/EPR decode section remains in the root diffs.
- No external workspace path replacement remains in the root diffs.
- No claim was added that validate/readiness was rerun.
- No claim was added that any plotting issue has been fixed.

The docs candidates are within the requested Batch 1 scope:

- `docs/CURRENT_STATUS.md` and `docs/PROJECT_INDEX.md` establish the current source-of-truth status/index.
- `docs/DIRTY_WORKTREE_GROUPING_PLAN.md`, `docs/OUTPUT_LAYOUT_CLEANUP_PLAN.md`, and `docs/NEXT_FUNCTION_FIX_ORDER.md` document cleanup and future repair strategy without changing functionality.
- `docs/LIGHT_CLEANUP_EXECUTION_A_REPORT.md`, `docs/PROPOSED_COMMIT_BATCHES.md`, and this review document record the cleanup/staging plan.
- They do not recommend committing OPJU, TIF, PNG, XLSX, ZIP, large JSON, or large output directories.

## Recommendation

Batch 1 is now suitable for a real staging review, limited to the 12 candidate files listed above.

Suggested command if the user confirms staging:

```powershell
git add -- README.md PROJECT_STATUS.md TASK_BOARD.md AGENT_HANDOFF.md docs/CURRENT_STATUS.md docs/PROJECT_INDEX.md docs/DIRTY_WORKTREE_GROUPING_PLAN.md docs/OUTPUT_LAYOUT_CLEANUP_PLAN.md docs/NEXT_FUNCTION_FIX_ORDER.md docs/LIGHT_CLEANUP_EXECUTION_A_REPORT.md docs/PROPOSED_COMMIT_BATCHES.md docs/BATCH1_STAGING_REVIEW.md
```

Do not stage `docs/ROOT_DOCS_EXTRA_CHANGES_HOLD.md` in Batch 1.

After Batch 1 is staged and committed, it is reasonable to start a separate `Script Layout Preflight` review; do not move, delete, stage, or edit scripts before that preflight.
