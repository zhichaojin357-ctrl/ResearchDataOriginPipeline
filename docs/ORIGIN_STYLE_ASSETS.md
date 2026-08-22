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

Runtime eligibility is resolved from the current manifest, binding contract,
validation plan, validation evidence, and file-integrity records. BET, EIS,
EPR, PL, photocurrent, XRD with a standard card, and the fixed nine-curve XRD
no-card layout have individually regenerated, independently validated `.otpu`
runtime assets. The XRD no-card product also has a separately validated
adaptive `.oth`+JSON route for other curve counts. Other historical
batch-derived `.otpu` files remain quarantined harvest records and are not
runtime fallbacks.

The remaining plotted types continue to use their registered `.oth` compatibility
assets until an individual `.otpu` has passed the same fresh-project, same-data,
save/reopen, native-600-dpi, exact-pixel, axis-title, and manual-preview gates.
Manifest status or hash integrity alone never constitutes visual acceptance.

`manifest.json` uses schema v2. Every referenced project-local file has a SHA-256 digest, byte size, and asset kind. Each product entry also records the expected layer/plot counts and harvest provenance. The reader remains compatible with schema v1, while `run.py validate` performs strict hash and structure checks for schema v2.

## Runtime Boundary

The `.oth` files are copied Origin graph formats saved from Origin's Copy Format payload. The style JSON snapshots store readback values such as plot colours so newly added data plots can be styled without reopening the source OPJU. The `data_snapshots/*.json` files store the reviewed template graph's plotted datasets, layer/plot mapping, paired X/Y worksheet columns, and per-plot style readback. This is the audit trail that proves a template-data replay used data embedded in the OPJU rather than adjacent raw text files.

Runtime product generation always starts from current processed data. The
formal executor dispatches an accepted `.otpu` only when the current manifest
and validator resolve its complete binding/evidence package; otherwise it uses
the registered `.oth` compatibility route or blocks. EIS, EPR, and PL additionally
apply their manifest-bound `.oth` and style snapshot after the `.otpu`, because
their reviewed colours, visibility state, rich-text axis titles, and object
layout require all three assets. EPR then restores the current-data X range and
updates the three reviewed `DL1`/`DL2`/`DL3` text objects with the current sample
labels. Project-local `reference_opju/*.opju` copies are retained for recovery
and independent visual/style evidence, never as routine product bases or
workbook data sources. Normal accepted `.otpu` execution does not load a
reference OPJU.

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

`run.py export-origin-style-assets` first copies each accepted product OPJU or directly supplied template OPJU to a task-owned temporary working copy, then opens that copy in Origin. This avoids locking or modifying the user's reviewed template file. It saves a sanitized project-local OPJU copy, copies the selected graph format through Origin's Copy Format mechanism, saves the copied `Origin XML Style` payload as a project-local `.oth` file, may save the selected graph page as a project-local `.otpu` candidate, and writes a `data_snapshots/<type>.json` template-data snapshot. Origin-native saves are performed through ASCII temporary paths and then copied back to the project asset directory, because LabTalk `save -t` can fail on non-ASCII output paths. Export alone does not make an `.otpu` runnable; promotion requires a complete binding contract and independent validation evidence recorded by the current manifest.

For the reviewed XRD Graph4 template, the data snapshot must contain five plotted datasets:

- Layer 1: `Book2_B`, `Book2_D`, `Book2_F`
- Layer 2: `Book2_H` standard-card sticks, paired with `Book2_G`
- Layer 3: `Book3_F`, paired with `Book3_E`

## Verification

Before claiming the asset path is self-contained, run:

```powershell
python run.py template-format-products --pairing "<pairing-plan.json>" --asset-only --compact-output --with-origin
```

For an independently validated `.otpu`, the expected metadata includes:

- `asset_only = true`
- `external_template_dependency = false`
- `template_format_plan.mode = verified_graph_template`
- `origin_processing.method = fresh_graph_verified_otpu_explicit_xy`
- `origin_processing.reference_opju_loaded = false`
- `origin_processing.reference_opju_used_as_product_base = false`
- `origin_processing.current_data_validation.status = matched`
- `asset_same_data_exact_validation.status = verified`
- `style_data_binding.status = matched`

Legacy accepted `.oth` routes continue to report `saved_format_theme` and
`saved_format_theme_apply`; these two modes must not be conflated.

