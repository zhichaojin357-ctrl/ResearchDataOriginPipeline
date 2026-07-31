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
The batch-derived `.otpu` files are quarantined harvest records and are not
runtime fallbacks.

## Latest Origin Audit

- The earlier 12/12 pixel-identical replay used byte-identical source and
  project-local reference OPJUs. It is now classified as 12
  `reference_opju_self_replay` results (deterministic export evidence), with
  zero independent style-asset matches. It does not validate `.oth` behavior
  on a newly constructed graph.
- The latest all-types Origin run produced all required OPJU/TIFF/PNG/data/
  metadata/report artifacts, and every TIFF passed native physical 600 dpi and
  metadata-path checks.
- All 12 products remain `blocked` by the strengthened independent-reference
  visual gate. The current `.oth` products and the reference OPJUs contain
  different data and labels and are not one-to-one pixel matches.
- A controlled XRD trial using the OPJU directly as the product base was
  rejected: workbook-column mismatch produced flat curves and overlapping
  labels despite a higher style-field match ratio.
- The fixed-data HPLC calibration regression reproduced all three reviewed
  source-OPJU PNGs exactly (3216 x 2461; zero changed pixels), while the source
  OPJU hash remained unchanged. The transaction-safe first run and explicit
  force rerun also decoded to zero changed pixels and left no Origin process.
  This evidence is scoped only to that controlled calibration helper.
- The final EPR transaction path was exercised separately after the all-types
  run. Official `jeol-epr-decode` regenerated 24 XLSX/metadata pairs without
  changing the raw-tree hash. The OH overlay then produced OPJU/TIFF/PNG under
  an isolated output root, with hash-matched `mT` evidence and a native
  3859 x 2953 TIFF at approximately 600 physical dpi. Its PNG was inspected.
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
