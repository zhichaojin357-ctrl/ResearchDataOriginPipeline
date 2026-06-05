# OPJU exemplar conformance engine review

The v2 conformance path reads an OPJU exemplar copy through an isolated Origin
session and records object-level graph properties before creating a new product
graph.

Compared property groups:

- Page/layer: page width, page height, layer left/top/width/height, axis line
  width.
- Axis: tick direction, tick lengths/counts, tick label size/bold/offset, axis
  title size/bold/position, axis ranges.
- Plot: line width, color, marker shape, marker size, plot count.
- Legend/title: visibility, position, font size, bold state.
- Graph objects: object positions when COM exposes graph-object geometry.

Product policies applied after exemplar style:

- Curve line width is forced to 3 pt unless a data-type override explicitly
  supplies the same policy.
- X and Y axis titles are forced bold.
- Exemplar scientific annotations are not copied.
- EIS v2 uses cleaned measured points plus a Randles-CPE draft fit curve; raw
  all-point line connection is not emitted.

Conformance status is a technical readback and manual-review aid. It is not a
human acceptance result and does not establish scientific conclusions.
