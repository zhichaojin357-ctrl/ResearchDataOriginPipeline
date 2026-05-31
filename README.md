# ResearchDataOriginPipeline

Current checkpoint: Phase 1.8 reviewed-queue safety gate and manual-review output.

Latest locked Origin package: `output/phase1_6_origin_results_20260531_041538`

Phase 1.6 produced 167 real Origin result sets. Phase 1.7 added preview review, manifest dry-run, Origin isolation proof, and triage-recognition reports. Phase 1.8 adds a user-reviewed queue gate and the post-AI manual review list; it does not process new real data and does not launch Origin.

## Current Scope

- Phase 1.6 Origin exports completed: EIS 22, photocurrent 3, Raman 30, Mott-Schottky 90, EPR 13, XPS 9.
- Origin visual QC: 167/167 `QC_PASS`.
- XPS outputs are raw spectrum plots only; no automatic valence assignment.
- SEM, TEM, NMR, and MS remain scan-only/deferred.
- Kinetics/reference folders remain `reference_literature`.
- PPT generation and kinetics processors remain forbidden.

## Phase 1.8 Reviewed Queue Workflow

Generate a decision template from the Phase 1.7 review-only proposals:

```powershell
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --write-template
```

Edit:

```text
output\reports\phase1_8_review_decisions_template.csv
```

CSV rules:

- Do not edit traceability columns such as `proposal_id`, `relative_path`, `source_hash`, `proposed_data_type`, `proposed_processor`, `risk_level`, and `reason`.
- Empty `user_decision` means skip; it will not enter a queue.
- The only approval value is `approve_for_no_origin_queue`.
- Approved rows must include `approved_by` and `approval_date`.
- High-risk rows must include `high_risk_ack=true`.
- Folder/header conflict rows must include `folder_header_conflict_ack=true`.
- Use UTF-8 when saving the CSV; do not let spreadsheet software rename columns or damage paths.

Run the dry-run planner:

```powershell
D:\Python\python.exe run.py reviewed-queue --proposals output\reports\phase1_7_new_override_proposals_after_optimization.json --decisions output\reports\phase1_8_review_decisions_template.csv --dry-run
```

Outputs:

- `output/reports/phase1_8_review_decisions_template.csv`
- `output/reports/phase1_8_reviewed_queue_plan.json`
- `output/reports/phase1_8_reviewed_queue_plan.md`
- `docs/agent_reports/phase1_8_reviewed_queue_report.md`

The planner validates path safety, current hash, current triage state, Phase 1.6 duplicate/processed status, required approvals, and high-risk acknowledgement. It never launches Origin and never calls `process`.

## Manual Review After AI-Assisted Recognition

After code-rule optimization and AI-assisted semantic review of the current manifest, the files still needing manual review are listed here:

- CSV: `output/reports/phase1_8_manual_review_required_after_ai.csv`
- Markdown: `output/reports/phase1_8_manual_review_required_after_ai.md`

Current counts:

- 538 files still require manual review after exclusions.
- 18 are classifiable review-only proposals that need user approval before a future no-Origin queue.
- 520 can be context-classified by folder/name/type hints but remain unprocessable safely because parser probing did not succeed.
- 151 MANUAL_REVIEW items were excluded from this user-review list because they are already represented in Phase 1.6 results.
- 53 MANUAL_REVIEW items were excluded because they are duplicate-grouped.

## Phase 1.7 Review Outputs

- Preview review checklist: `output/reports/phase1_7_origin_preview_review_checklist.csv`
- Preview gallery: `output/review_dashboard/phase1_7_preview_gallery.md`
- Gallery by type: `output/review_dashboard/phase1_7_preview_gallery_by_type.md`
- High-priority manual review: `output/reports/phase1_7_high_priority_manual_review.md`
- Manual override decision table: `output/reports/phase1_7_manual_override_decision_table.csv`

The preview checklist is for visual acceptance of the 167 completed Phase 1.6 figures. It is not approval to process new files.

## Manifest Runner

Dry-run is the default:

```powershell
D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run
D:\Python\python.exe run.py origin-batch --manifest output\phase1_6_origin_results_20260531_041538\index.csv --dry-run --only-type XPS
```

The runner reads the package manifest, verifies paths and hashes, skips completed outputs, writes a run plan, and does not launch Origin.

## Why Remaining MANUAL_REVIEW Is Not Processed In Bulk

The latest triage still has 742 `MANUAL_REVIEW` items. Only 18 became review-only proposals after optimization; no new safe promotion candidates were created. Many remaining items involve parser failures, proprietary/binary formats, duplicate ambiguity, folder/header conflicts, or scientific context. Do not use global `--include-ambiguous`.

## Recommended Validation Commands

```powershell
D:\Python\python.exe -m pytest
D:\Python\python.exe run.py deps-audit
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py scan --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml
D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh
```

## Data Safety

- Workspace copy: `workspace_data/LL_detection_copy_20260530`
- Stable backup reference: `F:\课题\LL\检测`
- Do not write into workspace source folders or the F-drive backup.
- Do not batch-process all `MANUAL_REVIEW`.
- Do not auto-apply override proposals.
