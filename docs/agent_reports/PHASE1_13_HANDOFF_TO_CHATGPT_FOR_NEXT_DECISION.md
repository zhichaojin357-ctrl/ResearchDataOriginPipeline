# Phase 1.13 Handoff To ChatGPT For Next Decision

## Summary

Phase 1.13 installed and verified optional scientific packages, added lazy adapter modules, compared adapter behavior against current fallback logic, and ran shadow-mode checks on Phase 1.6 processed CSVs only. No raw/workspace/F-drive data was modified and no real Origin export was run.

## Installed / Verified Packages

- `pybaselines` 1.2.1: ok=True, policy=optional adapter, core_default=True
- `scipy` 1.17.1: ok=True, policy=optional adapter, core_default=True
- `impedance` 1.7.1: ok=True, policy=optional adapter, core_default=True
- `Pillow` 12.2.0: ok=True, policy=optional adapter, core_default=True
- `matplotlib` 3.10.8: ok=True, policy=optional adapter, core_default=True
- `pygaps` 4.6.1: ok=True, policy=optional adapter, core_default=True
- `lmfitxps` 4.2.0: ok=True, policy=optional adapter, core_default=True
- `nmrglue` 0.11: ok=True, policy=optional adapter, core_default=True
- `tifffile` 2026.3.3: ok=True, policy=optional adapter, core_default=True
- `scikit-image` 0.26.0: ok=True, policy=optional adapter, core_default=True
- `pyimpspec` 5.1.3: ok=True, policy=GPL reference-only, core_default=False
- `ixdat` 0.3.0: ok=True, policy=optional adapter, core_default=True
- `galvani` 0.5.0: ok=True, policy=GPL reference-only, core_default=False
- `eclabfiles` 0.4.1: ok=True, policy=license unknown reference-only, core_default=False
- `cwepr` 0.5.1: ok=True, policy=optional adapter, core_default=True
- `EPRpy` 0.9.0b2: ok=True, policy=optional adapter, core_default=True
- `hplc-py` 0.2.7: ok=True, policy=GPL reference-only, core_default=False
- `rainbow-api` 1.0.10: ok=True, policy=LGPL optional boundary, core_default=False
- `MOCCA2` 0.1.18: ok=True, policy=optional adapter, core_default=True
- `pymzML` 2.6.0: ok=True, policy=optional adapter, core_default=True
- `pyteomics` 5.0: ok=True, policy=optional adapter, core_default=True
- `matchms` : ok=False, policy=blocked_core_dependency_change, core_default=False

## Blocked

- `matchms`: dry-run would change core `numpy/scipy`, so it was not installed.

## Adapter Modules

- `src/adapters/baseline_adapter.py`
- `src/adapters/peak_detection_adapter.py`
- `src/adapters/eis_impedance_adapter.py`
- `src/adapters/eis_pyimpspec_adapter.py`
- `src/adapters/bet_pygaps_adapter.py`
- `src/adapters/xps_lmfitxps_adapter.py`
- `src/adapters/epr_adapter.py`
- `src/adapters/raman_adapter.py`
- `src/adapters/electrochem_import_adapter.py`
- `src/adapters/hplc_adapter.py`
- `src/adapters/nmr_adapter.py`
- `src/adapters/ms_adapter.py`
- `src/adapters/image_metadata_adapter.py`

## Validation

- pytest: 249 passed, 29 warnings
- deps-audit: exit 0
- validate: exit 0
- readiness --no-desktop-review-xlsx: exit 0
- origin-batch dry-run: exit 0, no Origin launch

## Next Decision

- Decide whether a future Phase 1.14 should use these adapters in a small reviewed no-Origin batch.
- Keep GPL/license-unclear packages reference-only unless the user explicitly approves a separate boundary.
- Use a separate environment for `matchms` if MS similarity workflows become important.