Every replay and formal product TIFF is exported natively by Origin at 600 dpi. Verification reads the final graph's dynamic `page.width` and `page.height` and checks the expected raster pixels, effective physical DPI, and TIFF DPI tags without rewriting or resampling the file.

Origin's native TIFF writer also stores the current project identity in an IPTC
field. The export path therefore saves and reopens the final OPJU, reads the
target page dimensions, runs `doc -rn` followed by `doc -s`, verifies that `%X`
is empty and `%G` is `UNTITLED`, reactivates the graph, and only then exports the
TIFF. A controlled before/after comparison showed identical decoded pixels; the
operation removes the temporary path identity without restyling or re-encoding
the graph.

For the dedicated XRD product paths, expected metadata is also:

- `reference_opju_loaded = false`
- standard-card products report `style_mode = fixed_otpu` and contain native
  sample curves plus native standard-card sticks/annotations
- no-card products report `style_mode = fixed_otpu` for exactly nine curves or
  `style_mode = adaptive_oth_json` for another positive curve count
- no-card direct labels are rebuilt from current labels; template placeholder
  labels and reference OPJU content are never product data

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

The current independent replacements supersede that historical conclusion for
the following products:

- BET: `validation_evidence/BET_verified_20260813.json`.
- EIS: `validation_evidence/EIS_verified_20260822.json`; the formal same-data
  replay has zero changed pixels, and a separate real-data formal product was
  accepted after OPJU save/reopen, exact 8-by-101 X/Y readback, style
  conformance, native 600 dpi export, and manual PNG inspection.
- EPR: `validation_evidence/EPR_verified_20260822.json`; the formal same-data
  replay has zero changed pixels with the reviewed shared-X 4096-by-3 mapping
  and 59/59 style readback. A separate current-data product was accepted after
  the existing Origin baseline/AAV7/offset transform, OPJU save/reopen, exact
  X/Y readback, persistent current `BC`/`CWO`/`BOBC` label-object readback,
  native 600 dpi export, and manual PNG inspection.
- PL: `validation_evidence/PL_verified_20260822.json`; the accepted runtime
  bundle requires `.otpu` + `.oth` + snapshot and uses `A→B` rows 1–351,
  `A→D` rows 1–176, and `A→F` rows 1–351. The formal project replay passed
  59/59 style checks, save/reopen, native 600 dpi export, and zero decoded-pixel
  difference with RMS 0. The separate real-data product did not load the
  reference OPJU; its no-label/path audit had 0 hits, and its same-data
  4190×2806 TIF matched the reference replay TIF pixel-for-pixel.
- Photocurrent: `validation_evidence/photocurrent_verified_20260822.json`; the
  accepted runtime asset requires `.otpu` + style snapshot and does not require
  `.oth`. The formal same-data replay passed 59/59 style checks, save/reopen,
  native 600 dpi export, and zero decoded-pixel difference. Its independent
  real-data product used `fresh_graph_verified_otpu_explicit_xy` with
  `reference_opju_loaded=false`, paired `A→B`, `C→D`, and `E→F` mappings of
  2600 points each, 1 pt curves, 16 pt non-bold dynamic axis titles, and native
  600 dpi export. The real-data product is not claimed to be pixel-identical to
  the reference data.
- XRD with standard card: `validation_evidence/XRD_verified_20260823.json`;
  the accepted fixed-shape OTPU uses the explicit three-layer worksheet/plot
  binding contract and passed fresh-project same-data exact-pixel replay. The
  dedicated runtime constructs only native Origin worksheet plots, axes,
  legend, card sticks, and annotations, then saves/reopens before native TIFF
  export.
- XRD without standard card:
  `validation_evidence/XRD_no_card_verified_20260823.json` validates the fixed
  nine-curve OTPU, while
  `validation_evidence/XRD_no_card_oth_json_adaptive_verified_20260823.json`
  validates the retained adaptive OTH+JSON path. Both are fresh-project,
  same-data, zero-difference validations and neither loads a reference OPJU as
  a product base.

Do not infer from a correct reference OPJU that it is a safe generic workbook
base. A controlled XRD replacement trial preserved most style fields but mapped
the current columns incorrectly, producing flat curves and overlapping labels.
Reference OPJUs therefore remain independent evidence unless a future
type-specific manifest and replacement contract proves complete workbook and
plot mapping for that exact data shape.
