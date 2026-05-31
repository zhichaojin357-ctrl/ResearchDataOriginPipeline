# License Risk Notes

Scope: dependency planning only. This project must not copy third-party source code into the repository. All third-party use should happen through installed packages, small adapter modules, or manual/external-tool references.

## License Preference

Preferred licenses for Phase 1 dependencies:

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

The conservative Phase 1 core dependency draft is:

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

- Missing optional dependencies produce warnings, not failures.
- Optional imports should live behind adapters or lazy import checks.
- Optional libraries must not expand Phase 1 scope. For example, an EIS fitting library does not permit automatic equivalent-circuit fitting in Phase 1.
- Optional packages that parse proprietary vendor formats should only be enabled after format-specific tests and license review.

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
- `impedance`
- `pyimpspec`
- `DearEIS`
- `ixdat`
- `galvani`
- `eclabfiles`
- `pyGAPS`
- `lmfitxps`
- `RamanSPy`
- `RamPy`
- `SpectroChemPy`
- `hplc-py`
- `rainbow-api`
- `MOCCA`
- `EPyR Tools`
- `cwepr`
- `eprpy`
- `CustomXepr`
- `absorption_tauc_plot`
- `xrdfit`
- `pymzML`
- `Pyteomics`
- `matchms`
- `nmrglue`
- `HyperSpy`
- `eXSpy`

`scikit-image` is commonly BSD-licensed and suitable as a future optional candidate, but SEM/TEM image analysis remains deferred regardless of license.

## Practical Implementation Guardrails

- Store third-party package checks in `deps-audit` output with version and license fields.
- Add tests that optional missing packages do not break Phase 1.
- Add tests that forbidden scientific claims are not emitted when optional libraries produce fitted values.
- Keep all high-risk outputs as candidates with `manual_check_required: true`.
