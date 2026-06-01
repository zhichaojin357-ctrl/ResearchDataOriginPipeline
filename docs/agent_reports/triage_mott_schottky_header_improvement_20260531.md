# Mott-Schottky Triage Header Improvement

## Scope

This report records a safe recognition improvement for CHI-style Mott-Schottky exports. No real data processing or Origin export was run.

## Problem

- Many Mott-Schottky `.csv` files start with instrument metadata such as date, `Impedance - Potential`, instrument model, voltage range, frequency, and amplitude.
- The previous text reader treated the first line as the CSV header, so rows like `Nov. 26, 2025 21:24:18` became column names.
- Because the real header row was missed, the triage layer saw weak column evidence and left otherwise readable Mott-Schottky tables in `MANUAL_REVIEW`.

## Changes

- Text table reading now builds a small delimited grid and scores possible header rows.
- Normal text files scan only the first 10 rows for a header.
- CHI/instrument-metadata text files scan up to 30 rows so delayed headers such as `Potential/V, Z'/ohm, Z"/ohm, Z/ohm, Phase/deg` are found.
- Header scoring now rewards obvious summary-table headers (`metric`, `value`, `unit`) and penalizes numeric-looking headers, preventing BET summary tables from being reinterpreted as data-row headers.
- Mott-Schottky header scoring now treats `Potential/V` plus impedance/phase columns without frequency as Mott-Schottky evidence rather than EIS evidence.

## Safety

- No confidence thresholds were lowered.
- No `--include-ambiguous` behavior was enabled.
- No MANUAL_REVIEW batch processing was run.
- No no-Origin processing was run for newly recognized candidates.
- No Origin process was launched.
- XPS, EPR, XRD, SEM/TEM/NMR/MS, and reference-literature guardrails were not weakened.

## Current Triage Impact

After refreshing scan and triage:

- Total files: 1644
- `AUTO_PROCESS`: 188
- `MANUAL_REVIEW`: 618
- `EXCLUDE_INVALID`: 113
- `DUPLICATE_SUPPRESSED`: 66
- `AUXILIARY_ONLY`: 117
- `DEFERRED_TYPE`: 525
- `REFERENCE_ONLY`: 17
- Parser probe success: 530
- Parser probe fail: 35
- Parser probe skipped: 1079

Compared with the previous refreshed state in this turn:

- `AUTO_PROCESS`: 72 -> 188
- `MANUAL_REVIEW`: 723 -> 618
- Mott-Schottky decisions now include:
  - `AUTO_PROCESS`: 92
  - `MANUAL_REVIEW`: 153
  - `DUPLICATE_SUPPRESSED`: 46
  - `AUXILIARY_ONLY`: 16
  - `EXCLUDE_INVALID`: 1

The newly auto-recognized Mott-Schottky rows are table-recognition candidates only. They still require the existing no-Origin queue/process step before any processed CSV or figures are produced.

## Verification

- Targeted tests: `D:\Python\python.exe -m pytest -q tests\test_processor_behaviors.py tests\test_phase1_7_triage_recognition.py tests\test_phase1_2_mixed_triage.py`
  - 60 passed, 2 warnings, 3 subtests passed.
- Full tests: `D:\Python\python.exe -m pytest`
  - 147 passed, 2 warnings.
- `D:\Python\python.exe run.py validate`
  - exit 0.
- `D:\Python\python.exe run.py deps-audit`
  - exit 0.
- `D:\Python\python.exe run.py scan --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml`
  - exit 0.
- `D:\Python\python.exe run.py triage --input workspace_data\LL_detection_copy_20260530 --config config/default.yaml --explain --force-refresh`
  - exit 0.
- Residual process check:
  - No Excel or Origin process was left by this work.

## Remaining Work

- The 153 remaining Mott-Schottky MANUAL_REVIEW items are mostly unsupported binary/vendor files or lower-confidence cases and should not be auto-processed without additional evidence.
- BET remains parser-improved but not formally processed or plotted.
- Formal processing of newly recognized Mott-Schottky candidates should be done in a later explicit queue step with no-Origin first, then Origin only after preview/QC passes.
