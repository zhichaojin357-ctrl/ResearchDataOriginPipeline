# HPLC/LC Blockers

Date: 2026-06-04

The no-Origin synthetic HPLC/LC module is complete for automatically verifiable exported-table behavior. The following items remain blocked until the user provides real inputs or changes scope.

## Real Data Blockers

- A real exported HPLC/LC chromatogram is required to validate real chromatogram parsing.
- A real exported peak table is required to validate real integration-table parsing.
- A real exported calibration table is required to validate real calibration provenance.
- Real detector, wavelength, retention-time unit, and response-unit metadata must be confirmed by the user.

## Calibration and Mapping Blockers

- Real conversion requires calibration.
- Real selectivity requires calibration.
- Real yield requires calibration.
- Real concentration requires calibration.
- Product identity requires user-provided analyte mapping or validated standards.
- Substrate/product role mapping requires user confirmation.
- Dilution, volume, concentration, and response-factor rules require user confirmation.

## Raw Format Blockers

- Agilent `.d` raw directories are not decoded.
- Waters `.raw` raw directories are not decoded.
- LC-MS raw files are not decoded.
- Proprietary binary vendor exports are not decoded.

## Origin and Visual Blockers

- Origin was not run in this module completion goal.
- No OPJU, TIF, PNG, PDF, XLSX, ZIP, or visual artifact was generated.
- Real plot visual acceptance requires a separate user-approved Origin or visual QA goal.

## Safety Rule

Until these blockers are resolved, the module must keep all HPLC/LC outputs candidate-level and manual-check gated.
