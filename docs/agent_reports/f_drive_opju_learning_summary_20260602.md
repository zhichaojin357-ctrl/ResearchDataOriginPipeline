# F-drive OPJU Exemplar Learning Summary

Source scanned read-only: `F:\课题\LL\检测`

No F-drive files were modified. OPJU inspection used temporary copied projects under `output/reports/opju_learning_tmp`, then those temporary copies were removed.

## OPJU Coverage

- Total OPJU files found: 60
- Data families with processed OPJU exemplars:
  - BET: 2
  - EPR: 1
  - PL: 1
  - XPS/VBXPS: 8
  - XRD: 10
  - Reaction screening / calibration: 9
  - Photocurrent response: 3
  - UV-vis DRS: 2
  - Raman: 4
  - FTIR: 3
  - Mott-Schottky: 11
  - EIS: 6
- Data families without local OPJU in this backup scan:
  - SEM
  - TEM
  - NMR
  - LC/HPLC reports
  - MS

## Learned Processing And Plotting Methods

### XRD

- Evidence: OPJU near `.raw`, `.TXT`, `.dql`, `.jip`, `.bc`, and exported `.tif`.
- OPJU inspection example: `CWO+BOBC+标卡.opju` uses Graph pages `Graph1` to `Graph4`; `Graph4` has X title `2θ (degree)`, Y title `Intensity (a.u)`, X range `5..80`, line width `3`, and multiple overlaid curves.
- Processing: prefer exported numeric tables when available; treat `.raw/.dql/.jip/.bc` as probe/reference metadata unless a validated reader is available.
- Plotting: intensity versus `2θ`, stacked/offset overlays allowed, reference-card sticks only when supplied/verified.

### Photocurrent / Photocurrent Response

- Evidence: CHI-style `.txt` plus `.bin`; headers include `Amperometric i-t Curve`, `Time/sec`, `Current/A`, `Sample Interval`, and `Run Time`.
- Processing: read exported text first; keep raw time-current; derive current density only when electrode area is supplied; light-cycle intervals are candidates only.
- Plotting: `Time (s)` versus `Current` or current density with numeric Y ticks and subtle light on/off markers.

### EIS

- Evidence: `.z/.txt` ZPlotW exports with `Freq(Hz)`, `Z'`, `Z''`; `.lst` LEVM reports; ZView `FitResult` `.TXT`; `.xlsm` summaries.
- Processing: separate measured spectra from supplied fit curves and parameters; sort Bode by frequency; preserve fit provenance.
- Plotting: Nyquist `-Z''` versus `Z'`; optional Bode panels; numeric ticks; no automatic equivalent-circuit conclusion.

### Mott-Schottky

- Evidence: CHI-style `.csv/.bin`; headers include `Potential/V`, `Z'/ohm`, `Z''/ohm`, `Z/ohm`, `Phase/deg`, and fixed `Frequency`.
- Processing: use supplied capacitance or `1/C^2` when present; otherwise derive only with explicit frequency/formula provenance; fit interval remains manual-check unless supplied.
- Plotting: `1/C^2` versus potential with numeric ticks; frequency labels in legend; no CB/VB conversion.

### Reaction Screening And Calibration

- Evidence: OPJU folders for catalyst screening, solvent screening, cycling, radical trapping, time sampling, and standard curves.
- Processing: treat OPJU workbooks as processed summaries when no source tables are present; do not infer best condition or mechanism automatically.
- Plotting: categorical bars/connected plots with numeric Y ticks; calibration uses raw standard points and Origin linear fit rules.

### Raman

- Evidence: LabRAM `.txt` exports with acquisition headers and two-column spectra.
- Processing: preserve raw spectra and acquisition metadata; baseline/normalization must be recorded; raw and corrected traces stay distinct.
- Plotting: intensity versus Raman shift; consistent crop ranges; hidden numeric Y ticks only for normalized/offset overlays.

### PL

- Evidence: OPJU plus zip folders containing `.txt`, `.FS`, and `.wmf`; text headers identify emission/excitation scans.
- Processing: separate emission and excitation scans by metadata; prefer exported `.txt` unless `.FS` reader is validated.
- Plotting: wavelength-intensity spectra, separate panels/layers or explicit legend labels for scan type/fixed wavelength.

### FTIR

- Evidence: `.dpt` files are two-column numeric tables, often descending wavenumber, with `.0/.pdf/.tif` companions.
- Processing: read `.dpt`; convert transmittance to absorbance only when requested and formula is recorded.
- Plotting: response versus wavenumber; descending wavenumber convention; Y numeric labels only hidden for stacked arbitrary-unit comparisons.

### UV-vis DRS

- Evidence: OPJU and `.tif` exports; some folders lack text source tables.
- Processing: if only image/OPJU exists, treat as exemplar or linked result, not automatically processable raw data; derive Tauc only with formula provenance.
- Plotting: raw DRS and Tauc both keep quantitative ticks unless deliberately offset.

### BET

