# Script Layout Batch 3B Review

Date: 2026-06-03

Scope: review only for script directory README files and script-layout planning docs. No `git add`, no `git commit`, no file deletion, no file move, no `.py` script edit, no import edit, no source/config/test edit, no output edit, no Origin run, no validate/readiness/full pytest, and no plotting fix was performed.

Baseline:

- Batch 1 commit: `3625b7c`
- Batch 3A commit: `4cab88e`
- `scripts/regenerate_manual_review_filtered.py` was already moved to `scripts/reports/regenerate_manual_review_filtered.py` in Batch 3A.

## Candidate Files

| File | Current status | Purpose in Batch 3B |
| --- | --- | --- |
| `scripts/README.md` | modified | Top-level script directory policy: function-first, data-type second |
| `scripts/reports/README.md` | untracked | Report-generation helper directory scope |
| `scripts/maintenance/README.md` | tracked clean | Maintenance directory scope already present in HEAD |
| `scripts/one_off/README.md` | tracked clean | One-off directory scope already present in HEAD |
| `scripts/data_types/README.md` | untracked | Data-type-specific script boundary |
| `scripts/data_types/xps/README.md` | untracked | XPS-specific script boundary |
| `docs/SCRIPT_LAYOUT_PREFLIGHT.md` | untracked | Historical preflight audit and risk map before Batch 3A |
| `docs/SCRIPT_LAYOUT_BATCH_PLAN.md` | untracked | Script-layout batch plan and staging constraints |

This review document, `docs/SCRIPT_LAYOUT_BATCH3B_REVIEW.md`, is also suitable to include in the Batch 3B staging command if the user wants the review evidence committed with the directory docs.

## Commands Run

```powershell
git status --short
git status --short -- scripts docs/SCRIPT_LAYOUT_PREFLIGHT.md docs/SCRIPT_LAYOUT_BATCH_PLAN.md
git diff --stat -- scripts/README.md scripts/reports/README.md scripts/maintenance/README.md scripts/one_off/README.md scripts/data_types/README.md scripts/data_types/xps/README.md docs/SCRIPT_LAYOUT_PREFLIGHT.md docs/SCRIPT_LAYOUT_BATCH_PLAN.md
git diff --check -- scripts/README.md scripts/reports/README.md scripts/maintenance/README.md scripts/one_off/README.md scripts/data_types/README.md scripts/data_types/xps/README.md docs/SCRIPT_LAYOUT_PREFLIGHT.md docs/SCRIPT_LAYOUT_BATCH_PLAN.md
```

Additional read-only inspection:

- direct `Get-Content` reads of each candidate README
- direct content checks of `docs/SCRIPT_LAYOUT_PREFLIGHT.md` and `docs/SCRIPT_LAYOUT_BATCH_PLAN.md`
- read-only status/diff check for `scripts/build_xps_in_situ_20260506.py` and `scripts/data_types/xps/`

## Diff Evidence

`git diff --stat --` over the Batch 3B candidate list reports only the tracked top-level README change:

```text
 scripts/README.md | 10 +++++++---
 1 file changed, 7 insertions(+), 3 deletions(-)
```

The other candidate files are either untracked or tracked clean, so normal `git diff --stat` does not show their content before staging.

`git diff --check --` over the candidate path list passed with exit code 0. The only output was the expected line-ending warning for `scripts/README.md`; no whitespace-error or conflict-marker failure was reported.

## Content Review

`scripts/README.md`:

- describes script directory policy
- uses function-first, data-type-second organization
- restricts `scripts/data_types/<data_type>/` to scripts strongly bound to one instrument, data type, or raw format
- lists subdirectories only
- does not claim all scripts are fully organized

`scripts/reports/README.md`:

- defines reusable report-generation and index-refresh helpers
- separates one-time audit helpers and long-lived maintenance checks
- does not describe a feature implementation

`scripts/maintenance/README.md`:

- defines reusable maintenance scripts
- excludes one-off report generators, processing outputs, and result artifacts
- tracked clean; no new staging effect unless explicitly added with the rest

