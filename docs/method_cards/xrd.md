# Method Card: XRD

## Common File Formats
- `.csv`, `.txt`, `.xlsx`, `.xls`, `.dat`, `.xy`
- Exported two-column diffraction data.

## Automatic Recognition Signals
- Folder/name keywords: `XRD`, `x-ray diffraction`, `2theta`, `2θ`.
- Header keywords: `2theta`, `2θ`, `angle`, `intensity`, `counts`.
- Numeric pattern: angle range commonly between 0 and 90 degrees with intensity values.

## Basic Processing Flow
1. Read diffraction table.
2. Detect 2theta/intensity columns.
3. Sort by 2theta and remove empty rows.
4. Optionally normalize intensity when configured.
5. When explicitly requested, search a configured local Jade/PDF XID/SID/RID database and output reference-card match candidates.
6. Record database stem, card identifiers, matched/unmatched peaks, alternatives, tolerance, and candidate score.
7. Plot single or stacked patterns in Origin only when separately requested.
8. Save processed CSV, `metadata.json`, card-candidate JSON, and any separately requested Origin artifacts.

## Automatic Calculations Allowed
- Ordinary XRD processing retains the established local-neighbour peak
  candidates; the explicit `xrd-analyze` path uses parameterized
  `scipy.signal.find_peaks` candidates and records its provenance.
- Local Jade/PDF reference-card candidate ranking with traceable card identifiers and peak deviations.
- Relative intensity normalization.
- Basic smoothing only if explicitly configured and reported.

## Recommended Origin Plot Type
- Line plot: intensity versus 2theta.
- Stacked line plot for multiple samples.
- Standard-card overlay: the reviewed fixed-shape `XRD.otpu` path, with current
  data and card peaks bound as native Origin worksheet plots.
- No-card overlay: exactly nine curves use the reviewed
  `XRD_no_card.otpu`; other positive curve counts use the retained adaptive
  `XRD_no_card.oth` plus explicit JSON/style replay. Both paths rebuild labels
  from current data and do not load a reference OPJU as the product base.

## Manual Checks Required
- Confirm wavelength/source and scan range.
- Confirm background subtraction or smoothing choices.
- Confirm candidate peaks, database provenance, card identifiers, match tolerances, alternatives, and any reference pattern comparison.
- Confirm phase identity, phase purity, and crystal-plane assignments manually using independent evidence.

## Forbidden Claims
- Do not automatically label crystal planes.
- Do not claim no impurity phase automatically.
- Do not infer crystallinity mechanism.

## Required Metadata Fields
- `dataset_id`, `data_type`, `subtype`, `source_files`, `source_hash`
- `processor_name`, `processing_status`, `plot_type`
- `origin_template_used`, `origin_file`, `figure_tif`, `processed_data`
- `manual_check_required`, `manual_check_items`, `forbidden_claims`
- `warnings`, `parameters`, `key_results`, `confidence_level`
- Extra recommended fields: `x_axis_unit`, `normalization`, `peak_detection_parameters`, `radiation_source`

## the current automated pipeline Implementation Status
- Supported in the current automated pipeline.
- Planned processor: `xrd_processor`.
- Data-only direct command: `python run.py xrd-analyze --source <export> --database-dir <jade-dir> --card-query <formula> --output-root <external-output>`.
- Binary vendor `.raw` files are detected but remain unsupported; use instrument-exported TXT/CSV/XY/XLSX.
- J7 XID/SID/RID decoding currently has strict synthetic regression coverage;
  until the user's licensed local database is compared with a trusted exported
  card, decoder intensities and all rankings remain explicitly candidate-only.

## Risk Level
- Medium-high. Database-backed reference-card rankings are candidates only; phase identity, purity, quantitative fractions, crystallite size, strain, and crystal-plane interpretation remain manual.
