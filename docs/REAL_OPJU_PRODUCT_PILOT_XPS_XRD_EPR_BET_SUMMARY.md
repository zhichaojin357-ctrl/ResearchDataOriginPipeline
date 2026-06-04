# Real OPJU Product Pilot Summary: XPS/XRD/EPR/BET

## Final Run

- Run root: `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet`
- Product count: 5
- Failure count: 0
- F-drive files modified: no
- Original OPJU/OPJ files modified: no
- Output products committed: no

## Products

| Type | OPJU | TIF | PNG preview |
|---|---|---|---|
| BET | `BET\origin_files\BET_BOBC_exemplar_pilot.opju` | `BET\figures_tif\BET_BOBC_exemplar_pilot.tif` | `BET\figures_preview\BET_BOBC_exemplar_pilot_preview.png` |
| XPS in-situ | `XPS_in_situ\origin_files\XPS_in_situ_BOBC_exemplar_pilot.opju` | `XPS_in_situ\figures_tif\XPS_in_situ_BOBC_exemplar_pilot.tif` | `XPS_in_situ\figures_preview\XPS_in_situ_BOBC_exemplar_pilot_preview.png` |
| XPS non-in-situ | `XPS_non_in_situ\origin_files\XPS_non_in_situ_BOBC_BC_exemplar_pilot.opju` | `XPS_non_in_situ\figures_tif\XPS_non_in_situ_BOBC_BC_exemplar_pilot.tif` | `XPS_non_in_situ\figures_preview\XPS_non_in_situ_BOBC_BC_exemplar_pilot_preview.png` |
| XRD | `XRD\origin_files\XRD_BOBC_exemplar_pilot.opju` | `XRD\figures_tif\XRD_BOBC_exemplar_pilot.tif` | `XRD\figures_preview\XRD_BOBC_exemplar_pilot_preview.png` |
| EPR | `EPR\origin_files\EPR_BC_O3_dark_exemplar_pilot.opju` | `EPR\figures_tif\EPR_BC_O3_dark_exemplar_pilot.tif` | `EPR\figures_preview\EPR_BC_O3_dark_exemplar_pilot_preview.png` |

## Verification

- Origin smoke test: passed from clean worktree.
- OPJU style readback: all five generated OPJU files passed.
- Curve width: Origin readback width `30.0`, corresponding to 3 pt.
- Axis titles: bold rich text `\b(...)` for both x and y titles.
- Preview edge check: all five PNG previews have zero non-white pixels on image borders.
- Supplementary completion audit: run reports now include selected data, selected OPJU exemplar, manual review needs, forbidden scientific claims avoided, and visible-label audit status per type.
- Verification reports: `reports\origin_style_verification.json`, `reports\origin_visible_text_label_audit.json`, and `reports\preview_edge_check.json`.
- HPLC/LC: deferred; no Origin product, no conversion/selectivity/yield, and no product identity assignment.
