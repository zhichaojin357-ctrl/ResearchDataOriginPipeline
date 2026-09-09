# Native legend and export maintenance

## Scope

The user's requested change applies to all formal data-type plotting routes:
Origin generates linked legends from the current mapped Y-column labels. Scripts
no longer assign sample legend text or draw independent line/text legend rows.
Real source/sample names are retained without invented type prefixes or internal
signal-field suffixes. Meaningful measured/fitted and adsorption/desorption
branches remain distinct. Genuine curve labels, peak annotations and supplied
reference-card captions are not sample legends and remain native annotations.

`update_native_legend` supplies worksheet metadata and calls Origin's
`legendupdate`, or native legend append/delete operations for subsets/order.
Decimal chemical subscripts are preserved. HPLC equation/R-squared values are
current fit metadata consumed by the native custom legend, not literal legend rows.

Final placement is shared by the generic PowerShell exporter, template executor
(OPJU-copy, snapshot, OTPU and OTH paths), template product builder, fresh XRD
overlay and maintained HPLC calibration helper. It checks all visible layers,
freezes legal anchors and moves only conflicting native legends. Curves are read
once per page; candidate ordering uses Origin's native stable sort. Clearance
uses actual line/symbol size, not a percentage of the page. No font, curve, axis
or page resizing is used. If placement cannot be verified, export reports failure.
The geometry helper models ordinary 2D XY line/scatter/line-symbol plots; it is
not a universal renderer for arbitrary spline, area, bar or 3D geometry. Pages
without visible legends need no placement. Exported previews still need review.

## Workstation evidence (2026-09-10)

Only existing same-input products/processed tables were reused; no full raw-data
batch was repeated. Evidence is under the configured external output root in
`origin_curve_fix_20260910`, with a curated `原生图例人工核对_20260910` folder.

| Product | Real Origin evidence |
|---|---|
| EIS b3 | Formal generic exporter; native linked `b3`; original legal anchor retained; saved/reopened OPJU, native 600 dpi TIFF and PNG checked. |
| Raman | Three distributed native legends replace the old mixed legend/text/line objects; decimal subscripts corrected; saved/reopened result has no legend intersections. |
| FTIR | Current rich sample labels linked natively; legend relocated to a clear area; saved/reopened PNG and native TIFF checked. |
| XRD with card | Fresh template graph uses the same processed XY mappings; two native legends placed without intersection; saved/reopened binding check passed and second placement check moved nothing. |
| HPLC calibration (three compounds) | Formal helper, unchanged fit values, native legends; all three final previews checked. Existing anchors passed without movement. |

All seven final previews were visually inspected. Native TIFFs have 600 dpi tags
and pixel dimensions consistent with the final page's physical dimensions.
This is representative visual validation, not a claim that every possible
data/curve-count combination has been rendered.

HPLC's original reference exports remain separately available. Native metadata
lines have a different indentation from the old manually written legend. The
zero-pixel comparison applies to the reference **after the same explicit native
legend policy**, not to the untouched original reference.

## Other bounded changes and checks

- Fixed the generic TIFF losing curves: reopen a task-owned OPJU copy with
  `readonly=False, asksave=False`; Origin's read-only opening produced empty
  worksheets in the actual failing case. TIFF and PNG now come from the same
  reopened session; the saved product itself is not overwritten.
- Reuse Agilent ZIP member indexing and already-built processing/readiness
  summaries; stop numeric-column fallback after the first two usable columns.
- Removed obsolete manual-legend helpers and normalized-data corner heuristics.
  Did not rewrite scientific algorithms, replace runtime templates or merge
  previously unverified single-session exporting.
- Full pytest run: 1288 passed, 3 skipped, 68 subtests passed, with one old test
  expecting invented Mott-Schottky sample names. That assertion was updated to
  actual source names; its module plus adapter retest passed (136 tests).
- Final affected Origin/executor/builder/XRD tests: 359 passed, 13 subtests passed.
- `validate --scope runtime`: zero failures; `readiness --scope runtime
  --no-desktop-review-xlsx`: zero failures/warnings. Runtime scope is not a full
  release-readiness or historical-results certification.
- No raw data, external templates or checked-in style assets were changed.

Known pre-existing generic EIS axis-title clipping/crowded tick labels were not
changed by this legend-only request. Do not describe them as fixed.
