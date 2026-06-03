# Phase 1.13 Tier 2 Package Decision Report

| Package | OK | Version | Decision | Reason |
|---|---:|---|---|---|
| `ixdat` | True | 0.3.0 | installed_optional_adapter | import smoke passed; no automatic scientific assignment allowed |
| `galvani` | True | 0.5.0 | installed_reference_only | license GPL or unclear; usable only outside core automatic flow |
| `eclabfiles` | True | 0.4.1 | installed_reference_only | license GPL or unclear; usable only outside core automatic flow |
| `cwepr` | True | 0.5.1 | installed_optional_adapter | import smoke passed; no automatic scientific assignment allowed |
| `EPRpy` | True | 0.9.0b2 | installed_optional_adapter | import smoke passed; no automatic scientific assignment allowed |
| `hplc-py` | True | 0.2.7 | installed_reference_only | license GPL or unclear; usable only outside core automatic flow |
| `rainbow-api` | True | 1.0.10 | installed_optional_boundary | LGPL boundary; import/probe only unless future explicit approval |
| `MOCCA2` | True | 0.1.18 | installed_optional_adapter | import smoke passed; no automatic scientific assignment allowed |
| `pymzML` | True | 2.6.0 | installed_optional_adapter | import smoke passed; no automatic scientific assignment allowed |
| `pyteomics` | True | 5.0 | installed_optional_adapter | import smoke passed; no automatic scientific assignment allowed |
| `matchms` | False |  | blocked_core_dependency_change | dry-run would install/downgrade numpy and scipy; violates Phase 1.13 core dependency guard |
