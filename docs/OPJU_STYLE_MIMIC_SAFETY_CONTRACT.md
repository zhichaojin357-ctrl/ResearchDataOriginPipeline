# OPJU Style Mimic Safety Contract

## Input Handling

- Original F-drive data files are read-only sources.
- Original OPJU/OPJ files are never modified.
- Exemplar OPJU files are copied into the external run root before Origin opens them.
- Generated OPJU/TIF/PNG/CSV/JSON/MD products are written only under the external run root.

## Forbidden Automatic Transfers

The executor must not copy or infer:

- Peak assignments.
- Crystal-plane or phase labels.
- XPS valence, electron-transfer, or S-scheme text.
- EPR radical assignments.
- Equivalent-circuit labels.
- Product identity labels.
- Conversion/selectivity/yield values.
- Mechanism arrows or explanatory mechanism text.

## Required Manual Review

Each generated product is for visual calibration only. Scientific assignments,
sample-role confirmation, component labels, binding-energy direction, standard
card usage, and radical identity remain manual-review items.
