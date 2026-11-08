# Method Card: UV-vis DRS

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`
- Exported wavelength-reflectance or wavelength-absorbance spectra.

## Automatic Recognition Signals
- Folder/name keywords: `固体紫外`, `UV`, `UV-vis`, `DRS`, `diffuse reflectance`.
- Header keywords: `wavelength`, `nm`, `reflectance`, `R%`, `%R`, `absorbance`, `Kubelka`.
- Numeric pattern: wavelength range typically in UV-visible region.

## Basic Processing Flow
1. Read exported wavelength-signal table.
2. Detect reflectance or absorbance representation.
3. Convert `R%` to fractional `R` when explicit.
4. Calculate Kubelka-Munk `F(R)=(1-R)^2/(2R)` for reflectance input.
5. Calculate photon energy `hν=1239.7/λ`.
6. Generate DRS and Tauc candidate data, then plot in Origin.
7. Save `.opju`, 600 dpi `.tif`, processed CSV, and `metadata.json`.

## Automatic Calculations Allowed
- Kubelka-Munk transform from explicit reflectance data.
- Photon energy conversion.
- Tauc ordinate candidate for configured transition type.
- Candidate linear ranges and `Eg_candidate`, flagged for manual review.

## Recommended Origin Plot Type
- Line plot: reflectance/absorbance or `F(R)` versus wavelength.
- Tauc plot: transformed ordinate versus photon energy.

## Manual Checks Required
- Confirm whether input is reflectance, absorbance, or already transformed.
- Confirm transition type used for Tauc plot.
- Confirm selected linear region and bandgap candidate.
- Confirm baseline/scattering artifacts.

## Forbidden Claims
- Do not automatically confirm final band gap.
- Do not infer band structure or photocatalytic mechanism.
- Do not generate final energy-band diagram automatically.

## Required Metadata Fields
- `dataset_id`, `data_type`, `source_files`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `input_signal_type`, `tauc_transition_type`, `linear_region_candidates`, `Eg_candidate_eV`

## Current Implementation and Entrypoints

- Registered table processor: `uvvis_drs_processor`, using `src/core/table_reader.py`
  and `src/processors/calculations.py`.
- Hitachi U-3900 wavelength-scan TXT is supported: only the `Data Points` block
  is read; the preceding peak table is not spectrum data. `nm / Abs` is absorbance,
  not reflectance. UDS companions are retained as instrument originals and are
  not decoded or counted as additional spectra.
- Multi-file Origin products use `_build_template_uvvis_table` in
  `src/core/template_product_builder.py` and the formal `template-format-products`
  executor. Each spectrum keeps its own X/Y pair, source order and all negative
  absorbance values. No smoothing, normalization, baseline correction or
  interpolation is applied. Legends retain the filename stem, including `%`
  and Unicode; no material identity is inferred from abbreviations.
- The reviewed `UV_vis_DRS_Tauc.opju` Graph1 is the DRS style authority; Graph2
  is the separate Tauc authority. Runtime assets are resolved from the current
  manifest. Ordinary four-sample input uses the accepted adaptive OTH+JSON route,
  rather than filling a fixed template with duplicate/reference curves.

### Four-sample LL example

From the repository root, use the explicit file list in
`examples/ll_drs_pairing.json`. The example data live in `ll-drs/ll`.
Use a Python environment containing the project dependencies. On the current
Windows workstation, `D:\Python\python.exe` was verified; the unqualified
`python` command may instead select an unrelated application's Python.
The output root defaults to the configured external output directory; an
explicit `--output-root` must also remain outside the source tree and inputs.

```powershell
# Actual processing and CSV/metadata/report output, without starting Origin.
python run.py template-format-products --pairing examples/ll_drs_pairing.json --only-type "UV-vis DRS" --asset-only --compact-output

