# Data Format Note: SEM Scan-Only

## the current automated pipeline Classification
- Inferred data type: `SEM_image_data`
- Supported in the current automated pipeline: `false`
- Selected processor: `none`
- Special handling: `scan_only`
- Deferred reason: `image_data_deferred`

## Common File Formats
- `.tif`, `.tiff`, `.jpg`, `.jpeg`, `.png`, `.bmp`
- Instrument exports such as `.dm3`, `.dm4`, `.ser`, or vendor project folders may appear but are not parsed in the current automated pipeline.

## Automatic Recognition Signals
- Folder/name keywords: `SEM`, `扫描电镜`.
- Image extensions or instrument-image metadata.
- Filenames containing magnification, scale bar, voltage, detector, or sample name.

## the current automated pipeline Handling
1. Register file paths, extensions, size, and hashes in inventory output.
2. Preserve directory structure.
3. Mark processing status as deferred.
4. Do not call Origin and do not create processed data or figures.

## Manual Checks Required
- Confirm images are SEM rather than TEM or optical images.
- Confirm scale bars, magnification, and detector metadata manually.
- Confirm any morphology or particle-size claims manually.

## Forbidden Actions and Claims
- Do not perform particle analysis.
- Do not segment morphology.
- Do not infer sample structure or performance from images.
- Do not alter original images.
