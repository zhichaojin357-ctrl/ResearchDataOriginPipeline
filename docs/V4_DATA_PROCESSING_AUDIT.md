# V4 data-processing audit

- Final audited run: `D:\Codex Project\科研数据处理\输出\runs\20260606_125645_unified_v4_strict_template_conformance_all_types`
- Status: 11/11 products accepted after Origin save/reopen/readback.
- Global rule applied: every non-EIS product imports raw or staging source data into Origin first, then Origin workbook LabTalk creates the final plotted columns before graphing/export.
- EIS exception: EIS keeps the Python Randles-CPE cleaning/fitting workflow because the user explicitly allowed it to replace the previous ZView draft fit.
- Method-correctness audit: see `docs/V4_METHOD_CORRECTNESS_AUDIT.md`; it records per-type standard-method checks and unsupported automatic-analysis boundaries.

| Type | Source imported to Origin | Processing executed in Origin before plotting | Audit decision |
|---|---|---|---|
| BET | Raw/staging adsorption-desorption table copied from the selected instrument export. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for the current isotherm-style plot. No BET model/surface-area conclusion is claimed. |
| XPS in-situ | Fitted XPS source workbooks for the selected in-situ element/region. | Origin LabTalk normalizes curves, applies vertical offsets, and creates component fill helper curves from imported fitted-source curves. | Complies for plotting already fitted XPS workbooks. Peak fitting is not redone and no valence/mechanism conclusion is claimed. |
| XPS non-in-situ | Fitted XPS source workbooks for the selected non-in-situ comparison. | Origin LabTalk normalizes BOBC/BC curves, applies vertical offsets, and creates component fill helper curves from imported fitted-source curves. | Complies for plotting already fitted XPS workbooks. Peak fitting is not redone and no valence/mechanism conclusion is claimed. |
| XRD | Raw/staging two-theta and intensity columns from the selected pattern export. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for raw-pattern plotting. Phase assignment and peak indexing remain manual. |
| EPR | Three template-matched raw OH traces. | Origin LabTalk performs edge-region median baseline subtraction, Origin adjacent-average smoothing (`npts=7`), and vertical offset. | Complies. This replaces the earlier Python-preprocessed EPR overlay. |
| EIS | Cleaned EIS points and Python-generated draft fit curve. | Origin only plots the cleaned measured points and fit curve. | Explicit exception. Python performs invalid-tail cleaning and Randles-CPE draft fitting (`Rs + (Rct || CPE)`). No final equivalent-circuit conclusion is claimed. |
| Raman | Raw/staging XY spectrum columns. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for raw spectrum plotting. Baseline and peak fitting remain manual. |
| UV-vis DRS / Tauc | Raw/staging wavelength-signal columns. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for the current raw-signal plot. Tauc transform and bandgap extraction remain manual unless explicitly requested. |
| PL | Raw/staging emission XY columns. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for raw emission plotting. Peak fitting/integration remain manual. |
| photocurrent | Raw/staging time-current columns. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for raw transient plotting. Light on/off segmentation remains manual. |
| FTIR | Raw/staging aligned BOBC/CWO XY overlay columns. | Origin LabTalk copies imported plotting columns into final graph columns. | Complies for raw overlay plotting. Baseline correction and peak assignment remain manual. |

## Verification evidence

- Unified command returned `product_count=11`, `success_count=11`, `blocked_count=0`, `failed_count=0`.
- Product metadata check found `origin_processing.applied = true` for all non-EIS products.
- EPR metadata also records `epr_origin_processing.applied = true`.
- EIS metadata records the Python Randles-CPE draft fit workflow and keeps the Origin step limited to plotting.
- Product file check found all OPJU/TIF/PNG/processed-data/reference-preview files present and nonempty.
- Run-tree check found `empty_dirs = 0`.
- Template preview comparison reports are present for all 11 products.
- Forbidden-label audit found `hit_count = 0`.

## Manual boundaries

- These outputs are draft plot products plus manual-review packages.
- The workflow does not claim final BET surface area, XPS valence assignment, XRD phase assignment, Raman/PL/FTIR peak assignment, UV-vis bandgap, photocurrent segmentation, or electrochemical mechanism.
- HPLC/LC remains deferred and was not plotted in this V4 run.
