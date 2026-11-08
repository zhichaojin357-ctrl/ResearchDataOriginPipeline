# GC calibration reuse

| Component | Reuse | Scope |
|---|---|---|
| openpyxl | Existing OOXML reader | Read-only XLSX/XLSM selected blocks; no Excel authoring |
| shared linear_regression / linear_r_squared | Existing project calculations | No new regression algorithm |
| OriginOperations / connect_origin | Existing maintained COM adapter | Fresh project, worksheet, graph, native legend, save/reopen/export |
| Graph4FixedStyle | Existing fixed style contract | Fresh graphs; no template asset modification |
| runtime_paths / file_utils / project | Existing output routing and path safety | External, unique output directory; no overwrite |
| Pillow | Existing image reader | TIFF pixel and DPI verification |

The fixed-data HPLC regression script is not used as a GC production entrypoint. No extra dependencies or downloads are needed.