- Evidence: OPJU near `.SMP`, `.XLS`, `.DB3`, `.DB3-journal`, and reports.
- Processing: prefer exported `.XLS`; keep `.DB3/.SMP` as vendor data until a validated parser exists.
- Plotting: adsorption/desorption line+symbol isotherms and pore-size distribution with numeric axes.

### EPR

- Evidence: OPJU plus JEOL zip/raw folders and verified Excel exports; project has validated JEOL decode to 4096-point Excel.
- Processing: prefer verified `.xlsx` exports or validated JEOL decode output; keep sample/condition/time metadata as labels only.
- Plotting: magnetic field versus intensity; hidden numeric Y ticks allowed for stacked/normalized comparisons; no radical assignment.

### XPS / VBXPS

- Evidence: OPJU plus `.VGD`, `.vgp`, and exported `.xls/.xlsx`; fitted folders contain raw/background/envelope/component/residual structures.
- Processing: use exported fit tables or parsed VGD grids; keep each role distinct; descending binding-energy axis.
- Plotting: raw, background, envelope, components, and residuals with role-specific styles; no automatic valence, species, charge-transfer, or mechanism assignment.

### SEM/TEM/NMR/MS/LC Reports

- Evidence: SEM/TEM are mostly image/raw packages; NMR is Bruker-style folders; MS is `.d/AcqData`; LC is mostly reports.
- Processing: scan-only/reference unless validated exported numeric readers exist.
- Plotting: image panels or chromatograms only from validated source/export data; no scientific interpretation from reports/images.

## Skill Update

Updated `D:\CodexData\.codex\skills\origin-plotting\SKILL.md` with:

- A local exemplar-derived processing map.
- Data-type-specific processing and plotting rules learned from F-drive OPJU/data adjacency.
- Hard invariants for Graph4 geometry, axis-box length, axis/border thickness, curve width, Arial bold text, and fixed font sizes:
  - X/Y axis titles: `36`
  - X tick labels: `28`
  - Y tick labels: `36`
  - Legend: `26`
  - Manual annotations/direct labels/equations: `26`
  - Axis/border thickness: `3`
  - Sample curve line width: `3`

## Plot Primitive And Y-Axis Tick Policy Added

The skill now includes an explicit table for each data family covering:

- default graph primitive;
- marker/symbol rule;
- whether to show the Y-axis line and tick marks;
- whether to show numeric Y-axis tick labels;
- special notes for fitted curves, right axes, category axes, image panels, and forbidden scientific claims.

The default graph primitive is a starting point, not a limit. If the OPJU exemplar or actual data clearly uses another scientific plot type, the plotting workflow should use that actual type and record the reason. Recognized plot families include line, scatter, line+symbol, column/bar, grouped/stacked column, box, lollipop, chromatogram, stick spectrum, heatmap/matrix, contour, semilog decay, Bode log-frequency plots, dual-axis graphs, multi-layer graphs, fitted-component overlays, reference-card stick layers, image panels, EDS maps, calibration scatter with equation annotation, and schematic energy-level diagrams.

Summary:

| Data family | Default graph primitive | Y axis/ticks | Y numeric tick values |
|---|---|---|---|
| XRD | line; stacked/offset line for comparisons | show | hide only for offset/normalized arbitrary-unit overlays |
| Raman | line | show | hide only for normalized/offset overlays |
| FTIR | line | show | show for transmittance/absorbance; hide for stacked arbitrary-unit overlays |
| PL | line; separate emission/excitation panels when needed | show | hide only for normalized/offset overlays |
| TRPL | line, often semilog Y | show | show unless deliberately offset |
| UV-vis DRS | line | show | show for reflectance/absorbance/F(R) |
| Tauc | scatter or line+symbol plus optional linear guide | show | show |
| EIS Nyquist | point-line or scatter+line | show | show |
| EIS Bode | point-line with log-frequency X | show | show |
| Photocurrent | line | show | show |
| Mott-Schottky | point-line or scatter+fit guide | show | show |
| BET isotherm | line+symbol | show | show |
| BET pore distribution | line or line+symbol | show | show |
| EPR | line; stacked/offset line for comparisons | show | hide only for normalized/offset overlays |
| XPS survey/high-resolution | line | show | hide for stacked/offset/baseline-shifted arbitrary-unit display |
| XPS fitted components | multi-line overlay | show | usually hide for arbitrary/offset fitted display |
| VBXPS | line plus optional supplied leading-edge guide | show | hide only for offset/normalized display |
| Reaction screening | column/bar or connected categorical plot | show | show |
| Cycling | column/bar or point-line | show | show |
| Radical trapping/quenching | column/bar or connected categorical plot | show | show |
| Calibration | scatter or line+symbol for raw standards | show | show |
| HPLC/LC chromatogram | line | show | show |
| HPLC/LC peak summary | column/bar/lollipop | show | show |
| SEM/TEM/EDS panels | image/map panel | hide graph axes | hide |
| NMR exported spectrum | line | show | show unless offset stacked |
| MS spectrum/chromatogram | stick spectrum or line chromatogram | show | show |
| Energy-level diagram | schematic or quantitative level diagram | show only for quantitative axis | show only when quantitative values are supplied |
