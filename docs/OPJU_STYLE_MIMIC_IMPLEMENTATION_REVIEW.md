# OPJU Style Mimic Implementation Review

## Scope

The reviewed style-mimic layer is implemented in `src/origin/style_mimic.py`.
It opens a copied exemplar OPJU, enumerates graph pages, records a numeric style
snapshot, and applies numeric layout values to a new graph.

## Captured Style Fields

- Page size.
- Layer geometry.
- Axis line thickness.
- Tick-label point sizes.
- Axis/title/legend/tick visibility values.
- Legend coordinates when present.
- Axis/title/legend font names and sizes when Origin exposes them.
- Plot count.
- Plot line-width, color, marker-shape, and marker-size readbacks when Origin exposes plot names.
- Graph-page list and layer count for multi-panel review.

## Safety Boundary

The mimic layer does not copy visible text objects from exemplar projects.
Peak assignments, phase labels, XPS valence labels, mechanism text, EPR radical
labels, product identity text, and conversion/selectivity/yield annotations are
kept out of the generated graph and routed to manual review.

The current product policy overrides series line width to 3 pt after style
application, and wraps axis titles in Origin bold rich text.
