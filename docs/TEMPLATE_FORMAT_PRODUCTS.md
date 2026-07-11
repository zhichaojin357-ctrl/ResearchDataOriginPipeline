# Template-format product executor

The formal entrypoint is `run.py template-format-products`. Current processed CSV data are imported into a clean Origin project, then the accepted project-local `.oth` format theme is applied. A manifest-approved `.otpu` is the only graph-template fallback. Product generation must not reuse workbook data from a template OPJU.

Use the self-contained production mode for release verification:

```powershell
python run.py template-format-products --pairing "<pairing-plan.json>" --asset-only --compact-output --with-origin
```

`--asset-only` is mutually exclusive with `--exemplar-driven`. It disables F-drive/XPS template discovery, external-reference preview export, selected-OPJU execution, and `opju_template_base`. Each metadata file records the selected project asset, `template_format_plan.mode`, `origin_processing.method`, `asset_only`, and `external_template_dependency`.

The default command remains backward compatible and may export external reference previews for comparison. `--exemplar-driven` is a diagnostic/review mode that deliberately opens the pairing-plan OPJU and is not evidence of external-template independence.

Acceptance covers all 12 product types. It requires processed data, `.opju`, 600 dpi `.tif`, PNG preview, metadata, report, plot-count/readback checks, and manual-review boundaries. One-to-one style claims additionally require a successful `origin-style-asset-replay` result with `rms=0` and `exact_pixel_match=true`.
