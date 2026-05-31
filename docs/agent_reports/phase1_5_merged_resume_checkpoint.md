# Phase 1.5 Merged Resume Checkpoint

Created at: 2026-05-31 00:36 +08:00

## Purpose

This checkpoint supports automatic continuation after quota exhaustion or interruption. A thread heartbeat named `继续 Phase 1.5 任务` has been created with id `phase-1-5` and wakes this thread every 30 minutes.

## Active Goal

Complete ResearchDataOriginPipeline Phase 1.5-Merged while preserving raw-data safety, no-Origin defaults, and PPT/kinetics/deferred-type guardrails.

## Instruction Archive

The current long instruction was archived byte-for-byte at:

`D:\Codex Project\科研数据处理\指令归档\ResearchDataOriginPipeline_phase1_5_merged_completion_and_hardening_instruction.md`

Source attachment SHA256 and archived MD SHA256 were both:

`EB49DA73C432567EADFCB9A8C27A2A845F4DC9C40735256754207C582507A1AF`

## User Addendum

After completing the Phase 1.5 tasks, create a new result folder that:

- extracts/copies only selected data that need processing;
- processes those selected data;
- stores processed outputs, metadata, plot previews/screenshots, and an index table;
- labels every output clearly with the corresponding source dataset to avoid confusion.

## Hard Guardrails

- Do not modify, move, rename, or delete `F:\课题\LL\检测`.
- Do not modify, move, rename, or delete original files inside `workspace_data\LL_detection_copy_20260530`.
- Do not write scratch, output, cache, or marker files inside raw/workspace source-data folders.
- Do not generate PPT files or PPT modules.
- Do not create a kinetics processor or treat `14_动力学` as experimental kinetics data.
- Keep SEM/TEM/NMR/MS as scan-only/deferred.
- Do not batch-process all `MANUAL_REVIEW`.
- Queue processing must default to no-Origin.
- Ordinary tests must not launch Origin.
- Use explicit Origin execution only when a vetted queue is ready and the current step requires it.

## Current Known State Before Phase 1.5 Work

- Workspace copy: `workspace_data\LL_detection_copy_20260530`
- Stable backup: `F:\课题\LL\检测`
- Latest triage total: 1589 files
- AUTO_PROCESS: 18
- MANUAL_REVIEW: 737
- EXCLUDE_INVALID: 121
- DUPLICATE_SUPPRESSED: 58
- AUXILIARY_ONLY: 113
- DEFERRED_TYPE: 525
- REFERENCE_ONLY: 17
- Current queue: 18 EIS datasets
- Current no-Origin EIS processing: 18 success, 0 failure
- Traceability groups: 109
- Groups with existing Origin project/template files: 37
- Groups with queued files: 4
- Most recent full tests before Phase 1.5: `D:\Python\python.exe -m pytest` passed 75 tests with 2 openpyxl deprecation warnings.
- `deps-audit` and `validate` passed before Phase 1.5.

## Current Plan Status

1. Archived Phase 1.5 long instruction: completed.
2. Created active goal: completed.
3. Created heartbeat automation: completed.
4. Read Origin plotting skill and core CLI/process context: in progress.
5. Need next: baseline report, path safety audit, refreshed scan/triage report, bug radar.
6. Then: fix P0/P1 issues and add tests.
7. Then: build safe selected-data result folder with processed outputs and clearly labeled plot previews/screenshots.
8. Then: final audit, docs, validation, reviewer report, final summary.

## Running Subagents

The following read-only explorer subagents were started:

- `019e79bd-aca6-7271-87f3-70e37fbfeff0`: CLI/process/origin risk review.
- `019e79bd-d339-7961-a31a-c9c6b3b087f7`: safe promotion candidate analysis.

On resume, wait for these agents if still running, then close them after collecting useful results.

## Recommended Resume Commands

```powershell
cd "D:\Codex Project\科研数据处理\ResearchDataOriginPipeline"
D:\Python\python.exe -m pytest
D:\Python\python.exe run.py deps-audit
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py scan --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml
D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh
```

Do not run Origin unless explicitly processing a vetted Origin queue under the Phase 1.5 rules.
