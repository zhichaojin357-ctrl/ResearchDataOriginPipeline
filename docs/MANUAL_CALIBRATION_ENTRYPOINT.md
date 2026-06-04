# Manual Calibration Entrypoint

## Run Roots

- First batch: `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet`
- Remaining batch: `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts`

## Recommended Review Order

1. BET
2. XPS_in_situ
3. XPS_non_in_situ
4. XRD
5. EPR
6. EIS
7. Raman
8. photocurrent
9. Mott-Schottky
10. UV-vis DRS / Tauc
11. PL
12. FTIR
13. reaction_condition_screening
14. HPLC/LC deferred

## Product Entrypoints

| Type | OPJU | PNG preview | Key manual checks |
|---|---|---|---|
| BET | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\BET\origin_files\BET_BOBC_exemplar_pilot.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\BET\figures_preview\BET_BOBC_exemplar_pilot_preview.png` | isotherm/pore-distribution choice; units; legend; font |
| XPS_in_situ | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\XPS_in_situ\origin_files\XPS_in_situ_BOBC_exemplar_pilot.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\XPS_in_situ\figures_preview\XPS_in_situ_BOBC_exemplar_pilot_preview.png` | in-situ grouping; binding-energy direction; fitted roles; no valence/mechanism text |
| XPS_non_in_situ | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\XPS_non_in_situ\origin_files\XPS_non_in_situ_BOBC_BC_exemplar_pilot.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\XPS_non_in_situ\figures_preview\XPS_non_in_situ_BOBC_BC_exemplar_pilot_preview.png` | non-in-situ grouping; sample order; fitted roles; no electron-transfer/S-scheme text |
| XRD | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\XRD\origin_files\XRD_BOBC_exemplar_pilot.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\XRD\figures_preview\XRD_BOBC_exemplar_pilot_preview.png` | no copied reference-card claim; no phase/plane assignment; 2theta axis; stacked layout |
| EPR | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\EPR\origin_files\EPR_BC_O3_dark_exemplar_pilot.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\EPR\figures_preview\EPR_BC_O3_dark_exemplar_pilot_preview.png` | condition grouping; no radical assignment; line/legend |
| EIS | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\EIS\origin_files\EIS_BOBC_exemplar_draft.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\EIS\figures_preview\EIS_BOBC_exemplar_draft_preview.png` | Z'/-Z'' mapping; Nyquist/Bode choice; no equivalent-circuit conclusion |
| Raman | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\Raman\origin_files\Raman_BOBC_exemplar_draft.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\Raman\figures_preview\Raman_BOBC_exemplar_draft_preview.png` | axis/unit; grouping; no peak phase/defect assignment |
| photocurrent | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\photocurrent\origin_files\photocurrent_BOBC_exemplar_draft.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\photocurrent\figures_preview\photocurrent_BOBC_exemplar_draft_preview.png` | time/current axis; light on/off labels; no carrier-separation conclusion |
| Mott-Schottky | not generated | not generated | skipped because selected exemplar read back as XRD-style axis; provide a confirmed Mott-Schottky exemplar |
| UV-vis DRS / Tauc | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\UV_vis_DRS_Tauc\origin_files\UV_vis_DRS_Tauc_BOBC_exemplar_draft.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\UV_vis_DRS_Tauc\figures_preview\UV_vis_DRS_Tauc_BOBC_exemplar_draft_preview.png` | DRS/Tauc mode; transform parameters; no final bandgap or band-edge conclusion |
| PL | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\PL\origin_files\PL_BOBC_exemplar_draft.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\PL\figures_preview\PL_BOBC_exemplar_draft_preview.png` | excitation/emission mode; grouping; no recombination conclusion |
| FTIR | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\FTIR\origin_files\FTIR_BOBC_CWO_exemplar_draft.opju` | `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\FTIR\figures_preview\FTIR_BOBC_CWO_exemplar_draft_preview.png` | wavenumber direction; units; no functional-group assignment |
| reaction_condition_screening | not generated | not generated | skipped because no clear exported condition/value table was found |
| HPLC/LC deferred | not generated | not generated | PDF-only and no OPJU exemplar; no OCR or conversion/selectivity/yield calculation |

## Report Entrypoints

- First batch summary: `D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet\reports\final_summary.md`
- Remaining batch summary: `D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts\reports\final_summary.md`
- Product existence audit: `docs\POST_GENERATION_PRODUCT_EXISTENCE_AUDIT.md`
- Label audit: `docs\POST_GENERATION_NO_CODEX_LABEL_AUDIT.md`
- Input protection audit: `docs\POST_GENERATION_INPUT_PROTECTION_AUDIT.md`
- Output root audit: `docs\POST_GENERATION_OUTPUT_ROOT_AUDIT.md`
