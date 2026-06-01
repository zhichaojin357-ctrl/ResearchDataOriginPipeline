# BET Standardization Gap Report

Generated: 2026-05-31

## Summary

The BET folder has existing legacy processed outputs and Origin PNG previews, but BET is not yet part of the standardized Phase 1.6 result package and is not in the current Phase 1.8 AUTO_PROCESS queue.

## Evidence

- Workspace BET source folder exists: `workspace_data\LL_detection_copy_20260530\BET`
- Workspace BET file count: 42
- Workspace suffix counts:
  - `.db3`: 9
  - `.db3-journal`: 9
  - `.opju`: 2
  - `.pdf`: 8
  - `.smp`: 6
  - `.xls`: 8
- Current triage decisions for BET-related items:
  - `AUXILIARY_ONLY`: 10
  - `MANUAL_REVIEW`: 23
  - `EXCLUDE_INVALID`: 9
- Parser status for BET-related items:
  - `skipped`: 34
  - `fail`: 8
- The `.xls` BET exports currently fail triage probing with: `legacy .xls requires xlrd or explicit Excel COM processing`.
- Locked Phase 1.6 result package row count: 167
- Locked Phase 1.6 BET rows: 0
- Current Phase 1.8 AUTO_PROCESS queue rows: 188
- Current Phase 1.8 AUTO_PROCESS BET rows: 0

## Existing Legacy Outputs

Existing BET outputs under `D:\Codex Project\科研数据处理\数据\26.5.29\BET` include:

- Final legacy OPJU: `D:\Codex Project\科研数据处理\数据\26.5.29\BET\BET_N2_isotherm_and_pore_distribution_graph4_pointline_20260529_214645.opju`
- Isotherm PNG: `D:\Codex Project\科研数据处理\数据\26.5.29\BET\processed_origin\BET_N2_Isotherm_graph4_pointline_20260529_214645.png`
- Pore distribution PNG: `D:\Codex Project\科研数据处理\数据\26.5.29\BET\processed_origin\BET_Pore_Distribution_graph4_pointline_20260529_214645.png`
- Intermediate TSV/CSV files in `D:\Codex Project\科研数据处理\数据\26.5.29\BET\processed_origin`

These files should be treated as preserved legacy outputs, not as standardized Phase 1.6 package entries.

## Current Interpretation

BET is supported by the processor registry and method card, but current safe triage keeps real BET files in manual review because the source files are legacy `.xls`, `.smp`, `.db3`, `.pdf`, and existing `.opju` artifacts. The `.xls` tables require either `xlrd` or explicit hidden Excel COM handling. The current triage path intentionally does not use the Excel COM fallback.

## Recommended Next Steps

1. Keep current BET files out of automatic processing until the `.xls` export structure is verified.
2. Add a future explicit BET normalization step that reads the eight `.xls` files through the existing hidden Excel COM fallback or a reviewed dependency path.
3. Generate standardized no-Origin BET outputs first: processed CSV, metadata, and PNG preview.
4. Only after no-Origin QC, generate standardized OPJU/TIF/PNG outputs using the Origin plotting guardrails.
5. Preserve the legacy `D:\Codex Project\科研数据处理\数据\26.5.29\BET` outputs as reference material.

## Safety

No raw data was modified. No F-drive backup was touched. No Origin export was run for this report.
