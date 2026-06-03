# Next Function Fix Order

Audit time: 2026-06-03 15:36:34 +08:00.

This document is a future fix-order plan only. Do not fix drawing features, add features, delete files, or commit during the current整理 phase.

## Universal Rule Before Any Future Function Fix

Every future plotting/data-type fix must satisfy all of these before it can be called complete:

1. The change is merged into a formal code/config path, not left only in a temporary script.
2. The result is regenerated from the intended raw input, copied validation input, or reviewed queue, not patched manually.
3. The regenerated result has the expected processed CSV/metadata/OPJU/TIF/PNG artifacts where applicable.
4. The generated output is compared against the relevant OPJU exemplar or report contract when one exists.
5. The git diff is reviewed and limited to the intended code/config/test/report scope.
6. Verification commands are recorded with exit codes and report paths.
7. The fix does not auto-assign forbidden scientific conclusions.

Do not bulk-process `MANUAL_REVIEW`. Do not use raw `output/reports/processing_queue.json` as the next input.

## Priority Order

### P0. Worktree And Output整理

Status: current phase.

Reason: dirty worktree and output clutter are now the highest risk. Continuing data-type fixes before staging policy is clear will make the repo harder to recover.

Acceptance:

- Dirty worktree groups are agreed.
- Output layout cleanup policy is agreed.
- Script deletion/replacement is decided.
- Next commit scope is selected but not mixed with large output artifacts.

### P1. XPS OPJU Exemplar Gap

Reason: current status audit did not find a clear completed XPS OPJU-exemplar comparison report. Existing XPS outputs/QC are not the same as OPJU exemplar regression.

Future acceptance:

- Identify the exact user OPJU exemplar(s) and copied local reference path.
- Export reference graph pages into the regression reference area.
- Run the formal XPS path from explicit input or reviewed queue.
- Confirm generated OPJU/TIF/PNG and metadata exist.
- Compare graph intent: fitted/raw route, page/graph target, curve roles, reversed binding-energy axis, component/background/envelope/residual policy, labels, y-axis numeric label policy, forbidden claims.
- Add/adjust tests in the formal source path if defects are found.
- Provide git diff and commands.

### P2. Raman OPJU Warning

Reason: `phase1_14_opju_exemplar_regression_comparison` reports 8 total, 7 PASS, and 1 `WARNING_OPJU_CONTRACT_DELTA`; the warning item is Raman.

Future acceptance:

- Re-read the Raman warning reason and reference exports.
- Decide whether this is a real contract failure or an accepted style delta.
- If real, fix formal Raman/Origin plot path, not the comparison helper only.
- Regenerate from the Raman exemplar input.
- Re-run OPJU comparison and show PASS or documented accepted warning.
- Confirm no automatic defect assignment.

### P3. BET Formalization And Visual Acceptance

Reason: BET OPJU logic appears improved, with generated outputs and tests, but visual acceptance is still needed and some BET reference/compare trials are mixed in output folders.

Future acceptance:

- Use formal `process --with-origin` or reviewed queue route, not manual COM repair.
- Regenerate BET isotherm output from source/copy.
- Confirm summary-only BET tables do not produce single-point plots.
- Confirm adsorption/desorption isotherm uses relative pressure and branch columns.
- Confirm OPJU/TIF/PNG exist, TIF is 600 dpi, and preview is visually acceptable.
- Confirm pore-distribution plots are only produced when real pore-size distribution columns exist.

### P4. EPR Overlay Contract

Reason: EPR overlay now has a formal command and Phase 1.14 comparison PASS, but future work should keep the overlay contract stable.

Future acceptance:

- Use `run.py epr-overlay`, not raw single-trace process output, when the exemplar is an OH/O3 condition overlay.
- Confirm OH and O3 overlay OPJUs/TIFs/PNGs exist.
- Confirm baseline subtraction, smoothing, normalization, and background subtraction policies are stated in the report.
- Confirm no radical/mechanism assignment.
- Confirm JEOL 4096-point decode rule applies only to verified JEOL cAcqu raw decode, not to every overlay input.

