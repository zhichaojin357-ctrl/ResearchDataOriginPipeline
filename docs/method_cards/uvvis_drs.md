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
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `input_signal_type`, `tauc_transition_type`, `linear_region_candidates`, `Eg_candidate_eV`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `uvvis_drs_processor`.

## Risk Level
- High. Calculation candidates are allowed; final `Eg` and mechanism require manual review.
