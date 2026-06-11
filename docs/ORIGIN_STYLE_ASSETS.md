# Origin Style Assets

## Project-local style package root

The accepted template-format graph styles are stored inside the project:

```text
templates/origin_styles/
```

Current assets:

- `templates/origin_styles/manifest.json`
- `templates/origin_styles/graph_templates/*.otpu`
- `templates/origin_styles/previews/*.png`

The manifest has one accepted asset for each plotted type:

- BET
- XPS_in_situ
- XPS_non_in_situ
- XRD
- EPR
- EIS
- Raman
- UV-vis DRS / Tauc
- PL
- photocurrent
- FTIR

## Current implementation status

Implemented:

- 11 accepted template-format graph pages exported as project-local `.otpu` Graph Template files.
- `templates/origin_styles/manifest.json` records product key, data type, graph page, source run, source product OPJU, and preview comparison metadata.
- `src.origin.style_registry.resolve_origin_style_asset()` resolves a product key or data type to the project-local style package.
- `run.py export-origin-style-assets` can regenerate the package from a reviewed accepted template-format run.

Boundary:

- The current one-to-one product path is still OPJU template-base workbook replacement, because that preserves the original workbook, graph page, fills, labels, and layer object structure.
- The `.otpu` files are now the project-local style source for discovery/fallback when external OPJU exemplars are unavailable.
- Full no-OPJU product generation from `.otpu` still has to create a new graph from the template, bind processed data, export a preview, and pass visual comparison before one-to-one status can be claimed.

## Dependency boundary

Future style discovery no longer needs the original F-drive OPJU exemplars or the output-run `reference_opju` copies. Code should resolve project-local style packages through:

```python
from src.origin.style_registry import resolve_origin_style_asset
```

The OPJU-template path remains available for full workbook replacement, but missing external OPJU exemplars should fall back to the project-local `.otpu` style package before blocking.

## Exactness policy

A saved `.otpu` is a style package, not a scientific conclusion and not by itself a final product. Any regenerated product still has to export a preview and pass the template-vs-generated visual audit before one-to-one status can be claimed.

## Regeneration command

```powershell
D:\Python\python.exe run.py export-origin-style-assets --run-root "<output-root>\runs\<accepted-template-format-run>" --with-origin
```
