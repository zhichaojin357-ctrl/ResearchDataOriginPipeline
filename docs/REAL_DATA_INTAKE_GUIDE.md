# Real Data Intake Guide

## Rules

- Do not modify, move, delete, or rename raw source data.
- Do not write outputs into source-data folders or external template folders.
- Start with `scan` and `triage`.
- Do not process every `MANUAL_REVIEW` item in bulk.
- Use `reviewed-queue` or `auto-queue` dry-run plans before explicit processing.
- Keep scan-only entries scan-only until a tested processor exists.

## Recommended Flow

```powershell
D:\Python\python.exe run.py scan --input <data-root>
D:\Python\python.exe run.py triage --input <data-root> --explain --force-refresh
D:\Python\python.exe run.py auto-queue
D:\Python\python.exe run.py reviewed-queue --proposals <proposals.json> --write-template
D:\Python\python.exe run.py reviewed-queue --proposals <proposals.json> --decisions <decisions.csv> --dry-run
```

Only explicitly approved rows should enter processing. Use `--no-origin` first when validating a new queue.

## Manual Review

Manual-review rows usually indicate one or more of these conditions:

- parser failure or proprietary/binary source format;
- ambiguous folder/header evidence;
- missing required numeric columns;
- high-risk interpretation;
- duplicate or same-data uncertainty.

Manual review should decide whether to export a numeric table, keep the file scan-only, or approve a small no-Origin queue.

## Origin Export

Only run Origin export after processed CSV and metadata are verified. Successful exports must create:

- `.opju`
- 600 dpi `.tif`
- preview image
- metadata and report entries

OPJU-facing workbook names/comments should contain data-file names only, not full paths.
