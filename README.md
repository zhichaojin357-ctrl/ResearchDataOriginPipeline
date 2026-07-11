# ResearchDataOriginPipeline

Scientific characterization data pipeline for scanning, triage, processing, OriginPro plotting, `.opju` saving, 600 dpi `.tif` export, metadata, and review reports.

Formal entrypoints are `run.py` and `src/cli.py`. Helper scripts under `scripts/` are not replacement processing paths.

## Current Rules

- Raw data is read-only.
- Default output root is the configured sibling folder `../输出`; override it with `config/local.yaml`, `RESEARCH_PIPELINE_OUTPUT_ROOT` (or the compatibility name `RESEARCHDATAORIGINPIPELINE_OUTPUT_ROOT`), or `--output-root`.
- Every successful Origin job must save `.opju`, `.tif`, and a preview image.
- Output labels and Origin-facing workbook metadata must not contain Codex names, full local paths, or comments copied from source files.
- SEM, TEM, NMR, MS, and kinetics/reference folders are scan-only unless an explicit processor is added and tested.
- No PPT or kinetics processor is part of this project.
- High-risk scientific claims require manual review; the code must not infer mechanisms, valence, radical identity, phase assignment, or charge-transfer direction automatically.

## Main Commands

```powershell
python run.py scan --input <data-root>
python run.py triage --input <data-root> --explain --force-refresh
python run.py process --input <data-root> --no-origin
python run.py origin-batch --manifest <manifest.csv> --dry-run
python run.py template-format-products --pairing <pairing-plan.json> --with-origin
python run.py template-format-products --pairing <pairing-plan.json> --asset-only --with-origin
python run.py origin-style-asset-replay --template-plan <template-plan.json> --output-dir <run-dir> --with-origin
python run.py xrd-overlay --with-origin <required inputs>
python run.py validate
python run.py readiness --no-desktop-review-xlsx
```

`--asset-only` is the formal proof path for external-template independence. It uses only `templates/origin_styles`, does not scan external OPJU roots, does not export an external reference preview, and records `asset_only=true` plus `external_template_dependency=false` in each product metadata file. Harvest and replay commands may use reviewed source OPJU files; product generation does not.

## Documentation

- Current status: `docs/CURRENT_STATUS.md`
- Command/module map: `docs/PROJECT_INDEX.md`
- Real data intake: `docs/REAL_DATA_INTAKE_GUIDE.md`
- Compatibility matrix: `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- Origin/template requirements: `docs/TEMPLATE_FORMAT_PRODUCTS.md`, `docs/ORIGIN_STYLE_ASSETS.md`
- Method cards: `docs/method_cards/`
