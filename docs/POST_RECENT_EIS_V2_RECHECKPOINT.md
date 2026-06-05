# Post Recent EIS/V2 Recheckpoint

Generated from read-only inspection of the current repository and external output
roots. No Origin run, new product generation, staging, or commit was performed for
this recheckpoint.

## Git State

- Branch: `master`
- HEAD: `8e2d226 eis: preserve main branch and plot Randles CPE curve`
- Staged changes: none
- Worktree clean: no
- Visible untracked files before this document: four EIS review docs
  - `docs/EIS_DATA_QUALITY_AND_FITTING_REVIEW.md`
  - `docs/EIS_EXEMPLAR_CONFORMANCE_REPORT.md`
  - `docs/EIS_RANDLES_CPE_FIT_REVIEW.md`
  - `docs/EIS_V2_REGENERATION_SUMMARY.md`

## Recent Relevant Commits

- `8e2d226 eis: preserve main branch and plot Randles CPE curve`
- `0feb413 origin: prefer main graph page for OPJU style snapshots`
- `e9f9988 origin: refine EIS v2 plot intent`
- `ca9c843 origin: sanitize v2 metadata paths`
- `a4f1921 origin: read rich-text bold axis titles in conformance`
- `70328a8 origin: add v2 exemplar conformance and EIS Randles-CPE fit`
- `2a2d45b docs: record remaining opju product drafts`
- `a6cae7b origin: add remaining opju mimic pilots`
- `e7aa879 origin: add xps xrd epr bet opju mimic pilots`
- `adcf363 origin: add reviewed opju style mimic executor`

## Run Roots Inspected

Latest effective EIS v2 run:

```text
D:\Codex Project\科研数据处理\输出\runs\20260605_125416_eis_randles_cpe_v2
```

Earlier completed product runs still present:

```text
D:\Codex Project\科研数据处理\输出\runs\20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet
D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts
```

No run root matching `*_v2_exemplar_conformance_all_types*` or `*all_types*`
was found under the external output root.

## Product Coverage

There is no single all-types V2 regeneration run. Product coverage is split
across earlier runs plus the latest EIS-only v2 run.

| Type | Latest source run | OPJU | TIF | PNG | processed_data | metadata | report | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| BET | `20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet` | 1 | 1 | 1 | yes | yes | yes | present, older 5-type pilot |
| XPS_in_situ | `20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet` | 1 | 1 | 1 | yes | yes | yes | present, older 5-type pilot |
| XPS_non_in_situ | `20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet` | 1 | 1 | 1 | yes | yes | yes | present, older 5-type pilot |
| XRD | `20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet` | 1 | 1 | 1 | yes | yes | yes | present, older 5-type pilot |
| EPR | `20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet` | 1 | 1 | 1 | yes | yes | yes | present, older 5-type pilot |
| EIS | `20260605_125416_eis_randles_cpe_v2` | 1 | 1 | 1 | yes | yes | yes | completed with Randles-CPE v2 |
| Raman | `20260605_000310_remaining_opju_product_drafts` | 1 | 1 | 1 | yes | yes | yes | present, remaining draft |
| UV_vis_DRS_Tauc | `20260605_000310_remaining_opju_product_drafts` | 1 | 1 | 1 | yes | yes | yes | present, remaining draft |
| PL | `20260605_000310_remaining_opju_product_drafts` | 1 | 1 | 1 | yes | yes | yes | present, remaining draft |
| photocurrent | `20260605_000310_remaining_opju_product_drafts` | 1 | 1 | 1 | yes | yes | yes | present, remaining draft |
| FTIR | `20260605_000310_remaining_opju_product_drafts` | 1 | 1 | 1 | yes | yes | yes | present, remaining draft |

## EIS Randles-CPE Status

Latest effective EIS run:

```text
D:\Codex Project\科研数据处理\输出\runs\20260605_125416_eis_randles_cpe_v2
```

Required EIS files are present:

- `EIS/processed_data/raw_eis_data.csv`
- `EIS/processed_data/cleaned_eis_data.csv`
- `EIS/processed_data/ignored_eis_points.csv`
- `EIS/processed_data/eis_randles_cpe_fit_curve.csv`
- `EIS/metadata/eis_cleaning_and_fit_metadata.json`
- `EIS/origin_files/EIS_BOBC_exemplar_v2.opju`
- `EIS/figures_tif/EIS_BOBC_exemplar_v2.tif`
- `EIS/figures_preview/EIS_BOBC_exemplar_v2_preview.png`
- `EIS/reports/EIS_BOBC_exemplar_v2_report.md`

Metadata readback:

- Raw points: 71
- Cleaned points: 62
- Ignored points: 9
- Model: `Model A: Rs + (Rct || CPE)`
- Parameters present: `Rs`, `Rct`, `Q`, `n`
- Review policy: `draft fit for visualization/manual review only`
- Avoided claims:
  - no final equivalent-circuit conclusion
  - no charge-transfer resistance interpretation
  - no electrochemical mechanism conclusion
- Warning: `Rct reached the bounded search ceiling; draft fit is under-constrained by the available cleaned branch and requires manual review.`

## Exemplar-Conformance Engine

Code and tests are present:

- `src/origin/conformance.py`
- `src/origin/style_mimic.py`
- `tests/test_opju_exemplar_conformance.py`
- `tests/test_origin_style_mimic.py`
- `docs/OPJU_EXEMPLAR_CONFORMANCE_ENGINE_REVIEW.md`

The engine is not just documentation: `src/core/v2_exemplar_conformance.py`
calls `extract_style_snapshot`, `read_graph_style_snapshot`, and
`compare_style_snapshots` around product generation. It compares page/layer,
axis, plot, legend/title, line width, and axis-title-bold readbacks. The latest
EIS metadata confirms exemplar graph `Graph1`, product plot count 2, line width
readback `30.0,30.0`, axis title bold true, and overlap check pass.

`src/origin/exemplar.py` does not exist, but the implemented comparison lives in
`style_mimic.py` and `conformance.py`.

## User Style Override

Code, config, docs, and tests are present:

- `src/origin/user_style.py`
- `config/user_plot_style.example.yaml`
- `docs/USER_PLOT_STYLE_OVERRIDE_GUIDE.md`
- `tests/test_user_plot_style_override.py`

The implementation supports global and per-data-type overrides for line width,
axis line width, tick width, axis title font size, tick label font size, legend
font size, title font size, marker size, and bold font policy. It is wired into
`src/core/v2_exemplar_conformance.py`.

## Product Safety

Latest EIS no-label audit:

- `reports/product_no_label_audit.json`: `hit_count = 0`
- `path_only_hits = []`

This recheckpoint did not modify `F:\` files, did not modify original OPJU
files, did not generate new OPJU/TIF/PNG products, did not run Origin, did not
stage, and did not commit.

## Decision

Case B is the closest current state:

- EIS Randles-CPE cleaning/fitting v2 is completed.
- Exemplar-conformance engine is implemented and used.
- User style override is implemented and used.
- A single all-types V2 regeneration run was not found.
- The listed product types have artifacts across older split runs plus the
  latest EIS v2 run, but they were not regenerated together in one all-types V2
  conformance run.

Recommended next step:

Continue with an all-types V2 regeneration/checkpoint only if the user wants a
single unified run root. Otherwise, move to manual visual calibration using the
latest EIS v2 preview and the two older product run roots.
