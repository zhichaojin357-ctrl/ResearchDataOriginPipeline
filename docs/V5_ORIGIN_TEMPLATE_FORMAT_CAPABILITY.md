# V5 Origin template/format capability notes

## Official Origin behavior checked

- Graph Templates store graph page, layer, axis, label, annotation, and data-plot style holder properties. Cloneable templates can also preserve plot-to-workbook structure.
- Graph Formats and Themes are distinct from templates. A Format is copied to the clipboard; a Theme is a saved `.OTH` file that can be reapplied later.
- Copy/Paste Format can copy selected page/layer/axis/title/legend/plot formatting, but it is object-oriented and the available paste behavior depends on the selected source and target object.

Official documentation used:

- https://docs.originlab.com/origin-help/graph-format-theme/
- https://docs.originlab.com/origin-help/copypaste-format/
- https://docs.originlab.com/origin-help/graph-template-elements/
- https://docs.originlab.com/origin-help/graph-template-basics/

## Local Origin COM probe

The local OriginPro 2026 COM object exposes:

- `Load(Path, readonly)`
- `Save(Path)`
- `CreatePage(Type, Name, templateName, option)`
- `LoadPage(pathname, Options)`
- `CopyPage(Name, format, dpi, colordepth)`
- `FindGraphLayer(Name)`
- `GetWorksheet(Name, r1, c1, r2, c2, format)`
- `PutWorksheet(Name, data, r1, c1)`

For existing OPJU templates, `FindGraphLayer("[Graph]Layer1").DataPlots.Item(i).Name` exposes workbook-column dataset references such as `Book8_B`, `Book8_C`, and `Book8_E`. This makes a safer template-base path possible:

1. Copy the selected OPJU exemplar into the run output.
2. Open the OPJU copy in isolated Origin.
3. Read the selected graph's plot dataset names.
4. Replace the referenced workbook columns with processed data using `PutWorksheet`.
5. Preserve the existing graph page, layers, legends, fills, and object-level styling.
6. Enforce global user policies that are not optional: 3 pt curves and bold axis titles.
7. Save as a new product OPJU, reopen, export TIF/PNG, and compare with the exported template preview.

## Policy boundary

V5 must not claim one-to-one replication merely because a template or style package exists. The claim is allowed only after exported template preview and product preview comparison, plot count checks, style readback, and manual calibration gates pass.

If neither an OPJU exemplar nor a saved Theme/Graph Template/style package is available, V5 must block plotting instead of falling back to parameter-only mimicry.

## Project-local style assets

The final accepted V5 run has been harvested into project-local Origin graph templates:

```text
templates/origin_styles/manifest.json
templates/origin_styles/graph_templates/*.otpu
```

These `.otpu` files are the saved style-package fallback for future runs when external OPJU exemplars are unavailable. They remove the dependency on F-drive OPJU style sources for style discovery, while preserving the rule that any regenerated product must still pass exported preview comparison before one-to-one status is claimed.
