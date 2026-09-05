# Current Status

This repository is the maintained runtime pipeline. The active path is
`run.py -> src/cli.py -> src/core / src/processors / src/origin`. Historical
commits and old generated assets are evidence only; current behavior is defined
by the working tree, registry, manifest, validators, and current run reports.

The latest broad code audit remains
[CODEBASE_AUDIT_2026-07-31.md](CODEBASE_AUDIT_2026-07-31.md). This file records
the newer runtime state after the Origin style-route work and XRD data-module
merge.

## Optimization branch awaiting workstation acceptance

`codex/optimize-pipeline-preserve-plots` implements input / asset reuse,
algorithmic search improvements, Origin readback batching, a single generic
export session, and impact-based validation. See
[OPTIMIZATION_HANDOFF.md](OPTIMIZATION_HANDOFF.md) for the implementation map,
executed checks, known environment failures, and copyable workstation tests.
Native Windows / Origin output comparisons are still pending. The earlier
asset and full-regression results below are historical evidence and do not
establish visual acceptance of this branch.

## Runtime scope

`config/processor_registry.yaml` currently declares 15 supported pipeline
entries:

- photocurrent
- BET
- EPR
- PL
- XPS
- XRD
- UV-vis DRS
- photocurrent_response
- reaction_condition_screening
- FTIR
- Raman
- Mott-Schottky
- HPLC/LC exported data
- HPLC/LC OpenLab raw data
- EIS

SEM, TEM, NMR, MS, and kinetics/reference inputs remain scan-only or
reference-only. The registry, rather than this summary, is authoritative when
the supported set changes.

Formal outputs resolve through the configured output-root policy. On the
current workstation the normal root is the external
`D:\Codex Project\科研数据处理\输出`; project-local generated-output
directories are not production destinations.

## Origin product state

`templates/origin_styles/manifest.json` currently contains 14 accepted Origin
product keys:

- BET
- EIS
- EPR
- FTIR
- Mott-Schottky
- photocurrent
- PL
- Raman
- Tauc
- UV-vis DRS
- XPS_in_situ
- XPS_non_in_situ
- XRD
- XRD_no_card

Every product retains both supported routes:

1. A manifest-bound fixed `.otpu` route for the reviewed curve/layer shape.
   Each current fixed route has fresh-project, same-data, save/reopen, native
   600 dpi, manual-preview, and exact decoded-pixel evidence.
2. A manifest-bound adaptive `.oth` + JSON route for current data identities
   and data shapes. Each current adaptive route has its own accepted evidence;
   acceptance is route-specific and does not imply that every adaptive product
   is pixel-identical to the fixed reference.

Reference OPJU files are retained as isolated style evidence and recovery
assets. They are not runtime graph bases or data sources. The confirmed-invalid
historical `graph_templates/BET.otpu` was removed after its accepted replacement
`BET_verified_20260813.otpu` became the sole BET fixed-template runtime asset.
Older audit documents may still mention the former path as historical evidence.

The EIS adaptive route is the important non-pixel-exact case. Its controlled
same-input run passed current X/Y and row-range readback, per-plot style,
legend, axis, save/reopen, native 600 dpi, and manual PNG inspection, but its
decoded pixels were not identical to the fixed-template replay. The fixed EIS
OTPU route remains the exact-replay route. No threshold was relaxed to call the
adaptive comparison exact.

XRD has two native-Origin products. `XRD` handles sample curves plus one
provided standard-card stick plot; `XRD_no_card` handles sample-only curves.
Their fixed routes preserve the reviewed layouts, while the adaptive routes
handle valid variable sample counts without raster overlays or synthetic
layout filler.

Detailed asset roles, contracts, and acceptance evidence are authoritative in
the manifest and the referenced files under:

- `templates/origin_styles/binding_contracts/`
- `templates/origin_styles/validation_plans/`
- `templates/origin_styles/validation_evidence/`

## XRD data processing

The `codex/xrd-data-optimization` branch is an ancestor of the current
`master`; its data-only Jade/PDF candidate-analysis work was integrated by
merge commit `ca095d1`. This module is separate from Origin plotting and does
not require a graph test when only its data-processing behavior changes.

XRD card matching remains candidate-only. It must record the selected local
database/card source, matches, alternatives, and manual-review requirements.
It does not automatically prove phase purity, hkl assignments, quantitative
phase fractions, or absence of impurities.

## Safety and interpretation boundaries

- Raw data, user templates, and locked result packages remain read-only.
- Origin is started only for explicit plotting work, and task-owned instances
  are closed by code.
- Successful Origin products must be saved, reopened, read back, and natively
  exported as 600 dpi TIFF plus PNG preview.
- High-risk scientific conclusions remain governed by
  `config/claim_policy.yaml` and require manual review.
- A file's presence, an old `accepted` label, or a self-replay is not
  independent asset validation.

## Validation

Latest final verification on 2026-08-24:

- Targeted cleanup/style-contract tests: 196 passed and 9 subtests passed.
- Final full regression: 1186 passed, 3 skipped, and 59 subtests passed.
- `validate`: all dependency, registry, Origin contract, claim-policy, and
  14-asset integrity checks passed. The command still exits 1 only because
  user PPT files remain under the repository-local
  `output/组会PPT_20260808/`; they were not deleted or moved.
- `readiness`: 21 checks, 1 failure, 17 warnings, `ready=false`, and
  `release_ready=false`. The failure is the current validation report; the
  warnings are missing or stale operational queue/review artifacts. No rule
  was weakened to make the report green.

Follow the impact-based validation matrix in `AGENTS.md` section 10. During
development run the affected tests and compare the affected data or figures.
Run the full suite and applicable project checks once before integrating a
complete optimization batch, not after every small commit. Record unrelated
pre-existing failures without expanding the task to fix them:

```powershell
python -m pytest
python run.py validate
python run.py readiness --no-desktop-review-xlsx
```

The validate and readiness commands must run in that order. Plot-format changes also
require the affected formal Origin run and actual PNG inspection; data-only or
documentation-only changes do not.
