# Current Status

The project is maintained as a final runtime pipeline. The active code path is `run.py` -> `src/cli.py` -> `src/core`/`src/processors`/`src/origin`.

The latest full codebase audit is
[`CODEBASE_AUDIT_2026-07-31.md`](CODEBASE_AUDIT_2026-07-31.md).

## Active Scope

- Scan and classify characterization data.
- Build triage and reviewed queues.
- Process supported numeric data into normalized CSV plus `metadata.json`.
- Generate OriginPro products, save `.opju`, export 600 dpi `.tif`, and write preview/report artifacts.
- Keep uncertain or high-risk interpretation as manual-review fields.

## Output Root

All formal runs should write under:

```text
D:\Codex Project\科研数据处理\输出
```

Project-local `output/` is not the default runtime destination.

## Supported Runtime Types

The processor registry currently supports 15 maintained pipeline entries:

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
- HPLC/LC OpenLab raw data (dedicated raw-to-Excel command)
- EIS

SEM, TEM, NMR, MS, and kinetics/reference folders remain scan-only.

## Origin Requirements

- Use OriginPro through the formal Origin modules.
- Use template-backed plotting when a template exists.
- Save `.opju`, reopen that final project read-only, and natively export the target graph as a 600 dpi `.tif`.
- Validate the TIFF tag, both pixel dimensions, and effective DPI against the reopened Origin page dimensions; retagging or interpolating a smaller raster is not accepted.
- Do not write full source paths, Codex labels, or comments into OPJU-facing workbook names/comments.
- For template conformance work, a current run must provide strict one-to-one comparison evidence, not only cached or manual-check artifacts.

Project-local `reference_opju` files may be opened only from isolated copies as
independent visual/style evidence. They are not product bases or data sources.
Historical batch-derived `.otpu` files are quarantined and are not runtime
fallbacks. Runtime `.otpu` dispatch is manifest-driven. The current individually
regenerated and independently validated products are BET, EIS, EPR, PL,
photocurrent, XRD with a standard card, and the fixed nine-curve XRD no-card
layout. The XRD no-card product retains an adaptive OTH+JSON route for every
other positive curve count.

## Latest Origin Audit

- The earlier 12/12 pixel-identical replay used byte-identical source and
  project-local reference OPJUs. It is now classified as 12
  `reference_opju_self_replay` results (deterministic export evidence), with
  zero independent style-asset matches. It does not validate `.oth` behavior
  on a newly constructed graph.
- The latest all-types Origin run produced all required OPJU/TIFF/PNG/data/
  metadata/report artifacts, and every TIFF passed native physical 600 dpi and
  metadata-path checks.
- BET, EIS, and EPR now have accepted detached `.otpu` runtime packages with
  explicit X/Y binding contracts and fresh-project same-data exact-pixel
  evidence. EIS
  also passed a separate real-data formal run on 2026-08-22: 8 plots, 101 points
  per plot, current labels, OPJU save/reopen, style conformance, native 600 dpi
  TIFF, and manual PNG inspection, without loading a reference OPJU.
- PL now has an accepted detached runtime bundle requiring the manifest-bound
  `.otpu`, `.oth`, and style snapshot together. Its reviewed mapping is
  `A→B` rows 1–351, `A→D` rows 1–176, and `A→F` rows 1–351. The project formal
  replay passed 59/59 style checks, save/reopen, native 600 dpi export, and
  same-data TIFF comparison with zero decoded-pixel difference (RMS 0). The
  separate real-data product did not load a reference OPJU; its no-label/path
  audit had 0 hits, and its 4190×2806 TIF matched the reference replay TIF with
  zero decoded-pixel difference.
- Photocurrent now has an accepted detached runtime asset requiring the
  manifest-bound `.otpu` and style snapshot (no `.oth`). The formal same-data
  replay passed 59/59 style checks, save/reopen, native 600 dpi export, and
  zero decoded-pixel difference. Its separate real-data product used fresh
  graph creation with `reference_opju_loaded=false`, independent `A→B`,
  `C→D`, and `E→F` mappings (2600 points per curve), 1 pt curves, 16 pt
  non-bold dynamic axis titles, and native 600 dpi export; this run is not
  claimed to be pixel-identical to the reference data.
- The other historical `.otpu` files remain quarantined. Their `.oth` products
  have not inherited BET/EIS/EPR/PL/photocurrent acceptance and must be validated
  one type at a time; do not describe the complete all-types set as visually
  accepted.
- A controlled XRD trial using the OPJU directly as the product base was
  rejected: workbook-column mismatch produced flat curves and overlapping
  labels despite a higher style-field match ratio.
- The fixed-data HPLC calibration regression reproduced all three reviewed
  source-OPJU PNGs exactly (3216 x 2461; zero changed pixels), while the source
  OPJU hash remained unchanged. The transaction-safe first run and explicit
  force rerun also decoded to zero changed pixels and left no Origin process.
  This evidence is scoped only to that controlled calibration helper.
- EPR passed both independent asset and current-data runtime gates on
  2026-08-22. The fresh-project replay used the exact reference 4096-by-3 data
  and shared-X mapping, matched 59/59 style fields, and changed zero decoded
  pixels. A separate verified-JEOL OH run generated a new OPJU from the accepted
  OTPU/OTH/snapshot package without loading the reference OPJU; save/reopen X/Y
  readback matched, current bold `BC`/`CWO`/`BOBC` labels persisted at the
  reviewed positions, the native 3859 x 2953 TIFF was approximately 600
  physical dpi, and the PNG was inspected with no old template labels.
- XRD with a standard card now starts from a fresh Origin project and the
  accepted `XRD.otpu`, binds current sample/card worksheets as native Origin
  plots, replaces current annotations, saves/reopens the OPJU, and exports a
  native 600 dpi TIFF without loading the reference OPJU. Its same-data formal
  replay changed zero decoded pixels, and the separate real-data PNG was
  inspected with one bold X title, one bold Y title, three current sample
  curves, and the current standard card.
- XRD without a standard card now has two detached native-Origin paths:
  exactly nine curves use `XRD_no_card.otpu`; every other positive count uses
  `XRD_no_card.oth` plus the explicit style/label contract. Both same-data
  validations changed zero decoded pixels. A separate nine-file real-data run
  created nine worksheet-bound curves and current direct labels, loaded no
  reference OPJU, saved/reopened the OPJU, passed the native 600 dpi TIFF gate,
  and passed manual PNG inspection.
- The last full test run passed 844 tests with 3 skips. `validate` exits 0.
  `readiness` reports 21 checks, 0 failures, 15 warnings, `ready=true`, and
  `release_ready=false`.

Do not call the current all-types product set visually accepted or
release-ready. Do not lower the comparison threshold merely to make it green.

## Validation Commands

```powershell
python -m pytest
python run.py validate
python run.py readiness --no-desktop-review-xlsx
```

For plot-format changes, additionally run the relevant formal Origin commands and inspect their reports under the generated run root in `输出\runs`.

`readiness.summary.ready` is the compatibility signal for zero hard failures.
Release decisions use `readiness.summary.release_ready`, which additionally
requires zero warnings.
