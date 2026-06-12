# Origin Style Assets

## Project-Local Format Assets

The accepted Origin graph formats are stored inside the project:

```text
templates/origin_styles/
```

Current runtime assets:

- `templates/origin_styles/manifest.json`
- `templates/origin_styles/format_themes/*.oth`
- `templates/origin_styles/previews/*.png`

The manifest has one accepted `.oth` format theme for each plotted type:

- BET
- XPS_in_situ
- XPS_non_in_situ
- XRD
- EPR
- EIS
- Raman
- UV-vis DRS / Tauc
- PL
- photocurrent
- FTIR

## Runtime Boundary

The `.oth` files are copied Origin graph formats. Product runs create a clean target graph from current processed data, apply the matching `.oth` format theme, then save a new `.opju` and export `.tif`/preview `.png`.

Runtime product generation must not use a template OPJU as a data-replacement base. OPJU exemplars are only historical extraction sources and are not required after the `.oth` assets exist.

## Regeneration

Regenerate the project-local format assets from a reviewed accepted product run:

```powershell
D:\Python\python.exe run.py export-origin-style-assets --run-root "<output-root>\runs\<accepted-template-format-run>" --with-origin
```

`run.py export-origin-style-assets` opens each accepted product OPJU, copies the selected graph format through Origin's Copy Format mechanism, and saves the copied `Origin XML Style` payload as a project-local `.oth` file.

## Verification

Before claiming the asset path is self-contained, run `template-format-products --with-origin` with only `templates/origin_styles/format_themes` available. The expected product metadata is:

- `template_format_plan.mode = saved_format_theme`
- `origin_processing.method = saved_format_theme_apply`
- `template_path = templates/origin_styles/format_themes/<type>.oth`
