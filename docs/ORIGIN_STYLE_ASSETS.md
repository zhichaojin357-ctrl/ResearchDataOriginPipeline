# Origin Style Assets

## Project-Local Format Assets

The registered Origin graph formats are stored inside the project:

```text
templates/origin_styles/
```

Current runtime assets and evidence:

- `templates/origin_styles/manifest.json`
- `templates/origin_styles/format_themes/*.oth`
- `templates/origin_styles/snapshots/*.json`
- `templates/origin_styles/data_snapshots/*.json`
- `templates/origin_styles/reference_opju/*.opju`
- `templates/origin_styles/previews/*.png`

`templates/origin_styles/graph_templates/*.otpu` are retained only as quarantined harvest records. The current batch-derived files have not passed independent visual acceptance and are not runtime assets.

The manifest has one integrity-registered `.oth` format theme for each plotted
type. Here, manifest status and hash integrity do not by themselves mean that a
new-data product has passed independent visual acceptance:

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

The `.oth` files are copied Origin graph formats saved from Origin's Copy Format payload. The style JSON snapshots store readback values such as plot colours so newly added data plots can be styled without reopening the source OPJU. The `data_snapshots/*.json` files store the reviewed template graph's plotted datasets, layer/plot mapping, paired X/Y worksheet columns, and per-plot style readback. This is the audit trail that proves a template-data replay used data embedded in the OPJU rather than adjacent raw text files.

Runtime product generation creates a clean target graph from current processed data and applies the matching `.oth` asset. A project-local `.otpu` cannot satisfy style-asset integrity, cannot substitute for `format_theme`, and is never dispatched by the formal executor. Project-local `reference_opju/*.opju` copies are retained for harvest recovery, replay, and independent visual/style evidence. In `--asset-only` mode the declared reference OPJU is copied to an isolated temporary path and opened read-only only long enough to export its reference preview and read its graph style; it is never used as the product base, never contributes workbook data, and is never saved. The original asset hash is checked before and after this step. The external F-drive/source OPJU is therefore unnecessary after assets are harvested.

The project-local reference preview must be freshly exported from that independent OPJU copy. A generated product preview cannot be copied or reused as its own reference. Outside `--asset-only`, an explicitly selected external reference still has priority.

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

`run.py export-origin-style-assets` first copies each accepted product OPJU or directly supplied template OPJU to a task-owned temporary working copy, then opens that copy in Origin. This avoids locking or modifying the user's reviewed template file. It saves a sanitized project-local OPJU copy, copies the selected graph format through Origin's Copy Format mechanism, saves the copied `Origin XML Style` payload as a project-local `.oth` file, may save the selected graph page as a project-local `.otpu` harvest artifact, and writes a `data_snapshots/<type>.json` template-data snapshot. Origin-native saves are performed through ASCII temporary paths and then copied back to the project asset directory, because LabTalk `save -t` can fail on non-ASCII output paths. Whether `.otpu` export succeeds or not has no effect on runtime readiness: the project-local `reference_opju`, accepted `.oth`, style snapshot, and data snapshot remain the authoritative self-contained asset set.

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
- `origin_status.external_reference_preview.reference_kind = project_local_reference_opju`
- `origin_status.external_reference_preview.read_only_runtime_copy = true`
- `origin_status.external_reference_preview.used_as_product_base = false`

Every replay and formal product TIFF is exported natively by Origin at 600 dpi. Verification reads the final graph's dynamic `page.width` and `page.height` and checks the expected raster pixels, effective physical DPI, and TIFF DPI tags without rewriting or resampling the file.

Origin's native TIFF writer also stores the current project identity in an IPTC
field. The export path therefore saves and reopens the final OPJU, reads the
target page dimensions, runs `doc -rn` followed by `doc -s`, verifies that `%X`
is empty and `%G` is `UNTITLED`, reactivates the graph, and only then exports the
TIFF. A controlled before/after comparison showed identical decoded pixels; the
operation removes the temporary path identity without restyling or re-encoding
the graph.

For XRD with standard-card templates, expected metadata is also:

- `template_format_plan.mode = saved_format_theme`
- `origin_processing.method = saved_format_theme_apply`
- `origin_processing.legend_policy.line_samples_removed = false`
- `origin_processing.legend_policy.entry_count = 4` for the reviewed BOBC/CuWO4 standard-card exemplar

For template-asset replay verification, run:

```powershell
python run.py origin-style-asset-replay --template-plan "<output-root>\runs\<run>\template_harvest_plan.json" --output-dir "<output-root>\runs\<run>" --with-origin
```

This exports `source_template.png/.tif/.opju`, `project_asset.png/.tif`, a product-named `.opju` such as `BET.opju`, `side_by_side.png`, and `comparison.json` for each data type. Replay is a verification operation and may read the reviewed source OPJU. `comparison.json` records source/asset hashes, RMS, and the difference bounding box. Pixel equality can count as an independent match only when the compared OPJU contents are different. If the source and project-local OPJU hashes are identical, an exact result is classified as `reference_opju_self_replay`; it proves deterministic Origin export only and does not validate the `.oth` theme on a newly constructed graph. Product acceptance separately requires plot-count, style-readback, artifact, independent-reference, and visual checks.

The 2026-07-31 evidence contains 12 exact decoded-pixel self-replays because
each declared source OPJU and project-local reference OPJU had identical
content. They are now reported as 12 inconclusive self-replays and zero
independent matches. The separately generated `.oth` products remain blocked
by the independent-reference gate.

Do not infer from a correct reference OPJU that it is a safe generic workbook
base. A controlled XRD replacement trial preserved most style fields but mapped
the current columns incorrectly, producing flat curves and overlapping labels.
Reference OPJUs therefore remain independent evidence unless a future
type-specific manifest and replacement contract proves complete workbook and
plot mapping for that exact data shape.
