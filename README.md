# ResearchDataOriginPipeline

Scientific characterization data pipeline for scanning, triage, processing, OriginPro plotting, `.opju` saving, 600 dpi `.tif` export, metadata, and review reports.

Formal entrypoints are `run.py` and `src/cli.py`. Helper scripts under `scripts/` are not replacement processing paths.

## Current Rules

- Raw data is read-only.
- Default output root is the workspace sibling folder `D:\Codex Project\科研数据处理\输出`.
- Every successful Origin job must save `.opju`, `.tif`, and a preview image.
- Output labels and Origin-facing workbook metadata must not contain Codex names, full local paths, or comments copied from source files.
- SEM, TEM, NMR, MS, and kinetics/reference folders are scan-only unless an explicit processor is added and tested.
- No PPT or kinetics processor is part of this project.
- High-risk scientific claims require manual review; the code must not infer mechanisms, valence, radical identity, phase assignment, or charge-transfer direction automatically.

## Main Commands

```powershell
D:\Python\python.exe run.py scan --input <data-root>
D:\Python\python.exe run.py triage --input <data-root> --explain --force-refresh
D:\Python\python.exe run.py process --input <data-root> --no-origin
D:\Python\python.exe run.py origin-batch --manifest <manifest.csv> --dry-run
D:\Python\python.exe run.py template-format-products --pairing <pairing-plan.json> --with-origin
D:\Python\python.exe run.py xrd-overlay --with-origin <required inputs>
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py readiness --no-desktop-review-xlsx
```

## Documentation

- Current status: `docs/CURRENT_STATUS.md`
- Command/module map: `docs/PROJECT_INDEX.md`
- Real data intake: `docs/REAL_DATA_INTAKE_GUIDE.md`
- Compatibility matrix: `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- Origin/template requirements: `docs/TEMPLATE_FORMAT_PRODUCTS.md`, `docs/ORIGIN_STYLE_ASSETS.md`
- Method cards: `docs/method_cards/`