### P5. XRD Contract Is Currently Lower Priority

Reason: current XRD BWO OPJU comparison reports PASS for two items, and cleanup report says remaining XRD origin job files are gone.

Future acceptance for any new XRD fix:

- Run from raw XRD input or focused validation queue.
- Confirm no reference-card/stick layer is drawn unless explicit current standard-card data are supplied.
- Confirm peak candidates stay in processed CSV only unless explicitly required.
- Confirm no phase or crystal-plane assignment.
- Confirm OPJU/TIF/PNG and comparison report pass.

### P6. Remaining Spectral/Electrochemical Types

Reason: PL, FTIR, EIS, Mott-Schottky, photocurrent, and photocurrent_response currently have OPJU comparison evidence or no current priority blocker in the latest status docs. They should wait until P0-P3 are settled.

Future acceptance:

- Use formal process/queue path.
- Regenerate from intended input.
- Verify expected axes, units, curve roles, and manual-check fields.
- Confirm no forbidden scientific conclusions.
- Add tests only when changing formal behavior.

## Data-Type Acceptance Matrix

| data type | future fix trigger | acceptance focus |
|---|---|---|
| `XPS` | Missing OPJU-exemplar comparison or plot contract defect | OPJU intent, reversed binding-energy axis, raw/background/envelope/component roles, no valence/electron-transfer claim |
| `Raman` | Current OPJU warning | Exemplar comparison PASS or justified warning, peak candidates only, no defect assignment |
| `BET` | Visual acceptance or summary-to-plot regression | Isotherm branch plot, relative pressure x-axis, adsorption/desorption y branches, no summary-only single-point plot |
| `EPR` | Overlay contract change or decode issue | JEOL decode only for verified raw files, OH/O3 overlay route, no radical assignment |
| `XRD` | New exemplar or new XRD run | Raw pattern route, no automatic reference card, no phase/plane assignment |
| `EIS` | Nyquist/Bode plotting issue | Correct impedance sign convention, frequency/magnitude/phase handling, no equivalent-circuit conclusion |
| `Mott-Schottky` | Fit/axis issue | Candidate linear interval only, frequency grouping preserved, no CB/VB conclusion |
| `photocurrent` | Cycle/current plotting issue | Time-current units, light-cycle markers if available, no carrier-separation conclusion |
| `photocurrent_response` | OCP/response plotting issue | Time-current response plot, clear units, no carrier-separation conclusion |
| `FTIR` | Baseline/axis/style issue | Wavenumber axis, valley/peak candidates only, no bond assignment |
| `PL` | Emission/excitation plotting issue | Wavelength-intensity route, normalization clear, no recombination conclusion |
| `UV-vis DRS` | DRS/Tauc issue | Kubelka-Munk/Tauc candidate math only, no final bandgap/mechanism claim |
| `HPLC/LC exported data` | Chromatogram/peak table issue | Exported chromatogram or peak table only, no product/conversion without calibration |
| `reaction_condition_screening` | Condition table issue | Conditions and response values only, no final optimized-condition claim |

## Verification Command Pattern For Future Fixes

Use exact commands appropriate to the fix. A complete future fix should include at least:

```powershell
D:\Python\python.exe -m pytest <targeted tests>
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py readiness --no-desktop-review-xlsx
D:\Python\python.exe run.py <formal command used to regenerate the target output>
git diff -- <changed formal paths>
git status --short
```

For Origin-bearing fixes, also include the focused OPJU comparison command/report path and manually inspect the generated PNG preview before claiming visual correctness.

## Not Allowed During Function Fixes

- Do not patch output files manually.
- Do not leave working logic only inside `scripts/one_off` or temporary comparison scripts.
- Do not use `output/reports/processing_queue.json` directly.
- Do not process all `MANUAL_REVIEW`.
- Do not expand scan-only types into processors without explicit approval.
- Do not auto-assign XPS valence, EPR radicals, XRD phases/planes, EIS circuits, MS products, PL recombination, photocurrent carrier separation, or CB/VB positions.
