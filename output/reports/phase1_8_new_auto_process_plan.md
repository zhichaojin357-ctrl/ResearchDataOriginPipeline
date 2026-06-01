# Phase 1.8 New AUTO_PROCESS Queue Plan

- Created at: 2026-05-31T20:54:31
- Source queue: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\reports\processing_queue.json`
- Candidate queue: `D:\Codex Project\科研数据处理\ResearchDataOriginPipeline\output\reports\phase1_8_new_auto_process_queue.json`
- Source queue items: 188
- Accepted new candidates: 105
- Skipped: 83
- Blocked: 0
- Phase 1.6 processed hashes: 167
- Will run process: false
- Will launch Origin: false

## Accepted By Type

| data_type | count |
|---|---:|
| EPR | 44 |
| Mott-Schottky | 32 |
| EIS | 24 |
| photocurrent | 5 |

## Skipped / Blocked Reasons

| status | count |
|---|---:|
| SKIPPED_PHASE1_6_ALREADY_PROCESSED | 83 |

## Policy

- This planner is dry-run only.
- It does not call `process`.
- It does not launch Origin.
- It excludes source hashes already present in the Phase 1.6 Origin package.
- The resulting queue is for a future explicit no-Origin run after review.