`scripts/one_off/README.md`:

- defines one-off migration/audit/report-generation helpers kept for traceability
- recommends documenting produced reports in indexes
- tracked clean; no new staging effect unless explicitly added with the rest

`scripts/data_types/README.md`:

- defines data-type-specific scripts narrowly
- explicitly keeps general maintenance, report, Origin, packaging, and migration helpers in functional directories

`scripts/data_types/xps/README.md`:

- defines XPS-specific scripts only when tied to XPS data or an XPS-only workflow
- does not approve staging the XPS `.py` script

`docs/SCRIPT_LAYOUT_PREFLIGHT.md`:

- records pre-Batch-3A script-layout status and risks
- is now partially historical because Batch 3A has already completed
- its earlier `regenerate_manual_review_filtered` uncertainty is superseded by `docs/SCRIPT_LAYOUT_BATCH3A_REVIEW.md` and commit `4cab88e`
- still useful as a preflight record because it explicitly warns not to handle XPS script drift in the same small batch

`docs/SCRIPT_LAYOUT_BATCH_PLAN.md`:

- records Batch 3A/3B/3C boundaries and verification commands
- now has a historical Batch 3A section because Batch 3A is complete
- Batch 3B and deferred-work rules remain relevant
- explicitly forbids Python scripts, source/config/output files, cache files, generated artifacts, and XPS script handling in Batch 3B

## Disallowed Content Review

No candidate README or planning doc was found to:

- promise new functionality
- claim an unverified plotting fix
- require bulk staging of `output/` or `output/reports/`
- say all scripts are already fully organized
- include actual `.py` implementation content
- ask Batch 3B to stage XPS in-situ `.py` scripts

The planning docs mention specific script paths because they are script-layout evidence and boundaries. Those references are acceptable for a planning/review commit as long as actual `.py` files are not staged in Batch 3B.

## Actual Script Changes

Actual `.py` script changes exist in the dirty working tree but are outside the Batch 3B candidate set:

- `M scripts/build_xps_in_situ_20260506.py`
- `?? scripts/data_types/xps/build_xps_in_situ_20260506.py`
- `?? scripts/maintenance/opju_exemplar_regression.py`
- `?? scripts/one_off/verify_jeol_epr_decode_against_exports.py`

These must not be staged in Batch 3B.

## XPS In-Situ Drift

XPS in-situ drift is present outside the Batch 3B candidate set:

- root script `scripts/build_xps_in_situ_20260506.py` has a functional/CLI diff
- untracked `scripts/data_types/xps/build_xps_in_situ_20260506.py` exists
- `scripts/data_types/xps/README.md` is only a directory boundary note and does not validate or approve the XPS `.py` script

Recommendation: keep XPS in-situ script handling out of Batch 3B. Review it later in a separate Batch 3C or XPS-specific preflight.

## Recommendation

Batch 3B is suitable for staging as a documentation-only commit if staging is done with explicit file paths.

Recommended `git add` command:

```powershell
git add -- scripts/README.md scripts/reports/README.md scripts/maintenance/README.md scripts/one_off/README.md scripts/data_types/README.md scripts/data_types/xps/README.md docs/SCRIPT_LAYOUT_PREFLIGHT.md docs/SCRIPT_LAYOUT_BATCH_PLAN.md docs/SCRIPT_LAYOUT_BATCH3B_REVIEW.md
```

Do not use `git add scripts/`, `git add scripts/data_types/`, `git add .`, or `git add -A`, because those would risk staging actual `.py` scripts and unrelated dirty paths.

Do not stage:

- `scripts/build_xps_in_situ_20260506.py`
- `scripts/data_types/xps/build_xps_in_situ_20260506.py`
- any other `.py` script
- `docs/indexes/scripts_index.md`
- `src/`, `config/`, `tests/`, `output/`, `outputs/`
- OPJU/TIF/PNG/XLSX/ZIP/large JSON artifacts
