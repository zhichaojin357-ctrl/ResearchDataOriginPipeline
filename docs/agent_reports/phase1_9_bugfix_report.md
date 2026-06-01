# Phase 1.9 Bugfix Report

## Fixed High-impact Issues

1. EIS common CHI-style aliases
   - Added support for `Z'/ohm`, `Z"/ohm`, unicode prime variants, and `Freq/Hz` style headers.
   - Added regression test: `test_eis_accepts_common_chi_z_prime_and_z_double_prime_headers`.

2. Mott-Schottky capacitance matching
   - Replaced broad `c` substring fallback with strict capacitance aliases.
   - `Current/A` is no longer treated as capacitance.
   - Explicit rows without `1/C^2` or capacitance now produce an empty Mott table instead of falling back to unrelated numeric pairs.
   - Added regression test: `test_mott_schottky_does_not_treat_current_as_capacitance`.

3. XPS residual handling
   - `Residuals`, residual/difference/error columns are excluded from XPS component area calculations.
   - Added regression test: `test_xps_residuals_are_not_treated_as_fit_components`.

4. Metadata algorithm provenance
   - Metadata now records processor name, calculation module, processed headers, candidate methods, fit point count, and fit regions where available.
   - Added regression test: `test_metadata_records_algorithm_provenance_for_candidate_calculations`.

5. Spectral package-backed processing
   - Raman/PL/FTIR now add optional pybaselines ASLS baseline and corrected-intensity candidate columns when available.
   - Local peak candidates use `scipy.signal.find_peaks` when available with the existing local-neighbor fallback.
   - Added regression test: `test_spectral_processors_add_optional_pybaselines_corrected_signal`.

6. XPS Origin script compile guard
   - Fixed indentation in the generated direct Origin XPS Python script.
   - Added regression test: `test_direct_origin_xps_generated_script_compiles`.

7. XPS in-situ Origin pseudo-success guard
   - `_try_write_origin_project` now checks OPJU and Origin preview PNG existence/non-empty size after Origin export.
   - Missing artifacts now return `ok=false` and write an Origin error record.
   - Added regression test: `test_origin_export_reports_failure_when_expected_artifacts_are_missing`.

## Verification

- `D:\Python\python.exe -m pytest tests\test_processor_behaviors.py tests\test_phase1_9_governance.py`: 45 passed.
- `D:\Python\python.exe -m pytest tests\test_xps_heterojunction_stacked.py tests\test_xps_in_situ.py -q`: 15 passed.
- `D:\Python\python.exe -m py_compile src\processors\calculations.py src\processors\base.py src\core\metadata.py src\core\phase1_9.py src\core\xps_in_situ.py src\core\xps_heterojunction.py`: passed.

## Deferred Larger Items

- Real VGD, BET proprietary DB3/SMP, Bruker EPR, Bruker NMR, vendor MS AcqData, XRD RAW/DQL, and LEVM LST adapters need more real sample-specific fixtures before entering automatic processing.
- GPL or expert-system packages remain reference-only and are not imported in the automatic processing path.
