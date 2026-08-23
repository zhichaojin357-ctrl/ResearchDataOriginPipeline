# Template Discovery and Selection

- Project style root scanned: `templates/origin_styles`
- Selection policy: resolve accepted runtime assets from the current manifest.
- Runtime policy: use the accepted detached `.otpu` route for the reviewed fixed
  structure; use a separately accepted `.oth`+JSON route only when the current
  series cardinality requires adaptation.

| Product | Selected Format Asset | Graph | Status | Reason |
|---|---|---|---|---|
| BET | `templates/origin_styles/format_themes/BET.oth` | Graph3 | selected | project-local saved Origin format theme |
| XPS_in_situ | `templates/origin_styles/format_themes/XPS_in_situ.oth` | Cl_2p | selected | project-local saved Origin format theme |
| XPS_non_in_situ | `templates/origin_styles/format_themes/XPS_non_in_situ.oth` | XPS_Bi_BOBC_vs_c890fa98 | selected | project-local saved Origin format theme |
| XRD | `templates/origin_styles/format_themes/XRD.oth` | Graph4 | selected | project-local saved Origin format theme |
| EPR | `templates/origin_styles/format_themes/EPR.oth` | ohG | selected | project-local saved Origin format theme |
| EIS | `templates/origin_styles/format_themes/EIS.oth` | Graph1 | selected | project-local saved Origin format theme |
| Raman | `templates/origin_styles/graph_templates/Raman.otpu` (fixed); `templates/origin_styles/format_themes/Raman.oth` + JSON snapshots (adaptive) | Graph2 | accepted | fixed three-series/two-layer exact replay plus separately validated variable-cardinality Origin-native route |
| UV-vis DRS / Tauc | `templates/origin_styles/format_themes/UV_vis_DRS_Tauc.oth` | Graph1 | selected | project-local saved Origin format theme |
| PL | `templates/origin_styles/format_themes/PL.oth` | EXJF | selected | project-local saved Origin format theme |
| photocurrent | `templates/origin_styles/format_themes/photocurrent.oth` | Graph1 | selected | project-local saved Origin format theme |
| FTIR | `templates/origin_styles/format_themes/FTIR.oth` | Graph1 | selected | project-local saved Origin format theme |
