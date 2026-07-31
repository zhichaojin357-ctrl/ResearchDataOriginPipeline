# License Risk Notes

Scope: dependency planning only. This project must not copy third-party source code into the repository. All third-party use should happen through installed packages, small adapter modules, or manual/external-tool references.

## License Preference

Preferred licenses for the current automated pipeline dependencies:

- MIT
- BSD-2-Clause / BSD-3-Clause
- Apache-2.0
- Python Software Foundation-style licenses

These licenses are generally compatible with a Python automation project when used as dependencies. Even for preferred licenses, record the package name, version, license, and source URL in the dependency audit output once implementation begins.

## GPL And Copying Rule

GPL, LGPL, AGPL, unclear, or custom academic licenses need explicit review before use.

Rules:

- Do not copy third-party source code, algorithms, tables, examples, or bundled scripts into this repo.
- Do not vendor package files.
- Do not translate GPL source into local project code.
- If a GPL-family package is useful, treat it as an optional external tool until the project owner approves the license impact.
- If a package license cannot be verified quickly, mark it `needs_verification` and keep it out of core dependencies.

## Core Dependency Risk

The conservative the current automated pipeline core dependency draft is:

- `pandas`: BSD-3-Clause; low license risk.
- `numpy`: BSD-3-Clause; low license risk.
- `scipy`: BSD-3-Clause; low license risk.
- `openpyxl`: MIT; low license risk.
- `PyYAML`: MIT; low license risk.
- `pybaselines`: BSD-3-Clause; low license risk.
- `pywin32`: PSF-style license; low license risk for Windows COM automation.
- `originpro`: license metadata needs verification; also requires installed OriginPro. Use only as an automation interface and do not redistribute OriginPro components.

## Optional External-Tool Handling

Optional dependencies must remain optional:

- Missing optional dependencies do not break unrelated commands. A selected
  file-format command may fail explicitly when its required extra is absent.
- Optional imports should live behind adapters or lazy import checks.
- Optional libraries must not expand the current automated pipeline scope. For example, an EIS fitting library does not permit automatic equivalent-circuit fitting in the current automated pipeline.
- Optional packages that parse proprietary vendor formats should only be enabled after format-specific tests and license review.

## Current EIS/EPR/XPS Adapter Decisions

- `impedance` 1.7.1 reports MIT metadata, but the formal EIS processor does not call it. `src.adapters.eis_impedance_adapter` and `draft_fit_eis_randles_cpe` are retained only for separately approved diagnostic/manual-review work.
- `pyimpspec` 5.1.3 reports GPLv3 metadata and remains reference-only/import-smoke. It must not be placed in the default automated EIS processing path without explicit owner approval.
- `cwepr` 0.5.1 reports BSD metadata and `eprpy` 0.9.0b2 reports MIT metadata. They may support EPR candidate metrics through `src.adapters.epr_adapter`, with radical assignment still blocked.
- `vgd-reader` 0.1.0 reports MIT metadata and may parse Thermo VGD XPS spectra through `src.adapters.xps_vgd_reader_adapter`; parsed spectra remain unassigned XPS tables.
- `lmfitxps` 4.2.0 reports an MIT package license with internal third-party license caveats, including GPL text for some background implementations. The current adapter uses import/provenance and existing-curve summarization only; do not call background or fitting routines in automatic the current automated pipeline output without a focused license and method review.

## Current BET Adapter Decision

- `pyGAPS` 4.6.1 reports MIT metadata and is allowed only through `src.adapters.bet_pygaps_adapter`.
- The adapter may construct a `PointIsotherm` candidate from exported relative-pressure/loading rows and record provenance.
- the current automated pipeline must not call pyGAPS BET fitting, pore-size modeling, material classification, or any automatic adsorption interpretation.
- If pyGAPS is unavailable or construction fails, the BET processor falls back to the exported-table parser and keeps only table-derived candidate values.

## Current Local Import Audit

- Available with permissive or acceptable metadata in `D:\Python\python.exe`: `impedance`, `ixdat`, `pyGAPS`, `nmrglue`, `tifffile`, `Pillow`, `vgd-reader`, `MOCCA2`, `pymzML`, `pyteomics`, `cwepr`, `eprpy`, and narrow `lmfitxps` import/provenance use.
- Reference-only or non-default because of GPL/unclear license boundaries: `pyimpspec`, `galvani`, `eclabfiles`, and `hplc-py`.
- `rainbow-api` is an LGPL command-specific dependency for the maintained OpenLab raw-data export. It is not imported by unrelated commands, and the OpenLab command must fail explicitly if it is absent or too old.
- Not importable in the current `D:\Python\python.exe` environment and not used by the main flow: `ramanspy`, `rampy`, `spectrochempy`, and `matchms`. `matchms` is blocked for the current automated pipeline because its dry-run would change core numpy/scipy versions.

## Origin Tools And Manual References

OriginPro is already installed on the target machine. This project may test Python/COM automation and may save `.opju` files and export `.tif` figures through Origin.

License boundaries:

- Do not install OriginPro.
- Do not redistribute OriginPro files, app source, templates, or proprietary examples unless the project owner provides explicit permission.
- Treat Origin XPS Area and Origin XPS Line apps as optional/manual references for the user, not embedded project dependencies.
- If Origin app behavior is referenced in documentation, cite it as manual workflow guidance rather than copied implementation.

## Packages Needing License Verification

The following candidates should remain optional until package metadata and project terms are verified:

- `originpro`
- `pyimpspec` (verified GPLv3; reference-only unless approved)
- `DearEIS`
- `ixdat`
- `galvani`
- `eclabfiles`
- `lmfitxps` advanced fitting/background routines
- `RamanSPy`
- `RamPy`
- `SpectroChemPy`
- `hplc-py`
- `rainbow-api`
- `MOCCA`
- `EPyR Tools`
- `CustomXepr`
- `absorption_tauc_plot`
- `xrdfit`
- `pymzML`
- `Pyteomics`
- `matchms`
- `nmrglue`
- `HyperSpy`
- `eXSpy`

`scikit-image` is commonly BSD-licensed and suitable as a future optional candidate, but the current image metadata adapter uses only Pillow/tifffile and SEM/TEM image analysis remains deferred regardless of license.

## Practical Implementation Guardrails

- Store third-party package checks in `deps-audit` output with version and license fields.
- Add tests that optional missing packages do not break the current automated pipeline.
- Add tests that forbidden scientific claims are not emitted when optional libraries produce fitted values.
- Keep all high-risk outputs as candidates with `manual_check_required: true`.
