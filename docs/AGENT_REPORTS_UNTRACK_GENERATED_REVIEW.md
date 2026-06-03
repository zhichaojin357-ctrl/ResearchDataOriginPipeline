# Agent Reports Untrack Generated Review

Date: 2026-06-04

Scope: AR-UNTRACK-GENERATED review.

## Decision

No `docs/agent_reports` paths are untracked in this MEGA goal.

Reason:

- current dirty agent reports are Markdown documentation/provenance files;
- current indexes and README navigation treat them as keep targets;
- several reports are cited by current status/project index docs;
- broad `docs/agent_reports` untracking or ignoring is explicitly forbidden.

## Future Possible User Decision

A future archive goal may decide whether older historical agent reports should remain in active docs, be moved to an archive, or be left as-is. That future goal must not delete or move files without explicit user approval.
