# JEOL EPR Decode Skill Integration 2026-06-02

## Source Skill

- Skill: `D:\CodexData\.codex\skills\jeol-epr-decode\SKILL.md`
- Reference behavior: JEOL JES-FA/JES-X3 `cAcqu`, CH1 float32 from offset 9500, 65536 raw points averaged into 4096 exported points.

## Implemented In Project

- Extended `src/core/epr_jeol.py` with skill-compatible data-only Excel export.
- Added optional reference Excel comparison workbook generation.
- Added CLI command: `D:\Python\python.exe run.py jeol-epr-decode --out <out_dir> <raw_epr_folder>`.
- Existing EPR no-Origin processor path continues to decode verified JEOL files to project rows.

## Safety

- Header is checked before export.
- Non-`cAcqu` JEOL-like files are not silently processed.
- Output workbook has two numeric columns and no header row.
- No radical assignment or reaction mechanism claim is generated.
- No raw/workspace/F-drive data was modified by this integration.

## Verification

- `D:\Python\python.exe -m pytest tests\test_jeol_epr_decode.py -q`: 7 passed, 2 warnings.
- `D:\Python\python.exe -m pytest`: 252 passed, 29 warnings.
- `D:\Python\python.exe run.py deps-audit`: exit 0.
- `D:\Python\python.exe run.py validate`: exit 0.
