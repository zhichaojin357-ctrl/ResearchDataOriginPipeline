# Project Rename Report - 2026-05-31

## Summary

- Old project name: `GroupMeetingAutoPPT`
- New project name: `ResearchDataOriginPipeline`
- New usable path: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`
- Reason: the project now focuses on scientific data triage, data processing, review queues, and Origin figure export workflows rather than automatic group-meeting PPT generation.

## Completed Updates

- Updated tracked project text references from `GroupMeetingAutoPPT` to `ResearchDataOriginPipeline`.
- Updated package/config metadata:
  - `README.md`
  - `pyproject.toml`
  - `config/default.yaml`
- Updated project status and handoff documents.
- Updated reports and dashboard references that contained the old project path.
- Renamed archived instruction files under `D:\Codex Project\科研数据处理\指令归档` to the new prefix.
- Updated `D:\Codex Project\科研数据处理\指令归档\README.md`.
- Updated generated output indexes and reports under `output/` where they store display paths.
- Skipped `workspace_data/manifests` provenance files because they describe the original data-copy operation and should only be refreshed through the workspace manifest workflow.
- Kept `GROUPMEETINGAUTOPPT_DISABLE_ORIGIN` as a legacy compatibility environment variable.
- Added `RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN` as the primary Origin test guard variable.

## Folder Rename Status

Windows refused a direct physical rename of:

`D:\Codex Project\科研数据处理\GroupMeetingAutoPPT`

to:

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

The refusal was `Access is denied`, consistent with the active Codex workspace holding the old directory open. To avoid killing Codex or interrupting the current task, a temporary NTFS junction was created:

`D:\Codex Project\科研数据处理\ResearchDataOriginPipeline`

pointing to:

`D:\Codex Project\科研数据处理\GroupMeetingAutoPPT`

This makes the new path usable immediately without copying or modifying raw data. A true physical rename can be completed after the active Codex workspace releases the old directory handle.

## Safety Notes

- No F-drive backup files were modified.
- No raw data files were modified.
- No Origin process was launched for this rename.
- No no-Origin or with-Origin processing was run for this rename.
