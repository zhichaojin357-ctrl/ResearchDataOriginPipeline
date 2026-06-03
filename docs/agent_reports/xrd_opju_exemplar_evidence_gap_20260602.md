# XRD OPJU Exemplar Evidence and Gap Report

Date: 2026-06-02
Scope: XRD only. No EPR/XPS files were edited. F-drive and workspace_data raw files were read only.

## 2026-06-03 Status Update

This earlier gap report is now closed by `output/reports/xrd_opju_exemplar_comparison_20260602.md`.
The focused BWO XRD Origin run produced two project OPJU/TIF/PNG result sets and the comparison report records `PASS` for both XRD items. The old "no current XRD project-generated OPJU/PNG/TIF" statement below is retained as historical context only and is no longer the current state.

Current verified generated XRD evidence:

- `output/origin_files/XRD_xrd_bwo_a_q_817dee06aa36.opju`
- `output/origin_files/XRD_xrd_bwo_m_q_e5ff93abb2a4.opju`
- `output/figures_tif/XRD_xrd_bwo_a_q_cbd7e65c.tif`
- `output/figures_tif/XRD_xrd_bwo_m_q_1e789e1f.tif`
- `output/figures_preview/XRD_xrd_bwo_a_q_cbd7e65c.png`
- `output/figures_preview/XRD_xrd_bwo_m_q_1e789e1f.png`

Current remaining work for this report family is cleanup only: remove temporary XRD job scripts after confirming the generated outputs and comparison reports remain intact.

## OPJU evidence found

| Evidence | Path | Evidence from this run |
|---|---|---|
| Human XRD OPJU, raw BWO overlay | `F:\课题\LL\检测\XRD\BWO\BWO.opju` | Binary OPJU strings include `Graph1`, `\b( A BWO)`, `\b( M BWO)`, `\b(Intensity (a.u))`; SHA256 `797F576E48C8FEB01581C7CDCC794C750655D9F85BBE2DACE46CEA64AC24DBBB`. |
| Human XRD OPJU, KIT-6 overlay | `F:\课题\LL\检测\XRD\KIT-6\kit-6.opju` | Binary OPJU strings include `Graph1`, `\b( KIT-6 (1))`, `\b( KIT-6 (2))`, `\b(Intensity (a.u.))`; SHA256 `841B2CDF55A8EA5380F005F2165888A0521CD166CC44C742C2BA662506B51FB9`. |
| Human XRD OPJU with standard-card residue risk | `F:\课题\LL\检测\XRD\CWO+BOBC\CWO+BOBC+标卡.opju` | Binary OPJU strings include `Angle cwo`, `Angle BOBC`, `2θ CWO标准卡片`, `JCPDS card No.04-009-6293`, and `\b( BiCu-15)`; SHA256 `7C5A5CDDC099D6975C6EE4C79C8818FE3F68FC77874C4A192DC89F30183FDE89`. This file is a residue/reference-card guard, not an automatic phase target. |
| Human XRD TIF | `F:\课题\LL\检测\XRD\CWO+BOBC\cwo+bobc\XRD2.tif` | 3390 x 2380 RGB, 300 dpi, SHA256 `61B411831C6C6EA2D3E2DC2DC20BBB76C94CA271B3611826507DBB72D85C6986`. |
| Human XRD TIF | `F:\课题\LL\检测\XRD\KIT-6\kit-6.tif` | 4972 x 4102 RGB, 600 dpi, SHA256 `2533B5E99B6B651E2BE4EF645348D4D18D7FFA93434E232565DF3159390DBC15`. |

## Current project-generated XRD evidence

Exact search under `output/processed_data/XRD`, `output/origin_files`, `output/origin_jobs`, `output/figures_preview`, and `output/figures_tif` found no current XRD project-generated OPJU/PNG/TIF. `output/opju_exemplar_regression/copied_exemplar_manifest.json` previously contained 8 exemplar types and no XRD item; this run added two BWO XRD reference-copy entries and a focused validation queue.

## Code-side comparison against exemplar rules

- Raw pattern: project adapter now selects only raw XRD intensity/counts/y/signal columns for plotting.
- Peak candidates: `peak_candidate_flag` remains in processed CSV only and is excluded from Origin plot CSV.
- Reference-card stick layer: not plotted automatically. Columns containing `reference`, `standard`, `JCPDS`, `PDF`, `hkl`, `phase`, `plane`, `标卡`, `标准卡`, `晶面`, or `物相` are excluded from automatic XRD plot columns.
- Plot primitive: XRD policy remains `line` / Origin plot code `200`. No default `reference_card_stick_layer` is emitted.
- Y axis: XRD keeps Y axis and tick marks but hides Y numeric tick values for arbitrary-unit/offset-style patterns.
- Forbidden claims: no phase assignment and no crystal-plane assignment are emitted by XRD processor or plot policy.
- Template residue: the Origin helper already clears extra layers and asserts against residual `BiCu`, `JCPDS`, `04-009`, and `card` text when it runs. This still needs a live Origin run to prove on XRD output.

## Files prepared for main-thread Origin comparison

| Prepared file | Purpose |
|---|---|
| `output/opju_exemplar_regression/input/XRD/xrd_bwo_a.txt` | Copied XRD raw-pattern input from `F:\课题\LL\检测\XRD\BWO\A BWO.TXT`; SHA256 `D43E75F3F9C4FE1700DAF363EE24F27B8A95EC4DF60231B51B4DC80E00CB81E8`. |
| `output/opju_exemplar_regression/input/XRD/xrd_bwo_m.txt` | Copied XRD raw-pattern input from `F:\课题\LL\检测\XRD\BWO\M BWO.TXT`; SHA256 `49F9826129EB97B4EC9336925E1F7326403931FE76187A532DA1927FCF67A0E9`. |
| `output/opju_exemplar_regression/reference_opju/xrd_bwo.opju` | Copied human BWO reference OPJU. |
| `output/opju_exemplar_regression/reference_opju/xrd_cwo_bobc_standard_card_residue_guard.opju` | Copied standard-card OPJU used only as a template-residue guard. |
| `output/reports/xrd_opju_exemplar_validation_queue_20260602.json` | Focused, two-item XRD queue for main-thread real-Origin generation. |

## Main-thread commands required

Run these only from the main thread that controls real Origin:

```powershell
D:\Python\python.exe run.py process --input output\opju_exemplar_regression\input --from-queue output\reports\xrd_opju_exemplar_validation_queue_20260602.json --with-origin --only-type XRD --force
D:\Python\python.exe scripts\maintenance\opju_exemplar_regression.py --queue output\reports\xrd_opju_exemplar_validation_queue_20260602.json --processing-report output\reports\processing_report.json --output-json output\reports\xrd_opju_exemplar_comparison_20260602.json --output-md output\reports\xrd_opju_exemplar_comparison_20260602.md --export-reference
```

## Remaining gap

This worker did not start real Origin, so the missing end-to-end evidence is not fully closed. The gap is now narrowed to one explicit comparison run: generated XRD OPJU/PNG/TIF from the two BWO copied inputs versus the human BWO OPJU graph export, plus residue checks against the standard-card OPJU.
