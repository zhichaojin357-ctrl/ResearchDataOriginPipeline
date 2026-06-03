# Tracked Output Reports Goal Summary

日期：2026-06-03

## 1. Starting Dirty Counts

| item | count |
|---|---:|
| total dirty at GOAL start | 277 |
| `output/reports` dirty at GOAL start | 194 |
| staged at GOAL start | 0 |

## 2. Policy Decision

Policy decision:

- Keep `output/reports` visible for Markdown and selected JSON/CSV evidence until the user makes a wider report policy decision.
- Do not batch untrack JSON, CSV, or Markdown reports in this GOAL.
- Use narrow `.gitignore` rules for obvious generated report artifacts.
- Execute only one pilot `git rm --cached` batch for tracked generated XLSX report artifacts.

## 3. Keep Tracked Summary

Keep tracked for now:

- active/baseline reports such as README, processing, readiness, validation, dependency, inventory, source hash, traceability, and classification reports;
- human-readable Markdown reports;
- JSON/CSV reports that may still act as evidence;
- historical phase reports until user confirms a broader untrack/restore policy.

## 4. Untrack Candidate Summary

Pilot untrack candidates:

- `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`
- `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- `output/reports/phase1_9_manual_review_required_final.xlsx`

Reason:

- generated XLSX report artifacts;
- not protected locked/canonical/release-freeze paths;
- local files existed before untrack and remained after untrack;
- future XLSX report artifacts are covered by `output/reports/*.xlsx`.

## 5. User Decision Required Summary

Still requires user decision:

- tracked modified JSON/MD baseline reports;
- tracked modified phase reports;
- generated JSON and CSV reports;
- Markdown reports under `output/reports`;
- whether current status should move fully to `docs/` and leave `output/reports` untracked.

## 6. `.gitignore`

Modified `.gitignore`: yes.

Added narrow generated report rules:

```gitignore
output/reports/PHASE1_*_HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION.json
output/reports/phase1_13_pip_*.txt
output/reports/*_temp_*_deleted_items_*.json
```

No broad rules were added for:

- `output/reports/*.md`
- all `output/reports/*.json`
- all `output/reports/*.csv`
- `output/`
- `output/reports/`

## 7. `git rm --cached`

Executed `git rm --cached`: yes.

Paths:

```text
output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx
output/reports/phase1_8_manual_review_required_filtered.xlsx
output/reports/phase1_9_manual_review_required_final.xlsx
```

Category and count:

- generated XLSX report artifacts: 3.

## 8. Local File Preservation

Local files retained: yes.

Post-untrack local checks:

| path | local file exists | tracked after untrack |
|---|---:|---:|
| `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx` | yes | no |
| `output/reports/phase1_8_manual_review_required_filtered.xlsx` | yes | no |
| `output/reports/phase1_9_manual_review_required_final.xlsx` | yes | no |

## 9. Safety Statements

- Deleted local output files: no.
- Moved local output files: no.
- Cleaned `output/` or `outputs/`: no.
- Ran Origin: no.
- Processed real data: no.
- Ran process / triage / validate / readiness commands that refresh output: no.
- Generated OPJU/TIF/PNG/PDF/XLSX/ZIP/large JSON: no.
- Staged/committed output file content changes: no.
- Staged/committed output index removals: yes, only the 3 explicit XLSX paths above.

## 10. End Dirty Counts

Expected post-commit counts after the pilot untrack commit:

| item | count |
|---|---:|
| total dirty | 253 |
| `output/reports` dirty | 170 |
| `output/outputs` dirty | 173 |
| staged | 0 |

Reason:

- narrow `.gitignore` rules hide generated handoff JSON, pip TXT, and temp deleted-items JSON;
- the XLSX pilot removes one tracked modified XLSX from visible dirty status after commit;
- the two other XLSX files were tracked but clean, so untracking them does not reduce dirty count beyond keeping future changes ignored.

## 11. Next Recommendation

Recommended next GOAL:

```text
GOAL: Output Reports JSON/Markdown Policy Decision
```

Minimum scope:

- decide whether generated JSON/CSV reports should remain visible or be ignored/untracked;
- decide whether Markdown reports under `output/reports` remain repo history or move to `docs/`;
- do not batch process without explicit user confirmation.
