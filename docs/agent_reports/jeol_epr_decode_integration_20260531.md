# JEOL EPR Decode Integration

- Skill reviewed: `D:\CodexData\.codex\skills\jeol-epr-decode`
- Project integration: added a native JEOL JES-FA/JES-X3 `cAcqu` decoder for EPR files without extensions.
- Scope: decode verified `cAcqu` CH1 binary data to a two-column field-intensity table for the existing EPR processor.
- Safety: unsupported JEOL process types are not silently processed; EPR radical assignment remains forbidden.
- Origin: no Origin processing is started by this integration or its tests.
- Raw data: no raw data or F-drive backup files are modified.

## Files Changed

- `src/core/epr_jeol.py`
- `src/processors/base.py`
- `src/core/triage.py`
- `config/processor_registry.yaml`
- `docs/method_cards/epr.md`
- `tests/test_jeol_epr_decode.py`

## Expected Effect

- No-extension JEOL `cAcqu` EPR files in EPR/ESR folders can be recognized during triage.
- Verified files can be processed through the existing no-Origin EPR processor path.
- Non-`cAcqu` JEOL-like files remain blocked for manual review or explicit decoder extension.

## Read-Only Workspace Probe

- Workspace checked: `workspace_data/LL_detection_copy_20260530`
- JEOL-like no-extension EPR files found by header: 40
- Verified `cAcqu` files: 40
- Unsupported or failed JEOL-like files: 0
- Example verified files:
  - `EPR/20260410-3/BC-O3-dark`
  - `EPR/20260410-3/BC-O3-light1`
  - `EPR/20260410-3/BC-OH-dark`

## Verification

- `D:\Python\python.exe -m pytest -q tests\test_jeol_epr_decode.py tests\test_processor_behaviors.py`: 32 passed
- `D:\Python\python.exe -m pytest -q tests\test_phase1_7_triage_recognition.py tests\test_processor_profiles.py tests\test_phase1_contracts.py`: 27 passed, 2 warnings
- `D:\Python\python.exe -m pytest`: 136 passed, 2 warnings
- `D:\Python\python.exe run.py validate`: exit 0
- `D:\Python\python.exe run.py deps-audit`: exit 0
