# Origin Style Assets

## Project-Local Format Assets

The accepted Origin graph formats are stored inside the project:

```text
templates/origin_styles/
```

Current runtime assets:

- `templates/origin_styles/manifest.json`
- `templates/origin_styles/format_themes/*.oth`
- `templates/origin_styles/graph_templates/*.otpu`
- `templates/origin_styles/snapshots/*.json`
- `templates/origin_styles/data_snapshots/*.json`
- `templates/origin_styles/reference_opju/*.opju`
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

The `.oth` files are copied Origin graph formats saved from Origin's Copy Format payload. The `.otpu` files are saved graph templates for complex multi-layer graphs. The style JSON snapshots store readback values such as plot colours so newly added data plots can be styled without reopening the source OPJU. The `data_snapshots/*.json` files store the reviewed template graph's plotted datasets, layer/plot mapping, paired X/Y worksheet columns, and per-plot style readback. This is the audit trail that proves a template-data replay used data embedded in the OPJU rather than adjacent raw text files.

Runtime product generation creates a clean target graph from current processed data and applies the matching `.oth` asset. Project-local `reference_opju/*.opju` copies are retained only as recovery/extraction sources for inspecting reviewed examples; they are not used as the default data-replacement base for XRD products. This avoids carrying multi-layer template residue into current products while still keeping the external F-drive/source OPJU unnecessary after assets are harvested.

## Regeneration

Regenerate the project-local format assets from a reviewed accepted product run:

```powershell
D:\Python\python.exe run.py export-origin-style-assets --run-root "<output-root>\runs\<accepted-template-format-run>" --with-origin
```

To harvest one reviewed OPJU template directly:

```powershell
D:\Python\python.exe run.py export-origin-style-assets --template-opju "<template.opju>" --product-key XRD --data-type XRD --graph-page Graph4 --with-origin
```

To harvest a reviewed set of OPJU templates directly:

```powershell
D:\Python\python.exe run.py export-origin-style-assets --template-plan "output\runs\<run>\template_harvest_plan.json" --with-origin
```

`run.py export-origin-style-assets` first copies each accepted product OPJU or directly supplied template OPJU to a task-owned temporary working copy, then opens that copy in Origin. This avoids locking or modifying the user's reviewed template file. It saves a sanitized project-local OPJU copy, copies the selected graph format through Origin's Copy Format mechanism, saves the copied `Origin XML Style` payload as a project-local `.oth` file, attempts to save the selected graph page as a project-local `.otpu` graph template, and writes a `data_snapshots/<type>.json` template-data snapshot. Origin-native saves are performed through ASCII temporary paths and then copied back to the project asset directory, because LabTalk `save -t` can fail on non-ASCII output paths. If Origin refuses `save -t` for a graph page, the `.otpu` field is left empty; the project-local `reference_opju`, `.oth`, style snapshot, and data snapshot remain the authoritative self-contained asset set.

For the reviewed XRD Graph4 template, the data snapshot must contain five plotted datasets:

- Layer 1: `Book2_B`, `Book2_D`, `Book2_F`
- Layer 2: `Book2_H` standard-card sticks, paired with `Book2_G`
- Layer 3: `Book3_F`, paired with `Book3_E`

## Verification

Before claiming the asset path is self-contained, run `template-format-products --with-origin` with the project-local `templates/origin_styles` assets available. The expected simple-product metadata is:

- `template_format_plan.mode = saved_format_theme`
- `origin_processing.method = saved_format_theme_apply`
- `template_path = templates/origin_styles/format_themes/<type>.oth`

For XRD with standard-card templates, expected metadata is also:

- `template_format_plan.mode = saved_format_theme`
- `origin_processing.method = saved_format_theme_apply`
- `origin_processing.legend_policy.line_samples_removed = false`
- `origin_processing.legend_policy.entry_count = 4` for the reviewed BOBC/CuWO4 standard-card exemplar

For template-asset replay verification, run:

```powershell
D:\Python\python.exe run.py origin-style-asset-replay --template-plan "output\runs\<run>\template_harvest_plan.json" --output-dir "output\runs\<run>" --with-origin
```

This exports `source_template.png/.tif/.opju`, `project_asset.png/.tif`, a product-named `.opju` such as `BET.opju`, `side_by_side.png`, and `comparison.json` for each data type. `comparison.json` records the RMS and difference bounding box; a separate pixel-difference image is not written to product folders. A replay is accepted only when the source template export and the project-local asset export are pixel-identical (`rms = 0`, `exact_pixel_match = true`).
