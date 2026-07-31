# Template-format product executor

The formal entrypoint is `run.py template-format-products`. Current processed CSV data are imported into a clean Origin project, then the accepted project-local `.oth` format theme is applied. Existing `.otpu` files are harvest-only records and are never runtime fallbacks; an asset with only `.otpu` and no readable `.oth` is blocked. Product generation must not reuse workbook data from a template OPJU.

Use the self-contained production mode for release verification:

```powershell
python run.py template-format-products --pairing "<pairing-plan.json>" --asset-only --compact-output --with-origin
```

`--asset-only` is mutually exclusive with `--exemplar-driven`. It disables F-drive/XPS template discovery, external-reference preview export, pairing-OPJU execution, and `opju_template_base`. A manifest-declared project-local `reference_opju` may still be copied into the isolated runtime and opened only to export an independent reference preview and read a style snapshot. That copy is never the product base, never supplies product data, and is never saved; the source hash is checked before and after the read-only evidence step. Each metadata file records the selected project asset, `template_format_plan.mode`, `origin_processing.method`, `asset_only`, and `external_template_dependency`.

The default command remains backward compatible and gives an explicitly selected external reference priority over the project-local reference OPJU. `--exemplar-driven` is a diagnostic/review mode that deliberately opens the pairing-plan OPJU and is not evidence of external-template independence. A generated product preview is never copied into the reference-preview slot; acceptance requires two independent files.

For the formal single-spectrum EIS product, the CSV and graph retain every parsed measured Nyquist point in source order. Automatic cleaning/exclusion, semicircle-branch selection, equivalent-circuit fitting, fit columns, and fit sidecars are not run. A future diagnostic fit requires an explicit opt-in and cannot silently become a formal product.

Acceptance covers all 12 product types. It requires processed data, `.opju`, a native Origin 600 dpi `.tif`, an independent reference PNG, a generated PNG preview, metadata, report, plot-count/readback checks, and manual-review boundaries. TIFF verification reads `page.width` and `page.height` from the reopened final graph and checks both raster pixel dimensions and TIFF DPI tags; retagging or resizing a lower-resolution export is not accepted. Saved-theme conformance is computed field by field with the real style-snapshot comparator, not a hard-coded pass. One-to-one style claims additionally require an independent-content `origin-style-asset-replay` result with `rms=0` and `exact_pixel_match=true`; a byte-identical reference-OPJU self-replay is deterministic-export evidence only and cannot satisfy this requirement.
