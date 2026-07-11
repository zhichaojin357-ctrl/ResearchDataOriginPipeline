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
- Mott-Schottky

`manifest.json` uses schema v2. Every referenced project-local file has a SHA-256 digest, byte size, and asset kind. Each product entry also records the expected layer/plot counts and harvest provenance. The reader remains compatible with schema v1, while `run.py validate` performs strict hash and structure checks for schema v2.

## Runtime Boundary

The `.oth` files are copied Origin graph formats saved from Origin's Copy Format payload. The `.otpu` files are saved graph templates for complex multi-layer graphs. The style JSON snapshots store readback values such as plot colours so newly added data plots can be styled without reopening the source OPJU. The `data_snapshots/*.json` files store the reviewed template graph's plotted datasets, layer/plot mapping, paired X/Y worksheet columns, and per-plot style readback. This is the audit trail that proves a template-data replay used data embedded in the OPJU rather than adjacent raw text files.

Runtime product generation creates a clean target graph from current processed data and applies the matching `.oth` asset. A project-local `.otpu` may be used only as an explicit graph-template fallback. Project-local `reference_opju/*.opju` copies are retained for harvest recovery and pixel replay; they are not opened by formal `--asset-only` product generation. The external F-drive/source OPJU is therefore unnecessary after assets are harvested.

## Regeneration

Regenerate the project-local format assets from a reviewed accepted product run:

```powershell
python run.py export-origin-style-assets --run-root "<output-root>\runs\<accepted-template-format-run>" --with-origin
```

To harvest one reviewed OPJU template directly:

```powershell
python run.py export-origin-style-assets --template-opju "<template.opju>" --product-key XRD --data-type XRD --graph-page Graph4 --with-origin
```

To harvest a reviewed set of OPJU templates directly:

```powershell
python run.py export-origin-style-assets --template-plan "<output-root>\runs\<run>\template_harvest_plan.json" --with-origin
```

`run.py export-origin-style-assets` first copies each accepted product OPJU or directly supplied template OPJU to a task-owned temporary working copy, then opens that copy in Origin. This avoids locking or modifying the user's reviewed template file. It saves a sanitized project-local OPJU copy, copies the selected graph format through Origin's Copy Format mechanism, saves the copied `Origin XML Style` payload as a project-local `.oth` file, attempts to save the selected graph page as a project-local `.otpu` graph template, and writes a `data_snapshots/<type>.json` template-data snapshot. Origin-native saves are performed through ASCII temporary paths and then copied back to the project asset directory, because LabTalk `save -t` can fail on non-ASCII output paths. If Origin refuses `save -t` for a graph page, the `.otpu` field is left empty; the project-local `reference_opju`, `.oth`, style snapshot, and data snapshot remain the authoritative self-contained asset set.

For the reviewed XRD Graph4 template, the data snapshot must contain five plotted datasets:

- Layer 1: `Book2_B`, `Book2_D`, `Book2_F`
- Layer 2: `Book2_H` standard-card sticks, paired with `Book2_G`
- Layer 3: `Book3_F`, paired with `Book3_E`

## Verification

Before claiming the asset path is self-contained, run:

```powershell
python run.py template-format-products --pairing "<pairing-plan.json>" --asset-only --compact-output --with-origin
```

The expected metadata is:

- `asset_only = true`
- `external_template_dependency = false`
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
python run.py origin-style-asset-replay --template-plan "<output-root>\runs\<run>\template_harvest_plan.json" --output-dir "<output-root>\runs\<run>" --with-origin
```

This exports `source_template.png/.tif/.opju`, `project_asset.png/.tif`, a product-named `.opju` such as `BET.opju`, `side_by_side.png`, and `comparison.json` for each data type. Replay is a verification operation and may read the reviewed source OPJU. `comparison.json` records RMS and the difference bounding box. A replay is accepted only when source and project-local asset exports are pixel-identical (`rms = 0`, `exact_pixel_match = true`). Product plots use current data, so their pixels are expected to differ from a template that contains different data; their acceptance additionally requires plot-count, style-readback, artifact, and visual checks.
