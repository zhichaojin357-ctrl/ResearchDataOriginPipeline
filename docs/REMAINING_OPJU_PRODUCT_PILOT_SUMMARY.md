# Remaining OPJU Product Pilot Summary

## Final Run

- Run root: `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts`
- Previous completed run: `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet`
- Product count: 6
- Failure count: 0
- Skipped/deferred count: 3
- F-drive files modified: no
- Original OPJU/OPJ files modified: no
- Output products committed: no

## Products

| Type | OPJU | TIF | PNG preview |
|---|---|---|---|
| EIS | `EIS\origin_files\EIS_BOBC_exemplar_draft.opju` | `EIS\figures_tif\EIS_BOBC_exemplar_draft.tif` | `EIS\figures_preview\EIS_BOBC_exemplar_draft_preview.png` |
| Raman | `Raman\origin_files\Raman_BOBC_exemplar_draft.opju` | `Raman\figures_tif\Raman_BOBC_exemplar_draft.tif` | `Raman\figures_preview\Raman_BOBC_exemplar_draft_preview.png` |
| UV-vis DRS / Tauc | `UV_vis_DRS_Tauc\origin_files\UV_vis_DRS_Tauc_BOBC_exemplar_draft.opju` | `UV_vis_DRS_Tauc\figures_tif\UV_vis_DRS_Tauc_BOBC_exemplar_draft.tif` | `UV_vis_DRS_Tauc\figures_preview\UV_vis_DRS_Tauc_BOBC_exemplar_draft_preview.png` |
| PL | `PL\origin_files\PL_BOBC_exemplar_draft.opju` | `PL\figures_tif\PL_BOBC_exemplar_draft.tif` | `PL\figures_preview\PL_BOBC_exemplar_draft_preview.png` |
| photocurrent | `photocurrent\origin_files\photocurrent_BOBC_exemplar_draft.opju` | `photocurrent\figures_tif\photocurrent_BOBC_exemplar_draft.tif` | `photocurrent\figures_preview\photocurrent_BOBC_exemplar_draft_preview.png` |
| FTIR | `FTIR\origin_files\FTIR_BOBC_CWO_exemplar_draft.opju` | `FTIR\figures_tif\FTIR_BOBC_CWO_exemplar_draft.tif` | `FTIR\figures_preview\FTIR_BOBC_CWO_exemplar_draft_preview.png` |

## Deferred Or Skipped

- Mott-Schottky: `invalid_mott_exemplar_mismatched_type`; Origin axis readback showed XRD-style 2theta/intensity labels.
- reaction_condition_screening: `skipped_no_clear_data_pair`; OPJU candidates exist, but no clear exported source data table was found.
- HPLC/LC: `deferred_hplc_lc_pdf_only_no_opju`; PDF-only samples, no OPJU exemplar, no OCR, no conversion/selectivity/yield, no product identity assignment.

## Verification

- Origin smoke test: passed before generation.
- OPJU style readback: all six generated OPJU files passed.
- Curve width: Origin readback width `30.0`, corresponding to 3 pt.
- Axis titles: bold rich text `\b(...)` for both x and y titles.
- Preview edge check: all six PNG previews have zero non-white pixels on image borders.
- Visible-label audit hit count: 0.
- Verification reports: `reports\origin_style_verification.json`, `reports\origin_visible_text_label_audit.json`, and `reports\preview_edge_check.json`.
