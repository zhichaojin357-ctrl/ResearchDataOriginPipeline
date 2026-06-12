# Data Format Note: NMR / 核磁 Scan-Only

## the current automated pipeline Classification
- Inferred data type: `NMR`
- Supported in the current automated pipeline: `false`
- Selected processor: `none`
- Special handling: `scan_only`
- Deferred reason: `nmr_deferred`

## Common File Formats
- `.fid`, `.ser`, `.mnova`, `.jdx`, `.dx`, `.csv`, `.txt`, `.pdf`
- Vendor folders from Bruker, Agilent/Varian, JEOL, or processed spectrum exports.

## Automatic Recognition Signals
- Folder/name keywords: `核磁`, `NMR`, `1H`, `13C`, `H NMR`, `C NMR`.
- Filenames containing solvent, nucleus, frequency, or sample identifiers.
- Vendor subfolders such as `pdata`, `fid`, or acquisition parameter files.

## the current automated pipeline Handling
1. Register file paths, extensions, size, and hashes in inventory output.
2. Preserve folder structure and vendor subfolders.
3. Mark processing status as deferred.
4. Do not process, integrate, phase-correct, or plot spectra.

## Manual Checks Required
- Confirm nucleus, solvent, reference peak, and processing state.
- Confirm integration and peak assignments manually.
- Confirm whether future NMR support should target raw vendor data or exported spectra.

## Forbidden Actions and Claims
- Do not assign chemical shifts or structures.
- Do not integrate peaks.
- Do not infer purity, conversion, or product identity.
- Do not call Origin for NMR data in the current automated pipeline.
