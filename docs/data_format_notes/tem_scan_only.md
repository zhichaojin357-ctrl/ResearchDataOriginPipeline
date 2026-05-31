# Data Format Note: TEM Scan-Only

## Phase 1 Classification
- Inferred data type: `TEM_image_data`
- Supported in Phase 1: `false`
- Selected processor: `none`
- Special handling: `scan_only`
- Deferred reason: `image_data_deferred`

## Common File Formats
- `.tif`, `.tiff`, `.jpg`, `.jpeg`, `.png`, `.bmp`
- Instrument formats such as `.dm3`, `.dm4`, `.ser`, `.emi` may appear but are not parsed in Phase 1.

## Automatic Recognition Signals
- Folder/name keywords: `TEM`, `HRTEM`, `透射电镜`.
- Image extensions and filenames containing lattice, SAED, EDS, scale, or magnification hints.

## Phase 1 Handling
1. Register file paths, extensions, size, and hashes in inventory output.
2. Preserve directory structure.
3. Mark processing status as deferred.
4. Do not call Origin and do not create processed image outputs.

## Manual Checks Required
- Confirm TEM/HRTEM image type and scale.
- Confirm lattice-fringe measurement manually.
- Confirm SAED/EDS handling is outside Phase 1.

## Forbidden Actions and Claims
- Do not assign lattice fringes or crystal planes.
- Do not perform image enhancement, segmentation, or particle analysis.
- Do not infer morphology, defects, or mechanism automatically.
