# Data Format Note: MS / 质谱 Scan-Only

## Phase 1 Classification
- Inferred data type: `MS`
- Supported in Phase 1: `false`
- Selected processor: `none`
- Special handling: `scan_only`
- Deferred reason: `ms_deferred`

## Common File Formats
- `.mzML`, `.mzXML`, `.mgf`, `.raw`, `.d`, `.wiff`, `.csv`, `.txt`, `.xlsx`, `.pdf`
- Exported peak lists or instrument reports.

## Automatic Recognition Signals
- Folder/name keywords: `质谱`, `MS`, `LC-MS`, `GC-MS`, `HRMS`, `mass spectrum`.
- Header keywords in exported tables: `m/z`, `intensity`, `retention time`, `RT`.
- Vendor raw directory/file patterns.

## Phase 1 Handling
1. Register file paths, extensions, size, and hashes in inventory output.
2. Preserve vendor raw directories as source records.
3. Mark processing status as deferred.
4. If `.mzML` or exported CSV exists, note that a future LC-MS/MS processor may be enabled.
5. Do not plot or identify products in Phase 1.

## Manual Checks Required
- Confirm ionization mode, adducts, calibration, and instrument type.
- Confirm exact mass, isotope pattern, and MS/MS evidence manually.
- Confirm product identity manually.

## Forbidden Actions and Claims
- Do not assign products automatically.
- Do not confirm molecular formula.
- Do not process proprietary raw files.
- Do not call Origin for MS data in Phase 1.