# Actual Origin plot, saved/reopened OPJU, native 600 dpi TIF and PNG preview.
python run.py template-format-products --pairing examples/ll_drs_pairing.json --only-type "UV-vis DRS" --asset-only --compact-output --with-origin
```

Do not add `--timestamp` with an already used value: each invocation writes a
new run under the output root. Check the command summary and `metadata.json`;
the data-only invocation does not claim a completed Origin export. Inspect the
final PNG before accepting visual output.

The template-product command reports overall **plot** acceptance. Without
`--with-origin` it writes the real CSV/metadata/report, then reports `blocked`
and exit code 1 because the graph artifacts are absent; this does not mean the
CSV parsing failed. Use `--with-origin` for the completed plotting workflow.

All four LL TXT files report `Data Mode: Abs` and contain negative absorbance.
Keep these values visible and review the instrument baseline/reference before
quantitative interpretation. This example requests DRS only, with wavelength
and absorbance axes. It does not request a Tauc fit or bandgap. The existing
Tauc calculation currently produces a direct-transition squared-ordinate
candidate; other transition types and a reviewed fitting interval must not be
assumed from this example.

### One project with a three-sample DRS graph and two-sample Tauc graph

`examples/ll_drs_tauc_pairing.json` selects BOB, BVO and one 7.5% scan for
DRS, with explicit legend names `BOB`, `BVO`, `BV-7.5%`. Only BOB and BVO
enter Tauc. Optional `legend_entries` must name every explicitly paired file
in its listed order; it changes display names and headers, not numeric data.

```powershell
python run.py template-format-products --pairing examples/ll_drs_tauc_pairing.json --only-type "UV-vis DRS / Tauc" --asset-only --compact-output --with-origin --uvvis-bundle
```

`--uvvis-bundle` reuses the two accepted template products, appends their native
graphs into `bundle/DRS_Tauc.opju`, and draws native dashed tangent objects.
The combined project is saved and reopened; both complete X/Y datasets and
row ranges are checked against the current CSVs. Final TIF/PNG exports come
from this reopened combined project, with the linked sample legends retained.
The [Origin document-append command](https://docs.originlab.com/labtalk/guide/managing-the-project/)
is used; the reference OPJU is not the product base.

The Tauc entry must supply `tauc_fit_intervals_eV` keyed by current sample
names and a nonempty `tauc_fit_note`. Fits use at least five actual points,
positive slope, R² >= 0.98 and a positive X intercept below the fitted interval.
The supplied LL intervals are BOB 3.02–3.18 eV and BVO 2.50–2.65 eV, chosen
from the rising absorption edges. They are explicit analysis choices, not
universal intervals for future samples. Gap candidates, slope, intercept,
R², point count and provenance are saved in the bundle metadata/report.
Both raw spectra and transformed data remain editable; the Tauc display is
focused on 2–4 eV. Negative absorbance and the squared-transition assumption
are recorded as interpretation limits. No final band-edge positions are inferred.

### Confirmed percent-transmission exports

The general processor continues to reject automatic interpretation of `%T`.
For a user-confirmed transmission measurement, an explicit pairing field
`"transmittance_conversion": "percent_to_absorbance_log10"` enables the
existing template workflow to calculate `A=-log10(T_percent/100)` before the
squared Tauc transform. Percent units must be explicit in the source headers;
nonpositive or nonfinite wavelength/transmittance is rejected. The spectrum
page retains the original percent values with `Transmittance (%)` as its Y
title. No Kubelka–Munk conversion is applied to these transmission data.

The complete conversion, including signed absorbance, is retained in the
combined OPJU and `Transmission_conversion_*.csv`. Values above 100% are kept
and produce negative absorbance. In that case, a squared-transform intercept
is only a mathematical candidate; reference/baseline validity and the
transition model still require review. No clipping, sign reversal, smoothing
or baseline subtraction is performed.

The bundle may also specify `bundle_plot_styles`, keyed by the explicitly
listed sample names, with `rgb: [r,g,b]` (integers 0–255) and `line_style`
(0 solid, 1 dash, 2 dot). Styles apply only to the new combined product, and
line colors/dash styles are read back after save/reopen. For example, BOB may
use yellow, BVO pink, and BV-7.5% pink dashed, retaining linked native legends.

## Risk Level
- High. Calculation candidates are allowed; final `Eg` and mechanism require manual review.
